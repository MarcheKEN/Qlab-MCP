"""The Playlist duration edit must preserve curve and archive ownership."""

import pytest

from qlab_mcp.light_patch.archive import Archive
from qlab_mcp.saved_cue_settings import _archive
from test_light_cue_curves import CUE, OTHER, _workspace_with_curves


def playlist_workspace():
    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    inner.ref(ids["up_shape"]).pop("extraShapeField")
    cue = inner.ref(ids["target_cue"])
    cue.update({"$class": inner.cls("GroupCue"), "groupMode": 6,
                "cues": inner.make_array([]), "playlistCrossfadeDuration": inner.add(3.0),
                "playlistOffsetTime": inner.add(-2.0),
                "playlistInFade": cue["fade"], "playlistOutFade": cue["fade"]})
    inner.ref(cue["fade"]).update(duration=1.0, fadeType=1)
    carrier["NS.data"] = inner.dump()
    return outer.dump()


def test_saved_crossfade_scales_durations_and_preserves_shared_shapes():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    source = playlist_workspace()
    _, _, _, before, old, _ = _archive(source, include_fade=True)
    plan = plan_playlist_crossfade(source, [{"cue_id": CUE, "duration": 6.0}], cue_id=CUE)
    _, _, _, after, new, _ = _archive(plan["output_bytes"], include_fade=True)
    group = new[CUE.upper()][0]
    assert after.ref(group["playlistCrossfadeDuration"]) == 6.0
    assert after.ref(group["playlistOffsetTime"]) == -4.0
    for key in ("playlistInFade", "playlistOutFade"):
        assert after.ref(group[key])["duration"] == 2.0
        assert after.ref(group[key])["shapes"] == before.ref(old[CUE.upper()][0][key])["shapes"]
    assert group["playlistInFade"] == group["playlistOutFade"]
    assert after.ref(new[OTHER.upper()][0]["fade"]) == before.ref(old[OTHER.upper()][0]["fade"])


@pytest.mark.parametrize("duration", [0, -1, float("nan"), float("inf"), True])
def test_saved_crossfade_rejects_unverified_durations(duration):
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    with pytest.raises(ValueError):
        plan_playlist_crossfade(playlist_workspace(), [{"cue_id": CUE, "duration": duration}], cue_id=CUE)


def test_saved_crossfade_refuses_nonplaylist():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    source = playlist_workspace()
    outer = Archive(source); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    from qlab_mcp.light_patch.curves import _reachable_cues
    _reachable_cues(inner, ("GroupCue",))[0][CUE.upper()][0]["groupMode"] = 3
    carrier["NS.data"] = inner.dump()
    with pytest.raises(ValueError, match="Playlist"):
        plan_playlist_crossfade(outer.dump(), [{"cue_id": CUE, "duration": 1.0}], cue_id=CUE)


def test_saved_crossfade_noop_keeps_original_bytes():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    source = playlist_workspace()
    plan = plan_playlist_crossfade(source, [{"cue_id": CUE, "duration": 3.0}], cue_id=CUE)
    assert plan["output_bytes"] == source
    assert plan["changes"] == []


def test_saved_crossfade_does_not_parse_unrelated_light_patch():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    outer = Archive(playlist_workspace())
    settings = outer.mapping(outer.mapping(outer.root)["settings"])
    light = outer.mapping(settings["Light"])
    outer.ref(light["patch"])["NS.data"] = b"unrecognized light data"
    plan = plan_playlist_crossfade(outer.dump(), [{"cue_id": CUE, "duration": 4.0}], cue_id=CUE)
    assert plan["changes"] and plan["summary"]["duration"] == 4.0


def test_saved_crossfade_blocks_automatic_open_or_close_cues():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    outer = Archive(playlist_workspace())
    settings = outer.mapping(outer.mapping(outer.root)["settings"])
    general_ref = settings["General"]
    general = outer.ref(general_ref)
    keys = [outer.ref(key) for key in general["NS.keys"]]
    general["NS.objects"][keys.index("doStartOnOpen")] = outer.add(True)
    with pytest.raises(ValueError, match="automatic open/close"):
        plan_playlist_crossfade(outer.dump(), [{"cue_id": CUE, "duration": 4.0}], cue_id=CUE)


def test_saved_crossfade_blocks_unknown_curve_fields():
    from qlab_mcp.write.playlist_archive import plan_playlist_crossfade

    source = playlist_workspace()
    outer = Archive(source); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    from qlab_mcp.light_patch.curves import _reachable_cues
    cue = _reachable_cues(inner, ("GroupCue",))[0][CUE.upper()][0]
    fade = inner.ref(cue["playlistInFade"])
    shapes = inner.ref(fade["shapes"])
    inner.ref(shapes["upShape"])["unknownFutureField"] = True
    carrier["NS.data"] = inner.dump()
    with pytest.raises(ValueError, match="curves"):
        plan_playlist_crossfade(outer.dump(), [{"cue_id": CUE, "duration": 4.0}], cue_id=CUE)


