from __future__ import annotations

import struct
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from qlab_mcp.audio_effect_integrity import capture_effects, effects_match
from qlab_mcp.audio_volume_limits import (
    SetAudioVolumeLimits,
    _postcondition,
    _verify_live,
    edit_audio_volume_limits,
    plan_audio_volume_limits,
)
from qlab_mcp.light_patch.archive import Archive
from test_audio_archive import audio_workspace


WS = "11111111-1111-4111-8111-111111111111"


def _limits(source: bytes) -> dict[str, float]:
    archive = Archive(source)
    meta = archive.mapping(archive.root)
    settings = archive.mapping(meta["settings"])
    audio = archive.mapping(settings["Audio"])
    return {"min_volume": archive.ref(audio["minVolume"]),
            "max_volume": archive.ref(audio["maxVolume"])}


def _audio_settings(source: bytes) -> dict:
    archive = Archive(source)
    meta = archive.mapping(archive.root)
    settings = archive.mapping(meta["settings"])
    return archive.mapping(settings["Audio"])


def _effect_snapshot(source: bytes) -> dict:
    outer = Archive(source)
    carrier = outer.ref(outer.mapping(outer.root)["cueLists"])
    return capture_effects(outer, Archive(carrier["NS.data"]))


def test_plan_updates_only_limits_and_preserves_audio_and_effect_graphs():
    source = Archive(audio_workspace())
    meta = source.mapping(source.root)
    settings = source.mapping(meta["settings"])
    audio_object = source.ref(settings["Audio"])
    audio_object["NS.keys"].append(source.add("opaqueAudioField"))
    audio_object["NS.objects"].append(source.add("preserve me"))
    original = source.dump()
    source_effects = _effect_snapshot(original)

    plan = plan_audio_volume_limits(original, [{
        "action": "set_volume_limits", "min_volume": -80, "max_volume": 6,
    }])

    assert plan["workspace_id"] == WS
    assert plan["summary"] == {"workspace_id": WS, "min_volume": -80.0, "max_volume": 6.0}
    assert plan["changes"] == [{"action": "set_volume_limits", "min_volume": -80, "max_volume": 6}]
    assert _limits(original) == {"min_volume": -60.0, "max_volume": 12.0}
    edited = Archive(plan["output_bytes"])
    edited_audio = _audio_settings(plan["output_bytes"])
    assert _limits(plan["output_bytes"]) == {"min_volume": -80.0, "max_volume": 6.0}
    assert edited.ref(edited_audio["opaqueAudioField"]) == "preserve me"
    assert edited.ref(edited_audio["audioOutputPatches"]) == source.ref(
        source.mapping(settings["Audio"])["audioOutputPatches"]
    )
    assert effects_match(plan["output_bytes"], source_effects)
    assert plan["output_bytes"] != original


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ({"action": "set_volume_limits", "min_volume": -180}, (-180.0, 12.0)),
        ({"action": "set_volume_limits", "min_volume": -40}, (-40.0, 12.0)),
        ({"action": "set_volume_limits", "max_volume": -30}, (-60.0, -30.0)),
        ({"action": "set_volume_limits", "max_volume": 60}, (-60.0, 60.0)),
    ],
)
def test_plan_accepts_conservative_boundary_values(operation, expected):
    plan = plan_audio_volume_limits(audio_workspace(), [operation])
    assert (plan["summary"]["min_volume"], plan["summary"]["max_volume"]) == expected


def test_plan_accepts_both_documented_schema_bands_together():
    plan = plan_audio_volume_limits(audio_workspace(), [{
        "action": "set_volume_limits", "min_volume": -40, "max_volume": -30,
    }])
    assert (plan["summary"]["min_volume"], plan["summary"]["max_volume"]) == (-40.0, -30.0)


