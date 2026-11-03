"""Fixed local AppleEvents for saved cue settings; no caller-provided script."""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, StrictBool, StrictInt, StrictStr

from .errors import OscTimeoutError, QLabMcpError


class AppleScriptPreparationError(QLabMcpError):
    """The fixed script failed before its setter."""


class AppleScriptTimeoutError(QLabMcpError):
    """A script timed out; a mutation must never be resent automatically."""


class NativeTriggerProperties(BaseModel):
    hotkeyTriggerEnabled: StrictBool | None = None
    midiTriggerEnabled: StrictBool | None = None
    midiTriggerCommand: Annotated[StrictInt, Field(ge=0, le=5)] | None = None
    midiTriggerChannel: Annotated[StrictInt, Field(ge=-1, le=16)] | None = None
    midiTriggerByte1: Annotated[StrictInt, Field(ge=0, le=127)] | None = None
    midiTriggerByte2: Annotated[StrictInt, Field(ge=0, le=127)] | None = None
    midiTriggerByte1String: StrictStr | None = None
    midiTriggerByte2String: StrictStr | None = None
    wallClockTriggerEnabled: StrictBool | None = None
    wallClockHours: Annotated[StrictInt, Field(ge=0, le=23)] | None = None
    wallClockMinutes: Annotated[StrictInt, Field(ge=0, le=59)] | None = None
    wallClockSeconds: Annotated[StrictInt, Field(ge=0, le=59)] | None = None
    timecodeTriggerEnabled: StrictBool | None = None
    timecodeShowAsTimecode: StrictBool | None = None


TRIGGER_KEYS = frozenset(NativeTriggerProperties.model_fields)
ENABLED_KEYS = frozenset(key for key in TRIGGER_KEYS if key.endswith("Enabled"))
_APP_IDENTITY_KEYS = frozenset({"path", "pid", "bundle_id", "version", "build"})
_NATIVE_PROPERTIES = {
    "hotkeyTriggerEnabled": "hotkey trigger", "midiTriggerEnabled": "midi trigger",
    "midiTriggerCommand": "midi command", "midiTriggerChannel": "midi trigger channel",
    "midiTriggerByte1": "midi byte one", "midiTriggerByte2": "midi byte two",
    "midiTriggerByte1String": "midi byte one string", "midiTriggerByte2String": "midi byte two string",
    "wallClockTriggerEnabled": "wall clock trigger", "wallClockHours": "wall clock hours",
    "wallClockMinutes": "wall clock minutes", "wallClockSeconds": "wall clock seconds",
    "timecodeTriggerEnabled": "timecode trigger", "timecodeShowAsTimecode": "timecode show as timecode",
}
_CUE_TYPES = frozenset({"Group", "Audio", "Mic", "Video", "Camera", "Text", "Light", "Fade",
    "Network", "MIDI", "MIDI File", "Timecode", "Script", "Start", "Stop", "Pause", "Load",
    "Reset", "Devamp", "GoTo", "Target", "Arm", "Disarm", "Wait", "Memo"})


def validate_trigger_changes(changes):
    native = TRIGGER_KEYS & changes.keys()
    for key in native:
        _validate(key, changes[key])
    for byte in (1, 2):
        if {f"midiTriggerByte{byte}", f"midiTriggerByte{byte}String"} <= native:
            raise ValueError("Use a numeric MIDI trigger byte or its display string, not both.")
    if "midiTriggerCommand" in native and len(native) > 1:
        raise ValueError("Change MIDI trigger command separately, then read its dependent bytes again.")
    if native and ({"armed", "continueMode", "skipIfDisarmed"} & changes.keys() or
                   any(key.startswith("timecodeTrigger/") for key in changes)):
        raise ValueError("Change safety controls or Timecode time separately from native Triggers.")
    if ENABLED_KEYS & native and len(native) > 1:
        raise ValueError("Change trigger activation separately from its configuration.")


