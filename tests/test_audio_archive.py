"""Audio archive tests use synthetic keyed archives, never a user workspace."""
import plistlib
from types import SimpleNamespace
from uuid import UUID
import pytest

from qlab_mcp import video_settings
from qlab_mcp.audio_archive import (
    _verify_live,
    inspect_saved_audio_patches,
    plan_saved_audio_patches,
    read_saved_audio_patches,
)
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
            "component": outer.add(bytes.fromhex("78667561706d63646c7070610200000000000000")),
            "class": outer.add("F53Effect"),
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
    assert patch["cue_output_buses"][0]["effects"][0]["identity_status"] == "validated"
    assert patch["cue_output_buses"][0]["effects"][0]["saved_state_write_supported"] is True
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


def _audio_workspace_with_matrix_cells(patch_id, count, *, duplicate_id=False):
    outer = Archive(audio_workspace())
    settings = outer.mapping(outer.mapping(outer.root)["settings"])
    output = outer.mapping(settings["Audio"])
    patches = outer.array(output["audioOutputPatches"])
    target = next(outer.ref(ref) for ref in patches if outer.ref(outer.ref(ref)["uniqueID"]) == patch_id)
    levels = outer.ref(target["levels"])
    cell_ref = next(iter(outer.mapping(levels["entries"]).values()))
    levels["entries"] = outer.make_dict({index: cell_ref for index in range(count)})
    if duplicate_id:
        other = next(outer.ref(ref) for ref in patches if outer.ref(outer.ref(ref)["uniqueID"]) == OUT2)
        other["uniqueID"] = OUT1
    return outer.dump()


def test_scoped_saved_patch_read_summarizes_only_selected_output_matrix(tmp_path, monkeypatch):
    source = _audio_workspace_with_matrix_cells(OUT2, 8192)
    path = tmp_path / "Show.qlab5"
    path.write_bytes(source)
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", lambda _: {"documents": [row]})
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {"status": "unavailable", "devices": []})

    scoped = read_saved_audio_patches(reader, WS, patch_type="output", ref=OUT1)

    assert scoped["status"] == "ready"
    assert [patch["id"] for patch in scoped["saved"]["output_patches"]] == [OUT1]
    assert scoped["saved"]["output_patches"][0]["routing_matrix"]["total_cells"] == 1
    assert scoped["saved"]["input_patches"] == []
    full_scope = read_saved_audio_patches(reader, WS, patch_type="output")
    assert full_scope["status"] == "unavailable"
    assert "8192-cell inspection limit" in full_scope["issues"][0]
    with pytest.raises(ValueError, match="8192-cell inspection limit"):
        inspect_saved_audio_patches(source)


def test_input_patch_read_ignores_unrelated_8193_cell_output_matrix(tmp_path, monkeypatch):
    path = tmp_path / "Show.qlab5"
    path.write_bytes(_audio_workspace_with_matrix_cells(OUT2, 8193))
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", lambda _: {"documents": [row]})
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {"status": "unavailable", "devices": []})

    result = read_saved_audio_patches(reader, WS, patch_type="input", ref=IN1)

    assert result["status"] == "ready"
    assert [patch["id"] for patch in result["saved"]["input_patches"]] == [IN1]
    assert result["saved"]["output_patches"] == []


def test_input_patch_read_ignores_unrelated_oversized_output_inventory(tmp_path, monkeypatch):
    outer = Archive(audio_workspace())
    root_ref = outer.data["$top"]["root"]
    root = outer.mapping(root_ref)
    settings = outer.mapping(root["settings"])
    audio = outer.mapping(settings["Audio"])
    output_refs = outer.array(audio["audioOutputPatches"])
    audio["audioOutputPatches"] = outer.make_array(output_refs * 65)
    settings["Audio"] = outer.make_dict(audio)
    outer.data["$top"]["root"] = outer.replacing_mapping(root_ref, "settings", outer.make_dict(settings))
    path = tmp_path / "Show.qlab5"
    path.write_bytes(outer.dump())
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", lambda _: {"documents": [row]})
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {"status": "unavailable", "devices": []})

    scoped = read_saved_audio_patches(reader, WS, patch_type="input", ref=IN1)

    assert scoped["status"] == "ready"
    assert [patch["id"] for patch in scoped["saved"]["input_patches"]] == [IN1]
    full_scope = read_saved_audio_patches(reader, WS)
    assert full_scope["status"] == "unavailable"
    assert "inventory exceeds 128 entries" in full_scope["issues"][0]


