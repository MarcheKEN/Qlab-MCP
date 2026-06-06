"""Workspace settings overview and detail readers."""

from __future__ import annotations

from typing import Any

from ..osc.addressing import _clean_workspace_id, _workspace_address
from ..errors import OscTimeoutError
from .redaction import _record_redactions, _redact_payload
from .summarizers import (
    _basic_item_summary,
    _collection_items,
    _first_present,
    _select_setting_item,
    _summarize_audio_map,
    _summarize_audio_map_detail,
    _summarize_audio_patch,
    _summarize_light_patch,
    _summarize_light_patch_detail,
    _summarize_midi_patch,
    _summarize_network_patch,
    _summarize_setting_detail_item,
    _summarize_video_route,
    _summarize_video_stage,
    _summarize_video_stage_detail,
)


WORKSPACE_SETTINGS_SECTIONS = ("audio", "video", "network", "midi", "light", "general")
WORKSPACE_SETTINGS_MODES = {"summary", "details"}
WORKSPACE_SETTINGS_PROFILES = {"safe", "technical", "exhaustive"}
SUMMARY_PROFILE_WARNING = (
    "Summary mode stays compact and uses safe summaries; use mode='details' with profile='technical' "
    "or profile='exhaustive' for deeper read-only payloads."
)
TECHNICAL_PROFILE_WARNING = (
    "Technical profile can include low-level infrastructure such as IPs, ports, interfaces, devices, routes, "
    "regions, and raw payloads. Passcodes and credentials remain redacted."
)
EXHAUSTIVE_PROFILE_WARNING = (
    "Exhaustive profile returns the deepest allowlisted read-only workspace settings data and may be large. "
    "Passcodes and credentials remain redacted."
)
TCP_FALLBACK_MEANING = (
    "TCP was used to retrieve a large response after UDP could not return it; "
    "this does not imply output failure, missing controllers, or degraded physical playback."
)
WORKSPACE_SETTING_DETAIL_KINDS = {
    "all",
    "output_patch",
    "input_patch",
    "audio_map",
    "route",
    "stage",
    "video_input_patch",
    "network_patch",
    "midi_patch",
    "light_patch",
}

def _normalize_workspace_settings_mode(mode: str) -> str:
    normalized = str(mode or "").strip().lower()
    if normalized not in WORKSPACE_SETTINGS_MODES:
        allowed = ", ".join(sorted(WORKSPACE_SETTINGS_MODES))
        raise ValueError(f"Unknown workspace settings mode {mode!r}; use one of: {allowed}")
    return normalized

def _normalize_workspace_settings_profile(profile: str) -> str:
    normalized = str(profile or "").strip().lower()
    if normalized not in WORKSPACE_SETTINGS_PROFILES:
        allowed = ", ".join(sorted(WORKSPACE_SETTINGS_PROFILES))
        raise ValueError(f"Unknown workspace settings profile {profile!r}; use one of: {allowed}")
    return normalized


def _settings_workspace_resolution_error(
    workspace_id: str,
    mode: str,
    profile: str,
    status: str,
    message: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "status": status,
        "error_code": status,
        "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
        "workspace_id": workspace_id,
        "mode": mode,
        "profile": profile,
        "requested_profile": profile,
        "sections": {},
        "summary": {
            "requested_sections": [],
            "returned_sections": [],
            "section_count": 0,
            "error_count": 1,
            "redaction_count": 0,
        },
        "available_detail_requests": [],
        "requested_count": 0 if mode == "details" else None,
        "succeeded_count": 0 if mode == "details" else None,
        "failed_count": 0 if mode == "details" else None,
        "results": [],
        "redactions": [],
        "errors": {"workspace_resolution": message},
        "warnings": ["Requested workspace could not be resolved."],
    }

def _normalize_workspace_settings_sections(sections: list[str] | tuple[str, ...] | str | None) -> list[str]:
    if sections is None:
        return list(WORKSPACE_SETTINGS_SECTIONS)
    if isinstance(sections, str):
        raw_sections = [item.strip() for item in sections.split(",")]
    else:
        raw_sections = [str(item).strip() for item in sections]

    normalized_sections: list[str] = []
    for item in raw_sections:
        if not item:
            continue
        normalized = item.lower()
        if normalized not in WORKSPACE_SETTINGS_SECTIONS:
            allowed = ", ".join(WORKSPACE_SETTINGS_SECTIONS)
            raise ValueError(f"Unknown workspace settings section {item!r}; use one of: {allowed}")
        if normalized not in normalized_sections:
            normalized_sections.append(normalized)
    return normalized_sections or list(WORKSPACE_SETTINGS_SECTIONS)

