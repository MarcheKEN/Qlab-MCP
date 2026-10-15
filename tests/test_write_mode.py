from __future__ import annotations

from pathlib import Path
import time
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from qlab_mcp.models import CreateCueResult, CreateCuesResult, UpdateCuesResult, WriteReadinessResult
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache
import qlab_mcp.write.operations as write_operations
import qlab_mcp.write.moves as move_helpers
import qlab_mcp.write.registry as write_registry
from qlab_mcp.cues import refs as cue_refs
from qlab_mcp.cues import overview as cue_overview
from qlab_mcp.write.moves import _build_plan, move_cues, simulate_move_batch
from qlab_mcp.write.allowlist import CUE_TYPES, validate_writable_cue_type
from qlab_mcp.write.registry import UPDATE_PROFILE_NAMES, profile_catalog
from qlab_mcp.write.network_patch_types import classify_network_patch_type


def test_write_modules_reuse_canonical_container_types_without_widening_placement_sets() -> None:
    assert cue_refs.CONTAINER_CUE_TYPES == {"Cue List", "Cue Cart", "Cart", "Group"}
    assert cue_overview.CONTAINER_CUE_TYPES is cue_refs.CONTAINER_CUE_TYPES
    assert move_helpers.CONTAINER_CUE_TYPES is cue_refs.CONTAINER_CUE_TYPES
    assert move_helpers._LINEAR_PARENT_TYPES == {"Cue List", "Group"}
    assert move_helpers._CART_PARENT_TYPES == {"Cue Cart", "Cart"}


def test_qlab_reader_no_longer_exposes_generic_python_cue_editors() -> None:
    assert not hasattr(QLabReader, "edit_cues")
    assert not hasattr(QLabReader, "update_cue")


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


def test_create_destination_appends_to_selected_cue_list(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_list_id = "22222222-2222-4222-8222-222222222222"
    last_cue_id = "11111111-1111-4111-8111-111111111111"
    snapshot = {
        "nodes": {
            cue_list_id: {"uniqueID": cue_list_id, "type": "Cue List"},
            last_cue_id: {"uniqueID": last_cue_id, "type": "Memo"},
        },
        "parent_by_child": {last_cue_id: cue_list_id},
        "children_by_parent": {cue_list_id: [last_cue_id]},
    }
    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 0})

    _, _, placement, error = write_operations._create_preflight(
        object(), "ws-1", "destination",
        {"kind": "cue_list", "id": cue_list_id, "after_cue_id": None},
    )

    assert error is None
    assert placement is not None
    assert placement["parent_id"] == cue_list_id
    assert placement["after_cue_id"] == last_cue_id
    assert placement["expected_index"] == 1


def test_create_destination_accepts_qlab_cart_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    cart_id = "22222222-2222-4222-8222-222222222222"
    snapshot = {
        "nodes": {cart_id: {"uniqueID": cart_id, "type": "Cart"}},
        "parent_by_child": {},
        "children_by_parent": {cart_id: []},
    }
    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 0})

    _, _, placement, error = write_operations._create_preflight(
        object(), "ws-1", "destination",
        {"kind": "cue_cart", "id": cart_id, "after_cue_id": None},
    )

    assert error is None
    assert placement is not None
    assert placement["mode"] == "empty_cart"


@pytest.mark.parametrize("cue_types,ids,anchor", [
    (["audio"], {}, None),
    (["audio"], {"cue_list_id": "11111111-1111-4111-8111-111111111111", "group_id": "22222222-2222-4222-8222-222222222222"}, None),
    (["audio", "video"], {"cue_cart_id": "11111111-1111-4111-8111-111111111111"}, None),
    (["group"], {"cue_cart_id": "11111111-1111-4111-8111-111111111111"}, None),
    (["audio"], {"cue_cart_id": "11111111-1111-4111-8111-111111111111"}, "22222222-2222-4222-8222-222222222222"),
])
def test_create_destination_rejects_invalid_selection_before_io(cue_types, ids, anchor) -> None:
    with pytest.raises(UnsafeWriteOperationError):
        write_operations._normalize_create_destination(
            ids.get("cue_list_id"), ids.get("group_id"), ids.get("cue_cart_id"), anchor, cue_types
        )


