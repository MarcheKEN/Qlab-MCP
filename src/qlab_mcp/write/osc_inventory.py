"""QLab OSC cue update inventory derived from the official dictionary text."""

from __future__ import annotations

import re
from typing import Any


SECTION_TITLES: tuple[tuple[str, str], ...] = (
    ("common/global cue properties", "Cue messages"),
    ("Group/List/Cart", "Group cue/List/Cart messages"),
    ("Audio", "Audio cue messages"),
    ("Mic", "Mic cue messages"),
    ("Video", "Video cue messages"),
    ("Camera", "Camera cue messages"),
    ("Text", "Text cue messages"),
    ("Light", "Light cue messages"),
    ("Fade", "Fade cue messages"),
    ("Network", "Network cue messages"),
    ("MIDI", "MIDI cue messages"),
    ("MIDI File", "MIDI file cue messages"),
    ("Timecode", "Timecode cue messages"),
    ("Reset", "Reset cue messages"),
    ("Devamp", "Devamp cue messages"),
    ("Script", "Script cue messages"),
)

SECTION_PROFILE = {
    "common/global cue properties": "common",
    "Group/List/Cart": "group_basic",
    "Audio": "audio_basic",
    "Mic": "mic_basic",
    "Video": "video_basic",
    "Camera": "camera_basic",
    "Text": "text_basic",
    "Light": "light_basic",
    "Fade": "fade_basic",
    "Network": "network_basic",
    "MIDI": "midi_basic",
    "MIDI File": "midi_file_basic",
    "Timecode": "timecode_basic",
    "Reset": "reset_basic",
    "Devamp": "devamp_basic",
    "Script": "script_basic",
}

MUTATING_ACTIONS = {
    "addSliceMarker",
    "audioOutputPatch/mute/clear",
    "audioOutputPatch/reset",
    "audioOutputPatch/routing/reset",
    "audioOutputPatch/solo/clear",
    "collateAndStart",
    "compileSource",
    "deleteSliceMarker",
    "deleteSliceMarkers",
    "mute/channel/clear",
    "mute/clear",
    "mute/object/clear",
    "prune",
    "pruneCommands",
    "removeLightCommandsMatching",
    "replaceLightCommand",
    "resetRotation",
    "safeSort",
    "safeSortCommands",
    "setDefaultLevels",
    "setLight",
    "setSilentLevels",
    "solo/channel/clear",
    "solo/clear",
    "solo/object/clear",
    "stage/region/{}/moveBy",
    "stage/region/{}/resetControlPoints",
    "stage/regionID/{}/moveBy",
    "stage/regionID/{}/resetControlPoints",
    "stage/regionIndex/{}/moveBy",
    "stage/regionIndex/{}/resetControlPoints",
    "videoEffect/{}/delete",
    "videoEffect/{}/move",
    "videoEffectIndex/{}/delete",
    "videoEffectIndex/{}/move",
    "videoEffects/add",
    "videoEffects/insert",
}


def extract_cue_osc_inventory(dictionary_text: str) -> list[dict[str, Any]]:
    """Return writable/action cue OSC routes grouped by official QLab section."""
    lines = dictionary_text.splitlines()
    ranges = _section_ranges(lines)
    entries: list[dict[str, Any]] = []
    for start, end, section in ranges:
        line_index = start + 1
        while line_index < end:
            if not lines[line_index].startswith("/cue/{cue_number}"):
                line_index += 1
                continue
            route_group: list[str] = []
            group_index = line_index
            while group_index < end and lines[group_index].startswith("/cue/{cue_number}"):
                route_group.append(_route_only(lines[group_index]))
                group_index += 1
            access_row = _access_row(lines, group_index, end)
            writable = "read/write" in access_row
            action = any(_is_mutating_action(_suffix(route)) for route in route_group)
            if writable or action:
                for route in route_group:
                    if route.endswith("/live"):
                        continue
                    suffix = _suffix(route)
                    entries.append(
                        {
                            "section": section,
                            "profile": SECTION_PROFILE[section],
                            "route": route,
                            "property": suffix,
                            "normalized_property": normalize_registry_key(suffix),
                            "args": _arg_names(lines[line_index]),
                            "access": access_row,
                            "kind": "action" if action and not writable else "property",
                            "line": line_index + 1,
                            "live": any(candidate.endswith("/live") for candidate in route_group),
                        }
                    )
            line_index = group_index
    return entries


