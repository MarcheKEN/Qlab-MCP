"""The research probe must tolerate cyclic curve references without mutating input."""
import plistlib
import runpy
from pathlib import Path

import pytest


inspect_curves = runpy.run_path(str(Path(__file__).parents[1] / "scripts/inspect_light_authoring.py"))["inspect_curves"]
prepare_sample = runpy.run_path(str(Path(__file__).parents[1] / "scripts/inspect_light_authoring.py"))["prepare_curve_point_sample"]


def test_curve_probe_follows_points_without_expanding_link_cycles():
    objects = ["$null"]
    def add(value):
        objects.append(value)
        return plistlib.UID(len(objects) - 1)
    def cls(name):
        return add({"$classname": name, "$classes": [name, "NSObject"]})
    point = add({"t": 0.0, "v": 0.0})
    objects[point.data].update(previous=point, next=point)
    entries = add({"NS.objects": [point]})
    shape = add({"type": 0, "curveParameter": 1.0, "shapeEntries": entries})
    shapes = add({"upShape": shape, "downShape": shape, "mirrorShape": False})
    fade = add({"shapes": shapes})
    root = add({"$class": cls("LightCue"), "fade": fade})
    source = plistlib.dumps(dict(archiver="unused", **{"$archiver": "NSKeyedArchiver",
        "$version": 100000, "$top": {"root": root}, "$objects": objects}), fmt=plistlib.FMT_BINARY)
    result = inspect_curves(source)
    assert result["samples"][0]["curves"]["upShape"]["points"] == [{"t": 0.0, "v": 0.0}]
    assert result["write_acceptance"] == "not_demonstrated"
    assert plistlib.loads(source)["$objects"][point.data]["next"] == point


def test_curve_probe_rejects_invalid_archive():
    with pytest.raises(ValueError):
        inspect_curves(b"not an archive")


def test_offline_point_sample_preserves_other_fields_and_source():
    from qlab_mcp.light_patch.archive import Archive
    from test_light_patch_archive import workspace
    a = Archive(workspace())
    points = [a.add({"t": t, "v": v}) for t, v in ((0., 0.), (.5, .7), (1., 1.))]
    shape = a.add({"type": 0, "curveParameter": 1., "shapeEntries": a.make_array(points)})
    shapes = a.add({"upShape": shape, "unknown": "preserve"})
    cue = a.add({"$class": a.cls("LightCue"), "uniqueID": a.add("exact-id"),
                 "fade": a.add({"shapes": shapes})})
    inner = Archive(workspace())
    inner.data = {**a.data, "$top": {"root": a.make_array([cue])}}
    carrier = a.add({"NS.data": inner.dump()})
    root = a.mapping(a.root)
    root["cueLists"] = carrier
    a.data["$top"] = {"root": a.make_dict(root)}
    source = a.dump()
    output = prepare_sample(source, "exact-id", 1, .8)
    before, after = inspect_curves(source), inspect_curves(output)
    assert before["samples"][0]["curves"]["upShape"]["points"][1]["v"] == .7
    saved = next(sample for sample in after["samples"] if sample["location"] != "outer")
    assert saved["curves"]["upShape"]["points"][1]["v"] == .8
    outer = Archive(output)
    assert outer.ref(outer.mapping(outer.root)["unrelated"]) == "keep cues"
    for args in (("wrong-id", 1, .8), ("exact-id", 0, .8), ("exact-id", 1, float("nan"))):
        with pytest.raises(ValueError):
            prepare_sample(source, *args)
