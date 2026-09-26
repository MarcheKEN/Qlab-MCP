"""Remaining families: conditional reads and opt-in sensitive content."""
import pytest

from qlab_mcp.qlab import QLabReader
from test_control_cue_tools import control_fixture, read_keys
from test_cue_list_tools import WS
from test_light_group_cue_tools import FIRST, SECOND


@pytest.mark.parametrize("family,kind", [("fade", "Fade"), ("network", "Network"),
    ("midi", "MIDI"), ("midi", "MIDI File"), ("timecode", "Timecode"), ("script", "Script")])
def test_remaining_detail_exists_and_preserves_identity(family, kind):
    osc = control_fixture(kind)
    osc.cell_values[FIRST].update(messageType=1, outputType=0, fadeType=0, targetMode=1)
    result = getattr(QLabReader(osc), f"get_{family}_cue_details")(WS, FIRST)
    assert result.ok, result.errors
    assert result.identity.type == kind


@pytest.mark.parametrize("family,kind,key,value", [
    ("script", "Script", "scriptSource", "do shell script PRIVATE"),
    ("network", "Network", "customString", "/secret PRIVATE"),
    ("network", "Network", "parameterValues", [None, {"password": "PRIVATE"}]),
    ("network", "Network", "messageError", "Illegal OSC address PRIVATE"),
])
def test_sensitive_fields_require_technical(family, kind, key, value):
    osc = control_fixture(kind)
    osc.cell_values[FIRST].update({key: value, "fadeType": 0})
    result = getattr(QLabReader(osc), f"get_{family}_cue_details")(WS, FIRST)
    assert key not in read_keys(osc)
    assert "PRIVATE" not in result.model_dump_json()


def test_network_message_error_requires_technical():
    osc = control_fixture("Network")
    osc.cell_values[FIRST].update(fadeType=0, messageError="Illegal OSC address PRIVATE")
    result = QLabReader(osc).get_network_cue_details(WS, FIRST, "technical")
    assert result.ok and result.content.messageError == "Illegal OSC address PRIVATE"


@pytest.mark.parametrize("mode,expected,forbidden", [
    (1, "channel", "rawString"), (2, "command", "channel"), (3, "rawString", "command")])
def test_midi_reads_only_selected_mode(mode, expected, forbidden):
    osc = control_fixture("MIDI")
    osc.cell_values[FIRST]["messageType"] = mode
    result = QLabReader(osc).get_midi_cue_details(WS, FIRST)
    assert result.ok
    assert expected in read_keys(osc) and forbidden not in read_keys(osc)


def test_conditional_timeout_is_partial_not_fatal():
    osc = control_fixture("MIDI")
    osc.cell_values[FIRST]["messageType"] = 1
    original = osc.reply
    def reply(address, args):
        if address.endswith("valuesForKeys") and '"channel"' in args[0]:
            raise TimeoutError("secondary read timed out")
        return original(address, args)
    osc.reply = reply
    result = QLabReader(osc).get_midi_cue_details(WS, FIRST)
    assert result.ok and result.partial and result.identity.type == "MIDI"
    assert result.detail.kind == "midi"


@pytest.mark.parametrize("kind,selector", [("MIDI", "messageType"), ("Timecode", "outputType"),
    ("Network", "fadeType"), ("Fade", "targetMode")])
def test_first_detail_timeout_preserves_identity(kind, selector):
    osc = control_fixture(kind)
    osc.cell_values[FIRST].update(messageType=1, outputType=0, fadeType=1, targetMode=1)
    original = osc.reply
    def reply(address, args):
        if address.endswith("valuesForKeys") and '"parent"' in args[0]:
            raise TimeoutError("detail read timed out")
        return original(address, args)
    osc.reply = reply
    result = getattr(QLabReader(osc), f"get_{kind.lower()}_cue_details")(WS, FIRST)
    assert result.ok and result.partial and result.identity.type == kind
    assert result.errors


def test_fade_target_timeout_preserves_fade_detail():
    osc = control_fixture("Fade")
    osc.cell_values[FIRST].update(targetMode=0, cueTargetID=SECOND, fadeType=1)
    original = osc.reply
    def reply(address, args):
        if f"/cue_id/{SECOND}/" in address:
            raise TimeoutError("target read timed out")
        return original(address, args)
    osc.reply = reply
    result = QLabReader(osc).get_fade_cue_details(WS, FIRST)
    assert result.ok and result.partial and result.identity.type == "Fade"
    assert result.fade.targetMode == 0
    assert "target" in result.errors


