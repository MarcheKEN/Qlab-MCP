"""Filtered QLab cue query implementation."""

from __future__ import annotations

from typing import Any

from ..allowlist import properties_for_profile, validate_value_keys
from ..osc.addressing import _clean_workspace_id, _workspace_address
from .editorial import _is_ambiguous_label, _is_empty_text
from .profiles import _coerce_qlab_bool, _derive_profile_fields, _is_positive_number
from .refs import _flatten_cue_refs


QUERY_FILTERS = {
    "type",
    "flagged",
    "armed",
    "disarmed",
    "isBroken",
    "isWarning",
    "isRunning",
    "isPaused",
    "isLoaded",
    "isOverridden",
    "isAuditioning",
    "colorName",
    "name_contains",
    "number_prefix",
    "cue_list_id",
    "parent_id",
    "hasFileTargets",
    "hasCueTargets",
    "skipIfDisarmed",
    "autoLoad",
    "continueMode",
    "hasPreWait",
    "hasPostWait",
    "hasDuration",
    "name_empty",
    "displayName_empty",
    "number_empty",
    "ambiguous_label",
    "flagged_or_broken",
}
LIVE_STATE_QUERY_FILTERS = {
    "isRunning",
    "isPaused",
    "isLoaded",
    "isOverridden",
    "isAuditioning",
}
QUERY_FILTER_PROPERTIES = {
    "type": ("type",),
    "flagged": ("flagged",),
    "armed": ("armed",),
    "disarmed": ("armed",),
    "isBroken": ("isBroken",),
    "isWarning": ("isWarning",),
    "isRunning": ("isRunning",),
    "isPaused": ("isPaused",),
    "isLoaded": ("isLoaded",),
    "isOverridden": ("isOverridden",),
    "isAuditioning": ("isAuditioning",),
    "colorName": ("colorName",),
    "name_contains": ("name", "displayName", "listName"),
    "number_prefix": ("number",),
    "cue_list_id": (),
    "parent_id": ("parent",),
    "hasFileTargets": ("hasFileTargets",),
    "hasCueTargets": ("hasCueTargets",),
    "skipIfDisarmed": ("skipIfDisarmed",),
    "autoLoad": ("autoLoad",),
    "continueMode": ("continueMode",),
    "hasPreWait": ("preWait",),
    "hasPostWait": ("postWait",),
    "hasDuration": ("duration",),
    "name_empty": ("name",),
    "displayName_empty": ("displayName",),
    "number_empty": ("number",),
    "ambiguous_label": ("name", "displayName", "listName", "number", "type"),
    "flagged_or_broken": ("flagged", "isBroken"),
}
QUERY_BASE_PROPERTIES = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
    "isBroken",
    "isWarning",
    "skipIfDisarmed",
    "autoLoad",
    "continueMode",
    "hasFileTargets",
    "hasCueTargets",
    "isLoaded",
)
QUERY_DEFAULT_OUTPUT_KEYS = QUERY_BASE_PROPERTIES

def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(values))

def _normalize_query_filter(filter_name: str, value: Any) -> dict[str, Any]:
    normalized = filter_name.strip()
    if normalized not in QUERY_FILTERS:
        allowed = ", ".join(sorted(QUERY_FILTERS))
        raise ValueError(f"Unknown cue query filter {filter_name!r}; use one of: {allowed}")
    return {"filter": normalized, "value": value}

