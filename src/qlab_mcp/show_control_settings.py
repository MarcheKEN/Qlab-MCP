"""Read last-saved Network, MIDI and MSC settings without interpreting secrets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from uuid import UUID

from . import workspace_documents as docs
from .light_patch.archive import Archive
from .light_patch.reader import _read_file
from .sanitizer import sanitize_exception_message

MAX_PATCHES = 128
MAX_DESTINATIONS = 256
MAX_MSC_DESTINATIONS = 256
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _mapping(archive: Archive, value) -> dict | None:
    item = archive.ref(value)
    if not isinstance(item, dict):
        return None
    if "NS.keys" in item:
        try:
            return archive.mapping(value)
        except (KeyError, TypeError, ValueError):
            return None
    return item


def _array(archive: Archive, value) -> list | None:
    item = archive.ref(value)
    if isinstance(item, list):
        return item
    if isinstance(item, dict) and isinstance(item.get("NS.objects"), list) and "NS.keys" not in item:
        return item["NS.objects"]
    return None


def _text(archive: Archive, value, maximum: int = 1024) -> str | None:
    value = archive.ref(value)
    if not isinstance(value, str):
        return None
    return value[:maximum]


def _uuid(archive: Archive, value) -> str | None:
    text = _text(archive, value, 64)
    if text is None:
        return None
    try:
        return str(UUID(text)).upper()
    except ValueError:
        return None


def _section(archive: Archive, settings: dict, name: str) -> dict | None:
    return _mapping(archive, settings.get(name))


def _collection(archive: Archive, section: dict | None, key: str, limit: int, name: str,
                diagnostics: list[dict]) -> list:
    if section is None or key not in section:
        diagnostics.append({"section": name, "code": "missing_collection", "message": f"Saved {name} collection is unavailable."})
        return []
    refs = _array(archive, section[key])
    if refs is None:
        diagnostics.append({"section": name, "code": "invalid_collection", "message": f"Saved {name} collection has an unknown format."})
        return []
    if len(refs) > limit:
        diagnostics.append({"section": name, "code": "collection_truncated", "message": f"Saved {name} collection exceeds its {limit}-item limit."})
    return refs[:limit]


def _network_patch(archive: Archive, ref, index: int, diagnostics: list[dict]) -> dict | None:
    wrapper = _mapping(archive, ref)
    if wrapper is None:
        diagnostics.append({"section": "network", "code": "invalid_patch", "message": "A saved Network patch could not be interpreted.", "index": index})
        return None
    payload = _mapping(archive, wrapper.get("data")) or wrapper
    patch_id = _uuid(archive, payload.get("uniqueID"))
    if patch_id is None:
        diagnostics.append({"section": "network", "code": "missing_patch_id", "message": "A saved Network patch has no readable identity.", "index": index})
        return None
    client_states = _array(archive, payload.get("clientStates"))
    destinations = []
    if client_states is None and payload.get("clientStates") is not None:
        state = _mapping(archive, payload.get("clientStates"))
        client_states = [state] if state is not None else None
    if client_states is None:
        diagnostics.append({"section": "network", "code": "unknown_destinations", "message": "Saved Network destinations have an unknown format.", "index": index})
    else:
        if len(client_states) > MAX_DESTINATIONS:
            diagnostics.append({"section": "network", "code": "destinations_truncated", "message": f"Network patch destinations exceed the {MAX_DESTINATIONS}-item limit.", "index": index})
        for state_ref in client_states[:MAX_DESTINATIONS]:
            state = _mapping(archive, state_ref)
            if state is None:
                diagnostics.append({"section": "network", "code": "invalid_destination", "message": "A saved Network destination could not be interpreted.", "index": index})
                continue
            host = _text(archive, state.get("host"), 255)
            interface = _text(archive, state.get("interface"), 255)
            port = archive.ref(state.get("port"))
            use_tcp = archive.ref(state.get("useTcp"))
            if host is None or interface is None or type(port) is not int or type(use_tcp) is not bool:
                diagnostics.append({"section": "network", "code": "incomplete_destination", "message": "A saved Network destination has unreadable connection fields.", "index": index})
            destinations.append({
                "host": host,
                "interface": interface,
                "port": port if type(port) is int and 1 <= port <= 65535 else None,
                "transport": "tcp" if use_tcp is True else "udp" if use_tcp is False else None,
            })
    plugin_data_present = payload.get("userData") is not None
    if plugin_data_present:
        diagnostics.append({"section": "network", "code": "opaque_plugin_data", "message": "Opaque Network plugin data is present and was not interpreted.", "index": index})
    return {
        "id": patch_id,
        "name": _text(archive, payload.get("name"), 255),
        "descriptor_identifier": _text(archive, payload.get("deviceIdentifier"), 255),
        "destinations": destinations,
        "destination_count": len(client_states) if client_states is not None else None,
        "opaque_plugin_data_present": plugin_data_present,
        # userData is intentionally never returned; it may contain credentials or plugin data.
    }


def _midi_patch(archive: Archive, ref, index: int, diagnostics: list[dict]) -> dict | None:
    patch = _mapping(archive, ref)
    if patch is None:
        diagnostics.append({"section": "midi", "code": "invalid_patch", "message": "A saved MIDI patch could not be interpreted.", "index": index})
        return None
    patch_id = _uuid(archive, patch.get("uniqueID"))
    if patch_id is None:
        diagnostics.append({"section": "midi", "code": "missing_patch_id", "message": "A saved MIDI patch has no readable identity.", "index": index})
        return None
    device = _mapping(archive, patch.get("deviceDescription"))
    if patch.get("deviceDescription") is not None and device is None:
        diagnostics.append({"section": "midi", "code": "unknown_device_description", "message": "A saved MIDI device description has an unknown format.", "index": index})
    numeric_id = archive.ref(device.get("uniqueID")) if device else None
    return {
        "id": patch_id,
        "name": _text(archive, patch.get("name"), 255),
        "manufacturer": _text(archive, device.get("manufacturer"), 255) if device else None,
        "device_name": _text(archive, device.get("name"), 255) if device else None,
        "long_name": _text(archive, device.get("longName"), 512) if device else None,
        "device_unique_id_present": True if type(numeric_id) is int else None,
    }


def _msc_entry(archive: Archive, ref, index: int, diagnostics: list[dict]) -> dict | None:
    entry = _mapping(archive, ref)
    if entry is None:
        diagnostics.append({"section": "msc_broadcast", "code": "invalid_destination", "message": "An MSC Broadcast destination could not be interpreted.", "index": index})
        return None
    command_format = archive.ref(entry.get("mscCommandFormat"))
    device_id = archive.ref(entry.get("mscDeviceID"))
    return {
        "id": _uuid(archive, entry.get("uniqueID")),
        "patch_type_identifier": _text(archive, entry.get("patchTypeIdentifier"), 255),
        "patch_id": _uuid(archive, entry.get("patchID")),
        "command_format": command_format if type(command_format) is int else None,
        "device_id": device_id if type(device_id) is int and 0 <= device_id <= 127 else None,
    }


def inspect_saved_show_control_settings(source: bytes) -> dict:
    """Project only reviewed fields from the outer QLab archive; omit userData and credentials."""
    archive = Archive(source)
    meta = archive.mapping(archive.root)
    version, build = archive.ref(meta.get("QLabShortVersionString")), archive.ref(meta.get("QLabBuildNumber"))
    if version != "5.5.10" or build != 5510:
        raise ValueError("Saved Network and MIDI inspection supports QLab 5.5.10/build 5510.")
    workspace_id = str(UUID(str(archive.ref(meta["uniqueID"])))).upper()
    settings = _mapping(archive, meta.get("settings"))
    if settings is None:
        raise ValueError("Saved Workspace Settings have an unknown format.")
    diagnostics: list[dict] = []
    network = _section(archive, settings, "Network")
    midi = _section(archive, settings, "MIDI")
    events = _section(archive, settings, "Events")
    network_refs = _collection(archive, network, "networkPatches", MAX_PATCHES, "network", diagnostics)
    midi_refs = _collection(archive, midi, "midiPatches", MAX_PATCHES, "midi", diagnostics)
    event_refs = _collection(archive, events, "eventEntries", MAX_MSC_DESTINATIONS, "msc_broadcast", diagnostics)
    network_patches = [item for index, ref in enumerate(network_refs) if (item := _network_patch(archive, ref, index, diagnostics))]
    midi_patches = [item for index, ref in enumerate(midi_refs) if (item := _midi_patch(archive, ref, index, diagnostics))]
    msc_destinations = [item for index, ref in enumerate(event_refs) if (item := _msc_entry(archive, ref, index, diagnostics))]
    send_msc = archive.ref(events.get("sendMSC")) if events is not None else None
    if type(send_msc) is not bool:
        diagnostics.append({"section": "msc_broadcast", "code": "unknown_enabled_state", "message": "Saved MSC Broadcast enabled state is unavailable."})
        send_msc = None
    result = {
        "status": "partial" if diagnostics else "ready",
        "source": "saved_archive",
        "workspace_id": workspace_id,
        "version": version,
        "build": build,
        "coverage": "partial" if diagnostics else "complete",
        "network_patches": network_patches,
        "midi_patches": midi_patches,
        "msc_broadcast": {"enabled": send_msc, "destinations": msc_destinations,
                           "destination_count": len(event_refs)},
        "diagnostics": diagnostics,
        "freshness": "unavailable",
        "document_modified": None,
        "sha256": hashlib.sha256(source).hexdigest(),
    }
    if len(json.dumps(result, allow_nan=False).encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise ValueError("Saved Network and MIDI settings exceed the 2 MiB response limit.")
    return result


def read_saved_show_control_settings(reader, workspace_id: str) -> dict:
    result = {"status": "unavailable", "source": "saved_archive", "freshness": "unavailable",
              "workspace_id": workspace_id, "network_patches": [], "midi_patches": [],
              "msc_broadcast": {"enabled": None, "destinations": [], "destination_count": None},
              "diagnostics": []}
    try:
        workspace_id = docs._uuid(workspace_id)
        docs._local(reader)
        with docs._LOCK:
            before = docs._document(docs._inventory(reader, running_bundle=True), workspace_id)
            if not before["path"]:
                raise ValueError("Workspace has no saved document path.")
            source, file_identity = _read_file(Path(before["path"]))
            saved = inspect_saved_show_control_settings(source)
            if saved["workspace_id"] != workspace_id:
                raise ValueError("Saved workspace UUID does not match the request.")
            after = docs._document(docs._inventory(reader, running_bundle=True), workspace_id)
            current, current_identity = _read_file(Path(before["path"]))
            state_keys = ("workspace_id", "path", "modified", "edit_mode", "show_mode", "active_cue_ids")
            if any(before.get(key) != after.get(key) for key in state_keys) or source != current or file_identity != current_identity:
                return {**result, "status": "changed_during_read", "diagnostics": [{
                    "section": "workspace", "code": "changed_during_read",
                    "message": "Workspace or saved file changed during the read; saved settings were discarded.",
                }]}
            saved.update(freshness="possibly_stale" if before["modified"] else "last_saved",
                         document_modified=bool(before["modified"]))
            return saved
    except Exception as exc:
        return {**result, "diagnostics": [{"section": "saved_archive", "code": "unavailable",
                                           "message": sanitize_exception_message(exc)}]}


def enrich_saved_show_control_settings(reader, workspace_id: str, domain: str,
                                        ref: str | None, result: dict) -> dict:
    """Attach last-saved settings separately from the current OSC observation."""
    saved = read_saved_show_control_settings(reader, workspace_id)
    patch_key = "network_patches" if domain == "network" else "midi_patches"
    patches = saved.get(patch_key, [])
    selected = None
    selection_status = "not_requested"
    diagnostics = list(saved.get("diagnostics", []))
    if ref is not None:
        matches = [patch for patch in patches
                   if patch.get("id", "").casefold() == ref.casefold()
                   or patch.get("name") == ref]
        if len(matches) == 1:
            selected, selection_status = matches[0], "matched"
        else:
            selection_status = "ambiguous" if matches else "not_found"
            if matches:
                diagnostics.append({"section": domain, "code": "ambiguous_ref",
                                    "message": "Saved patch reference matches more than one patch."})
    configuration = {
        "status": saved.get("status", "unavailable"),
        "source": "saved_archive",
        "freshness": saved.get("freshness", "unavailable"),
        "document_modified": saved.get("document_modified"),
        "version": saved.get("version"),
        "build": saved.get("build"),
        "sha256": saved.get("sha256"),
        "selection_status": selection_status,
        "patches": patches if ref is None else [],
        "patch": selected,
        "diagnostics": diagnostics,
    }
    if domain == "midi":
        configuration["msc_broadcast"] = saved.get("msc_broadcast")
    data = result.get("data")
    if not isinstance(data, dict):
        data = {}
        result["data"] = data
    data["saved_configuration"] = configuration
    return result
