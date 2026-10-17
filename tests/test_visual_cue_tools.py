"""Scoped visual-family contracts and secondary OSC property reads."""

import asyncio
import json

import pytest
from fastmcp import Client

import qlab_mcp.server as server
from qlab_mcp.qlab import QLabReader
from test_cue_list_tools import Osc, root, WS, LIST, CART, OTHER

FIRST = "EEEEEEEE-EEEE-EEEE-EEEE-EEEEEEEEEEEE"
SECOND = "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF"
KINDS = ("video", "camera", "text")


class VisualOsc(Osc):
    def reply(self, address, args):
        prefix = f"/workspace/{WS}/cue_id/"
        # QLab's common addressing helper uses /cue_id/ for UUID references.
        for cue_id in (FIRST, SECOND):
            for marker in (f"/cue_id/{cue_id}/", f"/cue/{cue_id}/"):
                if marker in address and not address.endswith("valuesForKeys"):
                    key = address.split(marker, 1)[1]
                    value = self.cell_values[cue_id].get(key)
                    from types import SimpleNamespace
                    return SimpleNamespace(data=value, status="ok")
        return super().reply(address, args)


def fixture(kind):
    osc = VisualOsc()
    osc.children[LIST] = [root(OTHER, "Group")]
    osc.children[OTHER] = [root(FIRST, kind.title()), root(SECOND, kind.title()), root("unrelated", "Audio")]
    for uid in (FIRST, SECOND):
        osc.cell_values[uid] = {
            **root(uid, kind.title()), "parent": OTHER,
            "preWait": 0.0, "duration": 3.5, "postWait": 0.0, "continueMode": 0,
            "stageID": OTHER, "stageName": "Stage", "stageNumber": 1,
            "cueSize": {"width": 1920, "height": 1080},
            "anchor": {"x": 0, "y": 0}, "translation": {"x": 10, "y": -20},
            "scale": {"x": 1.5, "y": 1.5}, "quaternion": [0, 0, 0, 1],
            "cropTop": 1, "cropBottom": 2, "cropLeft": 3, "cropRight": 4,
            "opacity": 0.75, "layer": 500, "blendMode": "Normal",
            "fillStage": False, "fillStyle": 0, "preserveAspectRatio": True, "smooth": True,
            "videoEffects": [{"name": "ColorControls", "enabled": True, "parameters": {"inputContrast": 1, "apiKey": "secret-value"}}],
            "numChannelsIn": 0, "levels": [[-3.0, "-inf"]], "sliderLevels": [-3.0, "-inf"],
            "muteChannels": [], "soloChannels": [], "audioOutputPatchID": "",
            "channels": 1, "channelOffset": 0, "audioInputPatchID": "",
            "videoInputPatchID": "", "videoInputPatchName": "none", "videoInputPatchNumber": 0,
            "rate": 1.0, "preservePitch": 0, "sliceMarkers": [], "clockType": "video", "holdLastFrame": True,
            "fileTarget": "/private/video.mov", "notes": "Private note", "hasFileTargets": True,
            "audioTrackFormats": {},
            "text": "Hello world", "fixedWidth": 0,
            "text/outputSize": {"width": 200, "height": 100},
            "text/format": [
                {"range": [0, 5], "fontName": "Helvetica", "fontSize": 24, "color": [1, 0, 0, 1]},
                {"range": [5, 6], "fontName": "Courier", "fontSize": 36, "color": [0, 1, 0, 1]},
            ],
            "text/format/alignment": "center",
            "text/format/fontFamilyAndStyle": {"fontFamily": "Helvetica", "fontStyle": "Bold"},
            "text/format/shadowOffset": {"width": 1, "height": 2},
        }
    return osc


def detail(reader, kind, **kwargs):
    return getattr(reader, f"get_{kind}_cue_details")(WS, FIRST, **kwargs)


def test_unavailable_slices_do_not_advertise_enabled_edits():
    osc = fixture('video')
    osc.cell_values[FIRST].pop('sliceMarkers')
    result = detail(QLabReader(osc), 'video')
    assert result.ok and result.audio.sliceMarkers is None
    for key in ('addSliceMarker', 'deleteSliceMarker', 'deleteSliceMarkers', 'sliceMarker/time',
                'sliceMarker/playCount', 'lastSlicePlayCount'):
        assert key in result.edit_capabilities['blocked_properties']
        assert key not in result.edit_capabilities['allowed_properties']