def _validate_application_identity(app):
    if (not isinstance(app, dict) or set(app) != _APP_IDENTITY_KEYS
            or type(app.get("path")) is not str or not app["path"].startswith("/") or "\0" in app["path"]
            or type(app.get("pid")) is not int or app["pid"] <= 0
            or app.get("bundle_id") != "com.figure53.QLab.5"
            or app.get("version") != "5.5.10" or app.get("build") != "5510"):
        raise ValueError("Native QLab installation identity is unavailable or unsupported.")
    return app


def validate_trigger_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != TRIGGER_KEYS | {"armed", "continueMode", "skipIfDisarmed", "timecodeTrigger", "app_identity"}:
        raise ValueError("Complete native trigger snapshot is unavailable.")
    _validate_application_identity(snapshot["app_identity"])
    for key in TRIGGER_KEYS:
        _validate(key, snapshot[key], observed=True)
    if type(snapshot["armed"]) is not bool or type(snapshot["skipIfDisarmed"]) is not bool:
        raise ValueError("Native cue safety booleans are unavailable.")
    if type(snapshot["continueMode"]) is not int or snapshot["continueMode"] not in range(3):
        raise ValueError("Native continue mode is unavailable.")
    parts = snapshot["timecodeTrigger"]
    if not isinstance(parts, dict) or set(parts) != {"hours", "minutes", "seconds", "frames", "bits"} or any(type(v) is not int or v < 0 for v in parts.values()):
        raise ValueError("Native Timecode components are unavailable.")
    return snapshot


def trigger_snapshot(reader, ws, uid, kind):
    return validate_trigger_snapshot(request(reader, ws, uid, "triggerSnapshot", expected_type=kind))


def trigger_preflight(snapshot, changes):
    validate_trigger_changes(changes)
    validate_trigger_snapshot(snapshot)
    for key in TRIGGER_KEYS & changes.keys():
        if key in ENABLED_KEYS:
            if changes[key] and (snapshot["armed"] or snapshot["continueMode"] != 0 or snapshot["skipIfDisarmed"]):
                raise ValueError("Enabling a trigger requires disarmed, Do not continue and Skip if disarmed off.")
            if key == "hotkeyTriggerEnabled" and changes[key]:
                raise ValueError("Hotkey activation is blocked: assigned key/modifiers cannot be read through the dictionary.")
        elif snapshot["midiTriggerEnabled" if key.startswith("midi") else "wallClockTriggerEnabled" if key.startswith("wallClock") else "timecodeTriggerEnabled"]:
            raise ValueError("Disable this trigger before changing its configuration.")
        if key.startswith("midiTriggerByte2") and snapshot["midiTriggerCommand"] in {4, 5}:
            raise ValueError("This one-byte MIDI command has no editable second byte.")


def trigger_capabilities(capabilities, triggers):
    allowed = set(capabilities.get("allowed_properties", []))
    blocked = capabilities.setdefault("blocked_properties", {})
    for key in TRIGGER_KEYS:
        if triggers is None or getattr(triggers, key, None) is None:
            blocked[key] = "Request include_native_triggers=true; requires fresh local AppleScript evidence."
        else:
            blocked.pop(key, None)
    capabilities["allowed_properties"] = sorted((allowed | TRIGGER_KEYS) - blocked.keys())
    if "gated_or_planned_properties" in capabilities:
        capabilities["gated_or_planned_properties"] = {
            key: reason for key, reason in capabilities["gated_or_planned_properties"].items() if key not in blocked}
    capabilities.setdefault("property_transports", {}).update({key: "applescript" for key in TRIGGER_KEYS})
    capabilities["native_trigger_preconditions"] = [
        "Configure a disabled trigger; change activation and MIDI command separately.",
        "Activation requires disarmed, Do not continue and Skip if disarmed off.",
        "Hotkey activation is blocked without documented key/modifier readback; disabling is supported.",
        "Hotkey assignment and Wall Clock weekdays are not available through the dictionary.",
    ]
    if "property_capabilities" in capabilities:
        for key in TRIGGER_KEYS:
            capabilities["property_capabilities"][key] = {
                "state": "blocked" if key in blocked else "gated", "transport": "applescript",
                "reason": blocked.get(key, "Signed confirmation and complete native snapshot required.")}
    return capabilities


