"""Data-driven edit registry for QLab cue update profiles."""

from __future__ import annotations

from dataclasses import dataclass
from string import Formatter
from typing import Any

from ..errors import UnsafeWriteOperationError


COMMON_UPDATE_PROFILE = "common"
AUDIO_BASIC_UPDATE_PROFILE = "audio_basic"
TEXT_BASIC_UPDATE_PROFILE = "text_basic"


@dataclass(frozen=True)
class CuePropertySpec:
    name: str
    path: str | None = None
    args: tuple[tuple[str, str], ...] = (("value", "any"),)
    osc_args: tuple[str, ...] = ("value",)
    read_key: str | None = None
    modes: tuple[str, ...] = ("saved",)
    risk_tier: str = "safe"
    real_write_enabled: bool = False
    planned_only_reason: str | None = None


@dataclass(frozen=True)
class UpdateProfileSpec:
    name: str
    cue_types: tuple[str, ...]
    properties: tuple[CuePropertySpec, ...]
    risk_tier: str
    real_write_enabled: bool
    description: str


def _prop(
    name: str,
    validator: str = "any",
    *,
    path: str | None = None,
    read_key: str | None = None,
    modes: tuple[str, ...] = ("saved",),
    risk_tier: str = "safe",
    real_write_enabled: bool = False,
    planned_only_reason: str | None = None,
) -> CuePropertySpec:
    return CuePropertySpec(
        name=name,
        path=path,
        args=(("value", validator),),
        osc_args=("value",),
        read_key=read_key if read_key is not None else name,
        modes=modes,
        risk_tier=risk_tier,
        real_write_enabled=real_write_enabled,
        planned_only_reason=planned_only_reason,
    )


def _op(
    name: str,
    args: tuple[tuple[str, str], ...],
    *,
    path: str | None = None,
    osc_args: tuple[str, ...] | None = None,
    read_key: str | None = None,
    modes: tuple[str, ...] = ("saved",),
    risk_tier: str = "medium",
    real_write_enabled: bool = False,
    planned_only_reason: str = "planned_only_until_real_world_validation",
) -> CuePropertySpec:
    path_args = _path_arg_names(path or name)
    return CuePropertySpec(
        name=name,
        path=path,
        args=args,
        osc_args=osc_args if osc_args is not None else tuple(arg for arg, _ in args if arg not in path_args),
        read_key=read_key,
        modes=modes,
        risk_tier=risk_tier,
        real_write_enabled=real_write_enabled,
        planned_only_reason=planned_only_reason if not real_write_enabled else None,
    )


def _planned_prop(
    name: str,
    validator: str = "any",
    *,
    path: str | None = None,
    read_key: str | None = None,
    reason: str,
) -> CuePropertySpec:
    return _prop(
        name,
        validator,
        path=path,
        read_key=read_key,
        risk_tier="high",
        real_write_enabled=False,
        planned_only_reason=reason,
    )


def _path_arg_names(path: str) -> tuple[str, ...]:
    return tuple(field_name for _, field_name, _, _ in Formatter().parse(path) if field_name)


def _planned_patch_refs(prefix: str, *, validator: str) -> tuple[CuePropertySpec, ...]:
    return (
        _planned_prop(f"{prefix}Name", "string", reason="patch_or_map_refs_need_dedicated_resolution"),
        _planned_prop(f"{prefix}Number", "non_negative_int", reason="patch_or_map_refs_need_dedicated_resolution"),
        _planned_prop(f"{prefix}ID", "string", reason="patch_or_map_refs_need_dedicated_resolution"),
    )


def _rgba_args() -> tuple[tuple[str, str], ...]:
    return (("red", "color_component"), ("green", "color_component"), ("blue", "color_component"), ("alpha", "alpha"))


def _group_properties() -> tuple[CuePropertySpec, ...]:
    return (
        _prop("mode", "int", real_write_enabled=True),
        _planned_prop("playbackPosition", "string", reason="playhead_changes_are_control_behavior"),
        _planned_prop("playbackPositionID", "string", reason="playhead_changes_are_control_behavior"),
        _op(
            "moveCartCue",
            (("child", "non_empty_string"), ("row", "non_negative_int"), ("column", "non_negative_int")),
            path="moveCartCue/{child}",
            risk_tier="high",
            planned_only_reason="cart_child_order_changes_need_dedicated_validation",
        ),
        _prop("playlist/doLoop", "boolean", real_write_enabled=True),
        _prop("playlist/doShuffle", "boolean", real_write_enabled=True),
        _prop("playlist/doCrossfade", "boolean", real_write_enabled=True),
        _prop("playlist/crossfade/duration", "non_negative_number", real_write_enabled=True),
        _prop("timecodeFreewheelTime", "non_negative_number", real_write_enabled=True),
        _prop("timecodeLookbackTime", "non_negative_number", real_write_enabled=True),
        _prop("timecodeSMPTEFormat", "int", real_write_enabled=True),
        _prop("timecodeStartBehavior", "int", real_write_enabled=True),
        _prop("timecodeStopBehavior", "int", real_write_enabled=True),
        _prop("timecodeSyncMode", "int", real_write_enabled=True),
    )