def test_scoped_saved_patch_read_rejects_missing_and_ambiguous_exact_ids(tmp_path, monkeypatch):
    path = tmp_path / "Show.qlab5"
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(host="127.0.0.1")))
    monkeypatch.setattr("qlab_mcp.workspace_documents._inventory", lambda _: {"documents": [row]})
    monkeypatch.setattr(video_settings, "_native_metadata", lambda _: {"status": "unavailable", "devices": []})

    path.write_bytes(audio_workspace())
    missing = read_saved_audio_patches(reader, WS, patch_type="output", ref="55555555-5555-4555-8555-555555555555")
    assert missing["status"] == "unavailable"
    assert "Audio patch reference must match one exact saved UUID." in missing["issues"][0]

    path.write_bytes(_audio_workspace_with_matrix_cells(OUT2, 8192, duplicate_id=True))
    ambiguous = read_saved_audio_patches(reader, WS, patch_type="output", ref=OUT1)
    assert ambiguous["status"] == "unavailable"
    assert "Audio patch reference must match one exact saved UUID." in ambiguous["issues"][0]


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


def test_duplicate_patch_alone_is_deterministic_and_changes_archive():
    source = audio_workspace()
    operations = [{"action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
                   "source_patch_id": OUT1, "name": "Backup"}]
    first = plan_saved_audio_patches(source, operations, include_effects=False)
    second = plan_saved_audio_patches(source, operations, include_effects=False)
    assert first["changes"] and first["output_bytes"] != source
    assert first["output_bytes"] == second["output_bytes"]
    saved = inspect_saved_audio_patches(first["output_bytes"])
    assert [patch["name"] for patch in saved["output_patches"]] == ["Main", "Alt", "Backup"]
    assert saved["output_patches"][2]["cue_output_buses"][0]["effects"][0]["identifier"] != \
        saved["output_patches"][0]["cue_output_buses"][0]["effects"][0]["identifier"]


def test_duplicate_patch_blocks_corrupted_effect_copy(monkeypatch):
    from qlab_mcp.audio_archive import AudioPatchArchive

    refresh = AudioPatchArchive._refresh_effect_ids

    def corrupt_copy(self, root_ref, label):
        refresh(self, root_ref, label)
        patch = self.a.ref(root_ref)
        bus_ref = self.a.array(patch["cueOutputEffects"])[0]
        bus = self.a.ref(bus_ref)
        effect = self.a.ref(self.a.array(bus["effects"])[0])
        effect["state"] = self.a.make_dict({"unexpected": self.a.add("corrupted copy")})

    monkeypatch.setattr(AudioPatchArchive, "_refresh_effect_ids", corrupt_copy)
    with pytest.raises(ValueError, match="Duplicated audio effect graph"):
        plan_saved_audio_patches(audio_workspace(), [{
            "action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
            "source_patch_id": OUT1, "name": "Backup",
        }])


@pytest.mark.parametrize("replacement", [1, 1.0])
def test_duplicate_patch_blocks_effect_scalar_type_change(monkeypatch, replacement):
    from qlab_mcp.audio_archive import AudioPatchArchive

    refresh = AudioPatchArchive._refresh_effect_ids

    def change_scalar_type(self, root_ref, label):
        refresh(self, root_ref, label)
        patch = self.a.ref(root_ref)
        bus_ref = self.a.array(patch["cueOutputEffects"])[0]
        effect = self.a.ref(self.a.array(self.a.ref(bus_ref)["effects"])[0])
        state = self.a.ref(effect["state"])
        keys = [self.a.ref(key) for key in state["NS.keys"]]
        state["NS.objects"][keys.index("enabled")] = self.a.add(replacement)

    monkeypatch.setattr(AudioPatchArchive, "_refresh_effect_ids", change_scalar_type)
    with pytest.raises(ValueError, match="Duplicated audio effect graph"):
        plan_saved_audio_patches(audio_workspace(), [{
            "action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
            "source_patch_id": OUT1, "name": "Backup",
        }])