SCRIPT = '''use framework "AppKit"
on runningQLab()
 set apps to current application's NSRunningApplication's runningApplicationsWithBundleIdentifier:"com.figure53.QLab.5"
 if (apps's |count|() as integer) is not 1 then error "Exactly one local QLab instance must already be running."
 set runningApp to apps's firstObject()
 if runningApp's isTerminated() then error "The QLab process is no longer running."
 set runningPath to ((runningApp's bundleURL()'s |path|()) as text)
 set processID to runningApp's processIdentifier() as integer
 if runningPath is "" or processID is less than or equal to 0 then error "Running QLab identity is unavailable."
 set bundle to current application's NSBundle's bundleWithPath:runningPath
 if bundle is missing value then error "The running QLab bundle is unavailable."
 set appInfo to bundle's infoDictionary()
 if ((appInfo's objectForKey:"CFBundleIdentifier") as text) is not "com.figure53.QLab.5" then error "Unexpected QLab bundle identity."
 if ((appInfo's objectForKey:"CFBundleShortVersionString") as text) is not "5.5.10" or ((appInfo's objectForKey:"CFBundleVersion") as text) is not "5510" then error "Native cue properties require QLab 5.5.10/build 5510."
 set identity to current application's NSMutableDictionary's dictionary()
 identity's setObject:runningPath forKey:"path"
 identity's setObject:processID forKey:"pid"
 identity's setObject:(appInfo's objectForKey:"CFBundleIdentifier") forKey:"bundle_id"
 identity's setObject:(appInfo's objectForKey:"CFBundleShortVersionString") forKey:"version"
 identity's setObject:(appInfo's objectForKey:"CFBundleVersion") forKey:"build"
 return identity
end runningQLab
on run argv
 set sent to false
 set output to current application's NSMutableDictionary's dictionary()
 try
  set raw to current application's NSString's stringWithString:(item 1 of argv)
  set payload to current application's NSJSONSerialization's JSONObjectWithData:(raw's dataUsingEncoding:(current application's NSUTF8StringEncoding)) options:0 |error|:(missing value)
  set wsid to (payload's objectForKey:"workspace_id") as text
  set uid to (payload's objectForKey:"cue_id") as text
  set propertyKey to (payload's objectForKey:"property") as text
  set appIdentity to my runningQLab()
  set applicationPath to (appIdentity's objectForKey:"path") as text
  if ((payload's objectForKey:"write") as boolean) and (propertyKey is "loadTime" or propertyKey is "assignedNumber") then
   set expectedApplication to payload's objectForKey:"expected_application"
   if expectedApplication is missing value or not (my sameSnapshot(appIdentity, expectedApplication)) then error "QLab installation identity changed since preflight."
  end if
  using terms from application "/Applications/QLab.app"
  tell application applicationPath
   set w to first workspace whose unique id is wsid
   set c to cue id uid of w
   if (unique id of w) is not wsid or (uniqueID of c) is not uid then error "AppleScript identity mismatch."
   set kind to q type of c
   if propertyKey is "loadTime" and kind is "Load" then
    set observed to load time of c
   else if propertyKey is "assignedNumber" and kind is "Target" then
    set observed to assigned number of c
   else
    error "Property does not apply to this cue."
   end if
   if ((payload's objectForKey:"write") as boolean) then
    if not (edit mode of w) or (count of active cues of w) is not 0 then error "Workspace must be inactive and in Edit Mode."
    set expectedTarget to (payload's objectForKey:"expected_target") as text
    set targetID to ""
    set receiver to cue target of c
    if receiver is not missing value then set targetID to uniqueID of receiver
    if targetID is not expectedTarget then error "Cue target changed before setter."
    if propertyKey is "loadTime" then
     set previous to (payload's objectForKey:"expected") as real
     set wanted to (payload's objectForKey:"value") as real
    else
     set previous to (payload's objectForKey:"expected") as text
     set wanted to (payload's objectForKey:"value") as text
     if wanted is not "" then
      set assignedID to (payload's objectForKey:"assigned_cue_id") as text
      set assignedCue to cue id assignedID of w
      if (q number of assignedCue) is not wanted then error "Assigned cue number changed before setter."
     end if
    end if
    if observed is not previous then error "Property changed before setter."
    set currentIdentity to my runningQLab()
    if not (my sameSnapshot(currentIdentity, appIdentity)) then error "QLab process identity changed before native cue setter."
    set sent to true
    if propertyKey is "loadTime" then
     set load time of c to wanted
     set observed to load time of c
    else
     set assigned number of c to wanted
     set observed to assigned number of c
    end if
   end if
  end tell
  end using terms from
  set currentIdentity to my runningQLab()
  if not (my sameSnapshot(currentIdentity, appIdentity)) then error "QLab process identity changed during the native cue request."
  output's setObject:wsid forKey:"workspace_id"
  output's setObject:uid forKey:"cue_id"
  output's setObject:kind forKey:"type"
  output's setObject:observed forKey:"value"
 on error messageText number errorNumber
  output's setObject:messageText forKey:"error"
  output's setObject:errorNumber forKey:"error_number"
 end try
 output's setObject:sent forKey:"sent"
 set jsonData to current application's NSJSONSerialization's dataWithJSONObject:output options:0 |error|:(missing value)
 return (current application's NSString's alloc()'s initWithData:jsonData encoding:(current application's NSUTF8StringEncoding)) as text
end run
'''

