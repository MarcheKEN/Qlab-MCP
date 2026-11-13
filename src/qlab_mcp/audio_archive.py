"""Saved QLab audio patch inspection and guarded archive edits."""
from __future__ import annotations

import hashlib
import json
import math
import plistlib
import struct
from functools import partial
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID, uuid5, NAMESPACE_URL

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, TypeAdapter

from . import workspace_documents as docs
from .light_patch.archive import Archive, MAX_BYTES
from .light_patch.reader import _read_file
from .sanitizer import sanitize_exception_message

MAX_PATCHES = 128
MAX_BUSES = 128
MAX_EFFECTS = 50
MAX_LEVEL_CELLS = 4096
MAX_TOTAL_BUSES = 8192
MAX_TOTAL_EFFECTS = 1024
MAX_TOTAL_LEVEL_CELLS = 8192
_NAME = Annotated[StrictStr, Field(min_length=1, max_length=255)]
_REF = Annotated[StrictStr, Field(min_length=1, max_length=64)]
# Exact component identities observed in QLab 5.5.10 persisted AudioUnit fixtures.
_VALIDATED_AUDIO_UNITS = {
    ("SnapTune", "Nico Fernandez", "666d756174706e537a66634e0000000000000000"),
    ("AUDynamicsProcessor", "Apple", "78667561706d63646c7070610200000000000000"),
}


class AudioPatchBase(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    patch_type: Literal["input", "output"]
    patch_id: _REF


class RenamePatch(AudioPatchBase):
    action: Literal["rename_patch"]
    name: _NAME


class DeletePatch(AudioPatchBase):
    action: Literal["delete_patch"]


class DuplicatePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["duplicate_patch"]
    patch_type: Literal["input", "output"]
    client_ref: _NAME
    source_patch_id: _REF
    name: _NAME


class ReorderPatches(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    action: Literal["reorder_patches"]
    patch_type: Literal["input", "output"]
    patch_ids: Annotated[list[_REF], Field(max_length=MAX_PATCHES)]


class SetAudioDevice(AudioPatchBase):
    action: Literal["set_device"]
    device_uid: Annotated[StrictStr, Field(min_length=1, max_length=512)]


class SetSystemDevice(AudioPatchBase):
    action: Literal["set_system_device"]
    enabled: StrictBool


class SetCueOutputName(AudioPatchBase):
    action: Literal["set_cue_output_name"]
    patch_type: Literal["output"]
    output_channel: Annotated[StrictInt, Field(ge=1, le=128)]
    name: Annotated[StrictStr, Field(max_length=255)]


class AudioBusOperation(AudioPatchBase):
    patch_type: Literal["output"]
    bus_type: Literal["cue", "device"]
    bus_index: Annotated[StrictInt, Field(ge=1, le=MAX_BUSES)]


class SetAudioBusName(AudioBusOperation):
    action: Literal["set_bus_name"]
    name: _NAME


class RemoveAudioBusEffect(AudioBusOperation):
    action: Literal["remove_bus_effect"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=MAX_EFFECTS - 1)]


class MoveAudioBusEffect(AudioBusOperation):
    action: Literal["move_bus_effect"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=MAX_EFFECTS - 1)]
    new_index: Annotated[StrictInt, Field(ge=0, le=MAX_EFFECTS - 1)]


class SetAudioBusEffectEnabled(AudioBusOperation):
    action: Literal["set_bus_effect_enabled"]
    effect_index: Annotated[StrictInt, Field(ge=0, le=MAX_EFFECTS - 1)]
    enabled: StrictBool


AudioPatchOperation = Annotated[
    RenamePatch | DeletePatch | DuplicatePatch | ReorderPatches | SetAudioDevice | SetSystemDevice |
    SetCueOutputName | SetAudioBusName | RemoveAudioBusEffect |
    MoveAudioBusEffect | SetAudioBusEffectEnabled,
    Field(discriminator="action"),
]
AudioPatchOperations = Annotated[list[AudioPatchOperation], Field(min_length=1, max_length=50)]
PublicAudioPatchOperation = Annotated[
    RenamePatch | DeletePatch | DuplicatePatch | ReorderPatches | SetAudioDevice | SetSystemDevice |
    SetCueOutputName | SetAudioBusName, Field(discriminator="action")
]
PublicAudioPatchOperations = Annotated[list[PublicAudioPatchOperation], Field(min_length=1, max_length=50)]


def _class_name(archive: Archive, value) -> str | None:
    obj = archive.ref(value)
    if isinstance(obj, dict) and "$class" in obj:
        try:
            return archive.kind(obj)
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _text(archive: Archive, value):
    value = archive.ref(value)
    if isinstance(value, dict) and "NS.string" in value:
        return archive.ref(value["NS.string"])
    return value


