"""Cue detail profile helpers and safe derived fields."""

from __future__ import annotations

import math
from typing import Any

from ..osc.addressing import _clean_cue_ref


AUTO_IDENTITY_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "colorName",
    "secondColorName",
    "useSecondColor",
)
AUTO_STRUCTURE_KEYS = (
    "parent",
    "cartPosition",
)
AUTO_STATUS_KEYS = (
    "armed",
    "flagged",
    "isRunning",
    "isPaused",
    "isLoaded",
    "isBroken",
    "isWarning",
    "isActionRunning",
    "isAuditioning",
    "isOverridden",
    "skipIfDisarmed",
    "autoLoad",
)
AUTO_TIMING_KEYS = (
    "preWait",
    "duration",
    "postWait",
    "continueMode",
    "continueModeLabel",
    "timecodeTrigger",
    "timecodeTrigger/text",
)
AUTO_TARGET_KEYS = (
    "hasFileTargets",
    "fileTargetPresent",
    "hasCueTargets",
    "cueTargetID",
    "cueTargetNumber",
    "tempCueTargetID",
    "tempCueTargetNumber",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
)
AUTO_AUDIO_KEYS = (
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
    "audioMap",
    "audioMap/size",
)
AUTO_VIDEO_KEYS = (
    "stageName",
    "stageNumber",
    "stageID",
    "stage/size",
    "stage/uniqueID",
    "cueSize",
    "cueSize/width",
    "cueSize/height",
    "translation",
    "scale",
    "opacity",
    "videoEffects",
    "videoInputPatchName",
    "videoInputPatchNumber",
    "videoInputPatchID",
)
AUTO_TEXT_KEYS = (
    *AUTO_VIDEO_KEYS,
    "text",
    "text/fragments",
    "text/outputSize",
    "text/outputSize/width",
    "text/outputSize/height",
)
AUTO_LIGHT_KEYS = (
    "lightCommandText",
    "alwaysCollate",
    "subcontroller",
)
AUTO_NETWORK_KEYS = (
    "networkPatchName",
    "networkPatchNumber",
    "networkPatchID",
    "customString",
    "message",
    "messageError",
    "parameterValues",
)
AUTO_MIDI_KEYS = (
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
)
AUTO_TIMECODE_KEYS = (
    "outputType",
    "framerate",
    "startTime",
    "endTime",
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
    "ltcChannel",
)
AUTO_GROUP_KEYS = tuple(sorted(GROUP_KEY for GROUP_KEY in (
    "cartColumns",
    "cartRows",
    "currentTimecode",
    "currentTimecode/text",
    "isChildAuditioning",
    "isChildFlagged",
    "mode",
    "playbackPosition",
    "playbackPositionID",
    "playhead",
    "playheadID",
    "playlist/currentCue",
    "playlist/currentCueID",
    "playlistCrossfade",
    "playlistCrossfadeDuration",
    "playlistLoop",
    "playlistShuffle",
)))
AUTO_FADE_KEYS = (
    "cueTargetID",
    "cueTargetNumber",
    "currentCueTargetID",
    "targetMode",
    "patchTargetID",
    "audioMapTargetID",
    "audioOutputPatchName",
    "audioOutputPatchID",
    "stopTargetWhenDone",
    "levelsMode",
    "geoMode",
    "mode",
    "fadeType",
    "pathHeight",
    "pathWidth",
    "rotation",
    "rotationType",
    "doOpacity",
    "doRate",
    "doRotation",
    "doScale",
    "doTranslation",
)
AUTO_TRANSPORT_KEYS = (
    "cueTargetID",
    "cueTargetNumber",
    "tempCueTargetID",
    "tempCueTargetNumber",
    "currentCueTargetID",
    "currentCueTargetNumber",
    "targetMode",
)
AUTO_RESET_KEYS = (
    *AUTO_TRANSPORT_KEYS,
    "patchTargetID",
    "audioMapTargetID",
)
AUTO_DEVAMP_KEYS = (
    *AUTO_TRANSPORT_KEYS,
    "devampType",
    "startNextCueWhenSliceEnds",
    "stopTargetWhenSliceEnds",
)
AUTO_TYPE_SPECIFIC_KEYS = {
    "audio": (*AUTO_AUDIO_KEYS,),
    "mic": (*AUTO_AUDIO_KEYS,),
    "video": (*AUTO_VIDEO_KEYS, "audioOutputPatchName", "audioOutputPatchID"),
    "camera": (*AUTO_VIDEO_KEYS, "audioOutputPatchName", "audioOutputPatchID"),
    "text": AUTO_TEXT_KEYS,
    "light": AUTO_LIGHT_KEYS,
    "network": AUTO_NETWORK_KEYS,
    "midi": AUTO_MIDI_KEYS,
    "midi file": AUTO_MIDI_KEYS,
    "timecode": AUTO_TIMECODE_KEYS,
    "group": AUTO_GROUP_KEYS,
    "cue list": AUTO_GROUP_KEYS,
    "cue cart": AUTO_GROUP_KEYS,
    "fade": AUTO_FADE_KEYS,
    "start": AUTO_TRANSPORT_KEYS,
    "stop": AUTO_TRANSPORT_KEYS,
    "pause": AUTO_TRANSPORT_KEYS,
    "load": AUTO_TRANSPORT_KEYS,
    "reset": AUTO_RESET_KEYS,
    "devamp": AUTO_DEVAMP_KEYS,
    "go to": AUTO_TRANSPORT_KEYS,
    "goto": AUTO_TRANSPORT_KEYS,
    "target": AUTO_TRANSPORT_KEYS,
    "arm": AUTO_TRANSPORT_KEYS,
    "disarm": AUTO_TRANSPORT_KEYS,
    "wait": (),
    "memo": (),
    "script": (),
}

