"""Phase 3D Video Appearance write-family helpers."""

from __future__ import annotations

import hashlib
import json
import secrets
from typing import Any
from uuid import UUID

from ..osc.addressing import _clean_cue_ref
from .tokens import decode_confirm_token, encode_confirm_token


PROPERTIES = frozenset({"blendMode", "preserveAspectRatio"})
PROFILE_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
OPERATION_KIND = "video_phase3d_appearance_write"
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
        return "Phase 3D appearance real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in PROFILE_TYPES:
        return "Phase 3D appearance real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3D appearance real writes require exactly one property."
    appearance_operation = operations[0]
    if (
        appearance_operation.get("property") not in PROPERTIES
        or appearance_operation.get("path") != appearance_operation.get("property")
    ):
        return "Phase 3D real writes allow only blendMode or preserveAspectRatio."
    if appearance_operation.get("mode") != "saved":
        return "Phase 3D appearance real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3D appearance real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _value_valid(property_name: str, value: Any) -> bool:
    if property_name == "preserveAspectRatio":
        return isinstance(value, bool)
    if property_name == "blendMode":
        return isinstance(value, str) and bool(value)
    return False


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
        "baseline": baseline,
        "baseline_sha256": _sha256(baseline),
        "requested": requested,
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _confirm_token(**payload_args: Any) -> str:
    return encode_confirm_token(
        "videoAppearance",
        TOKEN_VERSION,
        _token_payload(**payload_args),
        _TOKEN_SECRET,
    )


def _decode_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    payload, error = decode_confirm_token(token, "videoAppearance", TOKEN_VERSION, _TOKEN_SECRET)
    if error == "malformed":
        return None, "Phase 3D appearance confirm_token is malformed or has an unsupported version."
    if error == "signature":
        return None, "Phase 3D appearance confirm_token signature is invalid."
    if error == "payload" or payload is None:
        return None, "Phase 3D appearance confirm_token payload is invalid."
    return payload, None


def dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    appearance_operation = operation(item)
    if (
        appearance_operation is None
        or item.get("profile") not in PROFILE_TYPES
        or not isinstance(before, dict)
        or before.get("type") != PROFILE_TYPES.get(item.get("profile"))
    ):
        return {}
    property_name = appearance_operation["property"]
    baseline = before.get(property_name)
    requested = (
        appearance_operation["args"][0] if appearance_operation.get("args") else None
    )
    if not _value_valid(property_name, baseline):
        return {
            property_name: f"Phase 3D appearance requires readable {property_name} baseline."
        }
    if not _value_valid(property_name, requested):
        return {
            property_name: f"Phase 3D appearance requested {property_name} value is invalid."
        }
    return {}


def annotate_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    appearance_operation = operation(item)
    if appearance_operation is None or item.get("profile") not in PROFILE_TYPES:
        return []
    property_name = appearance_operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = (
        appearance_operation["args"][0] if appearance_operation.get("args") else None
    )
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == PROFILE_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _value_valid(property_name, baseline)
        and _value_valid(property_name, requested)
    )
    if not candidate:
        appearance_operation.pop("confirm_token", None)
        return []
    appearance_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3d_video_appearance_candidate": True,
            "planned_only_reason": "video_appearance_requires_confirm_token",
            "future_gate_requirements": [
                "phase3d_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    appearance_operation["confirm_token"] = _confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=appearance_operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def validate_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    appearance_operation = operation(item)
    property_name = (
        appearance_operation.get("property") if appearance_operation else "video_appearance"
    )
    if appearance_operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3D appearance preflight is incomplete."}
    if before.get("type") != PROFILE_TYPES.get(item.get("profile")):
        return {
            property_name: (
                "Phase 3D appearance real writes require matching Video, Camera, or Text cue type/profile."
            )
        }
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {
            property_name: "Phase 3D appearance real writes require a healthy cue without warnings."
        }
    if any(
        before.get(key) is True
        for key in ("isRunning", "isPaused", "isAuditioning")
    ):
        return {property_name: "Phase 3D appearance real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = (
        appearance_operation["args"][0] if appearance_operation.get("args") else None
    )
    if cue_id != item.get("cue_ref"):
        return {
            property_name: "Phase 3D fresh read uniqueID does not exactly match requested cue UUID."
        }
    if not _value_valid(property_name, baseline):
        return {
            property_name: f"Phase 3D appearance requires readable {property_name} baseline."
        }
    if not _value_valid(property_name, requested):
        return {
            property_name: f"Phase 3D appearance requested {property_name} value is invalid."
        }
    payload, token_error = _decode_confirm_token(item["confirm_gates"][0])
    if token_error or payload is None:
        return {
            property_name: token_error
            or "Phase 3D appearance confirm_token is invalid."
        }
    expected = _token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=appearance_operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 3D appearance confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if (
        payload.get("baseline_sha256") != expected["baseline_sha256"]
        or payload.get("baseline") != expected["baseline"]
    ):
        return {
            property_name: (
                f"stale_video_appearance_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def mark_real_operation(item: dict[str, Any]) -> None:
    appearance_operation = operation(item)
    if appearance_operation is None:
        return
    appearance_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3d_video_appearance_candidate": True,
            "future_gate_requirements": [
                "phase3d_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    appearance_operation.pop("planned_only_reason", None)


def label_rejection(item: dict[str, Any]) -> None:
    appearance_operation = operation(item)
    if appearance_operation is not None:
        appearance_operation["planned_only_reason"] = (
            "video_appearance_requires_confirm_token"
        )


def refresh_real_result(result: dict[str, Any], item: dict[str, Any]) -> None:
    appearance_operation = operation(item)
    if appearance_operation is None or not result.get("executed_operations"):
        return
    property_name = appearance_operation["property"]
    for candidate in result.get("operations") or []:
        if candidate.get("property") == property_name:
            candidate["real_write_enabled"] = True
            candidate["real_write_possible"] = True
            candidate["requires_confirm_token"] = True
            candidate.pop("planned_only_reason", None)
    for candidate in result.get("planned_operations") or []:
        if (
            candidate.get("operation") == "set_property"
            and candidate.get("property") == property_name
        ):
            candidate["real_write_enabled"] = True
            candidate["real_write_possible"] = True
            candidate["requires_confirm_token"] = True
            candidate.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        cue_type = (result.get("before") or {}).get("type") or "visual"
        plan["status"] = result.get("status")
        plan["intent"] = f"Executed saved {property_name} change on {cue_type} cue."
        plan["real_write_enabled"] = True
        plan["real_write_possible"] = True
        plan["requires_confirm_token"] = True
        plan.pop("why_not_written", None)
        plan["after"] = (result.get("after") or {}).get(property_name)
        plan["verification"] = {"readback_matched": result.get("errors") is None}
        safety = dict(plan.get("safety") or {})
        safety.update({"no_executed_operations": False, "will_modify_qlab": True})
        plan["safety"] = safety