@pytest.mark.parametrize(
    "operation",
    [
        {"action": "set_volume_limits", "min_volume": -181},
        {"action": "set_volume_limits", "min_volume": -39},
        {"action": "set_volume_limits", "max_volume": -31},
        {"action": "set_volume_limits", "max_volume": 61},
        {"action": "set_volume_limits", "min_volume": float("nan")},
        {"action": "set_volume_limits", "max_volume": float("inf")},
        {"action": "set_volume_limits", "min_volume": True},
        {"action": "set_volume_limits"},
        {"action": "set_volume_limits", "min_volume": -80, "unexpected": 1},
    ],
)
def test_typed_operation_rejects_unbounded_or_coerced_values(operation):
    with pytest.raises(ValidationError):
        TypeAdapter(SetAudioVolumeLimits).validate_python(operation)


def test_plan_checks_new_value_against_unchanged_limit():
    source = Archive(audio_workspace())
    meta = source.mapping(source.root)
    settings = source.mapping(meta["settings"])
    audio_object = source.ref(settings["Audio"])
    keys = [source.ref(key) for key in audio_object["NS.keys"]]
    audio_object["NS.objects"][keys.index("minVolume")] = source.add(-20.0)

    with pytest.raises(ValueError, match="min_volume must be between"):
        plan_audio_volume_limits(source.dump(), [{"action": "set_volume_limits", "max_volume": -30}])


def test_plan_blocks_non_5510_archive():
    source = Archive(audio_workspace())
    root = source.ref(source.data["$top"]["root"])
    keys = [source.ref(key) for key in root["NS.keys"]]
    root["NS.objects"][keys.index("QLabBuildNumber")] = 5511

    with pytest.raises(ValueError, match="requires the QLab 5.5.10 archive format, build 5510"):
        plan_audio_volume_limits(source.dump(), [{"action": "set_volume_limits", "min_volume": -80}])


def test_postcondition_checks_saved_values_and_effect_graph():
    plan = plan_audio_volume_limits(audio_workspace(), [{
        "action": "set_volume_limits", "min_volume": -80, "max_volume": 6,
    }])
    assert _postcondition(plan["output_bytes"], plan) is True
    assert _postcondition(audio_workspace(), plan) is False

    changed = Archive(plan["output_bytes"])
    meta = changed.mapping(changed.root)
    settings = changed.mapping(meta["settings"])
    audio_object = changed.ref(settings["Audio"])
    keys = [changed.ref(key) for key in audio_object["NS.keys"]]
    audio_object["NS.objects"][keys.index("visibleChannels")] = changed.add(99)
    assert _postcondition(changed.dump(), plan) is False


def test_live_verifier_reads_both_limits_fresh(monkeypatch):
    import qlab_mcp.audio_volume_limits as limits

    calls = []
    reader = SimpleNamespace(_request=lambda address, **_kwargs: (
        calls.append(address) or SimpleNamespace(data={
            f"/workspace/{WS}/settings/audio/minVolume": -80.0,
            f"/workspace/{WS}/settings/audio/maxVolume": 6.0,
        }[address])
    ))
    monkeypatch.setattr(
        "qlab_mcp.runtime.read_cache.shared_read_cache",
        lambda: SimpleNamespace(clear=lambda: calls.append("clear")),
    )

    result = _verify_live(reader, WS, {"workspace_id": WS, "min_volume": -80.0, "max_volume": 6.0})

    assert result["minimum"] == -80.0 and result["maximum"] == 6.0
    assert calls == [
        "clear",
        f"/workspace/{WS}/settings/audio/minVolume",
        f"/workspace/{WS}/settings/audio/maxVolume",
    ]


def test_live_verifier_rejects_mismatched_readback(monkeypatch):
    reader = SimpleNamespace(_request=lambda address, **_kwargs: SimpleNamespace(
        data=-80.0 if address.endswith("minVolume") else 12.0,
    ))
    monkeypatch.setattr(
        "qlab_mcp.runtime.read_cache.shared_read_cache",
        lambda: SimpleNamespace(clear=lambda: None),
    )
    with pytest.raises(ValueError, match="Fresh OSC volume limits do not match"):
        _verify_live(reader, WS, {"workspace_id": WS, "min_volume": -80.0, "max_volume": 6.0})


