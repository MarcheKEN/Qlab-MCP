"""Specialized adapters keep the existing executor and its safety gates."""
from uuid import UUID

import pytest
from pydantic import ValidationError

from qlab_mcp.write import remaining

WS, CUE = [str(UUID(int=i)).upper() for i in (1, 2)]


class Reader:
    def __init__(self):
        self.calls = []



@pytest.mark.parametrize("family", remaining.FAMILIES)
def test_adapter_uses_exact_family_and_preserves_confirmations(monkeypatch, family):
    calls = []
    monkeypatch.setattr(remaining.control, "edit_control_cues", lambda reader, ws, items, dry_run, _family: calls.append((ws, items, dry_run, _family)))
    remaining.edit_remaining_cues(Reader(), WS, [{"cue_id": CUE, "properties": {"name": "new"}, "confirm_gates": ["fresh-token"]}], True, family=family)
    ws, items, dry_run, selected = calls[0]
    assert (ws, dry_run, selected) == (WS, True, family)
    assert items[0].properties.name == "new" and items[0].confirm_gates == ["fresh-token"]


@pytest.mark.parametrize("family", remaining.FAMILIES)
@pytest.mark.parametrize("properties", [{}, {"name": None}, {"name": 4}, {"unknown": 1},
                                       {"duration": True}, {"duration": float("nan")},
                                       {"secondTriggerAction": 6}, {"fadeAndStopOthers": 4},
                                       {"timecodeTrigger": {}}, {"audioMapID": CUE}])
def test_typed_contract_rejects_unsafe_input(family, properties):
    with pytest.raises(ValidationError):
        remaining.FAMILIES[family].model_validate({"cue_id": CUE, "properties": properties})


@pytest.mark.parametrize("family", remaining.FAMILIES)
def test_batch_rejects_duplicates_bounds_and_ambiguous_uuid(family):
    reader = Reader()
    item = {"cue_id": CUE, "properties": {"name": "new"}}
    for updates in ([], [item, item], [item] * 51, [{**item, "cue_id": "1"}]):
        with pytest.raises(ValueError):
            remaining.edit_remaining_cues(reader, WS, updates, True, family=family)
    assert not reader.calls


def test_indexed_setters_use_existing_operation_shape():
    item = remaining.AudioCueEditInput.model_validate({"cue_id": CUE, "properties": {"level": {"inChannel": 1, "outChannel": 2, "decibel": "-inf"}}})
    op = remaining.normalize_item(item, "audio")[0]
    assert op["path"] == "level/1/2" and op["args"] == ["-inf"]


@pytest.mark.parametrize("family,properties", [
    ("audio", {"level": {"inChannel": 25, "outChannel": 1, "decibel": 0}}),
    ("mic", {"channels": 25}), ("midi", {"channel": 17}), ("midi", {"messageType": True}),
    ("timecode", {"ltcChannel": 0}), ("timecode", {"outputType": True}),
    ("fade", {"cueTargetID": "cue number"}), ("script", {"scriptSource": "run"}),
    ("light", {"collateAndStart": True}), ("network", {"fps": 121}),
])
def test_family_specific_boundaries(family, properties):
    with pytest.raises(ValidationError):
        remaining.FAMILIES[family].model_validate({"cue_id": CUE, "properties": properties})


@pytest.mark.parametrize("family", remaining.FAMILIES)
def test_capabilities_match_public_model(family):
    model = remaining.control._FAMILIES[family][1]
    caps = remaining.capabilities(family)
    assert caps["tool"] == f"qlab_edit_{family}_cues"
    assert set(caps["allowed_properties"]) | set(caps["blocked_properties"]) == {
        field.alias or name for name, field in model.model_fields.items()}
    assert caps["requires_fresh_preflight"]


def test_triggers_mix_with_family_properties_in_one_plan():
    item = remaining.AudioCueEditInput.model_validate({"cue_id": CUE, "properties": {"duckOthers": True, "rate": 2}})
    assert [op["property"] for op in remaining.normalize_item(item, "audio")] == ["duckOthers", "rate"]


@pytest.fixture
def trigger_reader(monkeypatch):
    from test_control_cue_writes import Reader as ControlReader
    monkeypatch.setattr(remaining.control, "check_write_readiness", lambda *a: {"ok": True})
    monkeypatch.setattr(remaining.control, "ensure_write_ready", lambda *a: None)
    return ControlReader()


