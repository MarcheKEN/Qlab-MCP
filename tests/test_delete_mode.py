from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from qlab_mcp.cues.refs import CONTAINER_CUE_TYPES
from qlab_mcp.errors import OscTimeoutError, QLabReplyError


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
LIST_ID = "22222222-2222-4222-8222-222222222222"
GROUP_ID = "33333333-3333-4333-8333-333333333333"
FIRST_ID = "44444444-4444-4444-8444-444444444444"
SECOND_ID = "55555555-5555-4555-8555-555555555555"
THIRD_ID = "66666666-6666-4666-8666-666666666666"
NESTED_ID = "77777777-7777-4777-8777-777777777777"
CART_ID = "88888888-8888-4888-8888-888888888888"
OTHER_GROUP_ID = "99999999-9999-4999-8999-999999999999"
MISSING_GROUP_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"


def test_delete_mode_reuses_canonical_container_types() -> None:
    from qlab_mcp.write import deletes

    assert deletes.CONTAINER_CUE_TYPES is CONTAINER_CUE_TYPES


class DeleteReader:
    def __init__(self) -> None:
        self.workspace_id = WORKSPACE_ID
        self.children = {
            LIST_ID: [FIRST_ID, GROUP_ID, SECOND_ID, THIRD_ID],
            GROUP_ID: [],
        }
        self.nodes = {
            LIST_ID: {"uniqueID": LIST_ID, "type": "Cue List"},
            GROUP_ID: {"uniqueID": GROUP_ID, "type": "Group"},
            CART_ID: {"uniqueID": CART_ID, "type": "Cue Cart"},
            FIRST_ID: {"uniqueID": FIRST_ID, "type": "Memo", "isRunning": False, "isPaused": False},
            SECOND_ID: {"uniqueID": SECOND_ID, "type": "Memo", "isRunning": False, "isPaused": False},
            THIRD_ID: {"uniqueID": THIRD_ID, "type": "Memo", "isRunning": False, "isPaused": False},
        }
        self.requests: list[tuple[str, tuple[Any, ...]]] = []
        self.fail_on: str | None = None
        self.timeout_on: str | None = None
        self.keep_deleted: set[str] = set()
        self.delayed_deletes: dict[str, int] = {}
        self.pending_deletes: dict[str, int] = {}
        self.active_cues: list[dict[str, Any]] = []
        self.client = SimpleNamespace(
            config=SimpleNamespace(write_dry_run_default=True),
            request=self.request,
        )

    def _resolve_workspace_id_strict(self, workspace_id: str) -> str:
        assert workspace_id == self.workspace_id
        return workspace_id

    def get_cue_lists(self, *_: Any, **__: Any) -> dict[str, Any]:
        for cue_id, remaining in list(self.pending_deletes.items()):
            if remaining <= 0:
                self._apply_delete(cue_id)
                self.pending_deletes.pop(cue_id, None)
            else:
                self.pending_deletes[cue_id] = remaining - 1
        return {"cue_lists": [self.nodes[LIST_ID]]}

    def get_cue_children(self, _workspace_id: str, cue_id: str, **_: Any) -> dict[str, Any]:
        return {"children": [self.nodes[child_id] for child_id in self.children.get(cue_id, [])]}

    def get_running_cues(self, *_: Any, **__: Any) -> dict[str, Any]:
        return {"running_cues": self.active_cues}

    def request(self, address: str, *args: Any, **_: Any) -> Any:
        self.requests.append((address, args))
        if address == "/alwaysReply":
            return SimpleNamespace(data={"status": "ok"}, status="ok")
        cue_id = address.rsplit("/", 1)[-1]
        if cue_id == self.fail_on:
            raise QLabReplyError("error", {"status": "error"}, address)
        if cue_id not in self.keep_deleted:
            if cue_id in self.delayed_deletes:
                self.pending_deletes[cue_id] = self.delayed_deletes.pop(cue_id)
            else:
                self._apply_delete(cue_id)
        if cue_id == self.timeout_on:
            raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
        return SimpleNamespace(data={"status": "ok"}, status="ok")

    def _apply_delete(self, cue_id: str) -> None:
        for children in self.children.values():
            if cue_id in children:
                children.remove(cue_id)
        self.nodes.pop(cue_id, None)