def registry_coverage(inventory: list[dict[str, Any]], catalog: dict[str, Any]) -> list[dict[str, Any]]:
    """Annotate inventory rows with registry coverage status."""
    indexed = _registry_index(catalog)
    coverage: list[dict[str, Any]] = []
    for entry in inventory:
        profile = entry["profile"]
        keys = _coverage_keys(entry["property"])
        match = _best_match(profile, keys, indexed)
        coverage.append({**entry, **match})
    return coverage


def coverage_summary(coverage: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for entry in coverage:
        section = entry["section"]
        status = entry["registry_status"]
        summary.setdefault(section, {})
        summary[section][status] = summary[section].get(status, 0) + 1
    return summary


def normalize_registry_key(value: str) -> str:
    route = value.strip().split()[0].removesuffix("/live")
    return re.sub(r"\{[^}]+\}", "{}", route)


def _section_ranges(lines: list[str]) -> list[tuple[int, int, str]]:
    starts: list[tuple[int, str]] = []
    for section, title in SECTION_TITLES:
        for index, line in enumerate(lines):
            if line.strip() == title:
                starts.append((index, section))
                break
    starts.sort()
    return [
        (start, starts[index + 1][0] if index + 1 < len(starts) else len(lines), section)
        for index, (start, section) in enumerate(starts)
    ]


def _route_only(line: str) -> str:
    return line.strip().split()[0]


def _suffix(route: str) -> str:
    return route.removeprefix("/cue/{cue_number}/")


def _access_row(lines: list[str], start: int, end: int) -> str:
    index = start
    while index < end and not lines[index].strip():
        index += 1
    if index < end and lines[index].strip().startswith("view"):
        index += 1
        while index < end and not lines[index].strip():
            index += 1
        if index < end:
            return lines[index].strip()
    return ""


def _arg_names(line: str) -> list[str]:
    return [match for match in re.findall(r"\{([^}]+)\}", line) if match != "cue_number"]


def _is_mutating_action(property_path: str) -> bool:
    normalized = normalize_registry_key(property_path)
    return any(normalized == action or normalized.startswith(f"{action}/") for action in MUTATING_ACTIONS)


def _registry_index(catalog: dict[str, Any]) -> dict[str, dict[str, dict[str, Any]]]:
    indexed: dict[str, dict[str, dict[str, Any]]] = {}
    for profile, spec in catalog.items():
        indexed[profile] = {}
        for name, prop in spec["properties"].items():
            keys = {
                normalize_registry_key(name),
                normalize_registry_key(prop["path"]),
                _base_key(name),
                _base_key(prop["path"]),
            }
            for key in keys:
                indexed[profile][key] = {"property": name, **prop}
    return indexed


def _coverage_keys(property_path: str) -> list[str]:
    exact = normalize_registry_key(property_path)
    base = _base_key(property_path)
    return [exact] if exact == base else [exact, base]


def _base_key(value: str) -> str:
    normalized = normalize_registry_key(value)
    return normalized.split("/{}")[0] if "/{}" in normalized else normalized


def _best_match(profile: str, keys: list[str], indexed: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    for candidate_profile in (profile, "common"):
        for key in keys:
            prop = indexed.get(candidate_profile, {}).get(key)
            if not prop:
                continue
            if prop["real_write_enabled"]:
                status = "real_write"
            elif prop.get("capability_gate"):
                status = "gated"
            else:
                status = "planned_only"
            return {
                "registry_status": status,
                "registry_profile": candidate_profile,
                "registry_property": prop["property"],
                "risk": prop["risk_tier"],
                "capability_gate": prop.get("capability_gate"),
                "planned_only_reason": prop.get("planned_only_reason"),
                "validator": {arg["name"]: arg["validator"] for arg in prop["args"]},
            }
    return {
        "registry_status": "missing",
        "registry_profile": None,
        "registry_property": None,
        "risk": "unknown",
        "capability_gate": None,
        "planned_only_reason": "missing_registry_spec",
        "validator": {},
    }
