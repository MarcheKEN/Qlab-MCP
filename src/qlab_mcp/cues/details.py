"""Cue detail profiles and deep cue inspection."""

from __future__ import annotations

from typing import Any

from ..allowlist import properties_for_profile, validate_value_keys
from ..errors import QLabReplyError
from ..osc.addressing import _clean_cue_ref, _clean_workspace_id
from ..sanitizer import sanitize_exception_message, truncate_profile_payload
from ..write.registry import editable_update_capabilities
from .profiles import (
    _auto_type_specific_keys,
    _build_auto_sections,
    _build_video_summary,
    _derive_profile_fields,
    _empty_auto_sections,
    _is_active_cue_ref,
)
from .coverage import default_read_coverage_report


MAX_VALUES_FOR_KEYS = 100
MAX_BATCH_CUE_DETAILS = 50
UNRESOLVED_CUE_ERROR_CODE = "cue_ref_unresolved"
EXHAUSTIVE_WARNING = (
    "profile='exhaustive' may return large, sensitive, or heavy read-only payloads "
    "including notes, file targets, scripts, stage data, maps, routing, and geometry."
)
EXHAUSTIVE_BATCH_WARNING = (
    "Batch exhaustive cue details can be very large; prefer one cue or a small batch "
    "unless load testing."
)


def _chunk_keys(keys: list[str] | tuple[str, ...], size: int = MAX_VALUES_FOR_KEYS) -> list[list[str]]:
    return [list(keys[index : index + size]) for index in range(0, len(keys), size)]


def _looks_unresolved(values: dict[str, Any], errors: dict[str, str]) -> bool:
    return not values and bool(errors) and any(key.startswith("valuesForKeys") for key in errors)


def _compact_unresolved_errors() -> dict[str, str]:
    return {
        "error_code": UNRESOLVED_CUE_ERROR_CODE,
        "message": "Cue ref could not be resolved or read.",
    }


def _workspace_resolution_errors(status: str, message: str) -> dict[str, str]:
    return {
        "error_code": status,
        "message": message,
    }


def _batch_error_summary(result: dict[str, Any]) -> str:
    result_errors = result.get("errors")
    if isinstance(result_errors, dict) and result_errors.get("error_code"):
        return str(result_errors["error_code"])
    return "Cue detail read returned errors; inspect results item errors for details."


def _profile_warnings(profile: str, requested_count: int = 1) -> list[str]:
    if profile.strip().lower() != "exhaustive":
        return []
    warnings = [EXHAUSTIVE_WARNING]
    if requested_count > 1:
        warnings.append(EXHAUSTIVE_BATCH_WARNING)
    return warnings


def _attach_read_coverage(result: dict[str, Any], profile: str) -> None:
    if profile.strip().lower() == "exhaustive":
        result["read_coverage"] = default_read_coverage_report()


def _failed_cue_detail_result(
    workspace_id: str,
    cue_ref: str,
    profile: str,
    error_code: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "error",
        "partial": False,
        "error_code": error_code,
        "message": message,
        "workspace_id": _clean_workspace_id(workspace_id),
        "cue_ref": str(cue_ref).strip().strip("/"),
        "profile": profile,
        "cue_type": None,
        "properties": {},
        "sections": None,
        "update_capabilities": None,
        "errors": {"error_code": error_code, "message": message},
        "warnings": [],
        "active_count": None,
    }