@pytest.mark.parametrize("kind", KINDS)
def test_scoped_paged_inventory_and_empty(kind):
    osc = fixture(kind)
    read = getattr(QLabReader(osc), f"get_{kind}_cues")
    first = read(WS.lower(), LIST.lower(), limit=1)
    assert first.ok and first.scan_complete and first.matched_count == 2 and first.next_offset == 1
    assert first.cues[0].uniqueID == FIRST and first.cues[0].parent_id == OTHER
    assert all(CART not in addr and SECOND not in addr and "unrelated" not in addr for addr, _ in osc.calls)
    assert read(WS, LIST, offset=1).cues[0].uniqueID == SECOND
    assert read(WS, CART).error_code == "cue_list_type_mismatch"
    assert read(WS, LIST, max_cues_scanned=1).truncated
    osc.children[LIST] = []
    result = read(WS, LIST)
    assert result.ok and result.cues == [] and result.scan_complete


@pytest.mark.parametrize("kind", KINDS)
@pytest.mark.parametrize("limits", [{"limit": True}, {"limit": 0}, {"offset": -1}, {"max_cues_scanned": 5001}])
def test_inventory_limits_before_io(kind, limits):
    osc = fixture(kind)
    assert getattr(QLabReader(osc), f"get_{kind}_cues")(WS, LIST, **limits).error_code == "validation_failed"
    assert not osc.calls


@pytest.mark.parametrize("kind", KINDS)
def test_typed_geometry_and_family_exclusions(kind):
    osc = fixture(kind)
    result = detail(QLabReader(osc), kind)
    assert result.ok and result.identity.type == kind.title()
    assert result.video.translation.x == 10 and result.video.quaternion == [0, 0, 0, 1]
    assert result.video.videoEffects[0].name == "ColorControls"
    keys = {key for addr, args in osc.calls if addr.endswith("valuesForKeys") for key in json.loads(args[0])}
    assert not keys.intersection({"audioMap", "objects", "fileTarget", "notes"})
    assert not any("/live" in addr or "/settings/" in addr or "/videoEffectIndex/" in addr for addr, _ in osc.calls)
    if kind != "video":
        assert not keys.intersection({"rate", "preservePitch", "sliceMarkers", "startTime", "audioTrackFormats", "hasFileTargets"})
    if kind == "camera":
        assert result.video.videoInputPatchID == "" and result.audio.channels == 1
    elif kind == "text":
        assert not keys.intersection({"levels", "muteChannels", "audioOutputPatchID", "channels"})
        assert result.text.text == "Hello world" and len(result.text.fragments) == 2
        assert result.text.fragments[1].fontName == "Courier"
        assert result.text.outputSize.width == 200
    else:
        assert result.audio.numChannelsIn == 0 and result.timing.holdLastFrame is True


@pytest.mark.parametrize('kind', KINDS)
def test_selected_fx_enabled_updates_summary_and_returns_metadata(kind):
    osc = fixture(kind)
    osc.cell_values[FIRST].update({
        'videoEffectIndex/0/enabled': False,
        'videoEffectIndex/0/parameter/inputContrast': 1,
    })
    result = detail(QLabReader(osc), kind, video_effects=[{
        'effect_type': 'ColorControls', 'index': 0, 'key': 'inputContrast'}])
    assert result.ok and not result.partial
    assert result.video.videoEffects[0].enabled is False
    assert result.selected_video_effects[0]['enabled'] is False
    assert result.selected_video_effects[0]['parameter_metadata']['inputContrast']['kind'] == 'number'


