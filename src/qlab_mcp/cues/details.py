"""Cue detail profiles and deep cue inspection."""

from __future__ import annotations

from typing import Any

from ..allowlist import properties_for_profile, validate_value_keys
from ..errors import QLabReplyError
from ..osc.addressing import _clean_cue_ref, _clean_workspace_id
from ..write.registry import editable_update_capabilities
from .profiles import (
    _auto_type_specific_keys,
    _build_auto_sections,
    _derive_profile_fields,
    _empty_auto_sections,
    _is_active_cue_ref,
)


MAX_VALUES_FOR_KEYS = 100


def _chunk_keys(keys: list[str] | tuple[str, ...], size: int = MAX_VALUES_FOR_KEYS) -> list[list[str]]:
    return [list(keys[index : index + size]) for index in range(0, len(keys), size)]


class CueDetailsMixin:
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
                errors[chunk_error_key] = str(exc)

            for property_path in normalized_keys:
                try:
                    values[property_path] = self.read_cue_property(workspace_id, cue_ref, property_path)["value"]
                except Exception as property_exc:
                    errors[property_path] = str(property_exc)
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
        values = _derive_profile_fields("auto", values)

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
            values = _derive_profile_fields("auto", values)

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
        if profile.strip().lower() == "auto":
            result["sections"] = _empty_auto_sections()
        return result

    def get_cue_details(self, workspace_id: str, cue_ref: str, profile: str = "auto") -> dict[str, Any]:
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
            values = self._read_cue_values_with_fallback(workspace_id, cue_ref, keys, errors, profile=profile)
        values = _derive_profile_fields(profile, values)

        result: dict[str, Any] = {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "profile": profile,
            "cue_type": values.get("type"),
            "properties": values,
        }
        if errors:
            result["errors"] = errors
        return result