@pytest.mark.parametrize("kind,container_type", [("cue_list", "Cue List"), ("group", "Group")])
def test_create_destination_resolves_empty_and_direct_child(
    monkeypatch: pytest.MonkeyPatch, kind: str, container_type: str
) -> None:
    container_id = "11111111-1111-4111-8111-111111111111"
    first_id = "22222222-2222-4222-8222-222222222222"
    other_id = "33333333-3333-4333-8333-333333333333"
    snapshot = {
        "nodes": {
            container_id: {"uniqueID": container_id, "type": container_type},
            first_id: {"uniqueID": first_id, "type": "Memo"},
            other_id: {"uniqueID": other_id, "type": "Memo"},
        },
        "parent_by_child": {first_id: container_id},
        "children_by_parent": {container_id: []},
    }
    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: snapshot)
    monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 0})
    monkeypatch.setattr(write_operations, "_read_current_cue_list_id", lambda *_: container_id)

    request = {"kind": kind, "id": container_id, "after_cue_id": None}
    _, _, placement, error = write_operations._create_preflight(object(), "ws-1", "destination", request)
    assert error is None
    assert placement["mode"] == f"empty_{kind}"

    snapshot["children_by_parent"][container_id] = [first_id]
    request["after_cue_id"] = first_id
    _, _, placement, error = write_operations._create_preflight(object(), "ws-1", "destination", request)
    assert error is None
    assert placement["after_cue_id"] == first_id
    assert placement["expected_index"] == 1

    request["after_cue_id"] = other_id
    _, _, placement, error = write_operations._create_preflight(object(), "ws-1", "destination", request)
    assert placement is None
    assert "direct child" in error


def test_create_cues_result_has_typed_items_and_destination() -> None:
    result = CreateCuesResult.model_validate({
        "ok": True, "status": "dry_run", "workspace_id": "ws-1", "dry_run": True,
        "requested_count": 1,
        "destination": {"kind": "cue_list", "id": "22222222-2222-4222-8222-222222222222"},
        "results": [{"index": 0, "cue_type": "Audio", "status": "planned"}],
        "message": "planned",
    })

    assert result.destination.kind == "cue_list"
    assert result.results[0].index == 0
    assert result.results[0].created_cue_id is None


