"""Fade curve reads must remain separate from the trajectory and write API."""
import pytest
from qlab_mcp.light_patch.archive import Archive
from qlab_mcp.saved_cue_settings import inspect_saved_cue
from test_light_cue_curves import CUE, _workspace_with_curves


def fade_source(native_type=0):
    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    inner.objects[ids["target_cue"].data]["$class"] = inner.cls("FadeCue")
    inner.objects[ids["up_shape"].data]["type"] = native_type
    inner.ref(inner.objects[ids["target_cue"].data]["fade"])["fadeType"] = 2
    carrier["NS.data"] = inner.dump()
    return outer.dump()


def test_saved_fade_curve_reports_shape_and_trajectory_separately():
    result = inspect_saved_cue(fade_source(), CUE, include_audio_effects=False)
    curve = result["settings"]["fade_curve"]
    assert curve["trajectory_type"] == 2
    assert curve["up"]["type"] == "custom"
    assert curve["up"]["points"][1] == {"t": 0.5, "v": 0.6}
    assert curve["down"]["type"] == "custom"


def test_unknown_curve_type_is_partial_and_not_guessed():
    result = inspect_saved_cue(fade_source(99), CUE, include_audio_effects=False)
    assert result["status"] == "partial"
    assert result["settings"]["fade_curve"]["up"]["type"] is None
    assert "unknown_curve_type" in result["settings"]["fade_curve"]["up"]["issues"]


@pytest.mark.parametrize(("native", "expected"), [(0, "custom"), (1, "s_curve"), (2, "parametric"), (3, "linear")])
def test_known_curve_types(native, expected):
    result = inspect_saved_cue(fade_source(native), CUE, include_audio_effects=False)
    assert result["settings"]["fade_curve"]["up"]["type"] == expected


def test_group_playlist_curves_are_read_without_enabling_writes():
    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    cue = inner.objects[ids["target_cue"].data]
    cue["$class"] = inner.cls("GroupCue")
    cue["cues"] = inner.add({"$class": inner.cls("NSArray"), "NS.objects": []})
    cue["playlistInFade"] = cue["fade"]
    cue["playlistOutFade"] = cue["fade"]
    inner.ref(cue["fade"])["fadeType"] = 1
    carrier["NS.data"] = inner.dump()
    result = inspect_saved_cue(outer.dump(), CUE, include_audio_effects=False)
    assert result["cue_type"] == "Group"
    assert result["settings"]["playlist_curves"]["in"]["up"]["type"] == "custom"