def _normalize_cue_detail_result(result: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(result)
    errors = normalized.get("errors")
    error_code = errors.get("error_code") if isinstance(errors, dict) else None
    has_readable_payload = bool(normalized.get("properties")) or normalized.get("cue_type") is not None
    if normalized.get("ok") is False or (error_code == UNRESOLVED_CUE_ERROR_CODE and not has_readable_payload):
        normalized["ok"] = False
        normalized["status"] = "error"
        normalized["partial"] = False
        normalized["error_code"] = normalized.get("error_code") or error_code
        if normalized.get("message") is None and isinstance(errors, dict):
            normalized["message"] = errors.get("message")
        return normalized
    if errors:
        normalized["ok"] = True
        normalized["status"] = "partial"
        normalized["partial"] = True
        return normalized
    normalized["ok"] = True
    normalized["status"] = "ok"
    normalized["partial"] = False
    return normalized


class CueDetailsMixin:
    def _attach_video_summaries(
        self,
        workspace_id: str,
        results: list[dict[str, Any]],
        profile: str,
    ) -> None:
        if profile.strip().lower() != "inspector_safe":
            return
        visual_results = [
            result for result in results
            if str(result.get("cue_type") or "").strip().casefold() in {"video", "text", "camera"}
        ]
        if not visual_results:
            return
        settings_errors: dict[str, str] = {}
        try:
            video_settings = self._workspace_settings_video(workspace_id, "safe", [], settings_errors)
        except Exception as exc:
            settings_errors["video.settings"] = sanitize_exception_message(exc)
            video_settings = None
        for result in visual_results:
            summary = _build_video_summary(result.get("properties", {}), video_settings, settings_errors)
            if summary is None:
                continue
            sections = result.setdefault("sections", {})
            sections["video_summary"] = summary

    def _read_cue_values_with_fallback(
        self,
        workspace_id: str,
        cue_ref: str,
        keys: list[str] | tuple[str, ...],
        errors: dict[str, str],
        error_key: str = "valuesForKeys",
        profile: str | None = None,
        cacheable: bool = True,
    ) -> dict[str, Any]:
        if not keys:
            return {}
        values: dict[str, Any] = {}
        for chunk_index, raw_chunk in enumerate(_chunk_keys(keys), start=1):
            normalized_keys = validate_value_keys(raw_chunk)
            chunk_error_key = error_key if chunk_index == 1 else f"{error_key}:{chunk_index}"
            try:
                batched_values = self.read_cue_values(
                    workspace_id,
                    cue_ref,
                    normalized_keys,
                    cache_profile=profile,
                    cacheable=cacheable,
                )["values"]
                if not isinstance(batched_values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
                values.update(batched_values)
                continue
            except Exception as exc:
                errors[chunk_error_key] = sanitize_exception_message(exc)

            for property_path in normalized_keys:
                try:
                    values[property_path] = self.read_cue_property(workspace_id, cue_ref, property_path)["value"]
                except Exception as property_exc:
                    errors[property_path] = sanitize_exception_message(property_exc)
        return values

    def _get_auto_cue_details(self, workspace_id: str, cue_ref: str) -> dict[str, Any]:
        errors: dict[str, str] = {}
        common_keys = list(properties_for_profile("auto"))
        if _is_active_cue_ref(cue_ref):
            try:
                active_values = self.read_cue_values(
                    workspace_id,
                    cue_ref,
                    common_keys,
                    cache_profile="auto",
                    cacheable=False,
                )["values"]
                if not isinstance(active_values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
                values = active_values
            except QLabReplyError as exc:
                if exc.status == "error":
                    return self._empty_active_details(workspace_id, cue_ref, "auto")
                raise
        else:
            values = self._read_cue_values_with_fallback(workspace_id, cue_ref, common_keys, errors, profile="auto")
        if _looks_unresolved(values, errors):
            errors = _compact_unresolved_errors()
        values = truncate_profile_payload("auto", _derive_profile_fields("auto", values))

        type_specific_keys = [
            key for key in _auto_type_specific_keys(values.get("type")) if key not in values
        ]
        if type_specific_keys:
            cacheable = not _is_active_cue_ref(cue_ref)
            type_specific_values = self._read_cue_values_with_fallback(
                workspace_id,
                cue_ref,
                type_specific_keys,
                errors,
                error_key="valuesForKeys:type_specific",
                profile="auto",
                cacheable=cacheable,
            )
            values.update(type_specific_values)
            values = truncate_profile_payload("auto", _derive_profile_fields("auto", values))

        result: dict[str, Any] = {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "profile": "auto",
            "cue_type": values.get("type"),
            "properties": values,
            "sections": _build_auto_sections(values),
        }
        if errors:
            result["errors"] = errors
        return result

    def _empty_active_details(self, workspace_id: str, cue_ref: str, profile: str) -> dict[str, Any]:
        result: dict[str, Any] = {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "profile": profile,
            "cue_type": None,
            "properties": {},
            "active_count": 0,
            "message": "No active cues are currently running or paused.",
        }
        _attach_read_coverage(result, profile)
        if profile.strip().lower() == "auto":
            result["sections"] = _empty_auto_sections()
        return result

    def _get_single_cue_details(
        self,
        workspace_id: str,
        cue_ref: str,
        profile: str = "auto",
        include_read_coverage: bool = True,
    ) -> dict[str, Any]:
        normalized_profile = profile.strip().lower()
        if normalized_profile == "auto":
            return self._get_auto_cue_details(workspace_id, cue_ref)
        if normalized_profile == "editable":
            result = self._get_auto_cue_details(workspace_id, cue_ref)
            result["profile"] = "editable"
            result["update_capabilities"] = editable_update_capabilities(result.get("cue_type"))
            return result

        keys = list(properties_for_profile(profile))
        errors: dict[str, str] = {}
        if _is_active_cue_ref(cue_ref):
            try:
                values = self.read_cue_values(
                    workspace_id,
                    cue_ref,
                    keys,
                    cache_profile=profile,
                    cacheable=False,
                )["values"]
                if not isinstance(values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
            except QLabReplyError as exc:
                if exc.status == "error":
                    return self._empty_active_details(workspace_id, cue_ref, profile)
                raise
        else:
            values = self._read_cue_values_with_fallback(
                workspace_id,
                cue_ref,
                keys,
                errors,
                profile=profile,
                cacheable=normalized_profile != "exhaustive",
            )
        if _looks_unresolved(values, errors):
            errors = _compact_unresolved_errors()
        values = truncate_profile_payload(profile, _derive_profile_fields(profile, values))

        result: dict[str, Any] = {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "profile": profile,
            "cue_type": values.get("type"),
            "properties": values,
        }
        warnings = _profile_warnings(normalized_profile)
        if warnings:
            result["warnings"] = warnings
        if include_read_coverage:
            _attach_read_coverage(result, normalized_profile)
        if normalized_profile == "inspector_safe":
            result["sections"] = _build_auto_sections(values)
        if errors:
            result["errors"] = errors
        return result

    def get_cue_details(self, workspace_id: str, cue_ref: str | list[str], profile: str = "auto") -> dict[str, Any]:
        requested_workspace_id = _clean_workspace_id(workspace_id)
        try:
            resolved_workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            errors = _workspace_resolution_errors(
                getattr(exc, "status", "workspace_not_found"),
                sanitize_exception_message(exc),
            )
            if isinstance(cue_ref, str):
                result = _failed_cue_detail_result(
                    requested_workspace_id,
                    cue_ref,
                    profile,
                    errors["error_code"],
                    errors["message"],
                )
                result["warnings"] = ["Requested workspace could not be resolved."]
                return result
            return {
                "ok": False,
                "status": "error",
                "partial": False,
                "error_code": errors["error_code"],
                "message": "Requested workspace could not be resolved.",
                "workspace_id": requested_workspace_id,
                "requested_count": len(cue_ref) if isinstance(cue_ref, list) else 0,
                "succeeded_count": 0,
                "failed_count": len(cue_ref) if isinstance(cue_ref, list) else 0,
                "profile": profile,
                "results": [],
                "errors": {"workspace_resolution": sanitize_exception_message(exc), "error_code": errors["error_code"]},
                "warnings": ["Requested workspace could not be resolved."],
            }
        if isinstance(cue_ref, str):
            result = _normalize_cue_detail_result(self._get_single_cue_details(resolved_workspace_id, cue_ref, profile))
            self._attach_video_summaries(resolved_workspace_id, [result], profile)
            return result
        if not isinstance(cue_ref, list):
            raise ValueError("cue_ref must be a string or a list of strings")
        if not cue_ref:
            raise ValueError("cue_ref list must include at least one cue")
        if len(cue_ref) > MAX_BATCH_CUE_DETAILS:
            raise ValueError(f"cue_ref list can include at most {MAX_BATCH_CUE_DETAILS} cues")

        results: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        warnings: list[str] = _profile_warnings(profile, len(cue_ref))
        failed_count = 0
        for index, ref in enumerate(cue_ref):
            if not isinstance(ref, str) or not ref.strip():
                key = str(ref) if ref is not None else f"index:{index}"
                errors[key] = "cue_ref entries must be non-empty strings"
                results.append(
                    _failed_cue_detail_result(
                        resolved_workspace_id,
                        key,
                        profile,
                        "invalid_cue_ref",
                        "cue_ref entries must be non-empty strings",
                    )
                )
                failed_count += 1
                continue
            try:
                result = self._get_single_cue_details(
                    resolved_workspace_id,
                    ref,
                    profile,
                    include_read_coverage=False,
                )
                result = _normalize_cue_detail_result(result)
                results.append(result)
                if result.get("errors"):
                    errors[ref] = _batch_error_summary(result)
                    failed_count += 1
            except Exception as exc:
                errors[ref] = sanitize_exception_message(exc)
                failed_count += 1

        succeeded_count = len(cue_ref) - failed_count
        self._attach_video_summaries(resolved_workspace_id, results, profile)
        if failed_count:
            warnings.append("One or more cue detail reads failed; inspect errors for per-cue failures.")
        batch_result = {
            "ok": failed_count == 0 or succeeded_count > 0,
            "status": "error" if succeeded_count == 0 and failed_count else "partial" if failed_count else "ok",
            "partial": bool(failed_count and succeeded_count),
            "workspace_id": resolved_workspace_id,
            "requested_count": len(cue_ref),
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "profile": profile,
            "results": results,
            "errors": errors or None,
            "warnings": warnings,
        }
        _attach_read_coverage(batch_result, profile)
        return batch_result