@pytest.mark.parametrize('kind', KINDS)
def test_selected_fx_can_discover_type_from_index(kind):
    osc = fixture(kind)
    osc.cell_values[FIRST].update({
        'videoEffectIndex/0/enabled': True,
        'videoEffectIndex/0/parameter/inputContrast': 1,
    })
    result = detail(QLabReader(osc), kind, video_effects=[{'index': 0, 'key': 'inputContrast'}])
    assert result.ok and not result.partial
    selected = result.selected_video_effects[0]
    assert selected['type'] == 'ColorControls'
    assert selected['parameters'] == {'inputContrast': 1}
    assert result.edit_capabilities['video_fx']['allowed_operations'] == [
        'videoEffectIndex/enabled', 'videoEffectIndex/parameter', 'videoEffectIndex/parameters'
    ]


def test_video_fx_read_selector_requires_index_but_not_effect_type():
    async def get_tool():
        async with Client(server.mcp) as client:
            return next(tool for tool in await client.list_tools() if tool.name == 'qlab_get_video_cue_details')

    schema = asyncio.run(get_tool()).inputSchema['properties']['video_effects']['anyOf'][0]['items']
    assert schema['required'] == ['index']
    assert 'effect_type' in schema['properties']


@pytest.mark.parametrize('kind', KINDS)
def test_selected_fx_missing_enabled_is_partial(kind):
    osc = fixture(kind)
    osc.cell_values[FIRST]['videoEffectIndex/0/parameter/inputContrast'] = 1
    result = detail(QLabReader(osc), kind, video_effects=[{
        'effect_type': 'ColorControls', 'index': 0, 'key': 'inputContrast'}])
    assert result.partial and result.status == 'partial'
    assert 'videoEffectSelectors' in result.errors
    assert 'videoEffectIndex/selected' in result.coverage.failed_routes
    assert result.selected_video_effects == []


@pytest.mark.parametrize("kind", KINDS)
def test_technical_redaction_and_normalized_sections(kind):
    result = detail(QLabReader(fixture(kind)), kind, profile="technical")
    assert result.ok and result.basics.notes == "Private note"
    assert result.video.scale.x == 1.5
    assert "secret-value" not in result.model_dump_json()
    assert result.technical_payload["videoEffects"][0]["parameters"]["apiKey"] == "[redacted]"
    if kind == "video":
        assert result.basics.fileTarget == "/private/video.mov"
    else:
        assert "fileTarget" not in result.technical_payload


@pytest.mark.parametrize("kind", KINDS)
def test_wrong_type_uuid_and_payload(kind):
    osc = fixture(kind)
    reader = QLabReader(osc)
    osc.cell_values[FIRST]["type"] = "Audio"
    assert detail(reader, kind).error_code == f"{kind}_cue_type_mismatch"
    osc.cell_values[FIRST]["uniqueID"] = SECOND
    assert detail(reader, kind).error_code == f"{kind}_cue_identity_mismatch"
    osc.cell_values[FIRST] = []
    assert detail(reader, kind).error_code == f"{kind}_cue_payload_invalid"


@pytest.mark.parametrize("kind", KINDS)
def test_secondary_fields_are_partial(kind):
    osc = fixture(kind)
    osc.cell_values[FIRST]["opacity"] = float("nan")
    osc.cell_values[FIRST]["videoEffects"] = [1]
    result = detail(QLabReader(osc), kind)
    assert result.partial and result.video.opacity is None and result.video.videoEffects is None
    assert result.video.translation.x == 10


def test_text_property_failure_and_malformed_fragments():
    osc = fixture("text")
    reader = QLabReader(osc)
    original = reader.read_cue_property
    def fail(ws, cue, prop):
        if prop == "text/format/alignment":
            raise TimeoutError("Timed out")
        return original(ws, cue, prop)
    reader.read_cue_property = fail
    osc.cell_values[FIRST]["text/format"] = [{}]
    result = detail(reader, "text")
    assert result.partial and result.text.text == "Hello world"
    assert "text/format" in result.errors and "text/format/alignment" in result.errors
    assert result.text.fragments is None


@pytest.mark.parametrize("kind", ("video", "camera"))
def test_crosspoint_and_invalid_selectors(kind):
    osc = fixture(kind)
    reader = QLabReader(osc)
    assert detail(reader, kind, input_channel=0, output_channel=1).level.value == "-inf"
    for kwargs in ({"input_channel": 0}, {"input_channel": True, "output_channel": 0},
                   {"input_channel": 1.0, "output_channel": 0}, {"input_channel": "1", "output_channel": 0},
                   {"input_channel": -1, "output_channel": 0}, {"input_channel": 25, "output_channel": 0},
                   {"input_channel": 0, "output_channel": 129}):
        osc.calls.clear()
        assert detail(reader, kind, **kwargs).error_code == "validation_failed"
        assert not osc.calls


