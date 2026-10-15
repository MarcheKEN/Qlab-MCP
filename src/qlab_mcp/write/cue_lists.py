"""Create root Cue Lists/Carts and expose their safe typed edits."""

from __future__ import annotations

import hashlib
import json
import secrets
import threading
import time
from typing import Any, Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator
from ..models import CanonicalWorkspaceUUID
from .control import Nonnegative, _FAMILIES, edit_control_cues
from uuid import UUID

from ..errors import QLabReplyError, UnsafeWriteOperationError
from ..osc.addressing import _workspace_address
from .moves import _activity_snapshot, _read_snapshot
from .safety import ensure_write_ready, resolve_dry_run
from .tokens import decode_confirm_token, encode_confirm_token


MAX_CUE_LIST_WRITES = 50
_TOKEN_TTL_SECONDS = 300
_TOKEN_SECRET = secrets.token_bytes(32)
_CONSUMED_TOKENS: dict[str, int] = {}
_TOKEN_LOCK = threading.Lock()
_ROOT_TYPES = {
    "cue_list": ("cuelist", "Cue List"),
    "cue_cart": ("cart", "Cue Cart"),
}
_EDIT_FIELDS = {
    "name": "name",
    "number": "number",
    "notes": "notes",
    "armed": "armed",
    "flagged": "flagged",
    "color_name": "colorName",
    "second_color_name": "secondColorName",
    "use_second_color": "useSecondColor",
    "auto_load": "autoLoad",
    "skip_if_disarmed": "skipIfDisarmed",
    "freewheel_seconds": "timecodeFreewheelTime",
    "lookback_seconds": "timecodeLookbackTime",
}
_EDIT_ENUMS = {
    "timecode_sync_mode": ("timecodeSyncMode", {"mtc": 0, "ltc": 1}),
    "smpte_format": ("timecodeSMPTEFormat", {
        "24_fps": 0, "25_fps": 1, "30_fps_drop": 2, "30_fps": 3,
    }),
    "start_behavior": ("timecodeStartBehavior", {
        "ignore_earlier": 0,
        "start_within_last_minute": 1,
        "start_within_last_hour": 2,
        "start_within_lookback": 3,
        "start_all_earlier": 4,
    }),
    "stop_behavior": ("timecodeStopBehavior", {
        "do_nothing": 0, "pause_triggered": 1, "stop_triggered": 2,
    }),
}


