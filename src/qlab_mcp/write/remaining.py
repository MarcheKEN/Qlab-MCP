"""Typed family adapters over the existing gated cue executors."""
from __future__ import annotations

from typing import Annotated, Literal, Union, get_args
import hashlib
import json
import math
import os
import re
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictBool, StrictInt, StrictStr, create_model, model_validator

from . import control
from .control import CueEditCommonProperties, ControlCueEditInput, Number, Nonnegative
from .registry import UPDATE_PROFILES, normalize_update_request
from ..osc.addressing import _workspace_address
from ..settings.summarizers import _collection_items
from .visual import (ChannelName, Crosspoint, Gang, OutputFlag, Quaternion, Slider,
                     SliceAdd, SliceCount, SliceDelete, SliceTime, TrueOnly)

PositiveInt = Annotated[StrictInt, Field(ge=1)]
Index = Annotated[StrictInt, Field(ge=0)]
Mode = Annotated[StrictInt, Field(ge=0, le=1)]
Rate = Annotated[Number, Field(ge=0.03, le=33)]
Byte = Annotated[StrictInt, Field(ge=0, le=127)]
WideByte = Annotated[StrictInt, Field(ge=0, le=16383)]
PatchUUID = Annotated[StrictStr, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
PatchID = PatchUUID | Literal[""]


class Basics(CueEditCommonProperties):
    duration: Nonnegative | None = None


class LevelFlag(BaseModel):
    model_config = {"extra": "forbid"}
    row: Annotated[StrictInt, Field(ge=0, le=24)]
    column: Annotated[StrictInt, Field(ge=0, le=128)]
    value: StrictBool


class ObjectName(BaseModel):
    model_config = {"extra": "forbid"}
    objectID: PatchUUID
    name: Annotated[StrictStr, Field(min_length=1)]


class ObjectColor(BaseModel):
    model_config = {"extra": "forbid"}
    objectID: PatchUUID
    colorName: StrictStr


class ObjectPosition(BaseModel):
    model_config = {"extra": "forbid"}
    objectID: PatchUUID
    x: Number
    y: Number


class ObjectSpread(BaseModel):
    model_config = {"extra": "forbid"}
    objectID: PatchUUID
    spread: Number


class ObjectLevel(BaseModel):
    model_config = {"extra": "forbid"}
    row: Annotated[StrictInt, Field(ge=0, le=24)]
    objectID: PatchUUID
    decibel: Annotated[Number, Field(ge=-120, le=12)] | Literal["-inf"]


class ObjectLevelFlag(BaseModel):
    model_config = {"extra": "forbid"}
    row: Annotated[StrictInt, Field(ge=0, le=24)]
    objectID: PatchUUID
    value: StrictBool


class ObjectFlag(BaseModel):
    model_config = {"extra": "forbid"}
    objectID: PatchUUID
    value: StrictBool


class AudioOutputProperties(Basics):
    audioOutputPatchID: PatchID | None = None
    level: Crosspoint | None = None
    sliderLevel: Slider | None = None
    inputChannelName: ChannelName | None = None
    gang: Gang | None = None
    doLevel: LevelFlag | None = None
    mute: OutputFlag | None = None
    solo: OutputFlag | None = None
    mute_clear: TrueOnly | None = Field(default=None, alias="mute/clear")
    mute_channel_clear: TrueOnly | None = Field(default=None, alias="mute/channel/clear")
    solo_clear: TrueOnly | None = Field(default=None, alias="solo/clear")
    solo_channel_clear: TrueOnly | None = Field(default=None, alias="solo/channel/clear")
    setDefaultLevels: TrueOnly | None = None
    setSilentLevels: TrueOnly | None = None


class AudioCueEditProperties(AudioOutputProperties):
    fileTarget: StrictStr | None = None
    rate: Rate | None = None
    startTime: Nonnegative | None = None
    endTime: Nonnegative | None = None
    playCount: PositiveInt | None = None
    infiniteLoop: StrictBool | None = None
    preservePitch: StrictBool | None = None
    doFade: StrictBool | None = None
    lockFadeToCue: StrictBool | None = None
    lastSlicePlayCount: PositiveInt | Literal[-1] | None = None
    lastSliceInfiniteLoop: StrictBool | None = None
    addSliceMarker: SliceAdd | None = None
    deleteSliceMarker: SliceDelete | None = None
    deleteSliceMarkers: TrueOnly | None = None
    slice_time: SliceTime | None = Field(default=None, alias="sliceMarker/time")
    slice_count: SliceCount | None = Field(default=None, alias="sliceMarker/playCount")
    object_name: ObjectName | None = Field(default=None, alias="objectID/name")
    object_color: ObjectColor | None = Field(default=None, alias="objectID/colorName")
    object_position: ObjectPosition | None = Field(default=None, alias="objectID/position")
    object_spread: ObjectSpread | None = Field(default=None, alias="objectID/spread")
    objectIDLevel: ObjectLevel | None = None
    doObjectIDLevel: ObjectLevelFlag | None = None
    mute_object: ObjectFlag | None = Field(default=None, alias="mute/objectID")
    solo_object: ObjectFlag | None = Field(default=None, alias="solo/objectID")


class MicCueEditProperties(AudioOutputProperties):
    object_name: ObjectName | None = Field(default=None, alias="objectID/name")
    object_color: ObjectColor | None = Field(default=None, alias="objectID/colorName")
    object_position: ObjectPosition | None = Field(default=None, alias="objectID/position")
    object_spread: ObjectSpread | None = Field(default=None, alias="objectID/spread")
    objectIDLevel: ObjectLevel | None = None
    mute_object: ObjectFlag | None = Field(default=None, alias="mute/objectID")
    solo_object: ObjectFlag | None = Field(default=None, alias="solo/objectID")
    audioInputPatchID: PatchID | None = None
    channels: Annotated[StrictInt, Field(ge=1, le=24)] | None = None
    channelOffset: Index | None = None


class LightCueEditProperties(Basics):
    lightCommandText: StrictStr | None = None
    alwaysCollate: StrictBool | None = None
    subcontroller: StrictBool | None = None


class FadeCueEditProperties(Basics):
    cueTargetID: PatchID | None = None
    patchTargetID: PatchUUID | None = None
    targetMode: Mode | None = None
    stopTargetWhenDone: StrictBool | None = None
    levelsMode: Mode | None = None
    geoMode: Mode | None = None
    fadeType: Annotated[StrictInt, Field(ge=1, le=2)] | None = None
    pathHeight: Annotated[Number, Field(gt=0)] | None = None
    pathWidth: Annotated[Number, Field(gt=0)] | None = None
    rotation: Number | None = None
    rotationType: Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    doOpacity: StrictBool | None = None
    doRate: StrictBool | None = None
    doRotation: StrictBool | None = None
    doScale: StrictBool | None = None
    doTranslation: StrictBool | None = None
    opacity: Annotated[Number, Field(ge=0, le=1)] | None = None
    rate: Rate | None = None
    translation_x: Number | None = Field(default=None, alias="translation/x")
    translation_y: Number | None = Field(default=None, alias="translation/y")
    scale_x: Number | None = Field(default=None, alias="scale/x")
    scale_y: Number | None = Field(default=None, alias="scale/y")
    quaternion: Quaternion | None = None
    level: Crosspoint | None = None
    sliderLevel: Slider | None = None
    doLevel: LevelFlag | None = None
    inputChannelName: ChannelName | None = None
    gang: Gang | None = None
    doObjectIDLevel: ObjectLevelFlag | None = None


class FadePoint(BaseModel):
    model_config = {"extra": "forbid"}
    x: Number
    y: Number


class ParameterValue(BaseModel):
    model_config = {"extra": "forbid"}
    parameter: Annotated[StrictStr, Field(min_length=1)]
    value: JsonValue


class ParameterFlag(ParameterValue):
    value: StrictBool


class NetworkCueEditProperties(Basics):
    networkPatchID: PatchID | None = None
    customString: StrictStr | None = None
    fadeEntries: list[FadePoint] | None = None
    fadeFrom: Number | None = None
    fadeTo: Number | None = None
    fadeNumberType: Mode | None = None
    fadeType: Annotated[StrictInt, Field(ge=0, le=2)] | None = None
    fps: Annotated[StrictInt, Field(ge=1, le=120)] | None = None
    pathHeight: Annotated[Number, Field(gt=0)] | None = None
    pathWidth: Annotated[Number, Field(gt=0)] | None = None
    parameterValue: ParameterValue | None = None
    parameterFadeEnabled: ParameterFlag | None = None


class MidiCueEditProperties(Basics):
    midiPatchID: PatchID | None = None
    messageType: Annotated[StrictInt, Field(ge=1, le=3)] | None = None
    channel: Annotated[StrictInt, Field(ge=1, le=16)] | None = None
    status: Annotated[StrictInt, Field(ge=0, le=6)] | None = None
    command: Byte | None = None
    commandFormat: Byte | None = None
    byte1: Byte | None = None
    byte2: Byte | None = None
    byteCombo: WideByte | None = None
    note: Byte | None = None
    velocity: Byte | None = None
    programChange: Byte | None = None
    pitchBend: WideByte | None = None
    controlNumber: WideByte | None = None
    controlValue: WideByte | None = None
    deviceID: Byte | None = None
    endValue: WideByte | None = None
    hours: Byte | None = None
    minutes: Byte | None = None
    seconds: Byte | None = None
    frames: Byte | None = None
    subframes: Byte | None = None
    macro: Byte | None = None
    rawString: StrictStr | None = None
    qList: StrictStr | None = None
    qNumber: StrictStr | None = None
    qPath: StrictStr | None = None
    timecodeString: StrictStr | None = None
    timecodeFormat: Annotated[StrictInt, Field(ge=0, le=3)] | None = None
    doFade: StrictBool | None = None


class MidiFileCueEditProperties(Basics):
    fileTarget: StrictStr | None = None
    midiPatchID: PatchID | None = None
    rate: Rate | None = None
    startTime: Nonnegative | None = None
    endTime: Nonnegative | None = None
    playCount: PositiveInt | None = None


class TimecodeCueEditProperties(Basics):
    outputType: Mode | None = None
    timecodeFrameRate: Annotated[StrictInt, Field(ge=0, le=7)] | None = None
    startTime: StrictStr | None = None
    endTime: StrictStr | None = None
    ltcChannel: Annotated[StrictInt, Field(ge=1, le=128)] | None = None
    audioOutputPatchID: PatchID | None = None
    midiPatchID: PatchID | None = None


class ScriptCueEditProperties(Basics):
    """OSC has no scriptSource setter; only saved Basics/Triggers are exposed."""


class AudioCueEditInput(ControlCueEditInput):
    properties: AudioCueEditProperties


class MicCueEditInput(ControlCueEditInput):
    properties: MicCueEditProperties


class LightCueEditInput(ControlCueEditInput):
    properties: LightCueEditProperties


class FadeCueEditInput(ControlCueEditInput):
    properties: FadeCueEditProperties


class NetworkCueEditInput(ControlCueEditInput):
    properties: NetworkCueEditProperties


class MidiCueEditInput(ControlCueEditInput):
    properties: MidiCueEditProperties


class MidiFileCueEditInput(ControlCueEditInput):
    properties: MidiFileCueEditProperties


class TimecodeCueEditInput(ControlCueEditInput):
    properties: TimecodeCueEditProperties


class ScriptCueEditInput(ControlCueEditInput):
    properties: ScriptCueEditProperties


FAMILIES = {"audio": AudioCueEditInput, "mic": MicCueEditInput, "light": LightCueEditInput,
            "fade": FadeCueEditInput, "network": NetworkCueEditInput, "midi": MidiCueEditInput,
            "midi_file": MidiFileCueEditInput, "timecode": TimecodeCueEditInput, "script": ScriptCueEditInput}
COMMON = {field.alias or key for key, field in Basics.model_fields.items()}
TRIGGERS = {key for key in COMMON if key.startswith("timecodeTrigger/")} | {
    "duckOthers", "duckTime", "duckLevel", "fadeAndStopOthers", "fadeAndStopOthersTime",
    "secondTriggerAction", "secondTriggerOnRelease"} | control.control_applescript.TRIGGER_KEYS
for family, model in FAMILIES.items():
    spec = UPDATE_PROFILES[family + "_basic"]
    control._FAMILIES[family] = (model, model.model_fields["properties"].annotation,
                               spec.cue_types, spec.name, f"qlab_edit_{family}_cues")


class IndexedOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FamilyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cue_id: control.CanonicalWorkspaceUUID
    confirm_gates: list[StrictStr] = Field(default_factory=list)

    @model_validator(mode="after")
    def has_changes(self):
        if self.properties is None and "properties" in self.model_fields_set:
            raise ValueError("Explicit null properties are not edits.")
        if self.properties is None and not self.operations:
            raise ValueError("Provide properties or indexed operations.")
        return self


# Derive indexed argument contracts from the already-public property models.
for _family, _old_model in list(FAMILIES.items()):
    _properties = _old_model.model_fields["properties"].annotation
    _variants = []
    for _name, _field in _properties.model_fields.items():
        _key = _field.alias or _name
        _type = next((t for t in get_args(_field.annotation)
                      if isinstance(t, type) and issubclass(t, BaseModel)), None)
        if _type is not None:
            _variants.append(create_model(
                _old_model.__name__.replace("Input", "") + _name.title().replace("_", "") + "Operation",
                __base__=IndexedOperation, property=(Literal[_key], ...), args=(_type, ...)))
    _operation_type = Annotated[Union[tuple(_variants)], Field(discriminator="property")] if len(_variants) > 1 else _variants[0] if _variants else None
    _fields = {"properties": (_properties | None, None)}
    if _operation_type is not None:
        _fields["operations"] = (list[_operation_type], Field(default_factory=list, max_length=50))
    else:
        _fields["operations"] = (list[JsonValue], Field(default_factory=list, max_length=0))
    _model = create_model(_old_model.__name__, __base__=FamilyInput, **_fields)
    FAMILIES[_family] = _model
    globals()[_old_model.__name__] = _model
    control._FAMILIES[_family] = (_model, _properties, UPDATE_PROFILES[_family + "_basic"].cue_types,
                                _family + "_basic", f"qlab_edit_{_family}_cues")


_BLOCKED = {"setDefaultLevels": "Template default state cannot be read reliably.",
            "parameterValue": "Device Definition parameter type/range metadata is unavailable.",
            "parameterFadeEnabled": "Device Definition fade capability metadata is unavailable."}

def capabilities(family, triggers=None, result=None):
    model = control._FAMILIES[family][1]
    max_operations = next((m.max_length for m in FAMILIES[family].model_fields['operations'].metadata
                           if hasattr(m, 'max_length')), 0)
    names = {field.alias or key for key, field in model.model_fields.items()}
    blocked = {key: reason for key, reason in _BLOCKED.items() if key in names}
    if family in {"audio", "mic"}:
        blocked.update({key: "Documented for Fade cues only." for key in names & {"doLevel", "doObjectIDLevel"}})
    if family == "mic":
        blocked.update({key: "Input patch capacity is not available through documented OSC." for key in {"channels", "channelOffset"}})
    if triggers is None or type(triggers.fadeAndStopOthers) is not int:
        blocked["fadeAndStopOthers"] = "Scope readback must be an integer, not boolean."
    if family == 'midi':
        blocked.update({key: 'Command-specific MSC activation is not reliably readable through OSC.' for key in
            ('controlNumber', 'controlValue', 'hours', 'minutes', 'seconds', 'frames', 'subframes', 'macro', 'qList', 'qNumber', 'qPath', 'timecodeString', 'timecodeFormat')})
    if result is not None and (result.basics is None or result.basics.allowsEditingDuration is not True):
        blocked['duration'] = 'Cue duration capability is unavailable or false.'
    pending = names & {'parameterValue', 'parameterFadeEnabled'}
    unavailable = ['Hotkey/MIDI/Wall Clock setup', 'Timecode activation/display', 'Trim', 'Audio FX', 'Undocumented curves',
                   *(['Script source editing'] if family == 'script' else [])]
    return control.control_applescript.trigger_capabilities({"tool": f"qlab_edit_{family}_cues", "allowed_properties": sorted(names - blocked.keys()),
            "blocked_properties": blocked, "requires_fresh_preflight": True,
            "gated_or_planned_properties": {key: "Requires signed dry run, readable baseline and family dependencies." for key in names - blocked.keys()},
            "property_capabilities": {
                **{key: {"state": "pending_validation" if key in pending else "blocked" if key in blocked else "gated",
                          "reason": blocked.get(key, "Signed confirmation, readable baseline and verified family dependencies required.")} for key in sorted(names)},
                **{key: {"state": "unavailable_via_osc", "reason": "No documented saved setter in this OSC phase."} for key in unavailable}},
            "max_cues": 50, "max_indexed_operations_per_cue": max_operations,
            "notes": ["All writes require signed five-minute single-use confirmations.",
                      "Basics, Triggers and supported family settings can share a sequential non-atomic batch.",
                      "Selectors which may reset dependent settings require a separate dry run."],
            "unavailable_via_osc": unavailable,
            "excluded": ["Audio Maps", "/live", "cue execution", "workspace settings", "deprecated aliases"]}, triggers)


def normalize_item(item, family):
    props = item.properties.model_dump(by_alias=True, exclude_unset=True) if item.properties is not None else {}
    specs = {p.name: p for p in UPDATE_PROFILES[family + "_basic"].properties}
    requests = list(props.items()) + [(o.property, o.args.model_dump()) for o in item.operations]
    normalized = []
    for key, value in requests:
        if key in TRIGGERS:
            ops = control._normalize({key: value})
        elif specs[key].args == ():
            ops = normalize_update_request(family + "_basic", None, [{"property": key, "args": {}, "mode": "saved"}])[1]
        elif specs[key].args[0][0] == "value" and len(specs[key].args) == 1:
            ops = normalize_update_request(family + "_basic", {key: value}, None)[1]
        else:
            ops = normalize_update_request(family + "_basic", None, [{"property": key, "args": value, "mode": "saved"}])[1]
        for op in ops:
            indexed = isinstance(value, dict)
            op["key"] = op["path"] if indexed or op["path"] != key else key
            op["read_path"] = op["path"]
            op["requested"] = op["args"][0] if len(op["args"]) == 1 else list(op["args"])
            op["real_write_enabled"] = True
            op["requires_confirm_token"] = True
            op.pop("planned_only_reason", None)
            op.pop("confirm_token", None)
            if key == "fadeEntries":
                op["args"] = [json.dumps(op["requested"], separators=(",", ":"), allow_nan=False)]
            normalized.append(op)
    paths = [op["path"] for op in normalized]
    if len(paths) != len(set(paths)):
        raise ValueError("Multiple properties address the same OSC setter.")
    for path in paths:
        if any(other != path and other.startswith(path + "/") for other in paths):
            raise ValueError("Aggregate and component setters overlap.")
    return normalized


def edit_remaining_cues(reader, workspace_id, updates, dry_run=None, *, family):
    model = FAMILIES[family]
    items = [model.model_validate(item.model_dump(by_alias=True, exclude_unset=True)
                                  if isinstance(item, BaseModel) else item) for item in updates]
    for item in items:
        normalize_item(item, family)  # reject conflicting aliases before any OSC
    return control.edit_control_cues(reader, workspace_id, items, dry_run, _family=family)


def _raw(reader, ws, route):
    return reader._request(_workspace_address(ws, route), workspace_id=ws, ensure_always_reply=True).data


def _scalar(reader, ws, uid, key):
    return _raw(reader, ws, f'cue_id/{uid}/{key}')


def read(reader, ws, uid, keys, changes=None):
    identity = _scalar(reader, ws, uid, 'uniqueID')
    if not isinstance(identity, str) or identity.upper() != uid:
        raise ValueError('Fresh cue UUID could not be verified.')
    base = {'uniqueID': identity, 'type': _scalar(reader, ws, uid, 'type')}
    if not isinstance(base['type'], str):
        raise ValueError('Fresh cue type could not be verified.')
    values = dict(base)
    for key in keys:
        if key in values:
            continue
        if key in control.control_applescript.TRIGGER_KEYS:
            values.update(control._read(reader, ws, uid, ['uniqueID', 'type', *(control.control_applescript.TRIGGER_KEYS & set(keys))]))
            continue
        if key in {'addSliceMarker', 'deleteSliceMarkers'} or key.startswith('deleteSliceMarker/'):
            value = _scalar(reader, ws, uid, 'sliceMarkers')
        elif key in {'mute/clear', 'solo/clear'}:
            stem = key.split('/')[0]
            value = {k: _scalar(reader, ws, uid, stem + k.title()) for k in ('channels', 'objects')}
        elif key in {'mute/channel/clear', 'solo/channel/clear'}:
            value = _scalar(reader, ws, uid, key.split('/')[0] + 'Channels')
        elif key == 'setSilentLevels':
            value = _scalar(reader, ws, uid, 'levels')
        else:
            value = _scalar(reader, ws, uid, 'framerate' if key == 'timecodeFrameRate' else key)
        if key == 'preservePitch' and type(value) is int and value in (0, 1):
            value = bool(value)
        values[key] = value
    final = {key: _scalar(reader, ws, uid, key) for key in base}
    if final != base:
        raise ValueError('Cue identity changed during reads.')
    return values


def _reference(reader, ws, route, uid, dependencies):
    payload = _raw(reader, ws, route)
    dependencies['routes'][route] = payload
    match = next((p for p in _collection_items(payload)
                  if str(p.get('uniqueID', p.get('id', ''))).casefold() == uid.casefold()), None)
    if match is None:
        raise ValueError(f'Patch UUID is absent from workspace {route}.')
    return match


def _depend(reader, ws, uid, keys, dependencies):
    values = read(reader, ws, uid, keys)
    if any(values.get(k) is None for k in keys):
        raise ValueError('Required family context could not be read.')
    dependencies['cues'].setdefault(uid, {}).update({k: values[k] for k in keys})
    return values


def _time_seconds(text, fmt):
    if type(fmt) is not int or fmt not in range(8):
        raise ValueError('Timecode frame rate is unavailable.')
    nominal = (24, 25, 30, 30, 24, 25, 30, 30)[fmt]
    rate = (24, 25, 30, 30, 24000 / 1001, 25000 / 1001, 30000 / 1001, 30000 / 1001)[fmt]
    match = re.fullmatch(r'(\d{1,2}):(\d{2}):(\d{2})[:;](\d{2})(?:\.(\d{2}))?', text)
    if not match:
        try:
            number = float(text)
        except (ValueError, TypeError):
            raise ValueError('Use SMPTE time or nonnegative seconds.') from None
        if not math.isfinite(number) or number < 0:
            raise ValueError('Time must be finite and nonnegative.')
        return number
    h, m, s, f, bits = [int(x or 0) for x in match.groups()]
    if not (h < 24 and m < 60 and s < 60 and f < nominal and bits < 100):
        raise ValueError('Timecode components exceed the frame rate.')
    drop = fmt in (3, 7)
    if drop and m % 10 and s == 0 and f < 2:
        raise ValueError('Timecode selects a skipped drop-frame label.')
    frames = ((h * 3600 + m * 60 + s) * nominal + f + bits / 100)
    if drop:
        minutes = h * 60 + m
        frames -= 2 * (minutes - minutes // 10)
    return frames / rate


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _validate_scalar_baseline(op):
    baseline, requested = op['baseline'], op['requested']
    if baseline is None:
        raise ValueError(f"{op['property']}: baseline is unavailable.")
    if type(requested) is bool and type(baseline) is not bool:
        raise ValueError(f"{op['property']}: expected boolean baseline.")
    if _finite(requested) and not _finite(baseline):
        raise ValueError(f"{op['property']}: expected finite numeric baseline.")
    if isinstance(requested, str) and requested != '-inf' and not isinstance(baseline, str):
        raise ValueError(f"{op['property']}: expected string baseline.")
    if isinstance(baseline, (dict, list)) and op['args'] and not isinstance(requested, (dict, list)):
        raise ValueError(f"{op['property']}: invalid scalar readback.")


def preflight(reader, ws, item, family):
    from types import SimpleNamespace
    from .remaining_context import validate
    uid = str(item.cue_id).upper()
    operations = normalize_item(item, family)
    common = item.properties.model_dump(by_alias=True, exclude_unset=True) if item.properties is not None else {}
    common = {k: v for k, v in common.items() if k in COMMON}
    if common:
        before, _, _, deps = control._preflight(reader, ws,
            SimpleNamespace(cue_id=item.cue_id, properties=control.ControlCueEditProperties.model_validate(common)), family, _core=True)
    else:
        before = read(reader, ws, uid, ['uniqueID', 'type', 'parent', 'isRunning', 'isPaused', 'isAuditioning', 'isBroken', 'isWarning'])
        deps = {}
    if before['type'] not in control._FAMILIES[family][2]:
        raise ValueError(f'Expected {family} cue.')
    if any(before.get(k) is not False for k in ('isRunning', 'isPaused', 'isAuditioning')):
        raise ValueError('Source cue must be inactive.')
    caps = capabilities(family, SimpleNamespace(fadeAndStopOthers=before.get('fadeAndStopOthers')))
    for op in operations:
        if op['property'] in caps['blocked_properties'] and op['property'] not in control.control_applescript.TRIGGER_KEYS:
            raise ValueError(caps['blocked_properties'][op['property']])
    before.update(read(reader, ws, uid, [op['key'] for op in operations]))
    for op in operations:
        op['baseline'] = before[op['key']]
        if op['property'].startswith('objectID/') and op['property'].endswith('/position'):
            if not isinstance(op['baseline'], list) or len(op['baseline']) != 2 or not all(_finite(x) for x in op['baseline']):
                raise ValueError('Object position must be a finite OSC coordinate pair.')
        _validate_scalar_baseline(op)
    deps.update(validate(reader, ws, uid, family, operations, before))
    deps['routes'] = {route: _fingerprint(payload) for route, payload in deps['routes'].items()}
    for op in operations:
        snapshot = selector_snapshot(reader, ws, uid, family, op['property'])
        if snapshot is not None:
            before['selector_effects'] = snapshot
            deps['selector'] = {'family': family, 'property': op['property'], 'snapshot': snapshot}
    # Immutable dependencies cannot also be modified by this request.
    modified = {op['key'] for op in operations}
    if 'framerate' in modified:
        modified.add('timecodeFrameRate')
    for key in modified:
        deps.get('cues', {}).get(uid, {}).pop(key, None)
    changes = {op['key']: op['requested'] for op in operations}
    return before, changes, operations, deps


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def check_dependencies(reader, ws, uid, dependencies):
    for route, baseline in dependencies.get('routes', {}).items():
        if _fingerprint(_raw(reader, ws, route)) != baseline:
            raise ValueError('Workspace patch dependencies changed; run a new dry run.')
    for cue, baseline in dependencies.get('cues', {}).items():
        current = read(reader, ws, cue, list(baseline))
        if any(not control._same(current.get(k), v) for k, v in baseline.items()):
            raise ValueError('Cue dependency changed; run a new dry run.')
    selector = dependencies.get('selector')
    if selector and not control._same(selector_snapshot(reader, ws, uid, selector['family'], selector['property']), selector['snapshot']):
        raise ValueError('Selector-dependent state changed after dry run.')
    if 'fade_activation' in dependencies:
        if not control._same(_scalar(reader, ws, uid, 'doLevel'), dependencies['fade_activation']):
            raise ValueError('Fade activation matrix changed before setter.')
    if 'object_ids' in dependencies:
        entries = _collection_items(_raw(reader, ws, f'cue_id/{uid}/objects'))
        if sorted(str(x.get('uniqueID', x.get('id', ''))).upper() for x in entries) != dependencies['object_ids']:
            raise ValueError('Cue object identities changed.')
    if 'slice_inventory' in dependencies:
        if not control._same(_scalar(reader, ws, uid, 'sliceMarkers'), dependencies['slice_inventory']):
            raise ValueError('Slice inventory changed before setter.')
    if 'light_patch' in dependencies:
        from .operations import _try_read_safe_light_patch
        patch, error = _try_read_safe_light_patch(reader, ws)
        if error or patch != dependencies['light_patch']:
            raise ValueError('Light patch changed before setter.')
    for path, baseline in dependencies.get('files', {}).items():
        stat = os.stat(path)
        if os.path.realpath(path) != baseline['realpath'] or stat.st_size != baseline['size'] or stat.st_mtime_ns != baseline['mtime_ns']:
            raise ValueError('Media file changed after dry run.')


def matches(key, actual, wanted, dependencies, reader, ws, uid):
    if key in {'startTime', 'endTime'} and isinstance(wanted, str):
        fmt = dependencies.get('timecode_frame_rate')
        if fmt is not None and isinstance(actual, str):
            return math.isclose(_time_seconds(actual, fmt), _time_seconds(wanted, fmt), rel_tol=1e-6, abs_tol=1e-4)
    if key.startswith(('level/', 'sliderLevel/', 'objectIDLevel/')) and _finite(actual) and _finite(wanted):
        return math.isclose(actual, wanted, rel_tol=1e-6, abs_tol=1e-3)
    if key == 'rawString' and isinstance(actual, str) and isinstance(wanted, str):
        return re.sub(r'\s+', '', actual).casefold() == re.sub(r'\s+', '', wanted).casefold()
    if wanted == '-inf' and _finite(actual):
        minimum = dependencies.get('audio_minimum')
        return minimum is not None and control._same(actual, minimum)
    matched = control._same(actual, wanted)
    if matched and key == 'fileTarget' and wanted:
        matched = _scalar(reader, ws, uid, 'isBroken') is False
    if matched and key.startswith('doLevel/') and 'fade_activation' in dependencies:
        matrix = [list(row) for row in dependencies['fade_activation']]
        row, column = [int(x) for x in key.split('/')[1:]]
        matrix[row][column] = wanted
        matched = control._same(_scalar(reader, ws, uid, 'doLevel'), matrix)
        if matched:
            dependencies['fade_activation'] = matrix
    if matched and key in dependencies.get('slice_expected', {}):
        inventory = _scalar(reader, ws, uid, 'sliceMarkers')
        matched = control._same(inventory, dependencies['slice_expected'][key])
    if matched and key == 'framerate' and 'timecode_selector_times' in dependencies:
        times = read(reader, ws, uid, ['startTime', 'endTime', 'duration'])
        previous = dependencies['timecode_selector_times']
        matched = times['startTime'] == previous['startTime'] and control._same(times['duration'], previous['duration'])
        span = _time_seconds(times['endTime'], wanted) - _time_seconds(times['startTime'], wanted)
        matched = matched and math.isclose(span, previous['duration'], abs_tol=1 / 24 + 1e-3)
        if times['startTime'] == times['endTime'] and previous['startTime'] == previous['endTime']:
            matched = control._same(times['duration'], previous['duration'])
    if matched and 'slice_inventory' in dependencies and (key.startswith('sliceMarker/') or key in {'addSliceMarker', 'deleteSliceMarkers'} or key.startswith('deleteSliceMarker/')):
        dependencies['slice_inventory'] = _scalar(reader, ws, uid, 'sliceMarkers')
    return matched


# Queries derive selectors from the same contracts, without accepting setter values.
INSPECTIONS = {}
for _family, _entry in control._FAMILIES.items():
    if _family not in FAMILIES:
        continue
    _variants = []
    for _name, _field in _entry[1].model_fields.items():
        _name = _field.alias or _name
        if _name in control.control_applescript.TRIGGER_KEYS:
            continue
        _spec = next((p for p in UPDATE_PROFILES[_family + "_basic"].properties if p.name == _name), None)
        if _spec is None:
            _spec = next(p for p in UPDATE_PROFILES["control_basic"].properties if p.name == _name)
        if not _spec.args:  # action reads belong to their explicit aggregate snapshots
            continue
        _argument = next((a for a in get_args(_field.annotation) if isinstance(a, type) and issubclass(a, BaseModel)), None)
        _selectors = set(re.findall(r"\{(\w+)\}", (_spec.path or _spec.name)))
        _fields = {k: (v.rebuild_annotation(), ...) for k, v in (_argument.model_fields.items() if _argument else []) if k in _selectors}
        _query_args = create_model(f"{_family.title()}_{_name.replace('/', '_')}Selectors", __base__=IndexedOperation, **_fields)
        _query = create_model(f"{_family.title()}_{_name.replace('/', '_')}Inspection", __base__=IndexedOperation,
                              property=(Literal[_name], ...), args=(_query_args, Field(default_factory=_query_args)) if not _selectors else (_query_args, ...))
        _variants.append(_query)
    INSPECTIONS[_family] = Annotated[Union[tuple(_variants)], Field(discriminator="property")]


def inspect(reader, result, queries):
    """Read only requested scalar/indexed endpoints, bounded by count and response budget."""
    if not queries or not result.identity:
        return result
    from pydantic import TypeAdapter
    from ..cues.limits import MAX_SENSITIVE_CUE_RESPONSE_BYTES, serialized_payload_bytes
    from ..cues.lists import _finish
    from ..settings.redaction import _redact_payload
    family = result.identity.type.lower().replace(' ', '_')
    specs = {p.name: p for p in (*UPDATE_PROFILES['control_basic'].properties, *UPDATE_PROFILES[family + '_basic'].properties)}
    adapter = TypeAdapter(list[INSPECTIONS[family]])
    parsed = adapter.validate_python(queries)
    if len(parsed) > 50:
        raise ValueError('At most 50 inspections per cue.')
    paths = [(specs[q.property].path or specs[q.property].name).format(**q.args.model_dump()) for q in parsed]
    if len(paths) != len(set(paths)):
        raise ValueError('Repeated inspection destinations.')
    uid = str(result.cue_id).upper()
    for path in paths:
        if result.profile == 'safe' and path in {'fileTarget', 'notes', 'customString', 'message', 'rawString', 'lightCommandText'}:
            result.coverage.unavailable_fields.append('inspection_values.' + path)
            result.coverage.notes.append(path + ': use technical profile for free text or media paths.')
            continue
        try:
            values = read(reader, result.workspace_id, uid, [path])
            if values['type'] != result.identity.type:
                raise ValueError('Cue type changed during inspection.')
            if values[path] is None:
                result.coverage.unavailable_fields.append('inspection_values.' + path)
            result.inspection_values[path] = _redact_payload({path: values[path]}, section=family + '_cue', profile=result.profile, redactions=result.redactions)[path]
        except Exception as exc:
            from ..sanitizer import sanitize_exception_message
            result.errors['inspection_values.' + path] = sanitize_exception_message(exc)
    if serialized_payload_bytes(result.model_dump(mode='json')) > MAX_SENSITIVE_CUE_RESPONSE_BYTES:
        result.inspection_values = {}
        result.errors['inspections'] = 'Inspection response exceeds byte budget.'
    return _finish(result)


def selector_snapshot(reader, ws, uid, family, property_name):
    """Observe dependent saved state when a selector can reset its inspector."""
    keys = {
        'fileTarget': ['fileTarget', 'rate', 'startTime', 'endTime', 'playCount', 'isBroken'],
        'audioOutputPatchID': ['audioOutputPatchID', 'levels', 'sliderLevels'],
        'audioInputPatchID': ['audioInputPatchID', 'channels', 'channelOffset', 'levels'],
        'networkPatchID': ['networkPatchID', 'customString', 'fadeType'],
        'midiPatchID': ['midiPatchID'],
        'cueTargetID': ['cueTargetID', 'targetMode', 'levelsMode', 'geoMode', 'doLevel'],
        'patchTargetID': ['patchTargetID', 'targetMode', 'levelsMode', 'doLevel'],
        'targetMode': ['cueTargetID', 'patchTargetID', 'targetMode', 'doLevel'],
        'fadeType': ['fadeType', 'fadeEntries'] if family == 'network' else ['fadeType', 'geoMode', 'levelsMode'],
    }.get(property_name)
    if property_name == 'fileTarget' and family == 'audio':
        keys += ['numChannelsIn', 'levels', 'sliderLevels']
    if family == 'midi' and property_name in {'messageType', 'status'}:
        mode = _scalar(reader, ws, uid, 'messageType')
        keys = ['messageType'] + (['status', 'channel', 'byte1', 'byte2', 'byteCombo', 'doFade', 'endValue'] if mode == 1 else
               ['command', 'commandFormat', 'deviceID'] if mode == 2 else ['rawString'] if mode == 3 else [])
    if family == 'timecode' and property_name in {'outputType', 'timecodeFrameRate'}:
        output = _scalar(reader, ws, uid, 'outputType')
        keys = ['outputType', 'timecodeFrameRate', 'startTime', 'endTime'] + (['audioOutputPatchID', 'ltcChannel'] if output == 1 else ['midiPatchID'])
    if keys is None:
        return None
    values = read(reader, ws, uid, keys)
    if any(values[k] is None for k in keys):
        raise ValueError('Selector effects cannot be observed completely; setter blocked.')
    return {k: values[k] for k in keys}
