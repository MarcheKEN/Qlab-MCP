"""Response and error helpers for the FastMCP tool layer."""

from __future__ import annotations

from typing import Any

from .errors import (
    OscProtocolError,
    OscTimeoutError,
    QLabMcpError,
    QLabReplyError,
    UnsafeCuePropertyError,
    UnsafeWriteOperationError,
)
from .sanitizer import sanitize_exception_message, stable_error


def safe_tool_error_message(exc: QLabMcpError | ValueError) -> str:
    if isinstance(exc, QLabReplyError):
        if exc.status == "denied":
            return (
                "QLab denied an OSC request. Check the workspace passcode, OSC permissions, "
                "or accept the connection prompt in QLab."
            )
        return f"QLab returned status {exc.status!r} for an OSC request."
    if isinstance(exc, OscTimeoutError):
        return "Timed out waiting for QLab to reply over OSC. Check that QLab is running and OSC is enabled."
    if isinstance(exc, OscProtocolError):
        if exc.error_code:
            return f"{exc.error_code}: {exc}"
        return "QLab returned an invalid or unexpected OSC reply."
    if isinstance(exc, UnsafeCuePropertyError):
        return "The requested cue property or profile is not allowed for read-only access."
    if isinstance(exc, UnsafeWriteOperationError):
        if exc.error_code:
            return f"{exc.error_code}: {exc}"
        return str(exc)
    return sanitize_exception_message(exc)


def structured_error_result(
    *,
    error_code: str,
    message: str,
    received: Any = None,
    allowed: Any = None,
    details: Any = None,
) -> dict[str, Any]:
    payload = stable_error(
        error_code=error_code,
        message=message,
        details=details,
        received=received,
        allowed=allowed,
    )
    payload["status"] = "error"
    payload["partial"] = False
    return payload


def read_status_from_payload(payload: dict[str, Any], *, partial: bool = False) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("ok") is False:
        normalized["partial"] = False
        if normalized.get("error_code") is None and normalized.get("status") not in {None, "error"}:
            normalized["error_code"] = normalized.get("status")
        normalized["status"] = "error"
        return normalized
    if normalized.get("ok") is None:
        normalized["ok"] = True
    effective_partial = bool(partial or normalized.get("partial") or normalized.get("errors"))
    normalized["partial"] = effective_partial
    if normalized.get("status") is None:
        normalized["status"] = "partial" if effective_partial else "ok"
    return normalized


def overview_success_payload(payload: dict[str, Any]) -> dict[str, Any]:
    limits = payload.get("limits") if isinstance(payload.get("limits"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    partial = bool(
        payload.get("errors")
        or (limits or {}).get("truncated")
        or summary.get("total_cue_ids_status") not in {None, "known"}
        or summary.get("health_counts_status") not in {None, "known", "not_calculated"}
    )
    return read_status_from_payload(payload, partial=partial)


def settings_success_payload(payload: dict[str, Any]) -> dict[str, Any]:
    partial = bool(payload.get("errors") or (payload.get("failed_count") or 0) > 0)
    return read_status_from_payload(payload, partial=partial)


def query_success_payload(payload: dict[str, Any]) -> dict[str, Any]:
    partial = bool(payload.get("errors") or payload.get("query_completeness") == "partial" or payload.get("truncated"))
    return read_status_from_payload(payload, partial=partial)


def cue_details_item_payload(payload: dict[str, Any]) -> dict[str, Any]:
    errors = payload.get("errors")
    error_code = errors.get("error_code") if isinstance(errors, dict) else None
    has_readable_payload = bool(payload.get("properties")) or payload.get("cue_type") is not None
    if error_code == "cue_ref_unresolved" and not has_readable_payload:
        return read_status_from_payload({**payload, "ok": False})
    return read_status_from_payload(payload)


def cue_details_success_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload.get("results"), list):
        payload = {
            **payload,
            "results": [
                cue_details_item_payload(item)
                if isinstance(item, dict)
                else item
                for item in payload["results"]
            ],
        }
    partial = bool(payload.get("errors") or (payload.get("failed_count") or 0) > 0)
    return read_status_from_payload(payload, partial=partial)