def _normalize_workspace_setting_detail_kind(kind: str | None, section: str) -> str:
    if kind is None:
        return "light_patch" if section == "light" else "all"
    normalized = str(kind or "").strip().lower()
    if normalized not in WORKSPACE_SETTING_DETAIL_KINDS:
        allowed = ", ".join(sorted(WORKSPACE_SETTING_DETAIL_KINDS))
        raise ValueError(f"Unknown workspace setting detail kind {kind!r}; use one of: {allowed}")
    return normalized

def _detail_request_ref(item: dict[str, Any]) -> Any:
    return _first_present(item, ("name", "displayName", "uniqueID", "id", "patchID", "routeID", "stageID", "_key"))

def _detail_request(section: str, kind: str, item: dict[str, Any] | None = None) -> dict[str, Any]:
    request: dict[str, Any] = {"section": section, "kind": kind, "ref": None}
    if item:
        ref = _detail_request_ref(item)
        if ref is not None:
            request["ref"] = str(ref)
        for output_key, keys in {
            "name": ("name", "displayName", "patchName", "routeName", "stageName"),
            "uniqueID": ("uniqueID", "id", "patchID", "routeID", "stageID"),
        }.items():
            value = _first_present(item, keys)
            if value is not None:
                request[output_key] = value
    return request

def _available_detail_requests(sections: dict[str, Any]) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    audio = sections.get("audio")
    if isinstance(audio, dict):
        for item in audio.get("output_patches") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("audio", "output_patch", item))
        for item in audio.get("input_patches") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("audio", "input_patch", item))
        for item in audio.get("audio_maps") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("audio", "audio_map", item))
    video = sections.get("video")
    if isinstance(video, dict):
        for item in video.get("input_patches") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("video", "video_input_patch", item))
        for item in video.get("routes") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("video", "route", item))
        for item in video.get("stages") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("video", "stage", item))
    network = sections.get("network")
    if isinstance(network, dict):
        for item in network.get("patches") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("network", "network_patch", item))
    midi = sections.get("midi")
    if isinstance(midi, dict):
        for item in midi.get("patches") or []:
            if isinstance(item, dict):
                requests.append(_detail_request("midi", "midi_patch", item))
    if "light" in sections:
        requests.append(_detail_request("light", "light_patch"))
    if "general" in sections:
        requests.append(_detail_request("general", "all"))
    return requests

def _raw_detail_requests(requests: Any) -> list[Any]:
    if requests is None:
        raise ValueError("requests is required when mode='details'")
    if isinstance(requests, dict):
        return [requests]
    if isinstance(requests, (list, tuple)):
        if not requests:
            raise ValueError("requests must include at least one detail request when mode='details'")
        return list(requests)
    raise ValueError("requests must be a detail request object or a list of request objects")

def _normalize_detail_request(raw_request: Any) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("detail request must be an object with section, kind, and optional ref")
    section = _normalize_workspace_settings_sections([raw_request.get("section")])[0]
    kind = _normalize_workspace_setting_detail_kind(raw_request.get("kind"), section)
    raw_ref = raw_request.get("ref")
    ref = None if raw_ref in (None, "") else str(raw_ref)
    return {"section": section, "kind": kind, "ref": ref}

def _profile_warnings(profile: str) -> list[str]:
    if profile == "technical":
        return [TECHNICAL_PROFILE_WARNING]
    if profile == "exhaustive":
        return [EXHAUSTIVE_PROFILE_WARNING]
    return []