def _audio_effect_summary(archive: Archive, effect_ref) -> dict:
    effect = archive.ref(effect_ref)
    archive_class = _class_name(archive, effect)
    identifier = _text(archive, effect.get("identifier")) if isinstance(effect, dict) else None
    frame_identifier = _text(archive, effect.get("frameIdentifier")) if isinstance(effect, dict) else None
    if archive_class != "F53Effect":
        return {"type": None, "manufacturer": None, "component_id_hex": None,
                "class": None, "identifier": identifier, "frame_identifier": frame_identifier,
                "enabled": None, "parameters": [], "parameters_observed": False,
                "parameters_truncated": False, "archive_class": archive_class,
                "saved_state_write_supported": False, "identity_status": "unknown",
                "read_only_reason": "Unrecognized archived AudioUnit effect class."}
    state_ref = effect.get("state")
    try:
        state = archive.mapping(state_ref) if state_ref is not None else {}
    except (KeyError, TypeError, ValueError):
        return {"type": None, "manufacturer": None, "component_id_hex": None,
                "class": None, "identifier": identifier, "frame_identifier": frame_identifier,
                "enabled": None, "parameters": [], "parameters_observed": False,
                "parameters_truncated": False, "archive_class": archive_class,
                "saved_state_write_supported": False, "identity_status": "unknown",
                "read_only_reason": "AudioUnit state has an unknown encoding."}
    def value(key):
        return _text(archive, state[key]) if key in state else None
    settings = {}
    settings_ref = state.get("settings")
    if settings_ref is not None:
        try:
            settings = archive.mapping(settings_ref)
        except (KeyError, TypeError, ValueError):
            settings = {}
    parameters = []
    for key, ref in settings.items():
        item = archive.ref(ref)
        if key == "data":
            data = item.get("NS.data") if isinstance(item, dict) else None
            if isinstance(data, bytes):
                parameters.extend(_decode_audio_unit_parameters(data))
            continue
        if key in {"manufacturer", "subtype", "type", "version", "name"}:
            continue
        scalar = _text(archive, ref)
        if type(scalar) in (bool, int, float, str) and (not isinstance(scalar, float) or math.isfinite(scalar)):
            parameters.append({"key": key, "value": scalar, "source": "saved_audio_unit_state"})
    component = archive.ref(state.get("component"))
    effect_type = value("displayName") or value("name")
    manufacturer = value("manufacturer")
    component_id = component.hex() if isinstance(component, bytes) else None
    enabled = value("enabled")
    identity_status = "validated" if (effect_type, manufacturer, component_id) in _VALIDATED_AUDIO_UNITS else "unknown"
    return {
        "type": effect_type,
        "manufacturer": manufacturer,
        "component_id_hex": component_id,
        "class": value("class"),
        "identifier": identifier,
        "frame_identifier": frame_identifier,
        "enabled": enabled,
        "parameters": parameters[:256],
        "parameters_observed": bool(parameters),
        "parameters_truncated": len(parameters) > 256,
        "saved_state_write_supported": identity_status == "validated",
        "identity_status": identity_status,
        **({"read_only_reason": "AudioUnit identity has no validated QLab 5.5.10 fixture."}
           if identity_status != "validated" else {}),
    }


def _decode_audio_unit_parameters(data: bytes) -> list[dict]:
    """Decode QLab's observed 12-byte header and (parameter ID, float32) pairs."""
    if len(data) < 12 or (len(data) - 12) % 8:
        return []
    count = struct.unpack_from(">I", data, 8)[0]
    if count > 256 or len(data) != 12 + count * 8:
        return []
    result = []
    for offset in range(12, len(data), 8):
        parameter_id = struct.unpack_from(">I", data, offset)[0]
        value = struct.unpack_from(">f", data, offset + 4)[0]
        if not math.isfinite(value):
            return []
        result.append({"parameter_id": parameter_id, "value": value, "source": "saved_audio_unit_state"})
    return result


def _effect_chain(archive: Archive, value, *, array_key: str | None = None) -> list[dict]:
    if value is None:
        return []
    if array_key is not None:
        refs = archive.array(archive.mapping(value)[array_key])
    else:
        refs = archive.array(value)
    if len(refs) > MAX_EFFECTS:
        raise ValueError("Audio FX chain exceeds 50 instances.")
    return [dict(index=index, **_audio_effect_summary(archive, ref)) for index, ref in enumerate(refs)]


def _audio_patches(archive: Archive, domain: str) -> list:
    meta = archive.mapping(archive.root)
    settings = archive.mapping(meta["settings"])
    section = archive.mapping(settings["Audio" if domain == "output" else "Mic"])
    key = "audioOutputPatches" if domain == "output" else "audioInputPatches"
    values = archive.array(section[key])
    if len(values) > MAX_PATCHES:
        raise ValueError("Saved audio patch inventory exceeds 128 entries.")
    return values


def _patch_id(archive: Archive, patch_ref, domain: str) -> str:
    patch = archive.ref(patch_ref)
    expected = "AudioOutputPatch" if domain == "output" else "AudioInputPatch"
    if _class_name(archive, patch) != expected:
        raise ValueError(f"Unknown saved {domain} audio patch class.")
    patch_id = _text(archive, patch.get("uniqueID"))
    try:
        return str(UUID(str(patch_id))).upper()
    except ValueError as exc:
        raise ValueError("Saved audio patch has an invalid uniqueID.") from exc


def _device_settings(archive: Archive, patch) -> dict:
    description = archive.ref(patch.get("deviceDescription"))
    if not isinstance(description, dict) or "NS.keys" not in description:
        return {"status": "unavailable"}
    values = archive.mapping(description)
    allowed = ("deviceUID", "name", "manufacturer", "deviceModelUID", "inputChannels", "outputChannels")
    result = {key: _text(archive, values[key]) for key in allowed if key in values}
    result["use_system_device"] = archive.ref(patch.get("useSystemDevice"))
    result["source"] = "saved_archive"
    return result


def _bus_summary(archive: Archive, patch, key: str, *, include_effects=True) -> list[dict]:
    refs = archive.array(patch[key]) if archive.ref(patch.get(key)) is not None else []
    if len(refs) > MAX_BUSES:
        raise ValueError("Audio patch bus inventory exceeds 128.")
    result = []
    for index, ref in enumerate(refs, 1):
        bus = archive.ref(ref)
        summary = {"index": index, "name": _text(archive, bus.get("name")),
                   "channels": archive.ref(bus.get("channels"))}
        if include_effects:
            summary["effects"] = _effect_chain(archive, bus.get("effects"))
        result.append(summary)
    return result


