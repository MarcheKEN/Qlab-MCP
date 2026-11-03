"""Saved Light curve reads are bounded, provenance-labelled, and read-only."""
from pathlib import Path
from types import SimpleNamespace

from qlab_mcp.light_patch.archive import Archive
from test_light_cue_curves import CUE, WS, _workspace_with_curves


def _reader(monkeypatch, source, *, modified=False, changed=False):
    import qlab_mcp.light_patch.reader as patch_reader
    import qlab_mcp.workspace_documents as docs

    path = Path("/tmp/Curve Test.qlab5")
    row = dict(workspace_id=WS, name="Curve Test", path=str(path), modified=modified,
               edit_mode=True, show_mode=False, active_cue_ids=[])
    reader = SimpleNamespace()
    read_count = [0]
    monkeypatch.setattr(docs, "_local", lambda _: None)
    monkeypatch.setattr(docs, "_inventory", lambda _: {"documents": [dict(row)]})

    def read_file(_):
        current = read_count[0]
        read_count[0] += 1
        if changed and current:
            return source + b"changed", (1, 2, len(source) + 7, 4)
        return source, (1, 2, len(source), 3)

    monkeypatch.setattr(patch_reader, "_read_file", read_file)
    return reader


def _workspace_with_up_point_count(count):
    import plistlib

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    from qlab_mcp.light_patch.archive import Archive as InnerArchive
    inner = InnerArchive(carrier["NS.data"])
    inner.ref(ids["shapes"]).pop("extraShapesField")
    inner.ref(ids["up_shape"]).pop("extraShapeField")
    entry_class = inner.cls("FadeShapeEntry")
    refs = [inner.add({"$class": entry_class,
                       "t": index / (count - 1), "v": index / (count - 1),
                       "previous": plistlib.UID(0), "next": plistlib.UID(0)})
            for index in range(count)]
    for index, ref in enumerate(refs):
        point = inner.ref(ref)
        point["previous"] = refs[index - 1] if index else plistlib.UID(0)
        point["next"] = refs[index + 1] if index + 1 < len(refs) else plistlib.UID(0)
    inner.ref(ids["up_shape"])["shapeEntries"] = inner.make_array(refs)
    carrier["NS.data"] = inner.dump()
    return outer.dump()