def test_delete_cues_dry_run_is_side_effect_free_and_issues_dedicated_token() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    result = delete_cues(reader, WORKSPACE_ID, [FIRST_ID, SECOND_ID], dry_run=True)

    assert result["status"] == "planned"
    assert result["confirm_token"].startswith("confirm:deleteCues:v1:")
    assert [item["cue_id"] for item in result["results"]] == [FIRST_ID, SECOND_ID]
    assert reader.requests == []


def test_delete_token_binds_parent_order_and_deletion_impact() -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    result = deletes.delete_cues(reader, WORKSPACE_ID, [SECOND_ID], dry_run=True)
    payload, error = deletes._decode_token(result["confirm_token"])
    item = payload["binding"]["plan"][0]

    assert error is None
    assert payload["binding"]["operation_version"] == 1
    assert payload["binding"]["requested_cue_ids"] == [SECOND_ID]
    assert item["previous_sibling_id"] == GROUP_ID
    assert item["next_sibling_id"] == THIRD_ID
    assert item["parent_children_fingerprint"]
    assert item["deletion_impact_fingerprint"]
    assert item["readiness_snapshot"]


def test_delete_cues_rejects_stale_parent_order_after_prior_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.delayed_deletes[FIRST_ID] = 4
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    monkeypatch.setattr(deletes.time, "sleep", lambda _: None)
    plan_a = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID], dry_run=True)
    plan_b = deletes.delete_cues(reader, WORKSPACE_ID, [SECOND_ID], dry_run=True)

    first = deletes.delete_cues(
        reader, WORKSPACE_ID, [FIRST_ID], dry_run=False, confirm_token=plan_a["confirm_token"]
    )
    stale = deletes.delete_cues(
        reader, WORKSPACE_ID, [SECOND_ID], dry_run=False, confirm_token=plan_b["confirm_token"]
    )

    assert first["status"] == "deleted_after_convergence"
    assert stale["status"] == "preflight_failed"
    assert "does not match" in str(stale["errors"]).lower()
    assert SECOND_ID in reader.nodes


def test_delete_cues_polls_delayed_readback_until_convergence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.delayed_deletes[FIRST_ID] = 2
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    monkeypatch.setattr(deletes.time, "sleep", lambda _: None)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID], dry_run=True)

    result = deletes.delete_cues(
        reader, WORKSPACE_ID, [FIRST_ID], dry_run=False, confirm_token=planned["confirm_token"]
    )

    assert result["status"] == "deleted_after_convergence"
    assert result["results"][0]["verification_status"] == "confirmed_after_convergence"
    assert result["results"][0]["readback"]["exists"] is False


def test_delete_cues_waits_for_each_batch_item_before_continuing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.delayed_deletes[FIRST_ID] = 1
    reader.delayed_deletes[SECOND_ID] = 1
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    monkeypatch.setattr(deletes.time, "sleep", lambda _: None)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID, SECOND_ID], dry_run=True)

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        [FIRST_ID, SECOND_ID],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    delete_requests = [address for address, _ in reader.requests if "/delete_id/" in address]
    assert result["status"] == "deleted_after_convergence"
    assert delete_requests == [
        f"/workspace/{WORKSPACE_ID}/delete_id/{FIRST_ID}",
        f"/workspace/{WORKSPACE_ID}/delete_id/{SECOND_ID}",
    ]
    assert [item["verification_status"] for item in result["results"]] == [
        "confirmed_after_convergence",
        "confirmed_after_convergence",
    ]


