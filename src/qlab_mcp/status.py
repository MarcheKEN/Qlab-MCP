"""Read-only operational workspace status summaries."""

from __future__ import annotations

from typing import Any

from .allowlist import validate_value_keys
from .cues.profiles import _coerce_qlab_bool
from .cues.refs import _bounded_cue_refs_from_shallow
from .osc.addressing import _clean_workspace_id


WORKSPACE_STATUS_PROFILES = {"summary", "technical"}
DEFAULT_TIMECODE_TRIGGER_TEXTS = {"1:00:00:00", "01:00:00:00"}
DEFAULT_LIST_TIMECODE_SETTINGS = {
    "timecodeSyncMode": 0,
    "timecodeSMPTEFormat": 3,
    "timecodeStartBehavior": 4,
    "timecodeStopBehavior": 1,
    "timecodeFreewheelTime": 0.25,
    "timecodeLookbackTime": 0,
}
TIMECODE_CONFIG_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "timecodeTrigger",
    "timecodeTrigger/text",
    "timecodeSyncMode",
    "timecodeSMPTEFormat",
    "timecodeStartBehavior",
    "timecodeStopBehavior",
    "timecodeFreewheelTime",
    "timecodeLookbackTime",
    "timecodeString",
    "timecodeFormat",
    "timecodeMode",
    "timecodeFrameRate",
)


def _normalize_workspace_status_profile(profile: str) -> str:
    normalized = str(profile or "").strip().lower()
    if normalized not in WORKSPACE_STATUS_PROFILES:
        allowed = ", ".join(sorted(WORKSPACE_STATUS_PROFILES))
        raise ValueError(f"Unknown workspace status profile {profile!r}; use one of: {allowed}")
    return normalized


def _status_section(source: str, available: bool, **values: Any) -> dict[str, Any]:
    return {"source": source, "available": available, **values}


def _count_bool(cues: list[dict[str, Any]], key: str) -> int:
    return sum(1 for cue in cues if _coerce_qlab_bool(cue.get(key)) is True)


def _compact_error(exc: Exception) -> str:
    return str(exc)


def _numbers_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return left == right


