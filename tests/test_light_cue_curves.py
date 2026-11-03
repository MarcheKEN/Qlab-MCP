"""Bounded curve archive edits against synthetic QLab-shaped archives."""
import plistlib

import pytest

from qlab_mcp.light_patch.archive import Archive
from test_light_patch_archive import workspace


WS = "11111111-1111-4111-8111-111111111111"
CUE = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
OTHER = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def _workspace_with_curves(*, shared_shapes=True, mirror=False, domain_mode=0,
                           residual=False, unknown_point_fields=True,
                           duplicate_active=False):
    outer = Archive(workspace())
    objects = ["$null"]

    def add(value):
        objects.append(value)
        return plistlib.UID(len(objects) - 1)

    def cls(name):
        return add({"$classname": name, "$classes": [name, "NSObject"]})

    def array(values):
        return add({"$class": cls("NSMutableArray"), "NS.objects": list(values)})

    entry_class = cls("FadeShapeEntry")
    point_refs = []
    point_values = [(0.0, 0.0), (0.5, 0.6), (1.0, 1.0)]
    for index, (t, v) in enumerate(point_values):
        entry = {"$class": entry_class, "t": t, "v": v}
        if unknown_point_fields:
            entry["extra"] = f"preserve-{index}"
        point_refs.append(add(entry))
    for index, ref in enumerate(point_refs):
        objects[ref.data]["previous"] = point_refs[index - 1] if index else plistlib.UID(0)
        objects[ref.data]["next"] = point_refs[index + 1] if index + 1 < len(point_refs) else plistlib.UID(0)
    entry_array = array(point_refs)
    shape_ref = add({"$class": cls("FadeShape"), "type": 0,
                     "curveParameter": 1.0, "shapeEntries": entry_array,
                     "extraShapeField": "preserve"})
    down_refs = [add({"$class": entry_class, "t": 0.0, "v": 1.0, "previous": None}),
                 add({"$class": entry_class, "t": 1.0, "v": 0.0, "previous": None})]
    objects[down_refs[0].data]["next"] = down_refs[1]
    objects[down_refs[1].data]["previous"] = down_refs[0]
    objects[down_refs[1].data]["next"] = None
    down_shape = add({"$class": cls("FadeShape"), "type": 0,
                      "curveParameter": 1.0, "shapeEntries": array(down_refs)})
    domain = add({"$class": cls("FadeDomain"), "mode": domain_mode, "absolute": False})
    shapes = add({"$class": cls("FadeShapesFunction"), "upShape": shape_ref,
                  "downShape": down_shape, "mirrorShape": mirror,
                  "domain": domain, "resolution": 0.0033333332,
                  "extraShapesField": "preserve"})
    fade = add({"$class": cls("Fade"), "shapes": shapes, "extraFadeField": "preserve"})
    cue = add({"$class": cls("LightCue"), "uniqueID": CUE, "fade": fade})
    second_fade = add({"$class": cls("Fade"), "shapes": shapes if shared_shapes else add({
        "$class": cls("FadeShapesFunction"), "upShape": shape_ref,
        "downShape": down_shape, "mirrorShape": False, "domain": domain,
        "resolution": 0.0033333332})})
    other_cue = add({"$class": cls("LightCue"), "uniqueID": OTHER, "fade": second_fade})
    residual_ref = None
    if residual:
        residual_ref = add({"$class": cls("LightCue"), "uniqueID": CUE,
                            "fade": add({"$class": cls("Fade"), "shapes": shapes})})
    cue_list_root = array([cue, cue, other_cue] if duplicate_active else [cue, other_cue])
    inner = plistlib.dumps({"$archiver": "NSKeyedArchiver", "$version": 100000,
        "$top": {"root": cue_list_root}, "$objects": objects},
        fmt=plistlib.FMT_BINARY, sort_keys=False)
    outer_root_ref = outer.data["$top"]["root"]
    carrier = outer.add({"$class": outer.cls("NSMutableData"), "NS.data": inner,
                         "unknownCarrierField": "preserve"})
    root_value = outer.ref(outer_root_ref)
    root_value["NS.keys"].append(outer.add("cueLists"))
    root_value["NS.objects"].append(carrier)
    return outer.dump(), dict(target_cue=cue, other_cue=other_cue, shapes=shapes,
        up_shape=shape_ref, down_shape=down_shape, point_refs=point_refs,
        residual=residual_ref, carrier=carrier)


