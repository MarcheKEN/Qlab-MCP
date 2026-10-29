"""The fixed AppleScript bridge and the signed Control executor share safety gates."""
import json
import subprocess
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from qlab_mcp import control_applescript as bridge
from qlab_mcp.write import control as writes
from test_control_cue_writes import reader, request, WS, START, WAIT, TARGET
from test_control_cue_tools import control_fixture
from test_light_group_cue_tools import FIRST
from test_cue_list_tools import WS as READ_WS
from qlab_mcp.qlab import QLabReader


APP_IDENTITY = dict(path="/Applications/QLab.app", pid=1234,
                    bundle_id="com.figure53.QLab.5", version="5.5.10", build="5510")
NATIVE_SNAPSHOT = dict(
    app_identity=APP_IDENTITY, hotkeyTriggerEnabled=False, midiTriggerEnabled=False,
    midiTriggerCommand=1, midiTriggerChannel=0, midiTriggerByte1=0, midiTriggerByte2=0,
    midiTriggerByte1String="0", midiTriggerByte2String="0", wallClockTriggerEnabled=False,
    wallClockHours=0, wallClockMinutes=0, wallClockSeconds=0, timecodeTriggerEnabled=False,
    timecodeShowAsTimecode=True, armed=False, continueMode=0, skipIfDisarmed=False,
    timecodeTrigger=dict(hours=1, minutes=0, seconds=0, frames=0, bits=0))


@pytest.mark.parametrize("key,value", [("fadeAndStopOthers", 2), ("sliceMarkers", []),
    ("sliceMarkers", [{"time": 1.25, "playCount": -1}])])
def test_fixed_common_readback_accepts_typed_values(key, value):
    bridge.validate_common_value(key, value)


@pytest.mark.parametrize("key,value", [("fadeAndStopOthers", False), ("fadeAndStopOthers", 4),
    ("sliceMarkers", None), ("sliceMarkers", [{"time": True, "playCount": 1}]),
    ("sliceMarkers", [{"time": 1, "playCount": 0}])])
def test_fixed_common_readback_rejects_ambiguous_values(key, value):
    with pytest.raises(ValueError):
        bridge.validate_common_value(key, value)


@pytest.fixture
def script_reader(reader, monkeypatch):
    reader.values[START].update(type="Load", hasCueTargets=True, cueTargetID=TARGET, loadTime=0.0)
    reader.native_snapshot = json.loads(json.dumps(NATIVE_SNAPSHOT))
    reader.script_setters = []

    def script_request(_reader, ws, uid, key, **kwargs):
        assert ws == WS
        if key == "triggerSnapshot":
            return json.loads(json.dumps(reader.native_snapshot))
        if "value" in kwargs:
            assert kwargs["expected_application"] == reader.native_snapshot["app_identity"]
            assert reader.values[uid][key] == kwargs["expected"]
            reader.script_setters.append((uid, key, kwargs["value"]))
            reader.values[uid][key] = kwargs["value"]
            if reader.fail == "timeout":
                raise bridge.AppleScriptTimeoutError("timeout")
        return reader.values[uid][key]

    monkeypatch.setattr(bridge, "request", script_request)
    return reader


def confirmed_items(reader, items, family="control"):
    plan = writes.edit_control_cues(reader, WS, items, True, _family=family)
    assert plan["ok"], plan
    assert all(not result["executed_operations"] for result in plan["results"])
    for item, result in zip(items, plan["results"], strict=True):
        item["confirm_gates"] = [op["confirm_token"] for op in result["planned_operations"]]
    return items


@pytest.mark.parametrize("value", [1.25, -2.5, 0])
def test_load_time_uses_signed_script_operation_without_osc_setter(script_reader, value):
    items = confirmed_items(script_reader, [request(loadTime=value)])
    assert not script_reader.script_setters and not script_reader.setters
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert result["ok"], result
    assert result["results"][0]["after"]["loadTime"] == value
    assert script_reader.script_setters == [(START, "loadTime", value)]
    assert not script_reader.setters
    assert result["results"][0]["executed_operations"][0]["transport"] == "applescript"
    assert not writes.edit_control_cues(script_reader, WS, items, False)["ok"]