class WorkspaceStatusMixin:
    def get_workspace_status(
        self,
        workspace_id: str,
        profile: str = "summary",
        include_timecode: bool = True,
        max_cues_scanned: int = 1000,
        sample_limit: int = 10,
    ) -> dict[str, Any]:
        if max_cues_scanned < 1:
            raise ValueError("max_cues_scanned must be 1 or greater")
        if max_cues_scanned > 5000:
            raise ValueError("max_cues_scanned must be 5000 or lower")
        if sample_limit < 0:
            raise ValueError("sample_limit must be 0 or greater")
        if sample_limit > 50:
            raise ValueError("sample_limit must be 50 or lower")

        resolved_workspace_id = _clean_workspace_id(workspace_id)
        normalized_profile = _normalize_workspace_status_profile(profile)
        sections: dict[str, Any] = {}
        errors: dict[str, str] = {}
        warnings: list[str] = []

        cue_scan = self._workspace_status_cue_scan(resolved_workspace_id, max_cues_scanned, sample_limit, errors)
        sections["warnings_summary"] = cue_scan["warnings_summary"]
        sections["trigger_summary"] = cue_scan["trigger_summary"]
        if include_timecode:
            sections["timecode_config"] = cue_scan["timecode_config"]
            sections["timecode_live_status"] = self._workspace_status_timecode_live(
                resolved_workspace_id,
                cue_scan["timecode_live_refs"],
                sample_limit,
                errors,
            )
        else:
            sections["timecode_config"] = _status_section(
                "derived_from_cues",
                False,
                status="skipped",
                notes=["include_timecode=false"],
            )
            sections["timecode_live_status"] = _status_section(
                "qlab_osc",
                False,
                status="skipped",
                notes=["include_timecode=false"],
            )

        sections["settings_summary"] = self._workspace_status_settings(
            resolved_workspace_id,
            normalized_profile,
            errors,
        )
        for section_name in ("logs", "artnet", "video_metrics"):
            sections[section_name] = _status_section(
                "not_exposed",
                False,
                notes=[
                    "No documented read-only QLab OSC endpoint was found for this Workspace Status section."
                ],
            )
        sections["info"] = _status_section(
            "qlab_osc",
            True,
            workspace_id=resolved_workspace_id,
            machine_id="redacted",
            notes=["Machine ID is intentionally not returned by default."],
        )

        if cue_scan["warnings_summary"].get("warning_count", 0) or cue_scan["warnings_summary"].get("broken_count", 0):
            warnings.append("Workspace has cues marked warning or broken in sampled read.")
        if cue_scan["scan_completeness"] != "complete":
            warnings.append("Workspace status cue-derived sections are partial; inspect limits and errors.")

        return {
            "workspace_id": resolved_workspace_id,
            "profile": normalized_profile,
            "sections": sections,
            "summary": {
                "available_sections": [name for name, section in sections.items() if section.get("available")],
                "unavailable_sections": [name for name, section in sections.items() if not section.get("available")],
                "cue_scan_completeness": cue_scan["scan_completeness"],
                "scanned_count": cue_scan["scanned_count"],
                "matched_timecode_config_count": sections["timecode_config"].get("configured_count", 0),
                "settings_error_count": len(sections["settings_summary"].get("errors") or {}),
            },
            "limits": {
                "max_cues_scanned": max_cues_scanned,
                "sample_limit": sample_limit,
            },
            "warnings": warnings,
            "errors": errors or None,
        }

    def _workspace_status_cue_scan(
        self,
        workspace_id: str,
        max_cues_scanned: int,
        sample_limit: int,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        try:
            bounded = _bounded_cue_refs_from_shallow(
                self,
                workspace_id,
                limit=max_cues_scanned,
                max_depth=None,
                cacheable=True,
                fallback_child_ids=True,
            )
        except Exception as exc:
            errors["cue_scan"] = _compact_error(exc)
            unavailable = _status_section(
                "derived_from_cues",
                False,
                status="error",
                notes=["Cue scan failed; cue-derived status sections unavailable."],
            )
            return {
                "warnings_summary": unavailable,
                "trigger_summary": unavailable,
            "timecode_config": unavailable,
            "timecode_refs": [],
            "timecode_live_refs": [],
            "scan_completeness": "failed",
            "scanned_count": 0,
            }

        if "root_read_error" in (bounded.get("truncation_reasons") or []) and not bounded.get("refs"):
            for key, value in (bounded.get("errors") or {}).items():
                errors[f"cue_scan.{key}"] = str(value)
            unavailable = _status_section(
                "derived_from_cues",
                False,
                status="error",
                notes=["Root cue-list read failed; cue-derived status sections unavailable."],
            )
            return {
                "warnings_summary": unavailable,
                "trigger_summary": unavailable,
                "timecode_config": unavailable,
                "timecode_refs": [],
                "timecode_live_refs": [],
                "scan_completeness": "failed",
                "scanned_count": 0,
            }

        for key, value in (bounded.get("errors") or {}).items():
            errors[f"cue_scan.{key}"] = str(value)
        keys = validate_value_keys(TIMECODE_CONFIG_KEYS + (
            "armed",
            "flagged",
            "isRunning",
            "isPaused",
            "isLoaded",
            "isBroken",
            "isWarning",
            "continueMode",
        ))
        cues: list[dict[str, Any]] = []
        for cue_ref in bounded.get("refs") or []:
            cue = dict(cue_ref.get("cue") or {})
            cue_id = cue_ref.get("uniqueID") or cue.get("uniqueID")
            if cue_id:
                try:
                    values = self.read_cue_values(
                        workspace_id,
                        str(cue_id),
                        keys,
                        cache_profile="inspector_safe",
                        cacheable=True,
                    )["values"]
                    if isinstance(values, dict):
                        cue.update(values)
                    else:
                        errors[f"cue_values.{cue_id}"] = "QLab valuesForKeys response must be an object"
                except Exception as exc:
                    errors[f"cue_values.{cue_id}"] = _compact_error(exc)
            cue.setdefault("uniqueID", cue_id)
            cue["continueModeLabel"] = self._continue_mode_label(cue.get("continueMode"))
            cues.append(cue)

        scan_completeness = "partial" if bounded.get("truncated") or bounded.get("errors") else "complete"
        warning_cues = [cue for cue in cues if _coerce_qlab_bool(cue.get("isWarning")) is True]
        broken_cues = [cue for cue in cues if _coerce_qlab_bool(cue.get("isBroken")) is True]
        flagged_cues = [cue for cue in cues if _coerce_qlab_bool(cue.get("flagged")) is True]
        timecode_configs = [
            self._timecode_config_item(cue)
            for cue in cues
            if self._cue_has_timecode_config(cue)
        ]
        default_timecode_values_seen = any(self._cue_has_default_timecode_values(cue) for cue in cues)
        default_timecode_values_not_counted = any(
            self._cue_has_default_timecode_values(cue) and not self._cue_has_timecode_config(cue)
            for cue in cues
        )

        return {
            "warnings_summary": _status_section(
                "derived_from_cues",
                True,
                status=scan_completeness,
                scanned_count=len(cues),
                warning_count=len(warning_cues),
                broken_count=len(broken_cues),
                flagged_count=len(flagged_cues),
                running_count=_count_bool(cues, "isRunning"),
                paused_count=_count_bool(cues, "isPaused"),
                sample_warning_cues=[self._cue_identity(cue) for cue in warning_cues[:sample_limit]],
                sample_broken_cues=[self._cue_identity(cue) for cue in broken_cues[:sample_limit]],
                notes=bounded.get("truncation_reasons") or [],
            ),
            "trigger_summary": _status_section(
                "derived_from_cues",
                True,
                status=scan_completeness,
                timecode_trigger_count=sum(1 for cue in cues if self._cue_has_non_default_timecode_trigger(cue)),
                auto_continue_count=sum(1 for cue in cues if cue.get("continueModeLabel") == "auto_continue"),
                auto_follow_count=sum(1 for cue in cues if cue.get("continueModeLabel") == "auto_follow"),
                default_timecode_values_seen=default_timecode_values_seen,
                default_timecode_values_not_counted=default_timecode_values_not_counted,
                general_trigger_status="not_exposed",
                notes=[
                    "General trigger summary is not exposed as one documented OSC status endpoint; "
                    "this section reports safely readable cue fields."
                ],
            ),
            "timecode_config": _status_section(
                "derived_from_cues",
                bool(timecode_configs),
                status=scan_completeness,
                configured_count=len(timecode_configs),
                sample=timecode_configs[:sample_limit],
                default_timecode_values_seen=default_timecode_values_seen,
                default_timecode_values_not_counted=default_timecode_values_not_counted,
                notes=[] if timecode_configs else ["No timecode cue/list/cart config was found in sampled cues."],
            ),
            "timecode_refs": [item["uniqueID"] for item in timecode_configs if item.get("uniqueID")],
            "timecode_live_refs": [
                item["uniqueID"]
                for item in timecode_configs
                if item.get("uniqueID") and str(item.get("type") or "").casefold() in {"cue list", "cue cart", "cart"}
            ],
            "scan_completeness": scan_completeness,
            "scanned_count": len(cues),
        }

    def _workspace_status_settings(
        self,
        workspace_id: str,
        profile: str,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        try:
            result = self.get_workspace_settings(
                workspace_id,
                mode="summary",
                sections=["audio", "video", "network", "midi", "light", "general"],
                profile="safe",
            )
        except Exception as exc:
            errors["settings_summary"] = _compact_error(exc)
            return _status_section(
                "derived_from_settings",
                False,
                status="error",
                notes=["Workspace settings summary failed."],
            )

        for key, value in (result.get("errors") or {}).items():
            errors[f"settings.{key}"] = str(value)
        summary = dict(result.get("summary") or {})
        if profile == "summary":
            return _status_section(
                "derived_from_settings",
                True,
                status="available",
                summary=summary,
                errors=result.get("errors") or None,
                notes=result.get("warnings") or [],
            )
        return _status_section(
            "derived_from_settings",
            True,
            status="available",
            summary=summary,
            sections=result.get("sections") or {},
            errors=result.get("errors") or None,
            notes=result.get("warnings") or [],
        )

    def _workspace_status_timecode_live(
        self,
        workspace_id: str,
        cue_refs: list[str],
        sample_limit: int,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        if not cue_refs:
            return _status_section(
                "not_running_or_not_exposed",
                False,
                status="unavailable",
                notes=[
                    "QLab exposes currentTimecode/text per cue list or cue cart; no candidate was found in sampled cues."
                ],
            )

        live: list[dict[str, Any]] = []
        unavailable_count = 0
        for cue_ref in cue_refs[:sample_limit]:
            try:
                value = self.read_cue_property(workspace_id, cue_ref, "currentTimecode/text")["value"]
                live.append({"cue_ref": cue_ref, "currentTimecode/text": value})
            except Exception:
                unavailable_count += 1

        return _status_section(
            "qlab_osc" if live else "not_running_or_not_exposed",
            bool(live),
            status="available" if live else "unavailable",
            sample=live,
            notes=[
                "Live timecode is read from documented per-cue currentTimecode/text, not a global Workspace Status endpoint.",
                *(
                    [f"currentTimecode/text unavailable for {unavailable_count} candidate cue list/cart item(s)."]
                    if unavailable_count
                    else []
                ),
            ],
        )

    def _cue_has_timecode_config(self, cue: dict[str, Any]) -> bool:
        cue_type = str(cue.get("type") or "").casefold()
        if cue_type == "timecode":
            return True
        if self._cue_has_non_default_timecode_trigger(cue):
            return True
        if cue_type in {"cue list", "cue cart", "cart"}:
            return any(
                key in cue and not _numbers_equal(cue.get(key), default_value)
                for key, default_value in DEFAULT_LIST_TIMECODE_SETTINGS.items()
            )
        return False

    def _cue_has_default_timecode_values(self, cue: dict[str, Any]) -> bool:
        if self._timecode_trigger_is_default(cue):
            return True
        return any(
            key in cue and _numbers_equal(cue.get(key), default_value)
            for key, default_value in DEFAULT_LIST_TIMECODE_SETTINGS.items()
        )

    def _cue_has_non_default_timecode_trigger(self, cue: dict[str, Any]) -> bool:
        text = cue.get("timecodeTrigger/text")
        if isinstance(text, str) and text.strip():
            return text.strip() not in DEFAULT_TIMECODE_TRIGGER_TEXTS
        trigger = cue.get("timecodeTrigger")
        if isinstance(trigger, dict):
            return not self._timecode_trigger_is_default(cue)
        return trigger not in (None, "", False)

    def _timecode_trigger_is_default(self, cue: dict[str, Any]) -> bool:
        text = cue.get("timecodeTrigger/text")
        if isinstance(text, str) and text.strip() in DEFAULT_TIMECODE_TRIGGER_TEXTS:
            return True
        trigger = cue.get("timecodeTrigger")
        if isinstance(trigger, dict):
            parts = {
                "hours": 1,
                "minutes": 0,
                "seconds": 0,
                "frames": 0,
                "bits": 0,
            }
            return all(_numbers_equal(trigger.get(key), expected) for key, expected in parts.items())
        return False

    def _timecode_config_item(self, cue: dict[str, Any]) -> dict[str, Any]:
        return {key: cue.get(key) for key in TIMECODE_CONFIG_KEYS if key in cue and cue.get(key) is not None}

    def _cue_identity(self, cue: dict[str, Any]) -> dict[str, Any]:
        return {
            key: cue.get(key)
            for key in ("uniqueID", "number", "name", "displayName", "type")
            if cue.get(key) is not None
        }

    def _continue_mode_label(self, value: Any) -> str:
        if isinstance(value, bool) or value in (None, ""):
            return "unknown"
        if isinstance(value, int):
            return {0: "do_not_continue", 1: "auto_continue", 2: "auto_follow"}.get(value, "unknown")
        if isinstance(value, float) and value.is_integer():
            return {0: "do_not_continue", 1: "auto_continue", 2: "auto_follow"}.get(int(value), "unknown")
        normalized = str(value).strip().casefold().replace("-", "_").replace(" ", "_")
        if normalized in {"0", "do_not_continue", "manual", "none"}:
            return "do_not_continue"
        if normalized in {"1", "auto_continue", "autocontinue"}:
            return "auto_continue"
        if normalized in {"2", "auto_follow", "autofollow"}:
            return "auto_follow"
        return "unknown"
