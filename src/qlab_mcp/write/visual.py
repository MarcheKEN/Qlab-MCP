"""Saved Video, Camera and Text edits through the shared sequential writer."""
from __future__ import annotations

from typing import Annotated, Literal, Union, get_args
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, AfterValidator, StrictBool, StrictInt, StrictStr, model_validator, create_model

from . import control
from . import video_fx
from .text_format import TextFormatOperation
from . import text_format
from .control import CueEditCommonProperties, ControlCueEditInput, Number, Nonnegative
from .registry import normalize_update_request
from ..osc.addressing import _workspace_address


class Coordinates(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: Number
    y: Number


class Crop(BaseModel):
    model_config = ConfigDict(extra="forbid")
    top: Number
    bottom: Number
    left: Number
    right: Number


def _true(value):
    if value is not True:
        raise ValueError("Cleanup/reset must be exactly true.")
    return value


TrueOnly = Annotated[StrictBool, AfterValidator(_true)]

Color = Annotated[list[Annotated[Number, Field(ge=0, le=1)]], Field(min_length=4, max_length=4)]
Quaternion = Annotated[list[Number], Field(min_length=4, max_length=4)]


Output = Annotated[StrictInt, Field(ge=0, le=128)]
Input = Annotated[StrictInt, Field(ge=0, le=24)]
Level = Annotated[Number, Field(ge=-120, le=12)] | Literal["-inf"]


class Crosspoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inChannel: Input
    outChannel: Output
    decibel: Level


class Slider(BaseModel):
    model_config = ConfigDict(extra="forbid")
    channel: Output
    decibel: Level


class OutputFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    output: Output
    value: StrictBool


class EffectFlag(BaseModel):
    model_config = ConfigDict(extra='forbid')
    index: Annotated[StrictInt, Field(ge=0)]
    value: StrictBool


class SliceTime(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: Annotated[StrictInt, Field(ge=0)]
    time: Nonnegative


class SliceCount(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: Annotated[StrictInt, Field(ge=0)]
    playCount: Annotated[StrictInt, Field(ge=1)] | Literal[-1]


class ChannelName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: Annotated[StrictInt, Field(ge=1, le=24)]
    name: StrictStr


class Gang(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inChannel: Input
    outChannel: Output
    gang: StrictStr


class SliceAdd(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: Nonnegative
    playCount: Annotated[StrictInt, Field(ge=1)] | Literal[-1]


class SliceDelete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: Annotated[StrictInt, Field(ge=0)]


class ShadowOffset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    width: Number
    height: Number


class FontPair(BaseModel):
    model_config = ConfigDict(extra="forbid")
    family: StrictStr
    style: StrictStr


class AudioVisualProperties(BaseModel):
    level: Crosspoint | None = None
    sliderLevel: Slider | None = None
    mute_channel: OutputFlag | None = Field(default=None, alias="mute/channel")
    solo_channel: OutputFlag | None = Field(default=None, alias="solo/channel")
    mute_clear: TrueOnly | None = Field(default=None, alias="mute/channel/clear")
    solo_clear: TrueOnly | None = Field(default=None, alias="solo/channel/clear")
    inputChannelName: ChannelName | None = None
    gang: Gang | None = None



class VisualCueEditProperties(CueEditCommonProperties):
    duration: Nonnegative | None = None
    stageID: StrictStr | None = None
    layer: Annotated[StrictInt, Field(ge=0, le=1000)] | None = None
    opacity: Annotated[Number, Field(ge=0, le=1)] | None = None
    fillStage: StrictBool | None = None
    fillStyle: Annotated[StrictInt, Field(ge=0, le=2)] | None = None
    preserveAspectRatio: StrictBool | None = None
    smooth: StrictBool | None = None
    blendMode: StrictStr | None = None
    anchor: Coordinates | None = None
    translation: Coordinates | None = None
    scale: Coordinates | None = None
    origin: Coordinates | None = None
    origin_x: Number | None = Field(default=None, alias="origin/x")
    origin_y: Number | None = Field(default=None, alias="origin/y")
    anchor_x: Number | None = Field(default=None, alias="anchor/x")
    anchor_y: Number | None = Field(default=None, alias="anchor/y")
    translation_x: Number | None = Field(default=None, alias="translation/x")
    translation_y: Number | None = Field(default=None, alias="translation/y")
    scale_x: Number | None = Field(default=None, alias="scale/x")
    scale_y: Number | None = Field(default=None, alias="scale/y")
    crop: Crop | None = None
    cropTop: Number | None = None
    cropBottom: Number | None = None
    cropLeft: Number | None = None
    cropRight: Number | None = None
    quaternion: Quaternion | None = None
    resetRotation: TrueOnly | None = None
    effect_enabled: EffectFlag | None = Field(default=None, alias="videoEffectIndex/enabled")

    @model_validator(mode="after")
    def independent_properties(self):
        changes = self.model_dump(by_alias=True, exclude_unset=True)
        for aggregate, components in {"origin": {"origin/x", "origin/y"}, "anchor": {"anchor/x", "anchor/y"}, "translation": {"translation/x", "translation/y"},
                                      "scale": {"scale/x", "scale/y"}, "crop": {"cropTop", "cropBottom", "cropLeft", "cropRight"}}.items():
            if aggregate in changes and components & changes.keys():
                raise ValueError(f"Use {aggregate} or its components in one update.")
        for key in ("stageID", "videoInputPatchID", "audioOutputPatchID"):
            if changes.get(key):
                if str(UUID(changes[key])).casefold() != changes[key].casefold():
                    raise ValueError(f"{key} requires an exact UUID or empty string.")
        if self.resetRotation is True and self.quaternion is not None:
            raise ValueError("Use quaternion or resetRotation, not both.")
        if self.quaternion is not None:
            import math
            if not math.isclose(sum(x*x for x in self.quaternion), 1, abs_tol=1e-5):
                raise ValueError("quaternion must be a unit quaternion.")
        return self


class VideoCueEditProperties(VisualCueEditProperties, AudioVisualProperties):
    fileTarget: StrictStr | None = None
    audioOutputPatchID: StrictStr | None = None
    startTime: Nonnegative | None = None
    endTime: Nonnegative | None = None
    rate: Annotated[Number, Field(ge=0.03, le=33)] | None = None
    playCount: Annotated[StrictInt, Field(ge=1)] | None = None
    infiniteLoop: StrictBool | None = None
    preservePitch: StrictBool | None = None
    holdLastFrame: StrictBool | None = None
    clockType: Literal["audio", "video"] | None = None
    doFade: StrictBool | None = None
    lockFadeToCue: StrictBool | None = None
    lastSlicePlayCount: Annotated[StrictInt, Field(ge=1)] | Literal[-1] | None = None
    addSliceMarker: SliceAdd | None = None
    deleteSliceMarker: SliceDelete | None = None
    deleteSliceMarkers: TrueOnly | None = None
    slice_time: SliceTime | None = Field(default=None, alias="sliceMarker/time")
    slice_count: SliceCount | None = Field(default=None, alias="sliceMarker/playCount")


class CameraCueEditProperties(VisualCueEditProperties, AudioVisualProperties):
    videoInputPatchID: StrictStr | None = None
    audioInputPatchID: StrictStr | None = None
    channels: Annotated[StrictInt, Field(ge=1, le=24)] | None = None
    channelOffset: Annotated[StrictInt, Field(ge=0)] | None = None
    audioOutputPatchID: StrictStr | None = None


class TextCueEditProperties(VisualCueEditProperties):
    text: StrictStr | None = None
    fixedWidth: Nonnegative | None = None
    alignment: Literal["left", "center", "right", "justify"] | None = Field(default=None, alias="text/format/alignment")
    fontName: StrictStr | None = Field(default=None, alias="text/format/fontName")
    fontSize: Annotated[Number, Field(gt=0)] | None = Field(default=None, alias="text/format/fontSize")
    fontPair: FontPair | None = Field(default=None, alias="text/format/fontFamilyAndStyle")
    shadowOffset: ShadowOffset | None = Field(default=None, alias="text/format/shadowOffset")
    shadowWidth: Number | None = Field(default=None, alias="text/format/shadowOffset/width")
    shadowHeight: Number | None = Field(default=None, alias="text/format/shadowOffset/height")
    lineSpacing: Number | None = Field(default=None, alias="text/format/lineSpacing")
    color: Color | None = Field(default=None, alias="text/format/color")
    backgroundColor: Color | None = Field(default=None, alias="text/format/backgroundColor")
    shadowColor: Color | None = Field(default=None, alias="text/format/shadowColor")
    shadowBlurRadius: Nonnegative | None = Field(default=None, alias="text/format/shadowBlurRadius")
    underlineColor: Color | None = Field(default=None, alias="text/format/underlineColor")
    strikethroughColor: Color | None = Field(default=None, alias="text/format/strikethroughColor")
    underlineStyle: Literal["none", "single", "double"] | None = Field(default=None, alias="text/format/underlineStyle")
    strikethroughStyle: Literal["none", "single", "double"] | None = Field(default=None, alias="text/format/strikethroughStyle")


class VisualInput(ControlCueEditInput):
    @model_validator(mode="after")
    def has_changes(self):
        if self.properties is None and "properties" in self.model_fields_set:
            raise ValueError("Explicit null properties are not edits.")
        if self.properties is None and not self.operations:
            raise ValueError("Provide properties or operations.")
        return self


def _input_model(name, properties, text=False):
    variants = list(get_args(get_args(video_fx.FxOperation)[0]))
    for field_name, field in properties.model_fields.items():
        key = field.alias or field_name
        if key == 'videoEffectIndex/enabled':
            continue
        argument = next((typ for typ in get_args(field.annotation) if isinstance(typ, type) and issubclass(typ, BaseModel)), None)
        if argument is not None:
            variants.append(create_model(name + field_name.title().replace('_', '') + 'Operation', __base__=video_fx.FxOperationBase,
                                         property=(Literal[key], ...), args=(argument, ...)))
    if text:
        variants.append(TextFormatOperation)
    operation = Annotated[Union[tuple(variants)], Field(discriminator='property')]
    return create_model(name, __base__=VisualInput, properties=(properties | None, None),
                        operations=(list[operation], Field(default_factory=list, max_length=50)))


VideoCueEditInput = _input_model('VideoCueEditInput', VideoCueEditProperties)
CameraCueEditInput = _input_model('CameraCueEditInput', CameraCueEditProperties)
TextCueEditInput = _input_model('TextCueEditInput', TextCueEditProperties, text=True)


for family, input_model, props, kind in (
    ("video", VideoCueEditInput, VideoCueEditProperties, "Video"),
    ("camera", CameraCueEditInput, CameraCueEditProperties, "Camera"),
    ("text", TextCueEditInput, TextCueEditProperties, "Text"),
):
    control._FAMILIES[family] = (input_model, props, (kind,), f"{family}_basic", f"qlab_edit_{family}_cues")

_STRUCTURED = {"origin", "anchor", "translation", "scale", "crop", "level", "sliderLevel", "mute/channel", "solo/channel", "videoEffectIndex/enabled", "sliceMarker/time", "sliceMarker/playCount", "inputChannelName", "gang", "addSliceMarker", "deleteSliceMarker", "text/format/shadowOffset", "text/format/fontFamilyAndStyle"}
_COLORS = {"text/format/" + key for key in ("color", "backgroundColor", "shadowColor", "underlineColor", "strikethroughColor")}
_ACTIONS = {"resetRotation": "quaternion", "mute/channel/clear": "muteChannels", "solo/channel/clear": "soloChannels", "deleteSliceMarkers": "sliceMarkers"}
_COMMON = {field.alias or name for name, field in CueEditCommonProperties.model_fields.items()}


def normalize(changes, family):
    operations = []
    for key, value in changes.items():
        if key in control.control_applescript.TRIGGER_KEYS:
            operations.extend(control._normalize({key: value}))
            continue
        profile = "control_basic" if key in _COMMON else f"{family}_basic"
        if key in _ACTIONS:
            operations.extend(normalize_update_request(profile, None, [{"property": key, "args": {}}])[1])
        elif key in _STRUCTURED or key in _COLORS:
            args = dict(zip(("red", "green", "blue", "alpha"), value, strict=True)) if key in _COLORS else value
            operations.extend(normalize_update_request(profile, None, [{"property": key, "args": args}])[1])
        else:
            operations.extend(normalize_update_request(profile, {key: value}, None)[1])
    for op in operations:
        for key in ("confirm_token", "future_gate_requirements", "planned_only_reason"):
            op.pop(key, None)
        op.update(real_write_enabled=True, real_write_possible=True, requires_confirm_token=True)
    return operations


def read(reader, ws, uid, keys, changes=None):
    changes = changes or {}
    # QLab suppresses unchanged query replies unless alwaysReply is enabled.
    identity = reader._request(_workspace_address(ws, f"cue_id/{uid}/uniqueID"),
                               workspace_id=ws, ensure_always_reply=True).data
    if not isinstance(identity, str) or identity.upper() != uid:
        raise ValueError("Fresh cue UUID could not be verified.")
    # valuesForKeys does not reliably expose slash paths or composite OSC getters.
    base = [key for key in keys if key in control._CONTEXT]
    values = control._read(reader, ws, uid, list(dict.fromkeys(["uniqueID", "type", *base])))
    # No intervening property reads: QLab can suppress an identical second query.
    if set(keys) <= set(control._CONTEXT):
        return values
    fragments = None
    for key in keys:
        if key in values or key in control._CONTEXT:
            continue
        if key in control.control_applescript.TRIGGER_KEYS:
            values.update(control._read(reader, ws, uid, ["uniqueID", "type", *control.control_applescript.TRIGGER_KEYS & set(keys)]))
            continue
        if key.startswith("text/format@"):
            values[key] = text_format.read(reader, ws, uid)
        elif key.startswith(('videoEffectIndex/', 'videoEffects/')) and key != 'videoEffectIndex/enabled':
            values.update(video_fx.read_values(reader, ws, uid, [key], changes))
        elif key.startswith('indexed@'):
            original = key.split('/', 1)[1]
            selected = changes[key]
            op = normalize({original: selected}, values['type'].lower())[0]
            observed = control._scalar(reader, ws, uid, op['path'])
            value_key = next(name for name in selected if name not in {'inChannel', 'outChannel', 'channel', 'output', 'index', 'number'})
            values[key] = {**selected, value_key: observed}
        elif key in _ACTIONS:
            values[key] = control._scalar(reader, ws, uid, _ACTIONS[key])
        elif key in {"addSliceMarker", "deleteSliceMarker"}:
            values[key] = control._scalar(reader, ws, uid, "sliceMarkers")
        elif key in {"level", "sliderLevel", "mute/channel", "solo/channel", "videoEffectIndex/enabled", "sliceMarker/time", "sliceMarker/playCount", "inputChannelName", "gang"}:
            selected = changes.get(key)
            if not isinstance(selected, dict):
                raise ValueError(f"{key}: indexed selectors required.")
            op = normalize({key: selected}, values["type"].lower())[0]
            observed = control._scalar(reader, ws, uid, op["path"])
            value_key = next(name for name in selected if name not in {"inChannel", "outChannel", "channel", "output", "index", "number"})
            values[key] = {**selected, value_key: observed}
        elif key.startswith("text/format/"):
            if fragments is None:
                fragments = control._scalar(reader, ws, uid, "text/format")
                from ..cues.visual import TextRun
                if not isinstance(fragments, list) or not fragments:
                    raise ValueError("Text format fragments are unavailable.")
                for run in fragments:
                    TextRun.model_validate(run)
            if key == "text/format/fontFamilyAndStyle":
                families = {(run.get("fontFamily"), run.get("fontStyle")) for run in fragments}
                if len(families) != 1 or None in next(iter(families)):
                    raise ValueError("Font pair baseline is absent or mixed.")
                family_name, style = next(iter(families))
                values[key] = {"family": family_name, "style": style}
                continue
            attribute = key.removeprefix("text/format/").split("/")[0]
            if not all(isinstance(run, dict) and attribute in run for run in fragments):
                raise ValueError(f"{key}: fragments omit this attribute; no reliable baseline.")
            if not all(control._same(run[attribute], fragments[0][attribute]) for run in fragments):
                raise ValueError(f"{key}: mixed formatting requires a fragment edit.")
            values[key] = fragments[0][attribute]
            if key.count("/") == 3:
                values[key] = values[key].get(key.rsplit("/", 1)[1])
        else:
            values[key] = control._scalar(reader, ws, uid, key)
        if key == "crop" and isinstance(values[key], list):
            if len(values[key]) != 4:
                raise ValueError("crop: expected four OSC coordinates.")
            values[key] = Crop.model_validate(dict(zip(("top", "bottom", "left", "right"), values[key], strict=True))).model_dump()
        if key in {"preservePitch", "infiniteLoop"} and type(values[key]) is int and values[key] in (0, 1):
            values[key] = bool(values[key])
    final = control._read(reader, ws, uid, ["uniqueID", "type"])
    if final["type"] != values["type"]:
        raise ValueError("Cue type changed during reads.")
    return values


def _reference(reader, ws, route, uid):
    from ..settings.summarizers import _collection_items
    inventory = reader._request(_workspace_address(ws, route), workspace_id=ws).data
    match = next((x for x in _collection_items(inventory) if str(x.get("uniqueID", "")).casefold() == uid.casefold()), None)
    if match is None:
        raise ValueError(f"Reference UUID is absent from workspace {route}.")
    return match


def preflight(reader, ws, item, family):
    uid = str(item.cue_id).upper()
    changes = item.properties.model_dump(by_alias=True, exclude_unset=True) if item.properties is not None else {}
    supplied = [op.model_dump(exclude_unset=True) for op in item.operations]
    text_requests = [op for op in supplied if op["property"] == "text/format"]
    scalar_formats = any(key.startswith("text/format/") for key in changes) or any(op["property"].startswith("text/format/") for op in supplied)
    if "text" in changes and (scalar_formats or text_requests):
        raise ValueError("Separate content replacement and formatting with a fresh dry run.")
    if text_requests and scalar_formats:
        raise ValueError("Use typed format operations for all formatting destinations in this update.")
    fx_requests = [op for op in supplied if op['property'].startswith(('videoEffectIndex/', 'videoEffects/'))]
    if 'videoEffectIndex/enabled' in changes:
        legacy = changes.pop('videoEffectIndex/enabled')
        native = video_fx.inventory(reader, ws, uid)
        if not isinstance(native, list) or legacy['index'] >= len(native):
            raise ValueError('Legacy FX enabled: native instance inventory is unavailable.')
        effect_type = video_fx.native_type(reader, ws, uid, native, legacy['index'])
        fx_requests.append({'property': 'videoEffectIndex/enabled', 'args': {**legacy, 'effect_type': effect_type}})
    generic_requests = [op for op in supplied if not op['property'].startswith(('videoEffectIndex/', 'videoEffects/')) and op['property'] != 'text/format']
    requested_keys = set(changes) | {op['property'] for op in generic_requests}
    for aggregate in ('anchor', 'translation', 'scale', 'origin', 'text/format/shadowOffset'):
        if aggregate in requested_keys and any(key.startswith(aggregate + '/') for key in requested_keys):
            raise ValueError(f'Use {aggregate} or its components, not both.')
    slices = {'sliceMarker/time', 'sliceMarker/playCount', 'lastSlicePlayCount', 'addSliceMarker', 'deleteSliceMarker', 'deleteSliceMarkers'}
    if sum(op['property'] in slices for op in generic_requests) + len(slices & changes.keys()) > 1:
        raise ValueError('Use one slice operation per cue update.')
    if 'fileTarget' in changes and requested_keys & {'duration', 'startTime', 'endTime', 'rate', 'level', 'sliderLevel', 'sliceMarker/time', 'sliceMarker/playCount', 'addSliceMarker', 'deleteSliceMarker'}:
        raise ValueError('Retarget media separately before editing media-dependent properties.')
    if requested_keys & {'audioInputPatchID', 'audioOutputPatchID'} and requested_keys & {'level', 'sliderLevel', 'mute/channel', 'solo/channel', 'inputChannelName', 'gang'}:
        raise ValueError('Retarget audio patches separately before editing their channels.')
    for aggregate in ("anchor", "translation", "scale", "origin"):
        x, y = f"{aggregate}/x", f"{aggregate}/y"
        if x in changes and y in changes:
            changes[aggregate] = {"x": changes.pop(x), "y": changes.pop(y)}
    if "text/format/fontName" in changes and "text/format/fontFamilyAndStyle" in changes:
        raise ValueError("Use fontName or fontFamilyAndStyle, not both.")
    operations = normalize(changes, family)
    for op in operations:
        key = op["property"]
        if key not in _ACTIONS:
            changes[key] = op["arg_values"] if key in _STRUCTURED else changes[key] if key in _COLORS else op["arg_values"]["value"]
    indexed_dependencies = {}
    for sequence, request in enumerate(generic_requests):
        validation_item = control._FAMILIES[family][0].model_validate({'cue_id': uid, 'properties': {request['property']: request['args']}})
        _, _, validated_ops, validated_dependencies = preflight(reader, ws, validation_item, family)
        op = validated_ops[0]
        for dependency, value in validated_dependencies.items():
            if dependency in indexed_dependencies and not control._same(indexed_dependencies[dependency], value):
                raise ValueError('Indexed dependencies changed during preflight.')
            indexed_dependencies[dependency] = value
        key = f"indexed@{sequence}/{request['property']}"
        op.update(property=key, key=key)
        operations.append(op)
        changes[key] = op['arg_values']
    if len(operations) + len(fx_requests) + len(text_requests) > 50:
        raise ValueError('At most 50 operations per cue.')
    if len({op['path'] for op in operations}) != len(operations):
        raise ValueError('Duplicate visual destination.')
    before = read(reader, ws, uid, [*control._CONTEXT, *changes], changes)
    if before["type"] != control._FAMILIES[family][2][0]:
        raise ValueError(f"Expected {family} cue.")
    if any(before.get(key) is not False for key in ("isRunning", "isPaused", "isAuditioning")):
        raise ValueError("Source cue must be inactive.")
    if any(before.get(key) is not False for key in ("isBroken", "isWarning")) and (bool(fx_requests or text_requests) or not set(changes) <= {"name", "number", "notes", "stageID", "fileTarget", "videoInputPatchID", "audioInputPatchID", "audioOutputPatchID"}):
        recovery = {"mute/channel", "solo/channel", "mute/channel/clear", "solo/channel/clear"}
        if before.get("isBroken") is not False or before.get("isWarning") is not True or bool(fx_requests or text_requests) or not set(changes) <= recovery:
            raise ValueError("Visual changes require readable cue health; repair routing/media first.")
        from .operations import _phase9_mute_solo_warning_recovery_allowed
        before.update(control._read(reader, ws, uid, ["uniqueID", "type", "muteChannels", "soloChannels"]))
        if not all(_phase9_mute_solo_warning_recovery_allowed({"profile": "video_basic", "operations": [op]}, before) for op in operations):
            raise ValueError("Warnings allow only clearing readable, existing mutes or solos.")
    if "duration" in changes and before.get("allowsEditingDuration") is not True:
        raise ValueError("This cue has no editable duration.")
    if "fadeAndStopOthers" in changes and type(before["fadeAndStopOthers"]) is not int:
        raise ValueError("Fade & Stop scope is not reliably readable; boolean is not a mode.")
    dependencies = indexed_dependencies
    if text_requests:
        saved = text_format.read(reader, ws, uid)
        text_format.preflight(saved, text_requests, changes)
        dependencies["text_format"] = saved
        for sequence, request in enumerate(text_requests):
            op = text_format.normalize(request, sequence, saved)
            key = op["property"]
            before[key] = saved
            changes[key] = request["args"]
            operations.append(op)
    if fx_requests:
        fx_before, fx_changes, fx_ops, fx_dependencies = video_fx.preflight(reader, ws, uid, fx_requests, other_properties=bool(changes) or bool([op for op in supplied if op['property'] == 'text/format']))
        before.update(fx_before)
        changes.update(fx_changes)
        operations.extend(fx_ops)
        dependencies.update(fx_dependencies)
    if {"scale", "scale/x", "scale/y"} & changes.keys():
        aspect = control._scalar(reader, ws, uid, "preserveAspectRatio")
        if type(aspect) is not bool:
            raise ValueError("Scale editing requires readable preserveAspectRatio.")
        requested = changes.get("scale")
        if requested and changes.get("preserveAspectRatio", aspect) and requested["x"] != requested["y"]:
            raise ValueError("Nonuniform scale requires preserveAspectRatio=false.")
        if changes.get("preserveAspectRatio") is True and requested is None:
            raise ValueError("Use an explicit scale pair when enabling preserveAspectRatio in the same update.")
        dependencies["aspect_ratio"] = aspect
        if changes.get("preserveAspectRatio") is True:
            operations.sort(key=lambda op: op["property"] == "preserveAspectRatio")
    if "text/format/shadowOffset" in changes and {"text/format/shadowOffset/width", "text/format/shadowOffset/height"} & changes.keys():
        raise ValueError("Use shadowOffset or its components, not both.")
    audio_changes = {"level", "sliderLevel", "mute/channel", "solo/channel", "mute/channel/clear", "solo/channel/clear", "inputChannelName", "gang"}
    if {"audioInputPatchID", "audioOutputPatchID"} & changes.keys() and audio_changes & changes.keys():
        raise ValueError("Retarget audio patches separately before editing their channels.")
    if "fileTarget" in changes and ({"duration", "startTime", "endTime", "rate", "level", "sliderLevel", "sliceMarker/time", "sliceMarker/playCount", "addSliceMarker", "deleteSliceMarker"} & changes.keys()):
        raise ValueError("Retarget media separately before editing media-dependent properties.")
    for key, value in changes.items():
        if key.startswith(('videoEffectIndex/', 'videoEffects/', 'indexed@', 'text/format@')):
            continue
        if before[key] is None:
            raise ValueError(f"{key}: baseline unavailable.")
        if key not in _ACTIONS and key not in {"addSliceMarker", "deleteSliceMarker"}:
            if key not in control.control_applescript.TRIGGER_KEYS:
                control._FAMILIES[family][1].model_validate({key: before[key]})
                normalize({key: before[key]}, family)
    for key, route in {"stageID": "settings/video/stages", "videoInputPatchID": "settings/video/inputPatchList",
                       "audioInputPatchID": "settings/audio/inputPatchList", "audioOutputPatchID": "settings/audio/patchList"}.items():
        if key in changes and changes[key]:
            dependencies[route] = _reference(reader, ws, route, changes[key])
    if "number" in changes and changes["number"]:
        nodes = control._read_snapshot(reader, ws)["nodes"].values()
        if any(node.get("number") == changes["number"] and str(node["uniqueID"]).upper() != uid for node in nodes):
            raise ValueError("Cue number is already assigned.")
    if any(key.startswith("timecodeTrigger/") for key in changes):
        dependencies["timecode"] = control._timecode(reader, ws, before, changes)
    if "text" in changes or any(key.startswith("text/format/") for key in changes):
        dependencies["text/format"] = control._scalar(reader, ws, uid, "text/format")
        from ..cues.visual import TextRun
        if not isinstance(dependencies["text/format"], list):
            raise ValueError("Text formatting baseline unavailable.")
        for run in dependencies["text/format"]:
            TextRun.model_validate(run)
    if "fileTarget" in changes:
        from pathlib import Path
        path = Path(changes["fileTarget"])
        if not path.is_absolute() or not path.is_file():
            raise ValueError("fileTarget requires an existing absolute file path.")
        stat = path.stat()
        dependencies["fileTarget"] = {"path": str(path), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}
    if {"startTime", "endTime", "rate", "playCount", "infiniteLoop", "preservePitch"} & changes.keys():
        evidence = control._read(reader, ws, uid, ["uniqueID", "audioTrackFormats", "numChannelsIn", "levels"])
        dependencies["media"] = {"fileTarget": control._scalar(reader, ws, uid, "fileTarget"),
                                  "numChannelsIn": evidence.get("numChannelsIn")}
        formats = evidence.get("audioTrackFormats")
        channels = evidence.get("numChannelsIn")
        levels = evidence.get("levels")
        has_audio = (
            isinstance(formats, str) and bool(formats.strip())
            or isinstance(formats, (list, tuple, set, dict)) and bool(formats)
            or isinstance(channels, (int, float)) and not isinstance(channels, bool) and channels > 0
            or isinstance(levels, (list, tuple)) and bool(levels)
        )
        if not has_audio:
            raise ValueError("Video time/loop editing requires readable embedded audio evidence.")
    if {"startTime", "endTime"} & changes.keys():
        start = changes.get("startTime", control._scalar(reader, ws, uid, "startTime"))
        end = changes.get("endTime", control._scalar(reader, ws, uid, "endTime"))
        if type(start) not in (int, float) or type(end) not in (int, float) or start >= end:
            raise ValueError("startTime must precede endTime.")
        dependencies["trim"] = {"startTime": control._scalar(reader, ws, uid, "startTime"), "endTime": control._scalar(reader, ws, uid, "endTime")}

    audio_keys = {"level", "sliderLevel", "mute/channel", "solo/channel", "mute/channel/clear", "solo/channel/clear", "inputChannelName", "gang"}
    if audio_keys & changes.keys():
        channels = control._scalar(reader, ws, uid, "numChannelsIn")
        patch_id = changes.get("audioOutputPatchID", control._scalar(reader, ws, uid, "audioOutputPatchID"))
        if type(channels) is not int or channels < 1 or not patch_id:
            raise ValueError("Audio input channels and output patch must be readable.")
        patch = reader._request(_workspace_address(ws, f"settings/audio/patchID/{patch_id}"), workspace_id=ws).data
        if not isinstance(patch, dict) or str(patch.get("uniqueID", "")).casefold() != patch_id.casefold():
            raise ValueError("Audio patch identity could not be verified.")
        outputs = patch.get("cueOutputChannels")
        if type(outputs) is not int or outputs < 1:
            raise ValueError("Audio output channel bounds are unavailable.")
        for key in audio_keys & changes.keys():
            selected = changes[key] if isinstance(changes[key], dict) else {}
            if selected.get("number", 0) > channels:
                raise ValueError("Input channel name is outside the cue bounds.")
            if selected.get("inChannel", 0) > channels or selected.get("outChannel", selected.get("channel", selected.get("output", 0))) > outputs:
                raise ValueError("Audio channel is outside the cue/patch bounds.")
        dependencies["audio_bounds"] = {"numChannelsIn": channels, "patch_id": patch_id, "outputs": outputs}
    if family == "camera" and {"channels", "channelOffset"} & changes.keys():
        input_id = changes.get("audioInputPatchID", control._scalar(reader, ws, uid, "audioInputPatchID"))
        if not input_id:
            raise ValueError("Camera input channel editing requires a valid input patch.")
        raise ValueError("Camera input channel bounds have no validated OSC inventory; channel edits remain blocked.")
    if "videoEffectIndex/enabled" in changes:
        effects = control._scalar(reader, ws, uid, "videoEffects")
        index = changes["videoEffectIndex/enabled"]["index"]
        if not isinstance(effects, list) or index >= len(effects):
            raise ValueError("Video effect index is unavailable.")
        dependencies["videoEffects"] = effects

    slice_keys = {"sliceMarker/time", "sliceMarker/playCount", "lastSlicePlayCount", "addSliceMarker", "deleteSliceMarker", "deleteSliceMarkers"}
    if slice_keys & changes.keys():
        if len(slice_keys & changes.keys()) > 1:
            raise ValueError("Use one slice operation per cue update.")
        markers = control._scalar(reader, ws, uid, "sliceMarkers")
        from .operations import _phase8c_expected_slice_markers, _phase8c_baseline_slice_markers
        context = {"sliceMarkers": markers, "startTime": control._scalar(reader, ws, uid, "startTime"),
                   "endTime": control._scalar(reader, ws, uid, "endTime")}
        if _phase8c_baseline_slice_markers(context) is None:
            raise ValueError("Slice inventory is unavailable.")
        op = next(op for op in operations if op["property"] in slice_keys)
        expected, error = _phase8c_expected_slice_markers(op, context)
        if error:
            raise ValueError(error)
        dependencies["sliceMarkers"] = markers
        dependencies["slice_expected"] = expected
    return before, changes, operations, dependencies


def check_dependencies(reader, ws, uid, dependencies):
    video_fx.check_dependencies(reader, ws, uid, dependencies)
    if "text_format" in dependencies:
        text_format.check_dependencies(reader, ws, uid, dependencies["text_format"])
    for route, expected in dependencies.items():
        if route.startswith("settings/"):
            if _reference(reader, ws, route, expected["uniqueID"]) != expected:
                raise ValueError("Routing dependency changed before setter.")
        elif route == "aspect_ratio":
            if control._scalar(reader, ws, uid, "preserveAspectRatio") is not expected:
                raise ValueError("Aspect ratio changed before setter.")
        elif route == "text/format":
            if control._scalar(reader, ws, uid, route) != expected:
                raise ValueError("Text fragments changed before setter.")
        elif route == "media":
            if any(control._scalar(reader, ws, uid, key) != value for key, value in expected.items()):
                raise ValueError("Media dependency changed before setter.")
        elif route == "audio_bounds":
            patch = reader._request(_workspace_address(ws, f"settings/audio/patchID/{expected['patch_id']}"), workspace_id=ws).data
            if control._scalar(reader, ws, uid, "audioOutputPatchID") != expected["patch_id"] or control._scalar(reader, ws, uid, "numChannelsIn") != expected["numChannelsIn"] or not isinstance(patch, dict) or str(patch.get("uniqueID", "")).casefold() != expected["patch_id"].casefold() or patch.get("cueOutputChannels") != expected["outputs"]:
                raise ValueError("Audio channel bounds changed before setter.")
        elif route in {"videoEffects", "sliceMarkers"}:
            if control._scalar(reader, ws, uid, route) != expected:
                raise ValueError(f"{route} changed before setter.")
        elif route == "fileTarget":
            from pathlib import Path
            stat = Path(expected["path"]).stat()
            if stat.st_size != expected["size"] or stat.st_mtime_ns != expected["mtime_ns"]:
                raise ValueError("Media file changed before setter.")


def edit_video_cues(reader, workspace_id, updates, dry_run=None):
    return control.edit_control_cues(reader, workspace_id, updates, dry_run, _family="video")


def edit_camera_cues(reader, workspace_id, updates, dry_run=None):
    return control.edit_control_cues(reader, workspace_id, updates, dry_run, _family="camera")


def edit_text_cues(reader, workspace_id, updates, dry_run=None):
    return control.edit_control_cues(reader, workspace_id, updates, dry_run, _family="text")


def capabilities(kind, result):
    family = kind.lower()
    model = control._FAMILIES[family][1]
    fields = {field.alias or name for name, field in model.model_fields.items()}
    blocked = {}
    fx_capabilities = video_fx.capabilities(result.video.videoEffects if result.video else None)
    if not fx_capabilities['allowed_operations']:
        blocked['videoEffectIndex/enabled'] = 'Use a typed FX operation with fresh native index/type proof; parameter keys alone cannot prove identity.'
    if result.basics is None or result.basics.allowsEditingDuration is not True:
        blocked["duration"] = "Cue reports no editable duration or capability is unknown."
    if result.triggers is None or type(result.triggers.fadeAndStopOthers) is not int:
        blocked["fadeAndStopOthers"] = "Scope readback must be an integer, not boolean."
    if kind == "Camera":
        blocked.update({key: "Input channel bounds require validated OSC inventory." for key in ("channels", "channelOffset")})
    if kind == "Video" and (result.audio is None or result.audio.sliceMarkers is None):
        blocked.update({key: "OSC slice inventory is unavailable; absence does not prove an empty list."
                        for key in ("addSliceMarker", "deleteSliceMarker", "deleteSliceMarkers", "sliceMarker/time", "sliceMarker/playCount", "lastSlicePlayCount")})
    if kind == "Text" and result.text is not None:
        for key in fields:
            if key.startswith("text/format/"):
                name = key.removeprefix("text/format/").split("/")[0]
                if name == "fontFamilyAndStyle":
                    runs = result.text.fragments
                    if not runs or any(run.fontFamily is None or run.fontStyle is None or (run.fontFamily, run.fontStyle) != (runs[0].fontFamily, runs[0].fontStyle) for run in runs):
                        blocked[key] = "Font family/style is absent or mixed between fragments."
                    continue
                runs = result.text.fragments
                if not runs or any(getattr(run, name, None) is None for run in runs) or any(
                        not control._same(getattr(run, name), getattr(runs[0], name)) for run in runs):
                    blocked[key] = "Format fragments omit this attribute or have mixed values."
    return control.control_applescript.trigger_capabilities({"tool": f"qlab_edit_{family}_cues", "allowed_properties": sorted(fields - blocked.keys()),
            'video_fx': fx_capabilities,
            **({"text_format": text_format.capabilities()} if kind == "Text" else {}),
            "blocked_properties": blocked, "requires_fresh_preflight": True,
            "unavailable_via_osc": ["Hotkey/MIDI/Wall Clock setup", "Timecode activation/display"],
            "excluded": ["Audio Maps", "/live", "cue execution", "workspace stage/region edits"],
            "pending_validation": ["FX LinearKey/DropShadow creation, ambiguous native identities and unavailable native parameter baselines", "Audio FX", "Non-Latin Text fallback, complex words, unobserved fonts and partial shadows", "Camera input channel bounds"],
            "blocked_operations": ["setDefaultLevels", "setSilentLevels"]}, result.triggers)


def matches(key, observed, requested, dependencies, reader=None, ws=None, uid=None):
    if key.startswith("text/format@"):
        expected = text_format.advance(dependencies["text_format"], {"property": "text/format", "args": requested})
        if not text_format.matches(observed, expected):
            return False
        dependencies["text_format"] = observed
        return True
    if key.startswith(('videoEffectIndex/', 'videoEffects/')):
        return video_fx.matches(key, observed, requested, dependencies, reader, ws, uid)
    fragments = None
    if key == "text" and reader is not None:
        fragments = control._scalar(reader, ws, uid, "text/format")
        previous = dependencies.get("text/format")
        if requested and previous:
            if not isinstance(fragments, list) or not fragments or not isinstance(fragments[0], dict):
                return False
            if any(not control._same(fragments[0].get(k), v) for k, v in previous[0].items() if k != "range"):
                return False
    if key == "resetRotation":
        return control._same(observed, [0, 0, 0, 1])
    if key in {"mute/channel/clear", "solo/channel/clear", "deleteSliceMarkers"}:
        return observed == []
    if key in {"addSliceMarker", "deleteSliceMarker"}:
        return control._same(observed, dependencies["slice_expected"])
    if key in {"level", "sliderLevel"}:
        import math
        actual, wanted = observed.get("decibel"), requested["decibel"]
        if type(actual) in (int, float) and type(wanted) in (int, float):
            return math.isfinite(actual) and math.isclose(actual, wanted, abs_tol=1e-3)
    matched = control._same(observed, requested)
    if matched and key == "fileTarget" and requested:
        matched = reader is not None and control._scalar(reader, ws, uid, "isBroken") is False
    if matched and key == "preserveAspectRatio" and "aspect_ratio" in dependencies:
        dependencies["aspect_ratio"] = observed
    if matched and reader is not None and (key == "text" or key.startswith("text/format/")):
        if fragments is None:
            fragments = control._scalar(reader, ws, uid, "text/format")
        from ..cues.visual import TextRun
        if not isinstance(fragments, list):
            return False
        for run in fragments:
            TextRun.model_validate(run)
        dependencies["text/format"] = fragments
    return matched


def expected_before_setter(key, dependencies, default):
    if key.startswith("text/format@"):
        return dependencies["text_format"]
    state = dependencies.get('video_fx')
    if state is None:
        return default
    op = next((op for op in state['operations'] if op['property'] == key), None)
    if op is None:
        return default
    prop, args = op['fx_property'], op['arg_values']
    if prop in video_fx.STRUCTURAL:
        return state['stack']
    item = state['stack'][args['index']]
    return item['enabled'] if prop.endswith('/enabled') else item['parameters'] if prop.endswith('/parameters') else item['parameters'][args['key']]