def test_delete_cues_rejects_duplicates_and_containers_before_mutation() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    duplicate = delete_cues(reader, WORKSPACE_ID, [FIRST_ID, FIRST_ID], dry_run=True)
    container = delete_cues(reader, WORKSPACE_ID, [LIST_ID], dry_run=True)

    assert duplicate["status"] == "preflight_failed"
    assert "duplicate" in str(duplicate["errors"]).lower()
    assert container["status"] == "preflight_failed"
    assert "container" in str(container["errors"]).lower()
    assert reader.requests == []


def test_delete_cues_plans_exact_empty_group_container_delete() -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=True,
    )
    payload, error = deletes._decode_token(planned["confirm_token"])

    assert error is None
    assert planned["status"] == "planned"
    assert planned["requested_count"] == 1
    assert planned["planned_count"] == 1
    assert planned["container_id"] == GROUP_ID
    assert planned["recursive"] is False
    assert planned["results"][0]["cue_id"] == GROUP_ID
    assert planned["results"][0]["cue_type"] == "Group"
    assert payload["binding"]["container_id"] == GROUP_ID
    assert payload["binding"]["recursive"] is False
    assert payload["binding"]["requested_cue_ids"] == [GROUP_ID]
    assert payload["binding"]["plan"][0]["parent_children"] == [FIRST_ID, GROUP_ID, SECOND_ID, THIRD_ID]
    assert reader.requests == []


def test_delete_cues_executes_exact_empty_group_and_verifies_absence(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=True,
    )
    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "deleted_immediately"
    assert result["deleted_count"] == 1
    assert result["container_id"] == GROUP_ID
    assert result["preserved_container_id"] is None
    assert reader.nodes[LIST_ID]["uniqueID"] == LIST_ID
    assert GROUP_ID not in reader.nodes
    assert reader.children[LIST_ID] == [FIRST_ID, SECOND_ID, THIRD_ID]
    assert [address for address, _ in reader.requests if "/delete_id/" in address] == [
        f"/workspace/{WORKSPACE_ID}/delete_id/{GROUP_ID}"
    ]


def test_delete_cues_rejects_nonempty_or_unsupported_direct_containers() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    reader.children[LIST_ID].append(CART_ID)
    reader.children[GROUP_ID] = [NESTED_ID]
    reader.nodes[NESTED_ID] = {"uniqueID": NESTED_ID, "type": "Memo", "isRunning": False, "isPaused": False}
    nonempty = delete_cues(reader, WORKSPACE_ID, container_id=GROUP_ID, dry_run=True)
    cue_list = delete_cues(reader, WORKSPACE_ID, container_id=LIST_ID, dry_run=True)
    cue_cart = delete_cues(reader, WORKSPACE_ID, container_id=CART_ID, dry_run=True)

    assert nonempty["status"] == "preflight_failed"
    assert "empty Group" in str(nonempty["errors"])
    assert cue_list["status"] == "preflight_failed"
    assert "empty Group" in str(cue_list["errors"])
    assert cue_cart["status"] == "preflight_failed"
    assert "empty Group" in str(cue_cart["errors"])
    assert reader.requests == []


def test_delete_cues_rejects_stale_empty_group_token_after_child_appears() -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=True,
    )
    reader.children[GROUP_ID] = [NESTED_ID]
    reader.nodes[NESTED_ID] = {"uniqueID": NESTED_ID, "type": "Memo", "isRunning": False, "isPaused": False}

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "preflight_failed"
    assert "empty Group" in str(result["errors"])
    assert GROUP_ID in reader.nodes
    assert [address for address, _ in reader.requests if "/delete_id/" in address] == []


def test_delete_cues_rejects_active_empty_group_before_mutation() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    reader.nodes[GROUP_ID]["isRunning"] = True

    result = delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=False,
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert "active" in str(result["errors"]).lower()
    assert reader.requests == []


def test_delete_cues_rejects_missing_or_wrong_token_for_empty_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, container_id=GROUP_ID, dry_run=True)

    missing = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        dry_run=False,
        confirm_token=None,
    )
    wrong = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        dry_run=False,
        confirm_token=planned["confirm_token"] + "wrong",
    )

    assert missing["status"] == "preflight_failed"
    assert "required" in str(missing["errors"]).lower()
    assert wrong["status"] == "preflight_failed"
    assert "invalid" in str(wrong["errors"]).lower()
    assert [address for address, _ in reader.requests if "/delete_id/" in address] == []


