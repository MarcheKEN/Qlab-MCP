"""Response sanitation, truncation, and stable error helpers."""

from __future__ import annotations

from typing import Any


DEFAULT_TEXT_LIMIT = 512
INTERNAL_PATH_MARKERS = (
    "/qlab-mcp-osc/",
    "/src/qlab_mcp/",
    "/.codex/",
    "/.agents/",
    "/references/qlab/",
)
INTERNAL_PATH_KEYS = {
    "source_path",
    "traceback",
    "stack",
    "stacktrace",
}
MEDIA_PATH_KEYS = {
    "fileTarget",
    "audioFileTarget",
    "videoFileTarget",
}
REDACTED_INTERNAL_PATH = "[redacted_internal_path]"
TRUNCATABLE_TEXT_KEYS = {
    "notes",
    "text",
    "scriptSource",
    "scriptText",
    "lightCommandText",
    "message",
    "messageError",
    "customString",
    "rawString",
}
COMPACT_PROFILES = {
    "auto",
    "basic",
    "basic_safe",
    "health",
    "targets",
    "type_specific",
    "inspector_safe",
    "editable",
    "technical",
}
FULL_TEXT_PROFILES = {"full", "full_sensitive", "exhaustive"}


def stable_error(
    *,
    error_code: str,
    message: str,
    details: Any = None,
    received: Any = None,
    allowed: Any = None,
) -> dict[str, Any]:
    """Build stable, JSON-serializable validation error payload."""
    payload: dict[str, Any] = {
        "ok": False,
        "error_code": error_code,
        "message": sanitize_response(message),
        "details": sanitize_response(details) if details is not None else None,
        "received": sanitize_response(received) if received is not None else None,
        "allowed": sanitize_response(allowed) if allowed is not None else None,
    }
    return payload


def sanitize_response(value: Any, *, redact_internal_paths: bool = True, key: str | None = None) -> Any:
    """Redact MCP/project internals from arbitrary response payloads."""
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            key_str = str(key)
            if key_str in INTERNAL_PATH_KEYS:
                continue
            redacted[key] = sanitize_response(nested, redact_internal_paths=redact_internal_paths, key=key_str)
        return redacted
    if isinstance(value, list):
        return [sanitize_response(item, redact_internal_paths=redact_internal_paths, key=key) for item in value]
    if isinstance(value, tuple):
        return [sanitize_response(item, redact_internal_paths=redact_internal_paths, key=key) for item in value]
    if isinstance(value, str) and redact_internal_paths:
        if key not in MEDIA_PATH_KEYS and any(marker in value for marker in INTERNAL_PATH_MARKERS):
            return REDACTED_INTERNAL_PATH
    return value


def sanitize_exception_message(exc: Exception | str) -> str:
    """Return a compact, stable exception summary without tracebacks or internal paths."""
    text = str(exc)
    if any(marker in text for marker in INTERNAL_PATH_MARKERS):
        return REDACTED_INTERNAL_PATH
    first_line = text.splitlines()[0] if text else exc.__class__.__name__ if isinstance(exc, Exception) else ""
    return str(first_line)[:DEFAULT_TEXT_LIMIT]


def truncate_profile_payload(profile: str, value: Any, *, limit: int = DEFAULT_TEXT_LIMIT) -> Any:
    """Truncate large/sensitive text for compact profiles while preserving shape."""
    normalized = str(profile or "").strip().lower()
    if normalized in FULL_TEXT_PROFILES:
        return sanitize_response(value)
    if normalized not in COMPACT_PROFILES:
        return sanitize_response(value)
    return _truncate_value(sanitize_response(value), limit=limit)


def _truncate_value(value: Any, *, limit: int, key: str | None = None) -> Any:
    if isinstance(value, dict):
        truncated: dict[str, Any] = {}
        for child_key, child_value in value.items():
            child_key_str = str(child_key)
            if child_key_str in INTERNAL_PATH_KEYS:
                continue
            truncated[child_key] = _truncate_value(child_value, limit=limit, key=child_key_str)
        return truncated
    if isinstance(value, list):
        return [_truncate_value(item, limit=limit, key=key) for item in value]
    if isinstance(value, str) and (key in TRUNCATABLE_TEXT_KEYS or len(value) > limit * 4):
        if len(value) > limit:
            return {
                "value": value[:limit],
                "field_truncated": True,
                "original_length": len(value),
            }
    return value