def test_create_cues_places_one_cue_in_empty_cart(monkeypatch: pytest.MonkeyPatch) -> None:
    cart_id = "22222222-2222-4222-8222-222222222222"
    created_id = "33333333-3333-4333-8333-333333333333"
    snapshot = {
        "nodes": {cart_id: {"uniqueID": cart_id, "type": "Cue Cart"}},
        "parent_by_child": {}, "children_by_parent": {cart_id: []},
    }
    placement = {
        "mode": "empty_cart", "parent_id": cart_id, "parent_type": "Cue Cart",
        "parent_container_id": cart_id, "parent_osc_id": cart_id,
        "new_args": [cart_id, 0, 0], "expected_index": 0,
        "parent_children": [], "parent_fingerprint": write_operations._structural_fingerprint([]),
        "tree_fingerprint": write_operations._create_tree_fingerprint(snapshot),
    }
    monkeypatch.setattr(write_operations, "_create_preflight", lambda *_: (
        snapshot, {"active_count": 0}, placement, None
    ))
    monkeypatch.setattr(write_operations, "ensure_write_ready", lambda *_: "ws-1")

    class Stub:
        client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True))

        @staticmethod
        def _resolve_workspace_id_strict(workspace_id: str) -> str:
            return workspace_id

    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: {"children_by_parent": {cart_id: [created_id]}})
    monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 0})
    calls: list[tuple[str | None, str | None, bool]] = []

    def fake_create_cue(_workspace, _cue_type, dry_run=None, after_cue_id=None, parent_container_id=None, confirm_token=None):
        del confirm_token
        calls.append((after_cue_id, parent_container_id, bool(dry_run)))
        if dry_run:
            return {"ok": True, "confirm_token": "item-token"}
        return {"ok": True, "status": "created", "created_cue_id": created_id}

    stub = Stub()
    stub.create_cue = fake_create_cue
    planned = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["audio"], dry_run=True, cue_cart_id=cart_id
    )
    result = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["audio"], dry_run=False,
        cue_cart_id=cart_id, confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "created"
    assert result["results"][0]["created_cue_id"] == created_id
    assert calls == [(None, cart_id, True), (None, cart_id, False)]


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

    monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: {"children_by_parent": {parent: [anchor, "33333333-3333-4333-8333-333333333333", "44444444-4444-4444-8444-444444444444"]}})
    monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 0})
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
        stub, "ws-1", ["memo", "audio"], dry_run=True, cue_list_id=parent
    )
    assert planned["status"] == "dry_run"
    assert "plan operations" in planned["message"]
    assert "requested_count" in planned["message"]
    assert any(
        item.get("operation") == "new" and item.get("anchor_from_previous") is True
        for item in planned["planned_operations"]
    )
    changed_order = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["audio", "memo"], dry_run=False,
        cue_list_id=parent, confirm_token=planned["confirm_token"],
    )
    changed_destination = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio"], dry_run=False,
        group_id=parent, confirm_token=planned["confirm_token"],
    )
    old_token = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio"], dry_run=False,
        cue_list_id=parent,
        confirm_token=planned["confirm_token"].replace("createCues:v2", "createCues:v1"),
    )
    assert changed_order["status"] == changed_destination["status"] == old_token["status"] == "preflight_failed"
    assert calls == []
    result = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio"], dry_run=False,
        cue_list_id=parent, confirm_token=planned["confirm_token"],
    )
    assert result["status"] == "created"
    assert result["destination"]["kind"] == "cue_list"
    assert result["destination"]["id"] == parent
    assert result["destination"]["resolved_after_cue_id"] == anchor
    assert result["destination"]["insertion_index"] == 1
    assert [(item["index"], item["cue_type"], item["created_cue_id"]) for item in result["results"]] == [
        (0, "Memo", "33333333-3333-4333-8333-333333333333"),
        (1, "Audio", "44444444-4444-4444-8444-444444444444"),
    ]
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
        stub, "ws-1", ["memo", "audio", "wait"], dry_run=True, cue_list_id=parent
    )
    result = write_operations.QLabWriteMixin.create_cues(
        stub, "ws-1", ["memo", "audio", "wait"], dry_run=False,
        cue_list_id=parent, confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "partial_failed"
    assert result["created_count"] == 1
    assert result["results"][0]["created_cue_id"] == created_id
    assert result["error_code"] == "verification_failed"
    assert "Inspect" in result["suggested_action"]
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

    def read_cue_values(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"values": {"isBroken": False, "isWarning": False}}


@pytest.mark.parametrize("field", ["isBroken", "isWarning"])
def test_move_cues_reads_fresh_health_when_shallow_structure_omits_it(field: str) -> None:
    reader = MovePlanReader()
    reads = []

    def values(workspace_id: str, cue_id: str, keys: list[str], **kwargs: Any) -> dict[str, Any]:
        reads.append(cue_id)
        assert workspace_id == reader.workspace_id
        assert kwargs["cacheable"] is False
        health = {"isBroken": False, "isWarning": False}
        health[field] = cue_id == reader.first_id
        return {"values": health}

    reader.read_cue_values = values
    result = move_cues(reader, reader.workspace_id, [{"cue_id": reader.first_id, "position": "last"}], dry_run=True)

    assert result["status"] == "planned"
    assert reader.first_id in reads
    assert result["results"][0]["source_health"]["is_broken" if field == "isBroken" else "is_warning"] is True
    assert any("health" in warning.lower() for warning in result["warnings"])


@pytest.mark.parametrize("values", [{}, {"isBroken": False}, {"isBroken": "false", "isWarning": False}])
def test_move_cues_rejects_incomplete_or_invalid_health(values: dict[str, Any]) -> None:
    reader = MovePlanReader()
    reader.read_cue_values = lambda *_args, **_kwargs: {"values": values}
    result = move_cues(reader, reader.workspace_id, [{"cue_id": reader.first_id, "position": "last"}], dry_run=True)
    assert result["status"] == "preflight_failed"
    assert result["confirm_token"] is None


@pytest.mark.parametrize("field", ["before_cue_id", "after_cue_id"])
def test_move_cues_accepts_uppercase_uuid_anchors(field: str) -> None:
    reader = MovePlanReader()
    reader.first_id = "AAAAAAAA-AAAA-4AAA-8AAA-AAAAAAAAAAAA"
    reader.second_id = "BBBBBBBB-BBBB-4BBB-8BBB-BBBBBBBBBBBB"
    source, anchor = (reader.second_id, reader.first_id) if field == "before_cue_id" else (reader.first_id, reader.second_id)
    result = move_cues(reader, reader.workspace_id, [{"cue_id": source, field: anchor}], dry_run=True)
    assert result["status"] == "planned"
    assert result["results"][0][field] == anchor.lower()
    assert result["results"][0]["destination_index"] == (0 if field == "before_cue_id" else 1)


def test_move_cues_skips_verified_noop_before_executing_next_move(monkeypatch: pytest.MonkeyPatch) -> None:
    reader = MovePlanReader()
    children = reader.get_cue_children(reader.workspace_id, reader.list_id)["children"]
    reader.get_cue_children = lambda *_args, **_kwargs: {"children": children}
    sent = []

    def request(address: str, index: int, **_: Any) -> Any:
        cue_id = address.rsplit("/", 1)[-1]
        sent.append(cue_id)
        if cue_id == reader.first_id:
            raise ValueError("QLab rejects a move to the existing index")
        children.insert(index, children.pop(1))
        return SimpleNamespace(data={"parent_cue_id": reader.list_id, "index": index}, status="ok")

    reader.client.request = request
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    moves = [{"cue_id": cid, "position": "first"} for cid in (reader.first_id, reader.second_id)]
    plan = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert result["ok"] and result["moved_count"] == 2
    assert sent == [reader.second_id]
    assert result["results"][0]["reply_status"] == "skipped_no_op"


def test_move_cues_executes_fifty_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    from uuid import UUID

    reader = MovePlanReader()
    cue_ids = [str(UUID(int=index + 100)) for index in range(50)]
    children = [{"uniqueID": cue_id, "type": "Memo"} for cue_id in cue_ids]
    reader.get_cue_children = lambda *_args, **_kwargs: {"children": children}
    sent = []

    def request(address: str, index: int, **_: Any) -> Any:
        cue_id = address.rsplit("/", 1)[-1]
        sent.append(cue_id)
        moving = next(cue for cue in children if cue["uniqueID"] == cue_id)
        children.remove(moving)
        children.insert(index, moving)
        return SimpleNamespace(data={"parent_cue_id": reader.list_id, "index": index}, status="ok")

    reader.client.request = request
    monkeypatch.setattr("qlab_mcp.write.moves.ensure_write_ready", lambda *_: reader.workspace_id)
    moves = [{"cue_id": cue_id, "position": "first"} for cue_id in cue_ids]
    planned = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=planned["confirm_token"])

    assert result["moved_count"] == 50
    assert sent == cue_ids[1:]
    assert [cue["uniqueID"] for cue in children] == list(reversed(cue_ids))


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
        current = [reader.second_id, reader.first_id] if reader.after_set and reader.snapshot_reads >= 5 else original_children
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
        allow_empty_data: bool = False,
        ensure_always_reply: bool = False,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/alwaysReply":
            return SimpleNamespace(data=None, status="ok")
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
    assert any(item["operation"] == "set_current_cue_list" and item["status"] == "indeterminate" for item in result["executed_operations"])
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
        allow_empty_data: bool = False,
        ensure_always_reply: bool = False,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": self.workspace_id, "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/alwaysReply":
            return SimpleNamespace(data=None, status="ok")
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
        if not args and not allow_empty_data:
            return SimpleNamespace(data=self.cues[cue_id].get(prop), status="ok")
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