KINDS = {"loadTime": "Load", "assignedNumber": "Target"}
COMMON_READ_KEYS = {"fadeAndStopOthers", "sliceMarkers"}


def validate_common_value(key, value):
    if key == "fadeAndStopOthers":
        if type(value) is not int or value not in range(4):
            raise ValueError("Fade & Stop Others requires an integer scope 0–3.")
    elif key == "sliceMarkers":
        if not isinstance(value, list) or len(value) > 4096:
            raise ValueError("Slice markers must be an explicit bounded list.")
        previous = -1
        for marker in value:
            if (not isinstance(marker, dict) or set(marker) != {"time", "playCount"}
                    or type(marker["time"]) not in {int, float} or not math.isfinite(marker["time"])
                    or marker["time"] < 0 or marker["time"] <= previous
                    or type(marker["playCount"]) is not int or marker["playCount"] not in {-1} and marker["playCount"] < 1):
                raise ValueError("Invalid slice marker or ordering.")
            previous = marker["time"]
    else:
        raise ValueError("Unsupported common native read.")

# Build only from this fixed dictionary, never from request text or property paths.
_snapshot_lines = []
_setter_lines = []
for _key, _property in _NATIVE_PROPERTIES.items():
    _expression = f"({_property} of c is enabled)" if _key in ENABLED_KEYS else f"{_property} of c"
    if _key == "midiTriggerCommand":
        _expression = "my midiCommandNumber(midi command of c, applicationPath)"
    _snapshot_lines.append(f'  set v to {_expression}\n  output\'s setObject:v forKey:"{_key}"')
    _wanted = "((payload's objectForKey:\"value\") as text)" if _key.endswith("String") else "((payload's objectForKey:\"value\") as boolean)" if _key == "timecodeShowAsTimecode" else "((payload's objectForKey:\"value\") as integer)"
    if _key in ENABLED_KEYS:
        _body = f'''  set wanted to disabled
  if ((payload's objectForKey:"value") as boolean) then set wanted to enabled
  set {_property} of c to wanted'''
    elif _key == "midiTriggerCommand":
        _body = '''  set commands to {note_off, note_on, key_pressure, control_change, program_change, channel_pressure}
  set midi command of c to item (((payload's objectForKey:"value") as integer) + 1) of commands'''
    else:
        _body = f"  set {_property} of c to {_wanted}"
    _setter_lines.append(f' {"if" if not _setter_lines else "else if"} propertyKey is "{_key}" then\n{_body}')