def test_live_verifier_compares_both_limits_as_osc_float32(monkeypatch):
    def float32(value):
        return struct.unpack(">f", struct.pack(">f", value))[0]

    values = {
        "minVolume": float32(-80.1),
        "maxVolume": float32(6.1),
    }
    reader = SimpleNamespace(_request=lambda address, **_kwargs: SimpleNamespace(
        data=values["minVolume" if address.endswith("minVolume") else "maxVolume"],
    ))
    monkeypatch.setattr(
        "qlab_mcp.runtime.read_cache.shared_read_cache",
        lambda: SimpleNamespace(clear=lambda: None),
    )

    result = _verify_live(reader, WS, {"workspace_id": WS, "min_volume": -80.1, "max_volume": 6.1})

    assert result["minimum"] == float32(-80.1)
    assert result["maximum"] == float32(6.1)


def test_live_verifier_rejects_value_different_from_osc_float32_plan(monkeypatch):
    def float32(value):
        return struct.unpack(">f", struct.pack(">f", value))[0]

    reader = SimpleNamespace(_request=lambda address, **_kwargs: SimpleNamespace(
        data=float32(-80.1) if address.endswith("minVolume") else float32(6.2),
    ))
    monkeypatch.setattr(
        "qlab_mcp.runtime.read_cache.shared_read_cache",
        lambda: SimpleNamespace(clear=lambda: None),
    )

    with pytest.raises(ValueError, match="Fresh OSC volume limits do not match"):
        _verify_live(reader, WS, {"workspace_id": WS, "min_volume": -80.1, "max_volume": 6.1})


@pytest.mark.parametrize(
    ("readback_minimum", "planned_minimum"),
    [(float("nan"), -80.1), (-80.1, float("inf"))],
)
def test_live_verifier_rejects_non_finite_float32_values(
    monkeypatch, readback_minimum, planned_minimum,
):
    reader = SimpleNamespace(_request=lambda address, **_kwargs: SimpleNamespace(
        data=readback_minimum if address.endswith("minVolume") else 6.1,
    ))
    monkeypatch.setattr(
        "qlab_mcp.runtime.read_cache.shared_read_cache",
        lambda: SimpleNamespace(clear=lambda: None),
    )

    with pytest.raises(ValueError, match="not a finite OSC number"):
        _verify_live(reader, WS, {
            "workspace_id": WS, "min_volume": planned_minimum, "max_volume": 6.1,
        })


def test_edit_adapter_passes_typed_operations_and_archive_guards(monkeypatch):
    import qlab_mcp.audio_volume_limits as limits

    seen = {}
    expected = {"ok": True, "status": "planned"}

    def fake_edit_archive(reader, workspace_id, operations, dry_run, confirm_token, **options):
        seen.update(reader=reader, workspace_id=workspace_id, operations=operations,
                    dry_run=dry_run, confirm_token=confirm_token, options=options)
        plan = options["planner"](audio_workspace(), operations)
        assert options["postcondition"](plan["output_bytes"], plan)
        return expected

    monkeypatch.setattr("qlab_mcp.workspace_archive.edit_archive", fake_edit_archive)
    reader = object()
    result = edit_audio_volume_limits(reader, WS, {
        "action": "set_volume_limits", "min_volume": -80, "max_volume": 6,
    }, dry_run=True, confirm_token=None)

    assert result is expected
    assert seen["reader"] is reader and seen["workspace_id"] == WS
    assert seen["operations"] == [{"action": "set_volume_limits", "min_volume": -80, "max_volume": 6}]
    assert seen["options"]["token_family"] == "audioVolumeLimits"
    assert seen["options"]["live_verifier"] is _verify_live
    assert result["native_audio_volume_limits_verified"] is False
    assert "native_patch_verified" not in result
