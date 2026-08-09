"""Gated deletion of explicit leaves or one recursively emptied container."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from typing import Any

from ..cues.refs import CONTAINER_CUE_TYPES
from ..errors import OscTimeoutError, UnsafeWriteOperationError
from .moves import (
    _activity_snapshot,
    _fingerprint,
    _is_descendant,
    _qlab_bool,
    _read_snapshot,
    _uuid_key,
)
from .safety import ensure_write_ready, resolve_dry_run


MAX_BATCH_DELETES = 10
MAX_RECURSIVE_DELETE_DESCENDANTS = 500
DELETE_TOKEN_TTL_SECONDS = 300
DELETE_OPERATION_VERSION = 1
DELETE_CONVERGENCE_DEADLINES_SECONDS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0)
_DELETE_TOKEN_SECRET = secrets.token_bytes(32)
_CONSUMED_DELETE_TOKENS: dict[str, int] = {}
_CONSUMED_DELETE_TOKENS_LOCK = threading.Lock()


def delete_cues(
    reader: Any,
    workspace_id: str,
    cue_ids: list[str] | None = None,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
    *,
    container_id: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    requested_count = _validate_delete_request(cue_ids, container_id, recursive)

    effective_dry_run = resolve_dry_run(reader, dry_run)
    workspace = _resolve_workspace(reader, workspace_id)
    try:
        snapshot, normalized, errors, activity, readiness = _read_delete_state(
            reader, workspace, cue_ids, container_id, recursive
        )
    except Exception as exc:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            failed_count=requested_count,
            results=[],
            errors={"preflight": str(exc)},
            message="Cue delete preflight could not read a complete fresh workspace structure.",
        )

    if errors:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            failed_count=len(errors),
            results=[],
            errors=errors,
            message="Cue delete preflight failed; no mutating OSC commands were sent.",
        )
    if activity["active_count"]:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            failed_count=requested_count,
            results=[],
            errors={"activity": "Workspace has running or paused cues; deletion requires 0 / 0 / 0 activity."},
            message="Cue delete preflight failed because workspace activity is not safely idle.",
        )

    plan = _build_plan(snapshot, normalized, activity, readiness)
    if effective_dry_run:
        return _result(
            ok=True,
            status="planned",
            workspace_id=workspace,
            dry_run=True,
            container_id=container_id,
            recursive=recursive,
            expanded_count=len(plan) if container_id is not None else 0,
            requested_count=requested_count,
            planned_count=len(plan),
            results=plan,
            confirm_token=_encode_token(
                workspace,
                plan,
                container_id=container_id,
                recursive=recursive,
            ),
            warnings=["Dry run only: no mutating OSC commands were sent to QLab."],
            message="Cue delete batch planned; review the dedicated confirmation token before real execution.",
        )

    try:
        ensure_write_ready(reader, workspace)
    except Exception as exc:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"readiness": str(exc)},
            message="Cue delete real execution was rejected before any mutating OSC command.",
        )

    payload, token_error = _decode_token(confirm_token)
    if token_error:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"confirm_token": token_error},
            message="Cue delete real execution was rejected before any mutating OSC command.",
        )

    try:
        (
            fresh_snapshot,
            fresh_ids,
            fresh_errors,
            fresh_activity,
            fresh_readiness,
        ) = _read_delete_state(
            reader, workspace, cue_ids, container_id, recursive
        )
    except Exception as exc:
        fresh_errors = {"preflight": str(exc)}
        fresh_ids = []
        fresh_activity = {"active_count": 0, "active_cue_ids": []}
        fresh_readiness = {}
        fresh_snapshot = None
    if fresh_errors:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors=fresh_errors,
            message="Cue delete dependencies changed before mutation; no delete was sent.",
        )
    if fresh_activity["active_count"]:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"activity": "Workspace activity changed before deletion."},
            message="Cue delete execution was rejected before mutation because activity changed.",
        )
    fresh_plan = _build_plan(fresh_snapshot, fresh_ids, fresh_activity, fresh_readiness)
    if payload.get("binding") != _token_binding(
        workspace,
        fresh_plan,
        container_id=container_id,
        recursive=recursive,
    ):
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            container_id=container_id,
            recursive=recursive,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"confirm_token": "delete confirmation token does not match the fresh workspace plan."},
            message="Cue delete real execution was rejected before any mutating OSC command.",
        )

    try:
        preserved_container_id = (
            _uuid_key(container_id, "container_id") if container_id is not None else None
        )
    except (TypeError, ValueError):
        preserved_container_id = container_id

    if not fresh_plan and container_id is not None:
        # Empty-container deletion is a verified no-op; the root is preserved.
        token_error = _consume_delete_token(confirm_token, payload)
        if token_error:
            return _result(
                ok=False,
                status="preflight_failed",
                workspace_id=workspace,
                dry_run=False,
                requested_count=requested_count,
                planned_count=0,
                failed_count=0,
                results=[],
                errors={"confirm_token": token_error},
                message="Delete no-op token could not be consumed safely.",
            )
        return _result(
            ok=True,
            status="deleted_immediately",
            workspace_id=workspace,
            dry_run=False,
            requested_count=requested_count,
            planned_count=0,
            deleted_count=0,
            results=[],
            container_id=preserved_container_id,
            recursive=True,
            preserved_container_id=preserved_container_id,
            expanded_count=0,
            warnings=["Container was already empty; root was preserved."],
            message="Recursive delete completed as a verified no-op.",
        )

    token_error = _consume_delete_token(confirm_token, payload)
    if token_error:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"confirm_token": token_error},
            message="Cue delete real execution was rejected because its token was already used.",
        )

    return _execute_delete_batch(
        reader,
        workspace,
        fresh_plan,
        requested_count=requested_count,
        preserved_container_id=preserved_container_id,
        container_id=preserved_container_id,
        recursive=recursive,
    )


def _execute_delete_batch(
    reader: Any,
    workspace_id: str,
    plan: list[dict[str, Any]],
    *,
    requested_count: int | None = None,
    preserved_container_id: str | None = None,
    container_id: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    requested_count = len(plan) if requested_count is None else requested_count
    try:
        reader.client.request("/alwaysReply", 1)
    except Exception as exc:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace_id,
            dry_run=False,
            requested_count=requested_count,
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"always_reply": str(exc)},
            message="QLab alwaysReply could not be enabled; no delete was sent.",
        )

    results: list[dict[str, Any]] = []
    deleted_count = 0
    timeout_confirmed_count = 0
    requested_ids = {item["cue_id"] for item in plan}
    unaffected_neighbors = {
        neighbor
        for item in plan
        for neighbor in item["neighbors"]
        if neighbor not in requested_ids
    }

    for index, item in enumerate(plan):
        if _activity_snapshot(reader, workspace_id)["active_count"]:
            return _failure(
                workspace_id, plan, results, deleted_count, index,
                "Workspace activity changed before the next delete.",
                requested_count=requested_count,
                container_id=container_id,
                recursive=recursive,
                preserved_container_id=preserved_container_id,
            )
        address = f"/workspace/{workspace_id}/delete_id/{item['cue_id_osc']}"
        reply_status = "ok"
        reply_data: Any = None
        timeout_error: str | None = None
        try:
            reply = reader.client.request(address, workspace_id=workspace_id)
            reply_status = getattr(reply, "status", "ok")
            reply_data = getattr(reply, "data", None)
        except OscTimeoutError as exc:
            reply_status = "timeout_pending_readback"
            timeout_error = str(exc)
        except Exception as exc:
            try:
                after = _read_snapshot(reader, workspace_id)
                exists = item["cue_id"] in after["nodes"]
            except Exception as readback_exc:
                return _failure(
                    workspace_id, plan, results, deleted_count, index,
                    f"Delete failed and existence readback failed: {readback_exc}",
                    requested_count=requested_count,
                    status="verification_failed",
                    container_id=container_id,
                    recursive=recursive,
                    preserved_container_id=preserved_container_id,
                )
            return _failure(
                workspace_id, plan, results, deleted_count, index,
                str(exc), readback={"exists": exists}, reply_status="error", reply_data=reply_data,
                requested_count=requested_count,
                status="failed" if deleted_count == 0 else "partial_failed",
                container_id=container_id,
                recursive=recursive,
                preserved_container_id=preserved_container_id,
            )

        if reply_status != "ok" and reply_status != "timeout_pending_readback":
            return _failure(
                workspace_id, plan, results, deleted_count, index,
                f"QLab delete reply status was {reply_status!r}.",
                requested_count=requested_count,
                status="failed" if deleted_count == 0 else "partial_failed",
                reply_status=reply_status, reply_data=reply_data,
                container_id=container_id,
                recursive=recursive,
                preserved_container_id=preserved_container_id,
            )
        verification = _poll_delete_convergence(
            reader,
            workspace_id,
            item,
            completed_ids={completed["cue_id"] for completed in results},
            unaffected_neighbors=unaffected_neighbors,
            preserved_container_id=preserved_container_id,
        )
        if not verification["ok"]:
            return _failure(
                workspace_id, plan, results, deleted_count, index,
                verification["error"], status=verification["status"], readback=verification["readback"],
                requested_count=requested_count,
                reply_status=reply_status, reply_data=reply_data,
                verification_status=verification["verification_status"],
                verification_elapsed_ms=verification["elapsed_ms"],
                container_id=container_id,
                recursive=recursive,
                preserved_container_id=preserved_container_id,
            )
        status = (
            "deleted_immediately"
            if verification["verification_status"] == "confirmed_immediately"
            else "deleted_after_convergence"
        )
        results.append({
            **item,
            "status": status,
            "reply_status": reply_status,
            "reply_data": reply_data,
            "reply_data_status": "provisional",
            "readback": verification["readback"],
            "verification_status": verification["verification_status"],
            "verification_elapsed_ms": verification["elapsed_ms"],
            **({"reply_error": timeout_error} if timeout_error else {}),
        })
        deleted_count += 1
        timeout_confirmed_count += int(reply_status == "timeout_pending_readback")

    if _activity_snapshot(reader, workspace_id)["active_count"]:
        return _failure(
            workspace_id, plan, results, deleted_count, len(plan) - 1,
            "Workspace activity changed after deletion.",
            requested_count=requested_count,
            status="verification_failed",
            container_id=container_id,
            recursive=recursive,
            preserved_container_id=preserved_container_id,
        )
    return _result(
        ok=True,
        status=(
            "deleted_after_convergence"
            if any(item.get("status") == "deleted_after_convergence" for item in results)
            else "deleted_immediately"
        ),
        workspace_id=workspace_id,
        dry_run=False,
        requested_count=requested_count,
        planned_count=len(plan),
        deleted_count=deleted_count,
        timeout_confirmed_count=timeout_confirmed_count,
        results=results,
        container_id=container_id,
        recursive=recursive,
        preserved_container_id=preserved_container_id,
        expanded_count=len(plan),
        warnings=["Deletes were executed sequentially and are not atomic."],
        message="Cue delete batch completed with fresh existence readback after every delete.",
    )


def _failure(
    workspace_id: str,
    plan: list[dict[str, Any]],
    results: list[dict[str, Any]],
    deleted_count: int,
    failed_index: int,
    error: str,
    *,
    requested_count: int | None = None,
    status: str = "partial_failed",
    readback: dict[str, Any] | None = None,
    reply_status: str | None = None,
    reply_data: Any = None,
    verification_status: str | None = None,
    verification_elapsed_ms: int | None = None,
    container_id: str | None = None,
    recursive: bool = False,
    preserved_container_id: str | None = None,
) -> dict[str, Any]:
    item = dict(plan[failed_index])
    item.update({"status": status, "error": error})
    if readback is not None:
        item["readback"] = readback
    if reply_status is not None:
        item["reply_status"] = reply_status
        item["reply_data"] = reply_data
        item["reply_data_status"] = "provisional"
    if verification_status is not None:
        item["verification_status"] = verification_status
    if verification_elapsed_ms is not None:
        item["verification_elapsed_ms"] = verification_elapsed_ms
    results.append(item)
    return _result(
        ok=False,
        status=status,
        workspace_id=workspace_id,
        dry_run=False,
        requested_count=len(plan) if requested_count is None else requested_count,
        planned_count=len(plan),
        deleted_count=deleted_count,
        failed_count=len(plan) - deleted_count,
        results=results,
        container_id=container_id,
        recursive=recursive,
        preserved_container_id=preserved_container_id,
        expanded_count=len(plan) if recursive else 0,
        errors={f"cue_ids[{failed_index}]": error},
        warnings=["No automatic rollback was sent; deletion is treated as irreversible."],
        message="Cue delete batch stopped after the first failed or unverifiable deletion.",
    )


def _validate_delete_request(
    cue_ids: list[str] | None,
    container_id: str | None,
    recursive: bool,
) -> int:
    if container_id is not None:
        if cue_ids not in (None, []):
            raise UnsafeWriteOperationError("container_id cannot be combined with cue_ids.")
        if not recursive:
            raise UnsafeWriteOperationError("recursive must be true when container_id is supplied.")
        return 1
    if recursive:
        raise UnsafeWriteOperationError("recursive requires container_id.")
    if not isinstance(cue_ids, list) or not cue_ids:
        raise UnsafeWriteOperationError("cue_ids must include at least one cue UUID.")
    if len(cue_ids) > MAX_BATCH_DELETES:
        raise UnsafeWriteOperationError(f"cue_ids can include at most {MAX_BATCH_DELETES} cue UUIDs.")
    return len(cue_ids)


def _normalize_delete_request(
    snapshot: dict[str, Any],
    cue_ids: list[str] | None,
    container_id: str | None,
    recursive: bool,
) -> tuple[list[str], dict[str, str]]:
    if container_id is None:
        # _validate_delete_request keeps this branch list-shaped for callers.
        return _normalize_delete_ids(snapshot, cue_ids or [])
    try:
        root_id = _uuid_key(container_id, "container_id")
    except (TypeError, ValueError) as exc:
        return [], {"container_id": str(exc)}
    nodes = snapshot["nodes"]
    root = nodes.get(root_id)
    if root is None:
        return [], {"container_id": "container_id does not resolve in this workspace."}
    if str(root.get("type") or "") not in CONTAINER_CUE_TYPES:
        return [], {"container_id": "container_id must identify a Cue List, Group, or Cue Cart."}
    if any(_qlab_bool(root.get(field)) for field in ("isRunning", "isPaused", "isAuditioning")):
        return [], {"container_id": "Active, paused, or auditioning containers cannot be emptied."}
    if not recursive:
        return [], {"recursive": "recursive must be true when container_id is supplied."}
    try:
        expanded = _postorder_descendants(snapshot, root_id)
    except ValueError as exc:
        return [], {"container_id": str(exc)}
    if not expanded:
        return [], {}
    if len(expanded) > MAX_RECURSIVE_DELETE_DESCENDANTS:
        return [], {
            "container_id": (
                f"recursive deletion expands to {len(expanded)} descendants; "
                f"the maximum is {MAX_RECURSIVE_DELETE_DESCENDANTS}."
            )
        }
    for cue_id in expanded:
        cue = nodes[cue_id]
        if any(_qlab_bool(cue.get(field)) for field in ("isRunning", "isPaused", "isAuditioning")):
            return [], {"container_id": "Active, paused, or auditioning descendants cannot be deleted."}
    return expanded, {}


def _postorder_descendants(snapshot: dict[str, Any], root_id: str) -> list[str]:
    tree = snapshot["children_by_parent"]
    ordered: list[str] = []
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(parent_id: str) -> None:
        if parent_id in visiting:
            raise ValueError("Cue tree contains a cycle below container_id.")
        if parent_id in visited:
            return
        visiting.add(parent_id)
        for child_id in tree.get(parent_id, []):
            visit(child_id)
            ordered.append(child_id)
        visiting.remove(parent_id)
        visited.add(parent_id)

    visit(root_id)
    return ordered


def _normalize_delete_ids(snapshot: dict[str, Any], cue_ids: list[str]) -> tuple[list[str], dict[str, str]]:
    nodes = snapshot["nodes"]
    parents = snapshot["parent_by_child"]
    normalized: list[str] = []
    errors: dict[str, str] = {}
    seen: set[str] = set()
    for index, raw_id in enumerate(cue_ids):
        key = f"cue_ids[{index}]"
        try:
            cue_id = _uuid_key(raw_id, f"{key}.cue_id")
            if cue_id in seen:
                raise ValueError("Duplicate cue_id is not allowed in one batch.")
            seen.add(cue_id)
            cue = nodes.get(cue_id)
            if cue is None:
                raise ValueError("cue_id does not resolve in this workspace.")
            cue_type = str(cue.get("type") or "")
            if cue_type in CONTAINER_CUE_TYPES or snapshot["children_by_parent"].get(cue_id):
                raise ValueError("Container cues and cues with children are blocked; delete is leaf-only.")
            if parents.get(cue_id) is None:
                raise ValueError("Top-level cue deletion is blocked.")
            if any(_qlab_bool(cue.get(field)) for field in ("isRunning", "isPaused", "isAuditioning")):
                raise ValueError("Active, paused, or auditioning cues cannot be deleted.")
            normalized.append(cue_id)
        except (TypeError, ValueError) as exc:
            errors[key] = str(exc)

    if not errors:
        for index, cue_id in enumerate(normalized):
            for other_id in normalized[index + 1 :]:
                if _is_descendant(other_id, cue_id, parents) or _is_descendant(cue_id, other_id, parents):
                    errors["batch"] = "A parent and one of its descendants cannot be deleted in one batch."
                    return normalized, errors
    return normalized, errors


def _build_plan(
    snapshot: dict[str, Any],
    cue_ids: list[str],
    activity: dict[str, Any],
    readiness: dict[str, Any],
) -> list[dict[str, Any]]:
    nodes = snapshot["nodes"]
    parent_by_child = snapshot["parent_by_child"]
    tree = snapshot["children_by_parent"]
    tree_fingerprint = _tree_fingerprint(tree)
    plan: list[dict[str, Any]] = []
    for cue_id in cue_ids:
        parent_id = parent_by_child[cue_id]
        siblings = tree[parent_id]
        index = siblings.index(cue_id)
        cue = nodes[cue_id]
        previous_sibling_id = siblings[index - 1] if index else None
        next_sibling_id = siblings[index + 1] if index + 1 < len(siblings) else None
        parent_children_fingerprint = _fingerprint(siblings)
        plan.append({
            "cue_id": cue_id,
            "cue_id_osc": cue["uniqueID"],
            "cue_type": cue.get("type", ""),
            "name": cue.get("name", ""),
            "number": cue.get("number", ""),
            "parent_id": parent_id,
            "neighbors": [sibling for sibling in siblings if sibling != cue_id],
            "previous_sibling_id": previous_sibling_id,
            "next_sibling_id": next_sibling_id,
            "parent_children": list(siblings),
            "parent_children_fingerprint": parent_children_fingerprint,
            "original_index": index,
            "request_index": len(plan),
            "descendant_ids": [],
            "source_health": {
                "is_broken": _qlab_bool(cue.get("isBroken")),
                "is_warning": _qlab_bool(cue.get("isWarning")),
            },
            "activity_snapshot": activity,
            "readiness_snapshot": readiness,
            "tree_fingerprint": tree_fingerprint,
            "deletion_impact_fingerprint": _deletion_impact_fingerprint(
                cue_id, parent_id, siblings, cue_ids
            ),
            "address": f"/workspace/{{workspace_id}}/delete_id/{cue['uniqueID']}",
            "args": [],
        })
    return plan


def _tree_fingerprint(tree: dict[str, list[str]]) -> str:
    return _fingerprint([f"{parent}:{','.join(children)}" for parent, children in sorted(tree.items())])


def _deletion_impact_fingerprint(
    cue_id: str,
    parent_id: str,
    siblings: list[str],
    requested_ids: list[str],
) -> str:
    payload = {
        "cue_id": cue_id,
        "parent_id": parent_id,
        "siblings": siblings,
        "requested_ids": requested_ids,
    }
    return _fingerprint([json.dumps(payload, sort_keys=True, separators=(",", ":"))])


def _readiness_snapshot(reader: Any, workspace_id: str) -> dict[str, Any]:
    config = reader.client.config
    return {
        "workspace_id": workspace_id,
        "write_enabled": bool(getattr(config, "enable_write", False)),
        "passcode_configured": bool(getattr(config, "passcode", None)),
    }


def _poll_delete_convergence(
    reader: Any,
    workspace_id: str,
    item: dict[str, Any],
    *,
    completed_ids: set[str],
    unaffected_neighbors: set[str],
    preserved_container_id: str | None = None,
) -> dict[str, Any]:
    started = time.monotonic()
    last_readback: dict[str, Any] | None = None
    last_error: str | None = None
    previous_deadline = 0.0
    expected_parent_children = [
        cue_id
        for cue_id in item["parent_children"]
        if cue_id not in completed_ids and cue_id != item["cue_id"]
    ]
    for deadline in DELETE_CONVERGENCE_DEADLINES_SECONDS:
        delay = deadline - previous_deadline
        if delay > 0:
            time.sleep(delay)
        previous_deadline = deadline
        try:
            after = _read_snapshot(reader, workspace_id)
            exists = item["cue_id"] in after["nodes"]
            actual_parent_children = after["children_by_parent"].get(item["parent_id"], [])
            missing_neighbors = sorted(
                neighbor for neighbor in unaffected_neighbors if neighbor not in after["nodes"]
            )
            parent_structure_changed = actual_parent_children != expected_parent_children
            preserved_container_exists = (
                preserved_container_id is None or preserved_container_id in after["nodes"]
            )
            last_readback = {
                "exists": exists,
                "preserved_container_exists": preserved_container_exists,
                "missing_unaffected_neighbors": missing_neighbors,
                "parent_children": actual_parent_children,
                "expected_parent_children": expected_parent_children,
            }
            last_error = None
        except Exception as exc:
            last_error = str(exc)
            continue
        if not exists and not missing_neighbors and not parent_structure_changed and preserved_container_exists:
            return {
                "ok": True,
                "readback": last_readback,
                "verification_status": (
                    "confirmed_immediately" if deadline == 0 else "confirmed_after_convergence"
                ),
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
    return {
        "ok": False,
        "status": "indeterminate",
        "readback": last_readback,
        "verification_status": "indeterminate",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "error": last_error or "Deleted UUID did not converge before the 10-second deadline.",
    }


def _resolve_workspace(reader: Any, workspace_id: str) -> str:
    resolver = getattr(reader, "_resolve_workspace_id_strict", None)
    return str(resolver(workspace_id) if resolver else workspace_id)


def _read_delete_state(
    reader: Any,
    workspace_id: str,
    cue_ids: list[str] | None,
    container_id: str | None,
    recursive: bool,
) -> tuple[
    dict[str, Any],
    list[str],
    dict[str, str],
    dict[str, Any],
    dict[str, Any],
]:
    snapshot = _read_snapshot(reader, workspace_id)
    normalized, errors = _normalize_delete_request(
        snapshot,
        cue_ids,
        container_id,
        recursive,
    )
    return (
        snapshot,
        normalized,
        errors,
        _activity_snapshot(reader, workspace_id),
        _readiness_snapshot(reader, workspace_id),
    )


def _token_binding(
    workspace_id: str,
    plan: list[dict[str, Any]],
    *,
    container_id: str | None = None,
    recursive: bool = False,
) -> dict[str, Any]:
    return {
        "version": DELETE_OPERATION_VERSION,
        "operation_version": DELETE_OPERATION_VERSION,
        "workspace_id": workspace_id,
        "container_id": container_id,
        "recursive": recursive,
        "requested_cue_ids": [item["cue_id"] for item in plan],
        "requested_cue_ids_osc": [item["cue_id_osc"] for item in plan],
        "activity_snapshot": plan[0]["activity_snapshot"] if plan else {},
        "readiness_snapshot": plan[0]["readiness_snapshot"] if plan else {},
        "impact_fingerprint": _fingerprint([item["deletion_impact_fingerprint"] for item in plan]),
        "plan": plan,
    }


def _encode_token(
    workspace_id: str,
    plan: list[dict[str, Any]],
    *,
    container_id: str | None = None,
    recursive: bool = False,
) -> str:
    payload = {
        "binding": _token_binding(
            workspace_id,
            plan,
            container_id=container_id,
            recursive=recursive,
        ),
        "expires_at": int(time.time()) + DELETE_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _encode_payload(payload)
    signature = hmac.new(_DELETE_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return f"confirm:deleteCues:v1:{encoded}:{signature}"


def _decode_token(token: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "delete confirmation token is required."
    parts = token.split(":")
    if len(parts) != 5 or parts[:3] != ["confirm", "deleteCues", "v1"]:
        return None, "delete confirmation token is malformed or has an unsupported family."
    encoded, signature = parts[3:]
    expected = hmac.new(_DELETE_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None, "delete confirmation token signature is invalid."
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode())
    except Exception:
        return None, "delete confirmation token payload is invalid."
    if not isinstance(payload, dict) or not isinstance(payload.get("expires_at"), int):
        return None, "delete confirmation token payload is invalid."
    binding = payload.get("binding")
    if not isinstance(binding, dict) or binding.get("operation_version") != DELETE_OPERATION_VERSION:
        return None, "delete confirmation token operation version is unsupported."
    if payload["expires_at"] < int(time.time()):
        return None, "delete confirmation token has expired."
    return payload, None


def _consume_delete_token(token: str | None, payload: dict[str, Any]) -> str | None:
    if not isinstance(token, str):
        return "delete confirmation token is required."
    digest = hashlib.sha256(token.encode()).hexdigest()
    now = int(time.time())
    expires_at = int(payload.get("expires_at", 0))
    with _CONSUMED_DELETE_TOKENS_LOCK:
        for consumed, expiry in list(_CONSUMED_DELETE_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_DELETE_TOKENS[consumed]
        if digest in _CONSUMED_DELETE_TOKENS:
            return "confirmation_already_consumed: delete confirm_token has already been used."
        _CONSUMED_DELETE_TOKENS[digest] = expires_at
    return None


def _encode_payload(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _result(
    *,
    ok: bool,
    status: str,
    workspace_id: str,
    dry_run: bool,
    requested_count: int,
    results: list[dict[str, Any]],
    planned_count: int = 0,
    deleted_count: int = 0,
    failed_count: int = 0,
    timeout_confirmed_count: int = 0,
    confirm_token: str | None = None,
    container_id: str | None = None,
    recursive: bool = False,
    preserved_container_id: str | None = None,
    expanded_count: int = 0,
    errors: dict[str, str] | None = None,
    warnings: list[str] | None = None,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": requested_count,
        "planned_count": planned_count,
        "deleted_count": deleted_count,
        "failed_count": failed_count,
        "timeout_confirmed_count": timeout_confirmed_count,
        "results": results,
        "confirm_token": confirm_token,
        "container_id": container_id,
        "recursive": recursive,
        "preserved_container_id": preserved_container_id,
        "expanded_count": expanded_count,
        "errors": errors,
        "warnings": warnings or [],
        "message": message,
    }