_handlers = '''
on midiCommandNumber(cmd, applicationPath)
 using terms from application "/Applications/QLab.app"
 tell application applicationPath
  set commands to {note_off, note_on, key_pressure, control_change, program_change, channel_pressure}
  repeat with n from 1 to count of commands
   if cmd is item n of commands then return n - 1
  end repeat
  error "Unsupported MIDI trigger command."
 end tell
 end using terms from
end midiCommandNumber
on nativeSnapshot(c, applicationIdentity)
 set output to current application's NSMutableDictionary's dictionary()
 output's setObject:applicationIdentity forKey:"app_identity"
 set applicationPath to (applicationIdentity's objectForKey:"path") as text
 using terms from application "/Applications/QLab.app"
 tell application applicationPath
''' + "\n".join(_snapshot_lines) + '''
  output's setObject:(armed of c) forKey:"armed"
  output's setObject:(skip if disarmed of c) forKey:"skipIfDisarmed"
  set modes to {do_not_continue, auto_continue, auto_follow}
  set modeNumber to -1
  repeat with n from 1 to count of modes
   if (continue mode of c) is item n of modes then set modeNumber to n - 1
  end repeat
  output's setObject:modeNumber forKey:"continueMode"
  set parts to current application's NSMutableDictionary's dictionary()
  parts's setObject:(timecode hours of c) forKey:"hours"
  parts's setObject:(timecode minutes of c) forKey:"minutes"
  parts's setObject:(timecode seconds of c) forKey:"seconds"
  parts's setObject:(timecode frames of c) forKey:"frames"
  parts's setObject:(timecode bits of c) forKey:"bits"
  output's setObject:parts forKey:"timecodeTrigger"
 end tell
 end using terms from
 return output
end nativeSnapshot
on nativeSet(c, propertyKey, payload, applicationPath)
 using terms from application "/Applications/QLab.app"
 tell application applicationPath
''' + "\n".join(_setter_lines) + '''
 else
  error "Unsupported fixed native trigger setter."
 end if
 end tell
 end using terms from
end nativeSet
'''
SNAPSHOT_COMPARISON_HANDLER = '''
on sameSnapshot(observed, expected)
 set matchesState to observed's isEqualToDictionary:expected
 return matchesState as boolean
end sameSnapshot
'''
_native_branch = '''   if propertyKey is "triggerSnapshot" or payload's objectForKey:"expected_snapshot" is not missing value then
    if kind is not ((payload's objectForKey:"expected_type") as text) then error "Native cue type changed."
    set snapshot to my nativeSnapshot(c, appIdentity)
    set observed to snapshot
    if propertyKey is not "triggerSnapshot" then set observed to snapshot's objectForKey:propertyKey
    if ((payload's objectForKey:"write") as boolean) then
     if not (edit mode of w) or (count of active cues of w) is not 0 then error "Workspace must be inactive and in Edit Mode."
     if not (my sameSnapshot(snapshot, payload's objectForKey:"expected_snapshot")) then error "Native trigger or safety baseline changed."
     set triggerKey to "timecodeTriggerEnabled"
     if propertyKey starts with "midi" then set triggerKey to "midiTriggerEnabled"
     if propertyKey starts with "wallClock" then set triggerKey to "wallClockTriggerEnabled"
     if propertyKey ends with "Enabled" then
      if ((payload's objectForKey:"value") as boolean) then
       if propertyKey is "hotkeyTriggerEnabled" then error "Hotkey assignment cannot be verified."
       if (armed of c) or (continue mode of c) is not do_not_continue or (skip if disarmed of c) then error "Unsafe native trigger activation."
      end if
     else
      if ((snapshot's objectForKey:triggerKey) as boolean) then error "Disable the trigger before editing configuration."
     end if
     if propertyKey starts with "midiTriggerByte2" and ((snapshot's objectForKey:"midiTriggerCommand") as integer) > 3 then error "One-byte MIDI trigger command."
     set currentIdentity to my runningQLab()
     if not (my sameSnapshot(currentIdentity, appIdentity)) then error "QLab process identity changed before native cue setter."
     set sent to true
     my nativeSet(c, propertyKey, payload, applicationPath)
     set snapshot to my nativeSnapshot(c, appIdentity)
     set observed to snapshot's objectForKey:propertyKey
    end if
   else
'''
_native_branch = _native_branch.replace('propertyKey is "triggerSnapshot" or payload\'s objectForKey:"expected_snapshot" is not missing value',
    'propertyKey is in {' + ', '.join('"' + key + '"' for key in ("triggerSnapshot", *_NATIVE_PROPERTIES)) + '}')