def test_duplicate_patch_preserves_unknown_effect_class_and_shared_aliases():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    patch = source.ref(source.array(source.mapping(settings["Audio"])["audioOutputPatches"])[0])
    buses = source.array(patch["cueOutputEffects"])
    first_bus, second_bus = (source.ref(ref) for ref in buses[:2])
    first_bus["effects"] = source.make_array([source.add({
        "$class": source.cls("FutureAudioEffect"), "identifier": source.add("opaque-id"),
        "opaqueState": source.make_dict({"vendorField": source.add(b"opaque")}),
    })])
    second_bus["effects"] = first_bus["effects"]

    plan = plan_saved_audio_patches(source.dump(), [{
        "action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
        "source_patch_id": OUT1, "name": "Backup",
    }])
    copied = Archive(plan["output_bytes"])
    output = copied.mapping(copied.mapping(copied.root)["settings"])["Audio"]
    original_ref, copy_ref = copied.array(copied.mapping(output)["audioOutputPatches"])[0], \
        copied.array(copied.mapping(output)["audioOutputPatches"])[2]
    original = copied.ref(original_ref)
    duplicate = copied.ref(copy_ref)
    original_buses = copied.array(original["cueOutputEffects"])
    duplicate_buses = copied.array(duplicate["cueOutputEffects"])
    original_first, original_second = (copied.ref(ref) for ref in original_buses[:2])
    duplicate_first, duplicate_second = (copied.ref(ref) for ref in duplicate_buses[:2])

    assert duplicate_first["effects"] == duplicate_second["effects"]
    assert duplicate_first["effects"] != original_first["effects"]
    copied_effect_ref = copied.array(duplicate_first["effects"])[0]
    original_effect_ref = copied.array(original_first["effects"])[0]
    assert copied.kind(copied_effect_ref) == "FutureAudioEffect"
    assert copied.ref(copied.ref(copied_effect_ref)["identifier"]) == copied.ref(
        copied.ref(original_effect_ref)["identifier"]
    )
    copied_opaque = copied.mapping(copied.ref(copied_effect_ref)["opaqueState"])
    original_opaque = copied.mapping(copied.ref(original_effect_ref)["opaqueState"])
    assert copied.ref(copied_opaque["vendorField"]) == copied.ref(original_opaque["vendorField"]) == b"opaque"


def test_duplicate_patch_regenerates_every_recognized_effect_id():
    plan = plan_saved_audio_patches(audio_workspace(), [{
        "action": "duplicate_patch", "patch_type": "output", "client_ref": "copy",
        "source_patch_id": OUT1, "name": "Backup",
    }])
    saved = inspect_saved_audio_patches(plan["output_bytes"])
    original = saved["output_patches"][0]["cue_output_buses"][0]["effects"]
    duplicate = saved["output_patches"][2]["cue_output_buses"][0]["effects"]
    original_ids = {item["identifier"] for item in original}
    duplicate_ids = [item["identifier"] for item in duplicate]

    assert len(duplicate_ids) == len(set(duplicate_ids)) == len(original_ids)
    assert original_ids.isdisjoint(duplicate_ids)
    assert all(UUID(value) for value in duplicate_ids)


@pytest.mark.parametrize("operation,expected", [
    ({"action": "reorder_patches", "patch_type": "output", "patch_ids": [OUT2, OUT1]}, ["Alt", "Main"]),
    ({"action": "delete_patch", "patch_type": "output", "patch_id": OUT2}, ["Main"]),
])
def test_structural_patch_operation_alone_is_not_a_noop(operation, expected):
    source = audio_workspace()
    plan = plan_saved_audio_patches(source, [operation], include_effects=False)
    assert plan["changes"] and plan["output_bytes"] != source
    assert [patch["name"] for patch in inspect_saved_audio_patches(plan["output_bytes"])["output_patches"]] == expected


