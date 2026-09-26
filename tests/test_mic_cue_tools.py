"""Mic contracts reuse Audio traversal without requesting file-only properties."""
import asyncio
import json

import pytest
from fastmcp import Client
import qlab_mcp.server as server
from qlab_mcp.qlab import QLabReader
from test_audio_cue_tools import fixture as audio_fixture, AUDIO, SECOND
from test_cue_list_tools import WS, LIST, CART, OTHER


def fixture():
    osc = audio_fixture()
    for cue in osc.children[OTHER][:2]:
        cue["type"] = "Mic"
    for uid in (AUDIO, SECOND):
        osc.cell_values[uid].update(type="Mic", channels=2, channelOffset=0,
                                    audioInputPatchID=OTHER, audioInputPatchName="Input",
                                    audioInputPatchNumber=1)
    return osc


def test_inventory_scoped_and_paginated():
    osc = fixture()
    reader = QLabReader(osc)
    page = reader.get_mic_cues(WS.lower(), LIST.lower(), limit=1)
    assert page.ok and page.matched_count == 2 and page.next_offset == 1
    assert page.cues[0].type == "Mic" and page.cues[0].parent_id == OTHER
    assert not any(CART in addr or SECOND in addr for addr, _ in osc.calls)
    assert reader.get_mic_cues(WS, LIST, offset=1).cues[0].uniqueID == SECOND
    assert reader.get_mic_cues(WS, CART).error_code == "cue_list_type_mismatch"
    assert reader.get_mic_cues(WS, LIST, max_cues_scanned=1).truncated
    osc.children[LIST] = []
    assert reader.get_mic_cues(WS, LIST).cues == []


@pytest.mark.parametrize("profile", ["safe", "technical"])
def test_details_and_allowed_keys(profile):
    osc = fixture()
    result = QLabReader(osc).get_mic_cue_details(WS, AUDIO, profile, 0, 1)
    assert result.ok and result.identity.type == "Mic" and result.level.value == "-inf"
    assert result.audio.channels == 2 and result.audio.channelOffset == 0
    assert result.audio.audioInputPatchID == OTHER
    requested = {key for addr, args in osc.calls if addr.endswith("valuesForKeys") for key in json.loads(args[0])}
    assert not requested.intersection({"fileTarget", "audioTrackFormats", "sliceMarkers", "preservePitch", "rate"})
    assert not any("object" in key.lower() or "audiomap" in key.lower() or "/live" in key for key in requested)
    assert ("notes" in requested) == (profile == "technical")
    if profile == "technical":
        assert result.technical_payload["channels"] == 2


@pytest.mark.parametrize("kwargs", [{"input_channel": 1}, {"output_channel": 1},
    {"input_channel": True, "output_channel": 1}, {"input_channel": 1.0, "output_channel": 1},
    {"input_channel": "1", "output_channel": 1}, {"input_channel": -1, "output_channel": 1},
    {"input_channel": 25, "output_channel": 1}, {"input_channel": 1, "output_channel": 129}])
def test_invalid_selectors_before_io(kwargs):
    osc = fixture()
    assert QLabReader(osc).get_mic_cue_details(WS, AUDIO, **kwargs).error_code == "validation_failed"
    assert not osc.calls


def test_wrong_type_identity_and_partial_fields():
    osc = fixture()
    osc.cell_values[AUDIO]["type"] = "Audio"
    reader = QLabReader(osc)
    wrong = reader.get_mic_cue_details(WS, AUDIO)
    assert wrong.error_code == "mic_cue_type_mismatch" and "qlab_get_mic_cues" in wrong.suggested_action
    osc.cell_values[AUDIO]["type"] = "Mic"
    osc.cell_values[AUDIO]["channels"] = True
    partial = reader.get_mic_cue_details(WS, AUDIO)
    assert partial.partial and partial.audio.channels is None and partial.audio.channelOffset == 0
    osc.cell_values[AUDIO]["uniqueID"] = SECOND
    assert reader.get_mic_cue_details(WS, AUDIO).error_code == "mic_cue_identity_mismatch"


def test_fastmcp_contract(monkeypatch):
    monkeypatch.setattr(server, "_reader", lambda: QLabReader(fixture()))
    async def run():
        async with Client(server.mcp) as client:
            listing = await client.call_tool("qlab_get_mic_cues", {"workspace_id": WS, "cue_list_id": LIST})
            assert listing.structured_content["returned_count"] == 2
            detail = await client.call_tool("qlab_get_mic_cue_details", {"workspace_id": WS, "cue_id": AUDIO})
            assert detail.structured_content["audio"]["channels"] == 2
            with pytest.raises(Exception):
                await client.call_tool("qlab_get_mic_cues", {"workspace_id": WS, "cue_list_id": LIST, "limit": True})
    asyncio.run(run())