COMMON_PROPERTIES = (
    _prop("name", "string", real_write_enabled=True),
    _prop("number", "string", real_write_enabled=True),
    _prop("notes", "string", real_write_enabled=True),
    _prop("armed", "boolean", real_write_enabled=True),
    _prop("flagged", "boolean", real_write_enabled=True),
    _prop("colorName", "string", real_write_enabled=True),
    _prop("preWait", "non_negative_number", real_write_enabled=True),
    _prop("postWait", "non_negative_number", real_write_enabled=True),
    _prop("duration", "non_negative_number", real_write_enabled=True),
    _prop("tempDuration", "non_negative_number", real_write_enabled=True),
    _prop("continueMode", "continue_mode", real_write_enabled=True),
    _prop("skipIfDisarmed", "boolean", real_write_enabled=True),
    _prop("autoLoad", "boolean", real_write_enabled=True),
)

AUDIO_SAFE_PROPERTIES = (
    _prop("rate", "rate", real_write_enabled=True),
    _prop("startTime", "non_negative_number", real_write_enabled=True),
    _prop("endTime", "non_negative_number", real_write_enabled=True),
    _prop("playCount", "positive_int", real_write_enabled=True),
    _prop("infiniteLoop", "boolean", real_write_enabled=True),
    _prop("preservePitch", "boolean", real_write_enabled=True),
)

AUDIO_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    *_planned_patch_refs("audioOutputPatch", validator="patch_ref"),
    *_planned_patch_refs("audioMap", validator="patch_ref"),
    _planned_prop("doFade", "boolean", reason="integrated_fade_changes_playback_behavior"),
    _planned_prop("lockFadeToCue", "boolean", reason="integrated_fade_changes_playback_behavior"),
    _op(
        "level",
        (("inChannel", "positive_int"), ("outChannel", "positive_int"), ("decibel", "number")),
        path="level/{inChannel}/{outChannel}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "sliderLevel",
        (("channel", "positive_int"), ("decibel", "number")),
        path="sliderLevel/{channel}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "mute",
        (("output", "positive_int"), ("value", "boolean")),
        path="mute/channel/{output}",
        risk_tier="high",
        planned_only_reason="mute_changes_audio_output",
    ),
    _op(
        "solo",
        (("output", "positive_int"), ("value", "boolean")),
        path="solo/{output}",
        risk_tier="high",
        planned_only_reason="solo_changes_audio_output",
    ),
    _op(
        "sliceMarker",
        (("index", "non_negative_int"), ("time", "non_negative_number"), ("playCount", "int_or_minus_one")),
        path="sliceMarker/{index}",
        risk_tier="medium",
        planned_only_reason="slice_editing_needs_dedicated_validation",
    ),
    _op(
        "addSliceMarker",
        (("time", "non_negative_number"), ("playCount", "int_or_minus_one")),
        path="addSliceMarker",
        risk_tier="medium",
        planned_only_reason="slice_editing_needs_dedicated_validation",
    ),
    _op(
        "object/position",
        (("object", "non_empty_string"), ("x", "number"), ("y", "number")),
        path="object/{object}/position",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/spread",
        (("object", "non_empty_string"), ("spread", "number")),
        path="object/{object}/spread",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "audioMap/filter/position",
        (("filter", "non_empty_string"), ("x", "number"), ("y", "number")),
        path="audioMap/filter/{filter}/position",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/filter/passthrough",
        (("filter", "non_empty_string"), ("output", "positive_int"), ("value", "boolean")),
        path="audioMap/filter/{filter}/passthrough/{output}",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
)

MIC_CATALOG_PROPERTIES = (
    *_planned_patch_refs("audioInputPatch", validator="patch_ref"),
    _prop("channelOffset", "non_negative_int", risk_tier="medium", real_write_enabled=True),
    _prop("channels", "positive_int", risk_tier="medium", real_write_enabled=True),
    *AUDIO_CATALOG_PROPERTIES,
)

