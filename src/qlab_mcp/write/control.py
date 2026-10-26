"""Typed mixed control-cue edits using the shared OSC and write primitives."""
from __future__ import annotations

from copy import deepcopy
import math
import re
import secrets
import threading
import time
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr, model_validator

from ..errors import OscPreparationError, OscTimeoutError, QLabReplyError
from .. import control_applescript
from ..models import CanonicalWorkspaceUUID
from ..cues.lists import _inventory
from ..osc.addressing import _workspace_address
from .registry import CONTROL_EDIT_TYPES, normalize_update_request
from .safety import check_write_readiness, ensure_write_ready, resolve_dry_run
from .timeouts import setter_reply_timeout, UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS
from .tokens import decode_confirm_token, encode_confirm_token
from .moves import _activity_snapshot, _read_snapshot

Number = StrictInt | Annotated[StrictFloat, Field(allow_inf_nan=False)]
Nonnegative = Annotated[Number, Field(ge=0)]
_SECRET = secrets.token_bytes(32)
_LOCK = threading.Lock()
_CONSUMED: dict[str, int] = {}
_TTL = 300
_BOOLS = {"armed", "flagged", "autoLoad", "skipIfDisarmed", "useSecondColor", "duckOthers", "secondTriggerOnRelease"}
_CONTEXT = ["uniqueID", "type", "parent", "hasCueTargets", "canHavePatchTargets", "allowsEditingDuration",
            "isRunning", "isPaused", "isAuditioning", "isBroken", "isWarning", "targetMode", "cueTargetID", "patchTargetID"]


