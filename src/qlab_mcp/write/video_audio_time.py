"""Phase 8B Video Time & Loops write-family helpers."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from typing import Any
from uuid import UUID

from ..osc.addressing import _clean_cue_ref
from .tokens import decode_confirm_token, encode_confirm_token


PROPERTIES = frozenset(
    {
        "startTime",
        "endTime",
        "playCount",
        "infiniteLoop",
        "rate",
        "preservePitch",
        "holdLastFrame",
    }
)
PROFILE_TYPES = {"video_basic": "Video"}
AUDIO_TRACK_PROPERTIES = PROPERTIES - {"holdLastFrame"}
EVIDENCE_KEYS = ("audioTrackFormats", "numChannelsIn", "levels")
OPERATION_KIND = "video_phase8b_audio_time_write"
TOKEN_VERSION = 1
_TOKEN_SECRET = secrets.token_bytes(32)


def _is_exact_cue_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)).casefold() == value.casefold()
    except (ValueError, AttributeError):
        return False


def _resolved_cue_id(values: dict[str, Any] | None) -> str | None:
    if not isinstance(values, dict):
        return None
    value = values.get("uniqueID")
    if isinstance(value, str) and value.strip():
        return _clean_cue_ref(value)
    return None


def operation(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("profile") != "video_basic":
        return None
    return next(
        (
            candidate
            for candidate in item.get("operations", [])
            if candidate.get("property") in PROPERTIES
        ),
        None,
    )


def call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 8B Video audio time writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "video_basic":
        return "Phase 8B Video audio time writes require video_basic profile."
    if len(operations) != 1:
        return "Phase 8B Video audio time writes require exactly one property."
    audio_time_operation = operations[0]
    if (
        audio_time_operation.get("property") not in PROPERTIES
        or audio_time_operation.get("path") != audio_time_operation.get("property")
    ):
        return "Phase 8B Video audio time writes allow only Time & Loops scalar properties."
    if audio_time_operation.get("mode") != "saved":
        return "Phase 8B Video audio time writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 8B Video audio time writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _requested_value(audio_time_operation: dict[str, Any]) -> Any:
    return audio_time_operation["args"][0] if audio_time_operation.get("args") else None


def _value_valid(property_name: str, value: Any) -> bool:
    if property_name in {"infiniteLoop", "preservePitch", "holdLastFrame"}:
        return isinstance(value, bool)
    if property_name == "playCount":
        return isinstance(value, int) and not isinstance(value, bool) and value >= 1
    if property_name in {"startTime", "endTime"}:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and value >= 0
        )
    if property_name == "rate":
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(float(value))
            and 0.03 <= float(value) <= 33.0
        )
    return False


def _readback_value_valid(property_name: str, value: Any) -> bool:
    if property_name == "preservePitch":
        return isinstance(value, bool) or (
            isinstance(value, int)
            and not isinstance(value, bool)
            and value in {0, 1}
        )
    return _value_valid(property_name, value)


def canonical_value(property_name: str, value: Any) -> Any:
    if (
        property_name == "preservePitch"
        and isinstance(value, int)
        and not isinstance(value, bool)
        and value in {0, 1}
    ):
        return bool(value)
    return value


def _has_embedded_audio_evidence(before: dict[str, Any]) -> bool:
    formats = before.get("audioTrackFormats")
    if isinstance(formats, str) and formats.strip():
        return True
    if isinstance(formats, (list, tuple, set, dict)) and bool(formats):
        return True
    channels = before.get("numChannelsIn")
    if (
        isinstance(channels, (int, float))
        and not isinstance(channels, bool)
        and channels > 0
    ):
        return True
    levels = before.get("levels")
    return isinstance(levels, (list, tuple)) and bool(levels)


def _needs_audio_evidence(property_name: str) -> bool:
    return property_name in AUDIO_TRACK_PROPERTIES


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    baseline: Any,
    requested: Any,
) -> dict[str, Any]:
    baseline = canonical_value(operation["property"], baseline)
    requested = canonical_value(operation["property"], requested)
    return {
        "version": TOKEN_VERSION,
        "operation_kind": OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": "Video",
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": baseline,
        "baseline_sha256": _sha256(baseline),
        "requested": requested,
        "requested_sha256": _sha256(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "workspace_validation": "post_write_fresh_readback_required",
        "mcp_secret_version": 1,
    }


def _confirm_token(**payload_args: Any) -> str:
    return encode_confirm_token(
        "videoAudioTime",
        TOKEN_VERSION,
        _token_payload(**payload_args),
        _TOKEN_SECRET,
    )


def _decode_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    payload, error = decode_confirm_token(
        token,
        "videoAudioTime",
        TOKEN_VERSION,
        _TOKEN_SECRET,
    )
    if error == "malformed":
        return None, "Phase 8B Video audio time confirm_token is malformed or has an unsupported version."
    if error == "signature":
        return None, "Phase 8B Video audio time confirm_token signature is invalid."
    if error == "payload" or payload is None:
        return None, "Phase 8B Video audio time confirm_token payload is invalid."
    return payload, None


def dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    audio_time_operation = operation(item)
    if (
        audio_time_operation is None
        or item.get("profile") != "video_basic"
        or not isinstance(before, dict)
        or before.get("type") != "Video"
    ):
        return {}
    property_name = audio_time_operation["property"]
    baseline = before.get(property_name)
    requested = _requested_value(audio_time_operation)
    if not _readback_value_valid(property_name, baseline):
        return {
            property_name: f"Phase 8B Video audio time requires readable {property_name} baseline."
        }
    if not _value_valid(property_name, requested):
        return {
            property_name: (
                f"Phase 8B Video audio time requested {property_name} value is outside "
                "the validated range or type."
            )
        }
    if _needs_audio_evidence(property_name) and not _has_embedded_audio_evidence(before):
        return {
            property_name: "Phase 8B Video audio time requires readable embedded-audio evidence."
        }
    return {}


def annotate_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    audio_time_operation = operation(item)
    if audio_time_operation is None or item.get("profile") != "video_basic":
        return []
    property_name = audio_time_operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = _requested_value(audio_time_operation)
    has_audio_evidence = (
        isinstance(before, dict)
        and (
            not _needs_audio_evidence(property_name)
            or _has_embedded_audio_evidence(before)
        )
    )
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == "Video"
        and cue_id == item.get("cue_ref")
        and _readback_value_valid(property_name, baseline)
        and _value_valid(property_name, requested)
        and has_audio_evidence
    )
    if not candidate:
        audio_time_operation.pop("confirm_token", None)
        return []
    audio_time_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase8b_video_audio_time_candidate": True,
            "planned_only_reason": "video_audio_time_requires_confirm_token",
            "future_gate_requirements": [
                "phase8b_video_audio_time_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
                *(
                    ["embedded_audio_evidence"]
                    if _needs_audio_evidence(property_name)
                    else []
                ),
            ],
        }
    )
    audio_time_operation["confirm_token"] = _confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=audio_time_operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def validate_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    audio_time_operation = operation(item)
    property_name = (
        audio_time_operation.get("property")
        if audio_time_operation
        else "video_audio_time"
    )
    if audio_time_operation is None or not isinstance(before, dict):
        return {
            property_name: "Phase 8B Video audio time preflight is incomplete."
        }
    if before.get("type") != "Video" or item.get("profile") != "video_basic":
        return {
            property_name: (
                "Phase 8B Video audio time real writes require a Video cue with "
                "video_basic profile."
            )
        }
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {
            property_name: (
                "Phase 8B Video audio time real writes require a healthy cue "
                "without warnings."
            )
        }
    if any(
        before.get(key) is True
        for key in ("isRunning", "isPaused", "isAuditioning")
    ):
        return {
            property_name: "Phase 8B Video audio time real writes require an inactive cue."
        }
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = _requested_value(audio_time_operation)
    if cue_id != item.get("cue_ref"):
        return {
            property_name: (
                "Phase 8B fresh read uniqueID does not exactly match requested cue UUID."
            )
        }
    if not _readback_value_valid(property_name, baseline):
        return {
            property_name: f"Phase 8B Video audio time requires readable {property_name} baseline."
        }
    if not _value_valid(property_name, requested):
        return {
            property_name: (
                f"Phase 8B Video audio time requested {property_name} value is outside "
                "the validated range or type."
            )
        }
    if _needs_audio_evidence(property_name) and not _has_embedded_audio_evidence(before):
        return {
            property_name: "Phase 8B Video audio time requires readable embedded-audio evidence."
        }
    payload, token_error = _decode_confirm_token(item["confirm_gates"][0])
    if token_error or payload is None:
        return {
            property_name: token_error
            or "Phase 8B Video audio time confirm_token is invalid."
        }
    expected = _token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=audio_time_operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 8B Video audio time confirm_token does not match this workspace, "
                    "cue, property, value, or risk context."
                )
            }
    if (
        payload.get("baseline_sha256") != expected["baseline_sha256"]
        or payload.get("baseline") != expected["baseline"]
    ):
        return {
            property_name: (
                f"stale_video_audio_time_baseline: current {property_name} no longer "
                "matches the reviewed dry-run baseline."
            )
        }
    return {}


def mark_real_operation(item: dict[str, Any]) -> None:
    audio_time_operation = operation(item)
    if audio_time_operation is None:
        return
    property_name = audio_time_operation["property"]
    audio_time_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase8b_video_audio_time_candidate": True,
            "future_gate_requirements": [
                "phase8b_video_audio_time_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
                *(
                    ["embedded_audio_evidence"]
                    if _needs_audio_evidence(property_name)
                    else []
                ),
            ],
        }
    )
    audio_time_operation.pop("planned_only_reason", None)


def label_rejection(item: dict[str, Any]) -> None:
    audio_time_operation = operation(item)
    if audio_time_operation is not None:
        audio_time_operation[
            "planned_only_reason"
        ] = "video_audio_time_requires_confirm_token"


def refresh_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    audio_time_operation = operation(item)
    if audio_time_operation is None or not result.get("executed_operations"):
        return
    property_name = audio_time_operation["property"]
    for result_operation in result.get("operations") or []:
        if result_operation.get("property") == property_name:
            result_operation["real_write_enabled"] = True
            result_operation["real_write_possible"] = True
            result_operation["requires_confirm_token"] = True
            result_operation.pop("planned_only_reason", None)
    for result_operation in result.get("planned_operations") or []:
        if (
            result_operation.get("operation") == "set_property"
            and result_operation.get("property") == property_name
        ):
            result_operation["real_write_enabled"] = True
            result_operation["real_write_possible"] = True
            result_operation["requires_confirm_token"] = True
            result_operation.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        plan["status"] = result.get("status")
        plan[
            "intent"
        ] = f"Executed saved {property_name} Time & Loops change on Video cue."
        plan["real_write_enabled"] = True
        plan["real_write_possible"] = True
        plan["requires_confirm_token"] = True
        plan.pop("why_not_written", None)
        plan["after"] = (result.get("after") or {}).get(property_name)
        plan["rollback"] = {
            "property": property_name,
            "value": (result.get("before") or {}).get(property_name),
        }
        plan["verification"] = {
            "readback_matched": result.get("errors") is None
        }
        safety = dict(plan.get("safety") or {})
        safety.update(
            {"no_executed_operations": False, "will_modify_qlab": True}
        )
        plan["safety"] = safety
