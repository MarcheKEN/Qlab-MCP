"""Gated Workspace Settings writes."""

from __future__ import annotations

import hashlib
import math
import secrets
import struct
import threading
import time
from typing import Any

from ..errors import OscTimeoutError, QLabReplyError
from ..models import GeneralSettingsEditInput, GeneralSettingsEditResult
from ..osc.addressing import _workspace_address
from ..write.safety import check_write_readiness, ensure_write_ready, resolve_dry_run
from ..write.timeouts import AFTER_READ_RETRY_DELAYS, setter_reply_timeout
from ..write.tokens import decode_confirm_token, encode_confirm_token
from .write_registry import WorkspaceSettingsWriteSpec, get_workspace_settings_write_spec


SETTINGS_TOKEN_FAMILY = "workspaceSettings"
SETTINGS_TOKEN_VERSION = 1
SETTINGS_TOKEN_TTL_SECONDS = 300
_SETTINGS_TOKEN_SECRET = secrets.token_bytes(32)
_CONSUMED_SETTINGS_TOKENS: dict[str, int] = {}
_CONSUMED_SETTINGS_TOKENS_LOCK = threading.RLock()


def _canonical_float32(value: int | float) -> float:
    return struct.unpack(">f", struct.pack(">f", float(value)))[0]


def _numeric_match(actual: Any, requested: int | float) -> bool:
    if isinstance(actual, bool) or not isinstance(actual, int | float) or not math.isfinite(float(actual)):
        return False
    expected = float(requested)
    actual_float = float(actual)
    return math.isclose(actual_float, expected, rel_tol=1e-5, abs_tol=1e-5)


def _activity_snapshot(reader: Any, workspace_id: str) -> dict[str, Any]:
    result = reader.get_running_cues(workspace_id, include_paused=True, include_children=True)
    running = result.get("running_cues") if isinstance(result, dict) else None
    if not isinstance(running, list):
        raise ValueError("QLab runningOrPausedCues reply is not a list.")
    cue_ids: list[str] = []
    auditioning: list[str] = []
    for cue in running:
        if isinstance(cue, dict):
            cue_id = str(cue.get("uniqueID") or cue.get("id") or cue)
            if cue.get("isAuditioning") is True or cue.get("auditioning") is True:
                auditioning.append(cue_id)
        else:
            cue_id = str(cue)
        cue_ids.append(cue_id)
    if auditioning:
        raise ValueError("QLab activity data identifies auditioning cues; settings writes are blocked.")
    return {
        "active_count": len(cue_ids),
        "active_cue_ids": sorted(cue_ids),
        "activity_policy": "running_or_paused_zero",
    }


def _consume_settings_token(token: str, payload: dict[str, Any]) -> str | None:
    digest = hashlib.sha256(token.encode()).hexdigest()
    expires_at = int(payload.get("expires_at", 0))
    now = int(time.time())
    with _CONSUMED_SETTINGS_TOKENS_LOCK:
        for consumed, expiry in list(_CONSUMED_SETTINGS_TOKENS.items()):
            if expiry < now:
                del _CONSUMED_SETTINGS_TOKENS[consumed]
        if digest in _CONSUMED_SETTINGS_TOKENS:
            return "confirmation_already_consumed: workspace settings confirm_token has already been used."
        _CONSUMED_SETTINGS_TOKENS[digest] = expires_at
    return None


def _token_payload(
    workspace_id: str,
    operation: str,
    baseline: int | float,
    requested_value: int | float,
    spec: WorkspaceSettingsWriteSpec,
) -> dict[str, Any]:
    return {
        "workspace_id": workspace_id,
        "operation": operation,
        "baseline": _canonical_float32(baseline),
        "requested_value": _canonical_float32(requested_value),
        "requested_input": requested_value,
        "requested_wire_type": type(requested_value).__name__,
        "registry_version": spec.registry_version,
        "expires_at": int(time.time()) + SETTINGS_TOKEN_TTL_SECONDS,
        "nonce": secrets.token_urlsafe(12),
    }