class CueEditCommonProperties(control_applescript.NativeTriggerProperties):
    model_config = ConfigDict(extra="forbid")
    name: StrictStr | None = None
    number: StrictStr | None = None
    notes: StrictStr | None = None
    colorName: StrictStr | None = None
    secondColorName: StrictStr | None = None
    useSecondColor: StrictBool | None = None
    armed: StrictBool | None = None
    flagged: StrictBool | None = None
    autoLoad: StrictBool | None = None
    skipIfDisarmed: StrictBool | None = None
    preWait: Nonnegative | None = None
    postWait: Nonnegative | None = None
    continueMode: Annotated[StrictInt, Field(ge=0, le=2)] | None = None
    duckOthers: StrictBool | None = None
    duckLevel: Annotated[Number, Field(ge=-120, le=12)] | None = None
    duckTime: Nonnegative | None = None
    fadeAndStopOthers: Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    fadeAndStopOthersTime: Nonnegative | None = None
    secondTriggerAction: Annotated[StrictInt, Field(ge=0, le=5)] | None = None
    secondTriggerOnRelease: StrictBool | None = None
    timecode_text: StrictStr | None = Field(default=None, alias="timecodeTrigger/text")
    timecode_hours: Annotated[StrictInt, Field(ge=0, le=23)] | None = Field(default=None, alias="timecodeTrigger/hours")
    timecode_minutes: Annotated[StrictInt, Field(ge=0, le=59)] | None = Field(default=None, alias="timecodeTrigger/minutes")
    timecode_seconds: Annotated[StrictInt, Field(ge=0, le=59)] | None = Field(default=None, alias="timecodeTrigger/seconds")
    timecode_frames: Annotated[StrictInt, Field(ge=0, le=29)] | None = Field(default=None, alias="timecodeTrigger/frames")
    timecode_bits: Annotated[StrictInt, Field(ge=0, le=99)] | None = Field(default=None, alias="timecodeTrigger/bits")

    @model_validator(mode="after")
    def valid_changes(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Provide at least one property; explicit null values are not edits.")
        values = self.model_dump(by_alias=True, exclude_unset=True)
        control_applescript.validate_trigger_changes(values)
        for key in ("cueTargetID", "patchTargetID"):
            if key in values and values[key] != "":
                if str(UUID(values[key])).casefold() != values[key].casefold():
                    raise ValueError(f"{key} must be an exact UUID.")
        if values.get("patchTargetID") == "":
            raise ValueError("Patch target clearing is not enabled.")
        if "timecodeTrigger/text" in values and any(k.startswith("timecodeTrigger/") and k != "timecodeTrigger/text" for k in values):
            raise ValueError("Use Timecode text or components, not both.")
        return self


class ControlCueEditProperties(CueEditCommonProperties):
    loadTime: Number | None = None
    cueTargetID: StrictStr | None = None
    duration: Nonnegative | None = None
    patchTargetID: StrictStr | None = None
    targetMode: Annotated[StrictInt, Field(ge=0, le=1)] | None = None


class DevampCueEditProperties(CueEditCommonProperties):
    cueTargetID: StrictStr | None = None
    devampType: Annotated[StrictInt, Field(ge=1, le=2)] | None = None
    startNextCueWhenSliceEnds: StrictBool | None = None
    stopTargetWhenSliceEnds: StrictBool | None = None


class TargetCueEditProperties(CueEditCommonProperties):
    assignedNumber: StrictStr | None = None
    cueTargetID: StrictStr | None = None


class ControlCueEditInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cue_id: CanonicalWorkspaceUUID
    properties: ControlCueEditProperties
    confirm_gates: list[StrictStr] = Field(default_factory=list)


class DevampCueEditInput(ControlCueEditInput):
    properties: DevampCueEditProperties


class TargetCueEditInput(ControlCueEditInput):
    properties: TargetCueEditProperties


_FAMILIES = {
    "control": (ControlCueEditInput, ControlCueEditProperties, CONTROL_EDIT_TYPES, "control_basic", "qlab_edit_control_cues"),
    "devamp": (DevampCueEditInput, DevampCueEditProperties, ("Devamp",), "devamp_basic", "qlab_edit_devamp_cues"),
    "target": (TargetCueEditInput, TargetCueEditProperties, ("Target",), "target_basic", "qlab_edit_target_cues"),
}
_DEVAMP_FIELDS = {"devampType", "startNextCueWhenSliceEnds", "stopTargetWhenSliceEnds"}
_BOOLS.update({"startNextCueWhenSliceEnds", "stopTargetWhenSliceEnds"})


def _normalize(changes, family="control"):
    native = control_applescript.TRIGGER_KEYS & changes.keys()
    if native:
        return [op for key, value in changes.items() for op in (
            [{"property": key, "path": key, "transport": "applescript", "args": [value],
              "arg_values": {"value": value}, "real_write_enabled": True, "requires_confirm_token": True}]
            if key in native else _normalize({key: value}, family))]
    if family in {"video", "camera", "text"}:
        from .visual import normalize
        return normalize(changes, family)
    operations = []
    for key, value in changes.items():
        if key in control_applescript.KINDS:
            if (key, family) not in {("loadTime", "control"), ("assignedNumber", "target")}:
                raise ValueError("AppleScript property does not apply to this editor.")
            control_applescript._validate(key, value)
            operations.append({"property": key, "transport": "applescript", "args": [value]})
            continue
        profile = "group_basic" if family in {"group", "cue_list"} and (key in {"duration", "mode"} or key.startswith("playlist/") or key.startswith("timecode") and not key.startswith("timecodeTrigger/")) else "devamp_basic" if key in _DEVAMP_FIELDS else "control_basic"
        operations.extend(normalize_update_request(profile, {key: value}, None)[1])
    return operations


def control_edit_capabilities(kind, triggers=None, *, applescript_available=None):
    family = "devamp" if kind == "Devamp" else "target" if kind == "Target" else "control"
    _, properties_model, types, _, tool = _FAMILIES[family]
    if kind not in types:
        return {"tool": None, "reason": "Unsupported cue family."}
    allowed = [field.alias or name for name, field in properties_model.model_fields.items()]
    blocked = {"fadeAndStopOthers": "Requires integer scope readback; boolean cannot identify scope."}
    if triggers is not None and type(triggers.fadeAndStopOthers) is int:
        blocked = {}
    if kind in {"Wait", "Memo"}:
        allowed = [key for key in allowed if key not in {"cueTargetID", "patchTargetID", "targetMode"}]
    elif kind != "Reset":
        allowed = [key for key in allowed if key not in {"patchTargetID", "targetMode"}]
    if kind != "Wait":
        allowed = [key for key in allowed if key != "duration"]
    if kind != "Load":
        allowed = [key for key in allowed if key != "loadTime"]
    native = "loadTime" if kind == "Load" else "assignedNumber" if kind == "Target" else None
    if native and applescript_available is not True:
        blocked[native] = "Requires a fresh local AppleScript read, macOS Automation permission, and exactly one running QLab 5.5.10/build 5510 instance."
    return control_applescript.trigger_capabilities({"tool": tool, "allowed_properties": sorted(set(allowed) - blocked.keys()),
            "blocked_properties": blocked, "requires_fresh_preflight": True,
            "property_transports": {native: "applescript"} if native else {},
            "unavailable_via_osc": ["Load Time", "Hotkey/MIDI/Wall Clock setup", "Timecode activation/display", *(["Target Cue Number (assignedNumber)"] if kind == "Target" else [])],
            "pending_validation": []}, triggers)


def _same(actual, wanted):
    if isinstance(actual, bool) or isinstance(wanted, bool):
        return type(actual) is type(wanted) and actual == wanted
    if isinstance(actual, (int, float)) and isinstance(wanted, (int, float)):
        return math.isfinite(actual) and math.isclose(actual, wanted, rel_tol=1e-6, abs_tol=1e-5)
    if isinstance(actual, dict) and isinstance(wanted, dict):
        return actual.keys() == wanted.keys() and all(_same(actual[k], wanted[k]) for k in actual)
    if isinstance(actual, list) and isinstance(wanted, list):
        return len(actual) == len(wanted) and all(_same(a, b) for a, b in zip(actual, wanted, strict=True))
    return type(actual) is type(wanted) and actual == wanted


def _read(reader, ws, uid, keys, family="control", changes=None):
    native = control_applescript.TRIGGER_KEYS & set(keys)
    if native:
        values = _read(reader, ws, uid, [key for key in keys if key not in native], family, changes)
        snapshot = control_applescript.trigger_snapshot(reader, ws, uid, values["type"])
        values.update({key: snapshot[key] for key in native})
        return values
    if family in {"video", "camera", "text"}:
        from .visual import read
        return read(reader, ws, uid, keys, changes)
    if family in {"audio", "mic", "light", "fade", "network", "midi", "midi_file", "timecode", "script"}:
        from .remaining import read
        return read(reader, ws, uid, keys, changes)
    from .operations import _try_read_update_values
    native_keys = [key for key in keys if key in control_applescript.KINDS]
    values, errors = _try_read_update_values(reader, ws, uid, [key for key in keys if key not in native_keys])
    if errors or not values or str(values.get("uniqueID", "")).upper() != uid:
        raise ValueError("Fresh cue identity could not be verified.")
    if "fadeAndStopOthers" in keys:
        values["fadeAndStopOthers"] = _scalar(reader, ws, uid, "fadeAndStopOthers")
    for key in native_keys:
        if values.get("type") != control_applescript.KINDS[key]:
            raise ValueError(f"{key} does not apply to this cue type.")
        values[key] = control_applescript.request(reader, ws, uid, key)
    return values


def _scalar(reader, ws, uid, key):
    return reader._request(_workspace_address(ws, f"cue_id/{uid}/{key}"), workspace_id=ws).data


def _script_dependencies(reader, ws, uid, before, changes):
    app_identity = control_applescript.trigger_snapshot(reader, ws, uid, before["type"])["app_identity"]
    receiver = before.get("cueTargetID")
    if type(receiver) is not str:
        raise ValueError("AppleScript cueTargetID must be readable; unknown is not an empty target.")
    receiver = str(UUID(receiver)).upper() if receiver else ""
    context = {"app_identity": app_identity, "cueTargetID": receiver}
    if receiver:
        resolved = _read(reader, ws, str(UUID(receiver)).upper(),
                         ["uniqueID", "type", "hasCueTargets", "isRunning", "isPaused", "isAuditioning"])
        if any(resolved.get(k) is not False for k in ("isRunning", "isPaused", "isAuditioning")):
            raise ValueError("AppleScript target must be inactive.")
        if "assignedNumber" in changes and (resolved.get("hasCueTargets") is not True or resolved.get("type") == "Fade"):
            raise ValueError("Target receiver must accept cue targets; Fade is excluded.")
        context["receiver"] = resolved
    if changes.get("assignedNumber"):
        matches = [node for node in _read_snapshot(reader, ws)["nodes"].values()
                   if node.get("number") == changes["assignedNumber"]]
        if len(matches) != 1:
            raise ValueError("assignedNumber must resolve to one existing cue in this workspace.")
        assigned = str(matches[0]["uniqueID"]).upper()
        if assigned in {uid, str(receiver).upper()}:
            raise ValueError("Assignment cannot target this Target cue or its receiver itself.")
        context["assigned"] = _read(reader, ws, assigned, ["uniqueID", "type", "number", "isRunning", "isPaused", "isAuditioning"])
        if context["assigned"].get("number") != changes["assignedNumber"] or any(
                context["assigned"].get(k) is not False for k in ("isRunning", "isPaused", "isAuditioning")):
            raise ValueError("Assigned cue identity, number and inactivity must be readable.")
    return context


def _timecode_format(reader, ws, uid):
    values = _read(reader, ws, uid, ["uniqueID", "type", "timecodeSMPTEFormat"])
    fmt = values.get("timecodeSMPTEFormat")
    if values.get("type") not in {"Cue List", "Cue Cart", "Cart"} or type(fmt) is not int or fmt not in range(4):
        raise ValueError("Containing list SMPTE format is unavailable.")
    return fmt


def _timecode(reader, ws, before, changes):
    roots = {str(x["uniqueID"]).upper() for x in _inventory(reader, ws)}
    parent = str(before.get("parent", "")).upper()
    seen = set()
    while parent not in roots:
        if not parent or parent in seen or len(seen) >= 100:
            raise ValueError("Timecode containing list cannot be verified.")
        seen.add(parent)
        parent = str(_read(reader, ws, parent, ["uniqueID", "parent"])["parent"]).upper()
    fmt = _timecode_format(reader, ws, parent)
    aggregate = _scalar(reader, ws, str(before["uniqueID"]).upper(), "timecodeTrigger")
    if not isinstance(aggregate, dict):
        raise ValueError("Timecode baseline is unavailable.")
    parts = {key: aggregate.get(key) for key in ("hours", "minutes", "seconds", "frames", "bits")}
    if "timecodeTrigger/text" in changes:
        match = re.fullmatch(r"(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})(?:\.(\d{2}))?", changes["timecodeTrigger/text"])
        if not match:
            raise ValueError("Use Timecode hours:minutes:seconds:frames, optionally .bits.")
        parts.update(zip(parts, [int(x or 0) for x in match.groups()], strict=True))
    else:
        parts.update({key.split("/")[1]: value for key, value in changes.items() if key.startswith("timecodeTrigger/")})
    fps = (24, 25, 30, 30)[fmt]
    limits = (24, 60, 60, fps, 100)
    if any(type(value) is not int or not 0 <= value < limit for value, limit in zip(parts.values(), limits, strict=True)):
        raise ValueError("Timecode components are outside the containing list format.")
    if fmt == 2 and parts["minutes"] % 10 and parts["seconds"] == 0 and parts["frames"] < 2:
        raise ValueError("Timecode selects a skipped drop-frame label.")
    return {"list_id": parent, "format": fmt, "timecode_baseline": deepcopy(aggregate)}


def _preflight(reader, ws, item, family="control", *, _core=False):
    before, changes, operations, dependencies = _family_preflight(reader, ws, item, family, _core=_core)
    if not _core and control_applescript.TRIGGER_KEYS & changes.keys():
        snapshot = control_applescript.trigger_snapshot(reader, ws, str(item.cue_id).upper(), before["type"])
        control_applescript.trigger_preflight(snapshot, changes)
        if any(before.get(key) != snapshot[key] for key in control_applescript.TRIGGER_KEYS & changes.keys()):
            raise ValueError("Native trigger baseline changed during preflight.")
        dependencies["native_triggers"] = snapshot
        if {"timecodeTriggerEnabled", "timecodeShowAsTimecode"} & changes.keys():
            dependencies["timecode"] = _timecode(reader, ws, before, {})
    return before, changes, operations, dependencies


def _family_preflight(reader, ws, item, family="control", *, _core=False):
    if not _core and family in {"audio", "mic", "light", "fade", "network", "midi", "midi_file", "timecode", "script"}:
        from .remaining import preflight
        return preflight(reader, ws, item, family)
    if family in {"video", "camera", "text"}:
        from .visual import preflight
        return preflight(reader, ws, item, family)
    if family == "group" and not _core:
        from .group import preflight
        return preflight(reader, ws, item)
    if family == "cue_list" and not _core:
        from .cue_lists import preflight
        return preflight(reader, ws, item)
    uid = str(item.cue_id).upper()
    changes = item.properties.model_dump(by_alias=True, exclude_unset=True)
    native = control_applescript.KINDS.keys() & changes.keys()
    if native and "cueTargetID" in changes:
        raise ValueError("Change cueTargetID separately, then run a new dry run for the AppleScript property.")
    if "cueTargetID" in changes and "patchTargetID" in changes:
        raise ValueError("Choose a cue target or patch target, not both.")
    implicit = 1 if "patchTargetID" in changes else 0 if "cueTargetID" in changes else None
    if implicit is not None:
        if changes.get("targetMode", implicit) != implicit:
            raise ValueError("Target UUID contradicts targetMode.")
    before = _read(reader, ws, uid, list(dict.fromkeys([*_CONTEXT, *(_DEVAMP_FIELDS if family == "devamp" else []), *(["mode", "secondTriggerAction"] if family == "group" else []), *changes])))
    kind = before.get("type")
    if kind not in _FAMILIES[family][2]:
        raise ValueError(f"{_FAMILIES[family][4]} accepts only {_FAMILIES[family][2]}.")
    if any(before.get(k) is not False for k in ("isRunning", "isPaused", "isAuditioning")):
        raise ValueError("Source cue must be inactive.")
    if "duration" in changes and before.get("allowsEditingDuration") is not True:
        raise ValueError("This cue has no editable duration.")
    targets = {"cueTargetID", "patchTargetID", "targetMode"} & changes.keys()
    if targets and kind in {"Wait", "Memo"}:
        raise ValueError("Wait and Memo cannot have targets.")
    if targets and kind != "Reset" and ("patchTargetID" in changes or changes.get("targetMode", 0) != 0):
        raise ValueError("Only Reset can target a patch.")
    if "cueTargetID" in changes and before.get("hasCueTargets") is not True:
        raise ValueError("Cue target capability is unavailable.")
    if implicit is not None and kind == "Reset" and before.get("targetMode") != implicit:
        changes["targetMode"] = implicit
    dependencies = {}
    if native:
        dependencies["applescript"] = _script_dependencies(reader, ws, uid, before, changes)
    target = changes.get("cueTargetID", before.get("cueTargetID"))
    mode = changes.get("targetMode", before.get("targetMode", 0))
    if family == "devamp" and _DEVAMP_FIELDS & changes.keys():
        if not target:
            raise ValueError("Devamp settings require a valid Audio/Video cue target.")
        targets.add("cueTargetID")
        start_next = changes.get("startNextCueWhenSliceEnds", before.get("startNextCueWhenSliceEnds"))
        stop_target = changes.get("stopTargetWhenSliceEnds", before.get("stopTargetWhenSliceEnds"))
        if stop_target is True and start_next is not True:
            raise ValueError("Stopping the Devamp target requires Start next enabled.")
    if targets and mode == 0 and target:
        target = str(UUID(target)).upper()
        if target == uid:
            raise ValueError("A cue cannot target itself.")
        resolved = _read(reader, ws, target, ["uniqueID", "type", "isBroken", "isWarning", "isRunning", "isPaused", "isAuditioning"])
        if any(resolved.get(k) is not False for k in ("isBroken", "isWarning", "isRunning", "isPaused", "isAuditioning")):
            raise ValueError("Target health and inactivity cannot be verified.")
        if family == "devamp" and resolved["type"] not in {"Audio", "Video"}:
            raise ValueError("Devamp must target an Audio or Video cue.")
        if family == "target":
            resolved["hasCueTargets"] = _scalar(reader, ws, target, "hasCueTargets")
            if resolved["type"] == "Fade" or resolved["hasCueTargets"] is not True:
                raise ValueError("Target must target a cue accepting cue targets; Fade is excluded.")
        dependencies["target"] = resolved
    if targets and mode == 1:
        patch = changes.get("patchTargetID", before.get("patchTargetID"))
        if not patch or before.get("canHavePatchTargets") is not True:
            raise ValueError("Reset patch capability or target is unavailable.")
        inventory = reader._request(_workspace_address(ws, "settings/audio/patchList"), workspace_id=ws).data
        from ..settings.summarizers import _collection_items
        if not any(str(x.get("uniqueID", "")).casefold() == patch.casefold() for x in _collection_items(inventory)):
            raise ValueError("Patch UUID is absent from the workspace audio output inventory.")
        resolved = reader._request(_workspace_address(ws, f"settings/audio/patchID/{patch}"), workspace_id=ws).data
        if not isinstance(resolved, dict) or str(resolved.get("uniqueID", "")).casefold() != patch.casefold():
            raise ValueError("Patch identity could not be verified.")
        dependencies["patch"] = {key: resolved.get(key) for key in ("uniqueID", "name", "deviceID")}
    if "number" in changes and changes["number"]:
        nodes = _read_snapshot(reader, ws)["nodes"].values()
        if any(node.get("number") == changes["number"] and str(node["uniqueID"]).upper() != uid for node in nodes):
            raise ValueError("Cue number is unavailable or already assigned.")
    if any(key.startswith("timecodeTrigger/") for key in changes):
        dependencies["timecode"] = _timecode(reader, ws, before, changes)
    operations = _normalize(changes, family)
    operations.sort(key=lambda op: op["property"] != "targetMode")
    for op in operations:
        key = op["property"]
        if key not in before:
            before[key] = _scalar(reader, ws, uid, key)
        value = before[key]
        if value is None:
            raise ValueError(f"{key}: baseline is unavailable.")
        if key == "fadeAndStopOthers" and type(value) is not int:
            raise ValueError("Fade & Stop scope is not reliably readable; boolean is not a mode.")
        if key in _BOOLS and type(value) is not bool:
            raise ValueError(f"{key}: expected boolean baseline.")
        # Validate observed values with the same scalar validators as requests.
        if key not in control_applescript.TRIGGER_KEYS and not (key == "patchTargetID" and value == ""):
            _normalize({key: value}, family)
    return before, changes, operations, dependencies


def _batch_dependency_conflict(bindings):
    for binding in bindings:
        dependencies = binding['dependencies']
        for cue, values in dependencies.get('cues', {}).items():
            other = next((candidate for candidate in bindings
                          if candidate['cue_id'] == cue and candidate is not binding), None)
            if other and values.keys() & other['properties'].keys():
                return 'Separate edits to cues used as batch dependencies.'
        for cue, values in dependencies.get('light_pull_sources', {}).items():
            other = next((candidate for candidate in bindings
                          if candidate['cue_id'] == cue and candidate is not binding), None)
            if other:
                changed_source_fields = {'number'}
                if 'text_sha256' in values:
                    changed_source_fields.add('lightCommandText')
                if changed_source_fields & other['properties'].keys():
                    return 'Separate edits to cues used as batch dependencies.'
        pull_numbers = set(dependencies.get('light_pull_number_index', {}).get('numbers', ()))
        if pull_numbers:
            for candidate in bindings:
                changes = candidate['properties']
                if 'number' in changes and any(
                    str(value) in pull_numbers
                    for value in (candidate['before'].get('number'), changes['number'])
                ):
                    return 'Separate cue number changes that affect Light cue pulls.'
    return None


def edit_control_cues(reader, workspace_id, updates, dry_run=None, *, _family="control"):
    deadline = time.monotonic() + UPDATE_REAL_WRITE_SOFT_BUDGET_SECONDS
    input_model, _, _, profile, tool = _FAMILIES[_family]
    remaining_family = _family in {"audio", "mic", "light", "fade", "network", "midi", "midi_file", "timecode", "script"}
    items = [input_model.model_validate(x.model_dump(by_alias=True, exclude_unset=True) if isinstance(x, BaseModel) else x) for x in updates]
    ids = [str(x.cue_id).upper() for x in items]
    if not 1 <= len(items) <= 50 or len(set(ids)) != len(ids):
        raise ValueError("updates requires 1–50 distinct cue UUIDs.")
    numbers = [x.properties.number for x in items if x.properties is not None and x.properties.number]
    if len(numbers) != len(set(numbers)):
        raise ValueError("Requested cue numbers must be unique within the batch.")
    ws = str(UUID(str(workspace_id))).upper()
    dry = resolve_dry_run(reader, dry_run)
    results = [{"cue_ref": uid, "cue_id": uid, "profile": profile, "status": "planned",
                "properties": {}, "operations": [], "planned_operations": [], "executed_operations": [],
                "before": None, "after": None, "errors": None, "warnings": []} for uid in ids]
    bindings = []

    def finish(status):
        updated = sum(x["status"] in {"updated", "updated_with_confirmed_timeouts"} for x in results)
        success = status in {"dry_run", "updated", "updated_with_confirmed_timeouts"}
        return {"ok": success, "status": status, "workspace_id": ws, "dry_run": dry,
                "requested_count": len(items), "planned_count": sum(bool(x["planned_operations"]) for x in results),
                "updated_count": updated, "failed_count": sum(bool(x["errors"]) for x in results),
                "timeout_confirmed_count": sum(x["status"] == "updated_with_confirmed_timeouts" for x in results),
                "results": results, "errors": None if success else {"batch": "Inspect per-cue errors; pending operations were not sent."},
                "warnings": ["Sequential, non-atomic edits; no automatic rollback or setter retry."], "message": status}

    try:
        resolved = reader._resolve_workspace_id_strict(ws)
        if str(resolved).upper() != ws:
            raise ValueError("Workspace identity mismatch.")
        readiness = check_write_readiness(reader, ws)
        if not readiness.get("ok"):
            raise ValueError(readiness.get("message", "Edit access required."))
        if _activity_snapshot(reader, ws)["active_count"]:
            raise ValueError("Workspace has running or paused cues.")
    except Exception as exc:
        results[0].update(status="preflight_failed", errors={"preflight": str(exc)})
        return finish("preflight_failed")
    for item, result in zip(items, results, strict=True):
        try:
            if time.monotonic() >= deadline:
                raise ValueError("Batch time budget exhausted before planning.")
            before, changes, operations, dependencies = _preflight(reader, ws, item, _family)
            result.update(before=before, properties=changes, operations=operations,
                          diff={key: {"before": before[key], "requested": value} for key, value in changes.items()})
            binding = {"tool": tool, "workspace_id": ws, "cue_id": result["cue_id"], "before": before,
                       "properties": changes, "dependencies": dependencies}
            bindings.append(binding)
            for op in operations:
                plan = {"operation": "set_property", "property": op["property"], "key": op.get("key", op["property"]),
                        "address": None if op.get("transport") == "applescript" else _workspace_address(ws, f"cue_id/{result['cue_id']}/{op['path']}"),
                        "args": op["args"], "status": "planned"}
                if op.get("transport") == "applescript":
                    plan["transport"] = "applescript"
                result["planned_operations"].append(plan)
            result["status"] = "dry_run" if dry else "planned"
        except Exception as exc:
            result.update(status="dry_run_preflight_failed" if dry else "preflight_failed", errors={"preflight": str(exc)})
    if any(x["errors"] for x in results):
        return finish("preflight_failed")
    for binding in bindings:
        assigned = binding["dependencies"].get("applescript", {}).get("assigned")
        if assigned and any(b["cue_id"] == str(assigned["uniqueID"]).upper() and "number" in b["properties"] for b in bindings):
            results[0].update(status="preflight_failed", errors={"dependencies": "Renumber assigned cues separately, then run a new dry run."})
            return finish("preflight_failed")
    if remaining_family:
        conflict = _batch_dependency_conflict(bindings)
        if conflict:
            results[0].update(status="preflight_failed", errors={"dependencies": conflict})
            return finish("preflight_failed")
    if dry:
        for result, binding in zip(results, bindings, strict=True):
            for plan in result["planned_operations"]:
                payload = {
                    **binding,
                    "property": plan.get("key", plan["property"]),
                    "expires_at": int(time.time()) + _TTL,
                    "nonce": secrets.token_urlsafe(12),
                }
                plan["confirm_token"] = encode_confirm_token("controlCue", 1, payload, _SECRET)
        return finish("dry_run")
    tokens = []
    try:
        for item, result, binding in zip(items, results, bindings, strict=True):
            payloads = {}
            for token in item.confirm_gates:
                payload, error = decode_confirm_token(token, "controlCue", 1, _SECRET)
                if error or not payload or type(payload.get("expires_at")) is not int or payload["expires_at"] <= int(time.time()):
                    raise ValueError("Confirmation invalid or expired; run a new dry run.")
                if any(payload.get(k) != v for k, v in binding.items()) or payload.get("property") in payloads:
                    raise ValueError("Confirmation baseline, property or dependencies changed.")
                payloads[payload.get("property")] = (token, payload)
            if set(payloads) != set(result["properties"]):
                raise ValueError("Provide exactly one confirmation for every planned setter.")
            tokens.extend(payloads.values())
        ensure_write_ready(reader, ws)
        if _activity_snapshot(reader, ws)["active_count"]:
            raise ValueError("Workspace activity changed before mutation.")
        for item, binding in zip(items, bindings, strict=True):
            before, changes, _, dependencies = _preflight(reader, ws, item, _family)
            if before != binding["before"] or changes != binding["properties"] or dependencies != binding["dependencies"]:
                raise ValueError("Fresh baseline or target dependencies changed; run a new dry run.")
        with _LOCK:
            now = int(time.time())
            for token in list(_CONSUMED):
                if _CONSUMED[token] <= now:
                    del _CONSUMED[token]
            if any(token in _CONSUMED or payload["expires_at"] <= now for token, payload in tokens):
                raise ValueError("Confirmation expired or already reserved; run a new dry run.")
            _CONSUMED.update({token: payload["expires_at"] for token, payload in tokens})
    except Exception as exc:
        results[0].update(status="preflight_failed", errors={"confirmation": str(exc)})
        return finish("preflight_failed")
    for result, binding in zip(results, bindings, strict=True):
        confirmed_timeout = False
        for plan in result["planned_operations"]:
            key = plan.get("key", plan["property"])
            attempted = False
            setter_error = None
            try:
                if time.monotonic() >= deadline:
                    raise ValueError("Batch time budget exhausted; pending setters were not sent.")
                ensure_write_ready(reader, ws)
                fresh = _read(reader, ws, result["cue_id"], ["uniqueID", "type", key], _family, result["properties"])
                expected = result["before"][key]
                if result["after"]:
                    expected = result["after"].get(key, expected)
                if _family in {"video", "camera", "text"}:
                    from . import visual
                    hook = getattr(visual, "expected_before_setter", None)
                    if hook is not None:
                        expected = hook(key, binding["dependencies"], expected)
                if fresh.get("type") != result["before"]["type"] or not _same(fresh.get(key), expected):
                    raise ValueError("Property changed immediately before setter.")
                if _activity_snapshot(reader, ws)["active_count"]:
                    raise ValueError("Workspace became active before setter.")
                target_dependency = binding["dependencies"].get("target")
                if (key in {"cueTargetID", "targetMode"} or key in _DEVAMP_FIELDS) and target_dependency:
                    target_now = _read(reader, ws, str(target_dependency["uniqueID"]).upper(), list(target_dependency))
                    if target_now != target_dependency:
                        raise ValueError("Target dependency changed before setter.")
                patch_dependency = binding["dependencies"].get("patch")
                if key in {"patchTargetID", "targetMode"} and patch_dependency:
                    patch_now = reader._request(_workspace_address(ws, f"settings/audio/patchID/{patch_dependency['uniqueID']}"), workspace_id=ws).data
                    if not isinstance(patch_now, dict) or {k: patch_now.get(k) for k in patch_dependency} != patch_dependency:
                        raise ValueError("Patch dependency changed before setter.")
                if key.startswith("timecodeTrigger/") or key in {"timecodeTriggerEnabled", "timecodeShowAsTimecode"}:
                    context = binding["dependencies"]["timecode"]
                    current_parent = _read(reader, ws, result["cue_id"], ["uniqueID", "parent"])
                    current_context = _timecode(reader, ws, current_parent, result["properties"])
                    if (current_context["list_id"] != context["list_id"] or
                            current_context["format"] != context["format"] or
                            current_context["timecode_baseline"] != context["timecode_baseline"]):
                        raise ValueError("Containing list or Timecode baseline changed before setter.")
                if _family == "group":
                    from .group import check_dependencies
                    check_dependencies(reader, ws, result["cue_id"], binding["dependencies"])
                if _family == "cue_list":
                    from .cue_lists import check_dependencies
                    check_dependencies(reader, ws, result["cue_id"], binding["dependencies"])
                if _family in {"video", "camera", "text"}:
                    from .visual import check_dependencies
                    check_dependencies(reader, ws, result["cue_id"], binding["dependencies"])
                if remaining_family:
                    from .remaining import check_dependencies
                    check_dependencies(reader, ws, result["cue_id"], binding["dependencies"])
                native_snapshot = binding["dependencies"].get("native_triggers")
                if native_snapshot is not None:
                    if control_applescript.trigger_snapshot(reader, ws, result["cue_id"], result["before"]["type"]) != native_snapshot:
                        raise ValueError("Native trigger or safety dependency changed before setter.")
                if plan.get("transport") == "applescript" and key not in control_applescript.TRIGGER_KEYS:
                    target_now = _read(reader, ws, result["cue_id"], ["uniqueID", "type", "cueTargetID"])
                    if _script_dependencies(reader, ws, result["cue_id"], target_now, result["properties"]) != binding["dependencies"]["applescript"]:
                        raise ValueError("AppleScript target or assigned cue dependency changed before setter.")
                if time.monotonic() >= deadline:
                    raise ValueError("Batch time budget exhausted; pending setters were not sent.")
                attempted = True
                timeout = False
                setter_error = None
                try:
                    if plan.get("transport") == "applescript":
                        if key in control_applescript.TRIGGER_KEYS:
                            context = {"expected_snapshot": native_snapshot, "expected_type": result["before"]["type"]}
                        else:
                            dependency = binding["dependencies"]["applescript"]
                            context = {"expected_target": dependency["cueTargetID"],
                                       "expected_application": dependency["app_identity"],
                                       "assigned_cue_id": dependency.get("assigned", {}).get("uniqueID")}
                        control_applescript.request(reader, ws, result["cue_id"], key, value=plan["args"][0],
                            expected=expected, **context, timeout=min(reader.client.config.timeout, max(0.01, deadline - time.monotonic())))
                    else:
                        reader._request(plan["address"], *plan["args"], workspace_id=ws,
                                    request_timeout=min(max(0.01, deadline - time.monotonic()), setter_reply_timeout(reader, sum(len(x["operations"]) for x in results))),
                                    ensure_always_reply=True, allow_empty_data=True)
                except (OscPreparationError, control_applescript.AppleScriptPreparationError):
                    attempted = False
                    raise
                except Exception as exc:
                    timeout = isinstance(exc, (OscTimeoutError, control_applescript.AppleScriptTimeoutError))
                    setter_error = exc
                result["executed_operations"].append({**plan, "status": "sent", "reply_error": str(setter_error) if setter_error else None})
                attempted = False
                verification_keys = [key] if remaining_family or _family in {"video", "camera", "text"} else list(result["properties"])
                after = _read(reader, ws, result["cue_id"], ["uniqueID", "type", *verification_keys], _family, result["properties"])
                if remaining_family and binding["dependencies"].get("selector"):
                    from .remaining import selector_snapshot
                    selector = binding["dependencies"]["selector"]
                    after["selector_effects"] = selector_snapshot(reader, ws, result["cue_id"], _family, selector["property"])
                result["after"] = {**(result["after"] or {}), **after}
                matched = _same(after.get(key), result["properties"][key] if remaining_family or _family in {"video", "camera", "text"} else plan["args"][0])
                if remaining_family:
                    from .remaining import matches
                    matched = matches(key, after.get(key), result["properties"][key], binding["dependencies"], reader, ws, result["cue_id"])
                if _family in {"video", "camera", "text"}:
                    from .visual import matches
                    matched = matches(key, after.get(key), result["properties"][key], binding["dependencies"], reader, ws, result["cue_id"])
                if key == "timecodeTrigger/text" and isinstance(after.get(key), str):
                    pattern = r"(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})(?:\.(\d{2}))?"
                    observed, requested = re.fullmatch(pattern, after[key]), re.fullmatch(pattern, plan["args"][0])
                    matched = bool(observed and requested and tuple(int(x or 0) for x in observed.groups()) == tuple(int(x or 0) for x in requested.groups()))
                if after.get("type") != result["before"]["type"] or not matched:
                    raise ValueError("Setter verification failed; no retry was sent.")
                if native_snapshot is not None:
                    snapshot_after = control_applescript.trigger_snapshot(reader, ws, result["cue_id"], result["before"]["type"])
                    allowed_changes = {key}
                    if key in {"midiTriggerByte1", "midiTriggerByte2"}:
                        allowed_changes.add(key + "String")
                    if key in {"midiTriggerByte1String", "midiTriggerByte2String"}:
                        allowed_changes.add(key.removesuffix("String"))
                    result["after"]["native_trigger_snapshot"] = snapshot_after
                    if any(snapshot_after[k] != v for k, v in native_snapshot.items() if k not in allowed_changes):
                        raise ValueError("Unexpected native trigger side effects; pending setters were not sent.")
                    binding["dependencies"]["native_triggers"] = snapshot_after
                if key.startswith("timecodeTrigger/"):
                    aggregate = _scalar(reader, ws, result["cue_id"], "timecodeTrigger")
                    if not isinstance(aggregate, dict):
                        raise ValueError("Fresh Timecode aggregate readback is unavailable.")
                    binding["dependencies"]["timecode"]["timecode_baseline"] = deepcopy(aggregate)
                if _family == "group":
                    from .group import verify_children
                    verify_children(reader, ws, result["cue_id"], plan, binding["dependencies"])
                if setter_error and not timeout:
                    raise ValueError(f"Setter returned an error despite matching readback: {setter_error}")
                if remaining_family and binding["dependencies"].get("selector"):
                    binding["dependencies"]["selector"]["snapshot"] = after["selector_effects"]
                plan["status"] = "confirmed_after_timeout" if timeout else "verified"
                confirmed_timeout |= timeout
            except Exception as exc:
                if attempted:
                    result["executed_operations"].append({**plan, "status": "uncertain"})
                plan["status"] = "failed"
                rejected_without_change = (
                    isinstance(setter_error, QLabReplyError)
                    and isinstance(result["after"], dict)
                    and key in result["before"]
                    and _same(result["after"].get(key), result["before"][key])
                )
                status = "verification_failed" if rejected_without_change else (
                    "verification_inconclusive" if result["executed_operations"] else "preflight_failed"
                )
                error = (f"QLab rejected the setter ({setter_error}); fresh readback is unchanged. No retry was sent."
                         if rejected_without_change else str(exc))
                result.update(status=status, errors={key: error})
                prior_success = any(
                    operation.get("status") in {"verified", "confirmed_after_timeout"}
                    for item_result in results for operation in item_result["planned_operations"]
                )
                batch_status = ("partial_failed" if prior_success else "verification_failed") if rejected_without_change else (
                    "partial_failed" if any(x["executed_operations"] for x in results) else "preflight_failed"
                )
                return finish(batch_status)
        result["status"] = "updated_with_confirmed_timeouts" if confirmed_timeout else "updated"
    return finish("updated_with_confirmed_timeouts" if any(x["status"] == "updated_with_confirmed_timeouts" for x in results) else "updated")


def edit_devamp_cues(reader, workspace_id, updates, dry_run=None):
    return edit_control_cues(reader, workspace_id, updates, dry_run, _family="devamp")


def edit_target_cues(reader, workspace_id, updates, dry_run=None):
    return edit_control_cues(reader, workspace_id, updates, dry_run, _family="target")
