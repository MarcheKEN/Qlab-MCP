"""Control-family scope, completeness, conditional reads and public contracts."""
import asyncio
import json

import pytest
from fastmcp import Client

import qlab_mcp.server as server
from qlab_mcp.qlab import QLabReader
from qlab_mcp.cues.control import CONTROL_TYPES, _models
from qlab_mcp.allowlist import validate_property_path
from test_light_group_cue_tools import fixture, FIRST, SECOND
from test_cue_list_tools import WS, LIST, CART, OTHER, root


def control_fixture(kind="Start"):
    osc = fixture(kind)
    osc.cell_values[FIRST].update(
        cueTargetID=SECOND, cueTargetNumber="2", currentCueTargetID=SECOND,
        tempCueTargetID="", targetMode=1, patchTargetID=OTHER,
        devampType=2, startNextCueWhenSliceEnds=True, stopTargetWhenSliceEnds=False,
        secondTriggerAction=2, secondTriggerOnRelease=True,
        duckOthers=True, duckLevel=-12.0, duckTime=1.5,
        fadeAndStopOthers=1, fadeAndStopOthersTime=3.0,
        actionElapsed=0.0, currentDuration=5.0, cartPosition=[0, 0],
        isNextInPlaylist=False, isCrossfadingOut=False,
        **{"timecodeTrigger/text": "00:00:00:00"},
    )
    return osc


def read_keys(osc):
    return {key for address, args in osc.calls if address.endswith("valuesForKeys") for key in json.loads(args[0])}


@pytest.mark.parametrize("kind", CONTROL_TYPES)
@pytest.mark.parametrize("profile", ["safe", "technical"])
def test_all_types_complete_common_and_conditional_details(kind, profile):
    osc = control_fixture(kind)
    result = QLabReader(osc).get_control_cue_details(WS, FIRST, profile)
    assert result.ok and not result.partial, result.errors
    assert result.identity.type == kind and result.identity.parent_id == OTHER
    assert result.basics.secondTriggerAction == 2 and result.basics.duckLevel == -12
    assert result.timing.currentDuration == 5 and result.timing.timecodeTriggerText == "00:00:00:00"
    assert result.state.isNextInPlaylist is False
    assert (result.basics.notes == "private") == (profile == "technical" or kind == "Memo")
    assert (result.target is not None) == (kind not in {"Wait", "Memo"})
    assert (result.reset is not None) == (kind == "Reset")
    assert (result.devamp is not None) == (kind == "Devamp")
    keys = read_keys(osc)
    assert ("devampType" in keys) == (kind == "Devamp")
    assert ("patchTargetID" in keys) == (kind == "Reset")
    assert not keys.intersection({"audioMapTargetID", "loadAt", "loadTime", "assignedNumber"})
    assert all("settings" not in path and "/live" not in path for path, _ in osc.calls)
    assert all(path.endswith(("/workspaces", "/valuesForKeys", "/timecodeTrigger/text")) for path, _ in osc.calls)


def test_inventory_filters_before_pagination_and_rejects_cart():
    osc = control_fixture("Start")
    osc.children[OTHER] = [root(FIRST, "Start"), root(SECOND, "Memo"), root(CART, "Audio")]
    osc.cell_values[SECOND] = root(SECOND, "Memo")
    reader = QLabReader(osc)
    result = reader.get_control_cues(WS, LIST, limit=1)
    assert result.matched_count == 2 and result.has_more and result.next_offset == 1
    assert reader.get_control_cues(WS, LIST, offset=1).cues[0].type == "Memo"
    assert reader.get_control_cues(WS, LIST, cue_type="Memo").matched_count == 1
    assert reader.get_control_cues(WS, LIST, cue_type="Stop").cues == []
    assert reader.get_control_cues(WS, CART).error_code == "cue_list_type_mismatch"
    assert not any(f"/{CART}/" in address for address, _ in osc.calls)


@pytest.mark.parametrize("kwargs", [{"limit": 0}, {"offset": -1}, {"limit": True}, {"limit": "1"}, {"max_cues_scanned": 5001}, {"cue_type": "Audio"}])
def test_invalid_inventory_before_io(kwargs):
    osc = control_fixture()
    assert QLabReader(osc).get_control_cues(WS, LIST, **kwargs).error_code == "validation_failed"
    assert not osc.calls


@pytest.mark.parametrize("kind", ["Audio", "Group", "Cue List", "Cue Cart"])
def test_wrong_type(kind):
    result = QLabReader(control_fixture(kind)).get_control_cue_details(WS, FIRST)
    assert result.error_code == "control_cue_type_mismatch" and result.identity is None