VIDEO_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    _op("anchor", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _prop("anchor/x", "number", risk_tier="medium", real_write_enabled=True),
    _prop("anchor/y", "number", risk_tier="medium", real_write_enabled=True),
    _op("translation", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _prop("translation/x", "number", risk_tier="medium", real_write_enabled=True),
    _prop("translation/y", "number", risk_tier="medium", real_write_enabled=True),
    _op("scale", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _prop("scale/x", "number", risk_tier="medium", real_write_enabled=True),
    _prop("scale/y", "number", risk_tier="medium", real_write_enabled=True),
    _prop("rotation", "number", risk_tier="medium", real_write_enabled=True),
    _prop("opacity", "opacity", risk_tier="medium", real_write_enabled=True),
    _op("crop", (("top", "number"), ("bottom", "number"), ("left", "number"), ("right", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _prop("cropTop", "number", risk_tier="medium", real_write_enabled=True),
    _prop("cropBottom", "number", risk_tier="medium", real_write_enabled=True),
    _prop("cropLeft", "number", risk_tier="medium", real_write_enabled=True),
    _prop("cropRight", "number", risk_tier="medium", real_write_enabled=True),
    _prop("blendMode", "string", risk_tier="medium", real_write_enabled=True),
    _prop("clockType", "string", risk_tier="medium", real_write_enabled=True),
    *_planned_patch_refs("stage", validator="patch_ref"),
    *_planned_patch_refs("videoOutputPatch", validator="patch_ref"),
    _planned_prop("videoEffect", "any", reason="video_effect_parameters_need_profile_specific_validation"),
)

TEXT_SAFE_PROPERTIES = (
    _prop("text", "string", real_write_enabled=True),
    _prop("fixedWidth", "non_negative_number", real_write_enabled=True),
    _prop("text/format/alignment", "text_alignment", real_write_enabled=True),
    _prop("text/format/fontName", "non_empty_string", real_write_enabled=True),
    _prop("text/format/fontSize", "positive_number", real_write_enabled=True),
)

TEXT_CATALOG_PROPERTIES = (
    _op("text/format", (("format", "dict_or_json_string"),), path="text/format", planned_only_reason="rich_text_format_needs_dedicated_validation"),
    _op("text/format/fontFamilyAndStyle", (("family", "non_empty_string"), ("style", "non_empty_string")), planned_only_reason="font_pair_needs_system_font_validation"),
    _op("text/format/color", _rgba_args(), planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/backgroundColor", _rgba_args(), planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/shadowColor", _rgba_args(), planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/underlineColor", _rgba_args(), planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/strikethroughColor", _rgba_args(), planned_only_reason="text_color_changes_need_visual_validation"),
    _planned_prop("text/format/underlineStyle", "text_line_style", reason="text_decoration_needs_visual_validation"),
    _planned_prop("text/format/strikethroughStyle", "text_line_style", reason="text_decoration_needs_visual_validation"),
    *VIDEO_CATALOG_PROPERTIES,
)

LIGHT_CATALOG_PROPERTIES = (
    _planned_prop("lightCommandText", "string", reason="light_commands_can_affect_visual_output"),
    _op("setLight", (("command", "dict_or_json_string"),), risk_tier="high", planned_only_reason="light_commands_can_affect_visual_output"),
    _op("replaceLightCommand", (("command", "dict_or_json_string"),), risk_tier="high", planned_only_reason="light_commands_can_affect_visual_output"),
    _op("removeLightCommand", (("index", "non_negative_int"),), risk_tier="high", planned_only_reason="light_commands_can_affect_visual_output"),
    _op("safeSortCommands", (), path="safeSortCommands", risk_tier="high", planned_only_reason="light_commands_can_affect_visual_output"),
    _planned_prop("subcontroller", "string", reason="light_dashboard_changes_need_validation"),
    _planned_prop("parameterValues", "dict_or_json_string", reason="fixture_parameter_changes_need_validation"),
)

FADE_CATALOG_PROPERTIES = (
    _planned_prop("stopTargetWhenDone", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("audioMapTargetID", "string", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("targetMode", "int", reason="target_behavior_needs_validation"),
    _planned_prop("levelsMode", "int", reason="fade_level_mode_needs_validation"),
    _planned_prop("mode", "int", reason="fade_mode_needs_validation"),
    _planned_prop("rotation", "number", reason="fade_geometry_needs_target_validation"),
    _planned_prop("rotationType", "int", reason="fade_geometry_needs_target_validation"),
    _planned_prop("doOpacity", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doRate", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doRotation", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doScale", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doTranslation", "boolean", reason="fade_target_behavior_needs_validation"),
    _op("doLevel", (("row", "non_negative_int"), ("column", "non_negative_int"), ("value", "boolean")), path="doLevel/{row}/{column}", risk_tier="high", planned_only_reason="fade_level_targets_need_validation"),
    _op("doObjectLevel", (("row", "non_negative_int"), ("object", "non_empty_string"), ("value", "boolean")), path="doObjectLevel/{row}/{object}", risk_tier="high", planned_only_reason="fade_object_targets_need_validation"),
)

NETWORK_CATALOG_PROPERTIES = (
    *_planned_patch_refs("networkPatch", validator="patch_ref"),
    _planned_prop("messageType", "int", reason="network_message_mode_needs_validation"),
    _planned_prop("protocol", "string", reason="network_protocol_changes_need_validation"),
    _planned_prop("message", "string", reason="network_messages_can_trigger_external_systems"),
    _planned_prop("customString", "string", reason="network_messages_can_trigger_external_systems"),
    _op("oscMessage", (("address", "non_empty_string"), ("arguments", "list"),), path="message", risk_tier="high", planned_only_reason="network_messages_can_trigger_external_systems"),
    _planned_prop("resend", "boolean", reason="network_resend_behavior_needs_validation"),
)

MIDI_CATALOG_PROPERTIES = (
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
    _planned_prop("messageType", "int", reason="midi_message_mode_needs_validation"),
    _planned_prop("channel", "midi_channel", reason="midi_can_trigger_external_devices"),
    _planned_prop("command", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("commandFormat", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("status", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("note", "byte", path="byte1", read_key="byte1", reason="midi_voice_alias_needs_message_type_validation"),
    _planned_prop("velocity", "byte", path="byte2", read_key="byte2", reason="midi_voice_alias_needs_message_type_validation"),
    _planned_prop("programChange", "byte", path="byte1", read_key="byte1", reason="midi_voice_alias_needs_message_type_validation"),
    _planned_prop("pitchBend", "byte_combo", path="byteCombo", read_key="byteCombo", reason="midi_voice_alias_needs_message_type_validation"),
    _planned_prop("byte1", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("byte2", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("byteCombo", "byte_combo", reason="midi_can_trigger_external_devices"),
    _planned_prop("controlNumber", "byte_combo", reason="midi_can_trigger_external_devices"),
    _planned_prop("controlValue", "byte_combo", reason="midi_can_trigger_external_devices"),
    _planned_prop("deviceID", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("endValue", "byte_combo", reason="midi_can_trigger_external_devices"),
    _planned_prop("macro", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("rawString", "string", reason="sysex_can_trigger_external_devices"),
    _planned_prop("qList", "string", reason="msc_fields_need_validation"),
    _planned_prop("qNumber", "string", reason="msc_fields_need_validation"),
    _planned_prop("qPath", "string", reason="msc_fields_need_validation"),
    _planned_prop("timecodeString", "string", reason="msc_timecode_needs_validation"),
    _planned_prop("timecodeFormat", "int", reason="msc_timecode_needs_validation"),
)

MIDI_FILE_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    _prop("rate", "rate", risk_tier="medium", real_write_enabled=True),
    _prop("startTime", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("endTime", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("duration", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("playCount", "positive_int", risk_tier="medium", real_write_enabled=True),
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
)

TIMECODE_CATALOG_PROPERTIES = (
    _prop("timecodeMode", "int", risk_tier="medium", real_write_enabled=True),
    _prop("timecodeString", "string", risk_tier="medium", real_write_enabled=True),
    _prop("timecodeFormat", "int", risk_tier="medium", real_write_enabled=True),
    _prop("timecodeFrameRate", "positive_int", path="framerate", read_key="framerate", risk_tier="medium", real_write_enabled=True),
    _prop("startTime", "string", risk_tier="medium", real_write_enabled=True),
    _prop("endTime", "string", risk_tier="medium", real_write_enabled=True),
    *_planned_patch_refs("audioOutputPatch", validator="patch_ref"),
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
)

TARGET_CATALOG_PROPERTIES = (
    _planned_prop("cueTargetNumber", "string", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("cueTargetID", "string", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("cueTargetName", "string", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("targetMode", "int", reason="target_behavior_needs_validation"),
)

RESET_CATALOG_PROPERTIES = (
    _planned_prop("audioMapTargetID", "string", reason="reset_targets_need_validation"),
    _planned_prop("targetMode", "int", reason="reset_targets_need_validation"),
)

DEVAMP_CATALOG_PROPERTIES = (
    _planned_prop("cueTargetNumber", "string", reason="devamp_targets_need_validation"),
    _planned_prop("cueTargetID", "string", reason="devamp_targets_need_validation"),
    _planned_prop("cueTargetName", "string", reason="devamp_targets_need_validation"),
    _planned_prop("targetMode", "int", reason="devamp_targets_need_validation"),
    _planned_prop("stopTargetWhenSliceEnds", "boolean", reason="devamp_targets_need_validation"),
)

SCRIPT_CATALOG_PROPERTIES = (
    _planned_prop("scriptSource", "string", reason="script_execution_risk"),
    _planned_prop("scriptText", "string", path="scriptSource", read_key="scriptSource", reason="script_execution_risk"),
)


UPDATE_PROFILES: dict[str, UpdateProfileSpec] = {
    COMMON_UPDATE_PROFILE: UpdateProfileSpec(
        COMMON_UPDATE_PROFILE,
        (),
        COMMON_PROPERTIES,
        "safe",
        True,
        "Safe common cue properties.",
    ),
    "memo_basic": UpdateProfileSpec("memo_basic", ("Memo",), COMMON_PROPERTIES, "safe", True, "Memo cue common properties."),
    "wait_basic": UpdateProfileSpec("wait_basic", ("Wait",), COMMON_PROPERTIES, "safe", True, "Wait cue common properties."),
    "group_basic": UpdateProfileSpec(
        "group_basic",
        ("Group", "Cue List", "Cue Cart"),
        (*COMMON_PROPERTIES, *_group_properties()),
        "medium",
        True,
        "Group, cue list, and cue cart properties.",
    ),
    AUDIO_BASIC_UPDATE_PROFILE: UpdateProfileSpec(
        AUDIO_BASIC_UPDATE_PROFILE,
        ("Audio",),
        (*COMMON_PROPERTIES, *AUDIO_SAFE_PROPERTIES, *AUDIO_CATALOG_PROPERTIES),
        "medium",
        True,
        "Audio profile; only transport metadata is real-write enabled.",
    ),
    "mic_basic": UpdateProfileSpec("mic_basic", ("Mic",), (*COMMON_PROPERTIES, *MIC_CATALOG_PROPERTIES), "medium", True, "Mic profile with safe channel metadata writes."),
    "video_basic": UpdateProfileSpec("video_basic", ("Video",), (*COMMON_PROPERTIES, *VIDEO_CATALOG_PROPERTIES), "medium", True, "Video profile with one-argument geometry writes."),
    "camera_basic": UpdateProfileSpec("camera_basic", ("Camera",), (*COMMON_PROPERTIES, *MIC_CATALOG_PROPERTIES, *VIDEO_CATALOG_PROPERTIES), "medium", True, "Camera profile with safe channel and geometry writes."),
    TEXT_BASIC_UPDATE_PROFILE: UpdateProfileSpec(
        TEXT_BASIC_UPDATE_PROFILE,
        ("Text",),
        (*COMMON_PROPERTIES, *TEXT_SAFE_PROPERTIES, *TEXT_CATALOG_PROPERTIES),
        "medium",
        True,
        "Text profile; only simple text formatting is real-write enabled.",
    ),
    "light_basic": UpdateProfileSpec("light_basic", ("Light",), (*COMMON_PROPERTIES, *LIGHT_CATALOG_PROPERTIES), "high", True, "Light profile; light commands remain dry-run only."),
    "fade_basic": UpdateProfileSpec("fade_basic", ("Fade",), (*COMMON_PROPERTIES, *FADE_CATALOG_PROPERTIES), "high", True, "Fade profile; fade targets remain dry-run only."),
    "network_basic": UpdateProfileSpec("network_basic", ("Network",), (*COMMON_PROPERTIES, *NETWORK_CATALOG_PROPERTIES), "high", True, "Network profile; network messages remain dry-run only."),
    "midi_basic": UpdateProfileSpec("midi_basic", ("MIDI",), (*COMMON_PROPERTIES, *MIDI_CATALOG_PROPERTIES), "high", True, "MIDI profile; MIDI messages remain dry-run only."),
    "midi_file_basic": UpdateProfileSpec("midi_file_basic", ("MIDI File",), (*COMMON_PROPERTIES, *MIDI_FILE_CATALOG_PROPERTIES), "medium", True, "MIDI File profile with playback metadata writes."),
    "timecode_basic": UpdateProfileSpec("timecode_basic", ("Timecode",), (*COMMON_PROPERTIES, *TIMECODE_CATALOG_PROPERTIES), "medium", True, "Timecode profile with basic metadata writes."),
    "target_basic": UpdateProfileSpec("target_basic", ("Start", "Stop", "Pause", "Load", "Goto", "Target", "Arm", "Disarm"), (*COMMON_PROPERTIES, *TARGET_CATALOG_PROPERTIES), "high", True, "Target cue profile; target refs remain dry-run only."),
    "reset_basic": UpdateProfileSpec("reset_basic", ("Reset",), (*COMMON_PROPERTIES, *RESET_CATALOG_PROPERTIES), "high", True, "Reset profile; reset targets remain dry-run only."),
    "devamp_basic": UpdateProfileSpec("devamp_basic", ("Devamp",), (*COMMON_PROPERTIES, *DEVAMP_CATALOG_PROPERTIES), "high", True, "Devamp profile; devamp targets remain dry-run only."),
    "script_basic": UpdateProfileSpec("script_basic", ("Script",), (*COMMON_PROPERTIES, *SCRIPT_CATALOG_PROPERTIES), "high", True, "Script profile; script source remains dry-run only."),
}

UPDATE_PROFILE_NAMES = tuple(UPDATE_PROFILES)
WRITE_GATE_REQUIREMENTS = (
    "QLAB_ENABLE_WRITE",
    "QLAB_PASSCODE",
    "edit_scope_via_connect",
    "edit_mode_via_showMode",
)
RISK_TIER_ORDER = {"safe": 0, "medium": 1, "high": 2}


def validate_update_profile(profile: str | None) -> str:
    value = (profile or COMMON_UPDATE_PROFILE).strip().casefold()
    if value not in UPDATE_PROFILES:
        allowed = ", ".join(UPDATE_PROFILE_NAMES)
        raise UnsafeWriteOperationError(f"update profile is not allowed: {profile!r}; use one of: {allowed}")
    return value


def profile_catalog() -> dict[str, Any]:
    return {
        name: {
            "cue_types": list(spec.cue_types),
            "risk_tier": spec.risk_tier,
            "real_write_enabled": spec.real_write_enabled,
            "description": spec.description,
            "properties": {
                prop.name: {
                    "path": prop.path or prop.name,
                    "args": [{"name": arg_name, "validator": validator} for arg_name, validator in prop.args],
                    "read_key": prop.read_key,
                    "modes": list(prop.modes),
                    "risk_tier": prop.risk_tier,
                    "real_write_enabled": prop.real_write_enabled,
                    "planned_only_reason": prop.planned_only_reason,
                }
                for prop in spec.properties
            },
        }
        for name, spec in UPDATE_PROFILES.items()
    }


def editable_update_capabilities(cue_type: str | None) -> dict[str, Any]:
    normalized_type = cue_type.casefold() if isinstance(cue_type, str) else None
    compatible_profiles = [COMMON_UPDATE_PROFILE]
    for name, spec in UPDATE_PROFILES.items():
        if name == COMMON_UPDATE_PROFILE or not spec.cue_types or normalized_type is None:
            continue
        if normalized_type in {candidate.casefold() for candidate in spec.cue_types}:
            compatible_profiles.append(name)

    recommended_profile = compatible_profiles[1] if len(compatible_profiles) > 1 else COMMON_UPDATE_PROFILE
    catalog = profile_catalog()
    real_write_details: dict[str, dict[str, Any]] = {}
    dry_run_only_details: dict[str, dict[str, Any]] = {}
    operations: dict[str, dict[str, Any]] = {}
    validators: dict[str, dict[str, str]] = {}
    planned_only_reason: dict[str, str] = {}
    max_risk = "safe"

    for profile_name in compatible_profiles:
        profile = catalog[profile_name]
        if RISK_TIER_ORDER[profile["risk_tier"]] > RISK_TIER_ORDER[max_risk]:
            max_risk = profile["risk_tier"]
        for property_name, prop in profile["properties"].items():
            prop_summary = {
                "profiles": [profile_name],
                "path": prop["path"],
                "args": prop["args"],
                "modes": prop["modes"],
                "risk_tier": prop["risk_tier"],
                "real_write_enabled": prop["real_write_enabled"],
                "planned_only_reason": prop["planned_only_reason"],
            }
            target = real_write_details if prop["real_write_enabled"] else dry_run_only_details
            if property_name in target:
                target[property_name]["profiles"].append(profile_name)
            else:
                target[property_name] = prop_summary
            operations[property_name] = {
                "property": property_name,
                "path": prop["path"],
                "args": prop["args"],
                "modes": prop["modes"],
                "risk_tier": prop["risk_tier"],
                "real_write_enabled": prop["real_write_enabled"],
                "planned_only_reason": prop["planned_only_reason"],
            }
            validators[property_name] = {arg["name"]: arg["validator"] for arg in prop["args"]}
            if prop["planned_only_reason"]:
                planned_only_reason[property_name] = prop["planned_only_reason"]

    return {
        "compatible_profiles": compatible_profiles,
        "recommended_profile": recommended_profile,
        "real_write_properties": sorted(real_write_details),
        "dry_run_only_properties": sorted(dry_run_only_details),
        "property_details": {
            "real_write": real_write_details,
            "dry_run_only": dry_run_only_details,
        },
        "operations": operations,
        "risk_tier": max_risk,
        "validators": validators,
        "arg_schema": {
            "properties": {
                "type": "object",
                "description": "Use for one-argument setters only, keyed by property name.",
                "allowed_properties": sorted(real_write_details | dry_run_only_details),
            },
            "operations": {
                "type": "array",
                "item_shape": {"property": "string", "args": "object", "mode": "saved|live"},
                "allowed_operations": sorted(operations),
            },
        },
        "planned_only_reason": planned_only_reason,
        "requires_write_gates": list(WRITE_GATE_REQUIREMENTS),
    }


def validate_update_profile_for_cue(profile: str, cue_values: dict[str, Any] | None) -> None:
    spec = UPDATE_PROFILES[validate_update_profile(profile)]
    if not spec.cue_types:
        return
    cue_type = cue_values.get("type") if isinstance(cue_values, dict) else None
    normalized_type = cue_type.casefold() if isinstance(cue_type, str) else None
    allowed = {cue_type.casefold() for cue_type in spec.cue_types}
    if normalized_type not in allowed:
        if len(spec.cue_types) == 1:
            article = "an" if spec.cue_types[0][0].casefold() in {"a", "e", "i", "o", "u"} else "a"
            raise UnsafeWriteOperationError(f"{spec.name} update profile requires {article} {spec.cue_types[0]} cue")
        allowed_text = ", ".join(spec.cue_types)
        raise UnsafeWriteOperationError(f"{spec.name} update profile requires cue type: {allowed_text}")


def normalize_update_request(
    profile: str,
    properties: dict[str, Any] | None,
    operations: list[dict[str, Any]] | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    update_profile = validate_update_profile(profile)
    normalized_properties: dict[str, Any] = {}
    normalized_operations: list[dict[str, Any]] = []

    if properties is not None:
        if not isinstance(properties, dict):
            raise UnsafeWriteOperationError("properties must be an object")
        for raw_key, raw_value in properties.items():
            if not isinstance(raw_key, str):
                raise UnsafeWriteOperationError("property names must be strings")
            operation = _normalize_one_operation(update_profile, raw_key.strip(), raw_value, source="properties")
            normalized_operations.append(operation)
            if operation["read_key"] and len(operation["args"]) == 1:
                normalized_properties[operation["read_key"]] = operation["args"][0]

    if operations is not None:
        if not isinstance(operations, list):
            raise UnsafeWriteOperationError("operations must be a list")
        for raw_operation in operations:
            operation = _normalize_operation_dict(update_profile, raw_operation)
            normalized_operations.append(operation)
            if operation["read_key"] and len(operation["args"]) == 1:
                normalized_properties[operation["read_key"]] = operation["args"][0]

    if not normalized_operations:
        raise UnsafeWriteOperationError("properties or operations must include at least one allowlisted cue update")
    _validate_cross_property_values(normalized_properties)
    return normalized_properties, normalized_operations


def ensure_real_write_allowed(profile: str, operations: list[dict[str, Any]]) -> None:
    spec = UPDATE_PROFILES[validate_update_profile(profile)]
    if not spec.real_write_enabled:
        raise UnsafeWriteOperationError(f"{profile} is cataloged for dry-run only; real write is not enabled yet.")
    blocked = [operation for operation in operations if not operation["real_write_enabled"]]
    if blocked:
        names = ", ".join(operation["property"] for operation in blocked)
        raise UnsafeWriteOperationError(f"These update operations are dry-run only for profile {profile}: {names}")


def read_keys_for_operations(operations: list[dict[str, Any]]) -> list[str]:
    keys = ["uniqueID", "type"]
    keys.extend(operation["read_key"] for operation in operations if operation.get("read_key"))
    return list(dict.fromkeys(keys))


def planned_write_capabilities(dry_run_default: bool) -> dict[str, Any]:
    catalog = profile_catalog()
    return {
        "create_cue": {
            "planned": True,
            "cue_types": ["memo", "group", "wait", "audio"],
            "properties": [prop.name for prop in COMMON_PROPERTIES],
            "dry_run_default": dry_run_default,
            "placement": {
                "after_cue_id": "dry_run_only_in_this_preface",
                "parent_id": "planned_later",
                "index": "planned_later",
            },
        },
        "edit_existing_cue": {
            "planned": True,
            "profiles": {
                name: {
                    "cue_types": profile["cue_types"],
                    "risk_tier": profile["risk_tier"],
                    "real_write_enabled": profile["real_write_enabled"],
                    "properties": list(profile["properties"]),
                }
                for name, profile in catalog.items()
            },
            "properties": [prop.name for prop in COMMON_PROPERTIES],
            "supports_operations": True,
            "dry_run_default": dry_run_default,
        },
        "playback_control": {"enabled": False},
        "raw_osc": {"enabled": False},
    }


def _normalize_operation_dict(profile: str, raw_operation: Any) -> dict[str, Any]:
    if not isinstance(raw_operation, dict):
        raise UnsafeWriteOperationError("each operation must be an object")
    raw_property = raw_operation.get("property")
    if not isinstance(raw_property, str) or not raw_property.strip():
        raise UnsafeWriteOperationError("operation.property must be a non-empty string")
    return _normalize_one_operation(
        profile,
        raw_property.strip(),
        raw_operation.get("args", {}),
        mode=raw_operation.get("mode", "saved"),
        source="operations",
    )


def _normalize_one_operation(
    profile: str,
    property_name: str,
    raw_args: Any,
    *,
    mode: Any = "saved",
    source: str,
) -> dict[str, Any]:
    spec = _property_spec(profile, property_name)
    normalized_mode = _validate_mode(spec, mode)
    normalized_args = _normalize_args(spec, raw_args, source=source)
    path = _render_path(spec, normalized_args)
    if normalized_mode == "live":
        path = f"{path}/live"
    osc_args = [normalized_args[arg_name] for arg_name in spec.osc_args]
    return {
        "operation": "set_property",
        "property": spec.name,
        "path": path,
        "mode": normalized_mode,
        "args": osc_args,
        "arg_values": normalized_args,
        "read_key": spec.read_key,
        "risk_tier": spec.risk_tier,
        "real_write_enabled": spec.real_write_enabled,
        "planned_only_reason": spec.planned_only_reason,
    }


def _property_spec(profile: str, property_name: str) -> CuePropertySpec:
    profile_name = validate_update_profile(profile)
    properties = {prop.name: prop for prop in UPDATE_PROFILES[profile_name].properties}
    if property_name not in properties:
        raise UnsafeWriteOperationError(f"Cue property is not allowlisted for update profile {profile_name}: {property_name}")
    return properties[property_name]


def _validate_mode(spec: CuePropertySpec, mode: Any) -> str:
    if mode is None:
        mode = "saved"
    if not isinstance(mode, str):
        raise UnsafeWriteOperationError("operation.mode must be saved or live")
    normalized = mode.strip().casefold()
    if normalized not in spec.modes:
        allowed = ", ".join(spec.modes)
        raise UnsafeWriteOperationError(f"{spec.name} does not support mode {mode!r}; use one of: {allowed}")
    return normalized


def _normalize_args(spec: CuePropertySpec, raw_args: Any, *, source: str) -> dict[str, Any]:
    if source == "properties":
        if len(spec.args) != 1 or spec.args[0][0] != "value":
            raise UnsafeWriteOperationError(f"{spec.name} requires operations[] because it has structured arguments")
        return {"value": _validate_named_value(spec.name, spec.args[0][1], raw_args)}
    if len(spec.args) == 1 and spec.args[0][0] == "value" and not isinstance(raw_args, dict):
        return {"value": _validate_named_value(spec.name, spec.args[0][1], raw_args)}
    if not isinstance(raw_args, dict):
        raise UnsafeWriteOperationError(f"{spec.name} args must be an object")
    allowed = {arg_name for arg_name, _ in spec.args}
    unknown = sorted(set(raw_args) - allowed)
    if unknown:
        raise UnsafeWriteOperationError(f"{spec.name} args include unknown keys: {', '.join(unknown)}")
    normalized: dict[str, Any] = {}
    for arg_name, validator in spec.args:
        if arg_name not in raw_args:
            raise UnsafeWriteOperationError(f"{spec.name} args missing required key: {arg_name}")
        normalized[arg_name] = _validate_named_value(f"{spec.name}.{arg_name}", validator, raw_args[arg_name])
    return normalized


def _render_path(spec: CuePropertySpec, args: dict[str, Any]) -> str:
    path = spec.path or spec.name
    for arg_name in _path_arg_names(path):
        path = path.replace(f"{{{arg_name}}}", str(args[arg_name]))
    return path


def _validate_cross_property_values(values: dict[str, Any]) -> None:
    if "startTime" in values and "endTime" in values and values["endTime"] <= values["startTime"]:
        raise UnsafeWriteOperationError("endTime must be greater than startTime when both are provided")
    if values.get("infiniteLoop") is True and "playCount" in values:
        raise UnsafeWriteOperationError("infiniteLoop=true cannot be combined with playCount in one update")


def _validate_value(validator: str, value: Any) -> Any:
    if validator == "any":
        return value
    if validator == "string":
        if not isinstance(value, str):
            raise UnsafeWriteOperationError("value must be a string")
        return value
    if validator == "non_empty_string":
        if not isinstance(value, str) or not value.strip():
            raise UnsafeWriteOperationError("value must be a non-empty string")
        return value
    if validator == "boolean":
        if not isinstance(value, bool):
            raise UnsafeWriteOperationError("value must be a boolean")
        return value
    if validator == "number":
        return _number(value, "value must be a number")
    if validator == "non_negative_number":
        number = _number(value, "value must be a non-negative number")
        if number < 0:
            raise UnsafeWriteOperationError("value must be a non-negative number")
        return number
    if validator == "positive_number":
        number = _number(value, "value must be a positive number")
        if number <= 0:
            raise UnsafeWriteOperationError("value must be a positive number")
        return number
    if validator == "int":
        return _int(value, "value must be an integer")
    if validator == "non_negative_int":
        number = _int(value, "value must be a non-negative integer")
        if number < 0:
            raise UnsafeWriteOperationError("value must be a non-negative integer")
        return number
    if validator == "positive_int":
        number = _int(value, "value must be a positive integer")
        if number <= 0:
            raise UnsafeWriteOperationError("value must be a positive integer")
        return number
    if validator == "int_or_minus_one":
        number = _int(value, "value must be a positive integer or -1")
        if number != -1 and number <= 0:
            raise UnsafeWriteOperationError("value must be a positive integer or -1")
        return number
    if validator == "rate":
        number = _number(value, "rate must be a number from 0.03 to 33.0")
        if number < 0.03 or number > 33.0:
            raise UnsafeWriteOperationError("rate must be a number from 0.03 to 33.0")
        return number
    if validator == "opacity":
        number = _number(value, "opacity must be a number from 0 to 100")
        if number < 0 or number > 100:
            raise UnsafeWriteOperationError("opacity must be a number from 0 to 100")
        return number
    if validator == "continue_mode":
        return _continue_mode(value)
    if validator == "text_alignment":
        return _enum_string(value, {"left", "center", "right", "justify"}, "value must be left, center, right, or justify")
    if validator == "text_line_style":
        return _enum_string(value, {"none", "single", "double"}, "value must be none, single, or double")
    if validator == "byte":
        return _int_range(value, 0, 127, "value must be an integer from 0 to 127")
    if validator == "byte_combo":
        return _int_range(value, 0, 16383, "value must be an integer from 0 to 16383")
    if validator == "midi_channel":
        return _int_range(value, 1, 16, "value must be an integer from 1 to 16")
    if validator == "color_component":
        return _int_range(value, 0, 255, "color component must be an integer from 0 to 255")
    if validator == "alpha":
        number = _number(value, "alpha must be a number from 0 to 1")
        if number < 0 or number > 1:
            raise UnsafeWriteOperationError("alpha must be a number from 0 to 1")
        return number
    if validator == "dict_or_json_string":
        if isinstance(value, (dict, list)) or isinstance(value, str):
            return value
        raise UnsafeWriteOperationError("value must be a dict, list, or JSON string")
    if validator == "list":
        if not isinstance(value, list):
            raise UnsafeWriteOperationError("value must be a list")
        return value
    if validator == "patch_ref":
        if isinstance(value, str):
            return value
        if isinstance(value, int) and value >= 0:
            return value
        raise UnsafeWriteOperationError("patch reference must be a string or non-negative integer")
    raise UnsafeWriteOperationError(f"unknown validator: {validator}")


def _validate_named_value(name: str, validator: str, value: Any) -> Any:
    try:
        return _validate_value(validator, value)
    except UnsafeWriteOperationError as exc:
        message = str(exc)
        if message.startswith("value must"):
            message = message.replace("value must", f"{name} must", 1)
        elif message.startswith("rate must"):
            message = message.replace("rate must", f"{name} must", 1)
        elif message.startswith("opacity must"):
            message = message.replace("opacity must", f"{name} must", 1)
        elif message.startswith("color component must"):
            message = message.replace("color component must", f"{name} must", 1)
        elif message.startswith("alpha must"):
            message = message.replace("alpha must", f"{name} must", 1)
        raise UnsafeWriteOperationError(message) from exc


def _number(value: Any, message: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeWriteOperationError(message)
    return value


def _int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsafeWriteOperationError(message)
    return value


def _int_range(value: Any, minimum: int, maximum: int, message: str) -> int:
    number = _int(value, message)
    if number < minimum or number > maximum:
        raise UnsafeWriteOperationError(message)
    return number


def _enum_string(value: Any, allowed: set[str], message: str) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError(message)
    normalized = value.strip().casefold()
    if normalized not in allowed:
        raise UnsafeWriteOperationError(message)
    return normalized


_CONTINUE_MODE_VALUES = {
    "0": 0,
    "do_not_continue": 0,
    "do-not-continue": 0,
    "manual": 0,
    "none": 0,
    "1": 1,
    "auto_continue": 1,
    "auto-continue": 1,
    "autocontinue": 1,
    "2": 2,
    "auto_follow": 2,
    "auto-follow": 2,
    "autofollow": 2,
}


def _continue_mode(value: Any) -> int:
    if isinstance(value, bool):
        raise UnsafeWriteOperationError("continueMode must be 0, 1, 2, or a known label")
    if isinstance(value, int) and value in {0, 1, 2}:
        return value
    if isinstance(value, float) and value.is_integer() and int(value) in {0, 1, 2}:
        return int(value)
    if isinstance(value, str):
        normalized = value.strip().casefold().replace(" ", "_")
        if normalized in _CONTINUE_MODE_VALUES:
            return _CONTINUE_MODE_VALUES[normalized]
    raise UnsafeWriteOperationError("continueMode must be 0, 1, 2, do_not_continue, auto_continue, or auto_follow")
