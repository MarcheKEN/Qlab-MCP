"""Native trigger configuration shares the signed executor without sending cues."""
from copy import deepcopy
from types import SimpleNamespace
import json
import subprocess
import sys

import pytest
from pydantic import ValidationError

from qlab_mcp import control_applescript as bridge
from qlab_mcp.write import control, remaining, visual
from qlab_mcp.qlab import QLabReader
from test_control_cue_writes import reader, WS, START, WAIT, request
from test_control_cue_tools import control_fixture
from test_light_group_cue_tools import FIRST
from test_cue_list_tools import WS as READ_WS


BASE = dict(hotkeyTriggerEnabled=False, midiTriggerEnabled=False,
            midiTriggerCommand=1, midiTriggerChannel=0, midiTriggerByte1=0,
            midiTriggerByte2=0, midiTriggerByte1String="0", midiTriggerByte2String="0",
            wallClockTriggerEnabled=False, wallClockHours=0, wallClockMinutes=0,
            wallClockSeconds=0, timecodeTriggerEnabled=False, timecodeShowAsTimecode=True,
            armed=False, continueMode=0, skipIfDisarmed=False,
            timecodeTrigger=dict(hours=1, minutes=0, seconds=0, frames=0, bits=0))


@pytest.fixture
def native(reader, monkeypatch):
    reader.native = {uid: deepcopy(BASE) for uid in reader.values}
    reader.native_setters = []

    def call(_reader, ws, uid, key, **change):
        current = reader.native[uid]
        if "value" in change:
            if change.get("expected_snapshot") != current:
                raise bridge.AppleScriptPreparationError("Trigger baseline changed")
            reader.native_setters.append((uid, key, change["value"]))
            current[key] = change["value"]
            if key in {"midiTriggerByte1", "midiTriggerByte2"}:
                display = current[key + "String"]
                prefix = display[0] if display.startswith(("<", ">")) else ""
                current[key + "String"] = prefix + str(change["value"])
            if reader.fail == "neighbor":
                current["wallClockSeconds"] = 22
            if reader.fail == "timeout":
                raise bridge.AppleScriptTimeoutError("timeout")
        return deepcopy(current) if key == "triggerSnapshot" else current[key]

    monkeypatch.setattr(bridge, "request", call)
    return reader


