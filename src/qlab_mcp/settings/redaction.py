"""Redaction helpers for safe workspace-setting summaries."""

from __future__ import annotations

from typing import Any


ALWAYS_REDACT_KEYS = {
    "passcode",
    "passcodes",
    "password",
    "passwords",
    "secret",
    "secrets",
    "token",
    "tokens",
    "credential",
    "credentials",
}
SAFE_NETWORK_REDACT_KEYS = {
    "address",
    "destination",
    "destinationaddress",
    "host",
    "hostname",
    "interface",
    "ip",
    "ipaddress",
    "network",
    "networkinterface",
    "port",
}
SAFE_DEVICE_REDACT_KEYS = {
    "decklinkhandle",
    "device",
    "deviceid",
    "devicename",
    "destinationinfo",
    "displaymode",
    "displaymodeinfo",
    "screenid",
    "screenserialnumber",
    "serial",
    "serialnumber",
}
REDACTED_VALUE = "[redacted]"
REDACTION_IMPACTS = {
    "credential": "Sensitive credential value is hidden; authentication details cannot be audited from this response.",
    "network_destination": "Network destination details are hidden; exact host, IP, port, or interface cannot be verified.",
    "device_or_route_detail": "Device or route details are hidden; exact hardware, display, or routing identity cannot be verified.",
    "video_destination": "Video destination details are hidden; exact display, screen, or route endpoint cannot be verified.",
}


def _normalize_key_name(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


def _contains_any_key(value: Any, normalized_keys: set[str]) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _normalize_key_name(str(key)) in normalized_keys or _contains_any_key(nested, normalized_keys):
                return True
    if isinstance(value, list):
        return any(_contains_any_key(item, normalized_keys) for item in value)
    return False


def _redaction_reason(section: str, key: str, profile: str) -> str | None:
    normalized_key = _normalize_key_name(key)
    if normalized_key in ALWAYS_REDACT_KEYS:
        return "credential"
    if profile != "safe":
        return None
    if section == "network" and normalized_key in SAFE_NETWORK_REDACT_KEYS:
        return "network_destination"
    if section in {"audio", "video", "midi"} and normalized_key in SAFE_DEVICE_REDACT_KEYS:
        return "device_or_route_detail"
    if section == "video" and normalized_key in SAFE_NETWORK_REDACT_KEYS:
        return "video_destination"
    return None


def _redact_payload(
    value: Any,
    *,
    section: str,
    profile: str,
    redactions: list[dict[str, str]],
    path: str = "",
) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            reason = _redaction_reason(section, str(key), profile)
            if reason is not None:
                redacted[key] = REDACTED_VALUE
                redactions.append(
                    {
                        "section": section,
                        "path": child_path,
                        "reason": reason,
                        "impact": REDACTION_IMPACTS.get(reason, "Redacted value limits conclusions at this path."),
                    }
                )
            else:
                redacted[key] = _redact_payload(
                    nested,
                    section=section,
                    profile=profile,
                    redactions=redactions,
                    path=child_path,
                )
        return redacted
    if isinstance(value, list):
        return [
            _redact_payload(
                item,
                section=section,
                profile=profile,
                redactions=redactions,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return value


def _record_redactions(value: Any, section: str, profile: str, redactions: list[dict[str, str]], path: str) -> None:
    _redact_payload(value, section=section, profile=profile, redactions=redactions, path=path)