@pytest.mark.parametrize("kind", KINDS)
def test_identity_change_in_secondary_read(kind, monkeypatch):
    reader = QLabReader(fixture(kind))
    original = reader.read_cue_values
    def changed(*args, **kwargs):
        result = original(*args, **kwargs)
        if "opacity" in args[2]:
            result["values"]["uniqueID"] = SECOND
        return result
    monkeypatch.setattr(reader, "read_cue_values", changed)
    result = detail(reader, kind)
    assert not result.ok and result.identity is None
    assert result.error_code == f"{kind}_cue_identity_mismatch"


def test_text_budget_clears_content():
    osc = fixture("text")
    osc.cell_values[FIRST]["text"] = "x" * 1_100_000
    result = detail(QLabReader(osc), "text")
    assert result.error_code == "cue_payload_too_large" and result.text is None and result.video is None
    assert result.technical_payload is None and len(result.model_dump_json()) < 10000


@pytest.mark.parametrize("kind", KINDS)
def test_fastmcp_roundtrip(kind, monkeypatch):
    monkeypatch.setattr(server, "_reader", lambda: QLabReader(fixture(kind)))
    async def run():
        async with Client(server.mcp) as client:
            inv = await client.call_tool(f"qlab_get_{kind}_cues", {"workspace_id": WS, "cue_list_id": LIST})
            assert inv.structured_content["returned_count"] == 2
            result = await client.call_tool(f"qlab_get_{kind}_cue_details", {"workspace_id": WS, "cue_id": FIRST})
            assert result.structured_content["ok"] and result.structured_content["identity"]["type"] == kind.title()
            if kind == "text":
                with pytest.raises(Exception):
                    await client.call_tool("qlab_get_text_cue_details", {"workspace_id": WS, "cue_id": FIRST, "input_channel": 0})
    asyncio.run(run())


@pytest.mark.parametrize('values,expected', [([None, None], None), ([2, 2], 2), ([2, 3], None), ([2, None], None)])
def test_text_optional_attributes_from_fragments(values, expected):
    osc = fixture('text')
    for run, value in zip(osc.cell_values[FIRST]['text/format'], values):
        if value is not None:
            run['shadowBlurRadius'] = value
    result = detail(QLabReader(osc), 'text')
    assert result.text.shadowBlurRadius == expected
    assert not any('/text/format/shadowBlurRadius' in address for address, _ in osc.calls)
    assert not result.errors


def test_text_format_timeout_is_not_hidden():
    osc = fixture('text')
    reader = QLabReader(osc)
    original = reader.read_cue_property
    def request(ws, cue, prop):
        if prop == 'text/format':
            raise TimeoutError('format timeout')
        return original(ws, cue, prop)
    reader.read_cue_property = request
    result = detail(reader, 'text')
    assert result.partial and 'text/format' in result.errors
    assert result.text.fragments is None and result.text.shadowBlurRadius is None

@pytest.mark.parametrize('value, expected', [(0, False), (1, True), (False, False), (True, True)])
def test_video_infinite_loop_native_boolean_reads(value, expected):
    osc = fixture('video')
    osc.cell_values[FIRST]['infiniteLoop'] = value
    result = detail(QLabReader(osc), 'video', profile='technical')
    assert result.ok and not result.partial
    assert result.timing.infiniteLoop is expected
    assert result.technical_payload['infiniteLoop'] is expected


@pytest.mark.parametrize('value', [2, -1, 1.0, '1', 'true', [], float('nan')])
def test_video_infinite_loop_invalid_read_stays_partial(value):
    osc = fixture('video')
    osc.cell_values[FIRST]['infiniteLoop'] = value
    result = detail(QLabReader(osc), 'video')
    assert result.partial and result.timing.infiniteLoop is None
    assert result.errors['infiniteLoop'] == 'Invalid OSC value for this field'
