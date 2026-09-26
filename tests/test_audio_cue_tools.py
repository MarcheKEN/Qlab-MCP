"""Regression checks for scoped Audio reads."""
import asyncio
import json

import pytest
from fastmcp import Client
import qlab_mcp.server as server
from qlab_mcp.qlab import QLabReader
from test_cue_list_tools import Osc, root, WS, LIST, CART, OTHER

AUDIO = "EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"
SECOND = "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"


def fixture():
    osc = Osc()
    osc.children[LIST] = [root(OTHER, "Group")]
    osc.children[OTHER] = [root(AUDIO, "Audio"), root(SECOND, "Audio"), root("video", "Video")]
    for uid in (AUDIO, SECOND):
        osc.cell_values[uid] = {
            **root(uid, "Audio"), "duration": 12.5, "rate": 1.0, "hasFileTargets": True,
            "fileTarget": "/private/show/audio.wav", "notes": "Private notes",
            "numChannelsIn": 2, "levels": [[0.0, "-inf"], [-3.0, -6.0]],
            "sliderLevels": [0.0, "-inf"], "muteChannels": [1], "soloChannels": [],
            "sliceMarkers": [{"time": 2.0, "playCount": 1}],
            "audioOutputPatchID": OTHER,
            "parent": OTHER, "preservePitch": 0,
            "audioTrackFormats": {"1": {"sampleRate": 48000, "apiKey": "hide-me"}},
        }
    return osc


def test_scoped_inventory_pages_only_read_returned_audio():
    osc = fixture()
    result = QLabReader(osc).get_audio_cues(WS.lower(), LIST.lower(), limit=1)
    assert result.ok and result.scan_complete
    assert result.matched_count == 2 and result.next_offset == 1
    assert result.cues[0].uniqueID == AUDIO
    assert result.cues[0].cue_list_id == LIST and result.cues[0].parent_id == OTHER
    assert not any(CART in addr or SECOND in addr or "video/" in addr for addr, _ in osc.calls)
    page = QLabReader(osc).get_audio_cues(WS, LIST, offset=1)
    assert page.cues[0].uniqueID == SECOND and not page.has_more


def test_empty_partial_and_wrong_container():
    osc = fixture()
    reader = QLabReader(osc)
    assert reader.get_audio_cues(WS, CART).error_code == "cue_list_type_mismatch"
    assert reader.get_audio_cues(WS, AUDIO).error_code == "cue_list_not_found"
    partial = reader.get_audio_cues(WS, LIST, max_cues_scanned=1)
    assert partial.truncated and not partial.scan_complete
    osc.children[LIST] = []
    empty = reader.get_audio_cues(WS, LIST)
    assert empty.ok and empty.scan_complete and empty.cues == []


@pytest.mark.parametrize("kwargs", [
    {"limit": True}, {"limit": 0}, {"offset": -1}, {"offset": "1"},
    {"max_cues_scanned": 5001}, {"limit": 1.0},
])
def test_invalid_inventory_limits_before_io(kwargs):
    osc = fixture()
    assert QLabReader(osc).get_audio_cues(WS, LIST, **kwargs).error_code == "validation_failed"
    assert osc.calls == []


def test_details_typed_matrix_and_exclusions():
    osc = fixture()
    result = QLabReader(osc).get_audio_cue_details(WS, AUDIO, input_channel=0, output_channel=1)
    assert result.ok and result.level.value == "-inf"
    assert result.audio.sliceMarkers[0].time == 2.0
    assert result.audio.muteChannels == [1]
    assert result.timing.preservePitch is False
    assert result.identity.parent_id == OTHER
    assert result.basics.fileTarget is None and result.basics.notes is None
    requested = [key for addr, args in osc.calls if addr.endswith("valuesForKeys") for key in json.loads(args[0])]
    assert not any("object" in key.lower() or "audiomap" in key.lower() or "/live" in key for key in requested)
    assert "fileTarget" not in requested and "notes" not in requested