def _matrix_summary(archive: Archive, patch) -> dict:
    levels = archive.ref(patch.get("levels"))
    if not isinstance(levels, dict) or "entries" not in levels:
        return {"cells": [], "total_cells": 0, "truncated": False, "status": "unavailable"}
    entries = archive.mapping(levels["entries"])
    total = len(entries)
    cells, invalid_cells = [], 0
    for ref in list(entries.values())[:MAX_LEVEL_CELLS]:
        entry = archive.ref(ref)
        row, column = archive.ref(entry.get("row")), archive.ref(entry.get("column"))
        initial, trim = archive.ref(entry.get("initialLevel")), archive.ref(entry.get("trimLevel"))
        if (type(row) is not int or type(column) is not int or not 0 <= row <= 128 or not 0 <= column <= 128
                or any(type(value) not in (int, float) or not math.isfinite(value) for value in (initial, trim))):
            invalid_cells += 1
            continue
        cells.append({"row": row, "column": column, "initial_level": initial, "trim_level": trim})
    cells.sort(key=lambda item: (item["row"], item["column"]))
    return {"cells": cells, "total_cells": total, "truncated": total > MAX_LEVEL_CELLS,
            "invalid_cells": invalid_cells, "status": "partial" if invalid_cells else "available"}


def _patch_summary(archive: Archive, patch_ref, domain: str, *, include_effects=True) -> dict:
    patch = archive.ref(patch_ref)
    patch_id = _patch_id(archive, patch_ref, domain)
    result = {"id": patch_id, "name": _text(archive, patch.get("name")),
              "device": _device_settings(archive, patch), "patch_type": domain}
    if domain == "input":
        return result
    count = archive.ref(patch.get("cueOutputChannels"))
    if type(count) is not int or not 1 <= count <= 128:
        raise ValueError("Saved output patch has an invalid cue output count.")
    names = archive.mapping(patch["cueOutputNames"]) if archive.ref(patch.get("cueOutputNames")) is not None else {}
    result.update(cue_output_channels=count,
                  cue_output_names={str(key): _text(archive, value) for key, value in names.items()},
                  routing_matrix=_matrix_summary(archive, patch),
                  cue_output_buses=_bus_summary(archive, patch, "cueOutputEffects", include_effects=include_effects),
                  device_output_buses=_bus_summary(archive, patch, "patchOutputEffects", include_effects=include_effects))
    return result


def _walk_audio_effects(archive: Archive) -> tuple[list[dict], list[str]]:
    meta = archive.mapping(archive.root)
    carrier = archive.ref(meta.get("cueLists"))
    if not isinstance(carrier, dict) or not isinstance(carrier.get("NS.data"), bytes):
        return [], ["Saved cue archive is unavailable; cue Audio FX were not inspected."]
    inner = Archive(carrier["NS.data"])
    result = []
    issues = []
    from .light_patch.curves import _reachable_cues
    try:
        cues, _ = _reachable_cues(inner, ("AudioCue", "MicCue", "VideoCue"))
    except (KeyError, TypeError, ValueError) as exc:
        return [], ["Active cue tree could not be read for Audio FX: " + str(exc)]
    video_audio = {
        child.data
        for cue, _ in cues.values()
        if inner.kind(cue) == "VideoCue"
        and isinstance((child := cue.get("audioCue")), plistlib.UID)
    }
    for cue_id, (cue, index) in cues.items():
        kind = inner.kind(cue)
        if kind == "VideoCue":
            audio_cue = inner.ref(cue.get("audioCue"))
            if not isinstance(audio_cue, dict) or _class_name(inner, audio_cue) != "AudioCue":
                issues.append(f"Audio FX owner is unavailable for Video cue {cue_id}.")
                continue
            cue_type = "Video Audio"
        elif kind in {"AudioCue", "MicCue"}:
            if index in video_audio:
                continue
            audio_cue, cue_type = cue, kind
        else:
            continue
        try:
            for effect in _effect_chain(inner, audio_cue.get("effects")):
                result.append({**effect, "cue_type": cue_type, "cue_id": cue_id})
                if len(result) > MAX_TOTAL_EFFECTS:
                    raise ValueError("Saved cue Audio FX inventory exceeds 1024 instances.")
        except (KeyError, TypeError, ValueError) as exc:
            if len(result) > MAX_TOTAL_EFFECTS:
                raise
            issues.append(f"Audio FX chain could not be read for cue {cue_id}: {exc}")
    return result, issues