def _normalize_optional_filters(filters: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    normalized_filters: list[dict[str, Any]] = []
    for item in filters or []:
        if not isinstance(item, dict):
            raise ValueError("optional_filters entries must be objects with filter and value")
        filter_name = item.get("filter") or item.get("name") or item.get("field")
        if not isinstance(filter_name, str):
            raise ValueError("optional_filters entries require a string filter")
        normalized_filters.append(_normalize_query_filter(filter_name, item.get("value")))
    return normalized_filters

def _query_uses_live_state(filters: list[dict[str, Any]]) -> bool:
    return any(query_filter["filter"] in LIVE_STATE_QUERY_FILTERS for query_filter in filters)

def _parse_bool_filter(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "t", "yes", "y", "1"}:
            return True
        if normalized in {"false", "f", "no", "n", "0"}:
            return False
    raise ValueError(f"Boolean cue query filter value must be true or false: {value!r}")

def _string_equals(actual: Any, expected: Any) -> bool:
    return str(actual or "").casefold() == str(expected or "").casefold()

def _matches_bool_filter(actual: Any, expected: Any) -> bool:
    normalized = _coerce_qlab_bool(actual)
    return normalized is not None and normalized is _parse_bool_filter(expected)

def _cue_matches_filter(cue: dict[str, Any], cue_ref: dict[str, Any], query_filter: dict[str, Any]) -> bool:
    filter_name = query_filter["filter"]
    expected = query_filter["value"]
    if filter_name in {
        "flagged",
        "armed",
        "isBroken",
        "isWarning",
        "isRunning",
        "isPaused",
        "isLoaded",
        "isOverridden",
        "isAuditioning",
        "hasFileTargets",
        "hasCueTargets",
        "skipIfDisarmed",
        "autoLoad",
    }:
        return _matches_bool_filter(cue.get(filter_name), expected)
    if filter_name == "disarmed":
        armed = _coerce_qlab_bool(cue.get("armed"))
        return armed is not None and (not armed) is _parse_bool_filter(expected)
    if filter_name in {"type", "colorName"}:
        return _string_equals(cue.get(filter_name), expected)
    if filter_name == "continueMode":
        return _string_equals(cue.get("continueMode"), expected)
    if filter_name == "hasPreWait":
        return _is_positive_number(cue.get("preWait")) is _parse_bool_filter(expected)
    if filter_name == "hasPostWait":
        return _is_positive_number(cue.get("postWait")) is _parse_bool_filter(expected)
    if filter_name == "hasDuration":
        return _is_positive_number(cue.get("duration")) is _parse_bool_filter(expected)
    if filter_name == "name_empty":
        return _is_empty_text(cue.get("name")) is _parse_bool_filter(expected)
    if filter_name == "displayName_empty":
        return _is_empty_text(cue.get("displayName")) is _parse_bool_filter(expected)
    if filter_name == "number_empty":
        return _is_empty_text(cue.get("number")) is _parse_bool_filter(expected)
    if filter_name == "ambiguous_label":
        return _is_ambiguous_label(cue) is _parse_bool_filter(expected)
    if filter_name == "flagged_or_broken":
        flagged = _coerce_qlab_bool(cue.get("flagged")) is True
        broken = _coerce_qlab_bool(cue.get("isBroken")) is True
        return (flagged or broken) is _parse_bool_filter(expected)
    if filter_name == "name_contains":
        needle = str(expected or "").casefold()
        haystack = " ".join(str(cue.get(key) or "") for key in ("name", "displayName", "listName")).casefold()
        return needle in haystack
    if filter_name == "number_prefix":
        return str(cue.get("number") or "").startswith(str(expected or ""))
    if filter_name == "cue_list_id":
        return _string_equals(cue_ref.get("cue_list_id") or cue.get("parent"), expected)
    if filter_name == "parent_id":
        return _string_equals(cue_ref.get("parent_id") or cue.get("parent"), expected)
    raise ValueError(f"Unknown cue query filter {filter_name!r}")


class CueQueryMixin:
    def query_cues(
        self,
        workspace_id: str,
        primary_filter: str,
        primary_value: Any,
        optional_filters: list[dict[str, Any]] | None = None,
        profile: str = "basic_safe",
        max_results: int = 500,
        max_cues_scanned: int = 500,
    ) -> dict[str, Any]:
        if max_results < 1:
            raise ValueError("max_results must be 1 or greater")
        if max_results > 5000:
            raise ValueError("max_results must be 5000 or lower")
        if max_cues_scanned < 1:
            raise ValueError("max_cues_scanned must be 1 or greater")
        if max_cues_scanned > 5000:
            raise ValueError("max_cues_scanned must be 5000 or lower")

        filters = [
            _normalize_query_filter(primary_filter, primary_value),
            *_normalize_optional_filters(optional_filters),
        ]
        cacheable = not _query_uses_live_state(filters)

        cue_ref_data = self._request_data(
            _workspace_address(workspace_id, "cueLists/uniqueIDs"),
            workspace_id=workspace_id,
            cacheable=cacheable,
            cache_profile=profile,
        )
        cue_refs = _flatten_cue_refs(cue_ref_data)
        profile_keys = list(properties_for_profile(profile))
        filter_keys: list[str] = []
        for query_filter in filters:
            filter_keys.extend(QUERY_FILTER_PROPERTIES[query_filter["filter"]])
        keys = validate_value_keys(_dedupe_preserve_order([*QUERY_BASE_PROPERTIES, *profile_keys, *filter_keys]))

        scanned_count = 0
        matched_count = 0
        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        for cue_ref in cue_refs[:max_cues_scanned]:
            cue_id = cue_ref.get("uniqueID")
            if not cue_id:
                continue
            scanned_count += 1
            try:
                values = self.read_cue_values(
                    workspace_id,
                    str(cue_id),
                    keys,
                    cache_profile=profile,
                    cacheable=cacheable,
                )["values"]
                if not isinstance(values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
            except Exception as exc:
                errors[str(cue_id)] = str(exc)
                continue

            if not all(_cue_matches_filter(values, cue_ref, query_filter) for query_filter in filters):
                continue

            matched_count += 1
            if len(cues) < max_results:
                cue = {
                    key: values.get(key)
                    for key in keys
                    if key in values or key in QUERY_DEFAULT_OUTPUT_KEYS
                }
                cue["parent_id"] = cue_ref.get("parent_id")
                cue["cue_list_id"] = cue_ref.get("cue_list_id")
                cue["depth"] = cue_ref.get("depth")
                cue = _derive_profile_fields(profile, cue)
                cues.append(cue)

        scanned_all_cues = len(cue_refs) <= max_cues_scanned
        result_limited = matched_count > len(cues)
        truncation_reasons: list[str] = []
        if not scanned_all_cues:
            truncation_reasons.append("max_cues_scanned")
        if result_limited:
            truncation_reasons.append("max_results")
        truncated = bool(truncation_reasons)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "filters": filters,
            "profile": profile,
            "scanned_count": scanned_count,
            "matched_count": matched_count,
            "returned_count": len(cues),
            "total_cue_ids": len(cue_refs),
            "truncated": truncated,
            "truncation_reasons": truncation_reasons,
            "scanned_all_cues": scanned_all_cues,
            "result_limited": result_limited,
            "limits": {
                "max_results": max_results,
                "max_cues_scanned": max_cues_scanned,
            },
            "cues": cues,
            "errors": errors or None,
        }
