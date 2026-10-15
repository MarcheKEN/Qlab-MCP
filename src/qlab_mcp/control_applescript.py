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


def validate_trigger_snapshot(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != TRIGGER_KEYS | {"armed", "continueMode", "skipIfDisarmed", "timecodeTrigger"}:
        raise ValueError("Complete native trigger snapshot is unavailable.")
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
on run argv
 set sent to false
 set output to current application's NSMutableDictionary's dictionary()
 try
  set raw to current application's NSString's stringWithString:(item 1 of argv)
  set payload to current application's NSJSONSerialization's JSONObjectWithData:(raw's dataUsingEncoding:(current application's NSUTF8StringEncoding)) options:0 |error|:(missing value)
  set wsid to (payload's objectForKey:"workspace_id") as text
  set uid to (payload's objectForKey:"cue_id") as text
  set propertyKey to (payload's objectForKey:"property") as text
  set apps to current application's NSRunningApplication's runningApplicationsWithBundleIdentifier:"com.figure53.QLab.5"
  if (apps's |count|() as integer) is not 1 then error "Exactly one local QLab instance must already be running."
  if (((apps's firstObject())'s bundleURL()'s |path|()) as text) is not "/Applications/QLab.app" then error "The running QLab must be /Applications/QLab.app."
  tell application "/Applications/QLab.app"
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

# Build only from this fixed dictionary, never from request text or property paths.
_snapshot_lines = []
_setter_lines = []
for _key, _property in _NATIVE_PROPERTIES.items():
    _expression = f"({_property} of c is enabled)" if _key in ENABLED_KEYS else f"{_property} of c"
    if _key == "midiTriggerCommand":
        _expression = "my midiCommandNumber(midi command of c)"
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
on midiCommandNumber(cmd)
 tell application "/Applications/QLab.app"
  set commands to {note_off, note_on, key_pressure, control_change, program_change, channel_pressure}
  repeat with n from 1 to count of commands
   if cmd is item n of commands then return n - 1
  end repeat
  error "Unsupported MIDI trigger command."
 end tell
end midiCommandNumber
on nativeSnapshot(c)
 set output to current application's NSMutableDictionary's dictionary()
 tell application "/Applications/QLab.app"
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
 return output
end nativeSnapshot
on nativeSet(c, propertyKey, payload)
 tell application "/Applications/QLab.app"
''' + "\n".join(_setter_lines) + '''
 else
  error "Unsupported fixed native trigger setter."
 end if
 end tell
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
    set snapshot to my nativeSnapshot(c)
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
     set sent to true
     my nativeSet(c, propertyKey, payload)
     set snapshot to my nativeSnapshot(c)
     set observed to snapshot's objectForKey:propertyKey
    end if
   else
'''
_native_branch = _native_branch.replace('propertyKey is "triggerSnapshot" or payload\'s objectForKey:"expected_snapshot" is not missing value',
    'propertyKey is in {' + ', '.join('"' + key + '"' for key in ("triggerSnapshot", *_NATIVE_PROPERTIES)) + '}')
SCRIPT = SCRIPT.replace('   if propertyKey is "loadTime"', _native_branch + '   if propertyKey is "loadTime"', 1)
SCRIPT = SCRIPT.replace('  end tell\n  output', '   end if\n  end tell\n  output', 1) + _handlers + SNAPSHOT_COMPARISON_HANDLER


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
        native = key in TRIGGER_KEYS or key == "triggerSnapshot"
        if key not in KINDS and not native or set(change) - {"value", "expected", "expected_target", "assigned_cue_id", "expected_type", "expected_snapshot"}:
            raise ValueError("Unsupported fixed AppleScript operation.")
        if native and change.get("expected_type") not in _CUE_TYPES:
            raise ValueError("Native Triggers require an exact supported cue type.")
        writing = "value" in change
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
    if key == "triggerSnapshot":
        validate_trigger_snapshot(value)
    else:
        _validate(key, value, observed=not writing)
    return value