def test_archive_transaction_contract_and_recovery(monkeypatch):
    from qlab_mcp import workspace_archive
    from qlab_mcp.models import UpdateCuesResult
    from qlab_mcp.write import playlist_archive, safety
    from qlab_mcp.write.group import GroupCueEditInput

    base = {"source": {"playlist/crossfade/duration": 3.0}, "children": {}}
    monkeypatch.setattr(safety, "check_write_readiness", lambda *args: {"ok": True})
    monkeypatch.setattr(playlist_archive, "_context", lambda *args: base)
    archive_results = iter([
        {"ok": True, "status": "planned", "changes": [{}], "confirm_token": "confirm:archive"},
        {"ok": False, "status": "uncertain", "error": "reopen failed", "file_replaced": True,
         "recovery_path": "/tmp/recovery", "executed_operations": [{"action": "replace_file"}]},
    ])
    monkeypatch.setattr(workspace_archive, "edit_archive", lambda *args, **kwargs: next(archive_results))
    reader = type("Reader", (), {"client": type("Client", (), {"config": type("Config", (), {"write_dry_run_default": True})()})()})()
    ws = "11111111-1111-4111-8111-111111111111"
    item = GroupCueEditInput.model_validate({"cue_id": CUE,
        "properties": {"playlist/crossfade/duration": 4.0}})
    dry = UpdateCuesResult.model_validate(playlist_archive.edit_playlist_crossfade(reader, ws, item, True))
    assert dry.ok and dry.results[0].planned_operations[0]["confirm_token"] == "confirm:archive"
    item.confirm_gates = ["confirm:archive"]
    real = UpdateCuesResult.model_validate(playlist_archive.edit_playlist_crossfade(reader, ws, item, False))
    assert not real.ok and real.status == "verification_inconclusive"
    assert real.results[0].debug["archive_transaction"]["recovery_path"] == "/tmp/recovery"


def test_saved_crossfade_postcondition_detects_unknown_effect_change():
    from qlab_mcp.write.playlist_archive import _postcondition, plan_playlist_crossfade

    outer = Archive(playlist_workspace()); carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    from qlab_mcp.light_patch.curves import _reachable_cues
    other = _reachable_cues(inner, ("LightCue",))[0][OTHER.upper()][0]
    state = inner.add({"$class": inner.cls("UnknownEffectState"), "opaque": b"original"})
    other["effects"] = inner.make_array([state, state])
    carrier["NS.data"] = inner.dump()
    plan = plan_playlist_crossfade(outer.dump(), [{"cue_id": CUE, "duration": 4.0}], cue_id=CUE)
    assert _postcondition(plan["output_bytes"], plan)
    changed = Archive(plan["output_bytes"]); data = changed.ref(changed.mapping(changed.root)["cueLists"])
    inner = Archive(data["NS.data"]); inner.ref(state)["opaque"] = b"changed"
    data["NS.data"] = inner.dump()
    assert not _postcondition(changed.dump(), plan)


def test_archive_dependency_recheck_blocks_changed_children(monkeypatch):
    from qlab_mcp import workspace_archive
    from qlab_mcp.write import playlist_archive, safety
    from qlab_mcp.write.group import GroupCueEditInput

    state = {"source": {"playlist/crossfade/duration": 3.0}, "children": {"fingerprint": "a"}}
    monkeypatch.setattr(safety, "check_write_readiness", lambda *args: {"ok": True})
    monkeypatch.setattr(playlist_archive, "_context", lambda *args: state.copy())
    def archive(*args, **kwargs):
        state["children"] = {"fingerprint": "changed"}
        kwargs["dependency_check"]()
        raise AssertionError("changed dependency must fail first")
    monkeypatch.setattr(workspace_archive, "edit_archive", archive)
    reader = type("Reader", (), {"client": type("Client", (), {"config": type("Config", (), {"write_dry_run_default": True})()})()})()
    item = GroupCueEditInput.model_validate({"cue_id": CUE,
        "properties": {"playlist/crossfade/duration": 4.0}, "confirm_gates": ["token"]})
    result = playlist_archive.edit_playlist_crossfade(reader, "11111111-1111-4111-8111-111111111111", item, False)
    assert not result["ok"] and "changed" in str(result["results"][0]["errors"])