def _token_error(
    token: str | None,
    workspace_id: str,
    operation: str,
    baseline: int | float,
    requested_value: int | float,
    spec: WorkspaceSettingsWriteSpec,
) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(token, str):
        return None, "confirm_token is required for real Workspace Settings writes."
    payload, error = decode_confirm_token(
        token,
        SETTINGS_TOKEN_FAMILY,
        SETTINGS_TOKEN_VERSION,
        _SETTINGS_TOKEN_SECRET,
    )
    if error or payload is None:
        return None, f"confirm_token is invalid ({error or 'malformed'})."
    if not isinstance(payload.get("expires_at"), int) or payload["expires_at"] < int(time.time()):
        return None, "confirm_token has expired."
    expected = _token_payload(workspace_id, operation, baseline, requested_value, spec)
    for key in ("workspace_id", "operation", "registry_version", "requested_wire_type"):
        if payload.get(key) != expected[key]:
            return None, f"confirm_token binding mismatch for {key}."
    if payload.get("requested_input") != requested_value:
        return None, "confirm_token binding mismatch for requested_input."
    for key in ("baseline", "requested_value"):
        try:
            actual = _canonical_float32(float(payload.get(key)))
        except (TypeError, ValueError, OverflowError, struct.error):
            return None, f"confirm_token binding is invalid for {key}."
        if actual != expected[key]:
            return None, f"confirm_token binding mismatch for {key}."
    return payload, None