def test_technical_profile_and_bad_secondary_values():
    osc = fixture()
    result = QLabReader(osc).get_audio_cue_details(WS, AUDIO, profile="technical")
    assert result.ok and result.basics.fileTarget == "/private/show/audio.wav"
    assert result.technical_payload["notes"] == "Private notes"
    assert result.technical_payload["audioTrackFormats"]["1"]["apiKey"] == "[redacted]"
    assert "hide-me" not in result.model_dump_json()
    osc.cell_values[AUDIO]["rate"] = True
    osc.cell_values[AUDIO]["levels"] = [[float("nan")]]
    partial = QLabReader(osc).get_audio_cue_details(WS, AUDIO)
    assert partial.partial and partial.timing.rate is None and partial.audio.levels is None


@pytest.mark.parametrize("kwargs", [
    {"input_channel": 0}, {"output_channel": 1},
    {"input_channel": True, "output_channel": 1},
    {"input_channel": 25, "output_channel": 0},
    {"input_channel": 0, "output_channel": 129},
    {"input_channel": "0", "output_channel": 1},
])
def test_invalid_channels_before_io(kwargs):
    osc = fixture()
    assert QLabReader(osc).get_audio_cue_details(WS, AUDIO, **kwargs).error_code == "validation_failed"
    assert osc.calls == []


def test_wrong_type_identity_and_invalid_payload():
    osc = fixture()
    osc.cell_values[AUDIO]["type"] = "Video"
    assert QLabReader(osc).get_audio_cue_details(WS, AUDIO).error_code == "audio_cue_type_mismatch"
    osc.cell_values[AUDIO]["uniqueID"] = SECOND
    assert QLabReader(osc).get_audio_cue_details(WS, AUDIO).error_code == "audio_cue_identity_mismatch"
    osc.cell_values[AUDIO] = []
    assert QLabReader(osc).get_audio_cue_details(WS, AUDIO).error_code == "audio_cue_payload_invalid"


def test_fastmcp_roundtrip_and_strict_schema(monkeypatch):
    monkeypatch.setattr(server, "_reader", lambda: QLabReader(fixture()))
    async def run():
        async with Client(server.mcp) as client:
            listing = await client.call_tool("qlab_get_audio_cues", {"workspace_id": WS, "cue_list_id": LIST})
            assert listing.structured_content["returned_count"] == 2
            detail = await client.call_tool("qlab_get_audio_cue_details", {"workspace_id": WS, "cue_id": AUDIO})
            assert detail.structured_content["audio"]["levels"][0][1] == "-inf"
            with pytest.raises(Exception):
                await client.call_tool("qlab_get_audio_cues", {"workspace_id": WS, "cue_list_id": LIST, "limit": True})
    asyncio.run(run())


def test_secondary_timeout_is_partial_without_retry(monkeypatch):
    reader = QLabReader(fixture())
    read = reader.read_cue_values
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(args)
        if len(calls) == 2:
            raise TimeoutError("Timed out")
        return read(*args, **kwargs)
    monkeypatch.setattr(reader, "read_cue_values", fail_second)
    result = reader.get_audio_cue_details(WS, AUDIO)
    assert result.partial and result.identity.uniqueID == AUDIO
    assert "valuesForKeys:audio" in result.errors and len(calls) == 2


def test_identity_change_during_detail_is_error(monkeypatch):
    reader = QLabReader(fixture())
    read = reader.read_cue_values
    def change_identity(*args, **kwargs):
        result = read(*args, **kwargs)
        if "levels" in args[2]:
            result["values"]["uniqueID"] = SECOND
        return result
    monkeypatch.setattr(reader, "read_cue_values", change_identity)
    result = reader.get_audio_cue_details(WS, AUDIO)
    assert not result.ok and result.identity is None
    assert result.error_code == "audio_cue_identity_mismatch"


def test_invalid_metadata_and_payload_budget(monkeypatch):
    osc = fixture()
    osc.cell_values[AUDIO]["audioTrackFormats"] = ["invalid"]
    result = QLabReader(osc).get_audio_cue_details(WS, AUDIO, profile="technical")
    assert result.partial and "audioTrackFormats" in result.errors
    monkeypatch.setattr("qlab_mcp.cues.audio.MAX_SENSITIVE_CUE_RESPONSE_BYTES", 1)
    result = QLabReader(osc).get_audio_cue_details(WS, AUDIO, profile="technical")
    assert not result.ok and result.error_code == "cue_payload_too_large"
    assert result.technical_payload is None and result.basics is None