def test_delete_cues_rejects_group_token_replay_for_different_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.children[LIST_ID].append(OTHER_GROUP_ID)
    reader.nodes[OTHER_GROUP_ID] = {"uniqueID": OTHER_GROUP_ID, "type": "Group"}
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, container_id=GROUP_ID, dry_run=True)

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=OTHER_GROUP_ID,
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "preflight_failed"
    assert "does not match" in str(result["errors"]).lower()
    assert GROUP_ID in reader.nodes
    assert OTHER_GROUP_ID in reader.nodes
    assert [address for address, _ in reader.requests if "/delete_id/" in address] == []


def test_delete_cues_rejects_nonexistent_direct_group() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    result = delete_cues(reader, WORKSPACE_ID, container_id=MISSING_GROUP_ID, dry_run=True)

    assert result["status"] == "preflight_failed"
    assert "does not resolve" in str(result["errors"]).lower()
    assert reader.requests == []


def test_delete_cues_keeps_empty_cue_list_and_cart_direct_delete_blocked() -> None:
    from qlab_mcp.write.deletes import delete_cues

    empty_list_reader = DeleteReader()
    empty_list_reader.children[LIST_ID] = []
    empty_list = delete_cues(empty_list_reader, WORKSPACE_ID, container_id=LIST_ID, dry_run=True)

    empty_cart_reader = DeleteReader()
    empty_cart_reader.children[LIST_ID].append(CART_ID)
    empty_cart_reader.nodes[CART_ID] = {"uniqueID": CART_ID, "type": "Cue Cart"}
    empty_cart = delete_cues(empty_cart_reader, WORKSPACE_ID, container_id=CART_ID, dry_run=True)

    assert empty_list["status"] == "preflight_failed"
    assert "only an empty group" in str(empty_list["errors"]).lower()
    assert empty_cart["status"] == "preflight_failed"
    assert "only an empty group" in str(empty_cart["errors"]).lower()
    assert empty_list_reader.requests == []
    assert empty_cart_reader.requests == []


def test_delete_cues_rejects_parent_and_descendant_batch() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    reader.children[GROUP_ID] = [NESTED_ID]
    reader.nodes[NESTED_ID] = {"uniqueID": NESTED_ID, "type": "Memo", "isRunning": False, "isPaused": False}

    result = delete_cues(reader, WORKSPACE_ID, [GROUP_ID, NESTED_ID], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert "container" in str(result["errors"]).lower()
    assert reader.requests == []


def test_recursive_container_delete_expands_post_order_and_preserves_root() -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.children[LIST_ID] = [GROUP_ID, THIRD_ID]
    reader.children[GROUP_ID] = [NESTED_ID, SECOND_ID]
    reader.children[NESTED_ID] = [FIRST_ID]
    reader.nodes[NESTED_ID] = {"uniqueID": NESTED_ID, "type": "Group"}

    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=True,
        dry_run=True,
    )
    payload, error = deletes._decode_token(planned["confirm_token"])

    assert error is None
    assert [item["cue_id"] for item in planned["results"]] == [FIRST_ID, NESTED_ID, SECOND_ID]
    assert GROUP_ID not in [item["cue_id"] for item in planned["results"]]
    assert payload["binding"]["container_id"] == GROUP_ID
    assert payload["binding"]["recursive"] is True
    assert reader.requests == []


def test_recursive_empty_container_is_verified_noop(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=True,
        dry_run=True,
    )
    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=True,
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "deleted_immediately"
    assert result["planned_count"] == 0
    assert result["preserved_container_id"] == GROUP_ID
    assert GROUP_ID in reader.nodes
    assert [address for address, _ in reader.requests if "/delete_id/" in address] == []