def test_stale_load_time_token_prevents_all_setters(script_reader):
    items = confirmed_items(script_reader, [request(loadTime=3, name="new")])
    script_reader.values[START]["loadTime"] = 0.5
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


def test_changed_qlab_process_invalidates_load_time_confirmation(script_reader):
    items = confirmed_items(script_reader, [request(loadTime=3)])
    script_reader.native_snapshot["app_identity"] = {**APP_IDENTITY, "pid": 4321}
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


def test_changed_qlab_process_invalidates_assigned_number_confirmation(script_reader, monkeypatch):
    target_setup(script_reader, monkeypatch)
    items = confirmed_items(script_reader, [request(assignedNumber="3")], "target")
    script_reader.native_snapshot["app_identity"] = {**APP_IDENTITY, "pid": 4321}
    result = writes.edit_target_cues(script_reader, WS, items, False)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


def test_load_time_rejected_for_other_control_types_before_any_write(script_reader):
    result = writes.edit_control_cues(script_reader, WS, [request(name="new"), request(WAIT, loadTime=2)], True)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


@pytest.mark.parametrize("value", [True, "2", float("inf"), float("nan")])
def test_load_time_strict_request(value):
    with pytest.raises(ValidationError):
        writes.ControlCueEditInput.model_validate(request(loadTime=value))


def test_script_timeout_confirmed_by_readback_never_resends(script_reader):
    items = confirmed_items(script_reader, [request(loadTime=4)])
    script_reader.fail = "timeout"
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert result["status"] == "updated_with_confirmed_timeouts", result
    assert len(script_reader.script_setters) == 1


def test_script_preparation_failure_consumes_token_without_setter(script_reader, monkeypatch):
    items = confirmed_items(script_reader, [request(loadTime=4)])
    original = bridge.request
    def fail_preparation(*args, **kwargs):
        if "value" in kwargs:
            raise bridge.AppleScriptPreparationError("Automation denied")
        return original(*args, **kwargs)
    monkeypatch.setattr(bridge, "request", fail_preparation)
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert not result["ok"] and result["results"][0]["executed_operations"] == []
    assert not script_reader.script_setters
    monkeypatch.setattr(bridge, "request", original)
    assert not writes.edit_control_cues(script_reader, WS, items, False)["ok"]


def target_setup(script_reader, monkeypatch):
    script_reader.values[START].update(type="Target", assignedNumber="", cueTargetID=WAIT)
    script_reader.values[WAIT]["hasCueTargets"] = True
    monkeypatch.setattr(writes, "_read_snapshot", lambda *a: {"nodes": script_reader.values})


@pytest.mark.parametrize("number", ["3", ""])
def test_assigned_number_resolves_workspace_identity_and_can_clear(script_reader, monkeypatch, number):
    target_setup(script_reader, monkeypatch)
    if not number:
        script_reader.values[START]["assignedNumber"] = "3"
    items = confirmed_items(script_reader, [request(assignedNumber=number)], "target")
    result = writes.edit_target_cues(script_reader, WS, items, False)
    assert result["ok"], result
    assert script_reader.script_setters == [(START, "assignedNumber", number)]
    assert script_reader.values[START]["number"] == "0"
    assert script_reader.values[WAIT]["cueTargetID"] == ""


@pytest.mark.parametrize("number", ["missing", "0", "1"])
def test_missing_or_self_assignment_rejected_without_write(script_reader, monkeypatch, number):
    target_setup(script_reader, monkeypatch)
    result = writes.edit_target_cues(script_reader, WS, [request(assignedNumber=number)], True)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


