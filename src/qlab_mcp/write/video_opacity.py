"""Phase 3A Video Opacity write-family helpers."""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from typing import Any
from uuid import UUID

from ..osc.addressing import _clean_cue_ref
from .tokens import decode_confirm_token, encode_confirm_token


PROPERTY = "opacity"
PROFILE_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
OPERATION_KIND = "video_phase3_opacity_write"
TOKEN_VERSION = 1
_NUMERIC_MATCH_ABS_TOLERANCE = 1e-5
_NUMERIC_MATCH_REL_TOLERANCE = 1e-6
_TOKEN_SECRET = secrets.token_bytes(32)


def _is_exact_cue_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)).casefold() == value.casefold()
    except (ValueError, AttributeError):
        return False


def _is_plain_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _resolved_cue_id(values: dict[str, Any] | None) -> str | None:
    if not isinstance(values, dict):
        return None
    value = values.get("uniqueID")
    if isinstance(value, str) and value.strip():
        return _clean_cue_ref(value)
    return None


def operation(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("profile") not in PROFILE_TYPES:
        return None
    return next(
        (
            candidate
            for candidate in item.get("operations", [])
            if candidate.get("property") == PROPERTY
        ),
        None,
    )


def call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3A opacity real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in PROFILE_TYPES:
        return "Phase 3A opacity real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3A opacity real writes require exactly one property."
    opacity_operation = operations[0]
    if opacity_operation.get("property") != PROPERTY or opacity_operation.get("path") != PROPERTY:
        return "Phase 3A real writes allow only opacity."
    if opacity_operation.get("mode") != "saved":
        return "Phase 3A opacity real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3A opacity real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _sha256(value: int | float) -> str:
    return hashlib.sha256(
        json.dumps(float(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    baseline: int | float,
    requested: int | float,
) -> dict[str, Any]:
    return {
        "version": TOKEN_VERSION,
        "operation_kind": OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": PROFILE_TYPES[item["profile"]],
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": float(baseline),
        "baseline_sha256": _sha256(baseline),
        "requested": float(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _confirm_token(**payload_args: Any) -> str:
    return encode_confirm_token(
        "videoOpacity",
        TOKEN_VERSION,
        _token_payload(**payload_args),
        _TOKEN_SECRET,
    )


def _decode_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    payload, error = decode_confirm_token(token, "videoOpacity", TOKEN_VERSION, _TOKEN_SECRET)
    if error == "malformed":
        return None, "Phase 3A opacity confirm_token is malformed or has an unsupported version."
    if error == "signature":
        return None, "Phase 3A opacity confirm_token signature is invalid."
    if error == "payload" or payload is None:
        return None, "Phase 3A opacity confirm_token payload is invalid."
    return payload, None


def annotate_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    opacity_operation = operation(item)
    if opacity_operation is None:
        return []
    cue_id = _resolved_cue_id(before)
    baseline = before.get(PROPERTY) if isinstance(before, dict) else None
    requested = opacity_operation["args"][0] if opacity_operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == PROFILE_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _is_plain_finite_number(baseline)
        and _is_plain_finite_number(requested)
    )
    opacity_operation.update(
        {
            "real_write_enabled": False,
            "real_write_possible": candidate,
            "requires_confirm_token": candidate,
            "phase3_video_opacity_candidate": candidate,
            "planned_only_reason": (
                "video_opacity_requires_confirm_token"
                if candidate
                else "video_opacity_requires_single_healthy_uuid_cue"
            ),
            "future_gate_requirements": [
                "phase3a_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    if candidate:
        opacity_operation["confirm_token"] = _confirm_token(
            workspace_id=workspace_id,
            cue_ref=item["cue_ref"],
            cue_id=cue_id,
            item=item,
            operation=opacity_operation,
            baseline=baseline,
            requested=requested,
        )
    else:
        opacity_operation.pop("confirm_token", None)
    return [] if candidate else ["Opacity update is not confirmable outside Phase 3A gate."]


def validate_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    opacity_operation = operation(item)
    if opacity_operation is None or not isinstance(before, dict):
        return {PROPERTY: "Phase 3A opacity preflight is incomplete."}
    if before.get("type") != PROFILE_TYPES.get(item.get("profile")):
        return {PROPERTY: "Phase 3A opacity real writes require matching Video, Camera, or Text cue type."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {PROPERTY: "Phase 3A opacity real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {PROPERTY: "Phase 3A opacity real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(PROPERTY)
    requested = opacity_operation["args"][0] if opacity_operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {PROPERTY: "Phase 3A fresh read uniqueID does not exactly match requested cue UUID."}
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {PROPERTY: "Phase 3A opacity requires finite numeric baseline and requested value."}
    payload, token_error = _decode_confirm_token(item["confirm_gates"][0])
    if token_error or payload is None:
        return {PROPERTY: token_error or "Phase 3A opacity confirm_token is invalid."}
    expected = _token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=opacity_operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                PROPERTY: (
                    "Phase 3A opacity confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not math.isclose(
        float(payload.get("baseline", math.nan)),
        float(expected["baseline"]),
        abs_tol=_NUMERIC_MATCH_ABS_TOLERANCE,
        rel_tol=_NUMERIC_MATCH_REL_TOLERANCE,
    ):
        return {
            PROPERTY: (
                "stale_video_opacity_baseline: current opacity no longer matches the reviewed dry-run baseline."
            )
        }
    return {}


def mark_real_operation(item: dict[str, Any]) -> None:
    opacity_operation = operation(item)
    if opacity_operation is None:
        return
    opacity_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3_video_opacity_candidate": True,
            "future_gate_requirements": [
                "phase3a_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    opacity_operation.pop("planned_only_reason", None)


def refresh_real_result(result: dict[str, Any], item: dict[str, Any]) -> None:
    if operation(item) is None or not result.get("executed_operations"):
        return
    for candidate in result.get("operations") or []:
        if candidate.get("property") == PROPERTY:
            candidate["real_write_enabled"] = True
            candidate["real_write_possible"] = True
            candidate["requires_confirm_token"] = True
            candidate.pop("planned_only_reason", None)
    for candidate in result.get("planned_operations") or []:
        if candidate.get("operation") == "set_property" and candidate.get("property") == PROPERTY:
            candidate["real_write_enabled"] = True
            candidate["real_write_possible"] = True
            candidate["requires_confirm_token"] = True
            candidate.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        cue_type = (result.get("before") or {}).get("type") or "visual"
        plan["status"] = result.get("status")
        plan["intent"] = f"Executed saved opacity change on {cue_type} cue."
        plan["real_write_enabled"] = True
        plan["real_write_possible"] = True
        plan["requires_confirm_token"] = True
        plan.pop("why_not_written", None)
        plan["after"] = (result.get("after") or {}).get(PROPERTY)
        plan["verification"] = {"readback_matched": result.get("errors") is None}
        safety = dict(plan.get("safety") or {})
        safety.update({"no_executed_operations": False, "will_modify_qlab": True})
        plan["safety"] = safety
