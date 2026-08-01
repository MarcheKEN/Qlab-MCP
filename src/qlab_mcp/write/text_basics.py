"""Phase 3E Text Basics write-family helpers.

The public update orchestration remains in :mod:`operations`; this module only
owns the Text Basics route's metadata, token binding, validation, and result
annotations.
"""

from __future__ import annotations

import hashlib
import json
import math
import secrets
from typing import Any
from uuid import UUID

from ..osc.addressing import _clean_cue_ref
from .tokens import decode_confirm_token, encode_confirm_token


TEXT_PHASE3E_COLOR_PROPERTIES = frozenset({"text/format/color"})
TEXT_PHASE3E_PROPERTIES = frozenset(
    {
        "text",
        "fixedWidth",
        "text/format/alignment",
        "text/format/fontName",
        "text/format/fontSize",
        "text/format/lineSpacing",
        *TEXT_PHASE3E_COLOR_PROPERTIES,
    }
)
PHASE3E_TEXT_BASIC_OPERATION_KIND = "video_phase3e_text_basic_write"
PHASE3E_TEXT_BASIC_TOKEN_VERSION = 1
UPDATE_NUMERIC_MATCH_ABS_TOLERANCE = 1e-5
UPDATE_NUMERIC_MATCH_REL_TOLERANCE = 1e-6
_LIGHT_WRITE_TOKEN_SECRET = secrets.token_bytes(32)


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
    if item.get("profile") != "text_basic":
        return None
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in TEXT_PHASE3E_PROPERTIES
        ),
        None,
    )


def call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3E Text Basics real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "text_basic":
        return "Phase 3E Text Basics real writes require profile='text_basic'."
    if len(operations) != 1:
        return "Phase 3E Text Basics real writes require exactly one property."
    operation = operations[0]
    if (
        operation.get("property") not in TEXT_PHASE3E_PROPERTIES
        or operation.get("path") != operation.get("property")
    ):
        return "Phase 3E real writes allow only approved scalar Text cue properties."
    if operation.get("mode") != "saved":
        return "Phase 3E Text Basics real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3E Text Basics real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _text_basic_value_valid(property_name: str, value: Any) -> bool:
    if property_name == "text":
        return isinstance(value, str) and len(value) <= 20000
    if property_name == "fixedWidth":
        return _is_plain_finite_number(value) and float(value) >= 0
    if property_name == "text/format/alignment":
        return isinstance(value, str) and value in {"left", "center", "right", "justify"}
    if property_name == "text/format/fontName":
        return isinstance(value, str) and 0 < len(value) <= 128 and not any(ord(ch) < 32 for ch in value)
    if property_name == "text/format/fontSize":
        return _is_plain_finite_number(value) and 0 < float(value) <= 1000
    if property_name == "text/format/lineSpacing":
        return _is_plain_finite_number(value) and float(value) >= 0
    if property_name in TEXT_PHASE3E_COLOR_PROPERTIES:
        return (
            isinstance(value, list)
            and len(value) == 4
            and all(_is_plain_finite_number(component) and 0 <= float(component) <= 1 for component in value)
        )
    return False


def _text_basic_canonical_value(property_name: str, value: Any) -> Any:
    if property_name in {"fixedWidth", "text/format/fontSize", "text/format/lineSpacing"}:
        return float(value)
    if property_name in TEXT_PHASE3E_COLOR_PROPERTIES:
        return [float(component) for component in value]
    return value


def _text_basic_sha256(property_name: str, value: Any) -> str:
    canonical = _text_basic_canonical_value(property_name, value)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _text_basic_requested_value(operation: dict[str, Any]) -> Any:
    property_name = operation.get("property")
    if property_name in TEXT_PHASE3E_COLOR_PROPERTIES:
        values = operation.get("arg_values")
        if not isinstance(values, dict):
            values = operation.get("args") if isinstance(operation.get("args"), dict) else {}
        return [values.get("red"), values.get("green"), values.get("blue"), values.get("alpha")]
    return operation["args"][0] if operation.get("args") else None