def _inspect_saved_audio_patch_scope(source: bytes, *, include_effects=True,
                                     patch_type="all", ref=None) -> dict:
    archive = Archive(source)
    meta = archive.mapping(archive.root)
    version, build = archive.ref(meta.get("QLabShortVersionString")), archive.ref(meta.get("QLabBuildNumber"))
    if (version, build) != ("5.5.10", 5510):
        raise ValueError("Saved audio patch inspection supports QLab 5.5.10/build 5510.")
    workspace_id = str(UUID(str(archive.ref(meta["uniqueID"])))).upper()
    if patch_type not in {"all", "input", "output"}:
        raise ValueError("patch_type must be all, input or output.")
    if ref is not None and patch_type == "all":
        raise ValueError("ref requires patch_type='input' or 'output'.")

    # Count only inventories in scope. Full inspection still bounds both;
    # scoped reads do not parse or reject unrelated inventory data.
    output_refs = _audio_patches(archive, "output") if patch_type in {"all", "output"} else []
    input_refs = _audio_patches(archive, "input") if patch_type in {"all", "input"} else []
    if ref is not None:
        refs = output_refs if patch_type == "output" else input_refs
        matches = [patch_ref for patch_ref in refs
                   if _patch_id(archive, patch_ref, patch_type).casefold() == str(ref).casefold()]
        if len(matches) != 1:
            raise ValueError("Audio patch reference must match one exact saved UUID.")
        if patch_type == "output":
            output_refs = matches
        else:
            input_refs = matches

    output_patches = []
    total_buses = total_effects = total_level_cells = 0
    for patch_ref in output_refs:
        patch = _patch_summary(archive, patch_ref, "output", include_effects=include_effects)
        buses = patch["cue_output_buses"] + patch["device_output_buses"]
        total_buses += len(buses)
        total_effects += sum(len(bus.get("effects", [])) for bus in buses)
        total_level_cells += patch["routing_matrix"]["total_cells"]
        if total_buses > MAX_TOTAL_BUSES:
            raise ValueError("Saved audio patch buses exceed the 8192-entry inspection limit.")
        if total_effects > MAX_TOTAL_EFFECTS:
            raise ValueError("Saved audio patch FX inventory exceeds 1024 instances.")
        if total_level_cells > MAX_TOTAL_LEVEL_CELLS:
            raise ValueError("Saved audio routing matrices exceed the 8192-cell inspection limit.")
        output_patches.append(patch)
    audio_effects, audio_effects_issues = _walk_audio_effects(archive) if include_effects else ([], [])
    if total_effects + len(audio_effects) > MAX_TOTAL_EFFECTS:
        raise ValueError("Saved Audio FX inventory exceeds 1024 instances.")
    return {"workspace_id": workspace_id, "version": version, "build": build,
            "output_patches": output_patches,
            "input_patches": [_patch_summary(archive, patch_ref, "input") for patch_ref in input_refs],
            "audio_effects": audio_effects,
            "audio_effects_issues": audio_effects_issues,
            "coverage": "Saved archive configuration only; current device observations are separate."}


def inspect_saved_audio_patches(source: bytes, *, include_effects=True) -> dict:
    return _inspect_saved_audio_patch_scope(source, include_effects=include_effects)


def read_saved_audio_patches(reader, workspace_id: str, *, patch_type="all", ref=None) -> dict:
    result = {"status": "unavailable", "source": "saved_archive", "saved": {},
              "device_observations": {"status": "not_requested", "source": "macos_coreaudio"}, "issues": []}
    try:
        workspace_id = docs._uuid(workspace_id)
        if patch_type not in {"all", "input", "output"}:
            raise ValueError("patch_type must be all, input or output.")
        if ref is not None and patch_type == "all":
            raise ValueError("ref requires patch_type='input' or 'output'.")
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader), workspace_id)
            source, identity = _read_file(Path(before["path"]))
            saved = _inspect_saved_audio_patch_scope(
                source, include_effects=False, patch_type=patch_type, ref=ref)
            if saved["workspace_id"] != workspace_id:
                raise ValueError("Saved workspace UUID does not match the request.")
            after = docs._document(docs._inventory(reader), workspace_id)
            current, current_identity = _read_file(Path(before["path"]))
            if before != after or (source, identity) != (current, current_identity):
                return {**result, "status": "changed_during_read", "issues": ["Workspace or file changed during read; saved configuration discarded."]}
            saved["sha256"] = hashlib.sha256(source).hexdigest()
            saved["document_modified"] = bool(before["modified"])
            saved["freshness"] = "possibly_stale" if before["modified"] else "last_saved"
            from .video_settings import _native_metadata
            native = _native_metadata("audio")
            result["device_observations"] = {
                "status": native.get("status", "unavailable"), "source": "macos_coreaudio",
                "output_status": native.get("output_status", "unavailable"),
                "observed_at": native.get("observed_at"), "capture_started": False,
                "devices": [{key: row.get(key) for key in (
                    "id", "uid", "name", "manufacturer", "model_uid", "input_channels", "output_channels",
                    "metadata_errors",
                )}
                            for row in native.get("devices", []) if isinstance(row, dict)],
                "identity_scope": native.get("identity_scope"),
                "default_input_id": native.get("default_input_id"),
                "default_output_id": native.get("default_output_id"),
            }
            result.update(status="partial" if saved["audio_effects_issues"] else "ready",
                          saved=saved, freshness=saved["freshness"],
                          document_modified=saved["document_modified"], sha256=saved["sha256"], issues=[])
            if saved["audio_effects_issues"]:
                result["issues"] = list(saved["audio_effects_issues"])
        if len(json.dumps(result, allow_nan=False).encode()) > 2 * 1024 * 1024:
            raise ValueError("Saved audio patch data exceeds 2 MiB.")
    except Exception as exc:
        result["issues"] = [sanitize_exception_message(exc)]
    return result


