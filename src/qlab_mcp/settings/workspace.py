"""Workspace settings overview and detail readers."""

from __future__ import annotations

import math
from typing import Any
from uuid import UUID

from ..osc.addressing import _clean_workspace_id, _workspace_address
from ..errors import OscTimeoutError, QLabReplyError
from ..sanitizer import sanitize_exception_message
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
    _summarize_video_input_patch,
    _summarize_video_route,
    _summarize_video_stage,
    _summarize_video_stage_detail,
    _video_settings_problems,
)


WORKSPACE_SETTINGS_SECTIONS = ("audio", "video", "network", "midi", "light", "general")
MAX_WORKSPACE_DETAIL_REQUESTS = 50
MAX_WORKSPACE_SETTINGS_SECTIONS = len(WORKSPACE_SETTINGS_SECTIONS)
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

_SETTING_COLLECTION_COMMANDS = {
    "audio/patchList",
    "mic/patchList",
    "audio/maps",
    "video/inputPatchList",
    "video/routes",
    "video/stages",
    "network/patchList",
    "midi/patchList",
}


def _valid_setting_number(value: Any, *, nonnegative: bool = False) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and (not isinstance(value, float) or math.isfinite(value))
        and (not nonnegative or value >= 0)
    )


def _valid_positive_setting_int(value: Any, *, maximum: int | None = None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 1
        and (maximum is None or value <= maximum)
    )


def _valid_positive_setting_int_list(value: Any) -> bool:
    return isinstance(value, list) and all(_valid_positive_setting_int(item) for item in value)


def _validate_workspace_setting_payload(command: str, data: Any) -> bool:
    if command in _SETTING_COLLECTION_COMMANDS:
        valid = isinstance(data, list) and all(
            isinstance(item, dict) and _detail_request_ref(item) is not None for item in data
        )
        if valid and command == "audio/patchList":
            return all(
                item.get("routing") is None or _valid_positive_setting_int_list(item["routing"])
                for item in data
            )
        return valid
    if command.endswith("/regions"):
        return isinstance(data, list) and all(isinstance(item, dict) for item in data)
    if command == "general/minGoTime":
        return _valid_setting_number(data, nonnegative=True)
    if command == "general/selectionIsPlayhead" or command.endswith("/enableGuides"):
        return isinstance(data, bool)
    if command in {"audio/maxVolume", "audio/minVolume"}:
        return _valid_setting_number(data)
    if command in {"audio/cueOutputChannelCounts", "audio/outputChannelNames"}:
        return isinstance(data, (list, dict))
    if command.startswith("audio/patchID/"):
        if command.endswith("/cueOutputChannels"):
            return _valid_positive_setting_int(data, maximum=128)
        if command.endswith(("/muteChannels", "/soloChannels")):
            return _valid_positive_setting_int_list(data)
        if "/level/" in command:
            return _valid_setting_number(data) or data == "-inf"
        return (
            isinstance(data, dict)
            and _detail_request_ref(data) is not None
            and (data.get("routing") is None or _valid_positive_setting_int_list(data["routing"]))
        )
    if command.startswith(("video/stageID/", "video/routeID/")):
        return isinstance(data, dict) and bool(data)
    return True


def _setting_read_error_code(errors: dict[str, str]) -> str:
    if any(str(message).startswith("setting_payload_invalid:") for message in errors.values()):
        return "setting_payload_invalid"
    return "setting_read_failed"

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

    if len(raw_sections) > MAX_WORKSPACE_SETTINGS_SECTIONS:
        raise ValueError(
            f"workspace settings sections can include at most {MAX_WORKSPACE_SETTINGS_SECTIONS} entries"
        )

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


def _patch_scoped_setting(payload: Any, patch_id: str) -> Any:
    mappings = [payload] if isinstance(payload, dict) else payload if isinstance(payload, list) else []
    for mapping in mappings:
        if not isinstance(mapping, dict):
            continue
        for key, value in mapping.items():
            if str(key).casefold() == patch_id.casefold():
                return value
    return None


def _normalize_output_channel_names(payload: Any, patch_id: str) -> list[dict[str, Any]]:
    names = _patch_scoped_setting(payload, patch_id)
    if not isinstance(names, dict):
        return []
    normalized = []
    for channel, name in names.items():
        try:
            channel_number = int(channel)
        except (TypeError, ValueError):
            continue
        if _valid_positive_setting_int(channel_number) and isinstance(name, str):
            normalized.append({"channel": channel_number, "name": name})
    return sorted(normalized, key=lambda item: item["channel"])


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
        if len(requests) > MAX_WORKSPACE_DETAIL_REQUESTS:
            raise ValueError(
                f"workspace settings details can include at most {MAX_WORKSPACE_DETAIL_REQUESTS} requests"
            )
        return list(requests)
    raise ValueError("requests must be a detail request object or a list of request objects")