def _coerce_qlab_bool(value: Any) -> bool | None:
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
    return None

def _is_positive_number(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False

def _derive_profile_fields(profile: str, values: dict[str, Any]) -> dict[str, Any]:
    normalized = profile.strip().lower()
    derived = dict(values)
    if "hasFileTargets" in derived:
        derived["fileTargetPresent"] = bool(_coerce_qlab_bool(derived.get("hasFileTargets")))
    if "continueMode" in derived:
        derived["continueModeLabel"] = _continue_mode_label(derived.get("continueMode"))
    if normalized == "auto":
        for sensitive_key in ("notes", "fileTarget", "scriptSource"):
            derived.pop(sensitive_key, None)
        for heavy_key in ("stage", "stage/regions"):
            derived.pop(heavy_key, None)
    if normalized in {"health", "targets"}:
        derived.pop("fileTarget", None)
    if normalized in {"type_specific", "inspector_safe"}:
        for sensitive_or_heavy_key in ("notes", "fileTarget", "scriptSource", "stage", "stage/regions"):
            derived.pop(sensitive_or_heavy_key, None)
    if normalized == "full":
        for sensitive_or_heavy_key in ("notes", "fileTarget", "scriptSource", "stage", "stage/regions"):
            derived.pop(sensitive_or_heavy_key, None)
    health_summary = _health_summary(derived)
    if health_summary is not None:
        derived["health_summary"] = health_summary
    return derived


def _continue_mode_label(value: Any) -> str:
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


def _health_summary(values: dict[str, Any]) -> dict[str, Any] | None:
    has_broken = "isBroken" in values
    has_warning = "isWarning" in values
    if not has_broken and not has_warning and not values.get("messageError"):
        return None

    is_broken = _coerce_qlab_bool(values.get("isBroken")) is True
    is_warning = _coerce_qlab_bool(values.get("isWarning")) is True
    file_target_present = _coerce_qlab_bool(values.get("fileTargetPresent")) is True
    cue_type = str(values.get("type") or "").strip()
    normalized_type = cue_type.casefold()
    messages: list[str] = []
    evidence: list[str] = []
    probable_causes: list[str] = []
    diagnostic_hints: list[str] = []
    needs_human_check: list[str] = []

    if cue_type:
        evidence.append(f"type={cue_type}")
    if has_broken:
        evidence.append(f"isBroken={str(is_broken).lower()}")
    if has_warning:
        evidence.append(f"isWarning={str(is_warning).lower()}")
    if "fileTargetPresent" in values:
        evidence.append(f"fileTargetPresent={str(file_target_present).lower()}")

    if is_broken and normalized_type in {"cue list", "cue cart", "group"}:
        messages.append("Container reports a broken state, likely inherited from one or more broken child cues.")
        probable_causes.append("broken_child_cue_likely")
        diagnostic_hints.append("Query or expand child cues with isBroken=true before editing the container.")
        needs_human_check.append("Open QLab Workspace Status or expand the container to confirm which child cue is broken.")
    elif is_broken and file_target_present:
        messages.append("File target exists but the cue is broken; likely missing, unavailable, or incompatible media.")
        probable_causes.append("file_target_present_but_broken")
        diagnostic_hints.append("Inspect the cue with profile='technical' only if the exact media path is needed.")
        needs_human_check.append("Check that the media volume is mounted and the target file is reachable and supported by QLab.")
    elif is_broken and normalized_type == "light":
        messages.append("Light cue reports a broken state.")
        probable_causes.append("light_cue_reported_broken")
        diagnostic_hints.append("Inspect the light cue command and the workspace light patch before changing cues.")
        needs_human_check.append("Check QLab license, light patch, and physical DMX/Art-Net/sACN output in QLab.")
    elif is_broken:
        messages.append("Cue reports a broken state.")
        probable_causes.append("cue_reported_broken")
        diagnostic_hints.append("Inspect the cue with profile='auto' or 'technical' to gather type-specific context.")
        needs_human_check.append("Open QLab Workspace Status for the exact human-facing reason.")

    if is_warning:
        messages.append("Cue reports a warning state.")
        probable_causes.append("cue_reported_warning")
        diagnostic_hints.append("Review this cue in QLab before assuming the warning affects playback.")
        needs_human_check.append("Decide whether this warning is operationally relevant for the show.")

    message_error = values.get("messageError")
    if message_error not in (None, ""):
        evidence.append("messageError_present")
        messages.append(f"Network/message error reported: {message_error}")
        probable_causes.append("network_message_error")
        diagnostic_hints.append("Inspect the network patch and message payload before assuming the receiver is reachable.")
        needs_human_check.append("Confirm the target application or device receives the network message.")

    if is_broken and is_warning:
        status = "broken_warning"
    elif is_broken:
        status = "broken"
    elif is_warning:
        status = "warning"
    elif messages:
        status = "attention"
    else:
        status = "ok"

    return {
        "status": status,
        "messages": messages,
        "evidence": evidence,
        "probable_causes": probable_causes,
        "diagnostic_hints": diagnostic_hints,
        "needs_human_check": needs_human_check,
        "confidence": "derived",
    }


def _normalized_cue_type(cue_type: Any) -> str:
    return str(cue_type or "").strip().casefold()


def _auto_type_specific_keys(cue_type: Any) -> tuple[str, ...]:
    return tuple(AUTO_TYPE_SPECIFIC_KEYS.get(_normalized_cue_type(cue_type), ()))


def _section_values(values: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: values[key] for key in keys if key in values}


def _video_effects_summary(value: Any) -> dict[str, Any]:
    effects = value if isinstance(value, list) else []
    summarized: list[dict[str, Any]] = []
    raw_keys: set[str] = set()
    for index, effect in enumerate(effects):
        entry: dict[str, Any] = {"index": index}
        if isinstance(effect, dict):
            keys = sorted(str(key) for key in effect)
            raw_keys.update(keys)
            entry["keys"] = keys
            name = next(
                (effect.get(key) for key in ("name", "effectName", "displayName", "oscName") if effect.get(key)),
                None,
            )
            if name is not None:
                entry["name"] = name
                entry["addressing"] = {
                    "by_index": f"videoEffectIndex/{index}",
                    "by_name": f"videoEffect/{name}",
                }
            else:
                entry["identity_available"] = False
                entry["addressing"] = {"by_index": f"videoEffectIndex/{index}"}
            effect_type = next(
                (effect.get(key) for key in ("type", "effectType", "category") if effect.get(key)),
                None,
            )
            if effect_type is not None:
                entry["type"] = effect_type
            else:
                entry["type_available"] = False
            enabled = effect.get("enabled", effect.get("isEnabled"))
            if isinstance(enabled, bool):
                entry["enabled"] = enabled
                entry["enabled_readback_stable"] = True
                entry["enabled_write_documented"] = True
            else:
                entry["enabled_available"] = False
            parameters, source = _video_effect_parameter_inventory(effect)
            if parameters:
                entry["parameters_source"] = source
                entry["parameters"] = [
                    _video_effect_parameter_summary(key, parameter_value)
                    for key, parameter_value in sorted(parameters.items(), key=lambda item: str(item[0]))
                ]
        elif isinstance(effect, str):
            entry["name"] = effect
        summarized.append(entry)
    return {
        "hasVideoEffects": bool(effects),
        "effect_count": len(effects),
        "effects": summarized,
        "raw_effect_keys": sorted(raw_keys),
    }


_VIDEO_EFFECT_IDENTITY_KEYS = frozenset(
    {
        "name",
        "effectName",
        "displayName",
        "oscName",
        "type",
        "effectType",
        "category",
        "enabled",
        "isEnabled",
        "parameters",
    }
)


def _video_effect_parameter_inventory(effect: dict[str, Any]) -> tuple[dict[str, Any], str]:
    parameters = effect.get("parameters")
    if isinstance(parameters, dict):
        return parameters, "parameters"
    return {
        str(key): value
        for key, value in effect.items()
        if str(key) not in _VIDEO_EFFECT_IDENTITY_KEYS
    }, "flat_payload"


def _video_effect_parameter_summary(key: Any, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        kind, stable = "boolean", True
    elif isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)):
        kind, stable = "number", True
    elif isinstance(value, str):
        kind, stable = "enum_or_string", True
    elif (
        isinstance(value, list)
        and len(value) == 4
        and all(
            isinstance(component, (int, float))
            and not isinstance(component, bool)
            and math.isfinite(float(component))
            and 0 <= float(component) <= 1
            for component in value
        )
    ):
        kind, stable = "color", False
    elif isinstance(value, (list, dict)):
        kind, stable = "structured", False
    else:
        kind, stable = "unknown", False
    summary = {
        "key": str(key),
        "value_type": type(value).__name__,
        "kind": kind,
        "scalar": stable,
        "readback_stable": stable,
        "writable_path_documented": True,
        "dry_run_candidate": stable,
        "risk": "high",
    }
    if stable:
        summary["value"] = value
    return summary