def test_device_assignment_requires_current_exact_passive_device():
    source = audio_workspace()
    operation = {"action": "set_device", "patch_type": "input", "patch_id": IN1,
                 "device_uid": "fixture-device"}
    devices = {"fixture-device": {"uid": "fixture-device", "name": "Current Device",
        "manufacturer": None, "model_uid": None, "input_channels": 2, "output_channels": 0}}
    plan = plan_saved_audio_patches(source, [operation], devices=devices)
    saved = inspect_saved_audio_patches(plan["output_bytes"])
    assert saved["input_patches"][0]["device"]["name"] == "Current Device"
    assert saved["input_patches"][0]["device"]["manufacturer"] == "Example"
    assert saved["input_patches"][0]["device"]["deviceModelUID"] == "Fixture"
    with pytest.raises(ValueError, match="passive CoreAudio"):
        plan_saved_audio_patches(source, [operation])


def test_new_device_assignment_does_not_invent_unobserved_metadata():
    operation = {"action": "set_device", "patch_type": "output", "patch_id": OUT1,
                 "device_uid": "new-device"}
    device = {"uid": "new-device", "name": "New Device", "manufacturer": None,
              "model_uid": None, "input_channels": 0, "output_channels": 2}

    plan = plan_saved_audio_patches(audio_workspace(), [operation], devices={device["uid"]: device})
    saved = inspect_saved_audio_patches(plan["output_bytes"])["output_patches"][0]["device"]
    assert saved["deviceUID"] == "new-device"
    assert saved["manufacturer"] == "Unknown"
    assert saved["deviceModelUID"] == "Unknown"


def test_patch_rename_preserves_existing_audio_effects():
    source = audio_workspace()
    before = inspect_saved_audio_patches(source)["output_patches"][0]["cue_output_buses"][0]["effects"]
    plan = plan_saved_audio_patches(source, [{"action": "rename_patch", "patch_type": "output",
                                             "patch_id": OUT1, "name": "Renamed"}])
    after = inspect_saved_audio_patches(plan["output_bytes"])["output_patches"][0]["cue_output_buses"][0]["effects"]
    assert after == before


def test_public_patch_planner_preserves_unrecognized_effect_chain():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    patch = source.ref(source.array(source.mapping(settings["Audio"])["audioOutputPatches"])[0])
    bus = source.ref(source.array(patch["cueOutputEffects"])[0])
    bus["effects"] = source.add({"future_effect_format": "opaque"})
    before = source.dump()
    plan = plan_saved_audio_patches(before, [{"action": "rename_patch", "patch_type": "output",
                                              "patch_id": OUT1, "name": "Renamed"}], include_effects=False)
    after = Archive(plan["output_bytes"])
    after_settings = after.mapping(after.mapping(after.root)["settings"])
    after_patch = after.ref(after.array(after.mapping(after_settings["Audio"])["audioOutputPatches"])[0])
    after_bus = after.ref(after.array(after_patch["cueOutputEffects"])[0])
    assert after.ref(after_bus["effects"]) == {"future_effect_format": "opaque"}


