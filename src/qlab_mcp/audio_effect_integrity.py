"""Compare archived effect graphs without loading or interpreting plug-ins."""
from __future__ import annotations

import hashlib
import plistlib
import struct
from uuid import UUID

from .light_patch.archive import Archive


def _digest(value):
    return hashlib.sha256(plistlib.dumps({"value": value}, fmt=plistlib.FMT_BINARY,
                                         sort_keys=False)).hexdigest()


def _capture(archive):
    owners = {}
    links = {}
    pending = []
    for index, value in enumerate(archive.objects):
        if not isinstance(value, dict):
            continue
        if "effects" in value:
            owners[index] = _digest({key: value[key] for key in ("$class", "effects") if key in value})
            pending.append(value["effects"])
        for key in ("cueOutputEffects", "patchOutputEffects"):
            if key in value:
                links[index, key] = _digest(archive.ref(value[key]))
        if "audioCue" in value:
            child = archive.ref(value["audioCue"])
            if isinstance(child, dict) and "effects" in child:
                links[index, "audioCue"] = _digest(child["effects"])
    nodes = {}
    while pending:
        value = pending.pop()
        if isinstance(value, plistlib.UID):
            if value.data == 0 or value.data in nodes:
                continue
            value_index = value.data
            value = archive.ref(value)
            nodes[value_index] = _digest(value)
        if isinstance(value, dict):
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    return {"owners": owners, "nodes": nodes, "links": links}


def _class_name(archive, value):
    if not isinstance(value, dict) or "$class" not in value:
        return None
    return archive.kind(value)


def _effect_identifier(archive, value):
    effect = archive.ref(value)
    if not isinstance(effect, dict):
        return None
    identifier = archive.ref(effect.get("identifier"))
    if isinstance(identifier, dict) and "NS.string" in identifier:
        identifier = archive.ref(identifier["NS.string"])
    return identifier


def _project_effect_graph(archive, patch_ref):
    patch = archive.ref(patch_ref)
    if not isinstance(patch, dict):
        raise ValueError("Audio effect owner is unavailable.")

    # Canonicalize keyed-archive UIDs by traversal order. The projection retains
    # aliasing while ignoring only recognized AudioUnit IDs, which are checked
    # separately below.
    aliases = {}
    identifiers = []

    def project(value):
        if isinstance(value, plistlib.UID):
            if value.data == 0:
                return ("null",)
            if value.data in aliases:
                return ("ref", aliases[value.data])
            node_id = len(aliases)
            aliases[value.data] = node_id
            return ("node", node_id, project(archive.ref(value)))
        if isinstance(value, dict):
            kind = _class_name(archive, value)
            fields = []
            for key, item in value.items():
                if kind == "F53Effect" and key == "identifier":
                    identifiers.append(_effect_identifier(archive, value))
                    fields.append((project(key), ("regenerated-effect-id",)))
                else:
                    fields.append((project(key), project(item)))
            return ("dict", tuple(fields))
        if isinstance(value, list):
            return ("list", tuple(project(item) for item in value))
        scalar = struct.pack(">d", value) if type(value) is float else value
        return ("scalar", type(value).__name__, scalar)

    graph = project([patch.get("cueOutputEffects"), patch.get("patchOutputEffects")])
    return {"graph": graph, "identifiers": identifiers}


def _check_regenerated_ids(source_ids, duplicate_ids):
    if len(source_ids) != len(duplicate_ids):
        return False
    try:
        source_values = [str(UUID(value)).casefold() for value in source_ids]
        duplicate_values = [str(UUID(value)).casefold() for value in duplicate_ids]
    except (TypeError, ValueError, AttributeError):
        return False
    return (len(duplicate_values) == len(set(duplicate_values))
            and not set(source_values).intersection(duplicate_values)
            and all(old != new for old, new in zip(source_values, duplicate_values)))


def _check_generated_ids(source_ids, duplicate_ids):
    try:
        source_values = {str(UUID(value)).casefold() for value in source_ids}
        duplicate_values = [str(UUID(value)).casefold() for value in duplicate_ids]
    except (TypeError, ValueError, AttributeError):
        return False
    return len(duplicate_values) == len(set(duplicate_values)) and not source_values.intersection(duplicate_values)


def verify_duplicate_effect_graph(source_graph, duplicate_graph):
    if (source_graph["graph"] != duplicate_graph["graph"]
            or not _check_regenerated_ids(source_graph["identifiers"], duplicate_graph["identifiers"])):
        raise ValueError("Duplicated audio effect graph could not be verified.")


def verify_serialized_duplicate_effect_graph(expected_graph, actual_graph, source_ids):
    if (expected_graph["graph"] != actual_graph["graph"]
            or expected_graph["identifiers"] != actual_graph["identifiers"]
            or not _check_generated_ids(source_ids, actual_graph["identifiers"])):
        raise ValueError("Duplicated audio effect graph could not be verified.")


def capture_patch_effect_graph(archive, patch_ref):
    return _project_effect_graph(archive, patch_ref)


def capture_effects(outer, inner):
    return {"outer": _capture(outer), "inner": _capture(inner)}


def _matches(archive, snapshot):
    try:
        for index, expected in snapshot["owners"].items():
            value = archive.objects[index]
            if not isinstance(value, dict) or "effects" not in value:
                return False
            if _digest({key: value[key] for key in ("$class", "effects") if key in value}) != expected:
                return False
        for (index, key), expected in snapshot["links"].items():
            value = archive.objects[index]
            linked = archive.ref(value[key])
            if key == "audioCue":
                linked = linked["effects"]
            if _digest(linked) != expected:
                return False
        return all(_digest(archive.objects[index]) == expected for index, expected in snapshot["nodes"].items())
    except (IndexError, KeyError, TypeError, ValueError, OverflowError):
        return False


def effects_match(source, snapshot):
    try:
        outer = Archive(source)
        meta = outer.mapping(outer.root)
        carrier = outer.ref(meta["cueLists"])
        inner = Archive(carrier["NS.data"])
        return _matches(outer, snapshot["outer"]) and _matches(inner, snapshot["inner"])
    except (IndexError, KeyError, TypeError, ValueError, OverflowError):
        return False
