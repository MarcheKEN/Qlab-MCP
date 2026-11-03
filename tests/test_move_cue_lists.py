"""Root reorder exercises the shared move executor without a live QLab."""

from types import SimpleNamespace
import asyncio
from uuid import UUID

import pytest

from qlab_mcp.errors import OscTimeoutError, UnsafeWriteOperationError
from qlab_mcp.models import MoveCuesResult
from qlab_mcp.write import moves as module


class RootReader:
    workspace_id = str(UUID(int=100))

    def __init__(self, count=3):
        self.roots = [{"uniqueID": str(UUID(int=i + 1)), "type": "Cart" if i % 2 else "Cue List"} for i in range(count)]
        self.child = {"uniqueID": str(UUID(int=200)), "type": "Memo"}
        self.children = {self.roots[0]["uniqueID"]: [self.child]}
        self.sent = []
        self.active = []
        self.client = SimpleNamespace(config=SimpleNamespace(write_dry_run_default=True), request=self.request)

    def _resolve_workspace_id_strict(self, workspace_id):
        assert workspace_id == self.workspace_id
        return workspace_id

    def get_cue_lists(self, *args, **kwargs):
        assert kwargs["cacheable"] is False
        return {"cue_lists": self.roots}

    def get_cue_children(self, workspace, cue_id, **kwargs):
        return {"children": self.children.get(cue_id, [])}

    def read_cue_values(self, *args, **kwargs):
        return {"values": {"isBroken": True, "isWarning": False}}

    def get_running_cues(self, *args, **kwargs):
        return {"running_cues": self.active}

    def request(self, address, index):
        self.sent.append((address, index))
        source = next(root for root in self.roots if root["uniqueID"] == address.rsplit("/", 1)[-1])
        self.roots.remove(source)
        self.roots.insert(index, source)
        return SimpleNamespace(status="ok", data={"parent_cue_id": "__root__", "index": index})


@pytest.fixture
def reader(monkeypatch):
    monkeypatch.setattr(module, "ensure_write_ready", lambda *args: None)
    monkeypatch.setattr(module, "MOVE_CONVERGENCE_DEADLINES_SECONDS", (0.0,))
    return RootReader()


def execute(reader, moves, token=None):
    planned = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)
    assert planned["ok"]
    return module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=False,
                                 confirm_token=token or planned["confirm_token"])


@pytest.mark.parametrize("placement", [{"position": "first"}, {"destination_index": 0},
                                      {"before_cue_id": str(UUID(int=1))}, {"after_cue_id": str(UUID(int=1))}])
def test_mixed_roots_and_placements(reader, placement):
    result = execute(reader, [{"cue_id": str(UUID(int=2)), **placement}])
    assert result["ok"] and result["moved_count"] == 1
    assert result["results"][0]["readback"]["parent_id"] == "__root__"
    assert reader.children[str(UUID(int=1))] == [reader.child]
    assert any("health" in warning.lower() for warning in result["warnings"])
    MoveCuesResult.model_validate(result)


def test_sequential_batch_and_noop(reader):
    result = execute(reader, [{"cue_id": str(UUID(int=i)), "position": "first"} for i in [1, 2, 3]])
    assert result["ok"] and result["moved_count"] == 3
    assert len(reader.sent) == 2
    assert result["results"][0]["reply_status"] == "skipped_no_op"
    assert [root["uniqueID"] for root in reader.roots] == [str(UUID(int=i)) for i in [3, 2, 1]]


def test_root_reference_can_target_an_earlier_move(reader):
    moves = [
        {"cue_id": str(UUID(int=3)), "position": "first"},
        {"cue_id": str(UUID(int=2)), "after_cue_id": str(UUID(int=3))},
    ]
    result = execute(reader, moves)
    assert result["ok"] and result["moved_count"] == 2
    assert [root["uniqueID"] for root in reader.roots] == [
        str(UUID(int=3)), str(UUID(int=2)), str(UUID(int=1))
    ]