def create_cue_lists(
    reader: Any,
    workspace_id: str,
    container_types: list[str],
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> dict[str, Any]:
    if not isinstance(container_types, list) or not 1 <= len(container_types) <= MAX_CUE_LIST_WRITES:
        raise UnsafeWriteOperationError("container_types must contain between 1 and 50 items.")
    try:
        normalized = [_ROOT_TYPES[item] for item in container_types]
    except (KeyError, TypeError) as exc:
        raise UnsafeWriteOperationError("container_types accepts cue_list and cue_cart only.") from exc

    workspace = _resolve_workspace(reader, workspace_id)
    effective_dry_run = resolve_dry_run(reader, dry_run)
    try:
        snapshot = _read_snapshot(reader, workspace, root_moves=True)
        activity = _activity_snapshot(reader, workspace)
    except Exception as exc:
        return _create_result(workspace, container_types, effective_dry_run, status="preflight_failed",
                              errors={"preflight": str(exc)})
    if activity["active_count"]:
        return _create_result(workspace, container_types, effective_dry_run, status="preflight_failed",
                              errors={"activity": "Workspace has running or paused cues."})

    binding = _binding(workspace, container_types, snapshot)
    plan = [
        {"index": index, "container_type": kind, "address": _workspace_address(workspace, "new"),
         "args": [wire_type]}
        for index, (kind, (wire_type, _)) in enumerate(zip(container_types, normalized))
    ]
    if effective_dry_run:
        token = encode_confirm_token("createCueLists", 1, {
            "expires_at": int(time.time()) + _TOKEN_TTL_SECONDS,
            "binding": binding,
        }, _TOKEN_SECRET)
        results = [
            {"index": index, "container_type": kind, "status": "planned", "verified": False}
            for index, kind in enumerate(container_types)
        ]
        return _create_result(workspace, container_types, True, ok=True, status="dry_run",
                              results=results, planned_operations=plan, confirm_token=token)

    payload, error = _decode_token(confirm_token)
    if error or payload is None:
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan, errors={"confirm_token": error or "Invalid token."})
    if _token_is_consumed(confirm_token):
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan,
                              errors={"confirm_token": "The createCueLists confirmation token has already been consumed."})
    try:
        ensure_write_ready(reader, workspace)
        fresh = _read_snapshot(reader, workspace, root_moves=True)
        fresh_activity = _activity_snapshot(reader, workspace)
    except Exception as exc:
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan, errors={"preflight": str(exc)})
    if fresh_activity["active_count"]:
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan, errors={"activity": "Workspace has running or paused cues."})
    if payload.get("binding") != _binding(workspace, container_types, fresh):
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan,
                              errors={"confirm_token": "Token does not match the fresh root structure."})
    error = _consume_token(confirm_token, payload)
    if error:
        return _create_result(workspace, container_types, False, status="preflight_failed",
                              planned_operations=plan, errors={"confirm_token": error})

    results: list[dict[str, Any]] = []
    executed: list[dict[str, Any]] = []
    expected = fresh
    for index, (kind, (wire_type, expected_type)) in enumerate(zip(container_types, normalized)):
        try:
            current = _read_snapshot(reader, workspace, root_moves=True)
            if _snapshot_fingerprint(current) != _snapshot_fingerprint(expected):
                raise UnsafeWriteOperationError("Root structure changed before the next creation.")
            if _activity_snapshot(reader, workspace)["active_count"]:
                raise UnsafeWriteOperationError("Workspace became active before the next creation.")
        except Exception as exc:
            return _create_result(workspace, container_types, False, status="partial_failed",
                                  results=results, planned_operations=plan, executed_operations=executed,
                                  errors={"preflight": str(exc)}, attempted_count=index)

        operation = dict(plan[index], status="sent")
        try:
            executed.append(operation)
            reply = reader.client.request(operation["address"], wire_type)
            if getattr(reply, "status", None) != "ok":
                raise QLabReplyError(getattr(reply, "status", "error"), getattr(reply, "data", None), operation["address"])
            cue_id = _created_uuid(getattr(reply, "data", None))
        except Exception as exc:
            uncertain = not isinstance(exc, QLabReplyError)
            failed_results = [*results, {
                "index": index, "container_type": kind,
                "status": "verification_failed" if uncertain else "failed",
                "verified": False, "errors": {"create": str(exc)},
            }]
            return _create_result(workspace, container_types, False, status="partial_failed" if results else "verification_failed",
                                  results=failed_results, planned_operations=plan, executed_operations=executed,
                                  errors={f"items[{index}]": str(exc)}, attempted_count=index + 1,
                                  uncertain_indices=[index] if uncertain else [])
        try:
            after = _read_snapshot(reader, workspace, root_moves=True)
            before_roots = expected["children_by_parent"]["__root__"]
            after_roots = after["children_by_parent"]["__root__"]
            if after_roots != [*before_roots, cue_id]:
                raise UnsafeWriteOperationError("Fresh root order did not confirm the created container.")
            node = after["nodes"].get(cue_id)
            if node is None or node.get("type") not in ({"Cue Cart", "Cart"} if expected_type == "Cue Cart" else {"Cue List"}):
                raise UnsafeWriteOperationError("Fresh readback did not confirm the created container type.")
            if after["children_by_parent"].get(cue_id) != []:
                raise UnsafeWriteOperationError("Created container was not empty on fresh readback.")
        except Exception as exc:
            failed_results = [*results, {
                "index": index, "container_type": kind, "created_cue_list_id": cue_id,
                "status": "verification_failed", "verified": False,
                "errors": {"verification": str(exc)},
            }]
            return _create_result(workspace, container_types, False, status="verification_failed" if not results else "partial_failed",
                                  results=failed_results, planned_operations=plan, executed_operations=executed,
                                  errors={f"items[{index}]": str(exc)}, attempted_count=index + 1,
                                  uncertain_indices=[index])
        results.append({"index": index, "container_type": kind, "created_cue_list_id": cue_id,
                        "qlab_type": node["type"], "status": "created", "verified": True})
        expected = after

    try:
        final = _read_snapshot(reader, workspace, root_moves=True)
        if _snapshot_fingerprint(final) != _snapshot_fingerprint(expected):
            raise UnsafeWriteOperationError("Final root structure changed after the batch.")
    except Exception as exc:
        return _create_result(workspace, container_types, False, status="partial_failed",
                              results=results, planned_operations=plan, executed_operations=executed,
                              errors={"final_verification": str(exc)}, attempted_count=len(container_types))
    return _create_result(workspace, container_types, False, ok=True, status="created", results=results,
                          planned_operations=plan, executed_operations=executed,
                          attempted_count=len(container_types), batch_verified=True)


