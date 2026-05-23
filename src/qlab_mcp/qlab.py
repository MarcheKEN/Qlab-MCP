"""Read-only QLab cue information operations."""

from __future__ import annotations

import json
from typing import Any

from .allowlist import properties_for_profile, validate_property_path, validate_value_keys
from .client import QLabOscClient
from .errors import OscTimeoutError, QLabReplyError


def _clean_workspace_id(workspace_id: str) -> str:
    value = workspace_id.strip().strip("/")
    if not value:
        raise ValueError("workspace_id is required")
    if "/" in value:
        raise ValueError("workspace_id must be a workspace unique ID or OSC-compatible display name")
    return value


def _clean_cue_ref(cue_ref: str) -> str:
    value = str(cue_ref).strip().strip("/")
    if not value:
        raise ValueError("cue_ref is required")
    if "/" in value:
        raise ValueError("cue_ref must be a cue number, selected, playhead, playbackPosition, active, or cue ID")
    return value


def _workspace_address(workspace_id: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    return f"/workspace/{workspace}/{command.strip('/')}"


def _cue_address(workspace_id: str, cue_ref: str, command: str) -> str:
    workspace = _clean_workspace_id(workspace_id)
    cue = _clean_cue_ref(cue_ref)
    prefix = "cue_id" if _looks_like_unique_id(cue) else "cue"
    return f"/workspace/{workspace}/{prefix}/{cue}/{command.strip('/')}"


def _looks_like_unique_id(value: str) -> bool:
    # QLab unique IDs are UUID-like. Cue numbers can contain dashes, so require long UUID shape.
    return len(value) >= 32 and value.count("-") >= 4


def _normalize_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        cue_ids: list[str] = []
        unique_id = value.get("uniqueID")
        if unique_id is not None:
            cue_ids.append(str(unique_id))
        children = value.get("cues")
        if children is not None:
            cue_ids.extend(_normalize_id_list(children))
        return cue_ids
    if isinstance(value, list):
        cue_ids: list[str] = []
        for item in value:
            cue_ids.extend(_normalize_id_list(item))
        return cue_ids
    raise ValueError("QLab cue ID response must be a list, object, or string")


CONTAINER_CUE_TYPES = {"Cue List", "Cue Cart", "Group"}
QLAB_VERSION_KEYS = ("qlabVersion", "QLabVersion", "applicationVersion", "version")
OVERVIEW_CUE_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "listName",
    "type",
    "armed",
    "flagged",
    "colorName",
    "colorName/live",
    "isBroken",
    "isWarning",
    "continueMode",
)
CUE_INDEX_COLUMNS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "listName",
    "cue_list_id",
    "parent_id",
    "depth",
    "armed",
    "flagged",
    "colorName",
    "isBroken",
    "isWarning",
    "continueMode",
    "continueModeLabel",
)
CUE_INDEX_VALUE_KEYS = (
    "uniqueID",
    "number",
    "name",
    "displayName",
    "type",
    "listName",
    "armed",
    "flagged",
    "colorName",
    "isBroken",
    "isWarning",
    "continueMode",
)

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
)
AUTO_LIGHT_KEYS = (
    "lightCommandText",
    "parameterValues",
    "parameterFadesEnabled",
    "alwaysCollate",
    "subcontroller",
)
AUTO_NETWORK_KEYS = (
    "networkPatchName",
    "networkPatchNumber",
    "networkPatchID",
    "message",
    "messageError",
)
AUTO_MIDI_KEYS = (
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
)
AUTO_TIMECODE_KEYS = (
    "timecodeString",
    "timecodeFormat",
    "midiPatchName",
    "midiPatchNumber",
    "midiPatchID",
    "audioOutputPatchName",
    "audioOutputPatchNumber",
    "audioOutputPatchID",
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
)
AUTO_TRANSPORT_KEYS = (
    "cueTargetID",
    "cueTargetNumber",
    "currentCueTargetID",
    "currentCueTargetNumber",
    "targetMode",
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
    "reset": AUTO_TRANSPORT_KEYS,
    "devamp": AUTO_TRANSPORT_KEYS,
    "go to": AUTO_TRANSPORT_KEYS,
    "goto": AUTO_TRANSPORT_KEYS,
    "target": AUTO_TRANSPORT_KEYS,
    "arm": AUTO_TRANSPORT_KEYS,
    "disarm": AUTO_TRANSPORT_KEYS,
    "wait": (),
    "memo": (),
    "script": (),
}
WORKSPACE_SETTINGS_SECTIONS = ("audio", "video", "network", "midi", "light", "general")
WORKSPACE_SETTINGS_PROFILES = {"safe", "technical"}
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
ALWAYS_REDACT_KEYS = {
    "passcode",
    "passcodes",
    "password",
    "passwords",
    "secret",
    "secrets",
    "token",
    "tokens",
    "credential",
    "credentials",
}
SAFE_NETWORK_REDACT_KEYS = {
    "address",
    "destination",
    "destinationaddress",
    "host",
    "hostname",
    "interface",
    "ip",
    "ipaddress",
    "network",
    "networkinterface",
    "port",
}
SAFE_DEVICE_REDACT_KEYS = {
    "decklinkhandle",
    "device",
    "deviceid",
    "devicename",
    "destinationinfo",
    "displaymode",
    "displaymodeinfo",
    "screenid",
    "screenserialnumber",
    "serial",
    "serialnumber",
}
REDACTED_VALUE = "[redacted]"


def _normalize_key_name(value: str) -> str:
    return "".join(ch for ch in value.casefold() if ch.isalnum())


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


