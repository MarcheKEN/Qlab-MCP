"""Compatibility facade for gated QLab write-mode validation."""

from __future__ import annotations

from typing import Any

from ..errors import UnsafeWriteOperationError
from .registry import (
    COMMON_UPDATE_PROFILE,
    VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES,
    UPDATE_PROFILE_NAMES,
    UPDATE_PROFILES,
    ensure_real_write_allowed,
    normalize_update_request,
    planned_write_capabilities,
    profile_catalog,
    read_keys_for_operations,
    real_write_permission_errors,
    validate_update_profile,
    validate_update_profile_for_cue,
)


CUE_TYPES: dict[str, str] = {
    "memo": "memo",
    "group": "group",
    "wait": "wait",
    "audio": "audio",
    "mic": "mic",
    "video": "video",
    "camera": "camera",
    "text": "text",
    "light": "light",
    "fade": "fade",
    "network": "network",
    "midi": "midi",
    "midi_file": "midi file",
    "timecode": "timecode",
    "start": "start",
    "stop": "stop",
    "pause": "pause",
    "load": "load",
    "reset": "reset",
    "devamp": "devamp",
    "goto": "goto",
    "target": "target",
    "arm": "arm",
    "disarm": "disarm",
}

# Compatibility name for callers that used the old allowlist constant.
WRITABLE_CUE_TYPES = CUE_TYPES

WRITABLE_CUE_PROPERTIES = tuple(profile_catalog()[COMMON_UPDATE_PROFILE]["properties"])


def validate_writable_cue_type(cue_type: str) -> str:
    normalized = _normalize_token(cue_type)
    if normalized not in CUE_TYPES:
        allowed = ", ".join(CUE_TYPES)
        raise UnsafeWriteOperationError(f"cue_type is not allowed for write mode: {cue_type!r}; use one of: {allowed}")
    return CUE_TYPES[normalized]


def writable_cue_type_label(cue_type: str) -> str:
    normalized = _normalize_token(cue_type)
    if normalized not in CUE_TYPES:
        validate_writable_cue_type(cue_type)
    return {"midi": "MIDI", "midi_file": "MIDI File", "goto": "GoTo"}.get(normalized, normalized.title())


def validate_write_properties(properties: dict[str, Any] | None) -> dict[str, Any]:
    return normalize_write_properties(properties)[0]


def normalize_write_properties(
    properties: dict[str, Any] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Normalize common Edit properties through the registry once."""
    if properties is None:
        return {}, []
    normalized_properties, operations = normalize_update_request(COMMON_UPDATE_PROFILE, properties, None)
    blocked = [operation["property"] for operation in operations if not operation["real_write_enabled"]]
    if blocked:
        blocked_text = ", ".join(blocked)
        raise UnsafeWriteOperationError(
            f"cue edit property is not allowlisted for real writes; blocked: {blocked_text}"
        )
    return normalized_properties, operations


def validate_update_properties(
    properties: dict[str, Any] | None,
    *,
    profile: str = COMMON_UPDATE_PROFILE,
) -> dict[str, Any]:
    if properties is None:
        return {}
    normalized_properties, _ = normalize_update_request(profile, properties, None)
    return normalized_properties


def _normalize_token(value: str) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("cue_type must be a string")
    normalized = value.strip().casefold().replace(" ", "_").replace("-", "_")
    if not normalized:
        raise UnsafeWriteOperationError("cue_type is required")
    return normalized
