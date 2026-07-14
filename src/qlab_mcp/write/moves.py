"""Pure structural-move planning helpers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any
from uuid import UUID

from ..errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from .safety import ensure_write_ready, resolve_dry_run


LINEAR_PLACEMENT_FIELDS = ("destination_index", "before_cue_id", "after_cue_id", "position")
MAX_BATCH_MOVES = 10
MOVE_TOKEN_TTL_SECONDS = 300
MOVE_CONVERGENCE_DEADLINES_SECONDS = (0.0, 0.25, 0.5, 1.0, 2.0, 4.0, 6.0, 8.0, 10.0)
_MOVE_TOKEN_SECRET = secrets.token_bytes(32)
_CONTAINER_TYPES = {"Cue List", "Cue Cart", "Cart", "Group"}
_LINEAR_PARENT_TYPES = {"Cue List", "Group"}
_CART_PARENT_TYPES = {"Cue Cart", "Cart"}


def simulate_move_batch(
    children_by_parent: dict[str, list[str]],
    moves: list[dict[str, Any]],
) -> dict[str, dict[str, list[str]]]:
    """Apply linear placements in request order to an in-memory ordered tree."""
    tree = {parent_id: list(children) for parent_id, children in children_by_parent.items()}
    parents = _parents_by_child(tree)
    sources = [str(move.get("cue_id") or "") for move in moves]
    if not all(sources) or len(sources) != len(set(sources)):
        raise ValueError("Each batch move must use one distinct cue_id.")

    for move in moves:
        cue_id = str(move["cue_id"])
        source_parent = parents.get(cue_id)
        destination_parent = str(move.get("destination_parent_id") or source_parent or "")
        if source_parent is None:
            raise ValueError(f"Source cue {cue_id} does not exist in the supplied tree.")
        if destination_parent not in tree:
            raise ValueError(f"Destination parent {destination_parent} does not exist in the supplied tree.")
        if move.get("cart_row") is not None or move.get("cart_column") is not None:
            # Cart coordinates are two-dimensional and do not change the documented linear child order.
            continue

        placement = [field for field in LINEAR_PLACEMENT_FIELDS if move.get(field) is not None]
        if len(placement) != 1:
            raise ValueError("Linear placement requires exactly one placement field.")

        source_children = tree[source_parent]
        source_children.remove(cue_id)
        destination_children = tree[destination_parent]
        index = _resolved_index(destination_children, move)
        destination_children.insert(index, cue_id)
        parents[cue_id] = destination_parent

    return {"children_by_parent": tree}


def _parents_by_child(children_by_parent: dict[str, list[str]]) -> dict[str, str]:
    parents: dict[str, str] = {}
    for parent_id, children in children_by_parent.items():
        for child_id in children:
            if child_id in parents:
                raise ValueError(f"Cue {child_id} has more than one parent.")
            parents[child_id] = parent_id
    return parents


def _resolved_index(children: list[str], move: dict[str, Any]) -> int:
    if move.get("position") == "first":
        return 0
    if move.get("position") == "last":
        return len(children)
    before = move.get("before_cue_id")
    if before is not None:
        return _reference_index(children, str(before), "before_cue_id")
    after = move.get("after_cue_id")
    if after is not None:
        return _reference_index(children, str(after), "after_cue_id") + 1
    index = move.get("destination_index")
    if not isinstance(index, int) or isinstance(index, bool) or index < 0 or index > len(children):
        raise ValueError("destination_index must be a non-negative canonical insertion index.")
    return index


def _reference_index(children: list[str], reference: str, field: str) -> int:
    try:
        return children.index(reference)
    except ValueError as exc:
        raise ValueError(f"{field} must identify a current child of the destination parent.") from exc


def move_cues(
    reader: Any,
    workspace_id: str,
    moves: list[dict[str, Any]],
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> dict[str, Any]:
    """Plan or execute a structurally safe batch; Cue Cart writes remain runtime-gated."""
    if not isinstance(moves, list) or not moves:
        raise UnsafeWriteOperationError("moves must include at least one move.")
    if len(moves) > MAX_BATCH_MOVES:
        raise UnsafeWriteOperationError(f"moves can include at most {MAX_BATCH_MOVES} moves.")

    effective_dry_run = resolve_dry_run(reader, dry_run)
    workspace = _resolve_workspace(reader, workspace_id)
    try:
        snapshot = _read_snapshot(reader, workspace)
    except Exception as exc:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            requested_count=len(moves),
            failed_count=len(moves),
            results=[],
            errors={"structure": str(exc)},
            message="Cue move preflight could not read a complete fresh workspace structure.",
        )
    normalized, errors = _normalize_moves(snapshot, moves)
    if errors:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            requested_count=len(moves),
            failed_count=len(errors),
            results=[],
            errors=errors,
            message="Cue move preflight failed; no mutating OSC commands were sent.",
        )

    activity = _activity_snapshot(reader, workspace)
    if activity["active_count"]:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            requested_count=len(moves),
            failed_count=len(moves),
            results=[],
            errors={"activity": "Workspace has running or paused cues; structural moves require 0 / 0 / 0 activity."},
            message="Cue move preflight failed because workspace activity is not safely idle.",
        )

    try:
        simulated = simulate_move_batch(snapshot["children_by_parent"], normalized)
    except ValueError as exc:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=effective_dry_run,
            requested_count=len(moves),
            failed_count=len(moves),
            results=[],
            errors={"simulation": str(exc)},
            message="Cue move preflight failed during ordered batch simulation.",
        )

    plan = _build_plan(snapshot, normalized, activity)
    if effective_dry_run:
        token = _encode_token(workspace, plan)
        return _result(
            ok=True,
            status="planned",
            workspace_id=workspace,
            dry_run=True,
            requested_count=len(moves),
            planned_count=len(plan),
            results=plan,
            confirm_token=token,
            warnings=[
                "Dry run only: no mutating OSC commands were sent to QLab.",
                "Cue Cart execution remains runtime-blocked until disposable-workspace semantics are recorded.",
            ],
            message="Cue move batch planned; review the dedicated confirmation token before real execution.",
        )

    ensure_write_ready(reader, workspace)
    payload, token_error = _decode_token(confirm_token)
    if token_error:
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            requested_count=len(moves),
            failed_count=len(moves),
            results=plan,
            errors={"confirm_token": token_error},
            message="Cue move real execution was rejected before any mutating OSC command.",
        )
    if payload.get("binding") != _token_binding(workspace, plan):
        return _result(
            ok=False,
            status="preflight_failed",
            workspace_id=workspace,
            dry_run=False,
            requested_count=len(moves),
            failed_count=len(moves),
            results=plan,
            errors={"confirm_token": "move confirmation token does not match current workspace and planned batch."},
            message="Cue move real execution was rejected before any mutating OSC command.",
        )
    if any(item["kind"] == "cart" for item in plan):
        return _result(
            ok=False,
            status="runtime_blocked",
            workspace_id=workspace,
            dry_run=False,
            requested_count=len(moves),
            planned_count=len(plan),
            failed_count=len(plan),
            results=plan,
            errors={"runtime": "Cue Cart execution remains blocked pending disposable-workspace route validation."},
            message="Cue move batch contains a Cue Cart placement that is not yet runtime-proven.",
        )
    return _execute_linear_batch(reader, workspace, snapshot, normalized, plan)


def _execute_linear_batch(
    reader: Any,
    workspace_id: str,
    initial_snapshot: dict[str, Any],
    moves: list[dict[str, Any]],
    plan: list[dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    moved_count = 0
    for index, item in enumerate(plan):
        if _activity_snapshot(reader, workspace_id)["active_count"]:
            return _execution_failure(
                workspace_id,
                plan,
                results,
                moved_count,
                index,
                item,
                "Workspace activity changed before the structural setter was sent.",
            )
        expected = simulate_move_batch(initial_snapshot["children_by_parent"], moves[: index + 1])["children_by_parent"]
        try:
            reply = reader.client.request(
                item["address"].replace("{workspace_id}", workspace_id),
                *item["args"],
            )
            reply_data = getattr(reply, "data", None)
            reply_status = getattr(reply, "status", "ok")
        except OscTimeoutError as exc:
            reply_data = None
            reply_status = "timeout_pending_readback"
            reply_error = str(exc)
        except (QLabReplyError, Exception) as exc:
            return _execution_failure(
                workspace_id,
                plan,
                results,
                moved_count,
                index,
                item,
                str(exc),
            )

        expected_children = expected[item["destination_parent_id"]]
        expected_index = expected_children.index(item["cue_id"])
        verification = _poll_move_convergence(
            reader,
            workspace_id,
            item["cue_id"],
            {"parent_id": item["destination_parent_id"], "index": expected_index},
        )
        if not verification["ok"]:
            return _execution_failure(
                workspace_id,
                plan,
                results,
                moved_count,
                index,
                item,
                verification["error"],
                status="verification_inconclusive",
                readback=verification["readback"],
                reply_status=reply_status,
                reply_data=reply_data,
                verification_status=verification["verification_status"],
                verification_elapsed_ms=verification["elapsed_ms"],
            )
        results.append(
            {
                **item,
                "status": "moved_with_confirmed_timeout" if reply_status == "timeout_pending_readback" else "moved",
                "reply_status": reply_status,
                "reply_data": reply_data,
                "reply_data_status": "provisional",
                "readback": verification["readback"],
                "verification_status": verification["verification_status"],
                "verification_elapsed_ms": verification["elapsed_ms"],
                **({"reply_error": reply_error} if reply_status == "timeout_pending_readback" else {}),
            }
        )
        moved_count += 1

    if _activity_snapshot(reader, workspace_id)["active_count"]:
        return _execution_failure(
            workspace_id,
            plan,
            results,
            moved_count,
            len(plan) - 1,
            plan[-1],
            "Workspace activity changed after structural execution.",
            status="verification_failed",
        )

    timeout_confirmed_count = sum(item["status"] == "moved_with_confirmed_timeout" for item in results)
    converged_after_polling = any(
        item["verification_status"] == "confirmed_after_convergence" for item in results
    )
    return _result(
        ok=True,
        status=(
            "moved_with_confirmed_timeout"
            if timeout_confirmed_count
            else "moved_after_convergence"
            if converged_after_polling
            else "moved"
        ),
        workspace_id=workspace_id,
        dry_run=False,
        requested_count=len(plan),
        planned_count=len(plan),
        moved_count=moved_count,
        results=results,
        warnings=["Moves were executed sequentially and are not atomic."],
        message="Cue move batch completed with fresh structural readback after every move.",
        timeout_confirmed_count=timeout_confirmed_count,
    )


def _readback_position(snapshot: dict[str, Any], cue_id: str) -> dict[str, Any]:
    parent_id = snapshot["parent_by_child"].get(cue_id)
    if parent_id is None:
        return {"parent_id": None, "index": None}
    return {"parent_id": parent_id, "index": snapshot["children_by_parent"][parent_id].index(cue_id)}


def _poll_move_convergence(
    reader: Any,
    workspace_id: str,
    cue_id: str,
    expected: dict[str, Any],
) -> dict[str, Any]:
    started = time.monotonic()
    last_readback: dict[str, Any] | None = None
    last_error: str | None = None
    previous_deadline = 0.0
    for deadline in MOVE_CONVERGENCE_DEADLINES_SECONDS:
        delay = deadline - previous_deadline
        if delay > 0:
            time.sleep(delay)
        previous_deadline = deadline
        try:
            after = _read_snapshot(reader, workspace_id)
            last_readback = _readback_position(after, cue_id)
            last_error = None
        except Exception as exc:
            last_error = str(exc)
            continue
        if last_readback == expected:
            return {
                "ok": True,
                "readback": last_readback,
                "verification_status": "confirmed_immediately" if deadline == 0 else "confirmed_after_convergence",
                "elapsed_ms": round((time.monotonic() - started) * 1000),
            }
    return {
        "ok": False,
        "readback": last_readback,
        "verification_status": "indeterminate",
        "elapsed_ms": round((time.monotonic() - started) * 1000),
        "error": last_error or "Fresh structural readback did not converge within 10 seconds.",
    }


def _execution_failure(
    workspace_id: str,
    plan: list[dict[str, Any]],
    results: list[dict[str, Any]],
    moved_count: int,
    failed_index: int,
    item: dict[str, Any],
    error: str,
    *,
    status: str = "partial_failed",
    readback: dict[str, Any] | None = None,
    reply_status: str | None = None,
    reply_data: Any = None,
    verification_status: str | None = None,
    verification_elapsed_ms: int | None = None,
) -> dict[str, Any]:
    results.append(
        {
            **item,
            "status": status,
            "error": error,
            **({"readback": readback} if readback else {}),
            **({"reply_status": reply_status} if reply_status is not None else {}),
            **({"reply_data": reply_data} if reply_status is not None else {}),
            **({"reply_data_status": "provisional"} if reply_status is not None else {}),
            **({"verification_status": verification_status} if verification_status is not None else {}),
            **({"verification_elapsed_ms": verification_elapsed_ms} if verification_elapsed_ms is not None else {}),
        }
    )
    inverse_moves = [
        {
            "cue_id": completed["cue_id"],
            "destination_parent_id": completed["source_parent_id"],
            "destination_index": completed["original_index"],
        }
        for completed in reversed(results[:moved_count])
    ]
    return _result(
        ok=False,
        status=status,
        workspace_id=workspace_id,
        dry_run=False,
        requested_count=len(plan),
        planned_count=len(plan),
        moved_count=moved_count,
        failed_count=len(plan) - moved_count,
        results=results,
        rollback={
            "status": "fresh_confirmation_required",
            "moves": inverse_moves,
            "reason": "Run the inverse moves as a new dry run before any rollback write.",
        }
        if inverse_moves
        else None,
        errors={f"moves[{failed_index}]": error},
        warnings=["No automatic rollback was sent; successful earlier moves require a fresh confirmed inverse batch."],
        message="Cue move batch stopped after a failed move or unverifiable readback.",
    )


def _resolve_workspace(reader: Any, workspace_id: str) -> str:
    resolver = getattr(reader, "_resolve_workspace_id_strict", None)
    if resolver is None:
        return str(workspace_id)
    return str(resolver(workspace_id))


def _read_snapshot(reader: Any, workspace_id: str) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    children_by_parent: dict[str, list[str]] = {}
    parent_by_child: dict[str, str | None] = {}

    roots = reader.get_cue_lists(
        workspace_id,
        include_children=False,
        cacheable=False,
        tcp_fallback_on_timeout=True,
    ).get("cue_lists")
    if not isinstance(roots, list):
        raise UnsafeWriteOperationError("QLab cueLists/shallow reply is not a list.")

    def visit(cue: Any, parent_id: str | None) -> None:
        if not isinstance(cue, dict):
            raise UnsafeWriteOperationError("QLab structural cue reply contains a non-object entry.")
        cue_osc_id = _uuid_text(cue.get("uniqueID"), "QLab cue uniqueID")
        cue_id = _uuid_key(cue_osc_id, "QLab cue uniqueID")
        if cue_id in nodes:
            raise UnsafeWriteOperationError(f"QLab structural tree repeats cue {cue_id}.")
        cue_type = str(cue.get("type") or "")
        nodes[cue_id] = dict(cue, uniqueID=cue_osc_id, type=cue_type)
        parent_by_child[cue_id] = parent_id
        if parent_id is not None:
            children_by_parent.setdefault(parent_id, []).append(cue_id)
        if cue_type not in _CONTAINER_TYPES:
            return
        children_by_parent.setdefault(cue_id, [])
        try:
            result = reader.get_cue_children(
                workspace_id,
                cue_osc_id,
                shallow=True,
                ids_only=False,
                tcp_fallback_on_timeout=True,
            )
        except Exception as exc:
            address = getattr(exc, "address", None)
            suffix = f" ({address})" if address else ""
            raise UnsafeWriteOperationError(f"QLab children read failed for {cue_id}: {exc}{suffix}") from exc
        children = result.get("children")
        if not isinstance(children, list):
            raise UnsafeWriteOperationError(f"QLab children/shallow reply for {cue_id} is not a list.")
        for child in children:
            visit(child, cue_id)

    for root in roots:
        visit(root, None)
    return {
        "nodes": nodes,
        "children_by_parent": children_by_parent,
        "parent_by_child": parent_by_child,
    }


def _normalize_moves(snapshot: dict[str, Any], moves: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, str]]:
    nodes = snapshot["nodes"]
    parents = snapshot["parent_by_child"]
    normalized: list[dict[str, Any]] = []
    errors: dict[str, str] = {}
    seen_sources: set[str] = set()
    for index, raw_move in enumerate(moves):
        key = f"moves[{index}]"
        if not isinstance(raw_move, dict):
            errors[key] = "Each move must be an object."
            continue
        try:
            cue_id = _uuid_key(raw_move.get("cue_id"), f"{key}.cue_id")
            if cue_id in seen_sources:
                raise ValueError("Duplicate cue_id is not allowed in one batch.")
            seen_sources.add(cue_id)
            source = nodes.get(cue_id)
            if source is None:
                raise ValueError("cue_id does not resolve in this workspace.")
            source_parent = parents.get(cue_id)
            if source_parent is None:
                raise ValueError("Moving a top-level Cue List or Cue Cart is runtime-blocked.")
            destination_parent = _optional_uuid_text(raw_move.get("destination_parent_id"), f"{key}.destination_parent_id")
            destination_parent = destination_parent or source_parent
            destination = nodes.get(destination_parent)
            if destination is None:
                raise ValueError("destination_parent_id does not resolve in this workspace.")
            _validate_health(source, "source")
            _validate_health(destination, "destination")
            if source.get("type") in _CONTAINER_TYPES and _is_descendant(destination_parent, cue_id, parents):
                raise ValueError("A Group, Cue List, or Cue Cart cannot move into itself or a descendant.")

            cart_row = raw_move.get("cart_row")
            cart_column = raw_move.get("cart_column")
            linear_fields = [field for field in LINEAR_PLACEMENT_FIELDS if raw_move.get(field) is not None]
            if cart_row is not None or cart_column is not None:
                if raw_move.get("destination_parent_id") is None:
                    raise ValueError("Cue Cart placement requires destination_parent_id.")
                if cart_row is None or cart_column is None:
                    raise ValueError("Cue Cart placement requires both cart_row and cart_column.")
                if linear_fields:
                    raise ValueError("Cue Cart placement cannot include linear placement fields.")
                if destination.get("type") not in _CART_PARENT_TYPES:
                    raise ValueError("cart_row and cart_column require a Cue Cart destination.")
                if source.get("type") == "Group":
                    raise ValueError("Cue Cart destinations cannot contain Group cues.")
                if not _non_negative_int(cart_row) or not _non_negative_int(cart_column):
                    raise ValueError("cart_row and cart_column must be non-negative integers.")
                if source_parent != destination_parent:
                    raise ValueError("Cross-parent Cue Cart moves are runtime-blocked.")
                normalized.append(
                    {
                        "cue_id": cue_id,
                        "source_parent_id": source_parent,
                        "destination_parent_id": destination_parent,
                        "cart_row": cart_row,
                        "cart_column": cart_column,
                        "kind": "cart",
                    }
                )
                continue
            if destination.get("type") not in _LINEAR_PARENT_TYPES:
                raise ValueError("Linear placement requires a Cue List or Group destination.")
            if len(linear_fields) != 1:
                raise ValueError("Linear placement requires exactly one placement field.")
            for field in ("before_cue_id", "after_cue_id"):
                if raw_move.get(field) is not None:
                    reference = _uuid_key(raw_move[field], f"{key}.{field}")
                    if reference == cue_id:
                        raise ValueError(f"{field} cannot equal cue_id.")
            position = raw_move.get("position")
            if position is not None and position not in {"first", "last"}:
                raise ValueError("position must be first or last.")
            if raw_move.get("destination_index") is not None and not _non_negative_int(raw_move["destination_index"]):
                raise ValueError("destination_index must be a non-negative integer.")
            normalized.append(
                {
                    "cue_id": cue_id,
                    "source_parent_id": source_parent,
                    "destination_parent_id": destination_parent,
                    **{field: raw_move.get(field) for field in LINEAR_PLACEMENT_FIELDS if raw_move.get(field) is not None},
                    "kind": "linear",
                }
            )
        except (TypeError, ValueError) as exc:
            errors[key] = str(exc)
    if not errors:
        try:
            _validate_batch_dependencies(normalized, parents)
        except ValueError as exc:
            errors["batch"] = str(exc)
    return normalized, errors


def _validate_batch_dependencies(moves: list[dict[str, Any]], parents: dict[str, str | None]) -> None:
    sources = {move["cue_id"] for move in moves}
    for move in moves:
        for field in ("before_cue_id", "after_cue_id"):
            reference = move.get(field)
            if reference in sources:
                raise ValueError(f"{field} cannot reference a cue moved in the same batch.")
        destination = move["destination_parent_id"]
        if destination in sources and destination != move["cue_id"]:
            raise ValueError("destination_parent_id cannot reference a cue moved in the same batch.")
    for index, move in enumerate(moves):
        for other in moves[index + 1 :]:
            if _is_descendant(other["cue_id"], move["cue_id"], parents) or _is_descendant(
                move["cue_id"], other["cue_id"], parents
            ):
                raise ValueError("A container cue and one of its descendants cannot move in the same batch.")


def _build_plan(
    snapshot: dict[str, Any], moves: list[dict[str, Any]], activity: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    initial_tree = snapshot["children_by_parent"]
    nodes = snapshot["nodes"]
    plan: list[dict[str, Any]] = []
    for move_index, move in enumerate(moves):
        source_parent = move["source_parent_id"]
        destination_parent = move["destination_parent_id"]
        source_osc_id = nodes[move["cue_id"]]["uniqueID"]
        destination_osc_id = nodes[destination_parent]["uniqueID"]
        entry = dict(move)
        entry["original_index"] = initial_tree[source_parent].index(move["cue_id"])
        entry["original_neighbors"] = _neighbors(initial_tree[source_parent], move["cue_id"])
        entry["source_parent_fingerprint"] = _fingerprint(initial_tree[source_parent])
        entry["source_health"] = _health_snapshot(nodes[move["cue_id"]])
        entry["destination_health"] = _health_snapshot(nodes[destination_parent])
        entry["activity_snapshot"] = activity or {"active_count": 0, "active_cue_ids": []}
        if move["kind"] == "linear":
            step_tree = simulate_move_batch(initial_tree, moves[: move_index + 1])["children_by_parent"]
            entry["destination_index"] = step_tree[destination_parent].index(move["cue_id"])
            entry["destination_fingerprint"] = _fingerprint(step_tree[destination_parent])
            entry["final_neighbors"] = _neighbors(step_tree[destination_parent], move["cue_id"])
            entry["address"] = f"/workspace/{{workspace_id}}/move/{source_osc_id}"
            entry["args"] = [entry["destination_index"]] + (
                [destination_osc_id] if destination_parent != source_parent else []
            )
        else:
            entry["destination_fingerprint"] = _fingerprint(initial_tree[destination_parent])
            entry["final_neighbors"] = _neighbors(initial_tree[destination_parent], move["cue_id"])
            entry["address"] = f"/cue_id/{destination_osc_id}/moveCartCue/{source_osc_id}"
            entry["args"] = [move["cart_row"], move["cart_column"]]
        plan.append(entry)
    return plan


def _activity_snapshot(reader: Any, workspace_id: str) -> dict[str, Any]:
    running = reader.get_running_cues(workspace_id, include_paused=True, include_children=True).get("running_cues")
    if not isinstance(running, list):
        raise UnsafeWriteOperationError("QLab runningOrPausedCues reply is not a list.")
    cue_ids = sorted(str(cue.get("uniqueID") or cue) if isinstance(cue, dict) else str(cue) for cue in running)
    return {"active_count": len(cue_ids), "active_cue_ids": cue_ids}


def _validate_health(cue: dict[str, Any], role: str) -> None:
    if _qlab_bool(cue.get("isBroken")) or _qlab_bool(cue.get("isWarning")):
        raise ValueError(f"{role} cue must be healthy and unflagged by QLab warnings.")


def _health_snapshot(cue: dict[str, Any]) -> dict[str, bool]:
    return {
        "is_broken": _qlab_bool(cue.get("isBroken")),
        "is_warning": _qlab_bool(cue.get("isWarning")),
    }


def _qlab_bool(value: Any) -> bool:
    return value is True or value == 1 or (isinstance(value, str) and value.casefold() in {"true", "yes", "1"})


def _is_descendant(candidate: str, ancestor: str, parents: dict[str, str | None]) -> bool:
    current: str | None = candidate
    while current is not None:
        if current == ancestor:
            return True
        current = parents.get(current)
    return False


def _neighbors(children: list[str], cue_id: str) -> dict[str, str | None]:
    index = children.index(cue_id)
    return {
        "before": children[index - 1] if index else None,
        "after": children[index + 1] if index + 1 < len(children) else None,
    }


def _fingerprint(children: list[str]) -> str:
    return hashlib.sha256(json.dumps(children, separators=(",", ":")).encode()).hexdigest()


def _uuid_text(value: Any, label: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a UUID.")
    UUID(value)
    return value


def _uuid_key(value: Any, label: str) -> str:
    return str(UUID(_uuid_text(value, label)))


def _optional_uuid_text(value: Any, label: str) -> str | None:
    return None if value is None else _uuid_key(value, label)


def _non_negative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _token_binding(workspace_id: str, plan: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "version": 1,
        "workspace_id": workspace_id,
        "plan": plan,
    }


def _encode_token(workspace_id: str, plan: list[dict[str, Any]]) -> str:
    payload = {
        "binding": _token_binding(workspace_id, plan),
        "expires_at": int(time.time()) + MOVE_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = _encode_payload(payload)
    signature = hmac.new(_MOVE_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return f"confirm:moveCues:v1:{encoded}:{signature}"


def _decode_token(token: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "move confirmation token is required."
    parts = token.split(":")
    if len(parts) != 5 or parts[:3] != ["confirm", "moveCues", "v1"]:
        return None, "move confirmation token is malformed or has an unsupported family."
    encoded, signature = parts[3:]
    expected = hmac.new(_MOVE_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None, "move confirmation token signature is invalid."
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode())
    except Exception:
        return None, "move confirmation token payload is invalid."
    if not isinstance(payload, dict) or not isinstance(payload.get("expires_at"), int):
        return None, "move confirmation token payload is invalid."
    if payload["expires_at"] < int(time.time()):
        return None, "move confirmation token has expired."
    return payload, None


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
    planned_count: int = 0,
    moved_count: int = 0,
    failed_count: int = 0,
    timeout_confirmed_count: int = 0,
    results: list[dict[str, Any]],
    confirm_token: str | None = None,
    rollback: dict[str, Any] | None = None,
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
        "moved_count": moved_count,
        "failed_count": failed_count,
        "timeout_confirmed_count": timeout_confirmed_count,
        "results": results,
        "confirm_token": confirm_token,
        "rollback": rollback,
        "errors": errors,
        "warnings": warnings or [],
        "message": message,
    }
