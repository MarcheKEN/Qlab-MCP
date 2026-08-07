"""Filtered QLab cue query implementation."""

from __future__ import annotations

from typing import Any

from ..allowlist import properties_for_profile, validate_value_keys
from ..osc.addressing import _clean_workspace_id
from ..sanitizer import sanitize_exception_message, truncate_profile_payload
from .editorial import _is_ambiguous_label, _is_empty_text
from .limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES, sensitive_payload_size
from .profiles import _coerce_qlab_bool, _derive_profile_fields, _is_positive_number
from .refs import _bounded_cue_refs_from_shallow


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
    "cartPosition",
    "cartPosition/row",
    "cartPosition/column",
)
QUERY_DEFAULT_OUTPUT_KEYS = QUERY_BASE_PROPERTIES

MAX_VALUES_FOR_KEYS = 100
MAX_SENSITIVE_QUERY_RESULTS = 50


def _sensitive_query_limit_error(
    workspace_id: str,
    filters: list[dict[str, Any]],
    profile: str,
    max_results: int,
    max_cues_scanned: int,
    message: str,
    *,
    received: dict[str, Any],
    payload_size: int | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "error",
        "error_code": "cue_payload_too_large",
        "message": message,
        "received": {**received, **({"payload_bytes": payload_size} if payload_size is not None else {})},
        "allowed": {
            "max_results": MAX_SENSITIVE_QUERY_RESULTS,
            "max_payload_bytes": MAX_SENSITIVE_CUE_RESPONSE_BYTES,
        },
        "workspace_id": workspace_id,
        "filters": filters,
        "profile": profile,
        "scanned_count": 0,
        "matched_count": 0,
        "returned_count": 0,
        "total_cue_ids": 0,
        "query_completeness": "failed",
        "query_completeness_reasons": ["validation"],
        "id_only_unscanned_count": 0,
        "omitted_branches": [],
        "partial_branches": [],
        "truncated": False,
        "truncation_reasons": [],
        "scanned_all_cues": False,
        "result_limited": False,
        "limits": {"max_results": max_results, "max_cues_scanned": max_cues_scanned},
        "cues": [],
        "warnings": [message],
        "errors": {"validation": message, "error_code": "cue_payload_too_large"},
    }


def _dedupe_preserve_order(values: list[str] | tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys(values))


def _chunk_keys(keys: list[str], size: int = MAX_VALUES_FOR_KEYS) -> list[list[str]]:
    return [keys[index : index + size] for index in range(0, len(keys), size)]


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


