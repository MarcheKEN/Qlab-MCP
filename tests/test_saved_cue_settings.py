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
