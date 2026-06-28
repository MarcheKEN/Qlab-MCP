"""Gated mutating OSC operations for QLab write mode."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import time
from typing import Any
from uuid import UUID

from ..errors import OscTimeoutError, UnsafeWriteOperationError
from ..osc.addressing import (
    _clean_cue_ref,
    _clean_workspace_id,
    _cue_address,
    _normalize_id_list,
    _workspace_address,
)
from ..runtime.read_cache import shared_read_cache
from ..settings.light_commands import analyze_light_command_text
from .allowlist import (
    COMMON_UPDATE_PROFILE,
    VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES,
    ensure_real_write_allowed,
    normalize_update_request,
    read_keys_for_operations,
    real_write_permission_errors,
    validate_update_profile,
    validate_update_profile_for_cue,
    validate_writable_cue_type,
    validate_write_properties,
)
from .safety import check_write_readiness, ensure_write_ready, resolve_dry_run


MAX_BATCH_UPDATES = 50
AFTER_READ_RETRY_DELAYS = (0.2, 0.5, 1.0)
UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS = 90.0
UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS = 0.1
UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS = 8.0
UPDATE_AFTER_READ_TIMEOUT_CAP_SECONDS = 0.5
UPDATE_MIN_REPLY_TIMEOUT_SECONDS = 0.001
UPDATE_NUMERIC_MATCH_ABS_TOLERANCE = 1e-5
UPDATE_NUMERIC_MATCH_REL_TOLERANCE = 1e-6
UPDATE_STATUS_ACTIONS = {
    "preflight_failed": "Inspect per-cue errors; no setters were sent, so fix cue refs/profiles before retrying.",
    "partial_failed": "Inspect per-cue errors and verify the affected cues in QLab before retrying only failed items.",
    "verification_failed": "Read the cue fresh and compare requested versus after values before retrying.",
    "verification_inconclusive": "Treat the update as unsafe; inspect executed operations and add deterministic readback before retrying.",
}
UPDATE_STATUS_CODES = {
    "preflight_failed": "QLAB_UPDATE_PREFLIGHT_FAILED",
    "partial_failed": "QLAB_UPDATE_PARTIAL_FAILED",
    "verification_failed": "QLAB_UPDATE_VERIFICATION_FAILED",
    "verification_inconclusive": "QLAB_UPDATE_VERIFICATION_INCONCLUSIVE",
}
CONTINUE_MODE_VALUES = {
    0: 0,
    1: 1,
    2: 2,
    "0": 0,
    "1": 1,
    "2": 2,
    "do_not_continue": 0,
    "do-not-continue": 0,
    "manual": 0,
    "none": 0,
    "auto_continue": 1,
    "auto-continue": 1,
    "autocontinue": 1,
    "auto_follow": 2,
    "auto-follow": 2,
    "autofollow": 2,
}
CASEFOLD_COMPARISON_KEYS = {
    "blendMode",
    "clockType",
    "colorName",
    "text/format/alignment",
    "text/format/strikethroughStyle",
    "text/format/underlineStyle",
}
LIGHT_COMMAND_PROPERTY = "lightCommandText"
LIGHT_BEHAVIOR_PROPERTIES = frozenset({"alwaysCollate", "subcontroller"})
VIDEO_PHASE2_PROFILES = frozenset({"video_basic", "camera_basic", "text_basic"})
VIDEO_PHASE3_OPACITY_PROPERTY = "opacity"
VIDEO_PHASE3_OPACITY_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
VIDEO_PHASE3_TRANSLATION_PROPERTIES = frozenset({"translation/x", "translation/y"})
VIDEO_PHASE3_TRANSLATION_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
VIDEO_PHASE3_SCALAR_PROPERTIES = frozenset(
    {
        "scale/x",
        "scale/y",
        "anchor/x",
        "anchor/y",
        "cropTop",
        "cropBottom",
        "cropLeft",
        "cropRight",
    }
)
VIDEO_PHASE3_SCALAR_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
VIDEO_PHASE3_APPEARANCE_PROPERTIES = frozenset({"blendMode", "preserveAspectRatio"})
VIDEO_PHASE3_APPEARANCE_TYPES = {
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
}
TEXT_PHASE3E_PROPERTIES = frozenset(
    {"text", "text/format/fontSize", "text/format/alignment"}
)
TEXT_PHASE3F_PROPERTIES = frozenset(
    {
        "text/format/shadowBlurRadius",
        "text/format/shadowOffset/width",
        "text/format/shadowOffset/height",
        "text/format/underlineStyle",
        "text/format/strikethroughStyle",
    }
)
VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES = frozenset(
    {
        "videoEffect/enabled",
        "videoEffectIndex/enabled",
        "videoEffect/parameter",
        "videoEffectIndex/parameter",
    }
)
VIDEO_PHASE4C_FX_SCALAR_PROPERTY = "videoEffectIndex/parameter"
VIDEO_PHASE4C_FX_ALLOWED_PARAMETER = "inputRadius"
VIDEO_PHASE4C_FX_ALLOWED_INDEX = 0
VIDEO_PHASE2_HEALTH_READ_KEYS = (
    "number",
    "name",
    "armed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isAuditioning",
)
PHASE4_LIGHT_OPERATION_KIND = "phase4_light_command_text_write"
PHASE4_LIGHT_TOKEN_VERSION = 1
PHASE5_LIGHT_OPERATION_KIND = "phase5_light_behavior_flag_write"
PHASE5_LIGHT_TOKEN_VERSION = 1
PHASE3_VIDEO_OPACITY_OPERATION_KIND = "video_phase3_opacity_write"
PHASE3_VIDEO_OPACITY_TOKEN_VERSION = 1
PHASE3_VIDEO_TRANSLATION_OPERATION_KIND = "video_phase3b_translation_write"
PHASE3_VIDEO_TRANSLATION_TOKEN_VERSION = 1
PHASE3_VIDEO_SCALAR_OPERATION_KIND = "video_phase3c_scalar_write"
PHASE3_VIDEO_SCALAR_TOKEN_VERSION = 1
PHASE3_VIDEO_APPEARANCE_OPERATION_KIND = "video_phase3d_appearance_write"
PHASE3_VIDEO_APPEARANCE_TOKEN_VERSION = 1
PHASE3E_TEXT_BASIC_OPERATION_KIND = "video_phase3e_text_basic_write"
PHASE3E_TEXT_BASIC_TOKEN_VERSION = 1
PHASE3F_TEXT_STYLE_OPERATION_KIND = "video_phase3f_text_style_write"
PHASE3F_TEXT_STYLE_TOKEN_VERSION = 1
PHASE4C_VIDEO_FX_SCALAR_OPERATION_KIND = "video_phase4c_fx_scalar_write"
PHASE4C_VIDEO_FX_SCALAR_TOKEN_VERSION = 1
_LIGHT_WRITE_TOKEN_SECRET = secrets.token_bytes(32)


def _write_workspace_resolution_error(
    workspace_id: str,
    *,
    dry_run: bool,
    status: str,
    message: str,
    requested_count: int = 0,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": requested_count,
        "planned_count": 0,
        "updated_count": 0,
        "failed_count": requested_count,
        "timeout_confirmed_count": 0,
        "results": [],
        "planned_operations": [],
        "executed_operations": [],
        "errors": {"workspace_resolution": message},
        "warnings": ["Requested workspace could not be resolved."],
        "error_code": status,
        "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
        "message": "Requested workspace could not be resolved; no mutating OSC commands were planned or sent.",
    }


class QLabWriteMixin:
    def check_write_readiness(self, workspace_id: str) -> dict[str, Any]:
        return check_write_readiness(self, workspace_id)

    def create_cue(
        self,
        workspace_id: str,
        cue_type: str,
        properties: dict[str, Any] | None = None,
        dry_run: bool | None = None,
        after_cue_id: str | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        effective_dry_run = resolve_dry_run(self, dry_run)
        qlab_cue_type = validate_writable_cue_type(cue_type)
        normalized_properties = validate_write_properties(properties)
        placement = _normalize_placement(after_cue_id)

        if placement is not None and not effective_dry_run:
            raise UnsafeWriteOperationError(
                "after_cue_id placement is only available in dry-run during this write-mode preface."
            )

        if effective_dry_run:
            try:
                workspace = self._resolve_workspace_id_strict(workspace)
            except Exception as exc:
                return {
                    "ok": False,
                    "status": getattr(exc, "status", "workspace_not_found"),
                    "workspace_id": _clean_workspace_id(workspace_id),
                    "cue_type": qlab_cue_type,
                    "dry_run": True,
                    "created_cue_id": None,
                    "placement": placement,
                    "properties": normalized_properties,
                    "planned_operations": [],
                    "executed_operations": [],
                    "verification": None,
                    "errors": {"workspace_resolution": str(exc)},
                    "warnings": ["Requested workspace could not be resolved."],
                    "error_code": getattr(exc, "status", "workspace_not_found"),
                    "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                    "message": "Requested workspace could not be resolved; no cue create operation was planned or sent.",
                }
            planned_operations = _planned_create_operations(workspace, qlab_cue_type, normalized_properties, placement)
            return {
                "ok": True,
                "status": "dry_run",
                "workspace_id": workspace,
                "cue_type": qlab_cue_type,
                "dry_run": True,
                "created_cue_id": None,
                "placement": placement,
                "properties": normalized_properties,
                "planned_operations": planned_operations,
                "executed_operations": [],
                "verification": None,
                "warnings": [
                    "Dry run only: no mutating OSC commands were sent to QLab.",
                ],
                "message": "Dry run succeeded; review planned_operations before disabling dry_run.",
            }

        workspace = ensure_write_ready(self, workspace)
        planned_operations = _planned_create_operations(workspace, qlab_cue_type, normalized_properties, placement)

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()

        executed_operations: list[dict[str, Any]] = []
        warnings: list[str] = []
        errors: dict[str, str] = {}
        before_ids = _try_workspace_cue_ids(self, workspace)
        new_address = _workspace_address(workspace, "new")
        try:
            new_reply = self.client.request(new_address, qlab_cue_type)
            created_cue_id = _extract_created_cue_id(new_reply.data)
            new_status = new_reply.status
        except OscTimeoutError as exc:
            created_cue_id = _resolve_created_cue_after_timeout(self, workspace, before_ids)
            new_status = "timeout_confirmed_by_fresh_read"
            warnings.append(f"QLab did not reply to /new, but a fresh cue ID diff found created cue {created_cue_id}.")
            if created_cue_id is None:
                raise UnsafeWriteOperationError(f"QLab did not reply to /new and the created cue could not be identified: {exc}") from exc
        executed_operations.append(
            {
                "operation": "new",
                "address": new_address,
                "args": [qlab_cue_type],
                "status": new_status,
                "created_cue_id": created_cue_id,
            }
        )

        for key, value in normalized_properties.items():
            address = _cue_id_address(workspace, created_cue_id, key)
            try:
                reply = self.client.request(address, value)
                status = reply.status
                error = None
            except OscTimeoutError as exc:
                status = "timeout_pending_verification"
                error = str(exc)
                warnings.append(f"QLab did not reply to setter {key}; fresh verification is authoritative.")
            except Exception as exc:
                errors[key] = str(exc)
                break
            executed_operations.append(
                {
                    "operation": "set_property",
                    "property": key,
                    "address": address,
                    "args": [value],
                    "status": status,
                    **({"error": error} if error else {}),
                }
            )

        read_cache.clear()
        verification = self.get_cue_details(workspace, created_cue_id, "auto")
        read_cache.clear()
        verification_properties = verification.get("properties") if isinstance(verification, dict) else {}
        verified = _properties_match(verification_properties, normalized_properties)
        if errors or not verified:
            status = "verification_failed"
            ok = False
            message = "Cue create command was sent, but fresh verification did not confirm all requested properties."
        else:
            status = "created"
            ok = True
            message = "Cue created, safe initial properties applied, and cue details read back fresh."

        return {
            "ok": ok,
            "status": status,
            "workspace_id": workspace,
            "cue_type": qlab_cue_type,
            "dry_run": False,
            "created_cue_id": created_cue_id,
            "placement": placement,
            "properties": normalized_properties,
            "planned_operations": planned_operations,
            "executed_operations": executed_operations,
            "verification": verification,
            "errors": errors or None,
            "warnings": warnings,
            "message": message,
        }

    def update_cue(
        self,
        workspace_id: str,
        cue_ref: str,
        properties: dict[str, Any] | None = None,
        dry_run: bool | None = None,
        profile: str | None = None,
        operations: list[dict[str, Any]] | None = None,
        confirm_gates: list[str] | None = None,
    ) -> dict[str, Any]:
        """Compatibility wrapper for local Python callers; MCP exposes qlab_update_cues."""
        raw_update = {
            "cue_ref": cue_ref,
            "profile": profile or COMMON_UPDATE_PROFILE,
            "properties": properties,
            "operations": operations,
            "confirm_gates": confirm_gates,
        }
        _normalize_batch_update_item(raw_update)
        batch = self.update_cues(
            workspace_id,
            [raw_update],
            dry_run=dry_run,
        )
        item = dict(batch["results"][0])
        if not batch["ok"] and batch["status"] == "preflight_failed" and not batch["dry_run"]:
            messages = []
            if item.get("errors"):
                messages.extend(str(message) for message in item["errors"].values())
            if batch.get("errors"):
                messages.extend(str(message) for message in batch["errors"].values())
            message = "; ".join(messages) or batch["message"]
            if (
                "gated or dry-run only" in message
                or "outside QLAB_ALLOWED_FILE_ROOTS" in message
                or item.get("errors", {}).get("write_readiness")
            ):
                raise UnsafeWriteOperationError(message)
        if not batch["ok"] and batch["status"] == "preflight_failed" and item.get("errors") and "profile" in item["errors"]:
            raise UnsafeWriteOperationError("; ".join(item["errors"].values()))
        status = item["status"]
        if item.get("errors") and "cue" in item["errors"]:
            status = "cue_not_found"
        if status == "updated_with_confirmed_timeouts":
            status = "updated"
        result = {
            "ok": batch["ok"],
            "status": status,
            "workspace_id": batch["workspace_id"],
            "cue_ref": item["cue_ref"],
            "profile": item["profile"],
            "dry_run": batch["dry_run"],
            "properties": item["properties"],
            "operations": item["operations"],
            "confirm_gates": item.get("confirm_gates", []),
            "before": item["before"],
            "after": item["after"],
            "diff": item["diff"],
            "planned_operations": item["planned_operations"],
            "executed_operations": item["executed_operations"],
            "verification": {"properties": item["after"]} if item.get("after") else None,
            "errors": item["errors"],
            "warnings": item["warnings"],
            "notices": item.get("notices", []),
            "message": batch["message"],
        }
        if item.get("updateq_plan") is not None:
            result["updateq_plan"] = item["updateq_plan"]
        return result

    def update_cues(
        self,
        workspace_id: str,
        updates: list[dict[str, Any]],
        dry_run: bool | None = None,
    ) -> dict[str, Any]:
        workspace = _clean_workspace_id(workspace_id)
        if not isinstance(updates, list):
            raise UnsafeWriteOperationError("updates must be a list")
        if not updates:
            raise UnsafeWriteOperationError("updates must include at least one cue update")
        if len(updates) > MAX_BATCH_UPDATES:
            raise UnsafeWriteOperationError(f"updates can include at most {MAX_BATCH_UPDATES} cue updates")
        effective_dry_run = resolve_dry_run(self, dry_run)
        phase4_light_call = any(_raw_update_requests_light_command(raw_update) for raw_update in updates)
        phase5_light_call = any(_raw_update_requests_light_behavior(raw_update) for raw_update in updates)
        items = [_normalize_batch_update_item_for_batch(raw_update) for raw_update in updates]
        phase3_video_opacity_call = any(_phase3_video_opacity_operation(item) is not None for item in items)
        phase3_video_translation_call = any(
            _phase3_video_translation_operation(item) is not None for item in items
        )
        phase3_video_scalar_call = any(
            _phase3_video_scalar_operation(item) is not None for item in items
        )
        phase3_video_appearance_call = any(
            _phase3_video_appearance_operation(item) is not None for item in items
        )
        phase3e_text_basic_call = any(
            _phase3e_text_basic_operation(item) is not None for item in items
        )
        phase3f_text_style_call = any(
            _phase3f_text_style_operation(item) is not None for item in items
        )
        phase4c_video_fx_scalar_call = any(
            _phase4c_video_fx_scalar_operation(item) is not None for item in items
        )
        for item in items:
            _strip_video_phase2_confirm_tokens(item)
            if item.get("profile") in VIDEO_PHASE2_PROFILES and item.get("operations"):
                item["read_keys"] = list(dict.fromkeys([*item["read_keys"], *VIDEO_PHASE2_HEALTH_READ_KEYS]))
        video_phase2_dry_run_errors = (
            [_video_phase2_dry_run_blocked_errors(item) for item in items]
            if effective_dry_run
            else []
        )
        if any(video_phase2_dry_run_errors):
            results = []
            for item, blocked_errors in zip(items, video_phase2_dry_run_errors, strict=True):
                errors = dict(item.get("errors") or {})
                errors.update(blocked_errors)
                if not errors:
                    errors["video_phase2"] = (
                        "Batch rejected because another Video-family operation is blocked even for dry-run."
                    )
                results.append(
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=None,
                        status="dry_run_preflight_failed",
                        before=None,
                        after=None,
                        errors=errors,
                        warnings=["Dry run rejected before any OSC request was sent to QLab."],
                    )
                )
            return _batch_update_result(
                workspace,
                dry_run=True,
                results=results,
                status="preflight_failed",
                requested_count=len(items),
                errors={
                    "preflight": (
                        "Video-family dry-run policy blocks this property; no OSC requests were sent."
                    )
                },
            )
        for item in items:
            _bind_confirm_tokens(workspace, item)
        video_phase2_dry_run_structure_error = (
            _video_phase2_dry_run_structure_error(items) if effective_dry_run else None
        )
        video_fx_dry_run_structure_error = (
            _video_fx_dry_run_structure_error(items) if effective_dry_run else None
        )
        if video_phase2_dry_run_structure_error or video_fx_dry_run_structure_error:
            structure_error = video_phase2_dry_run_structure_error or video_fx_dry_run_structure_error
            results = [
                _batch_item_result(
                    workspace,
                    item,
                    cue_id=None,
                    status="dry_run_preflight_failed",
                    before=None,
                    after=None,
                    errors={
                        **(item.get("errors") or {}),
                        "video_phase2": structure_error,
                    },
                    warnings=["Dry run only: no mutating OSC commands were sent to QLab."],
                )
                for item in items
            ]
            return _batch_update_result(
                workspace,
                dry_run=True,
                results=results,
                status="preflight_failed",
                requested_count=len(items),
                errors={"preflight": structure_error},
            )
        if not effective_dry_run:
            phase4_structure_error = _phase4_light_call_structure_error(items) if phase4_light_call else None
            phase5_structure_error = _phase5_light_call_structure_error(items) if phase5_light_call else None
            phase3_structure_error = (
                _phase3_video_opacity_call_structure_error(items) if phase3_video_opacity_call else None
            )
            phase3_translation_structure_error = (
                _phase3_video_translation_call_structure_error(items)
                if phase3_video_translation_call
                else None
            )
            phase3_scalar_structure_error = (
                _phase3_video_scalar_call_structure_error(items)
                if phase3_video_scalar_call
                else None
            )
            phase3_appearance_structure_error = (
                _phase3_video_appearance_call_structure_error(items)
                if phase3_video_appearance_call
                else None
            )
            phase3e_text_structure_error = (
                _phase3e_text_basic_call_structure_error(items)
                if phase3e_text_basic_call
                else None
            )
            phase3f_text_structure_error = (
                _phase3f_text_style_call_structure_error(items)
                if phase3f_text_style_call
                else None
            )
            phase4c_video_fx_structure_error = (
                _phase4c_video_fx_scalar_call_structure_error(items)
                if phase4c_video_fx_scalar_call
                else None
            )
            gate_results = []
            gate_ok = True
            for item in items:
                errors = dict(item.get("errors") or {})
                if not errors and phase4_structure_error:
                    errors[LIGHT_COMMAND_PROPERTY] = phase4_structure_error
                elif not errors and phase5_structure_error:
                    errors["light_behavior"] = phase5_structure_error
                elif not errors and phase4_light_call:
                    if len(item["confirm_gates"]) != 1:
                        errors[LIGHT_COMMAND_PROPERTY] = (
                            "lightCommandText is gated or dry-run only without exactly one reviewed "
                            "Phase 4 confirm_token."
                        )
                elif not errors and phase5_light_call:
                    property_name = item["operations"][0]["property"]
                    if len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 5 confirm_token."
                        )
                elif not errors and phase3_video_opacity_call:
                    if phase3_structure_error:
                        errors[VIDEO_PHASE3_OPACITY_PROPERTY] = phase3_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[VIDEO_PHASE3_OPACITY_PROPERTY] = (
                            "opacity is gated or dry-run only without exactly one reviewed "
                            "Phase 3A confirm_token."
                        )
                elif not errors and phase3_video_translation_call:
                    property_name = item["operations"][0]["property"]
                    if phase3_translation_structure_error:
                        errors[property_name] = phase3_translation_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 3B confirm_token."
                        )
                elif not errors and phase3_video_scalar_call:
                    property_name = item["operations"][0]["property"]
                    if phase3_scalar_structure_error:
                        errors[property_name] = phase3_scalar_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 3C confirm_token."
                        )
                elif not errors and phase3_video_appearance_call:
                    property_name = item["operations"][0]["property"]
                    if phase3_appearance_structure_error:
                        errors[property_name] = phase3_appearance_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 3D confirm_token."
                        )
                elif not errors and phase3e_text_basic_call:
                    property_name = item["operations"][0]["property"]
                    if phase3e_text_structure_error:
                        errors[property_name] = phase3e_text_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 3E confirm_token."
                        )
                elif not errors and phase3f_text_style_call:
                    property_name = item["operations"][0]["property"]
                    if phase3f_text_structure_error:
                        errors[property_name] = phase3f_text_structure_error
                    else:
                        errors[property_name] = (
                            f"{property_name} real write is blocked: QLab 5.5.10 did not provide "
                            "reliable fresh readback for Phase 3F Text Style validation."
                        )
                elif not errors and phase4c_video_fx_scalar_call:
                    property_name = item["operations"][0]["property"]
                    if phase4c_video_fx_structure_error:
                        errors[property_name] = phase4c_video_fx_structure_error
                    elif len(item["confirm_gates"]) != 1:
                        errors[property_name] = (
                            f"{property_name} is gated or dry-run only without exactly one reviewed "
                            "Phase 4C confirm_token."
                        )
                elif not errors:
                    errors.update(_video_phase2_real_write_errors(item))
                    if not errors:
                        errors.update(real_write_permission_errors(item["profile"], item["operations"], item["confirm_gates"]))
                if errors:
                    gate_ok = False
                gate_results.append(
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=None,
                        status="preflight_failed" if errors else "planned",
                        before=None,
                        after=None,
                        errors=errors or None,
                        warnings=[],
                    )
                )
            if not gate_ok:
                return _batch_update_result(
                    workspace,
                    dry_run=False,
                    results=gate_results,
                    status="preflight_failed",
                    requested_count=len(updates),
                    errors={"preflight": "One or more cue updates failed real-write gate preflight; no setters were sent."},
                )
        if effective_dry_run:
            try:
                workspace = self._resolve_workspace_id_strict(workspace)
            except Exception as exc:
                return _write_workspace_resolution_error(
                    _clean_workspace_id(workspace_id),
                    dry_run=True,
                    status=getattr(exc, "status", "workspace_not_found"),
                    message=str(exc),
                    requested_count=len(updates),
                )

        if effective_dry_run:
            results = []
            phase5_candidate_shape = (
                phase5_light_call
                and not phase4_light_call
                and _phase5_light_call_structure_error(items) is None
            )
            phase3_candidate_shape = (
                phase3_video_opacity_call
                and not phase4_light_call
                and not phase5_light_call
                and _phase3_video_opacity_call_structure_error(items) is None
            )
            phase3_translation_candidate_shape = (
                phase3_video_translation_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and _phase3_video_translation_call_structure_error(items) is None
            )
            phase3_scalar_candidate_shape = (
                phase3_video_scalar_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and not phase3_video_translation_call
                and _phase3_video_scalar_call_structure_error(items) is None
            )
            phase3_appearance_candidate_shape = (
                phase3_video_appearance_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and not phase3_video_translation_call
                and not phase3_video_scalar_call
                and _phase3_video_appearance_call_structure_error(items) is None
            )
            phase3e_text_candidate_shape = (
                phase3e_text_basic_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and not phase3_video_translation_call
                and not phase3_video_scalar_call
                and not phase3_video_appearance_call
                and _phase3e_text_basic_call_structure_error(items) is None
            )
            phase3f_text_candidate_shape = (
                phase3f_text_style_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and not phase3_video_translation_call
                and not phase3_video_scalar_call
                and not phase3_video_appearance_call
                and not phase3e_text_basic_call
                and _phase3f_text_style_call_structure_error(items) is None
            )
            phase4c_video_fx_candidate_shape = (
                phase4c_video_fx_scalar_call
                and not phase4_light_call
                and not phase5_light_call
                and not phase3_video_opacity_call
                and not phase3_video_translation_call
                and not phase3_video_scalar_call
                and not phase3_video_appearance_call
                and not phase3e_text_basic_call
                and not phase3f_text_style_call
                and _phase4c_video_fx_scalar_call_structure_error(items) is None
            )
            light_patch: dict[str, Any] | None = None
            light_patch_error: dict[str, str] | None = None
            light_patch_loaded = False
            for item in items:
                errors = dict(item.get("errors") or {})
                before = None
                warnings = ["Dry run only: no mutating OSC commands were sent to QLab."]
                if not errors and item["cue_ref"]:
                    before, read_errors = _try_read_update_values(self, workspace, item["cue_ref"], item["read_keys"])
                    errors.update(read_errors)
                    errors.update(_validate_profile_for_before(item["profile"], before))
                    errors.update(_video_phase2_dry_run_identity_errors(item, before))
                    errors.update(_video_phase2_dry_run_health_errors(item, before))
                    errors.update(_phase3_video_translation_dry_run_errors(item, before))
                    errors.update(_phase3_video_scalar_dry_run_errors(item, before))
                    errors.update(_phase3_video_appearance_dry_run_errors(item, before))
                    errors.update(_phase3e_text_basic_dry_run_errors(item, before))
                    errors.update(_phase3f_text_style_dry_run_errors(item, before))
                    errors.update(_video_fx_dry_run_errors(item, before))
                if not errors and _light_command_operation(item) is not None:
                    if not light_patch_loaded:
                        light_patch, light_patch_error = _try_read_safe_light_patch(self, workspace)
                        light_patch_loaded = True
                    warnings.extend(
                        _annotate_light_command_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            light_patch=light_patch,
                            patch_error=light_patch_error,
                        )
                    )
                if not errors and _light_behavior_operation(item) is not None:
                    warnings.extend(
                        _annotate_light_behavior_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase5_candidate_shape,
                        )
                    )
                if not errors and _phase3_video_opacity_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3_video_opacity_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3_candidate_shape,
                        )
                    )
                if not errors and _phase3_video_translation_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3_video_translation_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3_translation_candidate_shape,
                        )
                    )
                if not errors and _phase3_video_scalar_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3_video_scalar_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3_scalar_candidate_shape,
                        )
                    )
                if not errors and _phase3_video_appearance_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3_video_appearance_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3_appearance_candidate_shape,
                        )
                    )
                if not errors and _phase3e_text_basic_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3e_text_basic_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3e_text_candidate_shape,
                        )
                    )
                if not errors and _phase3f_text_style_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase3f_text_style_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase3f_text_candidate_shape,
                        )
                    )
                if not errors and _phase4c_video_fx_scalar_operation(item) is not None:
                    warnings.extend(
                        _annotate_phase4c_video_fx_scalar_operation(
                            item,
                            workspace_id=workspace,
                            before=before,
                            candidate_shape=phase4c_video_fx_candidate_shape,
                        )
                    )
                elif not errors and _video_fx_dry_run_operation(item) is not None:
                    _annotate_video_fx_dry_run_operation(item, workspace, before)
                cue_id = _resolved_cue_id(before)
                results.append(
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=cue_id,
                        status="dry_run" if not errors else "dry_run_preflight_failed",
                        before=before,
                        after=None,
                        errors=errors or None,
                        warnings=warnings,
                        notices=_video_phase2_dry_run_notices(item, before),
                    )
                )
            failed_count = sum(1 for result in results if result["errors"])
            return _batch_update_result(
                workspace,
                dry_run=True,
                results=results,
                status="dry_run" if failed_count == 0 else "preflight_failed",
                requested_count=len(updates),
                warnings=["Dry run only: no mutating OSC commands were sent to QLab."],
            )

        try:
            workspace = ensure_write_ready(self, workspace)
        except Exception as exc:
            return _batch_update_result(
                workspace,
                dry_run=False,
                results=[
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=None,
                        status="preflight_failed",
                        before=None,
                        after=None,
                        errors={"write_readiness": str(exc)},
                        warnings=[],
                    )
                    for item in items
                ],
                status="preflight_failed",
                requested_count=len(updates),
                errors={"write_readiness": str(exc)},
            )
        file_root_errors = _file_target_root_errors(self, items)
        if file_root_errors:
            return _batch_update_result(
                workspace,
                dry_run=False,
                results=[
                    _batch_item_result(
                        workspace,
                        item,
                        cue_id=None,
                        status="preflight_failed" if index in file_root_errors else "planned",
                        before=None,
                        after=None,
                        errors=file_root_errors.get(index),
                        warnings=[],
                    )
                    for index, item in enumerate(items)
                ],
                status="preflight_failed",
                requested_count=len(updates),
                errors={"preflight": "One or more fileTarget paths failed root validation; no setters were sent."},
            )
        update_deadline = time.monotonic() + UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS
        setter_count = sum(len(item["operations"]) for item in items)
        setter_reply_timeout = _setter_reply_timeout(self, setter_count, update_deadline)

        read_cache = getattr(self, "_read_cache", shared_read_cache())
        read_cache.clear()
        preflight_results: list[dict[str, Any]] = []
        preflight_ok = True
        for item in items:
            before = None
            before_errors: dict[str, str] = {}
            errors = dict(item.get("errors") or {})
            if not errors and item["cue_ref"]:
                before, before_errors = _try_read_update_values(self, workspace, item["cue_ref"], item["read_keys"])
            resolved_cue_id = _resolved_cue_id(before)
            errors.update(before_errors)
            if not item.get("errors") and (before is None or not resolved_cue_id):
                errors.setdefault("cue", "Cue could not be read before update.")
            if not item.get("errors"):
                errors.update(_validate_profile_for_before(item["profile"], before))
            if not item.get("errors"):
                errors.update(_validate_contextual_real_write(self, workspace, item, before))
            if not errors and phase4_light_call:
                errors.update(_validate_phase4_light_real_write(self, workspace, item, before))
            elif not errors and phase5_light_call:
                errors.update(_validate_phase5_light_real_write(workspace, item, before))
            elif not errors and phase3_video_opacity_call:
                errors.update(_validate_phase3_video_opacity_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3_video_opacity_real_operation(item)
            elif not errors and phase3_video_translation_call:
                errors.update(_validate_phase3_video_translation_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3_video_translation_real_operation(item)
            elif not errors and phase3_video_scalar_call:
                errors.update(_validate_phase3_video_scalar_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3_video_scalar_real_operation(item)
            elif not errors and phase3_video_appearance_call:
                errors.update(_validate_phase3_video_appearance_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3_video_appearance_real_operation(item)
            elif not errors and phase3e_text_basic_call:
                errors.update(_validate_phase3e_text_basic_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3e_text_basic_real_operation(item)
            elif not errors and phase3f_text_style_call:
                errors.update(_validate_phase3f_text_style_real_write(workspace, item, before))
                if not errors:
                    _mark_phase3f_text_style_real_operation(item)
            elif not errors and phase4c_video_fx_scalar_call:
                errors.update(_validate_phase4c_video_fx_scalar_real_write(workspace, item, before))
                if not errors:
                    _mark_phase4c_video_fx_scalar_real_operation(item)
            if errors:
                preflight_ok = False
                if phase3_video_scalar_call:
                    _label_phase3_video_scalar_rejection(item)
                if phase3_video_appearance_call:
                    _label_phase3_video_appearance_rejection(item)
                if phase3e_text_basic_call:
                    _label_phase3e_text_basic_rejection(item)
                if phase3f_text_style_call:
                    _label_phase3f_text_style_rejection(item)
                if phase4c_video_fx_scalar_call:
                    _label_phase4c_video_fx_scalar_rejection(item)
            preflight_results.append(
                _batch_item_result(
                    workspace,
                    item,
                    cue_id=resolved_cue_id,
                    status="planned" if not errors else "preflight_failed",
                    before=before,
                    after=None,
                    errors=errors or None,
                    warnings=[],
                )
            )

        if not preflight_ok:
            read_cache.clear()
            return _batch_update_result(
                workspace,
                dry_run=False,
                results=preflight_results,
                status="preflight_failed",
                requested_count=len(updates),
                errors={"preflight": "One or more cue updates failed preflight; no setters were sent."},
            )

        executed_items: list[dict[str, Any]] = []
        for item, planned in zip(items, preflight_results, strict=True):
            cue_id = planned["cue_id"]
            executed_operations: list[dict[str, Any]] = []
            errors: dict[str, str] = {}
            setter_timeouts: dict[str, str] = {}
            for operation in item["operations"]:
                key = operation["property"]
                address = _cue_id_address(workspace, cue_id, operation["path"])
                if _budget_remaining(update_deadline) <= 0:
                    errors[key] = "Global update time budget exhausted before setter was sent."
                    break
                try:
                    reply = self.client.request(
                        address,
                        *operation["args"],
                        reply_timeout=_bounded_reply_timeout(
                            self,
                            setter_reply_timeout,
                            update_deadline,
                        ),
                    )
                    status = reply.status
                    error = None
                except OscTimeoutError as exc:
                    setter_timeouts[key] = str(exc)
                    status = "timeout_pending_verification"
                    error = str(exc)
                except Exception as exc:
                    errors[key] = str(exc)
                    break
                executed_operations.append(
                    {
                        "operation": "set_property",
                        "property": key,
                        "address": address,
                        "args": operation["args"],
                        "mode": operation["mode"],
                        "capability_gate": operation.get("capability_gate"),
                        "status": status,
                        **({"error": error} if error else {}),
                    }
                )
            item_result = dict(planned)
            item_result["executed_operations"] = executed_operations
            item_result["_setter_timeouts"] = setter_timeouts
            item_result["_setter_errors"] = errors
            executed_items.append(item_result)

        read_cache.clear()
        final_results: list[dict[str, Any]] = []
        timeout_confirmed_count = 0
        for item, result in zip(items, executed_items, strict=True):
            requested_values = _verification_requested_values(item)
            after, after_errors = _try_read_update_values_with_retries(
                self,
                workspace,
                result["cue_id"],
                item["read_keys"],
                requested_values,
                retry_on_mismatch=bool(result["_setter_timeouts"]),
                request_timeout=_bounded_reply_timeout(
                    self,
                    UPDATE_AFTER_READ_TIMEOUT_CAP_SECONDS,
                    update_deadline,
                ),
                deadline=update_deadline,
            )
            confirmed_by_after = _properties_match(after, requested_values)
            setter_timeouts = result.pop("_setter_timeouts")
            setter_errors = result.pop("_setter_errors")
            unconfirmed_timeouts = {} if confirmed_by_after else setter_timeouts
            value_mismatch = {}
            if not confirmed_by_after and not setter_errors and not unconfirmed_timeouts and not after_errors:
                value_mismatch["verification"] = _verification_mismatch_message(after, requested_values)
            errors = {**setter_errors, **unconfirmed_timeouts, **after_errors, **value_mismatch}
            warnings = list(result["warnings"])
            unverifiable_operations = [
                operation
                for operation in item["operations"]
                if not operation.get("read_key") or len(operation.get("args") or []) != 1
            ]
            inconclusive = bool(unverifiable_operations)
            if setter_timeouts and confirmed_by_after:
                timeout_confirmed_count += 1
                warnings.append(
                    "setter_timeout_but_readback_matched"
                    if (
                        _phase3_video_opacity_operation(item) is not None
                        or _phase3_video_translation_operation(item) is not None
                        or _phase3_video_scalar_operation(item) is not None
                        or _phase3_video_appearance_operation(item) is not None
                        or _phase3e_text_basic_operation(item) is not None
                        or _phase3f_text_style_operation(item) is not None
                        or _phase4c_video_fx_scalar_operation(item) is not None
                    )
                    else "One or more setters did not reply, but fresh after-read confirmed requested values."
                )
            failed = bool(setter_errors) or bool(unconfirmed_timeouts)
            verification_failed = (bool(after_errors) or bool(value_mismatch)) and not failed
            if failed:
                status = "partial_failed"
            elif inconclusive:
                status = "verification_inconclusive"
                errors["verification"] = "No deterministic readback values were available for this real write."
            elif verification_failed:
                status = "verification_failed"
            elif setter_timeouts and (
                _phase3_video_opacity_operation(item) is not None
                or _phase3_video_translation_operation(item) is not None
                or _phase3_video_scalar_operation(item) is not None
                or _phase3_video_appearance_operation(item) is not None
                or _phase3e_text_basic_operation(item) is not None
                or _phase3f_text_style_operation(item) is not None
                or _phase4c_video_fx_scalar_operation(item) is not None
            ):
                status = "updated"
            elif setter_timeouts:
                status = "updated_with_confirmed_timeouts"
            else:
                status = "updated"
            result.update(
                {
                    "status": status,
                    "after": after,
                    "diff": _diff_properties(result["before"], requested_values, after),
                    "errors": errors or None,
                    "warnings": warnings,
                }
            )
            _refresh_phase3_video_opacity_real_result(result, item)
            _refresh_phase3_video_translation_real_result(result, item)
            _refresh_phase3_video_scalar_real_result(result, item)
            _refresh_phase3_video_appearance_real_result(result, item)
            _refresh_phase3e_text_basic_real_result(result, item)
            _refresh_phase3f_text_style_real_result(result, item)
            _refresh_phase4c_video_fx_scalar_real_result(result, item)
            if _update_debug_enabled(self):
                result["debug"] = {
                    "cue_ref": item["cue_ref"],
                    "cue_id": result["cue_id"],
                    "requested_properties": item["properties"],
                    "requested_values": requested_values,
                    "after_values": _after_values_for_requested(after, requested_values),
                    "properties_match": confirmed_by_after,
                    "setter_timeouts": setter_timeouts,
                    "confirmed_timeouts": bool(setter_timeouts and confirmed_by_after),
                    "setter_errors": setter_errors,
                    "final_status": status,
                }
            final_results.append(result)
        read_cache.clear()

        if any(result["status"] == "partial_failed" for result in final_results):
            status = "partial_failed"
        elif any(result["status"] == "verification_failed" for result in final_results):
            status = "verification_failed"
        elif any(result["status"] == "verification_inconclusive" for result in final_results):
            status = "verification_inconclusive"
        elif any(result["status"] == "updated_with_confirmed_timeouts" for result in final_results):
            status = "updated_with_confirmed_timeouts"
        else:
            status = "updated"
        return _batch_update_result(
            workspace,
            dry_run=False,
            results=final_results,
            status=status,
            requested_count=len(updates),
            timeout_confirmed_count=timeout_confirmed_count,
        )


def _normalize_placement(after_cue_id: str | None) -> dict[str, Any] | None:
    if after_cue_id is None:
        return None
    cue_id = _clean_cue_ref(after_cue_id)
    return {
        "after_cue_id": cue_id,
        "status": "planned_only",
        "message": "after_cue_id is accepted for dry-run planning only in this preface.",
    }


def _clean_update_cue_ref(cue_ref: str) -> str:
    cue = _clean_cue_ref(cue_ref)
    if cue.casefold() in {"selected", "playhead", "playbackposition", "active"}:
        raise UnsafeWriteOperationError("cue_ref for update must be a concrete cue number or unique ID")
    return cue


def _normalize_batch_update_item(raw_update: Any) -> dict[str, Any]:
    item = _normalize_batch_update_item_for_batch(raw_update)
    if item.get("errors"):
        raise UnsafeWriteOperationError("; ".join(str(message) for message in item["errors"].values()))
    return item


def _bind_confirm_tokens(workspace_id: str, item: dict[str, Any]) -> None:
    for operation in item.get("operations") or []:
        token = operation.get("confirm_token")
        if not token:
            continue
        payload = {
            "workspace_id": workspace_id,
            "cue_ref": item["cue_ref"],
            "profile": item["profile"],
            "property": operation["property"],
            "path": operation["path"],
            "mode": operation["mode"],
            "args": operation["args"],
            "base_token": token,
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
        operation["confirm_token"] = f"confirm:{operation['property']}:{digest[:16]}"


def _strip_video_phase2_confirm_tokens(item: dict[str, Any]) -> None:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES:
        return

    def strip(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("confirm_token", None)
            for nested in value.values():
                strip(nested)
        elif isinstance(value, list):
            for nested in value:
                strip(nested)

    strip(item)


def _video_phase2_real_write_errors(item: dict[str, Any]) -> dict[str, str]:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES:
        return {}
    return {
        str(operation["property"]): (
            f"{operation['property']} is gated or dry-run only under the current Video write policy; "
            "no confirm_token can authorize a real write."
        )
        for operation in item.get("operations") or []
        if not operation.get("real_write_enabled")
    }


def _video_phase2_dry_run_blocked_errors(item: dict[str, Any]) -> dict[str, str]:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES:
        return {}
    errors: dict[str, str] = {}
    property_names = set(item.get("requested_property_names") or ())
    operations = {
        str(operation.get("property", "")): operation for operation in item.get("operations") or []
    }
    property_names.update(operations)
    for property_name in property_names:
        operation = operations.get(property_name)
        common_real_write = bool(operation and operation.get("real_write_enabled"))
        video_fx_dry_run = property_name in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES
        if (
            property_name
            and property_name not in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES
            and not video_fx_dry_run
            and not common_real_write
        ):
            errors[property_name] = _video_phase2_blocked_property_message(property_name)
    return errors


def _video_phase2_blocked_property_message(property_name: str) -> str:
    if property_name in {"anchor", "crop", "scale", "translation"}:
        family = "aggregate geometry"
    elif property_name == "fileTarget":
        family = "file target"
    elif property_name == "cameraPatch" or property_name.startswith("videoInputPatch"):
        family = "camera input patch"
    elif property_name.startswith("videoEffect"):
        family = "Video FX mutation"
    elif property_name in {"rotation", "quaternion", "resetRotation"} or property_name.startswith("rotate/"):
        family = "rotation"
    elif property_name.startswith("stage"):
        family = "stage, region, route, or warping"
    elif property_name.startswith("text/format"):
        family = "rich text formatting"
    else:
        family = "property outside the scalar allowlist"
    return (
        f"{property_name} is blocked even for dry-run by Video-family policy ({family}); "
        "no OSC request was sent."
    )


def _video_phase2_dry_run_identity_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES or not before:
        return {}
    returned_id = before.get("uniqueID")
    if returned_id != item.get("cue_ref"):
        return {"cue_ref": "Video-family fresh read uniqueID does not exactly match requested cue UUID."}
    return {}


def _video_phase2_dry_run_health_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES or not item.get("operations") or not before:
        return {}
    errors: dict[str, str] = {}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        errors["health"] = "Video-family dry-runs require a healthy cue without warnings."
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        errors["active"] = "Video-family dry-runs require an inactive cue."
    return errors


def _video_phase2_dry_run_notices(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> list[str]:
    if item.get("profile") in VIDEO_PHASE2_PROFILES and before and before.get("armed") is False:
        return ["cue_disarmed"]
    return []


def _is_exact_cue_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)).casefold() == value.casefold()
    except (ValueError, AttributeError):
        return False


def _video_phase2_dry_run_structure_error(items: list[dict[str, Any]]) -> str | None:
    phase2_items = [
        item
        for item in items
        if item.get("profile") in VIDEO_PHASE2_PROFILES
        and any(
            operation.get("property") in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES
            for operation in item.get("operations") or []
        )
    ]
    if not phase2_items:
        return None
    if len(items) != 1 or len(phase2_items[0].get("operations") or []) != 1:
        return "Video-family dry-runs require exactly one cue and one property."
    item = phase2_items[0]
    operation = item["operations"][0]
    if operation.get("property") not in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES:
        return "Video-family dry-runs allow only one supported scalar property."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Video-family dry-runs require exact cue UUID as cue_ref; cue numbers are rejected."
    if item.get("confirm_gates"):
        return "Video-family dry-runs require empty confirm_gates unless a specialized real-write gate applies."
    if operation.get("mode") != "saved":
        return "Video-family dry-runs require saved mode."
    return None


def _video_fx_dry_run_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("profile") not in VIDEO_PHASE2_PROFILES:
        return None
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES
        ),
        None,
    )


def _video_fx_dry_run_structure_error(items: list[dict[str, Any]]) -> str | None:
    fx_items = [item for item in items if _video_fx_dry_run_operation(item) is not None]
    if not fx_items:
        return None
    if len(items) != 1 or len(fx_items[0].get("operations") or []) != 1:
        return "Video FX dry-runs require exactly one cue and one operation."
    item = fx_items[0]
    operation = item["operations"][0]
    if operation.get("mode") != "saved":
        return "Video FX dry-runs require saved mode; /live remains blocked."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Video FX dry-runs require exact cue UUID as cue_ref; cue numbers are rejected."
    if item.get("confirm_gates"):
        return "Video FX dry-runs do not accept confirm_gates or emit confirm tokens."
    return None


def _video_fx_effect(
    effects: Any,
    operation: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(effects, list):
        return None, "Video FX inventory is unavailable."
    values = operation.get("arg_values") or {}
    if operation["property"].startswith("videoEffectIndex/"):
        index = values.get("index")
        if not isinstance(index, int) or index < 0 or index >= len(effects):
            return None, "Video FX index does not resolve in the fresh effect inventory."
        effect = effects[index]
    else:
        requested_name = values.get("name")
        matches = [
            candidate
            for candidate in effects
            if isinstance(candidate, dict)
            and requested_name
            in {
                candidate.get("name"),
                candidate.get("effectName"),
                candidate.get("displayName"),
                candidate.get("oscName"),
            }
        ]
        if len(matches) > 1:
            return None, "Video FX name is ambiguous; use the zero-based index operation."
        effect = matches[0] if matches else None
    if not isinstance(effect, dict):
        return None, "Video FX effect does not resolve to readable structured data."
    return effect, None


def _video_fx_scalar_kind(value: Any) -> str | None:
    if isinstance(value, bool):
        return "boolean"
    if _is_plain_finite_number(value):
        return "number"
    if isinstance(value, str):
        return "string"
    return None


_VIDEO_FX_NON_PARAMETER_KEYS = frozenset(
    {
        "name",
        "effectName",
        "displayName",
        "oscName",
        "type",
        "effectType",
        "category",
        "enabled",
        "isEnabled",
        "parameters",
    }
)


def _video_fx_parameters(effect: dict[str, Any]) -> tuple[dict[str, Any], str]:
    parameters = effect.get("parameters")
    if isinstance(parameters, dict):
        return parameters, "parameters"
    return {
        str(key): value
        for key, value in effect.items()
        if str(key) not in _VIDEO_FX_NON_PARAMETER_KEYS
    }, "flat_payload"


def _video_fx_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _video_fx_dry_run_operation(item)
    if operation is None or not isinstance(before, dict):
        return {}
    property_name = operation["property"]
    effect, error = _video_fx_effect(before.get("videoEffects"), operation)
    if error or effect is None:
        return {property_name: error or "Video FX effect inventory is unavailable."}
    values = operation.get("arg_values") or {}
    if property_name.endswith("/enabled"):
        current = effect.get("enabled", effect.get("isEnabled"))
        if not isinstance(current, bool):
            return {property_name: "Video FX enabled baseline is not available as a boolean."}
        return {}
    parameter_key = values.get("parameterKey")
    parameters, _ = _video_fx_parameters(effect)
    if not isinstance(parameters, dict) or parameter_key not in parameters:
        return {property_name: "Video FX parameter is absent from the fresh readable parameter inventory."}
    current = parameters[parameter_key]
    requested = values.get("setting")
    current_kind = _video_fx_scalar_kind(current)
    requested_kind = _video_fx_scalar_kind(requested)
    if current_kind is None or requested_kind is None:
        return {
            property_name: (
                "Video FX parameter dry-run supports only existing finite numeric, boolean, or string values."
            )
        }
    if current_kind != requested_kind:
        return {
            property_name: (
                f"Video FX parameter type mismatch: fresh value is {current_kind}, "
                f"requested value is {requested_kind}."
            )
        }
    return {}


def _annotate_video_fx_dry_run_operation(
    item: dict[str, Any],
    workspace_id: str,
    before: dict[str, Any] | None,
) -> None:
    operation = _video_fx_dry_run_operation(item)
    if operation is None or not isinstance(before, dict):
        return
    effect, _ = _video_fx_effect(before.get("videoEffects"), operation)
    if effect is None:
        return
    values = operation.get("arg_values") or {}
    property_name = operation["property"]
    parameter_key = values.get("parameterKey")
    parameters, parameter_source = _video_fx_parameters(effect)
    current = (
        effect.get("enabled", effect.get("isEnabled"))
        if property_name.endswith("/enabled")
        else parameters.get(parameter_key)
    )
    requested = values.get("value") if property_name.endswith("/enabled") else values.get("setting")
    cue_id = _resolved_cue_id(before)
    address = (
        _cue_id_address(workspace_id, cue_id, operation["path"])
        if cue_id
        else operation["path"]
    )
    operation.update(
        {
            "real_write_enabled": False,
            "real_write_possible": False,
            "requires_confirm_token": False,
            "planned_only": True,
            "planned_only_reason": "video_fx_phase4b_dry_run_only",
            "video_fx_plan": {
                "status": "planned",
                "planned_only": True,
                "cue_id": cue_id,
                "cue_type": before.get("type"),
                "effect": {
                    "index": values.get("index"),
                    "name": values.get("name")
                    or effect.get("name")
                    or effect.get("effectName")
                    or effect.get("displayName")
                    or effect.get("oscName"),
                },
                "property": property_name,
                "path": operation.get("path"),
                "expected_setter_address": address,
                "expected_readback_address": address,
                "parameter": parameter_key,
                "parameters_source": parameter_source if parameter_key is not None else None,
                "before": current,
                "requested": requested,
                "inventory_readback_key": "videoEffects",
                "risk_tier": "high",
                "planned_only_reason": "video_fx_phase4b_dry_run_only",
                "will_modify_qlab": False,
            },
        }
    )
    operation.pop("confirm_token", None)


def _phase4c_video_fx_scalar_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    operation = _video_fx_dry_run_operation(item)
    if operation is None:
        return None
    values = operation.get("arg_values") or {}
    if (
        item.get("profile") == "video_basic"
        and operation.get("property") == VIDEO_PHASE4C_FX_SCALAR_PROPERTY
        and operation.get("path") == "videoEffectIndex/0/parameter/inputRadius"
        and operation.get("mode") == "saved"
        and values.get("index") == VIDEO_PHASE4C_FX_ALLOWED_INDEX
        and values.get("parameterKey") == VIDEO_PHASE4C_FX_ALLOWED_PARAMETER
    ):
        return operation
    return None


def _phase4c_video_fx_scalar_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 4C Video FX scalar real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "video_basic":
        return "Phase 4C Video FX scalar real writes require video_basic profile."
    if len(operations) != 1:
        return "Phase 4C Video FX scalar real writes require exactly one property."
    operation = operations[0]
    if operation.get("property") != VIDEO_PHASE4C_FX_SCALAR_PROPERTY:
        return "Phase 4C real writes allow only videoEffectIndex/parameter."
    if operation.get("mode") != "saved":
        return "Phase 4C Video FX scalar real writes require saved mode; /live remains blocked."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 4C Video FX scalar real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    values = operation.get("arg_values") or {}
    if values.get("index") != VIDEO_PHASE4C_FX_ALLOWED_INDEX:
        return "Phase 4C Video FX scalar real writes allow only effect index 0."
    if values.get("parameterKey") != VIDEO_PHASE4C_FX_ALLOWED_PARAMETER:
        return "Phase 4C Video FX scalar real writes allow only inputRadius."
    if not _is_plain_finite_number(values.get("setting")):
        return "Phase 4C Video FX scalar real writes require a finite numeric setting."
    return None


def _video_fx_effect_payload_sha256(effect: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(effect, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    ).hexdigest()


def _phase4c_video_fx_scalar_token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    effect: dict[str, Any],
    baseline: int | float,
    requested: int | float,
) -> dict[str, Any]:
    values = operation.get("arg_values") or {}
    return {
        "version": PHASE4C_VIDEO_FX_SCALAR_TOKEN_VERSION,
        "operation_kind": PHASE4C_VIDEO_FX_SCALAR_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": "Video",
        "profile": item["profile"],
        "property": operation["property"],
        "effect_index": values.get("index"),
        "parameter_key": values.get("parameterKey"),
        "path": operation["path"],
        "osc_setter_path": operation["path"],
        "mode": operation["mode"],
        "baseline": float(baseline),
        "baseline_sha256": _video_opacity_sha256(baseline),
        "requested": float(requested),
        "raw_effect_payload_sha256": _video_fx_effect_payload_sha256(effect),
        "risk_tier": "high",
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase4c_video_fx_scalar_confirm_token(**payload_args: Any) -> str:
    payload = _phase4c_video_fx_scalar_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:videoFxScalar:v{PHASE4C_VIDEO_FX_SCALAR_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase4c_video_fx_scalar_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", "videoFxScalar", f"v{PHASE4C_VIDEO_FX_SCALAR_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 4C Video FX scalar confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 4C Video FX scalar confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 4C Video FX scalar confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 4C Video FX scalar confirm_token payload is invalid."
    return payload, None


def _phase4c_video_fx_scalar_candidate_values(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> tuple[dict[str, Any] | None, int | float | None, int | float | None, str | None]:
    operation = _phase4c_video_fx_scalar_operation(item)
    if operation is None or not isinstance(before, dict):
        return None, None, None, "Phase 4C Video FX scalar preflight is incomplete."
    effect, error = _video_fx_effect(before.get("videoEffects"), operation)
    if error or effect is None:
        return None, None, None, error or "Video FX effect inventory is unavailable."
    parameters, source = _video_fx_parameters(effect)
    if source != "flat_payload":
        return None, None, None, "Phase 4C requires the QLab 5.5.10 flat Video FX payload shape."
    baseline = parameters.get(VIDEO_PHASE4C_FX_ALLOWED_PARAMETER)
    requested = (operation.get("arg_values") or {}).get("setting")
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return None, None, None, "Phase 4C requires finite numeric baseline and requested value."
    if math.isclose(
        float(baseline),
        float(requested),
        rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
        abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
    ):
        return None, None, None, "Phase 4C Video FX scalar no-op writes are blocked; requested value matches baseline."
    return effect, baseline, requested, None


def _annotate_phase4c_video_fx_scalar_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase4c_video_fx_scalar_operation(item)
    if operation is None:
        return []
    cue_id = _resolved_cue_id(before)
    effect, baseline, requested, error = _phase4c_video_fx_scalar_candidate_values(item, before)
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == "Video"
        and cue_id == item.get("cue_ref")
        and effect is not None
        and baseline is not None
        and requested is not None
        and error is None
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return [error or "Phase 4C Video FX scalar is not confirmable outside the ultra-limited gate."]
    _annotate_video_fx_dry_run_operation(item, workspace_id, before)
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase4c_video_fx_scalar_candidate": True,
            "planned_only_reason": "video_fx_scalar_requires_confirm_token",
            "future_gate_requirements": [
                "phase4c_video_fx_scalar_confirm_token",
                "single_video_cue_single_parameter",
                "uuid_cue_ref",
                "effect_index_0",
                "inputRadius_only",
                "saved_mode",
                "fresh_flat_payload_baseline",
                "raw_effect_payload_hash",
                "new_token_for_rollback",
            ],
        }
    )
    operation["video_fx_plan"]["real_write_possible"] = True
    operation["video_fx_plan"]["requires_confirm_token"] = True
    operation["video_fx_plan"]["planned_only_reason"] = "video_fx_scalar_requires_confirm_token"
    operation["confirm_token"] = _phase4c_video_fx_scalar_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        effect=effect,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase4c_video_fx_scalar_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    property_name = VIDEO_PHASE4C_FX_SCALAR_PROPERTY
    operation = _phase4c_video_fx_scalar_operation(item)
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 4C Video FX scalar preflight is incomplete."}
    if before.get("type") != "Video":
        return {property_name: "Phase 4C Video FX scalar real writes require cue type Video."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 4C Video FX scalar real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 4C Video FX scalar real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 4C fresh read uniqueID does not exactly match requested cue UUID."}
    effect, baseline, requested, error = _phase4c_video_fx_scalar_candidate_values(item, before)
    if error or effect is None or baseline is None or requested is None:
        return {property_name: error or "Phase 4C Video FX scalar baseline is unavailable."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase4c_video_fx_scalar_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 4C Video FX scalar confirm_token is invalid."}
    expected = _phase4c_video_fx_scalar_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        effect=effect,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256", "raw_effect_payload_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 4C Video FX scalar confirm_token does not match this workspace, cue, "
                    "effect index, parameter, value, or risk context."
                )
            }
    if (
        payload.get("baseline_sha256") != expected["baseline_sha256"]
        or payload.get("raw_effect_payload_sha256") != expected["raw_effect_payload_sha256"]
        or not math.isclose(
            float(payload.get("baseline", math.nan)),
            float(expected["baseline"]),
            abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
            rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
        )
    ):
        return {
            property_name: (
                "stale_video_fx_scalar_baseline: current Video FX payload no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def _mark_phase4c_video_fx_scalar_real_operation(item: dict[str, Any]) -> None:
    operation = _phase4c_video_fx_scalar_operation(item)
    if operation is None:
        return
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase4c_video_fx_scalar_candidate": True,
        }
    )
    operation.pop("planned_only_reason", None)


def _label_phase4c_video_fx_scalar_rejection(item: dict[str, Any]) -> None:
    operation = _phase4c_video_fx_scalar_operation(item)
    if operation is not None:
        operation["planned_only_reason"] = "video_fx_scalar_requires_confirm_token"


def _refresh_phase4c_video_fx_scalar_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    fx_operation = _phase4c_video_fx_scalar_operation(item)
    if fx_operation is None or not result.get("executed_operations"):
        return
    property_name = fx_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation.update(
                real_write_enabled=True,
                real_write_possible=True,
                requires_confirm_token=True,
            )
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation.update(
                real_write_enabled=True,
                real_write_possible=True,
                requires_confirm_token=True,
            )
            operation.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if not isinstance(plan, dict):
        cue_values = result.get("before") or {}
        plan = {
            "status": result.get("status"),
            "intent": "Executed saved videoEffectIndex/0/parameter/inputRadius change on Video cue.",
            "cue": {
                "uniqueID": result.get("cue_id"),
                "number": cue_values.get("number"),
                "name": cue_values.get("name"),
                "type": cue_values.get("type"),
            },
            "property": property_name,
            "profile": item["profile"],
            "mode": "saved",
            "risk_tier": "high",
        }
        result["updateq_plan"] = plan
    plan.update(
        status=result.get("status"),
        intent="Executed saved videoEffectIndex/0/parameter/inputRadius change on Video cue.",
        real_write_enabled=True,
        real_write_possible=True,
        requires_confirm_token=True,
        planned_only=False,
        after=_phase4c_video_fx_after_value(result.get("after")),
        verification={"readback_matched": result.get("errors") is None},
    )
    plan.pop("why_not_written", None)
    safety = dict(plan.get("safety") or {})
    safety.update({"no_executed_operations": False, "will_modify_qlab": True})
    plan["safety"] = safety


def _phase4c_video_fx_after_value(after: Any) -> Any:
    if not isinstance(after, dict):
        return None
    effects = after.get("videoEffects")
    if not isinstance(effects, list) or len(effects) <= VIDEO_PHASE4C_FX_ALLOWED_INDEX:
        return None
    effect = effects[VIDEO_PHASE4C_FX_ALLOWED_INDEX]
    if not isinstance(effect, dict):
        return None
    parameters, _ = _video_fx_parameters(effect)
    return parameters.get(VIDEO_PHASE4C_FX_ALLOWED_PARAMETER)


def _phase3_video_opacity_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") == VIDEO_PHASE3_OPACITY_PROPERTY
        ),
        None,
    )


def _phase3_video_opacity_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3A opacity real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in VIDEO_PHASE3_OPACITY_TYPES:
        return "Phase 3A opacity real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3A opacity real writes require exactly one property."
    operation = operations[0]
    if operation.get("property") != VIDEO_PHASE3_OPACITY_PROPERTY or operation.get("path") != VIDEO_PHASE3_OPACITY_PROPERTY:
        return "Phase 3A real writes allow only opacity."
    if operation.get("mode") != "saved":
        return "Phase 3A opacity real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3A opacity real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _is_plain_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _video_opacity_sha256(value: int | float) -> str:
    return hashlib.sha256(
        json.dumps(float(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _phase3_video_opacity_token_payload(
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
        "version": PHASE3_VIDEO_OPACITY_TOKEN_VERSION,
        "operation_kind": PHASE3_VIDEO_OPACITY_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": VIDEO_PHASE3_OPACITY_TYPES[item["profile"]],
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": float(baseline),
        "baseline_sha256": _video_opacity_sha256(baseline),
        "requested": float(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3_video_opacity_confirm_token(**payload_args: Any) -> str:
    payload = _phase3_video_opacity_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:videoOpacity:v{PHASE3_VIDEO_OPACITY_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3_video_opacity_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", "videoOpacity", f"v{PHASE3_VIDEO_OPACITY_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3A opacity confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3A opacity confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3A opacity confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 3A opacity confirm_token payload is invalid."
    return payload, None


def _annotate_phase3_video_opacity_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3_video_opacity_operation(item)
    if operation is None:
        return []
    cue_id = _resolved_cue_id(before)
    baseline = before.get(VIDEO_PHASE3_OPACITY_PROPERTY) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == VIDEO_PHASE3_OPACITY_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _is_plain_finite_number(baseline)
        and _is_plain_finite_number(requested)
    )
    operation.update(
        {
            "risk_tier": "high",
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
        operation["confirm_token"] = _phase3_video_opacity_confirm_token(
            workspace_id=workspace_id,
            cue_ref=item["cue_ref"],
            cue_id=cue_id,
            item=item,
            operation=operation,
            baseline=baseline,
            requested=requested,
        )
    else:
        operation.pop("confirm_token", None)
    return [] if candidate else ["Opacity update is not confirmable outside Phase 3A gate."]


def _validate_phase3_video_opacity_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_opacity_operation(item)
    if operation is None or not isinstance(before, dict):
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A opacity preflight is incomplete."}
    if before.get("type") != VIDEO_PHASE3_OPACITY_TYPES.get(item.get("profile")):
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A opacity real writes require matching Video, Camera, or Text cue type."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A opacity real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A opacity real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(VIDEO_PHASE3_OPACITY_PROPERTY)
    requested = operation["args"][0] if operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A fresh read uniqueID does not exactly match requested cue UUID."}
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {VIDEO_PHASE3_OPACITY_PROPERTY: "Phase 3A opacity requires finite numeric baseline and requested value."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase3_video_opacity_confirm_token(token)
    if token_error or payload is None:
        return {VIDEO_PHASE3_OPACITY_PROPERTY: token_error or "Phase 3A opacity confirm_token is invalid."}
    expected = _phase3_video_opacity_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                VIDEO_PHASE3_OPACITY_PROPERTY: (
                    "Phase 3A opacity confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not math.isclose(
        float(payload.get("baseline", math.nan)),
        float(expected["baseline"]),
        abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
        rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
    ):
        return {
            VIDEO_PHASE3_OPACITY_PROPERTY: (
                "stale_video_opacity_baseline: current opacity no longer matches the reviewed dry-run baseline."
            )
        }
    return {}


def _phase3_video_translation_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in VIDEO_PHASE3_TRANSLATION_PROPERTIES
        ),
        None,
    )


def _phase3_video_translation_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3B translation real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in VIDEO_PHASE3_TRANSLATION_TYPES:
        return "Phase 3B translation real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3B translation real writes require exactly one property."
    operation = operations[0]
    if (
        operation.get("property") not in VIDEO_PHASE3_TRANSLATION_PROPERTIES
        or operation.get("path") != operation.get("property")
    ):
        return "Phase 3B real writes allow only translation/x or translation/y."
    if operation.get("mode") != "saved":
        return "Phase 3B translation real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3B translation real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _video_translation_sha256(value: int | float) -> str:
    return hashlib.sha256(
        json.dumps(float(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _phase3_video_translation_token_payload(
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
        "version": PHASE3_VIDEO_TRANSLATION_TOKEN_VERSION,
        "operation_kind": PHASE3_VIDEO_TRANSLATION_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": VIDEO_PHASE3_TRANSLATION_TYPES[item["profile"]],
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": float(baseline),
        "baseline_sha256": _video_translation_sha256(baseline),
        "requested": float(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3_video_translation_confirm_token(**payload_args: Any) -> str:
    payload = _phase3_video_translation_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:videoTranslation:v{PHASE3_VIDEO_TRANSLATION_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3_video_translation_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = [
        "confirm",
        "videoTranslation",
        f"v{PHASE3_VIDEO_TRANSLATION_TOKEN_VERSION}",
    ]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3B translation confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3B translation confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3B translation confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 3B translation confirm_token payload is invalid."
    return payload, None


def _phase3_video_translation_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_translation_operation(item)
    if (
        operation is None
        or item.get("profile") not in VIDEO_PHASE3_TRANSLATION_TYPES
        or not isinstance(before, dict)
        or before.get("type") != VIDEO_PHASE3_TRANSLATION_TYPES.get(item.get("profile"))
    ):
        return {}
    property_name = operation["property"]
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {
            property_name: (
                "Phase 3B translation requires finite numeric baseline and requested value."
            )
        }
    return {}


def _annotate_phase3_video_translation_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3_video_translation_operation(item)
    if operation is None or item.get("profile") not in VIDEO_PHASE3_TRANSLATION_TYPES:
        return []
    property_name = operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == VIDEO_PHASE3_TRANSLATION_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _is_plain_finite_number(baseline)
        and _is_plain_finite_number(requested)
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return []
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3b_video_translation_candidate": True,
            "planned_only_reason": "video_translation_requires_confirm_token",
            "future_gate_requirements": [
                "phase3b_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation["confirm_token"] = _phase3_video_translation_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase3_video_translation_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_translation_operation(item)
    property_name = operation.get("property") if operation else "translation"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3B translation preflight is incomplete."}
    if before.get("type") != VIDEO_PHASE3_TRANSLATION_TYPES.get(item.get("profile")):
        return {
            property_name: (
                "Phase 3B translation real writes require matching Video, Camera, or Text cue type/profile."
            )
        }
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3B translation real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3B translation real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 3B fresh read uniqueID does not exactly match requested cue UUID."}
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {property_name: "Phase 3B translation requires finite numeric baseline and requested value."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase3_video_translation_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 3B translation confirm_token is invalid."}
    expected = _phase3_video_translation_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 3B translation confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not math.isclose(
        float(payload.get("baseline", math.nan)),
        float(expected["baseline"]),
        abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
        rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
    ):
        return {
            property_name: (
                f"stale_video_translation_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def _phase3_video_scalar_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in VIDEO_PHASE3_SCALAR_PROPERTIES
        ),
        None,
    )


def _phase3_video_scalar_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3C scalar real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in VIDEO_PHASE3_SCALAR_TYPES:
        return "Phase 3C scalar real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3C scalar real writes require exactly one property."
    operation = operations[0]
    if (
        operation.get("property") not in VIDEO_PHASE3_SCALAR_PROPERTIES
        or operation.get("path") != operation.get("property")
    ):
        return "Phase 3C real writes allow only scale, anchor, or crop scalar properties."
    if operation.get("mode") != "saved":
        return "Phase 3C scalar real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3C scalar real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _video_scalar_sha256(value: int | float) -> str:
    return hashlib.sha256(
        json.dumps(float(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _phase3_video_scalar_token_payload(
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
        "version": PHASE3_VIDEO_SCALAR_TOKEN_VERSION,
        "operation_kind": PHASE3_VIDEO_SCALAR_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": VIDEO_PHASE3_SCALAR_TYPES[item["profile"]],
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": float(baseline),
        "baseline_sha256": _video_scalar_sha256(baseline),
        "requested": float(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3_video_scalar_confirm_token(**payload_args: Any) -> str:
    payload = _phase3_video_scalar_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:videoScalar:v{PHASE3_VIDEO_SCALAR_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3_video_scalar_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = [
        "confirm",
        "videoScalar",
        f"v{PHASE3_VIDEO_SCALAR_TOKEN_VERSION}",
    ]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3C scalar confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3C scalar confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3C scalar confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 3C scalar confirm_token payload is invalid."
    return payload, None


def _phase3_video_scalar_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_scalar_operation(item)
    if (
        operation is None
        or item.get("profile") not in VIDEO_PHASE3_SCALAR_TYPES
        or not isinstance(before, dict)
        or before.get("type") != VIDEO_PHASE3_SCALAR_TYPES.get(item.get("profile"))
    ):
        return {}
    property_name = operation["property"]
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {
            property_name: "Phase 3C scalar requires finite numeric baseline and requested value."
        }
    return {}


def _annotate_phase3_video_scalar_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3_video_scalar_operation(item)
    if operation is None or item.get("profile") not in VIDEO_PHASE3_SCALAR_TYPES:
        return []
    property_name = operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == VIDEO_PHASE3_SCALAR_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _is_plain_finite_number(baseline)
        and _is_plain_finite_number(requested)
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return []
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3c_video_scalar_candidate": True,
            "planned_only_reason": "video_scalar_requires_confirm_token",
            "future_gate_requirements": [
                "phase3c_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation["confirm_token"] = _phase3_video_scalar_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase3_video_scalar_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_scalar_operation(item)
    property_name = operation.get("property") if operation else "video_scalar"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3C scalar preflight is incomplete."}
    if before.get("type") != VIDEO_PHASE3_SCALAR_TYPES.get(item.get("profile")):
        return {
            property_name: (
                "Phase 3C scalar real writes require matching Video, Camera, or Text cue type/profile."
            )
        }
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3C scalar real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3C scalar real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 3C fresh read uniqueID does not exactly match requested cue UUID."}
    if not _is_plain_finite_number(baseline) or not _is_plain_finite_number(requested):
        return {property_name: "Phase 3C scalar requires finite numeric baseline and requested value."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase3_video_scalar_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 3C scalar confirm_token is invalid."}
    expected = _phase3_video_scalar_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 3C scalar confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not math.isclose(
        float(payload.get("baseline", math.nan)),
        float(expected["baseline"]),
        abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
        rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
    ):
        return {
            property_name: (
                f"stale_video_scalar_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def _phase3_video_appearance_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in VIDEO_PHASE3_APPEARANCE_PROPERTIES
        ),
        None,
    )


def _phase3_video_appearance_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3D appearance real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") not in VIDEO_PHASE3_APPEARANCE_TYPES:
        return "Phase 3D appearance real writes require video_basic, camera_basic, or text_basic profile."
    if len(operations) != 1:
        return "Phase 3D appearance real writes require exactly one property."
    operation = operations[0]
    if (
        operation.get("property") not in VIDEO_PHASE3_APPEARANCE_PROPERTIES
        or operation.get("path") != operation.get("property")
    ):
        return "Phase 3D real writes allow only blendMode or preserveAspectRatio."
    if operation.get("mode") != "saved":
        return "Phase 3D appearance real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3D appearance real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _video_appearance_value_valid(property_name: str, value: Any) -> bool:
    if property_name == "preserveAspectRatio":
        return isinstance(value, bool)
    if property_name == "blendMode":
        return isinstance(value, str) and bool(value)
    return False


def _video_appearance_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _phase3_video_appearance_token_payload(
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
        "version": PHASE3_VIDEO_APPEARANCE_TOKEN_VERSION,
        "operation_kind": PHASE3_VIDEO_APPEARANCE_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": VIDEO_PHASE3_APPEARANCE_TYPES[item["profile"]],
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": baseline,
        "baseline_sha256": _video_appearance_sha256(baseline),
        "requested": requested,
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3_video_appearance_confirm_token(**payload_args: Any) -> str:
    payload = _phase3_video_appearance_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:videoAppearance:v{PHASE3_VIDEO_APPEARANCE_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3_video_appearance_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = [
        "confirm",
        "videoAppearance",
        f"v{PHASE3_VIDEO_APPEARANCE_TOKEN_VERSION}",
    ]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3D appearance confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3D appearance confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3D appearance confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 3D appearance confirm_token payload is invalid."
    return payload, None


def _phase3_video_appearance_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_appearance_operation(item)
    if (
        operation is None
        or item.get("profile") not in VIDEO_PHASE3_APPEARANCE_TYPES
        or not isinstance(before, dict)
        or before.get("type") != VIDEO_PHASE3_APPEARANCE_TYPES.get(item.get("profile"))
    ):
        return {}
    property_name = operation["property"]
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if not _video_appearance_value_valid(property_name, baseline):
        return {property_name: f"Phase 3D appearance requires readable {property_name} baseline."}
    if not _video_appearance_value_valid(property_name, requested):
        return {property_name: f"Phase 3D appearance requested {property_name} value is invalid."}
    return {}


def _annotate_phase3_video_appearance_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3_video_appearance_operation(item)
    if operation is None or item.get("profile") not in VIDEO_PHASE3_APPEARANCE_TYPES:
        return []
    property_name = operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == VIDEO_PHASE3_APPEARANCE_TYPES.get(item.get("profile"))
        and cue_id == item.get("cue_ref")
        and _video_appearance_value_valid(property_name, baseline)
        and _video_appearance_value_valid(property_name, requested)
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return []
    operation.update(
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
    operation["confirm_token"] = _phase3_video_appearance_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase3_video_appearance_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3_video_appearance_operation(item)
    property_name = operation.get("property") if operation else "video_appearance"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3D appearance preflight is incomplete."}
    if before.get("type") != VIDEO_PHASE3_APPEARANCE_TYPES.get(item.get("profile")):
        return {
            property_name: (
                "Phase 3D appearance real writes require matching Video, Camera, or Text cue type/profile."
            )
        }
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3D appearance real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3D appearance real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 3D fresh read uniqueID does not exactly match requested cue UUID."}
    if not _video_appearance_value_valid(property_name, baseline):
        return {property_name: f"Phase 3D appearance requires readable {property_name} baseline."}
    if not _video_appearance_value_valid(property_name, requested):
        return {property_name: f"Phase 3D appearance requested {property_name} value is invalid."}
    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase3_video_appearance_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 3D appearance confirm_token is invalid."}
    expected = _phase3_video_appearance_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
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


def _phase3e_text_basic_operation(item: dict[str, Any]) -> dict[str, Any] | None:
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


def _phase3e_text_basic_call_structure_error(items: list[dict[str, Any]]) -> str | None:
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
        return "Phase 3E real writes allow only text, text/format/fontSize, or text/format/alignment."
    if operation.get("mode") != "saved":
        return "Phase 3E Text Basics real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3E Text Basics real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _text_basic_value_valid(property_name: str, value: Any) -> bool:
    if property_name == "text":
        return isinstance(value, str)
    if property_name == "text/format/alignment":
        return isinstance(value, str) and value.strip().casefold() in {
            "left",
            "center",
            "right",
            "justify",
        }
    if property_name == "text/format/fontSize":
        return _is_plain_finite_number(value) and 0 < float(value) <= 1000
    return False


def _text_basic_canonical_value(property_name: str, value: Any) -> Any:
    if property_name == "text/format/fontSize":
        return float(value)
    if property_name == "text/format/alignment":
        return value.strip().casefold()
    return value


def _text_basic_sha256(property_name: str, value: Any) -> str:
    canonical = _text_basic_canonical_value(property_name, value)
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


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
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:textBasic:v{PHASE3E_TEXT_BASIC_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3e_text_basic_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", "textBasic", f"v{PHASE3E_TEXT_BASIC_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3E Text Basics confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3E Text Basics confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3E Text Basics confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 3E Text Basics confirm_token payload is invalid."
    return payload, None


def _phase3e_text_basic_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3e_text_basic_operation(item)
    if operation is None or not isinstance(before, dict) or before.get("type") != "Text":
        return {}
    property_name = operation["property"]
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if not _text_basic_value_valid(property_name, baseline):
        return {property_name: f"Phase 3E Text Basics requires readable {property_name} baseline."}
    if not _text_basic_value_valid(property_name, requested):
        return {property_name: f"Phase 3E Text Basics requested {property_name} value is invalid."}
    return {}


def _annotate_phase3e_text_basic_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3e_text_basic_operation(item)
    if operation is None:
        return []
    property_name = operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == "Text"
        and cue_id == item.get("cue_ref")
        and _text_basic_value_valid(property_name, baseline)
        and _text_basic_value_valid(property_name, requested)
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return []
    operation.update(
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
    operation["confirm_token"] = _phase3e_text_basic_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase3e_text_basic_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3e_text_basic_operation(item)
    property_name = operation.get("property") if operation else "text_basic"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3E Text Basics preflight is incomplete."}
    if item.get("profile") != "text_basic" or before.get("type") != "Text":
        return {property_name: "Phase 3E Text Basics real writes require a Text cue and text_basic profile."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3E Text Basics real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3E Text Basics real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
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
    expected = _phase3e_text_basic_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
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
        if property_name == "text/format/fontSize"
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


def _phase3f_text_style_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    if item.get("profile") != "text_basic":
        return None
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in TEXT_PHASE3F_PROPERTIES
        ),
        None,
    )


def _phase3f_text_style_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 3F Text Style real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "text_basic":
        return "Phase 3F Text Style real writes require profile='text_basic'."
    if len(operations) != 1:
        return "Phase 3F Text Style real writes require exactly one property."
    operation = operations[0]
    if (
        operation.get("property") not in TEXT_PHASE3F_PROPERTIES
        or operation.get("path") != operation.get("property")
    ):
        return "Phase 3F real writes allow only the approved scalar shadow and decoration properties."
    if operation.get("mode") != "saved":
        return "Phase 3F Text Style real writes require saved mode."
    if not _is_exact_cue_uuid(item.get("cue_ref")):
        return "Phase 3F Text Style real writes require exact cue UUID as cue_ref; cue numbers are rejected."
    return None


def _text_style_value_valid(property_name: str, value: Any) -> bool:
    if property_name == "text/format/shadowBlurRadius":
        return _is_plain_finite_number(value) and float(value) >= 0
    if property_name in {
        "text/format/shadowOffset/width",
        "text/format/shadowOffset/height",
    }:
        return _is_plain_finite_number(value)
    if property_name in {
        "text/format/underlineStyle",
        "text/format/strikethroughStyle",
    }:
        return isinstance(value, str) and value.strip().casefold() in {"none", "single", "double"}
    return False


def _text_style_canonical_value(property_name: str, value: Any) -> Any:
    if property_name in {
        "text/format/shadowBlurRadius",
        "text/format/shadowOffset/width",
        "text/format/shadowOffset/height",
    }:
        return float(value)
    return value.strip().casefold()


def _text_style_sha256(property_name: str, value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            _text_style_canonical_value(property_name, value),
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _phase3f_text_style_token_payload(
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
        "version": PHASE3F_TEXT_STYLE_TOKEN_VERSION,
        "operation_kind": PHASE3F_TEXT_STYLE_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "cue_type": "Text",
        "profile": item["profile"],
        "property": property_name,
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": _text_style_canonical_value(property_name, baseline),
        "baseline_sha256": _text_style_sha256(property_name, baseline),
        "requested": _text_style_canonical_value(property_name, requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "mcp_secret_version": 1,
    }


def _phase3f_text_style_confirm_token(**payload_args: Any) -> str:
    payload = _phase3f_text_style_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:textStyle:v{PHASE3F_TEXT_STYLE_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase3f_text_style_confirm_token(
    token: str,
) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", "textStyle", f"v{PHASE3F_TEXT_STYLE_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 3F Text Style confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 3F Text Style confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 3F Text Style confirm_token payload is invalid."
    return (payload, None) if isinstance(payload, dict) else (
        None,
        "Phase 3F Text Style confirm_token payload is invalid.",
    )


def _phase3f_text_style_dry_run_errors(
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3f_text_style_operation(item)
    if operation is None or not isinstance(before, dict) or before.get("type") != "Text":
        return {}
    property_name = operation["property"]
    requested = operation["args"][0] if operation.get("args") else None
    if not _text_style_value_valid(property_name, requested):
        return {property_name: f"Phase 3F Text Style requested {property_name} value is invalid."}
    return {
        property_name: (
            f"Phase 3F Text Style is blocked: reliable fresh {property_name} "
            "baseline/readback is unavailable in QLab 5.5.10."
        )
    }


def _annotate_phase3f_text_style_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operation = _phase3f_text_style_operation(item)
    if operation is None:
        return []
    property_name = operation["property"]
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name) if isinstance(before, dict) else None
    requested = operation["args"][0] if operation.get("args") else None
    candidate = (
        candidate_shape
        and isinstance(before, dict)
        and before.get("type") == "Text"
        and cue_id == item.get("cue_ref")
        and _text_style_value_valid(property_name, baseline)
        and _text_style_value_valid(property_name, requested)
    )
    if not candidate:
        operation.pop("confirm_token", None)
        return []
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3f_text_style_candidate": True,
            "planned_only_reason": "text_style_requires_confirm_token",
            "future_gate_requirements": [
                "phase3f_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation["confirm_token"] = _phase3f_text_style_confirm_token(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    return []


def _validate_phase3f_text_style_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _phase3f_text_style_operation(item)
    property_name = operation.get("property") if operation else "text_style"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 3F Text Style preflight is incomplete."}
    return {
        property_name: (
            f"Phase 3F Text Style real write is blocked: reliable fresh {property_name} "
            "baseline/readback is unavailable in QLab 5.5.10."
        )
    }
    if item.get("profile") != "text_basic" or before.get("type") != "Text":
        return {property_name: "Phase 3F Text Style real writes require a Text cue and text_basic profile."}
    if before.get("isBroken") is True or before.get("isWarning") is True:
        return {property_name: "Phase 3F Text Style real writes require a healthy cue without warnings."}
    if any(before.get(key) is True for key in ("isRunning", "isPaused", "isAuditioning")):
        return {property_name: "Phase 3F Text Style real writes require an inactive cue."}
    cue_id = _resolved_cue_id(before)
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    if cue_id != item.get("cue_ref"):
        return {property_name: "Phase 3F fresh read uniqueID does not exactly match requested cue UUID."}
    if not _text_style_value_valid(property_name, baseline):
        return {property_name: f"Phase 3F Text Style requires readable {property_name} baseline."}
    if not _text_style_value_valid(property_name, requested):
        return {property_name: f"Phase 3F Text Style requested {property_name} value is invalid."}
    payload, token_error = _decode_phase3f_text_style_confirm_token(item["confirm_gates"][0])
    if token_error or payload is None:
        return {property_name: token_error or "Phase 3F Text Style confirm_token is invalid."}
    expected = _phase3f_text_style_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key in {"baseline", "baseline_sha256"}:
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 3F Text Style confirm_token does not match this workspace, cue, property, "
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
        if _is_plain_finite_number(expected["baseline"])
        else payload.get("baseline") == expected["baseline"]
    )
    if payload.get("baseline_sha256") != expected["baseline_sha256"] or not baseline_matches:
        return {
            property_name: (
                f"stale_text_style_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def _phase4_light_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 4 lightCommandText real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "light_basic":
        return "Phase 4 lightCommandText real writes require profile='light_basic'."
    if len(operations) != 1:
        return "Phase 4 lightCommandText real writes require exactly one property or operation."
    operation = operations[0]
    if operation.get("property") != LIGHT_COMMAND_PROPERTY or operation.get("path") != LIGHT_COMMAND_PROPERTY:
        return "Phase 4 real writes allow only lightCommandText."
    if operation.get("mode") != "saved":
        return "Phase 4 lightCommandText real writes require saved mode."
    return None


def _raw_update_requests_light_command(raw_update: Any) -> bool:
    if hasattr(raw_update, "model_dump"):
        raw_update = raw_update.model_dump()
    if not isinstance(raw_update, dict):
        return False
    properties = raw_update.get("properties")
    if isinstance(properties, dict) and LIGHT_COMMAND_PROPERTY in properties:
        return True
    operations = raw_update.get("operations")
    return isinstance(operations, list) and any(
        isinstance(operation, dict)
        and (
            operation.get("property") == LIGHT_COMMAND_PROPERTY
            or operation.get("path") == LIGHT_COMMAND_PROPERTY
        )
        for operation in operations
    )


def _phase5_light_call_structure_error(items: list[dict[str, Any]]) -> str | None:
    if len(items) != 1:
        return "Phase 5 Light behavior real writes require exactly one cue update."
    item = items[0]
    operations = item.get("operations") or []
    if item.get("profile") != "light_basic":
        return "Phase 5 Light behavior real writes require profile='light_basic'."
    if len(operations) != 1:
        return "Phase 5 Light behavior real writes require exactly one property or operation."
    operation = operations[0]
    property_name = operation.get("property")
    if property_name not in LIGHT_BEHAVIOR_PROPERTIES or operation.get("path") != property_name:
        return "Phase 5 real writes allow only alwaysCollate or subcontroller."
    if operation.get("mode") != "saved":
        return "Phase 5 Light behavior real writes require saved mode."
    return None


def _raw_update_requests_light_behavior(raw_update: Any) -> bool:
    if hasattr(raw_update, "model_dump"):
        raw_update = raw_update.model_dump()
    if not isinstance(raw_update, dict):
        return False
    properties = raw_update.get("properties")
    if isinstance(properties, dict) and LIGHT_BEHAVIOR_PROPERTIES.intersection(properties):
        return True
    operations = raw_update.get("operations")
    return isinstance(operations, list) and any(
        isinstance(operation, dict)
        and (
            operation.get("property") in LIGHT_BEHAVIOR_PROPERTIES
            or operation.get("path") in LIGHT_BEHAVIOR_PROPERTIES
        )
        for operation in operations
    )


def _normalize_batch_update_item_for_batch(raw_update: Any) -> dict[str, Any]:
    if hasattr(raw_update, "model_dump"):
        raw_update = raw_update.model_dump()
    if not isinstance(raw_update, dict):
        return _invalid_batch_update_item("", COMMON_UPDATE_PROFILE, {"update": "each update must be an object"})

    errors: dict[str, str] = {}
    raw_cue_ref = raw_update.get("cue_ref", "")
    try:
        cue = _clean_update_cue_ref(raw_cue_ref)
    except Exception as exc:
        cue = str(raw_cue_ref or "")
        errors["cue_ref"] = str(exc)

    raw_profile = raw_update.get("profile") or COMMON_UPDATE_PROFILE
    try:
        profile = validate_update_profile(raw_profile)
    except Exception as exc:
        profile = str(raw_profile or COMMON_UPDATE_PROFILE)
        errors["profile"] = str(exc)

    properties: dict[str, Any] = {}
    operations: list[dict[str, Any]] = []
    requested_property_names = _raw_update_property_names(raw_update)
    confirm_gates, gate_error = _normalize_confirm_gates(raw_update.get("confirm_gates"))
    if gate_error:
        errors["confirm_gates"] = gate_error
    if "profile" not in errors:
        try:
            properties, operations = normalize_update_request(
                profile,
                raw_update.get("properties"),
                raw_update.get("operations"),
            )
        except Exception as exc:
            errors["validation"] = str(exc)

    return {
        "cue_ref": cue,
        "profile": profile,
        "properties": properties,
        "operations": operations,
        "requested_property_names": requested_property_names,
        "confirm_gates": confirm_gates,
        "read_keys": read_keys_for_operations(operations),
        "errors": errors or None,
    }


def _invalid_batch_update_item(cue_ref: str, profile: str, errors: dict[str, str]) -> dict[str, Any]:
    return {
        "cue_ref": cue_ref,
        "profile": profile,
        "properties": {},
        "operations": [],
        "requested_property_names": [],
        "confirm_gates": [],
        "read_keys": read_keys_for_operations([]),
        "errors": errors,
    }


def _raw_update_property_names(raw_update: dict[str, Any]) -> list[str]:
    names: list[str] = []
    properties = raw_update.get("properties")
    if isinstance(properties, dict):
        names.extend(str(name).strip() for name in properties if isinstance(name, str) and name.strip())
    operations = raw_update.get("operations")
    if isinstance(operations, list):
        names.extend(
            str(operation["property"]).strip()
            for operation in operations
            if isinstance(operation, dict)
            and isinstance(operation.get("property"), str)
            and str(operation["property"]).strip()
        )
    return list(dict.fromkeys(names))


def _normalize_confirm_gates(raw_gates: Any) -> tuple[list[str], str | None]:
    if raw_gates is None:
        return [], None
    if not isinstance(raw_gates, list):
        return [], "confirm_gates must be a list of gate strings"
    gates: list[str] = []
    for raw_gate in raw_gates:
        if not isinstance(raw_gate, str) or not raw_gate.strip():
            return [], "confirm_gates entries must be non-empty strings"
        gates.append(raw_gate.strip())
    return list(dict.fromkeys(gates)), None


def _validate_file_target_roots(reader: Any, items: list[dict[str, Any]]) -> None:
    errors = _file_target_root_errors(reader, items)
    if errors:
        first = next(iter(errors.values()))
        raise UnsafeWriteOperationError(next(iter(first.values())))


def _file_target_root_errors(reader: Any, items: list[dict[str, Any]]) -> dict[int, dict[str, str]]:
    requested_paths: list[str] = []
    requested_items: list[tuple[int, str]] = []
    for index, item in enumerate(items):
        for operation in item["operations"]:
            if operation["property"] == "fileTarget" and operation.get("capability_gate") == "file_target_access":
                if operation["args"]:
                    requested_path = str(operation["args"][0])
                    requested_paths.append(requested_path)
                    requested_items.append((index, requested_path))
    if not requested_paths:
        return {}
    config = getattr(getattr(reader, "client", None), "config", None)
    roots = tuple(getattr(config, "allowed_file_roots", ()) or ())
    if not roots:
        return {
            index: {
                "fileTarget": "fileTarget real writes require QLAB_ALLOWED_FILE_ROOTS to include at least one allowed media root."
            }
            for index, _ in requested_items
        }
    normalized_roots = tuple(os.path.realpath(root) for root in roots)
    errors: dict[int, dict[str, str]] = {}
    for index, requested_path in requested_items:
        absolute_path = os.path.realpath(requested_path)
        if not any(_path_is_under_root(absolute_path, root) for root in normalized_roots):
            errors[index] = {"fileTarget": f"fileTarget path is outside QLAB_ALLOWED_FILE_ROOTS: {requested_path!r}"}
    return errors


def _path_is_under_root(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:
        return False


def _validate_profile_for_before(profile: str, before: dict[str, Any] | None) -> dict[str, str]:
    if before is None:
        return {}
    try:
        validate_update_profile_for_cue(profile, before)
    except Exception as exc:
        return {"profile": str(exc)}
    return {}


def _validate_contextual_real_write(
    reader: Any,
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    if before is None:
        return {}
    errors: dict[str, str] = {}
    for operation in item.get("operations", []):
        prop = str(operation.get("property", ""))
        if prop.startswith("playlist/") and before.get("mode") != 6:
            errors[prop] = "Playlist setters require the Group cue to already be in Playlist mode (mode 6)."
        if prop in {"duration", "tempDuration"} and before.get("allowsEditingDuration") is False:
            errors[prop] = f"{prop} requires a cue with editable duration."
        if prop in {"cueTargetName"}:
            errors[prop] = f"{prop} real writes require cueTargetID or cueTargetNumber; name resolution is not supported."
        if prop in {"cueTargetID", "cueTargetNumber", "tempCueTargetID", "tempCueTargetNumber"}:
            target_ref = operation["args"][0] if operation.get("args") else None
            if _is_empty_target_ref(target_ref):
                continue
            target, target_errors = _try_read_update_values(reader, workspace_id, str(target_ref), ["uniqueID"])
            target_id = _resolved_cue_id(target)
            if target_errors or not target_id:
                errors[prop] = f"{prop} target could not be resolved before update."
            elif target_id == before.get("uniqueID"):
                errors[prop] = f"{prop} target cannot be the cue being updated."
    return errors


def _is_empty_target_ref(value: Any) -> bool:
    return isinstance(value, str) and value.strip().casefold() in {"", "none"}


def _light_command_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") == LIGHT_COMMAND_PROPERTY
        ),
        None,
    )


def _light_behavior_operation(item: dict[str, Any]) -> dict[str, Any] | None:
    return next(
        (
            operation
            for operation in item.get("operations", [])
            if operation.get("property") in LIGHT_BEHAVIOR_PROPERTIES
        ),
        None,
    )


def _annotate_light_behavior_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    candidate_shape: bool,
) -> list[str]:
    operations = [
        operation
        for operation in item.get("operations", [])
        if operation.get("property") in LIGHT_BEHAVIOR_PROPERTIES
    ]
    if not operations:
        return []
    cue_id = _resolved_cue_id(before)
    candidates: list[bool] = []
    for operation in operations:
        property_name = operation["property"]
        baseline = before.get(property_name) if isinstance(before, dict) else None
        requested = operation["args"][0] if operation.get("args") else None
        candidate = (
            candidate_shape
            and before is not None
            and before.get("type") == "Light"
            and isinstance(baseline, bool)
            and isinstance(requested, bool)
            and cue_id is not None
        )
        candidates.append(candidate)
        operation.update(
            {
                "risk_tier": "high",
                "real_write_enabled": False,
                "real_write_possible": candidate,
                "requires_confirm_token": candidate,
                "phase5_light_behavior_candidate": candidate,
                "planned_only_reason": (
                    "light_behavior_requires_confirm_token"
                    if candidate
                    else "light_behavior_requires_single_property"
                ),
            }
        )
        if candidate:
            operation["confirm_token"] = _phase5_light_confirm_token(
                workspace_id=workspace_id,
                cue_ref=item["cue_ref"],
                cue_id=cue_id,
                item=item,
                operation=operation,
                baseline=baseline,
                requested=requested,
            )
        else:
            operation.pop("confirm_token", None)
    return (
        []
        if any(candidates)
        else ["Light behavior update is not confirmable outside a single-cue, single-property dry-run."]
    )


def _try_read_safe_light_patch(
    reader: Any,
    workspace_id: str,
) -> tuple[dict[str, Any] | None, dict[str, str] | None]:
    try:
        result = reader._get_workspace_setting_details_single(
            workspace_id,
            section="light",
            kind="light_patch",
            profile="safe",
        )
    except Exception:
        return None, {
            "code": "light_patch_read_failed",
            "message": "Light Patch safe model could not be read.",
        }
    details = result.get("details") if isinstance(result, dict) else None
    if not isinstance(details, dict) or result.get("errors"):
        return None, {
            "code": "light_patch_read_failed",
            "message": "Light Patch safe model could not be read.",
        }
    return details, None


def _annotate_light_command_operation(
    item: dict[str, Any],
    *,
    workspace_id: str,
    before: dict[str, Any] | None,
    light_patch: dict[str, Any] | None,
    patch_error: dict[str, str] | None,
) -> list[str]:
    operation = _light_command_operation(item)
    if operation is None:
        return []
    if light_patch is None:
        analysis = _unavailable_light_command_analysis(
            patch_error
            or {
                "code": "light_patch_read_failed",
                "message": "Light Patch safe model could not be read.",
            }
        )
    else:
        try:
            helper_result = analyze_light_command_text(str(operation["args"][0]), light_patch)
            analysis = _summarize_light_command_analysis(helper_result)
        except Exception:
            analysis = _unavailable_light_command_analysis(
                {
                    "code": "light_command_analyzer_failed",
                    "message": "Internal LCL analyzer failed.",
                }
            )

    overall_status = analysis["overall_status"]
    requested = str(operation["args"][0])
    baseline = before.get(LIGHT_COMMAND_PROPERTY) if isinstance(before, dict) else None
    cue_id = _resolved_cue_id(before)
    empty_command = not requested.strip()
    candidate = (
        overall_status == "valid"
        and not empty_command
        and isinstance(baseline, str)
        and cue_id is not None
    )
    planned_only_reason = {
        "warning": "light_command_analysis_warning",
        "invalid": "light_command_analysis_failed",
        "unsupported": "unsupported_light_command_syntax",
        "unavailable": "light_command_analysis_unavailable",
    }.get(overall_status, "light_command_requires_valid_analysis_and_confirm_token")
    if overall_status == "valid" and empty_command:
        planned_only_reason = "empty_light_command_text_not_writeable"
    elif overall_status == "valid" and (not isinstance(baseline, str) or cue_id is None):
        planned_only_reason = "light_command_baseline_unavailable"
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": False,
            "real_write_possible": candidate,
            "requires_confirm_token": candidate,
            "phase4_real_write_candidate": candidate,
            "planned_only_reason": planned_only_reason,
            "light_command_analysis": analysis,
        }
    )
    if candidate:
        operation["confirm_token"] = _phase4_light_confirm_token(
            workspace_id=workspace_id,
            cue_ref=item["cue_ref"],
            cue_id=cue_id,
            item=item,
            operation=operation,
            baseline=baseline,
            requested=requested,
        )
    else:
        operation.pop("confirm_token", None)
    if candidate:
        return []
    if overall_status == "valid" and empty_command:
        return ["Empty lightCommandText is valid to analyze but is not confirmable for Phase 4 real write."]
    if overall_status == "valid":
        return ["Light cue baseline is unavailable; Phase 4 real write is not possible."]
    return [
        {
            "warning": "LCL analysis returned warnings; inspect results before future confirmation.",
            "invalid": "LCL analysis found invalid commands; real write is not possible.",
            "unsupported": "LCL analysis found unsupported syntax; real write is not possible.",
            "unavailable": "LCL analysis is unavailable; real write is not possible.",
        }[overall_status]
    ]


def _phase4_light_token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    baseline: str,
    requested: str,
) -> dict[str, Any]:
    return {
        "version": PHASE4_LIGHT_TOKEN_VERSION,
        "operation_kind": PHASE4_LIGHT_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline_sha256": _text_sha256(baseline),
        "requested_sha256": _text_sha256(requested),
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
        "analysis_status": "valid",
    }


def _phase4_light_confirm_token(**payload_args: Any) -> str:
    payload = _phase4_light_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:{LIGHT_COMMAND_PROPERTY}:v{PHASE4_LIGHT_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase4_light_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", LIGHT_COMMAND_PROPERTY, f"v{PHASE4_LIGHT_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 4 lightCommandText confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 4 lightCommandText confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 4 lightCommandText confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 4 lightCommandText confirm_token payload is invalid."
    return payload, None


def _text_sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_phase4_light_real_write(
    reader: Any,
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _light_command_operation(item)
    if operation is None or not isinstance(before, dict):
        return {LIGHT_COMMAND_PROPERTY: "Phase 4 lightCommandText preflight is incomplete."}
    if before.get("type") != "Light":
        return {LIGHT_COMMAND_PROPERTY: "Phase 4 lightCommandText real writes require cue type exactly Light."}
    baseline = before.get(LIGHT_COMMAND_PROPERTY)
    requested = operation["args"][0] if operation.get("args") else None
    cue_id = _resolved_cue_id(before)
    if not isinstance(baseline, str) or not isinstance(requested, str) or cue_id is None:
        return {LIGHT_COMMAND_PROPERTY: "Fresh Light cue baseline or requested command text is unavailable."}
    if not requested.strip():
        return {LIGHT_COMMAND_PROPERTY: "Empty lightCommandText is not writeable in Phase 4."}

    light_patch, patch_error = _try_read_safe_light_patch(reader, workspace_id)
    if light_patch is None:
        return {
            LIGHT_COMMAND_PROPERTY: (patch_error or {}).get(
                "message", "Light Patch safe model could not be read."
            )
        }
    try:
        analysis = _summarize_light_command_analysis(analyze_light_command_text(requested, light_patch))
    except Exception:
        return {LIGHT_COMMAND_PROPERTY: "Internal LCL analyzer failed during Phase 4 preflight."}
    if analysis["overall_status"] != "valid":
        return {
            LIGHT_COMMAND_PROPERTY: (
                "Phase 4 lightCommandText real write requires fresh analysis status valid; "
                f"received {analysis['overall_status']}."
            )
        }

    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase4_light_confirm_token(token)
    if token_error or payload is None:
        return {LIGHT_COMMAND_PROPERTY: token_error or "Phase 4 lightCommandText confirm_token is invalid."}
    expected = _phase4_light_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key == "baseline_sha256":
            continue
        if payload.get(key) != value:
            return {
                LIGHT_COMMAND_PROPERTY: (
                    "Phase 4 lightCommandText confirm_token does not match this workspace, cue, value, or risk context."
                )
            }
    if payload.get("baseline_sha256") != expected["baseline_sha256"]:
        return {
            LIGHT_COMMAND_PROPERTY: (
                "stale_light_command_baseline: current lightCommandText no longer matches the reviewed dry-run baseline."
            )
        }
    return {}


def _phase5_light_token_payload(
    *,
    workspace_id: str,
    cue_ref: str,
    cue_id: str,
    item: dict[str, Any],
    operation: dict[str, Any],
    baseline: bool,
    requested: bool,
) -> dict[str, Any]:
    return {
        "version": PHASE5_LIGHT_TOKEN_VERSION,
        "operation_kind": PHASE5_LIGHT_OPERATION_KIND,
        "workspace_id": workspace_id,
        "cue_ref": cue_ref,
        "cue_id": cue_id,
        "profile": item["profile"],
        "property": operation["property"],
        "path": operation["path"],
        "mode": operation["mode"],
        "baseline": baseline,
        "requested": requested,
        "risk_tier": operation["risk_tier"],
        "capability_gate": operation.get("capability_gate"),
    }


def _phase5_light_confirm_token(**payload_args: Any) -> str:
    payload = _phase5_light_token_payload(**payload_args)
    encoded = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(_LIGHT_WRITE_TOKEN_SECRET, encoded.encode("ascii"), hashlib.sha256).hexdigest()
    return f"confirm:lightBehavior:v{PHASE5_LIGHT_TOKEN_VERSION}:{encoded}:{signature}"


def _decode_phase5_light_confirm_token(token: str) -> tuple[dict[str, Any] | None, str | None]:
    parts = token.split(":", 4)
    expected_prefix = ["confirm", "lightBehavior", f"v{PHASE5_LIGHT_TOKEN_VERSION}"]
    if len(parts) != 5 or parts[:3] != expected_prefix:
        return None, "Phase 5 Light behavior confirm_token is malformed or has an unsupported version."
    encoded, signature = parts[3], parts[4]
    expected_signature = hmac.new(
        _LIGHT_WRITE_TOKEN_SECRET,
        encoded.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        return None, "Phase 5 Light behavior confirm_token signature is invalid."
    try:
        padding = "=" * (-len(encoded) % 4)
        payload = json.loads(base64.urlsafe_b64decode(encoded + padding).decode("utf-8"))
    except Exception:
        return None, "Phase 5 Light behavior confirm_token payload is invalid."
    if not isinstance(payload, dict):
        return None, "Phase 5 Light behavior confirm_token payload is invalid."
    return payload, None


def _validate_phase5_light_real_write(
    workspace_id: str,
    item: dict[str, Any],
    before: dict[str, Any] | None,
) -> dict[str, str]:
    operation = _light_behavior_operation(item)
    property_name = operation.get("property") if operation else "light_behavior"
    if operation is None or not isinstance(before, dict):
        return {property_name: "Phase 5 Light behavior preflight is incomplete."}
    if before.get("type") != "Light":
        return {property_name: "Phase 5 Light behavior real writes require cue type exactly Light."}
    baseline = before.get(property_name)
    requested = operation["args"][0] if operation.get("args") else None
    cue_id = _resolved_cue_id(before)
    if not isinstance(baseline, bool) or not isinstance(requested, bool) or cue_id is None:
        return {property_name: "Fresh Light cue baseline or requested boolean is unavailable."}

    token = item["confirm_gates"][0]
    payload, token_error = _decode_phase5_light_confirm_token(token)
    if token_error or payload is None:
        return {property_name: token_error or "Phase 5 Light behavior confirm_token is invalid."}
    expected = _phase5_light_token_payload(
        workspace_id=workspace_id,
        cue_ref=item["cue_ref"],
        cue_id=cue_id,
        item=item,
        operation=operation,
        baseline=baseline,
        requested=requested,
    )
    for key, value in expected.items():
        if key == "baseline":
            continue
        if payload.get(key) != value:
            return {
                property_name: (
                    "Phase 5 Light behavior confirm_token does not match this workspace, cue, property, "
                    "value, or risk context."
                )
            }
    if payload.get("baseline") is not expected["baseline"]:
        return {
            property_name: (
                f"stale_light_behavior_baseline: current {property_name} no longer matches "
                "the reviewed dry-run baseline."
            )
        }
    return {}


def _mark_phase3_video_opacity_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3_video_opacity_operation(item)
    if operation is None:
        return
    operation.update(
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
    operation.pop("planned_only_reason", None)


def _refresh_phase3_video_opacity_real_result(result: dict[str, Any], item: dict[str, Any]) -> None:
    if _phase3_video_opacity_operation(item) is None or not result.get("executed_operations"):
        return
    for operation in result.get("operations") or []:
        if operation.get("property") == VIDEO_PHASE3_OPACITY_PROPERTY:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == VIDEO_PHASE3_OPACITY_PROPERTY:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        cue_type = (result.get("before") or {}).get("type") or "visual"
        plan["status"] = result.get("status")
        plan["intent"] = f"Executed saved opacity change on {cue_type} cue."
        plan["real_write_enabled"] = True
        plan["real_write_possible"] = True
        plan["requires_confirm_token"] = True
        plan.pop("why_not_written", None)
        plan["after"] = (result.get("after") or {}).get(VIDEO_PHASE3_OPACITY_PROPERTY)
        plan["verification"] = {"readback_matched": result.get("errors") is None}
        safety = dict(plan.get("safety") or {})
        safety.update({"no_executed_operations": False, "will_modify_qlab": True})
        plan["safety"] = safety


def _mark_phase3_video_translation_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3_video_translation_operation(item)
    if operation is None:
        return
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3b_video_translation_candidate": True,
            "future_gate_requirements": [
                "phase3b_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation.pop("planned_only_reason", None)


def _refresh_phase3_video_translation_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    translation_operation = _phase3_video_translation_operation(item)
    if translation_operation is None or not result.get("executed_operations"):
        return
    property_name = translation_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
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


def _mark_phase3_video_scalar_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3_video_scalar_operation(item)
    if operation is None:
        return
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3c_video_scalar_candidate": True,
            "future_gate_requirements": [
                "phase3c_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation.pop("planned_only_reason", None)


def _label_phase3_video_scalar_rejection(item: dict[str, Any]) -> None:
    operation = _phase3_video_scalar_operation(item)
    if operation is not None:
        operation["planned_only_reason"] = "video_scalar_requires_confirm_token"


def _refresh_phase3_video_scalar_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    scalar_operation = _phase3_video_scalar_operation(item)
    if scalar_operation is None or not result.get("executed_operations"):
        return
    property_name = scalar_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
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


def _mark_phase3_video_appearance_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3_video_appearance_operation(item)
    if operation is None:
        return
    operation.update(
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
    operation.pop("planned_only_reason", None)


def _label_phase3_video_appearance_rejection(item: dict[str, Any]) -> None:
    operation = _phase3_video_appearance_operation(item)
    if operation is not None:
        operation["planned_only_reason"] = "video_appearance_requires_confirm_token"


def _refresh_phase3_video_appearance_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    appearance_operation = _phase3_video_appearance_operation(item)
    if appearance_operation is None or not result.get("executed_operations"):
        return
    property_name = appearance_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
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


def _mark_phase3e_text_basic_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3e_text_basic_operation(item)
    if operation is None:
        return
    operation.update(
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
    operation.pop("planned_only_reason", None)


def _label_phase3e_text_basic_rejection(item: dict[str, Any]) -> None:
    operation = _phase3e_text_basic_operation(item)
    if operation is not None:
        operation["planned_only_reason"] = "text_basic_requires_confirm_token"


def _refresh_phase3e_text_basic_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    text_operation = _phase3e_text_basic_operation(item)
    if text_operation is None or not result.get("executed_operations"):
        return
    property_name = text_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation["real_write_enabled"] = True
            operation["real_write_possible"] = True
            operation["requires_confirm_token"] = True
            operation.pop("planned_only_reason", None)
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


def _mark_phase3f_text_style_real_operation(item: dict[str, Any]) -> None:
    operation = _phase3f_text_style_operation(item)
    if operation is None:
        return
    operation.update(
        {
            "risk_tier": "high",
            "real_write_enabled": True,
            "real_write_possible": True,
            "requires_confirm_token": True,
            "phase3f_text_style_candidate": True,
            "future_gate_requirements": [
                "phase3f_confirm_token",
                "single_cue_single_property",
                "uuid_cue_ref",
                "saved_mode",
                "fresh_baseline",
                "exact_readback",
                "manual_rollback_plan",
            ],
        }
    )
    operation.pop("planned_only_reason", None)


def _label_phase3f_text_style_rejection(item: dict[str, Any]) -> None:
    operation = _phase3f_text_style_operation(item)
    if operation is not None:
        operation["planned_only_reason"] = "text_style_requires_confirm_token"


def _refresh_phase3f_text_style_real_result(
    result: dict[str, Any],
    item: dict[str, Any],
) -> None:
    style_operation = _phase3f_text_style_operation(item)
    if style_operation is None or not result.get("executed_operations"):
        return
    property_name = style_operation["property"]
    for operation in result.get("operations") or []:
        if operation.get("property") == property_name:
            operation.update(
                real_write_enabled=True,
                real_write_possible=True,
                requires_confirm_token=True,
            )
            operation.pop("planned_only_reason", None)
    for operation in result.get("planned_operations") or []:
        if operation.get("operation") == "set_property" and operation.get("property") == property_name:
            operation.update(
                real_write_enabled=True,
                real_write_possible=True,
                requires_confirm_token=True,
            )
            operation.pop("planned_only_reason", None)
    plan = result.get("updateq_plan")
    if isinstance(plan, dict):
        plan.update(
            status=result.get("status"),
            intent=f"Executed saved {property_name} change on Text cue.",
            real_write_enabled=True,
            real_write_possible=True,
            requires_confirm_token=True,
            after=(result.get("after") or {}).get(property_name),
            verification={"readback_matched": result.get("errors") is None},
        )
        plan.pop("why_not_written", None)
        safety = dict(plan.get("safety") or {})
        safety.update({"no_executed_operations": False, "will_modify_qlab": True})
        plan["safety"] = safety


def _summarize_light_command_analysis(helper_result: dict[str, Any]) -> dict[str, Any]:
    results = helper_result.get("results") if isinstance(helper_result.get("results"), list) else []
    status_counts = {status: 0 for status in ("valid", "warning", "invalid", "unsupported")}
    affected_pairs: set[tuple[str, str]] = set()
    skipped_member_count = 0
    for result in results:
        status = result.get("status")
        if status in status_counts:
            status_counts[status] += 1
        for affected in result.get("affected", []):
            instrument = affected.get("instrument") if isinstance(affected, dict) else None
            parameter = affected.get("parameter") if isinstance(affected, dict) else None
            if isinstance(instrument, str) and isinstance(parameter, str):
                affected_pairs.add((instrument, parameter))
        skipped = result.get("skipped_members")
        if isinstance(skipped, list):
            skipped_member_count += len(skipped)

    if status_counts["invalid"]:
        overall_status = "invalid"
    elif status_counts["unsupported"]:
        overall_status = "unsupported"
    elif status_counts["warning"]:
        overall_status = "warning"
    else:
        overall_status = "valid"
    return {
        "availability": "available",
        "overall_status": overall_status,
        "line_count": helper_result.get("line_count", 0),
        "analyzed_count": helper_result.get("analyzed_count", len(results)),
        "status_counts": status_counts,
        "affected_instruments": sorted({instrument for instrument, _ in affected_pairs}),
        "affected_parameters": sorted({parameter for _, parameter in affected_pairs}),
        "affected_pair_count": len(affected_pairs),
        "skipped_member_count": skipped_member_count,
        "results": results,
    }


def _unavailable_light_command_analysis(error: dict[str, str]) -> dict[str, Any]:
    return {
        "availability": "unavailable",
        "overall_status": "unavailable",
        "line_count": None,
        "analyzed_count": None,
        "status_counts": {status: 0 for status in ("valid", "warning", "invalid", "unsupported")},
        "affected_instruments": [],
        "affected_parameters": [],
        "affected_pair_count": 0,
        "skipped_member_count": 0,
        "results": [],
        "error": error,
    }


def _batch_item_result(
    workspace_id: str,
    item: dict[str, Any],
    *,
    cue_id: str | None,
    status: str,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
    errors: dict[str, str] | None,
    warnings: list[str],
    notices: list[str] | None = None,
) -> dict[str, Any]:
    item_notices = list(notices or [])
    diff = _diff_properties(before, item["properties"], after)
    planned_operations = []
    if not errors:
        planned_operations = _planned_update_operations(
            workspace_id,
            item["cue_ref"],
            item["operations"],
            resolved_cue_id=cue_id,
        )
    result = {
        "cue_ref": item["cue_ref"],
        "cue_id": cue_id,
        "profile": item["profile"],
        "status": status,
        "properties": item["properties"],
        "operations": item["operations"],
        "confirm_gates": item["confirm_gates"],
        "before": before,
        "after": after,
        "diff": diff,
        "planned_operations": planned_operations,
        "executed_operations": [],
        "errors": errors,
        "warnings": warnings,
        "notices": item_notices,
    }
    updateq_plan = _video_phase2_updateq_plan(item, before, diff, errors, item_notices)
    if updateq_plan is not None:
        result["updateq_plan"] = updateq_plan
    return result


def _video_phase2_updateq_plan(
    item: dict[str, Any],
    before: dict[str, Any] | None,
    diff: dict[str, dict[str, Any]],
    errors: dict[str, str] | None,
    notices: list[str],
) -> dict[str, Any] | None:
    property_names = list(dict.fromkeys(item.get("requested_property_names") or ()))
    operations = {str(operation.get("property", "")): operation for operation in item.get("operations") or []}
    if item.get("profile") not in VIDEO_PHASE2_PROFILES or not any(
        _is_video_phase2_property(name, operations.get(name)) for name in property_names
    ):
        return None

    property_name = property_names[0] if len(property_names) == 1 else None
    cue_values = before or {}
    cue = {
        "uniqueID": cue_values.get("uniqueID")
        or (item.get("cue_ref") if _is_exact_cue_uuid(item.get("cue_ref")) else None),
        "number": cue_values.get("number"),
        "name": cue_values.get("name"),
        "type": cue_values.get("type"),
    }
    safety = {
        "no_live": True,
        "no_playback": True,
        "no_workspace_video_write": True,
        "no_executed_operations": True,
        "will_modify_qlab": False,
    }
    notice_explanations = {}
    if "cue_disarmed" in notices:
        notice_explanations["cue_disarmed"] = (
            "Cue is disarmed; this affects playback readiness, not saved-property planning."
        )

    if errors:
        reason = errors.get(property_name) if property_name else None
        reason = reason or next(iter(errors.values()))
        return {
            "status": "rejected",
            "intent": f"Reject {property_name or 'requested'} Video-family change.",
            "cue": cue,
            "property": property_name,
            "profile": item["profile"],
            "reason": reason,
            "planned_mutation": False,
            "real_write_enabled": False,
            "real_write_possible": False,
            "requires_confirm_token": False,
            "notices": notices,
            "notice_explanations": notice_explanations,
            "suggestion": _video_phase2_updateq_suggestion(property_name, reason),
            "safety": safety,
        }

    fx_operation = _video_fx_dry_run_operation(item)
    if fx_operation is not None:
        fx_plan = fx_operation.get("video_fx_plan")
        if not isinstance(fx_plan, dict):
            return None
        return {
            "status": "planned",
            "intent": "Preview one saved Video FX change without executing it.",
            "cue": cue,
            "property": fx_operation["property"],
            "profile": item["profile"],
            "mode": "saved",
            "before": fx_plan.get("before"),
            "requested": fx_plan.get("requested"),
            "diff": {
                "before": fx_plan.get("before"),
                "requested": fx_plan.get("requested"),
            },
            "risk_tier": "high",
            "real_write_enabled": bool(fx_operation.get("real_write_enabled")),
            "real_write_possible": bool(fx_operation.get("real_write_possible")),
            "requires_confirm_token": bool(fx_operation.get("requires_confirm_token")),
            "planned_only": not bool(fx_operation.get("real_write_possible")),
            "why_not_written": fx_operation.get("planned_only_reason"),
            "video_fx": fx_plan,
            "notices": notices,
            "notice_explanations": notice_explanations,
            "safety": safety,
        }

    if property_name not in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES:
        return None
    operation = operations[property_name]
    property_diff = diff.get(property_name, {})
    plan = {
        "status": "planned",
        "intent": f"Preview saved {property_name} change on {cue.get('type') or 'visual'} cue.",
        "cue": cue,
        "property": property_name,
        "profile": item["profile"],
        "mode": "saved",
        "before": property_diff.get("before"),
        "requested": property_diff.get("requested"),
        "diff": property_diff,
        "risk_tier": operation["risk_tier"],
        "real_write_enabled": bool(operation.get("real_write_enabled")),
        "real_write_possible": bool(operation.get("real_write_possible")),
        "requires_confirm_token": bool(operation.get("requires_confirm_token")),
        "why_not_written": operation.get("planned_only_reason"),
        "future_gate_requirements": list(operation.get("future_gate_requirements") or []),
        "notices": notices,
        "notice_explanations": notice_explanations,
        "safety": safety,
    }
    if property_name == "text":
        plan.update(
            {
                "format_inheritance_warning": True,
                "warning": "Changing text inherits formatting from the first existing character.",
            }
        )
    return plan


def _is_video_phase2_property(property_name: str, operation: dict[str, Any] | None) -> bool:
    if property_name in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES:
        return True
    if operation and not operation.get("real_write_enabled"):
        return True
    return (
        property_name in {"anchor", "crop", "fileTarget", "quaternion", "resetRotation", "rotation", "scale", "translation"}
        or property_name == "cameraPatch"
        or property_name.startswith(("rotate/", "stage", "text/format", "videoEffect", "videoInputPatch"))
    )


def _video_phase2_updateq_suggestion(property_name: str | None, reason: str) -> str | None:
    name = property_name or ""
    if "live" in reason.casefold():
        return "Retry the same scalar property as a saved-mode dry-run."
    scalar_geometry = {
        "anchor": "anchor/x and anchor/y",
        "translation": "translation/x and translation/y",
        "scale": "scale/x and scale/y",
        "crop": "cropTop, cropBottom, cropLeft, and cropRight",
    }
    if name in scalar_geometry:
        return f"Plan {scalar_geometry[name]} separately as saved-mode dry-runs."
    if name in {"quaternion", "resetRotation", "rotation"} or name.startswith("rotate/"):
        return "Rotation editing is deferred to a dedicated rotation phase."
    if name == "fileTarget":
        return "Media target editing is outside current Video write scope."
    if name.startswith("videoEffect"):
        return "Video FX mutations are deferred to a later Video FX phase."
    if name == "cameraPatch" or name.startswith("videoInputPatch"):
        return "Camera patch editing is blocked; inspect the input patch read-only instead."
    if name.startswith("stage"):
        return "Stage editing is blocked; inspect stage topology read-only instead."
    if name.startswith("text/format"):
        return "Rich text editing is blocked; use one allowed scalar text property when applicable."
    return None


def _batch_update_result(
    workspace_id: str,
    *,
    dry_run: bool,
    results: list[dict[str, Any]],
    status: str,
    requested_count: int,
    timeout_confirmed_count: int = 0,
    errors: dict[str, str] | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    fixed_results = results
    failed_count = sum(1 for result in fixed_results if result.get("errors"))
    updated_count = sum(
        1
        for result in fixed_results
        if result.get("status") in {"updated", "updated_with_confirmed_timeouts"}
    )
    planned_count = sum(1 for result in fixed_results if result.get("planned_operations"))
    ok = failed_count == 0 and status not in {
        "preflight_failed",
        "partial_failed",
        "verification_failed",
        "verification_inconclusive",
    }
    if status == "dry_run":
        message = "Dry run succeeded; review planned_operations before disabling dry_run."
    elif status == "preflight_failed":
        message = "Batch cue update was blocked during preflight; no mutating OSC commands were sent."
    elif status == "partial_failed":
        message = "Batch cue update partially failed; inspect per-cue results and errors."
    elif status == "verification_failed":
        message = "Batch cue update commands completed, but fresh verification failed."
    elif status == "verification_inconclusive":
        message = "Batch cue update commands completed, but deterministic verification was not available."
    elif status == "updated_with_confirmed_timeouts":
        message = "Batch cue update completed; some setters timed out but fresh after-reads confirmed requested values."
    else:
        message = "Batch cue update completed and fresh after-reads confirmed requested values."
    global_warnings = list(warnings or [])
    if status == "updated_with_confirmed_timeouts":
        global_warnings.append("One or more setters did not reply before timeout, but fresh after-reads confirmed the changes.")
    return {
        "ok": ok,
        "status": status,
        "workspace_id": workspace_id,
        "dry_run": dry_run,
        "requested_count": requested_count,
        "planned_count": planned_count,
        "updated_count": updated_count,
        "failed_count": failed_count,
        "timeout_confirmed_count": timeout_confirmed_count,
        "results": fixed_results,
        "errors": errors,
        "warnings": global_warnings,
        "error_code": None if ok else UPDATE_STATUS_CODES.get(status, f"QLAB_UPDATE_{status.upper()}"),
        "suggested_action": None if ok else UPDATE_STATUS_ACTIONS.get(status, "Inspect per-cue results before retrying."),
        "message": message,
    }


def _planned_create_operations(
    workspace_id: str,
    cue_type: str,
    properties: dict[str, Any],
    placement: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    operations: list[dict[str, Any]] = [
        {
            "operation": "new",
            "address": _workspace_address(workspace_id, "new"),
            "args": [cue_type],
        }
    ]
    if placement is not None:
        operations.append(
            {
                "operation": "move_after",
                "after_cue_id": placement["after_cue_id"],
                "status": "planned_only",
            }
        )
    for key, value in properties.items():
        operations.append(
            {
                "operation": "set_property",
                "property": key,
                "address": f"/workspace/{workspace_id}/cue_id/{{created_cue_id}}/{key}",
                "args": [value],
            }
        )
    operations.append(
        {
            "operation": "verify",
            "profile": "auto",
            "cacheable": False,
        }
    )
    return operations


def _planned_update_operations(
    workspace_id: str,
    cue_ref: str,
    update_operations: list[dict[str, Any]],
    resolved_cue_id: str | None = None,
) -> list[dict[str, Any]]:
    operations = [
        {
            "operation": "read_before",
            "profile": "update_safe",
            "cacheable": False,
        }
    ]
    for update_operation in update_operations:
        address = (
            _cue_id_address(workspace_id, resolved_cue_id, update_operation["path"])
            if resolved_cue_id
            else _cue_address(workspace_id, cue_ref, update_operation["path"])
        )
        planned = {
            "operation": "set_property",
            "property": update_operation["property"],
            "address": address,
            "args": update_operation["args"],
            "mode": update_operation["mode"],
            "risk_tier": update_operation["risk_tier"],
            "real_write_enabled": update_operation["real_write_enabled"],
            "capability_gate": update_operation.get("capability_gate"),
        }
        if update_operation.get("confirm_token"):
            planned["confirm_token"] = update_operation["confirm_token"]
        for key in (
            "real_write_possible",
            "requires_confirm_token",
            "future_gate_requirements",
            "phase3_video_opacity_candidate",
            "phase3b_video_translation_candidate",
            "phase3c_video_scalar_candidate",
            "phase3d_video_appearance_candidate",
            "phase3e_text_basic_candidate",
            "phase3f_text_style_candidate",
            "phase4c_video_fx_scalar_candidate",
            "video_fx_plan",
            "planned_only",
            "phase4_real_write_candidate",
            "phase5_light_behavior_candidate",
            "light_command_analysis",
        ):
            if key in update_operation:
                planned[key] = update_operation[key]
        if update_operation.get("contextual_requirements"):
            planned["contextual_requirements"] = update_operation["contextual_requirements"]
        if update_operation.get("planned_only_reason"):
            planned["planned_only_reason"] = update_operation["planned_only_reason"]
        operations.append(planned)
    operations.append(
        {
            "operation": "verify",
            "profile": "auto",
            "cacheable": False,
        }
    )
    return operations


def _resolved_cue_id(values: dict[str, Any] | None) -> str | None:
    if not isinstance(values, dict):
        return None
    value = values.get("uniqueID")
    if isinstance(value, str) and value.strip():
        return _clean_cue_ref(value)
    return None


def _client_config_timeout(reader: Any, fallback: float) -> float:
    value = getattr(getattr(getattr(reader, "client", None), "config", None), "timeout", fallback)
    try:
        return max(UPDATE_MIN_REPLY_TIMEOUT_SECONDS, float(value))
    except (TypeError, ValueError):
        return fallback


def _budget_remaining(deadline: float | None) -> float:
    if deadline is None:
        return UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS
    return deadline - time.monotonic()


def _bounded_reply_timeout(reader: Any, cap: float, deadline: float | None = None) -> float:
    timeout = min(_client_config_timeout(reader, cap), cap)
    if deadline is not None:
        remaining = _budget_remaining(deadline)
        if remaining <= 0:
            return UPDATE_MIN_REPLY_TIMEOUT_SECONDS
        timeout = min(timeout, remaining)
    return max(UPDATE_MIN_REPLY_TIMEOUT_SECONDS, timeout)


def _setter_reply_timeout(reader: Any, setter_count: int, deadline: float | None = None) -> float:
    if setter_count <= 0:
        return UPDATE_MIN_REPLY_TIMEOUT_SECONDS
    per_setter_budget = UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS / setter_count
    cap = min(UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS, per_setter_budget)
    return _bounded_reply_timeout(reader, cap, deadline)


def _try_read_update_values(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    read_keys: list[str],
    *,
    request_timeout: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    try:
        values = reader.read_cue_values(
            workspace_id,
            cue_ref,
            read_keys,
            cache_profile="basic_safe",
            cacheable=False,
            request_timeout=request_timeout,
        )["values"]
        if not isinstance(values, dict):
            raise ValueError("QLab valuesForKeys response must be an object")
        return values, {}
    except Exception as exc:
        return None, {"read_before": str(exc)}


def _try_read_update_values_with_retries(
    reader: Any,
    workspace_id: str,
    cue_ref: str,
    read_keys: list[str],
    requested: dict[str, Any],
    *,
    retry_on_mismatch: bool,
    request_timeout: float | None = None,
    deadline: float | None = None,
) -> tuple[dict[str, Any] | None, dict[str, str]]:
    after, errors = _try_read_update_values(
        reader,
        workspace_id,
        cue_ref,
        read_keys,
        request_timeout=request_timeout,
    )
    if not retry_on_mismatch or _properties_match(after, requested):
        return after, errors
    for delay in AFTER_READ_RETRY_DELAYS:
        remaining = _budget_remaining(deadline)
        if deadline is not None and remaining <= 0:
            break
        time.sleep(delay if deadline is None else min(delay, max(0.0, remaining)))
        after, errors = _try_read_update_values(
            reader,
            workspace_id,
            cue_ref,
            read_keys,
            request_timeout=request_timeout,
        )
        if _properties_match(after, requested):
            return after, errors
    return after, errors


def _try_workspace_cue_ids(reader: Any, workspace_id: str) -> list[str] | None:
    try:
        reply = reader.client.request(_workspace_address(workspace_id, "cueLists/uniqueIDs"))
        return _normalize_id_list(reply.data)
    except Exception:
        return None


def _resolve_created_cue_after_timeout(reader: Any, workspace_id: str, before_ids: list[str] | None) -> str | None:
    if before_ids is None:
        return None
    after_ids = _try_workspace_cue_ids(reader, workspace_id)
    if after_ids is None:
        return None
    created = [cue_id for cue_id in after_ids if cue_id not in set(before_ids)]
    return created[0] if len(created) == 1 else None


def _properties_match(values: Any, requested: dict[str, Any]) -> bool:
    if not isinstance(values, dict):
        return False
    return all(_property_values_match(key, values.get(key), value) for key, value in requested.items())


def _verification_requested_values(item: dict[str, Any]) -> dict[str, Any]:
    requested = dict(item["properties"])
    for operation in item["operations"]:
        read_key = operation.get("read_key")
        args = operation.get("args") or []
        if _phase4c_video_fx_scalar_operation(item) is operation:
            values = operation.get("arg_values") or {}
            requested["videoEffects"] = {
                "__video_fx_scalar__": True,
                "index": values.get("index"),
                "parameterKey": values.get("parameterKey"),
                "setting": values.get("setting"),
            }
            continue
        if read_key and len(args) == 1:
            requested[str(read_key)] = args[0]
    return requested


def _verification_mismatch_message(values: Any, requested: dict[str, Any]) -> str:
    if not isinstance(values, dict):
        return "Fresh after-read did not return cue values for verification."
    mismatches = [
        {"key": key, "requested": requested_value, "after": values.get(key)}
        for key, requested_value in requested.items()
        if not _property_values_match(key, values.get(key), requested_value)
    ]
    return f"Fresh after-read did not confirm requested values: {mismatches}"


def _property_values_match(key: str, actual: Any, requested: Any) -> bool:
    if key == "videoEffects" and isinstance(requested, dict) and requested.get("__video_fx_scalar__") is True:
        index = requested.get("index")
        parameter_key = requested.get("parameterKey")
        if not isinstance(actual, list) or not isinstance(index, int) or index < 0 or index >= len(actual):
            return False
        effect = actual[index]
        if not isinstance(effect, dict) or not isinstance(parameter_key, str):
            return False
        parameters, _ = _video_fx_parameters(effect)
        actual_value = parameters.get(parameter_key)
        requested_value = requested.get("setting")
        return _property_values_match(parameter_key, actual_value, requested_value)
    actual_value = _comparison_value(key, actual)
    requested_value = _comparison_value(key, requested)
    if _is_plain_number(actual_value) and _is_plain_number(requested_value):
        return math.isclose(
            float(actual_value),
            float(requested_value),
            rel_tol=UPDATE_NUMERIC_MATCH_REL_TOLERANCE,
            abs_tol=UPDATE_NUMERIC_MATCH_ABS_TOLERANCE,
        )
    return actual_value == requested_value


def _comparison_value(key: str, value: Any) -> Any:
    if key == "continueMode":
        return _continue_mode_comparison_value(value)
    if key in CASEFOLD_COMPARISON_KEYS and isinstance(value, str):
        return value.strip().casefold()
    return value


def _continue_mode_comparison_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().casefold().replace(" ", "_")
        return CONTINUE_MODE_VALUES.get(normalized, value)
    return CONTINUE_MODE_VALUES.get(value, value)


def _is_plain_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _after_values_for_requested(values: Any, requested: dict[str, Any]) -> dict[str, Any] | None:
    if not isinstance(values, dict):
        return None
    return {key: values.get(key) for key in requested}


def _update_debug_enabled(reader: Any) -> bool:
    config = getattr(getattr(reader, "client", None), "config", None)
    if config is not None and hasattr(config, "update_debug"):
        return bool(getattr(config, "update_debug"))
    return os.getenv("QLAB_UPDATE_DEBUG", "").strip().casefold() in {"1", "true", "yes", "on"}


def _diff_properties(
    before: dict[str, Any] | None,
    requested: dict[str, Any],
    after: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    diff: dict[str, dict[str, Any]] = {}
    for key, requested_value in requested.items():
        entry = {
            "before": before.get(key) if before else None,
            "requested": requested_value,
        }
        if after is not None:
            entry["after"] = after.get(key)
        diff[key] = entry
    return diff


def _extract_created_cue_id(data: Any) -> str:
    if isinstance(data, str):
        return _clean_cue_ref(data)
    if isinstance(data, dict):
        for key in ("uniqueID", "cueID", "cue_id", "id"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return _clean_cue_ref(value)
        cue = data.get("cue")
        if isinstance(cue, dict):
            return _extract_created_cue_id(cue)
    if isinstance(data, list) and data:
        return _extract_created_cue_id(data[0])
    raise UnsafeWriteOperationError("QLab did not return a cue unique ID after /new.")


def _cue_id_address(workspace_id: str, cue_id: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    cue = _clean_cue_ref(cue_id)
    return f"/workspace/{workspace}/cue_id/{cue}/{command.strip('/')}"