class WorkspaceSettingsWriteMixin:
    """Single-operation Workspace Settings write surface."""

    def edit_general_settings(
        self,
        workspace_id: str,
        operation: str,
        value: int | float,
        dry_run: bool | None = None,
        confirm_token: str | None = None,
    ) -> GeneralSettingsEditResult:
        request = GeneralSettingsEditInput(
            workspace_id=workspace_id,
            operation=operation,
            value=value,
            dry_run=dry_run,
            confirm_token=confirm_token,
        )
        workspace = str(request.workspace_id)
        is_dry_run = resolve_dry_run(self, request.dry_run)
        spec = get_workspace_settings_write_spec(request.operation)
        readiness: dict[str, Any] | None = None
        activity: dict[str, Any] | None = None
        baseline: int | float | None = None
        planned = [{
            "operation": "set_workspace_setting",
            "property": request.operation,
            "address": _workspace_address(workspace, spec.osc_path),
            "args": [request.value],
            "mode": spec.mode,
            "risk_tier": spec.risk_tier,
            "real_write_enabled": spec.real_write_enabled,
        }]

        try:
            self._resolve_settings_workspace_uuid(workspace)
            readiness = check_write_readiness(self, workspace)
            if not readiness.get("ok"):
                return self._settings_result(
                    request, workspace, is_dry_run, baseline, None, planned, [], readiness=readiness,
                    activity=None, status="dry_run_preflight_failed" if is_dry_run else "preflight_failed",
                    errors={"readiness": readiness.get("message", "Workspace Settings write readiness failed.")},
                    error_code=readiness.get("error_code"),
                    suggested_action=readiness.get("suggested_action"),
                    message="Workspace Settings write was blocked during readiness checks.",
                )
            baseline = self._read_settings_number(workspace, spec)
            activity = _activity_snapshot(self, workspace)
            if activity["active_count"]:
                return self._settings_result(
                    request, workspace, is_dry_run, baseline, None, planned, [], readiness=readiness,
                    activity=activity, status="dry_run_preflight_failed" if is_dry_run else "preflight_failed",
                    errors={"activity": "Workspace has running or paused cues; settings write is blocked."},
                    error_code="QLAB_SETTINGS_ACTIVE_CUES",
                    suggested_action="Stop or pause no cues, then obtain a fresh dry-run token.",
                    message="Workspace Settings write was blocked because cues are active or paused.",
                )
        except Exception as exc:
            return self._settings_result(
                request, workspace, is_dry_run, baseline, None, planned, [], readiness=readiness,
                activity=activity,
                status="dry_run_preflight_failed" if is_dry_run else "preflight_failed",
                errors={"preflight": str(exc)}, error_code="QLAB_SETTINGS_PREFLIGHT_FAILED",
                suggested_action="Inspect the preflight error and retry with the exact workspace UUID.",
                message="Workspace Settings write was blocked during preflight.",
            )

        warnings = ["The activity reader cannot prove workspace-wide Audition state; keep Audition disabled."]
        token = encode_confirm_token(
            SETTINGS_TOKEN_FAMILY,
            SETTINGS_TOKEN_VERSION,
            _token_payload(workspace, request.operation, baseline, request.value, spec),
            _SETTINGS_TOKEN_SECRET,
        )
        if is_dry_run:
            return self._settings_result(
                request, workspace, True, baseline, None, planned, [], readiness=readiness,
                activity=activity, confirm_token=token, warnings=warnings, status="dry_run",
                message="Dry run succeeded; review the planned setter and use its fresh confirm_token to execute once.",
            )

        try:
            payload, token_error = _token_error(
                request.confirm_token, workspace, request.operation, baseline, request.value, spec
            )
            if token_error or payload is None:
                return self._settings_result(
                    request, workspace, False, baseline, None, planned, [], readiness=readiness,
                    activity=activity, warnings=warnings, status="preflight_failed",
                    errors={"confirm_token": token_error or "confirm_token is invalid."},
                    error_code="QLAB_SETTINGS_CONFIRM_TOKEN_INVALID",
                    suggested_action="Run a fresh dry-run and use its exact confirm_token.",
                    message="Workspace Settings write was blocked by confirmation-token validation.",
                )
            ensure_write_ready(self, workspace)
            self._resolve_settings_workspace_uuid(workspace)
            fresh_baseline = self._read_settings_number(workspace, spec)
            fresh_activity = _activity_snapshot(self, workspace)
            if fresh_activity["active_count"]:
                return self._settings_result(
                    request, workspace, False, fresh_baseline, None, planned, [], readiness=readiness,
                    activity=fresh_activity, warnings=warnings, status="preflight_failed",
                    errors={"activity": "Workspace activity changed before mutation."},
                    error_code="QLAB_SETTINGS_ACTIVE_CUES",
                    suggested_action="Stop or pause all cues and obtain a fresh dry-run token.",
                    message="Workspace Settings write was blocked by the immediate activity recheck.",
                )
            if _canonical_float32(fresh_baseline) != _canonical_float32(baseline):
                return self._settings_result(
                    request, workspace, False, fresh_baseline, None, planned, [], readiness=readiness,
                    activity=fresh_activity, warnings=warnings, status="preflight_failed",
                    errors={"confirm_token": "confirm_token baseline is stale."},
                    error_code="QLAB_SETTINGS_STALE_BASELINE",
                    suggested_action="Run a fresh dry-run after confirming the current setting.",
                    message="Workspace Settings write was blocked by a changed baseline.",
                )
            consume_error = _consume_settings_token(request.confirm_token, payload)
            if consume_error:
                return self._settings_result(
                    request, workspace, False, fresh_baseline, None, planned, [], readiness=readiness,
                    activity=fresh_activity, warnings=warnings, status="preflight_failed",
                    errors={"confirm_token": consume_error}, error_code="QLAB_SETTINGS_CONFIRM_TOKEN_REPLAY",
                    suggested_action="Run a fresh dry-run to obtain a single-use token.",
                    message="Workspace Settings write was blocked because the token was already consumed.",
                )
        except Exception as exc:
            return self._settings_result(
                request, workspace, False, baseline, None, planned, [], readiness=readiness,
                activity=activity, warnings=warnings, status="preflight_failed",
                errors={"preflight": str(exc)}, error_code="QLAB_SETTINGS_PREFLIGHT_FAILED",
                suggested_action="Inspect the preflight error and obtain a fresh token.",
                message="Workspace Settings write was blocked before the setter.",
            )

        address = _workspace_address(workspace, spec.osc_path)
        executed = [{"operation": "set_workspace_setting", "property": request.operation, "address": address, "args": [request.value]}]
        setter_error: str | None = None
        setter_timeout = False
        try:
            reply = self._request(address, request.value, workspace_id=workspace, request_timeout=setter_reply_timeout(self, 1))
            if getattr(reply, "status", "ok") != "ok":
                raise QLabReplyError(getattr(reply, "status", "error"), getattr(reply, "data", None), address)
            executed[0]["status"] = "ok"
        except OscTimeoutError as exc:
            setter_error = str(exc)
            setter_timeout = True
            executed[0].update(status="timeout_pending_verification", error=setter_error)
        except Exception as exc:
            setter_error = str(exc)
            executed[0].update(status="error_pending_verification", error=setter_error)

        if hasattr(self, "_read_cache"):
            self._read_cache.clear()
        readback: int | float | None = None
        readback_error: str | None = None
        for attempt in range(len(AFTER_READ_RETRY_DELAYS) + 1):
            try:
                readback = self._read_settings_number(workspace, spec)
                if _numeric_match(readback, request.value) or attempt == len(AFTER_READ_RETRY_DELAYS):
                    break
            except Exception as exc:
                readback_error = str(exc)
                break
            time.sleep(AFTER_READ_RETRY_DELAYS[attempt])
        if readback_error is not None:
            return self._settings_result(
                request, workspace, False, baseline, None, planned, executed, readiness=readiness,
                activity=activity, warnings=warnings, status="verification_inconclusive", retry_unsafe=True,
                verification={"matched": False, "readback_available": False},
                timeout_confirmation={"confirmed": False, "setter_timeout": setter_timeout},
                errors={"readback": readback_error, **({"setter": setter_error} if setter_error else {})},
                error_code="QLAB_SETTINGS_VERIFICATION_INCONCLUSIVE",
                suggested_action="Inspect QLab state manually; do not retry the consumed write.",
                message="Workspace Settings setter was attempted, but fresh readback was unavailable.",
            )
        matched = readback is not None and _numeric_match(readback, request.value)
        if matched:
            status = "updated_with_confirmed_timeouts" if setter_timeout else "updated"
            if setter_error and not setter_timeout:
                warnings = [*warnings, "Setter reply was uncertain, but fresh readback matched the requested value."]
            return self._settings_result(
                request, workspace, False, baseline, readback, planned, executed, readiness=readiness,
                activity=activity, warnings=warnings, status=status,
                verification={"matched": True, "readback_available": True},
                timeout_confirmation={"confirmed": setter_timeout, "setter_timeout": setter_timeout},
                message="Workspace Settings setter completed and fresh readback matched the requested value.",
            )
        return self._settings_result(
            request, workspace, False, baseline, readback, planned, executed, readiness=readiness,
            activity=activity, warnings=warnings, status="verification_failed",
            verification={"matched": False, "readback_available": True},
            timeout_confirmation={"confirmed": False, "setter_timeout": setter_timeout},
            errors={"readback": "Fresh readback did not match the requested value.", **({"setter": setter_error} if setter_error else {})},
            error_code="QLAB_SETTINGS_VERIFICATION_FAILED",
            suggested_action="Inspect the fresh readback; do not retry without a new dry-run token.",
            message="Workspace Settings setter was attempted, but fresh readback did not match.",
        )

    def _resolve_settings_workspace_uuid(self, workspace_id: str) -> str:
        response = self.get_workspaces()
        workspaces = response.get("workspaces") if isinstance(response, dict) else None
        if not isinstance(workspaces, list):
            raise ValueError("QLab workspaces response must be a list.")
        matches = [item for item in workspaces if isinstance(item, dict) and item.get("uniqueID") == workspace_id]
        if len(matches) != 1:
            raise ValueError("workspace_id must exactly match one QLab workspace uniqueID; display names are not accepted.")
        return workspace_id

    def _read_settings_number(self, workspace_id: str, spec: WorkspaceSettingsWriteSpec) -> int | float:
        reply = self._request(_workspace_address(workspace_id, spec.readback_path), workspace_id=workspace_id)
        value = reply.data
        if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(float(value)):
            raise ValueError("QLab Workspace Settings readback is not a finite number.")
        return value

    @staticmethod
    def _settings_result(
        request: GeneralSettingsEditInput,
        workspace_id: str,
        dry_run: bool,
        baseline: int | float | None,
        readback: int | float | None,
        planned: list[dict[str, Any]],
        executed: list[dict[str, Any]],
        *,
        status: str,
        readiness: dict[str, Any] | None,
        activity: dict[str, Any] | None,
        confirm_token: str | None = None,
        verification: dict[str, Any] | None = None,
        timeout_confirmation: dict[str, Any] | None = None,
        retry_unsafe: bool = False,
        errors: dict[str, str] | None = None,
        warnings: list[str] | None = None,
        error_code: str | None = None,
        suggested_action: str | None = None,
        message: str,
    ) -> GeneralSettingsEditResult:
        return GeneralSettingsEditResult(
            ok=status in {"dry_run", "updated", "updated_with_confirmed_timeouts"},
            status=status,
            workspace_id=workspace_id,
            operation=request.operation,
            dry_run=dry_run,
            requested_value=request.value,
            baseline=baseline,
            readback=readback,
            planned_operations=planned,
            executed_operations=executed,
            confirm_token=confirm_token,
            readiness=readiness,
            activity=activity,
            verification=verification,
            timeout_confirmation=timeout_confirmation,
            retry_unsafe=retry_unsafe,
            errors=errors,
            warnings=warnings or [],
            error_code=error_code,
            suggested_action=suggested_action,
            message=message,
        )