def edit_cue_lists(
    reader: Any,
    workspace_id: str,
    updates: list[dict[str, Any]],
    dry_run: bool | None = None,
) -> dict[str, Any]:
    if not isinstance(updates, list) or not 1 <= len(updates) <= MAX_CUE_LIST_WRITES:
        raise UnsafeWriteOperationError("updates must contain between 1 and 50 items.")
    workspace = _resolve_workspace(reader, workspace_id)
    snapshot = _read_snapshot(reader, workspace, root_moves=True)
    roots = set(snapshot["children_by_parent"]["__root__"])
    mapped = []
    seen = set()
    for index, update in enumerate(updates):
        try:
            cue_id = str(UUID(str(update["cue_list_id"])))
            key = cue_id.casefold()
            if key in seen:
                raise ValueError("Duplicate cue_list_id is not allowed.")
            seen.add(key)
            if key not in roots:
                raise ValueError("cue_list_id must identify a root Cue List or Cue Cart.")
            properties = _map_edit_properties(update.get("properties"))
        except (KeyError, TypeError, ValueError) as exc:
            raise UnsafeWriteOperationError(f"updates[{index}]: {exc}") from exc
        # Preserve QLab's UUID spelling from the fresh root read; OSC cue_id routes are case-sensitive.
        mapped.append({
            "cue_id": snapshot["nodes"][key]["uniqueID"],
            "properties": properties,
            "confirm_gates": update.get("confirm_gates", []),
        })
    _FAMILIES["cue_list"] = (CueListSignedInput, CueListSignedProperties,
        ("Cue List", "Cue Cart", "Cart"), "group_basic", "qlab_edit_cue_lists")
    return edit_control_cues(reader, workspace, mapped, dry_run, _family="cue_list")


class CueListSignedProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr | None = None
    number: StrictStr | None = None
    notes: StrictStr | None = None
    armed: StrictBool | None = None
    flagged: StrictBool | None = None
    colorName: StrictStr | None = None
    secondColorName: StrictStr | None = None
    useSecondColor: StrictBool | None = None
    autoLoad: StrictBool | None = None
    skipIfDisarmed: StrictBool | None = None
    timecodeSyncMode: Annotated[StrictInt, Field(ge=0, le=1)] | None = None
    timecodeSMPTEFormat: Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    timecodeStartBehavior: Annotated[StrictInt, Field(ge=0, le=4)] | None = None
    timecodeStopBehavior: Annotated[StrictInt, Field(ge=0, le=2)] | None = None
    timecodeFreewheelTime: Annotated[Nonnegative, Field(le=2)] | None = None
    timecodeLookbackTime: Nonnegative | None = None

    @model_validator(mode="after")
    def require_changes(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide non-null Cue List changes.")
        return self


class CueListSignedInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cue_id: CanonicalWorkspaceUUID
    properties: CueListSignedProperties
    confirm_gates: list[StrictStr] = Field(default_factory=list)


def preflight(reader, ws, item):
    from .control import _preflight
    before, changes, operations, dependencies = _preflight(reader, ws, item, "cue_list", _core=True)
    CueListSignedProperties.model_validate({key: before[key] for key in changes})
    snapshot = _read_snapshot(reader, ws, root_moves=True)
    if str(item.cue_id).casefold() not in snapshot["children_by_parent"]["__root__"]:
        raise ValueError("Cue List edit requires a root container.")
    dependencies["root_structure"] = _snapshot_fingerprint(snapshot)
    return before, changes, operations, dependencies


def check_dependencies(reader, ws, uid, dependencies):
    snapshot = _read_snapshot(reader, ws, root_moves=True)
    if _snapshot_fingerprint(snapshot) != dependencies["root_structure"]:
        raise ValueError("Cue List root structure changed before setter.")



def _map_edit_properties(properties: Any) -> dict[str, Any]:
    if not isinstance(properties, dict) or not properties:
        raise ValueError("properties must be a non-empty object.")
    unknown = set(properties) - set(_EDIT_FIELDS) - set(_EDIT_ENUMS)
    if unknown:
        raise ValueError(f"Unsupported properties: {', '.join(sorted(unknown))}.")
    mapped = {_EDIT_FIELDS[key]: value for key, value in properties.items() if key in _EDIT_FIELDS}
    for key, (target, values) in _EDIT_ENUMS.items():
        if key in properties:
            try:
                mapped[target] = values[properties[key]]
            except (KeyError, TypeError) as exc:
                raise ValueError(f"Invalid {key} value.") from exc
    return mapped


def _resolve_workspace(reader: Any, workspace_id: str) -> str:
    resolver = getattr(reader, "_resolve_workspace_id_strict", None)
    return str(resolver(workspace_id) if resolver else workspace_id)


def _snapshot_fingerprint(snapshot: dict[str, Any]) -> str:
    structural = {
        "children": snapshot["children_by_parent"],
        "types": {key: value.get("type") for key, value in snapshot["nodes"].items()},
    }
    return hashlib.sha256(json.dumps(structural, sort_keys=True).encode()).hexdigest()


def _binding(workspace: str, container_types: list[str], snapshot: dict[str, Any]) -> dict[str, Any]:
    return {"workspace_id": workspace, "container_types": container_types,
            "structure": _snapshot_fingerprint(snapshot)}


def _created_uuid(data: Any) -> str:
    if isinstance(data, dict):
        data = data.get("uniqueID") or data.get("id")
    try:
        return str(UUID(str(data)))
    except (TypeError, ValueError) as exc:
        raise UnsafeWriteOperationError("QLab /new did not return a valid UUID.") from exc


def _decode_token(token: str | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "A createCueLists confirmation token is required."
    payload, error = decode_confirm_token(token, "createCueLists", 1, _TOKEN_SECRET)
    if error or payload is None:
        return None, "The createCueLists confirmation token is invalid or incompatible."
    if not isinstance(payload.get("expires_at"), int) or payload["expires_at"] < int(time.time()):
        return None, "The createCueLists confirmation token has expired."
    return payload, None


def _consume_token(token: str | None, payload: dict[str, Any]) -> str | None:
    digest = hashlib.sha256(str(token).encode()).hexdigest()
    now = int(time.time())
    with _TOKEN_LOCK:
        for key, expiry in list(_CONSUMED_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_TOKENS[key]
        if digest in _CONSUMED_TOKENS:
            return "The createCueLists confirmation token has already been consumed."
        _CONSUMED_TOKENS[digest] = int(payload["expires_at"])
    return None


def _token_is_consumed(token: str | None) -> bool:
    digest = hashlib.sha256(str(token).encode()).hexdigest()
    now = int(time.time())
    with _TOKEN_LOCK:
        for key, expiry in list(_CONSUMED_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_TOKENS[key]
        return digest in _CONSUMED_TOKENS


def _create_result(
    workspace: str,
    requested: list[str],
    dry_run: bool,
    *,
    ok: bool = False,
    status: str,
    results: list[dict[str, Any]] | None = None,
    planned_operations: list[dict[str, Any]] | None = None,
    executed_operations: list[dict[str, Any]] | None = None,
    confirm_token: str | None = None,
    errors: dict[str, str] | None = None,
    attempted_count: int = 0,
    uncertain_indices: list[int] | None = None,
    batch_verified: bool = False,
) -> dict[str, Any]:
    uncertain = uncertain_indices or []
    pending = [index for index in range(attempted_count, len(requested)) if index not in uncertain]
    if dry_run:
        pending = list(range(len(requested)))
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace,
        "dry_run": dry_run,
        "requested_count": len(requested),
        "planned_count": len(planned_operations or []),
        "created_count": sum(item.get("status") == "created" for item in (results or [])),
        "pending_indices": pending,
        "uncertain_indices": uncertain,
        "batch_verified": batch_verified,
        "results": results or [],
        "planned_operations": planned_operations or [],
        "executed_operations": executed_operations or [],
        "confirm_token": confirm_token,
        "errors": errors,
        "warnings": ["Creation is sequential and has no automatic rollback."],
        "message": "Cue List/Cart creation completed." if ok else (
            "Cue List/Cart creation planned; no mutating OSC was sent." if dry_run else
            "Cue List/Cart creation stopped; inspect results before retrying."
        ),
    }