class AudioPatchArchive:
    def __init__(self, source: bytes, devices: dict | None = None, *, include_effects=True):
        self.source = source
        self.include_effects = include_effects
        self.hash = hashlib.sha256(source).hexdigest()
        self.a = Archive(source)
        self.meta = self.a.mapping(self.a.root)
        if (self.a.ref(self.meta.get("QLabShortVersionString")), self.a.ref(self.meta.get("QLabBuildNumber"))) != ("5.5.10", 5510):
            raise ValueError("Audio patch editing requires QLab 5.5.10/build 5510.")
        settings = self.a.mapping(self.meta["settings"])
        general = self.a.mapping(settings["General"])
        if any(self.a.ref(general.get(key)) is not False for key in ("doStartOnOpen", "doStartOnClose")):
            raise ValueError("Workspace automatic open/close cues must be known disabled.")
        self.sections = {"output": self.a.mapping(settings["Audio"]), "input": self.a.mapping(settings["Mic"])}
        self.keys = {"output": "audioOutputPatches", "input": "audioInputPatches"}
        self.refs = {domain: list(self.a.array(self.sections[domain][key])) for domain, key in self.keys.items()}
        self.devices = devices or {}
        self.created: dict[str, str] = {}
        self.effect_duplicates = []
        self.dirty = False
        self._unique_ids()
        self._check_cue_references()

    def _unique_ids(self):
        for domain, refs in self.refs.items():
            ids = []
            for ref in refs:
                patch = self.a.ref(ref)
                value = self.a.ref(patch.get("uniqueID"))
                ids.append(str(UUID(str(value))).upper())
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate saved {domain} audio patch IDs.")

    def _check_cue_references(self):
        carrier = self.a.ref(self.meta.get("cueLists"))
        if not isinstance(carrier, dict) or not isinstance(carrier.get("NS.data"), bytes):
            raise ValueError("Audio patch cue dependencies cannot be checked.")
        self.cues = Archive(carrier["NS.data"])

    def ident(self, ref, domain):
        patch = self.a.ref(ref)
        expected = "AudioOutputPatch" if domain == "output" else "AudioInputPatch"
        if _class_name(self.a, patch) != expected:
            raise ValueError(f"Unsupported {domain} audio patch class.")
        return str(UUID(str(self.a.ref(patch.get("uniqueID"))))).upper()

    def target(self, domain, patch_id):
        try:
            patch_id = str(UUID(str(patch_id))).upper()
        except ValueError as exc:
            raise ValueError("Patch ID must be an exact UUID.") from exc
        matches = [ref for ref in self.refs[domain] if self.ident(ref, domain) == patch_id]
        if len(matches) != 1:
            raise ValueError("Patch UUID must identify one active saved audio patch.")
        return matches[0]

    def _write_array(self, domain):
        self.sections[domain][self.keys[domain]] = self.a.make_array(self.refs[domain])
        self.dirty = True

    def _patch_string(self, ref, key, value):
        patch = self.a.ref(ref)
        current = _text(self.a, patch.get(key))
        if current != value:
            patch[key] = self.a.add(value) if isinstance(patch.get(key), plistlib.UID) else value
            self.dirty = True

    def _device(self, ref, device_uid):
        candidates = [item for item in self.devices.values() if item.get("uid") == device_uid]
        if len(candidates) != 1:
            raise ValueError("Device UID must match one current passive CoreAudio observation.")
        device = candidates[0]
        patch = self.a.ref(ref)
        domain = "output" if _class_name(self.a, patch) == "AudioOutputPatch" else "input"
        capacity_key = "output_channels" if domain == "output" else "input_channels"
        capacity = device.get(capacity_key)
        if type(capacity) is not int or capacity < 1:
            raise ValueError(f"Current CoreAudio device has no known {domain} channels.")
        if (not isinstance(device.get("name"), str) or not device["name"]
                or any(type(device.get(key)) is not int or device[key] < 0
                       for key in ("input_channels", "output_channels"))):
            raise ValueError("Current CoreAudio device identity or channel counts are incomplete.")
        descriptor_ref = patch.get("deviceDescription")
        descriptor = self.a.ref(descriptor_ref)
        if not isinstance(descriptor, dict) or "NS.keys" not in descriptor:
            raise ValueError("Saved audio device descriptor has an unknown encoding.")
        current = self.a.mapping(descriptor_ref)
        required = {"deviceUID", "name", "manufacturer", "deviceModelUID", "inputChannels", "outputChannels"}
        if not required <= set(current):
            raise ValueError("Saved device descriptor does not match the validated QLab 5.5.10 schema.")
        values = dict(current)
        saved_uid = _text(self.a, current["deviceUID"])
        replacements = {"deviceUID": device_uid, "name": device["name"],
                        "manufacturer": device.get("manufacturer") or "Unknown",
                        "deviceModelUID": device.get("model_uid") or "Unknown",
                        "inputChannels": device.get("input_channels", 0),
                        "outputChannels": device.get("output_channels", 0)}
        if saved_uid == device_uid:
            for observed_key, saved_key in (("manufacturer", "manufacturer"), ("model_uid", "deviceModelUID")):
                if not device.get(observed_key):
                    saved_value = _text(self.a, current[saved_key])
                    if isinstance(saved_value, str) and saved_value:
                        replacements[saved_key] = saved_value
        for key, value in replacements.items():
            values[key] = self.a.add(value)
        patch["deviceDescription"] = self.a.make_dict(values)
        patch["useSystemDevice"] = self.a.add(False) if isinstance(patch.get("useSystemDevice"), plistlib.UID) else False
        self.dirty = True

    def _system_device(self, ref, enabled):
        patch = self.a.ref(ref)
        current = self.a.ref(patch.get("useSystemDevice"))
        if type(current) is not bool:
            raise ValueError("Saved system-device setting is unavailable.")
        if current is enabled:
            return
        if enabled:
            descriptor = patch.get("deviceDescription")
            if descriptor is None:
                raise ValueError("Saved audio device descriptor is unavailable.")
            values = self.a.mapping(descriptor)
            required = {"deviceUID", "name", "manufacturer", "deviceModelUID", "inputChannels", "outputChannels"}
            if not required <= set(values):
                raise ValueError("Saved device descriptor does not match the validated QLab 5.5.10 schema.")
            patch["useSystemDevice"] = self.a.add(True) if isinstance(patch.get("useSystemDevice"), plistlib.UID) else True
            self.dirty = True
            return
        descriptor = patch.get("deviceDescription")
        if descriptor is None:
            raise ValueError("Saved device descriptor is unavailable; explicit device assignment cannot be verified.")
        values = self.a.mapping(descriptor)
        device_uid = _text(self.a, values.get("deviceUID"))
        if not isinstance(device_uid, str) or not device_uid:
            raise ValueError("Saved device UID is unavailable; explicit device assignment cannot be verified.")
        # Reuse set_device's exact passive-device, channel-capacity, and descriptor checks.
        self._device(ref, device_uid)

    def _clone(self, value, memo=None):
        memo = {} if memo is None else memo
        if isinstance(value, plistlib.UID):
            if value.data == 0:
                return plistlib.UID(0)
            if value.data not in memo:
                memo[value.data] = self.a.add(None)
                self.a.objects[memo[value.data].data] = self._clone(self.a.objects[value.data], memo)
            return memo[value.data]
        if isinstance(value, dict):
            return {key: self._clone(item, memo) for key, item in value.items()}
        if isinstance(value, list):
            return [self._clone(item, memo) for item in value]
        return value

    def duplicate(self, op):
        from .audio_effect_integrity import capture_patch_effect_graph, verify_duplicate_effect_graph

        domain = op.patch_type
        source_ref = self.target(domain, op.source_patch_id)
        source_effect_graph = capture_patch_effect_graph(self.a, source_ref)
        if any(_text(self.a, self.a.ref(ref).get("name")) == op.name for ref in self.refs[domain]):
            raise ValueError("Audio patch names must be unique within their type.")
        label = op.client_ref
        if label in self.created:
            raise ValueError("client_ref must be unique within the batch.")
        clone_ref = self._clone(source_ref)
        clone = self.a.ref(clone_ref)
        new_id = str(uuid5(NAMESPACE_URL, self.hash + ":audio:" + domain + ":" + label)).upper()
        clone["uniqueID"] = self.a.add(new_id) if isinstance(clone.get("uniqueID"), plistlib.UID) else new_id
        clone["name"] = self.a.add(op.name) if isinstance(clone.get("name"), plistlib.UID) else op.name
        self._refresh_effect_ids(clone_ref, label)
        copy_effect_graph = capture_patch_effect_graph(self.a, clone_ref)
        verify_duplicate_effect_graph(source_effect_graph, copy_effect_graph)
        self.refs[domain].append(clone_ref)
        self.created[label] = new_id
        self.effect_duplicates.append({"domain": domain, "patch_id": new_id,
                                       "source_ids": source_effect_graph["identifiers"]})
        self._write_array(domain)

    def _refresh_effect_ids(self, root_ref, label):
        root_index = root_ref.data if isinstance(root_ref, plistlib.UID) else None
        stack = [root_ref]
        visited = set()
        effect_index = 0
        while stack:
            value = stack.pop()
            if isinstance(value, plistlib.UID):
                if value.data == 0 or value.data in visited:
                    continue
                visited.add(value.data)
                value = self.a.ref(value)
            if isinstance(value, dict):
                if _class_name(self.a, value) == "F53Effect":
                    identifier = str(uuid5(NAMESPACE_URL, f"{self.hash}:audio:effect:{label}:{effect_index}")).upper()
                    effect_index += 1
                    value["identifier"] = self.a.add(identifier) if isinstance(value.get("identifier"), plistlib.UID) else identifier
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        if root_index is not None and root_index not in visited:
            raise ValueError("Copied audio patch graph is incomplete.")

    def _used_by_cue(self, domain, patch_id):
        field = "audioOutputPatchID" if domain == "output" else "audioInputPatchID"
        for obj in self.cues.objects:
            if not isinstance(obj, dict) or _class_name(self.cues, obj) not in {"AudioCue", "MicCue", "VideoCue"}:
                continue
            target = self.cues.ref(obj.get(field))
            if isinstance(target, str) and target.casefold() == patch_id.casefold():
                return True
        return False

    def _bus(self, ref, bus_type, bus_index):
        patch = self.a.ref(ref)
        key = "cueOutputEffects" if bus_type == "cue" else "patchOutputEffects"
        buses = self.a.array(patch[key])
        if not 1 <= bus_index <= len(buses):
            raise ValueError("Bus index is outside the saved output patch.")
        return buses[bus_index - 1]

    def _cue_output_name(self, ref, channel, name):
        patch = self.a.ref(ref)
        cue_outputs = self.a.ref(patch.get("cueOutputChannels"))
        if type(cue_outputs) is not int or channel > cue_outputs:
            raise ValueError("Output channel name is outside the saved cue output count.")
        mapping_ref = patch.get("cueOutputNames")
        values = self.a.mapping(mapping_ref) if self.a.ref(mapping_ref) is not None else {}
        if name:
            values[channel] = self.a.add(name)
        else:
            values.pop(channel, None)
        patch["cueOutputNames"] = self.a.make_dict(values)
        self.dirty = True

    def _effect(self, ref, bus_type, bus_index, effect_index):
        bus = self.a.ref(self._bus(ref, bus_type, bus_index))
        effects = list(self.a.array(bus["effects"]))
        if not 0 <= effect_index < len(effects):
            raise ValueError("Audio effect index is outside the bus chain.")
        return bus, effects, effect_index

    def _effect_reference_count(self, target):
        count = 0
        stack = [self.a.data["$top"]["root"]]
        visited = set()
        while stack:
            value = stack.pop()
            if isinstance(value, plistlib.UID):
                if value == target:
                    count += 1
                elif value.data and value.data not in visited:
                    visited.add(value.data)
                    stack.append(self.a.ref(value))
            elif isinstance(value, dict):
                stack.extend(value.values())
            elif isinstance(value, list):
                stack.extend(value)
        return count

    def _effect_array_owner_count(self, target):
        count = 0
        for patch_ref in self.refs["output"]:
            patch = self.a.ref(patch_ref)
            for key in ("cueOutputEffects", "patchOutputEffects"):
                bus_refs = self.a.ref(patch.get(key))
                if bus_refs is None:
                    continue
                for bus_ref in self.a.array(patch[key]):
                    bus = self.a.ref(bus_ref)
                    if bus.get("effects") == target:
                        count += 1
        return count

    def apply(self, op):
        domain = op.patch_type
        if op.action == "duplicate_patch":
            self.duplicate(op)
            return
        if op.action == "reorder_patches":
            ordered = [self.target(domain, value) for value in op.patch_ids]
            if len(ordered) != len(self.refs[domain]) or len(set(ordered)) != len(ordered) or set(ordered) != set(self.refs[domain]):
                raise ValueError("patch_ids must list every active patch exactly once.")
            if ordered != self.refs[domain]:
                self.refs[domain] = ordered
                self._write_array(domain)
            return
        ref = self.target(domain, op.patch_id)
        patch_id = self.ident(ref, domain)
        if op.action == "rename_patch":
            if any(other != ref and _text(self.a, self.a.ref(other).get("name")) == op.name for other in self.refs[domain]):
                raise ValueError("Audio patch names must be unique within their type.")
            self._patch_string(ref, "name", op.name)
        elif op.action == "delete_patch":
            if domain == "output" and len(self.refs[domain]) <= 1:
                raise ValueError("The last audio output patch cannot be deleted.")
            if self._used_by_cue(domain, patch_id):
                raise ValueError("Audio patch is referenced by a cue and cannot be deleted.")
            self.refs[domain].remove(ref)
            self._write_array(domain)
        elif op.action == "set_device":
            self._device(ref, op.device_uid)
        elif op.action == "set_system_device":
            self._system_device(ref, op.enabled)
        elif op.action == "set_cue_output_name":
            self._cue_output_name(ref, op.output_channel, op.name)
        elif op.action == "set_bus_name":
            bus_ref = self._bus(ref, op.bus_type, op.bus_index)
            bus = self.a.ref(bus_ref)
            current = _text(self.a, bus.get("name"))
            if current != op.name:
                bus["name"] = self.a.add(op.name) if isinstance(bus.get("name"), plistlib.UID) else op.name
                self.dirty = True
        else:
            bus, effects, index = self._effect(ref, op.bus_type, op.bus_index, op.effect_index)
            effect_summary = _audio_effect_summary(self.a, effects[index])
            if effect_summary.get("saved_state_write_supported") is not True:
                raise ValueError("Unknown or unvalidated AudioUnit identity for QLab 5.5.10.")
            if op.action == "remove_bus_effect":
                del effects[index]
            elif op.action == "move_bus_effect":
                if op.new_index >= len(effects):
                    raise ValueError("New effect index is outside the current chain.")
                effects.insert(op.new_index, effects.pop(index))
            else:
                effect = self.a.ref(effects[index])
                state = self.a.ref(effect.get("state"))
                if not isinstance(state, dict) or "NS.keys" not in state:
                    raise ValueError("Audio effect state has an unknown encoding.")
                values = self.a.mapping(effect["state"])
                if "enabled" not in values:
                    raise ValueError("Audio effect has no saved enabled flag.")
                if type(self.a.ref(values["enabled"])) is not bool:
                    raise ValueError("Audio effect enabled state is unavailable.")
                effect_ref = effects[index]
                if (self._effect_array_owner_count(bus.get("effects")) != 1
                        or self._effect_reference_count(bus.get("effects")) != 1):
                    raise ValueError("Shared AudioUnit effect chains cannot be changed safely.")
                if not isinstance(effect_ref, plistlib.UID) or self._effect_reference_count(effect_ref) != 1:
                    raise ValueError("Shared AudioUnit effect references cannot be changed safely.")
                values["enabled"] = self.a.add(op.enabled)
                effect["state"] = self.a.make_dict(values)
            bus["effects"] = self.a.make_array(effects)
            self.dirty = True

    def snapshot(self):
        return inspect_saved_audio_patches(self.a.dump(), include_effects=self.include_effects)

    def output(self):
        root_ref = self.a.data["$top"]["root"]
        meta = self.a.mapping(root_ref)
        self.sections_map = self.a.mapping(meta["settings"])
        for domain in ("output", "input"):
            self.sections_map["Audio" if domain == "output" else "Mic"] = self.a.make_dict(self.sections[domain])
        settings_ref = self.a.make_dict(self.sections_map)
        self.a.data["$top"]["root"] = self.a.replacing_mapping(root_ref, "settings", settings_ref)
        return self.a.dump()


