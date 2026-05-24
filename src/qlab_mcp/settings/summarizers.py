"""Compact summarizers for QLab workspace settings payloads."""

from __future__ import annotations

from typing import Any

from .redaction import SAFE_DEVICE_REDACT_KEYS, SAFE_NETWORK_REDACT_KEYS, _contains_any_key


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


def _first_present_case_insensitive(mapping: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in mapping and mapping[key] not in (None, ""):
            return mapping[key]
    normalized_keys = {key.casefold(): key for key in keys}
    for key, value in mapping.items():
        if str(key).casefold() in normalized_keys and value not in (None, ""):
            return value
    return None


def _light_patch_conflicted(item: dict[str, Any]) -> Any:
    return _first_present_case_insensitive(item, ("conflicted", "conflict", "conflicts"))


def _light_instrument_summary(item: Any) -> dict[str, Any]:
    summary = _basic_item_summary(item)
    if not isinstance(item, dict):
        return summary
    for key in ("comment", "patched"):
        if key in item:
            summary[key] = item[key]
    conflicted = _light_patch_conflicted(item)
    if conflicted is not None:
        summary["conflicted"] = conflicted
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
