"""Contract and OSC request regressions for specialized Cue List reads."""

import asyncio
import json
from types import SimpleNamespace

import pytest
from fastmcp import Client

import qlab_mcp.server as server
from qlab_mcp.errors import OscTimeoutError
from qlab_mcp.qlab import QLabReader


WS = "AAAAAAAA-AAAA-AAAA-AAAA-AAAAAAAAAAAA"
LIST = "BBBBBBBB-BBBB-BBBB-BBBB-BBBBBBBBBBBB"
CART = "CCCCCCCC-CCCC-CCCC-CCCC-CCCCCCCCCCCC"
OTHER = "DDDDDDDD-DDDD-DDDD-DDDD-DDDDDDDDDDDD"


def root(uid=LIST, kind="Cue List", name="Main"):
    return {"uniqueID": uid, "type": kind, "name": name, "number": "", "armed": True, "flagged": False}


class Osc:
    def __init__(self):
        self.config = SimpleNamespace(cache_ttl=0, timeout=0.1)
        self.calls = []
        self.roots = [root(), root(CART, "Cue Cart")]
        self.current = LIST
        self.values = {
            **root(), "playhead": "1", "playheadID": "cue-1",
            "playbackPosition": "1", "playbackPositionID": "cue-1",
            "timecodeSyncMode": 0, "timecodeSMPTEFormat": 2,
            "timecodeStartBehavior": 3, "timecodeStopBehavior": 1,
            "timecodeFreewheelTime": 0.25, "timecodeLookbackTime": 4,
            "currentTimecode": 100, "currentTimecode/text": "00:00:04:00",
        }
        self.children = {LIST: [root("cue-1", "Memo"), root("group-1", "Group")],
                         "group-1": [root("cue-2", "Audio")]}
        self.failures = {}
        self.tcp_calls = []

    def request(self, address, *args, **kwargs):
        self.calls.append((address, args))
        if address in self.failures:
            raise self.failures[address]
        return self.reply(address, args)

    def request_tcp(self, address, *args, **kwargs):
        self.tcp_calls.append(address)
        return self.reply(address, args)

    def reply(self, address, args):
        if address == "/workspaces":
            value = [{"uniqueID": WS, "displayName": "Show.qlab5"}]
        elif address == f"/workspace/{WS}/cueLists/shallow":
            value = self.roots
        elif address == f"/workspace/{WS}/currentCueListID":
            value = self.current
        elif address.endswith("/valuesForKeys"):
            keys = json.loads(args[0])
            value = ({k: v for k, v in self.values.items() if k in keys}
                     if isinstance(self.values, dict) else self.values)
        elif address.endswith("/children/shallow"):
            value = self.children[address.split("/")[-3]]
        else:
            raise AssertionError(f"Unexpected OSC read: {address}")
        return SimpleNamespace(data=value, status="ok")


@pytest.fixture
def osc():
    return Osc()


def details(osc, **kwargs):
    return QLabReader(osc).get_cue_list_details(WS.lower(), LIST.lower(), **kwargs)


def test_inventory_is_compact_and_handles_current_cart(osc):
    osc.current = CART
    result = QLabReader(osc).get_cue_list_inventory(WS.lower())
    assert result.ok and result.workspace_id == WS
    assert result.cue_list_count == 1 and result.excluded_cue_cart_count == 1
    assert result.current_cue_list_id is None and result.current_container_id == CART
    assert result.cue_lists[0].is_current is False
    assert result.cue_lists[0].root_position == 0
    assert result.cue_lists[0].isWarning is None
    assert [a for a, _ in osc.calls] == ["/workspaces", f"/workspace/{WS}/cueLists/shallow", f"/workspace/{WS}/currentCueListID"]


@pytest.mark.parametrize("count", [0, 1, 2])
def test_inventory_empty_and_duplicate_names(osc, count):
    osc.roots = [root(), root(OTHER)][:count]
    osc.current = LIST if count else "none"
    result = QLabReader(osc).get_cue_list_inventory(WS)
    assert result.status == "ok" and result.cue_list_count == count
    if count:
        assert result.cue_lists[0].is_current is True


@pytest.mark.parametrize("payload", [None, 7, {}, [None], [{"name": "No ID"}], [root(), root()]])
def test_invalid_inventory_is_not_empty_success(osc, payload):
    osc.roots = payload
    for result in (QLabReader(osc).get_cue_list_inventory(WS), details(osc)):
        assert not result.ok and not result.partial
        assert result.error_code == "cue_list_payload_invalid"


