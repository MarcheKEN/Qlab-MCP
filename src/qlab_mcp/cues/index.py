"""Compact cue-index profiles for workspace overviews."""

from __future__ import annotations

from typing import Any, Literal

from .profiles import _derive_profile_fields


CueIndexProfile = Literal["minimal", "health"]

CUE_INDEX_MINIMAL_COLUMNS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "listName",
    "cue_list_id",
    "parent_id",
    "depth",
)
CUE_INDEX_HEALTH_COLUMNS = (
    *CUE_INDEX_MINIMAL_COLUMNS,
    "armed",
    "flagged",
    "colorName",
    "isBroken",
    "isWarning",
    "continueMode",
    "continueModeLabel",
)
CUE_INDEX_MINIMAL_VALUE_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "listName",
)
CUE_INDEX_HEALTH_VALUE_KEYS = (
    *CUE_INDEX_MINIMAL_VALUE_KEYS,
    "armed",
    "flagged",
    "colorName",
    "isBroken",
    "isWarning",
    "continueMode",
)

# Backward-compatible names for internal callers that imported the old constants.
CUE_INDEX_COLUMNS = CUE_INDEX_HEALTH_COLUMNS
CUE_INDEX_VALUE_KEYS = CUE_INDEX_HEALTH_VALUE_KEYS


def normalize_cue_index_profile(profile: str) -> CueIndexProfile:
    normalized = str(profile or "").strip().lower()
    if normalized not in {"minimal", "health"}:
        raise ValueError("cue_index_profile must be 'minimal' or 'health'")
    return normalized  # type: ignore[return-value]


def cue_index_columns(profile: str) -> tuple[str, ...]:
    return CUE_INDEX_HEALTH_COLUMNS if normalize_cue_index_profile(profile) == "health" else CUE_INDEX_MINIMAL_COLUMNS


def cue_index_value_keys(profile: str) -> tuple[str, ...]:
    return CUE_INDEX_HEALTH_VALUE_KEYS if normalize_cue_index_profile(profile) == "health" else CUE_INDEX_MINIMAL_VALUE_KEYS


def _cue_index_row(cue_ref: dict[str, Any], values: dict[str, Any], profile: str = "health") -> list[Any]:
    cue = _derive_profile_fields("cue_index", values)
    cue.setdefault("uniqueID", cue_ref.get("uniqueID"))
    cue["cue_list_id"] = cue_ref.get("cue_list_id")
    cue["parent_id"] = cue_ref.get("parent_id")
    cue["depth"] = cue_ref.get("depth")
    return [cue.get(column) for column in cue_index_columns(profile)]