def _curves(source):
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    pending, seen, found = [inner.data["$top"]["root"]], set(), {}
    while pending:
        ref = pending.pop()
        if isinstance(ref, plistlib.UID):
            if ref.data in seen:
                continue
            seen.add(ref.data)
            value = inner.ref(ref)
        else:
            value = ref
        if isinstance(value, dict):
            if "$class" in value and inner.kind(value) == "LightCue":
                found[inner.ref(value.get("uniqueID"))] = value
            pending.extend(value.values())
        elif isinstance(value, list):
            pending.extend(value)
    result = {}
    for cue_id, cue in found.items():
        shapes = inner.ref(inner.ref(cue["fade"])["shapes"])
        sides = {}
        for side in ("upShape", "downShape"):
            shape = inner.ref(shapes[side])
            points = [inner.ref(ref) for ref in inner.array(shape["shapeEntries"])]
            sides[side] = dict(type=inner.ref(shape["type"]),
                parameter=inner.ref(shape["curveParameter"]),
                points=[(inner.ref(point["t"]), inner.ref(point["v"])) for point in points])
        result[cue_id] = sides
    return outer, inner, found, result


def test_custom_curve_edit_clones_shared_shape_and_rewires_every_point():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, ids = _workspace_with_curves(shared_shapes=True, residual=True)
    _, original_inner, original_cues, _ = _curves(source)
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"points": [{"t": 0.0, "v": 0.0},
                           {"t": 0.25, "v": 0.7},
                           {"t": 1.0, "v": 1.0}]}}])
    changed_outer, changed_inner, changed_cues, curves = _curves(plan["output_bytes"])

    assert curves[CUE]["upShape"]["points"] == [(0.0, 0.0), (0.25, 0.7), (1.0, 1.0)]
    assert curves[CUE]["upShape"]["type"] == 0
    assert curves[CUE]["upShape"]["parameter"] == 1.0
    assert curves[OTHER] == _curves(source)[3][OTHER]
    assert changed_inner.ref(changed_cues[CUE]["fade"]) != original_inner.ref(original_cues[CUE]["fade"])
    new_shapes_ref = changed_inner.ref(changed_cues[CUE]["fade"])["shapes"]
    old_shapes_ref = original_inner.ref(original_cues[CUE]["fade"])["shapes"]
    assert new_shapes_ref != old_shapes_ref
    new_shapes = changed_inner.ref(new_shapes_ref)
    assert new_shapes["downShape"] == original_inner.ref(old_shapes_ref)["downShape"]
    entries = changed_inner.array(changed_inner.ref(new_shapes["upShape"])["shapeEntries"])
    assert len(entries) == 3
    for index, ref in enumerate(entries):
        point = changed_inner.ref(ref)
        assert point["previous"] == (entries[index - 1] if index else plistlib.UID(0))
        assert point["next"] == (entries[index + 1] if index + 1 < len(entries) else plistlib.UID(0))
        if "extra" in point:
            assert point["extra"] == f"preserve-{index}"
    assert changed_outer.ref(changed_outer.mapping(changed_outer.root)["unrelated"]) == "keep cues"
    assert changed_outer.ref(changed_outer.mapping(changed_outer.root)["cueLists"])["unknownCarrierField"] == "preserve"
    assert plan["changes"]


def test_type_and_parameter_edit_preserves_points_and_other_curve():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"type": "parametric", "parameter": 2.5}}])
    _, _, _, values = _curves(plan["output_bytes"])
    _, _, _, before = _curves(source)
    assert values[CUE]["upShape"]["type"] == 2
    assert values[CUE]["upShape"]["parameter"] == 2.5
    assert values[CUE]["upShape"]["points"] == before[CUE]["upShape"]["points"]
    assert values[CUE]["downShape"] == before[CUE]["downShape"]


def test_linear_curve_points_can_be_replaced_and_type_is_preserved():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"type": "linear", "points": [{"t": 0.0, "v": 0.0},
                                               {"t": 0.4, "v": 0.2},
                                               {"t": 1.0, "v": 1.0}]}}])
    _, _, _, values = _curves(plan["output_bytes"])
    assert values[CUE]["upShape"]["type"] == 3
    assert values[CUE]["upShape"]["points"] == [(0.0, 0.0), (0.4, 0.2), (1.0, 1.0)]


def test_non_custom_non_linear_curve_points_remain_blocked():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    with pytest.raises(ValueError, match="Custom or Linear"):
        plan_light_cue_curves(source, [{"cue_id": CUE,
            "up": {"type": "s_curve", "points": [{"t": 0.0, "v": 0.0},
                                                    {"t": 1.0, "v": 1.0}]}}])


def test_identical_update_is_byte_preserving_noop():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"type": "custom", "points": [{"t": 0.0, "v": 0.0},
                                                {"t": 0.5, "v": 0.6},
                                                {"t": 1.0, "v": 1.0}]}}])
    assert plan["output_bytes"] == source
    assert plan["changes"] == []


