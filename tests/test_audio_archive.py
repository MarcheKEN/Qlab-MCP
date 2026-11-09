"""Audio archive tests use synthetic keyed archives, never a user workspace."""
import plistlib
from types import SimpleNamespace
import pytest

from qlab_mcp import video_settings
from qlab_mcp.audio_archive import inspect_saved_audio_patches, plan_saved_audio_patches, read_saved_audio_patches
from qlab_mcp.light_patch.archive import Archive
from test_light_patch_archive import workspace as light_workspace

WS = "11111111-1111-4111-8111-111111111111"
OUT1 = "22222222-2222-4222-8222-222222222222"
OUT2 = "33333333-3333-4333-8333-333333333333"
IN1 = "44444444-4444-4444-8444-444444444444"


def audio_workspace():
    outer = Archive(light_workspace())

    def make_patch(patch_id, name, kind):
        device = outer.make_dict({
            "deviceUID": outer.add("fixture-device"), "name": outer.add("Fixture Device"),
            "manufacturer": outer.add("Example"), "deviceModelUID": outer.add("Fixture"),
            "inputChannels": outer.add(2), "outputChannels": outer.add(2),
        })
        if kind == "input":
            return outer.add({"$class": outer.cls("AudioInputPatch"), "uniqueID": patch_id,
                              "name": name, "deviceDescription": device, "useSystemDevice": False})
        state = outer.make_dict({
            "displayName": outer.add("AUDynamicsProcessor"), "manufacturer": outer.add("Apple"),
            "component": outer.add(b"fixture-au-component"), "class": outer.add("F53Effect"),
            "name": outer.add("AUDynamicsProcessor"), "enabled": outer.add(True),
        })
        effect = outer.add({"$class": outer.cls("F53Effect"), "identifier": outer.add(patch_id),
                            "frameIdentifier": plistlib.UID(0), "state": state})
        effect2 = outer.add({"$class": outer.cls("F53Effect"), "identifier": outer.add(OUT2),
                             "frameIdentifier": plistlib.UID(0), "state": state})
        cue_buses = [outer.add({"$class": outer.cls("F53EffectBus"), "channels": 1,
                                "name": outer.add(f"cue bus {index + 1}"),
                                "effects": outer.make_array([effect, effect2] if index == 0 else [])})
                     for index in range(2)]
        device_buses = [outer.add({"$class": outer.cls("F53EffectBus"), "channels": 1,
                                   "name": outer.add(f"device bus {index + 1}"),
                                   "effects": outer.make_array([])}) for index in range(2)]
        cell = outer.add({"$class": outer.cls("AudioLevelKnobs"), "row": 1,
                          "column": 1, "initialLevel": 1.0, "trimLevel": 0.5})
        levels = outer.add({"$class": outer.cls("AudioLevelMatrix"), "rows": 1025, "columns": 1025,
                            "entries": outer.make_dict({1025: cell}), "gangs": outer.make_dict({})})
        return outer.add({"$class": outer.cls("AudioOutputPatch"), "uniqueID": patch_id, "name": name,
                          "buildNumber": 5510, "cueOutputChannels": 2, "cueOutputNames": outer.make_dict({}),
                          "deviceDescription": device, "levels": levels,
                          "muteChannels": plistlib.UID(0), "soloChannels": plistlib.UID(0),
                          "useSystemDevice": False,
                          "cueOutputEffects": outer.make_array(cue_buses),
                          "patchOutputEffects": outer.make_array(device_buses)})

    output_refs = [make_patch(OUT1, "Main", "output"), make_patch(OUT2, "Alt", "output")]
    input_refs = [make_patch(IN1, "Mic", "input")]
    root = outer.data["$top"]["root"]
    meta = outer.mapping(root)
    settings = outer.mapping(meta["settings"])
    settings["Audio"] = outer.make_dict({"audioOutputPatches": outer.make_array(output_refs),
                                         "visibleChannels": outer.add(2), "maxVolume": outer.add(12.0),
                                         "minVolume": outer.add(-60.0)})
    settings["Mic"] = outer.make_dict({"audioInputPatches": outer.make_array(input_refs)})
    outer.data["$top"]["root"] = outer.replacing_mapping(root, "settings", outer.make_dict(settings))
    empty_cues = plistlib.dumps({"$archiver": "NSKeyedArchiver", "$version": 100000,
        "$top": {"root": plistlib.UID(1)}, "$objects": ["$null",
        {"$class": plistlib.UID(2), "NS.objects": []},
        {"$classname": "NSMutableArray", "$classes": ["NSMutableArray", "NSArray", "NSObject"]}]},
        fmt=plistlib.FMT_BINARY, sort_keys=False)
    root = outer.ref(outer.data["$top"]["root"])
    root["NS.keys"].append(outer.add("cueLists"))
    root["NS.objects"].append(outer.add({"$class": outer.cls("NSMutableData"), "NS.data": empty_cues}))
    return outer.dump()