def test_identity_and_type_change_even_within_family():
    osc = control_fixture()
    original = osc.reply
    def reply(address, args):
        if address.endswith("valuesForKeys") and "parent" in json.loads(args[0]):
            osc.cell_values[FIRST]["type"] = "Stop"
        return original(address, args)
    osc.reply = reply
    result = QLabReader(osc).get_control_cue_details(WS, FIRST)
    assert result.error_code == "control_cue_identity_mismatch" and result.identity is None


def test_invalid_secondary_fields_are_partial():
    osc = control_fixture("Devamp")
    osc.cell_values[FIRST].update(devampType=True, duckLevel=float("inf"))
    result = QLabReader(osc).get_control_cue_details(WS, FIRST)
    assert result.partial and result.devamp.startNextCueWhenSliceEnds is True
    assert {"devampType", "duckLevel"} <= result.errors.keys()


def test_allowlisted_documented_fields():
    for kind in CONTROL_TYPES:
        for model in _models(kind).values():
            for name, field in model.model_fields.items():
                validate_property_path(field.validation_alias or name)


@pytest.mark.parametrize("value", [False, True, 0, 1, 2, 3])
def test_fade_stop_preserves_documented_and_observed_types(value):
    osc = control_fixture()
    osc.cell_values[FIRST]["fadeAndStopOthers"] = value
    result = QLabReader(osc).get_control_cue_details(WS, FIRST)
    assert result.ok and not result.partial
    assert type(result.basics.fadeAndStopOthers) is type(value)
    assert result.basics.fadeAndStopOthers == value


def test_fastmcp_tools(monkeypatch):
    reader = QLabReader(control_fixture("Devamp"))
    monkeypatch.setattr(server, "_run_tool", lambda fn, **kwargs: fn(reader))
    async def run():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 48
            for name in ("qlab_get_control_cues", "qlab_get_control_cue_details"):
                assert tools[name].annotations.readOnlyHint and tools[name].outputSchema
            inventory = await client.call_tool("qlab_get_control_cues", {"workspace_id": WS, "cue_list_id": LIST})
            detail = await client.call_tool("qlab_get_control_cue_details", {"workspace_id": WS, "cue_id": FIRST})
            assert inventory.structured_content["cues"][0]["type"] == "Devamp"
            assert detail.structured_content["devamp"]["devampType"] == 2
    asyncio.run(run())


def test_budget_includes_complete_response(monkeypatch):
    import qlab_mcp.cues.control as module
    monkeypatch.setattr(module, "MAX_SENSITIVE_CUE_RESPONSE_BYTES", 100)
    result = QLabReader(control_fixture()).get_control_cue_details(WS, FIRST)
    assert result.error_code == "cue_payload_too_large" and result.identity is None
    assert result.basics is None and result.technical_payload is None


def test_secondary_timeout_preserves_fields_and_final_identity():
    osc = control_fixture()
    reader = QLabReader(osc)
    reader.read_cue_property = lambda *args: (_ for _ in ()).throw(TimeoutError("Timed out"))
    result = reader.get_control_cue_details(WS, FIRST)
    assert result.partial and result.basics.duckLevel == -12
    assert "timecodeTrigger/text" in result.errors
    assert osc.calls[-1][0].endswith("valuesForKeys")
    assert json.loads(osc.calls[-1][1][0]) == ["uniqueID", "type"]


@pytest.mark.parametrize("profile", ["safe", "technical"])
def test_unrequested_secrets_never_pass_through(profile):
    osc = control_fixture("Memo")
    reader = QLabReader(osc)
    original = reader.read_cue_values
    def read(*args, **kwargs):
        result = original(*args, **kwargs)
        result["values"]["authorization"] = "SECRET_VALUE"
        return result
    reader.read_cue_values = read
    result = reader.get_control_cue_details(WS, FIRST, profile)
    assert "SECRET_VALUE" not in result.model_dump_json()
    assert result.basics.notes == "private"


def test_scan_bound_and_empty_collection():
    osc = control_fixture()
    result = QLabReader(osc).get_control_cues(WS, LIST, max_cues_scanned=1)
    assert result.truncated and not result.scan_complete
    osc.children[LIST] = []
    result = QLabReader(osc).get_control_cues(WS, LIST)
    assert result.ok and result.scan_complete and not result.cues


@pytest.mark.parametrize("kind,label", [("Load", "Load cue load time"), ("Target", "Target cue assigned number")])
def test_documented_osc_gaps_are_explicit(kind, label):
    result = QLabReader(control_fixture(kind)).get_control_cue_details(WS, FIRST)
    assert label in result.coverage.unavailable_via_osc