def test_saved_curves_include_points_hash_and_dirty_state(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves
    from qlab_mcp.cues.light_group import SavedLightCueCurves

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    from qlab_mcp.light_patch.archive import Archive as InnerArchive
    inner = InnerArchive(carrier["NS.data"])
    inner.ref(ids["shapes"]).pop("extraShapesField")
    inner.ref(ids["up_shape"]).pop("extraShapeField")
    carrier["NS.data"] = inner.dump()
    source = outer.dump()
    reader = _reader(monkeypatch, source, modified=True)
    result = read_saved_light_cue_curves(reader, WS, CUE)
    contract = SavedLightCueCurves.model_validate(result)

    assert contract.status == "ready"
    assert contract.source == "saved_archive"
    assert contract.document_modified is True
    assert contract.freshness == "possibly_stale"
    assert len(contract.sha256) == 64
    assert contract.curves["up"].type == "custom"
    assert [(point.t, point.v) for point in contract.curves["up"].points] == [
        (0.0, 0.0), (0.5, 0.6), (1.0, 1.0)]


def test_saved_reader_reports_mirrored_points_without_enabling_writer(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    source, _ = _workspace_with_curves(mirror=True, unknown_point_fields=False)
    result = read_saved_light_cue_curves(_reader(monkeypatch, source), WS, CUE)

    assert result["status"] == "partial"
    assert result["curves"]["up"]["mirror_shape"] is True
    assert result["curves"]["up"]["points"]
    assert "curves_are_mirrored" in result["curves"]["up"]["issues"]


def test_saved_reader_discards_archive_if_file_changes_during_read(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    source, _ = _workspace_with_curves(unknown_point_fields=False)
    result = read_saved_light_cue_curves(_reader(monkeypatch, source, changed=True), WS, CUE)

    assert result["status"] == "changed_during_read"
    assert result["curves"] == {}
    assert result["sha256"] is None


def test_saved_reader_keeps_unknown_curve_type_inspectable(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    from qlab_mcp.light_patch.archive import Archive as InnerArchive
    inner = InnerArchive(carrier["NS.data"])
    inner.ref(ids["up_shape"])["type"] = 99
    inner.ref(ids["up_shape"])["futureShapeProperty"] = 1
    inner.ref(inner.ref(ids["shapes"])["domain"])["futureDomainProperty"] = 2
    carrier["NS.data"] = inner.dump()
    result = read_saved_light_cue_curves(_reader(monkeypatch, outer.dump()), WS, CUE)

    assert result["status"] == "partial"
    assert result["curves"]["up"]["native_type"] == 99
    assert result["curves"]["up"]["type"] is None
    assert result["curves"]["up"]["points"]
    assert result["curves"]["up"]["status"] == "partial"
    assert "unknown_shape_fields" in result["curves"]["up"]["issues"]
    assert "unknown_fade_domain_fields" in result["curves"]["up"]["issues"]
    assert "shape.futureShapeProperty" in result["curves"]["up"]["unknown_fields"]
    assert "fade_domain.futureDomainProperty" in result["curves"]["up"]["unknown_fields"]


def test_saved_reader_keeps_points_from_unknown_array_class_partial(monkeypatch):
    from qlab_mcp.light_patch.archive import Archive as InnerArchive
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = InnerArchive(carrier["NS.data"])
    entries = inner.ref(ids["up_shape"])["shapeEntries"]
    inner.ref(entries)["$class"] = inner.cls("FutureArray")
    carrier["NS.data"] = inner.dump()

    result = read_saved_light_cue_curves(_reader(monkeypatch, outer.dump()), WS, CUE)

    up = result["curves"]["up"]
    assert result["status"] == "partial"
    assert up["points"]
    assert up["status"] == "partial"
    assert "unknown_shape_entries_array_class" in up["issues"]
    assert "shapeEntries.array_class:FutureArray" in up["unknown_fields"]


def test_saved_reader_marks_unknown_fade_domain_class_partial(monkeypatch):
    from qlab_mcp.light_patch.archive import Archive as InnerArchive
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    source, ids = _workspace_with_curves(unknown_point_fields=False)
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    inner = InnerArchive(carrier["NS.data"])
    domain = inner.ref(ids["shapes"])["domain"]
    inner.ref(domain)["$class"] = inner.cls("FutureDomain")
    carrier["NS.data"] = inner.dump()

    result = read_saved_light_cue_curves(_reader(monkeypatch, outer.dump()), WS, CUE)

    up = result["curves"]["up"]
    assert result["status"] == "partial"
    assert up["points"]
    assert up["status"] == "partial"
    assert "unknown_fade_domain_class" in up["issues"]
    assert "fade_domain.class:FutureDomain" in up["unknown_fields"]


def test_saved_reader_returns_supported_curves_beyond_512_points(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves
    result = read_saved_light_cue_curves(
        _reader(monkeypatch, _workspace_with_up_point_count(600)), WS, CUE)

    up = result["curves"]["up"]
    assert len(up["points"]) == 600
    assert up["total_points"] == 600
    assert up["truncated"] is False
    assert up["status"] == "available"


def test_saved_reader_marks_points_above_supported_limit_truncated(monkeypatch):
    from qlab_mcp.light_patch.curves import read_saved_light_cue_curves

    result = read_saved_light_cue_curves(
        _reader(monkeypatch, _workspace_with_up_point_count(4097)), WS, CUE)

    up = result["curves"]["up"]
    assert len(up["points"]) == 4096
    assert up["total_points"] == 4097
    assert up["truncated"] is True
    assert up["status"] == "partial"
    assert "point_limit_reached" in up["issues"]


def test_detail_byte_budget_keeps_an_omission_diagnostic(monkeypatch):
    from types import SimpleNamespace

    import qlab_mcp.cues.light_group as light_group
    import qlab_mcp.light_patch.curves as curves
    from qlab_mcp.cues.light_group import LightCueDetailsResult, LightCueSummary, LightGroupCuesMixin
    from qlab_mcp.cues.limits import serialized_payload_bytes

    point_rows = [{"t": index / 999, "v": index / 999} for index in range(1000)]
    side = dict(status="available", native_type=0, type="custom", parameter=1.0,
                points=point_rows, total_points=1000, truncated=False, resolution=0.0033,
                mirror_shape=False, domain={"mode": 0, "absolute": False},
                unknown_fields=[], issues=[])
    saved = dict(status="ready", source="saved_archive", sha256="a" * 64,
                 freshness="last_saved", document_modified=False, version="5.5.10", build=5510,
                 curves={"up": side, "down": side}, coverage="Both saved curve shapes are decoded.")
    details = LightCueDetailsResult(workspace_id=WS, cue_id=CUE,
        identity=LightCueSummary(uniqueID=CUE, type="Light"), technical_payload={"large": "x" * 5000})
    base = details.model_copy(update={"technical_payload": None})
    monkeypatch.setattr(light_group, "MAX_SENSITIVE_CUE_RESPONSE_BYTES",
                        serialized_payload_bytes(base.model_dump(mode="json")) + 100)
    monkeypatch.setattr(curves, "read_saved_light_cue_curves", lambda *_: saved)
    reader = SimpleNamespace(_get_family_details=lambda *args, **kwargs: details)

    result = LightGroupCuesMixin.get_light_cue_details(reader, WS, CUE)

    assert result.saved_curves is None
    assert result.partial and result.status == "partial"
    assert any("omitted because the response byte limit" in note for note in result.coverage.notes)
    assert serialized_payload_bytes(result.model_dump(mode="json")) <= light_group.MAX_SENSITIVE_CUE_RESPONSE_BYTES