def test_custom_curve_can_change_point_count_when_entries_have_known_shape():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves(unknown_point_fields=False)
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": 0.3, "v": 0.4},
                           {"t": 0.6, "v": 0.8}, {"t": 1.0, "v": 1.0}]}}])
    _, inner, cues, values = _curves(plan["output_bytes"])
    assert values[CUE]["upShape"]["points"] == [
        (0.0, 0.0), (0.3, 0.4), (0.6, 0.8), (1.0, 1.0)]
    shape = inner.ref(inner.ref(cues[CUE]["fade"])["shapes"])["upShape"]
    refs = inner.array(inner.ref(shape)["shapeEntries"])
    assert len(refs) == 4
    assert all("extra" not in inner.ref(ref) for ref in refs)


def test_point_count_change_refuses_unrecognized_point_metadata():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves(unknown_point_fields=True)
    with pytest.raises(ValueError, match="unrecognized point metadata"):
        plan_light_cue_curves(source, [{"cue_id": CUE,
            "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": 0.4, "v": 0.6},
                               {"t": 0.7, "v": 0.8}, {"t": 1.0, "v": 1.0}]}}])


@pytest.mark.parametrize("operation", [
    {"cue_id": OTHER, "up": {"type": "unknown"}},
    {"cue_id": OTHER, "up": {"type": None}},
    {"cue_id": OTHER, "up": {"type": ["custom"]}},
    {"cue_id": OTHER, "up": {"points": [{"t": 0.1, "v": 0.0}, {"t": 1.0, "v": 1.0}]}},
    {"cue_id": OTHER, "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": 1.0, "v": 0.9}]}},
    {"cue_id": OTHER, "down": {"points": [{"t": 0.0, "v": 0.0}, {"t": 1.0, "v": 0.0}]}},
    {"cue_id": OTHER, "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": 0.7, "v": 0.5}, {"t": 0.6, "v": 0.8}, {"t": 1.0, "v": 1.0}]}},
    {"cue_id": OTHER, "up": {"parameter": 0.0}},
    {"cue_id": OTHER, "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": float("nan"), "v": 0.5}, {"t": 1.0, "v": 1.0}]}},
    {"cue_id": "not-a-uuid", "up": {"type": "linear"}},
])
def test_invalid_operations_are_rejected(operation):
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    with pytest.raises(ValueError):
        plan_light_cue_curves(source, [operation])


@pytest.mark.parametrize("kwargs", [{"mirror": True}, {"domain_mode": 1}])
def test_unverified_shape_modes_are_rejected(kwargs):
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves(**kwargs)
    with pytest.raises(ValueError, match="Mirrored|FadeDomain"):
        plan_light_cue_curves(source, [{"cue_id": CUE,
            "up": {"points": [{"t": 0.0, "v": 0.0}, {"t": 0.5, "v": 0.8}, {"t": 1.0, "v": 1.0}]}}])


@pytest.mark.parametrize("unknown_class", ["FutureArray", "FutureDomain"])
def test_writer_rejects_unrecognized_curve_container_classes(unknown_class):
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    if unknown_class == "FutureArray":
        shape = inner.ref(ids["up_shape"])
        inner.ref(shape["shapeEntries"])["$class"] = inner.cls(unknown_class)
        expected = "shapeEntries array class"
    else:
        shapes = inner.ref(ids["shapes"])
        inner.ref(shapes["domain"])["$class"] = inner.cls(unknown_class)
        expected = "Unknown Light cue curve domain"
    carrier["NS.data"] = inner.dump()

    with pytest.raises(ValueError, match=expected):
        plan_light_cue_curves(outer.dump(), [{"cue_id": CUE, "up": {"type": "linear"}}])


def test_only_reachable_exact_light_cue_is_edited():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, ids = _workspace_with_curves(residual=True)
    plan = plan_light_cue_curves(source, [{"cue_id": CUE,
        "up": {"parameter": 3.0}}])
    _, inner, cues, values = _curves(plan["output_bytes"])
    _, original_inner, _, _ = _curves(source)
    assert values[CUE]["upShape"]["parameter"] == 3.0
    assert inner.ref(ids["residual"]) == original_inner.ref(ids["residual"])
    with pytest.raises(ValueError, match="reachable"):
        plan_light_cue_curves(source, [{"cue_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
            "up": {"type": "linear"}}])


def test_duplicate_active_reference_to_target_cue_is_rejected():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves(duplicate_active=True)
    with pytest.raises(ValueError, match="shared"):
        plan_light_cue_curves(source, [{"cue_id": CUE,
            "up": {"parameter": 2.0}}])


