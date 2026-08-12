from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from qlab_mcp.models import CreateCueResult, CueUpdateInput, UpdateCuesResult, WriteReadinessResult
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache
import qlab_mcp.write.operations as write_operations
import qlab_mcp.write.groups as group_helpers
import qlab_mcp.write.moves as move_helpers
import qlab_mcp.write.registry as write_registry
import qlab_mcp.write.text_basics as text_basics
import qlab_mcp.write.video_appearance as video_appearance
import qlab_mcp.write.video_audio_time as video_audio_time
import qlab_mcp.write.video_opacity as video_opacity
import qlab_mcp.write.video_scalars as video_scalars
import qlab_mcp.write.video_translation as video_translation
from qlab_mcp.cues import refs as cue_refs
from qlab_mcp.cues import overview as cue_overview
from qlab_mcp.write.moves import _build_plan, move_cues, simulate_move_batch
from qlab_mcp.write.allowlist import CUE_TYPES, validate_writable_cue_type
from qlab_mcp.write.registry import QLAB_BLEND_MODES, UPDATE_PROFILE_NAMES, profile_catalog
from qlab_mcp.write.network_patch_types import classify_network_patch_type


@pytest.fixture
def no_after_read_retry_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(write_operations, "AFTER_READ_RETRY_DELAYS", (0.0, 0.0, 0.0))


UPDATE_BATCH_CALL_NAMES = frozenset(
    {
        "fade_phase1_call",
        "fade_profile_call",
        "group_call",
        "extracted_family_calls",
        "phase3f_text_style_call",
        "phase4_light_call",
        "phase4c_video_fx_scalar_call",
        "phase5_light_call",
        "phase7_video_geometry_call",
        "phase8_video_io_call",
        "phase8c_video_slice_call",
        "phase9a_video_audio_level_call",
        "phase9b_video_audio_matrix_call",
        "phase9c_video_audio_level_meta_call",
        "phase9d_video_audio_mute_solo_call",
        "phase9e_video_audio_level_bulk_call",
        "utility_target_call",
        "video_clock_type_call",
        "video_integrated_fade_call",
        "devamp_call",
        "network_call",
    }
)


def test_write_modules_reuse_canonical_container_types_without_widening_placement_sets() -> None:
    assert cue_refs.CONTAINER_CUE_TYPES == {"Cue List", "Cue Cart", "Cart", "Group"}
    assert cue_overview.CONTAINER_CUE_TYPES is cue_refs.CONTAINER_CUE_TYPES
    assert move_helpers.CONTAINER_CUE_TYPES is cue_refs.CONTAINER_CUE_TYPES
    assert move_helpers._LINEAR_PARENT_TYPES == {"Cue List", "Group"}
    assert move_helpers._CART_PARENT_TYPES == {"Cue Cart", "Cart"}


@pytest.mark.parametrize("value", [2_147_483_648, -2_147_483_649, 10**20, 10**309, 1e39, float("inf"), float("nan")])
def test_numeric_write_values_outside_osc_wire_ranges_are_rejected(value: Any) -> None:
    with pytest.raises(UnsafeWriteOperationError):
        write_registry._number(value, "value must be an OSC-representable number")


def test_numeric_write_values_at_osc_int32_boundaries_are_accepted() -> None:
    assert write_registry._number(-2_147_483_648, "invalid") == -2_147_483_648
    assert write_registry._number(2_147_483_647, "invalid") == 2_147_483_647


@pytest.mark.parametrize(
    ("properties", "status", "active"),
    [
        ({"isBroken": False, "isWarning": False}, "healthy", False),
        ({"isBroken": True, "isWarning": False}, "broken", False),
        ({"isBroken": False, "isWarning": True}, "warning", False),
        ({}, "unknown", False),
        ({"isBroken": False, "isRunning": True}, "unknown", True),
    ],
)
def test_create_health_is_informational_except_for_active_state(
    properties: dict[str, Any], status: str, active: bool
) -> None:
    health = write_operations._read_create_health(properties)
    assert health["status"] == status
    assert health["active"] is active


def test_create_cue_type_map_matches_osc_wire_names() -> None:
    expected = {
        "memo": "memo", "group": "group", "wait": "wait", "audio": "audio",
        "mic": "mic", "video": "video", "camera": "camera", "text": "text",
        "light": "light", "fade": "fade", "network": "network", "midi": "midi",
        "midi_file": "midi file", "timecode": "timecode", "start": "start",
        "stop": "stop", "pause": "pause", "load": "load", "reset": "reset",
        "devamp": "devamp", "goto": "goto", "target": "target", "arm": "arm",
        "disarm": "disarm",
    }
    assert CUE_TYPES == expected
    assert {key: validate_writable_cue_type(key) for key in expected} == expected


def test_create_preflight_allows_broken_inactive_anchor(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = "11111111-1111-4111-8111-111111111111"
    parent = "22222222-2222-4222-8222-222222222222"
    snapshot = {
        "nodes": {
            parent: {"uniqueID": parent, "type": "Cue List", "isBroken": True},
            anchor: {"uniqueID": anchor, "type": "Video", "isBroken": True, "isWarning": True},
        },
        "parent_by_child": {anchor: parent},
        "children_by_parent": {parent: [anchor]},
    }
    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(
        write_operations,
        "_structural_activity_snapshot",
        lambda *_: {"active_count": 0, "active_cue_ids": []},
    )

    _, _, placement, error = write_operations._create_preflight(
        object(), "ws-1", "anchored", anchor
    )

    assert error is None
    assert placement["after_cue_id"] == anchor
    assert placement["expected_index"] == 1


def test_create_preflight_rejects_active_anchor_even_when_broken(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = "11111111-1111-4111-8111-111111111111"
    parent = "22222222-2222-4222-8222-222222222222"
    snapshot = {
        "nodes": {
            parent: {"uniqueID": parent, "type": "Cue List"},
            anchor: {"uniqueID": anchor, "type": "Video", "isBroken": True, "isRunning": True},
        },
        "parent_by_child": {anchor: parent},
        "children_by_parent": {parent: [anchor]},
    }
    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(
        write_operations,
        "_structural_activity_snapshot",
        lambda *_: {"active_count": 0, "active_cue_ids": []},
    )

    _, _, placement, error = write_operations._create_preflight(
        object(), "ws-1", "anchored", anchor
    )

    assert placement is None
    assert "inactive" in (error or "")


def test_create_cues_chains_verified_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = "11111111-1111-4111-8111-111111111111"
    parent = "22222222-2222-4222-8222-222222222222"
    snapshot = {
        "nodes": {
            parent: {"uniqueID": parent, "type": "Cue List"},
            anchor: {"uniqueID": anchor, "type": "Memo", "isBroken": True},
        },
        "parent_by_child": {anchor: parent},
        "children_by_parent": {parent: [anchor]},
    }
    monkeypatch.setattr(write_operations, "_create_preflight", lambda *_: (
        snapshot,
        {"active_count": 0, "active_cue_ids": []},
        {
            "mode": "anchored", "after_cue_id": anchor, "anchor_osc_id": anchor,
            "new_args": [anchor], "parent_id": parent, "parent_type": "Cue List",
            "anchor_index": 0, "expected_index": 1, "parent_children": [anchor],
            "parent_fingerprint": write_operations._structural_fingerprint([anchor]),
            "tree_fingerprint": write_operations._create_tree_fingerprint(snapshot),
            "status": "anchored",
        },
        None,
    ))
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: "ws-1")

    class Stub:
        client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))

        @staticmethod
        def _resolve_workspace_id_strict(workspace_id: str) -> str:
            return workspace_id

    calls: list[tuple[str, str | None, bool]] = []
    created = iter([
        "33333333-3333-4333-8333-333333333333",
        "44444444-4444-4444-8444-444444444444",
    ])

    def fake_create_cue(_workspace, cue_type, dry_run=None, after_cue_id=None, parent_container_id=None, confirm_token=None):
        del parent_container_id, confirm_token
        calls.append((cue_type, after_cue_id, bool(dry_run)))
        if dry_run:
            return {"ok": True, "confirm_token": "item-token"}
        cue_id = next(created)
        return {"ok": True, "status": "created", "created_cue_id": cue_id, "executed_operations": [{"operation": "new"}]}

    stub = Stub()
    stub.create_cue = fake_create_cue
    planned = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio"], dry_run=True, after_cue_id=anchor
    )
    assert planned["status"] == "dry_run"
    assert any(
        item.get("operation") == "new" and item.get("anchor_from_previous") is True
        for item in planned["planned_operations"]
    )
    result = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio"], dry_run=False,
        after_cue_id=anchor, confirm_token=planned["confirm_token"],
    )
    assert result["status"] == "created"
    assert [call[:2] for call in calls] == [
        ("memo", anchor), ("memo", anchor),
        ("audio", "33333333-3333-4333-8333-333333333333"),
        ("audio", "33333333-3333-4333-8333-333333333333"),
    ]


def test_create_cues_stops_before_the_next_item_after_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    anchor = "11111111-1111-4111-8111-111111111111"
    parent = "22222222-2222-4222-8222-222222222222"
    snapshot = {
        "nodes": {
            parent: {"uniqueID": parent, "type": "Cue List"},
            anchor: {"uniqueID": anchor, "type": "Memo"},
        },
        "parent_by_child": {anchor: parent},
        "children_by_parent": {parent: [anchor]},
    }
    placement = {
        "mode": "anchored", "after_cue_id": anchor, "anchor_osc_id": anchor,
        "new_args": [anchor], "parent_id": parent, "parent_type": "Cue List",
        "anchor_index": 0, "expected_index": 1, "parent_children": [anchor],
        "parent_fingerprint": write_operations._structural_fingerprint([anchor]),
        "tree_fingerprint": write_operations._create_tree_fingerprint(snapshot),
        "status": "anchored",
    }
    monkeypatch.setattr(write_operations, "_create_preflight", lambda *_: (
        snapshot, {"active_count": 0, "active_cue_ids": []}, placement, None
    ))
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: "ws-1")

    class Stub:
        client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))

        @staticmethod
        def _resolve_workspace_id_strict(workspace_id: str) -> str:
            return workspace_id

    calls: list[tuple[str, bool, str | None]] = []
    created_id = "33333333-3333-4333-8333-333333333333"

    def fake_create_cue(_workspace, cue_type, dry_run=None, after_cue_id=None, parent_container_id=None, confirm_token=None):
        del parent_container_id, confirm_token
        calls.append((cue_type, bool(dry_run), after_cue_id))
        if dry_run:
            return {"ok": True, "confirm_token": f"item-{cue_type}"}
        if cue_type == "audio":
            return {"ok": False, "status": "verification_failed", "errors": {"new": "failed"}, "message": "failed"}
        return {"ok": True, "status": "created", "created_cue_id": created_id, "executed_operations": [{"operation": "new"}]}

    stub = Stub()
    stub.create_cue = fake_create_cue
    planned = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio", "wait"], dry_run=True, after_cue_id=anchor
    )
    result = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio", "wait"], dry_run=False,
        after_cue_id=anchor, confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "partial_failed"
    assert [call[0] for call in calls] == ["memo", "memo", "audio", "audio"]


def test_quaternion_reuses_osc_numeric_range_validation() -> None:
    with pytest.raises(UnsafeWriteOperationError):
        write_registry._quaternion([0, 0, 0, 1e39])


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" auto follow ", 2),
        ("auto follow", 2),
        ("AUTO-CONTINUE", 1),
        ("unknown", "unknown"),
        (False, 0),
        (True, 1),
        (0.0, 0),
        (1.0, 1),
        (2.0, 2),
        (3.0, 3.0),
    ],
)
def test_continue_mode_comparison_normalizer_preserves_legacy_values(value: Any, expected: Any) -> None:
    assert write_registry._continue_mode_comparison_value(value) == expected
    assert write_operations._continue_mode_comparison_value is write_registry._continue_mode_comparison_value


def test_continue_mode_comparison_normalizer_preserves_unhashable_type_error() -> None:
    with pytest.raises(TypeError):
        write_registry._continue_mode_comparison_value([])


def test_simulate_move_batch_applies_moves_in_input_order() -> None:
    list_id = "11111111-1111-4111-8111-111111111111"
    group_id = "22222222-2222-4222-8222-222222222222"
    first_id = "33333333-3333-4333-8333-333333333333"
    second_id = "44444444-4444-4444-8444-444444444444"
    third_id = "55555555-5555-4555-8555-555555555555"

    result = simulate_move_batch(
        {list_id: [first_id, second_id, third_id], group_id: []},
        [
            {"cue_id": first_id, "destination_parent_id": list_id, "position": "last"},
            {"cue_id": second_id, "destination_parent_id": group_id, "position": "first"},
        ],
    )

    assert result["children_by_parent"] == {
        list_id: [third_id, first_id],
        group_id: [second_id],
    }


class MovePlanReader:
    def __init__(self) -> None:
        self.client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))
        self.workspace_id = "11111111-1111-4111-8111-111111111111"
        self.list_id = "22222222-2222-4222-8222-222222222222"
        self.first_id = "33333333-3333-4333-8333-333333333333"
        self.second_id = "44444444-4444-4444-8444-444444444444"

    def _resolve_workspace_id_strict(self, workspace_id: str) -> str:
        assert workspace_id == self.workspace_id
        return workspace_id

    def get_cue_lists(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"cue_lists": [{"uniqueID": self.list_id, "type": "Cue List"}]}

    def get_cue_children(self, _: str, cue_id: str, **__: Any) -> dict[str, Any]:
        assert cue_id == self.list_id
        return {
            "children": [
                {"uniqueID": self.first_id, "type": "Memo"},
                {"uniqueID": self.second_id, "type": "Memo"},
            ]
        }

    def get_running_cues(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"running_cues": []}


def test_move_cues_dry_run_issues_reusable_dedicated_token() -> None:
    reader = MovePlanReader()
    first = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=True,
    )
    second = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=True,
    )

    assert first["status"] == "planned"
    assert first["results"][0]["destination_index"] == 1
    assert first["confirm_token"].startswith("confirm:moveCues:v1:")
    assert second["confirm_token"] != first["confirm_token"]


def test_move_cues_executes_linear_move_and_confirms_fresh_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = MovePlanReader()
    reader.client.config.write_dry_run_default = False

    def request(address: str, *args: Any, **_: Any) -> Any:
        assert address == f"/workspace/{reader.workspace_id}/move/{reader.first_id}"
        assert args == (1,)
        children = reader.get_cue_children(reader.workspace_id, reader.list_id)["children"]
        moving = children.pop(0)
        children.insert(1, moving)
        reader.get_cue_children = lambda *_args, **_kwargs: {"children": children}  # type: ignore[method-assign]
        return SimpleNamespace(data={"parent_cue_id": reader.list_id, "index": 1}, status="ok")

    reader.client.request = request
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    planned = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=True,
    )
    result = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "moved"
    assert result["moved_count"] == 1
    assert result["results"][0]["readback"]["index"] == 1


def test_move_cues_polls_stale_readback_until_convergence(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = MovePlanReader()
    reader.client.config.write_dry_run_default = False
    original_children = [reader.first_id, reader.second_id]
    reader.snapshot_reads = 0
    reader.after_set = False

    def children(_: str, cue_id: str, **kwargs: Any) -> dict[str, Any]:
        del cue_id, kwargs
        reader.snapshot_reads += 1
        current = [reader.second_id, reader.first_id] if reader.after_set and reader.snapshot_reads >= 4 else original_children
        return {"children": [{"uniqueID": cue_id, "type": "Memo"} for cue_id in current]}

    def request(_: str, *__: Any, **___: Any) -> Any:
        reader.after_set = True
        return SimpleNamespace(data={"parent_cue_id": reader.list_id, "index": 1}, status="ok")

    reader.get_cue_children = children  # type: ignore[method-assign]
    reader.client.request = request
    clock = [0.0]
    monkeypatch.setattr(move_helpers.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(move_helpers.time, "sleep", lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    planned = move_cues(reader, reader.workspace_id, [{"cue_id": reader.first_id, "position": "last"}], dry_run=True)

    result = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "moved_after_convergence"
    assert result["results"][0]["verification_status"] == "confirmed_after_convergence"
    assert result["results"][0]["readback"] == {"parent_id": reader.list_id, "index": 1}


def test_move_cues_rejects_reference_to_a_cue_moved_in_same_batch() -> None:
    reader = MovePlanReader()

    result = move_cues(
        reader,
        reader.workspace_id,
        [
            {"cue_id": reader.first_id, "before_cue_id": reader.second_id},
            {"cue_id": reader.second_id, "position": "last"},
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "same batch" in result["errors"]["batch"]


def test_move_plan_uses_each_step_resolved_index_not_the_final_index() -> None:
    list_id = "11111111-1111-4111-8111-111111111111"
    first_id = "22222222-2222-4222-8222-222222222222"
    second_id = "33333333-3333-4333-8333-333333333333"
    third_id = "44444444-4444-4444-8444-444444444444"
    snapshot = {
        "nodes": {
            list_id: {"uniqueID": list_id, "type": "Cue List"},
            **{cue_id: {"uniqueID": cue_id, "type": "Memo"} for cue_id in (first_id, second_id, third_id)},
        },
        "children_by_parent": {list_id: [first_id, second_id, third_id]},
        "parent_by_child": {first_id: list_id, second_id: list_id, third_id: list_id},
    }
    moves = [
        {"cue_id": first_id, "source_parent_id": list_id, "destination_parent_id": list_id, "position": "last", "kind": "linear"},
        {"cue_id": second_id, "source_parent_id": list_id, "destination_parent_id": list_id, "position": "last", "kind": "linear"},
    ]

    plan = _build_plan(snapshot, moves)

    assert [item["destination_index"] for item in plan] == [2, 2]


def test_move_plan_preserves_qlab_uuid_casing_in_osc_address_and_parent_arg() -> None:
    list_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    group_id = "BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB"
    cue_id = "CCCCCCCC-CCCC-4CCC-8CCC-CCCCCCCCCCCC"
    snapshot = {
        "nodes": {
            str(UUID(list_id)): {"uniqueID": list_id, "type": "Cue List"},
            str(UUID(group_id)): {"uniqueID": group_id, "type": "Group"},
            str(UUID(cue_id)): {"uniqueID": cue_id, "type": "Memo"},
        },
        "children_by_parent": {str(UUID(list_id)): [str(UUID(cue_id))], str(UUID(group_id)): []},
        "parent_by_child": {str(UUID(cue_id)): str(UUID(list_id))},
    }
    plan = _build_plan(
        snapshot,
        [
            {
                "cue_id": str(UUID(cue_id)),
                "source_parent_id": str(UUID(list_id)),
                "destination_parent_id": str(UUID(group_id)),
                "position": "first",
                "kind": "linear",
            }
        ],
    )

    assert plan[0]["address"].endswith(f"/{cue_id}")
    assert plan[0]["args"] == [0, group_id]


def test_move_cues_dry_run_plans_cart_coordinates_without_linear_index() -> None:
    reader = MovePlanReader()
    cart_id = "55555555-5555-4555-8555-555555555555"
    reader.get_cue_lists = lambda *_args, **_kwargs: {"cue_lists": [{"uniqueID": cart_id, "type": "Cue Cart"}]}  # type: ignore[method-assign]
    reader.get_cue_children = lambda *_args, **_kwargs: {  # type: ignore[method-assign]
        "children": [{"uniqueID": reader.first_id, "type": "Memo"}]
    }

    result = move_cues(
        reader,
        reader.workspace_id,
        [
            {
                "cue_id": reader.first_id,
                "destination_parent_id": cart_id,
                "cart_row": 2,
                "cart_column": 3,
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "planned"
    assert result["results"][0]["args"] == [2, 3]
    assert "destination_index" not in result["results"][0]


def test_move_cues_stops_on_second_failure_and_returns_fresh_rollback_plan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reader = MovePlanReader()
    reader.client.config.write_dry_run_default = False
    children = [
        {"uniqueID": reader.first_id, "type": "Memo"},
        {"uniqueID": reader.second_id, "type": "Memo"},
    ]
    reader.get_cue_children = lambda *_args, **_kwargs: {"children": children}  # type: ignore[method-assign]
    calls = 0

    def request(address: str, *args: Any, **_: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            assert address == f"/workspace/{reader.workspace_id}/move/{reader.first_id}"
            assert args == (1,)
            children[:] = [children[1], children[0]]
            return SimpleNamespace(data={"parent_cue_id": reader.list_id, "index": 1}, status="ok")
        raise QLabReplyError("error", "second move rejected", address)

    reader.client.request = request
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    moves = [
        {"cue_id": reader.first_id, "position": "last"},
        {"cue_id": reader.second_id, "position": "last"},
    ]
    planned = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=planned["confirm_token"])

    assert result["status"] == "partial_failed"
    assert result["moved_count"] == 1
    assert result["rollback"]["status"] == "fresh_confirmation_required"
    assert result["rollback"]["moves"] == [
        {
            "cue_id": reader.first_id,
            "destination_parent_id": reader.list_id,
            "destination_index": 0,
        }
    ]


def test_move_cues_confirms_timeout_only_after_fresh_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = MovePlanReader()
    reader.client.config.write_dry_run_default = False
    children = [
        {"uniqueID": reader.first_id, "type": "Memo"},
        {"uniqueID": reader.second_id, "type": "Memo"},
    ]
    reader.get_cue_children = lambda *_args, **_kwargs: {"children": children}  # type: ignore[method-assign]

    def request(_: str, *__: Any, **___: Any) -> Any:
        children[:] = [children[1], children[0]]
        raise OscTimeoutError("move reply timed out")

    reader.client.request = request
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    planned = move_cues(reader, reader.workspace_id, [{"cue_id": reader.first_id, "position": "last"}], dry_run=True)
    result = move_cues(
        reader,
        reader.workspace_id,
        [{"cue_id": reader.first_id, "position": "last"}],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "moved_with_confirmed_timeout"
    assert result["timeout_confirmed_count"] == 1


def test_move_token_rejects_wrong_family_signature_and_expiry(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = [{"cue_id": "11111111-1111-4111-8111-111111111111", "destination_index": 0}]
    monkeypatch.setattr(move_helpers.time, "time", lambda: 1000)
    token = move_helpers._encode_token("22222222-2222-4222-8222-222222222222", plan)

    assert move_helpers._decode_token("confirm:update:v1:not-a-move-token")[1]
    assert move_helpers._decode_token(f"{token[:-1]}x")[1] == "move confirmation token signature is invalid."
    monkeypatch.setattr(move_helpers.time, "time", lambda: 1000 + move_helpers.MOVE_TOKEN_TTL_SECONDS + 1)
    assert move_helpers._decode_token(token)[1] == "move confirmation token has expired."


class FakeWriteClient:
    def __init__(
        self,
        config: QLabConfig,
        created_cue_id: str | None = None,
        existing_cue_id: str | None = None,
        cue_values: dict[str, Any] | None = None,
        connect_data: str = "ok:view|edit",
        connect_status: str = "ok",
        show_mode_data: Any = False,
        show_mode_status: str = "ok",
        fail_set_property: str | None = None,
        timeout_set_property: str | None = None,
        missing_cue: bool = False,
    ):
        self.config = config
        self.created_cue_id = created_cue_id
        self.existing_cue_id = existing_cue_id
        self.cue_values = cue_values or {
            "uniqueID": existing_cue_id or created_cue_id,
            "number": "1",
            "name": "Stale",
            "displayName": "1 Stale",
            "type": "Memo",
            "armed": True,
            "flagged": False,
        }
        self.connect_data = connect_data
        self.connect_status = connect_status
        self.show_mode_data = show_mode_data
        self.show_mode_status = show_mode_status
        self.fail_set_property = fail_set_property
        self.timeout_set_property = timeout_set_property
        self.missing_cue = missing_cue
        self.created = False
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []
        self.reply_timeouts: list[float | None] = []

    def request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        if address == "/workspace/ws-1/connect":
            return SimpleNamespace(data=self.connect_data, status=self.connect_status)
        if address == "/workspace/ws-1/showMode":
            return SimpleNamespace(data=self.show_mode_data, status=self.show_mode_status)
        if address == "/workspace/ws-1/settings/audio/patchList":
            return SimpleNamespace(data=[{"uniqueID": "Patch 1"}, {"uniqueID": "value"}], status="ok")
        if address == "/workspace/ws-1/settings/mic/patchList":
            return SimpleNamespace(data=[{"uniqueID": "Patch 1"}, {"uniqueID": "value"}], status="ok")
        if address == "/workspace/ws-1/new":
            self.created = True
            self.cue_values["uniqueID"] = self.created_cue_id
            return SimpleNamespace(data={"uniqueID": self.created_cue_id}, status="ok")
        known_ids = {value for value in (self.created_cue_id, self.existing_cue_id) if value}
        if any(address.startswith(f"/workspace/ws-1/cue_id/{cue_id}/") for cue_id in known_ids) or address.startswith(
            "/workspace/ws-1/cue/1/"
        ):
            if self.missing_cue:
                raise QLabReplyError("error", "No cue found", address)
            if address.endswith("/valuesForKeys"):
                if self.created and self.created_cue_id:
                    self.cue_values["name"] = self.cue_values.get("name", "Created")
                return SimpleNamespace(
                    data=dict(self.cue_values),
                    status="ok",
                )
            property_name = self._property_name_from_address(address, known_ids)
            if property_name == self.fail_set_property:
                raise QLabReplyError("error", f"Failed setting {property_name}", address)
            self._set_property(
                property_name,
                list(args) if property_name == "quaternion" else (args[0] if args else None),
            )
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake write request: {address}")

    def _set_property(self, property_name: str, value: Any) -> None:
        if property_name == "resetRotation":
            self.cue_values["quaternion"] = [1, 0, 0, 0]
            return
        parameter_prefix = "videoEffectIndex/0/parameter/"
        if property_name.startswith(parameter_prefix):
            parameter_key = property_name.removeprefix(parameter_prefix)
            effects = self.cue_values.setdefault("videoEffects", [])
            while len(effects) <= 0:
                effects.append({})
            effect = effects[0]
            if isinstance(effect, dict):
                parameters = effect.get("parameters")
                if isinstance(parameters, dict) and parameter_key in parameters:
                    parameters[parameter_key] = value
                else:
                    effect[parameter_key] = value
                return
        self.cue_values[property_name] = value

    @staticmethod
    def _property_name_from_address(address: str, known_ids: set[str]) -> str:
        for cue_id in known_ids:
            prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
            if address.startswith(prefix):
                return address.removeprefix(prefix)
        return address.removeprefix("/workspace/ws-1/cue/1/")


class CreateAnchorReader(QLabReader):
    """Small structural fake for the anchored Create 031B contract."""

    workspace = "ws-1"
    list_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    anchor_id = "22222222-2222-4222-8222-222222222222"
    created_id = "33333333-3333-4333-8333-333333333333"

    def __init__(
        self,
        *,
        config: QLabConfig | None = None,
        timeout_new: bool = False,
        timeout_set_property: str | None = None,
        fail_set_property: str | None = None,
        health_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.client = _CreateAnchorClient(
            config or QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=True)
        )
        self.client.request_handler = self._request
        self._read_cache = shared_read_cache()
        self._read_deadline = None
        self.children = [self.anchor_id]
        self.extra_children: list[str] = []
        self.created = False
        self.created_type = "Wait"
        self.cue_values: dict[str, Any] = {}
        self.timeout_new = timeout_new
        self.timeout_set_property = timeout_set_property
        self.fail_set_property = fail_set_property
        self.health_overrides = health_overrides or {}
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []

    def _resolve_workspace_id_strict(self, workspace_id: str) -> str:
        if workspace_id != self.workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace_id

    def get_cue_lists(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"cue_lists": [{"uniqueID": self.list_id, "type": "Cue List"}]}

    def get_cue_children(self, _workspace_id: str, cue_ref: str, **_: Any) -> dict[str, Any]:
        assert cue_ref == self.list_id
        children = [{"uniqueID": self.anchor_id, "type": "Memo"}]
        children.extend({"uniqueID": cue_id, "type": "Memo"} for cue_id in self.extra_children)
        if self.created:
            children.append({"uniqueID": self.created_id, "type": self.created_type})
        return {"children": children}

    def get_running_cues(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"running_cues": []}

    def get_cue_details(self, _workspace_id: str, cue_ref: str, _profile: str = "auto") -> dict[str, Any]:
        if cue_ref == self.created_id and self.created:
            return {
                "ok": True,
                "status": "ok",
                "cue_ref": cue_ref,
                "cue_type": self.created_type,
                "properties": dict(self.cue_values),
            }
        raise QLabReplyError("error", "No cue found", cue_ref)

    def _request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        request_timeout: float | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        del request_timeout, reply_timeout
        self.requests.append((address, args, workspace_id))
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": self.workspace}], status="ok")
        if address == f"/workspace/{self.workspace}/connect":
            return SimpleNamespace(data="ok:view|edit|control", status="ok")
        if address == f"/workspace/{self.workspace}/showMode":
            return SimpleNamespace(data=False, status="ok")
        if address == f"/workspace/{self.workspace}/new":
            assert args[1:] == (self.anchor_id,)
            if self.timeout_new:
                raise OscTimeoutError("new timed out")
            self.created_type = str(args[0])
            self.created = True
            self.cue_values = {
                "uniqueID": self.created_id,
                "type": self.created_type,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
                "isActionRunning": False,
            }
            self.cue_values.update(self.health_overrides)
            return SimpleNamespace(data={"uniqueID": self.created_id}, status="ok")
        cue_prefix = f"/workspace/{self.workspace}/cue_id/{self.created_id}/"
        if address.startswith(cue_prefix):
            property_name = address.removeprefix(cue_prefix)
            if property_name == "valuesForKeys":
                return SimpleNamespace(data=dict(self.cue_values), status="ok")
            self.cue_values[property_name] = args[0] if args else None
            if property_name == self.fail_set_property:
                raise QLabReplyError("error", f"Failed setting {property_name}", address)
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake create request: {address}")


class _CreateAnchorClient:
    def __init__(self, config: QLabConfig) -> None:
        self.config = config
        self.request_handler: Any = None

    def request(self, address: str, *args: Any, **kwargs: Any) -> Any:
        return self.request_handler(address, *args, **kwargs)


class EmptyContainerReader(QLabReader):
    workspace = "ws-empty"
    list_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    initial_current_list_id = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
    group_id = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
    cart_id = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
    created_id = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"

    def __init__(
        self,
        container_type: str,
        *,
        real: bool = False,
        current_list_id: str | None = None,
        timeout_current_list_setter: bool = False,
        apply_current_list_on_timeout: bool = False,
        timeout_current_list_readback: bool = False,
    ) -> None:
        self.container_type = container_type
        self.client = _CreateAnchorClient(
            QLabConfig(
                enable_write=real,
                passcode="server-pass" if real else None,
                write_dry_run_default=not real,
            )
        )
        self.client.request_handler = self._request
        self._read_cache = shared_read_cache()
        self._read_deadline = None
        self.created = False
        self.current_list_id = current_list_id or self.initial_current_list_id
        self.current_list_setter_attempts = 0
        self.timeout_current_list_setter = timeout_current_list_setter
        self.apply_current_list_on_timeout = apply_current_list_on_timeout
        self.timeout_current_list_readback = timeout_current_list_readback
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []

    @property
    def target_id(self) -> str:
        return {
            "Cue List": self.list_id,
            "Group": self.group_id,
            "Cue Cart": self.cart_id,
        }[self.container_type]

    def _resolve_workspace_id_strict(self, workspace_id: str) -> str:
        if workspace_id != self.workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return workspace_id

    def _resolve_workspace_strict(self, workspaces: Any, workspace_id: str) -> dict[str, Any]:
        del workspaces
        if workspace_id != self.workspace:
            raise ValueError(f"Workspace not found: {workspace_id}")
        return {"uniqueID": self.workspace, "displayName": "empty-container"}

    def get_workspaces(self) -> dict[str, Any]:
        return {"workspaces": [{"uniqueID": self.workspace, "displayName": "empty-container"}]}

    def get_cue_lists(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"cue_lists": [{"uniqueID": self.list_id, "type": "Cue List"}]}

    def get_cue_children(self, _workspace_id: str, cue_ref: str, **_: Any) -> dict[str, Any]:
        if cue_ref == self.list_id:
            if self.container_type == "Cue List":
                children = [{"uniqueID": self.created_id, "type": "Memo"}] if self.created else []
            else:
                children = [{"uniqueID": self.target_id, "type": self.container_type}]
            return {"children": children}
        if cue_ref == self.group_id:
            children = [{"uniqueID": self.created_id, "type": "Memo"}] if self.created else []
            return {"children": children}
        if cue_ref == self.cart_id:
            children = [{"uniqueID": self.created_id, "type": "Memo"}] if self.created else []
            return {"children": children}
        raise AssertionError(f"Unexpected child read: {cue_ref}")

    def get_running_cues(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"running_cues": []}

    def get_cue_details(self, _workspace_id: str, cue_ref: str, _profile: str = "auto") -> dict[str, Any]:
        if cue_ref != self.created_id or not self.created:
            raise QLabReplyError("error", "No cue found", cue_ref)
        properties = {
            "uniqueID": self.created_id,
            "type": "Memo",
            "isBroken": False,
            "isWarning": False,
            "isRunning": False,
            "isPaused": False,
            "isAuditioning": False,
            "isActionRunning": False,
        }
        if self.container_type == "Cue Cart":
            properties.update({"cartPosition": [1, 1]})
        return {"ok": True, "status": "ok", "cue_ref": cue_ref, "cue_type": "Memo", "properties": properties}

    def _request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        request_timeout: float | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        del workspace_id, request_timeout, reply_timeout
        self.requests.append((address, args, None))
        if address == f"/workspace/{self.workspace}/connect":
            return SimpleNamespace(data="ok:view|edit|control", status="ok")
        if address == f"/workspace/{self.workspace}/showMode":
            return SimpleNamespace(data=False, status="ok")
        if address == f"/workspace/{self.workspace}/currentCueListID":
            if self.timeout_current_list_readback and self.current_list_setter_attempts:
                raise OscTimeoutError("current list readback timed out")
            return SimpleNamespace(data=self.current_list_id, status="ok")
        if address.startswith(f"/workspace/{self.workspace}/currentCueListID/"):
            self.current_list_setter_attempts += 1
            target_id = address.rsplit("/", 1)[-1]
            if self.timeout_current_list_setter:
                if self.apply_current_list_on_timeout:
                    self.current_list_id = target_id
                raise OscTimeoutError("current list setter timed out")
            self.current_list_id = target_id
            return SimpleNamespace(data=None, status="ok")
        if address == f"/workspace/{self.workspace}/new":
            expected = {
                "Cue List": ("memo",),
                "Group": ("memo", self.group_id),
                "Cue Cart": ("memo", self.cart_id, 0, 0),
            }[self.container_type]
            assert args == expected
            self.created = True
            return SimpleNamespace(data={"uniqueID": self.created_id}, status="ok")
        if address == f"/workspace/{self.workspace}/move/{self.created_id}":
            assert self.container_type == "Group"
            assert args == (0, self.group_id)
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected empty-container request: {address} {args}")


@pytest.mark.parametrize("container_type", ["Cue List", "Group", "Cue Cart"])
def test_create_empty_container_dry_run_plans_container_specific_route(container_type: str) -> None:
    reader = EmptyContainerReader(container_type)

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.target_id,
    )

    assert result["ok"] is True
    assert result["placement"]["parent_container_id"] == reader.target_id
    assert result["placement"]["expected_index"] == 0
    assert result["confirm_token"].startswith("confirm:createCue:v2:")
    assert result["executed_operations"] == []
    operations = result["planned_operations"]
    if container_type == "Cue List":
        assert [operation["operation"] for operation in operations] == [
            "set_current_cue_list",
            "verify_current_cue_list",
            "new",
            "verify",
            "verify_structure",
        ]
        assert operations[2]["args"] == ["memo"]
    elif container_type == "Group":
        assert [operation["operation"] for operation in operations] == [
            "new",
            "move_into_container",
            "verify",
            "verify_structure",
        ]
        assert operations[0]["args"] == ["memo", reader.group_id]
        assert operations[1]["args"] == [0, reader.group_id]
    else:
        assert [operation["operation"] for operation in operations] == [
            "new",
            "verify",
            "verify_structure",
        ]
        assert operations[0]["args"] == ["memo", reader.cart_id, 0, 0]
    assert not any(
        address.endswith("/new") or "/move/" in address or "currentCueListID/" in address
        for address, _, _ in reader.requests
    )


def test_create_empty_cue_list_real_selects_list_then_creates_first_child() -> None:
    reader = EmptyContainerReader(
        "Cue List",
        real=True,
        current_list_id=EmptyContainerReader.initial_current_list_id,
    )
    planned = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.list_id,
    )

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.list_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["verification"]["structure"]["parent_id"] == reader.list_id
    assert result["verification"]["structure"]["index"] == 0
    assert [address for address, _, _ in reader.requests].count(f"/workspace/{reader.workspace}/new") == 1
    assert any(address.endswith(f"/currentCueListID/{reader.list_id}") for address, _, _ in reader.requests)


def _empty_cue_list_real_counts(reader: EmptyContainerReader, start: int) -> dict[str, int]:
    requests = reader.requests[start:]
    setter = f"/workspace/{reader.workspace}/currentCueListID/{reader.list_id}"
    getter = f"/workspace/{reader.workspace}/currentCueListID"
    new = f"/workspace/{reader.workspace}/new"
    setter_index = next(index for index, (address, _, _) in enumerate(requests) if address == setter)
    after_setter = [address for address, _, _ in requests[setter_index:]]
    return {
        "setter": after_setter.count(setter),
        "getter": after_setter.count(getter),
        "new": after_setter.count(new),
    }


def _planned_empty_cue_list_create(reader: EmptyContainerReader) -> dict[str, Any]:
    return reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.list_id,
    )


def test_create_empty_cue_list_timeout_then_matching_readback_creates_once() -> None:
    reader = EmptyContainerReader(
        "Cue List",
        real=True,
        timeout_current_list_setter=True,
        apply_current_list_on_timeout=True,
    )
    planned = _planned_empty_cue_list_create(reader)
    start = len(reader.requests)

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.list_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["status"] == "created"
    assert "setter_timeout_but_readback_matched" in result["warnings"]
    assert not any(item["operation"] == "set_current_cue_list" for item in result["executed_operations"])
    assert _empty_cue_list_real_counts(reader, start) == {"setter": 1, "getter": 1, "new": 1}


def test_create_empty_cue_list_timeout_then_old_readback_blocks_new() -> None:
    reader = EmptyContainerReader("Cue List", real=True, timeout_current_list_setter=True)
    planned = _planned_empty_cue_list_create(reader)
    start = len(reader.requests)

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.list_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert result["error_code"] == "current_cue_list_failed"
    assert result["cleanup_required"] is False
    assert "current_cue_list_may_have_changed" in result["warnings"]
    assert _empty_cue_list_real_counts(reader, start) == {"setter": 1, "getter": 1, "new": 0}


def test_create_empty_cue_list_timeout_then_readback_timeout_blocks_new() -> None:
    reader = EmptyContainerReader(
        "Cue List",
        real=True,
        timeout_current_list_setter=True,
        timeout_current_list_readback=True,
    )
    planned = _planned_empty_cue_list_create(reader)
    start = len(reader.requests)

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.list_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert result["error_code"] == "current_cue_list_failed"
    assert "current_cue_list_may_have_changed" in result["warnings"]
    assert _empty_cue_list_real_counts(reader, start) == {"setter": 1, "getter": 1, "new": 0}


def test_create_empty_group_anchors_new_then_moves_once() -> None:
    reader = EmptyContainerReader("Group", real=True)
    planned = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.group_id,
    )

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.group_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["verification"]["structure"]["parent_id"] == reader.group_id
    assert result["verification"]["structure"]["index"] == 0
    assert [address for address, _, _ in reader.requests].count(f"/workspace/{reader.workspace}/new") == 1
    assert [address for address, _, _ in reader.requests].count(
        f"/workspace/{reader.workspace}/move/{reader.created_id}"
    ) == 1


def test_create_empty_group_preserves_wire_uuid_case() -> None:
    reader = EmptyContainerReader("Group", real=True)
    reader.group_id = reader.group_id.upper()
    planned = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.group_id,
    )

    move_plan = next(item for item in planned["planned_operations"] if item["operation"] == "move_into_container")
    assert move_plan["args"] == [0, reader.group_id]

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.group_id,
        confirm_token=planned["confirm_token"],
    )
    assert result["ok"] is True


def test_create_empty_cart_uses_direct_cart_coordinates_without_move() -> None:
    reader = EmptyContainerReader("Cue Cart", real=True)
    planned = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.cart_id,
    )

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        parent_container_id=reader.cart_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["verification"]["structure"]["parent_id"] == reader.cart_id
    assert result["verification"]["structure"]["index"] == 0
    assert result["verification"]["structure"]["cart_row"] == 0
    assert result["verification"]["structure"]["cart_column"] == 0
    assert result["verification"]["structure"]["cart_readback_row"] == 1
    assert result["verification"]["structure"]["cart_readback_column"] == 1
    assert [address for address, _, _ in reader.requests].count(f"/workspace/{reader.workspace}/new") == 1
    assert not any("/move/" in address for address, _, _ in reader.requests)


def test_create_group_in_empty_cart_is_rejected_before_new() -> None:
    reader = EmptyContainerReader("Cue Cart")
    result = reader.create_cue(
        reader.workspace,
        "group",
        dry_run=True,
        parent_container_id=reader.cart_id,
    )

    assert result["ok"] is False
    assert result["error_code"] == "preflight_failed"
    assert "cannot be created inside a Cue Cart" in result["errors"]["preflight"]
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []


def test_create_rejects_both_or_neither_placement_selectors() -> None:
    reader = EmptyContainerReader("Cue List")
    with pytest.raises(UnsafeWriteOperationError, match="exactly one"):
        reader.create_cue(reader.workspace, "memo", dry_run=True)
    with pytest.raises(UnsafeWriteOperationError, match="exactly one"):
        reader.create_cue(
            reader.workspace,
            "memo",
            dry_run=True,
            after_cue_id=reader.list_id,
            parent_container_id=reader.list_id,
        )


def test_create_rejects_nonempty_parent_container_before_new() -> None:
    reader = EmptyContainerReader("Group")
    reader.created = True

    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        parent_container_id=reader.group_id,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "empty container" in result["errors"]["preflight"]
    assert not any(address.endswith("/new") for address, _, _ in reader.requests)


class BatchFakeWriteClient:
    def __init__(
        self,
        config: QLabConfig,
        cues: dict[str, dict[str, Any]],
        cue_numbers: dict[str, str] | None = None,
        fail_set_property: tuple[str, str] | None = None,
        error_after_apply_properties: set[tuple[str, str]] | None = None,
        timeout_set_property: tuple[str, str] | None = None,
        timeout_set_properties: set[tuple[str, str]] | None = None,
        timeout_without_apply: bool = False,
        timeout_without_apply_properties: set[tuple[str, str]] | None = None,
        delay_on_timeout: bool = False,
        timeout_apply_after_reads: int | None = None,
        ignore_set_property: tuple[str, str] | None = None,
        missing_refs: set[str] | None = None,
        show_mode_data: Any = False,
        connect_data: str = "ok:view|edit",
        workspace_id: str = "ws-1",
        light_patch: dict[str, Any] | None = None,
        light_patch_error: bool = False,
        video_stages: list[dict[str, Any]] | None = None,
        video_stage_regions: dict[str, list[dict[str, Any]]] | None = None,
        audio_output_patches: list[dict[str, Any]] | None = None,
        audio_input_patches: list[dict[str, Any]] | None = None,
        network_patches: list[dict[str, Any]] | None = None,
        network_repair_outcomes: dict[tuple[str, str, Any], dict[str, Any]] | None = None,
        property_outcomes: dict[tuple[str, str, Any], dict[str, Any]] | None = None,
        children_by_parent: dict[str, list[str]] | None = None,
        group_child_outcomes: dict[tuple[str, str, Any], dict[str, dict[str, Any]]] | None = None,
        group_order_outcomes: dict[tuple[str, str, Any], list[str]] | None = None,
        broken_stage_ids: set[str] | None = None,
        numeric_bool_readback_properties: set[str] | None = None,
        omit_slice_markers_after_delete: bool = False,
        audio_min_volume: float = -60.0,
        qlab_silence_readback: bool = False,
    ):
        self.config = config
        self.cues = {cue_id: dict(values, uniqueID=cue_id) for cue_id, values in cues.items()}
        self.cue_numbers = cue_numbers or {}
        self.fail_set_property = fail_set_property
        self.error_after_apply_properties = error_after_apply_properties or set()
        self.timeout_set_property = timeout_set_property
        self.timeout_set_properties = timeout_set_properties or set()
        self.timeout_without_apply = timeout_without_apply
        self.timeout_without_apply_properties = timeout_without_apply_properties or set()
        self.delay_on_timeout = delay_on_timeout
        self.timeout_apply_after_reads = timeout_apply_after_reads
        self.ignore_set_property = ignore_set_property
        self.pending_timeout_applies: dict[tuple[str, str], Any] = {}
        self.after_read_counts: dict[str, int] = {}
        self.missing_refs = missing_refs or set()
        self.show_mode_data = show_mode_data
        self.connect_data = connect_data
        self.workspace_id = workspace_id
        self.light_patch = light_patch or {"instruments": [], "groups": []}
        self.light_patch_error = light_patch_error
        self.video_stages = video_stages or []
        self.video_stage_regions = video_stage_regions or {}
        self.audio_output_patches = audio_output_patches or []
        self.audio_input_patches = audio_input_patches or []
        self.network_patches = network_patches or []
        self.network_repair_outcomes = network_repair_outcomes or {}
        self.property_outcomes = property_outcomes or {}
        self.children_by_parent = {
            parent_id: list(child_ids) for parent_id, child_ids in (children_by_parent or {}).items()
        }
        self.group_child_outcomes = group_child_outcomes or {}
        self.group_order_outcomes = group_order_outcomes or {}
        self.broken_stage_ids = broken_stage_ids or set()
        self.numeric_bool_readback_properties = numeric_bool_readback_properties or set()
        self.omit_slice_markers_after_delete = omit_slice_markers_after_delete
        self.audio_min_volume = audio_min_volume
        self.qlab_silence_readback = qlab_silence_readback
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []
        self.reply_timeouts: list[float | None] = []

    def request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": self.workspace_id, "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": self.workspace_id, "displayName": "demo.qlab5"}], status="ok")
        if address == f"/workspace/{self.workspace_id}/connect":
            return SimpleNamespace(data=self.connect_data, status="ok")
        if address == f"/workspace/{self.workspace_id}/showMode":
            return SimpleNamespace(data=self.show_mode_data, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/audio/patchList":
            return SimpleNamespace(data=self.audio_output_patches, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/audio/minVolume":
            return SimpleNamespace(data=self.audio_min_volume, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/mic/patchList":
            return SimpleNamespace(data=self.audio_input_patches, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/network/patchList":
            return SimpleNamespace(data=self.network_patches, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/light/patch":
            if self.light_patch_error:
                raise QLabReplyError("error", "Light Patch unavailable", address)
            return SimpleNamespace(data=self.light_patch, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/video/stages":
            return SimpleNamespace(data=self.video_stages, status="ok")
        children_prefix = f"/workspace/{self.workspace_id}/cue_id/"
        if address.startswith(children_prefix) and address.endswith("/children/uniqueIDs/shallow"):
            parent_id = address.removeprefix(children_prefix).removesuffix("/children/uniqueIDs/shallow")
            return SimpleNamespace(
                data=[{"uniqueID": child_id} for child_id in self.children_by_parent.get(parent_id, [])],
                status="ok",
            )
        stage_prefix = f"/workspace/{self.workspace_id}/settings/video/stageID/"
        if address.startswith(stage_prefix) and address.endswith("/regions"):
            stage_id = address.removeprefix(stage_prefix).removesuffix("/regions")
            return SimpleNamespace(data=self.video_stage_regions.get(stage_id, []), status="ok")
        cue_id, prop = self._cue_id_and_property(address)
        if cue_id is None or prop is None:
            raise AssertionError(f"Unexpected fake batch request: {address}")
        if cue_id in self.missing_refs:
            raise QLabReplyError("error", "No cue found", address)
        if prop == "valuesForKeys":
            self.after_read_counts[cue_id] = self.after_read_counts.get(cue_id, 0) + 1
            if self.timeout_apply_after_reads is not None:
                for (pending_cue_id, pending_prop), pending_value in list(self.pending_timeout_applies.items()):
                    if pending_cue_id == cue_id and self.after_read_counts[cue_id] >= self.timeout_apply_after_reads:
                        self._set_property(pending_cue_id, pending_prop, pending_value)
                        del self.pending_timeout_applies[(pending_cue_id, pending_prop)]
            return SimpleNamespace(data=dict(self.cues[cue_id]), status="ok")
        if self.fail_set_property == (cue_id, prop):
            raise QLabReplyError("error", f"Failed setting {prop}", address)
        if self.timeout_set_property == (cue_id, prop) or (cue_id, prop) in self.timeout_set_properties:
            timeout_without_apply = self.timeout_without_apply or (cue_id, prop) in self.timeout_without_apply_properties
            if self.delay_on_timeout and reply_timeout is not None:
                time.sleep(reply_timeout)
            if not timeout_without_apply:
                if self.timeout_apply_after_reads is None:
                    self._set_property(cue_id, prop, self._request_value(prop, args))
                else:
                    self.pending_timeout_applies[(cue_id, prop)] = self._request_value(prop, args)
            raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
        if self.ignore_set_property == (cue_id, prop):
            return SimpleNamespace(data=None, status="ok")
        value = self._request_value(prop, args)
        self._set_property(cue_id, prop, value)
        outcome = None
        if prop in {"customString", "networkPatchID"} and isinstance(value, str):
            outcome = self.network_repair_outcomes.get((cue_id, prop, value))
        if isinstance(value, (str, int, float, bool, type(None))):
            outcome = self.property_outcomes.get((cue_id, prop, value), outcome)
        if outcome:
            self.cues[cue_id].update(outcome)
        group_outcome_key = (cue_id, prop, value) if isinstance(value, (str, int, float, bool, type(None))) else None
        child_outcome = self.group_child_outcomes.get(group_outcome_key) if group_outcome_key else None
        if child_outcome:
            for child_id, child_values in child_outcome.items():
                self.cues[child_id].update(child_values)
        order_outcome = self.group_order_outcomes.get(group_outcome_key) if group_outcome_key else None
        if order_outcome is not None:
            self.children_by_parent[cue_id] = list(order_outcome)
        if (cue_id, prop) in self.error_after_apply_properties:
            raise QLabReplyError("error", f"Failed setting {prop}", address)
        return SimpleNamespace(data=None, status="ok")

    @staticmethod
    def _request_value(prop: str, args: tuple[Any, ...]) -> Any:
        if prop in {
            "quaternion",
            "addSliceMarker",
            "text/format/color",
            "text/format/backgroundColor",
            "text/format/shadowColor",
            "text/format/strikethroughColor",
            "text/format/underlineColor",
        }:
            return list(args)
        return args[0] if args else None

    def _set_property(self, cue_id: str, prop: str, value: Any) -> None:
        if prop == "resetRotation":
            self.cues[cue_id]["quaternion"] = [1, 0, 0, 0]
            return
        if prop.startswith("sliceMarker/") and prop.endswith("/time"):
            index = int(prop.split("/")[1])
            self.cues[cue_id]["sliceMarkers"][index]["time"] = value
            return
        if prop.startswith("sliceMarker/") and prop.endswith("/playCount"):
            index = int(prop.split("/")[1])
            self.cues[cue_id]["sliceMarkers"][index]["playCount"] = value
            return
        if prop == "addSliceMarker":
            time_value, play_count = value
            markers = self.cues[cue_id].setdefault("sliceMarkers", [])
            markers.append({"time": time_value, "playCount": play_count})
            markers.sort(key=lambda marker: marker["time"])
            return
        if prop == "deleteSliceMarkers":
            if self.omit_slice_markers_after_delete:
                self.cues[cue_id].pop("sliceMarkers", None)
            else:
                self.cues[cue_id]["sliceMarkers"] = []
            return
        if prop.startswith("deleteSliceMarker/"):
            index = int(prop.split("/")[1])
            del self.cues[cue_id]["sliceMarkers"][index]
            return
        if prop == "stageID":
            self.cues[cue_id]["isBroken"] = value in self.broken_stage_ids
        if prop in self.numeric_bool_readback_properties and isinstance(value, bool):
            value = int(value)
        if prop.startswith("sliderLevel/"):
            if value == "-inf" and self.qlab_silence_readback:
                value = self.audio_min_volume
            channel = int(prop.split("/")[1])
            levels = list(self.cues[cue_id].setdefault("sliderLevels", []))
            while len(levels) <= channel:
                levels.append(0)
            levels[channel] = value
            self.cues[cue_id]["sliderLevels"] = levels
            return
        if prop.startswith("level/"):
            if value == "-inf" and self.qlab_silence_readback:
                value = self.audio_min_volume
            _, in_channel_text, out_channel_text = prop.split("/", 2)
            in_channel = int(in_channel_text)
            out_channel = int(out_channel_text)
            matrix = [list(row) if isinstance(row, list) else [] for row in self.cues[cue_id].setdefault("levels", [])]
            while len(matrix) <= in_channel:
                matrix.append([])
            row = list(matrix[in_channel])
            while len(row) <= out_channel:
                row.append(0)
            row[out_channel] = value
            matrix[in_channel] = row
            self.cues[cue_id]["levels"] = matrix
            return
        if prop.startswith("doLevel/"):
            _, row_text, column_text = prop.split("/", 2)
            row_index = int(row_text)
            column_index = int(column_text)
            matrix = [
                list(row) if isinstance(row, list) else []
                for row in self.cues[cue_id].setdefault("doLevel", [])
            ]
            while len(matrix) <= row_index:
                matrix.append([])
            row = list(matrix[row_index])
            while len(row) <= column_index:
                row.append(False)
            row[column_index] = value
            matrix[row_index] = row
            self.cues[cue_id]["doLevel"] = matrix
            return
        if prop.startswith("inputChannelName/"):
            self.cues[cue_id][prop] = value
            return
        if prop.startswith("gang/"):
            self.cues[cue_id][prop] = value
            return
        if prop.startswith("mute/channel/") and prop != "mute/channel/clear":
            output = int(prop.split("/")[-1])
            channels = set(self.cues[cue_id].setdefault("muteChannels", []))
            if value:
                channels.add(output)
            else:
                channels.discard(output)
            self.cues[cue_id]["muteChannels"] = sorted(channels)
            return
        if prop == "mute/channel/clear":
            self.cues[cue_id]["muteChannels"] = []
            return
        if prop.startswith("solo/") and prop != "solo/channel/clear":
            output = int(prop.split("/")[-1])
            channels = set(self.cues[cue_id].setdefault("soloChannels", []))
            if value:
                channels.add(output)
            else:
                channels.discard(output)
            self.cues[cue_id]["soloChannels"] = sorted(channels)
            return
        if prop == "solo/channel/clear":
            self.cues[cue_id]["soloChannels"] = []
            return
        parameter_prefix = "videoEffectIndex/0/parameter/"
        if prop.startswith(parameter_prefix):
            parameter_key = prop.removeprefix(parameter_prefix)
            effects = self.cues[cue_id].setdefault("videoEffects", [])
            while len(effects) <= 0:
                effects.append({})
            effect = effects[0]
            if isinstance(effect, dict):
                parameters = effect.get("parameters")
                if isinstance(parameters, dict) and parameter_key in parameters:
                    parameters[parameter_key] = value
                else:
                    effect[parameter_key] = value
                return
        self.cues[cue_id][prop] = value

    def _cue_id_and_property(self, address: str) -> tuple[str | None, str | None]:
        cue_id_prefix = f"/workspace/{self.workspace_id}/cue_id/"
        cue_number_prefix = f"/workspace/{self.workspace_id}/cue/"
        if address.startswith(cue_id_prefix):
            rest = address.removeprefix(cue_id_prefix)
            cue_id, _, prop = rest.partition("/")
            return cue_id, prop
        if address.startswith(cue_number_prefix):
            rest = address.removeprefix(cue_number_prefix)
            number, _, prop = rest.partition("/")
            return self.cue_numbers.get(number), prop
        return None, None


def planned_setters(result_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        operation["property"]: operation
        for operation in result_item["planned_operations"]
        if operation["operation"] in {"set_property", "action"}
    }


def assert_no_confirm_token(value: Any) -> None:
    if isinstance(value, dict):
        assert "confirm_token" not in value
        for nested in value.values():
            assert_no_confirm_token(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_confirm_token(nested)


def normalized_light_patch_fixture() -> dict[str, Any]:
    front = {
        "name": "Front",
        "parameters": {"0": {"name": "intensity"}},
        "definition": {
            "name": "Dimmer",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}},
        },
    }
    red = {
        "name": "Red Fixture",
        "parameters": {"0": {"name": "intensity"}, "1": {"name": "red"}},
        "definition": {
            "name": "RGB",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}, "1": {"name": "red"}},
        },
    }
    dimmer = {
        "name": "Dimmer Only",
        "parameters": {"0": {"name": "intensity"}},
        "definition": {
            "name": "Dimmer",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}},
        },
    }
    return {
        "instruments": [front, red, dimmer],
        "groups": [
            {"name": "Back", "instruments": [red, dimmer]},
            {"name": "all", "instruments": [front, red, dimmer]},
        ],
    }


def confirm_token_for(reader: QLabReader, cue_ref: str, update: dict[str, Any], profile: str = "common") -> str:
    dry_result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_ref, "profile": profile, **update}],
        dry_run=True,
    )
    setters = planned_setters(dry_result["results"][0])
    return setters[next(iter(setters))]["confirm_token"]


def devamp_fixture_cues(
    source_id: str,
    target_id: str,
    *,
    target_type: str = "Audio",
    devamp_type: int = 1,
    start_next: bool = False,
    stop_target: bool = False,
) -> dict[str, dict[str, Any]]:
    return {
        source_id: {
            "type": "Devamp",
            "cueTargetID": target_id,
            "hasCueTargets": True,
            "devampType": devamp_type,
            "startNextCueWhenSliceEnds": start_next,
            "stopTargetWhenSliceEnds": stop_target,
            "isBroken": False,
            "isWarning": False,
            "isRunning": False,
            "isPaused": False,
            "isAuditioning": False,
        },
        target_id: {
            "type": target_type,
            "isBroken": False,
            "isWarning": False,
            "isRunning": False,
            "isPaused": False,
            "isAuditioning": False,
        },
    }


def fade_fixture_cues(
    source_id: str,
    target_id: str,
    *,
    target_type: str = "Video",
    target_id_value: str | None = None,
    broken: bool = False,
    do_opacity: bool = True,
    do_scale: bool = False,
) -> dict[str, dict[str, Any]]:
    return {
        source_id: {
            "type": "Fade",
            "hasCueTargets": True,
            "cueTargetID": target_id if target_id_value is None else target_id_value,
            "targetMode": 0,
            "fadeType": 1,
            "geoMode": 0,
            "doOpacity": do_opacity,
            "doRate": False,
            "doRotation": False,
            "doScale": do_scale,
            "doTranslation": False,
            "opacity": 0.5,
            "name": "Fade fixture",
            "number": "1",
            "notes": "",
            "armed": True,
            "flagged": False,
            "colorName": "none",
            "preWait": 0,
            "postWait": 0,
            "duration": 0,
            "tempDuration": 0,
            "allowsEditingDuration": True,
            "continueMode": 0,
            "skipIfDisarmed": False,
            "autoLoad": False,
            "secondColorName": "none",
            "useSecondColor": False,
            "isBroken": broken,
            "isWarning": False,
            "isRunning": False,
            "isPaused": False,
            "isAuditioning": False,
        },
        target_id: {
            "type": target_type,
            "isBroken": False,
            "isWarning": False,
            "isRunning": False,
            "isPaused": False,
            "isAuditioning": False,
        },
    }


PROFILE_TEST_CUE_TYPES = {
    "common": "Memo",
    "memo_basic": "Memo",
    "wait_basic": "Wait",
    "group_basic": "Group",
    "audio_basic": "Audio",
    "mic_basic": "Mic",
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
    "light_basic": "Light",
    "fade_basic": "Fade",
    "network_basic": "Network",
    "midi_basic": "MIDI",
    "midi_file_basic": "MIDI File",
    "timecode_basic": "Timecode",
    "target_basic": "Start",
    "reset_basic": "Reset",
    "devamp_basic": "Devamp",
    "script_basic": "Script",
}

VIDEO_PHASE2_ALLOWED_PROPERTIES = {
    "anchor/x",
    "anchor/y",
    "blendMode",
    "clockType",
    "cropBottom",
    "cropLeft",
    "cropRight",
    "cropTop",
    "doFade",
    "fillStage",
    "fillStyle",
    "holdLastFrame",
    "infiniteLoop",
    "fixedWidth",
    "layer",
    "opacity",
    "playCount",
    "preservePitch",
    "preserveAspectRatio",
    "rate",
    "scale/x",
    "scale/y",
    "level",
    "sliderLevel",
    "inputChannelName",
    "gang",
    "lockFadeToCue",
    "mute/channel",
    "solo/channel",
    "mute/channel/clear",
    "solo/channel/clear",
    "smooth",
    "stageID",
    "startTime",
    "endTime",
    "text",
    "text/format/alignment",
    "text/format/backgroundColor",
    "text/format/color",
    "text/format/fontName",
    "text/format/fontSize",
    "text/format/lineSpacing",
    "text/format/shadowColor",
    "text/format/shadowBlurRadius",
    "text/format/shadowOffset/width",
    "text/format/shadowOffset/height",
    "text/format/strikethroughColor",
    "text/format/underlineStyle",
    "text/format/underlineColor",
    "text/format/strikethroughStyle",
    "translation/x",
    "translation/y",
    "audioInputPatchID",
    "audioOutputPatchID",
    "videoInputPatchID",
    "sliceMarker/time",
    "sliceMarker/playCount",
    "addSliceMarker",
    "deleteSliceMarker",
    "deleteSliceMarkers",
    "lastSlicePlayCount",
    "lastSliceInfiniteLoop",
}
VIDEO_PHASE3C_SCALAR_PROPERTIES = {
    "scale/x",
    "scale/y",
    "anchor/x",
    "anchor/y",
    "cropTop",
    "cropBottom",
    "cropLeft",
    "cropRight",
}
VIDEO_PHASE3D_APPEARANCE_PROPERTIES = {"blendMode", "preserveAspectRatio"}
PHASE3E_TEXT_BASIC_PROPERTIES = {
    "text",
    "fixedWidth",
    "text/format/alignment",
    "text/format/color",
    "text/format/fontName",
    "text/format/fontSize",
    "text/format/lineSpacing",
}
PHASE3F_TEXT_STYLE_VALUES = {
    "text/format/shadowBlurRadius": 2,
    "text/format/shadowOffset/width": 1,
    "text/format/shadowOffset/height": -1,
    "text/format/underlineStyle": "none",
    "text/format/strikethroughStyle": "single",
}
VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES = {
    "videoEffect/enabled",
    "videoEffectIndex/enabled",
    "videoEffect/parameter",
    "videoEffectIndex/parameter",
}
def _base_cue_values(cue_id: str, cue_type: str) -> dict[str, Any]:
    return {
        "uniqueID": cue_id,
        "number": "1",
        "name": "Stale",
        "displayName": "1 Stale",
        "type": cue_type,
        "armed": True,
        "flagged": False,
        "colorName": "none",
        "allowsEditingDuration": True,
    }


def _valid_value_for_validator(validator: str) -> Any:
    return {
        "any": {"value": True},
        "audio_level_row": 1,
        "audio_object_color_name": "blue",
        "audio_object_ref": "object-1",
        "audio_output_ref": 1,
        "audio_patch_channel_count": 2,
        "boolean": True,
        "byte": 64,
        "byte_combo": 1024,
        "color_condition": 1,
        "color_name": "blue",
        "continue_mode": "auto_continue",
        "cue_target_id": "target-id",
        "cue_target_number": "1",
        "decibel": -6,
        "devamp_type": 1,
        "device_output_ref": 1,
        "dict_or_json_string": {"fontSize": 24},
        "fade_mode": 1,
        "fade_number_type": 1,
        "fade_type": 1,
        "group_mode": 1,
        "int": 1,
        "int_or_minus_one": 1,
        "json_value": {"value": 1},
        "list": [1, 2],
        "list_or_json_string": [1, 2],
        "midi_time_part": 1,
        "midi_channel": 1,
        "midi_message_type": 1,
        "midi_status": 1,
        "midi_timecode_format": 1,
        "network_fade_type": 1,
        "network_fps": 24,
        "non_empty_string": "value",
        "non_negative_int": 1,
        "non_negative_number": 1,
        "number": 1,
        "opacity": 0.5,
        "patch_ref": "Patch 1",
        "positive_int": 2,
        "positive_number": 2,
        "quaternion": [0, 0, 0, 1],
        "rate": 1,
        "rotation_type": 1,
        "second_trigger_action": 1,
        "string": "value",
        "target_id": "target-id",
        "target_mode": 1,
        "text_alignment": "center",
        "text_font_size": 24,
        "text_line_style": "single",
        "timecode_framerate": 1,
        "timecode_part": 1,
        "timecode_output_type": 1,
        "unit_interval": 0.5,
        "video_blend_mode": "Normal",
        "video_clock_type": "video",
        "video_fill_style": 1,
        "video_layer": 1,
    }[validator]


def _invalid_value_for_validator(validator: str) -> Any:
    return {
        "any": object(),
        "audio_level_row": 25,
        "audio_object_color_name": "not-a-color",
        "audio_object_ref": "",
        "audio_output_ref": -1,
        "audio_patch_channel_count": 0,
        "boolean": "yes",
        "byte": 128,
        "byte_combo": 16384,
        "color_condition": 3,
        "color_name": "not-a-color",
        "continue_mode": "bad",
        "cue_target_id": 123,
        "cue_target_number": "",
        "decibel": "loud",
        "devamp_type": 3,
        "device_output_ref": 0,
        "dict_or_json_string": 1,
        "fade_mode": 2,
        "fade_number_type": 2,
        "fade_type": 3,
        "group_mode": 0,
        "int": 1.5,
        "int_or_minus_one": 0,
        "json_value": {1: "bad"},
        "list": "not-list",
        "list_or_json_string": 1,
        "midi_time_part": 128,
        "midi_channel": 17,
        "midi_message_type": 4,
        "midi_status": 7,
        "midi_timecode_format": 4,
        "network_fade_type": 3,
        "network_fps": 0,
        "non_empty_string": "",
        "non_negative_int": -1,
        "non_negative_number": -1,
        "number": "not-number",
        "opacity": 2,
        "patch_ref": -1,
        "positive_int": 0,
        "positive_number": 0,
        "quaternion": [0, 0, 0],
        "rate": 0.01,
        "rotation_type": 4,
        "second_trigger_action": 8,
        "string": 123,
        "target_id": "",
        "target_mode": 2,
        "text_alignment": "middle",
        "text_font_size": 0,
        "text_line_style": "triple",
        "timecode_framerate": 8,
        "timecode_part": 100,
        "timecode_output_type": 2,
        "unit_interval": 2,
        "video_blend_mode": "not-a-blend",
        "video_clock_type": "wall",
        "video_fill_style": 3,
        "video_layer": 1001,
    }[validator]


def _request_for_catalog_property(
    prop_name: str,
    prop: dict[str, Any],
    *,
    invalid_arg: str | None = None,
    invalid_value: Any = None,
) -> dict[str, Any]:
    args = prop["args"]
    if len(args) == 1 and args[0]["name"] == "value":
        value = invalid_value if invalid_arg == "value" else _valid_value_for_validator(args[0]["validator"])
        return {"properties": {prop_name: value}}

    operation_args = {}
    for arg in args:
        operation_args[arg["name"]] = (
            invalid_value
            if invalid_arg == arg["name"]
            else _valid_value_for_validator(arg["validator"])
        )
    return {"operations": [{"property": prop_name, "args": operation_args}]}


def _real_write_property_cases() -> list[Any]:
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            if prop["real_write_enabled"]:
                cases.append(
                    pytest.param(
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        id=f"{profile}:{prop_name}",
                    )
                )
    return cases


def _dry_run_only_property_cases() -> list[Any]:
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            if (
                profile in {"target_basic", "reset_basic"} and prop_name == "cueTargetID"
            ) or (
                profile == "devamp_basic"
                and prop_name in {"cueTargetID", "devampType", "startNextCueWhenSliceEnds", "stopTargetWhenSliceEnds"}
            ) or (
                profile == "fade_basic" and prop_name in write_operations.FADE_PHASE1_PROPERTIES
            ) or (
                profile == "group_basic"
                and prop_name
                in {
                    "mode",
                    "playlist/doLoop",
                    "playlist/doShuffle",
                    "playlist/doCrossfade",
                    "playlist/crossfade/duration",
                }
            ):
                continue
            if not prop["real_write_enabled"]:
                cases.append(
                    pytest.param(
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        id=f"{profile}:{prop_name}",
                    )
                )
    return cases


def _validator_negative_cases() -> list[Any]:
    seen = set()
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            for arg in prop["args"]:
                validator = arg["validator"]
                if validator in seen or validator == "any":
                    continue
                seen.add(validator)
                cases.append(
                    pytest.param(
                        validator,
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        arg["name"],
                        id=f"{validator}:{profile}:{prop_name}.{arg['name']}",
                    )
                )
    return cases


def _assert_update_profile_names_and_shape(catalog: dict[str, Any]) -> None:
    assert set(UPDATE_PROFILE_NAMES) == {
        "common",
        "memo_basic",
        "wait_basic",
        "group_basic",
        "audio_basic",
        "mic_basic",
        "video_basic",
        "camera_basic",
        "text_basic",
        "light_basic",
        "fade_basic",
        "network_basic",
        "midi_basic",
        "midi_file_basic",
        "timecode_basic",
        "target_basic",
        "reset_basic",
        "devamp_basic",
        "script_basic",
    }
    for profile in catalog.values():
        assert "properties" in profile
        assert "risk_tier" in profile
        assert "real_write_enabled" in profile


def _assert_planned_only_props(catalog: dict[str, Any], profile: str, props: tuple[str, ...]) -> None:
    for prop in props:
        assert catalog[profile]["properties"][prop]["real_write_enabled"] is False
        assert catalog[profile]["properties"][prop]["planned_only_reason"]


def _assert_absent_props(catalog: dict[str, Any], profile: str, props: tuple[str, ...]) -> None:
    for prop in props:
        assert prop not in catalog[profile]["properties"]


def _assert_audio_group_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["audio_basic"]["properties"]["level"]["planned_only_reason"]
    assert catalog["audio_basic"]["properties"]["fileTarget"]["planned_only_reason"]
    assert catalog["audio_basic"]["properties"]["level"]["args"] == [
        {"name": "inChannel", "validator": "audio_level_row"},
        {"name": "outChannel", "validator": "audio_output_ref"},
        {"name": "decibel", "validator": "decibel"},
    ]
    assert catalog["audio_basic"]["properties"]["sliderLevel"]["args"] == [
        {"name": "channel", "validator": "audio_output_ref"},
        {"name": "decibel", "validator": "decibel"},
    ]
    _assert_planned_only_props(
        catalog,
        "audio_basic",
        (
            "setDefaultLevels",
            "setSilentLevels",
            "deleteSliceMarker",
            "deleteSliceMarkers",
            "objectIDLevel",
            "audioOutputPatch/level",
            "audioMap/objectID/position",
        ),
    )
    assert catalog["group_basic"]["properties"]["mode"]["args"] == [{"name": "value", "validator": "group_mode"}]
    assert catalog["group_basic"]["properties"]["playlist/crossfade/duration"]["contextual_requirements"] == [
        "group_mode_is_playlist"
    ]
    assert all(
        "curve" not in property_name.casefold()
        for property_name in catalog["group_basic"]["properties"]
        if property_name.startswith("playlist")
    )
    assert catalog["memo_basic"]["properties"]["duration"]["contextual_requirements"] == ["allows_editing_duration"]
    _assert_planned_only_props(
        catalog,
        "group_basic",
        (
            "playhead",
            "playbackPosition",
            "playbackPositionID",
            "playhead/next",
            "playbackPosition/previousSequence",
            "moveCartCue",
            "playlist/currentCue",
            "playlist/currentCueID",
            "playlist/next",
            "playlist/previous",
            "shuffle",
            "playlistLoop",
            "playlistShuffle",
            "playlistCrossfade",
            "playlistCrossfadeDuration",
        ),
    )
    _assert_absent_props(
        catalog,
        "group_basic",
        ("cartRows", "cartColumns", "cartPosition", "cartPosition/row", "cartPosition/column"),
    )
    _assert_absent_props(
        catalog,
        "group_basic",
        (
            "alwaysCollate",
            "collateAndStart",
            "go",
            "start",
            "stop",
            "hardStop",
            "load",
            "pause",
        ),
    )


def _assert_media_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["mic_basic"]["real_write_enabled"] is True
    assert catalog["mic_basic"]["properties"]["channels"]["real_write_enabled"] is False
    assert catalog["mic_basic"]["properties"]["channels"]["planned_only_reason"] == (
        "audio_input_channel_count_needs_patch_bounds_validation"
    )
    assert catalog["video_basic"]["real_write_enabled"] is True
    assert catalog["video_basic"]["properties"]["translation/x"]["real_write_enabled"] is False
    assert catalog["video_basic"]["properties"]["translation/x"]["planned_only_reason"] == (
        "video_phase2_dry_run_only"
    )
    assert "rotation" not in catalog["video_basic"]["properties"]
    assert catalog["video_basic"]["properties"]["crop"]["planned_only_reason"]
    assert catalog["video_basic"]["properties"]["blendMode"]["args"][0]["validator"] == "video_blend_mode"
    assert catalog["video_basic"]["properties"]["clockType"]["args"][0]["validator"] == "video_clock_type"
    _assert_planned_only_props(
        catalog,
        "video_basic",
        (
            "layer",
            "fillStage",
            "fillStyle",
            "holdLastFrame",
            "preserveAspectRatio",
            "smooth",
            "stageName",
            "videoEffects/add",
            "videoEffect/parameter",
            "videoEffect/parameters",
        ),
    )
    assert catalog["camera_basic"]["real_write_enabled"] is True
    assert "rotation" not in catalog["camera_basic"]["properties"]
    assert catalog["camera_basic"]["properties"]["videoEffectIndex/parameter"]["planned_only_reason"]
    assert catalog["text_basic"]["properties"]["text/format/fontFamilyAndStyle"]["planned_only_reason"]
    assert catalog["text_basic"]["properties"]["text"]["real_write_enabled"] is False
    _assert_planned_only_props(
        catalog,
        "text_basic",
        (
            "text/format/shadowOffset",
            "text/format/shadowBlurRadius",
            "text/format/underlineStyle",
        ),
    )


def _assert_show_control_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["midi_file_basic"]["properties"]["rate"]["real_write_enabled"] is True
    assert catalog["network_basic"]["properties"]["customString"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert catalog["network_basic"]["properties"]["networkPatchID"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert catalog["network_basic"]["properties"]["fadeType"]["planned_only_reason"] == "network_fade_routes_require_deterministic_readback"
    assert catalog["network_basic"]["properties"]["parameterValue"]["planned_only_reason"]
    assert catalog["network_basic"]["properties"]["parameterValue"]["path"] == "parameterValue/{parameter}"
    assert catalog["network_basic"]["properties"]["parameterValues"]["args"][0]["validator"] == "list"
    assert catalog["network_basic"]["real_write_enabled"] is True
    _assert_absent_props(catalog, "network_basic", ("message", "messageType", "protocol", "resend", "oscMessage"))
    assert catalog["midi_basic"]["properties"]["note"]["path"] == "byte1"
    assert catalog["midi_basic"]["real_write_enabled"] is True
    assert catalog["midi_basic"]["properties"]["messageType"]["args"][0]["validator"] == "midi_message_type"
    assert catalog["midi_basic"]["properties"]["status"]["args"][0]["validator"] == "midi_status"
    assert catalog["midi_basic"]["properties"]["timecodeFormat"]["args"][0]["validator"] == "midi_timecode_format"
    assert catalog["midi_basic"]["properties"]["doFade"]["planned_only_reason"]
    assert catalog["timecode_basic"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["properties"]["outputType"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["properties"]["timecodeFrameRate"]["path"] == "framerate"
    assert catalog["timecode_basic"]["properties"]["timecodeFrameRate"]["args"][0]["validator"] == "timecode_framerate"
    assert catalog["timecode_basic"]["properties"]["ltcChannel"]["planned_only_reason"]
    assert catalog["timecode_basic"]["properties"]["timecodeString"]["planned_only_reason"]
    assert catalog["timecode_basic"]["properties"]["timecodeFormat"]["planned_only_reason"]
    _assert_planned_only_props(
        catalog,
        "target_basic",
        ("cueTargetID", "cueTargetNumber", "cueTargetName", "tempCueTargetID", "tempCueTargetNumber", "targetMode"),
    )
    assert catalog["target_basic"]["properties"]["cueTargetID"]["args"][0]["validator"] == "cue_target_id"
    assert catalog["target_basic"]["properties"]["cueTargetID"]["contextual_requirements"] == ["target_ref_resolves"]
    assert catalog["target_basic"]["properties"]["cueTargetName"]["contextual_requirements"] == [
        "target_name_resolution_unsupported"
    ]
    assert catalog["target_basic"]["properties"]["cueTargetNumber"]["args"][0]["validator"] == "cue_target_number"
    assert catalog["target_basic"]["properties"]["targetMode"]["args"][0]["validator"] == "target_mode"
    _assert_planned_only_props(
        catalog,
        "reset_basic",
        ("cueTargetID", "cueTargetNumber", "patchTargetID", "audioMapTargetID", "targetMode"),
    )
    assert catalog["reset_basic"]["properties"]["patchTargetID"]["args"][0]["validator"] == "target_id"
    _assert_planned_only_props(
        catalog,
        "devamp_basic",
        (
            "cueTargetID",
            "cueTargetNumber",
            "cueTargetName",
            "tempCueTargetID",
            "tempCueTargetNumber",
            "targetMode",
            "devampType",
            "startNextCueWhenSliceEnds",
            "stopTargetWhenSliceEnds",
        ),
    )
    assert catalog["devamp_basic"]["properties"]["devampType"]["args"][0]["validator"] == "devamp_type"
    assert catalog["devamp_basic"]["properties"]["cueTargetID"]["planned_only_reason"] == "devamp_target_requires_confirm_token"
    assert catalog["devamp_basic"]["properties"]["stopTargetWhenSliceEnds"]["planned_only_reason"] == "devamp_settings_require_confirm_token"


def _assert_light_profile_catalog(catalog: dict[str, Any]) -> None:
    light_properties = catalog["light_basic"]["properties"]
    light_specific = set(light_properties) - set(catalog["common"]["properties"])
    assert light_specific == {
        "alwaysCollate",
        "collateAndStart",
        "lightCommandText",
        "prune",
        "pruneCommands",
        "removeLightCommandsMatching",
        "replaceLightCommand",
        "safeSort",
        "safeSortCommands",
        "setLight",
        "subcontroller",
    }
    for prop in light_specific:
        assert light_properties[prop]["real_write_enabled"] is False
        assert light_properties[prop]["planned_only_reason"]
        assert light_properties[prop]["risk_tier"] == "high"
    assert light_properties["lightCommandText"]["args"][0]["validator"] == "string"
    assert light_properties["alwaysCollate"]["args"][0]["validator"] == "boolean"
    assert light_properties["subcontroller"]["args"][0]["validator"] == "boolean"
    assert light_properties["setLight"]["path"] == "setLight"
    assert light_properties["setLight"]["args"] == [
        {"name": "instrument_or_group", "validator": "non_empty_string"},
        {"name": "setting", "validator": "json_value"},
    ]
    assert light_properties["replaceLightCommand"]["args"] == [
        {"name": "oldCommand", "validator": "non_empty_string"},
        {"name": "newCommand", "validator": "non_empty_string"},
    ]
    assert light_properties["removeLightCommandsMatching"]["args"] == [
        {"name": "match", "validator": "non_empty_string"}
    ]
    for forbidden_light_prop in (
        "parameterValues",
        "parameterFadesEnabled",
        "removeLightCommand",
        "dashboard/setLight",
        "dashboard/updateLatestCue",
        "dashboard/updateSelectedCues",
        "lightPatch",
    ):
        assert forbidden_light_prop not in light_properties


def _assert_fade_script_profile_catalog(catalog: dict[str, Any]) -> None:
    _assert_planned_only_props(
        catalog,
        "fade_basic",
        (
            "stopTargetWhenDone",
            "audioMapTargetID",
            "patchTargetID",
            "targetMode",
            "levelsMode",
            "geoMode",
            "mode",
            "fadeType",
            "pathHeight",
            "pathWidth",
            "rotation",
            "rotationType",
            "doOpacity",
            "opacity",
            "doRate",
            "doRotation",
            "doScale",
            "doTranslation",
            "doLevel",
            "doObjectLevel",
            "doObjectIDLevel",
            "setGeometryFromTarget",
            "setLevelsFromTarget",
            "willFade",
        ),
    )
    assert catalog["fade_basic"]["properties"]["targetMode"]["args"][0]["validator"] == "target_mode"
    assert catalog["fade_basic"]["properties"]["levelsMode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["geoMode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["mode"]["path"] == "levelsMode"
    assert catalog["fade_basic"]["properties"]["mode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["fadeType"]["args"][0]["validator"] == "fade_type"
    assert catalog["fade_basic"]["properties"]["rotationType"]["args"][0]["validator"] == "rotation_type"
    assert catalog["fade_basic"]["properties"]["pathHeight"]["args"][0]["validator"] == "positive_number"
    assert catalog["fade_basic"]["properties"]["pathWidth"]["args"][0]["validator"] == "positive_number"
    assert catalog["fade_basic"]["properties"]["doLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "column", "validator": "audio_output_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["doObjectLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "object", "validator": "audio_object_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["doObjectIDLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "objectID", "validator": "audio_object_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["willFade"]["planned_only_reason"] == "deprecated_use_doLevel"
    _assert_absent_props(catalog, "fade_basic", ("fadeEntries", "fadeFrom", "fadeTo", "fps"))
    assert catalog["script_basic"]["real_write_enabled"] is True
    assert catalog["script_basic"]["properties"]["scriptSource"]["planned_only_reason"] == "not_editable_by_osc"


def test_update_registry_covers_all_profiles_and_planned_only_risk() -> None:
    catalog = profile_catalog()

    _assert_update_profile_names_and_shape(catalog)
    _assert_audio_group_profile_catalog(catalog)
    _assert_media_profile_catalog(catalog)
    _assert_show_control_profile_catalog(catalog)
    _assert_light_profile_catalog(catalog)
    _assert_fade_script_profile_catalog(catalog)


@pytest.mark.parametrize("profile", UPDATE_PROFILE_NAMES)
def test_update_cues_dry_run_contract_covers_every_profile(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_type = PROFILE_TEST_CUE_TYPES[profile]
    properties = profile_catalog()[profile]["properties"]
    prop_name = "targetMode" if profile == "fade_basic" else next(iter(properties))
    prop = properties[prop_name]
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True, (profile, result)
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(("profile", "cue_type", "prop_name", "prop"), _real_write_property_cases())
def test_update_cue_real_write_contract_covers_every_real_write_property(
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values = _base_cue_values(cue_id, cue_type)
    if profile == "group_basic" and prop_name.startswith("playlist/"):
        cue_values["mode"] = 6
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    result = reader.update_cue(
        "ws-1",
        cue_id,
        update.get("properties"),
        dry_run=False,
        profile=profile,
        operations=update.get("operations"),
    )

    assert result["ok"] is True, (profile, prop_name, result)
    assert result["status"] == "updated", (profile, prop_name, result)
    assert result["executed_operations"], (profile, prop_name, result)
    assert result["errors"] is None, (profile, prop_name, result)
    for key, value in result["properties"].items():
        assert result["after"][key] == value, (profile, prop_name, key, result)


@pytest.mark.parametrize(("profile", "cue_type", "prop_name", "prop"), _dry_run_only_property_cases())
def test_update_cue_dry_run_only_contract_plans_then_blocks_real_write_before_osc(
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values = _base_cue_values(cue_id, cue_type)
    if prop_name in {"translation/x", "translation/y"} | VIDEO_PHASE3C_SCALAR_PROPERTIES:
        cue_values[prop_name] = 0
    elif prop_name == "fillStage":
        cue_values[prop_name] = False
    elif prop_name == "fillStyle":
        cue_values[prop_name] = 0
    elif prop_name == "layer":
        cue_values[prop_name] = 10
    elif prop_name == "quaternion":
        cue_values[prop_name] = [0, 0, 0, 1]
    elif prop_name == "resetRotation":
        cue_values["quaternion"] = [0, 0, 0, 1]
    elif prop_name == "blendMode":
        cue_values[prop_name] = "Multiply"
    elif prop_name == "preserveAspectRatio":
        cue_values[prop_name] = True
    elif prop_name == "smooth":
        cue_values[prop_name] = False
    elif prop_name in {"stageID", "audioOutputPatchID", "videoInputPatchID", "audioInputPatchID"}:
        cue_values[prop_name] = "old-id"
    elif profile == "video_basic" and prop_name in {
        "rate",
        "startTime",
        "endTime",
        "playCount",
        "infiniteLoop",
        "preservePitch",
        "holdLastFrame",
    }:
        cue_values.update(
            {
                "rate": 1.0,
                "startTime": 0,
                "endTime": 10,
                "playCount": 1,
                "infiniteLoop": False,
                "preservePitch": True,
                "holdLastFrame": False,
                "audioTrackFormats": [{"channels": 2}],
            }
        )
    elif profile == "video_basic" and prop_name == "sliderLevel":
        cue_values.update(
            {
                "sliderLevels": [0.0, 0.0],
                "audioTrackFormats": [{"channels": 2}],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name == "level":
        cue_values.update(
            {
                "levels": [[0.0, 0.0], [0.0, 0.0]],
                "numChannelsIn": 1,
                "audioTrackFormats": [{"channels": 2}],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name in {"clockType", "doFade", "lockFadeToCue"}:
        cue_values.update(
            {
                "audioTrackFormats": [{"channels": 2}],
                "numChannelsIn": 2,
                "clockType": "video",
                "doFade": False,
                "lockFadeToCue": False,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif (
        profile in {"video_basic", "audio_basic", "mic_basic"}
        and prop_name in {"inputChannelName", "gang"}
    ) or (
        profile == "video_basic"
        and prop_name in {"mute/channel", "solo/channel", "mute/channel/clear", "solo/channel/clear"}
    ):
        cue_values.update(
            {
                "numChannelsIn": 2,
                "sliderLevels": [0.0, 0.0],
                "levels": [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
                "inputChannelName/2": "R",
                "gang/1/1": "music",
                "muteChannels": [1],
                "soloChannels": [1],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
        if profile == "video_basic":
            cue_values["audioTrackFormats"] = [{"channels": 2}]
    elif profile == "video_basic" and prop_name in {
        "sliceMarker/time",
        "sliceMarker/playCount",
        "addSliceMarker",
        "deleteSliceMarker",
        "deleteSliceMarkers",
        "lastSlicePlayCount",
        "lastSliceInfiniteLoop",
    }:
        cue_values.update(
            {
                "sliceMarkers": [{"time": 0.0, "playCount": 1}, {"time": 6.0, "playCount": 2}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "text_basic" and prop_name in PHASE3E_TEXT_BASIC_PROPERTIES:
        cue_values[prop_name] = {
            "text": "Old text",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/backgroundColor": [1, 1, 1, 1],
            "text/format/color": [1, 1, 1, 1],
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
            "text/format/lineSpacing": 1,
            "text/format/shadowColor": [0, 0, 0, 1],
            "text/format/strikethroughColor": [1, 1, 1, 1],
            "text/format/underlineColor": [1, 1, 1, 1],
        }[prop_name]
    elif profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES:
        cue_values[prop_name] = PHASE3F_TEXT_STYLE_VALUES[prop_name]
    dry_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    dry_reader = QLabReader(dry_client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    dry_result = dry_reader.update_cue(
        "ws-1",
        cue_id,
        update.get("properties"),
        dry_run=True,
        profile=profile,
        operations=update.get("operations"),
    )

    assert dry_result["executed_operations"] == []
    if dry_result["ok"]:
        setters = planned_setters(dry_result)
        assert prop_name in setters, (profile, prop_name, dry_result)
        assert setters[prop_name]["real_write_enabled"] is False
        assert setters[prop_name]["planned_only_reason"]
    else:
        assert dry_result["status"] == "dry_run_preflight_failed", (profile, prop_name, dry_result)
        assert dry_result["planned_operations"] == []
        video_phase2_blocked = (
            profile in {"video_basic", "camera_basic", "text_basic"}
            and prop_name not in VIDEO_PHASE2_ALLOWED_PROPERTIES
            and prop_name not in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES
        )
        if video_phase2_blocked:
            assert "blocked even for dry-run by Video-family policy" in dry_result["errors"][prop_name]
            assert dry_client.requests == []
        elif prop_name in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES:
            assert prop_name in dry_result["errors"]
        elif profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES:
            assert "baseline/readback is unavailable" in dry_result["errors"][prop_name]
        elif profile == "text_basic" and prop_name in PHASE3E_TEXT_BASIC_PROPERTIES:
            assert f"requires readable {prop_name} baseline" in dry_result["errors"][prop_name]
        else:
            assert "read_before" in dry_result["errors"], (profile, prop_name, dry_result)

    real_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    real_reader = QLabReader(real_client)  # type: ignore[arg-type]
    if (profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES) or profile == "fade_basic":
        real_result = real_reader.update_cue(
            "ws-1",
            cue_id,
            update.get("properties"),
            dry_run=False,
            profile=profile,
            operations=update.get("operations"),
        )
        assert real_result["status"] == "preflight_failed"
        assert real_result["executed_operations"] == []
        assert_no_confirm_token(real_result)
        assert not any(address.endswith(f"/{prop_name}") for address, _, _ in real_client.requests)
    else:
        with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
            real_reader.update_cue(
                "ws-1",
                cue_id,
                update.get("properties"),
                dry_run=False,
                profile=profile,
                operations=update.get("operations"),
            )
        assert real_client.requests == []


@pytest.mark.parametrize(
    ("validator", "profile", "cue_type", "prop_name", "prop", "arg_name"),
    _validator_negative_cases(),
)
def test_update_cues_validator_contract_rejects_one_bad_value_without_plan_or_osc(
    validator: str,
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
    arg_name: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(
        prop_name,
        prop,
        invalid_arg=arg_name,
        invalid_value=_invalid_value_for_validator(validator),
    )

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False, (validator, profile, prop_name, result)
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert not any("/cue/" in address or "/cue_id/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize("profile", [name for name in UPDATE_PROFILE_NAMES if name != "common"])
def test_update_cues_profile_mismatch_contract_has_no_plan_or_setters(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    expected_type = PROFILE_TEST_CUE_TYPES[profile]
    mismatched_type = "Wait" if expected_type == "Memo" else "Memo"
    prop_name, prop = next(iter(profile_catalog()[profile]["properties"].items()))
    update = _request_for_catalog_property(prop_name, prop)
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, mismatched_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False, (profile, result)
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert "profile" in result["results"][0]["errors"]


def test_write_config_defaults_to_disabled_and_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QLAB_ENABLE_WRITE", raising=False)
    monkeypatch.delenv("QLAB_WRITE_DRY_RUN_DEFAULT", raising=False)
    monkeypatch.delenv("QLAB_UPDATE_DEBUG", raising=False)

    config = QLabConfig.from_env()

    assert config.enable_write is False
    assert config.write_dry_run_default is True
    assert config.update_debug is False


def test_write_config_reads_update_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QLAB_UPDATE_DEBUG", "true")

    config = QLabConfig.from_env()

    assert config.update_debug is True


def test_check_write_readiness_reports_disabled_without_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "write_disabled"
    assert result["blockers"] == ["write_disabled"]
    assert result["error_code"] == "QLAB_WRITE_WRITE_DISABLED"
    assert result["suggested_action"] == "Set QLAB_ENABLE_WRITE=true only for a deliberate write session."
    assert result["passcode_configured"] is True
    assert result["capabilities"]["create_cue"]["dry_run_default"] is True
    assert result["capabilities"]["batch_update_cues"]["tool"] == "qlab_edit_cues"
    assert result["capabilities"]["batch_update_cues"]["batch"] == {
        "min_items": 1,
        "max_items": 50,
        "requires_concrete_cue_refs": True,
        "ambiguous_refs_allowed": False,
        "preflight_before_any_setter": True,
        "setter_target": "cue_id",
    }
    assert client.requests == []


def test_check_write_readiness_requires_passcode_without_leaking_secret() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "passcode_missing"
    assert result["blockers"] == ["passcode_missing"]
    assert result["error_code"] == "QLAB_WRITE_PASSCODE_MISSING"
    assert "QLAB_PASSCODE" in result["suggested_action"]
    assert "passcode" in result["checks"]
    assert "secret" not in str(result)
    assert client.requests == []


def test_check_write_readiness_requires_edit_confirmed_by_connect() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["error_code"] is None
    assert result["suggested_action"] is None
    assert result["checks"]["workspace_resolution"]["ok"] is True
    assert result["checks"]["edit_permission"]["status"] == "confirmed"
    assert result["checks"]["connect"]["scopes"] == ["view", "edit"]
    assert result["checks"]["show_mode"]["mode"] == "edit"
    assert client.requests == [
        ("/workspaces", (), None),
        ("/workspace/ws-1/connect", ("server-pass",), None),
        ("/workspace/ws-1/showMode", (), "ws-1"),
    ]


@pytest.mark.parametrize("connect_data", ["ok:view", "ok:view|control", "ok:admin"])
def test_check_write_readiness_blocks_without_edit_scope(connect_data: str) -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data=connect_data)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "edit_not_confirmed"
    assert result["blockers"] == ["edit_not_confirmed"]
    assert result["error_code"] == "QLAB_WRITE_EDIT_NOT_CONFIRMED"
    assert result["checks"]["edit_permission"]["ok"] is False


def test_check_write_readiness_blocks_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "workspace_in_show_mode"
    assert result["blockers"] == ["workspace_in_show_mode"]
    assert result["suggested_action"] == "Switch the QLab workspace to Edit Mode before real writes."
    assert result["checks"]["show_mode"]["mode"] == "show"


def test_check_write_readiness_blocks_unknown_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data="nope")
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "show_mode_unknown"
    assert result["blockers"] == ["show_mode_unknown"]
    assert result["checks"]["show_mode"]["status"] == "unexpected_data"


def test_check_write_readiness_invalid_workspace_fails_before_edit_checks() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("missing-ws")

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["checks"]["workspace_resolution"]["ok"] is False
    assert result["checks"]["connect"] is None
    assert result["checks"]["show_mode"] is None
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_write_readiness_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = WriteReadinessResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "write_enabled": True,
                "dry_run_default": True,
                "passcode_configured": True,
                "capabilities": {},
                "checks": {},
                "blockers": [status],
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert "passcode" not in str(result.model_dump().get("errors", ""))


def test_create_cue_disabled_blocks_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Write mode is disabled"):
        reader.create_cue("ws-1", "audio", dry_run=False)

    assert client.requests == []


def test_create_cue_dry_run_sends_no_mutating_osc() -> None:
    reader = CreateAnchorReader(config=QLabConfig(enable_write=False, passcode=None))

    result = reader.create_cue(
        reader.workspace,
        "audio",
        dry_run=True,
        after_cue_id=reader.anchor_id,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["cue_type"] == "Audio"
    assert result["properties"] == {}
    assert result["placement"]["after_cue_id"] == reader.anchor_id
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "new",
        "verify",
        "verify_structure",
    ]
    assert reader.requests == []


def test_create_cue_031b_dry_run_returns_anchor_bound_token_and_structure() -> None:
    reader = CreateAnchorReader()

    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=True,
        after_cue_id=reader.anchor_id,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["confirm_token"].startswith("confirm:createCue:v2:")
    assert result["placement"]["parent_id"] == reader.list_id
    assert result["placement"]["expected_index"] == 1
    assert result["planned_operations"][0]["args"] == ["wait", reader.anchor_id]
    assert not any(operation["operation"] == "move_after" for operation in result["planned_operations"])
    assert reader.requests == []


def test_create_cue_031b_consumes_token_verifies_order_and_rejects_replay() -> None:
    reader = CreateAnchorReader(config=QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=False))
    planned = reader.create_cue(reader.workspace, "wait", dry_run=True, after_cue_id=reader.anchor_id)

    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["verification"]["structure"]["parent_id"] == reader.list_id
    assert result["verification"]["structure"]["index"] == 1
    assert result["created_cue_id"] == reader.created_id
    assert [address for address, _, _ in reader.requests].count(f"/workspace/{reader.workspace}/new") == 1
    assert all(
        f"/cue_id/{reader.created_id}/" not in address or address.endswith("/valuesForKeys")
        for address, _, _ in reader.requests
    )

    replay = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )
    assert replay["ok"] is False
    assert replay["status"] == "preflight_failed"
    assert "already been used" in replay["errors"]["confirm_token"]


@pytest.mark.parametrize(
    ("health_overrides", "status"),
    [
        ({"isBroken": True}, "broken"),
        ({"isWarning": True}, "warning"),
        ({"isBroken": "missing"}, "unknown"),
    ],
)
def test_create_accepts_operational_health_states_when_structurally_verified(
    health_overrides: dict[str, Any], status: str
) -> None:
    reader = CreateAnchorReader(health_overrides=health_overrides)
    planned = reader.create_cue(reader.workspace, "wait", dry_run=True, after_cue_id=reader.anchor_id)
    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["cleanup_required"] is False
    assert result["verification"]["health"]["status"] == status


def test_create_active_readback_requires_manual_review() -> None:
    reader = CreateAnchorReader(health_overrides={"isRunning": True})
    planned = reader.create_cue(reader.workspace, "wait", dry_run=True, after_cue_id=reader.anchor_id)
    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is False
    assert result["cleanup_required"] is True
    assert result["verification"]["health"]["active"] is True


def test_create_cue_031b_requires_an_exact_anchor_uuid() -> None:
    reader = CreateAnchorReader()
    with pytest.raises(UnsafeWriteOperationError, match="exactly one of after_cue_id or parent_container_id"):
        reader.create_cue(reader.workspace, "wait", dry_run=True)


def test_create_cue_031b_rejects_structural_drift_before_new(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = CreateAnchorReader(config=QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=False))
    planned = reader.create_cue(reader.workspace, "wait", dry_run=True, after_cue_id=reader.anchor_id)
    reader.extra_children = ["44444444-4444-4444-8444-444444444444"]

    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "structure" in result["errors"]["confirm_token"]
    assert not any(address.endswith("/new") for address, _, _ in reader.requests)


def test_create_cue_031b_rejects_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = CreateAnchorReader(config=QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=False))
    planned = reader.create_cue(reader.workspace, "wait", dry_run=True, after_cue_id=reader.anchor_id)
    monkeypatch.setattr(write_operations.time, "time", lambda: 10**10)

    result = reader.create_cue(
        reader.workspace,
        "wait",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "expired" in result["errors"]["confirm_token"]
    assert not any(address.endswith("/new") for address, _, _ in reader.requests)


def test_create_cue_dry_run_invalid_workspace_has_no_plan() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue(
        "missing-ws",
        "memo",
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert "workspace_resolution" in result["errors"]
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_create_cue_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = CreateCueResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "cue_type": "Memo",
                "dry_run": True,
                "properties": {},
                "planned_operations": [],
                "executed_operations": [],
                "errors": {"workspace_resolution": "Workspace not found: INVALID"},
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert result.planned_operations == []
        assert result.executed_operations == []


def test_create_cue_rejects_script_and_container_types_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "script", dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "cue list", dry_run=True)

    assert client.requests == []




def test_create_cue_real_with_after_cue_id_fails_safely_without_passcode_leak() -> None:
    secret = "server-super-secret"
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=secret))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError) as exc_info:
        reader.create_cue("ws-1", "audio", dry_run=False, after_cue_id="cue-before")

    message = str(exc_info.value)
    assert "exact cue UUID" in message
    assert secret not in message
    assert not any(address.endswith("/new") for address, _, _ in client.requests)


def test_create_cue_real_blocks_without_confirmed_edit() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data="ok:view|control")
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="edit permission"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == ["/workspaces", "/workspace/ws-1/connect"]


def test_create_cue_real_blocks_in_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]
    assert client.requests[-1][2] == "ws-1"


def test_create_new_timeout_is_indeterminate_and_sends_no_setters(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    reader = CreateAnchorReader(
        config=QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=False),
        timeout_new=True,
    )
    reader.created_id = cue_id
    plan = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        after_cue_id=reader.anchor_id,
    )
    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=plan["confirm_token"],
    )  # type: ignore[arg-type]

    assert result["ok"] is False
    assert result["cleanup_required"] is True
    assert result["error_code"] == "create_identity_indeterminate"
    assert not any("/cue_id/" in address for address, _, _ in reader.requests)


def test_create_rejects_invalid_new_uuid_without_setters() -> None:
    reader = CreateAnchorReader(
        config=QLabConfig(enable_write=True, passcode="server-pass", write_dry_run_default=False),
    )
    reader.created_id = "not-a-uuid"
    plan = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=True,
        after_cue_id=reader.anchor_id,
    )
    result = reader.create_cue(
        reader.workspace,
        "memo",
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=plan["confirm_token"],
    )  # type: ignore[arg-type]

    assert result["ok"] is False
    assert result["error_code"] == "create_identity_invalid"
    assert result["cleanup_required"] is True
    assert not any("/cue_id/" in address for address, _, _ in reader.requests)


def test_update_cue_dry_run_sends_no_mutating_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=True)

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["before"]["name"] == "Stale"
    assert result["diff"]["name"] == {"before": "Stale", "requested": "New"}
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "read_before",
        "set_property",
        "set_property",
        "verify",
    ]
    assert [request[0] for request in client.requests] == [f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"]


def test_update_cues_batch_dry_run_allows_mixed_profiles() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    text_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old", "flagged": False},
            audio_id: {"type": "Audio", "name": "Audio old", "rate": 1.0},
            text_id: {"type": "Text", "name": "Text old", "text": "Old", "text/format/fontSize": 24},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "profile": "common", "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
            {"cue_ref": text_id, "profile": "text_basic", "properties": {"name": "Text new"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["requested_count"] == 3
    assert result["planned_count"] == 3
    assert result["updated_count"] == 0
    assert [item["profile"] for item in result["results"]] == ["common", "audio_basic", "text_basic"]
    assert all(item["executed_operations"] == [] for item in result["results"])
    assert all("updateq_plan" not in item for item in result["results"])
    assert all(request[0].endswith("/valuesForKeys") for request in client.requests)


def test_update_cues_single_item_real_uses_unique_id_and_one_readiness_check() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "flagged": False}},
        cue_numbers={"1": cue_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": "1", "properties": {"name": "New"}}], dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["updated_count"] == 1
    assert addresses.count("/workspaces") == 1
    assert addresses.count("/workspace/ws-1/connect") == 1
    assert addresses.count("/workspace/ws-1/showMode") == 1
    assert "/workspace/ws-1/cue/1/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert "/workspace/ws-1/cue/1/name" not in addresses


def test_update_cues_returns_normalization_failure_before_later_stages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = BatchFakeWriteClient(QLabConfig(enable_write=False), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]
    failure = {"ok": False, "status": "preflight_failed"}

    def fail_normalization(
        self: Any,
        workspace_id: str,
        updates: list[dict[str, Any]],
        dry_run: bool | None,
    ) -> dict[str, Any]:
        assert self is reader
        assert workspace_id == "ws-1"
        assert updates == [{"cue_ref": "cue-1", "properties": {"name": "New"}}]
        assert dry_run is True
        return failure

    monkeypatch.setattr(
        write_operations.QLabWriteMixin,
        "_normalize_and_validate_update_batch",
        fail_normalization,
    )
    monkeypatch.setattr(
        write_operations,
        "_plan_update_batch_dry_run",
        lambda *_args, **_kwargs: pytest.fail("dry-run planning must not run after normalization failure"),
    )

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": "cue-1", "properties": {"name": "New"}}],
        dry_run=True,
    )

    assert result is failure
    assert client.requests == []


def test_update_cues_normalization_boundary_returns_complete_bundle_and_blocks_missing_gate() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(QLabConfig(enable_write=True), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]

    bundle = reader._normalize_and_validate_update_batch(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"name": "New"}}],
        True,
    )

    assert set(bundle) == {
        "workspace",
        "effective_dry_run",
        "items",
        "requested_count",
        "calls",
    }
    assert bundle["workspace"] == "ws-1"
    assert bundle["effective_dry_run"] is True
    assert bundle["requested_count"] == 1
    assert set(bundle["calls"]) == UPDATE_BATCH_CALL_NAMES
    assert not any(bundle["calls"]["extracted_family_calls"].values())
    assert not any(
        value
        for name, value in bundle["calls"].items()
        if name != "extracted_family_calls"
    )
    assert client.requests == []

    gate_failure = reader._normalize_and_validate_update_batch(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "properties": {"opacity": 0.5},
            }
        ],
        False,
    )

    assert gate_failure["status"] == "preflight_failed"
    assert gate_failure["results"][0]["errors"]["opacity"] == (
        "opacity is gated or dry-run only without exactly one reviewed "
        "Phase 3A confirm_token."
    )
    assert client.requests == []


def test_update_cues_real_delegates_one_setter_and_fresh_readback_to_execution_helper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "flagged": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    original = write_operations._execute_and_verify_update_batch
    helper_calls = 0

    def tracked_helper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal helper_calls
        helper_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(write_operations, "_execute_and_verify_update_batch", tracked_helper)

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"name": "New"}}],
        dry_run=False,
    )

    cue_prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
    cue_requests = [address for address, *_ in client.requests if address.startswith(cue_prefix)]
    assert result["status"] == "updated"
    assert helper_calls == 1
    assert cue_requests == [
        f"{cue_prefix}valuesForKeys",
        f"{cue_prefix}name",
        f"{cue_prefix}valuesForKeys",
    ]


def test_update_cues_real_preflight_helper_sends_no_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "flagged": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    item = write_operations._normalize_batch_update_item_for_batch(
        {"cue_ref": cue_id, "properties": {"name": "New"}}
    )

    with pytest.raises(KeyError):
        write_operations._preflight_update_batch_real(
            reader,
            "ws-1",
            [item],
            time.monotonic() + write_operations.UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
            requested_count=1,
            calls={},
        )

    preflight = write_operations._preflight_update_batch_real(
        reader,
        "ws-1",
        [item],
        time.monotonic() + write_operations.UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
        requested_count=1,
        calls={
            **{name: False for name in UPDATE_BATCH_CALL_NAMES},
            "extracted_family_calls": {
                family: False
                for family in write_operations._EXTRACTED_WRITE_FAMILIES
            },
        },
    )

    cue_prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
    cue_requests = [address for address, *_ in client.requests if address.startswith(cue_prefix)]
    assert preflight["workspace"] == "ws-1"
    assert preflight["preflight_results"][0]["status"] == "planned"
    assert cue_requests == [f"{cue_prefix}valuesForKeys"]


def test_update_cues_dry_run_delegates_planning_without_setter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "name": "Old", "flagged": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    original = write_operations._plan_update_batch_dry_run
    helper_calls = 0

    def tracked_helper(*args: Any, **kwargs: Any) -> dict[str, Any]:
        nonlocal helper_calls
        helper_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(write_operations, "_plan_update_batch_dry_run", tracked_helper)

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"name": "New"}}],
        dry_run=True,
    )

    cue_prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
    cue_requests = [address for address, *_ in client.requests if address.startswith(cue_prefix)]
    assert result["status"] == "dry_run"
    assert helper_calls == 1
    assert cue_requests == [f"{cue_prefix}valuesForKeys"]


def test_update_cues_rejects_empty_and_over_limit() -> None:
    client = BatchFakeWriteClient(QLabConfig(enable_write=False), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="updates must be a list"):
        reader.update_cues("ws-1", "not-a-list", dry_run=True)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="at least one"):
        reader.update_cues("ws-1", [], dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="at most 50"):
        reader.update_cues(
            "ws-1",
            [{"cue_ref": str(index), "properties": {"name": "x"}} for index in range(51)],
            dry_run=True,
        )

    assert client.requests == []


def test_update_cues_dry_run_reports_invalid_property_value_per_item() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    group_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            group_id: {"type": "Group", "preWait": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo old"}},
            {"cue_ref": group_id, "properties": {"preWait": -1}},
        ],
        dry_run=True,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["dry_run"] is True
    assert result["requested_count"] == 2
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "preWait must be a non-negative number"
    assert result["results"][1]["planned_operations"] == []
    assert f"/workspace/ws-1/cue_id/{memo_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/preWait" not in addresses


def test_update_cues_dry_run_rejects_osc_unrepresentable_number_before_plan_or_setter() -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Group", "preWait": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"preWait": 10**309}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][0]["errors"]["error_code"] == "osc_value_out_of_range"
    assert result["results"][0]["planned_operations"] == []
    assert not any(address.endswith("/preWait") for address, _, _ in client.requests)


def test_update_cues_dry_run_rejects_unknown_color_name_without_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "colorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"colorName": "banana"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "colorName must be one of" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []


def test_update_cues_dry_run_accepts_known_color_name() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "colorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"colorName": "blue"}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert result["results"][0]["properties"]["colorName"] == "blue"
    assert result["results"][0]["planned_operations"]


def test_update_cues_dry_run_invalid_workspace_has_no_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "notes": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "missing-ws",
        [{"cue_ref": cue_id, "properties": {"notes": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["planned_count"] == 0
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert "workspace_resolution" in result["errors"]
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_update_cues_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = UpdateCuesResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 0,
                "updated_count": 0,
                "failed_count": 1,
                "timeout_confirmed_count": 0,
                "results": [],
                "errors": {"workspace_resolution": "Workspace not found: INVALID"},
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert result.planned_count == 0
        assert result.results == []


def test_update_cues_dry_run_reports_video_opacity_validation_per_item() -> None:
    video_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={video_id: {"type": "Video", "opacity": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    valid = reader.update_cues(
        "ws-1",
        [{"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )
    invalid = reader.update_cues(
        "ws-1",
        [{"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 80}}],
        dry_run=True,
    )

    assert valid["ok"] is True
    assert valid["results"][0]["status"] == "dry_run"
    assert valid["results"][0]["properties"]["opacity"] == 0.8
    assert invalid["ok"] is False
    assert invalid["results"][0]["status"] == "dry_run_preflight_failed"
    assert invalid["results"][0]["errors"]["validation"] == "opacity must be a number from 0 to 1"


def test_update_cues_dry_run_reports_video_text_extended_validation_per_item() -> None:
    video_id = "11111111-1111-4111-8111-111111111111"
    text_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            video_id: {"type": "Video", "blendMode": "Normal", "clockType": "video"},
            text_id: {"type": "Text", "text/format/shadowBlurRadius": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"blendMode": "not a blend mode"}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"clockType": "wall"}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"layer": 1001}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"fillStyle": 4}},
            {"cue_ref": text_id, "profile": "text_basic", "properties": {"text/format/shadowBlurRadius": -1}},
            {
                "cue_ref": video_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "videoEffect/parameter", "args": {"name": "ColorControls", "parameterKey": "inputBrightness"}}
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 6
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert "blendMode must be one of:" in result["results"][0]["errors"]["validation"]
    assert result["results"][1]["errors"]["validation"] == "clockType must be exactly audio or video"
    assert result["results"][2]["errors"]["validation"] == "layer must be an integer from 0 to 1000"
    assert result["results"][3]["errors"]["validation"] == "fillStyle must be 0 for fit, 1 for fill, or 2 for stretch"
    assert result["results"][4]["errors"]["validation"] == "text/format/shadowBlurRadius must be a non-negative number"
    assert "videoEffect/parameter args missing required key: setting" in result["results"][5]["errors"]["validation"]


def test_update_cues_dry_run_reports_text_rgba_validation_per_item() -> None:
    valid_text_id = "11111111-1111-4111-8111-111111111111"
    invalid_text_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            valid_text_id: {"type": "Text", "text/format/color": [1, 1, 1, 1]},
            invalid_text_id: {"type": "Text", "text/format/color": [1, 1, 1, 1]},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": valid_text_id,
                "profile": "text_basic",
                "operations": [
                    {"property": "text/format/color", "args": {"red": 1, "green": 0.5, "blue": 0, "alpha": 1}}
                ],
            },
            {
                "cue_ref": invalid_text_id,
                "profile": "text_basic",
                "operations": [
                    {"property": "text/format/color", "args": {"red": 255, "green": 0, "blue": 0, "alpha": 1}}
                ],
            }
        ],
        dry_run=True,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "Video-family dry-runs require exactly one cue and one property" in result["results"][0]["errors"]["video_phase2"]
    assert_no_confirm_token(result["results"][0])
    assert result["results"][1]["errors"]["validation"] == "text/format/color.red must be a number from 0 to 1"
    assert "read_before" not in result["results"][1]["errors"]
    assert result["results"][1]["planned_operations"] == []
    assert f"/workspace/ws-1/cue_id/{valid_text_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{invalid_text_id}/valuesForKeys" not in addresses


def test_update_cues_dry_run_unresolved_ref_has_no_planned_operations() -> None:
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": missing_id, "properties": {"notes": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["updated_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "read_before" in result["results"][0]["errors"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_dry_run_mixed_unresolved_ref_keeps_valid_plan_only() -> None:
    valid_id = "11111111-1111-4111-8111-111111111111"
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={valid_id: {"type": "Memo", "notes": "Old"}},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": valid_id, "properties": {"notes": "Ok"}},
            {"cue_ref": missing_id, "properties": {"notes": "Nope"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 1
    assert result["updated_count"] == 0
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][0]["planned_operations"]
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "read_before" in result["results"][1]["errors"]
    assert result["results"][1]["planned_operations"] == []
    assert result["results"][1]["executed_operations"] == []


def test_update_cues_dry_run_reports_invalid_continue_mode_per_item() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "continueMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"continueMode": "bad_mode"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["validation"] == (
        "continueMode must be 0, 1, 2, do_not_continue, auto_continue, or auto_follow"
    )


def test_update_cues_transport_target_profiles_dry_run_plan_documented_targets() -> None:
    start_id = "11111111-1111-4111-8111-111111111111"
    reset_id = "22222222-2222-4222-8222-222222222222"
    devamp_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            start_id: {"type": "Start", "cueTargetID": "", "cueTargetNumber": "", "targetMode": 0},
            reset_id: {"type": "Reset", "patchTargetID": "old-patch", "audioMapTargetID": "old-map", "targetMode": 0},
            devamp_id: {
                "type": "Devamp",
                "cueTargetID": "",
                "cueTargetNumber": "",
                "targetMode": 0,
                "devampType": 1,
                "startNextCueWhenSliceEnds": False,
                "stopTargetWhenSliceEnds": True,
            },
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": start_id,
                "profile": "target_basic",
                "properties": {
                    "cueTargetID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cueTargetNumber": "LX1",
                    "tempCueTargetID": "none",
                    "tempCueTargetNumber": "LX2",
                    "targetMode": 0,
                },
            },
            {
                "cue_ref": reset_id,
                "profile": "reset_basic",
                "properties": {
                    "cueTargetID": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "cueTargetNumber": "RST1",
                    "patchTargetID": "patch-1",
                    "audioMapTargetID": "map-1",
                    "targetMode": 1,
                },
            },
            {
                "cue_ref": devamp_id,
                "profile": "devamp_basic",
                "properties": {
                    "cueTargetID": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "cueTargetNumber": "DV1",
                    "tempCueTargetID": "",
                    "tempCueTargetNumber": "DV2",
                    "targetMode": 0,
                    "devampType": 2,
                    "startNextCueWhenSliceEnds": True,
                    "stopTargetWhenSliceEnds": False,
                },
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 3
    assert [item["profile"] for item in result["results"]] == ["target_basic", "reset_basic", "devamp_basic"]
    assert all(item["executed_operations"] == [] for item in result["results"])

    planned_by_item = [
        {
            operation["property"]: operation
            for operation in item["planned_operations"]
            if operation["operation"] == "set_property"
        }
        for item in result["results"]
    ]
    assert set(planned_by_item[0]) == {
        "cueTargetID",
        "cueTargetNumber",
        "tempCueTargetID",
        "tempCueTargetNumber",
        "targetMode",
    }
    assert set(planned_by_item[1]) == {"cueTargetID", "cueTargetNumber", "patchTargetID", "audioMapTargetID", "targetMode"}
    assert set(planned_by_item[2]) == {
        "cueTargetID",
        "cueTargetNumber",
        "tempCueTargetID",
        "tempCueTargetNumber",
        "targetMode",
        "devampType",
        "startNextCueWhenSliceEnds",
        "stopTargetWhenSliceEnds",
    }
    assert all(operation["real_write_enabled"] is False for item in planned_by_item for operation in item.values())
    assert planned_by_item[0]["tempCueTargetID"]["args"] == ["none"]
    assert planned_by_item[2]["tempCueTargetID"]["args"] == [""]


def test_update_cues_transport_target_validators_fail_without_plan() -> None:
    start_id = "11111111-1111-4111-8111-111111111111"
    devamp_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            start_id: {"type": "Start", "targetMode": 0},
            devamp_id: {"type": "Devamp", "devampType": 1, "startNextCueWhenSliceEnds": False},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": start_id, "profile": "target_basic", "properties": {"targetMode": 2}},
            {"cue_ref": start_id, "profile": "target_basic", "properties": {"cueTargetNumber": ""}},
            {"cue_ref": devamp_id, "profile": "devamp_basic", "properties": {"devampType": 3}},
            {"cue_ref": devamp_id, "profile": "devamp_basic", "properties": {"startNextCueWhenSliceEnds": "banana"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 4
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert result["results"][0]["errors"]["validation"] == "targetMode must be 0 for cue target or 1 for patch target"
    assert result["results"][1]["errors"]["validation"] == "cueTargetNumber must be a non-empty cue target number"
    assert result["results"][2]["errors"]["validation"] == "devampType must be 1 for current slice or 2 for looping cue"
    assert result["results"][3]["errors"]["validation"] == "startNextCueWhenSliceEnds must be a boolean"
    assert client.requests == []


def test_update_cues_target_profile_type_mismatch_fails_cleanly_without_plan() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={memo_id: {"type": "Memo", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": memo_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "target_basic update profile requires cue type" in result["results"][0]["errors"]["profile"]
    assert result["results"][0]["planned_operations"] == []


def test_update_cues_group_basic_dry_run_plans_documented_group_list_cart_paths() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    list_id = "22222222-2222-4222-8222-222222222222"
    cart_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            group_id: {"type": "Group", "mode": 3, "playlist/doLoop": False},
            list_id: {"type": "Cue List", "playbackPosition": "1", "playbackPositionID": "child-old"},
            cart_id: {"type": "Cue Cart", "mode": 5},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": group_id,
                "profile": "group_basic",
                "properties": {
                    "playlist/currentCue": "A1",
                    "playlist/currentCueID": "child-new",
                    "playlistLoop": False,
                    "playlistShuffle": False,
                    "playlistCrossfade": False,
                    "playlistCrossfadeDuration": 1.25,
                },
            },
            {
                "cue_ref": list_id,
                "profile": "group_basic",
                "properties": {
                    "playhead": "next",
                    "playheadID": "none",
                    "playbackPosition": "previous",
                    "playbackPositionID": "child-id",
                },
                "operations": [{"property": "playhead/next"}, {"property": "playbackPosition/previousSequence"}],
            },
            {
                "cue_ref": cart_id,
                "profile": "group_basic",
                "operations": [{"property": "moveCartCue", "args": {"child": "child-id", "row": 2, "column": 3}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    planned_by_item = [
        {
            operation["property"]: operation
            for operation in item["planned_operations"]
            if operation["operation"] == "set_property"
        }
        for item in result["results"]
    ]
    assert planned_by_item[0]["playlist/currentCueID"]["address"] == f"/workspace/ws-1/cue_id/{group_id}/playlist/currentCueID"
    assert planned_by_item[0]["playlist/currentCueID"]["planned_only_reason"] == "playlist_navigation_needs_dedicated_validation"
    assert planned_by_item[0]["playlistLoop"]["address"] == f"/workspace/ws-1/cue_id/{group_id}/playlistLoop"
    assert planned_by_item[0]["playlistLoop"]["planned_only_reason"] == "deprecated_use_playlist_doLoop"
    assert planned_by_item[1]["playhead"]["address"] == f"/workspace/ws-1/cue_id/{list_id}/playhead"
    assert planned_by_item[1]["playhead/next"]["address"] == f"/workspace/ws-1/cue_id/{list_id}/playhead/next"
    assert planned_by_item[1]["playbackPosition/previousSequence"]["address"] == (
        f"/workspace/ws-1/cue_id/{list_id}/playbackPosition/previousSequence"
    )
    assert planned_by_item[2]["moveCartCue"]["address"] == f"/workspace/ws-1/cue_id/{cart_id}/moveCartCue/child-id"
    assert planned_by_item[2]["moveCartCue"]["args"] == [2, 3]
    for item in result["results"]:
        assert item["executed_operations"] == []


def test_update_cues_group_basic_invalid_values_have_no_plan() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    list_id = "22222222-2222-4222-8222-222222222222"
    cart_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            group_id: {"type": "Group", "mode": 3},
            list_id: {"type": "Cue List", "playbackPosition": "1"},
            cart_id: {"type": "Cue Cart", "mode": 5},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 0}},
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": "yes"}},
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": -0.1}},
            {"cue_ref": list_id, "profile": "group_basic", "properties": {"playhead": ""}},
            {
                "cue_ref": cart_id,
                "profile": "group_basic",
                "operations": [{"property": "moveCartCue", "args": {"child": "child", "row": -1, "column": 0}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["failed_count"] == 5
    assert result["results"][0]["errors"]["validation"] == "mode must be 1, 2, 3, 4, or 6"
    assert result["results"][1]["errors"]["validation"] == "playlist/doLoop must be a boolean"
    assert result["results"][2]["errors"]["validation"] == "playlist/crossfade/duration must be a non-negative number"
    assert result["results"][3]["errors"]["validation"] == "playhead must be a non-empty string"
    assert result["results"][4]["errors"]["validation"] == "moveCartCue.row must be a non-negative integer"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_group_basic_real_blocks_planned_only_before_setters() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={group_id: {"type": "Group", "playbackPosition": "1"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playbackPosition": "next"}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["playbackPosition"]
    assert client.requests == []


def test_update_cues_group_basic_real_blocks_playlist_setters_without_playlist_mode() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=3)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": 2.5}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {
        "playlist/crossfade/duration": "Playlist setters require the Group cue to already be in Playlist mode (mode 6)."
    }
    assert all(not request[0].endswith("/playlist/crossfade/duration") for request in client.requests)


def test_update_cues_group_basic_real_allows_playlist_setters_for_playlist_mode() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": 2.5}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/crossfade/duration"]["confirm_token"]
    result = reader.update_cues(workspace_id, [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["playlist/crossfade/duration"] == 2.5


def _safe_group_fixture(
    group_id: str,
    child_id: str,
    *,
    mode: int = 3,
    duration: float = 10.0,
) -> tuple[dict[str, dict[str, Any]], dict[str, list[str]]]:
    inactive_health = {
        "armed": True,
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
        "isLoaded": False,
        "isOverridden": False,
        "isActionRunning": False,
    }
    return (
        {
            group_id: {
                "type": "Group",
                "mode": mode,
                "isChildAuditioning": False,
                "playlist/doLoop": False,
                "playlist/doShuffle": False,
                "playlist/doCrossfade": False,
                "playlist/crossfade/duration": 3.0,
                **inactive_health,
            },
            child_id: {
                "type": "Audio",
                "continueMode": 0,
                "preWait": 0.0,
                "postWait": 0.0,
                "duration": duration,
                **inactive_health,
            },
        },
        {group_id: [child_id]},
    )


def test_group_playlist_large_child_snapshot_preserves_all_ordered_children() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    first_child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, first_child_id, mode=6, duration=1.0)
    child_ids = [first_child_id]
    for index in range(1, 200):
        child_id = f"00000000-2222-4222-8222-{index:012x}"
        cues[child_id] = dict(cues[first_child_id], uniqueID=child_id)
        child_ids.append(child_id)
    children[group_id] = child_ids

    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}

    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["playlist/doLoop"]
    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [setter["confirm_token"]]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert [child["uniqueID"] for child in item["group_child_readback"]["ordered_children"]] == child_ids
    assert len(item["group_child_readback"]["ordered_children"]) == 200
    assert sum(address.endswith("/playlist/doLoop") for address, _, _ in client.requests) == 1


def test_group_warning_but_not_broken_fails_closed_before_setter() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    cues[group_id]["isWarning"] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["mode"] == "Group real writes require fresh isWarning=false."
    assert result["results"][0]["executed_operations"] == []
    assert all(not address.endswith("/mode") for address, _, _ in client.requests)


def test_group_playlist_crossfade_accepts_exact_shortest_child_duration() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6, duration=3.0)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doCrossfade": True}}

    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doCrossfade"]["confirm_token"]
    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["playlist/doCrossfade"] is True
    assert sum(address.endswith("/playlist/doCrossfade") for address, _, _ in client.requests) == 1


def test_group_playlist_crossfade_accepts_zero_duration_candidate() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6, duration=3.0)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": group_id,
        "profile": "group_basic",
        "properties": {"playlist/crossfade/duration": 0.0},
    }

    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/crossfade/duration"]["confirm_token"]
    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["playlist/crossfade/duration"] == 0.0
    assert sum(address.endswith("/playlist/crossfade/duration") for address, _, _ in client.requests) == 1


def test_group_token_from_previous_process_fails_signature_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    monkeypatch.setattr(group_helpers, "_GROUP_TOKEN_SECRET", b"simulated-new-process-secret")
    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["mode"] == "groupMode confirm_token signature is invalid."
    assert result["results"][0]["executed_operations"] == []
    assert all(not address.endswith("/mode") for address, _, _ in client.requests)


def test_group_mode_dry_run_emits_dedicated_expiring_confirm_token() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["mode"]
    assert result["status"] == "dry_run"
    assert setter["requires_confirm_token"] is True
    assert setter["real_write_possible"] is True
    assert setter["confirm_token"].startswith("confirm:groupMode:v1:")
    assert setter["address"] == f"/workspace/{workspace_id}/cue_id/{group_id}/mode"


@pytest.mark.parametrize("requested_mode", [1, 2, 3, 4, 6])
def test_group_mode_documented_writable_values_are_token_candidates(requested_mode: int) -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    baseline_mode = 2 if requested_mode == 3 else 3
    cues, children = _safe_group_fixture(group_id, child_id, mode=baseline_mode)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": requested_mode}}],
        dry_run=True,
    )

    token = planned_setters(result["results"][0])["mode"]["confirm_token"]
    assert token.startswith("confirm:groupMode:v1:")


def test_group_mode_real_write_requires_reviewed_token() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "confirm_token" in result["results"][0]["errors"]["mode"]
    assert all(not address.endswith("/mode") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("workspace_id", "cue_ref", "expected"),
    [
        ("ws-1", "11111111-1111-4111-8111-111111111111", "workspace UUID"),
        ("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa", "50", "cue UUID"),
    ],
)
def test_group_mode_requires_exact_workspace_and_cue_uuids(
    workspace_id: str,
    cue_ref: str,
    expected: str,
) -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        cue_numbers={"50": group_id},
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": cue_ref, "profile": "group_basic", "properties": {"mode": 1}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert expected in result["results"][0]["errors"]["mode"]


def test_group_mode_token_binds_fresh_ordered_child_fingerprint() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]
    client.cues[child_id]["continueMode"] = 2

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "stale" in result["results"][0]["errors"]["mode"].lower()
    assert all(not address.endswith("/mode") for address, _, _ in client.requests)


def test_group_mode_fails_closed_for_active_or_unhealthy_group() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    cues[group_id]["isRunning"] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "isRunning=false" in result["results"][0]["errors"]["mode"]
    assert result["results"][0]["planned_operations"] == []


def test_group_playlist_dry_run_fails_closed_when_mode_is_not_fresh_playlist() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=3)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert "mode 6" in result["results"][0]["errors"]["playlist/doLoop"]


def test_group_mode_reviewed_token_writes_and_reads_back() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["mode"] == 1
    assert result["results"][0]["side_effects"] == []
    assert result["results"][0]["operations"][0]["rollback_plan"] == {
        "status": "new_dry_run_and_fresh_token_required",
        "property": "mode",
        "value": 3,
        "automatic_restoration": False,
    }


def test_group_mode_immediate_replay_is_rejected_as_consumed_before_noop_baseline() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    first = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    replay = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert first["status"] == "updated"
    assert replay["status"] == "preflight_failed"
    assert replay["results"][0]["errors"] == {
        "mode": "confirmation_already_consumed: confirm_token has already been used."
    }
    assert replay["results"][0]["executed_operations"] == []
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1


def test_group_mode_timeout_with_matching_fresh_readback_is_confirmed() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", update_debug=True),
        cues=cues,
        children_by_parent=children,
        timeout_set_property=(group_id, "mode"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][0]["status"] == "updated_with_confirmed_timeouts"
    assert result["timeout_confirmed_count"] == 1
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1
    debug = result["results"][0]["debug"]
    assert debug["setter_send_count"] == 1
    assert debug["setter_elapsed_seconds"]["mode"] >= 0
    assert debug["confirmation_reason"] == "fresh_readback_matched"
    modeled = UpdateCuesResult.model_validate(result)
    assert modeled.results[0].executed_operations[0]["property"] == "mode"


def test_group_mode_ignored_setter_reports_structured_verification_failure_without_retry() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        ignore_set_property=(group_id, "mode"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 6}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    item = result["results"][0]

    assert result["status"] == "verification_failed"
    assert item["status"] == "verification_failed"
    assert item["after"]["mode"] == 3
    assert len(item["executed_operations"]) == 1
    assert item["executed_operations"][0]["address"].endswith("/mode")
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1
    modeled = UpdateCuesResult.model_validate(result)
    assert modeled.results[0].status == "verification_failed"

    replay = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    assert replay["status"] == "preflight_failed"
    assert "consumed" in replay["results"][0]["errors"]["mode"]
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1


def test_group_mode_token_is_rejected_after_rollback_restores_baseline() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    forward_update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    forward_plan = reader.update_cues(workspace_id, [forward_update], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["mode"]["confirm_token"]
    forward = reader.update_cues(
        workspace_id,
        [{**forward_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**forward_update, "properties": {"mode": 3}}
    rollback_plan = reader.update_cues(workspace_id, [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["mode"]["confirm_token"]
    rollback = reader.update_cues(
        workspace_id,
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )
    setter_count_before_replay = sum(address.endswith("/mode") for address, _, _ in client.requests)

    replay = reader.update_cues(
        workspace_id,
        [{**forward_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert rollback["status"] == "updated"
    assert replay["status"] == "preflight_failed"
    assert "consumed" in replay["results"][0]["errors"]["mode"]
    assert replay["results"][0]["executed_operations"] == []
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == setter_count_before_replay


def test_group_mode_same_token_concurrent_calls_send_one_setter(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]
    barrier = threading.Barrier(2)
    consume = write_operations._consume_group_token

    def synchronized_consume(item: dict[str, Any]) -> dict[str, str]:
        barrier.wait(timeout=2)
        return consume(item)

    monkeypatch.setattr(write_operations, "_consume_group_token", synchronized_consume)

    def execute() -> dict[str, Any]:
        return reader.update_cues(
            workspace_id,
            [{**update, "confirm_gates": [token]}],
            dry_run=False,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: execute(), range(2)))

    assert sum(result["status"] == "updated" for result in results) == 1
    assert sum(result["status"] == "preflight_failed" for result in results) == 1
    rejected = next(result for result in results if result["status"] == "preflight_failed")
    assert rejected["results"][0]["errors"] == {
        "mode": "confirmation_already_consumed: confirm_token has already been used."
    }
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1


@pytest.mark.parametrize("timeout_without_apply", [False, True])
def test_consumed_group_token_cannot_retry_after_timeout(
    timeout_without_apply: bool,
) -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        timeout_set_property=(group_id, "mode"),
        timeout_without_apply=timeout_without_apply,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    first = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[group_id]["mode"] = 3
    replay = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert first["status"] == (
        "partial_failed" if timeout_without_apply else "updated_with_confirmed_timeouts"
    )
    assert replay["status"] == "preflight_failed"
    assert "consumed" in replay["results"][0]["errors"]["mode"]
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1


def test_consumed_group_token_cannot_retry_after_qlab_error() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        error_after_apply_properties={(group_id, "mode")},
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    first = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[group_id]["mode"] = 3
    replay = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert first["status"] == "updated_with_confirmed_timeouts"
    assert "setter_error_but_readback_matched" in first["results"][0]["warnings"]
    assert replay["status"] == "preflight_failed"
    assert "consumed" in replay["results"][0]["errors"]["mode"]
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1
    modeled = UpdateCuesResult.model_validate(first)
    assert modeled.results[0].executed_operations[0]["property"] == "mode"


def test_group_mode_qlab_error_before_apply_reports_structured_partial_failure() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        fail_set_property=(group_id, "mode"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 6}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    item = result["results"][0]

    assert result["status"] == "partial_failed"
    assert item["after"]["mode"] == 3
    assert len(item["executed_operations"]) == 1
    assert item["errors"]["mode"]
    assert sum(address.endswith("/mode") for address, _, _ in client.requests) == 1
    modeled = UpdateCuesResult.model_validate(result)
    assert modeled.status == "partial_failed"


def test_group_continue_mode_real_change_and_rollback_use_integer_setter_once() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    cues[group_id]["continueMode"] = 0
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    forward_update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"continueMode": 1}}
    forward_plan = reader.update_cues(workspace_id, [forward_update], dry_run=True)
    forward = reader.update_cues(workspace_id, [forward_update], dry_run=False)
    rollback_update = {**forward_update, "properties": {"continueMode": 0}}
    reader.update_cues(workspace_id, [rollback_update], dry_run=True)
    rollback = reader.update_cues(workspace_id, [rollback_update], dry_run=False)

    setters = [(address, args) for address, args, _ in client.requests if address.endswith("/continueMode")]
    assert "confirm_token" not in planned_setters(forward_plan["results"][0])["continueMode"]
    assert forward["status"] == "updated"
    assert forward["results"][0]["after"]["continueMode"] == 1
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["continueMode"] == 0
    assert setters == [
        (f"/workspace/{workspace_id}/cue_id/{group_id}/continueMode", (1,)),
        (f"/workspace/{workspace_id}/cue_id/{group_id}/continueMode", (0,)),
    ]


def test_group_continue_mode_timeout_is_confirmed_without_retry() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    cues[group_id]["continueMode"] = 0
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        timeout_set_property=(group_id, "continueMode"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"continueMode": 1}}

    result = reader.update_cues(workspace_id, [update], dry_run=False)

    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][0]["after"]["continueMode"] == 1
    assert sum(address.endswith("/continueMode") for address, _, _ in client.requests) == 1


def test_group_continue_mode_mismatch_is_verification_failed() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    cues[group_id]["continueMode"] = 0
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        ignore_set_property=(group_id, "continueMode"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"continueMode": 1}}],
        dry_run=False,
    )

    assert result["status"] == "verification_failed"
    assert result["results"][0]["after"]["continueMode"] == 0
    assert sum(address.endswith("/continueMode") for address, _, _ in client.requests) == 1


def test_group_mode_rollback_requires_new_dry_run_token() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    forward_update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    forward_plan = reader.update_cues(workspace_id, [forward_update], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["mode"]["confirm_token"]
    forward = reader.update_cues(
        workspace_id,
        [{**forward_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**forward_update, "properties": {"mode": 3}}
    stale = reader.update_cues(
        workspace_id,
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues(workspace_id, [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["mode"]["confirm_token"]
    rollback = reader.update_cues(
        workspace_id,
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert stale["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["mode"] == 3


def test_group_mode_reports_child_side_effects_without_hidden_restoration() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        group_child_outcomes={(group_id, "mode", 6): {child_id: {"continueMode": 1, "postWait": 10.0}}},
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 6}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert "group_write_changed_child_state" in item["warnings"]
    assert {effect["field"] for effect in item["side_effects"]} == {"continueMode", "postWait"}
    rollback = item["operations"][0]["rollback_plan"]
    assert rollback["automatic_restoration"] is False
    assert rollback["status"] == "new_dry_run_and_fresh_token_required"
    modeled = UpdateCuesResult.model_validate(result).model_dump()
    assert modeled["results"][0]["side_effects"] == item["side_effects"]
    assert modeled["results"][0]["group_child_readback"] == item["group_child_readback"]


def test_group_mode_reports_unrequested_playlist_scalar_side_effect() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        property_outcomes={(group_id, "mode", 1): {"playlist/doLoop": True}},
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["results"][0]["side_effects"] == [
        {
            "scope": "group",
            "cue_id": group_id,
            "field": "playlist/doLoop",
            "before": False,
            "after": True,
        }
    ]


def test_group_playlist_reviewed_token_writes_in_verified_playlist_mode() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["playlist/doLoop"]
    assert setter["confirm_token"].startswith("confirm:groupPlaylist:v1:")

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [setter["confirm_token"]]}],
        dry_run=False,
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["playlist/doLoop"] is True


def test_group_playlist_timeout_is_confirmed_and_sends_one_setter() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        timeout_set_property=(group_id, "playlist/doLoop"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doLoop"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][0]["after"]["playlist/doLoop"] is True
    assert sum(address.endswith("/playlist/doLoop") for address, _, _ in client.requests) == 1


def test_group_playlist_ignored_setter_reports_structured_verification_failure_without_retry() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        ignore_set_property=(group_id, "playlist/doLoop"),
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doLoop"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    item = result["results"][0]

    assert result["status"] == "verification_failed"
    assert item["status"] == "verification_failed"
    assert item["after"]["playlist/doLoop"] is False
    assert len(item["executed_operations"]) == 1
    assert item["executed_operations"][0]["address"].endswith("/playlist/doLoop")
    assert sum(address.endswith("/playlist/doLoop") for address, _, _ in client.requests) == 1
    modeled = UpdateCuesResult.model_validate(result)
    assert modeled.results[0].status == "verification_failed"

    replay = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    assert replay["status"] == "preflight_failed"
    assert "consumed" in replay["results"][0]["errors"]["playlist/doLoop"]
    assert sum(address.endswith("/playlist/doLoop") for address, _, _ in client.requests) == 1


def test_group_playlist_token_binds_dependent_playlist_state() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": group_id,
        "profile": "group_basic",
        "properties": {"playlist/doCrossfade": True},
    }
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doCrossfade"]["confirm_token"]
    client.cues[group_id]["playlist/crossfade/duration"] = 2.0

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "stale_group_baseline" in result["results"][0]["errors"]["playlist/doCrossfade"]


def test_group_mode_confirm_token_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    monkeypatch.setattr(group_helpers.time, "time", lambda: 1000)
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]
    monkeypatch.setattr(group_helpers.time, "time", lambda: 1301)

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "expired" in result["results"][0]["errors"]["mode"]
    assert all(not address.endswith("/mode") for address, _, _ in client.requests)


def test_group_confirm_tokens_reject_changed_value_and_wrong_family() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    mode_update = {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 1}}
    plan = reader.update_cues(workspace_id, [mode_update], dry_run=True)
    token = planned_setters(plan["results"][0])["mode"]["confirm_token"]

    changed = reader.update_cues(
        workspace_id,
        [{**mode_update, "properties": {"mode": 2}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[group_id]["mode"] = 6
    wrong_family = reader.update_cues(
        workspace_id,
        [
            {
                "cue_ref": group_id,
                "profile": "group_basic",
                "properties": {"playlist/doLoop": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert "stale_group_baseline" in changed["results"][0]["errors"]["mode"]
    assert "unsupported family" in wrong_family["results"][0]["errors"]["playlist/doLoop"]


def test_group_playlist_token_rejects_malformed_tampered_and_wrong_bindings() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    other_group_id = "33333333-3333-4333-8333-333333333333"
    other_child_id = "44444444-4444-4444-8444-444444444444"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6)
    other_cues, other_children = _safe_group_fixture(other_group_id, other_child_id, mode=6)
    cues.update(other_cues)
    children.update(other_children)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": group_id,
        "profile": "group_basic",
        "properties": {"playlist/doLoop": True},
    }
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doLoop"]["confirm_token"]
    tampered = f"{token[:-1]}{'0' if token[-1] != '0' else '1'}"

    malformed = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": ["malformed"]}],
        dry_run=False,
    )
    invalid_signature = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [tampered]}],
        dry_run=False,
    )
    wrong_group = reader.update_cues(
        workspace_id,
        [{**update, "cue_ref": other_group_id, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_property = reader.update_cues(
        workspace_id,
        [
            {
                **update,
                "properties": {"playlist/doShuffle": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert "malformed" in malformed["results"][0]["errors"]["playlist/doLoop"]
    assert "signature is invalid" in invalid_signature["results"][0]["errors"]["playlist/doLoop"]
    assert "stale_group_baseline" in wrong_group["results"][0]["errors"]["playlist/doLoop"]
    assert "stale_group_baseline" in wrong_property["results"][0]["errors"]["playlist/doShuffle"]
    assert sum(
        address.endswith(("/playlist/doLoop", "/playlist/doShuffle"))
        for address, _, _ in client.requests
    ) == 0


def test_group_playlist_loop_requires_readable_nonzero_child_duration() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6, duration=0.0)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": True}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "non-zero duration" in result["results"][0]["errors"]["playlist/doLoop"]


def test_group_playlist_crossfade_rejects_duration_longer_than_child() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    child_id = "22222222-2222-4222-8222-222222222222"
    cues, children = _safe_group_fixture(group_id, child_id, mode=6, duration=2.0)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues=cues,
        children_by_parent=children,
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        workspace_id,
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doCrossfade": True}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "exceeds" in result["results"][0]["errors"]["playlist/doCrossfade"]


def test_group_playlist_shuffle_reports_order_side_effect() -> None:
    workspace_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
    group_id = "11111111-1111-4111-8111-111111111111"
    first_id = "22222222-2222-4222-8222-222222222222"
    second_id = "33333333-3333-4333-8333-333333333333"
    cues, children = _safe_group_fixture(group_id, first_id, mode=6)
    cues[second_id] = dict(cues[first_id], uniqueID=second_id)
    children[group_id].append(second_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        children_by_parent=children,
        group_order_outcomes={(group_id, "playlist/doShuffle", True): [second_id, first_id]},
        workspace_id=workspace_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": group_id,
        "profile": "group_basic",
        "properties": {"playlist/doShuffle": True},
    }
    plan = reader.update_cues(workspace_id, [update], dry_run=True)
    token = planned_setters(plan["results"][0])["playlist/doShuffle"]["confirm_token"]

    result = reader.update_cues(
        workspace_id,
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    effects = result["results"][0]["side_effects"]
    assert effects == [
        {
            "scope": "children",
            "field": "order",
            "before": [first_id, second_id],
            "after": [second_id, first_id],
        }
    ]


def test_update_cues_real_blocks_duration_when_cue_duration_is_not_editable() -> None:
    wait_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={wait_id: {"type": "Wait", "duration": 0, "allowsEditingDuration": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": 3}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"duration": "duration requires a cue with editable duration."}
    assert all(not request[0].endswith("/duration") for request in client.requests)


def test_update_cues_real_blocks_duration_when_editability_readback_is_missing() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Wait", "duration": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "wait_basic", "properties": {"duration": 1.0}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["duration"] == "duration requires a cue with editable duration."
    assert all(not request[0].endswith("/duration") for request in client.requests)


def test_update_cues_real_allows_duration_when_cue_duration_is_editable() -> None:
    audio_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={audio_id: {"type": "Audio", "duration": 0, "allowsEditingDuration": True}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": audio_id, "profile": "audio_basic", "properties": {"duration": 3}}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["duration"] == 3


def test_update_cues_group_basic_profile_mismatch_fails_cleanly() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "mode": 3}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "group_basic", "properties": {"mode": 3}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["errors"]["profile"] == "group_basic update profile requires cue type: Group, Cue List, Cue Cart"


def test_update_cues_fade_basic_dry_run_plans_documented_fade_fields() -> None:
    fade_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            fade_id: {
                "type": "Fade",
                "targetMode": 0,
                "levelsMode": 0,
                "geoMode": 0,
                "fadeType": 1,
                "pathHeight": 1,
                "pathWidth": 1,
                "rotationType": 0,
                "stopTargetWhenDone": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "properties": {
                    "targetMode": 1,
                    "mode": 0,
                    "fadeType": 2,
                    "pathHeight": 1.5,
                    "pathWidth": 2.5,
                    "audioMapTargetID": "map-1",
                    "patchTargetID": "patch-1",
                },
                "operations": [
                    {"property": "doObjectLevel", "args": {"row": 1, "object": "object-a", "value": True}},
                    {"property": "doObjectIDLevel", "args": {"row": 1, "objectID": "object-id", "value": True}},
                    {"property": "setGeometryFromTarget", "args": {}},
                    {"property": "setLevelsFromTarget", "args": {}},
                    {"property": "willFade", "args": {"row": 1, "column": 1, "value": False}},
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []
    assert "updateq_plan" not in result["results"][0]
    setters = [op for op in result["results"][0]["planned_operations"] if op["operation"] == "set_property"]
    setter_by_property = {setter["property"]: setter for setter in setters}
    assert setter_by_property["mode"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/levelsMode"
    assert setter_by_property["doObjectLevel"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/doObjectLevel/1/object-a"
    assert setter_by_property["doObjectIDLevel"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/doObjectIDLevel/1/object-id"
    assert setter_by_property["setGeometryFromTarget"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/setGeometryFromTarget"
    assert setter_by_property["setLevelsFromTarget"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/setLevelsFromTarget"
    assert setter_by_property["willFade"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/willFade/1/1"
    assert setter_by_property["setGeometryFromTarget"]["args"] == []
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert all(setter["planned_only_reason"] for setter in setters)
    assert len(client.requests) == 1
    address, args, workspace_id = client.requests[0]
    assert address == f"/workspace/ws-1/cue_id/{fade_id}/valuesForKeys"
    assert workspace_id == "ws-1"
    for key in ("geoMode", "pathHeight", "pathWidth", "fadeType", "patchTargetID"):
        assert f'"{key}"' in args[0]


def test_update_cues_fade_basic_validators_fail_without_plan() -> None:
    fade_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={fade_id: {"type": "Fade", "targetMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"targetMode": 99}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"levelsMode": 2}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"geoMode": -1}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"fadeType": 3}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"rotationType": 4}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"pathHeight": 0}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"pathWidth": -1}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"doOpacity": "banana"}},
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doLevel", "args": {"row": 25, "column": 1, "value": True}}],
            },
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doLevel", "args": {"row": 1, "column": 129, "value": True}}],
            },
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doObjectLevel", "args": {"row": 1, "object": "", "value": True}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 11
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert result["results"][0]["errors"]["validation"] == "targetMode must be 0 for cue target or 1 for patch target"
    assert result["results"][1]["errors"]["validation"] == "levelsMode must be 0 or 1"
    assert result["results"][2]["errors"]["validation"] == "geoMode must be 0 or 1"
    assert result["results"][3]["errors"]["validation"] == "fadeType must be 1 for 1D Curve or 2 for 2D Path"
    assert result["results"][4]["errors"]["validation"] == "rotationType must be an integer from 0 to 3"
    assert result["results"][5]["errors"]["validation"] == "pathHeight must be a positive number"
    assert result["results"][6]["errors"]["validation"] == "pathWidth must be a positive number"
    assert result["results"][7]["errors"]["validation"] == "doOpacity must be a boolean"
    assert result["results"][8]["errors"]["validation"] == "doLevel.row must be an integer from 0 to 24"
    assert result["results"][9]["errors"]["validation"] == (
        "doLevel.column must be an integer from 0 to 128 or a cue output name"
    )
    assert result["results"][10]["errors"]["validation"] == "doObjectLevel.object must be a non-empty object name or ID"
    assert client.requests == []


FADE_WORKSPACE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def _fade_plan(
    reader: QLabReader,
    source_id: str,
    property_name: str,
    value: Any,
    *,
    mode: str = "saved",
) -> tuple[dict[str, Any], str | None]:
    operation: dict[str, Any] = {"property": property_name, "args": {"value": value}}
    if mode != "saved":
        operation["mode"] = mode
    result = reader.update_cues(
        FADE_WORKSPACE_ID,
        [{"cue_ref": source_id, "profile": "fade_basic", "operations": [operation]}],
        dry_run=True,
    )
    setters = planned_setters(result["results"][0])
    token = setters.get(property_name, {}).get("confirm_token")
    return result, token


def _fade_write(
    reader: QLabReader,
    source_id: str,
    property_name: str,
    value: Any,
    token: str,
) -> dict[str, Any]:
    return reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {
                "cue_ref": source_id,
                "profile": "fade_basic",
                "properties": {property_name: value},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )


def fade_audio_fixture_cues(
    source_id: str,
    target_id: str,
    *,
    target_type: str = "Video",
    broken: bool = False,
    levels_mode: int = 0,
    do_level: bool = False,
) -> dict[str, dict[str, Any]]:
    cues = fade_fixture_cues(
        source_id,
        target_id,
        target_type=target_type,
        broken=broken,
        do_opacity=not broken,
    )
    matrix = [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]]
    cues[source_id].update(
        {
            "levelsMode": levels_mode,
            "numChannelsIn": 2,
            "levels": [list(row) for row in matrix],
            "sliderLevels": [0.0, 0.0],
            "doLevel": [[do_level, False], [False, False], [False, False]],
            "inputChannelName/1": "L",
            "inputChannelName/2": "R",
            "gang/1/0": "",
            "stopTargetWhenDone": False,
        }
    )
    cues[target_id].update(
        {
            "numChannelsIn": 2,
            "audioTrackFormats": [{"channels": 2, "format": "AAC"}],
            "levels": [list(row) for row in matrix],
            "sliderLevels": [0.0, 0.0],
        }
    )
    return cues


def _fade_operation_plan(
    reader: QLabReader,
    source_id: str,
    property_name: str,
    args: dict[str, Any],
    *,
    mode: str = "saved",
) -> tuple[dict[str, Any], str | None]:
    operation: dict[str, Any] = {"property": property_name, "args": args}
    if mode != "saved":
        operation["mode"] = mode
    result = reader.update_cues(
        FADE_WORKSPACE_ID,
        [{"cue_ref": source_id, "profile": "fade_basic", "operations": [operation]}],
        dry_run=True,
    )
    token = planned_setters(result["results"][0]).get(property_name, {}).get("confirm_token")
    return result, token


def _fade_operation_write(
    reader: QLabReader,
    source_id: str,
    property_name: str,
    args: dict[str, Any],
    token: str,
) -> dict[str, Any]:
    return reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {
                "cue_ref": source_id,
                "profile": "fade_basic",
                "operations": [{"property": property_name, "args": args}],
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )


def test_qlab_edit_cues_fade_basic_properties_shape_emits_fade_basic_token() -> None:
    """Mirror the MCP tool's model_dump shape, not the lower-level operations form."""
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"

    class SingleTargetReadClient(BatchFakeWriteClient):
        target_reads = 0

        def request(
            self,
            address: str,
            *args: Any,
            workspace_id: str | None = None,
            reply_timeout: float | None = None,
        ) -> Any:
            if address == f"/workspace/{FADE_WORKSPACE_ID}/cue_id/{target_id}/valuesForKeys":
                self.target_reads += 1
                if self.target_reads > 1:
                    raise OscTimeoutError("duplicate Fade target preflight read")
            return super().request(
                address,
                *args,
                workspace_id=workspace_id,
                reply_timeout=reply_timeout,
            )

    client = SingleTargetReadClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = CueUpdateInput(
        cue_ref=source_id,
        profile="fade_basic",
        properties={"name": "Renamed Fade"},
    ).model_dump()

    result = reader.edit_cues(FADE_WORKSPACE_ID, [update], dry_run=True)
    planned = planned_setters(result["results"][0])

    assert result["status"] == "dry_run"
    assert result["results"][0]["executed_operations"] == []
    assert planned["name"]["confirm_token"].startswith("confirm:fadeBasic:v1:")
    assert client.target_reads == 1


@pytest.mark.parametrize(
    ("property_name", "requested"),
    [
        ("name", "Renamed"),
        ("number", "2"),
        ("notes", "note"),
        ("armed", False),
        ("flagged", True),
        ("colorName", "blue"),
        ("preWait", 1),
        ("postWait", 1),
        ("duration", 1),
        ("tempDuration", 1),
        ("continueMode", "auto_continue"),
        ("skipIfDisarmed", True),
        ("autoLoad", True),
        ("secondColorName", "red"),
        ("useSecondColor", True),
    ],
)
def test_fade_phase1_all_shared_basics_emit_only_fade_basic_token(
    property_name: str, requested: Any
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, property_name, requested)

    assert plan["status"] == "dry_run"
    assert token and token.startswith("confirm:fadeBasic:v1:")
    assert plan["results"][0]["executed_operations"] == []
    expected = planned_setters(plan["results"][0])[property_name]["args"][0]
    written = _fade_write(reader, source_id, property_name, requested, token)
    assert written["status"] == "updated", written
    assert written["results"][0]["after"][property_name] == expected


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested", "prefix", "do_opacity", "do_scale"),
    [
        ("name", "Fade fixture", "Renamed Fade", "confirm:fadeBasic:v1:", True, False),
        ("geoMode", 0, 1, "confirm:fadeGeometry:v1:", True, False),
        ("opacity", 0.5, 0.75, "confirm:fadeGeometry:v1:", True, False),
        ("doOpacity", False, True, "confirm:fadeGeometry:v1:", False, True),
    ],
)
def test_fade_phase1_property_writes_and_rolls_back_with_fresh_tokens(
    property_name: str,
    baseline: Any,
    requested: Any,
    prefix: str,
    do_opacity: bool,
    do_scale: bool,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id, do_opacity=do_opacity, do_scale=do_scale)
    cues[source_id][property_name] = baseline
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, property_name, requested)
    assert plan["status"] == "dry_run"
    assert token and token.startswith(prefix)
    assert plan["results"][0]["executed_operations"] == []
    written = _fade_write(reader, source_id, property_name, requested, token)
    assert written["status"] == "updated", written
    assert written["results"][0]["after"][property_name] == requested

    rollback_plan, rollback_token = _fade_plan(reader, source_id, property_name, baseline)
    assert rollback_plan["status"] == "dry_run"
    assert rollback_token and rollback_token.startswith(prefix)
    assert rollback_token != token
    rolled_back = _fade_write(reader, source_id, property_name, baseline, rollback_token)
    assert rolled_back["status"] == "updated"
    assert rolled_back["results"][0]["after"][property_name] == baseline
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/{FADE_WORKSPACE_ID}/cue_id/{source_id}/{property_name}"
    ) == 2


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested", "flag"),
    [
        ("doRate", False, True, None),
        ("rate", 1.0, 0.5, "doRate"),
        ("translation/x", 0.0, 100.0, "doTranslation"),
        ("translation/y", 0.0, -50.0, "doTranslation"),
        ("scale/x", 1.0, 0.5, "doScale"),
        ("scale/y", 1.0, 1.5, "doScale"),
        ("rotationType", 1, 3, "doRotation"),
        ("rotation", 0.0, 45.0, "doRotation"),
    ],
)
def test_fade_geometry_documented_scalar_routes_use_geometry_token(
    property_name: str,
    baseline: Any,
    requested: Any,
    flag: str | None,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update(
        {
            "rate": 1.0,
            "translation/x": 0.0,
            "translation/y": 0.0,
            "scale/x": 1.0,
            "scale/y": 1.0,
            "rotationType": 1,
            "rotation": 0.0,
        }
    )
    cues[source_id][property_name] = baseline
    if flag:
        cues[source_id][flag] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, property_name, requested)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeGeometry:v1:")
    result = _fade_write(reader, source_id, property_name, requested, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"][property_name] == requested


@pytest.mark.parametrize(
    "property_name",
    ["doOpacity", "doRate", "doRotation", "doScale", "doTranslation"],
)
def test_fade_geometry_all_activation_flags_have_exact_write_readback(
    property_name: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id, do_opacity=property_name != "doOpacity")
    cues[source_id][property_name] = False
    if property_name == "doOpacity":
        cues[source_id]["doScale"] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, property_name, True)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeGeometry:v1:")
    written = _fade_write(reader, source_id, property_name, True, token)

    assert written["status"] == "updated", written
    assert written["results"][0]["after"][property_name] is True


@pytest.mark.parametrize("geo_mode", [0, 1])
def test_fade_geometry_opacity_supports_absolute_and_relative_modes(geo_mode: int) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update({"geoMode": geo_mode, "doOpacity": True, "opacity": 1.0})
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "opacity", 0.5)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeGeometry:v1:")
    result = _fade_write(reader, source_id, "opacity", 0.5, token)
    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["opacity"] == 0.5


@pytest.mark.parametrize("rotation_type", [1, 2, 3])
def test_fade_geometry_rotation_supports_x_y_and_z_axes(rotation_type: int) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update(
        {"doRotation": True, "rotationType": rotation_type, "rotation": 0.0}
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "rotation", 30.0)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeGeometry:v1:")
    result = _fade_write(reader, source_id, "rotation", 30.0, token)
    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["rotation"] == 30.0


def test_fade_geometry_absolute_3d_quaternion_uses_geometry_token() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update(
        {
            "geoMode": 0,
            "doOpacity": False,
            "doRotation": True,
            "rotationType": 0,
            "quaternion": [0, 0, 0, 1],
        }
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    requested = [0, 0, 0.1, 0.995]

    plan, token = _fade_plan(reader, source_id, "quaternion", requested)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeGeometry:v1:")
    result = _fade_write(reader, source_id, "quaternion", requested, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["quaternion"] == requested
    assert result["results"][0]["executed_operations"][0]["args"] == requested


@pytest.mark.parametrize(
    ("change", "property_name", "requested", "expected"),
    [
        ({"geoMode": 1, "rotationType": 0}, "quaternion", [0, 0, 0.1, 0.995], "absolute"),
        ({"geoMode": 0, "rotationType": 1}, "quaternion", [0, 0, 0.1, 0.995], "3D"),
        ({"geoMode": 1, "doRate": True}, "rate", 0.5, "relative rate"),
    ],
)
def test_fade_geometry_rejects_undocumented_relative_3d_and_rate_semantics(
    change: dict[str, Any],
    property_name: str,
    requested: Any,
    expected: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    target_type = "Audio" if property_name == "rate" else "Video"
    cues = fade_fixture_cues(source_id, target_id, target_type=target_type)
    cues[source_id].update(
        {
            "doOpacity": False,
            "doRotation": property_name == "quaternion",
            "rate": 1.0,
            "quaternion": [0, 0, 0, 1],
            **change,
        }
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, property_name, requested)

    assert plan["status"] == "preflight_failed"
    assert token is None
    assert expected in plan["results"][0]["errors"][property_name]
    assert plan["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("property_name", "requested", "change", "expected"),
    [
        ("translation/x", 10.0, {"doTranslation": False}, "doTranslation=true"),
        ("scale/x", 0.5, {"doScale": False}, "doScale=true"),
        ("rotation", 45.0, {"doRotation": True, "rotationType": 0}, "single-axis"),
        ("rotationType", 0, {"doRotation": True, "rotationType": 1}, "3D rotation remains planned-only"),
    ],
)
def test_fade_geometry_rejects_missing_flags_and_unpromoted_3d_mode(
    property_name: str,
    requested: Any,
    change: dict[str, Any],
    expected: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update(
        {
            "translation/x": 0.0,
            "scale/x": 1.0,
            "rotation": 0.0,
            "rotationType": 1,
            **change,
        }
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_plan(reader, source_id, property_name, requested)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert expected in result["results"][0]["errors"][property_name]
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(("baseline", "requested"), [(1, 0), (0, 1)])
@pytest.mark.parametrize("target_type", ["Audio", "Mic", "Video", "Camera"])
def test_fade_audio_levels_mode_has_dedicated_token_and_exact_readback(
    baseline: int,
    requested: int,
    target_type: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(
        source_id,
        target_id,
        levels_mode=baseline,
        target_type=target_type,
        do_level=True,
    )
    if target_type in {"Audio", "Mic"}:
        cues[source_id]["doOpacity"] = False
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "levelsMode", requested)
    assert plan["status"] == "dry_run"
    assert token and token.startswith("confirm:fadeAudio:v1:")
    assert plan["results"][0]["executed_operations"] == []
    result = _fade_write(reader, source_id, "levelsMode", requested, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["levelsMode"] == requested
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/{FADE_WORKSPACE_ID}/cue_id/{source_id}/levelsMode"
    ) == 1


def test_fade_behavior_stop_target_when_done_has_dedicated_token() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id, do_level=True),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "stopTargetWhenDone", True)
    assert plan["status"] == "dry_run"
    assert token and token.startswith("confirm:fadeBehavior:v1:")
    result = _fade_write(reader, source_id, "stopTargetWhenDone", True, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["stopTargetWhenDone"] is True


def test_fade_behavior_properties_shape_matches_live_mcp_request() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, do_level=True)
    cues[source_id].update(
        {
            "doOpacity": True,
            "levelsMode": 1,
            "stopTargetWhenDone": True,
        }
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan = reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {
                "cue_ref": source_id,
                "profile": "fade_basic",
                "properties": {"stopTargetWhenDone": False},
            }
        ],
        dry_run=True,
    )
    token = planned_setters(plan["results"][0])["stopTargetWhenDone"]["confirm_token"]
    result = reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {
                "cue_ref": source_id,
                "profile": "fade_basic",
                "properties": {"stopTargetWhenDone": False},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert token.startswith("confirm:fadeBehavior:v1:")
    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["stopTargetWhenDone"] is False


def test_fade_audio_do_level_and_level_use_matrix_bound_tokens() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
        qlab_silence_readback=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    do_args = {"row": 0, "column": 0, "value": True}
    do_plan, do_token = _fade_operation_plan(reader, source_id, "doLevel", do_args)
    assert do_plan["status"] == "dry_run", do_plan
    assert do_token and do_token.startswith("confirm:fadeAudio:v1:")
    activated = _fade_operation_write(reader, source_id, "doLevel", do_args, do_token)
    assert activated["status"] == "updated", activated
    assert activated["results"][0]["after"]["doLevel"][0][0] is True

    level_args = {"inChannel": 0, "outChannel": 0, "decibel": "-inf"}
    level_plan, level_token = _fade_operation_plan(reader, source_id, "level", level_args)
    assert level_plan["status"] == "dry_run", level_plan
    assert level_token and level_token.startswith("confirm:fadeAudio:v1:")
    silenced = _fade_operation_write(reader, source_id, "level", level_args, level_token)
    assert silenced["status"] == "updated", silenced
    assert silenced["results"][0]["after"]["levels"][0][0] == -60.0
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/{FADE_WORKSPACE_ID}/cue_id/{source_id}/doLevel/0/0"
    ) == 1
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/{FADE_WORKSPACE_ID}/cue_id/{source_id}/level/0/0"
    ) == 1


def test_fade_audio_silence_matches_workspace_minimum_readback() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id, do_level=True),
        workspace_id=FADE_WORKSPACE_ID,
        audio_min_volume=-60.0,
        qlab_silence_readback=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"inChannel": 0, "outChannel": 0, "decibel": "-inf"}

    plan, token = _fade_operation_plan(reader, source_id, "level", args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeAudio:v1:")
    result = _fade_operation_write(reader, source_id, "level", args, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["levels"][0][0] == -60.0

    rollback_args = {"inChannel": 0, "outChannel": 0, "decibel": 0.0}
    rollback_plan, rollback_token = _fade_operation_plan(
        reader,
        source_id,
        "level",
        rollback_args,
    )
    assert rollback_plan["status"] == "dry_run", rollback_plan
    assert rollback_token and rollback_token.startswith("confirm:fadeAudio:v1:")
    rollback = _fade_operation_write(
        reader,
        source_id,
        "level",
        rollback_args,
        rollback_token,
    )
    assert rollback["status"] == "updated", rollback
    assert rollback["results"][0]["after"]["levels"][0][0] == 0.0


def test_fade_audio_silence_rejects_workspace_minimum_noop() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, do_level=True)
    cues[source_id]["levels"][0][0] = -60.0
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        audio_min_volume=-60.0,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_operation_plan(
        reader,
        source_id,
        "level",
        {"inChannel": 0, "outChannel": 0, "decibel": "-inf"},
    )

    assert plan["status"] == "preflight_failed"
    assert token is None
    assert "must differ from the baseline" in plan["results"][0]["errors"]["level"]


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (-5.9999519405, -6.0),
        (-11.9999528486, -12.0),
        (-18.0001752149, -18.0),
        (-12.0009999, -12.0),
    ],
)
def test_fade_audio_db_readback_uses_explicit_tolerance(actual: float, expected: float) -> None:
    requested = {
        "__fade_audio_matrix_level__": True,
        "row": 0,
        "column": 0,
        "decibel": expected,
    }
    assert write_operations._property_values_match("levels", [[actual]], requested) is (abs(actual - expected) <= 0.001)


def test_fade_audio_db_readback_rejects_value_outside_tolerance() -> None:
    requested = {
        "__fade_audio_matrix_level__": True,
        "row": 0,
        "column": 0,
        "decibel": -12.0,
    }
    assert not write_operations._property_values_match("levels", [[-11.9989]], requested)


def test_fade_audio_relative_level_uses_finite_delta_and_individual_crosspoint() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, levels_mode=1)
    cues[source_id]["doLevel"][2][1] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"inChannel": 2, "outChannel": 1, "decibel": -6.0}

    plan, token = _fade_operation_plan(reader, source_id, "level", args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeAudio:v1:")
    result = _fade_operation_write(reader, source_id, "level", args, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["levels"][2][1] == -6.0


def test_fade_audio_validates_larger_fresh_matrix_dimensions() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, do_level=False)
    matrix = [[0.0 for _ in range(4)] for _ in range(5)]
    active = [[False for _ in range(4)] for _ in range(5)]
    active[4][3] = True
    cues[source_id].update(
        {
            "doOpacity": False,
            "numChannelsIn": 4,
            "levels": [list(row) for row in matrix],
            "sliderLevels": list(matrix[0]),
            "doLevel": active,
        }
    )
    cues[target_id].update(
        {
            "numChannelsIn": 4,
            "audioTrackFormats": [{"channels": 4, "format": "PCM"}],
            "levels": [list(row) for row in matrix],
            "sliderLevels": list(matrix[0]),
        }
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"inChannel": 4, "outChannel": 3, "decibel": -12.0}

    plan, token = _fade_operation_plan(reader, source_id, "level", args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeAudio:v1:")
    written = _fade_operation_write(reader, source_id, "level", args, token)

    assert written["status"] == "updated", written
    assert written["results"][0]["after"]["levels"][4][3] == -12.0


@pytest.mark.parametrize(
    ("levels_mode", "channel", "requested"),
    [(0, 0, "-inf"), (1, 1, -6.0)],
)
def test_fade_audio_slider_level_uses_matrix_bound_token_and_rolls_back(
    levels_mode: int,
    channel: int,
    requested: Any,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, levels_mode=levels_mode)
    cues[source_id]["doLevel"][0][channel] = True
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        qlab_silence_readback=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"channel": channel, "decibel": requested}

    plan, token = _fade_operation_plan(reader, source_id, "sliderLevel", args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeAudio:v1:")
    written = _fade_operation_write(reader, source_id, "sliderLevel", args, token)
    assert written["status"] == "updated", written
    expected = -60.0 if requested == "-inf" else requested
    assert written["results"][0]["after"]["sliderLevels"][channel] == expected

    rollback_args = {"channel": channel, "decibel": 0.0}
    _, rollback_token = _fade_operation_plan(reader, source_id, "sliderLevel", rollback_args)
    assert rollback_token and rollback_token.startswith("confirm:fadeAudio:v1:")
    rolled_back = _fade_operation_write(reader, source_id, "sliderLevel", rollback_args, rollback_token)
    assert rolled_back["status"] == "updated", rolled_back
    assert rolled_back["results"][0]["after"]["sliderLevels"][channel] == 0.0


@pytest.mark.parametrize(
    ("property_name", "args", "read_key", "requested", "rollback_args", "baseline"),
    [
        (
            "inputChannelName",
            {"number": 1, "name": "Dialogue"},
            "inputChannelName/1",
            "Dialogue",
            {"number": 1, "name": "L"},
            "L",
        ),
        (
            "gang",
            {"inChannel": 1, "outChannel": 0, "gang": "music"},
            "gang/1/0",
            "music",
            {"inChannel": 1, "outChannel": 0, "gang": ""},
            "",
        ),
    ],
)
def test_fade_audio_level_metadata_uses_dynamic_readback_and_rolls_back(
    property_name: str,
    args: dict[str, Any],
    read_key: str,
    requested: str,
    rollback_args: dict[str, Any],
    baseline: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_operation_plan(reader, source_id, property_name, args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeAudio:v1:")
    written = _fade_operation_write(reader, source_id, property_name, args, token)
    assert written["status"] == "updated", written
    assert written["results"][0]["after"][read_key] == requested

    _, rollback_token = _fade_operation_plan(reader, source_id, property_name, rollback_args)
    assert rollback_token and rollback_token.startswith("confirm:fadeAudio:v1:")
    rolled_back = _fade_operation_write(reader, source_id, property_name, rollback_args, rollback_token)
    assert rolled_back["status"] == "updated", rolled_back
    assert rolled_back["results"][0]["after"][read_key] == baseline


def test_fade_audio_slider_level_requires_active_crosspoint_without_setter() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"channel": 0, "decibel": -6.0}

    result, token = _fade_operation_plan(reader, source_id, "sliderLevel", args)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert "matching doLevel" in result["results"][0]["errors"]["sliderLevel"]
    assert result["results"][0]["executed_operations"] == []
    assert not any("/sliderLevel/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "args", "source_change", "expected"),
    [
        (
            "inputChannelName",
            {"number": 3, "name": "Extra"},
            {"inputChannelName/3": "Old"},
            "must exist in both",
        ),
        (
            "gang",
            {"inChannel": 0, "outChannel": 0, "gang": "main"},
            {"gang/0/0": ""},
            "row 0 is blocked",
        ),
    ],
)
def test_fade_audio_level_metadata_rejects_unsafe_coordinates_without_setter(
    property_name: str,
    args: dict[str, Any],
    source_change: dict[str, Any],
    expected: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id)
    cues[source_id].update(source_change)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_operation_plan(reader, source_id, property_name, args)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert expected in result["results"][0]["errors"][property_name]
    assert result["results"][0]["executed_operations"] == []
    assert not any(f"/{property_name}/" in address for address, _, _ in client.requests)


def test_fade_audio_level_metadata_rejects_stale_dynamic_baseline_without_setter() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"number": 1, "name": "Dialogue"}
    _, token = _fade_operation_plan(reader, source_id, "inputChannelName", args)
    assert token
    client.cues[source_id]["inputChannelName/1"] = "Changed externally"
    client.requests.clear()

    result = _fade_operation_write(reader, source_id, "inputChannelName", args, token)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any("/inputChannelName/" in address for address, _, _ in client.requests)


def test_fade_audio_setup_first_level_cell_repairs_broken_fade() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id, broken=True),
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={
            (source_id, "doLevel/0/0", True): {"isBroken": False},
            (source_id, "doLevel/0/0", False): {"isBroken": True},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"row": 0, "column": 0, "value": True}

    plan, token = _fade_operation_plan(reader, source_id, "doLevel", args)
    assert plan["status"] == "dry_run", plan
    assert token and token.startswith("confirm:fadeSetup:v1:")
    result = _fade_operation_write(reader, source_id, "doLevel", args, token)

    assert result["status"] == "updated", result
    assert result["results"][0]["after"]["isBroken"] is False
    assert "fade_setup_succeeded" in result["results"][0]["notices"]

    rollback_args = {"row": 0, "column": 0, "value": False}
    _, rollback_token = _fade_operation_plan(reader, source_id, "doLevel", rollback_args)
    assert rollback_token and rollback_token.startswith("confirm:fadeRecovery:v1:")
    rollback = _fade_operation_write(reader, source_id, "doLevel", rollback_args, rollback_token)
    assert rollback["status"] == "updated", rollback
    assert rollback["results"][0]["after"]["doLevel"][0][0] is False


@pytest.mark.parametrize(
    ("levels_mode", "args", "expected_error"),
    [
        (1, {"inChannel": 0, "outChannel": 0, "decibel": "-inf"}, "absolute Levels mode"),
        (0, {"inChannel": 3, "outChannel": 0, "decibel": -3.0}, "readable baseline"),
        (0, {"inChannel": 0, "outChannel": 3, "decibel": -3.0}, "readable baseline"),
    ],
)
def test_fade_audio_rejects_unsafe_silence_and_matrix_indexes_without_token(
    levels_mode: int,
    args: dict[str, Any],
    expected_error: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id, levels_mode=levels_mode, do_level=True),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_operation_plan(reader, source_id, "level", args)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert expected_error in result["results"][0]["errors"]["level"]
    assert result["results"][0]["executed_operations"] == []
    assert not any("/level/" in address for address, _, _ in client.requests)


def test_fade_audio_stale_matrix_token_rejected_without_setter() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_audio_fixture_cues(source_id, target_id, do_level=True),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    args = {"inChannel": 0, "outChannel": 0, "decibel": -6.0}
    _, token = _fade_operation_plan(reader, source_id, "level", args)
    assert token
    client.cues[source_id]["levels"][0][1] = -1.0
    client.requests.clear()

    result = _fade_operation_write(reader, source_id, "level", args, token)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any("/level/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("target_change", "expected"),
    [
        ({"type": "Text"}, "must be one of"),
        ({"numChannelsIn": 0, "audioTrackFormats": []}, "proven readable audio channels"),
        ({"isBroken": True}, "healthy"),
        ({"isWarning": True}, "healthy"),
        ({"isRunning": True}, "inactive"),
    ],
)
def test_fade_audio_rejects_incompatible_or_unhealthy_target_without_token(
    target_change: dict[str, Any],
    expected: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id)
    cues[target_id].update(target_change)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_plan(reader, source_id, "levelsMode", 1)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert expected in result["results"][0]["errors"]["levelsMode"]
    assert result["results"][0]["executed_operations"] == []


def test_fade_audio_mic_target_uses_fresh_levels_matrix_evidence() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, target_type="Mic")
    cues[source_id]["doOpacity"] = False
    # Mic/Audio Levels do not require Video's embedded-track metadata.
    cues[target_id].pop("numChannelsIn", None)
    cues[target_id].pop("audioTrackFormats", None)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_plan(reader, source_id, "levelsMode", 1)

    assert result["status"] == "dry_run"
    assert token and token.startswith("confirm:fadeAudio:v1:")
    assert result["results"][0]["executed_operations"] == []


def test_fade_audio_rejects_generic_wrong_family_and_target_drift_without_setter() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    other_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_audio_fixture_cues(source_id, target_id)
    cues[other_target] = dict(cues[target_id])
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    _, token = _fade_plan(reader, source_id, "levelsMode", 1)
    assert token

    for bad_token in ("confirm:levelsMode:1", "confirm:fadeGeometry:v1:bad:bad"):
        result = _fade_write(reader, source_id, "levelsMode", 1, bad_token)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    client.cues[source_id]["cueTargetID"] = other_target
    client.requests.clear()
    drift = _fade_write(reader, source_id, "levelsMode", 1, token)
    assert drift["status"] == "preflight_failed"
    assert drift["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/levelsMode") for address, _, _ in client.requests)


def test_fade_phase1_exact_visual_target_writes_and_rolls_back() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    old_target = "22222222-2222-4222-8222-222222222222"
    new_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(source_id, old_target)
    cues[new_target] = {
        "type": "Text",
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"), cues=cues, workspace_id=FADE_WORKSPACE_ID
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "cueTargetID", new_target)
    assert token and token.startswith("confirm:fadeTarget:v1:")
    assert _fade_write(reader, source_id, "cueTargetID", new_target, token)["status"] == "updated"
    rollback_plan, rollback_token = _fade_plan(reader, source_id, "cueTargetID", old_target)
    assert rollback_plan["status"] == "dry_run"
    assert rollback_token and rollback_token.startswith("confirm:fadeTarget:v1:")
    result = _fade_write(reader, source_id, "cueTargetID", old_target, rollback_token)
    assert result["results"][0]["after"]["cueTargetID"] == old_target


def test_fade_target_rejects_target_incompatible_with_active_parameters() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    visual_target = "22222222-2222-4222-8222-222222222222"
    audio_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(source_id, visual_target, do_opacity=True)
    cues[audio_target] = {
        "type": "Audio",
        "numChannelsIn": 2,
        "audioTrackFormats": [{"channels": 2}],
        "levels": [[0.0], [0.0], [0.0]],
        "sliderLevels": [0.0],
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "cueTargetID", audio_target)

    assert plan["status"] == "preflight_failed"
    assert token is None
    assert "active Fade parameters" in plan["results"][0]["errors"]["cueTargetID"]
    assert plan["results"][0]["executed_operations"] == []


def test_fade_target_can_leave_existing_group_but_does_not_assign_unvalidated_fanout() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    group_target = "22222222-2222-4222-8222-222222222222"
    visual_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(source_id, group_target, target_type="Group", do_opacity=True)
    cues[visual_target] = {
        "type": "Video",
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    leave_plan, leave_token = _fade_plan(reader, source_id, "cueTargetID", visual_target)
    assert leave_plan["status"] == "dry_run", leave_plan
    assert leave_token and leave_token.startswith("confirm:fadeTarget:v1:")

    client.cues[source_id]["cueTargetID"] = visual_target
    assign_plan, assign_token = _fade_plan(reader, source_id, "cueTargetID", group_target)
    assert assign_plan["status"] == "preflight_failed"
    assert assign_token is None
    assert assign_plan["results"][0]["executed_operations"] == []


def test_fade_geometry_rejects_flag_that_makes_existing_target_incompatible() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id, target_type="Audio", do_opacity=True)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "doRate", True)

    assert plan["status"] == "preflight_failed"
    assert token is None
    assert "compatible" in plan["results"][0]["errors"]["doRate"]
    assert plan["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("property_name", "requested"),
    [
        ("fadeType", 2),
        ("targetMode", 1),
        ("pathWidth", 200),
        ("pathHeight", 100),
        ("cueTargetNumber", "99"),
        ("tempCueTargetID", "33333333-3333-4333-8333-333333333333"),
        ("patchTargetID", "33333333-3333-4333-8333-333333333333"),
        ("audioMapTargetID", "33333333-3333-4333-8333-333333333333"),
    ],
)
def test_fade_unpromoted_properties_never_accept_generic_tokens_or_emit_setters(
    property_name: str,
    requested: Any,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {
        "cue_ref": source_id,
        "profile": "fade_basic",
        "properties": {property_name: requested},
        "confirm_gates": [f"confirm:{property_name}:test"],
    }

    result = reader.update_cues(FADE_WORKSPACE_ID, [request], dry_run=False)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_fade_curve_and_path_unsupported_controls_never_emit_setters() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    path = reader.update_cues(
        FADE_WORKSPACE_ID,
        [{"cue_ref": source_id, "profile": "fade_basic", "properties": {"pathWidth": 200}}],
        dry_run=True,
    )
    cues[source_id]["fadeType"] = 2
    curve = reader.update_cues(
        FADE_WORKSPACE_ID,
        [{"cue_ref": source_id, "profile": "fade_basic", "properties": {"curveType": "S-Curve"}}],
        dry_run=True,
    )

    assert path["results"][0]["executed_operations"] == []
    assert curve["results"][0]["executed_operations"] == []
    assert_no_confirm_token(path)
    assert_no_confirm_token(curve)
    assert not any(address.endswith(("/pathWidth", "/curveType")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "args"),
    [
        ("doObjectLevel", {"row": 1, "object": "A", "value": True}),
        ("doObjectIDLevel", {"row": 1, "objectID": "object-id", "value": True}),
        ("setGeometryFromTarget", {}),
        ("setLevelsFromTarget", {}),
        ("audioEffect/0/parameter", {"value": 0.5}),
        ("videoEffect/0/parameter", {"value": 0.5}),
    ],
)
def test_fade_objects_copy_actions_and_fx_remain_planned_only_without_setter(
    property_name: str,
    args: dict[str, Any],
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {
                "cue_ref": source_id,
                "profile": "fade_basic",
                "operations": [{"property": property_name, "args": args}],
            }
        ],
        dry_run=True,
    )

    assert result["status"] in {"dry_run", "preflight_failed"}
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(property_name.split("/")[0] in address for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_token", ["fake", "confirm:fadeTarget:v1:bad:bad", "confirm:name:new"])
def test_fade_phase1_rejects_fake_and_wrong_family_tokens_without_setter(bad_token: str) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = _fade_write(reader, source_id, "name", "Renamed", bad_token)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/name") for address, _, _ in client.requests)


def test_fade_phase1_rejects_stale_token_without_setter() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    _, token = _fade_plan(reader, source_id, "name", "Renamed")
    assert token
    client.cues[source_id]["name"] = "Changed externally"
    client.requests.clear()

    result = _fade_write(reader, source_id, "name", "Renamed", token)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/name") for address, _, _ in client.requests)


def test_fade_setup_missing_target_and_exact_recovery() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(
        source_id, target_id, target_id_value="", broken=True, do_opacity=False
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    _, token = _fade_plan(reader, source_id, "cueTargetID", target_id)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    setup = _fade_write(reader, source_id, "cueTargetID", target_id, token)
    assert setup["status"] == "updated"
    assert "fade_setup_progressed_missing_parameter" in setup["results"][0]["notices"]

    _, recovery_token = _fade_plan(reader, source_id, "cueTargetID", "")
    assert recovery_token and recovery_token.startswith("confirm:fadeRecovery:v1:")
    recovery = _fade_write(reader, source_id, "cueTargetID", "", recovery_token)
    assert recovery["status"] == "updated"
    assert recovery["results"][0]["after"]["cueTargetID"] == ""
    assert "fade_recovery_succeeded" in recovery["results"][0]["notices"]


def test_fade_setup_does_not_replace_valid_target_when_parameter_is_missing() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    current_target = "22222222-2222-4222-8222-222222222222"
    other_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(
        source_id,
        current_target,
        broken=True,
        do_opacity=False,
    )
    cues[other_target] = {
        "type": "Text",
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    plan, token = _fade_plan(reader, source_id, "cueTargetID", other_target)

    assert plan["status"] == "preflight_failed"
    assert token is None
    assert "current target is valid" in plan["results"][0]["errors"]["cueTargetID"]
    assert plan["results"][0]["executed_operations"] == []


def test_fade_recovery_rejects_target_drift_after_setup() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    other_target = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(source_id, target_id, broken=True, do_opacity=False)
    cues[other_target] = {
        "type": "Video",
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={(source_id, "doOpacity", True): {"isBroken": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    _, token = _fade_plan(reader, source_id, "doOpacity", True)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    assert _fade_write(reader, source_id, "doOpacity", True, token)["status"] == "updated"
    client.cues[source_id]["cueTargetID"] = other_target
    client.requests.clear()

    recovery_plan, recovery_token = _fade_plan(reader, source_id, "doOpacity", False)

    assert recovery_plan["status"] == "preflight_failed"
    assert recovery_token is None
    assert "target changed" in recovery_plan["results"][0]["errors"]["doOpacity"]
    assert recovery_plan["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/doOpacity") for address, _, _ in client.requests)


def test_fade_recovery_rejects_same_target_matrix_drift_after_audio_setup() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, broken=True, do_level=False)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={(source_id, "doLevel/0/0", True): {"isBroken": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    enable = {"row": 0, "column": 0, "value": True}

    _, token = _fade_operation_plan(reader, source_id, "doLevel", enable)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    assert _fade_operation_write(reader, source_id, "doLevel", enable, token)["status"] == "updated"
    client.cues[target_id]["levels"][0][0] = -1.0
    client.requests.clear()

    disable = {"row": 0, "column": 0, "value": False}
    recovery_plan, recovery_token = _fade_operation_plan(reader, source_id, "doLevel", disable)

    assert recovery_plan["status"] == "preflight_failed"
    assert recovery_token is None
    assert "target changed" in recovery_plan["results"][0]["errors"]["doLevel"]
    assert recovery_plan["results"][0]["executed_operations"] == []


def test_fade_setup_replaces_invalid_direct_target_and_recovers_exact_baseline() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    invalid_target_id = "33333333-3333-4333-8333-333333333333"
    cues = fade_fixture_cues(
        source_id,
        target_id,
        target_id_value=invalid_target_id,
        broken=True,
        do_opacity=True,
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={
            (source_id, "cueTargetID", target_id): {"isBroken": False},
            (source_id, "cueTargetID", invalid_target_id): {"isBroken": True},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    _, token = _fade_plan(reader, source_id, "cueTargetID", target_id)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    setup = _fade_write(reader, source_id, "cueTargetID", target_id, token)
    assert setup["status"] == "updated", setup
    assert setup["results"][0]["after"]["isBroken"] is False

    _, recovery_token = _fade_plan(reader, source_id, "cueTargetID", invalid_target_id)
    assert recovery_token and recovery_token.startswith("confirm:fadeRecovery:v1:")
    recovery = _fade_write(reader, source_id, "cueTargetID", invalid_target_id, recovery_token)
    assert recovery["results"][0]["errors"] is None, recovery["results"][0]["errors"]
    assert recovery["status"] == "updated", recovery["results"][0]
    assert recovery["results"][0]["after"]["cueTargetID"] == invalid_target_id
    assert recovery["results"][0]["after"]["isBroken"] is True


def test_fade_setup_disables_invalid_audio_matrix_selection_and_recovers() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_audio_fixture_cues(source_id, target_id, broken=True)
    cues[source_id]["doLevel"][2][1] = True
    cues[target_id]["levels"] = cues[target_id]["levels"][:2]
    cues[target_id]["numChannelsIn"] = 1
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={
            (source_id, "doLevel/2/1", False): {"isBroken": False},
            (source_id, "doLevel/2/1", True): {"isBroken": True},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    disable = {"row": 2, "column": 1, "value": False}

    _, token = _fade_operation_plan(reader, source_id, "doLevel", disable)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    setup = _fade_operation_write(reader, source_id, "doLevel", disable, token)
    assert setup["status"] == "updated", setup
    assert setup["results"][0]["after"]["doLevel"][2][1] is False
    assert setup["results"][0]["after"]["isBroken"] is False

    restore = {"row": 2, "column": 1, "value": True}
    _, recovery_token = _fade_operation_plan(reader, source_id, "doLevel", restore)
    assert recovery_token and recovery_token.startswith("confirm:fadeRecovery:v1:")
    recovery = _fade_operation_write(reader, source_id, "doLevel", restore, recovery_token)
    assert recovery["status"] == "updated", recovery
    assert recovery["results"][0]["after"]["doLevel"][2][1] is True
    assert recovery["results"][0]["after"]["isBroken"] is True


def test_fade_setup_missing_parameter_and_exact_recovery() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id, broken=True, do_opacity=False),
        workspace_id=FADE_WORKSPACE_ID,
        property_outcomes={
            (source_id, "doOpacity", True): {"isBroken": False},
            (source_id, "doOpacity", False): {"isBroken": True},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    _, token = _fade_plan(reader, source_id, "doOpacity", True)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    assert _fade_write(reader, source_id, "doOpacity", True, token)["status"] == "updated"

    _, recovery_token = _fade_plan(reader, source_id, "doOpacity", False)
    assert recovery_token and recovery_token.startswith("confirm:fadeRecovery:v1:")
    recovery = _fade_write(reader, source_id, "doOpacity", False, recovery_token)
    assert recovery["status"] == "updated"
    assert recovery["results"][0]["after"]["doOpacity"] is False


def test_fade_setup_failure_requires_recovery_and_other_broken_writes_stay_blocked() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=fade_fixture_cues(source_id, target_id, broken=True, do_opacity=False),
        workspace_id=FADE_WORKSPACE_ID,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    blocked, blocked_token = _fade_plan(reader, source_id, "opacity", 0.75)
    assert blocked["status"] == "preflight_failed"
    assert blocked_token is None
    _, token = _fade_plan(reader, source_id, "doOpacity", True)
    assert token and token.startswith("confirm:fadeSetup:v1:")
    failed = _fade_write(reader, source_id, "doOpacity", True, token)
    assert failed["status"] == "verification_failed"

    _, recovery_token = _fade_plan(reader, source_id, "doOpacity", False)
    assert recovery_token and recovery_token.startswith("confirm:fadeRecovery:v1:")
    assert _fade_write(reader, source_id, "doOpacity", False, recovery_token)["status"] == "updated"


def test_fade_phase1_rejects_batch_multi_property_live_and_active_source() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    other_fade = "33333333-3333-4333-8333-333333333333"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[other_fade] = dict(cues[source_id], name="Other")
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"), cues=cues, workspace_id=FADE_WORKSPACE_ID
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    batch = reader.update_cues(
        FADE_WORKSPACE_ID,
        [
            {"cue_ref": source_id, "profile": "fade_basic", "properties": {"name": "A"}},
            {"cue_ref": other_fade, "profile": "fade_basic", "properties": {"name": "B"}},
        ],
        dry_run=True,
    )
    multi = reader.update_cues(
        FADE_WORKSPACE_ID,
        [{"cue_ref": source_id, "profile": "fade_basic", "properties": {"name": "A", "geoMode": 1}}],
        dry_run=True,
    )
    live, live_token = _fade_plan(reader, source_id, "opacity", 0.75, mode="live")
    client.cues[source_id]["isRunning"] = True
    active, active_token = _fade_plan(reader, source_id, "opacity", 0.75)

    assert batch["status"] == "preflight_failed"
    assert multi["status"] == "preflight_failed"
    assert live["status"] == "preflight_failed" and live_token is None
    assert active["status"] == "preflight_failed" and active_token is None
    assert all(item["executed_operations"] == [] for item in batch["results"] + multi["results"])
    assert not any(address.endswith(("/name", "/geoMode", "/opacity")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("source_change", "target_change", "property_name", "requested"),
    [
        ({"targetMode": 1}, {}, "name", "Renamed"),
        ({"fadeType": 2}, {}, "name", "Renamed"),
        ({}, {"type": "Memo"}, "name", "Renamed"),
        ({}, {"isBroken": True}, "name", "Renamed"),
        ({}, {"isRunning": True}, "name", "Renamed"),
        ({}, {}, "cueTargetID", "11111111-1111-4111-8111-111111111111"),
    ],
)
def test_fade_phase1_rejects_wrong_modes_and_unsafe_targets_without_token(
    source_change: dict[str, Any],
    target_change: dict[str, Any],
    property_name: str,
    requested: Any,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    cues = fade_fixture_cues(source_id, target_id)
    cues[source_id].update(source_change)
    cues[target_id].update(target_change)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"), cues=cues, workspace_id=FADE_WORKSPACE_ID
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result, token = _fade_plan(reader, source_id, property_name, requested)

    assert result["status"] == "preflight_failed"
    assert token is None
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_fade_profile_type_mismatch_fails_cleanly_without_plan() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={memo_id: {"type": "Memo", "targetMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": memo_id, "profile": "fade_basic", "properties": {"targetMode": 0}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["errors"]["profile"] == "fade_basic update profile requires a Fade cue"


def test_update_cues_dry_run_reports_invalid_cue_ref_per_item_without_reading() -> None:
    client = BatchFakeWriteClient(QLabConfig(enable_write=False), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": "selected", "properties": {"name": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "concrete cue" in result["results"][0]["errors"]["cue_ref"]
    assert client.requests == []


def test_update_cues_dry_run_reports_invalid_profile_per_item() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "bad_profile", "properties": {"name": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "update profile is not allowed" in result["results"][0]["errors"]["profile"]
    assert client.requests == []


def test_update_cues_real_preflight_failure_blocks_all_setters() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            audio_id: {"type": "Memo", "rate": 1.0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["failed_count"] == 1
    assert "Audio cue" in result["results"][1]["errors"]["profile"]
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{audio_id}/rate" not in addresses


def test_update_cues_real_preflight_invalid_value_blocks_all_setters_without_secret_leak() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    group_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            group_id: {"type": "Group", "preWait": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": group_id, "properties": {"preWait": -1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["dry_run"] is False
    assert result["requested_count"] == 2
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "planned"
    assert result["results"][1]["status"] == "preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "preWait must be a non-negative number"
    assert "read_before" not in result["results"][1]["errors"]
    assert result["message"] == "Batch cue update was blocked during preflight; no mutating OSC commands were sent."
    assert f"/workspace/ws-1/cue_id/{memo_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/preWait" not in addresses
    assert "server-pass" not in repr(result)


def test_update_cues_real_updates_mixed_safe_profiles() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            audio_id: {"type": "Audio", "rate": 1.0, "startTime": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 0
    assert addresses.count("/workspaces") == 1
    assert addresses.count("/workspace/ws-1/connect") == 1
    assert addresses.count("/workspace/ws-1/showMode") == 1
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{audio_id}/rate" in addresses
    assert result["results"][0]["after"]["name"] == "Memo new"
    assert result["results"][1]["after"]["rate"] == 1.1


def test_update_cues_uses_configured_update_debug() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", update_debug=True),
        cues={cue_id: {"type": "Memo", "name": "Old"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"name": "New"}}], dry_run=False)

    assert result["ok"] is True
    assert result["results"][0]["debug"]["properties_match"] is True
    assert result["results"][0]["debug"]["requested_properties"] == {"name": "New"}


def test_update_cues_real_blocks_dry_run_only_property_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["level"]
    assert client.requests == []


def test_update_cues_real_blocks_target_refs_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["cueTargetID"]
    assert client.requests == []


def test_update_cues_utility_target_initial_assignment_allows_broken_empty_source() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            source_id: {
                "type": "Start", "cueTargetID": "", "hasCueTargets": True,
                "isBroken": True, "isWarning": False, "isRunning": False,
                "isPaused": False, "isAuditioning": False,
            },
            target_id: {
                "type": "Memo", "isBroken": False, "isWarning": False,
                "isRunning": False, "isPaused": False, "isAuditioning": False,
            },
        },
        property_outcomes={(source_id, "cueTargetID", target_id): {"isBroken": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": target_id}}

    dry = reader.update_cues("ws-1", [request], dry_run=True)
    operation = planned_setters(dry["results"][0])["cueTargetID"]
    result = reader.update_cues(
        "ws-1", [{**request, "confirm_gates": [operation["confirm_token"]]}], dry_run=False
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["cueTargetID"] == target_id
    assert result["results"][0]["after"]["isBroken"] is False
    assert sum(address.endswith("/cueTargetID") for address, _, _ in client.requests) == 1


@pytest.mark.parametrize(
    "source_values",
    [
        {"cueTargetID": "22222222-2222-4222-8222-222222222222", "isBroken": True},
        {"cueTargetID": "", "isBroken": True, "isWarning": True},
    ],
)
def test_update_cues_utility_target_initial_assignment_preserves_broken_source_guards(
    source_values: dict[str, Any],
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    source = {
        "type": "Start", "cueTargetID": "", "hasCueTargets": True,
        "isBroken": False, "isWarning": False, "isRunning": False,
        "isPaused": False, "isAuditioning": False,
    }
    source.update(source_values)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: source, target_id: {"type": "Memo", "isBroken": False, "isWarning": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": target_id}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "healthy source" in result["results"][0]["errors"]["cueTargetID"]
    assert not any(address.endswith("/cueTargetID") for address, _, _ in client.requests)


def test_update_cues_utility_target_initial_assignment_requires_exact_target_uuid() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True, "isBroken": True, "isWarning": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "cueTargetID requires an exact target cue UUID."}
    assert not any(address.endswith("/cueTargetID") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("target_basic", cue_type)
        for cue_type in ("Start", "Stop", "Pause", "Load", "Goto", "GoTo", "Arm", "Disarm")
    ]
    + [("reset_basic", "Reset")],
)
def test_update_cues_utility_target_uuid_gate_writes_and_rolls_back(
    profile: str, cue_type: str
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            source_id: {
                "type": cue_type,
                "cueTargetID": "",
                "hasCueTargets": True,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            },
            target_id: {
                "type": "Memo",
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            },
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": profile, "properties": {"cueTargetID": target_id}}

    dry = reader.update_cues("ws-1", [request], dry_run=True)
    operation = planned_setters(dry["results"][0])["cueTargetID"]
    token = operation["confirm_token"]
    payload, error = write_operations._decode_utility_target_confirm_token(token)
    assert error is None
    assert payload is not None
    assert {key: payload[key] for key in ("workspace_id", "cue_id", "cue_type", "profile", "property", "baseline", "requested")} == {
        "workspace_id": "ws-1",
        "cue_id": source_id,
        "cue_type": cue_type,
        "profile": profile,
        "property": "cueTargetID",
        "baseline": "",
        "requested": target_id,
    }

    written = reader.update_cues(
        "ws-1", [{**request, "confirm_gates": [token]}], dry_run=False
    )
    assert written["status"] == "updated"
    assert written["results"][0]["after"]["cueTargetID"] == target_id

    rollback_dry = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": profile, "properties": {"cueTargetID": ""}}],
        dry_run=True,
    )
    rollback_token = planned_setters(rollback_dry["results"][0])["cueTargetID"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": profile, "properties": {"cueTargetID": ""}, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["cueTargetID"] == ""


def test_update_cues_utility_target_gate_rejects_batch_multi_property_and_wrong_type() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            source_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True},
            target_id: {"type": "Memo"},
        },
        cue_numbers={"1": source_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    base = {"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": target_id}}
    dry = reader.update_cues("ws-1", [base], dry_run=True)
    token = planned_setters(dry["results"][0])["cueTargetID"]["confirm_token"]

    batch = reader.update_cues("ws-1", [{**base, "confirm_gates": [token]}, {**base, "confirm_gates": [token]}], dry_run=False)
    multi = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": target_id, "name": "No"}, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong = reader.update_cues(
        "ws-1",
        [{"cue_ref": target_id, "profile": "target_basic", "properties": {"cueTargetID": source_id}, "confirm_gates": [token]}],
        dry_run=False,
    )
    cue_number = reader.update_cues(
        "ws-1",
        [{"cue_ref": "1", "profile": "target_basic", "properties": {"cueTargetID": target_id}, "confirm_gates": [token]}],
        dry_run=False,
    )
    target_number = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetNumber": "1"}, "confirm_gates": [token]}],
        dry_run=False,
    )
    assert batch["status"] == multi["status"] == wrong["status"] == cue_number["status"] == target_number["status"] == "preflight_failed"
    assert all(not address.endswith("/cueTargetID") for address, _, _ in client.requests)


def test_update_cues_utility_target_gate_rejects_fake_wrong_and_stale_tokens() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    other_target_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            source_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True},
            target_id: {"type": "Memo"},
            other_target_id: {"type": "Memo"},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "target_basic", "properties": {"cueTargetID": target_id}}
    dry = reader.update_cues("ws-1", [request], dry_run=True)
    token = planned_setters(dry["results"][0])["cueTargetID"]["confirm_token"]

    fake = reader.update_cues("ws-1", [{**request, "confirm_gates": ["confirm:utilityTarget:v1:fake:fake"]}], dry_run=False)
    wrong = reader.update_cues("ws-1", [{**request, "confirm_gates": ["confirm:videoIO:v1:fake:fake"]}], dry_run=False)
    client.cues[source_id]["cueTargetID"] = other_target_id
    stale = reader.update_cues("ws-1", [{**request, "confirm_gates": [token]}], dry_run=False)

    assert fake["status"] == wrong["status"] == stale["status"] == "preflight_failed"
    assert "confirm_token" in fake["results"][0]["errors"]["cueTargetID"]
    assert "confirm_token" in wrong["results"][0]["errors"]["cueTargetID"]
    assert "confirm_token does not match" in stale["results"][0]["errors"]["cueTargetID"]
    assert all(not address.endswith("/cueTargetID") for address, _, _ in client.requests)


def test_update_cues_utility_target_gate_rejects_live_mode_without_osc() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{
            "cue_ref": source_id,
            "profile": "target_basic",
            "operations": [{"property": "cueTargetID", "args": {"value": "22222222-2222-4222-8222-222222222222"}, "mode": "live"}],
        }],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "saved" in result["results"][0]["errors"]["validation"]
    assert all(not address.endswith("/cueTargetID") for address, _, _ in client.requests)


def test_update_cues_real_blocks_unresolved_target_ref_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True}, target_id: {"type": "Memo"}},
        missing_refs={target_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": target_id},
                "confirm_gates": ["confirm:utilityTarget:v1:fake:fake"],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "cueTargetID target could not be resolved before update."}
    assert all(not request[0].endswith("/cueTargetID") for request in client.requests)


def test_update_cues_real_blocks_self_target_ref_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": cue_id},
                "confirm_gates": ["confirm:utilityTarget:v1:fake:fake"],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "cueTargetID target cannot be the cue being updated."}
    assert all(not request[0].endswith("/cueTargetID") for request in client.requests)


def test_update_cues_real_allows_resolved_target_ref_with_gate() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": "", "hasCueTargets": True}, target_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetID": target_id}})

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": target_id},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["cueTargetID"] == target_id


def test_update_cues_real_blocks_target_name_resolution_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetName": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(
        reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetName": "Target by name"}}
    )

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetName": "Target by name"},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {
        "cueTargetName": "cueTargetName is gated or dry-run only outside the specialized single-cue saved cueTargetID gate."
    }
    assert all(not request[0].endswith("/cueTargetName") for request in client.requests)


def test_update_cues_real_blocks_missing_cue_before_any_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old"}, missing_id: {"type": "Memo", "name": "Missing"}},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"name": "New"}},
            {"cue_ref": missing_id, "properties": {"name": "Nope"}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][1]["status"] == "preflight_failed"
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" not in addresses


@pytest.mark.parametrize(
    ("property_name", "requested", "start_next", "stop_target", "expected_target_id", "expected_target_type"),
    [
        ("cueTargetID", "33333333-3333-4333-8333-333333333333", False, False, "33333333-3333-4333-8333-333333333333", "Video"),
        ("devampType", 2, False, False, "22222222-2222-4222-8222-222222222222", "Audio"),
        ("startNextCueWhenSliceEnds", True, False, False, "22222222-2222-4222-8222-222222222222", "Audio"),
        ("stopTargetWhenSliceEnds", True, True, False, "22222222-2222-4222-8222-222222222222", "Audio"),
    ],
)
def test_update_cues_devamp_gate_writes_reads_back_and_rolls_back(
    property_name: str,
    requested: Any,
    start_next: bool,
    stop_target: bool,
    expected_target_id: str,
    expected_target_type: str,
) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    video_id = "33333333-3333-4333-8333-333333333333"
    cues = devamp_fixture_cues(source_id, audio_id, start_next=start_next, stop_target=stop_target)
    cues[video_id] = {"type": "Video", "isBroken": False, "isWarning": False, "isRunning": False}
    client = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), cues=cues)
    reader = QLabReader(client)  # type: ignore[arg-type]
    baseline = client.cues[source_id][property_name]
    request = {"cue_ref": source_id, "profile": "devamp_basic", "properties": {property_name: requested}}

    dry = reader.update_cues("ws-1", [request], dry_run=True)
    setter = planned_setters(dry["results"][0])[property_name]
    token = setter["confirm_token"]
    payload, error = write_operations._decode_devamp_confirm_token(token)

    assert dry["status"] == "dry_run"
    assert error is None
    assert payload is not None
    assert payload["workspace_id"] == "ws-1"
    assert payload["cue_id"] == source_id
    assert payload["cue_type"] == "Devamp"
    assert payload["profile"] == "devamp_basic"
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert payload["target_uuid"] == expected_target_id
    assert payload["target_type"] == expected_target_type

    updated = reader.update_cues("ws-1", [{**request, "confirm_gates": [token]}], dry_run=False)
    assert updated["status"] == "updated"
    assert updated["results"][0]["after"][property_name] == requested

    rollback_request = {"cue_ref": source_id, "profile": "devamp_basic", "properties": {property_name: baseline}}
    rollback_dry = reader.update_cues("ws-1", [rollback_request], dry_run=True)
    rollback_token = planned_setters(rollback_dry["results"][0])[property_name]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1", [{**rollback_request, "confirm_gates": [rollback_token]}], dry_run=False
    )
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"][property_name] == baseline


def test_update_cues_devamp_type_mcp_input_dry_run_returns_devamp_token() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=devamp_fixture_cues(source_id, audio_id),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = CueUpdateInput(
        cue_ref=source_id,
        profile="devamp_basic",
        properties={"devampType": 2},
    ).model_dump()

    result = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(result["results"][0])["devampType"]

    assert setter["confirm_token"].startswith("confirm:devamp:v1:")
    assert result["results"][0]["executed_operations"] == []
    assert client.cues[source_id]["devampType"] == 1


@pytest.mark.parametrize("target_type", ["Memo", "Light"])
def test_update_cues_devamp_target_requires_existing_audio_or_video(target_type: str) -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    target_id = "33333333-3333-4333-8333-333333333333"
    cues = devamp_fixture_cues(source_id, audio_id)
    cues[target_id] = {"type": target_type, "isBroken": False, "isWarning": False, "isRunning": False}
    client = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), cues=cues)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "properties": {"cueTargetID": target_id}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "Devamp cueTargetID target must be an Audio or Video cue."}
    assert all(not address.endswith("/cueTargetID") for address, _, _ in client.requests)


def test_update_cues_devamp_gate_rejects_missing_self_fake_wrong_and_stale_tokens() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    missing_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=devamp_fixture_cues(source_id, audio_id),
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    target_request = {"cue_ref": source_id, "profile": "devamp_basic", "properties": {"cueTargetID": missing_id}}
    missing = reader.update_cues("ws-1", [target_request], dry_run=True)
    self_target = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "properties": {"cueTargetID": source_id}}],
        dry_run=True,
    )
    settings_request = {"cue_ref": source_id, "profile": "devamp_basic", "properties": {"devampType": 2}}
    dry = reader.update_cues("ws-1", [settings_request], dry_run=True)
    token = planned_setters(dry["results"][0])["devampType"]["confirm_token"]
    fake = reader.update_cues(
        "ws-1", [{**settings_request, "confirm_gates": ["confirm:devamp:v1:fake:fake"]}], dry_run=False
    )
    wrong = reader.update_cues(
        "ws-1", [{**settings_request, "confirm_gates": ["confirm:utilityTarget:v1:fake:fake"]}], dry_run=False
    )
    client.cues[source_id]["startNextCueWhenSliceEnds"] = True
    stale = reader.update_cues("ws-1", [{**settings_request, "confirm_gates": [token]}], dry_run=False)

    assert missing["status"] == self_target["status"] == "preflight_failed"
    assert "could not be resolved" in missing["results"][0]["errors"]["cueTargetID"]
    assert "cannot be the cue" in self_target["results"][0]["errors"]["cueTargetID"]
    assert fake["status"] == wrong["status"] == stale["status"] == "preflight_failed"
    assert "confirm_token" in fake["results"][0]["errors"]["devampType"]
    assert "confirm_token" in wrong["results"][0]["errors"]["devampType"]
    assert "confirm_token does not match" in stale["results"][0]["errors"]["devampType"]
    assert all(not address.endswith("/cueTargetID") and not address.endswith("/devampType") for address, _, _ in client.requests)


def test_update_cues_devamp_gate_rejects_batch_multi_live_wrong_type_and_flag_dependencies() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=devamp_fixture_cues(source_id, audio_id),
        cue_numbers={"1": source_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    base = {"cue_ref": source_id, "profile": "devamp_basic", "properties": {"devampType": 2}}
    token = planned_setters(reader.update_cues("ws-1", [base], dry_run=True)["results"][0])["devampType"]["confirm_token"]
    batch = reader.update_cues("ws-1", [{**base, "confirm_gates": [token]}, {**base, "confirm_gates": [token]}], dry_run=False)
    multi = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "properties": {"devampType": 2, "startNextCueWhenSliceEnds": True}, "confirm_gates": [token]}],
        dry_run=False,
    )
    cue_number = reader.update_cues(
        "ws-1", [{**base, "cue_ref": "1", "confirm_gates": [token]}], dry_run=False
    )
    live = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "operations": [{"property": "devampType", "args": {"value": 2}, "mode": "live"}]}],
        dry_run=True,
    )
    wrong_type_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: {"type": "Memo", "devampType": 1}},
    )
    wrong_type = QLabReader(wrong_type_client).update_cues(  # type: ignore[arg-type]
        "ws-1", [base], dry_run=True
    )
    stop_without_start = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "properties": {"stopTargetWhenSliceEnds": True}}],
        dry_run=True,
    )
    client.cues[source_id]["startNextCueWhenSliceEnds"] = True
    client.cues[source_id]["stopTargetWhenSliceEnds"] = True
    disable_start = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "devamp_basic", "properties": {"startNextCueWhenSliceEnds": False}}],
        dry_run=True,
    )

    assert batch["status"] == multi["status"] == cue_number["status"] == "preflight_failed"
    assert live["status"] == wrong_type["status"] == stop_without_start["status"] == disable_start["status"] == "preflight_failed"
    assert "saved" in live["results"][0]["errors"]["validation"]
    assert "requires a Devamp cue" in wrong_type["results"][0]["errors"]["profile"]
    assert "requires startNextCueWhenSliceEnds=true" in stop_without_start["results"][0]["errors"]["stopTargetWhenSliceEnds"]
    assert "cannot disable" in disable_start["results"][0]["errors"]["startNextCueWhenSliceEnds"]
    assert all(not address.endswith("/devampType") for address, _, _ in client.requests)


def test_update_cues_real_timeout_confirmed_by_after_read() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "flagged": False}},
        timeout_set_property=(cue_id, "flagged"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"flagged": True}}], dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 1
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert result["results"][0]["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][0]["executed_operations"][0]["status"] == "timeout_pending_verification"
    assert result["results"][0]["after"]["flagged"] is True


def test_update_cues_many_setter_timeouts_are_bounded_and_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(write_operations, "UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS", 0.001)
    monkeypatch.setattr(write_operations, "UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS", 0.012)
    monkeypatch.setattr(write_operations, "UPDATE_AFTER_READ_TIMEOUT_CAP_SECONDS", 0.01)
    cues = {
        f"{index:08d}-1111-4111-8111-111111111111": {
            "type": "Memo",
            "flagged": False,
            "colorName": "none",
        }
        for index in range(12)
    }
    timeout_properties = {
        (cue_id, prop)
        for cue_id in cues
        for prop in ("flagged", "colorName")
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", timeout=5.0),
        cues=cues,
        timeout_set_properties=timeout_properties,
        delay_on_timeout=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    started = time.monotonic()
    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"flagged": True, "colorName": "blue"}}
            for cue_id in cues
        ],
        dry_run=False,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 12
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 12
    assert all(item["status"] == "updated_with_confirmed_timeouts" for item in result["results"])
    assert all(
        operation["status"] == "timeout_pending_verification"
        for item in result["results"]
        for operation in item["executed_operations"]
    )
    assert all(item["after"]["flagged"] is True and item["after"]["colorName"] == "blue" for item in result["results"])
    setter_timeouts = [
        timeout
        for (address, _, _), timeout in zip(client.requests, client.reply_timeouts, strict=True)
        if "/cue_id/" in address and not address.endswith("/valuesForKeys")
    ]
    assert setter_timeouts
    assert max(timeout for timeout in setter_timeouts if timeout is not None) <= 0.001


def test_update_cues_confirmed_timeouts_do_not_count_as_failures_across_batch() -> None:
    clean_id = "11111111-1111-4111-8111-111111111111"
    timeout_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            clean_id: {"type": "Memo", "name": "Old clean"},
            timeout_id: {"type": "Memo", "name": "Old timeout"},
        },
        timeout_set_property=(timeout_id, "name"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": clean_id, "properties": {"name": "New clean"}},
            {"cue_ref": timeout_id, "properties": {"name": "New timeout"}},
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert [item["status"] for item in result["results"]] == ["updated", "updated_with_confirmed_timeouts"]
    assert result["warnings"]


def test_update_cues_unconfirmed_timeout_counts_as_failure(
    no_after_read_retry_delay: None,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "flagged": False}},
        timeout_set_property=(cue_id, "flagged"),
        timeout_without_apply=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"flagged": True}}], dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["updated_count"] == 0
    assert result["failed_count"] == 1
    assert result["timeout_confirmed_count"] == 0
    assert result["results"][0]["status"] == "partial_failed"
    assert "flagged" in result["results"][0]["errors"]


def test_update_cues_timed_out_setter_without_after_confirmation_reports_property(
    no_after_read_retry_delay: None,
) -> None:
    confirmed_id = "11111111-1111-4111-8111-111111111111"
    unconfirmed_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            confirmed_id: {"type": "Memo", "colorName": "none"},
            unconfirmed_id: {"type": "Memo", "colorName": "none"},
        },
        timeout_set_properties={(confirmed_id, "colorName"), (unconfirmed_id, "colorName")},
        timeout_without_apply_properties={(unconfirmed_id, "colorName")},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": confirmed_id, "properties": {"colorName": "blue"}},
            {"cue_ref": unconfirmed_id, "properties": {"colorName": "green"}},
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["updated_count"] == 1
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][1]["status"] == "partial_failed"
    assert result["results"][1]["after"]["colorName"] == "none"
    assert "colorName" in result["results"][1]["errors"]


def test_update_cues_retries_after_read_for_late_timeout_application(
    no_after_read_retry_delay: None,
) -> None:
    cues = {
        f"{index:08d}-1111-4111-8111-111111111111": {"type": "Memo", "name": f"Old {index}"}
        for index in range(30)
    }
    timeout_id = list(cues)[17]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        timeout_set_property=(timeout_id, "name"),
        timeout_apply_after_reads=3,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"name": f"[CODEX30] {index}"}}
            for index, cue_id in enumerate(cues)
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 30
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert result["results"][17]["status"] == "updated_with_confirmed_timeouts"


def test_update_cues_after_read_mismatch_reports_requested_and_after_values(
    no_after_read_retry_delay: None,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old"}},
        ignore_set_property=(cue_id, "name"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"name": "New"}}], dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert result["updated_count"] == 0
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "verification_failed"
    assert result["error_code"] == "QLAB_UPDATE_VERIFICATION_FAILED"
    assert "compare requested versus after" in result["suggested_action"]
    assert "requested" in result["results"][0]["errors"]["verification"]
    assert "after" in result["results"][0]["errors"]["verification"]


def test_update_cues_verification_accepts_numeric_normalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "duration": 1.0, "allowsEditingDuration": True}},
        ignore_set_property=(cue_id, "duration"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"duration": 1}}], dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_verification_accepts_qlab_float_precision() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Audio", "rate": 1.0099999904632568, "startTime": 0.10000000149011612}},
        ignore_set_property=(cue_id, "rate"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "properties": {"rate": 1.01, "startTime": 0.1},
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_verification_accepts_continue_mode_labels() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "continueMode": "auto_continue"}},
        ignore_set_property=(cue_id, "continueMode"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"continueMode": "auto_continue"}}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_verification_accepts_safe_enum_string_normalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "colorName": "RED"}},
        ignore_set_property=(cue_id, "colorName"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "properties": {"colorName": "red"},
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_mixed_clean_confirmed_timeout_and_real_error_counts_only_error() -> None:
    clean_id = "11111111-1111-4111-8111-111111111111"
    timeout_id = "22222222-2222-4222-8222-222222222222"
    error_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            clean_id: {"type": "Memo", "name": "Old clean"},
            timeout_id: {"type": "Memo", "flagged": False},
            error_id: {"type": "Memo", "armed": True},
        },
        timeout_set_property=(timeout_id, "flagged"),
        fail_set_property=(error_id, "armed"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": clean_id, "properties": {"name": "New clean"}},
            {"cue_ref": timeout_id, "properties": {"flagged": True}},
            {"cue_ref": error_id, "properties": {"armed": False}},
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["error_code"] == "QLAB_UPDATE_PARTIAL_FAILED"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 1
    assert result["timeout_confirmed_count"] == 1
    assert [item["status"] for item in result["results"]] == [
        "updated",
        "updated_with_confirmed_timeouts",
        "partial_failed",
    ]
    assert "armed" in result["results"][2]["errors"]


def test_update_cues_real_reports_partial_failure_during_execution() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "armed": True}},
        fail_set_property=(cue_id, "armed"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"name": "New", "armed": False}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["failed_count"] == 1
    assert [operation["property"] for operation in result["results"][0]["executed_operations"]] == ["name"]
    assert "armed" in result["results"][0]["errors"]
    assert result["results"][0]["after"]["name"] == "New"


def test_update_cue_rejects_ambiguous_refs_and_bad_properties_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="concrete cue"):
        reader.update_cue("ws-1", "selected", {"name": "Nope"}, dry_run=True)

    planned = reader.update_cue("ws-1", "1", {"fileTarget": "/tmp/nope.wav"}, dry_run=True)
    assert planned["ok"] is True
    assert planned_setters(planned)["fileTarget"]["capability_gate"] == "file_target_access"

    with pytest.raises(UnsafeWriteOperationError, match="gated or dry-run only"):
        reader.update_cue("ws-1", "1", {"fileTarget": "/tmp/nope.wav"}, dry_run=False)


def test_update_cue_rejects_file_target_symlink_escape(tmp_path: Any) -> None:
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    target = outside_root / "secret.wav"
    target.write_text("secret")
    symlink_path = allowed_root / "linked.wav"
    symlink_path.symlink_to(target)
    client = FakeWriteClient(
        QLabConfig(
            enable_write=True,
            passcode="server-pass",
            allowed_file_roots=(str(allowed_root),),
        ),
        existing_cue_id="11111111-1111-4111-8111-111111111111",
        cue_values={
            "uniqueID": "11111111-1111-4111-8111-111111111111",
            "number": "1",
            "name": "Audio",
            "displayName": "1 Audio",
            "type": "Audio",
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, "1", {"properties": {"fileTarget": str(symlink_path)}})

    with pytest.raises(UnsafeWriteOperationError, match="outside QLAB_ALLOWED_FILE_ROOTS"):
        reader.update_cue(
            "ws-1",
            "1",
            {"fileTarget": str(symlink_path)},
            dry_run=False,
            confirm_gates=[token],
        )


def test_update_cue_audio_basic_dry_run_allows_small_audio_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"rate": 1.25, "startTime": 1, "endTime": 9, "preservePitch": False},
        dry_run=True,
        profile="audio_basic",
    )

    planned_setters = [
        operation["property"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["profile"] == "audio_basic"
    assert planned_setters == ["rate", "startTime", "endTime", "preservePitch"]
    assert result["executed_operations"] == []
    assert "updateq_plan" not in result


def test_update_cue_audio_last_slice_properties_dry_run_reads_before_and_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "lastSlicePlayCount": 1,
            "lastSliceInfiniteLoop": False,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "properties": {"lastSlicePlayCount": -1, "lastSliceInfiniteLoop": True},
            }
        ],
        dry_run=True,
    )

    item = result["results"][0]
    setters = [operation for operation in item["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert item["before"]["lastSlicePlayCount"] == 1
    assert item["before"]["lastSliceInfiniteLoop"] is False
    assert [setter["property"] for setter in setters] == ["lastSlicePlayCount", "lastSliceInfiniteLoop"]
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert item["executed_operations"] == []


def test_update_cues_audio_last_slice_invalid_values_have_no_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Audio", "lastSlicePlayCount": 1, "lastSliceInfiniteLoop": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "audio_basic", "properties": {"lastSlicePlayCount": 0}},
            {"cue_ref": cue_id, "profile": "audio_basic", "properties": {"lastSliceInfiniteLoop": "banana"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "lastSlicePlayCount must be a positive integer or -1" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "lastSliceInfiniteLoop must be a boolean" in result["results"][1]["errors"]["validation"]
    assert result["results"][1]["planned_operations"] == []


def test_update_cue_audio_basic_real_updates_and_verifies() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
        timeout_set_property="rate",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"rate": 1.25}, dry_run=False, profile="audio_basic")

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == "audio_basic"
    assert result["before"]["rate"] == 1.0
    assert result["after"]["rate"] == 1.25
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"


def test_update_cue_audio_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="rate"):
        reader.update_cue("ws-1", "1", {"rate": 0.01}, dry_run=True, profile="audio_basic")

    with pytest.raises(UnsafeWriteOperationError, match="endTime"):
        reader.update_cue(
            "ws-1",
            "1",
            {"startTime": 5, "endTime": 5},
            dry_run=True,
            profile="audio_basic",
        )

    with pytest.raises(UnsafeWriteOperationError, match="infiniteLoop"):
        reader.update_cue(
            "ws-1",
            "1",
            {"infiniteLoop": True, "playCount": 2},
            dry_run=True,
            profile="audio_basic",
        )

    assert client.requests == []


def test_update_cue_audio_basic_rejects_non_audio_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "rate": 1.0},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Audio cue"):
        reader.update_cue("ws-1", cue_id, {"rate": 1.2}, dry_run=False, profile="audio_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/rate" not in addresses


def test_update_cue_text_basic_dry_run_allows_small_text_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    updates = {
        "text": "New title",
        "fixedWidth": 640,
        "text/format/alignment": "center",
        "text/format/fontName": "Courier New",
        "text/format/fontSize": 56,
    }
    for property_name, value in updates.items():
        result = reader.update_cue(
            "ws-1", cue_id, {property_name: value}, dry_run=True, profile="text_basic"
        )
        assert result["ok"] is True
        assert list(planned_setters(result)) == [property_name]
        assert result["executed_operations"] == []


def test_update_cue_text_font_name_real_write_is_blocked_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
        timeout_set_property="text/format/fontName",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Phase 3E confirm_token"):
        reader.update_cue(
            "ws-1",
            cue_id,
            {"text/format/fontName": "Courier New"},
            dry_run=False,
            profile="text_basic",
        )

    assert client.requests == []


def test_update_cue_text_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="alignment"):
        reader.update_cue("ws-1", "1", {"text/format/alignment": "middle"}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontSize"):
        reader.update_cue("ws-1", "1", {"text/format/fontSize": 0}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontName"):
        reader.update_cue("ws-1", "1", {"text/format/fontName": ""}, dry_run=True, profile="text_basic")

    assert client.requests == []


def test_update_cue_video_opacity_uses_qlab_unit_interval() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="opacity must be a number from 0 to 1"):
        reader.update_cue("ws-1", "1", {"opacity": 80}, dry_run=True, profile="video_basic")

    assert client.requests == []


def test_video_phase2c_gate_vectors_doc_preserves_non_mutating_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    doc_path = repo_root / "docs/current/video_phase2c_gate_test_vectors.md"
    if not doc_path.exists():
        doc_path = repo_root / "docs/archive/video/video_phase2c_gate_test_vectors.md"
    doc = doc_path.read_text()

    for required in (
        "No token generation.",
        "No token validation.",
        "No setters.",
        "No real writes.",
        "No runtime QLab.",
        "No `real_write_possible=true`.",
        "No change to current Phase 2 behavior.",
        "`cue_id` | Canonical QLab cue `uniqueID`.",
        "`cue_ref` | Original request reference. Phase 3A still requires UUID-only refs",
        "`reject_opacity_out_of_range`",
        "`reject_opacity_non_finite`",
        "Setter timeout plus readback matches requested value within tolerance: confirmed success with warning.",
        "Setter timeout plus missing or mismatched readback: uncertain failure; no mutating retry.",
        "Video/Camera/Text Phase 2 dry-runs emit no `confirm_token`.",
        "`real_write_possible=false`.",
        "`requires_confirm_token=false`.",
        "`executed_operations=[]`.",
    ):
        assert required in doc


def test_camera_phase2_non_gated_property_emits_no_token_and_fabricated_token_cannot_unlock_real_write() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Camera", "clockType": "video"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    dry_run = reader.update_cue(
        "ws-1", cue_id, {"clockType": "audio"}, dry_run=True, profile="camera_basic"
    )
    setter = planned_setters(dry_run)["clockType"]
    assert_no_confirm_token(dry_run)
    assert "confirm_token" not in setter
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    client.requests.clear()

    real_attempt = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "camera_basic",
                "properties": {"clockType": "audio"},
                "confirm_gates": ["confirm:clockType:fabricated"],
            }
        ],
        dry_run=False,
    )

    assert real_attempt["ok"] is False
    assert "no confirm_token can authorize" in real_attempt["results"][0]["errors"]["clockType"]
    assert_no_confirm_token(real_attempt)
    assert real_attempt["results"][0]["planned_operations"] == []
    assert real_attempt["results"][0]["executed_operations"] == []
    assert client.requests == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "properties", "operations"),
    [
        ("video_basic", "Video", "fileTarget", {"fileTarget": "/tmp/video.mov"}, None),
        (
            "video_basic",
            "Video",
            "translation",
            None,
            [{"property": "translation", "args": {"x": 1, "y": 2}}],
        ),
        ("video_basic", "Video", "stage/name", {"stage/name": "Stage 2"}, None),
        ("camera_basic", "Camera", "cameraPatch", {"cameraPatch": 1}, None),
        (
            "text_basic",
            "Text",
            "text/format",
            None,
            [{"property": "text/format", "args": {"format": {"fontName": "Helvetica"}}}],
        ),
        (
            "text_basic",
            "Text",
            "text/format/shadowOffset",
            None,
            [{"property": "text/format/shadowOffset", "args": {"width": 1, "height": 2}}],
        ),
        (
            "camera_basic",
            "Camera",
            "videoInputPatchName",
            {"videoInputPatchName": "Patch 1"},
            None,
        ),
        (
            "camera_basic",
            "Camera",
            "videoInputPatchNumber",
            {"videoInputPatchNumber": 1},
            None,
        ),
        (
            "video_basic",
            "Video",
            "videoEffects/add",
            None,
            [{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffects/insert",
            None,
            [{"property": "videoEffects/insert", "args": {"name": "ColorControls", "index": 0}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/delete",
            None,
            [{"property": "videoEffect/delete", "args": {"name": "ColorControls"}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/delete",
            None,
            [{"property": "videoEffectIndex/delete", "args": {"index": 0}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/move",
            None,
            [{"property": "videoEffect/move", "args": {"name": "ColorControls", "newIndex": 1}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/move",
            None,
            [{"property": "videoEffectIndex/move", "args": {"index": 0, "newIndex": 1}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/enabled",
            None,
            [{"property": "videoEffect/enabled", "args": {"name": "ColorControls", "value": True}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/enabled",
            None,
            [{"property": "videoEffectIndex/enabled", "args": {"index": 0, "value": True}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/parameter",
            None,
            [
                {
                    "property": "videoEffect/parameter",
                    "args": {"name": "ColorControls", "parameterKey": "inputBrightness", "setting": 0.5},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/parameter",
            None,
            [
                {
                    "property": "videoEffectIndex/parameter",
                    "args": {"index": 0, "parameterKey": "inputBrightness", "setting": 0.5},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/parameters",
            None,
            [
                {
                    "property": "videoEffect/parameters",
                    "args": {"name": "ColorControls", "parameters": {"inputBrightness": 0.5}},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/parameters",
            None,
            [
                {
                    "property": "videoEffectIndex/parameters",
                    "args": {"index": 0, "parameters": {"inputBrightness": 0.5}},
                }
            ],
        ),
    ],
)
def test_video_phase2_dry_run_rejects_explicitly_blocked_families_before_osc(
    profile: str,
    cue_type: str,
    property_name: str,
    properties: dict[str, Any] | None,
    operations: list[dict[str, Any]] | None,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": cue_type, "videoEffects": []},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    result = reader.update_cue(
        "ws-1",
        cue_id,
        properties,
        dry_run=True,
        profile=profile,
        operations=operations,
    )

    assert result["ok"] is False
    assert result["status"] == "dry_run_preflight_failed"
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)
    if property_name in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES:
        assert "effect" in result["errors"][property_name].casefold()
        assert any(address.endswith("/valuesForKeys") for address, _, _ in client.requests)
    else:
        assert "blocked even for dry-run by Video-family policy" in result["errors"][property_name]
        assert client.requests == []


@pytest.mark.parametrize(
    ("cue_state", "error_key"),
    [
        ({"isBroken": True}, "health"),
        ({"isWarning": True}, "health"),
        ({"isRunning": True}, "active"),
        ({"isPaused": True}, "active"),
        ({"isAuditioning": True}, "active"),
    ],
)
def test_video_phase2_dry_run_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any], error_key: str
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1, **cue_state},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1", cue_id, {"opacity": 0.8}, dry_run=True, profile="video_basic"
    )

    assert result["ok"] is False
    assert error_key in result["errors"]
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)


def test_video_phase2_disarmed_cue_is_notice_not_blocker() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "scale/x": 1, "armed": False},
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1", cue_id, {"scale/x": 0.8}, dry_run=True, profile="video_basic"
    )

    assert result["ok"] is True
    assert result["notices"] == ["cue_disarmed"]
    assert result["executed_operations"] == []
    assert result["updateq_plan"]["notices"] == ["cue_disarmed"]
    assert "playback readiness" in result["updateq_plan"]["notice_explanations"]["cue_disarmed"]
    assert result["updateq_plan"]["safety"]["will_modify_qlab"] is False
    setter = planned_setters(result)["scale/x"]
    assert setter["confirm_token"].startswith("confirm:videoScalar:v1:")
    assert setter["real_write_possible"] is True


def _phase3_opacity_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    baseline: float = 1.0,
    requested: float = 0.8,
    ignore_readback: bool = False,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "opacity": baseline}},
        ignore_set_property=(cue_id, "opacity") if ignore_readback else None,
        timeout_set_property=(cue_id, "opacity") if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": profile, "properties": {"opacity": requested}}
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


class _FakeMonotonicClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_real_update_preflight_budget_exhaustion_sends_no_setter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    clock = _FakeMonotonicClock()
    original_read = write_operations._try_read_update_values
    preflight_timeouts: list[float | None] = []

    def consume_preflight_budget(
        reader_arg: Any,
        workspace_id: str,
        cue_ref: str,
        read_keys: list[str],
        *,
        request_timeout: float | None = None,
    ) -> tuple[dict[str, Any] | None, dict[str, str]]:
        preflight_timeouts.append(request_timeout)
        result = original_read(
            reader_arg,
            workspace_id,
            cue_ref,
            read_keys,
            request_timeout=request_timeout,
        )
        clock.advance(1.0)
        return result

    monkeypatch.setattr(write_operations.time, "monotonic", clock)
    monkeypatch.setattr(write_operations, "UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS", 1.0)
    monkeypatch.setattr(write_operations, "_try_read_update_values", consume_preflight_budget)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    setter_address = f"/workspace/ws-1/cue_id/{cue_id}/opacity"
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["read_before"] == (
        "Global update time budget exhausted during fresh preflight; no setter was sent."
    )
    assert preflight_timeouts == [pytest.approx(0.5)]
    assert not any(address == setter_address for address, _, _ in client.requests)


def test_real_update_preflight_shares_one_deadline_across_fifty_cues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cue_ids = [
        f"00000000-0000-4000-8000-{index:012d}"
        for index in range(50)
    ]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {"type": "Memo", "name": f"Cue {index}"}
            for index, cue_id in enumerate(cue_ids)
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    clock = _FakeMonotonicClock()
    original_read = write_operations._try_read_update_values
    preflight_timeouts: list[float | None] = []

    def consume_shared_budget(*args: Any, request_timeout: float | None = None, **kwargs: Any):
        preflight_timeouts.append(request_timeout)
        result = original_read(*args, request_timeout=request_timeout, **kwargs)
        clock.advance(0.03)
        return result

    monkeypatch.setattr(write_operations.time, "monotonic", clock)
    monkeypatch.setattr(write_operations, "UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS", 0.1)
    monkeypatch.setattr(write_operations, "_try_read_update_values", consume_shared_budget)

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"name": f"Updated {index}"}}
            for index, cue_id in enumerate(cue_ids)
        ],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert len(preflight_timeouts) == 4
    assert preflight_timeouts == sorted(preflight_timeouts, reverse=True)
    assert not any(
        address.endswith("/name")
        for address, *_ in client.requests
    )


def test_real_update_uses_fresh_verification_budget_after_setter_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    clock = _FakeMonotonicClock()
    original_request = client.request
    setter_address = f"/workspace/ws-1/cue_id/{cue_id}/opacity"

    def consume_remaining_budget_after_setter(
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        reply = original_request(
            address,
            *args,
            workspace_id=workspace_id,
            reply_timeout=reply_timeout,
        )
        if address == setter_address:
            clock.advance(1.0)
        return reply

    monkeypatch.setattr(write_operations.time, "monotonic", clock)
    monkeypatch.setattr(write_operations, "UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS", 1.0)
    monkeypatch.setattr(client, "request", consume_remaining_budget_after_setter)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["opacity"] == 0.8
    assert [address for address, _, _ in client.requests].count(setter_address) == 1
    assert client.reply_timeouts[-1] == pytest.approx(0.5)


def test_execution_guard_blocks_every_non_allowlisted_live_route() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    item = write_operations._normalize_batch_update_item_for_batch(
        {"cue_ref": cue_id, "properties": {"name": "New"}}
    )
    item["operations"][0].update(mode="live", path="name/live")
    planned = write_operations._batch_item_result(
        "ws-1",
        item,
        cue_id=cue_id,
        status="planned",
        before={"uniqueID": cue_id, "type": "Memo", "name": "Old"},
        after=None,
        errors=None,
        warnings=[],
    )

    result = write_operations._execute_and_verify_update_batch(
        reader,
        "ws-1",
        [item],
        [planned],
        time.monotonic() + write_operations.UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS,
        0.1,
        shared_read_cache(),
        requested_count=1,
    )

    assert result["results"][0]["errors"]["name"] == (
        "Live writes are blocked except for secondColorName."
    )
    assert not any(address.endswith("/name/live") for address, *_ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase3a_opacity_dry_run_candidate_emits_confirm_token(profile: str, cue_type: str) -> None:
    client, reader, cue_id, update, _ = _phase3_opacity_fixture(profile=profile, cue_type=cue_type)
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["opacity"]
    payload, error = video_opacity._decode_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["phase3_video_opacity_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"] == "video_opacity_requires_confirm_token"
    assert setter["confirm_token"].startswith("confirm:videoOpacity:v1:")
    assert plan["results"][0]["updateq_plan"]["real_write_possible"] is True
    assert plan["results"][0]["updateq_plan"]["requires_confirm_token"] is True
    assert plan["results"][0]["updateq_plan"]["intent"] == (
        f"Preview saved opacity change on {cue_type} cue."
    )
    assert plan["results"][0]["updateq_plan"]["safety"]["no_executed_operations"] is True
    assert plan["results"][0]["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert plan["results"][0]["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3_opacity_write"
    assert payload["cue_id"] == cue_id
    assert payload["cue_ref"] == cue_id
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == "opacity"
    assert payload["mode"] == "saved"
    assert payload["baseline"] == 1.0
    assert payload["requested"] == 0.8
    assert payload["risk_tier"] == "high"
    assert payload["capability_gate"] == "video_visual"
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase3a_opacity_real_write_with_token_sets_once_and_verifies(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture(
        profile=profile,
        cue_type=cue_type,
    )

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    address = f"/workspace/ws-1/cue_id/{cue_id}/opacity"
    item = result["results"][0]
    setter = planned_setters(item)["opacity"]
    plan = item["updateq_plan"]
    assert result["status"] == "updated"
    assert item["after"]["opacity"] == 0.8
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["operations"][0]["real_write_enabled"] is True
    assert item["operations"][0]["real_write_possible"] is True
    assert item["operations"][0]["requires_confirm_token"] is True
    assert "planned_only_reason" not in item["operations"][0]
    assert plan["status"] == "updated"
    assert plan["real_write_enabled"] is True
    assert plan["real_write_possible"] is True
    assert plan["requires_confirm_token"] is True
    assert plan["intent"] == f"Executed saved opacity change on {cue_type} cue."
    assert "why_not_written" not in plan
    assert plan["safety"]["no_executed_operations"] is False
    assert plan["safety"]["will_modify_qlab"] is True
    assert plan["safety"]["no_live"] is True
    assert plan["safety"]["no_playback"] is True
    assert plan["safety"]["no_workspace_video_write"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any(
        forbidden in address.casefold()
        for address, _, _ in client.requests
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview", "/live")
    )


def test_phase3a_opacity_token_cannot_authorize_other_value_workspace_or_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"opacity": 0.7}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    wrong_workspace_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        workspace_id="ws-2",
    )
    wrong_workspace = QLabReader(wrong_workspace_client).update_cues(  # type: ignore[arg-type]
        "ws-2", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.cues[cue_id]["opacity"] = 0.9
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_workspace["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_video_opacity_baseline" in stale["results"][0]["errors"]["opacity"]
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)
    assert not any(address.endswith("/opacity") for address, _, _ in wrong_workspace_client.requests)


@pytest.mark.parametrize("token_mutator", [
    lambda token: "not-a-token",
    lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
    lambda token: token.replace(":v1:", ":v2:", 1),
])
def test_phase3a_opacity_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3_opacity_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


def test_phase3a_opacity_real_attempt_requires_uuid_single_property_and_token() -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    client.cue_numbers["1"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "1", "confirm_gates": [token]}],
        [{**update, "properties": {"opacity": 0.8, "translation/x": 1}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


def test_phase3a_opacity_setter_timeout_with_matching_readback_is_updated_warning() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        timeout_set_property=(cue_id, "opacity"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    item = result["results"][0]
    setter = planned_setters(item)["opacity"]
    assert item["status"] == "updated"
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["verification"]["readback_matched"] is True
    assert item["updateq_plan"]["safety"]["no_executed_operations"] is False
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert item["executed_operations"][0]["status"] == "timeout_pending_verification"


def test_phase3a_opacity_setter_timeout_mismatch_is_uncertain_failure_no_retry(
    no_after_read_retry_delay: None,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        timeout_set_property=(cue_id, "opacity"),
        timeout_without_apply=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "partial_failed"
    assert result["timeout_confirmed_count"] == 0
    assert result["results"][0]["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/opacity")]) == 1


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), float("-inf")])
def test_phase3a_opacity_rejects_out_of_range_and_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    reader = QLabReader(  # type: ignore[arg-type]
        FakeWriteClient(
            QLabConfig(enable_write=False, passcode=None),
            existing_cue_id=cue_id,
            cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1},
        )
    )

    with pytest.raises(UnsafeWriteOperationError, match="opacity must be a number from 0 to 1"):
        reader.update_cue("ws-1", cue_id, {"opacity": value}, dry_run=True, profile="video_basic")


def _phase3b_translation_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "translation/x",
    baseline: float = 10.0,
    requested: float = 20.0,
    timeout: bool = False,
    timeout_without_apply: bool = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
        ignore_set_property=(cue_id, property_name) if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name"),
    [
        (profile, cue_type, property_name)
        for profile, cue_type in (
            ("video_basic", "Video"),
            ("camera_basic", "Camera"),
            ("text_basic", "Text"),
        )
        for property_name in ("translation/x", "translation/y")
    ],
)
def test_phase3b_translation_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, _ = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = video_translation._decode_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoTranslation:v1:")
    assert setter["phase3b_video_translation_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert item["updateq_plan"]["real_write_possible"] is True
    assert item["updateq_plan"]["requires_confirm_token"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert payload == {
        "version": 1,
        "operation_kind": "video_phase3b_translation_write",
        "workspace_id": "ws-1",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "cue_type": cue_type,
        "profile": profile,
        "property": property_name,
        "path": property_name,
        "mode": "saved",
        "baseline": 10.0,
        "baseline_sha256": video_translation._sha256(10.0),
        "requested": 20.0,
        "risk_tier": "high",
        "capability_gate": "video_visual",
        "mcp_secret_version": 1,
    }
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name"),
    [
        (profile, cue_type, property_name)
        for profile, cue_type in (
            ("video_basic", "Video"),
            ("camera_basic", "Camera"),
            ("text_basic", "Text"),
        )
        for property_name in ("translation/x", "translation/y")
    ],
)
def test_phase3b_translation_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    plan = item["updateq_plan"]
    assert result["status"] == "updated"
    assert item["after"][property_name] == 20.0
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert plan["status"] == "updated"
    assert plan["real_write_enabled"] is True
    assert plan["real_write_possible"] is True
    assert plan["requires_confirm_token"] is True
    assert plan["intent"] == f"Executed saved {property_name} change on {cue_type} cue."
    assert plan["safety"]["no_executed_operations"] is False
    assert plan["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3b_translation_token_rejects_context_mismatch_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"translation/x": 21.0}, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_axis = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "properties": {"translation/y": 20.0},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )
    client.cues[cue_id]["translation/x"] = 11.0
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_workspace_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "translation/x": 10.0}},
        workspace_id="ws-2",
    )
    wrong_workspace = QLabReader(wrong_workspace_client).update_cues(  # type: ignore[arg-type]
        "ws-2",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_axis["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert wrong_workspace["status"] == "preflight_failed"
    assert "stale_video_translation_baseline" in stale["results"][0]["errors"]["translation/x"]
    assert not any(
        address.endswith(("/translation/x", "/translation/y"))
        for address, _, _ in client.requests
    )
    assert not any(
        address.endswith("/translation/x")
        for address, _, _ in wrong_workspace_client.requests
    )


def test_phase3b_translation_token_rejects_wrong_cue_profile_and_type() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    other_cue_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_cue_id] = {
        "uniqueID": other_cue_id,
        "type": "Video",
        "translation/x": 10.0,
    }
    wrong_cue = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": other_cue_id, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_profile = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_cue["status"] == "preflight_failed"
    assert wrong_profile["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert all(
        item["executed_operations"] == []
        for result in (wrong_cue, wrong_profile, wrong_type)
        for item in result["results"]
    )
    assert not any(
        address.endswith("/translation/x")
        for address, _, _ in client.requests
    )


def test_phase3b_translation_token_is_bound_to_camera_type_and_profile() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture(
        profile="camera_basic",
        cue_type="Camera",
    )
    client.cues[cue_id]["type"] = "Text"

    result = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "profile": "text_basic",
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert "does not match" in result["results"][0]["errors"]["translation/x"]
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3b_translation_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3b_translation_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


def test_phase3b_translation_real_attempt_requires_video_uuid_single_saved_property() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [
            {
                **update,
                "properties": {"translation/x": 20.0, "translation/y": 30.0},
                "confirm_gates": [token],
            }
        ],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {
                        "property": "translation/x",
                        "args": {"value": 20.0},
                        "mode": "live",
                    }
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3b_translation_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_phase3b_translation_rejects_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "translation/x": 10.0}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "properties": {"translation/x": value},
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3b_translation_setter_timeout_matching_readback_is_updated_warning(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        timeout=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["verification"]["readback_matched"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True


def test_phase3b_translation_setter_timeout_mismatch_is_uncertain_no_retry(
    no_after_read_retry_delay: None,
) -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert result["timeout_confirmed_count"] == 0
    assert len(
        [address for address, _, _ in client.requests if address.endswith("/translation/x")]
    ) == 1


def test_phase3b_translation_normal_setter_readback_mismatch_fails_without_retry() -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(ignore_readback=True)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "verification_failed"
    assert len(
        [address for address, _, _ in client.requests if address.endswith("/translation/x")]
    ) == 1


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3b_translation_rollback_requires_new_token(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, forward_token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"translation/x": 10.0}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["translation/x"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["translation/x"] == 10.0


PHASE3C_SCALAR_CASES = [
    (profile, cue_type, property_name)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name in (
        "scale/x",
        "scale/y",
        "anchor/x",
        "anchor/y",
        "cropTop",
        "cropBottom",
        "cropLeft",
        "cropRight",
    )
]


def _phase3c_scalar_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "scale/x",
    baseline: float = 1.0,
    requested: float = 1.25,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("profile", "cue_type", "property_name"), PHASE3C_SCALAR_CASES)
def test_phase3c_scalar_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, _ = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = video_scalars._decode_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoScalar:v1:")
    assert setter["phase3c_video_scalar_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert payload["operation_kind"] == "video_phase3c_scalar_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["path"] == property_name
    assert payload["baseline"] == 1.0
    assert payload["requested"] == 1.25
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("profile", "cue_type", "property_name"), PHASE3C_SCALAR_CASES)
def test_phase3c_scalar_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    assert result["status"] == "updated"
    assert item["after"][property_name] == 1.25
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3c_scalar_token_rejects_wrong_property_type_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    wrong_property = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"scale/y": 1.25}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Video"
    client.cues[cue_id]["scale/x"] = 1.1
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_property["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    stale_item = stale["results"][0]
    assert "stale_video_scalar_baseline" in stale_item["errors"]["scale/x"]
    assert stale_item["operations"][0]["planned_only_reason"] == "video_scalar_requires_confirm_token"
    assert "Video Phase 2" not in stale_item["updateq_plan"]["intent"]
    assert not any(address.endswith(("/scale/x", "/scale/y")) for address, _, _ in client.requests)


def test_phase3c_scalar_token_cannot_cross_camera_and_text() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture(
        profile="camera_basic",
        cue_type="Camera",
    )
    client.cues[cue_id]["type"] = "Text"

    result = reader.update_cues(
        "ws-1",
        [{**update, "profile": "text_basic", "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3c_scalar_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


def test_phase3c_scalar_real_attempt_requires_uuid_single_saved_property() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [
            {
                **update,
                "properties": {"scale/x": 1.25, "scale/y": 1.25},
                "confirm_gates": [token],
            }
        ],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "scale/x", "args": {"value": 1.25}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3c_scalar_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_phase3c_scalar_rejects_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "scale/x": 1.0}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "properties": {"scale/x": value},
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3c_scalar_timeout_matching_readback_is_updated_warning(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        timeout=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["verification"]["readback_matched"] is True


def test_phase3c_scalar_timeout_mismatch_is_uncertain_no_retry(
    no_after_read_retry_delay: None,
) -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/scale/x")]) == 1


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3c_scalar_rollback_requires_new_token(profile: str, cue_type: str) -> None:
    client, reader, _, update, forward_token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"scale/x": 1.0}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["scale/x"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["scale/x"] == 1.0


PHASE3D_APPEARANCE_CASES = [
    (profile, cue_type, property_name, baseline, requested)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name, baseline, requested in (
        ("blendMode", "Normal", "Multiply"),
        ("preserveAspectRatio", True, False),
    )
]


def test_phase3d_appearance_operation_detection_precedes_profile_validation() -> None:
    appearance_operation = {
        "property": "blendMode",
        "path": "blendMode",
        "mode": "saved",
    }
    item = {
        "cue_ref": "11111111-1111-4111-8111-111111111111",
        "profile": "audio_basic",
        "operations": [appearance_operation],
    }

    assert video_appearance.operation(item) is appearance_operation
    assert video_appearance.call_structure_error([item]) == (
        "Phase 3D appearance real writes require video_basic, camera_basic, or text_basic profile."
    )


OFFICIAL_BLEND_MODE_NAMES = [
    "Normal",
    "Darken",
    "Multiply",
    "Color Burn",
    "Linear Burn",
    "Lighten",
    "Screen",
    "Color Dodge",
    "Linear Dodge",
    "Overlay",
    "Soft Light",
    "Hard Light",
    "Pin Light",
    "Difference",
    "Exclusion",
    "Subtract",
    "Divide",
    "Hue",
    "Saturation",
    "Color",
    "Luminosity",
    "Addition Compositing",
    "Maximum Compositing",
    "Source Atop Compositing",
]


def test_phase3d_blend_mode_allows_official_full_name_strings_only() -> None:
    assert list(QLAB_BLEND_MODES.values()) == OFFICIAL_BLEND_MODE_NAMES

    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    for mode in OFFICIAL_BLEND_MODE_NAMES:
        valid = reader.update_cues(
            "ws-1",
            [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": mode}}],
            dry_run=True,
        )
        assert valid["status"] == "dry_run"
        assert valid["results"][0]["properties"]["blendMode"] == mode


@pytest.mark.parametrize("bad_value", [1, 1.0, True, False, None, [], {}, "screen", " Screen ", "Scr", "Screen-ish", ""])
def test_phase3d_blend_mode_rejects_non_official_values(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][0]["planned_operations"] == []


def test_phase3d_blend_mode_rejects_old_case_insensitive_canonicalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": " screen "}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def _phase3d_appearance_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "blendMode",
    baseline: Any = "Normal",
    requested: Any = "Multiply",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE3D_APPEARANCE_CASES,
)
def test_phase3d_appearance_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase3d_appearance_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = video_appearance._decode_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAppearance:v1:")
    assert setter["phase3d_video_appearance_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3d_appearance_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE3D_APPEARANCE_CASES,
)
def test_phase3d_appearance_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3d_appearance_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAppearance:v1:fake"]}],
        [{**update, "properties": {"preserveAspectRatio": False}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"blendMode": "Multiply", "opacity": 0.5}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "blendMode", "args": {"value": "Multiply"}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/blendMode", "/preserveAspectRatio")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3d_appearance_tampered_token_rejects_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3d_appearance_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in client.requests)


def test_phase3d_appearance_rejects_wrong_type_profile_cue_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {"type": "Video", "blendMode": "Normal"}
    wrong_cue = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": other_id, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id].update({"type": "Video", "blendMode": "Screen"})
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_cue["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_video_appearance_baseline" in stale["results"][0]["errors"]["blendMode"]
    assert all(
        item["executed_operations"] == []
        for result in (wrong_cue, wrong_type, stale)
        for item in result["results"]
    )


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3d_appearance_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in client.requests)


def test_phase3d_appearance_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase3d_appearance_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"blendMode": "Normal"}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["blendMode"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["blendMode"] == "Normal"


def test_phase3d_appearance_timeout_mismatch_is_uncertain_no_retry(
    no_after_read_retry_delay: None,
) -> None:
    client, reader, _, update, token = _phase3d_appearance_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/blendMode")]) == 1


PHASE7_GEOMETRY_CASES = [
    (profile, cue_type, property_name, baseline, requested)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name, baseline, requested in (
        ("fillStage", False, True),
        ("fillStyle", 0, 1),
        ("layer", 10, 11),
        ("quaternion", [0, 0, 0, 1], [0, 0, 0.1, 0.995]),
        ("smooth", False, True),
    )
]


def _phase7_geometry_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "fillStage",
    baseline: Any = False,
    requested: Any = True,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def _phase7_reset_rotation_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    baseline: list[int | float] | None = None,
    timeout: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    baseline = baseline or [0, 0, 0.1, 0.995]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "quaternion": baseline}},
        timeout_set_property=(cue_id, "resetRotation") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {"resetRotation": True},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["resetRotation"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase3d_blend_mode_token_boundaries_reject_fx_and_geometry_tokens() -> None:
    appearance_client, appearance_reader, _, appearance_update, appearance_token = _phase3d_appearance_fixture()
    _, _, _, _, geometry_token = _phase7_geometry_fixture(property_name="fillStage")

    fx_cue_id = "11111111-1111-4111-8111-111111111111"
    fx_client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            fx_cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    fx_reader = QLabReader(fx_client)  # type: ignore[arg-type]
    fx_update = {
        "cue_ref": fx_cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    fx_plan = fx_reader.update_cues("ws-1", [fx_update], dry_run=True)
    fx_token = planned_setters(fx_plan["results"][0])["videoEffectIndex/parameter"]["confirm_token"]

    for wrong_token in (geometry_token, fx_token):
        result = appearance_reader.update_cues(
            "ws-1",
            [{**appearance_update, "confirm_gates": [wrong_token]}],
            dry_run=False,
        )
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    geometry_client, geometry_reader, _, geometry_update, _ = _phase7_geometry_fixture(property_name="fillStage")
    wrong_family = geometry_reader.update_cues(
        "ws-1",
        [{**geometry_update, "confirm_gates": [appearance_token]}],
        dry_run=False,
    )

    assert wrong_family["status"] == "preflight_failed"
    assert wrong_family["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in appearance_client.requests)
    assert not any(address.endswith("/fillStage") for address, _, _ in geometry_client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE7_GEOMETRY_CASES,
)
def test_phase7_geometry_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase7_geometry_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase7_video_geometry_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    expected_version = (
        4 if property_name == "smooth" else 3 if property_name == "quaternion" else 2 if property_name == "layer" else 1
    )
    assert setter["confirm_token"].startswith(f"confirm:videoGeometry:v{expected_version}:")
    assert setter["phase7_video_geometry_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert setter["args"] == (requested if property_name == "quaternion" else [requested])
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase7_geometry_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["version"] == expected_version
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE7_GEOMETRY_CASES,
)
def test_phase7_geometry_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase7_geometry_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase7_geometry_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase7_geometry_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoGeometry:v1:fake"]}],
        [{**update, "properties": {"fillStyle": 1}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"fillStage": True, "opacity": 0.5}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "fillStage", "args": {"value": True}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/fillStage", "/fillStyle")) for address, _, _ in client.requests)


def test_phase7b_layer_rejects_v1_token_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    layer_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {"layer": 11},
    }

    result = reader.update_cues(
        "ws-1",
        [{**layer_update, "confirm_gates": [v1_token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/layer") for address, _, _ in client.requests)


def test_phase7d_quaternion_rejects_v1_v2_and_v3_cross_tokens_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0, 1]
    quaternion_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {"quaternion": [0, 0, 0.1, 0.995]},
    }
    v3_plan = reader.update_cues("ws-1", [quaternion_update], dry_run=True)
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]

    cases = [
        {**quaternion_update, "confirm_gates": [v1_token]},
        {**quaternion_update, "confirm_gates": [v2_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [v3_token]},
    ]
    client.requests.clear()

    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/quaternion", "/fillStage", "/layer")) for address, _, _ in client.requests)


def test_phase7f_smooth_rejects_old_geometry_tokens_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0, 1]
    v3_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [0, 0, 0.1, 0.995]}}],
        dry_run=True,
    )
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]
    client.cues[cue_id]["smooth"] = False
    smooth_update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": True}}
    v4_plan = reader.update_cues("ws-1", [smooth_update], dry_run=True)
    v4_token = planned_setters(v4_plan["results"][0])["smooth"]["confirm_token"]
    client.requests.clear()

    cases = [
        {**smooth_update, "confirm_gates": [v1_token]},
        {**smooth_update, "confirm_gates": [v2_token]},
        {**smooth_update, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [v4_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [v4_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [0, 0, 0.1, 0.995]}, "confirm_gates": [v4_token]},
    ]
    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/smooth", "/fillStage", "/layer", "/quaternion")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [None, 1, 0, "true", [], {}])
def test_phase7f_smooth_invalid_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "smooth": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/smooth") for address, _, _ in client.requests)


PHASE8_IO_CASES = [
    ("video_basic", "Video", "stageID", "stage-old", "stage-new"),
    ("video_basic", "Video", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("camera_basic", "Camera", "stageID", "stage-old", "stage-new"),
    ("camera_basic", "Camera", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("camera_basic", "Camera", "videoInputPatchID", "video-in-old", "video-in-new"),
    ("camera_basic", "Camera", "audioInputPatchID", "audio-in-old", "audio-in-new"),
    ("text_basic", "Text", "stageID", "stage-old", "stage-new"),
    ("audio_basic", "Audio", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("mic_basic", "Mic", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("mic_basic", "Mic", "audioInputPatchID", "audio-in-old", "audio-in-new"),
]


def _phase8_io_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "stageID",
    baseline: str = "stage-old",
    requested: str = "stage-new",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    audio_output_patches = (
        [{"uniqueID": baseline}, {"uniqueID": requested}]
        if profile in {"audio_basic", "mic_basic"} and property_name == "audioOutputPatchID"
        else []
    )
    audio_input_patches = (
        [{"uniqueID": baseline}, {"uniqueID": requested}]
        if profile == "mic_basic" and property_name == "audioInputPatchID"
        else []
    )
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
        audio_output_patches=audio_output_patches,
        audio_input_patches=audio_input_patches,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("profile", "cue_type", "property_name", "baseline", "requested"), PHASE8_IO_CASES)
def test_phase8a_video_io_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: str,
    requested: str,
) -> None:
    client, reader, cue_id, update, _ = _phase8_io_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase8_video_io_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoIO:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8_io_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert payload["workspace_validation"] == "post_write_fresh_readback_required"
    if profile in {"audio_basic", "mic_basic"} and property_name in {"audioOutputPatchID", "audioInputPatchID"}:
        setting = "audio/patchList" if property_name == "audioOutputPatchID" else "mic/patchList"
        assert "workspace_patch_id_membership" in setter["future_gate_requirements"]
        assert "workspace_id_list_validation_future" not in setter["future_gate_requirements"]
        assert any(
            address == f"/workspace/ws-1/settings/{setting}"
            for address, _, _ in client.requests
        )
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("profile", "cue_type", "property_name", "baseline", "requested"), PHASE8_IO_CASES)
def test_phase8a_video_io_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: str,
    requested: str,
) -> None:
    client, reader, cue_id, update, token = _phase8_io_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": property_name, "value": baseline}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "setting"),
    [
        ("audio_basic", "Audio", "audioOutputPatchID", "audio/patchList"),
        ("mic_basic", "Mic", "audioOutputPatchID", "audio/patchList"),
        ("mic_basic", "Mic", "audioInputPatchID", "mic/patchList"),
    ],
)
def test_phase8a_audio_mic_patch_selection_requires_current_workspace_id(
    profile: str,
    cue_type: str,
    property_name: str,
    setting: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: "patch-old"}},
        audio_output_patches=[{"uniqueID": "patch-old"}],
        audio_input_patches=[{"uniqueID": "patch-old"}],
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: "patch-missing"},
    }

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    item = result["results"][0]
    assert result["status"] == "preflight_failed"
    assert "not a current" in item["errors"][property_name]
    assert item["executed_operations"] == []
    assert_no_confirm_token(result)
    assert any(address == f"/workspace/ws-1/settings/{setting}" for address, _, _ in client.requests)
    assert not any(
        address == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
        for address, _, _ in client.requests
    )


def test_phase8a_audio_mic_patch_selection_revalidates_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8_io_fixture(
        profile="mic_basic",
        cue_type="Mic",
        property_name="audioInputPatchID",
        baseline="input-old",
        requested="input-new",
    )
    client.audio_input_patches = [{"uniqueID": "input-old"}]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    assert result["status"] == "preflight_failed"
    assert "not a current" in item["errors"]["audioInputPatchID"]
    assert item["executed_operations"] == []
    assert any(address == "/workspace/ws-1/settings/mic/patchList" for address, _, _ in client.requests)
    assert not any(
        address == f"/workspace/ws-1/cue_id/{cue_id}/audioInputPatchID"
        for address, _, _ in client.requests
    )


def test_phase8a_video_io_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8_io_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoIO:v1:fake"]}],
        [{**update, "properties": {"stageID": "stage-other"}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"stageID": "stage-new", "smooth": False}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": False}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/stageID", "/smooth")) for address, _, _ in client.requests)


def test_phase8a_audio_and_mic_tokens_are_type_profile_bound() -> None:
    _, _, _, audio_update, audio_token = _phase8_io_fixture(
        profile="audio_basic",
        cue_type="Audio",
        property_name="audioOutputPatchID",
        baseline="audio-out-old",
        requested="audio-out-new",
    )
    mic_client, mic_reader, cue_id, mic_update, _ = _phase8_io_fixture(
        profile="mic_basic",
        cue_type="Mic",
        property_name="audioOutputPatchID",
        baseline="audio-out-old",
        requested="audio-out-new",
    )

    result = mic_reader.edit_cues("ws-1", [{**mic_update, "confirm_gates": [audio_token]}], dry_run=False)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(
        address == f"/workspace/ws-1/cue_id/{cue_id}/audioOutputPatchID"
        for address, _, _ in mic_client.requests
    )


@pytest.mark.parametrize("bad_value", [None, 1, True, "", "none", [], {}])
def test_phase8a_video_io_invalid_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "stageID": "stage-old"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"stageID": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/stageID") for address, _, _ in client.requests)


def test_phase8a_video_io_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase8_io_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**update, "properties": {"stageID": "stage-old"}}
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["stageID"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["stageID"] == "stage-old"


def test_phase8a_stageid_disconnected_stage_warns_but_still_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "stageID": "stage-old"}},
        video_stages=[{"uniqueID": "stage-new", "name": "Stage 2"}],
        video_stage_regions={
            "stage-new": [
                {"name": "A", "route": {"name": "Output 2", "connected": False, "device": {"present": False}}}
            ]
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-new"}}],
        dry_run=True,
    )

    item = result["results"][0]
    setter = planned_setters(item)["stageID"]
    assert result["status"] == "dry_run"
    assert setter["confirm_token"].startswith("confirm:videoIO:v1:")
    assert setter["warning_metadata"]["code"] == "stage_route_disconnected"
    assert "stage_route_disconnected" in item["notices"]
    assert any("currently disconnected" in warning for warning in item["warnings"])


def test_phase8a_stageid_broken_after_write_allows_exact_recovery_rollback_only() -> None:
    write_operations._PHASE8_STAGEID_RECOVERY_BASELINES.clear()
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "stageID": "stage-old", "isBroken": False}},
        broken_stage_ids={"stage-bad"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    forward_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-bad"}}
    forward_plan = reader.edit_cues("ws-1", [forward_update], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["stageID"]["confirm_token"]
    forward = reader.edit_cues("ws-1", [{**forward_update, "confirm_gates": [forward_token]}], dry_run=False)

    wrong_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-third"}}
    wrong = reader.edit_cues("ws-1", [wrong_update], dry_run=True)
    rollback_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-old"}}
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["stageID"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "stageid_write_result_is_broken" in forward["results"][0]["warnings"]
    assert wrong["status"] == "preflight_failed"
    assert wrong["results"][0]["executed_operations"] == []
    assert rollback_plan["status"] == "dry_run"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["stageID"] == "stage-old"
    assert rollback["results"][0]["after"]["isBroken"] is False


PHASE8B_VIDEO_AUDIO_TIME_CASES = [
    ("startTime", 0, 0.5),
    ("endTime", 10, 9.5),
    ("playCount", 1, 2),
    ("infiniteLoop", False, True),
    ("rate", 1.0, 1.25),
    ("preservePitch", True, False),
    ("holdLastFrame", False, True),
]


def _phase8b_video_audio_time_fixture(
    *,
    property_name: str = "rate",
    baseline: Any = 1.0,
    requested: Any = 1.25,
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values: dict[str, Any] = {"type": cue_type, property_name: baseline}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, property_name) if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {property_name: requested},
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("property_name", "baseline", "requested"), PHASE8B_VIDEO_AUDIO_TIME_CASES)
def test_phase8b_video_audio_time_dry_run_emits_bound_token(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase8b_video_audio_time_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = video_audio_time._decode_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioTime:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8b_audio_time_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert payload["workspace_validation"] == "post_write_fresh_readback_required"
    read_keys = [
        json.loads(args[0])
        for address, args, _ in client.requests
        if address.endswith("/valuesForKeys")
    ]
    assert read_keys
    assert all(
        {"audioTrackFormats", "numChannelsIn", "levels"}.issubset(keys)
        for keys in read_keys
    )
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("property_name", "baseline", "requested"), PHASE8B_VIDEO_AUDIO_TIME_CASES)
def test_phase8b_video_audio_time_real_write_sets_once_and_verifies(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": property_name, "value": baseline}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize(("baseline", "requested", "readback"), [(0, True, 1), (1, False, 0)])
def test_phase8b_preserve_pitch_accepts_numeric_qlab_readback(
    baseline: int,
    requested: bool,
    readback: int,
) -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture(
        property_name="preservePitch",
        baseline=baseline,
        requested=requested,
    )
    client.numeric_bool_readback_properties.add("preservePitch")
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    payload, error = video_audio_time._decode_confirm_token(
        planned_setters(plan["results"][0])["preservePitch"]["confirm_token"]
    )
    assert error is None
    assert payload["baseline"] is bool(baseline)
    assert payload["requested"] is requested

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["preservePitch"] == readback


def test_phase8b_preserve_pitch_rejects_invalid_numeric_baseline() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "preservePitch": 2, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"preservePitch": True}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


def test_phase8b_video_audio_time_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, appearance_update, appearance_token = _phase3d_appearance_fixture()
    _, _, _, io_update, io_token = _phase8_io_fixture(property_name="audioOutputPatchID")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioTime:v1:fake"]}],
        [{**update, "properties": {"rate": 1.5}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"rate": 1.25, "playCount": 2}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {"rate": 1.25}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [appearance_token]}],
        [{**update, "confirm_gates": [io_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**appearance_update, "confirm_gates": [token]}],
        [{**io_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/rate", "/playCount", "/smooth", "/blendMode", "/audioOutputPatchID")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "bad_value"),
    [
        ("rate", 0),
        ("rate", math.nan),
        ("rate", math.inf),
        ("startTime", -0.1),
        ("endTime", math.nan),
        ("playCount", 0),
        ("playCount", 1.5),
        ("infiniteLoop", 1),
        ("preservePitch", "true"),
        ("preservePitch", 0),
        ("preservePitch", 1),
        ("holdLastFrame", None),
    ],
)
def test_phase8b_video_audio_time_invalid_values_reject_before_setter(property_name: str, bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    baseline = False if property_name in {"infiniteLoop", "holdLastFrame"} else True if property_name == "preservePitch" else 1
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", property_name: baseline, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {property_name: bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_phase8b_video_audio_time_requires_embedded_audio_evidence_for_audio_routes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "rate": 1.0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"rate": 1.25}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["rate"] == "Phase 8B Video audio time requires readable embedded-audio evidence."
    assert_no_confirm_token(result)


@pytest.mark.parametrize("cue_type", ["Text", "Camera", "Audio"])
def test_phase8b_video_audio_time_rejects_wrong_cue_type(cue_type: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "rate": 1.0, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"rate": 1.25}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/rate") for address, _, _ in client.requests)


def test_phase8b_video_audio_time_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase8b_video_audio_time_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**update, "properties": {"rate": 1.0}}
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["rate"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["rate"] == 1.0


def test_phase8b_end_time_setter_error_matching_readback_is_updated_warning() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "endTime": 10, "audioTrackFormats": [{"channels": 2}]}},
        error_after_apply_properties={(cue_id, "endTime")},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"endTime": 9.5}}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["endTime"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["endTime"] == 9.5
    assert result["results"][0]["errors"] is None
    assert "setter_error_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8b_end_time_setter_error_mismatched_readback_fails() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "endTime": 10, "audioTrackFormats": [{"channels": 2}]}},
        fail_set_property=(cue_id, "endTime"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"endTime": 9.5}}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["endTime"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "partial_failed"
    assert result["results"][0]["after"]["endTime"] == 10
    assert result["results"][0]["errors"]["endTime"]


def _phase9a_video_audio_level_fixture(
    *,
    channel: int = 0,
    baseline: float = 0.0,
    requested: float = -1.0,
    profile: str = "video_basic",
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
    slider_levels: list[Any] | None = None,
    num_channels_in: int | None = None,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    levels = list(slider_levels) if slider_levels is not None else [baseline, 0.0]
    cue_values: dict[str, Any] = {"type": cue_type, "sliderLevels": levels}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    if num_channels_in is not None:
        cue_values["numChannelsIn"] = num_channels_in
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, f"sliderLevel/{channel}") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "operations": [{"property": "sliderLevel", "args": {"channel": channel, "decibel": requested}}],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["sliderLevel"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase9a_video_audio_level_dry_run_emits_bound_token() -> None:
    client, reader, cue_id, update, _ = _phase9a_video_audio_level_fixture(channel=0, baseline=0.0, requested=-1.0)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)["sliderLevel"]
    payload, error = write_operations._decode_phase9a_video_audio_level_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioLevels:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/0"
    assert setter["args"] == [-1.0]
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase9a_audio_level_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == "sliderLevel"
    assert payload["channel"] == 0
    assert payload["baseline"] == 0.0
    assert payload["requested"] == -1.0
    assert payload["workspace_validation"] == "post_write_fresh_sliderLevels_readback_required"
    assert not any(address.endswith("/sliderLevel/0") for address, _, _ in client.requests)


def test_phase9a_video_audio_level_accepts_num_channels_audio_evidence() -> None:
    client, reader, _, update, _ = _phase9a_video_audio_level_fixture(audio_evidence=False, num_channels_in=2)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    setter = planned_setters(result["results"][0])["sliderLevel"]
    assert setter["confirm_token"].startswith("confirm:videoAudioLevels:v1:")
    assert setter["real_write_possible"] is True
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/sliderLevel/0") for address, _, _ in client.requests)


def test_phase9a_video_audio_level_real_write_sets_once_and_verifies_channel_readback() -> None:
    client, reader, cue_id, update, token = _phase9a_video_audio_level_fixture(
        channel=1,
        baseline=0.0,
        requested=-1.5,
        slider_levels=[0.0, 0.0],
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)["sliderLevel"]
    address = f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/1"
    assert result["status"] == "updated"
    assert item["after"]["sliderLevels"] == [0.0, -1.5]
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": "sliderLevel", "args": {"channel": 1, "decibel": 0.0}}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)
    assert not any("/level/" in request[0] for request in client.requests)
    assert not any(request[0].endswith(("/setDefaultLevels", "/setSilentLevels")) for request in client.requests)


@pytest.mark.parametrize(("profile", "cue_type"), [("audio_basic", "Audio"), ("mic_basic", "Mic")])
def test_phase9a_audio_and_mic_level_reuse_slider_contract(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, cue_id, update, token = _phase9a_video_audio_level_fixture(
        profile=profile,
        cue_type=cue_type,
        channel=1,
        baseline=0.0,
        requested=-1.5,
        slider_levels=[0.0, 0.0],
        audio_evidence=False,
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["sliderLevel"]
    payload, error = write_operations._decode_phase9a_video_audio_level_confirm_token(setter["confirm_token"])
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert error is None
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["sliderLevels"] == [0.0, -1.5]
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "sliderLevel",
        "args": {"channel": 1, "decibel": 0.0},
    }
    assert [request[0] for request in client.requests].count(
        f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/1"
    ) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase9a_audio_and_mic_slider_tokens_are_type_profile_bound() -> None:
    _, _, _, _, audio_token = _phase9a_video_audio_level_fixture(
        profile="audio_basic",
        cue_type="Audio",
        channel=0,
        slider_levels=[0.0],
        audio_evidence=False,
    )
    mic_client, mic_reader, cue_id, mic_update, _ = _phase9a_video_audio_level_fixture(
        profile="mic_basic",
        cue_type="Mic",
        channel=0,
        slider_levels=[0.0],
        audio_evidence=False,
    )

    result = mic_reader.edit_cues("ws-1", [{**mic_update, "confirm_gates": [audio_token]}], dry_run=False)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(
        address == f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/0"
        for address, _, _ in mic_client.requests
    )


def test_phase9a_video_audio_level_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase9a_video_audio_level_fixture()
    _, _, _, time_update, time_token = _phase8b_video_audio_time_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, io_update, io_token = _phase8_io_fixture(property_name="audioOutputPatchID")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioLevels:v1:fake"]}],
        [{**update, "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -2.0}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "rate", "args": 1.25}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio_basic", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [time_token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [io_token]}],
        [{**time_update, "confirm_gates": [token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**io_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/sliderLevel/" in address or address.endswith(("/rate", "/smooth", "/audioOutputPatchID")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [True, "0", "-inf", math.nan, math.inf, None, [], {}])
def test_phase9a_video_audio_level_invalid_decibels_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0], "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": bad_value}}],
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/sliderLevel/" in address for address, _, _ in client.requests)


def test_phase9a_video_audio_level_rejects_missing_evidence_and_unreadable_channel() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    no_evidence = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )
    channel_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0], "audioTrackFormats": [{"channels": 2, "format": "AAC"}]}},
    )
    channel_reader = QLabReader(channel_client)  # type: ignore[arg-type]
    missing_channel = channel_reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 1, "decibel": -1.0}}]}],
        dry_run=True,
    )

    assert no_evidence["status"] == "preflight_failed"
    assert no_evidence["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable embedded-audio evidence."
    client.cues[cue_id]["levels"] = [[0.0]]
    levels_only = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )
    assert levels_only["status"] == "preflight_failed"
    assert levels_only["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable embedded-audio evidence."
    assert missing_channel["status"] == "preflight_failed"
    assert missing_channel["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable sliderLevels baseline for channel."
    assert_no_confirm_token(no_evidence)
    assert_no_confirm_token(levels_only)
    assert_no_confirm_token(missing_channel)


def test_phase9a_video_audio_level_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase9a_video_audio_level_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {
        **update,
        "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": 0.0}}],
    }
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["sliderLevel"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliderLevels"][0] == 0.0


def _phase9b_video_audio_matrix_fixture(
    *,
    in_channel: int = 1,
    out_channel: int = 0,
    baseline: float = 0.0,
    requested: float = -1.0,
    profile: str = "video_basic",
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
    levels: list[Any] | None = None,
    num_channels_in: int | None = 2,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "22222222-2222-4222-8222-222222222222"
    matrix = [list(row) for row in levels] if levels is not None else [[0.0, 0.0], [baseline, 0.0], [0.0, 0.0]]
    cue_values: dict[str, Any] = {"type": cue_type, "levels": matrix}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    if num_channels_in is not None:
        cue_values["numChannelsIn"] = num_channels_in
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, f"level/{in_channel}/{out_channel}") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "operations": [
            {"property": "level", "args": {"inChannel": in_channel, "outChannel": out_channel, "decibel": requested}}
        ],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["level"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase9b_video_audio_matrix_dry_run_emits_bound_token() -> None:
    client, reader, cue_id, update, _ = _phase9b_video_audio_matrix_fixture(requested=-1.0)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)["level"]
    payload, error = write_operations._decode_phase9b_video_audio_matrix_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioMatrix:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/level/1/0"
    assert setter["args"] == [-1.0]
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase9b_audio_matrix_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == "level"
    assert payload["inChannel"] == 1
    assert payload["outChannel"] == 0
    assert payload["baseline"] == 0.0
    assert payload["requested"] == -1.0
    assert payload["workspace_validation"] == "post_write_fresh_levels_matrix_readback_required"
    assert not any(address.endswith("/level/1/0") for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_real_write_sets_once_and_verifies_crosspoint_readback() -> None:
    client, reader, cue_id, update, token = _phase9b_video_audio_matrix_fixture(requested=-1.5)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)["level"]
    address = f"/workspace/ws-1/cue_id/{cue_id}/level/1/0"
    assert result["status"] == "updated"
    assert item["after"]["levels"][1][0] == -1.5
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {
        "property": "level",
        "args": {"inChannel": 1, "outChannel": 0, "decibel": 0.0},
    }
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)
    assert not any("/sliderLevel/" in request[0] for request in client.requests)
    assert not any(request[0].endswith(("/setDefaultLevels", "/setSilentLevels")) for request in client.requests)


@pytest.mark.parametrize(("profile", "cue_type"), [("audio_basic", "Audio"), ("mic_basic", "Mic")])
def test_phase9b_audio_and_mic_level_reuse_matrix_contract(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, cue_id, update, token = _phase9b_video_audio_matrix_fixture(
        profile=profile,
        cue_type=cue_type,
        in_channel=1,
        out_channel=0,
        baseline=0.0,
        requested=-1.5,
        audio_evidence=False,
        num_channels_in=2,
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["level"]
    payload, error = write_operations._decode_phase9b_video_audio_matrix_confirm_token(setter["confirm_token"])
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert error is None
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["levels"][1][0] == -1.5
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "level",
        "args": {"inChannel": 1, "outChannel": 0, "decibel": 0.0},
    }
    assert [request[0] for request in client.requests].count(
        f"/workspace/ws-1/cue_id/{cue_id}/level/1/0"
    ) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase9b_video_audio_matrix_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase9b_video_audio_matrix_fixture()
    _, _, _, slider_update, slider_token = _phase9a_video_audio_level_fixture()
    client.cue_numbers["v5"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioMatrix:v1:fake"]}],
        [{**update, "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": -2.0}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": "v5", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "rate", "args": 1.25}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio_basic", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [slider_token]}],
        [{**slider_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/level/" in address or "/sliderLevel/" in address or address.endswith("/rate") for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [True, "0", "-inf", math.nan, math.inf, None, [], {}])
def test_phase9b_video_audio_matrix_invalid_decibels_reject_before_setter(bad_value: Any) -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": [[0.0], [0.0]], "numChannelsIn": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": bad_value}}],
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/level/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("args", "levels", "num_channels_in", "expected_error"),
    [
        ({"inChannel": 0, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix row 0 is blocked; use Phase 9A sliderLevel."),
        ({"inChannel": 2, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0], [0.0]], 1, "Phase 9B Video audio matrix requires inChannel within numChannelsIn."),
        ({"inChannel": 2, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0]], 2, "Phase 9B Video audio matrix requires readable levels baseline for crosspoint."),
        ({"inChannel": 1, "outChannel": 2, "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix requires readable levels baseline for crosspoint."),
        ({"inChannel": 1, "outChannel": "Main", "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix requires integer outChannel."),
    ],
)
def test_phase9b_video_audio_matrix_rejects_unsafe_indexing(
    args: dict[str, Any],
    levels: list[Any],
    num_channels_in: int,
    expected_error: str,
) -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": levels, "numChannelsIn": num_channels_in}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "level", "args": args}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["level"] == expected_error
    assert_no_confirm_token(result)
    assert not any("/level/" in address for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_rejects_missing_evidence_live_batch_and_blocked_actions() -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    operation = {"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": -1.0}}
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": [[0.0], [0.0]], "sliderLevels": [0.0]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    no_evidence = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}],
        dry_run=True,
    )
    live = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{**operation, "mode": "live"}]}],
        dry_run=True,
    )
    batch = reader.edit_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]},
            {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]},
        ],
        dry_run=True,
    )
    multi = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation, {"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )

    assert no_evidence["status"] == "preflight_failed"
    assert no_evidence["results"][0]["errors"]["level"] == "Phase 9B Video audio matrix requires readable embedded-audio evidence."
    assert live["status"] == "preflight_failed"
    assert batch["status"] == "preflight_failed"
    assert multi["status"] == "preflight_failed"
    for result in [no_evidence, live, batch, multi]:
        assert_no_confirm_token(result)
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/level/" in address or "/live" in address for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase9b_video_audio_matrix_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {
        **update,
        "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": 0.0}}],
    }
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["level"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["levels"][1][0] == 0.0


def _phase9_levels_fixture(
    operation: dict[str, Any],
    *,
    cue_values: dict[str, Any] | None = None,
    timeout_property: str | None = None,
    profile: str = "video_basic",
    cue_type: str = "Video",
    audio_evidence: bool = True,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "33333333-3333-4333-8333-333333333333"
    values = {
        "type": cue_type,
        "numChannelsIn": 2,
        "sliderLevels": [0.0, 0.0, 0.0],
        "levels": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        "inputChannelName/1": "L",
        "inputChannelName/2": "R",
        "gang/1/0": "music",
        "muteChannels": [2],
        "soloChannels": [1],
    }
    if audio_evidence:
        values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    if cue_values:
        values.update(cue_values)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: values},
        timeout_set_property=(cue_id, timeout_property) if timeout_property else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": profile, "operations": [operation]}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_video_clock_type_dry_run_real_write_and_rollback() -> None:
    operation = {"property": "clockType", "args": {"value": "audio"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation, cue_values={"clockType": "video"})

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    rollback_update = {**update, "operations": [{"property": "clockType", "args": {"value": "video"}}]}
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["clockType"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert planned_setters(plan["results"][0])["clockType"]["confirm_token"].startswith("confirm:videoClockType:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["clockType"] == "audio"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["clockType"] == "video"
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/clockType") == 2


def test_video_clock_type_dry_run_allows_video_without_audio_evidence() -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "audioTrackFormats": [], "numChannelsIn": 0, "clockType": "video"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "clockType", "args": {"value": "audio"}}]}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["clockType"]
    assert result["status"] == "dry_run"
    assert setter["confirm_token"].startswith("confirm:videoClockType:v1:")


@pytest.mark.parametrize("property_name", ["doFade", "lockFadeToCue"])
@pytest.mark.parametrize("requested", [True, False])
def test_video_integrated_fade_dry_run_and_real_write(property_name: str, requested: bool) -> None:
    operation = {"property": property_name, "args": {"value": requested}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(
        operation,
        cue_values={"doFade": False, "lockFadeToCue": False},
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert planned_setters(plan["results"][0])[property_name]["confirm_token"].startswith(
        "confirm:videoIntegratedFade:v1:"
    )
    assert result["status"] == "updated"
    assert result["results"][0]["after"][property_name] is requested
    assert result["results"][0]["updateq_plan"]["rollback"] == {"property": property_name, "args": {"value": False}}
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{property_name}") == 1


@pytest.mark.parametrize("value", ["Audio", "VIDEO", "sound", "", None, True, False, 1, 0, [], {}])
def test_video_clock_type_rejects_invalid_values(value: Any) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "audioTrackFormats": [{"channels": 2}], "clockType": "video"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "clockType", "args": {"value": value}}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["doFade", "lockFadeToCue"])
@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, [], {}])
def test_video_integrated_fade_rejects_invalid_values(property_name: str, value: Any) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "audioTrackFormats": [{"channels": 2}],
                "doFade": False,
                "lockFadeToCue": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": property_name, "args": {"value": value}}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


def test_video_clock_and_integrated_fade_reject_cross_tokens_batch_wrong_type_and_no_audio() -> None:
    clock_client, clock_reader, cue_id, clock_update, clock_token = _phase9_levels_fixture(
        {"property": "clockType", "args": {"value": "audio"}},
        cue_values={"clockType": "video"},
    )
    _, _, _, fade_update, fade_token = _phase9_levels_fixture(
        {"property": "doFade", "args": {"value": True}},
        cue_values={"doFade": False},
    )
    cases = [
        [{**clock_update, "confirm_gates": [fade_token]}],
        [{**fade_update, "confirm_gates": [clock_token]}],
        [{**clock_update, "confirm_gates": ["confirm:videoClockType:v1:fabricated"]}],
        [{**clock_update, "confirm_gates": [clock_token]}, {**clock_update, "confirm_gates": [clock_token]}],
        [{**clock_update, "cue_ref": "v5", "confirm_gates": [clock_token]}],
        [{**clock_update, "operations": [*clock_update["operations"], {"property": "doFade", "args": {"value": True}}], "confirm_gates": [clock_token]}],
    ]
    for case in cases:
        result = clock_reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])

    live = clock_reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "clockType", "mode": "live", "args": {"value": "audio"}}],
            }
        ],
        dry_run=True,
    )
    assert live["status"] == "preflight_failed"
    assert_no_confirm_token(live)

    for cue_type in ("Audio", "Camera", "Text"):
        client = BatchFakeWriteClient(
            QLabConfig(enable_write=True, passcode="server-pass"),
            cues={cue_id: {"type": cue_type, "audioTrackFormats": [{"channels": 2}], "clockType": "video"}},
        )
        reader = QLabReader(client)  # type: ignore[arg-type]
        result = reader.edit_cues("ws-1", [clock_update], dry_run=True)
        assert result["status"] == "preflight_failed"
        assert_no_confirm_token(result)

    no_audio = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "audioTrackFormats": [], "numChannelsIn": 0, "clockType": "video", "doFade": False}},
    )
    reader = QLabReader(no_audio)  # type: ignore[arg-type]
    clock_plan = reader.edit_cues("ws-1", [clock_update], dry_run=True)
    assert clock_plan["status"] == "dry_run"
    assert planned_setters(clock_plan["results"][0])["clockType"]["confirm_token"].startswith("confirm:videoClockType:v1:")

    for update in (fade_update,):
        result = reader.edit_cues("ws-1", [update], dry_run=True)
        assert result["status"] == "preflight_failed"
        assert_no_confirm_token(result)
    assert not any("/clockType" in address or "/doFade" in address for address, _, _ in clock_client.requests)


def test_phase9c_input_channel_name_dry_run_and_real_write() -> None:
    operation = {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["inputChannelName"]
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert setter["confirm_token"].startswith("confirm:videoAudioLevelMeta:v1:")
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/inputChannelName/1"
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["inputChannelName/1"] == "Dialog"
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "inputChannelName",
        "args": {"number": 1, "name": "L"},
    }
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/inputChannelName/1") == 1


def test_phase9c_gang_dry_run_and_real_write() -> None:
    operation = {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "speech"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["gang/1/0"] == "speech"
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "gang",
        "args": {"inChannel": 1, "outChannel": 0, "gang": "music"},
    }
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/gang/1/0") == 1


def test_phase9c_gang_allows_empty_baseline_and_empty_rollback() -> None:
    operation = {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "MCPG"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation, cue_values={"gang/1/0": ""})

    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    rollback_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": ""}}],
    }
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["gang"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert forward["results"][0]["after"]["gang/1/0"] == "MCPG"
    assert forward["results"][0]["updateq_plan"]["rollback"] == {
        "property": "gang",
        "args": {"inChannel": 1, "outChannel": 0, "gang": ""},
    }
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["gang/1/0"] == ""
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/gang/1/0") == 2


@pytest.mark.parametrize(("profile", "cue_type"), [("audio_basic", "Audio"), ("mic_basic", "Mic")])
@pytest.mark.parametrize(
    ("operation", "after_key", "expected", "rollback"),
    [
        (
            {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}},
            "inputChannelName/1",
            "Dialog",
            {"property": "inputChannelName", "args": {"number": 1, "name": "L"}},
        ),
        (
            {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "speech"}},
            "gang/1/0",
            "speech",
            {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "music"}},
        ),
    ],
)
def test_phase9c_audio_and_mic_reuse_level_metadata_contract(
    profile: str,
    cue_type: str,
    operation: dict[str, Any],
    after_key: str,
    expected: str,
    rollback: dict[str, Any],
) -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(
        operation,
        profile=profile,
        cue_type=cue_type,
        audio_evidence=False,
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])[operation["property"]]
    payload, error = write_operations._decode_phase9_confirm_token(
        setter["confirm_token"],
        family="videoAudioLevelMeta",
        version=1,
        label="Phase 9C audio level metadata",
    )
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert error is None
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert "audioTrackFormats" not in result["results"][0]["before"]
    assert result["status"] == "updated"
    assert result["results"][0]["after"][after_key] == expected
    assert result["results"][0]["updateq_plan"]["rollback"] == rollback
    assert [request[0] for request in client.requests].count(
        f"/workspace/ws-1/cue_id/{cue_id}/{after_key}"
    ) == 1
    assert not any("/live" in address or "/mute" in address or "/solo" in address for address, _, _ in client.requests)


def test_phase9c_audio_and_mic_tokens_are_type_profile_bound() -> None:
    _, _, _, _, audio_token = _phase9_levels_fixture(
        {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}},
        profile="audio_basic",
        cue_type="Audio",
        audio_evidence=False,
    )
    mic_client, mic_reader, cue_id, mic_update, _ = _phase9_levels_fixture(
        {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}},
        profile="mic_basic",
        cue_type="Mic",
        audio_evidence=False,
    )

    result = mic_reader.edit_cues("ws-1", [{**mic_update, "confirm_gates": [audio_token]}], dry_run=False)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(
        address == f"/workspace/ws-1/cue_id/{cue_id}/inputChannelName/1"
        for address, _, _ in mic_client.requests
    )


def test_phase9c_audio_level_metadata_rejects_stale_baseline_before_setter() -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(
        {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}},
        profile="audio_basic",
        cue_type="Audio",
        audio_evidence=False,
    )
    client.cues[cue_id]["inputChannelName/1"] = "Changed elsewhere"

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "preflight_failed"
    assert "stale_video_phase9c_audio_level_meta_write" in result["results"][0]["errors"]["inputChannelName"]
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "operation", "cue_values", "expected_error"),
    [
        (
            "audio_basic",
            "Audio",
            {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}},
            {"inputChannelName/1": None},
            "requires readable inputChannelName/",
        ),
        (
            "mic_basic",
            "Mic",
            {"property": "inputChannelName", "args": {"number": 3, "name": "Dialog"}},
            {},
            "number must be within numChannelsIn",
        ),
        (
            "audio_basic",
            "Audio",
            {"property": "inputChannelName", "args": {"number": 1, "name": "Bad\nName"}},
            {},
            "1-64 character string",
        ),
        (
            "mic_basic",
            "Mic",
            {"property": "gang", "args": {"inChannel": 0, "outChannel": 0, "gang": "g"}},
            {},
            "row 0 is blocked",
        ),
    ],
)
def test_phase9c_audio_and_mic_metadata_rejects_unsafe_baselines_indexes_and_strings(
    profile: str,
    cue_type: str,
    operation: dict[str, Any],
    cue_values: dict[str, Any],
    expected_error: str,
) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    values = {
        "type": cue_type,
        "numChannelsIn": 2,
        "sliderLevels": [0.0, 0.0],
        "levels": [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
        "inputChannelName/1": "L",
        "gang/1/0": "music",
        **cue_values,
    }
    client = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), cues={cue_id: values})
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": profile, "operations": [operation]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert expected_error in result["results"][0]["errors"][operation["property"]]
    assert_no_confirm_token(result)
    assert not any("/inputChannelName/" in address or "/gang/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("operation", "cue_values", "expected_error"),
    [
        (
            {"property": "inputChannelName", "args": {"number": 3, "name": "Bad"}},
            {},
            "Phase 9C inputChannelName number must be within numChannelsIn and starts at 1.",
        ),
        (
            {"property": "inputChannelName", "args": {"number": 1, "name": "Bad\nName"}},
            {},
            "Phase 9C inputChannelName requires a 1-64 character string without control characters.",
        ),
        (
            {"property": "gang", "args": {"inChannel": 0, "outChannel": 0, "gang": "g"}},
            {},
            "Phase 9C gang row 0 is blocked; row 0 belongs to sliderLevels.",
        ),
        (
            {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "bad\nname"}},
            {},
            "Phase 9C gang requires a string up to 64 characters without control characters.",
        ),
    ],
)
def test_phase9c_level_metadata_rejects_unsafe_values(
    operation: dict[str, Any],
    cue_values: dict[str, Any],
    expected_error: str,
) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    values = {
        "type": "Video",
        "numChannelsIn": 2,
        "sliderLevels": [0.0],
        "levels": [[0.0], [0.0]],
        "inputChannelName/1": "L",
        "gang/1/0": "music",
        **cue_values,
    }
    client = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), cues={cue_id: values})
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues("ws-1", [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"][operation["property"]] == expected_error
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("operation", "read_key", "expected", "expected_path"),
    [
        (
            {"property": "mute/channel", "args": {"output": 1, "value": True}},
            "muteChannels",
            [1, 2],
            "mute/channel/1",
        ),
        (
            {"property": "solo/channel", "args": {"output": 1, "value": False}},
            "soloChannels",
            [],
            "solo/1",
        ),
    ],
)
def test_phase9d_mute_solo_real_write_uses_channel_routes(
    operation: dict[str, Any],
    read_key: str,
    expected: list[int],
    expected_path: str,
) -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    setter = planned_setters(plan["results"][0])[operation["property"]]
    assert setter["confirm_token"].startswith("confirm:videoAudioMuteSolo:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == expected
    assert not any("/object" in address or "/mute/clear" in address or "/solo/clear" in address for address, _, _ in client.requests)
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{expected_path}") == 1


@pytest.mark.parametrize(
    ("operation", "expected_error"),
    [
        ({"property": "mute/channel", "args": {"output": "Main", "value": True}}, "Phase 9D mute/solo requires integer output within readable sliderLevels."),
        ({"property": "solo/channel", "args": {"output": 99, "value": True}}, "Phase 9D mute/solo requires integer output within readable sliderLevels."),
        ({"property": "mute/channel", "args": {"output": 1, "value": "true"}}, "value must be a boolean"),
    ],
)
def test_phase9d_mute_solo_rejects_names_bounds_and_non_booleans(operation: dict[str, Any], expected_error: str) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "numChannelsIn": 2,
                "sliderLevels": [0.0, 0.0],
                "muteChannels": [],
                "soloChannels": [],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues("ws-1", [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert expected_error in str(result["results"][0]["errors"])
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("operation", "cue_values", "read_key"),
    [
        ({"property": "mute/channel", "args": {"output": 1, "value": False}}, {"muteChannels": [1]}, "muteChannels"),
        ({"property": "solo/channel", "args": {"output": 1, "value": False}}, {"soloChannels": [1]}, "soloChannels"),
    ],
)
def test_phase9d_mute_solo_can_rollback_self_induced_warning(
    operation: dict[str, Any],
    cue_values: dict[str, Any],
    read_key: str,
) -> None:
    client, reader, _, update, token = _phase9_levels_fixture(
        operation,
        cue_values={"isWarning": True, **cue_values},
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert planned_setters(plan["results"][0])[operation["property"]]["confirm_token"].startswith(
        "confirm:videoAudioMuteSolo:v1:"
    )
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == []


@pytest.mark.parametrize(
    ("operation", "read_key", "rollback", "expected_path"),
    [
        (
            {"property": "mute/channel/clear", "args": {}},
            "muteChannels",
            [{"property": "mute/channel", "args": {"output": 2, "value": True}}],
            "mute/channel/clear",
        ),
        (
            {"property": "solo/channel/clear", "args": {}},
            "soloChannels",
            [{"property": "solo/channel", "args": {"output": 1, "value": True}}],
            "solo/channel/clear",
        ),
    ],
)
def test_phase9e_channel_clear_real_write_and_rollback_plan(
    operation: dict[str, Any],
    read_key: str,
    rollback: list[dict[str, Any]],
    expected_path: str,
) -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    setter = planned_setters(plan["results"][0])[operation["property"]]
    assert setter["confirm_token"].startswith("confirm:videoAudioLevelBulk:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == []
    assert result["results"][0]["updateq_plan"]["rollback"] == rollback
    assert result["results"][0]["executed_operations"][0]["operation"] == "action"
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{expected_path}") == 1


@pytest.mark.parametrize("property_name", ["setDefaultLevels", "setSilentLevels"])
def test_phase9e_default_and_silent_levels_stay_planned_only(property_name: str) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "numChannelsIn": 2, "sliderLevels": [0.0], "levels": [[0.0], [0.0]]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": property_name, "args": {}}]}],
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    setter = planned_setters(result["results"][0])[property_name]
    assert setter["planned_only_reason"] == "video_audio_level_bulk_requires_full_runtime_validation"


def test_phase9c_9d_9e_reject_cross_tokens_and_batch_before_setter() -> None:
    meta_client, meta_reader, cue_id, meta_update, meta_token = _phase9_levels_fixture(
        {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}}
    )
    _, _, _, mute_update, mute_token = _phase9_levels_fixture(
        {"property": "mute/channel", "args": {"output": 1, "value": True}}
    )
    _, _, _, clear_update, clear_token = _phase9_levels_fixture({"property": "mute/channel/clear", "args": {}})
    cases = [
        [{**meta_update, "confirm_gates": [mute_token]}],
        [{**mute_update, "confirm_gates": [clear_token]}],
        [{**clear_update, "confirm_gates": [meta_token]}],
        [{**meta_update, "confirm_gates": [meta_token]}, {**meta_update, "confirm_gates": [meta_token]}],
        [{**meta_update, "cue_ref": "v5", "confirm_gates": [meta_token]}],
    ]
    meta_client.cue_numbers["v5"] = cue_id

    for case in cases:
        result = meta_reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/inputChannelName/" in address or "/mute/channel/" in address for address, _, _ in meta_client.requests)


PHASE8C_VIDEO_SLICE_CASES = [
    (
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
        [{"time": 1.5, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "sliceMarker/0/time",
        [1.5],
    ),
    (
        {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
        [{"time": 1.0, "playCount": -1}, {"time": 3.0, "playCount": 2}],
        "sliceMarker/0/playCount",
        [-1],
    ),
    (
        {"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}},
        [{"time": 1.0, "playCount": 1}, {"time": 2.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "addSliceMarker",
        [2.0, 1],
    ),
    (
        {"property": "deleteSliceMarker", "args": {"index": 1}},
        [{"time": 1.0, "playCount": 1}],
        "deleteSliceMarker/1",
        [],
    ),
    (
        {"property": "deleteSliceMarkers", "args": {}},
        [],
        "deleteSliceMarkers",
        [],
    ),
]


def _phase8c_video_slice_fixture(
    operation: dict[str, Any] | None = None,
    *,
    cue_type: str = "Video",
    cue_ref: str | None = None,
    timeout: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    operation = operation or {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}}
    prop_path = operation["property"]
    if prop_path == "sliceMarker/playCount":
        prop_path = f"sliceMarker/{operation.get('args', {}).get('index', 0)}/playCount"
    elif prop_path == "sliceMarker/time":
        prop_path = f"sliceMarker/{operation.get('args', {}).get('index', 0)}/time"
    elif prop_path == "deleteSliceMarker":
        prop_path = f"deleteSliceMarker/{operation.get('args', {}).get('index', 0)}"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": cue_type,
                "sliceMarkers": [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
        timeout_set_property=(cue_id, prop_path) if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_ref or cue_id,
        "profile": "video_basic",
        "operations": [operation],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"] if plan["status"] == "dry_run" else ""
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("operation", "expected", "path", "args"), PHASE8C_VIDEO_SLICE_CASES)
def test_phase8c_video_slice_dry_run_emits_bound_token(
    operation: dict[str, Any],
    expected: list[dict[str, Any]],
    path: str,
    args: list[Any],
) -> None:
    client, reader, cue_id, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[operation["property"]]
    payload, error = write_operations._decode_phase8c_video_slice_confirm_token(setter["confirm_token"])

    assert result["status"] == "dry_run"
    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoSlices:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{path}"
    assert setter["args"] == args
    assert setter["phase8c_expected_slice_markers"] == expected
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8c_slice_marker_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == operation["property"]
    assert payload["baseline"] == [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}]
    assert payload["expected"] == expected
    assert payload["workspace_validation"] == "post_write_fresh_sliceMarkers_readback_required"
    assert not any(address.endswith(path) for address, _, _ in client.requests)


@pytest.mark.parametrize(("operation", "expected", "path", "args"), PHASE8C_VIDEO_SLICE_CASES)
def test_phase8c_video_slice_real_write_sets_once_and_verifies(
    operation: dict[str, Any],
    expected: list[dict[str, Any]],
    path: str,
    args: list[Any],
) -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[operation["property"]]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{path}"
    assert result["status"] == "updated"
    assert item["after"]["sliceMarkers"] == expected
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize("bad_play_count", [-2, 0, 1.5, "1", True, None, [], {}])
def test_phase8c_video_slice_rejects_invalid_play_count_before_setter(bad_play_count: Any) -> None:
    operation = {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": bad_play_count}}
    client, reader, _, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/sliceMarker/0/playCount" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "operation",
    [
        {"property": "sliceMarker/playCount", "args": {"playCount": 1}},
        {"property": "sliceMarker/time", "args": {"time": 1.5}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": -0.1}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 11.0}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 2.98}},
        {"property": "sliceMarker/time", "args": {"index": 1, "time": 1.03}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 3.5}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": math.inf}},
        {"property": "addSliceMarker", "args": {"time": 1.03, "playCount": 1}},
        {"property": "addSliceMarker", "args": {"time": 11.0, "playCount": 1}},
        {"property": "deleteSliceMarker", "args": {"index": 99}},
    ],
)
def test_phase8c_video_slice_rejects_unsafe_marker_shape_before_setter(operation: dict[str, Any]) -> None:
    client, reader, _, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def test_phase8c_video_slice_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, audio_time_update, audio_time_token = _phase8b_video_audio_time_fixture()
    other_cue_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_cue_id] = {
        "uniqueID": other_cue_id,
        "type": "Video",
        "sliceMarkers": [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "startTime": 0,
        "endTime": 10,
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoSlices:v1:fake"]}],
        [{**update, "operations": [{"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": other_cue_id, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "deleteSliceMarker", "args": {"index": 1}}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [audio_time_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**audio_time_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/sliceMarker/0/playCount" in address for address, _, _ in client.requests)


def test_phase8c_video_slice_rejects_non_video_cues_and_malformed_baseline() -> None:
    non_video_client, non_video_reader, _, non_video_update, _ = _phase8c_video_slice_fixture(cue_type="Audio")
    malformed_client, malformed_reader, cue_id, _, _ = _phase8c_video_slice_fixture()
    malformed_client.cues[cue_id]["sliceMarkers"] = [{"time": 1.0, "playCount": 0}]

    non_video = non_video_reader.edit_cues("ws-1", [non_video_update], dry_run=True)
    malformed = malformed_reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 1}}]}],
        dry_run=True,
    )

    assert non_video["status"] == "preflight_failed"
    assert malformed["status"] == "preflight_failed"
    assert_no_confirm_token(non_video)
    assert_no_confirm_token(malformed)


def test_phase8c_video_slice_missing_baseline_allows_first_marker_add_and_rollback() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}}],
    }

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["addSliceMarker"]["confirm_token"]
    write = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    write_markers = [dict(marker) for marker in write["results"][0]["after"]["sliceMarkers"]]
    rollback_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "deleteSliceMarker", "args": {"index": 0}}],
    }
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["deleteSliceMarker"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert plan["status"] == "dry_run"
    assert planned_setters(plan["results"][0])["addSliceMarker"]["phase8c_expected_slice_markers"] == [
        {"time": 2.0, "playCount": 1}
    ]
    assert write["status"] == "updated"
    assert write_markers == [{"time": 2.0, "playCount": 1}]
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliceMarkers"] == []


@pytest.mark.parametrize(
    "operation",
    [
        {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 2.1}},
        {"property": "deleteSliceMarker", "args": {"index": 0}},
        {"property": "deleteSliceMarkers", "args": {}},
    ],
)
def test_phase8c_video_slice_existing_marker_operations_reject_missing_empty_baseline(operation: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def test_phase8c_video_slice_empty_baseline_add_edit_delete_flow_returns_empty() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    def apply(operation: dict[str, Any]) -> list[dict[str, Any]]:
        update = {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}
        plan = reader.edit_cues("ws-1", [update], dry_run=True)
        token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"]
        result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
        assert result["status"] == "updated"
        return result["results"][0]["after"]["sliceMarkers"]

    assert apply({"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}}) == [
        {"time": 2.0, "playCount": 1}
    ]
    assert apply({"property": "addSliceMarker", "args": {"time": 4.0, "playCount": -1}}) == [
        {"time": 2.0, "playCount": 1},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}}) == [
        {"time": 2.0, "playCount": 2},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "sliceMarker/time", "args": {"index": 0, "time": 2.1}}) == [
        {"time": 2.1, "playCount": 2},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "deleteSliceMarker", "args": {"index": 1}}) == [{"time": 2.1, "playCount": 2}]
    assert apply({"property": "deleteSliceMarker", "args": {"index": 0}}) == []


def test_phase8c_video_slice_delete_all_can_be_rolled_back_by_readding_baseline() -> None:
    client, reader, _, delete_update, delete_token = _phase8c_video_slice_fixture(
        {"property": "deleteSliceMarkers", "args": {}}
    )

    deleted = reader.edit_cues("ws-1", [{**delete_update, "confirm_gates": [delete_token]}], dry_run=False)
    assert deleted["status"] == "updated"
    assert deleted["results"][0]["after"]["sliceMarkers"] == []

    for marker in [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}]:
        rollback_update = {
            **delete_update,
            "operations": [{"property": "addSliceMarker", "args": marker}],
        }
        rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
        rollback_token = planned_setters(rollback_plan["results"][0])["addSliceMarker"]["confirm_token"]
        rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)
        assert rollback["status"] == "updated"

    final = reader.get_cue_details("ws-1", delete_update["cue_ref"], "auto")
    assert final["properties"]["sliceMarkers"] == [
        {"index": 0, "time": 1.0, "playCount": 1, "loopMode": "finite", "isInfinite": False},
        {"index": 1, "time": 3.0, "playCount": 2, "loopMode": "finite", "isInfinite": False},
    ]


def test_phase8c_last_slice_play_count_dry_run_emits_bound_token_and_writes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSlicePlayCount": -1}}

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lastSlicePlayCount"]
    payload, error = write_operations._decode_phase8c_video_slice_confirm_token(setter["confirm_token"])
    write = reader.edit_cues("ws-1", [{**update, "confirm_gates": [setter["confirm_token"]]}], dry_run=False)

    assert plan["status"] == "dry_run"
    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoSlices:v1:")
    assert payload["property"] == "lastSlicePlayCount"
    assert payload["baseline"] == 1
    assert payload["expected"] == -1
    assert write["status"] == "updated"
    assert write["results"][0]["after"]["lastSlicePlayCount"] == -1
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/lastSlicePlayCount") == 1


def test_phase8c_last_slice_infinite_loop_remains_planned_without_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSliceInfiniteLoop": True}}],
        dry_run=True,
    )
    item = result["results"][0]
    setter = planned_setters(item)["lastSliceInfiniteLoop"]

    assert result["status"] == "dry_run"
    assert item["executed_operations"] == []
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"]
    assert_no_confirm_token(result)


@pytest.mark.parametrize("bad_value", [-2, 0, 1.5, "1", True, None, [], {}])
def test_phase8c_last_slice_play_count_rejects_invalid_values_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSlicePlayCount": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/lastSlicePlayCount") for address, _, _ in client.requests)


def test_phase8c_video_slice_timeout_confirmed_by_slice_marker_readback() -> None:
    client, reader, _, update, token = _phase8c_video_slice_fixture(timeout=True)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["sliceMarkers"][0]["playCount"] == -1
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8c_video_slice_setter_error_matching_readback_is_updated_warning() -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture()
    client.error_after_apply_properties.add((cue_id, "sliceMarker/0/playCount"))

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["sliceMarkers"][0]["playCount"] == -1
    assert result["results"][0]["errors"] is None
    assert "setter_error_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8c_delete_slice_markers_missing_readback_counts_as_empty_after_confirmed_query() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
        timeout_set_property=(cue_id, "deleteSliceMarkers"),
        omit_slice_markers_after_delete=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "deleteSliceMarkers", "args": {}}],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["deleteSliceMarkers"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert "sliceMarkers" not in result["results"][0]["after"]
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]


@pytest.mark.parametrize(
    ("forward_operation", "rollback_operation", "final_markers"),
    [
        (
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 1}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.0}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}},
            {"property": "deleteSliceMarker", "args": {"index": 1}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "deleteSliceMarker", "args": {"index": 1}},
            {"property": "addSliceMarker", "args": {"time": 3.0, "playCount": 2}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
    ],
)
def test_phase8c_video_slice_fresh_token_rollback_restores_baseline(
    forward_operation: dict[str, Any],
    rollback_operation: dict[str, Any],
    final_markers: list[dict[str, Any]],
) -> None:
    client, reader, _, forward_update, forward_token = _phase8c_video_slice_fixture(forward_operation)
    forward = reader.edit_cues("ws-1", [{**forward_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**forward_update, "operations": [rollback_operation]}
    stale = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])[rollback_operation["property"]]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert stale["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliceMarkers"] == final_markers


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase7e_reset_rotation_dry_run_emits_bound_reset_token(profile: str, cue_type: str) -> None:
    baseline = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, _ = _phase7_reset_rotation_fixture(
        profile=profile,
        cue_type=cue_type,
        baseline=baseline,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    action = planned_setters(item)["resetRotation"]
    payload, error = write_operations._decode_phase7_video_geometry_confirm_token(
        action["confirm_token"],
        expected_family="videoGeometryReset",
    )

    assert error is None
    assert action["confirm_token"].startswith("confirm:videoGeometryReset:v1:")
    assert action["operation"] == "action"
    assert action["address"] == f"/workspace/ws-1/cue_id/{cue_id}/resetRotation"
    assert action["args"] == []
    assert action["phase7_video_geometry_candidate"] is True
    assert payload["operation_kind"] == "video_phase7_geometry_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == "resetRotation"
    assert payload["action"] == "resetRotation"
    assert payload["path"] == "resetRotation"
    assert payload["baseline"] == baseline
    assert payload["requested"] == "resetRotation"
    assert item["executed_operations"] == []
    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase7e_reset_rotation_real_write_action_and_quaternion_rollback(profile: str, cue_type: str) -> None:
    baseline = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, reset_token = _phase7_reset_rotation_fixture(
        profile=profile,
        cue_type=cue_type,
        baseline=baseline,
    )

    reset = reader.update_cues("ws-1", [{**update, "confirm_gates": [reset_token]}], dry_run=False)
    rollback_update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {"quaternion": baseline},
    }
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [reset_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["quaternion"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    reset_address = f"/workspace/ws-1/cue_id/{cue_id}/resetRotation"
    quaternion_address = f"/workspace/ws-1/cue_id/{cue_id}/quaternion"
    assert reset["status"] == "updated"
    assert reset["results"][0]["executed_operations"][0]["operation"] == "action"
    assert reset["results"][0]["executed_operations"][0]["args"] == []
    assert reset["results"][0]["after"]["quaternion"] == [1, 0, 0, 0]
    assert reset["results"][0]["updateq_plan"]["rollback"] == {"property": "quaternion", "value": baseline}
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["quaternion"] == baseline
    assert [request[0] for request in client.requests].count(reset_address) == 1
    assert [request[0] for request in client.requests].count(quaternion_address) == 1


def test_phase7e_reset_rotation_token_boundaries_reject_before_action() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0.1, 0.995]
    v3_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [1, 0, 0, 0]}}],
        dry_run=True,
    )
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]
    reset_update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"resetRotation": True}}
    reset_plan = reader.update_cues("ws-1", [reset_update], dry_run=True)
    reset_token = planned_setters(reset_plan["results"][0])["resetRotation"]["confirm_token"]
    cases = [
        {**reset_update, "confirm_gates": [v1_token]},
        {**reset_update, "confirm_gates": [v2_token]},
        {**reset_update, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [1, 0, 0, 0]}, "confirm_gates": [reset_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [reset_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [reset_token]},
    ]
    client.requests.clear()

    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/resetRotation", "/quaternion", "/fillStage", "/layer")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [False, None, 1, "true", {}, [], [True]])
def test_phase7e_reset_rotation_invalid_property_values_reject_before_action(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "quaternion": [0, 0, 0.1, 0.995]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"resetRotation": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


def test_phase7e_reset_rotation_structure_rejections_before_action() -> None:
    client, reader, cue_id, update, token = _phase7_reset_rotation_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"resetRotation": True, "quaternion": [1, 0, 0, 0]}, "confirm_gates": [token]}],
        [{**update, "properties": {"resetRotation": True, "fillStage": True}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "resetRotation", "args": {}, "mode": "live"}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": ["confirm:videoGeometryReset:v1:fake"]}],
    ]
    client.requests.clear()

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])

    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


def test_phase7e_reset_rotation_timeout_accepts_only_fresh_quaternion_readback() -> None:
    client, reader, cue_id, update, token = _phase7_reset_rotation_fixture(timeout=True)

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["quaternion"] == [1, 0, 0, 0]
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/resetRotation") == 1


@pytest.mark.parametrize("property_name", ["fillStage", "fillStyle", "layer", "quaternion", "smooth"])
def test_phase7_geometry_invalid_baseline_or_value_rejects_before_setter(property_name: str) -> None:
    values = {
        "fillStage": (False, True),
        "fillStyle": (0, 1),
        "layer": (10, 11),
        "quaternion": ([0, 0, 0, 1], [0, 0, 0.1, 0.995]),
        "smooth": (False, True),
    }
    baseline, requested = values[property_name]
    client, reader, cue_id, update, token = _phase7_geometry_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )
    client.cues[cue_id][property_name] = "bad" if property_name != "fillStyle" else 3

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "bad_value",
    [
        1,
        "0,0,0,1",
        {"a": 0, "b": 0, "c": 0, "d": 1},
        [0, 0, 1],
        [0, 0, 0, 1, 2],
        [0, 0, float("nan"), 1],
        [0, 0, float("inf"), 1],
        [0, 0, [0], 1],
        [0, 0, False, 1],
    ],
)
def test_phase7d_quaternion_invalid_requested_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "quaternion": [0, 0, 0, 1]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/quaternion") for address, _, _ in client.requests)


def test_phase7_geometry_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"fillStage": False}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["fillStage"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["fillStage"] is False


def test_phase7b_layer_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(
        property_name="layer",
        baseline=10,
        requested=11,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"layer": 10}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["layer"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["layer"] == 10


def test_phase7d_quaternion_timeout_and_rollback_contract() -> None:
    baseline = [0, 0, 0, 1]
    requested = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, forward_token = _phase7_geometry_fixture(
        property_name="quaternion",
        baseline=baseline,
        requested=requested,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"quaternion": baseline}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["quaternion"]["confirm_token"]
    client.timeout_set_property = None
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )
    address = f"/workspace/ws-1/cue_id/{cue_id}/quaternion"

    assert forward["status"] == "updated"
    assert forward["results"][0]["after"]["quaternion"] == requested
    assert forward["results"][0]["executed_operations"][0]["args"] == requested
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["quaternion"] == baseline
    assert [request[0] for request in client.requests].count(address) == 2


def test_phase7f_smooth_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(
        property_name="smooth",
        baseline=False,
        requested=True,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"smooth": False}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["smooth"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["smooth"] is False


@pytest.mark.parametrize("profile", ["video_basic", "camera_basic", "text_basic"])
def test_phase7c_keeps_rotation_reset_and_shutters_blocked_before_setter(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cases = [
        {"properties": {"rotation": 1}},
        {"properties": {"rotationType": 1}},
        {"operations": [{"property": "rotate/x", "args": {"value": 1}}]},
        {"operations": [{"property": "rotate/y", "args": {"value": 1}, "mode": "live"}]},
        {"properties": {"shutterTop": 1}},
        {"properties": {"shutterBottom": 1}},
        {"properties": {"shutterLeft": 1}},
        {"properties": {"shutterRight": 1}},
    ]

    for case in cases:
        client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
        reader = QLabReader(client)  # type: ignore[arg-type]
        try:
            result = reader.update_cues(
                "ws-1",
                [{"cue_ref": cue_id, "profile": profile, **case}],
                dry_run=True,
            )
        except UnsafeWriteOperationError:
            assert client.requests == []
            continue
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []
        assert_no_confirm_token(result)
        assert client.requests == []


def test_phase7b_stage_region_geometry_remains_blocked_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "stageName": "Stage 1"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    cases = [
        {"properties": {"stageName": "Stage 2"}},
        {
            "operations": [
                {
                    "property": "stage/regionIndex/moveBy",
                    "args": {"index": 0, "x": 1, "y": 1},
                    "mode": "saved",
                }
            ]
        },
        {
            "operations": [
                {
                    "property": "stage/regionIndex/resetControlPoints",
                    "args": {"index": 0},
                    "mode": "saved",
                }
            ]
        },
    ]

    for case in cases:
        result = reader.update_cues(
            "ws-1",
            [{"cue_ref": cue_id, "profile": "video_basic", **case}],
            dry_run=False,
        )
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    "property_name",
    ["rotation", "shutterTop", "shutterBottom", "shutterLeft", "shutterRight", "doOpacity"],
)
def test_phase3d_skipped_candidates_remain_unregistered(property_name: str) -> None:
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
        reader.update_cue(
            "ws-1",
            "11111111-1111-4111-8111-111111111111",
            {property_name: 1},
            dry_run=True,
            profile="video_basic",
        )


PHASE3E_TEXT_BASIC_CASES = [
    ("text", "Old text", "New\ntext"),
    ("fixedWidth", 0, 640),
    ("text/format/fontSize", 48, 56),
    ("text/format/alignment", "left", "center"),
    ("text/format/fontName", "Helvetica", "Courier New"),
    ("text/format/lineSpacing", 1.0, 1.25),
]


def _phase3e_text_basic_fixture(
    *,
    property_name: str = "text",
    baseline: Any = "Old text",
    requested: Any = "New text",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def _phase3e_text_color_fixture(
    *,
    property_name: str = "text/format/color",
    baseline: list[float] | None = None,
    requested: dict[str, float] | None = None,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    baseline = baseline or [1.0, 1.0, 1.0, 1.0]
    requested = requested or {"red": 0.25, "green": 0.5, "blue": 0.75, "alpha": 1.0}
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: baseline}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "operations": [{"property": property_name, "args": requested}],
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    PHASE3E_TEXT_BASIC_CASES,
)
def test_phase3e_text_basic_dry_run_emits_bound_token(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase3e_text_basic_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = text_basics._decode_phase3e_text_basic_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:textBasic:v1:")
    assert setter["phase3e_text_basic_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3e_text_basic_write"
    assert payload["cue_type"] == "Text"
    assert payload["profile"] == "text_basic"
    assert payload["property"] == property_name
    assert payload["requested"] == text_basics._text_basic_canonical_value(property_name, requested)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    PHASE3E_TEXT_BASIC_CASES,
)
def test_phase3e_text_basic_real_write_sets_once_and_verifies(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize(
    "property_name",
    [
        "text/format/color",
    ],
)
def test_phase3e_text_color_dry_run_real_write_and_rollback(property_name: str) -> None:
    client, reader, cue_id, update, token = _phase3e_text_color_fixture(property_name=property_name)

    plan = reader.update_cues("ws-1", [update], dry_run=True)
    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    rollback_update = {
        **update,
        "operations": [
            {"property": property_name, "args": {"red": 1.0, "green": 1.0, "blue": 1.0, "alpha": 1.0}}
        ],
    }
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])[property_name]["confirm_token"]
    rollback = reader.update_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    setter = planned_setters(plan["results"][0])[property_name]
    assert setter["confirm_token"].startswith("confirm:textBasic:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"][property_name] == [0.25, 0.5, 0.75, 1.0]
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"][property_name] == [1.0, 1.0, 1.0, 1.0]
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{property_name}") == 2


@pytest.mark.parametrize(
    "property_name",
    [
        "text/format/backgroundColor",
        "text/format/shadowColor",
        "text/format/strikethroughColor",
        "text/format/underlineColor",
    ],
)
def test_phase3e_text_runtime_blocked_color_routes_stay_planned_only(property_name: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: [1.0, 1.0, 1.0, 1.0]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "operations": [
            {
                "property": property_name,
                "args": {"red": 0.25, "green": 0.5, "blue": 0.75, "alpha": 1.0},
            }
        ],
    }

    plan = reader.update_cues("ws-1", [update], dry_run=True)
    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textBasic:v1:fake"]}],
        dry_run=False,
    )

    setter = planned_setters(plan["results"][0])[property_name]
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"] == "text_color_changes_need_visual_validation"
    assert_no_confirm_token(plan)
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_phase3e_text_basic_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    client.cue_numbers["v1"] = cue_id
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {"type": "Text", "text": "Old text"}
    cases = [
        [{**update, "confirm_gates": []}],
        [{**update, "confirm_gates": ["confirm:textBasic:v1:fake"]}],
        [{**update, "properties": {"text/format/alignment": "center"}, "confirm_gates": [token]}],
        [{**update, "cue_ref": other_id, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v1", "confirm_gates": [token]}],
        [{**update, "properties": {"text": "New text", "text/format/fontSize": 56}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "operations": [{"property": "text", "args": {"value": "New text"}, "mode": "live"}],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/text") for address, _, _ in client.requests)


def test_phase3e_text_basic_rejects_wrong_profile_type_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    wrong_profile = reader.update_cues(
        "ws-1",
        [{**update, "profile": "video_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Video"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id].update({"type": "Text", "text": "Changed baseline"})
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_profile["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_text_basic_baseline" in stale["results"][0]["errors"]["text"]
    assert all(
        item["executed_operations"] == []
        for result in (wrong_profile, wrong_type, stale)
        for item in result["results"]
    )


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3e_text_basic_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any],
) -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/text") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text", {"rich": "object"}),
        ("text", "x" * 20001),
        ("fixedWidth", -1),
        ("fixedWidth", "640"),
        ("fixedWidth", math.nan),
        ("text/format/fontSize", 0),
        ("text/format/fontSize", 1001),
        ("text/format/fontSize", math.nan),
        ("text/format/fontSize", math.inf),
        ("text/format/alignment", "middle"),
        ("text/format/alignment", "Center"),
        ("text/format/fontName", ""),
        ("text/format/fontName", "Bad\nFont"),
        ("text/format/lineSpacing", -1),
        ("text/format/lineSpacing", math.inf),
    ],
)
def test_phase3e_text_basic_rejects_invalid_values(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    "args",
    [
        {"red": 1, "green": 1, "blue": 1},
        {"red": -0.1, "green": 1, "blue": 1, "alpha": 1},
        {"red": 1.1, "green": 1, "blue": 1, "alpha": 1},
        {"red": True, "green": 1, "blue": 1, "alpha": 1},
        {"red": "1", "green": 1, "blue": 1, "alpha": 1},
        {"red": 1, "green": math.nan, "blue": 1, "alpha": 1},
    ],
)
def test_phase3e_text_color_rejects_invalid_values(args: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "text/format/color": [1, 1, 1, 1]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "operations": [{"property": "text/format/color", "args": args}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text/format", {"fontSize": 56}),
        ("text/format/fontFamilyAndStyle", {"family": "Helvetica", "style": "Regular"}),
        ("text/format/shadowOffset", {"width": 1, "height": 2}),
    ],
)
def test_phase3e_rich_text_properties_remain_blocked(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "text": "Old text"}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []


def test_phase3e_text_basic_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase3e_text_basic_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"text": "Old text"}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["text"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["text"] == "Old text"


def test_phase3e_text_basic_timeout_mismatch_is_uncertain_no_retry(
    no_after_read_retry_delay: None,
) -> None:
    client, reader, _, update, token = _phase3e_text_basic_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/text")]) == 1


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    [
        ("text/format/shadowBlurRadius", 2, 4),
        ("text/format/shadowOffset/width", 1, 3),
        ("text/format/shadowOffset/height", -1, 2),
        ("text/format/underlineStyle", "none", "single"),
        ("text/format/strikethroughStyle", "single", "double"),
    ],
)
def test_phase3f_text_style_dry_run_token_real_write_and_readback(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    """Phase 3F stays blocked until QLab returns reliable fresh readback."""
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: baseline}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: requested},
    }

    plan = reader.update_cues("ws-1", [update], dry_run=True)
    client.requests.clear()
    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert plan["status"] == "preflight_failed"
    assert plan["results"][0]["planned_operations"] == []
    assert "baseline/readback is unavailable" in plan["results"][0]["errors"][property_name]
    assert plan["results"][0]["executed_operations"] == []
    assert_no_confirm_token(plan)
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_phase3f_text_style_rejects_fake_stale_batch_and_non_text() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    other_id = "22222222-2222-4222-8222-222222222222"
    property_name = "text/format/underlineStyle"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {"type": "Text", property_name: "none"},
            other_id: {"type": "Video", property_name: "none"},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: "single"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    assert plan["status"] == "preflight_failed"
    assert_no_confirm_token(plan)
    client.cues[cue_id][property_name] = "double"

    cases = [
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}, {**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "cue_ref": other_id,
                "profile": "video_basic",
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)


def _phase3f_text_style_fixture() -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any]]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    property_name = "text/format/underlineStyle"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Text",
                property_name: "none",
                "text/format/strikethroughStyle": "none",
            }
        },
        cue_numbers={"v1": cue_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: "single"},
    }
    client.requests.clear()
    return client, reader, cue_id, update


def test_phase3f_text_style_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {
        "uniqueID": other_id,
        "type": "Text",
        "text/format/underlineStyle": "none",
    }
    cases = [
        [{**update, "confirm_gates": []}],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "properties": {"text/format/underlineStyle": "double"}, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "properties": {"text/format/strikethroughStyle": "single"},
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "cue_ref": other_id, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "cue_ref": "v1", "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "properties": {
                    "text/format/underlineStyle": "single",
                    "text/format/strikethroughStyle": "single",
                },
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}, {**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "operations": [
                    {
                        "property": "text/format/underlineStyle",
                        "args": {"value": "single"},
                        "mode": "live",
                    }
                ],
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "profile": "video_basic", "confirm_gates": ["confirm:textStyle:v1:fake"]}],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize("cue_type", ["Video", "Camera"])
def test_phase3f_text_style_rejects_video_and_camera_cues(cue_type: str) -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    client.cues[cue_id]["type"] = cue_type

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


def test_phase3f_text_style_token_is_bound_to_workspace() -> None:
    _, _, cue_id, update = _phase3f_text_style_fixture()
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "text/format/underlineStyle": "none"}},
        workspace_id="ws-2",
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-2",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3f_text_style_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any],
) -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


def test_phase3f_text_style_rollback_requires_fresh_token() -> None:
    client, reader, _, update = _phase3f_text_style_fixture()
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )
    rollback_update = {
        **update,
        "properties": {"text/format/underlineStyle": "none"},
    }
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert forward["status"] == "preflight_failed"
    assert old_token["status"] == "preflight_failed"
    assert rollback_plan["status"] == "preflight_failed"
    assert rollback["status"] == "preflight_failed"
    assert_no_confirm_token(rollback_plan)
    assert_no_confirm_token(rollback)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text/format/shadowBlurRadius", -1),
        ("text/format/shadowBlurRadius", math.nan),
        ("text/format/shadowOffset/width", math.inf),
        ("text/format/underlineStyle", "thick"),
        ("text/format/strikethroughStyle", ""),
    ],
)
def test_phase3f_text_style_rejects_invalid_values(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    result = QLabReader(  # type: ignore[arg-type]
        FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    ).update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("operation", "expected_before", "expected_requested"),
    [
        (
            {
                "property": "videoEffect/enabled",
                "args": {"name": "ColorControls", "value": False},
            },
            True,
            False,
        ),
        (
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputBrightness", "setting": 0.75},
            },
            0.5,
            0.75,
        ),
    ],
)
@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_video_fx_phase4b_dry_run_plans_only_known_scalar_change(
    operation: dict[str, Any],
    expected_before: Any,
    expected_requested: Any,
    profile: str,
    cue_type: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": cue_type,
            "videoEffects": [
                {
                    "name": "ColorControls",
                    "enabled": True,
                    "parameters": {"inputBrightness": 0.5, "mode": "normal"},
                }
            ],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile=profile,
        operations=[operation],
    )

    item_plan = result["updateq_plan"]
    setter = planned_setters(result)[operation["property"]]
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    assert setter["planned_only"] is True
    assert setter["video_fx_plan"]["before"] == expected_before
    assert setter["video_fx_plan"]["requested"] == expected_requested
    assert setter["video_fx_plan"]["planned_only"] is True
    assert setter["video_fx_plan"]["expected_setter_address"] == (
        f"/workspace/ws-1/cue_id/{cue_id}/{setter['video_fx_plan']['path']}"
    )
    assert setter["video_fx_plan"]["expected_readback_address"] == (
        setter["video_fx_plan"]["expected_setter_address"]
    )
    assert item_plan["video_fx"]["will_modify_qlab"] is False
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase4b_rejects_unknown_or_non_scalar_parameter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [
                {
                    "name": "ColorControls",
                    "parameters": {
                        "inputVector": [0, 1],
                        "inputColor": [1, 0, 0, 1],
                    },
                }
            ],
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    for parameter_key in ("missing", "inputVector", "inputColor"):
        result = reader.update_cue(
            "ws-1",
            cue_id,
            dry_run=True,
            profile="video_basic",
            operations=[
                {
                    "property": "videoEffect/parameter",
                    "args": {
                        "name": "ColorControls",
                        "parameterKey": parameter_key,
                        "setting": 0.5,
                    },
                }
            ],
        )
        assert result["status"] == "dry_run_preflight_failed"
        assert result["planned_operations"] == []
        assert result["executed_operations"] == []
        assert_no_confirm_token(result)


def test_video_fx_phase4c_dry_run_emits_token_for_flat_input_radius_by_index() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    )

    setter = planned_setters(result)["videoEffectIndex/parameter"]
    payload, error = write_operations._decode_phase4c_video_fx_scalar_confirm_token(setter["confirm_token"])
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert setter["video_fx_plan"]["before"] == 10
    assert setter["video_fx_plan"]["requested"] == 12
    assert setter["video_fx_plan"]["parameters_source"] == "flat_payload"
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["planned_only_reason"] == "video_fx_scalar_requires_confirm_token"
    assert setter["confirm_token"].startswith("confirm:videoFxScalar:v1:")
    assert error is None
    assert payload["operation_kind"] == "video_phase4c_fx_scalar_write"
    assert payload["cue_type"] == "Video"
    assert payload["effect_index"] == 0
    assert payload["parameter_key"] == "inputRadius"
    assert payload["baseline"] == 10.0
    assert payload["requested"] == 12.0
    assert result["updateq_plan"]["real_write_possible"] is True
    assert result["updateq_plan"]["requires_confirm_token"] is True
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase4c_real_write_updates_single_flat_input_radius() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputRadius"] == 12
    assert item["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "videoEffectIndex/parameter",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/videoEffectIndex/0/parameter/inputRadius",
            "args": [12],
            "mode": "saved",
            "capability_gate": "video_effects",
            "status": "ok",
        }
    ]
    assert item["updateq_plan"]["real_write_enabled"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert not any("/live" in address for address, _, _ in client.requests)


def test_video_fx_phase4c_accepts_setter_timeout_when_readback_matches() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    prop = "videoEffectIndex/0/parameter/inputRadius"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
        timeout_set_property=(cue_id, prop),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputRadius"] == 12
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert result["timeout_confirmed_count"] == 1


def test_video_fx_phase4c_rejects_stale_token_and_wrong_requested_value() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 11
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 10
    wrong_value = {
        **update,
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 13},
            }
        ],
        "confirm_gates": [token],
    }
    wrong = reader.update_cues("ws-1", [wrong_value], dry_run=False)

    assert stale["status"] == "preflight_failed"
    assert "stale_video_fx_scalar_baseline" in stale["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert wrong["status"] == "preflight_failed"
    assert "confirm_token does not match" in wrong["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith("/videoEffectIndex/0/parameter/inputRadius") and args
        for address, args, _ in client.requests
    )


def test_video_fx_phase6_dry_run_emits_v2_token_for_flat_input_intensity_by_index() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    )

    setter = planned_setters(result)["videoEffectIndex/parameter"]
    payload, error = write_operations._decode_phase4c_video_fx_scalar_confirm_token(setter["confirm_token"])
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert setter["video_fx_plan"]["before"] == 2.5
    assert setter["video_fx_plan"]["requested"] == 3.5
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["confirm_token"].startswith("confirm:videoFxScalar:v2:")
    assert error is None
    assert payload["version"] == 2
    assert payload["operation_kind"] == "video_phase6_fx_scalar_write"
    assert payload["parameter_key"] == "inputIntensity"
    assert payload["baseline"] == 2.5
    assert payload["requested"] == 3.5
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase6_real_write_updates_single_flat_input_intensity() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputIntensity"] == 3.5
    assert item["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "videoEffectIndex/parameter",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/videoEffectIndex/0/parameter/inputIntensity",
            "args": [3.5],
            "mode": "saved",
            "capability_gate": "video_effects",
            "status": "ok",
        }
    ]
    assert item["updateq_plan"]["after"] == 3.5
    assert not any("/live" in address for address, _, _ in client.requests)


def test_video_fx_phase6_accepts_setter_timeout_when_readback_matches() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    prop = "videoEffectIndex/0/parameter/inputIntensity"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
        timeout_set_property=(cue_id, prop),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputIntensity"] == 3.5
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert result["timeout_confirmed_count"] == 1


def test_video_fx_scalar_v1_and_v2_tokens_are_not_cross_authorized() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    radius_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    intensity_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    v1_token = planned_setters(reader.update_cues("ws-1", [radius_update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]
    v2_token = planned_setters(reader.update_cues("ws-1", [intensity_update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    v1_for_v2 = reader.update_cues("ws-1", [{**intensity_update, "confirm_gates": [v1_token]}], dry_run=False)
    v2_for_v1 = reader.update_cues("ws-1", [{**radius_update, "confirm_gates": [v2_token]}], dry_run=False)

    assert v1_for_v2["status"] == "preflight_failed"
    assert v2_for_v1["status"] == "preflight_failed"
    assert "confirm_token does not match" in v1_for_v2["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "confirm_token does not match" in v2_for_v1["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith(("/videoEffectIndex/0/parameter/inputIntensity", "/videoEffectIndex/0/parameter/inputRadius"))
        and args
        for address, args, _ in client.requests
    )


def test_video_fx_phase6_rejects_stale_token_wrong_value_and_payload_drift() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    client.cues[cue_id]["videoEffects"][0]["inputIntensity"] = 2.75
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputIntensity"] = 2.5
    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 11
    drift = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 10
    wrong_value = {
        **update,
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 4.0},
            }
        ],
        "confirm_gates": [token],
    }
    wrong = reader.update_cues("ws-1", [wrong_value], dry_run=False)

    assert stale["status"] == "preflight_failed"
    assert drift["status"] == "preflight_failed"
    assert wrong["status"] == "preflight_failed"
    assert "stale_video_fx_scalar_baseline" in stale["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "stale_video_fx_scalar_baseline" in drift["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "confirm_token does not match" in wrong["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith("/videoEffectIndex/0/parameter/inputIntensity") and args
        for address, args, _ in client.requests
    )


@pytest.mark.parametrize("parameter_key", ["inputPower", "Choose_Effect", "missing"])
def test_video_fx_phase6_dry_run_does_not_emit_token_for_other_flat_parameters(parameter_key: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputPower": 1, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": parameter_key, "setting": 2},
            }
        ],
    )

    assert result["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("update_patch", "cue_values", "expected_fragment"),
    [
        ({"profile": "camera_basic"}, {"type": "Camera"}, "gated or dry-run only"),
        ({"profile": "text_basic"}, {"type": "Text"}, "gated or dry-run only"),
        ({"cue_ref": "v11"}, {"type": "Video"}, "exact cue UUID"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "mode": "live", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "saved mode"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 1, "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffect/parameter", "args": {"name": "Blur", "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffectIndex/enabled", "args": {"index": 0, "value": False}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": "high"}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": [1, 0, 0, 1]}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": {"value": 3.5}}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5}}, {"property": "opacity", "args": {"value": 0.5}}]}, {"type": "Video"}, "exactly one property"),
        ({}, {"type": "Video", "isBroken": True}, "healthy cue"),
        ({}, {"type": "Video", "isRunning": True}, "inactive cue"),
    ],
)
def test_video_fx_phase6_rejects_blocked_real_write_shapes(
    update_patch: dict[str, Any],
    cue_values: dict[str, Any],
    expected_fragment: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
        "confirm_gates": ["confirm:videoFxScalar:v2:fake"],
    }
    update.update(update_patch)
    cue = {
        "type": "Video",
        "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        **cue_values,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue},
        cue_numbers={"v11": cue_id},
    )

    result = QLabReader(client).update_cues("ws-1", [update], dry_run=False)  # type: ignore[arg-type]

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert expected_fragment in str(result["results"][0]["errors"])


def test_video_fx_phase4b_rejects_type_mismatch_and_ambiguous_name() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [
                {"name": "Blur", "parameters": {"inputRadius": 5}},
                {"name": "Blur", "parameters": {"inputRadius": 10}},
            ],
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    ambiguous = reader.update_cue(
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffect/parameter",
                "args": {"name": "Blur", "parameterKey": "inputRadius", "setting": 6},
            }
        ],
    )
    mismatch = reader.update_cue(
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": "six"},
            }
        ],
    )

    assert "ambiguous" in ambiguous["errors"]["videoEffect/parameter"]
    assert "type mismatch" in mismatch["errors"]["videoEffectIndex/parameter"]
    assert ambiguous["executed_operations"] == []
    assert mismatch["executed_operations"] == []
    assert_no_confirm_token(ambiguous)
    assert_no_confirm_token(mismatch)


def test_video_fx_phase4b_real_live_batch_and_multi_property_stay_blocked() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue = {
        "type": "Video",
        "videoEffects": [
            {
                "name": "ColorControls",
                "enabled": True,
                "parameters": {"inputBrightness": 0.5},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    enabled = {
        "property": "videoEffect/enabled",
        "args": {"name": "ColorControls", "value": False},
    }
    parameter = {
        "property": "videoEffect/parameter",
        "args": {
            "name": "ColorControls",
            "parameterKey": "inputBrightness",
            "setting": 0.75,
        },
    }
    cases = [
        (
            False,
            [{"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]}],
        ),
        (
            True,
            [
                {
                    "cue_ref": cue_id,
                    "profile": "video_basic",
                    "operations": [{**enabled, "mode": "live"}],
                }
            ],
        ),
        (
            False,
            [
                {"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]},
                {"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]},
            ],
        ),
        (
            False,
            [
                {
                    "cue_ref": cue_id,
                    "profile": "video_basic",
                    "operations": [enabled, parameter],
                }
            ],
        ),
    ]

    for dry_run, updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=dry_run)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)
    assert not any(
        "/videoEffect" in address and not address.endswith("/valuesForKeys")
        for address, _, _ in client.requests
    )


@pytest.mark.parametrize("profile,cue_type", [("video_basic", "Video"), ("camera_basic", "Camera")])
def test_phase3e_text_properties_not_enabled_for_video_or_camera(
    profile: str,
    cue_type: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": profile, "properties": {"text": "Blocked"}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


def test_video_phase2_wrong_cue_type_failure_has_no_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio", "opacity": 1},
    )
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "profile" in result["results"][0]["errors"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["anchor", "translation", "scale", "crop"])
def test_video_phase2_rejects_aggregate_geometry(property_name: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    args = {"x": 1, "y": 2} if property_name != "crop" else {
        "top": 1,
        "bottom": 2,
        "left": 3,
        "right": 4,
    }
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": property_name, "args": args, "mode": "saved"}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "aggregate geometry" in result["results"][0]["errors"][property_name]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert client.requests == []


@pytest.mark.parametrize("cue_ref", ["1", "not-a-uuid"])
def test_video_phase2_requires_exact_cue_uuid(cue_ref: str) -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_ref, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "exact cue UUID" in result["results"][0]["errors"]["video_phase2"]
    assert result["results"][0]["executed_operations"] == []
    assert client.requests == []


def test_video_phase2_rejects_batch_second_property_and_confirm_gates() -> None:
    cue_a = "11111111-1111-4111-8111-111111111111"
    cue_b = "22222222-2222-4222-8222-222222222222"
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]
    cases = [
        [
            {"cue_ref": cue_a, "profile": "video_basic", "properties": {"opacity": 0.8}},
            {"cue_ref": cue_b, "profile": "video_basic", "properties": {"opacity": 0.7}},
        ],
        [
            {
                "cue_ref": cue_a,
                "profile": "video_basic",
                "properties": {"opacity": 0.8, "translation/x": 10},
            }
        ],
        [
            {
                "cue_ref": cue_a,
                "profile": "video_basic",
                "properties": {"opacity": 0.8},
                "confirm_gates": ["confirm:opacity:fabricated"],
            }
        ],
    ]

    for updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=True)
        assert result["ok"] is False
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert all(item["planned_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)


def test_video_phase2_rejects_fresh_unique_id_mismatch() -> None:
    cue_ref = "11111111-1111-4111-8111-111111111111"
    returned_id = "22222222-2222-4222-8222-222222222222"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_ref,
        cue_values={"uniqueID": returned_id, "type": "Video", "opacity": 1},
    )
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_ref, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "exactly match" in result["results"][0]["errors"]["cue_ref"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["rotation", "rotate/x", "rotate/y", "rotate/z"])
def test_video_phase2_rejects_unregistered_rotation_family_with_empty_execution(
    property_name: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {property_name: 10}}],
        dry_run=True,
    )

    item = result["results"][0]
    assert result["ok"] is False
    assert "rotation" in item["errors"][property_name]
    assert item["planned_operations"] == []
    assert item["executed_operations"] == []
    assert_no_confirm_token(result)
    assert client.requests == []


@pytest.mark.parametrize(
    ("update", "property_name", "suggestion_fragment"),
    [
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "translation/x", "args": {"value": 1}, "mode": "live"}],
            },
            "translation/x",
            "saved-mode dry-run",
        ),
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "translation", "args": {"x": 1, "y": 2}}],
            },
            "translation",
            "translation/x and translation/y",
        ),
        (
            {"profile": "video_basic", "properties": {"rotation": 10}},
            "rotation",
            "rotation phase",
        ),
        (
            {"profile": "video_basic", "properties": {"fileTarget": "/tmp/video.mov"}},
            "fileTarget",
            "outside current Video write scope",
        ),
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
            },
            "videoEffects/add",
            "later Video FX phase",
        ),
    ],
)
def test_video_phase2_rejections_include_updateq_plan(
    update: dict[str, Any], property_name: str, suggestion_fragment: str
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1", [{"cue_ref": cue_id, **update}], dry_run=True
    )

    item = result["results"][0]
    plan = item["updateq_plan"]
    assert result["ok"] is False
    assert plan["status"] == "rejected"
    assert plan["property"] == property_name
    assert plan["reason"]
    assert plan["planned_mutation"] is False
    assert plan["real_write_enabled"] is False
    assert plan["real_write_possible"] is False
    assert plan["requires_confirm_token"] is False
    assert suggestion_fragment.casefold() in plan["suggestion"].casefold()
    assert plan["safety"]["will_modify_qlab"] is False
    assert item["planned_operations"] == []
    assert item["executed_operations"] == []
    assert_no_confirm_token(result)


def test_video_phase2_fresh_read_is_uncached(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    original = reader.read_cue_values
    calls: list[dict[str, Any]] = []

    def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(reader, "read_cue_values", spy)
    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert calls and calls[0]["cacheable"] is False


def test_video_phase2_rejects_live_and_scalar_rotation_but_keeps_fade_rotation() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="does not support mode 'live'"):
        reader.update_cue(
            "ws-1",
            "1",
            dry_run=True,
            profile="video_basic",
            operations=[{"property": "translation/x", "args": {"value": 1}, "mode": "live"}],
        )
    for profile in ("video_basic", "camera_basic"):
        with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
            reader.update_cue("ws-1", "1", {"rotation": 10}, dry_run=True, profile=profile)

    assert "rotation" in profile_catalog()["fade_basic"]["properties"]
    assert client.requests == []


def test_update_cue_text_color_components_use_qlab_unit_interval() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="text/format/color.red must be a number from 0 to 1"):
        reader.update_cue(
            "ws-1",
            "1",
            operations=[{"property": "text/format/color", "args": {"red": 255, "green": 0, "blue": 0, "alpha": 1}}],
            dry_run=True,
            profile="text_basic",
        )

    assert client.requests == []


def test_update_cue_text_basic_rejects_non_text_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "text": "Not a Text cue"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Text cue"):
        reader.update_cue("ws-1", cue_id, {"text": "New text"}, dry_run=True, profile="text_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/text" not in addresses


def test_update_cue_operations_dry_run_builds_structured_osc_paths() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {
                "property": "level",
                "args": {"inChannel": 1, "outChannel": 2, "decibel": -6},
                "mode": "live",
            }
        ],
        dry_run=True,
        profile="audio_basic",
    )

    setters = [operation for operation in result["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert result["properties"] == {}
    assert setters[0]["confirm_token"].startswith("confirm:level:")
    setters[0].pop("confirm_token")
    assert setters == [
        {
            "operation": "set_property",
            "property": "level",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/level/1/2/live",
            "args": [-6],
            "mode": "live",
            "risk_tier": "high",
            "real_write_enabled": False,
            "planned_only_reason": "audio_levels_can_affect_live_output",
            "capability_gate": "audio_output",
        }
    ]
    assert result["executed_operations"] == []


def test_update_cue_audio_dry_run_builds_slice_level_object_and_patch_paths() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
            {"property": "deleteSliceMarker", "args": {"index": 2}},
            {"property": "deleteSliceMarkers", "args": {}},
            {"property": "setDefaultLevels", "args": {}},
            {"property": "sliderLevel", "args": {"channel": 0, "decibel": "-inf"}, "mode": "live"},
            {"property": "objectIDLevel", "args": {"row": 0, "objectID": "obj-1", "decibel": -12}},
            {"property": "objectID/position", "args": {"objectID": "obj-1", "x": 1.25, "y": -2}},
            {"property": "audioOutputPatch/level", "args": {"inChannel": 0, "outChannel": 1, "decibel": -3}},
            {"property": "audioOutputPatch/routing/reset", "args": {}},
            {"property": "audioMap/objectID/colorName", "args": {"objectID": "map-obj-1", "colorName": "sky blue"}},
        ],
        dry_run=True,
        profile="audio_basic",
    )

    setters = [operation for operation in result["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert [setter["address"] for setter in setters] == [
        f"/workspace/ws-1/cue_id/{cue_id}/sliceMarker/0/time",
        f"/workspace/ws-1/cue_id/{cue_id}/sliceMarker/0/playCount",
        f"/workspace/ws-1/cue_id/{cue_id}/deleteSliceMarker/2",
        f"/workspace/ws-1/cue_id/{cue_id}/deleteSliceMarkers",
        f"/workspace/ws-1/cue_id/{cue_id}/setDefaultLevels",
        f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/0/live",
        f"/workspace/ws-1/cue_id/{cue_id}/objectIDLevel/0/obj-1",
        f"/workspace/ws-1/cue_id/{cue_id}/objectID/obj-1/position",
        f"/workspace/ws-1/cue_id/{cue_id}/audioOutputPatch/level/0/1",
        f"/workspace/ws-1/cue_id/{cue_id}/audioOutputPatch/routing/reset",
        f"/workspace/ws-1/cue_id/{cue_id}/audioMap/objectID/map-obj-1/colorName",
    ]
    assert [setter["args"] for setter in setters] == [
        [1.5],
        [-1],
        [],
        [],
        [],
        ["-inf"],
        [-12],
        [1.25, -2],
        [-3],
        [],
        ["sky blue"],
    ]
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert result["executed_operations"] == []


def test_update_cues_audio_invalid_structured_operation_has_no_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [
                    {"property": "level", "args": {"inChannel": 25, "outChannel": 1, "decibel": -6}}
                ],
            },
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [
                    {"property": "sliderLevel", "args": {"channel": 1, "decibel": "loud"}}
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "level.inChannel must be an integer from 0 to 24" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "sliderLevel.decibel must be a number or '-inf'" in result["results"][1]["errors"]["validation"]
    assert result["results"][1]["planned_operations"] == []


def test_update_cue_operations_support_video_text_and_midi_dry_run_shapes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "blendMode": "Normal"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    video_updates = [({"blendMode": "Normal"}, None)]
    video_setters = []
    for properties, operations in video_updates:
        result = video.update_cue(
            "ws-1", cue_id, properties=properties, operations=operations, dry_run=True, profile="video_basic"
        )
        video_setters.extend(op for op in result["planned_operations"] if op["operation"] == "set_property")

    text_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text/format/alignment": "left",
        },
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    text_result = text.update_cue(
        "ws-1",
        cue_id,
        operations=[{"property": "text/format/alignment", "args": {"value": "center"}}],
        dry_run=True,
        profile="text_basic",
    )

    midi_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "MIDI"},
    )
    midi = QLabReader(midi_client)  # type: ignore[arg-type]
    midi_result = midi.update_cue(
        "ws-1",
        cue_id,
        properties={"channel": 1, "byte1": 64},
        dry_run=True,
        profile="midi_basic",
    )

    text_setters = [op for op in text_result["planned_operations"] if op["operation"] == "set_property"]
    midi_setters = [op["address"] for op in midi_result["planned_operations"] if op["operation"] == "set_property"]
    assert [(op["property"], op["address"], op["args"]) for op in video_setters] == [
        ("blendMode", f"/workspace/ws-1/cue_id/{cue_id}/blendMode", ["Normal"]),
    ]
    assert [(op["property"], op["address"], op["args"]) for op in text_setters] == [
        ("text/format/alignment", f"/workspace/ws-1/cue_id/{cue_id}/text/format/alignment", ["center"]),
    ]
    assert midi_setters == [f"/workspace/ws-1/cue_id/{cue_id}/channel", f"/workspace/ws-1/cue_id/{cue_id}/byte1"]


def test_update_cue_real_blocks_dry_run_only_profiles_and_properties_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        video.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "crop", "args": {"top": 1, "bottom": 2, "left": 3, "right": 4}}],
            dry_run=False,
            profile="video_basic",
        )
    assert video_client.requests == []

    video_fx_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "videoEffects": []},
    )
    video_fx = QLabReader(video_fx_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        video_fx.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
            dry_run=False,
            profile="video_basic",
        )
    assert video_fx_client.requests == []

    text_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Text", "text/format/shadowOffset": [0, 0]},
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        text.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "text/format/shadowOffset", "args": {"width": 2, "height": 4}}],
            dry_run=False,
            profile="text_basic",
        )
    assert text_client.requests == []

    audio_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    audio = QLabReader(audio_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        audio.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
            dry_run=False,
            profile="audio_basic",
        )
    assert audio_client.requests == []

    for profile, cue_type, properties in (
        ("light_basic", "Light", {"lightCommandText": "1 thru 5 @ 80"}),
        ("network_basic", "Network", {"customString": "/eos/cue/1/fire"}),
        ("midi_basic", "MIDI", {"note": 64}),
        ("timecode_basic", "Timecode", {"timecodeString": "01:00:00:00"}),
        ("script_basic", "Script", {"scriptSource": "display dialog \"blocked\""}),
    ):
        client = FakeWriteClient(
            QLabConfig(enable_write=True, passcode="server-pass"),
            existing_cue_id=cue_id,
            cue_values={"uniqueID": cue_id, "type": cue_type},
        )
        reader = QLabReader(client)  # type: ignore[arg-type]
        with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
            reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)
        assert client.requests == []

    fade_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Fade"},
    )
    fade = QLabReader(fade_client)  # type: ignore[arg-type]
    fade_result = fade.update_cue("ws-1", cue_id, {"targetMode": 0}, dry_run=False, profile="fade_basic")
    assert fade_result["status"] == "preflight_failed"
    assert fade_result["executed_operations"] == []
    assert not any(address.endswith("/targetMode") for address, _, _ in fade_client.requests)

    light_op_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Light"},
    )
    light_op = QLabReader(light_op_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        light_op.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "setLight", "args": {"instrument_or_group": "1", "setting": 50}}],
            dry_run=False,
            profile="light_basic",
        )
    assert light_op_client.requests == []


def test_update_cue_real_allows_gated_common_property_with_explicit_gate() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "duckLevel": -12},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, cue_id, {"properties": {"duckLevel": -6}})

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"duckLevel": -6},
        dry_run=False,
        confirm_gates=[token],
    )

    assert result["ok"] is True
    assert result["after"]["duckLevel"] == -6
    assert result["confirm_gates"] == [token]
    assert result["executed_operations"][0]["capability_gate"] == "cue_behavior"


def test_update_cues_real_operation_with_readback_verifies_as_updated() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "secondColorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "common",
                "operations": [{"property": "secondColorName", "args": {"value": "red"}}],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["status"] == "updated"
    assert result["results"][0]["after"]["secondColorName"] == "red"
    assert result["results"][0]["errors"] is None


def test_update_cues_confirm_token_is_bound_to_cue_ref() -> None:
    cue_a = "11111111-1111-4111-8111-111111111111"
    cue_b = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_a: {"type": "Audio"}, cue_b: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "profile": "audio_basic",
        "operations": [{"property": "objectIDLevel", "args": {"row": 1, "objectID": "object-1", "decibel": -6}}],
    }

    token_a = confirm_token_for(reader, cue_a, update)
    token_b = confirm_token_for(reader, cue_b, update)

    assert token_a.startswith("confirm:objectIDLevel:")
    assert token_a != token_b


def test_update_cue_timecode_frame_rate_uses_documented_framerate_path() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Timecode", "framerate": 3},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"timecodeFrameRate": 0},
        dry_run=True,
        profile="timecode_basic",
    )

    planned_setters = [
        operation for operation in result["planned_operations"] if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["properties"] == {"framerate": 0}
    assert planned_setters == [
        {
            "operation": "set_property",
            "property": "timecodeFrameRate",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/framerate",
            "args": [0],
            "mode": "saved",
            "risk_tier": "medium",
            "real_write_enabled": True,
            "capability_gate": None,
        }
    ]


def test_update_cue_timecode_rejects_invalid_output_type_and_frame_rate() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="outputType must be 0 for MTC or 1 for LTC"):
        reader.update_cue("ws-1", "1", {"outputType": 2}, dry_run=True, profile="timecode_basic")

    with pytest.raises(UnsafeWriteOperationError, match="timecodeFrameRate must be a timecode frame rate index"):
        reader.update_cue("ws-1", "1", {"timecodeFrameRate": 8}, dry_run=True, profile="timecode_basic")

    assert client.requests == []


def test_update_cues_mic_basic_dry_run_plans_documented_mic_and_audio_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Mic", "channels": 1, "channelOffset": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "mic_basic",
                "properties": {
                    "channels": 2,
                    "channelOffset": 1,
                    "audioInputPatchID": "input-patch",
                    "audioOutputPatchName": "Main",
                },
                "operations": [
                    {"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}},
                    {"property": "mute", "args": {"output": 1, "value": True}},
                ],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["channels"]["real_write_enabled"] is False
    assert setters["channels"]["planned_only_reason"] == "audio_input_channel_count_needs_patch_bounds_validation"
    assert setters["channelOffset"]["real_write_enabled"] is False
    assert setters["channelOffset"]["capability_gate"] == "patch_routing"
    for prop in ("channelOffset", "audioInputPatchID", "audioOutputPatchName", "level", "mute"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]
    assert setters["level"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/level/1/1"
    assert setters["level"]["args"] == [-6]
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_mic_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    mic_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={mic_id: {"type": "Mic"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channels": 0}},
            {"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channelOffset": -1}},
            {
                "cue_ref": mic_id,
                "profile": "mic_basic",
                "operations": [{"property": "level", "args": {"inChannel": 25, "outChannel": 1, "decibel": -6}}],
            },
            {"cue_ref": memo_id, "profile": "mic_basic", "properties": {"channels": 2}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 4
    assert result["results"][0]["errors"]["validation"] == "channels must be a positive integer"
    assert result["results"][1]["errors"]["validation"] == "channelOffset must be a non-negative integer"
    assert "level.inChannel must be an integer from 0 to 24" in result["results"][2]["errors"]["validation"]
    assert result["results"][3]["errors"]["profile"] == "mic_basic update profile requires a Mic cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_mic_channel_offset_blocks_real_write_without_patch_gate() -> None:
    mic_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={mic_id: {"type": "Mic", "channelOffset": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channelOffset": 1}}],
        dry_run=False,
    )
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "channelOffset" in result["results"][0]["errors"]["channelOffset"]
    assert all(not request[0].endswith("/channelOffset") for request in client.requests)


def test_update_cues_timecode_basic_dry_run_plans_ltc_mtc_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Timecode", "outputType": 1, "framerate": 3, "ltcChannel": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "timecode_basic",
                "properties": {
                    "outputType": 0,
                    "timecodeFrameRate": 7,
                    "startTime": "01:00:00:00",
                    "endTime": "01:00:10:00",
                    "ltcChannel": 2,
                    "midiPatchID": "midi-patch",
                    "audioOutputPatchNumber": 1,
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["timecodeFrameRate"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/framerate"
    assert setters["timecodeFrameRate"]["real_write_enabled"] is True
    assert setters["outputType"]["real_write_enabled"] is True
    for prop in ("ltcChannel", "midiPatchID", "audioOutputPatchNumber"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]


def test_update_cues_timecode_basic_invalid_ltc_and_profile_mismatch_have_no_plan() -> None:
    timecode_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={timecode_id: {"type": "Timecode"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": timecode_id, "profile": "timecode_basic", "properties": {"ltcChannel": 0}},
            {"cue_ref": memo_id, "profile": "timecode_basic", "properties": {"outputType": 0}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "ltcChannel must be a positive integer"
    assert result["results"][1]["errors"]["profile"] == "timecode_basic update profile requires a Timecode cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_midi_file_basic_dry_run_plans_playback_and_patch_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "MIDI File", "rate": 1, "playCount": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "midi_file_basic",
                "properties": {
                    "fileTarget": "/show/foo.mid",
                    "rate": 1.25,
                    "startTime": 0,
                    "endTime": 8,
                    "duration": 8,
                    "playCount": 2,
                    "midiPatchName": "Synth",
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    for prop in ("rate", "startTime", "endTime", "duration", "playCount"):
        assert setters[prop]["real_write_enabled"] is True
    for prop in ("fileTarget", "midiPatchName"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]


def test_update_cues_midi_file_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    midi_file_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={midi_file_id: {"type": "MIDI File"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"rate": 0.01}},
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"playCount": 0}},
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"duration": -1}},
            {"cue_ref": memo_id, "profile": "midi_file_basic", "properties": {"rate": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert "rate must be a number from 0.03 to 33.0" in result["results"][0]["errors"]["validation"]
    assert result["results"][1]["errors"]["validation"] == "playCount must be a positive integer"
    assert result["results"][2]["errors"]["validation"] == "duration must be a non-negative number"
    assert result["results"][3]["errors"]["profile"] == "midi_file_basic update profile requires a MIDI File cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_midi_basic_dry_run_plans_documented_message_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "MIDI", "messageType": 1, "status": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "midi_basic",
                "properties": {
                    "midiPatchID": "midi-patch",
                    "messageType": 2,
                    "channel": 16,
                    "command": 1,
                    "commandFormat": 2,
                    "status": 6,
                    "note": 64,
                    "velocity": 100,
                    "programChange": 10,
                    "pitchBend": 8192,
                    "byte1": 65,
                    "byte2": 66,
                    "byteCombo": 1024,
                    "controlNumber": 7,
                    "controlValue": 127,
                    "deviceID": 1,
                    "endValue": 127,
                    "macro": 2,
                    "rawString": "7E 7F 09 01",
                    "qList": "1",
                    "qNumber": "2",
                    "qPath": "3",
                    "timecodeString": "01:00:00:00",
                    "timecodeFormat": 3,
                    "doFade": True,
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["note"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byte1"
    assert setters["velocity"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byte2"
    assert setters["pitchBend"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byteCombo"
    for setter in setters.values():
        assert setter["real_write_enabled"] is False
        assert setter["planned_only_reason"]


def test_update_cues_midi_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    midi_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={midi_id: {"type": "MIDI"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"messageType": 4}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"channel": 17}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"byte1": 128}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"byteCombo": 16384}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"status": 7}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"timecodeFormat": 4}},
            {"cue_ref": memo_id, "profile": "midi_basic", "properties": {"channel": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "messageType must be 1 for MIDI voice, 2 for MSC, or 3 for SysEx"
    assert result["results"][1]["errors"]["validation"] == "channel must be an integer from 1 to 16"
    assert result["results"][2]["errors"]["validation"] == "byte1 must be an integer from 0 to 127"
    assert result["results"][3]["errors"]["validation"] == "byteCombo must be an integer from 0 to 16383"
    assert result["results"][4]["errors"]["validation"] == "status must be an integer from 0 to 6"
    assert result["results"][5]["errors"]["validation"] == (
        "timecodeFormat must be 0 for 24 fps, 1 for 25 fps, 2 for 30 fps drop, or 3 for 30 fps non-drop"
    )
    assert result["results"][6]["errors"]["profile"] == "midi_basic update profile requires a MIDI cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_network_basic_dry_run_plans_documented_non_ambiguous_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            cue_id: {
                "type": "Network",
                "customString": "/cue/1/start",
                "networkPatchType": "OSC Message",  # synthetic fixture data is not a documented safety signal.
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "network_basic",
                "properties": {
                    "customString": "/eos/cue/1/fire",
                    "networkPatchID": "net-patch",
                    "fadeType": 1,
                    "parameterValues": [1, "go"],
                },
                "operations": [{"property": "parameterValue", "args": {"parameter": "cueName", "value": "Intro"}}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["parameterValue"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/parameterValue/cueName"
    assert setters["parameterValue"]["args"] == ["Intro"]
    assert setters["customString"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert setters["networkPatchID"]["planned_only_reason"] == "network_osc_message_requires_patch_type_validation"
    assert setters["fadeType"]["planned_only_reason"] == "network_fade_routes_require_deterministic_readback"
    for setter in setters.values():
        assert setter["real_write_enabled"] is False
        assert setter["planned_only_reason"]
    assert_no_confirm_token(result)

    real = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "network_basic", "properties": {"customString": "/eos/cue/2/fire"}}],
        dry_run=False,
    )
    assert real["status"] == "preflight_failed"
    assert all(not address.endswith("/customString") for address, _, _ in client.requests)


def test_network_patch_type_classifier_is_exact_and_fail_closed() -> None:
    assert classify_network_patch_type("OSC Message - Main OSC") == "OSC Message"
    assert classify_network_patch_type("Plain Text - Console") == "Plain Text"
    assert classify_network_patch_type("Hex Codes - Device") == "Hex Codes"
    assert classify_network_patch_type("QLab 5 - Go") == "QLab 5"
    assert classify_network_patch_type("Go Button 3 - Cue") == "Go Button 3"
    assert classify_network_patch_type("d&b DS100 - Matrix") == "d&b DS100"
    assert classify_network_patch_type("OSC Message - ") is None
    assert classify_network_patch_type("osc message - Main OSC") is None
    assert classify_network_patch_type("OSC Message Main OSC") is None
    assert classify_network_patch_type("OSC Message - Plain Text - Imitation") is None


def test_update_cues_network_osc_message_gate_tokens_and_patch_classification() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    osc_one = "22222222-2222-4222-8222-222222222222"
    osc_two = "33333333-3333-4333-8333-333333333333"
    plain = "44444444-4444-4444-8444-444444444444"
    patches = [
        {"uniqueID": osc_one, "name": "OSC Message - One"},
        {"uniqueID": osc_two, "name": "OSC Message - Two"},
        {"uniqueID": plain, "name": "Plain Text - Plain"},
    ]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            source_id: {
                "type": "Network",
                "networkPatchID": osc_one,
                "networkPatchName": "One",
                "customString": "/cue/1/start",
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
        network_patches=patches,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/cue/1/stop"}}
    dry = reader.update_cues("ws-1", [request], dry_run=True)
    token = planned_setters(dry["results"][0])["customString"]["confirm_token"]
    assert token.startswith("confirm:networkOscMessage:v1:")
    assert dry["results"][0]["executed_operations"] == []
    real = reader.update_cues("ws-1", [{**request, "confirm_gates": [token]}], dry_run=False)
    assert real["status"] == "updated"
    assert client.cues[source_id]["customString"] == "/cue/1/stop"

    rollback_request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/cue/1/start"}}
    rollback_dry = reader.update_cues("ws-1", [rollback_request], dry_run=True)
    rollback_token = planned_setters(rollback_dry["results"][0])["customString"]["confirm_token"]
    rollback = reader.update_cues("ws-1", [{**rollback_request, "confirm_gates": [rollback_token]}], dry_run=False)
    assert rollback["status"] == "updated"
    assert client.cues[source_id]["customString"] == "/cue/1/start"

    patch_request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"networkPatchID": osc_two}}
    patch_dry = reader.update_cues("ws-1", [patch_request], dry_run=True)
    patch_setter = planned_setters(patch_dry["results"][0])["networkPatchID"]
    assert patch_setter["real_write_enabled"] is False
    assert "confirm_token" not in patch_setter
    patch_real = reader.update_cues(
        "ws-1", [{**patch_request, "confirm_gates": ["confirm:networkOscMessage:v1:fake:fake"]}], dry_run=False
    )
    assert patch_real["status"] == "preflight_failed"
    assert client.cues[source_id]["networkPatchID"] == osc_one
    assert all(not address.endswith("/networkPatchID") for address, _, _ in client.requests)


def test_network_osc_message_gate_rejects_negative_shapes_and_tokens() -> None:
    source_id = "11111111-1111-4111-8111-111111111111"
    osc_id = "22222222-2222-4222-8222-222222222222"
    plain_id = "33333333-3333-4333-8333-333333333333"
    cue = {
        "type": "Network",
        "networkPatchID": osc_id,
        "customString": "/cue/1/start",
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    patches = [
        {"uniqueID": osc_id, "name": "OSC Message - One"},
        {"uniqueID": plain_id, "name": "Plain Text - Plain"},
    ]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: cue},
        network_patches=patches,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    base = {"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/cue/1/stop"}}
    token = planned_setters(reader.update_cues("ws-1", [base], dry_run=True)["results"][0])["customString"]["confirm_token"]
    fake = reader.update_cues("ws-1", [{**base, "confirm_gates": ["confirm:networkOscMessage:v1:fake:fake"]}], dry_run=False)
    wrong = reader.update_cues("ws-1", [{**base, "confirm_gates": ["confirm:devamp:v1:fake:fake"]}], dry_run=False)
    client.network_patches[0]["name"] = "Plain Text - Changed"
    stale = reader.update_cues("ws-1", [{**base, "confirm_gates": [token]}], dry_run=False)
    assert fake["status"] == wrong["status"] == stale["status"] == "preflight_failed"
    assert fake["results"][0]["errors"]
    assert wrong["results"][0]["errors"]
    assert stale["results"][0]["errors"]
    assert all(not address.endswith("/customString") for address, _, _ in client.requests)

    batch = reader.update_cues("ws-1", [{**base, "confirm_gates": [token]}, {**base, "confirm_gates": [token]}], dry_run=False)
    multi = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/cue/1/a", "networkPatchID": osc_id}, "confirm_gates": [token]}],
        dry_run=False,
    )
    live = reader.update_cues(
        "ws-1",
        [{"cue_ref": source_id, "profile": "network_basic", "operations": [{"property": "customString", "args": {"value": "/cue/1/a"}, "mode": "live"}]}],
        dry_run=True,
    )
    assert batch["status"] == multi["status"] == live["status"] == "preflight_failed"
    assert "exactly one cue update" in batch["results"][0]["errors"]["customString"]
    assert "exactly one property" in multi["results"][0]["errors"]["customString"]
    assert "does not support mode 'live'" in live["results"][0]["errors"]["validation"]


def test_network_repair_custom_string_and_validation() -> None:
    workspace_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    source_id = "11111111-1111-4111-8111-111111111111"
    osc_id = "22222222-2222-4222-8222-222222222222"
    plain_id = "33333333-3333-4333-8333-333333333333"
    requested = "/codex/network/test 13"
    cue = {
        "type": "Network",
        "networkPatchID": osc_id,
        "customString": "",
        "message": "{custom}",
        "messageError": "Message '{custom}' is not a legal OSC address.",
        "isBroken": True,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: cue},
        workspace_id=workspace_id,
        network_patches=[
            {"uniqueID": osc_id, "name": "OSC Message - One"},
            {"uniqueID": plain_id, "name": "Plain Text - Plain"},
        ],
        network_repair_outcomes={
            (source_id, "customString", requested): {
                "isBroken": False,
                "isWarning": False,
                "message": requested,
                "messageError": "",
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": requested}}
    dry = reader.update_cues(workspace_id, [request], dry_run=True)
    token = planned_setters(dry["results"][0])["customString"]["confirm_token"]
    assert token.startswith("confirm:networkRepair:v1:")
    assert dry["results"][0]["executed_operations"] == []
    real = reader.update_cues(workspace_id, [{**request, "confirm_gates": [token]}], dry_run=False)
    assert real["status"] == "updated"
    assert real["results"][0]["after"]["customString"] == requested
    assert real["results"][0]["after"]["isBroken"] is False
    assert real["results"][0]["after"]["messageError"] == ""
    assert "network_repair_succeeded" in real["results"][0]["notices"]

    client.cues[source_id].update(cue)
    setter_count = len([address for address, _, _ in client.requests if address.endswith("/customString")])
    invalid = reader.update_cues(
        workspace_id,
        [{"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "{custom}"}}],
        dry_run=True,
    )
    assert invalid["status"] == "preflight_failed"
    assert invalid["results"][0]["executed_operations"] == []
    assert "valid OSC address/message" in invalid["results"][0]["errors"]["customString"]
    assert len([address for address, _, _ in client.requests if address.endswith("/customString")]) == setter_count

    non_osc = reader.update_cues(
        workspace_id,
        [{"cue_ref": source_id, "profile": "network_basic", "properties": {"networkPatchID": plain_id}}],
        dry_run=True,
    )
    assert non_osc["status"] == "preflight_failed"
    assert "not classified as OSC Message" in non_osc["results"][0]["errors"]["networkPatchID"]


def test_network_patch_repair_success_and_automatic_recovery() -> None:
    workspace_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    source_id = "11111111-1111-4111-8111-111111111111"
    baseline_id = "22222222-2222-4222-8222-222222222222"
    target_id = "33333333-3333-4333-8333-333333333333"
    patches = [
        {"uniqueID": baseline_id, "name": "Plain Text - Broken"},
        {"uniqueID": target_id, "name": "OSC Message - Repair"},
    ]
    cue = {
        "type": "Network",
        "networkPatchID": baseline_id,
        "customString": "/repair/test",
        "message": "",
        "messageError": "",
        "isBroken": True,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    success_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: cue},
        workspace_id=workspace_id,
        network_patches=patches,
        network_repair_outcomes={
            (source_id, "networkPatchID", target_id): {"isBroken": False, "isWarning": False, "messageError": ""}
        },
    )
    success_reader = QLabReader(success_client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"networkPatchID": target_id}}
    dry = success_reader.update_cues(workspace_id, [request], dry_run=True)
    token = planned_setters(dry["results"][0])["networkPatchID"]["confirm_token"]
    assert token.startswith("confirm:networkRepair:v1:")
    success = success_reader.update_cues(workspace_id, [{**request, "confirm_gates": [token]}], dry_run=False)
    assert success["status"] == "updated"
    assert success["results"][0]["after"]["networkPatchID"] == target_id
    assert success["results"][0]["after"]["isBroken"] is False

    recovery_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: cue},
        workspace_id=workspace_id,
        network_patches=patches,
    )
    recovery_reader = QLabReader(recovery_client)  # type: ignore[arg-type]
    recovery_dry = recovery_reader.update_cues(workspace_id, [request], dry_run=True)
    recovery_token = planned_setters(recovery_dry["results"][0])["networkPatchID"]["confirm_token"]
    failed = recovery_reader.update_cues(
        workspace_id, [{**request, "confirm_gates": [recovery_token]}], dry_run=False
    )
    assert failed["status"] == "verification_failed"
    assert failed["results"][0]["after"]["networkPatchID"] == baseline_id
    assert "baseline was restored" in failed["results"][0]["errors"]["networkRepair"]
    patch_setters = [args[0] for address, args, _ in recovery_client.requests if address.endswith("/networkPatchID")]
    assert patch_setters == [target_id, baseline_id]


def test_network_repair_rejects_tokens_shapes_live_and_active_without_setters() -> None:
    workspace_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    source_id = "11111111-1111-4111-8111-111111111111"
    osc_id = "22222222-2222-4222-8222-222222222222"
    cue = {
        "type": "Network",
        "networkPatchID": osc_id,
        "customString": "",
        "message": "{custom}",
        "messageError": "bad message",
        "isBroken": True,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={source_id: cue},
        workspace_id=workspace_id,
        network_patches=[{"uniqueID": osc_id, "name": "OSC Message - One"}],
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    request = {"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/repair/test"}}
    token = planned_setters(reader.update_cues(workspace_id, [request], dry_run=True)["results"][0])["customString"]["confirm_token"]
    rejected = [
        reader.update_cues(workspace_id, [{**request, "confirm_gates": ["confirm:networkRepair:v1:fake:fake"]}], dry_run=False),
        reader.update_cues(workspace_id, [{**request, "confirm_gates": ["confirm:networkOscMessage:v1:fake:fake"]}], dry_run=False),
    ]
    client.cues[source_id]["customString"] = "/stale/baseline"
    rejected.append(reader.update_cues(workspace_id, [{**request, "confirm_gates": [token]}], dry_run=False))
    client.cues[source_id]["customString"] = ""
    rejected.extend(
        [
            reader.update_cues(workspace_id, [{**request, "confirm_gates": [token]}, {**request, "confirm_gates": [token]}], dry_run=False),
            reader.update_cues(
                workspace_id,
                [{"cue_ref": source_id, "profile": "network_basic", "properties": {"customString": "/repair/test", "networkPatchID": osc_id}, "confirm_gates": [token]}],
                dry_run=False,
            ),
            reader.update_cues(
                workspace_id,
                [{"cue_ref": source_id, "profile": "network_basic", "operations": [{"property": "customString", "args": {"value": "/repair/test"}, "mode": "live"}]}],
                dry_run=True,
            ),
        ]
    )
    client.cues[source_id]["isRunning"] = True
    rejected.append(reader.update_cues(workspace_id, [request], dry_run=True))
    assert all(result["status"] == "preflight_failed" for result in rejected)
    assert all(not address.endswith(("/customString", "/networkPatchID")) for address, _, _ in client.requests)


def test_update_cues_rejects_slash_in_path_template_arg() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Network", "customString": "/cue/1/start"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "network_basic",
                "operations": [{"property": "parameterValue", "args": {"parameter": "foo/bar", "value": "Intro"}}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "must not contain '/'" in result["results"][0]["errors"]["validation"]


def test_update_cues_network_basic_invalid_values_and_unsupported_fields_have_no_plan() -> None:
    network_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={network_id: {"type": "Network"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"parameterValues": "not-list"}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"networkPatchNumber": -1}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"message": "/unsupported"}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"protocol": "udp"}},
            {"cue_ref": memo_id, "profile": "network_basic", "properties": {"customString": "/go"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "parameterValues must be a list"
    assert result["results"][1]["errors"]["validation"] == "networkPatchNumber must be a non-negative integer"
    assert "not allowlisted" in result["results"][2]["errors"]["validation"]
    assert "not allowlisted" in result["results"][3]["errors"]["validation"]
    assert result["results"][4]["errors"]["profile"] == "network_basic update profile requires a Network cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_light_basic_dry_run_plans_documented_light_cue_messages() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20", "alwaysCollate": False, "subcontroller": False}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {
                    "lightCommandText": "Front = 50",
                    "alwaysCollate": True,
                    "subcontroller": False,
                },
                "operations": [
                    {"property": "setLight", "args": {"instrument_or_group": "front.intensity", "setting": 50}},
                    {
                        "property": "replaceLightCommand",
                        "args": {"oldCommand": "1 = 50", "newCommand": "1 = 60"},
                    },
                    {"property": "removeLightCommandsMatching", "args": {"match": "2 = 0"}},
                    {"property": "safeSort"},
                    {"property": "safeSortCommands"},
                    {"property": "prune"},
                    {"property": "pruneCommands"},
                ],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []
    assert "updateq_plan" not in result["results"][0]
    setters = planned_setters(result["results"][0])
    assert setters["setLight"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/setLight"
    assert setters["setLight"]["args"] == ["front.intensity", 50]
    assert setters["replaceLightCommand"]["args"] == ["1 = 50", "1 = 60"]
    assert setters["removeLightCommandsMatching"]["args"] == ["2 = 0"]
    analysis = setters["lightCommandText"]["light_command_analysis"]
    assert analysis["overall_status"] == "valid"
    assert analysis["affected_instruments"] == ["Front"]
    assert analysis["affected_parameters"] == ["intensity"]
    assert setters["lightCommandText"]["real_write_possible"] is True
    assert setters["lightCommandText"]["requires_confirm_token"] is True
    assert setters["lightCommandText"]["phase4_real_write_candidate"] is True
    assert setters["lightCommandText"]["real_write_enabled"] is False
    assert setters["lightCommandText"]["planned_only_reason"] == (
        "light_command_requires_valid_analysis_and_confirm_token"
    )
    assert setters["lightCommandText"]["confirm_token"].startswith("confirm:lightCommandText:v1:")
    assert result["results"][0]["diff"]["lightCommandText"] == {
        "before": "Front = 20",
        "requested": "Front = 50",
    }
    for prop in (
        "lightCommandText",
        "alwaysCollate",
        "subcontroller",
        "setLight",
        "replaceLightCommand",
        "removeLightCommandsMatching",
        "safeSort",
        "safeSortCommands",
        "prune",
        "pruneCommands",
    ):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]
    assert [request[0] for request in client.requests].count("/workspace/ws-1/settings/light/patch") == 1
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_light_analysis_policies_share_one_patch_read() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Back.red = 50"}},
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Missing = 50"}},
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "1 - 3 = 50"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 3
    setters = [planned_setters(item)["lightCommandText"] for item in result["results"]]
    assert [setter["light_command_analysis"]["overall_status"] for setter in setters] == [
        "warning",
        "invalid",
        "unsupported",
    ]
    assert setters[0]["light_command_analysis"]["affected_instruments"] == ["Red Fixture"]
    assert setters[0]["light_command_analysis"]["skipped_member_count"] == 1
    assert setters[0]["real_write_possible"] is False
    assert setters[0]["phase4_real_write_candidate"] is False
    assert setters[0]["planned_only_reason"] == "light_command_analysis_warning"
    assert "confirm_token" not in setters[0]
    assert setters[1]["real_write_possible"] is False
    assert setters[1]["planned_only_reason"] == "light_command_analysis_failed"
    assert "confirm_token" not in setters[1]
    assert setters[2]["real_write_possible"] is False
    assert setters[2]["planned_only_reason"] == "unsupported_light_command_syntax"
    assert "confirm_token" not in setters[2]
    assert [request[0] for request in client.requests].count("/workspace/ws-1/settings/light/patch") == 1
    assert all(item["executed_operations"] == [] for item in result["results"])


def test_update_cues_light_analysis_unavailable_keeps_dry_run_planned() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch_error=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["lightCommandText"]
    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert setter["light_command_analysis"]["availability"] == "unavailable"
    assert setter["light_command_analysis"]["error"]["code"] == "light_patch_read_failed"
    assert setter["real_write_possible"] is False
    assert setter["phase4_real_write_candidate"] is False
    assert setter["planned_only_reason"] == "light_command_analysis_unavailable"
    assert "confirm_token" not in setter
    assert result["results"][0]["errors"] is None


def test_update_cues_light_analyzer_failure_is_nonfatal(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    monkeypatch.setattr(write_operations, "analyze_light_command_text", lambda *_: (_ for _ in ()).throw(RuntimeError()))

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}],
        dry_run=True,
    )

    analysis = planned_setters(result["results"][0])["lightCommandText"]["light_command_analysis"]
    assert result["ok"] is True
    assert analysis["availability"] == "unavailable"
    assert analysis["error"]["code"] == "light_command_analyzer_failed"


def test_update_cues_light_command_size_limit_rejects_before_reads_or_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {"lightCommandText": "x" * 65_537},
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][0]["errors"]["error_code"] == "light_command_input_too_large"
    assert result["results"][0]["planned_operations"] == []
    assert client.requests == []


def test_update_cues_light_non_command_updates_do_not_read_patch() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "alwaysCollate": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"alwaysCollate": True}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert "/workspace/ws-1/settings/light/patch" not in [request[0] for request in client.requests]


def test_update_cues_light_command_real_write_with_token_sets_once_and_verifies() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}
    dry_run = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(dry_run["results"][0])["lightCommandText"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 50"
    assert result["results"][0]["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "lightCommandText",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/lightCommandText",
            "args": ["Front = 50"],
            "mode": "saved",
            "capability_gate": "light_output",
            "status": "ok",
        }
    ]
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/ws-1/cue_id/{cue_id}/lightCommandText"
    ) == 1


def test_update_cues_light_command_rollback_uses_new_dry_run_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    forward = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}
    forward_plan = reader.update_cues("ws-1", [forward], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["lightCommandText"]["confirm_token"]
    assert reader.update_cues(
        "ws-1", [{**forward, "confirm_gates": [forward_token]}], dry_run=False
    )["status"] == "updated"

    rollback = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 20"}}
    rollback_plan = reader.update_cues("ws-1", [rollback], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["lightCommandText"]["confirm_token"]
    assert rollback_token != forward_token
    result = reader.update_cues(
        "ws-1", [{**rollback, "confirm_gates": [rollback_token]}], dry_run=False
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 20"
    assert client.cues[cue_id]["lightCommandText"] == "Front = 20"


def test_update_cues_empty_light_command_is_valid_but_not_confirmable() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": ""}}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["lightCommandText"]
    assert setter["light_command_analysis"]["overall_status"] == "valid"
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    assert setter["phase4_real_write_candidate"] is False
    assert setter["planned_only_reason"] == "empty_light_command_text_not_writeable"
    assert "confirm_token" not in setter


def _phase4_fixture(
    *,
    cue_type: str = "Light",
    connect_data: str = "ok:view|edit",
    show_mode_data: Any = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
        connect_data=connect_data,
        show_mode_data=show_mode_data,
        ignore_set_property=(cue_id, "lightCommandText") if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": "Front = 50"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["lightCommandText"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def _light_setter_requests(client: BatchFakeWriteClient) -> list[tuple[str, tuple[Any, ...], str | None]]:
    return [request for request in client.requests if request[0].endswith("/lightCommandText")]


def test_phase4_token_payload_binds_version_kind_and_write_context() -> None:
    _, _, cue_id, _, token = _phase4_fixture()

    payload, error = write_operations._decode_phase4_light_confirm_token(token)

    assert error is None
    assert payload == {
        "analysis_status": "valid",
        "baseline_sha256": write_operations._text_sha256("Front = 20"),
        "capability_gate": "light_output",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "mode": "saved",
        "operation_kind": "phase4_light_command_text_write",
        "path": "lightCommandText",
        "profile": "light_basic",
        "property": "lightCommandText",
        "requested_sha256": write_operations._text_sha256("Front = 50"),
        "risk_tier": "high",
        "version": 1,
        "workspace_id": "ws-1",
    }


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase4_malformed_tampered_or_wrong_version_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_token_cannot_authorize_another_requested_value_or_cue_ref() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()

    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"lightCommandText": "Front = 60"}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    client.cue_numbers["1"] = cue_id
    wrong_ref = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": "1", "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_ref["status"] == "preflight_failed"
    assert _light_setter_requests(client) == []


def test_phase4_token_cannot_authorize_another_workspace() -> None:
    _, _, cue_id, update, token = _phase4_fixture()
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        workspace_id="ws-2",
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-2",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "does not match" in result["results"][0]["errors"]["lightCommandText"]
    assert _light_setter_requests(client) == []


def test_phase4_missing_workspace_blocks_before_setter() -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "missing-ws",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "write_readiness" in result["errors"]
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


@pytest.mark.parametrize("command_text", ["Back.red = 50", "Missing = 50", "1 - 3 = 50", ""])
def test_phase4_nonconfirmable_analysis_has_no_real_write_path(command_text: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": command_text},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lightCommandText"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [update], dry_run=False)

    assert setter["real_write_possible"] is False
    assert "confirm_token" not in setter
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert client.requests == []


def test_phase4_unavailable_analysis_and_multiple_tokens_block_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
        light_patch_error=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": "Front = 50"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lightCommandText"]
    client.requests.clear()

    unavailable = reader.update_cues("ws-1", [update], dry_run=False)
    multiple = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["one", "two"]}],
        dry_run=False,
    )

    assert setter["light_command_analysis"]["overall_status"] == "unavailable"
    assert "confirm_token" not in setter
    assert unavailable["status"] == "preflight_failed"
    assert multiple["status"] == "preflight_failed"
    assert _light_setter_requests(client) == []


def test_phase4_stale_baseline_blocks_before_setter() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    client.cues[cue_id]["lightCommandText"] = "Front = 30"

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "stale_light_command_baseline" in result["results"][0]["errors"]["lightCommandText"]
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_readback_mismatch_returns_verification_failure() -> None:
    client, reader, _, update, token = _phase4_fixture(ignore_readback=True)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert len(_light_setter_requests(client)) == 1
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 20"
    assert result["results"][0]["diff"]["lightCommandText"]["requested"] == "Front = 50"


def test_phase4_batch_or_extra_property_blocks_whole_call_before_osc() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    second_id = "22222222-2222-4222-8222-222222222222"
    client.cues[second_id] = {
        "uniqueID": second_id,
        "type": "Light",
        "lightCommandText": "Front = 20",
    }

    batch = reader.update_cues(
        "ws-1",
        [
            {**update, "confirm_gates": [token]},
            {**update, "cue_ref": second_id, "confirm_gates": [token]},
        ],
        dry_run=False,
    )
    mixed = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "properties": {"lightCommandText": "Front = 50", "alwaysCollate": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert batch["status"] == "preflight_failed"
    assert mixed["status"] == "preflight_failed"
    assert all(item["executed_operations"] == [] for item in batch["results"])
    assert mixed["results"][0]["executed_operations"] == []
    assert client.requests == []


@pytest.mark.parametrize(
    ("connect_data", "show_mode_data"),
    [("ok:view", False), ("ok:view|edit", True)],
)
def test_phase4_edit_scope_and_show_mode_block_before_setter(
    connect_data: str,
    show_mode_data: Any,
) -> None:
    client, reader, _, update, token = _phase4_fixture(
        connect_data=connect_data,
        show_mode_data=show_mode_data,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_non_light_missing_cue_and_patch_failure_block_before_setter() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    client.cues[cue_id]["type"] = "Memo"
    non_light = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.cues[cue_id]["type"] = "Light"
    client.missing_refs.add(cue_id)
    missing = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.missing_refs.clear()
    client.light_patch_error = True
    patch_failure = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert [non_light["status"], missing["status"], patch_failure["status"]] == [
        "preflight_failed",
        "preflight_failed",
        "preflight_failed",
    ]
    assert _light_setter_requests(client) == []


def test_phase4_success_requests_no_dashboard_playback_or_unqualified_osc() -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    addresses = [address for address, _, _ in client.requests]
    assert result["status"] == "updated"
    assert all(address == "/workspaces" or address.startswith("/workspace/ws-1/") for address in addresses)
    assert not any(
        forbidden in address.casefold()
        for address in addresses
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview")
    )


def _phase5_fixture(
    property_name: str = "alwaysCollate",
    *,
    baseline: bool = False,
    requested: bool = True,
    cue_type: str = "Light",
    connect_data: str = "ok:view|edit",
    show_mode_data: Any = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", property_name: baseline}},
        connect_data=connect_data,
        show_mode_data=show_mode_data,
        ignore_set_property=(cue_id, property_name) if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.cues[cue_id]["type"] = cue_type
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    [
        ("alwaysCollate", False, True),
        ("alwaysCollate", True, False),
        ("subcontroller", False, True),
        ("subcontroller", True, False),
    ],
)
def test_phase5_dry_run_candidate_and_real_write_verify_boolean(
    property_name: str,
    baseline: bool,
    requested: bool,
) -> None:
    client, reader, cue_id, update, token = _phase5_fixture(
        property_name,
        baseline=baseline,
        requested=requested,
    )
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])[property_name]
    token = setter["confirm_token"]
    client.requests.clear()

    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["phase5_light_behavior_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"] == "light_behavior_requires_confirm_token"
    assert token.startswith("confirm:lightBehavior:v1:")

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert result["results"][0]["after"][property_name] is requested
    assert [request[0] for request in client.requests].count(address) == 1


def test_phase5_token_payload_binds_kind_property_and_context() -> None:
    _, _, cue_id, _, token = _phase5_fixture()

    payload, error = write_operations._decode_phase5_light_confirm_token(token)

    assert error is None
    assert payload == {
        "baseline": False,
        "capability_gate": "light_output",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "mode": "saved",
        "operation_kind": "phase5_light_behavior_flag_write",
        "path": "alwaysCollate",
        "profile": "light_basic",
        "property": "alwaysCollate",
        "requested": True,
        "risk_tier": "high",
        "version": 1,
        "workspace_id": "ws-1",
    }


def test_phase5_rollback_requires_new_dry_run_token() -> None:
    client, reader, cue_id, forward, token = _phase5_fixture()
    assert reader.update_cues(
        "ws-1", [{**forward, "confirm_gates": [token]}], dry_run=False
    )["status"] == "updated"

    rollback = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"alwaysCollate": False},
    }
    plan = reader.update_cues("ws-1", [rollback], dry_run=True)
    rollback_token = planned_setters(plan["results"][0])["alwaysCollate"]["confirm_token"]
    result = reader.update_cues(
        "ws-1", [{**rollback, "confirm_gates": [rollback_token]}], dry_run=False
    )

    assert rollback_token != token
    assert result["status"] == "updated"
    assert client.cues[cue_id]["alwaysCollate"] is False


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase5_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase5_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)


def test_phase5_token_cannot_authorize_other_property_value_workspace_or_cue_ref() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"alwaysCollate": False}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    wrong_property = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {"subcontroller": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )
    client.requests.clear()
    client.cue_numbers["1"] = cue_id
    wrong_ref = reader.update_cues(
        "ws-1", [{**update, "cue_ref": "1", "confirm_gates": [token]}], dry_run=False
    )
    client.requests.clear()
    other_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "alwaysCollate": False}},
        workspace_id="ws-2",
    )
    other_reader = QLabReader(other_client)  # type: ignore[arg-type]
    wrong_workspace = other_reader.update_cues(
        "ws-2", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert {wrong_value["status"], wrong_property["status"], wrong_ref["status"], wrong_workspace["status"]} == {
        "preflight_failed"
    }
    assert not any(
        address.endswith(("/alwaysCollate", "/subcontroller"))
        for address, _, _ in client.requests + other_client.requests
    )


def test_phase5_stale_baseline_and_readback_mismatch_are_detected() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    client.cues[cue_id]["alwaysCollate"] = True
    stale = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    assert stale["status"] == "preflight_failed"
    assert "stale_light_behavior_baseline" in stale["results"][0]["errors"]["alwaysCollate"]
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)

    mismatch_client, mismatch_reader, _, mismatch_update, mismatch_token = _phase5_fixture(
        ignore_readback=True
    )
    mismatch = mismatch_reader.update_cues(
        "ws-1",
        [{**mismatch_update, "confirm_gates": [mismatch_token]}],
        dry_run=False,
    )
    assert mismatch["status"] == "verification_failed"
    assert sum(address.endswith("/alwaysCollate") for address, _, _ in mismatch_client.requests) == 1


def test_phase5_batch_mixed_properties_and_live_mode_block_whole_call() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    second_id = "22222222-2222-4222-8222-222222222222"
    client.cues[second_id] = {"uniqueID": second_id, "type": "Light", "alwaysCollate": False}
    cases = [
        [
            {**update, "confirm_gates": [token]},
            {**update, "cue_ref": second_id, "confirm_gates": [token]},
        ],
        [
            {
                **update,
                "properties": {"alwaysCollate": True, "subcontroller": True},
                "confirm_gates": [token],
            }
        ],
        [
            {
                **update,
                "properties": {"alwaysCollate": True, "lightCommandText": "Front = 50"},
                "confirm_gates": [token],
            }
        ],
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "operations": [
                    {"property": "alwaysCollate", "args": {"value": True}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert client.requests == []


def test_phase5_non_strict_dry_run_has_no_confirmable_token() -> None:
    client, reader, cue_id, _, _ = _phase5_fixture()

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {"alwaysCollate": True, "subcontroller": True},
            }
        ],
        dry_run=True,
    )

    setters = planned_setters(result["results"][0])
    for setter in setters.values():
        assert setter["phase5_light_behavior_candidate"] is False
        assert setter["real_write_possible"] is False
        assert setter["requires_confirm_token"] is False
        assert setter["planned_only_reason"] == "light_behavior_requires_single_property"
        assert "confirm_token" not in setter
    assert not any("settings/light/patch" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("cue_type", "connect_data", "show_mode_data"),
    [
        ("Memo", "ok:view|edit", False),
        ("Light", "ok:view", False),
        ("Light", "ok:view|edit", True),
    ],
)
def test_phase5_non_light_edit_scope_and_show_mode_block_before_setter(
    cue_type: str,
    connect_data: str,
    show_mode_data: Any,
) -> None:
    client, reader, _, update, token = _phase5_fixture(
        cue_type=cue_type,
        connect_data=connect_data,
        show_mode_data=show_mode_data,
    )
    result = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)


def test_phase5_missing_cue_and_safe_addresses_only() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    client.missing_refs.add(cue_id)
    missing = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    assert missing["status"] == "preflight_failed"
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)

    client.missing_refs.clear()
    success = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    addresses = [address for address, _, _ in client.requests]
    assert success["status"] == "updated"
    assert all(address == "/workspaces" or address.startswith("/workspace/ws-1/") for address in addresses)
    assert not any(
        forbidden in address.casefold()
        for address in addresses
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview", "settings/light/patch")
    )


def test_update_cues_light_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    light_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={light_id: {"type": "Light"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"alwaysCollate": "yes"}},
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"subcontroller": "yes"}},
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [{"property": "setLight", "args": {"instrument_or_group": "1"}}],
            },
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [
                    {"property": "replaceLightCommand", "args": {"oldCommand": "", "newCommand": "1 = 60"}}
                ],
            },
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [{"property": "removeLightCommandsMatching", "args": {"match": ""}}],
            },
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"parameterValues": {"intensity": 80}}},
            {"cue_ref": memo_id, "profile": "light_basic", "properties": {"lightCommandText": "1 = 50"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "alwaysCollate must be a boolean"
    assert result["results"][1]["errors"]["validation"] == "subcontroller must be a boolean"
    assert result["results"][2]["errors"]["validation"] == "setLight args missing required key: setting"
    assert result["results"][3]["errors"]["validation"] == "replaceLightCommand.oldCommand must be a non-empty string"
    assert (
        result["results"][4]["errors"]["validation"]
        == "removeLightCommandsMatching.match must be a non-empty string"
    )
    assert "not allowlisted" in result["results"][5]["errors"]["validation"]
    assert result["results"][6]["errors"]["profile"] == "light_basic update profile requires a Light cue"
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert all(item["executed_operations"] == [] for item in result["results"])


def test_update_cues_script_basic_dry_run_plans_source_alias_without_execution() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Script", "scriptSource": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "script_basic",
                "properties": {"scriptSource": "display dialog \"planned\""},
                "operations": [{"property": "scriptText", "args": "display dialog \"alias\""}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["scriptSource"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/scriptSource"
    assert setters["scriptText"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/scriptSource"
    assert all(setter["real_write_enabled"] is False for setter in setters.values())
    assert all(setter["planned_only_reason"] == "not_editable_by_osc" for setter in setters.values())
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_script_basic_invalid_value_and_profile_mismatch_have_no_plan() -> None:
    script_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={script_id: {"type": "Script"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": script_id, "profile": "script_basic", "properties": {"scriptSource": 123}},
            {"cue_ref": memo_id, "profile": "script_basic", "properties": {"scriptSource": ""}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "scriptSource must be a string"
    assert result["results"][1]["errors"]["profile"] == "script_basic update profile requires a Script cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_wait_and_memo_basic_stay_common_only() -> None:
    catalog = profile_catalog()
    safe_common = set(catalog["memo_basic"]["properties"])
    assert set(catalog["wait_basic"]["properties"]) == safe_common
    assert safe_common < set(catalog["common"]["properties"])
    assert "duckLevel" not in safe_common
    assert "fileTarget" not in safe_common

    wait_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={wait_id: {"type": "Wait", "duration": 0}, memo_id: {"type": "Memo", "notes": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": 3, "continueMode": "auto_follow"}},
            {"cue_ref": memo_id, "profile": "memo_basic", "properties": {"name": "Memo", "notes": "Operator note"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 2
    assert planned_setters(result["results"][0])["continueMode"]["args"] == [2]
    assert planned_setters(result["results"][0])["duration"]["contextual_requirements"] == ["allows_editing_duration"]
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][1]["executed_operations"] == []


def test_update_cues_wait_and_memo_invalid_common_values_have_no_plan() -> None:
    wait_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={wait_id: {"type": "Wait", "duration": 0}, memo_id: {"type": "Memo", "duration": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": -1}},
            {"cue_ref": memo_id, "profile": "memo_basic", "properties": {"continueMode": "bad"}},
            {"cue_ref": memo_id, "profile": "wait_basic", "properties": {"duration": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "duration must be a non-negative number"
    assert "continueMode must be" in result["results"][1]["errors"]["validation"]
    assert result["results"][2]["errors"]["profile"] == "wait_basic update profile requires a Wait cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_create_cue_dry_run_reviews_generic_types_and_exclusions() -> None:
    for cue_type in (
        "memo", "group", "wait", "audio", "mic", "video", "camera", "text", "light",
        "fade", "network", "midi", "midi_file", "timecode", "start", "stop", "pause",
        "load", "reset", "devamp", "goto", "target", "arm", "disarm",
    ):
        supported_reader = CreateAnchorReader(config=QLabConfig(enable_write=False, passcode=None))
        result = supported_reader.create_cue(
            supported_reader.workspace,
            cue_type,
            dry_run=True,
            after_cue_id=supported_reader.anchor_id,
        )
        assert result["ok"] is True
        assert result["status"] == "dry_run"
        assert result["planned_operations"][0]["operation"] == "new"

    unsupported_client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    unsupported_reader = QLabReader(unsupported_client)  # type: ignore[arg-type]
    for cue_type in ("script", "list", "cart", "custom"):
        with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
            unsupported_reader.create_cue("ws-1", cue_type, dry_run=True)
    assert unsupported_client.requests == []


@pytest.mark.parametrize("cue_type", list(CUE_TYPES))
def test_create_generic_types_send_one_new_and_no_setters(cue_type: str) -> None:
    reader = CreateAnchorReader()
    planned = reader.create_cue(reader.workspace, cue_type, dry_run=True, after_cue_id=reader.anchor_id)
    result = reader.create_cue(
        reader.workspace,
        cue_type,
        dry_run=False,
        after_cue_id=reader.anchor_id,
        confirm_token=planned["confirm_token"],
    )

    assert result["ok"] is True
    assert [address for address, _, _ in reader.requests].count(f"/workspace/{reader.workspace}/new") == 1
    assert not any(
        "/cue_id/" in address and not address.endswith("/valuesForKeys")
        for address, _, _ in reader.requests
    )


@pytest.mark.parametrize(
    ("profile", "cue_type", "properties"),
    [
        ("midi_file_basic", "MIDI File", {"rate": 1.1, "startTime": 0, "endTime": 8, "playCount": 2}),
        ("timecode_basic", "Timecode", {"outputType": 1, "startTime": "01:00:00:00"}),
        ("target_basic", "Start", {"name": "Start cue renamed"}),
        ("reset_basic", "Reset", {"name": "Reset cue renamed"}),
        ("devamp_basic", "Devamp", {"name": "Devamp cue renamed"}),
        ("light_basic", "Light", {"name": "Light cue renamed"}),
        ("network_basic", "Network", {"name": "Network cue renamed"}),
        ("midi_basic", "MIDI", {"name": "MIDI cue renamed"}),
        ("script_basic", "Script", {"name": "Script cue renamed"}),
    ],
)
def test_update_cue_real_updates_new_safe_profiles(profile: str, cue_type: str, properties: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values = {
        "uniqueID": cue_id,
        "type": cue_type,
        "name": "Stale",
        "channels": 1,
        "channelOffset": 0,
        "translation/x": 0,
        "opacity": 1,
        "cropTop": 0,
        "scale/x": 1,
        "rotation": 0,
        "rate": 1,
        "startTime": 0,
        "endTime": 10,
        "playCount": 1,
        "outputType": 0,
    }
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == profile
    for key, value in properties.items():
        assert result["after"][key] == value
        assert f"/workspace/ws-1/cue_id/{cue_id}/{key}" in [request[0] for request in client.requests]


def test_update_cue_real_blocks_missing_cue_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        missing_cue=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" not in [request[0] for request in client.requests]


def test_update_cue_real_blocks_when_before_has_no_unique_id() -> None:
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=None,
        cue_values={"number": "1", "name": "Stale", "type": "Memo"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert "/workspace/ws-1/cue/1/name" not in addresses


def test_update_cue_real_updates_and_verifies_fresh_details() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["before"]["name"] == "Stale"
    assert result["after"]["name"] == "New"
    assert result["diff"]["armed"] == {"before": True, "requested": False, "after": False}
    assert result["verification"]["properties"]["name"] == "New"
    assert "/workspace/ws-1/connect" in addresses
    assert "/workspace/ws-1/showMode" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses


def test_update_cue_real_accepts_setter_timeout_when_after_read_confirms_value() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        timeout_set_property="flagged",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"flagged": True}, dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["after"]["flagged"] is True
    assert result["diff"]["flagged"] == {"before": False, "requested": True, "after": True}
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"
    assert result["warnings"] == ["One or more setters did not reply, but fresh after-read confirmed requested values."]
    assert len([address for address, _, _ in client.requests if address.endswith("/flagged")]) == 1


def test_update_cue_real_resolves_number_to_unique_id_for_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    planned_setters = [
        operation["address"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert "/workspace/ws-1/cue/1/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert "/workspace/ws-1/cue/1/name" not in addresses
    assert planned_setters == [f"/workspace/ws-1/cue_id/{cue_id}/name"]


def test_update_cue_real_blocks_in_show_mode() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        show_mode_data=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]


def test_update_cue_real_reports_partial_failure() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        fail_set_property="armed",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert [operation["property"] for operation in result["executed_operations"]] == ["name"]
    assert "armed" in result["errors"]
    assert result["after"]["name"] == "New"