def _lightweight_video_regions(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    regions: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        region = _section_values(item, ("name", "uniqueID", "index"))
        route = item.get("route")
        if isinstance(route, dict):
            route_summary = _section_values(
                route,
                ("name", "uniqueID", "connected", "present", "destination_present"),
            )
            device = route.get("device")
            if isinstance(device, dict):
                route_summary["device"] = _section_values(
                    device,
                    ("name", "type", "connected", "present"),
                )
            region["route"] = route_summary
        regions.append(region)
    return regions


def _camera_input_summary(
    values: dict[str, Any],
    input_patches: list[dict[str, Any]],
    *,
    validation_available: bool,
) -> dict[str, Any]:
    cue_patch = {
        "name": values.get("videoInputPatchName"),
        "number": values.get("videoInputPatchNumber"),
        "uniqueID": values.get("videoInputPatchID"),
    }
    deprecated_value = values.get("cameraPatch")
    result: dict[str, Any] = {
        "cue_patch": cue_patch,
        "validation_available": validation_available,
        "deprecated_reference_present": deprecated_value not in (None, "", 0, "0"),
    }
    if deprecated_value is not None:
        result["cameraPatch"] = deprecated_value
    if not validation_available:
        result.update(status="unknown", match_method="none", reason="input_patch_list_unavailable")
        return result

    patch_id = cue_patch["uniqueID"]
    patch_number = cue_patch["number"]
    match: dict[str, Any] | None = None
    match_method = "none"
    if patch_id not in (None, "", "none"):
        match = next((item for item in input_patches if item.get("uniqueID") == patch_id), None)
        if match is None:
            result.update(status="invalid_reference", match_method="id", reason="video_input_patch_id_not_found")
            return result
        match_method = "id"
    elif patch_number not in (None, "", 0, "0"):
        try:
            number = int(patch_number)
        except (TypeError, ValueError):
            number = -1
        match = next((item for item in input_patches if item.get("number") == number), None)
        if match is None:
            result.update(status="invalid_reference", match_method="number", reason="video_input_patch_number_out_of_range")
            return result
        match_method = "number"
    elif deprecated_value not in (None, "", 0, "0"):
        try:
            number = int(deprecated_value)
        except (TypeError, ValueError):
            number = -1
        match = next((item for item in input_patches if item.get("number") == number), None)
        result.update(status="deprecated_reference", match_method="cameraPatch", reason="camera_patch_is_deprecated")
        if match is not None:
            result["input_patch"] = match
        return result
    else:
        result.update(status="missing", match_method="none", reason="camera_input_patch_unassigned")
        return result

    result["input_patch"] = match
    result["match_method"] = match_method
    explicitly_disconnected = match.get("connected") is False or match.get("available") is False
    explicitly_disconnected = explicitly_disconnected or (
        match.get("device_presence_known") is True and match.get("device_present") is False
    ) or (
        match.get("source_presence_known") is True and match.get("source_present") is False
    )
    if explicitly_disconnected:
        result.update(status="disconnected", reason="video_input_patch_source_or_device_unavailable")
    else:
        result["status"] = "valid"
    return result


def _visual_problems(values: dict[str, Any], stage: dict[str, Any], camera_input: dict[str, Any] | None) -> list[dict[str, Any]]:
    problems: list[dict[str, Any]] = []
    cue_type = _normalized_cue_type(values.get("type"))
    is_broken = _coerce_qlab_bool(values.get("isBroken")) is True
    is_warning = _coerce_qlab_bool(values.get("isWarning")) is True
    if is_broken:
        problems.append({"code": "visual_cue_broken"})
    if is_warning:
        problems.append({"code": "visual_cue_warning"})
    if not stage.get("assigned"):
        problems.append({"code": "cue_without_stage"})
    elif stage.get("topology_available"):
        if not any(isinstance(region.get("route"), dict) and region["route"] for region in stage.get("regions", [])):
            problems.append({"code": "stage_without_routes"})
        if stage.get("multi_output") is True:
            problems.append({"code": "multi_output_stage"})
        if any(region.get("route", {}).get("connected") is False for region in stage.get("regions", [])):
            problems.append({"code": "disconnected_route"})
        if any(region.get("route", {}).get("device", {}).get("connected") is False for region in stage.get("regions", [])):
            problems.append({"code": "disconnected_device"})
    if camera_input is not None and camera_input.get("status") != "valid":
        problems.append({"code": f"camera_input_{camera_input.get('status', 'unknown')}"})
    if cue_type == "video":
        has_target = _coerce_qlab_bool(values.get("fileTargetPresent"))
        if has_target is False:
            problems.append({"code": "video_file_target_missing"})
        elif has_target is True and is_broken:
            problems.append({"code": "video_file_target_unavailable"})
    return problems


def _build_video_summary(
    values: dict[str, Any],
    video_settings: dict[str, Any] | None,
    settings_errors: dict[str, str] | None = None,
) -> dict[str, Any] | None:
    cue_type = _normalized_cue_type(values.get("type"))
    if cue_type not in {"video", "text", "camera"}:
        return None

    settings_errors = settings_errors or {}
    stages = video_settings.get("stages", []) if isinstance(video_settings, dict) else []
    input_patches = video_settings.get("input_patches", []) if isinstance(video_settings, dict) else []
    stage_id = values.get("stageID") or values.get("stage/uniqueID")
    stage_name = values.get("stageName")
    stage_number = values.get("stageNumber")
    matched_stage = next((item for item in stages if stage_id and item.get("uniqueID") == stage_id), None)
    if matched_stage is None and not stage_id and stage_name not in (None, "", "none"):
        matched_stage = next((item for item in stages if item.get("name") == stage_name), None)
    if matched_stage is None and not stage_id and stage_name in (None, "", "none") and stage_number not in (None, "", 0, "0"):
        try:
            matched_stage = stages[int(stage_number) - 1]
        except (TypeError, ValueError, IndexError):
            matched_stage = None

    assigned = bool(stage_id or stage_name not in (None, "", "none") or stage_number not in (None, "", 0, "0"))
    stage_summary: dict[str, Any] = {
        "name": stage_name,
        "uniqueID": stage_id,
        "number": stage_number,
        "size": values.get("stage/size"),
        "assigned": assigned,
        "topology_available": matched_stage is not None,
        "region_count": None,
        "multi_output": None,
        "regions": [],
    }
    if matched_stage is not None:
        stage_summary.update(
            region_count=matched_stage.get("region_count"),
            multi_output=matched_stage.get("multi_output"),
            regions=_lightweight_video_regions(matched_stage.get("regions")),
        )
        stage_summary["size"] = matched_stage.get("size", stage_summary["size"])

    any_settings_data = bool(video_settings and any(video_settings.get(key) for key in ("stages", "routes", "input_patches")))
    if settings_errors:
        topology_status = "partial" if any_settings_data else "unavailable"
    else:
        topology_status = "complete"
    if topology_status == "complete" and assigned and matched_stage is None:
        topology_status = "partial"
    input_patch_available = "video.inputPatchList" not in settings_errors and video_settings is not None
    camera_input = (
        _camera_input_summary(values, input_patches, validation_available=input_patch_available)
        if cue_type == "camera"
        else None
    )
    summary: dict[str, Any] = {
        "cue": _section_values(values, ("number", "name", "type", "uniqueID")),
        "stage": stage_summary,
        "geometry": _section_values(values, ("opacity", "translation", "scale")),
        "video_fx": _video_effects_summary(values.get("videoEffects")),
        "health_status": (values.get("health_summary") or {}).get("status", "unknown"),
        "topology_status": topology_status,
    }
    if settings_errors:
        summary["topology_errors"] = dict(settings_errors)
    if camera_input is not None:
        summary["camera_input"] = camera_input
    summary["problems"] = _visual_problems(values, stage_summary, camera_input)
    if topology_status != "complete":
        summary["problems"].append({"code": f"video_topology_{topology_status}"})
    return summary


def _build_auto_sections(values: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cue_type = values.get("type")
    type_specific_keys = _auto_type_specific_keys(cue_type)
    return {
        "identity": _section_values(values, AUTO_IDENTITY_KEYS),
        "structure": _section_values(values, AUTO_STRUCTURE_KEYS),
        "status": _section_values(values, AUTO_STATUS_KEYS),
        "timing": _section_values(values, AUTO_TIMING_KEYS),
        "targets": _section_values(values, AUTO_TARGET_KEYS),
        "type_specific": _section_values(values, type_specific_keys),
    }


def _empty_auto_sections() -> dict[str, dict[str, Any]]:
    return {
        "identity": {},
        "structure": {},
        "status": {},
        "timing": {},
        "targets": {},
        "type_specific": {},
    }


def _is_active_cue_ref(cue_ref: str) -> bool:
    return _clean_cue_ref(cue_ref).casefold() == "active"