def _phase3e_text_basic_token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    baseline: Any,
    requested: Any,
) -> dict[str, Any]:
    property_name = operation["property"]
    return {
        "version": PHASE3E_TEXT_BASIC_TOKEN_VERSION,
        "operation_kind": PHASE3E_TEXT_BASIC_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": "Text",
        "profile": item["profile"],
        "property": property_name,
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": _text_basic_canonical_value(property_name, baseline),
        "baseline_sha256": _text_basic_sha256(property_name, baseline),
        "requested": _text_basic_canonical_value(property_name, requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3e_text_basic_confirm_token(**payload_args: Any) -> str:
    payload = _phase3e_text_basic_token_payload(**payload_args)
    return encode_confirm_token(
        "textBasic",
        PHASE3E_TEXT_BASIC_TOKEN_VERSION,
        payload,
        _LIGHT_WRITE_TOKEN_SECRET,
    )


def _decode_phase3e_text_basic_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    payload, error = decode_confirm_token(
        token,
        "textBasic",
        PHASE3E_TEXT_BASIC_TOKEN_VERSION,
        _LIGHT_WRITE_TOKEN_SECRET,
    )
    if error == "malformed":
        return None, "Phase 3E Text Basics confirm_token is malformed or has an unsupported version."
    if error == "signature":
        return None, "Phase 3E Text Basics confirm_token signature is invalid."
    if error == "payload" or payload is None:
        return None, "Phase 3E Text Basics confirm_token payload is invalid."
    return payload, None


def dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    text_operation = operation(item)
    if text_operation is None or not isinstance(before, dict) or before.get("type") != "Text":
        return {}
    property_name = text_operation["property"]
    baseline = before.get(property_name)
    requested = _text_basic_requested_value(text_operation)
    if not _text_basic_value_valid(property_name, baseline):
        return {property_name: f"Phase 3E Text Basics requires readable {property_name} baseline."}
    if not _text_basic_value_valid(property_name, requested):
        return {property_name: f"Phase 3E Text Basics requested {property_name} value is invalid."}
    return {}


def annotate_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    text_operation = operation(item)
    if text_operation is None:
        return []
    property_name = text_operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = _text_basic_requested_value(text_operation)
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == "Text"
        and cue_id == item.get("cue_ref")
        and _text_basic_value_valid(property_name, baseline)
        and _text_basic_value_valid(property_name, requested)
    )
    if not candidate:
        text_operation.pop("confirm_token", None)
        return []
    text_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3e_text_basic_candidate": True,
            "planned_only_reason": "text_basic_requires_confirm_token",
            "future_gate_requirements": [
                "phase3e_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    text_operation["confirm_token"] = _phase3e_text_basic_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=text_operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def validate_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    text_operation = operation(item)
    property_name = text_operation.get("property") if text_operation else "text_basic"
    if text_operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3E Text Basics preflight is incomplete."}
    if item.get("profile") != "text_basic" or before.get("type") != "Text":
        return {property_name: "Phase 3E Text Basics real writes require a Text cue and text_basic profile."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3E Text Basics real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3E Text Basics real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = _text_basic_requested_value(text_operation)
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 3E fresh read uniqueID does not exactly match requested cue UUID."}
    if not _text_basic_value_valid(property_name, baseline):
        return {property_name: f"Phase 3E Text Basics requires readable {property_name} baseline."}
    if not _text_basic_value_valid(property_name, requested):
        return {property_name: f"Phase 3E Text Basics requested {property_name} value is invalid."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase3e_text_basic_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 3E Text Basics confirm_token is invalid."}
    token_operation = dict(text_operation)
    token_operation["risk_tier"] = "high"
    expected = _phase3e_text_basic_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=token_operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 3E Text Basics confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    baseline_matches = (
        math.isclose(
            float(payload.get("baseline", math.nan)),
            float(expected["baseline"]),
            abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
            rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
        )
        if property_name in {"fixedWidth", "text/format/fontSize", "text/format/lineSpacing"}
        else payload.get("baseline") == expected["baseline"]
    )
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not baseline_matches:
        return {
            property_name: (
                f"stale_text_basic_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def mark_real_operation(item: dict[str, Any]) -> None:
    text_operation = operation(item)
    if text_operation is None:
        return
    text_operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3e_text_basic_candidate": True,
            "future_gate_requirements": [
                "phase3e_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    text_operation.pop("planned_only_reason", None)


def label_rejection(item: dict[str, Any]) -> None:
    text_operation = operation(item)
    if text_operation is not None:
        text_operation["planned_only_reason"] = "text_basic_requires_confirm_token"


def refresh_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    text_operation = operation(item)
    if text_operation is None or not result.get("executed_operations"):
        return
    property_name = text_operation["property"]
    for result_operation in result.get("operations") or []:
        if result_operation.get("property") == property_name:
            result_operation["real_write_enabled"] = True
            result_operation["real_write_possible"] = True
            result_operation["requires_confirm_token"] = True
            result_operation.pop("planned_only_reason", None)
    for planned_operation in result.get("planned_operations") or []:
        if (
            planned_operation.get("operation") == "set_property"
            and planned_operation.get("property") == property_name
        ):
            planned_operation["real_write_enabled"] = True
            planned_operation["real_write_possible"] = True
            planned_operation["requires_confirm_token"] = True
            planned_operation.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        plan["status"] = result.get("status")
        plan["intent"] = f"Executed saved {property_name} change on Text cue."
        plan["real_write_enabled"] = True
        plan["real_write_possible"] = True
        plan["requires_confirm_token"] = True
        plan.pop("why_not_written", None)
        plan["after"] = (result.get("after") or {}).get(property_name)
        plan["verification"] = {"readback_matched": result.get("errors") is None}
        safety = dict(plan.get("safety") or {})
        safety.update({"no_executed_operations": False, "will_modify_qlab": True})
        plan["safety"] = safety