def _assert_update_profile_names_and_shape(catalog: dict[str, Any]) -> None:
    assert set(UPDATE_PROFILE_NAMES) == {
        "control_basic",
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
    assert catalog["audio_basic"]["properties"]["fileTarget"]["real_write_enabled"] is True
    assert catalog["audio_basic"]["properties"]["fileTarget"]["planned_only_reason"] is None
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
    assert "batch_update_cues" not in result["capabilities"]
    assert result["capabilities"]["edit_existing_cue"]["tool"] is None
    assert result["capabilities"]["edit_existing_cue"]["public_generic_editor"] is False
    assert "qlab_edit_control_cues" in result["capabilities"]["edit_existing_cue"]["replacement_tools"]
    assert result["capabilities"]["edit_existing_cue"]["batch"] == {
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

    result = reader.create_cue("ws-1", "audio", dry_run=False)
    assert result["status"] == "preflight_failed"
    assert "Write mode is disabled" in result["errors"]["preflight"]

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

    result = reader.create_cue("ws-1", "audio", dry_run=False, after_cue_id="cue-before")
    assert result["status"] == "preflight_failed"
    message = result["errors"]["preflight"]
    assert "exact cue UUID" in message
    assert secret not in message
    assert not any(address.endswith("/new") for address, _, _ in client.requests)


def test_create_cue_real_blocks_without_confirmed_edit() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data="ok:view|control")
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue("ws-1", "memo", dry_run=False)
    assert result["status"] == "preflight_failed"
    assert "edit permission" in result["errors"]["preflight"]

    assert [request[0] for request in client.requests] == ["/workspaces", "/workspace/ws-1/connect"]


def test_create_cue_real_blocks_in_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue("ws-1", "memo", dry_run=False)
    assert result["status"] == "preflight_failed"
    assert "Show Mode" in result["errors"]["preflight"]

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


@pytest.mark.parametrize("drift", ["siblings", "source", "group", "none_source", "none_group"])
def test_move_verifies_full_parent_orders_and_group_contents(monkeypatch, drift):
    reader = MovePlanReader()
    group_id = "55555555-5555-4555-8555-555555555555"
    nested_id = "66666666-6666-4666-8666-666666666666"
    third_id = "77777777-7777-4777-8777-777777777777"
    tree = {reader.list_id: [reader.first_id, reader.second_id, third_id, group_id],
            group_id: [nested_id]}
    reader.get_cue_children = lambda _, cid, **kw: {"children": [
        {"uniqueID": child, "type": "Group" if child == group_id else "Memo"}
        for child in tree[cid]]}
    target = group_id if drift.endswith("group") else reader.first_id
    move = {"cue_id": target, "position": "first" if drift.endswith("group") else "last"}
    if drift.endswith("source"):
        move["destination_parent_id"] = group_id

    def request(address, index, *args):
        cid = address.rsplit("/", 1)[-1]
        tree[reader.list_id].remove(cid)
        destination = args[0] if args else reader.list_id
        tree[destination].insert(index, cid)
        if drift == "group":
            tree[group_id].clear()
        elif not drift.startswith("none_"):
            tree[reader.list_id][:2] = reversed(tree[reader.list_id][:2])
        return SimpleNamespace(status="ok", data=None)

    reader.client.request = request
    monkeypatch.setattr(move_helpers, "ensure_write_ready", lambda *_: reader.workspace_id)
    monkeypatch.setattr(move_helpers, "MOVE_CONVERGENCE_DEADLINES_SECONDS", (0,))
    plan = move_cues(reader, reader.workspace_id, [move], dry_run=True)
    result = move_cues(reader, reader.workspace_id, [move], dry_run=False, confirm_token=plan["confirm_token"])
    assert result["ok"] is drift.startswith("none_")
    assert result["moved_count"] == int(drift.startswith("none_"))
    assert result["uncertain_cue_ids"] == ([] if drift.startswith("none_") else [target])
    assert result["pending_cue_ids"] == []


@pytest.mark.parametrize("phase", ["before", "between", "before_structure", "between_structure", "final_activity", "final_structure"])
def test_move_read_failures_preserve_confirmed_progress(monkeypatch, phase):
    reader = MovePlanReader()
    children = reader.get_cue_children(reader.workspace_id, reader.list_id)["children"]
    reader.get_cue_children = lambda *a, **kw: {"children": children}
    sent = []

    def request(address, index):
        cid = address.rsplit("/", 1)[-1]
        sent.append(cid)
        cue = next(c for c in children if c["uniqueID"] == cid)
        children.remove(cue)
        children.insert(index, cue)
        return SimpleNamespace(status="ok", data=None)

    reader.client.request = request
    moves = [{"cue_id": cid, "position": "last"} for cid in (reader.first_id, reader.second_id)]
    monkeypatch.setattr(move_helpers, "ensure_write_ready", lambda *_: reader.workspace_id)
    plan = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    activity_reads = 0

    def activity(*a, **kw):
        nonlocal activity_reads
        activity_reads += 1
        # execution preflight, before first, before second, final
        at = {"before": 2, "between": 3, "final_activity": 4}.get(phase)
        if activity_reads == at:
            raise OscTimeoutError("synthetic activity timeout")
        return {"running_cues": []}

    reader.get_running_cues = activity
    if phase in ("before_structure", "between_structure", "final_structure"):
        original = move_helpers._read_snapshot
        reads = 0

        def snapshot(*a, **kw):
            nonlocal reads
            reads += 1
            if reads == {"before_structure": 2, "between_structure": 4, "final_structure": 6}[phase]:
                raise OscTimeoutError("synthetic final structure timeout")
            return original(*a, **kw)

        monkeypatch.setattr(move_helpers, "_read_snapshot", snapshot)
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    count = {"before": 0, "between": 1, "before_structure": 0, "between_structure": 1}.get(phase, 2)
    assert result["moved_count"] == count == len(sent)
    assert result["pending_cue_ids"] == [m["cue_id"] for m in moves[count:]]
    assert result["uncertain_cue_ids"] == []
    assert len(result["results"]) == count + (count < 2)
    assert result["status"] == ("verification_failed" if count == 2 else "partial_failed" if count else "preflight_failed")


def test_move_checks_noop_structure_before_sending_any_setter(monkeypatch):
    reader = MovePlanReader()
    moves = [{"cue_id": reader.first_id, "position": "first"}]
    plan = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    original = move_helpers._read_snapshot
    reads = 0

    def snapshot(*a, **kw):
        nonlocal reads
        reads += 1
        result = original(*a, **kw)
        if reads == 2:
            result["children_by_parent"][reader.list_id].reverse()
        return result

    monkeypatch.setattr(move_helpers, "_read_snapshot", snapshot)
    monkeypatch.setattr(move_helpers, "ensure_write_ready", lambda *_: reader.workspace_id)
    reader.client.request = lambda *a: pytest.fail("No setter should be sent")
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert result["status"] == "preflight_failed"
    assert result["pending_cue_ids"] == [reader.first_id]


def test_move_group_token_binds_reviewed_contents(monkeypatch):
    reader = MovePlanReader()
    reader.get_cue_children = lambda _, cid, **kw: {"children": (
        [{"uniqueID": reader.first_id, "type": "Group"}, {"uniqueID": reader.second_id, "type": "Memo"}]
        if cid == reader.list_id else [])}
    moves = [{"cue_id": reader.first_id, "position": "last"}]
    plan = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    previous = reader.get_cue_children
    reader.get_cue_children = lambda ws, cid, **kw: (previous(ws, cid, **kw) if cid == reader.list_id else
        {"children": [{"uniqueID": "77777777-7777-4777-8777-777777777777", "type": "Memo"}]})
    monkeypatch.setattr(move_helpers, "ensure_write_ready", lambda *_: reader.workspace_id)
    reader.client.request = lambda *a: pytest.fail("No setter should be sent")
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert result["status"] == "preflight_failed"
    assert "confirm_token" in result["errors"]


def test_move_final_audit_detects_drift_without_duplicating_confirmed_results(monkeypatch):
    reader = MovePlanReader()
    children = reader.get_cue_children(reader.workspace_id, reader.list_id)["children"]
    reader.get_cue_children = lambda *a, **kw: {"children": children}

    def request(*a):
        children.reverse()
        return SimpleNamespace(status="ok", data=None)

    reader.client.request = request
    monkeypatch.setattr(move_helpers, "ensure_write_ready", lambda *_: reader.workspace_id)
    moves = [{"cue_id": reader.first_id, "position": "last"}]
    plan = move_cues(reader, reader.workspace_id, moves, dry_run=True)
    reads = 0
    original = move_helpers._read_snapshot

    def snapshot(*a, **kw):
        nonlocal reads
        reads += 1
        if reads == 4:
            children.reverse()
        return original(*a, **kw)

    monkeypatch.setattr(move_helpers, "_read_snapshot", snapshot)
    result = move_cues(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert result["status"] == "verification_failed"
    assert result["moved_count"] == len(result["results"]) == 1
    assert result["results"][0]["status"] == "moved"
    assert result["pending_cue_ids"] == result["uncertain_cue_ids"] == []


class BatchCreateReader(EmptyContainerReader):
    """Extend the existing OSC fixture with ordered, mixed-type creations."""
    def __init__(self, container_type="Cue List", populated=False):
        super().__init__(container_type, real=True)
        self.tree = {self.list_id: []}
        self.types = {self.list_id: "Cue List"}
        if container_type != "Cue List":
            self.tree[self.list_id].append(self.target_id)
            self.tree[self.target_id] = []
            self.types[self.target_id] = container_type
        if populated:
            self.tree[self.target_id].append(self.created_id)
            self.types[self.created_id] = "Memo"
        self.new_count = 0
        self.fail_at = None
        self.fail_kind = None
        self.after_new = lambda: None

    def get_cue_children(self, _workspace, cue_ref, **kwargs):
        return {"children": [{"uniqueID": cue_id, "type": self.types[cue_id]} for cue_id in self.tree[cue_ref]]}

    def get_cue_details(self, _workspace, cue_ref, _profile="auto"):
        props = {"uniqueID": cue_ref, "type": self.types[cue_ref], "isRunning": False,
                 "isPaused": False, "isAuditioning": False, "isActionRunning": False,
                 "isBroken": False, "isWarning": False}
        if self.container_type == "Cue Cart":
            props["cartPosition"] = [1, 1]
        return {"properties": props}

    def _request(self, address, *args, **kwargs):
        if address == f"/workspace/{self.workspace}/new":
            self.requests.append((address, args, None))
            self.new_count += 1
            if self.new_count == self.fail_at and self.fail_kind == "denied":
                raise QLabReplyError("denied", "edit denied", address)
            cue_id = str(UUID(int=self.new_count))
            self.types[cue_id] = write_operations.writable_cue_type_label(args[0])
            if self.types[cue_id] == "Group":
                self.tree[cue_id] = []
            anchor = args[1] if len(args) > 1 else None
            if len(args) == 4:
                parent, index = anchor, 0
            elif anchor:
                parent = next(parent for parent, children in self.tree.items() if anchor in children)
                index = self.tree[parent].index(anchor) + 1
            else:
                parent, index = self.current_list_id, 0
            self.tree[parent].insert(index, cue_id)
            self.after_new()
            if self.new_count == self.fail_at:
                if self.fail_kind == "timeout":
                    raise OscTimeoutError("new reply lost")
                if self.fail_kind == "protocol":
                    from qlab_mcp.errors import OscProtocolError
                    raise OscProtocolError("new reply malformed")
                if self.fail_kind == "uuid":
                    return SimpleNamespace(data="not-a-uuid", status="ok")
            return SimpleNamespace(data=cue_id, status="ok")
        if "/move/" in address:
            self.requests.append((address, args, None))
            cue_id = address.rsplit("/", 1)[-1]
            for children in self.tree.values():
                if cue_id in children:
                    children.remove(cue_id)
                    break
            self.tree[args[1]].insert(args[0], cue_id)
            return SimpleNamespace(data=None, status="ok")
        return super()._request(address, *args, **kwargs)


def _run_create_batch(reader, types):
    destination = {"Cue List": "cue_list_id", "Group": "group_id", "Cue Cart": "cue_cart_id"}[reader.container_type]
    args = {destination: reader.target_id}
    planned = reader.create_cues(reader.workspace, types, dry_run=True, **args)
    assert planned["ok"], planned
    return reader.create_cues(reader.workspace, types, dry_run=False, confirm_token=planned["confirm_token"], **args)


@pytest.mark.parametrize("count", [1, 50, 100])
@pytest.mark.parametrize("container,populated", [("Cue List", False), ("Cue List", True), ("Group", False), ("Group", True)])
def test_create_batch_real_executor_preserves_order_and_mixed_types(count, container, populated):
    reader = BatchCreateReader(container, populated)
    original = list(reader.tree[reader.target_id])
    types = list(CUE_TYPES)
    requested = [types[index % len(types)] for index in range(count)]
    result = _run_create_batch(reader, requested)
    assert result["ok"] and result["batch_verified"], result
    assert result["created_count"] == reader.new_count == count
    assert result["pending_indices"] == result["uncertain_indices"] == []
    ids = [item["created_cue_id"] for item in result["results"]]
    assert reader.tree[reader.target_id] == original + ids
    assert [reader.types[cue_id] for cue_id in ids] == [write_operations.writable_cue_type_label(t) for t in requested]
    replay = reader.create_cues(reader.workspace, requested, dry_run=False, cue_list_id=reader.list_id, confirm_token="invalid")
    assert not replay["ok"] and reader.new_count == count


def test_create_batch_final_verification_normalizes_uppercase_result_uuids():
    reader = BatchCreateReader("Group")
    before = write_operations._read_structural_snapshot(reader, reader.workspace)
    cue_id = "ABCDEFAB-0000-4000-8000-000000000001"
    reader.tree[reader.target_id].append(cue_id)
    reader.types[cue_id] = reader.types[cue_id.lower()] = "Memo"
    write_operations._verify_created_batch(
        reader,
        reader.workspace,
        before,
        {"parent_id": reader.target_id, "expected_index": 0},
        [{"created_cue_id": cue_id, "cue_type": "Memo"}],
    )


@pytest.mark.parametrize("kind,uncertain", [("timeout", [1]), ("protocol", [1]), ("uuid", [1]), ("denied", [])])
def test_create_batch_keeps_confirmed_results_and_never_resends(kind, uncertain):
    reader = BatchCreateReader()
    reader.fail_at, reader.fail_kind = 2, kind
    result = _run_create_batch(reader, ["memo", "audio", "wait"])
    assert result["status"] == "partial_failed"
    assert result["created_count"] == 1 and reader.new_count == 2
    assert result["results"][0]["created_cue_id"] == str(UUID(int=1))
    assert result["pending_indices"] == [2]
    assert result["uncertain_indices"] == uncertain
    assert not result["batch_verified"]
    new_ops = [op for op in result["executed_operations"] if op["operation"] == "new"]
    assert len(new_ops) == 2


@pytest.mark.parametrize("stage", ["plan", "execute", "final"])
def test_create_batch_catches_escaping_errors_without_losing_results(monkeypatch, stage):
    reader = BatchCreateReader()
    original = reader.create_cue
    def injected(*args, **kwargs):
        if reader.new_count == 1 and kwargs["dry_run"] == (stage == "plan"):
            raise OSError("injected failure")
        return original(*args, **kwargs)
    if stage == "final":
        monkeypatch.setattr(write_operations, "_verify_created_batch", lambda *_: (_ for _ in ()).throw(OSError("final read failed")))
    else:
        reader.create_cue = injected
    result = _run_create_batch(reader, ["memo", "wait"])
    assert result["status"] == "partial_failed"
    assert result["created_count"] == (2 if stage == "final" else 1)
    assert not result["batch_verified"]
    assert result["uncertain_indices"] == ([1] if stage == "execute" else [])


def test_create_batch_budget_stops_before_next_new(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(write_operations.time, "monotonic", lambda: clock[0])
    reader = BatchCreateReader()
    reader.after_new = lambda: clock.__setitem__(0, 271.0)
    result = _run_create_batch(reader, ["memo", "wait", "audio"])
    assert result["created_count"] == reader.new_count == 1
    assert result["pending_indices"] == [1, 2] and result["uncertain_indices"] == []
    assert result["error_code"] == "create_budget_exhausted"


@pytest.mark.parametrize("fault", ["order", "activity", "read"])
def test_create_final_verification_rejects_drift_and_read_errors(monkeypatch, fault):
    reader = BatchCreateReader(populated=True)
    verify = write_operations._verify_created_batch
    def injected(*args):
        if fault == "order":
            reader.tree[reader.list_id].reverse()
        elif fault == "activity":
            monkeypatch.setattr(write_operations, "_structural_activity_snapshot", lambda *_: {"active_count": 1})
        else:
            monkeypatch.setattr(write_operations, "_read_structural_snapshot", lambda *_: (_ for _ in ()).throw(OSError("final read failed")))
        return verify(*args)
    monkeypatch.setattr(write_operations, "_verify_created_batch", injected)
    result = _run_create_batch(reader, ["memo", "wait"])
    assert result["created_count"] == 2 and result["status"] == "partial_failed"
    assert result["pending_indices"] == result["uncertain_indices"] == []
    assert result["error_code"] == "create_final_verification_failed" and not result["batch_verified"]


def test_create_permission_denied_selecting_empty_list_never_sends_new():
    reader = BatchCreateReader()
    original = reader._request
    def denied(address, *args, **kwargs):
        if "/currentCueListID/" in address:
            raise QLabReplyError("denied", "control permission required", address)
        return original(address, *args, **kwargs)
    reader._request = denied
    result = _run_create_batch(reader, ["memo", "wait"])
    assert not result["ok"] and reader.new_count == 0
    assert result["uncertain_indices"] == [] and result["pending_indices"] == [1]
    assert "control permission" in result["errors"]["current_cue_list"]


@pytest.mark.parametrize("fault", ["expired", "consumed", "drift", "activity"])
def test_create_batch_token_and_preflight_block_without_new(monkeypatch, fault):
    reader = BatchCreateReader(populated=True)
    types = ["memo", "wait"]
    args = {"cue_list_id": reader.list_id}
    planned = reader.create_cues(reader.workspace, types, dry_run=True, **args)
    token = planned["confirm_token"]
    if fault == "expired":
        now = time.time()
        monkeypatch.setattr(write_operations.time, "time", lambda: now + 301)
    elif fault == "consumed":
        payload, error = write_operations._decode_create_cues_token(token)
        assert not error
        assert not write_operations._consume_create_token(token, payload)
    elif fault == "drift":
        extra = str(UUID(int=99))
        reader.tree[reader.list_id].append(extra)
        reader.types[extra] = "Memo"
    else:
        reader.get_running_cues = lambda *a, **kw: {"running_cues": [{"uniqueID": reader.created_id}]}
    result = reader.create_cues(reader.workspace, types, dry_run=False, confirm_token=token, **args)
    assert not result["ok"] and reader.new_count == 0
    assert result["pending_indices"] == [0, 1] and not result["uncertain_indices"]


def test_create_batch_budget_after_planning_does_not_send_new(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(write_operations.time, "monotonic", lambda: clock[0])
    reader = BatchCreateReader()
    original = reader.create_cue
    def plan_then_expire(*args, **kwargs):
        result = original(*args, **kwargs)
        if kwargs["dry_run"]:
            clock[0] = 271.0
        return result
    reader.create_cue = plan_then_expire
    result = _run_create_batch(reader, ["memo", "wait"])
    assert result["status"] == "preflight_failed" and reader.new_count == 0
    assert result["pending_indices"] == [0, 1] and result["uncertain_indices"] == []


def test_create_mutations_use_remaining_reader_deadline(monkeypatch):
    reader = BatchCreateReader("Group")
    handler = reader._request
    timeouts = []
    def request(address, *args, **kwargs):
        if address.endswith("/new") or "/move/" in address:
            timeouts.append(kwargs.get("reply_timeout"))
        return handler(address, *args, **kwargs)
    reader.client.request = request
    reader._request = QLabReader._request.__get__(reader, BatchCreateReader)
    result = _run_create_batch(reader, ["memo"])
    assert result["ok"]
    assert len(timeouts) == 2 and all(0 < timeout <= reader.client.config.timeout for timeout in timeouts)
