"""Allowlists and value validation for gated QLab write mode."""

from __future__ import annotations

from typing import Any

from ..errors import UnsafeWriteOperationError


WRITABLE_CUE_TYPES: dict[str, str] = {
    "audio": "Audio",
    "video": "Video",
    "text": "Text",
    "light": "Light",
    "network": "Network",
    "midi": "MIDI",
    "timecode": "Timecode",
    "group": "Group",
    "wait": "Wait",
    "memo": "Memo",
}

WRITABLE_CUE_PROPERTIES = (
    "name",
    "number",
    "armed",
    "flagged",
    "colorName",
    "preWait",
    "postWait",
    "duration",
    "continueMode",
)

_CONTINUE_MODE_VALUES = {
    "0": 0,
    "do_not_continue": 0,
    "do-not-continue": 0,
    "manual": 0,
    "none": 0,
    "1": 1,
    "auto_continue": 1,
    "auto-continue": 1,
    "autocontinue": 1,
    "2": 2,
    "auto_follow": 2,
    "auto-follow": 2,
    "autofollow": 2,
}


def validate_writable_cue_type(cue_type: str) -> str:
    normalized = _normalize_token(cue_type)
    if normalized not in WRITABLE_CUE_TYPES:
        allowed = ", ".join(WRITABLE_CUE_TYPES)
        raise UnsafeWriteOperationError(f"cue_type is not allowed for write mode: {cue_type!r}; use one of: {allowed}")
    return WRITABLE_CUE_TYPES[normalized]


def validate_write_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    if properties is None:
        return {}
    if not isinstance(properties, dict):
        raise UnsafeWriteOperationError("properties must be an object")

    normalized: dict[str, Any] = {}
    for raw_key, raw_value in properties.items():
        if not isinstance(raw_key, str):
            raise UnsafeWriteOperationError("property names must be strings")
        key = raw_key.strip()
        if key not in WRITABLE_CUE_PROPERTIES:
            raise UnsafeWriteOperationError(f"Cue property is not allowlisted for write mode: {key}")
        normalized[key] = _validate_property_value(key, raw_value)
    return normalized


def planned_write_capabilities(dry_run_default: bool) -> dict[str, Any]:
    return {
        "create_cue": {
            "planned": True,
            "cue_types": list(WRITABLE_CUE_TYPES),
            "properties": list(WRITABLE_CUE_PROPERTIES),
            "dry_run_default": dry_run_default,
            "placement": {
                "after_cue_id": "dry_run_only_in_this_preface",
                "parent_id": "planned_later",
                "index": "planned_later",
            },
        },
        "edit_existing_cue": {"planned": False},
        "playback_control": {"enabled": False},
        "raw_osc": {"enabled": False},
    }


def _normalize_token(value: str) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("cue_type must be a string")
    normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
    if not normalized:
        raise UnsafeWriteOperationError("cue_type is required")
    return normalized


def _validate_property_value(key: str, value: Any) -> Any:
    if key in {"name", "number", "colorName"}:
        if not isinstance(value, str):
            raise UnsafeWriteOperationError(f"{key} must be a string")
        return value
    if key in {"armed", "flagged"}:
        if not isinstance(value, bool):
            raise UnsafeWriteOperationError(f"{key} must be a boolean")
        return value
    if key in {"preWait", "postWait", "duration"}:
        return _validate_non_negative_number(key, value)
    if key == "continueMode":
        return _validate_continue_mode(value)
    raise UnsafeWriteOperationError(f"Cue property is not allowlisted for write mode: {key}")


def _validate_non_negative_number(key: str, value: Any) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeWriteOperationError(f"{key} must be a non-negative number")
    if value < 0:
        raise UnsafeWriteOperationError(f"{key} must be a non-negative number")
    return value


def _validate_continue_mode(value: Any) -> int:
    if isinstance(value, bool):
        raise UnsafeWriteOperationError("continueMode must be 0, 1, 2, or a known label")
    if isinstance(value, int) and value in {0, 1, 2}:
        return value
    if isinstance(value, float) and value.is_integer() and int(value) in {0, 1, 2}:
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().casefold().replace(" ", "_")
        if normalized in _CONTINUE_MODE_VALUES:
            return _CONTINUE_MODE_VALUES[normalized]
    raise UnsafeWriteOperationError("continueMode must be 0, 1, 2, do_not_continue, auto_continue, or auto_follow")