@pytest.mark.parametrize("family", remaining.FAMILIES)
def test_trigger_batch_uses_family_bound_one_use_tokens(trigger_reader, family):
    from test_control_cue_writes import START, MEMO
    kind = remaining.control._FAMILIES[family][2][0]
    for uid in (START, MEMO):
        trigger_reader.values[uid]["type"] = kind
    items = [{"cue_id": START, "properties": {"duckOthers": True}},
             {"cue_id": MEMO, "properties": {"secondTriggerAction": 1}}]
    plan = remaining.edit_remaining_cues(trigger_reader, WS, items, True, family=family)
    assert plan["ok"] and not trigger_reader.setters
    assert all(not result["executed_operations"] for result in plan["results"])
    for item, result in zip(items, plan["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    done = remaining.edit_remaining_cues(trigger_reader, WS, items, False, family=family)
    assert done["ok"] and done["updated_count"] == 2
    assert len(trigger_reader.setters) == 2
    assert not remaining.edit_remaining_cues(trigger_reader, WS, items, False, family=family)["ok"]
    assert len(trigger_reader.setters) == 2


@pytest.mark.parametrize("failure,expected", [("prepare", 0), ("timeout", 1), ("mismatch", 1)])
def test_trigger_preparation_timeout_and_batch_stop(trigger_reader, failure, expected):
    from test_control_cue_writes import START, MEMO
    trigger_reader.values[START]["type"] = trigger_reader.values[MEMO]["type"] = "Audio"
    items = [{"cue_id": START, "properties": {"duckOthers": True}},
             {"cue_id": MEMO, "properties": {"name": "pending"}}]
    plan = remaining.edit_remaining_cues(trigger_reader, WS, items, True, family="audio")
    for item, result in zip(items, plan["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    trigger_reader.fail = failure
    done = remaining.edit_remaining_cues(trigger_reader, WS, items, False, family="audio")
    assert len(trigger_reader.setters) == (2 if failure == "timeout" else expected)
    assert done["ok"] is (failure == "timeout")


def test_trigger_type_mismatch_blocks_every_item(trigger_reader):
    from test_control_cue_writes import START, MEMO
    trigger_reader.values[START]["type"] = "Audio"
    result = remaining.edit_remaining_cues(trigger_reader, WS, [
        {"cue_id": START, "properties": {"duckOthers": True}},
        {"cue_id": MEMO, "properties": {"name": "wrong"}}], True, family="audio")
    assert not result["ok"] and not trigger_reader.setters


def test_alias_collision_rejected_before_executor():
    reader = Reader()
    with pytest.raises(ValueError, match="same OSC setter"):
        remaining.edit_remaining_cues(reader, WS, [{"cue_id": CUE, "properties": {
            "note": 60, "byte1": 61}}], True, family="midi")
    assert not reader.calls


@pytest.mark.parametrize("family", remaining.FAMILIES)
def test_public_fastmcp_calls_delegate_to_real_executor(monkeypatch, family):
    import asyncio
    from fastmcp import Client
    from qlab_mcp.config import QLabConfig
    from qlab_mcp.qlab import QLabReader
    import qlab_mcp.server as server
    from test_write_mode import BatchFakeWriteClient, fade_fixture_cues
    kind = remaining.control._FAMILIES[family][2][0]
    values = {CUE: {"type": kind, "name": "old", "isRunning": False, "isPaused": False, "isAuditioning": False}}
    if family == "fade":
        values = fade_fixture_cues(CUE, str(UUID(int=90)).upper())
        values[CUE]["name"] = "old"
        values[CUE]["isAuditioning"] = False
    osc = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="test"), values, workspace_id=WS)
    reader = QLabReader(osc)
    monkeypatch.setattr(reader, "get_running_cues", lambda *a, **k: {"running_cues": []})
    monkeypatch.setattr(server, "_reader", lambda: reader)
    async def run():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            tool = tools[f"qlab_edit_{family}_cues"]
            assert not tool.annotations.readOnlyHint and tool.annotations.destructiveHint
            assert tool.inputSchema["properties"]["updates"]["maxItems"] == 50
            args = {"workspace_id": WS, "updates": [{"cue_id": CUE, "properties": {"name": "new"}}], "dry_run": True}
            plan = (await client.call_tool(tool.name, args)).structured_content
            assert plan["ok"], plan
            assert not plan["results"][0]["executed_operations"]
            assert not any(address.endswith('/name') and params for address, params, _ in osc.requests)
            args["updates"][0]["confirm_gates"] = [op["confirm_token"] for op in plan["results"][0]["planned_operations"]
                                                    if op.get("confirm_token")]
            args["dry_run"] = False
            result = (await client.call_tool(tool.name, args)).structured_content
            assert result["ok"] and result["results"][0]["after"]["name"] == "new", result
            setters = [(address, params) for address, params, _ in osc.requests if address.endswith('/name') and params]
            assert len(setters) == 1
    asyncio.run(run())
