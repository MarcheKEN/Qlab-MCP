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
    _light_patch_sheet,
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
WORKSPACE_SETTINGS_PROFILES = {"safe", "technical"}
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

def _normalize_workspace_settings_profile(profile: str) -> str:
    normalized = str(profile or "").strip().lower()
    if normalized not in WORKSPACE_SETTINGS_PROFILES:
        allowed = ", ".join(sorted(WORKSPACE_SETTINGS_PROFILES))
        raise ValueError(f"Unknown workspace settings profile {profile!r}; use one of: {allowed}")
    return normalized

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

        if profile == "technical":
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

        if profile == "technical":
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
        if profile == "technical":
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
        if profile == "technical":
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
        if profile != "technical":
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
            "patch_sheet": _light_patch_sheet(patch),
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

    def get_workspace_settings(
        self,
        workspace_id: str,
        sections: list[str] | tuple[str, ...] | str | None = None,
    ) -> dict[str, Any]:
        resolved_workspace_id = _clean_workspace_id(workspace_id)
        normalized_profile = "safe"
        normalized_sections = _normalize_workspace_settings_sections(sections)
        redactions: list[dict[str, str]] = []
        errors: dict[str, str] = {}
        result_sections: dict[str, Any] = {}

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
            "profile": normalized_profile,
            "sections": result_sections,
            "summary": summary,
            "redactions": redactions,
            "errors": errors or None,
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

    def get_workspace_setting_details(
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
                if normalized_profile == "safe":
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
