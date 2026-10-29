"""Passive, identity-bound input-channel capacity checks for Camera and Mic cues."""
from __future__ import annotations

import hashlib
from pathlib import Path

from .. import workspace_documents as docs
from ..light_patch.archive import Archive
from ..light_patch.reader import _read_file


def validate_span(capacity: int, channels: int, offset: int) -> None:
    if type(capacity) is not int or capacity < 1:
        raise ValueError("Input device channel capacity is unavailable.")
    if type(channels) is not int or not 1 <= channels <= 24:
        raise ValueError("Cue channels must be between 1 and 24.")
    if type(offset) is not int or offset < 0 or offset + channels > capacity:
        raise ValueError("Cue channel range exceeds the assigned input device capacity.")


def _archived_input_patch(source: bytes, workspace_id: str, patch_id: str) -> dict:
    archive = Archive(source)
    ref = archive.ref
    meta = archive.mapping(archive.root)
    if ref(meta.get("QLabShortVersionString")) != "5.5.10" or ref(meta.get("QLabBuildNumber")) != 5510:
        raise ValueError("Input-channel validation requires QLab 5.5.10/build 5510.")
    if str(ref(meta.get("uniqueID", ""))).upper() != workspace_id:
        raise ValueError("Saved workspace UUID does not match the target.")
    settings = archive.mapping(meta["settings"])
    patches = archive.array(archive.mapping(settings["Mic"])["audioInputPatches"])
    matches = []
    for item_ref in patches:
        item = ref(item_ref)
        if archive.kind(item) != "AudioInputPatch":
            continue
        if str(ref(item.get("uniqueID", ""))).upper() == patch_id:
            descriptor = archive.mapping(item.get("deviceDescription"))
            matches.append({
                "patch_id": patch_id,
                "use_system_device": ref(item.get("useSystemDevice")),
                "device_uid": ref(descriptor.get("deviceUID")),
                "saved_input_channels": ref(descriptor.get("inputChannels")),
            })
    if len(matches) != 1 or type(matches[0]["use_system_device"]) is not bool:
        raise ValueError("Exact saved input patch identity or device descriptor is unavailable.")
    return matches[0]


def _resolve_device(patch: dict, native: dict) -> dict:
    if patch["use_system_device"]:
        device_id = native.get("default_input_id")
        if type(device_id) is not int or device_id == 0:
            raise ValueError("macOS has no current default input device.")
        candidates = [row for row in native["devices"] if row.get("id") == device_id]
    else:
        device_uid = patch["device_uid"]
        if not isinstance(device_uid, str) or not device_uid:
            raise ValueError("Saved input patch has no exact device UID.")
        candidates = [row for row in native["devices"] if row.get("uid") == device_uid]
    if len(candidates) != 1:
        raise ValueError("Input patch does not resolve to one current macOS audio device.")
    return candidates[0]


def snapshot(reader, workspace_id: str, patch_id: str) -> dict:
    """Bind a clean saved input patch to a passive, exact CoreAudio device read."""
    workspace_id = docs._uuid(workspace_id)
    patch_id = docs._uuid(patch_id)
    docs._local(reader)
    with docs._LOCK:
        before = docs._document(docs._inventory(reader), workspace_id)
        if before["modified"]:
            raise ValueError("Workspace has unsaved changes; save it and run a new dry run.")
        if not before["path"]:
            raise ValueError("Workspace has no saved document path.")
        path = Path(before["path"])
        source, identity = _read_file(path)
        patch = _archived_input_patch(source, workspace_id, patch_id)
        from ..video_settings import _native_metadata
        native = _native_metadata("audio")
        if native.get("status") != "ready" or not isinstance(native.get("devices"), list):
            raise ValueError("Passive macOS audio-device inventory is unavailable.")
        device = _resolve_device(patch, native)
        capacity = device.get("input_channels")
        if type(capacity) is not int or capacity < 1:
            raise ValueError("Current input-device channel capacity is unavailable.")
        after = docs._document(docs._inventory(reader), workspace_id)
        current, current_identity = _read_file(path)
        if before != after or identity != current_identity or source != current:
            raise ValueError("Workspace or saved file changed during input-capacity read.")
        return {
            "workspace_id": workspace_id,
            "patch_id": patch_id,
            "archive_sha256": hashlib.sha256(source).hexdigest(),
            "archive_identity": list(identity),
            "device_id": device.get("id"),
            "device_uid": device.get("uid"),
            "device_name": device.get("name"),
            "input_channels": capacity,
            "use_system_device": patch["use_system_device"],
            "default_input_id": native.get("default_input_id"),
        }