def test_moved_reference_is_allowed_only_for_root_batches():
    moves = [
        {"cue_id": str(UUID(int=3)), "destination_parent_id": "parent", "position": "first"},
        {"cue_id": str(UUID(int=2)), "destination_parent_id": "parent", "after_cue_id": str(UUID(int=3))},
    ]
    parents = {str(UUID(int=i)): "parent" for i in (1, 2, 3)}
    with pytest.raises(ValueError, match="after_cue_id cannot reference a cue moved in the same batch"):
        module._validate_batch_dependencies(moves, parents)
    module._validate_batch_dependencies(moves, parents, allow_moved_references=True)


@pytest.mark.parametrize("bad", [
    {"cue_id": str(UUID(int=200)), "position": "last"},
    {"cue_id": str(UUID(int=999)), "position": "last"},
    {"cue_id": str(UUID(int=1)), "position": "first", "destination_index": 0},
    {"cue_id": str(UUID(int=1)), "before_cue_id": str(UUID(int=1))},
    {"cue_id": str(UUID(int=1)), "before_cue_id": str(UUID(int=200))},
    {"cue_id": str(UUID(int=1)), "destination_index": 3},
    {"cue_id": str(UUID(int=1)), "destination_index": True},
])
def test_invalid_requests_send_nothing(reader, bad):
    result = module.move_cue_lists(reader, reader.workspace_id, [bad], dry_run=True)
    assert not result["ok"] and not reader.sent


def test_public_mcp_tool_schema_and_call(reader, monkeypatch):
    from fastmcp import Client
    import qlab_mcp.server as server

    reader.move_cue_lists = lambda **kwargs: module.move_cue_lists(reader, **kwargs)
    monkeypatch.setattr(server, "_reader", lambda: reader)

    async def calls():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 88
            schema = tools["qlab_move_cue_lists"].inputSchema["properties"]["moves"]
            assert (schema["minItems"], schema["maxItems"]) == (1, 50)
            assert schema["items"]["additionalProperties"] is False
            assert "destination_parent_id" not in schema["items"]["properties"]
            request = {"workspace_id": reader.workspace_id,
                       "moves": [{"cue_id": str(UUID(int=1)), "position": "last"}], "dry_run": True}
            plan = await client.call_tool("qlab_move_cue_lists", request)
            assert plan.structured_content["status"] == "planned"
            result = await client.call_tool("qlab_move_cue_lists", {
                **request, "dry_run": False, "confirm_token": plan.structured_content["confirm_token"]})
            assert result.structured_content["moved_count"] == 1

    asyncio.run(calls())


def test_duplicates_and_forbidden_fields(reader):
    move = {"cue_id": str(UUID(int=1)), "position": "last"}
    assert not module.move_cue_lists(reader, reader.workspace_id, [move, move], dry_run=True)["ok"]
    with pytest.raises(UnsafeWriteOperationError):
        module.move_cue_lists(reader, reader.workspace_id, [{**move, "cart_row": 0}], dry_run=True)


def test_fifty_moves_and_limit(reader):
    reader = RootReader(50)
    moves = [{"cue_id": root["uniqueID"], "position": "first"} for root in reader.roots]
    assert execute(reader, moves)["moved_count"] == 50
    with pytest.raises(UnsafeWriteOperationError):
        module.move_cue_lists(reader, reader.workspace_id, moves + [moves[0]], dry_run=True)


@pytest.mark.parametrize("change", ["order", "content", "expired", "family", "renamed_family"])
def test_token_binds_structure_and_family(reader, monkeypatch, change):
    moves = [{"cue_id": str(UUID(int=1)), "position": "last"}]
    plan = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)
    token = plan["confirm_token"]
    assert token.startswith("confirm:moveCueLists:v1:")
    if change == "order":
        reader.roots.reverse()
    elif change == "content":
        reader.children[str(UUID(int=1))] = []
    elif change == "expired":
        now = module.time.time()
        monkeypatch.setattr(module.time, "time", lambda: now + 301)
    else:
        token = module._encode_token(reader.workspace_id, plan["results"])
        if change == "renamed_family":
            token = token.replace("moveCues", "moveCueLists", 1)
    result = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=False, confirm_token=token)
    assert not result["ok"] and not reader.sent