def plan_and_confirm(native, items, family="control"):
    result = control.edit_control_cues(native, WS, items, True, _family=family)
    assert result["ok"], result
    assert not native.native_setters and not native.setters
    for item, cue in zip(items, result["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in cue["planned_operations"]]
    return result


def test_native_multiple_properties_and_osc_share_signed_batch(native):
    items = [request(name="new", midiTriggerChannel=16, midiTriggerByte1=64, wallClockMinutes=25)]
    plan_and_confirm(native, items)
    result = control.edit_control_cues(native, WS, items, False)
    assert result["ok"], result
    assert len(native.native_setters) == 3 and len(native.setters) == 1
    assert all(op["transport"] == "applescript" and op["address"] is None
               for op in result["results"][0]["planned_operations"] if op["property"] != "name")
    assert not control.edit_control_cues(native, WS, items, False)["ok"]


def test_numeric_midi_byte_preserves_observed_predicate(native):
    native.native[START].update(midiTriggerByte2=70, midiTriggerByte2String="<70")
    items = [request(midiTriggerByte2=0)]
    plan_and_confirm(native, items)
    result = control.edit_control_cues(native, WS, items, False)
    assert result["ok"], result
    snapshot = result["results"][0]["after"]["native_trigger_snapshot"]
    assert snapshot["midiTriggerByte2"] == 0 and snapshot["midiTriggerByte2String"] == "<0"
    assert native.native_setters == [(START, "midiTriggerByte2", 0)]


@pytest.mark.parametrize("properties", [dict(midiTriggerChannel=17), dict(midiTriggerChannel=True),
    dict(midiTriggerCommand=6), dict(midiTriggerByte1=128), dict(wallClockHours=24),
    dict(wallClockMinutes=-1), dict(wallClockSeconds=1.5), dict(hotkeyTriggerEnabled=1),
    dict(midiTriggerByte1=1, midiTriggerByte1String="1"), dict(midiTriggerByte2String=">128"),
    dict(midiTriggerCommand=4, midiTriggerByte1=4)])
def test_strict_native_inputs(properties):
    with pytest.raises(ValidationError):
        control.ControlCueEditInput.model_validate(request(**properties))


@pytest.mark.parametrize("key", ["armed", "continueMode", "skipIfDisarmed", "wallClockSeconds"])
def test_native_dependency_change_invalidates_whole_batch(native, key):
    items = [request(midiTriggerChannel=1), request(WAIT, name="unchanged")]
    plan_and_confirm(native, items)
    native.native[START][key] = 1 if key == "continueMode" else True if key in {"armed", "skipIfDisarmed"} else 15
    result = control.edit_control_cues(native, WS, items, False)
    assert not result["ok"] and not native.native_setters and not native.setters


@pytest.mark.parametrize("state", [dict(armed=True), dict(continueMode=1), dict(skipIfDisarmed=True)])
def test_activation_blocks_armed_or_sequencing_cues(native, state):
    native.native[START].update(state)
    result = control.edit_control_cues(native, WS, [request(midiTriggerEnabled=True)], True)
    assert not result["ok"] and not native.native_setters


def test_configuration_requires_disabled_trigger(native):
    native.native[START]["midiTriggerEnabled"] = True
    result = control.edit_control_cues(native, WS, [request(midiTriggerChannel=1)], True)
    assert not result["ok"] and not native.native_setters


def test_one_byte_command_rejects_second_byte(native):
    native.native[START]["midiTriggerCommand"] = 4
    result = control.edit_control_cues(native, WS, [request(midiTriggerByte2=1)], True)
    assert not result["ok"]


@pytest.mark.parametrize("family,kind", [("audio", "Audio"), ("mic", "Mic"), ("light", "Light"),
    ("fade", "Fade"), ("network", "Network"), ("midi", "MIDI"), ("midi_file", "MIDI File"),
    ("timecode", "Timecode"), ("script", "Script"), ("video", "Video"), ("camera", "Camera"), ("text", "Text")])
def test_native_configuration_in_each_family(native, family, kind):
    native.values[START].update(type=kind, armed=False, skipIfDisarmed=False, continueMode=0)
    items = [request(wallClockSeconds=30)]
    plan_and_confirm(native, items, family)
    result = control.edit_control_cues(native, WS, items, False, _family=family)
    assert result["ok"], result
    assert native.native_setters == [(START, "wallClockSeconds", 30)] and not native.setters


def test_native_timeout_reads_without_resending(native):
    items = [request(wallClockSeconds=30)]
    plan_and_confirm(native, items)
    native.fail = "timeout"
    result = control.edit_control_cues(native, WS, items, False)
    assert result["status"] == "updated_with_confirmed_timeouts", result
    assert len(native.native_setters) == 1


def test_unexpected_neighbor_change_stops_pending_setters(native):
    items = [request(midiTriggerChannel=2, wallClockMinutes=3)]
    plan_and_confirm(native, items)
    native.fail = "neighbor"
    result = control.edit_control_cues(native, WS, items, False)
    assert not result["ok"] and len(native.native_setters) == 1
    assert result["results"][0]["planned_operations"][1]["status"] == "planned"


def test_optional_native_detail_read_keeps_osc_and_marks_transport(monkeypatch):
    monkeypatch.setattr(bridge, "request", lambda *a, **kw: deepcopy(BASE))
    result = QLabReader(control_fixture("Start")).get_control_cue_details(READ_WS, FIRST, include_native_triggers=True)
    assert result.ok and not result.partial, result.errors
    assert result.triggers.midiTriggerCommand == 1
    assert result.edit_capabilities["property_transports"]["wallClockSeconds"] == "applescript"
    assert "wallClockSeconds" in result.edit_capabilities["allowed_properties"]
    assert result.coverage.source == "documented_osc_and_applescript"


def test_native_denial_retains_osc_and_blocks_all_native_trigger_edits(monkeypatch):
    def deny(*a, **kw):
        raise bridge.AppleScriptPreparationError("Automation denied")
    monkeypatch.setattr(bridge, "request", deny)
    result = QLabReader(control_fixture("Start")).get_control_cue_details(READ_WS, FIRST, include_native_triggers=True)
    assert result.partial and result.identity and result.triggers.duckLevel == -12
    assert result.triggers.wallClockSeconds is None
    assert "wallClockSeconds" in result.edit_capabilities["blocked_properties"]
    assert "applescript:triggers" in result.errors


def test_native_bridge_serializes_checked_snapshot_and_preserves_types(native, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    def run(argv, **kw):
        payload = json.loads(argv[-1])
        assert payload["expected_snapshot"] == BASE
        return SimpleNamespace(returncode=0, stdout=json.dumps(dict(workspace_id=WS,
            cue_id=START, type="Start", value=30)), stderr="")
    monkeypatch.setattr(bridge.subprocess, "run", run)
    # Use the actual bridge, not the in-memory native fixture substitute.
    assert REAL_REQUEST(native, WS, START, "wallClockSeconds", value=30, expected=0,
                        expected_snapshot=BASE, expected_type="Start") == 30


REAL_REQUEST = bridge.request


def test_absent_native_reads_never_advertise_gated_remaining_properties():
    caps = remaining.capabilities("audio")
    assert "midiTriggerChannel" in caps["blocked_properties"]
    assert "midiTriggerChannel" not in caps["allowed_properties"]
    assert "midiTriggerChannel" not in caps["gated_or_planned_properties"]


@pytest.mark.skipif(sys.platform != "darwin", reason="AppleScript Foundation bridge requires macOS")
@pytest.mark.parametrize("seconds,expected", [(0, "true"), (1, "false")])
def test_foundation_snapshot_comparison_executes_without_qlab(seconds, expected):
    # Run the production comparison handler: no app events, cue access or setters.
    script = 'use framework "Foundation"\n' + bridge.SNAPSHOT_COMPARISON_HANDLER + f'''
on run
 set raw to current application's NSString's stringWithString:"{{\\"wallClockSeconds\\":0}}"
 set baseline to current application's NSJSONSerialization's JSONObjectWithData:(raw's dataUsingEncoding:4) options:0 |error|:(missing value)
 set currentState to current application's NSMutableDictionary's dictionary()
 currentState's setObject:{seconds} forKey:"wallClockSeconds"
 return my sameSnapshot(currentState, baseline)
end run
'''
    result = subprocess.run(["/usr/bin/osascript", "-"], input=script, text=True, capture_output=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