def _query_workspace_resolution_error(
    workspace_id: str,
    filters: list[dict[str, Any]],
    profile: str,
    max_results: int,
    max_cues_scanned: int,
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error_code": status,
        "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
        "workspace_id": workspace_id,
        "filters": filters,
        "profile": profile,
        "scanned_count": 0,
        "matched_count": 0,
        "returned_count": 0,
        "total_cue_ids": 0,
        "query_completeness": "failed",
        "query_completeness_reasons": ["workspace_resolution"],
        "id_only_unscanned_count": 0,
        "omitted_branches": [],
        "partial_branches": [],
        "truncated": False,
        "truncation_reasons": [],
        "scanned_all_cues": False,
        "result_limited": False,
        "limits": {
            "max_results": max_results,
            "max_cues_scanned": max_cues_scanned,
        },
        "cues": [],
        "warnings": ["Requested workspace could not be resolved."],
        "errors": {"workspace_resolution": message},
    }


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
        if str(profile).strip().lower() == "exhaustive":
            raise ValueError("profile='exhaustive' is supported only by qlab_get_cue_details")
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
        if str(profile).strip().lower() == "full_sensitive" and max_results > MAX_SENSITIVE_QUERY_RESULTS:
            return _sensitive_query_limit_error(
                _clean_workspace_id(workspace_id),
                filters,
                profile,
                max_results,
                max_cues_scanned,
                "full_sensitive cue queries can return at most 50 cues",
                received={"max_results": max_results, "profile": profile},
            )
        cacheable = not _query_uses_live_state(filters)
        try:
            resolved_workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _query_workspace_resolution_error(
                _clean_workspace_id(workspace_id),
                filters,
                profile,
                max_results,
                max_cues_scanned,
                getattr(exc, "status", "workspace_not_found"),
                str(exc),
            )

        bounded = _bounded_cue_refs_from_shallow(
            self,
            resolved_workspace_id,
            limit=max_cues_scanned,
            max_depth=None,
            cacheable=cacheable,
            fallback_child_ids=True,
        )
        cue_refs = bounded["refs"]
        profile_keys = list(properties_for_profile(profile))
        filter_keys: list[str] = []
        for query_filter in filters:
            filter_keys.extend(QUERY_FILTER_PROPERTIES[query_filter["filter"]])
        keys = _dedupe_preserve_order([*QUERY_BASE_PROPERTIES, *profile_keys, *filter_keys])
        key_chunks = [validate_value_keys(chunk) for chunk in _chunk_keys(keys)]

        scanned_count = 0
        matched_count = 0
        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        scanned_all_cues = not bounded["truncated"]
        omitted_branches = [
            {
                "cue_ref": item.get("cue_ref"),
                "number": item.get("number"),
                "name": item.get("name"),
                "type": item.get("type"),
                "child_count": item.get("child_count"),
                "child_count_source": item.get("child_count_source"),
                "fallback_used": bool(item.get("fallback_used")),
            }
            for item in bounded.get("child_read_errors", [])
        ]
        id_only_unscanned_count = sum(
            int(item.get("child_count") or 0)
            for item in omitted_branches
            if item.get("fallback_used") and item.get("child_count") is not None
        )
        base_truncation_reasons: list[str] = [
            "max_cues_scanned" if reason == "max_cues" else reason
            for reason in bounded["truncation_reasons"]
        ]
        query_completeness_reasons: list[str] = []
        if "max_cues_scanned" in base_truncation_reasons:
            query_completeness_reasons.append("max_cues_scanned")
        if id_only_unscanned_count > 0:
            query_completeness_reasons.append("id_only_unscanned")
        query_completeness = "partial" if query_completeness_reasons else "complete"
        warnings: list[str] = []
        if id_only_unscanned_count > 0:
            warnings.append(
                "Query scanned only cues with metadata available from shallow traversal; "
                "some ID-only branch children were counted but not searched."
            )
        if "max_cues_scanned" in query_completeness_reasons:
            warnings.append(
                "Query stopped at max_cues_scanned before all discoverable cue metadata was scanned."
            )

        def build_result() -> dict[str, Any]:
            result_limited = matched_count > len(cues)
            truncation_reasons = [*base_truncation_reasons]
            if result_limited:
                truncation_reasons.append("max_results")
            return {
                "workspace_id": resolved_workspace_id,
                "filters": filters,
                "profile": profile,
                "scanned_count": scanned_count,
                "matched_count": matched_count,
                "returned_count": len(cues),
                "total_cue_ids": len(cue_refs),
                "query_completeness": query_completeness,
                "query_completeness_reasons": query_completeness_reasons,
                "id_only_unscanned_count": id_only_unscanned_count,
                "omitted_branches": omitted_branches,
                "partial_branches": omitted_branches,
                "truncated": bool(truncation_reasons),
                "truncation_reasons": truncation_reasons,
                "scanned_all_cues": scanned_all_cues,
                "result_limited": result_limited,
                "limits": {
                    "max_results": max_results,
                    "max_cues_scanned": max_cues_scanned,
                },
                "cues": cues,
                "warnings": warnings,
                "errors": {**bounded["errors"], **errors} or None,
            }

        initial_payload_size = sensitive_payload_size(build_result(), profile)
        if initial_payload_size is not None and initial_payload_size > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
            return _sensitive_query_limit_error(
                resolved_workspace_id,
                filters,
                profile,
                max_results,
                max_cues_scanned,
                f"sensitive cue query response exceeds {MAX_SENSITIVE_CUE_RESPONSE_BYTES} bytes",
                received={"profile": profile},
                payload_size=initial_payload_size,
            )

        for cue_ref in cue_refs:
            cue_id = cue_ref.get("uniqueID")
            if not cue_id:
                continue
            scanned_count += 1
            try:
                values: dict[str, Any] = {}
                for key_chunk in key_chunks:
                    chunk_values = self.read_cue_values(
                        resolved_workspace_id,
                        str(cue_id),
                        key_chunk,
                        cache_profile=profile,
                        cacheable=cacheable,
                    )["values"]
                    if not isinstance(chunk_values, dict):
                        raise ValueError("QLab valuesForKeys response must be an object")
                    values.update(chunk_values)
            except Exception as exc:
                errors[str(cue_id)] = sanitize_exception_message(exc)
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
                cue = truncate_profile_payload(profile, _derive_profile_fields(profile, cue))
                cues.append(cue)
                partial_size = sensitive_payload_size(build_result(), profile)
                if partial_size is not None and partial_size > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
                    return _sensitive_query_limit_error(
                        resolved_workspace_id,
                        filters,
                        profile,
                        max_results,
                        max_cues_scanned,
                        (
                            f"sensitive cue query response exceeds "
                            f"{MAX_SENSITIVE_CUE_RESPONSE_BYTES} bytes"
                        ),
                        received={"profile": profile},
                        payload_size=partial_size,
                    )

        result = build_result()
        payload_size = sensitive_payload_size(result, profile)
        if payload_size is not None and payload_size > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
            return _sensitive_query_limit_error(
                resolved_workspace_id,
                filters,
                profile,
                max_results,
                max_cues_scanned,
                f"sensitive cue query response exceeds {MAX_SENSITIVE_CUE_RESPONSE_BYTES} bytes",
                received={"profile": profile},
                payload_size=payload_size,
            )
        return result