def _normalize_detail_request(raw_request: Any) -> dict[str, Any]:
    if not isinstance(raw_request, dict):
        raise ValueError("detail request must be an object with section, kind, and optional ref")
    section = _normalize_workspace_settings_sections([raw_request.get("section")])[0]
    kind = _normalize_workspace_setting_detail_kind(raw_request.get("kind"), section)
    raw_ref = raw_request.get("ref")
    ref = None if raw_ref in (None, "") else str(raw_ref)
    input_channel = raw_request.get("input_channel")
    output_channel = raw_request.get("output_channel")
    if (input_channel is None) != (output_channel is None):
        raise ValueError("input_channel and output_channel must be provided together")
    if input_channel is not None:
        if section != "audio" or kind != "output_patch":
            raise ValueError("channel selectors are only valid for an audio output_patch")
        if not _valid_positive_setting_int(input_channel, maximum=128):
            raise ValueError("input_channel must be a strict integer from 1 through 128")
        if not _valid_positive_setting_int(output_channel):
            raise ValueError("output_channel must be a strict positive integer")
    return {
        "section": section,
        "kind": kind,
        "ref": ref,
        "input_channel": input_channel,
        "output_channel": output_channel,
    }

def _profile_warnings(profile: str) -> list[str]:
    if profile == "technical":
        return [TECHNICAL_PROFILE_WARNING]
    if profile == "exhaustive":
        return [EXHAUSTIVE_PROFILE_WARNING]
    return []