SCRIPT = SCRIPT.replace('   if propertyKey is "loadTime"', _native_branch + '   if propertyKey is "loadTime"', 1)
SCRIPT = SCRIPT.replace('  end tell\n  end using terms from\n  set currentIdentity',
                        '   end if\n  end tell\n  end using terms from\n  set currentIdentity', 1) + _handlers + SNAPSHOT_COMPARISON_HANDLER

# Read-only dictionary properties omitted or collapsed by OSC in QLab 5.5.10.
SCRIPT = SCRIPT.replace('   if propertyKey is "loadTime" and kind is "Load" then', '''   if propertyKey is "fadeAndStopOthers" or propertyKey is "sliceMarkers" then
    if ((payload's objectForKey:"write") as boolean) then error "Common fallback is read-only."
    if kind is not ((payload's objectForKey:"expected_type") as text) then error "Cue type changed."
    if propertyKey is "fadeAndStopOthers" then
     set observed to get fade and stop others of c
    else
     if kind is not "Video" and kind is not "Audio" then error "Slices require an Audio or Video cue."
     set markers to get slice markers of c
     if (count of markers) > 4096 then error "Slice inventory exceeds its bound."
     set observed to current application's NSMutableArray's array()
     repeat with marker in markers
      set row to current application's NSMutableDictionary's dictionary()
      row's setObject:(time of marker) forKey:"time"
      row's setObject:(playCount of marker) forKey:"playCount"
      observed's addObject:row
     end repeat
    end if
   else if propertyKey is "loadTime" and kind is "Load" then''', 1)


def _validate(key, value, *, observed=False):
    if key == "loadTime":
        if type(value) not in {int, float} or not math.isfinite(value):
            raise ValueError("loadTime requires finite seconds; negative values count back from the end.")
    elif key == "assignedNumber":
        if type(value) is not str or "\0" in value:
            raise ValueError("assignedNumber requires text without NUL.")
    elif key in TRIGGER_KEYS:
        if key in ENABLED_KEYS or key == "timecodeShowAsTimecode":
            valid = type(value) is bool
        elif key.endswith("String"):
            valid = type(value) is str and "\0" not in value
            if valid and not observed:
                match = re.fullmatch(r"[<>]?(\d{1,3})", value)
                valid = value == "any" or bool(match and int(match[1]) <= 127)
        else:
            limits = (-1, 16) if key == "midiTriggerChannel" else (0, 5) if key == "midiTriggerCommand" else (0, 127) if "Byte" in key else (0, 23) if key == "wallClockHours" else (0, 59)
            valid = type(value) is int and (observed and "Byte" in key or limits[0] <= value <= limits[1])
        if not valid:
            raise ValueError(f"{key}: invalid native trigger value.")
    else:
        raise ValueError("Unsupported fixed AppleScript property.")