def test_assignment_number_change_invalidates_token(script_reader, monkeypatch):
    target_setup(script_reader, monkeypatch)
    items = confirmed_items(script_reader, [request(assignedNumber="3")], "target")
    script_reader.values[TARGET]["number"] = "4"
    assert not writes.edit_target_cues(script_reader, WS, items, False)["ok"]
    assert not script_reader.script_setters


def test_target_change_and_native_field_require_separate_dry_runs(script_reader):
    result = writes.edit_control_cues(script_reader, WS, [request(loadTime=2, cueTargetID=TARGET)], True)
    assert not result["ok"] and not script_reader.script_setters


@pytest.mark.parametrize("kind,key,section,value", [("Load", "loadTime", "load", -1.25), ("Target", "assignedNumber", "assignment", "3")])
def test_details_read_native_fields_and_expose_transport(monkeypatch, kind, key, section, value):
    monkeypatch.setattr(bridge, "request", lambda *a, **kw: value)
    result = QLabReader(control_fixture(kind)).get_control_cue_details(READ_WS, FIRST)
    assert result.ok and not result.partial, result.errors
    assert getattr(getattr(result, section), key) == value
    assert result.edit_capabilities["property_transports"][key] == "applescript"
    assert key in result.edit_capabilities["allowed_properties"]
    assert result.coverage.source == "documented_osc_and_applescript"


def test_details_automation_denied_preserves_osc_data_and_blocks_native_edit(monkeypatch):
    def denied(*a, **kw):
        raise bridge.AppleScriptPreparationError("Automation denied")
    monkeypatch.setattr(bridge, "request", denied)
    result = QLabReader(control_fixture("Load")).get_control_cue_details(READ_WS, FIRST)
    assert result.partial and result.identity is not None and result.basics is not None
    assert result.load is None and "applescript:loadTime" in result.errors
    assert "loadTime" in result.edit_capabilities["blocked_properties"]
    assert result.coverage.source == "documented_osc"


def test_wrong_family_details_remain_error_not_native_partial():
    result = QLabReader(control_fixture("Audio")).get_control_cue_details(READ_WS, FIRST)
    assert not result.ok and result.status == "error" and not result.partial


@pytest.mark.parametrize("response", [
    {"workspace_id": READ_WS, "cue_id": START, "type": "Load", "value": 1},
    {"workspace_id": WS, "cue_id": START, "type": "Audio", "value": 1},
    {"error": "Automation denied", "sent": False},
])
def test_bridge_rejects_identity_or_preparation_failure(reader, monkeypatch, response):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=json.dumps(response), stderr=""))
    with pytest.raises((ValueError, bridge.AppleScriptPreparationError)):
        bridge.request(reader, WS, START, "loadTime")


def test_bridge_reads_json_without_locale_conversion(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=json.dumps({"workspace_id": WS, "cue_id": START, "type": "Load", "value": 1.25}), stderr=""))
    assert bridge.request(reader, WS, START, "loadTime") == 1.25


@pytest.mark.parametrize("value", [True, None, "1,25", float("nan")])
def test_bridge_rejects_invalid_native_load_time(reader, monkeypatch, value):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: SimpleNamespace(
        returncode=0, stdout=json.dumps({"workspace_id": WS, "cue_id": START, "type": "Load", "value": value}), stderr=""))
    with pytest.raises(ValueError):
        bridge.request(reader, WS, START, "loadTime")


def test_bridge_remote_host_cannot_modify_local_qlab(reader, monkeypatch):
    reader.client.config = SimpleNamespace(host="192.0.2.1", timeout=2)
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("Must not send AppleEvents"))
    with pytest.raises(bridge.AppleScriptPreparationError):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET,
                       expected_application=APP_IDENTITY)


