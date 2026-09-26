"""Read-only Light/Group contracts and conditional traversal."""
import asyncio
import json

import pytest
from fastmcp import Client

from qlab_mcp.qlab import QLabReader
from qlab_mcp.server import mcp
from test_visual_cue_tools import VisualOsc, FIRST, SECOND
from test_cue_list_tools import root, WS, LIST, CART, OTHER
from test_cue_list_tools import Osc


class FamilyOsc(VisualOsc):
    def reply(self, address, args):
        if address.endswith("/children/shallow"):
            return Osc.reply(self, address, args)
        return super().reply(address, args)


def fixture(kind="Group", mode=3):
    osc = FamilyOsc()
    osc.children = {LIST: [root(OTHER, "Group")], OTHER: [root(FIRST, kind)],
                    FIRST: [root(SECOND, "Audio")]}
    osc.cell_values[OTHER] = root(OTHER, "Group")
    osc.cell_values[FIRST] = {
        **root(FIRST, kind), "parent": OTHER, "mode": mode,
        "lightCommandText": "front = 50\nback = 25", "alwaysCollate": True, "subcontroller": False,
        "isChildFlagged": False, "isChildAuditioning": False,
        "playlist/currentCue": "1", "playlist/currentCueID": SECOND,
        "playlist/doCrossfade": True, "playlist/doLoop": False, "playlist/doShuffle": True,
        "playlist/crossfade/duration": 2.5, "notes": "private",
    }
    return osc


@pytest.mark.parametrize("kind", ["Light", "Group"])
def test_inventory_scope_paging_empty_and_cart(kind):
    osc = fixture(kind)
    read = getattr(QLabReader(osc), f"get_{kind.lower()}_cues")
    result = read(WS, LIST, limit=1)
    assert result.ok and result.cues and result.cues[0].type == kind
    assert result.cues[0].cue_list_id == LIST
    assert result.has_more == (kind == "Group")
    assert read(WS, CART).error_code == "cue_list_type_mismatch"
    osc.children[LIST] = []
    assert read(WS, LIST).cues == []


@pytest.mark.parametrize("text", ["", "front = 50\nback = 25"])
@pytest.mark.parametrize("profile", ["safe", "technical"])
def test_light_text_and_no_patch_reads(text, profile):
    osc = fixture("Light")
    osc.cell_values[FIRST]["lightCommandText"] = text
    result = QLabReader(osc).get_light_cue_details(WS, FIRST, profile)
    assert result.ok and result.light.lightCommandText == text
    assert result.light.alwaysCollate is True and result.light.subcontroller is False
    assert result.basics.notes == ("private" if profile == "technical" else None)
    assert not any("settings" in address or "children" in address for address, _ in osc.calls)


@pytest.mark.parametrize("mode", [1, 2, 3, 4, 6])
def test_group_modes_and_conditional_playlist(mode):
    osc = fixture(mode=mode)
    result = QLabReader(osc).get_group_cue_details(WS, FIRST)
    assert result.ok and result.group.mode == mode and result.mode_label
    assert result.contents.children[0].uniqueID == SECOND
    assert bool(result.playlist) == (mode == 6)
    assert any("/playlist/" in address for address, _ in osc.calls) == (mode == 6)
    if mode == 6:
        assert result.playlist.crossfadeDuration == 2.5
        assert result.playlist.currentCueID == SECOND


def test_depth_zero_and_empty_group():
    osc = fixture()
    result = QLabReader(osc).get_group_cue_details(WS, FIRST, max_depth=0)
    assert result.ok and not result.contents.children
    assert not any("children" in address for address, _ in osc.calls)
    osc.children[FIRST] = []
    assert QLabReader(osc).get_group_cue_details(WS, FIRST).contents.children == []


@pytest.mark.parametrize("value", [-1, 6, True, 1.5, "2"])
def test_invalid_depth_before_io(value):
    osc = fixture()
    assert QLabReader(osc).get_group_cue_details(WS, FIRST, max_depth=value).error_code == "validation_failed"
    assert osc.calls == []


@pytest.mark.parametrize("kind", ["Cue List", "Cue Cart", "Audio"])
def test_wrong_type(kind):
    assert QLabReader(fixture(kind)).get_group_cue_details(WS, FIRST).error_code == "group_cue_type_mismatch"