def test_details_are_typed_ordered_and_scoped(osc):
    osc.roots.append(root(OTHER))
    result = details(osc)
    assert result.status == "ok" and result.cue_list_id == LIST
    assert result.identity.uniqueID == LIST and result.state.armed is True
    assert result.playhead.uniqueID == "cue-1" and result.playhead.present is True
    assert result.incoming_timecode.sync_mode.label == "MTC"
    assert result.incoming_timecode.smpte_format.value == 2
    assert result.contents.direct_child_count == 2 and result.contents.returned_count == 3
    assert [c.uniqueID for c in result.contents.children] == ["cue-1", "group-1"]
    assert result.contents.children[1].children[0].uniqueID == "cue-2"
    assert not result.contents.truncated
    assert result.technical_payload is None
    assert "sync_enabled" in result.coverage.unavailable_via_osc
    assert not any(CART in a or OTHER in a or "/live" in a for a, _ in osc.calls)
    keys = json.loads(next(args[0] for a, args in osc.calls if a.endswith("valuesForKeys")))
    assert not any("cart" in k.lower() or "playlist" in k.lower() for k in keys)


def test_unknown_timecode_does_not_imply_disabled(osc):
    osc.values["currentTimecode"] = None
    osc.values["currentTimecode/text"] = None
    osc.values["playhead"] = osc.values["playheadID"] = "none"
    result = details(osc)
    assert result.ok and result.playhead.present is False and result.playhead.uniqueID is None
    assert result.incoming_timecode.current is None
    assert "currentTimecode" in result.coverage.unavailable_fields
    assert "sync_enabled" not in result.incoming_timecode.model_dump()


@pytest.mark.parametrize("depth,limit,count", [(0, 100, 0), (1, 100, 2), (2, 1, 1)])
def test_contents_limits_are_explicit(osc, depth, limit, count):
    result = details(osc, max_depth=depth, max_cues=limit)
    assert result.contents.returned_count == count and result.contents.truncated
    if depth == 0:
        assert result.contents.direct_child_count is None
        assert not any(a.endswith("children/shallow") for a, _ in osc.calls)


@pytest.mark.parametrize("key,value", [("max_depth", -1), ("max_depth", 6), ("max_depth", True),
                                     ("max_depth", 1.5), ("max_depth", "2"), ("max_cues", 0),
                                     ("max_cues", 5001), ("max_cues", False), ("max_cues", 2.0), ("max_cues", "2")])
def test_invalid_limits_fail_before_io(osc, key, value):
    result = details(osc, **{key: value})
    assert result.error_code == "validation_failed" and osc.calls == []


@pytest.mark.parametrize("target,code", [("Main", "validation_failed"), ("1", "validation_failed"),
                                      (OTHER, "cue_list_not_found"), (CART, "cue_list_type_mismatch")])
def test_exact_selection(osc, target, code):
    result = QLabReader(osc).get_cue_list_details(WS, target)
    assert result.error_code == code and not result.ok
    assert not any(a.endswith("valuesForKeys") or "children" in a for a, _ in osc.calls)


@pytest.mark.parametrize("payload,code", [(None, "cue_list_payload_invalid"), ([], "cue_list_payload_invalid"),
                                      ({}, "cue_list_payload_invalid"), (root(OTHER), "cue_list_identity_mismatch"),
                                      (root(LIST, "Group"), "cue_list_type_mismatch")])
def test_principal_payload_failure(osc, payload, code):
    osc.values = payload
    result = details(osc)
    assert result.error_code == code and result.identity is None
    assert not any("children" in a for a, _ in osc.calls)


@pytest.mark.parametrize("key,value", [("armed", "false"), ("timecodeFreewheelTime", float("nan")),
                                     ("timecodeSyncMode", True), ("timecodeSyncMode", 99),
                                     ("timecodeLookbackTime", -1)])
def test_invalid_secondary_fields_preserve_valid_details(osc, key, value):
    osc.values[key] = value
    result = details(osc)
    assert result.ok and result.status == "partial" and key in result.errors
    assert result.identity.uniqueID == LIST


@pytest.mark.parametrize("children", [None, 1, [None], [{"name": "Missing identity"}]])
def test_invalid_children_are_partial(osc, children):
    osc.children[LIST] = children
    result = details(osc)
    assert result.ok and result.partial and result.errors
    assert result.contents.truncated