def test_bridge_user_text_stays_data_not_source(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    value = 'a" & do shell script "echo bad"\nβ'
    def run(argv, **kwargs):
        assert value not in kwargs["input"]
        payload = json.loads(argv[-1])
        assert payload["value"] == value
        assert payload["expected_application"] == APP_IDENTITY
        assert "shell" not in kwargs
        return SimpleNamespace(returncode=0, stdout=json.dumps({"workspace_id": WS, "cue_id": START, "type": "Target", "value": value}), stderr="")
    monkeypatch.setattr(bridge.subprocess, "run", run)
    assert bridge.request(reader, WS, START, "assignedNumber", value=value, expected="", expected_target=TARGET,
                          expected_application=APP_IDENTITY, assigned_cue_id=WAIT) == value


def test_bridge_process_timeout_is_not_retried(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    calls = []
    def run(*args, **kwargs):
        calls.append(args)
        raise subprocess.TimeoutExpired("osascript", 2)
    monkeypatch.setattr(bridge.subprocess, "run", run)
    with pytest.raises(bridge.AppleScriptTimeoutError):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET,
                       expected_application=APP_IDENTITY)
    assert len(calls) == 1


def test_script_targets_only_the_unique_verified_running_qlab_installation():
    script = bridge.SCRIPT
    assert 'runningApplicationsWithBundleIdentifier:"com.figure53.QLab.5"' in script
    assert 'if (apps\'s |count|() as integer) is not 1' in script
    assert 'CFBundleIdentifier' in script and 'CFBundleShortVersionString' in script and 'CFBundleVersion' in script
    assert 'is not "5.5.10"' in script and 'is not "5510"' in script
    assert 'tell application applicationPath' in script
    assert 'tell application "/Applications/QLab.app"' not in script
    assert 'on nativeSnapshot(c, applicationIdentity)' in script
    assert 'on nativeSet(c, propertyKey, payload, applicationPath)' in script
    assert 'on midiCommandNumber(cmd, applicationPath)' in script
    assert 'expected_application' in script


def test_script_rejects_ambiguous_or_changed_qlab_process_and_keeps_write_gates():
    script = bridge.SCRIPT
    assert 'Exactly one local QLab instance must already be running.' in script
    assert 'The QLab process is no longer running.' in script
    assert 'QLab process identity changed during the native cue request.' in script
    assert 'if (unique id of w) is not wsid or (uniqueID of c) is not uid' in script
    assert 'if not (edit mode of w) or (count of active cues of w) is not 0' in script
    assert 'Native trigger or safety baseline changed.' in script
    assert 'output\'s setObject:applicationIdentity forKey:"app_identity"' in script
    assert 'QLab process identity changed before native cue setter.' in script
    assert 'QLab installation identity changed since preflight.' in script


def test_dynamic_target_is_not_caller_controlled(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    def run(argv, **kwargs):
        payload = json.loads(argv[-1])
        assert "application_path" not in payload and "applicationPath" not in payload
        assert "tell application applicationPath" in kwargs["input"]
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "workspace_id": WS, "cue_id": START, "type": "Load", "value": 1.25}), stderr="")
    monkeypatch.setattr(bridge.subprocess, "run", run)
    assert bridge.request(reader, WS, START, "loadTime") == 1.25


def test_bridge_disabled_write_mode_never_sends_appleevents(reader, monkeypatch):
    from qlab_mcp.config import QLabConfig
    reader.client.config = QLabConfig()
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("Disabled writes must not start a script"))
    with pytest.raises(bridge.AppleScriptPreparationError):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET,
                       expected_application=APP_IDENTITY)


def test_scalar_script_write_requires_preflight_application_identity(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("No script without signed app identity"))
    with pytest.raises(bridge.AppleScriptPreparationError, match="installation identity"):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET)


def test_bridge_nonzero_exit_after_possible_mutation_is_not_claimed_unsent(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=1, stdout="", stderr="unexpected runtime exit"))
    with pytest.raises(bridge.QLabMcpError) as error:
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET,
                       expected_application=APP_IDENTITY)
    assert not isinstance(error.value, bridge.AppleScriptPreparationError)