def test_patch_postcondition_detects_changed_effect_state_and_shared_reference():
    from qlab_mcp.audio_archive import _postcondition
    original = Archive(audio_workspace())
    settings = original.mapping(original.mapping(original.root)["settings"])
    patch = original.ref(original.array(original.mapping(settings["Audio"])["audioOutputPatches"])[0])
    buses = original.array(patch["cueOutputEffects"])
    original.ref(buses[1])["effects"] = original.ref(buses[0])["effects"]
    plan = plan_saved_audio_patches(original.dump(), [{"action": "rename_patch", "patch_type": "output",
                                                       "patch_id": OUT1, "name": "Renamed"}], include_effects=False)
    assert _postcondition(plan["output_bytes"], plan)
    changed = Archive(plan["output_bytes"])
    settings = changed.mapping(changed.mapping(changed.root)["settings"])
    patch = changed.ref(changed.array(changed.mapping(settings["Audio"])["audioOutputPatches"])[0])
    buses = changed.array(patch["cueOutputEffects"])
    changed.ref(buses[1])["effects"] = changed.make_array([])
    assert not _postcondition(changed.dump(), plan)
    changed = Archive(plan["output_bytes"])
    settings = changed.mapping(changed.mapping(changed.root)["settings"])
    patch = changed.ref(changed.array(changed.mapping(settings["Audio"])["audioOutputPatches"])[0])
    patch["cueOutputEffects"] = changed.make_array([])
    assert not _postcondition(changed.dump(), plan)
    changed = Archive(plan["output_bytes"])
    settings = changed.mapping(changed.mapping(changed.root)["settings"])
    patch = changed.ref(changed.array(changed.mapping(settings["Audio"])["audioOutputPatches"])[0])
    bus = changed.ref(changed.array(patch["cueOutputEffects"])[0])
    effect = changed.ref(changed.array(bus["effects"])[0])
    effect["state"] = changed.make_dict({"unexpected": changed.add("changed")})
    assert not _postcondition(changed.dump(), plan)


def test_public_patch_edit_rejects_unreadable_effect_reference():
    original = Archive(audio_workspace())
    settings = original.mapping(original.mapping(original.root)["settings"])
    patch = original.ref(original.array(original.mapping(settings["Audio"])["audioOutputPatches"])[0])
    bus = original.ref(original.array(patch["cueOutputEffects"])[0])
    bus["effects"] = plistlib.UID(len(original.objects) + 10)
    with pytest.raises((IndexError, ValueError)):
        plan_saved_audio_patches(original.dump(), [{"action": "rename_patch", "patch_type": "output",
                                                    "patch_id": OUT1, "name": "Renamed"}], include_effects=False)


def test_public_audio_patch_schema_rejects_effect_operations():
    from pydantic import TypeAdapter, ValidationError
    from qlab_mcp.audio_archive import PublicAudioPatchOperations
    with pytest.raises(ValidationError):
        TypeAdapter(PublicAudioPatchOperations).validate_python([{
            "action": "remove_bus_effect", "patch_type": "output", "patch_id": OUT1,
            "bus_type": "cue", "bus_index": 1, "effect_index": 0,
        }])


def test_patch_edit_entrypoint_rejects_audio_effect_operations():
    from qlab_mcp.audio_archive import edit_saved_audio_patches
    result = edit_saved_audio_patches(SimpleNamespace(), WS, [{
        "action": "remove_bus_effect", "patch_type": "output", "patch_id": OUT1,
        "bus_type": "cue", "bus_index": 1, "effect_index": 0,
    }])
    assert result["status"] == "blocked" and result["executed_operations"] == []


def test_system_device_toggle_preserves_saved_descriptors_for_input_and_output():
    source = audio_workspace()
    before = inspect_saved_audio_patches(source)
    operations = [
        {"action": "set_system_device", "patch_type": "input", "patch_id": IN1, "enabled": True},
        {"action": "set_system_device", "patch_type": "output", "patch_id": OUT1, "enabled": True},
    ]

    plan = plan_saved_audio_patches(source, operations)
    after = inspect_saved_audio_patches(plan["output_bytes"])

    for domain in ("input_patches", "output_patches"):
        before_device = before[domain][0]["device"]
        after_device = after[domain][0]["device"]
        assert after_device["use_system_device"] is True
        assert {key: value for key, value in after_device.items() if key != "use_system_device"} == {
            key: value for key, value in before_device.items() if key != "use_system_device"
        }