def plan_saved_audio_patches(source, operations, *, devices=None, include_effects=True):
    ops = TypeAdapter(AudioPatchOperations).validate_python(operations) if operations else []
    editor = AudioPatchArchive(source, devices=devices, include_effects=include_effects)
    from .audio_effect_integrity import capture_effects, effects_match
    effect_snapshot = capture_effects(editor.a, editor.cues) if ops and not include_effects else None
    before = editor.snapshot()
    for op in ops:
        editor.apply(op)
    from .audio_effect_integrity import capture_patch_effect_graph, verify_serialized_duplicate_effect_graph
    duplicate_checks = []
    for duplicate in editor.effect_duplicates:
        patch_ref = editor.target(duplicate["domain"], duplicate["patch_id"])
        duplicate_checks.append({**duplicate, "expected": capture_patch_effect_graph(editor.a, patch_ref)})
    candidate = editor.output() if editor.dirty else source
    after = inspect_saved_audio_patches(candidate, include_effects=include_effects)
    changes = [] if before == after else [{"action": op.action, **op.model_dump(exclude_none=True)} for op in ops]
    output = candidate if changes else source
    if len(output) > MAX_BYTES:
        raise ValueError("Edited workspace exceeds 64 MiB.")
    if effect_snapshot is not None and not effects_match(output, effect_snapshot):
        raise ValueError("Existing audio effect data could not be preserved.")
    if duplicate_checks:
        archived = Archive(output)
        for duplicate in duplicate_checks:
            matches = [ref for ref in _audio_patches(archived, duplicate["domain"])
                       if _text(archived, archived.ref(ref).get("uniqueID")) == duplicate["patch_id"]]
            if len(matches) != 1:
                raise ValueError("Duplicated audio effect graph could not be verified.")
            actual = capture_patch_effect_graph(archived, matches[0])
            verify_serialized_duplicate_effect_graph(
                duplicate["expected"], actual, duplicate["source_ids"])
    if not changes:
        after = before
    return {"output_bytes": output, "workspace_id": before["workspace_id"],
            "summary": after, "changes": changes, "affected_cues": [],
            "warnings": ["Saved audio patch configuration is checked after reopen; devices are observed passively and no audio is activated."],
            "created_refs": editor.created, "include_effects": include_effects, "effect_snapshot": effect_snapshot}