def test_saved_audio_patch_reader_keeps_provenance_and_effect_parameters():
    saved = inspect_saved_audio_patches(audio_workspace())
    assert saved["workspace_id"] == WS
    assert [item["name"] for item in saved["output_patches"]] == ["Main", "Alt"]
    patch = saved["output_patches"][0]
    assert patch["routing_matrix"]["cells"] == [
        {"row": 1, "column": 1, "initial_level": 1.0, "trim_level": 0.5}
    ]
    assert patch["cue_output_buses"][0]["effects"][0]["type"] == "AUDynamicsProcessor"
    assert patch["cue_output_buses"][0]["effects"][0]["enabled"] is True
    assert patch["device"]["source"] == "saved_archive"


def test_audio_fx_catalogue_ignores_unreachable_archived_cues():
    from test_saved_cue_settings import CUE, _add_audio_effect, audio_fx_source

    outer = Archive(audio_workspace())
    cue_workspace = Archive(audio_fx_source("Audio"))
    cue_carrier = cue_workspace.ref(cue_workspace.mapping(cue_workspace.root)["cueLists"])
    inner = Archive(cue_carrier["NS.data"])
    orphan_effect = _add_audio_effect(inner, "Orphan Reverb", "orphan-fx")
    inner.add({"$class": inner.cls("AudioCue"), "uniqueID": inner.add("55555555-5555-4555-8555-555555555555"),
               "effects": inner.make_array([orphan_effect])})
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    carrier["NS.data"] = inner.dump()

    saved = inspect_saved_audio_patches(outer.dump())

    assert len(saved["audio_effects"]) == 2
    assert {(item["cue_type"], item["cue_id"]) for item in saved["audio_effects"]} == {("AudioCue", CUE.upper())}
    assert all(item["type"] != "Orphan Reverb" for item in saved["audio_effects"])
    assert saved["audio_effects_issues"] == []


def test_saved_routing_matrix_marks_out_of_range_cells_partial():
    outer = Archive(audio_workspace())
    settings = outer.mapping(outer.mapping(outer.root)["settings"])
    audio = outer.mapping(settings["Audio"])
    patch = outer.ref(outer.array(audio["audioOutputPatches"])[0])
    levels = outer.ref(patch["levels"])
    cell_ref = next(iter(outer.mapping(levels["entries"]).values()))
    outer.ref(cell_ref)["row"] = 129

    matrix = inspect_saved_audio_patches(outer.dump())["output_patches"][0]["routing_matrix"]

    assert matrix["cells"] == []
    assert matrix["invalid_cells"] == 1
    assert matrix["status"] == "partial"


def test_saved_patch_read_separates_stale_archive_and_current_device_observations(tmp_path, monkeypatch):
    path = tmp_path / "Show.qlab5"
    path.write_bytes(audio_workspace())
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=True,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", lambda _: {"documents": [row]})
    observed = {"status": "ready", "output_status": "ready", "observed_at": "2026-11-07T10:00:00Z",
        "identity_scope": "current_macos_audio_session", "default_input_id": 3,
        "default_output_id": 4, "devices": [{"id": 4, "uid": "fixture-device",
            "name": "Current Device", "manufacturer": "Example", "model_uid": "Fixture",
            "input_channels": 2, "output_channels": 2, "metadata_errors": {}}]}
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: observed)
    result = read_saved_audio_patches(reader, WS, patch_type="output", ref=OUT1)
    assert result["status"] == "ready"
    assert result["freshness"] == "possibly_stale"
    assert result["saved"]["freshness"] == "possibly_stale"
    assert [patch["id"] for patch in result["saved"]["output_patches"]] == [OUT1]
    assert result["saved"]["input_patches"] == []
    assert result["device_observations"]["source"] == "macos_coreaudio"
    assert result["device_observations"]["capture_started"] is False
    assert result["device_observations"]["output_status"] == "ready"
    assert result["device_observations"]["default_output_id"] == 4


def test_saved_patch_read_discards_results_if_document_changes(tmp_path, monkeypatch):
    path = tmp_path / "Show.qlab5"
    path.write_bytes(audio_workspace())
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    calls = 0
    def inventory(_):
        nonlocal calls
        calls += 1
        return {"documents": [{**row, "modified": calls > 1}]}
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", inventory)
    result = read_saved_audio_patches(reader, WS)
    assert result["status"] == "changed_during_read"
    assert result["saved"] == {}


