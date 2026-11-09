"""Saved cue edits isolate shared objects and preserve unrelated configuration."""
import plistlib

import pytest

from qlab_mcp.light_patch.archive import Archive
from test_light_cue_curves import CUE, OTHER, _workspace_with_curves


def source():
    data, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(data)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    hotkey = inner.add({"$class": inner.cls("F53HotKey"), "QLActionKeyKeyCode": 0,
        "QLActionKeyKeyCharacter": 0, **{f"QLActionKey{k}": False for k in
        ("Shift", "Control", "Option", "Command", "CapsLock", "NumericPad", "Function")}})
    for uid in (ids["target_cue"], ids["other_cue"]):
        inner.ref(uid).update(hotKey=hotkey, useHotKey=False, useWallClock=False, wallClockMode=0,
            **{f"wall{day}": True for day in ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")})
    carrier["NS.data"] = inner.dump()
    return outer.dump()


def test_hotkey_copy_on_write_preserves_other_cue():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = source()
    plan = plan_saved_cue_settings(original, [dict(action="set_hotkey", cue_id=CUE,
        key_code=4, character="h", modifiers=["control", "option"])])
    after = inspect_saved_cue(plan["output_bytes"], CUE)
    assert after["settings"]["hotkey"]["key_code"] == 4
    assert after["settings"]["hotkey"]["modifiers"] == ["control", "option"]
    assert after["settings"]["hotkey"]["enabled"] is False
    assert inspect_saved_cue(plan["output_bytes"], OTHER) == inspect_saved_cue(original, OTHER)
    assert plan["summary"]


def test_weekdays_are_an_explicit_replacement_and_repeat_is_no_op():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    op = dict(action="set_wall_clock_days", cue_id=CUE, days=["monday", "friday"])
    plan = plan_saved_cue_settings(source(), [op])
    assert inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["wall_clock"]["days"] == ["monday", "friday"]
    again = plan_saved_cue_settings(plan["output_bytes"], [op])
    assert again["output_bytes"] == plan["output_bytes"] and not again["changes"]


def test_hotkey_assignment_requires_disabled_trigger():
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    original = source()
    outer = Archive(original); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    from qlab_mcp.light_patch.curves import _reachable_cues
    _reachable_cues(inner)[0][CUE.upper()][0]["useHotKey"] = True
    carrier["NS.data"] = inner.dump()
    with pytest.raises(ValueError, match="disabled"):
        plan_saved_cue_settings(outer.dump(), [dict(action="set_hotkey", cue_id=CUE,
            key_code=4, character="h", modifiers=[])])


def test_hotkey_activation_requires_assigned_key_and_disarmed_cue():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = source()
    enable = dict(action="set_hotkey_enabled", cue_id=CUE, enabled=True)
    with pytest.raises(ValueError):
        plan_saved_cue_settings(original, [enable])
    outer = Archive(original); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    from qlab_mcp.light_patch.curves import _reachable_cues
    cue = _reachable_cues(inner)[0][CUE.upper()][0]
    cue.update(armed=False, continueMode=0, skipIfDisarmed=False)
    carrier["NS.data"] = inner.dump()
    assigned = plan_saved_cue_settings(outer.dump(), [dict(action="set_hotkey", cue_id=CUE,
        key_code=4, character="h", modifiers=["control"])])
    plan = plan_saved_cue_settings(assigned["output_bytes"], [enable])
    assert inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["hotkey"]["enabled"] is True


def test_unreachable_cue_and_unknown_operations_are_rejected():
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    with pytest.raises(ValueError):
        plan_saved_cue_settings(source(), [dict(action="set_unknown", cue_id=CUE)])
    with pytest.raises(ValueError, match="active"):
        plan_saved_cue_settings(source(), [dict(action="set_wall_clock_days",
            cue_id="00000000-0000-4000-8000-000000000001", days=[])])


def video_source():
    from qlab_mcp.light_patch.curves import _reachable_cues
    outer = Archive(source()); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"]); cue = _reachable_cues(inner)[0][CUE.upper()][0]
    audio = dict(cue)
    audio.update({"$class": inner.cls("AudioCue"), "track": -1, "inputNames": plistlib.UID(0),
        "levels": inner.add({"$class": inner.cls("AudioLevelMatrix"), "gangs": inner.make_dict({})}),
        "doFade": False, "lockFadeToCue": False})
    shapes = inner.ref(inner.ref(audio["fade"])["shapes"])
    inner.ref(shapes["domain"])["mode"] = 1
    down = inner.ref(shapes["downShape"])
    inner.ref(inner.array(down["shapeEntries"])[-1])["v"] = 1.0
    cue["$class"] = inner.cls("VideoCue"); cue["audioCue"] = inner.add(audio)
    cue["videoEffects"] = inner.make_dict({"effectEntries": inner.make_array([])})
    carrier["NS.data"] = inner.dump()
    return outer.dump()


def _add_audio_effect(a, name, identifier, *, enabled=True, parameter=0.5):
    state = a.make_dict({
        "displayName": a.add(name),
        "manufacturer": a.add("Fixture Audio Unit"),
        "component": a.add(b"fixture-au-component"),
        "class": a.add("AudioUnit"),
        "name": a.add(name),
        "enabled": a.add(enabled),
        "settings": a.make_dict({"gain": a.add(parameter)}),
    })
    return a.add({"$class": a.cls("F53Effect"), "identifier": a.add(identifier),
                  "frameIdentifier": plistlib.UID(0), "state": state})


def audio_fx_source(cue_type="Audio", *, video=False):
    from qlab_mcp.light_patch.curves import _reachable_cues
    outer = Archive(video_source() if video else source())
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    a = Archive(carrier["NS.data"])
    cue = _reachable_cues(a, ("VideoCue",) if video else ("LightCue",))[0][CUE.upper()][0]
    if video:
        audio = a.ref(cue["audioCue"])
    else:
        cue["$class"] = a.cls(f"{cue_type}Cue")
        audio = cue
    effects = [_add_audio_effect(a, "Fixture Reverb", "fx-1", parameter=0.25),
               _add_audio_effect(a, "Fixture Compressor", "fx-2", enabled=True, parameter=1.25)]
    audio["effects"] = a.make_array(effects)
    carrier["NS.data"] = a.dump()
    return outer.dump()


OBJECT_ID = "A0000000-0000-4000-8000-000000000001"


def audio_object_source(*, mapped=False, shared=False, video_owner=False, map_owned=False, duplicate=False):
    from qlab_mcp.light_patch.curves import _reachable_cues

    outer = Archive(source())
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    a = Archive(carrier["NS.data"])
    cues, _ = _reachable_cues(a, ("LightCue",))
    cue, other = cues[CUE.upper()][0], cues[OTHER.upper()][0]
    cue_ref = plistlib.UID(cues[CUE.upper()][1])
    cue["$class"] = a.cls("AudioCue")
    cue["audioMapID"] = a.add("attached-map") if mapped else a.add("")
    obj = a.add({"$class": a.cls("F53AudioObject"), "uniqueID": a.add(OBJECT_ID),
                 "name": a.add("Fixture Object"), "spread": 0.0})

    def collection(references):
        return a.add({"$class": a.cls("AudioObjectCollection"),
                      "audioObjects": a.make_array(references)})

    cue["audioObjects"] = collection([obj])
    if shared:
        other["$class"] = a.cls("MicCue")
        other["audioMapID"] = a.add("")
        other["audioObjects"] = collection([obj])
    if video_owner:
        other["$class"] = a.cls("VideoCue")
        other["audioCue"] = cue_ref
    if duplicate:
        a.add({"$class": a.cls("F53AudioObject"), "uniqueID": a.add(OBJECT_ID),
               "name": a.add("Duplicate"), "spread": 0.0})
    carrier["NS.data"] = a.dump()
    if map_owned:
        map_object = outer.add({"$class": outer.cls("F53AudioObject"),
                                "uniqueID": outer.add(OBJECT_ID), "name": outer.add("Map Object"),
                                "spread": 0.0})
        map_collection = outer.add({"$class": outer.cls("AudioObjectCollection"),
                                   "audioObjects": outer.make_array([map_object])})
        outer.add({"$class": outer.cls("AudioMap"), "audioObjects": map_collection})
    return outer.dump()


def test_saved_audio_object_owner_requires_direct_unmapped_cue_collection():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue_object_ownership

    result = inspect_saved_cue_object_ownership(audio_object_source(), CUE, [OBJECT_ID])
    assert result == {
        "source": "saved_archive", "workspace_id": "11111111-1111-4111-8111-111111111111",
        "cue_id": CUE.upper(), "cue_type": "Audio", "audio_map_id": "",
        "object_ids": [OBJECT_ID], "ownership": "direct_cue_collection",
    }


@pytest.mark.parametrize("fixture, message", [
    ({"mapped": True}, "Audio Map"),
    ({"shared": True}, "another cue"),
    ({"video_owner": True}, "embedded audio track"),
    ({"map_owned": True}, "Audio Map"),
    ({"duplicate": True}, "duplicated outside"),
])
def test_saved_audio_object_owner_rejects_map_shared_or_ambiguous_ids(fixture, message):
    from qlab_mcp.saved_cue_settings import inspect_saved_cue_object_ownership

    with pytest.raises(ValueError, match=message):
        inspect_saved_cue_object_ownership(audio_object_source(**fixture), CUE, [OBJECT_ID])


def test_saved_audio_object_owner_rejects_an_object_not_in_the_cue_collection():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue_object_ownership

    with pytest.raises(ValueError, match="absent from the cue-owned"):
        inspect_saved_cue_object_ownership(audio_object_source(), CUE,
                                           ["A0000000-0000-4000-8000-000000000002"])


def test_saved_audio_object_ownership_read_is_clean_and_hash_bound(monkeypatch):
    import hashlib
    from qlab_mcp import saved_cue_settings, workspace_documents

    data = audio_object_source()
    row = {"workspace_id": "11111111-1111-4111-8111-111111111111",
           "path": "/private/tmp/audio-object-owner-fixture.qlab5", "modified": False}
    monkeypatch.setattr(workspace_documents, "_local", lambda reader: None)
    monkeypatch.setattr(workspace_documents, "_inventory", lambda reader: {"documents": [row]})
    monkeypatch.setattr(workspace_documents, "_document", lambda inventory, workspace_id: row.copy())
    monkeypatch.setattr("qlab_mcp.light_patch.reader._read_file", lambda path: (data, (1, 2, len(data), 3)))

    result = saved_cue_settings.read_saved_cue_object_ownership(
        object(), "11111111-1111-4111-8111-111111111111", CUE, [OBJECT_ID],
    )
    assert result["sha256"] == hashlib.sha256(data).hexdigest()
    assert result["freshness"] == "last_saved"
    assert result["ownership"] == "direct_cue_collection"


def test_saved_audio_object_ownership_read_blocks_dirty_workspace(monkeypatch):
    from qlab_mcp import saved_cue_settings, workspace_documents

    row = {"workspace_id": "11111111-1111-4111-8111-111111111111",
           "path": "/private/tmp/audio-object-owner-fixture.qlab5", "modified": True}
    monkeypatch.setattr(workspace_documents, "_local", lambda reader: None)
    monkeypatch.setattr(workspace_documents, "_inventory", lambda reader: {"documents": [row]})
    monkeypatch.setattr(workspace_documents, "_document", lambda inventory, workspace_id: row.copy())
    with pytest.raises(ValueError, match="Save or discard"):
        saved_cue_settings.read_saved_cue_object_ownership(
            object(), "11111111-1111-4111-8111-111111111111", CUE, [OBJECT_ID],
        )


def test_video_envelope_is_in_embedded_audio_and_preserves_light_curves():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = video_source()
    points = [{"t": 0, "v": .2}, {"t": .3, "v": .8}, {"t": 1, "v": .4}]
    plan = plan_saved_cue_settings(original, [dict(action="set_integrated_audio_fade", cue_id=CUE,
        type="linear", points=points)])
    result = inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["video_audio"]["integrated_fade"]
    assert result["points"] == points and result["type"] == "linear"
    assert result["enabled"] is False and result["lock_to_cue"] is False
    assert inspect_saved_cue(plan["output_bytes"], OTHER) == inspect_saved_cue(original, OTHER)


@pytest.mark.parametrize("points", [[{"t": 0, "v": 1}],
    [{"t": 0, "v": 1}, {"t": .3, "v": 0}],
    [{"t": 0, "v": 1}, {"t": .5, "v": 0}, {"t": .5, "v": 1}, {"t": 1, "v": 1}]])
def test_video_envelope_rejects_partial_or_unordered_replacement(points):
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    with pytest.raises(ValueError):
        plan_saved_cue_settings(video_source(), [dict(action="set_integrated_audio_fade", cue_id=CUE,
            type="custom", points=points)])


def test_insert_native_fx_preserves_order_and_allocates_instance_ids():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = video_source()
    operations = [dict(action="insert_video_effect", cue_id=CUE, effect_type=name, index=0)
                  for name in ("LinearKey", "DropShadow")]
    plan = plan_saved_cue_settings(original, operations)
    effects = inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["video_effects"]
    assert [e["type"] for e in effects] == ["DropShadow", "LinearKey"]
    assert [e["instance_id"] for e in effects] == [2, 1]
    assert all(e["enabled"] for e in effects)
    assert inspect_saved_cue(plan["output_bytes"], OTHER) == inspect_saved_cue(original, OTHER)
    outer = Archive(plan["output_bytes"])
    inner = Archive(outer.ref(outer.mapping(outer.root)["cueLists"])["NS.data"])
    for obj in inner.objects:
        if isinstance(obj, dict) and "NS.keys" in obj:
            assert all(isinstance(ref, plistlib.UID) for ref in obj["NS.objects"]), "NSKeyedArchiver dictionaries require object references"


def test_audio_track_selection_requires_exact_media_dependency():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = video_source()
    op = dict(action="select_audio_track", cue_id=CUE, track_id=3)
    with pytest.raises(ValueError):
        plan_saved_cue_settings(original, [op])
    context = {CUE.upper(): {"track_ids": [2, 3], "path": "/fixture.mov"}}
    plan = plan_saved_cue_settings(original, [op], media=context)
    assert inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["video_audio"]["track"] == 3
    with pytest.raises(ValueError):
        plan_saved_cue_settings(original, [{**op, "track_id": 4}], media=context)


def test_sparse_channel_metadata_decodes_names_and_gang_member_coordinates():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue
    from qlab_mcp.light_patch.curves import _reachable_cues
    outer = Archive(video_source()); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    a = Archive(carrier["NS.data"]); cue = _reachable_cues(a, ("VideoCue",))[0][CUE.upper()][0]
    audio = a.ref(cue["audioCue"]); audio["inputNames"] = a.make_dict({1:a.add("Left")})
    knobs = a.add({"$class":a.cls("AudioLevelKnobs"), "row":1,"column":2,"gang":a.add("A")})
    a.ref(audio["levels"])["gangs"] = a.make_dict({"A":a.make_array([knobs])})
    carrier["NS.data"] = a.dump()
    metadata = inspect_saved_cue(outer.dump(), CUE)["settings"]["video_audio"]
    assert metadata["input_channel_names"] == [{"native_key":1,"channel":1,"name":"Left"}]
    assert metadata["gangs"] == [{"name":"A","members":[{"row":1,"column":2}]}]


@pytest.mark.parametrize("modified", [False, True])
def test_read_saved_settings_preserves_clean_and_dirty_provenance(monkeypatch, modified):
    from test_light_cue_saved_curves import _reader
    from test_light_cue_curves import WS
    from qlab_mcp.saved_cue_settings import read_saved_cue_settings
    data = source()
    reader = _reader(monkeypatch, data, modified=modified)
    result = read_saved_cue_settings(reader, WS, CUE)
    assert result["status"] == "ready"
    assert result["freshness"] == ("possibly_stale" if modified else "last_saved")
    assert result["document_modified"] is modified and len(result["sha256"]) == 64


def test_changed_file_discards_all_saved_settings(monkeypatch):
    from test_light_cue_saved_curves import _reader
    from test_light_cue_curves import WS
    from qlab_mcp.saved_cue_settings import read_saved_cue_settings
    result = read_saved_cue_settings(_reader(monkeypatch, source(), changed=True), WS, CUE)
    assert result["status"] == "changed_during_read" and not result["settings"]


def test_assignment_and_activation_cannot_share_a_batch():
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    with pytest.raises(ValueError, match="separate"):
        plan_saved_cue_settings(source(), [dict(action="set_hotkey",cue_id=CUE,key_code=4,character="h",modifiers=[]),
            dict(action="set_hotkey_enabled",cue_id=CUE,enabled=True)])


def test_unknown_channel_metadata_preserves_readable_track_and_envelope():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue
    from qlab_mcp.light_patch.curves import _reachable_cues
    outer = Archive(video_source()); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    a = Archive(carrier["NS.data"]); cue = _reachable_cues(a,("VideoCue",))[0][CUE.upper()][0]
    a.ref(a.ref(cue["audioCue"])["levels"])["gangs"] = a.add("unknown variant")
    carrier["NS.data"] = a.dump()
    report = inspect_saved_cue(outer.dump(), CUE)
    assert report["status"] == "partial"
    assert report["settings"]["video_audio"]["track"] == -1
    assert report["settings"]["video_audio"]["integrated_fade"]["points"]


def test_batch_returning_to_original_state_does_not_rewrite():
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings, DAYS
    original = source()
    plan = plan_saved_cue_settings(original, [
        dict(action='set_wall_clock_days', cue_id=CUE, days=['monday']),
        dict(action='set_wall_clock_days', cue_id=CUE, days=list(DAYS)),
    ])
    assert plan['output_bytes'] == original
    assert not plan['changes']


def test_native_effect_verification_rejects_wrong_type_with_same_count(monkeypatch):
    from qlab_mcp import saved_cue_settings as saved
    expected = dict(cue_type='Video', settings=dict(video_effects=[dict(type='LinearKey')]))
    def scalar(reader, ws, uid, key):
        return {'uniqueID':CUE.upper(), 'type':'Video', 'videoEffects':[{'type':'DropShadow'}]}[key]
    monkeypatch.setattr('qlab_mcp.write.control._scalar', scalar)
    with pytest.raises(ValueError, match='types'):
        saved._verify_live(None, 'ws', dict(media={}, cues={CUE.upper():expected}))


def test_batch_envelope_point_budget_is_bounded():
    from pydantic import TypeAdapter
    from qlab_mcp.saved_cue_settings import SavedCueOperations
    operation = dict(action='set_integrated_audio_fade', cue_id=CUE, type='custom',
        points=[dict(t=i/4095,v=1) for i in range(4096)])
    with pytest.raises(ValueError, match='8192'):
        TypeAdapter(SavedCueOperations).validate_python([operation]*3)


def test_native_untyped_fx_inventory_does_not_claim_type_observation(monkeypatch):
    from qlab_mcp import saved_cue_settings as saved
    expected = dict(cue_type='Video', settings=dict(video_effects=[dict(type='LinearKey')]))
    monkeypatch.setattr('qlab_mcp.write.control._scalar', lambda reader,ws,uid,key:
        {'uniqueID':CUE.upper(),'type':'Video','videoEffects':[{'inputThreshold':0}]}[key])
    result = saved._verify_live(None,'ws',dict(media={},cues={CUE.upper():expected}))
    assert result['effect_types_observed'] is False


@pytest.mark.parametrize(("cue_type", "video"), [("Audio", False), ("Mic", False), ("Video", True)])
def test_saved_audio_effects_include_identity_and_observed_parameters(cue_type, video):
    from qlab_mcp.saved_cue_settings import inspect_saved_cue
    saved = inspect_saved_cue(audio_fx_source(cue_type, video=video), CUE)
    effects = saved["settings"]["audio_effects"]
    assert [effect["identifier"] for effect in effects] == ["fx-1", "fx-2"]
    assert [effect["type"] for effect in effects] == ["Fixture Reverb", "Fixture Compressor"]
    assert effects[0]["enabled"] is True
    assert effects[0]["parameters"] == [
        {"key": "gain", "value": 0.25, "source": "saved_audio_unit_state"}
    ]
    if video:
        assert saved["settings"]["video_audio"]["track"] == -1


@pytest.mark.parametrize("cue_type", ["Audio", "Mic"])
def test_audio_and_mic_details_enrich_saved_audio_fx(monkeypatch, cue_type):
    from test_light_cue_saved_curves import _reader
    from test_light_cue_curves import WS
    from qlab_mcp.saved_cue_settings import enrich_cue_details
    if cue_type == "Audio":
        from qlab_mcp.cues.audio import AudioCueDetailsResult, AudioCueSummary
        result = AudioCueDetailsResult(workspace_id=WS, cue_id=CUE,
            identity=AudioCueSummary(uniqueID=CUE, type="Audio"))
    else:
        from qlab_mcp.cues.mic import MicCueDetailsResult, MicCueSummary
        result = MicCueDetailsResult(workspace_id=WS, cue_id=CUE,
            identity=MicCueSummary(uniqueID=CUE, type="Mic"))
    enriched = enrich_cue_details(_reader(monkeypatch, audio_fx_source(cue_type)), result)
    assert enriched.saved_settings.status == "ready"
    assert enriched.saved_settings.settings.audio_effects[0]["identifier"] == "fx-1"
    operations = enriched.edit_capabilities["saved_settings"]["operations"]
    assert "remove_audio_effect" in operations
    assert "set_audio_effect_bypassed" in operations


def test_audio_effect_chain_supports_only_remove_move_and_bypass_with_exact_postcondition():
    from qlab_mcp.saved_cue_settings import _postcondition, inspect_saved_cue, plan_saved_cue_settings
    original = audio_fx_source()
    operations = [
        dict(action="move_audio_effect", cue_id=CUE, effect_index=1, new_index=0),
        dict(action="set_audio_effect_bypassed", cue_id=CUE, effect_index=0, bypassed=True),
        dict(action="remove_audio_effect", cue_id=CUE, effect_index=1),
    ]
    plan = plan_saved_cue_settings(original, operations)
    effects = inspect_saved_cue(plan["output_bytes"], CUE)["settings"]["audio_effects"]
    assert [effect["identifier"] for effect in effects] == ["fx-2"]
    assert effects[0]["enabled"] is False
    assert effects[0]["parameters"] == [
        {"key": "gain", "value": 1.25, "source": "saved_audio_unit_state"}
    ]
    assert _postcondition(plan["output_bytes"], plan)
    assert [effect["identifier"] for effect in inspect_saved_cue(original, CUE)["settings"]["audio_effects"]] == ["fx-1", "fx-2"]


def test_audio_fx_edits_preserve_video_track_selection_and_video_fx_behavior():
    from qlab_mcp.saved_cue_settings import inspect_saved_cue, plan_saved_cue_settings
    original = audio_fx_source("Video", video=True)
    plan = plan_saved_cue_settings(original, [
        dict(action="select_audio_track", cue_id=CUE, track_id=3),
        dict(action="move_audio_effect", cue_id=CUE, effect_index=0, new_index=1),
    ], media={CUE.upper(): {"track_ids": [2, 3], "path": "/fixture.mov"}})
    settings = inspect_saved_cue(plan["output_bytes"], CUE)["settings"]
    assert settings["video_audio"]["track"] == 3
    assert [effect["identifier"] for effect in settings["audio_effects"]] == ["fx-2", "fx-1"]
    assert settings["video_effects"] == []


def test_audio_fx_edits_reject_missing_or_ambiguous_identity():
    from qlab_mcp.light_patch.curves import _reachable_cues
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    outer = Archive(audio_fx_source())
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    a = Archive(carrier["NS.data"])
    cue = _reachable_cues(a, ("AudioCue",))[0][CUE.upper()][0]
    refs = a.array(cue["effects"])
    a.ref(refs[1])["identifier"] = a.add("fx-1")
    carrier["NS.data"] = a.dump()
    with pytest.raises(ValueError, match="ambiguous"):
        plan_saved_cue_settings(outer.dump(), [dict(action="remove_audio_effect", cue_id=CUE, effect_index=0)])


def test_saved_audio_fx_operation_schemas_have_distinct_strict_fields():
    from pydantic import TypeAdapter
    from qlab_mcp.saved_cue_settings import SavedCueOperations
    adapter = TypeAdapter(SavedCueOperations)
    assert adapter.validate_python([dict(action="remove_audio_effect", cue_id=CUE, effect_index=0)])
    assert adapter.validate_python([dict(action="move_audio_effect", cue_id=CUE, effect_index=0, new_index=1)])
    assert adapter.validate_python([dict(action="set_audio_effect_bypassed", cue_id=CUE, effect_index=0, bypassed=True)])
    with pytest.raises(ValueError):
        adapter.validate_python([dict(action="remove_audio_effect", cue_id=CUE, effect_index=0, new_index=1)])
    with pytest.raises(ValueError):
        adapter.validate_python([dict(action="move_audio_effect", cue_id=CUE, effect_index=0)])
    with pytest.raises(ValueError):
        adapter.validate_python([dict(action="set_audio_effect_bypassed", cue_id=CUE, effect_index=50, bypassed=True)])


def test_audio_and_mic_fx_scope_does_not_expand_hotkey_or_video_operations():
    from qlab_mcp.saved_cue_settings import plan_saved_cue_settings
    with pytest.raises(ValueError, match="Hotkey and Wall Clock"):
        plan_saved_cue_settings(audio_fx_source("Audio"), [dict(
            action="set_wall_clock_days", cue_id=CUE, days=["monday"]
        )])
    with pytest.raises(ValueError, match="require a Video cue"):
        plan_saved_cue_settings(audio_fx_source("Mic"), [dict(
            action="select_audio_track", cue_id=CUE, track_id=-1
        )])
