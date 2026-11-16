from __future__ import annotations

import json

from qlab_mcp.light_patch.archive import Archive
from qlab_mcp.show_control_settings import inspect_saved_show_control_settings
from test_light_patch_archive import workspace as light_workspace

WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
NETWORK_ID = "22222222-2222-4222-8222-222222222222"
MIDI_ID = "33333333-3333-4333-8333-333333333333"
MSC_ID = "44444444-4444-4444-8444-444444444444"


def show_control_workspace() -> bytes:
    archive = Archive(light_workspace())
    root_ref = archive.data["$top"]["root"]
    root = archive.mapping(root_ref)
    settings = archive.mapping(root["settings"])

    network_state = archive.make_dict({
        "host": archive.add("192.0.2.20"), "interface": archive.add("Automatic"),
        "port": 53000, "useTcp": False, "passcode": archive.add("secret-passcode"),
    })
    network_payload = archive.make_dict({
        "uniqueID": archive.add(NETWORK_ID), "name": archive.add("Show OSC"),
        "deviceIdentifier": archive.add("com.figure53.oscmessage"),
        "clientStates": archive.make_array([network_state]),
        "userData": archive.add("secret-plugin-data"),
    })
    network_patch = archive.make_dict({"data": network_payload})
    midi_device = archive.make_dict({
        "manufacturer": archive.add("Example"), "name": archive.add("Keyboard"),
        "longName": archive.add("Example Keyboard Port 1"), "uniqueID": 9191,
    })
    midi_patch = archive.make_dict({
        "uniqueID": archive.add(MIDI_ID), "name": archive.add("Keys"),
        "deviceDescription": midi_device,
    })
    msc_entry = archive.make_dict({
        "uniqueID": archive.add(MSC_ID), "patchTypeIdentifier": archive.add("midi"),
        "patchID": archive.add(MIDI_ID), "mscCommandFormat": 0, "mscDeviceID": 7,
    })
    settings.update({
        "Network": archive.make_dict({"networkPatches": archive.make_array([network_patch])}),
        "MIDI": archive.make_dict({"midiPatches": archive.make_array([midi_patch])}),
        "Events": archive.make_dict({"sendMSC": True, "eventEntries": archive.make_array([msc_entry])}),
    })
    new_settings = archive.make_dict(settings)
    archive.data["$top"]["root"] = archive.replacing_mapping(root_ref, "settings", new_settings)
    return archive.dump()


def test_saved_show_control_settings_are_bounded_and_omit_credentials():
    result = inspect_saved_show_control_settings(show_control_workspace())

    assert result["status"] == "partial"
    assert result["workspace_id"] == WORKSPACE_ID
    assert result["network_patches"][0]["destinations"][0]["transport"] == "udp"
    assert result["network_patches"][0]["opaque_plugin_data_present"] is True
    assert result["midi_patches"][0]["device_unique_id_present"] is True
    assert result["msc_broadcast"]["destinations"][0]["device_id"] == 7
    serialized = json.dumps(result)
    assert "secret-passcode" not in serialized
    assert "secret-plugin-data" not in serialized
    assert "9191" not in serialized


def test_saved_configuration_is_separate_from_live_network_settings(monkeypatch):
    from qlab_mcp import show_control_settings

    saved = inspect_saved_show_control_settings(show_control_workspace())
    saved.update(freshness="last_saved", document_modified=False)
    monkeypatch.setattr(show_control_settings, "read_saved_show_control_settings", lambda *_: saved)
    live = {"data": {"detail": {"name": "Show OSC", "uniqueID": NETWORK_ID}}}

    result = show_control_settings.enrich_saved_show_control_settings(
        None, WORKSPACE_ID, "network", "Show OSC", live,
    )

    assert result["data"]["detail"] == live["data"]["detail"]
    assert result["data"]["saved_configuration"]["freshness"] == "last_saved"
    assert result["data"]["saved_configuration"]["patch"]["id"] == NETWORK_ID
    assert result["data"]["saved_configuration"]["patch"]["destinations"][0]["port"] == 53000
    assert "passcode" not in json.dumps(result)