@pytest.mark.parametrize("failure", ["before", "between", "after", "content", "uncertain", "timeout"])
def test_failure_progress_and_no_resend(reader, monkeypatch, failure):
    moves = [{"cue_id": str(UUID(int=i)), "position": "last"} for i in [1, 2]]
    plan = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)
    activity = reader.get_running_cues
    calls = 0

    def get_activity(*args, **kwargs):
        nonlocal calls
        calls += 1
        # Execution preflight, then each setter preflight, then final audit.
        if calls == {"before": 2, "between": 3, "after": 4}.get(failure):
            raise RuntimeError("activity read failed")
        return activity(*args, **kwargs)

    reader.get_running_cues = get_activity
    request = reader.request

    def setter(address, index):
        if failure == "uncertain":
            reader.sent.append((address, index))
            raise RuntimeError("transport lost")
        reply = request(address, index)
        if failure == "content":
            reader.children[str(UUID(int=1))] = []
        if failure == "timeout":
            raise OscTimeoutError(address)
        return reply

    reader.client.request = setter
    result = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    if failure == "timeout":
        assert result["ok"] and result["timeout_confirmed_count"] == 2
    else:
        assert not result["ok"]
        expected_count = {"before": 0, "between": 1, "after": 2, "content": 0, "uncertain": 0}[failure]
        assert result["moved_count"] == expected_count
        if failure in {"content", "uncertain"}:
            assert result["uncertain_cue_ids"] == [str(UUID(int=1))]
        if failure == "after":
            assert len(result["results"]) == 2 and result["pending_cue_ids"] == []
    assert len(reader.sent) <= 2


def test_root_block_and_activity(reader):
    moves = [{"cue_id": str(UUID(int=1)), "position": "last"}]
    assert not module.move_cues(reader, reader.workspace_id, moves, dry_run=True)["ok"]
    reader.active = [reader.child]
    assert not module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)["ok"]


@pytest.mark.parametrize("phase", ["initial", "setter", "readback", "final"])
def test_structure_read_failure_preserves_progress(reader, phase):
    moves = [{"cue_id": str(UUID(int=1)), "position": "last"}]
    plan = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)
    read = reader.get_cue_lists
    calls = 0

    def roots(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == {"initial": 1, "setter": 2, "readback": 3, "final": 4}[phase]:
            raise RuntimeError("root read failed")
        return read(*args, **kwargs)

    reader.get_cue_lists = roots
    result = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert not result["ok"]
    if phase in {"initial", "setter"}:
        assert result["pending_cue_ids"] == [str(UUID(int=1))] and not reader.sent
    elif phase == "readback":
        assert result["uncertain_cue_ids"] == [str(UUID(int=1))] and len(reader.sent) == 1
    else:
        assert result["moved_count"] == 1 and len(result["results"]) == 1
        assert result["pending_cue_ids"] == result["uncertain_cue_ids"] == []


def test_root_move_requires_readiness(reader, monkeypatch):
    def fail(*args):
        raise UnsafeWriteOperationError("Edit Mode required")

    monkeypatch.setattr(module, "ensure_write_ready", fail)
    result = execute(reader, [{"cue_id": str(UUID(int=1)), "position": "last"}])
    assert result["status"] == "preflight_failed" and not reader.sent


def test_concurrent_root_order_before_noop(reader, monkeypatch):
    moves = [{"cue_id": str(UUID(int=1)), "position": "first"}]
    plan = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=True)
    read = reader.get_cue_lists
    calls = 0

    def roots(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            reader.roots[1:] = reversed(reader.roots[1:])
        return read(*args, **kwargs)

    reader.get_cue_lists = roots
    result = module.move_cue_lists(reader, reader.workspace_id, moves, dry_run=False, confirm_token=plan["confirm_token"])
    assert not result["ok"] and not reader.sent