def test_malformed_light_and_playlist_are_partial():
    osc = fixture("Light")
    osc.cell_values[FIRST]["alwaysCollate"] = "yes"
    result = QLabReader(osc).get_light_cue_details(WS, FIRST)
    assert result.partial and "alwaysCollate" in result.errors
    osc = fixture(mode=6)
    osc.cell_values[FIRST]["playlist/doLoop"] = "yes"
    result = QLabReader(osc).get_group_cue_details(WS, FIRST)
    assert result.partial and "playlist/doLoop" in result.errors


def test_mode_change_invalidates_detail():
    osc = fixture(mode=6)
    original = osc.reply
    def reply(address, args):
        if address.endswith("children/shallow"):
            osc.cell_values[FIRST]["mode"] = 3
        return original(address, args)
    osc.reply = reply
    result = QLabReader(osc).get_group_cue_details(WS, FIRST)
    assert result.error_code == "group_cue_identity_mismatch" and result.contents is None


def test_new_tools_public_schemas():
    async def run():
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
        assert len(tools) == 48
        for family in ("light", "group"):
            for suffix in ("cues", "cue_details"):
                tool = tools[f"qlab_get_{family}_{suffix}"]
                assert tool.annotations.readOnlyHint
                assert "input_channel" not in tool.inputSchema["properties"]
                assert tool.outputSchema
    asyncio.run(run())


def test_children_truncated_and_secondary_failure():
    osc = fixture()
    osc.children[FIRST] = [root(SECOND, "Audio"), root(CART, "Memo")]
    result = QLabReader(osc).get_group_cue_details(WS, FIRST, max_cues=1)
    assert result.contents.truncated and result.contents.returned_count == 1
    osc.children[FIRST] = [None]
    result = QLabReader(osc).get_group_cue_details(WS, FIRST)
    assert result.partial and result.group.mode == 3 and result.contents.truncated


def test_group_budget_after_contents(monkeypatch):
    import qlab_mcp.cues.light_group as module
    monkeypatch.setattr(module, "MAX_SENSITIVE_CUE_RESPONSE_BYTES", 100)
    result = QLabReader(fixture()).get_group_cue_details(WS, FIRST)
    assert result.error_code == "cue_payload_too_large" and result.contents is None


@pytest.mark.parametrize("kind", ["Light", "Group"])
def test_identity_mismatch_and_invalid_payload(kind):
    osc = fixture(kind)
    reader = QLabReader(osc)
    read = getattr(reader, f"get_{kind.lower()}_cue_details")
    osc.cell_values[FIRST]["uniqueID"] = SECOND
    assert read(WS, FIRST).error_code == f"{kind.lower()}_cue_identity_mismatch"
    osc.cell_values[FIRST] = []
    assert read(WS, FIRST).error_code == f"{kind.lower()}_cue_payload_invalid"


def test_playlist_timeout_keeps_group_and_children():
    osc = fixture(mode=6)
    reader = QLabReader(osc)
    original = reader.read_cue_property
    def read(ws, cue, key):
        if key == "playlist/doLoop":
            raise TimeoutError("Timed out")
        return original(ws, cue, key)
    reader.read_cue_property = read
    result = reader.get_group_cue_details(WS, FIRST)
    assert result.partial and result.playlist.doCrossfade is True
    assert result.contents.returned_count == 1
    assert "playlist/doLoop" in result.errors


@pytest.mark.parametrize("family", ["light", "group"])
def test_fastmcp_calls(monkeypatch, family):
    import qlab_mcp.server as server
    reader = QLabReader(fixture(family.title()))
    monkeypatch.setattr(server, "_run_tool", lambda fn, **kwargs: fn(reader))
    async def run():
        async with Client(mcp) as client:
            inventory = await client.call_tool(f"qlab_get_{family}_cues", {"workspace_id": WS, "cue_list_id": LIST})
            result = await client.call_tool(f"qlab_get_{family}_cue_details", {"workspace_id": WS, "cue_id": FIRST})
            assert inventory.structured_content["ok"] and result.structured_content["ok"]
            assert result.structured_content["identity"]["type"] == family.title()
    asyncio.run(run())