def test_patch_edit_batch_can_rename_reorder_add_bus_name_and_duplicate():
    source = audio_workspace()
    operations = [
        {"action": "rename_patch", "patch_type": "output", "patch_id": OUT1, "name": "Main FOH"},
        {"action": "set_cue_output_name", "patch_type": "output", "patch_id": OUT1,
         "output_channel": 1, "name": "Dialogue"},
        {"action": "set_bus_name", "patch_type": "output", "patch_id": OUT1,
         "bus_type": "cue", "bus_index": 1, "name": "Voices"},
        {"action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
         "source_patch_id": OUT1, "name": "Backup"},
        {"action": "reorder_patches", "patch_type": "output", "patch_ids": [OUT2, OUT1,
         "TODO"]},
    ]
    # The new deterministic UUID is returned in created_refs; plan the first operations separately.
    initial = plan_saved_audio_patches(source, operations[:4])
    duplicate_id = initial["created_refs"]["copy"]
    operations[-1]["patch_ids"] = [OUT2, OUT1, duplicate_id]
    plan = plan_saved_audio_patches(source, operations)
    saved = inspect_saved_audio_patches(plan["output_bytes"])
    assert [item["name"] for item in saved["output_patches"]] == ["Alt", "Main FOH", "Backup"]
    assert saved["output_patches"][1]["cue_output_channels"] == 2
    assert saved["output_patches"][1]["cue_output_names"] == {"1": "Dialogue"}
    assert saved["output_patches"][1]["cue_output_buses"][0]["name"] == "Voices"
    assert saved["output_patches"][2]["id"] == duplicate_id
    assert saved["output_patches"][2]["cue_output_buses"][0]["effects"][0]["identifier"] != \
        saved["output_patches"][1]["cue_output_buses"][0]["effects"][0]["identifier"]
    assert inspect_saved_audio_patches(plan["output_bytes"]) == plan["summary"]


def test_device_assignment_requires_current_exact_passive_device():
    source = audio_workspace()
    operation = {"action": "set_device", "patch_type": "input", "patch_id": IN1,
                 "device_uid": "fixture-device"}
    devices = {"fixture-device": {"uid": "fixture-device", "name": "Current Device",
        "manufacturer": None, "model_uid": None, "input_channels": 2, "output_channels": 0}}
    plan = plan_saved_audio_patches(source, [operation], devices=devices)
    saved = inspect_saved_audio_patches(plan["output_bytes"])
    assert saved["input_patches"][0]["device"]["name"] == "Current Device"
    assert saved["input_patches"][0]["device"]["manufacturer"] == "Unknown"
    with pytest.raises(ValueError, match="passive CoreAudio"):
        plan_saved_audio_patches(source, [operation])


def test_delete_blocks_last_output_and_patch_referenced_by_audio_cue():
    source = audio_workspace()
    with pytest.raises(ValueError, match="last"):
        plan_saved_audio_patches(source, [{"action": "delete_patch", "patch_type": "output", "patch_id": OUT1},
                                          {"action": "delete_patch", "patch_type": "output", "patch_id": OUT2}])


def test_invalid_patch_permutation_and_bus_index_are_rejected():
    source = audio_workspace()
    with pytest.raises(ValueError, match="exactly"):
        plan_saved_audio_patches(source, [{"action": "reorder_patches", "patch_type": "output",
                                          "patch_ids": [OUT1, OUT1]}])
    with pytest.raises(ValueError):
        plan_saved_audio_patches(source, [{"action": "set_bus_name", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 3, "name": "Invalid"}])