def test_recursive_container_delete_executes_post_order_and_keeps_container(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.children[LIST_ID] = [GROUP_ID, THIRD_ID]
    reader.children[GROUP_ID] = [NESTED_ID, SECOND_ID]
    reader.children[NESTED_ID] = [FIRST_ID]
    reader.nodes[NESTED_ID] = {"uniqueID": NESTED_ID, "type": "Group"}
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    monkeypatch.setattr(deletes.time, "sleep", lambda _: None)

    planned = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=True,
        dry_run=True,
    )
    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        container_id=GROUP_ID,
        recursive=True,
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    delete_requests = [address for address, _ in reader.requests if "/delete_id/" in address]
    assert result["status"] == "deleted_immediately"
    assert delete_requests == [
        f"/workspace/{WORKSPACE_ID}/delete_id/{FIRST_ID}",
        f"/workspace/{WORKSPACE_ID}/delete_id/{NESTED_ID}",
        f"/workspace/{WORKSPACE_ID}/delete_id/{SECOND_ID}",
    ]
    assert GROUP_ID in reader.nodes
    assert reader.children[GROUP_ID] == []


def test_delete_cues_executes_in_order_and_confirms_fresh_absence_readback(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID, SECOND_ID], dry_run=True)
    reader.client.config.write_dry_run_default = False

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        [FIRST_ID, SECOND_ID],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    delete_requests = [address for address, _ in reader.requests if "/delete_id/" in address]
    assert delete_requests == [
        f"/workspace/{WORKSPACE_ID}/delete_id/{FIRST_ID}",
        f"/workspace/{WORKSPACE_ID}/delete_id/{SECOND_ID}",
    ]
    assert result["status"] == "deleted_immediately"
    assert [item["readback"]["exists"] for item in result["results"]] == [False, False]
    assert THIRD_ID in reader.nodes


def test_delete_cues_stops_after_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.fail_on = SECOND_ID
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID, SECOND_ID, THIRD_ID], dry_run=True)

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        [FIRST_ID, SECOND_ID, THIRD_ID],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    delete_requests = [address for address, _ in reader.requests if "/delete_id/" in address]
    assert result["status"] == "partial_failed"
    assert delete_requests == [
        f"/workspace/{WORKSPACE_ID}/delete_id/{FIRST_ID}",
        f"/workspace/{WORKSPACE_ID}/delete_id/{SECOND_ID}",
    ]
    assert THIRD_ID in reader.nodes
    assert FIRST_ID not in reader.nodes


def test_delete_cues_accepts_timeout_only_when_fresh_readback_confirms_absence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.timeout_on = FIRST_ID
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID], dry_run=True)

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        [FIRST_ID],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "deleted_immediately"
    assert result["results"][0]["readback"]["exists"] is False


def test_delete_cues_rejects_active_leaf_before_mutation() -> None:
    from qlab_mcp.write.deletes import delete_cues

    reader = DeleteReader()
    reader.nodes[FIRST_ID]["isRunning"] = True

    result = delete_cues(reader, WORKSPACE_ID, [FIRST_ID], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert "active" in str(result["errors"]).lower()
    assert reader.requests == []


def test_delete_cues_returns_indeterminate_when_readback_never_converges(monkeypatch: pytest.MonkeyPatch) -> None:
    from qlab_mcp.write import deletes

    reader = DeleteReader()
    reader.keep_deleted.add(FIRST_ID)
    monkeypatch.setattr(deletes, "ensure_write_ready", lambda *_: WORKSPACE_ID)
    monkeypatch.setattr(deletes.time, "sleep", lambda _: None)
    planned = deletes.delete_cues(reader, WORKSPACE_ID, [FIRST_ID], dry_run=True)

    result = deletes.delete_cues(
        reader,
        WORKSPACE_ID,
        [FIRST_ID],
        dry_run=False,
        confirm_token=planned["confirm_token"],
    )

    assert result["status"] == "indeterminate"
    assert result["results"][0]["readback"]["exists"] is True