@pytest.mark.parametrize("mode,expected,forbidden", [(0, "midiPatchID", "ltcChannel"), (1, "ltcChannel", "midiPatchID")])
def test_timecode_branches(mode, expected, forbidden):
    osc = control_fixture("Timecode")
    osc.cell_values[FIRST]["outputType"] = mode
    result = QLabReader(osc).get_timecode_cue_details(WS, FIRST)
    assert result.ok
    assert expected in read_keys(osc) and forbidden not in read_keys(osc)


@pytest.mark.parametrize("kind,key,value", [("MIDI", "messageType", 1), ("Timecode", "outputType", 0), ("Network", "fadeType", 1)])
def test_changed_selector_discards_detail(kind, key, value):
    osc = control_fixture(kind)
    osc.cell_values[FIRST][key] = value
    original = osc.reply
    def reply(address, args):
        if address.endswith("valuesForKeys") and args[0] == '["uniqueID", "type", "' + key + '"]':
            osc.cell_values[FIRST][key] = value + 1
        return original(address, args)
    osc.reply = reply
    result = getattr(QLabReader(osc), f"get_{kind.lower()}_cue_details")(WS, FIRST)
    assert not result.ok and result.identity is None


def test_network_null_and_redacted_parameters():
    osc = control_fixture("Network")
    osc.cell_values[FIRST].update(fadeType=0, parameterValues=[None, {"apiKey": "SECRET"}, 2])
    result = QLabReader(osc).get_network_cue_details(WS, FIRST, "technical")
    assert result.ok and not result.partial, result.errors
    assert result.content.parameterValues == [None, {"apiKey": "[redacted]"}, 2]
    assert "SECRET" not in result.model_dump_json()


def test_midi_file_discriminator_and_no_message_reads():
    osc = control_fixture("MIDI File")
    osc.cell_values[FIRST].update(rate=1.0, fileTarget="/private/test.mid")
    result = QLabReader(osc).get_midi_cue_details(WS, FIRST, "technical")
    assert result.detail.kind == "midi_file" and result.detail.file.rate == 1
    assert not read_keys(osc).intersection({"messageType", "status", "rawString", "channel"})


def test_public_midi_schema_contains_only_discriminated_detail():
    from qlab_mcp.cues.remaining import MidiCueDetailsResult
    properties = MidiCueDetailsResult.model_json_schema()["properties"]
    assert "detail" in properties
    assert not set(properties).intersection({"midi_selector", "voice", "msc", "sysex", "file"})


@pytest.mark.parametrize("family,kind", [("fade", "Fade"), ("network", "Network"), ("midi", "MIDI"), ("timecode", "Timecode"), ("script", "Script")])
def test_inventory_scope_and_validation(family, kind):
    from test_cue_list_tools import LIST, CART
    osc = control_fixture(kind)
    read = getattr(QLabReader(osc), f"get_{family}_cues")
    assert read(WS, LIST, limit=True).error_code == "validation_failed"
    assert not osc.calls
    result = read(WS, LIST)
    assert result.ok and result.cues[0].type == kind
    assert read(WS, CART).error_code == "cue_list_type_mismatch"


def test_public_tools_each_callable(monkeypatch):
    import asyncio
    from fastmcp import Client
    import qlab_mcp.server as server
    from test_cue_list_tools import LIST
    async def run():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert len(tools) == 48
            for family, kind in [("fade", "Fade"), ("network", "Network"), ("midi", "MIDI"), ("timecode", "Timecode"), ("script", "Script")]:
                osc = control_fixture(kind)
                osc.cell_values[FIRST].update(messageType=1, outputType=0, fadeType=1, targetMode=1)
                reader = QLabReader(osc)
                monkeypatch.setattr(server, "_run_tool", lambda fn, **kw: fn(reader))
                for suffix, args in [("cues", {"cue_list_id": LIST}), ("cue_details", {"cue_id": FIRST})]:
                    name = f"qlab_get_{family}_{suffix}"
                    assert tools[name].annotations.readOnlyHint
                    result = await client.call_tool(name, {"workspace_id": WS, **args})
                    assert result.structured_content["ok"], result.structured_content
    asyncio.run(run())