def test_script_timeout_with_unreadable_value_stops_pending_operations(script_reader, monkeypatch):
    items = confirmed_items(script_reader, [request(loadTime=4), request(WAIT, name="pending")])
    original = bridge.request
    attempted = []
    def timed_out(*args, **kwargs):
        if "value" in kwargs:
            attempted.append(kwargs["value"])
        if attempted:
            raise bridge.AppleScriptTimeoutError("timeout")
        return original(*args, **kwargs)
    monkeypatch.setattr(bridge, "request", timed_out)
    result = writes.edit_control_cues(script_reader, WS, items, False)
    assert not result["ok"] and attempted == [4]
    assert len(result["results"][0]["executed_operations"]) == 1
    assert not script_reader.setters
    assert result["results"][1]["planned_operations"][0]["status"] == "planned"


def test_assignment_batch_cannot_renumber_its_dependency(script_reader, monkeypatch):
    target_setup(script_reader, monkeypatch)
    script_reader.values[TARGET].update(type="Target", hasCueTargets=True, assignedNumber="", cueTargetID=WAIT)
    result = writes.edit_target_cues(script_reader, WS, [request(assignedNumber="3"), request(TARGET, number="4")], True)
    assert not result["ok"] and not script_reader.script_setters and not script_reader.setters


@pytest.mark.parametrize("target", [None, True, "not-a-uuid"])
def test_unknown_target_blocks_entire_batch_before_any_setter(script_reader, target):
    script_reader.values[START]["cueTargetID"] = target
    result = writes.edit_control_cues(script_reader, WS, [request(WAIT, name="must not change"), request(loadTime=2)], True)
    assert not result["ok"] and not script_reader.setters and not script_reader.script_setters
    assert all(not item["executed_operations"] for item in result["results"])


def test_missing_target_is_not_an_empty_placeholder(script_reader):
    del script_reader.values[START]["cueTargetID"]
    result = writes.edit_control_cues(script_reader, WS, [request(WAIT, name="must not change"), request(loadTime=2)], True)
    assert not result["ok"] and not script_reader.setters and not script_reader.script_setters


def test_invalid_script_arguments_are_preparation_failures(reader, monkeypatch):
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("Invalid arguments must not start a process"))
    with pytest.raises(bridge.AppleScriptPreparationError):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=None,
                       expected_application=APP_IDENTITY)


def test_expired_read_deadline_is_preparation_failure_before_script(reader, monkeypatch):
    from qlab_mcp.errors import OscTimeoutError
    def expired(*a):
        raise OscTimeoutError("Read deadline exhausted")
    reader._bounded_read_timeout = expired
    monkeypatch.setattr(bridge.sys, "platform", "darwin")
    monkeypatch.setattr(bridge.subprocess, "run", lambda *a, **kw: pytest.fail("No process after deadline"))
    with pytest.raises(bridge.AppleScriptPreparationError):
        bridge.request(reader, WS, START, "loadTime", value=1, expected=0, expected_target=TARGET,
                       expected_application=APP_IDENTITY)


def test_native_operation_confirms_with_public_fastmcp_schema(script_reader, monkeypatch):
    import asyncio
    from fastmcp import Client
    import qlab_mcp.server as server
    monkeypatch.setattr(server, "_run_tool", lambda fn, **kw: fn(script_reader))
    async def run():
        async with Client(server.mcp) as client:
            planned = await client.call_tool("qlab_edit_control_cues", {"workspace_id": WS, "updates": [request(loadTime=1.25)], "dry_run": True})
            result = planned.structured_content
            token = result["results"][0]["planned_operations"][0]["confirm_token"]
            executed = await client.call_tool("qlab_edit_control_cues", {"workspace_id": WS, "updates": [{**request(loadTime=1.25), "confirm_gates": [token]}], "dry_run": False})
            assert executed.structured_content["ok"]
    asyncio.run(run())
