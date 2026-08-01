"""Safety helpers for Group mode and Playlist scalar writes."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import secrets
import threading
import time
from typing import Any
from uuid import UUID


GROUP_MODE_PROPERTY = "mode"
GROUP_PLAYLIST_PROPERTIES = frozenset(
    {
        "playlist/doLoop",
        "playlist/doShuffle",
        "playlist/doCrossfade",
        "playlist/crossfade/duration",
    }
)
GROUP_PROPERTIES = frozenset({GROUP_MODE_PROPERTY, *GROUP_PLAYLIST_PROPERTIES})
GROUP_TOKEN_TTL_SECONDS = 300
GROUP_SOURCE_READ_KEYS = (
    "uniqueID",
    "type",
    "mode",
    "armed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isAuditioning",
    "isLoaded",
    "isOverridden",
    "isActionRunning",
    "isChildAuditioning",
    "playlist/doLoop",
    "playlist/doShuffle",
    "playlist/doCrossfade",
    "playlist/crossfade/duration",
)
GROUP_CHILD_READ_KEYS = (
    "uniqueID",
    "type",
    "continueMode",
    "preWait",
    "postWait",
    "duration",
    "armed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isAuditioning",
    "isLoaded",
    "isOverridden",
    "isActionRunning",
)
_GROUP_TOKEN_SECRET = secrets.token_bytes(32)
_CONSUMED_GROUP_TOKENS: dict[str, int] = {}
_CONSUMED_GROUP_TOKENS_LOCK = threading.Lock()


def group_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("profile") != "group_basic":
        return None
    operations = item.get("operations") or []
    return next((operation for operation in operations if operation.get("property") in GROUP_PROPERTIES), None)


def group_family(operation: dict[str, Any]) -> str:
    return "groupMode" if operation.get("property") == GROUP_MODE_PROPERTY else "groupPlaylist"


def group_structure_error(items: list[dict[str, Any]], workspace_id: str | None = None) -> str | None:
    if len(items) != 1:
        return "Group real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "group_basic":
        return "Group real writes require group_basic profile."
    if len(operations) != 1:
        return "Group real writes require exactly one property."
    operation = operations[0]
    if operation.get("property") not in GROUP_PROPERTIES or operation.get("path") != operation.get("property"):
        return "Group real writes allow only one canonical mode or Playlist property."
    if operation.get("mode") != "saved":
        return "Group real writes require saved mode."
    if not _is_uuid(item.get("cue_ref")):
        return "Group real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    if workspace_id is not None and not _is_uuid(workspace_id):
        return "Group real writes require an exact workspace UUID."
    return None


def read_group_snapshot(
    reader: Any,
    workspace_id: str,
    cue_id: str,
    *,
    require_safe: bool = True,
) -> tuple[dict[str, Any] | None, str | None]:
    try:
        children_result = reader.get_cue_children(
            workspace_id,
            cue_id,
            shallow=True,
            ids_only=True,
            tcp_fallback_on_timeout=True,
        )
        child_entries = children_result.get("children")
    except Exception as exc:
        return None, f"Group ordered children could not be read: {exc}"
    if not isinstance(child_entries, list) or any(
        not isinstance(entry, dict) or not _is_uuid(entry.get("uniqueID")) for entry in child_entries
    ):
        return None, "Group ordered children readback was missing or malformed."
    child_ids = [entry["uniqueID"] for entry in child_entries]
    if len(child_ids) != len(set(child_ids)):
        return None, "Group ordered children readback contained duplicate UUIDs."
    children: list[dict[str, Any]] = []
    for child_id in child_ids:
        try:
            result = reader.read_cue_values(
                workspace_id,
                child_id,
                list(GROUP_CHILD_READ_KEYS),
                cacheable=False,
            )
            values = result.get("values")
        except Exception as exc:
            return None, f"Group child {child_id} could not be freshly read: {exc}"
        error = _child_error(values, child_id, require_safe=require_safe)
        if error:
            return None, error
        children.append({key: values.get(key) for key in GROUP_CHILD_READ_KEYS})
    snapshot = {"ordered_children": children}
    snapshot["fingerprint"] = _sha256(snapshot["ordered_children"])
    return snapshot, None


def group_preflight(
    reader: Any,
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
    *,
    emit_token: bool,
) -> tuple[dict[str, str], list[str]]:
    operation = group_operation(item)
    property_name = operation.get("property") if operation else "group"
    if operation is None or not isinstance(before, dict):
        return ({property_name: "Group preflight is incomplete."}, [])
    source_error = _source_error(before, item)
    if source_error:
        return ({property_name: source_error}, [])
    cue_id = before.get("uniqueID")
    if cue_id != item.get("cue_ref"):
        return ({property_name: "Group real writes require a fresh exact cue UUID baseline."}, [])
    snapshot, snapshot_error = read_group_snapshot(reader, workspace_id, cue_id)
    if snapshot_error or snapshot is None:
        return ({property_name: snapshot_error or "Group child snapshot is unavailable."}, [])
    requested = operation.get("args", [None])[0]
    baseline = before.get(property_name)
    value_error = _value_error(property_name, requested, baseline, before, snapshot)
    if value_error:
        return ({property_name: value_error}, [])
    operation["group_before_snapshot"] = snapshot
    if emit_token:
        operation.update(
            {
                "risk_tier": "high",
                "real_write_enabled": False,
                "real_write_possible": True,
                "requires_confirm_token": True,
                "group_edit_candidate": True,
                "planned_only_reason": (
                    "group_mode_requires_confirm_token"
                    if property_name == GROUP_MODE_PROPERTY
                    else "group_playlist_requires_confirm_token"
                ),
                "future_gate_requirements": [
                    "single_group_single_property",
                    "exact_workspace_and_cue_uuid",
                    "fresh_group_mode_health_and_activity",
                    "fresh_ordered_child_fingerprint",
                    "expiring_process_bound_confirm_token",
                    "fresh_scalar_and_child_readback",
                    "new_dry_run_for_rollback",
                ],
                "rollback_plan": {
                    "status": "new_dry_run_and_fresh_token_required",
                    "property": property_name,
                    "value": baseline,
                    "automatic_restoration": False,
                },
            }
        )
        operation["confirm_token"] = _encode_token(
            group_family(operation),
            _binding(workspace_id, item, operation, before, snapshot),
        )
    return ({}, [])


def validate_group_token(
    reader: Any,
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = group_operation(item)
    property_name = operation.get("property") if operation else "group"
    if operation is None:
        return {property_name: "Group preflight is incomplete."}
    payload, token_error = _decode_token(item.get("confirm_gates", [None])[0], group_family(operation))
    if token_error or payload is None:
        return {property_name: token_error or "Group confirm_token is invalid."}
    token_digest = hashlib.sha256(item["confirm_gates"][0].encode()).hexdigest()
    now = int(time.time())
    with _CONSUMED_GROUP_TOKENS_LOCK:
        for digest, expires_at in list(_CONSUMED_GROUP_TOKENS.items()):
            if expires_at < now:
                del _CONSUMED_GROUP_TOKENS[digest]
        if token_digest in _CONSUMED_GROUP_TOKENS:
            return {property_name: "confirmation_already_consumed: confirm_token has already been used."}
    errors, _ = group_preflight(reader, workspace_id, item, before, emit_token=False)
    if errors or not isinstance(before, dict):
        return errors
    snapshot = operation["group_before_snapshot"]
    expected = _binding(workspace_id, item, operation, before, snapshot)
    if payload.get("binding") != expected:
        return {property_name: "stale_group_baseline: confirm_token no longer matches the Group or ordered children."}
    operation.update(
        real_write_enabled=True,
        real_write_possible=True,
        requires_confirm_token=True,
        rollback_plan={
            "status": "new_dry_run_and_fresh_token_required",
            "property": property_name,
            "value": before.get(property_name),
            "automatic_restoration": False,
        },
    )
    operation.pop("planned_only_reason", None)
    return {}


def consume_group_token(item: dict[str, Any]) -> dict[str, str]:
    """Atomically consume a validated Group token immediately before its setter."""
    operation = group_operation(item)
    property_name = operation.get("property") if operation else "group"
    if operation is None:
        return {}
    payload, token_error = _decode_token(item.get("confirm_gates", [None])[0], group_family(operation))
    if token_error or payload is None:
        return {property_name: token_error or "Group confirm_token is invalid."}
    token_digest = hashlib.sha256(item["confirm_gates"][0].encode()).hexdigest()
    now = int(time.time())
    with _CONSUMED_GROUP_TOKENS_LOCK:
        for digest, expires_at in list(_CONSUMED_GROUP_TOKENS.items()):
            if expires_at < now:
                del _CONSUMED_GROUP_TOKENS[digest]
        if token_digest in _CONSUMED_GROUP_TOKENS:
            return {property_name: "confirmation_already_consumed: confirm_token has already been used."}
        _CONSUMED_GROUP_TOKENS[token_digest] = payload["expires_at"]
    return {}


def group_side_effects(operation: dict[str, Any], after_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    before_snapshot = operation.get("group_before_snapshot")
    if not isinstance(before_snapshot, dict):
        return [{"scope": "children", "error": "missing reviewed child baseline"}]
    before_children = before_snapshot.get("ordered_children")
    after_children = after_snapshot.get("ordered_children")
    if not isinstance(before_children, list) or not isinstance(after_children, list):
        return [{"scope": "children", "error": "malformed child snapshot"}]
    effects: list[dict[str, Any]] = []
    before_ids = [child.get("uniqueID") for child in before_children]
    after_ids = [child.get("uniqueID") for child in after_children]
    if before_ids != after_ids:
        effects.append({"scope": "children", "field": "order", "before": before_ids, "after": after_ids})
    after_by_id = {child.get("uniqueID"): child for child in after_children}
    for child in before_children:
        child_id = child.get("uniqueID")
        after = after_by_id.get(child_id)
        if not isinstance(after, dict):
            effects.append({"scope": "child", "cue_id": child_id, "field": "presence", "before": True, "after": False})
            continue
        for key in GROUP_CHILD_READ_KEYS:
            if key != "uniqueID" and child.get(key) != after.get(key):
                effects.append(
                    {"scope": "child", "cue_id": child_id, "field": key, "before": child.get(key), "after": after.get(key)}
                )
    return effects


def _source_error(before: dict[str, Any], item: dict[str, Any]) -> str | None:
    if before.get("type") != "Group":
        return "Group mode and Playlist real writes require cue type Group."
    if not _is_uuid(before.get("uniqueID")) or before.get("uniqueID") != item.get("cue_ref"):
        return "Group real writes require exact fresh Group UUID readback."
    if not isinstance(before.get("armed"), bool):
        return "Group armed state must be freshly readable."
    for key in ("isBroken", "isWarning", "isRunning", "isPaused", "isAuditioning", "isLoaded", "isOverridden", "isActionRunning", "isChildAuditioning"):
        if before.get(key) is not False:
            return f"Group real writes require fresh {key}=false."
    mode = before.get("mode")
    if not isinstance(mode, int) or isinstance(mode, bool) or mode not in {1, 2, 3, 4, 6}:
        return "Group mode could not be freshly verified."
    return None


def _child_error(values: Any, child_id: str, *, require_safe: bool) -> str | None:
    if not isinstance(values, dict) or values.get("uniqueID") != child_id or not isinstance(values.get("type"), str):
        return f"Group child {child_id} identity readback was missing or malformed."
    if not isinstance(values.get("armed"), bool):
        return f"Group child {child_id} armed state was not readable."
    if (
        not isinstance(values.get("continueMode"), int)
        or isinstance(values.get("continueMode"), bool)
        or values.get("continueMode") not in {0, 1, 2}
    ):
        return f"Group child {child_id} continueMode was not readable."
    for key in ("preWait", "postWait", "duration"):
        value = values.get(key)
        if not _non_negative_number(value):
            return f"Group child {child_id} {key} was not a readable non-negative number."
    for key in ("isBroken", "isWarning", "isRunning", "isPaused", "isAuditioning", "isLoaded", "isOverridden", "isActionRunning"):
        if not isinstance(values.get(key), bool):
            return f"Group child {child_id} {key} was not readable."
        if require_safe and values.get(key) is not False:
            return f"Group child {child_id} requires fresh {key}=false."
    return None


def _value_error(
    property_name: str,
    requested: Any,
    baseline: Any,
    before: dict[str, Any],
    snapshot: dict[str, Any],
) -> str | None:
    if property_name == GROUP_MODE_PROPERTY:
        if not isinstance(requested, int) or isinstance(requested, bool) or requested not in {1, 2, 3, 4, 6}:
            return "mode must be 1, 2, 3, 4, or 6"
        if requested == 6 and (
            not all(isinstance(before.get(key), bool) for key in GROUP_PLAYLIST_PROPERTIES if key != "playlist/crossfade/duration")
            or not _non_negative_number(before.get("playlist/crossfade/duration"))
        ):
            return "Changing to Playlist mode requires fresh readable Playlist settings."
    elif property_name in GROUP_PLAYLIST_PROPERTIES:
        if before.get("mode") != 6:
            return "Playlist setters require the Group cue to already be in Playlist mode (mode 6)."
        if property_name == "playlist/crossfade/duration":
            if not _non_negative_number(requested):
                return "playlist/crossfade/duration must be a finite non-negative number"
        elif not isinstance(requested, bool):
            return f"{property_name} must be a boolean"
    if property_name == "playlist/crossfade/duration":
        baseline_valid = _non_negative_number(baseline)
    elif property_name == GROUP_MODE_PROPERTY:
        baseline_valid = isinstance(baseline, int) and not isinstance(baseline, bool) and baseline in {1, 2, 3, 4, 6}
    else:
        baseline_valid = isinstance(baseline, bool)
    if not baseline_valid:
        return f"{property_name} requires a fresh readable baseline."
    if baseline == requested:
        return f"{property_name} requested value must differ from the current baseline."
    children = snapshot["ordered_children"]
    durations = [child["duration"] for child in children]
    if property_name == "playlist/doLoop" and requested is True and not any(duration > 0 for duration in durations):
        return "Enabling Playlist loop requires at least one child with non-zero duration."
    effective_crossfade = requested if property_name == "playlist/crossfade/duration" else before.get("playlist/crossfade/duration")
    enabling_crossfade = property_name == "playlist/doCrossfade" and requested is True
    changing_enabled_crossfade = property_name == "playlist/crossfade/duration" and before.get("playlist/doCrossfade") is True
    if enabling_crossfade or changing_enabled_crossfade:
        if not _non_negative_number(effective_crossfade):
            return "Playlist crossfade duration could not be freshly verified."
        if any(duration < effective_crossfade for duration in durations):
            return "Playlist crossfade duration exceeds one or more child durations."
    return None


def _binding(
    workspace_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    before: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    property_name = operation["property"]
    return {
        "workspace_id": workspace_id,
        "cue_ref": item["cue_ref"],
        "cue_id": before["uniqueID"],
        "cue_type": before["type"],
        "profile": item["profile"],
        "property": property_name,
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": before.get(property_name),
        "requested": operation["args"][0],
        "current_group_mode": before["mode"],
        "source_health": {key: before.get(key) for key in GROUP_SOURCE_READ_KEYS if key.startswith("is") or key == "armed"},
        "playlist_state": {key: before.get(key) for key in sorted(GROUP_PLAYLIST_PROPERTIES)},
        "children_fingerprint": snapshot["fingerprint"],
    }


def _encode_token(family: str, binding: dict[str, Any]) -> str:
    payload = {
        "binding": binding,
        "expires_at": int(time.time()) + GROUP_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    signature = hmac.new(_GROUP_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    return f"confirm:{family}:v1:{encoded}:{signature}"


def _decode_token(token: Any, family: str) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, f"{family} confirm_token is required."
    parts = token.split(":")
    if len(parts) != 5 or parts[:3] != ["confirm", family, "v1"]:
        return None, f"{family} confirm_token is malformed or has an unsupported family."
    encoded, signature = parts[3:]
    expected = hmac.new(_GROUP_TOKEN_SECRET, encoded.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None, f"{family} confirm_token signature is invalid."
    try:
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode())
    except Exception:
        return None, f"{family} confirm_token payload is invalid."
    if not isinstance(payload, dict) or not isinstance(payload.get("expires_at"), int):
        return None, f"{family} confirm_token payload is invalid."
    if payload["expires_at"] < int(time.time()):
        return None, f"{family} confirm_token has expired."
    return payload, None


def _sha256(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)).casefold() == value.casefold()
    except (ValueError, AttributeError):
        return False


def _non_negative_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and value >= 0