def _postcondition(source, plan):
    from .audio_effect_integrity import effects_match
    snapshot = plan.get("effect_snapshot")
    return (inspect_saved_audio_patches(source, include_effects=plan.get("include_effects", True)) == plan["summary"]
            and (snapshot is None or effects_match(source, snapshot)))


def _device_dependencies(reader, workspace_id, operations):
    uses_device_inventory = any(
        op.get("action") == "set_device"
        or (op.get("action") == "set_system_device" and op.get("enabled") is False)
        for op in operations
    )
    if not uses_device_inventory:
        return {}
    from .video_settings import _native_metadata
    native = _native_metadata("audio")
    if native.get("status") != "ready":
        # Disabling system mode will still fail closed in the archive planner when
        # the current descriptor needs an explicit device; a no-op remains a no-op.
        if not any(op.get("action") == "set_device" for op in operations):
            return {"devices": {}}
        raise ValueError("Current passive CoreAudio inventory is unavailable.")
    devices = native.get("devices", [])
    fields = ("id", "uid", "name", "manufacturer", "model_uid", "input_channels", "output_channels")
    valid_devices = [row for row in devices if isinstance(row, dict) and isinstance(row.get("uid"), str)]
    uids = [row["uid"] for row in valid_devices]
    if len(uids) != len(set(uids)):
        raise ValueError("Current passive CoreAudio inventory has duplicate device UIDs.")
    by_uid = {row["uid"]: {key: row.get(key) for key in fields} for row in valid_devices}
    for op in operations:
        if op.get("action") == "set_device" and op.get("device_uid") not in by_uid:
            raise ValueError("Requested device UID is absent from the current passive CoreAudio inventory.")
    return {"devices": by_uid}