def test_disabling_system_device_requires_current_exact_saved_device():
    source = Archive(audio_workspace())
    root = source.mapping(source.root)
    settings = source.mapping(root["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    patch["useSystemDevice"] = source.add(True)
    system_source = source.dump()
    operation = {"action": "set_system_device", "patch_type": "output", "patch_id": OUT1, "enabled": False}

    device = {"uid": "fixture-device", "name": "Current Device", "manufacturer": "Example",
              "model_uid": "Fixture", "input_channels": 2, "output_channels": 2}
    plan = plan_saved_audio_patches(system_source, [operation], devices={device["uid"]: device})
    saved = inspect_saved_audio_patches(plan["output_bytes"])
    assert saved["output_patches"][0]["device"] == {
        "deviceUID": "fixture-device", "name": "Current Device", "manufacturer": "Example",
        "deviceModelUID": "Fixture", "inputChannels": 2, "outputChannels": 2,
        "use_system_device": False, "source": "saved_archive",
    }
    with pytest.raises(ValueError, match="passive CoreAudio"):
        plan_saved_audio_patches(system_source, [operation], devices={})


def test_system_device_false_noop_does_not_require_device_inventory():
    plan = plan_saved_audio_patches(audio_workspace(), [{
        "action": "set_system_device", "patch_type": "input", "patch_id": IN1, "enabled": False,
    }], devices={})

    assert plan["changes"] == []
    assert plan["output_bytes"] == audio_workspace()


def test_enabling_system_device_blocks_unknown_saved_descriptor():
    source = Archive(audio_workspace())
    root = source.mapping(source.root)
    settings = source.mapping(root["settings"])
    mic = source.mapping(settings["Mic"])
    patch = source.ref(source.array(mic["audioInputPatches"])[0])
    patch.pop("deviceDescription")

    with pytest.raises(ValueError, match="descriptor is unavailable"):
        plan_saved_audio_patches(source.dump(), [{
            "action": "set_system_device", "patch_type": "input", "patch_id": IN1, "enabled": True,
        }])


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


@pytest.mark.parametrize("action", ["remove_bus_effect", "move_bus_effect", "set_bus_effect_enabled"])
def test_unknown_audio_unit_identity_is_read_only_on_output_buses(action):
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    effect_ref = source.array(source.ref(source.array(patch["cueOutputEffects"])[0])["effects"])[0]
    effect = source.ref(effect_ref)
    state = source.mapping(effect["state"])
    state["displayName"] = source.add("Unrecognized Audio Unit")
    state["manufacturer"] = source.add("Unrecognized Vendor")
    state["component"] = source.add(b"unrecognized-component")
    effect["state"] = source.make_dict(state)

    summary = inspect_saved_audio_patches(source.dump())["output_patches"][0]["cue_output_buses"][0]["effects"][0]
    assert summary["type"] == "Unrecognized Audio Unit"
    assert summary["saved_state_write_supported"] is False
    assert summary["identity_status"] == "unknown"
    operation = {"action": action, "patch_type": "output", "patch_id": OUT1,
                 "bus_type": "cue", "bus_index": 1, "effect_index": 0}
    if action == "move_bus_effect":
        operation["new_index"] = 1
    if action == "set_bus_effect_enabled":
        operation["enabled"] = False
    with pytest.raises(ValueError, match="Unknown or unvalidated AudioUnit"):
        plan_saved_audio_patches(source.dump(), [operation])


def test_unrecognized_archived_bus_effect_class_is_returned_read_only():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    effect_ref = source.array(source.ref(source.array(patch["cueOutputEffects"])[0])["effects"])[0]
    source.ref(effect_ref)["$class"] = source.cls("FutureAudioEffect")

    summary = inspect_saved_audio_patches(source.dump())["output_patches"][0]["cue_output_buses"][0]["effects"][0]
    assert summary["archive_class"] == "FutureAudioEffect"
    assert summary["saved_state_write_supported"] is False
    assert summary["identity_status"] == "unknown"
    with pytest.raises(ValueError, match="Unknown or unvalidated AudioUnit"):
        plan_saved_audio_patches(source.dump(), [{"action": "remove_bus_effect", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0}])


def test_output_bus_bypass_blocks_shared_effect_array():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    buses = source.array(patch["cueOutputEffects"])
    first, second = (source.ref(ref) for ref in buses[:2])
    second["effects"] = first["effects"]

    with pytest.raises(ValueError, match="Shared AudioUnit effect chain"):
        plan_saved_audio_patches(source.dump(), [{"action": "set_bus_effect_enabled", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": False}])


def test_output_bus_bypass_blocks_unlisted_effect_array_owner():
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    bus = source.ref(source.array(patch["cueOutputEffects"])[0])
    audio["unrecognizedEffectOwner"] = source.add({"effects": bus["effects"]})
    settings["Audio"] = source.make_dict(audio)
    source.data["$top"]["root"] = source.replacing_mapping(
        source.data["$top"]["root"], "settings", source.make_dict(settings))

    with pytest.raises(ValueError, match="Shared AudioUnit effect chain"):
        plan_saved_audio_patches(source.dump(), [{"action": "set_bus_effect_enabled", "patch_type": "output",
            "patch_id": OUT1, "bus_type": "cue", "bus_index": 1, "effect_index": 0, "enabled": False}])


@pytest.mark.parametrize("action", ["remove_bus_effect", "move_bus_effect"])
def test_output_bus_structural_fx_edit_copies_shared_effect_array(action):
    source = Archive(audio_workspace())
    settings = source.mapping(source.mapping(source.root)["settings"])
    audio = source.mapping(settings["Audio"])
    patch = source.ref(source.array(audio["audioOutputPatches"])[0])
    buses = source.array(patch["cueOutputEffects"])
    first, second = (source.ref(ref) for ref in buses[:2])
    second["effects"] = first["effects"]
    operation = {"action": action, "patch_type": "output", "patch_id": OUT1,
                 "bus_type": "cue", "bus_index": 1, "effect_index": 0}
    if action == "move_bus_effect":
        operation["new_index"] = 1

    plan = plan_saved_audio_patches(source.dump(), [operation])
    cue_buses = inspect_saved_audio_patches(plan["output_bytes"])["output_patches"][0]["cue_output_buses"]
    ids = [[effect["identifier"] for effect in bus["effects"]] for bus in cue_buses]
    assert ids[0] == ([OUT2] if action == "remove_bus_effect" else [OUT2, OUT1])
    assert ids[1] == [OUT1, OUT2]


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


def test_live_audio_patch_verification_ignores_device_suffix_in_display_name():
    reader = SimpleNamespace(get_workspace_settings=lambda *args, **kwargs: {
        "errors": {},
        "sections": {"audio": {
            "output_patches": [
                {"uniqueID": OUT1, "name": "Main - System Output - Speakers (2 Out)"},
                {"uniqueID": OUT2, "name": "Alt - Speakers (2 Out)"},
            ],
            "input_patches": [
                {"uniqueID": IN1, "name": "Mic - System Input - Microphone (1 In)"},
            ],
        }},
    })
    summary = {
        "output_patches": [{"id": OUT1, "name": "Main"}, {"id": OUT2, "name": "Alt"}],
        "input_patches": [{"id": IN1, "name": "Mic"}],
    }

    result = _verify_live(reader, WS, summary)

    assert "IDs/order" in result["scope"]
    assert "canonical names" in result["scope"]

    reader_reordered = SimpleNamespace(get_workspace_settings=lambda *args, **kwargs: {
        "errors": {},
        "sections": {"audio": {
            "output_patches": [
                {"uniqueID": OUT2, "name": "Alt - Speakers (2 Out)"},
                {"uniqueID": OUT1, "name": "Main - System Output - Speakers (2 Out)"},
            ],
            "input_patches": [{"uniqueID": IN1, "name": "Mic - System Input - Microphone (1 In)"}],
        }},
    })
    with pytest.raises(ValueError, match="IDs/order"):
        _verify_live(reader_reordered, WS, summary)


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


def test_system_device_disable_confirmation_binds_to_passive_inventory(monkeypatch):
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
    result = edit_saved_audio_patches(SimpleNamespace(), WS, [{
        "action": "set_system_device", "patch_type": "output", "patch_id": OUT1, "enabled": False,
    }], dry_run=False, confirm_token="stale")

    assert result["status"] == "blocked"
    assert "device inventory changed since preview" in result["error"]