def test_transaction_postcondition_is_checked_before_and_after_reopen(tmp_path, monkeypatch):
    import json
    from copy import deepcopy
    from pathlib import Path
    from types import SimpleNamespace

    from qlab_mcp import workspace_archive as tx

    path = tmp_path / "Show.qlab5"
    source = json.dumps({"workspace_id": WS, "patch": {"name": "before"}}).encode()
    path.write_bytes(source)
    row = dict(workspace_id=WS, name="Show", path=str(path), modified=False,
        edit_mode=True, show_mode=False, active_cue_ids=[])
    state = SimpleNamespace(path=path, source=source, rows=[row], live={"name": "before"},
        callbacks=[], calls=[])
    monkeypatch.setattr(tx, "_app_build", lambda: ("5.5.10", "5510"))
    monkeypatch.setattr(tx, "_live", lambda reader, workspace_id, summary: summary)
    monkeypatch.setattr(tx.docs, "_inventory", lambda reader: {"documents": deepcopy(state.rows)})
    monkeypatch.setattr(tx.docs, "check_write_readiness", lambda *args: {"ok": True})
    monkeypatch.setattr(tx.docs, "_native_request", lambda reader, action, **payload: (
        state.calls.append(action) or state.rows.clear() or {"sent": True}))

    def planner(data, operations):
        value = json.loads(data)
        changes = []
        if operations and value["patch"]["name"] != operations[0]["name"]:
            value["patch"]["name"] = operations[0]["name"]
            changes = deepcopy(operations)
        return dict(output_bytes=json.dumps(value).encode(), workspace_id=WS,
            summary=value["patch"], changes=changes, warnings=[], affected_cues=[])

    def reopen(reader, file_path, workspace_id, expected_inventory):
        state.calls.append("open")
        state.rows.append(row.copy())
        state.live = json.loads(Path(file_path).read_bytes())["patch"]
        return {"sent": True}

    monkeypatch.setattr(tx, "_reopen", reopen)
    reader = SimpleNamespace(client=SimpleNamespace(config=SimpleNamespace(
        host="127.0.0.1", timeout=2)))
    reader.get_workspace_setting_details = lambda *args, **kwargs: dict(
        ok=True, partial=False, details={"patch": deepcopy(state.live)})

    def postcondition(data, plan):
        state.callbacks.append(json.loads(data)["patch"]["name"])
        return json.loads(data)["patch"] == plan["summary"]

    plan = tx.edit_light_patch(reader, WS, [{"name": "after"}], True,
        planner=planner, postcondition=postcondition)
    assert "confirm_token" in plan, plan
    result = tx.edit_light_patch(reader, WS, [{"name": "after"}], False,
        plan["confirm_token"], planner=planner, postcondition=postcondition)
    assert result["ok"] and result["postcondition_verified"]
    assert state.callbacks == ["after", "after", "after", "after"]
    assert state.calls == ["close", "open"]



def test_cue_target_reference_does_not_make_residual_active():
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, ids = _workspace_with_curves(residual=True)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = Archive(carrier["NS.data"])
    residual_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    inner.ref(ids["residual"])["uniqueID"] = residual_id
    inner.ref(ids["target_cue"])["cueTarget"] = ids["residual"]
    carrier["NS.data"] = inner.dump()
    with pytest.raises(ValueError, match="reachable"):
        plan_light_cue_curves(outer.dump(), [{"cue_id": residual_id, "up": {"type": "linear"}}])


def test_public_curve_schema_and_null_rejection_agree():
    from pydantic import TypeAdapter, ValidationError
    from qlab_mcp.light_patch.curves import LightCueCurveOperations
    adapter = TypeAdapter(LightCueCurveOperations)
    schema = adapter.json_schema()
    for name in ("CurveChanges", "LightCueCurveOperation"):
        for field in schema["$defs"][name]["properties"].values():
            assert {"type": "null"} not in field.get("anyOf", [])
    adapter.validate_python([{"cue_id": CUE, "up": {"type": "linear"}}])
    for change in ({"up": None}, {"up": {"parameter": None}}, {"down": {"points": None}}):
        with pytest.raises(ValidationError):
            adapter.validate_python([{"cue_id": CUE, **change}])


@pytest.mark.parametrize('cycle', [False, True])
def test_native_group_root_uses_only_valid_containment(cycle):
    from qlab_mcp.light_patch.curves import plan_light_cue_curves

    source, _ = _workspace_with_curves()
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)['cueLists'])
    inner = Archive(carrier['NS.data'])
    children = inner.data['$top']['root']
    group = inner.add({'$class': inner.cls('GroupCue'), 'cues': children})
    inner.data['$top']['root'] = group
    if cycle:
        inner.array(children).append(group)
    carrier['NS.data'] = inner.dump()
    if cycle:
        with pytest.raises(ValueError, match='cyclic'):
            plan_light_cue_curves(outer.dump(), [{'cue_id': CUE, 'up': {'type': 'linear'}}])
    else:
        assert plan_light_cue_curves(outer.dump(), [{'cue_id': CUE, 'up': {'type': 'linear'}}])['changes']