def _collection_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("items", "patches", "routes", "stages", "maps", "regions", "instruments", "groups"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
        items: list[Any] = []
        for key, item in value.items():
            if isinstance(item, dict):
                normalized = dict(item)
                normalized.setdefault("_key", key)
                items.append(normalized)
            else:
                items.append({"_key": key, "value": item})
        return items
    return [{"value": value}]


def _first_present(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    return None


def _basic_item_summary(item: Any) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {"value": item}
    summary: dict[str, Any] = {}
    for output_key, keys in {
        "name": ("name", "patchName", "routeName", "stageName", "displayName"),
        "uniqueID": ("uniqueID", "id", "patchID", "routeID", "stageID"),
        "type": ("type", "patchType", "deviceType", "kind"),
        "number": ("number", "index"),
        "key": ("_key",),
    }.items():
        value = _first_present(item, keys)
        if value is not None:
            summary[output_key] = value
    return summary


def _setting_ref_values(item: Any) -> list[str]:
    if not isinstance(item, dict):
        return []
    values: list[str] = []
    for key in (
        "uniqueID",
        "id",
        "patchID",
        "routeID",
        "stageID",
        "name",
        "patchName",
        "routeName",
        "stageName",
        "displayName",
        "_key",
    ):
        value = item.get(key)
        if value not in (None, ""):
            values.append(str(value))
    return values


def _select_setting_item(items: list[Any], ref: str | None) -> tuple[Any | None, list[dict[str, Any]], str | None]:
    choices = [_basic_item_summary(item) for item in items]
    if ref is None:
        if len(items) == 1:
            return items[0], choices, None
        if not items:
            return None, choices, "No matching settings items were returned by QLab."
        return None, choices, "Multiple settings items are available; pass ref as a name or uniqueID."

    wanted = str(ref).strip().casefold()
    matches = [item for item in items if any(value.casefold() == wanted for value in _setting_ref_values(item))]
    if len(matches) == 1:
        return matches[0], choices, None
    if len(matches) > 1:
        return None, [_basic_item_summary(item) for item in matches], "Multiple settings items match ref; use a uniqueID."
    return None, choices, f"No settings item matched ref {ref!r}."


def _count_nested(value: Any, names: tuple[str, ...]) -> int | None:
    if isinstance(value, dict):
        for name in names:
            nested = value.get(name)
            if isinstance(nested, (list, dict)):
                return len(_collection_items(nested))
    return None


def _contains_any_key(value: Any, normalized_keys: set[str]) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            if _normalize_key_name(str(key)) in normalized_keys or _contains_any_key(nested, normalized_keys):
                return True
    if isinstance(value, list):
        return any(_contains_any_key(item, normalized_keys) for item in value)
    return False


def _redaction_reason(section: str, key: str, profile: str) -> str | None:
    normalized_key = _normalize_key_name(key)
    if normalized_key in ALWAYS_REDACT_KEYS:
        return "credential"
    if profile != "safe":
        return None
    if section == "network" and normalized_key in SAFE_NETWORK_REDACT_KEYS:
        return "network_destination"
    if section in {"audio", "video", "midi"} and normalized_key in SAFE_DEVICE_REDACT_KEYS:
        return "device_or_route_detail"
    if section == "video" and normalized_key in SAFE_NETWORK_REDACT_KEYS:
        return "video_destination"
    return None


def _redact_payload(
    value: Any,
    *,
    section: str,
    profile: str,
    redactions: list[dict[str, str]],
    path: str = "",
) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, nested in value.items():
            child_path = f"{path}.{key}" if path else str(key)
            reason = _redaction_reason(section, str(key), profile)
            if reason is not None:
                redacted[key] = REDACTED_VALUE
                redactions.append({"section": section, "path": child_path, "reason": reason})
            else:
                redacted[key] = _redact_payload(
                    nested,
                    section=section,
                    profile=profile,
                    redactions=redactions,
                    path=child_path,
                )
        return redacted
    if isinstance(value, list):
        return [
            _redact_payload(
                item,
                section=section,
                profile=profile,
                redactions=redactions,
                path=f"{path}[{index}]",
            )
            for index, item in enumerate(value)
        ]
    return value


def _record_redactions(value: Any, section: str, profile: str, redactions: list[dict[str, str]], path: str) -> None:
    _redact_payload(value, section=section, profile=profile, redactions=redactions, path=path)


def _summarize_audio_patch(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        cue_outputs = _first_present(item, ("cueOutputChannels", "cueOutputCount", "outputs", "outputChannels"))
        if cue_outputs is not None:
            if isinstance(cue_outputs, (list, dict)):
                summary["cue_output_count"] = len(_collection_items(cue_outputs))
            else:
                summary["cue_outputs"] = cue_outputs
        routing = item.get("routing")
        if isinstance(routing, (list, dict)):
            summary["routing_present"] = bool(_collection_items(routing))
            summary["routing_count"] = len(_collection_items(routing))
        elif routing is not None:
            summary["routing_present"] = bool(routing)
        summary["device_present"] = _contains_any_key(item, {"device", "deviceid", "devicename"})
    return summary


def _summarize_audio_map(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        size = item.get("size")
        if size is None and ("width" in item or "height" in item):
            size = {key: item.get(key) for key in ("width", "height") if key in item}
        if size is not None:
            summary["size"] = size
        for output_key, names in {
            "object_count": ("objects", "mapObjects"),
            "filter_count": ("filters",),
            "mark_count": ("marks",),
        }.items():
            count = _count_nested(item, names)
            if count is not None:
                summary[output_key] = count
    return summary


def _summarize_audio_map_mark(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        for key in ("position", "gravity", "shadow"):
            if key in item:
                summary[key] = item[key]
        levels = item.get("levels")
        if isinstance(levels, list):
            summary["level_count"] = len(levels)
            summary["active_output_count"] = sum(1 for level in levels if isinstance(level, (int, float)) and level > -60)
    return summary


def _summarize_audio_map_detail(item: Any) -> dict[str, Any]:
    summary = _summarize_audio_map(item)
    if not isinstance(item, dict):
        return {"summary": summary}
    marks = item.get("marks")
    objects = item.get("objects")
    filters = item.get("filters")
    return {
        "summary": summary,
        "marks": [_summarize_audio_map_mark(mark) for mark in _collection_items(marks)],
        "objects": [_basic_item_summary(obj) for obj in _collection_items(objects)],
        "filters": [_basic_item_summary(filter_item) for filter_item in _collection_items(filters)],
        "technical_payloads_omitted": ["marks[].levels"],
    }


def _summarize_video_route(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        size = _first_present(item, ("size", "resolution", "pixelSize", "routeResolution"))
        if size is not None:
            summary["size"] = size
        connected = item.get("connected")
        if connected is not None:
            summary["connected"] = connected
            if connected is False:
                summary["attention"] = {
                    "status": "disconnected",
                    "message": "Video route is configured but QLab reports it is not connected.",
                }
        destination_info = item.get("destinationInfo")
        if isinstance(destination_info, dict):
            destination_type = destination_info.get("destinationType")
            if destination_type is not None:
                summary["destination_type"] = destination_type
        summary["destination_present"] = _contains_any_key(item, {"destinationinfo", "device", "deviceid", "devicename"})
        summary["guides_present"] = _contains_any_key(item, {"enableguides", "guides"})
    return summary


def _summarize_video_input_patch(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        summary["device_present"] = _contains_any_key(item, SAFE_DEVICE_REDACT_KEYS)
        summary["source_present"] = _contains_any_key(item, {"source", "input", "camera", "capturedevice"})
    return summary


def _summarize_video_stage(item: Any, regions: Any | None = None) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        size = _first_present(item, ("size", "stageSize", "resolution"))
        if size is None and ("width" in item or "height" in item):
            size = {key: item.get(key) for key in ("width", "height") if key in item}
        if size is not None:
            summary["size"] = size
        embedded_region_count = _count_nested(item, ("regions",))
        if embedded_region_count is not None:
            summary["region_count"] = embedded_region_count
        route = None
        item_regions = item.get("regions")
        if isinstance(item_regions, list) and item_regions and isinstance(item_regions[0], dict):
            route = item_regions[0].get("route")
        if isinstance(route, dict):
            route_summary = _summarize_video_route(route)
            if route_summary:
                summary["route"] = route_summary
    if regions is not None:
        summary["region_count"] = len(_collection_items(regions))
    return summary


def _summarize_video_region(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if not isinstance(item, dict):
        return summary
    for key in (
        "boundsOnStage",
        "meshWidth",
        "meshHeight",
        "warpType",
        "autoEdgeBlends",
        "edgeBlendTopPixels",
        "edgeBlendRightPixels",
        "edgeBlendBottomPixels",
        "edgeBlendLeftPixels",
        "edgeBlendPower",
        "edgeBlendGamma",
    ):
        if key in item:
            summary[key] = item[key]
    route = item.get("route")
    if isinstance(route, dict):
        summary["route"] = _summarize_video_route(route)
    for output_key, names in {
        "control_point_count": ("controlPoints",),
        "shadow_control_point_count": ("shadowControlPoints",),
        "mesh_subregion_count": ("meshSubregions",),
    }.items():
        count = _count_nested(item, names)
        if count is not None:
            summary[output_key] = count
    return summary


def _summarize_video_stage_detail(stage: Any, regions: Any | None) -> dict[str, Any]:
    region_summaries = [_summarize_video_region(region) for region in _collection_items(regions)]
    return {
        "stage": _summarize_video_stage(stage, regions),
        "regions": region_summaries,
        "technical_payloads_omitted": [
            "regions[].controlPoints",
            "regions[].shadowControlPoints",
            "regions[].meshSubregions",
            "regions[].route.destinationInfo",
        ],
    }


def _summarize_network_patch(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        destination_count = _count_nested(item, ("destinations", "outputs", "addresses"))
        if destination_count is not None:
            summary["destination_count"] = destination_count
        summary["destination_present"] = _contains_any_key(item, SAFE_NETWORK_REDACT_KEYS)
        summary["passcode_present"] = _contains_any_key(item, {"passcode", "passcodes"})
    return summary


def _summarize_midi_patch(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if isinstance(item, dict):
        summary["destination_present"] = _contains_any_key(item, {"destination", "device", "deviceid", "devicename"})
    return summary


def _summarize_light_patch(value: Any) -> dict[str, Any]:
    summary: dict[str, Any] = {"patch_present": value not in (None, {}, [])}
    if isinstance(value, (list, dict)):
        summary["top_level_count"] = len(_collection_items(value))
    if isinstance(value, dict):
        for output_key, names in {
            "instrument_count": ("instruments", "instrument"),
            "group_count": ("groups", "lightGroups"),
            "definition_count": ("definitions", "instrumentDefinitions", "lightDefinitions"),
        }.items():
            count = _count_nested(value, names)
            if count is not None:
                summary[output_key] = count
    return summary


def _light_groups(value: Any) -> list[Any]:
    if isinstance(value, dict):
        for key in ("groups", "lightGroups"):
            nested = value.get(key)
            if isinstance(nested, list):
                return nested
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict) and isinstance(item.get("instruments"), list)]
    return []


def _light_instrument_identity(item: Any) -> str:
    if not isinstance(item, dict):
        return f"value:{item!r}"
    for key in ("uniqueID", "id"):
        value = item.get(key)
        if value not in (None, ""):
            return f"{key}:{value}"
    name = item.get("name")
    comment = item.get("comment")
    if name not in (None, ""):
        return f"name:{name}:comment:{comment or ''}"
    return json.dumps(_basic_item_summary(item), sort_keys=True, default=str)


def _light_instruments(value: Any) -> list[Any]:
    instruments: list[Any] = []
    if isinstance(value, dict):
        for key in ("instruments", "instrument"):
            nested = value.get(key)
            if isinstance(nested, list):
                instruments.extend(nested)
        for group in _light_groups(value):
            if isinstance(group, dict):
                instruments.extend(_collection_items(group.get("instruments")))
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict) and isinstance(item.get("instruments"), list):
                instruments.extend(_collection_items(item.get("instruments")))
            else:
                instruments.append(item)

    unique_instruments: list[Any] = []
    seen: set[str] = set()
    for instrument in instruments:
        identity = _light_instrument_identity(instrument)
        if identity in seen:
            continue
        seen.add(identity)
        unique_instruments.append(instrument)
    return unique_instruments


def _light_definition_summary(definition: Any) -> dict[str, Any]:
    if not isinstance(definition, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in ("name", "manufacturer", "definitionVersion", "defaultParameter", "isBroken"):
        if key in definition:
            summary[key] = definition[key]
    parameters = definition.get("parameters")
    parameter_items = _collection_items(parameters)
    if parameter_items:
        summary["parameter_count"] = len(parameter_items)
        parameter_names: list[str] = []
        for item in parameter_items:
            if isinstance(item, dict):
                name = item.get("name")
                if name not in (None, "") and str(name) not in parameter_names:
                    parameter_names.append(str(name))
        if parameter_names:
            summary["parameter_names"] = parameter_names
    return summary


def _light_instrument_summary(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if not isinstance(item, dict):
        return summary
    for key in ("comment", "patched", "conflicted"):
        if key in item:
            summary[key] = item[key]
    definition = _light_definition_summary(item.get("definition"))
    if definition:
        summary["definition"] = definition
    parameters = item.get("parameters")
    parameter_items = _collection_items(parameters)
    if parameter_items:
        summary["parameter_count"] = len(parameter_items)
        parameter_names: list[str] = []
        for parameter in parameter_items:
            if isinstance(parameter, dict):
                name = parameter.get("name")
                if name not in (None, "") and str(name) not in parameter_names:
                    parameter_names.append(str(name))
        if parameter_names:
            summary["parameter_names"] = parameter_names
    return summary


def _summarize_light_patch_detail(value: Any) -> dict[str, Any]:
    summary = _summarize_light_patch(value)
    instruments = [_light_instrument_summary(item) for item in _light_instruments(value)]
    groups = []
    for group in _light_groups(value):
        group_summary = _basic_item_summary(group)
        group_instruments = _collection_items(group.get("instruments")) if isinstance(group, dict) else []
        group_summary["instrument_count"] = len(group_instruments)
        group_summary["instrument_names"] = [
            str(item.get("name"))
            for item in group_instruments
            if isinstance(item, dict) and item.get("name") not in (None, "")
        ]
        groups.append(group_summary)

    definition_counts: dict[str, int] = {}
    for instrument in instruments:
        definition = instrument.get("definition")
        if isinstance(definition, dict):
            name = definition.get("name") or "unknown"
            manufacturer = definition.get("manufacturer")
            key = f"{manufacturer} {name}".strip() if manufacturer else str(name)
            definition_counts[key] = definition_counts.get(key, 0) + 1

    summary.setdefault("instrument_count", len(instruments))
    summary.setdefault("group_count", len(groups))

    return {
        "summary": summary,
        "groups": groups,
        "instrument_index": {
            "columns": [
                "name",
                "comment",
                "patched",
                "conflicted",
                "definition",
                "manufacturer",
                "parameter_count",
                "parameter_names",
            ],
            "rows": [
                [
                    instrument.get("name"),
                    instrument.get("comment"),
                    instrument.get("patched"),
                    instrument.get("conflicted"),
                    (instrument.get("definition") or {}).get("name") if isinstance(instrument.get("definition"), dict) else None,
                    (instrument.get("definition") or {}).get("manufacturer")
                    if isinstance(instrument.get("definition"), dict)
                    else None,
                    instrument.get("parameter_count"),
                    instrument.get("parameter_names", []),
                ]
                for instrument in instruments
            ],
        },
        "definition_counts": dict(sorted(definition_counts.items())),
        "technical_payloads_omitted": [
            "instrument.definition.parameters",
            "instrument.parameters[].definitionParameter",
        ],
    }


def _summarize_setting_detail_item(section: str, kind: str, item: Any) -> dict[str, Any]:
    if section == "audio" and kind in {"output_patch", "input_patch"}:
        return _summarize_audio_patch(item)
    if section == "audio" and kind == "audio_map":
        return _summarize_audio_map_detail(item)
    if section == "video" and kind == "route":
        summary = _summarize_video_route(item)
        if isinstance(item, dict) and "destinationInfo" in item:
            summary["technical_payloads_omitted"] = ["destinationInfo"]
        return summary
    if section == "video" and kind == "video_input_patch":
        return _summarize_video_input_patch(item)
    if section == "network" and kind == "network_patch":
        return _summarize_network_patch(item)
    if section == "midi" and kind == "midi_patch":
        return _summarize_midi_patch(item)
    return _basic_item_summary(item)


def _workspace_overview_metadata(workspace: Any) -> dict[str, Any]:
    if not isinstance(workspace, dict):
        return {"value": workspace}

    name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
    qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)

    return {
        "uniqueID": workspace.get("uniqueID"),
        "name": name,
        "displayName": workspace.get("displayName"),
        "qlab_version": qlab_version,
        "metadata": dict(workspace),
    }


def _known_child_count(cue: Any) -> int | None:
    if not isinstance(cue, dict):
        return None
    children = cue.get("cues")
    if isinstance(children, list):
        return len(children)
    return None


def _cue_overview_node(cue: Any) -> dict[str, Any]:
    if not isinstance(cue, dict):
        return {"value": cue, "child_count": 0, "children": []}
    node = {key: cue[key] for key in OVERVIEW_CUE_KEYS if key in cue}
    node = _derive_profile_fields("overview", node)
    label = node.get("displayName") or node.get("name") or node.get("listName") or node.get("number") or node.get("uniqueID")
    if label is not None:
        node["label"] = str(label)
    node["child_count"] = _known_child_count(cue)
    node["children"] = []
    return node


def _is_container_cue(cue: dict[str, Any]) -> bool:
    return cue.get("type") in CONTAINER_CUE_TYPES


def _count_stat(stats: dict[str, Any], bucket: str, key: Any) -> None:
    normalized = "unknown" if key in (None, "") else str(key)
    stats[bucket][normalized] = stats[bucket].get(normalized, 0) + 1


def _record_cue_stats(stats: dict[str, Any], cue: dict[str, Any]) -> None:
    _count_stat(stats, "types", cue.get("type"))
    _count_stat(stats, "colors", cue.get("colorName"))
    if cue.get("armed") is True:
        stats["armed"] += 1
    elif cue.get("armed") is False:
        stats["disarmed"] += 1
    if cue.get("flagged") is True:
        stats["flagged"] += 1


def _connection_metadata(client: QLabOscClient) -> dict[str, Any]:
    return {
        "transport": "udp",
        "host": client.config.host,
        "osc_port": client.config.osc_port,
        "reply_port": client.config.reply_port,
        "timeout": client.config.timeout,
    }


def _workspace_candidate(workspace: Any) -> dict[str, Any]:
    if not isinstance(workspace, dict):
        return {"value": workspace}
    name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
    qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)
    return {
        "uniqueID": workspace.get("uniqueID"),
        "name": name,
        "displayName": workspace.get("displayName"),
        "qlab_version": qlab_version,
        "metadata": dict(workspace),
    }


def _base_permissions() -> dict[str, Any]:
    undetectable_reason = (
        "QLab does not expose passcode edit/control scopes through a read-only OSC query; "
        "proving this permission would require sending an edit or control command."
    )
    return {
        "probe_mode": "read_only",
        "view": {
            "ok": None,
            "status": "not_checked",
            "method": "cueLists/shallow",
            "safe_to_probe": True,
        },
        "edit": {
            "ok": None,
            "status": "not_checked",
            "method": None,
            "safe_to_probe": False,
            "reason": undetectable_reason,
        },
        "control": {
            "ok": None,
            "status": "not_checked",
            "method": None,
            "safe_to_probe": False,
            "reason": undetectable_reason,
        },
    }


def _base_capabilities() -> dict[str, Any]:
    return {
        "list_workspaces": False,
        "resolve_workspace": False,
        "read_workspace": False,
        "workspace_overview": False,
        "workspace_settings": False,
        "workspace_setting_details": False,
        "query_cues": False,
        "cue_details": False,
        "edit": None,
        "control": None,
    }


def _permission_warning() -> str:
    return (
        "Edit and control permissions are not checked by read-only diagnostics because QLab does not "
        "publish passcode scopes over OSC; confirming them would require an edit/control probe."
    )


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


def _matches_bool_filter(actual: Any, expected: Any) -> bool:
    normalized = _coerce_qlab_bool(actual)
    return normalized is not None and normalized is _parse_bool_filter(expected)


def _is_positive_number(value: Any) -> bool:
    if isinstance(value, bool) or value in (None, ""):
        return False
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def _flatten_cue_refs(
    value: Any,
    parent_id: str | None = None,
    cue_list_id: str | None = None,
    depth: int = 0,
) -> list[dict[str, Any]]:
    if value is None:
        return []
    if isinstance(value, str):
        return [{"uniqueID": value, "parent_id": parent_id, "cue_list_id": cue_list_id, "depth": depth}]
    if isinstance(value, dict):
        cue_refs: list[dict[str, Any]] = []
        unique_id_value = value.get("uniqueID")
        current_id = str(unique_id_value) if unique_id_value is not None else None
        current_cue_list_id = current_id if parent_id is None and current_id else cue_list_id
        if current_id:
            cue_refs.append(
                {
                    "uniqueID": current_id,
                    "parent_id": parent_id,
                    "cue_list_id": current_cue_list_id,
                    "depth": depth,
                }
            )
        children = value.get("cues")
        if children is not None:
            cue_refs.extend(
                _flatten_cue_refs(
                    children,
                    parent_id=current_id,
                    cue_list_id=current_cue_list_id,
                    depth=depth + 1,
                )
            )
        return cue_refs
    if isinstance(value, list):
        cue_refs: list[dict[str, Any]] = []
        for item in value:
            cue_refs.extend(
                _flatten_cue_refs(
                    item,
                    parent_id=parent_id,
                    cue_list_id=cue_list_id,
                    depth=depth,
                )
            )
        return cue_refs
    raise ValueError("QLab cue ID response must be a list, object, or string")


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
    if normalized == "type_specific":
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
    cue_type = str(values.get("type") or "").strip()
    normalized_type = cue_type.casefold()
    messages: list[str] = []

    if is_broken and normalized_type in {"cue list", "cue cart", "group"}:
        messages.append("Container reports a broken state, likely inherited from one or more broken child cues.")
    elif is_broken and values.get("fileTargetPresent"):
        messages.append("File target exists but the cue is broken; likely missing, unavailable, or incompatible media.")
    elif is_broken:
        messages.append("Cue reports a broken state.")

    if is_warning:
        messages.append("Cue reports a warning state.")

    message_error = values.get("messageError")
    if message_error not in (None, ""):
        messages.append(f"Network/message error reported: {message_error}")

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

    return {"status": status, "messages": messages}


def _normalized_cue_type(cue_type: Any) -> str:
    return str(cue_type or "").strip().casefold()


def _auto_type_specific_keys(cue_type: Any) -> tuple[str, ...]:
    return tuple(AUTO_TYPE_SPECIFIC_KEYS.get(_normalized_cue_type(cue_type), ()))


def _section_values(values: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: values[key] for key in keys if key in values}


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


def _cue_index_row(cue_ref: dict[str, Any], values: dict[str, Any]) -> list[Any]:
    cue = _derive_profile_fields("cue_index", values)
    cue.setdefault("uniqueID", cue_ref.get("uniqueID"))
    cue["cue_list_id"] = cue_ref.get("cue_list_id")
    cue["parent_id"] = cue_ref.get("parent_id")
    cue["depth"] = cue_ref.get("depth")
    return [cue.get(column) for column in CUE_INDEX_COLUMNS]


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


class QLabReader:
    def __init__(self, client: QLabOscClient | None = None):
        self.client = client or QLabOscClient()

    def get_workspaces(self) -> dict[str, Any]:
        reply = self.client.request("/workspaces")
        return {"workspaces": reply.data, "status": reply.status}

    def check_connection(
        self,
        workspace_id: str | None = None,
        require_read_access: bool = True,
    ) -> dict[str, Any]:
        passcode_configured = bool(self.client.config.passcode)
        permissions = _base_permissions()
        capabilities = _base_capabilities()
        warnings: list[str] = [_permission_warning()]
        checks: dict[str, Any] = {
            "workspaces": None,
            "workspace_resolution": None,
            "read_access": None,
        }
        base_result: dict[str, Any] = {
            "ok": False,
            "status": "unknown",
            "qlab_reachable": False,
            "workspace_available": False,
            "workspace_readable": False,
            "workspace_id": None,
            "workspace_name": None,
            "qlab_version": None,
            "workspace_count": 0,
            "available_workspaces": [],
            "passcode_configured": passcode_configured,
            "passcode_status": None,
            "message": "",
            "connection": _connection_metadata(self.client),
            "permissions": permissions,
            "capabilities": capabilities,
            "checks": checks,
            "warnings": warnings,
        }

        try:
            workspaces_result = self.get_workspaces()
        except Exception as exc:
            checks["workspaces"] = {"ok": False, "error": str(exc)}
            return {
                **base_result,
                "status": "qlab_unreachable",
                "message": "QLab did not respond to /workspaces over OSC.",
            }

        workspaces = workspaces_result.get("workspaces") or []
        workspace_count = len(workspaces) if isinstance(workspaces, list) else 0
        checks["workspaces"] = {
            "ok": True,
            "reply_status": workspaces_result.get("status"),
            "workspace_count": workspace_count,
        }
        base_result.update(
            {
                "qlab_reachable": True,
                "workspace_count": workspace_count,
            }
        )
        capabilities["list_workspaces"] = True

        if not isinstance(workspaces, list):
            checks["workspace_resolution"] = {"ok": False, "error": "QLab workspaces response was not a list."}
            return {
                **base_result,
                "status": "invalid_workspaces_response",
                "message": "QLab responded, but /workspaces did not return the expected list shape.",
            }

        available_workspaces = [_workspace_candidate(item) for item in workspaces]
        base_result["available_workspaces"] = available_workspaces

        if workspace_count == 0:
            checks["workspace_resolution"] = {"ok": False, "error": "No open QLab workspaces were returned."}
            return {
                **base_result,
                "status": "no_workspace",
                "message": "QLab is reachable, but no open workspace was returned by /workspaces.",
            }

        if workspace_id is None and workspace_count > 1:
            checks["workspace_resolution"] = {
                "ok": False,
                "error": "Multiple workspaces are open; pass workspace_id to choose one.",
            }
            return {
                **base_result,
                "workspace_available": True,
                "status": "workspace_ambiguous",
                "message": "QLab is reachable, but multiple workspaces are open and no workspace_id was provided.",
            }

        try:
            if workspace_id is not None:
                requested = _clean_workspace_id(workspace_id)
                workspace = next(
                    (
                        item
                        for item in workspaces
                        if isinstance(item, dict)
                        and (item.get("uniqueID") == requested or item.get("displayName") == requested)
                    ),
                    None,
                )
                if workspace is None:
                    raise ValueError(f"Workspace not found: {requested}")
            else:
                workspace = self._resolve_workspace(workspaces, workspace_id)
            resolved_workspace_id = _clean_workspace_id(workspace.get("uniqueID") or workspace_id or "")
        except Exception as exc:
            checks["workspace_resolution"] = {"ok": False, "error": str(exc)}
            return {
                **base_result,
                "status": "workspace_not_found",
                "message": "QLab is reachable, but the requested workspace could not be resolved.",
            }

        workspace_name = workspace.get("displayName") or workspace.get("name") or workspace.get("fileName")
        qlab_version = next((workspace.get(key) for key in QLAB_VERSION_KEYS if workspace.get(key)), None)
        checks["workspace_resolution"] = {
            "ok": True,
            "workspace_id": resolved_workspace_id,
            "workspace_name": workspace_name,
        }
        capabilities["resolve_workspace"] = True
        base_result.update(
            {
                "workspace_available": True,
                "workspace_id": resolved_workspace_id,
                "workspace_name": workspace_name,
                "qlab_version": qlab_version,
            }
        )

        if not require_read_access:
            checks["read_access"] = {"ok": None, "skipped": True, "reason": "require_read_access is false"}
            permissions["view"] = {
                **permissions["view"],
                "ok": None,
                "status": "skipped",
                "reason": "require_read_access is false",
            }
            return {
                **base_result,
                "ok": True,
                "status": "ready",
                "message": "QLab is reachable and a workspace is available; read access was not checked.",
            }

        try:
            cue_lists = self.get_cue_lists(resolved_workspace_id, include_children=False)["cue_lists"]
        except QLabReplyError as exc:
            passcode_status = exc.status
            checks["read_access"] = {
                "ok": False,
                "status": exc.status,
                "address": exc.address,
                "data": exc.data,
                "error": str(exc),
            }
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": exc.status,
                "address": exc.address,
                "error": str(exc),
            }
            return {
                **base_result,
                "passcode_status": passcode_status,
                "status": "workspace_denied" if exc.status == "denied" else "workspace_read_error",
                "message": "QLab is reachable, but the workspace denied the cue-list read check."
                if exc.status == "denied"
                else "QLab is reachable, but the workspace read check failed.",
            }
        except OscTimeoutError as exc:
            checks["read_access"] = {"ok": False, "status": "timeout", "error": str(exc)}
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": "timeout",
                "error": str(exc),
            }
            return {
                **base_result,
                "status": "workspace_read_timeout",
                "message": "QLab is reachable, but the workspace read check timed out.",
            }
        except Exception as exc:
            checks["read_access"] = {"ok": False, "status": "error", "error": str(exc)}
            permissions["view"] = {
                **permissions["view"],
                "ok": False,
                "status": "error",
                "error": str(exc),
            }
            return {
                **base_result,
                "status": "workspace_read_error",
                "message": "QLab is reachable, but the workspace read check failed.",
            }

        checks["read_access"] = {
            "ok": True,
            "method": "cueLists/shallow",
            "cue_list_count": len(cue_lists) if isinstance(cue_lists, list) else None,
        }
        permissions["view"] = {
            "ok": True,
            "status": "confirmed",
            "method": "cueLists/shallow",
            "safe_to_probe": True,
            "cue_list_count": len(cue_lists) if isinstance(cue_lists, list) else None,
        }
        capabilities.update(
            {
                "read_workspace": True,
                "workspace_overview": True,
                "workspace_settings": True,
                "workspace_setting_details": True,
                "query_cues": True,
                "cue_details": True,
            }
        )
        return {
            **base_result,
            "ok": True,
            "status": "ready",
            "workspace_readable": True,
            "passcode_status": "accepted" if passcode_configured else None,
            "message": "QLab is reachable, a workspace is open, and the MCP can read cue lists.",
        }

    def get_workspace_overview(
        self,
        workspace_id: str | None = None,
        max_depth: int = 2,
        max_cues: int = 1000,
        include_live_state: bool = False,
        include_cue_index: bool = True,
        max_index_cues: int = 1000,
        include_selected_and_running: bool | None = None,
    ) -> dict[str, Any]:
        if include_selected_and_running is not None:
            include_live_state = include_selected_and_running
        if max_depth < 0:
            raise ValueError("max_depth must be 0 or greater")
        if max_cues < 1:
            raise ValueError("max_cues must be 1 or greater")
        if max_index_cues < 1:
            raise ValueError("max_index_cues must be 1 or greater")

        workspaces_result = self.get_workspaces()
        workspaces = workspaces_result.get("workspaces") or []
        workspace = self._resolve_workspace(workspaces, workspace_id)
        resolved_workspace_id = _clean_workspace_id(workspace.get("uniqueID") or workspace_id or "")

        cue_lists = self.get_cue_lists(resolved_workspace_id, include_children=False)["cue_lists"] or []
        id_reply = self.client.request(
            _workspace_address(resolved_workspace_id, "cueLists/uniqueIDs"),
            workspace_id=resolved_workspace_id,
        )
        cue_ids = _normalize_id_list(id_reply.data)
        cue_refs = _flatten_cue_refs(id_reply.data)

        summary: dict[str, Any] = {
            "total_cue_ids": len(cue_ids),
            "inspected_cues": 0,
            "cue_lists": len(cue_lists),
            "types": {},
            "colors": {},
            "armed": 0,
            "disarmed": 0,
            "flagged": 0,
            "max_depth_returned": 0,
        }
        limits: dict[str, Any] = {
            "max_depth": max_depth,
            "max_cues": max_cues,
            "truncated": False,
            "truncation_reasons": [],
        }
        errors: dict[str, str] = {}

        def mark_truncated(reason: str) -> None:
            limits["truncated"] = True
            if reason not in limits["truncation_reasons"]:
                limits["truncation_reasons"].append(reason)

        def build_node(cue: Any, depth: int) -> dict[str, Any] | None:
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                return None

            node = _cue_overview_node(cue)
            node["depth"] = depth
            summary["inspected_cues"] += 1
            summary["max_depth_returned"] = max(summary["max_depth_returned"], depth)
            _record_cue_stats(summary, node)

            cue_id = node.get("uniqueID")
            if not cue_id:
                node["child_count"] = node["child_count"] or 0
                return node
            if not _is_container_cue(node):
                node["child_count"] = node["child_count"] or 0
                return node
            if depth >= max_depth:
                node["children_truncated"] = True
                mark_truncated("max_depth")
                return node

            try:
                children = self.get_cue_children(
                    resolved_workspace_id,
                    str(cue_id),
                    shallow=True,
                    ids_only=False,
                )["children"]
            except Exception as exc:
                errors[str(cue_id)] = str(exc)
                return node

            if not isinstance(children, list):
                node["child_count"] = 0
                return node

            node["child_count"] = len(children)
            child_nodes: list[dict[str, Any]] = []
            for child in children:
                child_node = build_node(child, depth + 1)
                if child_node is not None:
                    child_nodes.append(child_node)
                if summary["inspected_cues"] >= max_cues:
                    mark_truncated("max_cues")
                    break
            node["children"] = child_nodes
            if len(child_nodes) < len(children):
                node["children_truncated"] = True
            return node

        overview_cue_lists: list[dict[str, Any]] = []
        for cue_list in cue_lists:
            node = build_node(cue_list, 0)
            if node is not None:
                overview_cue_lists.append(node)
            if summary["inspected_cues"] >= max_cues:
                mark_truncated("max_cues")
                break

        live_state = None
        if include_live_state:
            live_state = {
                "selected_cues": self.get_selected_cues(
                    resolved_workspace_id,
                    include_children=False,
                )["selected_cues"],
                "running_cues": self.get_running_cues(
                    resolved_workspace_id,
                    include_paused=True,
                    include_children=False,
                )["running_cues"],
                "running_includes_paused": True,
            }

        warnings: list[str] = []
        if limits["truncated"]:
            reasons = ", ".join(limits["truncation_reasons"])
            if include_cue_index:
                warnings.append(
                    "Tree preview is partial"
                    + (f" ({reasons})" if reasons else "")
                    + "; cue_index may still contain the compact workspace map up to max_index_cues."
                )
            else:
                warnings.append(
                    "Tree preview is partial"
                    + (f" ({reasons})" if reasons else "")
                    + "; increase max_depth or max_cues for a deeper tree scan."
                )

        result = {
            "workspace_id": resolved_workspace_id,
            "workspace": _workspace_overview_metadata(workspace),
            "cue_count": len(cue_ids),
            "summary": summary,
            "cue_lists": overview_cue_lists,
            "limits": limits,
            "warnings": warnings,
            "errors": errors or None,
        }
        if live_state is not None:
            result["live_state"] = live_state
        if include_cue_index:
            index_errors: dict[str, str] = {}
            index_rows: list[list[Any]] = []
            index_keys = validate_value_keys(CUE_INDEX_VALUE_KEYS)
            for cue_ref in cue_refs[:max_index_cues]:
                cue_id = cue_ref.get("uniqueID")
                if not cue_id:
                    continue
                try:
                    values = self.read_cue_values(resolved_workspace_id, str(cue_id), index_keys)["values"]
                    if not isinstance(values, dict):
                        raise ValueError("QLab valuesForKeys response must be an object")
                except Exception as exc:
                    index_errors[str(cue_id)] = str(exc)
                    continue
                index_rows.append(_cue_index_row(cue_ref, values))

            result["cue_index"] = {
                "columns": list(CUE_INDEX_COLUMNS),
                "rows": index_rows,
                "total_cue_ids": len(cue_refs),
                "indexed_count": len(index_rows),
                "truncated": len(cue_refs) > max_index_cues,
                "max_index_cues": max_index_cues,
                "errors": index_errors or None,
            }
        return result

    def _resolve_workspace(self, workspaces: Any, workspace_id: str | None) -> dict[str, Any]:
        if not isinstance(workspaces, list):
            raise ValueError("QLab workspaces response must be a list")
        if workspace_id is None:
            if len(workspaces) != 1:
                raise ValueError("workspace_id is required when QLab has zero or multiple open workspaces")
            workspace = workspaces[0]
            if not isinstance(workspace, dict):
                raise ValueError("QLab workspace entry must be an object")
            return workspace

        requested = _clean_workspace_id(workspace_id)
        for workspace in workspaces:
            if not isinstance(workspace, dict):
                continue
            if workspace.get("uniqueID") == requested or workspace.get("displayName") == requested:
                return workspace
        return {"uniqueID": requested}

    def get_cue_lists(self, workspace_id: str, include_children: bool = False) -> dict[str, Any]:
        command = "cueLists" if include_children else "cueLists/shallow"
        return self._workspace_data(workspace_id, command, "cue_lists")

    def get_workspace_cue_ids(self, workspace_id: str, include_children: bool = True) -> dict[str, Any]:
        command = "cueLists/uniqueIDs" if include_children else "cueLists/uniqueIDs/shallow"
        reply = self.client.request(_workspace_address(workspace_id, command), workspace_id=workspace_id)
        cue_ids = _normalize_id_list(reply.data)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "include_children": include_children,
            "cue_count": len(cue_ids),
            "cue_ids": cue_ids,
        }

    def get_workspace_cue_inventory(
        self,
        workspace_id: str,
        include_details: bool = False,
        detail_profile: str = "basic_safe",
    ) -> dict[str, Any]:
        id_result = self.get_workspace_cue_ids(workspace_id, include_children=True)
        result: dict[str, Any] = {
            "workspace_id": id_result["workspace_id"],
            "cue_count": id_result["cue_count"],
            "cue_ids": id_result["cue_ids"],
        }
        if not include_details:
            return result

        cues: list[dict[str, Any]] = []
        errors: dict[str, str] = {}
        for cue_id in id_result["cue_ids"]:
            try:
                cues.append(self.get_cue_details(workspace_id, cue_id, detail_profile))
            except Exception as exc:
                errors[cue_id] = str(exc)
        result["detail_profile"] = detail_profile
        result["cues"] = cues
        if errors:
            result["errors"] = errors
        return result

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
            return detail

        summary = _summarize_light_patch(patch)
        if read_transport:
            summary["read_transport"] = read_transport
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
        if max_results > 500:
            raise ValueError("max_results must be 500 or lower")
        if max_cues_scanned < 1:
            raise ValueError("max_cues_scanned must be 1 or greater")
        if max_cues_scanned > 500:
            raise ValueError("max_cues_scanned must be 500 or lower")

        filters = [
            _normalize_query_filter(primary_filter, primary_value),
            *_normalize_optional_filters(optional_filters),
        ]

        response = self.client.request(_workspace_address(workspace_id, "cueLists/uniqueIDs"), workspace_id=workspace_id)
        cue_refs = _flatten_cue_refs(response.data)
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
                values = self.read_cue_values(workspace_id, str(cue_id), keys)["values"]
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

        truncated = scanned_count < len(cue_refs) or matched_count > len(cues)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "filters": filters,
            "profile": profile,
            "scanned_count": scanned_count,
            "matched_count": matched_count,
            "returned_count": len(cues),
            "total_cue_ids": len(cue_refs),
            "truncated": truncated,
            "limits": {
                "max_results": max_results,
                "max_cues_scanned": max_cues_scanned,
            },
            "cues": cues,
            "errors": errors or None,
        }

    def get_selected_cues(self, workspace_id: str, include_children: bool = False) -> dict[str, Any]:
        command = "selectedCues" if include_children else "selectedCues/shallow"
        return self._workspace_data(workspace_id, command, "selected_cues")

    def get_running_cues(
        self,
        workspace_id: str,
        include_paused: bool = True,
        include_children: bool = False,
    ) -> dict[str, Any]:
        base = "runningOrPausedCues" if include_paused else "runningCues"
        command = base if include_children else f"{base}/shallow"
        return self._workspace_data(workspace_id, command, "running_cues")

    def get_cue_children(
        self,
        workspace_id: str,
        cue_ref: str,
        shallow: bool = False,
        ids_only: bool = False,
    ) -> dict[str, Any]:
        suffix = "children"
        if ids_only:
            suffix += "/uniqueIDs"
        if shallow:
            suffix += "/shallow"
        reply = self.client.request(_cue_address(workspace_id, cue_ref, suffix), workspace_id=workspace_id)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "children": reply.data,
            "ids_only": ids_only,
            "shallow": shallow,
        }

    def _read_cue_values_with_fallback(
        self,
        workspace_id: str,
        cue_ref: str,
        keys: list[str] | tuple[str, ...],
        errors: dict[str, str],
        error_key: str = "valuesForKeys",
    ) -> dict[str, Any]:
        if not keys:
            return {}
        normalized_keys = validate_value_keys(keys)
        try:
            batched_values = self.read_cue_values(workspace_id, cue_ref, normalized_keys)["values"]
            if not isinstance(batched_values, dict):
                raise ValueError("QLab valuesForKeys response must be an object")
            return batched_values
        except Exception as exc:
            errors[error_key] = str(exc)
            values: dict[str, Any] = {}
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
                active_values = self.read_cue_values(workspace_id, cue_ref, common_keys)["values"]
                if not isinstance(active_values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
                values = active_values
            except QLabReplyError as exc:
                if exc.status == "error":
                    return self._empty_active_details(workspace_id, cue_ref, "auto")
                raise
        else:
            values = self._read_cue_values_with_fallback(workspace_id, cue_ref, common_keys, errors)
        values = _derive_profile_fields("auto", values)

        type_specific_keys = [
            key for key in _auto_type_specific_keys(values.get("type")) if key not in values
        ]
        if type_specific_keys:
            type_specific_values = self._read_cue_values_with_fallback(
                workspace_id,
                cue_ref,
                type_specific_keys,
                errors,
                error_key="valuesForKeys:type_specific",
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
        if profile.strip().lower() == "auto":
            return self._get_auto_cue_details(workspace_id, cue_ref)

        keys = list(properties_for_profile(profile))
        errors: dict[str, str] = {}
        if _is_active_cue_ref(cue_ref):
            try:
                values = self.read_cue_values(workspace_id, cue_ref, keys)["values"]
                if not isinstance(values, dict):
                    raise ValueError("QLab valuesForKeys response must be an object")
            except QLabReplyError as exc:
                if exc.status == "error":
                    return self._empty_active_details(workspace_id, cue_ref, profile)
                raise
        else:
            values = self._read_cue_values_with_fallback(workspace_id, cue_ref, keys, errors)
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

    def read_cue_property(self, workspace_id: str, cue_ref: str, property_path: str) -> dict[str, Any]:
        prop = validate_property_path(property_path)
        reply = self.client.request(_cue_address(workspace_id, cue_ref, prop), workspace_id=workspace_id)
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "property": prop,
            "value": reply.data,
        }

    def read_cue_values(self, workspace_id: str, cue_ref: str, keys: list[str]) -> dict[str, Any]:
        normalized_keys = validate_value_keys(keys)
        reply = self.client.request(
            _cue_address(workspace_id, cue_ref, "valuesForKeys"),
            json.dumps(normalized_keys),
            workspace_id=workspace_id,
        )
        return {
            "workspace_id": _clean_workspace_id(workspace_id),
            "cue_ref": _clean_cue_ref(cue_ref),
            "keys": normalized_keys,
            "values": reply.data,
        }

    def _workspace_data(self, workspace_id: str, command: str, key: str) -> dict[str, Any]:
        reply = self.client.request(_workspace_address(workspace_id, command), workspace_id=workspace_id)
        return {"workspace_id": _clean_workspace_id(workspace_id), key: reply.data}