def test_duplicate_child_does_not_claim_complete_tree(osc):
    osc.children[LIST] = [root("cue-1", "Memo"), root("cue-1", "Memo")]
    result = details(osc)
    assert result.partial and result.contents.truncated
    assert result.contents.returned_count == 1
    assert "invalid_payload" in result.contents.truncation_reasons


def test_empty_list_and_empty_group_are_valid(osc):
    osc.children[LIST] = []
    result = details(osc)
    assert result.status == "ok" and result.contents.direct_child_count == 0
    assert not result.contents.truncated
    osc.children[LIST] = [root("group-1", "Group")]
    osc.children["group-1"] = []
    result = details(osc)
    assert result.contents.children[0].children_complete is True
    assert not result.contents.truncated


def test_workspace_error_recommends_connection_check(osc):
    result = QLabReader(osc).get_cue_list_details(OTHER, LIST)
    assert result.error_code == "workspace_not_found"
    assert "qlab_check_connection" in result.suggested_action
    assert [a for a, _ in osc.calls] == ["/workspaces"]


def test_timeout_fallback_only_once_and_secondary_failure(osc):
    address = f"/workspace/{WS}/cue/group-1/children/shallow"
    osc.failures[address] = OscTimeoutError("Timed out")
    assert details(osc).ok
    assert osc.tcp_calls == [address]
    osc.failures[address] = ValueError("Malformed response")
    osc.tcp_calls.clear()
    result = details(osc)
    assert result.partial and result.contents.children[0].uniqueID == "cue-1"
    assert osc.tcp_calls == []


def test_technical_payload_remains_normalized_and_allowlisted(osc):
    osc.values["password"] = "secret"
    osc.values["playlist/currentCue"] = "unrelated"
    result = details(osc, profile="technical")
    assert result.identity.uniqueID == LIST and result.incoming_timecode.sync_mode.label == "MTC"
    assert result.technical_payload["timecodeSyncMode"] == 0
    assert "secret" not in result.model_dump_json() and "playlist" not in result.model_dump_json()


def test_generic_details_redirects_cue_lists_to_specialized_tool(osc):
    reader = QLabReader(osc)
    single = reader.get_cue_details(WS, LIST, "basic_safe")
    batch = reader.get_cue_details(WS, [LIST], "basic_safe")
    for item in (single, batch["results"][0]):
        assert item["ok"] is False
        assert item["error_code"] == "cue_list_specialized_tool_required"
        assert "qlab_get_cue_list_details" in item["suggested_action"]


def test_generic_details_keeps_cue_cart_support(osc):
    reader = QLabReader(osc)
    osc.values = {**root(CART, "Cue Cart"), "playhead": "none", "playheadID": "none"}
    result = reader.get_cue_details(WS, CART, "basic_safe")
    assert result["ok"] and result["properties"]["uniqueID"] == CART


def test_fastmcp_roundtrip_and_validation(monkeypatch, osc):
    monkeypatch.setattr(server, "_reader", lambda: QLabReader(osc))

    async def run():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 22
            detail_schema = tools["qlab_get_cue_list_details"].inputSchema
            assert detail_schema["properties"]["cue_list_id"]["format"] == "uuid"
            for key, minimum, maximum in [("max_depth", 0, 5), ("max_cues", 1, 5000)]:
                prop = detail_schema["properties"][key]
                assert prop["minimum"] == minimum and prop["maximum"] == maximum
            inventory = await client.call_tool("qlab_get_cue_lists", {"workspace_id": WS})
            assert inventory.structured_content["cue_list_count"] == 1
            result = await client.call_tool("qlab_get_cue_list_details", {"workspace_id": WS, "cue_list_id": LIST})
            assert result.structured_content["identity"]["uniqueID"] == LIST
            redirect = await client.call_tool(
                "qlab_get_cue_details",
                {"workspace_id": WS, "cue_ref": LIST, "profile": "auto"},
            )
            redirect_payload = redirect.structured_content["result"]
            assert redirect_payload["error_code"] == "cue_list_specialized_tool_required"
            assert "qlab_get_cue_list_details" in redirect_payload["suggested_action"]
            for key, value in [("max_depth", True), ("max_depth", "2"), ("max_depth", 1.0),
                               ("max_depth", -1), ("max_depth", 6), ("max_cues", 0),
                               ("cue_list_id", "Main")]:
                osc.calls.clear()
                with pytest.raises(Exception):
                    await client.call_tool("qlab_get_cue_list_details", {"workspace_id": WS, "cue_list_id": LIST, key: value})
                assert osc.calls == []
    asyncio.run(run())