def test_output_bus_chain_can_reorder_bypass_and_remove_observed_effects():
    source = audio_workspace()
    moved = plan_saved_audio_patches(source, [{"action": "move_bus_effect", "patch_type": "output",
        "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "new_index": 1}])
    effects = inspect_saved_audio_patches(moved["output_bytes"])["output_patches"][0]["cue_output_buses"][0]["effects"]
    assert [effect["identifier"] for effect in effects] == [OUT2, OUT1]

    disabled = plan_saved_audio_patches(source, [{"action": "set_bus_effect_enabled", "patch_type": "output",
        "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": False}])
    assert inspect_saved_audio_patches(disabled["output_bytes"])["output_patches"][0]["cue_output_buses"][0]["effects"][0]["enabled"] is False

    removed = plan_saved_audio_patches(source, [{"action": "remove_bus_effect", "patch_type": "output",
        "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0}])
    assert len(inspect_saved_audio_patches(removed["output_bytes"])["output_patches"][0]["cue_output_buses"][0]["effects"]) == 1


def test_output_bus_bypass_blocks_shared_effect_and_unknown_enabled_state():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    buses = source.array(patch["cueOutputEffects"])
    effect_ref = source.array(source.ref(buses[0])["effects"])[0]
    source.ref(buses[1])["effects"] = source.make_array([effect_ref])

    with pytest.raises(ValueError, match="Shared AudioUnit"):
        plan_saved_audio_patches(source.dump(), [{"action": "set_bus_effect_enabled", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": False}])

    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    effect_ref = source.array(source.ref(source.array(patch["cueOutputEffects"])[0])["effects"])[0]
    effect = source.ref(effect_ref)
    state = source.mapping(effect["state"])
    state["enabled"] = source.add("true")
    effect["state"] = source.make_dict(state)

    with pytest.raises(ValueError, match="enabled state"):
        plan_saved_audio_patches(source.dump(), [{"action": "set_bus_effect_enabled", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": False}])


def test_output_channel_name_and_device_assignment_reject_stale_or_out_of_range_values():
    with pytest.raises(ValueError, match="outside the saved cue output count"):
        plan_saved_audio_patches(audio_workspace(), [{"action": "set_cue_output_name", "patch_type": "output",
            "patch_id": OUT1, "output_channel": 3, "name": "Invalid"}])
    with pytest.raises(ValueError, match="passive CoreAudio"):
        plan_saved_audio_patches(audio_workspace(), [{"action": "set_device", "patch_type": "output",
            "patch_id": OUT1, "device_uid": "missing-device"}], devices={})


def test_audio_patch_operations_are_discriminated_and_bounded():
    with pytest.raises(ValueError):
        plan_saved_audio_patches(audio_workspace(), [{"action": "rename_patch", "patch_type": "output",
            "patch_id": OUT1, "name": "Name", "device_uid": "ignored"}])
    with pytest.raises(ValueError):
        plan_saved_audio_patches(audio_workspace(), [{"action": "set_bus_effect_enabled", "patch_type": "input",
            "patch_id": IN1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": True}])


def test_audio_device_confirmation_is_blocked_when_passive_inventory_changes(monkeypatch):
    from qlab_mcp import workspace_archive
    from qlab_mcp.audio_archive import edit_saved_audio_patches

    snapshots = [
        {"status": "ready", "devices": [{"id": 4, "uid": "fixture-device", "name": "Speaker",
            "manufacturer": "Example", "model_uid": "Fixture", "input_channels": 0, "output_channels": 2}]},
        {"status": "ready", "devices": [{"id": 4, "uid": "fixture-device", "name": "Changed Speaker",
            "manufacturer": "Example", "model_uid": "Fixture", "input_channels": 0, "output_channels": 2}]},
    ]
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: snapshots.pop(0))

    def edit_archive(*args, **kwargs):
        kwargs["dependency_check"]()
        return {"ok": True, "status": "verified"}

    monkeypatch.setattr(workspace_archive, "edit_archive", edit_archive)
    reader = SimpleNamespace()
    result = edit_saved_audio_patches(reader, WS, [{"action": "set_device", "patch_type": "output",
        "patch_id": OUT1, "device_uid": "fixture-device"}], dry_run=False, confirm_token="stale")
    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert "inventory changed since preview" in result["error"]


def test_device_assignment_blocks_duplicate_passive_uids(monkeypatch):
    from qlab_mcp.audio_archive import edit_saved_audio_patches

    row = {"id": 4, "uid": "fixture-device", "name": "Speaker", "manufacturer": "Example",
        "model_uid": "Fixture", "input_channels": 0, "output_channels": 2}
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {"status": "ready", "devices": [row, dict(row, id=5)]})
    result = edit_saved_audio_patches(SimpleNamespace(), WS, [{
        "action": "set_device", "patch_type": "output", "patch_id": OUT1,
        "device_uid": "fixture-device",
    }])

    assert result["status"] == "blocked"
    assert "duplicate device UIDs" in result["error"]


def test_device_assignment_blocks_empty_coreaudio_inventory(monkeypatch):
    from qlab_mcp.audio_archive import edit_saved_audio_patches

    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {
        "status": "unavailable", "devices": [], "default_output_id": 0,
    })
    result = edit_saved_audio_patches(SimpleNamespace(), WS, [{
        "action": "set_device", "patch_type": "output", "patch_id": OUT1,
        "device_uid": "missing-device",
    }])

    assert result["status"] == "blocked"
    assert "passive CoreAudio inventory is unavailable" in result["error"]