class WorkspaceSettingsMixin:
    def get_video_setting(
        self, workspace_id: str, *, kind: str, ref: str, profile: str = "safe",
    ) -> dict[str, Any]:
        """Read one Video object directly by UUID, without list/name selection."""
        if kind not in {"stage", "route"} or profile not in {"safe", "technical"}:
            raise ValueError("Video detail requires stage/route and safe/technical")
        object_id = str(UUID(str(ref))).upper()
        try:
            workspace_id = self._resolve_workspace_id_strict(workspace_id)
        except Exception as exc:
            return _settings_workspace_resolution_error(
                _clean_workspace_id(workspace_id), "details", profile,
                getattr(exc, "status", "workspace_not_found"), sanitize_exception_message(exc),
            )
        errors: dict[str, str] = {}
        redactions: list[dict[str, str]] = []
        command = f"video/{kind}ID/{object_id}"
        reply_errors: list[QLabReplyError] = []
        item = self._read_workspace_setting(workspace_id, command, errors, command, reply_errors=reply_errors)
        result = self._settings_details_result(
            workspace_id, "video", kind, object_id, profile, errors=errors,
        )
        code_prefix = "video_stage" if kind == "stage" else "video_output_route"
        if errors or not isinstance(item, dict) or not item:
            missing = not errors and item in (None, {})
            if reply_errors and reply_errors[0].status == "error":
                # QLab uses a generic error for missing UUIDs. Verify absence;
                # a timeout/denied reply must never be interpreted as absence.
                inventory_command = f"video/{'stages' if kind == 'stage' else 'routes'}"
                inventory_errors: dict[str, str] = {}
                inventory = self._read_workspace_setting(
                    workspace_id, inventory_command, inventory_errors, inventory_command,
                )
                if not inventory_errors and isinstance(inventory, (list, dict)):
                    candidates = _collection_items(inventory)
                    valid_inventory = all(isinstance(candidate, dict) and candidate.get("uniqueID") for candidate in candidates)
                    missing = valid_inventory and not any(
                        str(candidate["uniqueID"]).casefold() == object_id.casefold() for candidate in candidates
                    )
                errors.update(inventory_errors)
            result.update(
                ok=False, status="error", partial=False,
                error_code=(
                    f"{code_prefix}_not_found"
                    if missing
                    else "setting_payload_invalid"
                    if _setting_read_error_code(errors) == "setting_payload_invalid"
                    else f"{code_prefix}_read_failed"
                ),
                errors=errors or None,
                suggested_action="Call qlab_get_workspace_video_settings to obtain exact uniqueID values, then retry.",
            )
            return result
        if str(item.get("uniqueID", "")).casefold() != object_id.casefold():
            result.update(
                ok=False, status="error", partial=False,
                error_code=f"{code_prefix}_identity_mismatch",
                message="QLab did not return the requested uniqueID.",
            )
            return result
        if kind == "stage":
            regions = self._read_workspace_setting(
                workspace_id, f"{command}/regions", errors, f"{command}/regions",
            )
            raw = {"stage": item, "regions": regions}
            detail = _summarize_video_stage(item, regions)
            if regions is None:
                detail.update(regions=None, region_count=None, multi_output=None)
        else:
            item = dict(item)
            if "enableGuides" not in item:
                item["enableGuides"] = self._read_workspace_setting(
                    workspace_id, f"{command}/enableGuides", errors, f"{command}/enableGuides",
                )
            raw = item
            detail = _summarize_video_route(item)
            for key in ("enableGuides", "rotationDegrees", "scalingMode", "naturalSize", "rear"):
                if key in item:
                    detail[key] = item[key]
        if errors and _setting_read_error_code(errors) == "setting_payload_invalid":
            result.update(
                ok=False,
                status="error",
                partial=False,
                error_code="setting_payload_invalid",
                details=None,
                errors=errors,
                suggested_action="Verify QLab returned the documented Video settings payload, then retry.",
            )
            return result
        technical = None
        if profile == "technical":
            technical = _redact_payload(raw, section="video", profile=profile,
                                        redactions=redactions, path=f"video.{kind}")
        else:
            _record_redactions(raw, "video", profile, redactions, f"video.{kind}")
        result.update(
            ok=True, status="partial" if errors else "ok", partial=bool(errors),
            details={"detail": detail, "technical_payload": technical},
            errors=errors or None, redactions=redactions,
            warnings=[TECHNICAL_PROFILE_WARNING] if profile == "technical" else [],
        )
        return result

    def _read_workspace_setting(
        self,
        workspace_id: str,
        command: str,
        errors: dict[str, str],
        error_key: str,
        *,
        reply_errors: list[QLabReplyError] | None = None,
    ) -> Any:
        address = _workspace_address(workspace_id, f"settings/{command}")
        try:
            data = self._request(address, workspace_id=workspace_id).data
            if not _validate_workspace_setting_payload(command, data):
                errors[error_key] = f"setting_payload_invalid: unexpected payload for {command}"
                return None
            return data
        except OscTimeoutError as exc:
            errors[error_key] = sanitize_exception_message(exc)
            return None
        except QLabReplyError as exc:
            errors[error_key] = sanitize_exception_message(exc)
            if reply_errors is not None:
                reply_errors.append(exc)
            return None
        except Exception as exc:
            errors[error_key] = sanitize_exception_message(exc)
            return None

    def _read_light_patch_setting(
        self,
        workspace_id: str,
        errors: dict[str, str],
    ) -> tuple[Any, str | None]:
        address = _workspace_address(workspace_id, "settings/light/patch")
        try:
            return self._request(address, workspace_id=workspace_id).data, "udp"
        except OscTimeoutError as udp_exc:
            try:
                return self._request_tcp(address, workspace_id=workspace_id).data, "tcp_fallback"
            except Exception as tcp_exc:
                errors["light.patch"] = "Light patch read timed out over UDP; TCP fallback also failed."
                return None, None
        except Exception as exc:
            errors["light.patch"] = sanitize_exception_message(exc)
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
        max_volume = self._read_workspace_setting(workspace_id, "audio/maxVolume", errors, "audio.maxVolume")
        min_volume = self._read_workspace_setting(workspace_id, "audio/minVolume", errors, "audio.minVolume")

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
                "max_volume": max_volume,
                "min_volume": min_volume,
            }

        _record_redactions(output_patches, "audio", profile, redactions, "audio.output_patches")
        _record_redactions(input_patches, "audio", profile, redactions, "audio.input_patches")
        summarized_output_patches = []
        for item in _collection_items(output_patches):
            summary = _summarize_audio_patch(item)
            patch_id = summary.get("uniqueID")
            if patch_id:
                cue_output_count = _patch_scoped_setting(cue_output_counts, str(patch_id))
                if _valid_positive_setting_int(cue_output_count, maximum=128):
                    summary["cue_output_count"] = cue_output_count
                summary["output_channel_names"] = _normalize_output_channel_names(
                    output_channel_names, str(patch_id)
                )
            summarized_output_patches.append(summary)
        return {
            "output_patches": summarized_output_patches,
            "input_patches": [_summarize_audio_patch(item) for item in _collection_items(input_patches)],
            "cue_output_channel_counts": cue_output_counts,
            "output_channel_names": output_channel_names,
            "max_volume": max_volume,
            "min_volume": min_volume,
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
            if stage_id:
                stage_regions[str(stage_id)] = stage.get("regions")

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
        summarized_input_patches = [
            _summarize_video_input_patch(item, index)
            for index, item in enumerate(_collection_items(input_patches), start=1)
        ]
        summarized_routes = [_summarize_video_route(item) for item in _collection_items(routes)]
        summarized_stages = [
                _summarize_video_stage(stage, region_data_for_stage(stage))
                for stage in _collection_items(stages)
        ]
        return {
            "input_patches": summarized_input_patches,
            "routes": summarized_routes,
            "stages": summarized_stages,
            "problems": _video_settings_problems(summarized_stages, summarized_routes),
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
                    "message": "Use qlab_get_workspace_light_settings to inspect the light patch.",
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
        if "video" in result_sections:
            video = result_sections["video"]
            summary["video_route_count"] = len(video.get("routes") or [])
            summary["video_stage_count"] = len(video.get("stages") or [])
            summary["video_input_patch_count"] = len(video.get("input_patches") or [])
            problems = video.get("problems") or []
            problem_counts: dict[str, int] = {}
            for problem in problems:
                if isinstance(problem, dict) and problem.get("code"):
                    code = str(problem["code"])
                    problem_counts[code] = problem_counts.get(code, 0) + 1
            summary["video_problem_count"] = len(problems)
            summary["video_problem_counts"] = problem_counts
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
        selection_error_code: str | None = None,
    ) -> dict[str, Any]:
        result = {
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
        if selection_error_code is not None:
            if selection_error_code == "setting_ref_not_found":
                suggested_action = (
                    f"Ref {ref!r} was not found; call qlab_get_workspace_{section}_settings without ref "
                    "to inspect available refs, then retry with an exact setting name or uniqueID."
                )
            elif selection_error_code in {"setting_payload_invalid", "setting_read_failed"}:
                suggested_action = "Verify QLab is reachable and returned the documented settings payload, then retry."
            else:
                suggested_action = (
                    f"Call qlab_get_workspace_{section}_settings again with one exact "
                    "choices[].uniqueID as ref."
                )
            result.update(
                {
                    "ok": False,
                    "status": "error",
                    "partial": False,
                    "error_code": selection_error_code,
                    "suggested_action": suggested_action,
                }
            )
        return result

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
        if not item_list and errors:
            error_code = _setting_read_error_code(errors)
            return self._settings_details_result(
                workspace_id,
                section,
                kind,
                ref,
                profile,
                details=None,
                choices=[],
                redactions=redactions,
                errors=errors,
                message=(
                    "QLab returned an invalid settings payload."
                    if error_code == "setting_payload_invalid"
                    else "Settings could not be read."
                ),
                selection_error_code=error_code,
            )
        if not item_list and ref is None:
            return self._settings_details_result(
                workspace_id,
                section,
                kind,
                ref,
                profile,
                details={"items": [], "empty": True, "available": False},
                choices=[],
                redactions=redactions,
                errors=errors,
                message="No settings items are configured for this request.",
            )
        selected, choices, message, selection_error_code = _select_setting_item(item_list, ref)
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
                selection_error_code=selection_error_code,
            )
        if profile == "safe":
            _record_redactions(selected, section, profile, redactions, f"{section}.{kind}")
            details = _summarize_setting_detail_item(section, kind, selected)
        elif section in {"audio", "network", "midi"}:
            details = _summarize_setting_detail_item(section, kind, selected)
            details["technical_payload"] = _redact_payload(
                selected,
                section=section,
                profile=profile,
                redactions=redactions,
                path=f"{section}.{kind}",
            )
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

    def _workspace_audio_output_patch_details(
        self,
        workspace_id: str,
        ref: str | None,
        profile: str,
        input_channel: int | None,
        output_channel: int | None,
        redactions: list[dict[str, str]],
        errors: dict[str, str],
    ) -> dict[str, Any]:
        items = self._read_workspace_setting(workspace_id, "audio/patchList", errors, "audio.patchList")
        item_list = _collection_items(items)
        if not item_list:
            return self._setting_details_from_collection(
                workspace_id, "audio", "output_patch", ref, profile, items, redactions, errors,
            )
        selected, choices, message, selection_error_code = _select_setting_item(item_list, ref)
        if selected is None:
            return self._settings_details_result(
                workspace_id, "audio", "output_patch", ref, profile,
                details=None, choices=choices, redactions=redactions, errors=errors,
                message=message, selection_error_code=selection_error_code,
            )
        patch_id = _first_present(selected, ("uniqueID", "id", "patchID"))
        if patch_id in (None, ""):
            errors["audio.output_patch"] = "setting_payload_invalid: output patch has no uniqueID"
            return self._settings_details_result(
                workspace_id, "audio", "output_patch", ref, profile,
                details=None, redactions=redactions, errors=errors,
                message="QLab returned an invalid Audio Output Patch payload.",
                selection_error_code="setting_payload_invalid",
            )

        patch_id = str(patch_id)
        command = f"audio/patchID/{patch_id}"
        patch = self._read_workspace_setting(workspace_id, command, errors, f"audio.patchID.{patch_id}")
        if not isinstance(patch, dict):
            return self._settings_details_result(
                workspace_id, "audio", "output_patch", ref, profile,
                details=None, redactions=redactions, errors=errors,
                message="The exact Audio Output Patch could not be read.",
                selection_error_code=_setting_read_error_code(errors),
            )
        returned_id = _first_present(patch, ("uniqueID", "id", "patchID"))
        if returned_id is None or str(returned_id).casefold() != patch_id.casefold():
            errors[f"audio.patchID.{patch_id}"] = "setting_payload_invalid: output patch identity mismatch"
            return self._settings_details_result(
                workspace_id, "audio", "output_patch", ref, profile,
                details=None, redactions=redactions, errors=errors,
                message="QLab did not return the requested Audio Output Patch uniqueID.",
                selection_error_code="setting_payload_invalid",
            )

        cue_output_count = self._read_workspace_setting(
            workspace_id, f"{command}/cueOutputChannels", errors, f"audio.patchID.{patch_id}.cueOutputChannels",
        )
        output_names = self._read_workspace_setting(
            workspace_id, "audio/outputChannelNames", errors, "audio.outputChannelNames",
        )
        mute_channels = self._read_workspace_setting(
            workspace_id, f"{command}/muteChannels", errors, f"audio.patchID.{patch_id}.muteChannels",
        )
        solo_channels = self._read_workspace_setting(
            workspace_id, f"{command}/soloChannels", errors, f"audio.patchID.{patch_id}.soloChannels",
        )
        level = None
        level_value = None
        if input_channel is not None and output_channel is not None:
            level_command = f"{command}/level/{input_channel}/{output_channel}"
            level_value = self._read_workspace_setting(
                workspace_id, level_command, errors,
                f"audio.patchID.{patch_id}.level.{input_channel}.{output_channel}",
            )
            if level_value is not None:
                level = {
                    "input_channel": input_channel,
                    "output_channel": output_channel,
                    "decibels": level_value,
                }

        detail = _summarize_audio_patch(patch)
        detail.update(
            cue_output_count=cue_output_count,
            output_channel_names=_normalize_output_channel_names(output_names, patch_id),
            mute_channels=mute_channels or [],
            solo_channels=solo_channels or [],
            level=level,
        )
        raw = {
            "patch": patch,
            "cue_output_count": cue_output_count,
            "output_channel_names": output_names,
            "mute_channels": mute_channels,
            "solo_channels": solo_channels,
            "level": level_value,
        }
        if profile == "safe":
            _record_redactions(raw, "audio", profile, redactions, "audio.output_patch")
        else:
            detail["technical_payload"] = _redact_payload(
                raw, section="audio", profile=profile, redactions=redactions,
                path="audio.output_patch",
            )
        result = self._settings_details_result(
            workspace_id, "audio", "output_patch", ref, profile,
            details=detail, choices=[], redactions=redactions, errors=errors, message=None,
        )
        if errors:
            result.update(ok=True, status="partial", partial=True)
        return result

    def _get_workspace_setting_details_single(
        self,
        workspace_id: str,
        section: str,
        kind: str | None = None,
        ref: str | None = None,
        profile: str = "safe",
        input_channel: int | None = None,
        output_channel: int | None = None,
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
                return self._workspace_audio_output_patch_details(
                    resolved_workspace_id, ref, normalized_profile, input_channel, output_channel,
                    redactions, errors,
                )
            elif normalized_kind == "input_patch":
                items = self._read_workspace_setting(resolved_workspace_id, "mic/patchList", errors, "audio.inputPatchList")
            elif normalized_kind == "audio_map":
                items = self._read_workspace_setting(resolved_workspace_id, "audio/maps", errors, "audio.maps")
                item_list = _collection_items(items)
                if not item_list:
                    return self._settings_details_result(
                        resolved_workspace_id,
                        normalized_section,
                        normalized_kind,
                        ref,
                        normalized_profile,
                        details={"items": [], "empty": True, "available": False},
                        choices=[],
                        redactions=redactions,
                        errors=errors,
                        message="No settings items are configured for this request.",
                    )
                selected, choices, message, selection_error_code = _select_setting_item(item_list, ref)
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
                        selection_error_code=selection_error_code,
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
            if not stage_items:
                return self._settings_details_result(
                    resolved_workspace_id,
                    normalized_section,
                    normalized_kind,
                    ref,
                    normalized_profile,
                    details={"items": [], "empty": True, "available": False},
                    choices=[],
                    redactions=redactions,
                    errors=errors,
                    message="No settings items are configured for this request.",
                )
            selected, choices, message, selection_error_code = _select_setting_item(stage_items, ref)
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
                    selection_error_code=selection_error_code,
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
                    input_channel=request["input_channel"],
                    output_channel=request["output_channel"],
                )
                item_ok = result.get("details") is not None and (
                    not result.get("errors") or result.get("ok") is True
                )
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
                batch_errors[f"request_{index}"] = sanitize_exception_message(exc)
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
                    "errors": {"request": sanitize_exception_message(exc)},
                    "message": sanitize_exception_message(exc),
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
        if isinstance(sections, str) and len(sections.split(",")) > MAX_WORKSPACE_SETTINGS_SECTIONS:
            raise ValueError(
                f"workspace settings sections can include at most {MAX_WORKSPACE_SETTINGS_SECTIONS} entries"
            )
        if isinstance(sections, (list, tuple)) and len(sections) > MAX_WORKSPACE_SETTINGS_SECTIONS:
            raise ValueError(
                f"workspace settings sections can include at most {MAX_WORKSPACE_SETTINGS_SECTIONS} entries"
            )
        if isinstance(requests, (list, tuple)) and len(requests) > MAX_WORKSPACE_DETAIL_REQUESTS:
            raise ValueError(
                f"workspace settings details can include at most {MAX_WORKSPACE_DETAIL_REQUESTS} requests"
            )
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
        input_channel: int | None = None,
        output_channel: int | None = None,
    ) -> dict[str, Any]:
        batch = self.get_workspace_settings(
            workspace_id,
            mode="details",
            requests=[{
                "section": section,
                "kind": kind,
                "ref": ref,
                "input_channel": input_channel,
                "output_channel": output_channel,
            }],
            profile=profile,
        )
        if batch.get("ok") is False and not batch.get("results"):
            return {
                "ok": False,
                "status": batch.get("status"),
                "partial": False,
                "error_code": batch.get("error_code") or batch.get("status"),
                "suggested_action": batch.get("suggested_action"),
                "message": batch.get("message"),
                "received": batch.get("received"),
                "allowed": batch.get("allowed"),
                "workspace_id": batch.get("workspace_id") or _clean_workspace_id(workspace_id),
                "section": section,
                "kind": kind or ("light_patch" if section == "light" else "all"),
                "ref": ref,
                "profile": batch.get("profile") or profile,
                "details": None,
                "choices": [],
                "redactions": batch.get("redactions") or [],
                "errors": batch.get("errors"),
                "warnings": batch.get("warnings") or [],
            }
        if batch["results"]:
            result = dict(batch["results"][0])
            result.pop("request_index", None)
            result.pop("request", None)
            if result.get("ok") is True:
                result["partial"] = bool(result.get("errors"))
                result["status"] = "partial" if result["partial"] else "ok"
            request_error = (result.get("errors") or {}).get("request")
            if isinstance(request_error, str) and "Unknown workspace setting detail kind" in request_error:
                result.update(
                    {
                        "ok": False,
                        "status": "error",
                        "partial": False,
                        "error_code": "invalid_setting_kind",
                        "message": request_error,
                        "received": kind,
                        "allowed": sorted(WORKSPACE_SETTING_DETAIL_KINDS),
                        "details": {
                            "section": section,
                            "kind": kind,
                            "ref": ref,
                            "profile": profile,
                        },
                    }
                )
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