def _verify_live(reader, workspace_id, summary):
    from .runtime.read_cache import shared_read_cache
    shared_read_cache().clear()
    response = reader.get_workspace_settings(workspace_id, sections=["audio"], profile="technical")
    if response.get("errors"):
        raise ValueError("Fresh native audio patch inventory is incomplete.")
    section = (response.get("sections") or {}).get("audio")
    if not isinstance(section, dict):
        raise ValueError("Fresh native audio patch inventory is unavailable.")
    for saved_key, live_key in (("output_patches", "output_patches"), ("input_patches", "input_patches")):
        live = section.get(live_key)
        if not isinstance(live, list):
            raise ValueError("Fresh native audio patch list is unavailable.")
        expected = summary[saved_key]
        actual_ids = [str(item.get("uniqueID", "")).upper() for item in live]
        expected_ids = [str(item["id"]).upper() for item in expected]
        if actual_ids != expected_ids:
            raise ValueError(f"Native {saved_key} IDs/order do not match the saved plan.")
    return {"workspace_id": workspace_id, "scope": "Native patch IDs/order; canonical names and saved configuration are verified in the reopened archive."}


def edit_saved_audio_patches(reader, workspace_id, operations, dry_run=True, confirm_token=None):
    from .workspace_archive import edit_archive
    try:
        workspace_id = docs._uuid(workspace_id)
        ops = [op.model_dump(exclude_none=True) for op in TypeAdapter(PublicAudioPatchOperations).validate_python(operations)]
        context = _device_dependencies(reader, workspace_id, ops)
        def check():
            if _device_dependencies(reader, workspace_id, ops) != context:
                raise ValueError("CoreAudio device inventory changed since preview.")
        result = edit_archive(reader, workspace_id, ops, dry_run, confirm_token,
            planner=partial(plan_saved_audio_patches, devices=context.get("devices", {}), include_effects=False),
            token_family="savedAudioPatches", dependencies=context, dependency_check=check,
            postcondition=_postcondition, live_verifier=_verify_live)
    except Exception as exc:
        result = dict(ok=False, status="blocked", planned_operations=[], executed_operations=[], error=sanitize_exception_message(exc))
    result["tool"] = "qlab_edit_saved_audio_patches"
    result["native_patch_verification_scope"] = "Native patch IDs/order via OSC; canonical names and saved configuration via archive round-trip after reopen."
    result["verification_scope"] = "Saved Audio/Mic patch archive after reopen; native patch IDs/order. No capture, playback or output is verified."
    return result