def request(reader, workspace_id, cue_id, key, *, timeout=None, **change):
    config = reader.client.config
    if sys.platform != "darwin" or config.host not in {"127.0.0.1", "localhost", "::1"}:
        raise AppleScriptPreparationError("These properties require local macOS QLab; remote OSC has no AppleScript fallback.")
    try:
        ws, uid = str(UUID(str(workspace_id))).upper(), str(UUID(str(cue_id))).upper()
        common = key in COMMON_READ_KEYS
        native = key in TRIGGER_KEYS or key == "triggerSnapshot" or common
        if key not in KINDS and not native or set(change) - {
                "value", "expected", "expected_target", "assigned_cue_id", "expected_type",
                "expected_snapshot", "expected_application"}:
            raise ValueError("Unsupported fixed AppleScript operation.")
        if native and change.get("expected_type") not in _CUE_TYPES:
            raise ValueError("Native Triggers require an exact supported cue type.")
        writing = "value" in change
        if common and writing:
            raise ValueError("Common native fallback is read-only.")
        if "expected_application" in change and (not writing or key not in KINDS):
            raise ValueError("Application identity is only valid for confirmed scalar cue writes.")
        if writing:
            if not config.enable_write or not config.passcode:
                raise ValueError("Write mode and the existing OSC Edit access configuration are required.")
            _validate(key, change["value"])
            _validate(key, change.get("expected"), observed=True)
            if native:
                if key == "triggerSnapshot":
                    raise ValueError("Trigger snapshot is read-only.")
                snapshot = validate_trigger_snapshot(change.get("expected_snapshot"))
                trigger_preflight(snapshot, {key: change["value"]})
                if snapshot[key] != change["expected"]:
                    raise ValueError("Native baseline contradicts its snapshot.")
            else:
                _validate_application_identity(change.get("expected_application"))
                target = change.get("expected_target")
                if target != "":
                    change["expected_target"] = str(UUID(target)).upper()
            if key == "assignedNumber" and change["value"]:
                change["assigned_cue_id"] = str(UUID(change.get("assigned_cue_id"))).upper()
        payload = {"workspace_id": ws, "cue_id": uid, "property": key, "write": writing, **change}
        serialized = json.dumps(payload, allow_nan=False)
        bound = reader._bounded_read_timeout(timeout) if hasattr(reader, "_bounded_read_timeout") else timeout or config.timeout
        if type(bound) not in {int, float} or not math.isfinite(bound) or bound <= 0:
            raise ValueError("AppleScript requires a positive finite process timeout.")
    except (TypeError, ValueError, OverflowError, OscTimeoutError) as exc:
        raise AppleScriptPreparationError(f"AppleScript preparation failed: {exc}") from exc
    try:
        completed = subprocess.run(["/usr/bin/osascript", "-", serialized],
                                   input=SCRIPT, text=True, capture_output=True, timeout=bound, check=False)
    except subprocess.TimeoutExpired as exc:
        raise AppleScriptTimeoutError("AppleScript timed out; do not resend a setter. Read the property afresh.") from exc
    except OSError as exc:
        raise AppleScriptPreparationError("Could not start the fixed AppleScript bridge.") from exc
    if completed.returncode:
        error = QLabMcpError if writing else AppleScriptPreparationError
        raise error(f"AppleScript exited unexpectedly: {completed.stderr.strip()}")
    result = json.loads(completed.stdout)
    if not isinstance(result, dict):
        raise ValueError("Invalid AppleScript response.")
    if result.get("error"):
        error = QLabMcpError if result.get("sent") is True else AppleScriptPreparationError
        raise error(f"AppleScript: {result['error']} ({result.get('error_number')})")
    if result.get("workspace_id") != ws or result.get("cue_id") != uid or result.get("type") != (change["expected_type"] if native else KINDS[key]):
        raise ValueError("AppleScript workspace/cue identity or type mismatch.")
    value = result.get("value")
    if common:
        validate_common_value(key, value)
    elif key == "triggerSnapshot":
        validate_trigger_snapshot(value)
    else:
        _validate(key, value, observed=not writing)
    return value


def property_value(reader, ws, uid, key, value=None):
    """Use a current native getter only when an OSC baseline is unusable."""
    try:
        validate_common_value(key, value)
        return value
    except ValueError:
        kind = reader._request(f"/workspace/{ws}/cue_id/{uid}/type", workspace_id=ws).data
        if kind not in _CUE_TYPES:
            raise ValueError("Native fallback requires an exact cue type.")
        return request(reader, ws, uid, key, expected_type=kind)