class WorkspaceSettingsMixin:
    def _read_workspace_setting(
        self,
        workspace_id: str,
        command: str,
        errors: dict[str, str],
        error_key: str,
    ) -> Any:
        address = _workspace_address(workspace_id, f"settings/{command}")
        try:
            return self.client.request(address, workspace_id=workspace_id).data
        except OscTimeoutError as exc:
            errors[error_key] = str(exc)
            return None
        except Exception as exc:
            errors[error_key] = str(exc)
            return None

    def _read_light_patch_setting(
        self,
        workspace_id: str,
        errors: dict[str, str],
    ) -> tuple[Any, str | None]:
        address = _workspace_address(workspace_id, "settings/light/patch")
        try:
            return self.client.request(address, workspace_id=workspace_id).data, "udp"
        except OscTimeoutError as udp_exc:
            try:
                return self.client.request_tcp(address, workspace_id=workspace_id).data, "tcp_fallback"
            except Exception as tcp_exc:
                errors["light.patch"] = (
                    f"{udp_exc}; TCP fallback also failed for large light patch reply: {tcp_exc}"
                )
                return None, None
        except Exception as exc:
            errors["light.patch"] = str(exc)
            return None, None

    def _workspace_settings_audio(
        self,
        workspace_id: str,
        profile: str,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        output_patches = self._read_workspace_setting(workspace_id, "audio/patchList", errors, "audio.patchList")
        input_patches = self._read_workspace_setting(workspace_id, "mic/patchList", errors, "audio.inputPatchList")
        cue_output_counts = self._read_workspace_setting(
            workspace_id,
            "audio/cueOutputChannelCounts",
            errors,
            "audio.cueOutputChannelCounts",
        )
        output_channel_names = self._read_workspace_setting(
            workspace_id,
            "audio/outputChannelNames",
            errors,
            "audio.outputChannelNames",
        )
        audio_maps = self._read_workspace_setting(workspace_id, "audio/maps", errors, "audio.maps")

        if profile in {"technical", "exhaustive"}:
            return {
                "output_patches": _redact_payload(
                    output_patches,
                    section="audio",
                    profile=profile,
                    redactions=redactions,
                    path="audio.output_patches",
                ),
                "input_patches": _redact_payload(
                    input_patches,
                    section="audio",
                    profile=profile,
                    redactions=redactions,
                    path="audio.input_patches",
                ),
                "cue_output_channel_counts": cue_output_counts,
                "output_channel_names": output_channel_names,
                "audio_maps": _redact_payload(
                    audio_maps,
                    section="audio",
                    profile=profile,
                    redactions=redactions,
                    path="audio.audio_maps",
                ),
            }

        _record_redactions(output_patches, "audio", profile, redactions, "audio.output_patches")
        _record_redactions(input_patches, "audio", profile, redactions, "audio.input_patches")
        _record_redactions(audio_maps, "audio", profile, redactions, "audio.audio_maps")
        return {
            "output_patches": [_summarize_audio_patch(item) for item in _collection_items(output_patches)],
            "input_patches": [_summarize_audio_patch(item) for item in _collection_items(input_patches)],
            "cue_output_channel_counts": cue_output_counts,
            "output_channel_names": output_channel_names,
            "audio_maps": [_summarize_audio_map(item) for item in _collection_items(audio_maps)],
        }

    def _workspace_settings_video(
        self,
        workspace_id: str,
        profile: str,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        input_patches = self._read_workspace_setting(workspace_id, "video/inputPatchList", errors, "video.inputPatchList")
        routes = self._read_workspace_setting(workspace_id, "video/routes", errors, "video.routes")
        stages = self._read_workspace_setting(workspace_id, "video/stages", errors, "video.stages")
        stage_regions: dict[str, Any] = {}
        for stage in _collection_items(stages):
            if not isinstance(stage, dict):
                continue
            stage_id = _first_present(stage, ("uniqueID", "id", "stageID"))
            stage_name = _first_present(stage, ("name", "stageName", "displayName"))
            if stage_id:
                command = f"video/stageID/{stage_id}/regions"
                error_key = f"video.stageID.{stage_id}.regions"
                region_key = str(stage_id)
            elif stage_name:
                command = f"video/stage/{stage_name}/regions"
                error_key = f"video.stage.{stage_name}.regions"
                region_key = str(stage_name)
            else:
                continue
            stage_regions[region_key] = self._read_workspace_setting(workspace_id, command, errors, error_key)

        if profile in {"technical", "exhaustive"}:
            return {
                "input_patches": _redact_payload(
                    input_patches,
                    section="video",
                    profile=profile,
                    redactions=redactions,
                    path="video.input_patches",
                ),
                "routes": _redact_payload(
                    routes,
                    section="video",
                    profile=profile,
                    redactions=redactions,
                    path="video.routes",
                ),
                "stages": _redact_payload(
                    stages,
                    section="video",
                    profile=profile,
                    redactions=redactions,
                    path="video.stages",
                ),
                "stage_regions": _redact_payload(
                    stage_regions,
                    section="video",
                    profile=profile,
                    redactions=redactions,
                    path="video.stage_regions",
                ),
            }

        def region_data_for_stage(stage: Any) -> Any | None:
            if not isinstance(stage, dict):
                return None
            region_key = _first_present(stage, ("uniqueID", "id", "stageID", "name", "stageName", "displayName"))
            return stage_regions.get(str(region_key)) if region_key is not None else None

        _record_redactions(input_patches, "video", profile, redactions, "video.input_patches")
        _record_redactions(routes, "video", profile, redactions, "video.routes")
        _record_redactions(stages, "video", profile, redactions, "video.stages")
        _record_redactions(stage_regions, "video", profile, redactions, "video.stage_regions")
        return {
            "input_patches": [_basic_item_summary(item) for item in _collection_items(input_patches)],
            "routes": [_summarize_video_route(item) for item in _collection_items(routes)],
            "stages": [
                _summarize_video_stage(stage, region_data_for_stage(stage))
                for stage in _collection_items(stages)
            ],
        }

    def _workspace_settings_network(
        self,
        workspace_id: str,
        profile: str,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        patches = self._read_workspace_setting(workspace_id, "network/patchList", errors, "network.patchList")
        if profile in {"technical", "exhaustive"}:
            return {
                "patches": _redact_payload(
                    patches,
                    section="network",
                    profile=profile,
                    redactions=redactions,
                    path="network.patches",
                )
            }
        _record_redactions(patches, "network", profile, redactions, "network.patches")
        return {"patches": [_summarize_network_patch(item) for item in _collection_items(patches)]}

    def _workspace_settings_midi(
        self,
        workspace_id: str,
        profile: str,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        patches = self._read_workspace_setting(workspace_id, "midi/patchList", errors, "midi.patchList")
        if profile in {"technical", "exhaustive"}:
            return {
                "patches": _redact_payload(
                    patches,
                    section="midi",
                    profile=profile,
                    redactions=redactions,
                    path="midi.patches",
                )
            }
        _record_redactions(patches, "midi", profile, redactions, "midi.patches")
        return {"patches": [_summarize_midi_patch(item) for item in _collection_items(patches)]}

    def _workspace_settings_light(
        self,
        workspace_id: str,
        profile: str,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        if profile == "safe":
            return {
                "summary": {
                    "details_available": True,
                    "patch_read": "skipped",
                    "message": "Use qlab_get_workspace_setting_details with section='light' and kind='light_patch' to inspect the light patch.",
                }
            }
        patch, read_transport = self._read_light_patch_setting(workspace_id, errors)
        return self._workspace_settings_light_patch(patch, profile, redactions, read_transport)

    def _workspace_settings_light_patch(
        self,
        patch: Any,
        profile: str,
        redactions: list[dict[str, str]],
        read_transport: str | None = None,
    ) -> dict[str, Any]:
        if profile == "safe":
            detail = _summarize_light_patch_detail(patch)
            if read_transport:
                detail["summary"]["read_transport"] = read_transport
                if read_transport == "tcp_fallback":
                    detail["summary"]["read_transport_meaning"] = TCP_FALLBACK_MEANING
            return detail

        summary = _summarize_light_patch(patch)
        if read_transport:
            summary["read_transport"] = read_transport
            if read_transport == "tcp_fallback":
                summary["read_transport_meaning"] = TCP_FALLBACK_MEANING
        return {
            "summary": summary,
            "patch": _redact_payload(
                patch,
                section="light",
                profile=profile,
                redactions=redactions,
                path="light.patch",
            ),
        }

    def _workspace_settings_general(
        self,
        workspace_id: str,
        errors: dict[str, str],
    ) -> dict[str, Any]:
        return {
            "minGoTime": self._read_workspace_setting(workspace_id, "general/minGoTime", errors, "general.minGoTime"),
            "selectionIsPlayhead": self._read_workspace_setting(
                workspace_id,
                "general/selectionIsPlayhead",
                errors,
                "general.selectionIsPlayhead",
            ),
        }

    def _get_workspace_settings_summary(
        self,
        workspace_id: str,
        sections: list[str] | tuple[str, ...] | str | None = None,
        profile: str = "safe",
    ) -> dict[str, Any]:
        resolved_workspace_id = _clean_workspace_id(workspace_id)
        requested_profile = _normalize_workspace_settings_profile(profile)
        normalized_profile = "safe"
        normalized_sections = _normalize_workspace_settings_sections(sections)
        redactions: list[dict[str, str]] = []
        errors: dict[str, str] = {}
        warnings: list[str] = []
        result_sections: dict[str, Any] = {}
        if requested_profile != "safe":
            warnings.append(SUMMARY_PROFILE_WARNING)

        if "audio" in normalized_sections:
            result_sections["audio"] = self._workspace_settings_audio(
                resolved_workspace_id,
                normalized_profile,
                redactions,
                errors,
            )
        if "video" in normalized_sections:
            result_sections["video"] = self._workspace_settings_video(
                resolved_workspace_id,
                normalized_profile,
                redactions,
                errors,
            )
        if "network" in normalized_sections:
            result_sections["network"] = self._workspace_settings_network(
                resolved_workspace_id,
                normalized_profile,
                redactions,
                errors,
            )
        if "midi" in normalized_sections:
            result_sections["midi"] = self._workspace_settings_midi(
                resolved_workspace_id,
                normalized_profile,
                redactions,
                errors,
            )
        if "light" in normalized_sections:
            result_sections["light"] = self._workspace_settings_light(
                resolved_workspace_id,
                normalized_profile,
                redactions,
                errors,
            )
        if "general" in normalized_sections:
            result_sections["general"] = self._workspace_settings_general(resolved_workspace_id, errors)

        summary = {
            "requested_sections": normalized_sections,
            "returned_sections": list(result_sections),
            "section_count": len(result_sections),
            "error_count": len(errors),
            "redaction_count": len(redactions),
        }
        if "audio" in result_sections:
            audio = result_sections["audio"]
            summary["audio_output_patch_count"] = len(audio.get("output_patches") or [])
            summary["audio_input_patch_count"] = len(audio.get("input_patches") or [])
            summary["audio_map_count"] = len(audio.get("audio_maps") or [])
        if "video" in result_sections:
            video = result_sections["video"]
            summary["video_route_count"] = len(video.get("routes") or [])
            summary["video_stage_count"] = len(video.get("stages") or [])
            summary["video_input_patch_count"] = len(video.get("input_patches") or [])
        if "network" in result_sections:
            summary["network_patch_count"] = len(result_sections["network"].get("patches") or [])
        if "midi" in result_sections:
            summary["midi_patch_count"] = len(result_sections["midi"].get("patches") or [])

        return {
            "workspace_id": resolved_workspace_id,
            "mode": "summary",
            "profile": normalized_profile,
            "requested_profile": requested_profile,
            "sections": result_sections,
            "summary": summary,
            "available_detail_requests": _available_detail_requests(result_sections),
            "redactions": redactions,
            "errors": errors or None,
            "warnings": warnings,
        }

    def _settings_details_result(
        self,
        workspace_id: str,
        section: str,
        kind: str,
        ref: str | None,
        profile: str,
        details: Any = None,
        choices: list[dict[str, Any]] | None = None,
        redactions: list[dict[str, str]] | None = None,
        errors: dict[str, str] | None = None,
        message: str | None = None,
    ) -> dict[str, Any]:
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "section": section,
            "kind": kind,
            "ref": ref,
            "profile": profile,
            "details": details,
            "choices": choices or [],
            "redactions": redactions or [],
            "errors": errors or None,
            "message": message,
        }

    def _setting_details_from_collection(
        self,
        workspace_id: str,
        section: str,
        kind: str,
        ref: str | None,
        profile: str,
        items: Any,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        item_list = _collection_items(items)
        selected, choices, message = _select_setting_item(item_list, ref)
        if selected is None:
            return self._settings_details_result(
                workspace_id,
                section,
                kind,
                ref,
                profile,
                details=None,
                choices=choices,
                redactions=redactions,
                errors=errors,
                message=message,
            )
        if profile == "safe":
            _record_redactions(selected, section, profile, redactions, f"{section}.{kind}")
            details = _summarize_setting_detail_item(section, kind, selected)
        else:
            details = _redact_payload(
                selected,
                section=section,
                profile=profile,
                redactions=redactions,
                path=f"{section}.{kind}",
            )
        return self._settings_details_result(
            workspace_id,
            section,
            kind,
            ref,
            profile,
            details=details,
            choices=[],
            redactions=redactions,
            errors=errors,
            message=None,
        )

    def _get_workspace_setting_details_single(
        self,
        workspace_id: str,
        section: str,
        kind: str | None = None,
        ref: str | None = None,
        profile: str = "safe",
    ) -> dict[str, Any]:
        resolved_workspace_id = _clean_workspace_id(workspace_id)
        normalized_sections = _normalize_workspace_settings_sections([section])
        normalized_section = normalized_sections[0]
        normalized_kind = _normalize_workspace_setting_detail_kind(kind, normalized_section)
        normalized_profile = _normalize_workspace_settings_profile(profile)
        redactions: list[dict[str, str]] = []
        errors: dict[str, str] = {}

        if normalized_kind == "all":
            if normalized_section == "audio":
                details = self._workspace_settings_audio(resolved_workspace_id, normalized_profile, redactions, errors)
            elif normalized_section == "video":
                details = self._workspace_settings_video(resolved_workspace_id, normalized_profile, redactions, errors)
            elif normalized_section == "network":
                details = self._workspace_settings_network(resolved_workspace_id, normalized_profile, redactions, errors)
            elif normalized_section == "midi":
                details = self._workspace_settings_midi(resolved_workspace_id, normalized_profile, redactions, errors)
            elif normalized_section == "light":
                patch, read_transport = self._read_light_patch_setting(resolved_workspace_id, errors)
                details = self._workspace_settings_light_patch(patch, normalized_profile, redactions, read_transport)
            else:
                details = self._workspace_settings_general(resolved_workspace_id, errors)
            return self._settings_details_result(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                details=details,
                redactions=redactions,
                errors=errors,
            )

        if normalized_section == "audio":
            if normalized_kind == "output_patch":
                items = self._read_workspace_setting(resolved_workspace_id, "audio/patchList", errors, "audio.patchList")
            elif normalized_kind == "input_patch":
                items = self._read_workspace_setting(resolved_workspace_id, "mic/patchList", errors, "audio.inputPatchList")
            elif normalized_kind == "audio_map":
                items = self._read_workspace_setting(resolved_workspace_id, "audio/maps", errors, "audio.maps")
                item_list = _collection_items(items)
                selected, choices, message = _select_setting_item(item_list, ref)
                if selected is None:
                    return self._settings_details_result(
                        resolved_workspace_id,
                        normalized_section,
                        normalized_kind,
                        ref,
                        normalized_profile,
                        details=None,
                        choices=choices,
                        redactions=redactions,
                        errors=errors,
                        message=message,
                    )
                if normalized_profile == "safe":
                    _record_redactions(
                        selected,
                        normalized_section,
                        normalized_profile,
                        redactions,
                        f"{normalized_section}.{normalized_kind}",
                    )
                    return self._settings_details_result(
                        resolved_workspace_id,
                        normalized_section,
                        normalized_kind,
                        ref,
                        normalized_profile,
                        details=_summarize_audio_map_detail(selected),
                        choices=[],
                        redactions=redactions,
                        errors=errors,
                        message=None,
                    )
                map_id = _first_present(selected, ("uniqueID", "id", "mapID")) if isinstance(selected, dict) else None
                map_name = _first_present(selected, ("name", "displayName", "_key")) if isinstance(selected, dict) else None
                if map_id:
                    detail_payload = self._read_workspace_setting(
                        resolved_workspace_id,
                        f"audio/mapID/{map_id}",
                        errors,
                        f"audio.mapID.{map_id}",
                    )
                elif map_name:
                    detail_payload = self._read_workspace_setting(
                        resolved_workspace_id,
                        f"audio/map/{map_name}",
                        errors,
                        f"audio.map.{map_name}",
                    )
                else:
                    detail_payload = selected
                if detail_payload is None:
                    detail_payload = selected
                return self._settings_details_result(
                    resolved_workspace_id,
                    normalized_section,
                    normalized_kind,
                    ref,
                    normalized_profile,
                    details=_redact_payload(
                        detail_payload,
                        section=normalized_section,
                        profile=normalized_profile,
                        redactions=redactions,
                        path=f"{normalized_section}.{normalized_kind}",
                    ),
                    choices=[],
                    redactions=redactions,
                    errors=errors,
                    message=None,
                )
            else:
                raise ValueError("Audio details support kind output_patch, input_patch, audio_map, or all")
            return self._setting_details_from_collection(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                items,
                redactions,
                errors,
            )

        if normalized_section == "video":
            if normalized_kind == "route":
                items = self._read_workspace_setting(resolved_workspace_id, "video/routes", errors, "video.routes")
                return self._setting_details_from_collection(
                    resolved_workspace_id,
                    normalized_section,
                    normalized_kind,
                    ref,
                    normalized_profile,
                    items,
                    redactions,
                    errors,
                )
            if normalized_kind == "video_input_patch":
                items = self._read_workspace_setting(
                    resolved_workspace_id,
                    "video/inputPatchList",
                    errors,
                    "video.inputPatchList",
                )
                return self._setting_details_from_collection(
                    resolved_workspace_id,
                    normalized_section,
                    normalized_kind,
                    ref,
                    normalized_profile,
                    items,
                    redactions,
                    errors,
                )
            if normalized_kind != "stage":
                raise ValueError("Video details support kind stage, route, video_input_patch, or all")

            stages = self._read_workspace_setting(resolved_workspace_id, "video/stages", errors, "video.stages")
            stage_items = _collection_items(stages)
            selected, choices, message = _select_setting_item(stage_items, ref)
            if selected is None:
                return self._settings_details_result(
                    resolved_workspace_id,
                    normalized_section,
                    normalized_kind,
                    ref,
                    normalized_profile,
                    details=None,
                    choices=choices,
                    redactions=redactions,
                    errors=errors,
                    message=message,
                )
            stage_id = _first_present(selected, ("uniqueID", "id", "stageID")) if isinstance(selected, dict) else None
            stage_name = _first_present(selected, ("name", "stageName", "displayName")) if isinstance(selected, dict) else None
            if stage_id:
                regions = self._read_workspace_setting(
                    resolved_workspace_id,
                    f"video/stageID/{stage_id}/regions",
                    errors,
                    f"video.stageID.{stage_id}.regions",
                )
            elif stage_name:
                regions = self._read_workspace_setting(
                    resolved_workspace_id,
                    f"video/stage/{stage_name}/regions",
                    errors,
                    f"video.stage.{stage_name}.regions",
                )
            else:
                regions = None
            details = {
                "stage": selected,
                "regions": regions,
            }
            if normalized_profile == "safe":
                _record_redactions(
                    details,
                    normalized_section,
                    normalized_profile,
                    redactions,
                    "video.stage",
                )
                details = _summarize_video_stage_detail(selected, regions)
            return self._settings_details_result(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                details=(
                    details
                    if normalized_profile == "safe"
                    else _redact_payload(
                        details,
                        section="video",
                        profile=normalized_profile,
                        redactions=redactions,
                        path="video.stage",
                    )
                ),
                redactions=redactions,
                errors=errors,
            )

        if normalized_section == "network":
            if normalized_kind not in {"network_patch"}:
                raise ValueError("Network details support kind network_patch or all")
            items = self._read_workspace_setting(resolved_workspace_id, "network/patchList", errors, "network.patchList")
            return self._setting_details_from_collection(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                items,
                redactions,
                errors,
            )

        if normalized_section == "midi":
            if normalized_kind not in {"midi_patch"}:
                raise ValueError("MIDI details support kind midi_patch or all")
            items = self._read_workspace_setting(resolved_workspace_id, "midi/patchList", errors, "midi.patchList")
            return self._setting_details_from_collection(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                items,
                redactions,
                errors,
            )

        if normalized_section == "light":
            if normalized_kind not in {"light_patch"}:
                raise ValueError("Light details support kind light_patch or all")
            patch, read_transport = self._read_light_patch_setting(resolved_workspace_id, errors)
            details = self._workspace_settings_light_patch(patch, normalized_profile, redactions, read_transport)
            return self._settings_details_result(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                details=details,
                redactions=redactions,
                errors=errors,
            )

        if normalized_section == "general":
            if normalized_kind != "all":
                raise ValueError("General details support only kind all")
            details = self._workspace_settings_general(resolved_workspace_id, errors)
            return self._settings_details_result(
                resolved_workspace_id,
                normalized_section,
                normalized_kind,
                ref,
                normalized_profile,
                details=details,
                redactions=redactions,
                errors=errors,
            )

    def _get_workspace_settings_details_batch(
        self,
        workspace_id: str,
        requests: Any,
        profile: str = "safe",
    ) -> dict[str, Any]:
        resolved_workspace_id = _clean_workspace_id(workspace_id)
        normalized_profile = _normalize_workspace_settings_profile(profile)
        results: list[dict[str, Any]] = []
        batch_errors: dict[str, str] = {}
        warnings = _profile_warnings(normalized_profile)

        for index, raw_request in enumerate(_raw_detail_requests(requests)):
            try:
                request = _normalize_detail_request(raw_request)
                result = self._get_workspace_setting_details_single(
                    resolved_workspace_id,
                    section=request["section"],
                    kind=request["kind"],
                    ref=request["ref"],
                    profile=normalized_profile,
                )
                item_ok = result.get("details") is not None and not result.get("errors")
                if result.get("choices") and result.get("details") is None:
                    item_ok = False
                result = {
                    "ok": item_ok,
                    "request_index": index,
                    "request": request,
                    **result,
                }
                if not item_ok:
                    batch_errors[f"request_{index}"] = result.get("message") or "Workspace setting detail request failed."
            except (ValueError, TypeError) as exc:
                batch_errors[f"request_{index}"] = str(exc)
                result = {
                    "ok": False,
                    "request_index": index,
                    "request": raw_request if isinstance(raw_request, dict) else None,
                    "workspace_id": resolved_workspace_id,
                    "section": str(raw_request.get("section")) if isinstance(raw_request, dict) else None,
                    "kind": str(raw_request.get("kind")) if isinstance(raw_request, dict) else None,
                    "ref": raw_request.get("ref") if isinstance(raw_request, dict) else None,
                    "profile": normalized_profile,
                    "details": None,
                    "choices": [],
                    "redactions": [],
                    "errors": {"request": str(exc)},
                    "message": str(exc),
                }
            results.append(result)

        succeeded_count = sum(1 for result in results if result.get("ok") is True)
        failed_count = len(results) - succeeded_count
        return {
            "ok": failed_count == 0,
            "workspace_id": resolved_workspace_id,
            "mode": "details",
            "profile": normalized_profile,
            "requested_count": len(results),
            "succeeded_count": succeeded_count,
            "failed_count": failed_count,
            "results": results,
            "errors": batch_errors or None,
            "warnings": warnings,
        }

    def get_workspace_settings(
        self,
        workspace_id: str,
        mode: str = "summary",
        sections: list[str] | tuple[str, ...] | str | None = None,
        requests: Any = None,
        profile: str = "safe",
    ) -> dict[str, Any]:
        normalized_mode = _normalize_workspace_settings_mode(mode)
        normalized_profile = _normalize_workspace_settings_profile(profile)
        try:
            resolved_workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _settings_workspace_resolution_error(
                _clean_workspace_id(workspace_id),
                normalized_mode,
                normalized_profile,
                getattr(exc, "status", "workspace_not_found"),
                str(exc),
            )
        if normalized_mode == "summary":
            return self._get_workspace_settings_summary(resolved_workspace_id, sections=sections, profile=profile)
        return self._get_workspace_settings_details_batch(resolved_workspace_id, requests=requests, profile=profile)

    def get_workspace_setting_details(
        self,
        workspace_id: str,
        section: str,
        kind: str | None = None,
        ref: str | None = None,
        profile: str = "safe",
    ) -> dict[str, Any]:
        batch = self.get_workspace_settings(
            workspace_id,
            mode="details",
            requests=[{"section": section, "kind": kind, "ref": ref}],
            profile=profile,
        )
        if batch["results"]:
            result = dict(batch["results"][0])
            result.pop("ok", None)
            result.pop("request_index", None)
            result.pop("request", None)
            return result
        return self._settings_details_result(
            workspace_id,
            section,
            kind or "all",
            ref,
            profile,
            details=None,
            errors=batch.get("errors"),
            message="Workspace setting detail request failed.",
        )
