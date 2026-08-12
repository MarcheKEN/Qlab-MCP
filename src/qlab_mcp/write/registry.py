"""Data-driven edit registry for QLab cue update profiles."""

from __future__ import annotations

import hashlib
import json
import math
import struct
from dataclasses import dataclass, replace
from string import Formatter
from typing import Any

from ..errors import UnsafeWriteOperationError


COMMON_UPDATE_PROFILE = "common"
AUDIO_BASIC_UPDATE_PROFILE = "audio_basic"
TEXT_BASIC_UPDATE_PROFILE = "text_basic"
QLAB_COLOR_NAMES = {
    "none",
    "berry",
    "red",
    "crimson",
    "orange",
    "peach",
    "yellow",
    "green",
    "forest",
    "blue",
    "sky blue",
    "purple",
    "plum",
    "lavender",
    "indigo",
    "midnight",
    "olive",
    "cyan",
    "magenta",
    "pink",
    "hot pink",
    "white",
    "black",
    "gray",
    "grey",
}
AUDIO_OBJECT_COLOR_NAMES = QLAB_COLOR_NAMES

VALID_BLEND_MODES = (
    "Normal",
    "Darken",
    "Multiply",
    "Color Burn",
    "Linear Burn",
    "Lighten",
    "Screen",
    "Color Dodge",
    "Linear Dodge",
    "Overlay",
    "Soft Light",
    "Hard Light",
    "Pin Light",
    "Difference",
    "Exclusion",
    "Subtract",
    "Divide",
    "Hue",
    "Saturation",
    "Color",
    "Luminosity",
    "Addition Compositing",
    "Maximum Compositing",
    "Source Atop Compositing",
)
QLAB_BLEND_MODES = {name: name for name in VALID_BLEND_MODES}


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
    doc_section: str | None = None
    osc_paths: tuple[str, ...] = ()
    capability_gate: str | None = None
    readback: str = "value"
    contextual_requirements: tuple[str, ...] = ()
    write_family: str | None = None


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
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    capability_gate: str | None = None,
    readback: str = "value",
    contextual_requirements: tuple[str, ...] = (),
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
        doc_section=doc_section,
        osc_paths=osc_paths,
        capability_gate=capability_gate,
        readback=readback,
        contextual_requirements=contextual_requirements,
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
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    capability_gate: str | None = None,
    readback: str = "value",
    contextual_requirements: tuple[str, ...] = (),
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
        doc_section=doc_section,
        osc_paths=osc_paths,
        capability_gate=capability_gate,
        readback=readback,
        contextual_requirements=contextual_requirements,
    )


def _planned_prop(
    name: str,
    validator: str = "any",
    *,
    path: str | None = None,
    read_key: str | None = None,
    reason: str,
    modes: tuple[str, ...] = ("saved",),
    capability_gate: str | None = None,
    doc_section: str | None = None,
    osc_paths: tuple[str, ...] = (),
    contextual_requirements: tuple[str, ...] = (),
) -> CuePropertySpec:
    return _prop(
        name,
        validator,
        path=path,
        read_key=read_key,
        modes=modes,
        risk_tier="high",
        real_write_enabled=False,
        planned_only_reason=reason,
        capability_gate=capability_gate,
        doc_section=doc_section,
        osc_paths=osc_paths,
        contextual_requirements=contextual_requirements,
    )


def _path_arg_names(path: str) -> tuple[str, ...]:
    return tuple(field_name for _, field_name, _, _ in Formatter().parse(path) if field_name)


def _planned_patch_refs(prefix: str, *, validator: str) -> tuple[CuePropertySpec, ...]:
    return (
        _planned_prop(f"{prefix}Name", "string", reason="patch_or_map_refs_need_dedicated_resolution", capability_gate="patch_routing"),
        _planned_prop(f"{prefix}Number", "non_negative_int", reason="patch_or_map_refs_need_dedicated_resolution", capability_gate="patch_routing"),
        _planned_prop(f"{prefix}ID", "string", reason="patch_or_map_refs_need_dedicated_resolution", capability_gate="patch_routing"),
    )


def _rgba_args() -> tuple[tuple[str, str], ...]:
    return (("red", "unit_interval"), ("green", "unit_interval"), ("blue", "unit_interval"), ("alpha", "unit_interval"))


def _group_properties() -> tuple[CuePropertySpec, ...]:
    return (
        _planned_prop(
            "mode",
            "group_mode",
            reason="group_mode_requires_confirm_token",
            capability_gate="group_mode",
        ),
        _planned_prop("playhead", "non_empty_string", reason="playhead_changes_are_control_behavior"),
        _planned_prop("playheadID", "non_empty_string", reason="playhead_changes_are_control_behavior"),
        _planned_prop("playbackPosition", "non_empty_string", reason="playhead_changes_are_control_behavior"),
        _planned_prop("playbackPositionID", "non_empty_string", reason="playhead_changes_are_control_behavior"),
        _op("playhead/next", (), path="playhead/next", risk_tier="high", planned_only_reason="playhead_changes_are_control_behavior"),
        _op("playhead/previous", (), path="playhead/previous", risk_tier="high", planned_only_reason="playhead_changes_are_control_behavior"),
        _op("playhead/none", (), path="playhead/none", risk_tier="high", planned_only_reason="playhead_changes_are_control_behavior"),
        _op("playhead/nextSequence", (), path="playhead/nextSequence", risk_tier="high", planned_only_reason="playhead_changes_are_control_behavior"),
        _op("playhead/previousSequence", (), path="playhead/previousSequence", risk_tier="high", planned_only_reason="playhead_changes_are_control_behavior"),
        _op(
            "playbackPosition/next",
            (),
            path="playbackPosition/next",
            risk_tier="high",
            planned_only_reason="playhead_changes_are_control_behavior",
        ),
        _op(
            "playbackPosition/previous",
            (),
            path="playbackPosition/previous",
            risk_tier="high",
            planned_only_reason="playhead_changes_are_control_behavior",
        ),
        _op(
            "playbackPosition/none",
            (),
            path="playbackPosition/none",
            risk_tier="high",
            planned_only_reason="playhead_changes_are_control_behavior",
        ),
        _op(
            "playbackPosition/nextSequence",
            (),
            path="playbackPosition/nextSequence",
            risk_tier="high",
            planned_only_reason="playhead_changes_are_control_behavior",
        ),
        _op(
            "playbackPosition/previousSequence",
            (),
            path="playbackPosition/previousSequence",
            risk_tier="high",
            planned_only_reason="playhead_changes_are_control_behavior",
        ),
        _op(
            "moveCartCue",
            (("child", "non_empty_string"), ("row", "non_negative_int"), ("column", "non_negative_int")),
            path="moveCartCue/{child}",
            risk_tier="high",
            planned_only_reason="cart_child_order_changes_need_dedicated_validation",
        ),
        _planned_prop("playlist/currentCue", "non_empty_string", reason="playlist_navigation_needs_dedicated_validation"),
        _planned_prop("playlist/currentCueID", "non_empty_string", reason="playlist_navigation_needs_dedicated_validation"),
        _op(
            "playlist/next",
            (),
            path="playlist/next",
            risk_tier="high",
            planned_only_reason="playlist_navigation_starts_playback",
        ),
        _op(
            "playlist/previous",
            (),
            path="playlist/previous",
            risk_tier="high",
            planned_only_reason="playlist_navigation_starts_playback",
        ),
        _op(
            "shuffle",
            (),
            path="shuffle",
            risk_tier="high",
            planned_only_reason="group_shuffle_action_changes_child_order",
        ),
        _planned_prop(
            "playlist/doLoop",
            "boolean",
            reason="group_playlist_requires_confirm_token",
            capability_gate="group_playlist",
            contextual_requirements=("group_mode_is_playlist",),
        ),
        _planned_prop(
            "playlist/doShuffle",
            "boolean",
            reason="group_playlist_requires_confirm_token",
            capability_gate="group_playlist",
            contextual_requirements=("group_mode_is_playlist",),
        ),
        _planned_prop(
            "playlist/doCrossfade",
            "boolean",
            reason="group_playlist_requires_confirm_token",
            capability_gate="group_playlist",
            contextual_requirements=("group_mode_is_playlist",),
        ),
        _planned_prop(
            "playlist/crossfade/duration",
            "non_negative_number",
            reason="group_playlist_requires_confirm_token",
            capability_gate="group_playlist",
            contextual_requirements=("group_mode_is_playlist",),
        ),
        _planned_prop("playlistLoop", "boolean", path="playlistLoop", reason="deprecated_use_playlist_doLoop"),
        _planned_prop("playlistShuffle", "boolean", path="playlistShuffle", reason="deprecated_use_playlist_doShuffle"),
        _planned_prop("playlistCrossfade", "boolean", path="playlistCrossfade", reason="deprecated_use_playlist_doCrossfade"),
        _planned_prop(
            "playlistCrossfadeDuration",
            "non_negative_number",
            path="playlistCrossfadeDuration",
            reason="deprecated_use_playlist_crossfade_duration",
        ),
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
    _prop("colorName", "color_name", real_write_enabled=True),
    _prop("preWait", "non_negative_number", real_write_enabled=True),
    _prop("postWait", "non_negative_number", real_write_enabled=True),
    _prop(
        "duration",
        "non_negative_number",
        real_write_enabled=True,
        contextual_requirements=("allows_editing_duration",),
    ),
    _prop(
        "tempDuration",
        "non_negative_number",
        real_write_enabled=True,
        contextual_requirements=("allows_editing_duration",),
    ),
    _prop("continueMode", "continue_mode", real_write_enabled=True),
    _prop("skipIfDisarmed", "boolean", real_write_enabled=True),
    _prop("autoLoad", "boolean", real_write_enabled=True),
    _prop("secondColorName", "color_name", modes=("saved", "live"), real_write_enabled=True),
    _prop("useSecondColor", "boolean", real_write_enabled=True),
)

FADE_COMMON_PROPERTIES = tuple(
    replace(
        prop,
        risk_tier="high",
        real_write_enabled=False,
        planned_only_reason="fade_basic_requires_confirm_token",
    )
    for prop in COMMON_PROPERTIES
)

COMMON_CATALOG_PROPERTIES = (
    _planned_prop("colorCondition", "color_condition", reason="deprecated_unsupported_in_current_qlab"),
    _planned_prop("duckLevel", "decibel", reason="ducking_changes_cue_behavior"),
    _planned_prop("duckOthers", "boolean", reason="ducking_changes_cue_behavior"),
    _planned_prop("duckTime", "non_negative_number", reason="ducking_changes_cue_behavior"),
    _planned_prop("fadeAndStopOthers", "number", reason="fade_and_stop_changes_other_cues"),
    _planned_prop("fadeAndStopOthersTime", "non_negative_number", reason="fade_and_stop_changes_other_cues"),
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    _planned_prop("cueTargetNumber", "cue_target_number", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetID", "cue_target_id", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetNumber", "cue_target_number", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetID", "cue_target_id", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("patchTargetID", "target_id", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("targetMode", "target_mode", reason="target_behavior_needs_validation"),
    _planned_prop("secondTriggerAction", "second_trigger_action", reason="second_trigger_changes_show_control_behavior"),
    _planned_prop("secondTriggerOnRelease", "boolean", reason="second_trigger_changes_show_control_behavior"),
    _op("timecodeTrigger", (("hours", "timecode_part"), ("minutes", "timecode_part"), ("seconds", "timecode_part"), ("frames", "timecode_part"), ("bits", "timecode_part")), planned_only_reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/hours", "timecode_part", reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/minutes", "timecode_part", reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/seconds", "timecode_part", reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/frames", "timecode_part", reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/bits", "timecode_part", reason="timecode_trigger_changes_show_control_behavior"),
    _planned_prop("timecodeTrigger/text", "string", reason="timecode_trigger_changes_show_control_behavior"),
)

_AUDIO_TIME_ROUTE_VALIDATORS = (
    ("rate", "rate"),
    ("startTime", "non_negative_number"),
    ("endTime", "non_negative_number"),
    ("playCount", "positive_int"),
    ("infiniteLoop", "boolean"),
    ("preservePitch", "boolean"),
)

AUDIO_SAFE_PROPERTIES = tuple(
    _prop(name, validator, real_write_enabled=True)
    for name, validator in _AUDIO_TIME_ROUTE_VALIDATORS
)

VIDEO_AUDIO_TIME_PROPERTIES = tuple(
    _planned_prop(
        name,
        validator,
        reason="video_audio_time_requires_confirm_token",
        capability_gate="audio_output",
    )
    for name, validator in _AUDIO_TIME_ROUTE_VALIDATORS
)

VIDEO_AUDIO_LEVEL_PROPERTIES = (
    _op(
        "sliderLevel",
        (("channel", "audio_output_ref"), ("decibel", "decibel")),
        path="sliderLevel/{channel}",
        modes=("saved", "live"),
        read_key="sliderLevels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_levels_require_confirm_token",
    ),
)

VIDEO_AUDIO_MATRIX_PROPERTIES = (
    _op(
        "level",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("decibel", "decibel")),
        path="level/{inChannel}/{outChannel}",
        modes=("saved", "live"),
        read_key="levels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_matrix_requires_confirm_token",
    ),
)

VIDEO_AUDIO_LEVEL_META_PROPERTIES = (
    _op(
        "inputChannelName",
        (("number", "positive_int"), ("name", "string")),
        path="inputChannelName/{number}",
        risk_tier="medium",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_meta_requires_confirm_token",
    ),
    _op(
        "gang",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("gang", "string")),
        path="gang/{inChannel}/{outChannel}",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_meta_requires_confirm_token",
    ),
)

VIDEO_AUDIO_MUTE_SOLO_PROPERTIES = (
    _op(
        "mute/channel",
        (("output", "audio_output_ref"), ("value", "boolean")),
        path="mute/channel/{output}",
        read_key="muteChannels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_mute_solo_requires_confirm_token",
    ),
    _op(
        "solo/channel",
        (("output", "audio_output_ref"), ("value", "boolean")),
        path="solo/{output}",
        read_key="soloChannels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_mute_solo_requires_confirm_token",
    ),
)

VIDEO_AUDIO_LEVEL_BULK_PROPERTIES = (
    _op(
        "mute/channel/clear",
        (),
        path="mute/channel/clear",
        read_key="muteChannels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_bulk_requires_confirm_token",
    ),
    _op(
        "solo/channel/clear",
        (),
        path="solo/channel/clear",
        read_key="soloChannels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_bulk_requires_confirm_token",
    ),
    _op(
        "setDefaultLevels",
        (),
        path="setDefaultLevels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_bulk_requires_full_runtime_validation",
    ),
    _op(
        "setSilentLevels",
        (),
        path="setSilentLevels",
        risk_tier="high",
        capability_gate="audio_output",
        planned_only_reason="video_audio_level_bulk_requires_full_runtime_validation",
    ),
)

VIDEO_SLICE_MARKER_PROPERTIES = (
    _planned_prop(
        "lastSlicePlayCount",
        "int_or_minus_one",
        reason="video_slice_marker_requires_confirm_token",
        capability_gate="slice_editing",
    ),
    _planned_prop("lastSliceInfiniteLoop", "boolean", reason="last_slice_semantics_need_runtime_validation"),
    _planned_prop("sliceMarkers", "list", reason="slice_marker_collection_not_directly_settable_use_sliceMarker_operations"),
    _op(
        "sliceMarker/time",
        (("index", "non_negative_int"), ("time", "non_negative_number")),
        path="sliceMarker/{index}/time",
        read_key="sliceMarkers",
        risk_tier="high",
        planned_only_reason="video_slice_marker_requires_confirm_token",
    ),
    _op(
        "sliceMarker/playCount",
        (("index", "non_negative_int"), ("playCount", "int_or_minus_one")),
        path="sliceMarker/{index}/playCount",
        read_key="sliceMarkers",
        risk_tier="high",
        planned_only_reason="video_slice_marker_requires_confirm_token",
    ),
    _op(
        "addSliceMarker",
        (("time", "non_negative_number"), ("playCount", "int_or_minus_one")),
        path="addSliceMarker",
        read_key="sliceMarkers",
        risk_tier="high",
        planned_only_reason="video_slice_marker_requires_confirm_token",
    ),
    _op(
        "deleteSliceMarker",
        (("index", "non_negative_int"),),
        path="deleteSliceMarker/{index}",
        read_key="sliceMarkers",
        risk_tier="high",
        planned_only_reason="video_slice_marker_requires_confirm_token",
    ),
    _op(
        "deleteSliceMarkers",
        (),
        path="deleteSliceMarkers",
        read_key="sliceMarkers",
        risk_tier="high",
        planned_only_reason="video_slice_marker_requires_confirm_token",
    ),
)

AUDIO_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    *_planned_patch_refs("audioOutputPatch", validator="patch_ref"),
    *_planned_patch_refs("audioMap", validator="patch_ref"),
    _planned_prop("doFade", "boolean", reason="integrated_fade_changes_playback_behavior"),
    _planned_prop("lockFadeToCue", "boolean", reason="integrated_fade_changes_playback_behavior"),
    _planned_prop("lastSlicePlayCount", "int_or_minus_one", reason="slice_editing_needs_dedicated_validation"),
    _planned_prop("lastSliceInfiniteLoop", "boolean", reason="slice_editing_needs_dedicated_validation"),
    _planned_prop("patch", "non_negative_int", reason="deprecated_use_audioOutputPatchNumber"),
    _planned_prop("sliceMarkers", "list", reason="slice_marker_collection_not_directly_settable_use_sliceMarker_operations"),
    _op(
        "inputChannelName",
        (("number", "positive_int"), ("name", "string")),
        path="inputChannelName/{number}",
        risk_tier="medium",
        planned_only_reason="input_channel_labels_need_dedicated_validation",
    ),
    _op(
        "level",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("decibel", "decibel")),
        path="level/{inChannel}/{outChannel}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "sliderLevel",
        (("channel", "audio_output_ref"), ("decibel", "decibel")),
        path="sliderLevel/{channel}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "gang",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("gang", "string")),
        path="gang/{inChannel}/{outChannel}",
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "doLevel",
        (("row", "audio_level_row"), ("column", "audio_output_ref"), ("value", "boolean")),
        path="doLevel/{row}/{column}",
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "mute",
        (("output", "audio_output_ref"), ("value", "boolean")),
        path="mute/channel/{output}",
        risk_tier="high",
        planned_only_reason="mute_changes_audio_output",
    ),
    _op(
        "solo",
        (("output", "audio_output_ref"), ("value", "boolean")),
        path="solo/{output}",
        risk_tier="high",
        planned_only_reason="solo_changes_audio_output",
    ),
    _op("mute/clear", (), path="mute/clear", risk_tier="high", planned_only_reason="mute_changes_audio_output"),
    _op("mute/channel/clear", (), path="mute/channel/clear", risk_tier="high", planned_only_reason="mute_changes_audio_output"),
    _op("mute/object/clear", (), path="mute/object/clear", risk_tier="high", planned_only_reason="mute_changes_audio_output"),
    _op("solo/clear", (), path="solo/clear", risk_tier="high", planned_only_reason="solo_changes_audio_output"),
    _op("solo/channel/clear", (), path="solo/channel/clear", risk_tier="high", planned_only_reason="solo_changes_audio_output"),
    _op("solo/object/clear", (), path="solo/object/clear", risk_tier="high", planned_only_reason="solo_changes_audio_output"),
    _op("setDefaultLevels", (), path="setDefaultLevels", risk_tier="high", planned_only_reason="audio_levels_can_affect_live_output"),
    _op("setSilentLevels", (), path="setSilentLevels", risk_tier="high", planned_only_reason="audio_levels_can_affect_live_output"),
    _op(
        "sliceMarker",
        (("index", "non_negative_int"), ("time", "non_negative_number"), ("playCount", "int_or_minus_one")),
        path="sliceMarker/{index}",
        risk_tier="medium",
        planned_only_reason="slice_editing_needs_dedicated_validation",
    ),
    _op(
        "sliceMarker/time",
        (("index", "non_negative_int"), ("time", "non_negative_number")),
        path="sliceMarker/{index}/time",
        risk_tier="medium",
        planned_only_reason="slice_editing_needs_dedicated_validation",
    ),
    _op(
        "sliceMarker/playCount",
        (("index", "non_negative_int"), ("playCount", "int_or_minus_one")),
        path="sliceMarker/{index}/playCount",
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
        "deleteSliceMarker",
        (("index", "non_negative_int"),),
        path="deleteSliceMarker/{index}",
        risk_tier="high",
        planned_only_reason="destructive_slice_editing_needs_dedicated_validation",
    ),
    _op(
        "deleteSliceMarkers",
        (),
        path="deleteSliceMarkers",
        risk_tier="high",
        planned_only_reason="destructive_slice_editing_needs_dedicated_validation",
    ),
    _op(
        "object/name",
        (("object", "audio_object_ref"), ("name", "non_empty_string")),
        path="object/{object}/name",
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/name",
        (("objectID", "audio_object_ref"), ("name", "non_empty_string")),
        path="objectID/{objectID}/name",
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/colorName",
        (("object", "audio_object_ref"), ("colorName", "audio_object_color_name")),
        path="object/{object}/colorName",
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/colorName",
        (("objectID", "audio_object_ref"), ("colorName", "audio_object_color_name")),
        path="objectID/{objectID}/colorName",
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/position",
        (("object", "audio_object_ref"), ("x", "number"), ("y", "number")),
        path="object/{object}/position",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/position",
        (("objectID", "audio_object_ref"), ("x", "number"), ("y", "number")),
        path="objectID/{objectID}/position",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/position/x",
        (("object", "audio_object_ref"), ("x", "number")),
        path="object/{object}/position/x",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/position/y",
        (("object", "audio_object_ref"), ("y", "number")),
        path="object/{object}/position/y",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/position/x",
        (("objectID", "audio_object_ref"), ("x", "number")),
        path="objectID/{objectID}/position/x",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/position/y",
        (("objectID", "audio_object_ref"), ("y", "number")),
        path="objectID/{objectID}/position/y",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "object/spread",
        (("object", "audio_object_ref"), ("spread", "number")),
        path="object/{object}/spread",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectID/spread",
        (("objectID", "audio_object_ref"), ("spread", "number")),
        path="objectID/{objectID}/spread",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="spatial_audio_changes_output",
    ),
    _op(
        "objectLevel",
        (("row", "audio_level_row"), ("object", "audio_object_ref"), ("decibel", "decibel")),
        path="objectLevel/{row}/{object}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "objectIDLevel",
        (("row", "audio_level_row"), ("objectID", "audio_object_ref"), ("decibel", "decibel")),
        path="objectIDLevel/{row}/{objectID}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "doObjectLevel",
        (("row", "audio_level_row"), ("object", "audio_object_ref"), ("value", "boolean")),
        path="doObjectLevel/{row}/{object}",
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "doObjectIDLevel",
        (("row", "audio_level_row"), ("objectID", "audio_object_ref"), ("value", "boolean")),
        path="doObjectIDLevel/{row}/{objectID}",
        risk_tier="high",
        planned_only_reason="audio_levels_can_affect_live_output",
    ),
    _op(
        "mute/object",
        (("object", "audio_object_ref"), ("value", "boolean")),
        path="mute/object/{object}",
        risk_tier="high",
        planned_only_reason="mute_changes_audio_output",
    ),
    _op(
        "mute/objectID",
        (("objectID", "audio_object_ref"), ("value", "boolean")),
        path="mute/objectID/{objectID}",
        risk_tier="high",
        planned_only_reason="mute_changes_audio_output",
    ),
    _op(
        "solo/object",
        (("object", "audio_object_ref"), ("value", "boolean")),
        path="solo/object/{object}",
        risk_tier="high",
        planned_only_reason="solo_changes_audio_output",
    ),
    _op(
        "solo/objectID",
        (("objectID", "audio_object_ref"), ("value", "boolean")),
        path="solo/objectID/{objectID}",
        risk_tier="high",
        planned_only_reason="solo_changes_audio_output",
    ),
    _planned_prop("audioOutputPatch/cueOutputChannels", "audio_patch_channel_count", reason="audio_patch_routing_needs_dedicated_validation"),
    _op(
        "audioOutputPatch/level",
        (("inChannel", "audio_level_row"), ("outChannel", "device_output_ref"), ("decibel", "decibel")),
        path="audioOutputPatch/level/{inChannel}/{outChannel}",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_patch_routing_needs_dedicated_validation",
    ),
    _op(
        "audioOutputPatch/mute",
        (("output", "device_output_ref"), ("value", "boolean")),
        path="audioOutputPatch/mute/{output}",
        risk_tier="high",
        planned_only_reason="audio_patch_routing_needs_dedicated_validation",
    ),
    _op(
        "audioOutputPatch/solo",
        (("output", "device_output_ref"), ("value", "boolean")),
        path="audioOutputPatch/solo/{output}",
        risk_tier="high",
        planned_only_reason="audio_patch_routing_needs_dedicated_validation",
    ),
    _op("audioOutputPatch/mute/clear", (), path="audioOutputPatch/mute/clear", risk_tier="high", planned_only_reason="audio_patch_routing_needs_dedicated_validation"),
    _op("audioOutputPatch/solo/clear", (), path="audioOutputPatch/solo/clear", risk_tier="high", planned_only_reason="audio_patch_routing_needs_dedicated_validation"),
    _op("audioOutputPatch/reset", (), path="audioOutputPatch/reset", risk_tier="high", planned_only_reason="audio_patch_routing_needs_dedicated_validation"),
    _op("audioOutputPatch/routing/reset", (), path="audioOutputPatch/routing/reset", risk_tier="high", planned_only_reason="audio_patch_routing_needs_dedicated_validation"),
    _planned_prop("audioOutputPatch/name", "non_empty_string", reason="audio_patch_routing_needs_dedicated_validation"),
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
    _op(
        "audioMap/object/name",
        (("object", "audio_object_ref"), ("name", "non_empty_string")),
        path="audioMap/object/{object}/name",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/name",
        (("objectID", "audio_object_ref"), ("name", "non_empty_string")),
        path="audioMap/objectID/{objectID}/name",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/object/colorName",
        (("object", "audio_object_ref"), ("colorName", "audio_object_color_name")),
        path="audioMap/object/{object}/colorName",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/colorName",
        (("objectID", "audio_object_ref"), ("colorName", "audio_object_color_name")),
        path="audioMap/objectID/{objectID}/colorName",
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/object/position",
        (("object", "audio_object_ref"), ("x", "number"), ("y", "number")),
        path="audioMap/object/{object}/position",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/position",
        (("objectID", "audio_object_ref"), ("x", "number"), ("y", "number")),
        path="audioMap/objectID/{objectID}/position",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/object/position/x",
        (("object", "audio_object_ref"), ("x", "number")),
        path="audioMap/object/{object}/position/x",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/object/position/y",
        (("object", "audio_object_ref"), ("y", "number")),
        path="audioMap/object/{object}/position/y",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/position/x",
        (("objectID", "audio_object_ref"), ("x", "number")),
        path="audioMap/objectID/{objectID}/position/x",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/position/y",
        (("objectID", "audio_object_ref"), ("y", "number")),
        path="audioMap/objectID/{objectID}/position/y",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/object/spread",
        (("object", "audio_object_ref"), ("spread", "non_negative_number")),
        path="audioMap/object/{object}/spread",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
    _op(
        "audioMap/objectID/spread",
        (("objectID", "audio_object_ref"), ("spread", "non_negative_number")),
        path="audioMap/objectID/{objectID}/spread",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="audio_map_editing_needs_dedicated_validation",
    ),
)

MIC_CATALOG_PROPERTIES = (
    *_planned_patch_refs("audioInputPatch", validator="patch_ref"),
    _planned_prop(
        "channelOffset",
        "non_negative_int",
        reason="audio_input_channel_offset_needs_patch_bounds_validation",
        capability_gate="patch_routing",
    ),
    _planned_prop(
        "channels",
        "positive_int",
        reason="audio_input_channel_count_needs_patch_bounds_validation",
        capability_gate="patch_routing",
    ),
    *AUDIO_CATALOG_PROPERTIES,
)

VIDEO_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    _planned_prop("layer", "video_layer", reason="video_layer_changes_need_visual_validation"),
    _planned_prop("fillStage", "boolean", reason="video_framing_changes_need_visual_validation"),
    _planned_prop("fillStyle", "video_fill_style", reason="video_framing_changes_need_visual_validation"),
    _planned_prop("holdLastFrame", "boolean", reason="video_playback_visual_state_needs_validation"),
    _planned_prop("preserveAspectRatio", "boolean", reason="video_appearance_requires_confirm_token"),
    _planned_prop("smooth", "boolean", reason="video_rendering_changes_need_visual_validation"),
    _planned_prop("audioOutputPatchID", "string", reason="video_io_requires_confirm_token", capability_gate="patch_routing"),
    _op("anchor", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _planned_prop("anchor/x", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("anchor/y", "number", reason="video_phase2_dry_run_only"),
    _op("translation", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _planned_prop("translation/x", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("translation/y", "number", reason="video_phase2_dry_run_only"),
    _op("scale", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _planned_prop("scale/x", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("scale/y", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("opacity", "opacity", reason="video_phase2_dry_run_only"),
    _op("crop", (("top", "number"), ("bottom", "number"), ("left", "number"), ("right", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _planned_prop("cropTop", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("cropBottom", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("cropLeft", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("cropRight", "number", reason="video_phase2_dry_run_only"),
    _planned_prop("blendMode", "video_blend_mode", reason="video_appearance_requires_confirm_token"),
    _planned_prop("clockType", "video_clock_type", reason="video_phase2_dry_run_only"),
    _op("origin", (("x", "number"), ("y", "number")), modes=("saved", "live"), planned_only_reason="geometry_changes_need_visual_validation"),
    _planned_prop("origin/x", "number", modes=("saved", "live"), reason="geometry_changes_need_visual_validation"),
    _planned_prop("origin/y", "number", modes=("saved", "live"), reason="geometry_changes_need_visual_validation"),
    _planned_prop("quaternion", "quaternion", reason="video_quaternion_requires_confirm_token"),
    _op(
        "resetRotation",
        (),
        path="resetRotation",
        read_key="quaternion",
        risk_tier="high",
        planned_only_reason="3d_rotation_changes_need_visual_validation",
    ),
    _planned_prop("stage/name", "non_empty_string", reason="stage_name_changes_need_visual_validation"),
    _op("stage/region/bounds", (("region", "non_empty_string"), ("x", "number"), ("y", "number"), ("width", "positive_number"), ("height", "positive_number")), path="stage/region/{region}/bounds", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds", (("id", "non_empty_string"), ("x", "number"), ("y", "number"), ("width", "positive_number"), ("height", "positive_number")), path="stage/regionID/{id}/bounds", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds", (("index", "non_negative_int"), ("x", "number"), ("y", "number"), ("width", "positive_number"), ("height", "positive_number")), path="stage/regionIndex/{index}/bounds", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/origin", (("region", "non_empty_string"), ("x", "number"), ("y", "number")), path="stage/region/{region}/bounds/origin", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/origin", (("id", "non_empty_string"), ("x", "number"), ("y", "number")), path="stage/regionID/{id}/bounds/origin", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/origin", (("index", "non_negative_int"), ("x", "number"), ("y", "number")), path="stage/regionIndex/{index}/bounds/origin", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/origin/x", (("region", "non_empty_string"), ("x", "number")), path="stage/region/{region}/bounds/origin/x", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/origin/x", (("id", "non_empty_string"), ("x", "number")), path="stage/regionID/{id}/bounds/origin/x", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/origin/x", (("index", "non_negative_int"), ("x", "number")), path="stage/regionIndex/{index}/bounds/origin/x", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/origin/y", (("region", "non_empty_string"), ("y", "number")), path="stage/region/{region}/bounds/origin/y", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/origin/y", (("id", "non_empty_string"), ("y", "number")), path="stage/regionID/{id}/bounds/origin/y", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/origin/y", (("index", "non_negative_int"), ("y", "number")), path="stage/regionIndex/{index}/bounds/origin/y", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/size", (("region", "non_empty_string"), ("width", "positive_number"), ("height", "positive_number")), path="stage/region/{region}/bounds/size", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/size", (("id", "non_empty_string"), ("width", "positive_number"), ("height", "positive_number")), path="stage/regionID/{id}/bounds/size", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/size", (("index", "non_negative_int"), ("width", "positive_number"), ("height", "positive_number")), path="stage/regionIndex/{index}/bounds/size", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/size/height", (("region", "non_empty_string"), ("height", "positive_number")), path="stage/region/{region}/bounds/size/height", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/size/height", (("id", "non_empty_string"), ("height", "positive_number")), path="stage/regionID/{id}/bounds/size/height", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/size/height", (("index", "non_negative_int"), ("height", "positive_number")), path="stage/regionIndex/{index}/bounds/size/height", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/bounds/size/width", (("region", "non_empty_string"), ("width", "positive_number")), path="stage/region/{region}/bounds/size/width", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/bounds/size/width", (("id", "non_empty_string"), ("width", "positive_number")), path="stage/regionID/{id}/bounds/size/width", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/bounds/size/width", (("index", "non_negative_int"), ("width", "positive_number")), path="stage/regionIndex/{index}/bounds/size/width", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/enableGrid", (("region", "non_empty_string"), ("value", "boolean")), path="stage/region/{region}/enableGrid", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/enableGrid", (("id", "non_empty_string"), ("value", "boolean")), path="stage/regionID/{id}/enableGrid", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/enableGrid", (("index", "non_negative_int"), ("value", "boolean")), path="stage/regionIndex/{index}/enableGrid", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/enableGuide", (("region", "non_empty_string"), ("value", "boolean")), path="stage/region/{region}/enableGuide", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/enableGuide", (("id", "non_empty_string"), ("value", "boolean")), path="stage/regionID/{id}/enableGuide", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/enableGuide", (("index", "non_negative_int"), ("value", "boolean")), path="stage/regionIndex/{index}/enableGuide", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/moveBy", (("region", "non_empty_string"), ("x", "number"), ("y", "number")), path="stage/region/{region}/moveBy", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/moveBy", (("id", "non_empty_string"), ("x", "number"), ("y", "number")), path="stage/regionID/{id}/moveBy", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/moveBy", (("index", "non_negative_int"), ("x", "number"), ("y", "number")), path="stage/regionIndex/{index}/moveBy", risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/region/resetControlPoints", (("region", "non_empty_string"),), path="stage/region/{region}/resetControlPoints", osc_args=(), risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionID/resetControlPoints", (("id", "non_empty_string"),), path="stage/regionID/{id}/resetControlPoints", osc_args=(), risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _op("stage/regionIndex/resetControlPoints", (("index", "non_negative_int"),), path="stage/regionIndex/{index}/resetControlPoints", osc_args=(), risk_tier="high", planned_only_reason="stage_region_changes_need_visual_validation"),
    _planned_prop("surfaceID", "string", reason="surface_refs_need_dedicated_resolution"),
    _planned_prop("surfaceName", "string", reason="surface_refs_need_dedicated_resolution"),
    *_planned_patch_refs("stage", validator="patch_ref"),
    *_planned_patch_refs("videoOutputPatch", validator="patch_ref"),
    _op("videoEffects/add", (("name", "non_empty_string"),), path="videoEffects/add", read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op(
        "videoEffects/insert",
        (("name", "non_empty_string"), ("index", "non_negative_int")),
        path="videoEffects/insert",
        read_key="videoEffects",
        risk_tier="high",
        planned_only_reason="video_effect_changes_need_visual_validation",
    ),
    _op("videoEffect/delete", (("name", "non_empty_string"),), path="videoEffect/{name}/delete", osc_args=(), read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op("videoEffectIndex/delete", (("index", "non_negative_int"),), path="videoEffectIndex/{index}/delete", osc_args=(), read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op("videoEffect/enabled", (("name", "non_empty_string"), ("value", "boolean")), path="videoEffect/{name}/enabled", read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op("videoEffectIndex/enabled", (("index", "non_negative_int"), ("value", "boolean")), path="videoEffectIndex/{index}/enabled", read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op("videoEffect/move", (("name", "non_empty_string"), ("newIndex", "non_negative_int")), path="videoEffect/{name}/move", read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op("videoEffectIndex/move", (("index", "non_negative_int"), ("newIndex", "non_negative_int")), path="videoEffectIndex/{index}/move", read_key="videoEffects", risk_tier="high", planned_only_reason="video_effect_changes_need_visual_validation"),
    _op(
        "videoEffect/parameter",
        (("name", "non_empty_string"), ("parameterKey", "non_empty_string"), ("setting", "json_value")),
        path="videoEffect/{name}/parameter/{parameterKey}",
        read_key="videoEffects",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="video_effect_parameters_need_profile_specific_validation",
    ),
    _op(
        "videoEffectIndex/parameter",
        (("index", "non_negative_int"), ("parameterKey", "non_empty_string"), ("setting", "json_value")),
        path="videoEffectIndex/{index}/parameter/{parameterKey}",
        read_key="videoEffects",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="video_effect_parameters_need_profile_specific_validation",
    ),
    _op(
        "videoEffect/parameters",
        (("name", "non_empty_string"), ("parameters", "dict_or_json_string")),
        path="videoEffect/{name}/parameters",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="video_effect_parameters_need_profile_specific_validation",
    ),
    _op(
        "videoEffectIndex/parameters",
        (("index", "non_negative_int"), ("parameters", "dict_or_json_string")),
        path="videoEffectIndex/{index}/parameters",
        modes=("saved", "live"),
        risk_tier="high",
        planned_only_reason="video_effect_parameters_need_profile_specific_validation",
    ),
)

VIDEO_PHASE2_VISUAL_PROPERTY_NAMES = frozenset(
    {
        "anchor/x",
        "anchor/y",
        "blendMode",
        "clockType",
        "cropBottom",
        "cropLeft",
        "cropRight",
        "cropTop",
        "doFade",
        "fillStage",
        "fillStyle",
        "layer",
        "quaternion",
        "resetRotation",
        "opacity",
        "preserveAspectRatio",
        "scale/x",
        "scale/y",
        "smooth",
        "rate",
        "startTime",
        "endTime",
        "playCount",
        "infiniteLoop",
        "preservePitch",
        "holdLastFrame",
        "level",
        "sliderLevel",
        "inputChannelName",
        "gang",
        "mute/channel",
        "solo/channel",
        "mute/channel/clear",
        "solo/channel/clear",
        "setDefaultLevels",
        "setSilentLevels",
        "stageID",
        "audioOutputPatchID",
        "videoInputPatchID",
        "audioInputPatchID",
        "sliceMarker/time",
        "sliceMarker/playCount",
        "addSliceMarker",
        "deleteSliceMarker",
        "deleteSliceMarkers",
        "lastSlicePlayCount",
        "lastSliceInfiniteLoop",
        "lockFadeToCue",
        "translation/x",
        "translation/y",
    }
)
VIDEO_PHASE2_TEXT_PROPERTY_NAMES = frozenset(
    {
        "fixedWidth",
        "text",
        "text/format/alignment",
        "text/format/backgroundColor",
        "text/format/color",
        "text/format/fontName",
        "text/format/fontSize",
        "text/format/lineSpacing",
        "text/format/shadowColor",
        "text/format/shadowBlurRadius",
        "text/format/shadowOffset/width",
        "text/format/shadowOffset/height",
        "text/format/strikethroughColor",
        "text/format/underlineStyle",
        "text/format/underlineColor",
        "text/format/strikethroughStyle",
    }
)
VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES = VIDEO_PHASE2_VISUAL_PROPERTY_NAMES | VIDEO_PHASE2_TEXT_PROPERTY_NAMES
VIDEO_PHASE2_VISUAL_PROPERTIES = tuple(
    prop for prop in VIDEO_CATALOG_PROPERTIES if prop.name in VIDEO_PHASE2_VISUAL_PROPERTY_NAMES
)

TEXT_SAFE_PROPERTIES = (
    _planned_prop("text", "string", reason="video_phase2_text_format_inheritance_risk"),
    _planned_prop("fixedWidth", "non_negative_number", reason="video_phase2_dry_run_only"),
    _planned_prop("text/format/alignment", "text_alignment", reason="video_phase2_dry_run_only"),
    _planned_prop("text/format/fontName", "non_empty_string", reason="video_phase2_dry_run_only"),
    _planned_prop("text/format/fontSize", "text_font_size", reason="video_phase2_dry_run_only"),
)

CAMERA_CATALOG_PROPERTIES = (
    _planned_prop("cameraPatch", "non_negative_int", reason="camera_patch_refs_need_dedicated_resolution", capability_gate="patch_routing"),
    *_planned_patch_refs("videoInputPatch", validator="patch_ref"),
)

TEXT_CATALOG_PROPERTIES = (
    _op("text/format", (("format", "dict_or_json_string"),), path="text/format", planned_only_reason="rich_text_format_needs_dedicated_validation"),
    _op("text/format/fontFamilyAndStyle", (("family", "non_empty_string"), ("style", "non_empty_string")), planned_only_reason="font_pair_needs_system_font_validation"),
    _op("text/format/color", _rgba_args(), read_key="text/format/color", planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/backgroundColor", _rgba_args(), read_key="text/format/backgroundColor", planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/shadowColor", _rgba_args(), read_key="text/format/shadowColor", planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/underlineColor", _rgba_args(), read_key="text/format/underlineColor", planned_only_reason="text_color_changes_need_visual_validation"),
    _op("text/format/strikethroughColor", _rgba_args(), read_key="text/format/strikethroughColor", planned_only_reason="text_color_changes_need_visual_validation"),
    _planned_prop("text/format/lineSpacing", "number", reason="text_layout_changes_need_visual_validation"),
    _planned_prop("text/format/shadowBlurRadius", "non_negative_number", reason="text_shadow_changes_need_visual_validation"),
    _op("text/format/shadowOffset", (("width", "number"), ("height", "number")), planned_only_reason="text_shadow_changes_need_visual_validation"),
    _planned_prop("text/format/shadowOffset/width", "number", reason="text_shadow_changes_need_visual_validation"),
    _planned_prop("text/format/shadowOffset/height", "number", reason="text_shadow_changes_need_visual_validation"),
    _planned_prop("text/format/underlineStyle", "text_line_style", reason="text_decoration_needs_visual_validation"),
    _planned_prop("text/format/strikethroughStyle", "text_line_style", reason="text_decoration_needs_visual_validation"),
    *VIDEO_CATALOG_PROPERTIES,
)

LIGHT_CATALOG_PROPERTIES = (
    _planned_prop("lightCommandText", "string", reason="light_command_requires_valid_analysis_and_confirm_token"),
    _planned_prop("alwaysCollate", "boolean", reason="light_behavior_requires_confirm_token"),
    _planned_prop("subcontroller", "boolean", reason="light_behavior_requires_confirm_token"),
    _op("collateAndStart", (), path="collateAndStart", risk_tier="high", planned_only_reason="light_commands_can_affect_visual_output"),
    _op(
        "setLight",
        (("instrument_or_group", "non_empty_string"), ("setting", "json_value")),
        path="setLight",
        risk_tier="high",
        planned_only_reason="light_commands_can_affect_visual_output",
    ),
    _op(
        "replaceLightCommand",
        (("oldCommand", "non_empty_string"), ("newCommand", "non_empty_string")),
        risk_tier="high",
        planned_only_reason="light_commands_can_affect_visual_output",
    ),
    _op(
        "removeLightCommandsMatching",
        (("match", "non_empty_string"),),
        risk_tier="high",
        planned_only_reason="light_command_removal_needs_validation",
    ),
    _op("safeSort", (), path="safeSort", risk_tier="high", planned_only_reason="light_command_order_changes_need_validation"),
    _op("safeSortCommands", (), path="safeSortCommands", risk_tier="high", planned_only_reason="light_command_order_changes_need_validation"),
    _op("prune", (), path="prune", risk_tier="high", planned_only_reason="light_command_removal_needs_validation"),
    _op("pruneCommands", (), path="pruneCommands", risk_tier="high", planned_only_reason="light_command_removal_needs_validation"),
)

FADE_CATALOG_PROPERTIES = (
    _planned_prop("stopTargetWhenDone", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("cueTargetNumber", "cue_target_number", reason="fade_target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetID", "cue_target_id", reason="fade_target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetNumber", "cue_target_number", reason="fade_target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetID", "cue_target_id", reason="fade_target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("audioMapTargetID", "target_id", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("patchTargetID", "target_id", reason="target_refs_need_dedicated_resolution"),
    _planned_prop("targetMode", "target_mode", reason="target_behavior_needs_validation"),
    _planned_prop("levelsMode", "fade_mode", reason="fade_level_mode_needs_validation"),
    _planned_prop("geoMode", "fade_mode", reason="fade_geometry_mode_needs_validation"),
    _planned_prop("mode", "fade_mode", path="levelsMode", read_key="levelsMode", reason="deprecated_use_levelsMode"),
    _planned_prop("fadeType", "fade_type", reason="fade_type_needs_validation"),
    _planned_prop("pathHeight", "positive_number", reason="fade_geometry_path_needs_validation"),
    _planned_prop("pathWidth", "positive_number", reason="fade_geometry_path_needs_validation"),
    _planned_prop("rotation", "number", reason="fade_geometry_needs_target_validation"),
    _planned_prop("rotationType", "rotation_type", reason="fade_geometry_needs_target_validation"),
    _planned_prop("doOpacity", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doRate", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doRotation", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doScale", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("doTranslation", "boolean", reason="fade_target_behavior_needs_validation"),
    _planned_prop("opacity", "opacity", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("rate", "rate", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("translation/x", "number", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("translation/y", "number", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("scale/x", "number", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("scale/y", "number", reason="fade_geometry_requires_confirm_token"),
    _planned_prop("quaternion", "quaternion", reason="fade_geometry_requires_confirm_token"),
    _op(
        "sliderLevel",
        (("channel", "audio_output_ref"), ("decibel", "decibel")),
        path="sliderLevel/{channel}",
        read_key="sliderLevels",
        risk_tier="high",
        planned_only_reason="fade_audio_levels_require_confirm_token",
    ),
    _op(
        "level",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("decibel", "decibel")),
        path="level/{inChannel}/{outChannel}",
        read_key="levels",
        risk_tier="high",
        planned_only_reason="fade_audio_levels_require_confirm_token",
    ),
    _op("doLevel", (("row", "audio_level_row"), ("column", "audio_output_ref"), ("value", "boolean")), path="doLevel/{row}/{column}", read_key="doLevel", risk_tier="high", planned_only_reason="fade_level_targets_need_validation"),
    _op(
        "inputChannelName",
        (("number", "positive_int"), ("name", "string")),
        path="inputChannelName/{number}",
        risk_tier="high",
        planned_only_reason="fade_audio_level_meta_requires_confirm_token",
    ),
    _op(
        "gang",
        (("inChannel", "audio_level_row"), ("outChannel", "audio_output_ref"), ("gang", "string")),
        path="gang/{inChannel}/{outChannel}",
        risk_tier="high",
        planned_only_reason="fade_audio_level_meta_requires_confirm_token",
    ),
    _op("doObjectLevel", (("row", "audio_level_row"), ("object", "audio_object_ref"), ("value", "boolean")), path="doObjectLevel/{row}/{object}", risk_tier="high", planned_only_reason="fade_object_targets_need_validation"),
    _op("doObjectIDLevel", (("row", "audio_level_row"), ("objectID", "audio_object_ref"), ("value", "boolean")), path="doObjectIDLevel/{row}/{objectID}", risk_tier="high", planned_only_reason="fade_object_targets_need_validation"),
    _op("setGeometryFromTarget", (), path="setGeometryFromTarget", risk_tier="high", planned_only_reason="target_copy_actions_need_dedicated_validation"),
    _op("setLevelsFromTarget", (), path="setLevelsFromTarget", risk_tier="high", planned_only_reason="target_copy_actions_need_dedicated_validation"),
    _op("willFade", (("row", "audio_level_row"), ("column", "audio_output_ref"), ("value", "boolean")), path="willFade/{row}/{column}", risk_tier="high", planned_only_reason="deprecated_use_doLevel"),
)

NETWORK_CATALOG_PROPERTIES = (
    _planned_prop("networkPatchName", "string", reason="network_osc_message_requires_patch_type_validation", capability_gate="patch_routing"),
    _planned_prop("networkPatchNumber", "non_negative_int", reason="network_osc_message_requires_patch_type_validation", capability_gate="patch_routing"),
    _planned_prop("networkPatchID", "string", reason="network_osc_message_requires_patch_type_validation", capability_gate="patch_routing"),
    _planned_prop("customString", "string", reason="network_osc_message_requires_patch_type_validation"),
    _planned_prop("fadeEntries", "list_or_json_string", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("fadeFrom", "number", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("fadeNumberType", "fade_number_type", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("fadeTo", "number", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("fadeType", "network_fade_type", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("fps", "network_fps", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("pathHeight", "positive_number", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("pathWidth", "positive_number", reason="network_fade_routes_require_deterministic_readback"),
    _planned_prop("patch", "non_negative_int", reason="deprecated_use_networkPatchNumber"),
    _op("parameterFadeEnabled", (("parameter", "non_empty_string"), ("value", "boolean")), path="parameterFadeEnabled/{parameter}", risk_tier="high", planned_only_reason="network_device_description_parameters_out_of_scope"),
    _planned_prop("parameterFadesEnabled", "list", reason="network_device_description_parameters_out_of_scope"),
    _op(
        "parameterValue",
        (("parameter", "non_empty_string"), ("value", "json_value")),
        path="parameterValue/{parameter}",
        risk_tier="high",
        planned_only_reason="network_device_description_parameters_out_of_scope",
    ),
    _planned_prop("parameterValues", "list", reason="network_device_description_parameters_out_of_scope"),
)

MIDI_CATALOG_PROPERTIES = (
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
    _planned_prop("messageType", "midi_message_type", reason="midi_message_mode_needs_validation"),
    _planned_prop("channel", "midi_channel", reason="midi_can_trigger_external_devices"),
    _planned_prop("command", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("commandFormat", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("status", "midi_status", reason="midi_can_trigger_external_devices"),
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
    _planned_prop("hours", "midi_time_part", reason="msc_timecode_needs_validation"),
    _planned_prop("minutes", "midi_time_part", reason="msc_timecode_needs_validation"),
    _planned_prop("seconds", "midi_time_part", reason="msc_timecode_needs_validation"),
    _planned_prop("frames", "midi_time_part", reason="msc_timecode_needs_validation"),
    _planned_prop("subframes", "midi_time_part", reason="msc_timecode_needs_validation"),
    _planned_prop("macro", "byte", reason="midi_can_trigger_external_devices"),
    _planned_prop("rawString", "string", reason="sysex_can_trigger_external_devices"),
    _planned_prop("qList", "string", reason="msc_fields_need_validation"),
    _planned_prop("qNumber", "string", reason="msc_fields_need_validation"),
    _planned_prop("qPath", "string", reason="msc_fields_need_validation"),
    _planned_prop("timecodeString", "string", reason="msc_timecode_needs_validation"),
    _planned_prop("timecodeFormat", "midi_timecode_format", reason="msc_timecode_needs_validation"),
    _planned_prop("doFade", "boolean", reason="midi_fade_can_trigger_external_devices"),
    _planned_prop("patch", "non_negative_int", reason="deprecated_use_midiPatchNumber"),
)

MIDI_FILE_CATALOG_PROPERTIES = (
    _planned_prop("fileTarget", "string", reason="file_paths_need_dedicated_safety_policy"),
    _prop("rate", "rate", risk_tier="medium", real_write_enabled=True),
    _prop("startTime", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("endTime", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("duration", "non_negative_number", risk_tier="medium", real_write_enabled=True),
    _prop("playCount", "positive_int", risk_tier="medium", real_write_enabled=True),
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
    _planned_prop("patch", "non_negative_int", reason="deprecated_use_midiPatchNumber"),
)

TIMECODE_CATALOG_PROPERTIES = (
    _prop("outputType", "timecode_output_type", risk_tier="medium", real_write_enabled=True),
    _planned_prop(
        "timecodeMode",
        "timecode_output_type",
        path="outputType",
        read_key="outputType",
        reason="use_documented_outputType_for_timecode_output_mode",
    ),
    _planned_prop(
        "timecodeString",
        "string",
        reason="timecodeString_is_documented_for_midi_msc_not_timecode_cues",
    ),
    _planned_prop(
        "timecodeFormat",
        "timecode_framerate",
        path="framerate",
        read_key="framerate",
        reason="use_documented_timecodeFrameRate_for_timecode_framerate",
    ),
    _prop("timecodeFrameRate", "timecode_framerate", path="framerate", read_key="framerate", risk_tier="medium", real_write_enabled=True),
    _prop("startTime", "string", risk_tier="medium", real_write_enabled=True),
    _prop("endTime", "string", risk_tier="medium", real_write_enabled=True),
    _planned_prop("ltcChannel", "positive_int", reason="ltc_output_channel_affects_external_timecode_output"),
    *_planned_patch_refs("audioOutputPatch", validator="patch_ref"),
    *_planned_patch_refs("midiPatch", validator="patch_ref"),
)

TARGET_CATALOG_PROPERTIES = (
    _planned_prop("cueTargetNumber", "cue_target_number", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetID", "cue_target_id", reason="utility_target_requires_confirm_token", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetName", "non_empty_string", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_name_resolution_unsupported",)),
    _planned_prop("tempCueTargetNumber", "cue_target_number", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetID", "cue_target_id", reason="target_refs_need_dedicated_resolution", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("targetMode", "target_mode", reason="target_behavior_needs_validation"),
)

RESET_CATALOG_PROPERTIES = (
    _planned_prop("cueTargetNumber", "cue_target_number", reason="reset_targets_need_validation", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetID", "cue_target_id", reason="utility_target_requires_confirm_token", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("patchTargetID", "target_id", reason="reset_targets_need_validation"),
    _planned_prop("audioMapTargetID", "target_id", reason="reset_targets_need_validation"),
    _planned_prop("targetMode", "target_mode", reason="reset_targets_need_validation"),
)

DEVAMP_CATALOG_PROPERTIES = (
    _planned_prop("cueTargetNumber", "cue_target_number", reason="devamp_target_uuid_only", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetID", "cue_target_id", reason="devamp_target_requires_confirm_token", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("cueTargetName", "non_empty_string", reason="devamp_target_uuid_only", contextual_requirements=("target_name_resolution_unsupported",)),
    _planned_prop("tempCueTargetNumber", "cue_target_number", reason="devamp_target_uuid_only", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("tempCueTargetID", "cue_target_id", reason="devamp_target_uuid_only", contextual_requirements=("target_ref_resolves",)),
    _planned_prop("targetMode", "target_mode", reason="devamp_target_mode_out_of_scope"),
    _planned_prop("devampType", "devamp_type", reason="devamp_settings_require_confirm_token"),
    _planned_prop("startNextCueWhenSliceEnds", "boolean", reason="devamp_settings_require_confirm_token"),
    _planned_prop("stopTargetWhenSliceEnds", "boolean", reason="devamp_settings_require_confirm_token"),
)

SCRIPT_CATALOG_PROPERTIES = (
    _planned_prop("scriptSource", "string", reason="not_editable_by_osc"),
    _planned_prop("scriptText", "string", path="scriptSource", read_key="scriptSource", reason="not_editable_by_osc"),
    _op("compileSource", (), path="compileSource", risk_tier="high", planned_only_reason="script_compile_can_execute_or_surface_script_errors"),
)


UPDATE_PROFILES: dict[str, UpdateProfileSpec] = {
    COMMON_UPDATE_PROFILE: UpdateProfileSpec(
        COMMON_UPDATE_PROFILE,
        (),
        (*COMMON_PROPERTIES, *COMMON_CATALOG_PROPERTIES),
        "medium",
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
        "Audio transport, cue I/O selection, and Levels use specialized confirmation gates; other catalog routes remain dry-run only.",
    ),
    "mic_basic": UpdateProfileSpec(
        "mic_basic",
        ("Mic",),
        (*COMMON_PROPERTIES, *MIC_CATALOG_PROPERTIES),
        "medium",
        True,
        "Mic cue I/O selection and Levels use specialized confirmation gates; Format remains dry-run only pending input-patch capacity validation.",
    ),
    "video_basic": UpdateProfileSpec("video_basic", ("Video",), (*COMMON_PROPERTIES, *VIDEO_AUDIO_TIME_PROPERTIES, *VIDEO_AUDIO_LEVEL_PROPERTIES, *VIDEO_AUDIO_MATRIX_PROPERTIES, *VIDEO_AUDIO_LEVEL_META_PROPERTIES, *VIDEO_AUDIO_MUTE_SOLO_PROPERTIES, *VIDEO_AUDIO_LEVEL_BULK_PROPERTIES, _planned_prop("doFade", "boolean", reason="video_integrated_fade_requires_confirm_token"), _planned_prop("lockFadeToCue", "boolean", reason="video_integrated_fade_requires_confirm_token"), *VIDEO_SLICE_MARKER_PROPERTIES, *VIDEO_CATALOG_PROPERTIES), "medium", True, "Video opacity, translation, visual scalars, embedded-audio timing, audio level, audio matrix, audio level metadata, mute/solo, integrated fade, clockType, and slice marker edits use specialized confirmation gates; remaining visual properties stay dry-run only."),
    "camera_basic": UpdateProfileSpec("camera_basic", ("Camera",), (*COMMON_PROPERTIES, *MIC_CATALOG_PROPERTIES, *VIDEO_CATALOG_PROPERTIES, *CAMERA_CATALOG_PROPERTIES), "medium", True, "Camera opacity, translation, and visual scalars use specialized confirmation gates; remaining visual properties stay dry-run only."),
    TEXT_BASIC_UPDATE_PROFILE: UpdateProfileSpec(
        TEXT_BASIC_UPDATE_PROFILE,
        ("Text",),
        (*COMMON_PROPERTIES, *TEXT_SAFE_PROPERTIES, *VIDEO_PHASE2_VISUAL_PROPERTIES, *TEXT_CATALOG_PROPERTIES),
        "medium",
        True,
        "Text visual properties and basic text content, font size, and alignment use specialized confirmation gates; rich formatting stays dry-run only.",
    ),
    "light_basic": UpdateProfileSpec("light_basic", ("Light",), (*COMMON_PROPERTIES, *LIGHT_CATALOG_PROPERTIES), "high", True, "Light profile; lightCommandText and saved behavior flags use specialized confirmation gates."),
    "fade_basic": UpdateProfileSpec("fade_basic", ("Fade",), (*FADE_COMMON_PROPERTIES, *FADE_CATALOG_PROPERTIES), "high", True, "Fade Basics, exact cue targets, 1D geometry, Levels matrices, and completion behavior use specialized confirmation gates; remaining Fade routes stay planned-only."),
    "network_basic": UpdateProfileSpec("network_basic", ("Network",), (*COMMON_PROPERTIES, *NETWORK_CATALOG_PROPERTIES), "high", True, "Network profile; OSC Message mode cannot be proven from documented patch readback, so network output remains dry-run only."),
    "midi_basic": UpdateProfileSpec("midi_basic", ("MIDI",), (*COMMON_PROPERTIES, *MIDI_CATALOG_PROPERTIES), "high", True, "MIDI profile; MIDI messages remain dry-run only."),
    "midi_file_basic": UpdateProfileSpec("midi_file_basic", ("MIDI File",), (*COMMON_PROPERTIES, *MIDI_FILE_CATALOG_PROPERTIES), "medium", True, "MIDI File profile with playback metadata writes."),
    "timecode_basic": UpdateProfileSpec("timecode_basic", ("Timecode",), (*COMMON_PROPERTIES, *TIMECODE_CATALOG_PROPERTIES), "medium", True, "Timecode profile with basic metadata writes."),
    "target_basic": UpdateProfileSpec("target_basic", ("Start", "Stop", "Pause", "Load", "Goto", "GoTo", "Target", "Arm", "Disarm"), (*COMMON_PROPERTIES, *TARGET_CATALOG_PROPERTIES), "high", True, "Target cue profile; target refs remain dry-run only."),
    "reset_basic": UpdateProfileSpec("reset_basic", ("Reset",), (*COMMON_PROPERTIES, *RESET_CATALOG_PROPERTIES), "high", True, "Reset profile; reset targets remain dry-run only."),
    "devamp_basic": UpdateProfileSpec("devamp_basic", ("Devamp",), (*COMMON_PROPERTIES, *DEVAMP_CATALOG_PROPERTIES), "high", True, "Devamp target and settings use a specialized exact-UUID confirmation gate; name, number, temporary, and mode targets remain dry-run only."),
    "script_basic": UpdateProfileSpec("script_basic", ("Script",), (*COMMON_PROPERTIES, *SCRIPT_CATALOG_PROPERTIES), "high", True, "Script profile; script source remains dry-run only."),
}

_EXTRACTED_WRITE_FAMILY_PROPERTIES = {
    "video_opacity": {
        "video_basic": {"opacity"},
        "camera_basic": {"opacity"},
        "text_basic": {"opacity"},
    },
    "video_translation": {
        profile: {"translation/x", "translation/y"}
        for profile in ("video_basic", "camera_basic", "text_basic")
    },
    "video_scalars": {
        profile: {
            "scale/x",
            "scale/y",
            "anchor/x",
            "anchor/y",
            "cropTop",
            "cropBottom",
            "cropLeft",
            "cropRight",
        }
        for profile in ("video_basic", "camera_basic", "text_basic")
    },
    "video_appearance": {
        profile: {"blendMode", "preserveAspectRatio"}
        for profile in ("video_basic", "camera_basic", "text_basic")
    },
    "video_audio_time": {
        "video_basic": {
            "startTime",
            "endTime",
            "playCount",
            "infiniteLoop",
            "rate",
            "preservePitch",
            "holdLastFrame",
        }
    },
    "text_basics": {
        "text_basic": {
            "text",
            "fixedWidth",
            "text/format/fontSize",
            "text/format/alignment",
            "text/format/fontName",
            "text/format/lineSpacing",
            "text/format/color",
        }
    },
}

for _family_name, _profiles in _EXTRACTED_WRITE_FAMILY_PROPERTIES.items():
    for _profile_name, _property_names in _profiles.items():
        _profile = UPDATE_PROFILES[_profile_name]
        UPDATE_PROFILES[_profile_name] = replace(
            _profile,
            properties=tuple(
                replace(prop, write_family=_family_name)
                if prop.name in _property_names
                else prop
                for prop in _profile.properties
            ),
        )

CAPABILITY_GATES = {
    "audio_map_editing",
    "audio_output",
    "cue_behavior",
    "deprecated_osc",
    "fade_targets",
    "group_mode",
    "group_playlist",
    "file_target_access",
    "light_output",
    "midi_output",
    "network_output",
    "patch_routing",
    "script_compile",
    "slice_editing",
    "spatial_audio",
    "target_resolution",
    "text_rich_format",
    "video_effects",
    "video_visual",
}


def _default_capability_gate(profile: str, prop: CuePropertySpec) -> str | None:
    if prop.real_write_enabled or not prop.planned_only_reason:
        return prop.capability_gate
    name = prop.name
    if prop.planned_only_reason.startswith("deprecated_") or name == "patch":
        return "deprecated_osc"
    if name == "fileTarget":
        return "file_target_access"
    if "Patch" in name or "patchTarget" in name or "audioMapTarget" in name:
        return "patch_routing"
    if name.startswith(("cueTarget", "tempCueTarget", "targetMode")):
        return "target_resolution"
    if profile in {"target_basic", "reset_basic", "devamp_basic"}:
        return "target_resolution"
    if profile == "fade_basic":
        return "fade_targets"
    if profile == "light_basic":
        return "light_output"
    if profile == "network_basic":
        return "network_output"
    if profile == "midi_basic":
        return "midi_output"
    if profile == "script_basic":
        return "script_compile" if name == "compileSource" else None
    if name.startswith(("level", "sliderLevel", "gang", "doLevel", "mute", "solo", "setDefaultLevels", "setSilentLevels", "audioOutputPatch")):
        return "audio_output"
    if "Slice" in name or "sliceMarker" in name:
        return "slice_editing"
    if name.startswith(("object", "objectID", "objectLevel", "objectIDLevel", "doObject")):
        return "spatial_audio"
    if name.startswith("audioMap/"):
        return "audio_map_editing"
    if profile in {"audio_basic", "mic_basic"}:
        return "audio_output"
    if name.startswith("videoEffect") or name.startswith("videoEffects"):
        return "video_effects"
    if name.startswith("text/format"):
        return "text_rich_format"
    if profile in {"video_basic", "camera_basic", "text_basic"}:
        return "video_visual"
    if profile == COMMON_UPDATE_PROFILE:
        return "cue_behavior"
    return prop.capability_gate


def _apply_default_capability_gates() -> None:
    for profile_name, profile in list(UPDATE_PROFILES.items()):
        properties = tuple(
            replace(prop, capability_gate=_default_capability_gate(profile_name, prop))
            if _default_capability_gate(profile_name, prop) and prop.capability_gate is None
            else prop
            for prop in profile.properties
        )
        UPDATE_PROFILES[profile_name] = replace(profile, properties=properties)


_apply_default_capability_gates()

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
                    "doc_section": prop.doc_section,
                    "osc_paths": list(prop.osc_paths or (prop.path or prop.name,)),
                    "capability_gate": prop.capability_gate,
                    "readback": prop.readback,
                    "contextual_requirements": list(prop.contextual_requirements),
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
                "read_key": prop["read_key"],
                "readback": prop["readback"],
                "modes": prop["modes"],
                "risk_tier": prop["risk_tier"],
                "real_write_enabled": prop["real_write_enabled"],
                "planned_only_reason": prop["planned_only_reason"],
                "capability_gate": prop["capability_gate"],
                "doc_section": prop["doc_section"],
                "osc_paths": prop["osc_paths"],
                "contextual_requirements": prop["contextual_requirements"],
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
                "read_key": prop["read_key"],
                "readback": prop["readback"],
                "risk_tier": prop["risk_tier"],
                "real_write_enabled": prop["real_write_enabled"],
                "planned_only_reason": prop["planned_only_reason"],
                "capability_gate": prop["capability_gate"],
                "contextual_requirements": prop["contextual_requirements"],
            }
            validators[property_name] = {arg["name"]: arg["validator"] for arg in prop["args"]}
            if prop["planned_only_reason"]:
                planned_only_reason[property_name] = prop["planned_only_reason"]

    return {
        "compatible_profiles": compatible_profiles,
        "recommended_profile": recommended_profile,
        "real_write_properties": sorted(real_write_details),
        "dry_run_only_properties": sorted(dry_run_only_details),
        "gated_or_dry_run_only_properties": sorted(dry_run_only_details),
        "property_details": {
            "real_write": real_write_details,
            "dry_run_only": dry_run_only_details,
            "gated_or_dry_run_only": dry_run_only_details,
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
        "available_capability_gates": sorted(CAPABILITY_GATES),
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


def ensure_real_write_allowed(
    profile: str,
    operations: list[dict[str, Any]],
    confirmed_gates: list[str] | tuple[str, ...] | set[str] | None = None,
) -> None:
    errors = real_write_permission_errors(profile, operations, confirmed_gates)
    if errors:
        raise UnsafeWriteOperationError("; ".join(errors.values()))


def real_write_permission_errors(
    profile: str,
    operations: list[dict[str, Any]],
    confirmed_gates: list[str] | tuple[str, ...] | set[str] | None = None,
) -> dict[str, str]:
    spec = UPDATE_PROFILES[validate_update_profile(profile)]
    if not spec.real_write_enabled:
        return {"profile": f"{profile} is cataloged for dry-run only; real write is not enabled yet."}
    confirmed = {gate.strip() for gate in confirmed_gates or () if isinstance(gate, str) and gate.strip()}
    errors: dict[str, str] = {}
    for operation in operations:
        prop = str(operation["property"])
        if profile == "fade_basic":
            errors[prop] = (
                f"{prop} is gated or dry-run only outside the specialized single-cue Fade gate."
            )
            continue
        if profile in {"target_basic", "reset_basic"} and prop in {
            "cueTargetID",
            "cueTargetNumber",
            "cueTargetName",
            "tempCueTargetID",
            "tempCueTargetNumber",
            "patchTargetID",
            "audioMapTargetID",
            "targetMode",
        }:
            errors[prop] = (
                f"{prop} is gated or dry-run only outside the specialized single-cue saved cueTargetID gate."
            )
            continue
        if profile == "devamp_basic" and prop in {
            "cueTargetID",
            "devampType",
            "startNextCueWhenSliceEnds",
            "stopTargetWhenSliceEnds",
        }:
            errors[prop] = (
                f"{prop} is gated or dry-run only outside the specialized single-cue saved Devamp gate."
            )
            continue
        if profile == "light_basic" and prop == "lightCommandText":
            errors[prop] = (
                "lightCommandText is gated or dry-run only outside the specialized "
                "single-cue Phase 4 qlab_edit_cues flow."
            )
            continue
        if profile == "light_basic" and prop in {
            "collateAndStart",
            "setLight",
            "replaceLightCommand",
            "removeLightCommandsMatching",
            "safeSort",
            "safeSortCommands",
            "prune",
            "pruneCommands",
        }:
            errors[prop] = f"{prop} is gated or dry-run only in PLAN LUCES Phase 5."
            continue
        if profile == "light_basic" and prop in {"alwaysCollate", "subcontroller"}:
            errors[prop] = (
                f"{prop} is gated or dry-run only outside the specialized single-cue Phase 5 "
                "qlab_edit_cues flow."
            )
            continue
        if operation["real_write_enabled"]:
            continue
        token = str(operation.get("confirm_token") or "")
        if token not in confirmed:
            errors[prop] = (
                f"{prop} is gated or dry-run only for real writes and requires confirm_token {token!r}; broad capability gate "
                f"{operation.get('capability_gate') or 'no_real_write_gate'!r} is dry-run discovery only."
            )
        if not operation.get("read_key") or len(operation.get("args") or []) != 1:
            errors[prop] = (
                f"{prop} is gated or dry-run only because it has no deterministic one-value readback; "
                "dry-run only until a verifier is implemented."
            )
    return errors


def read_keys_for_operations(operations: list[dict[str, Any]]) -> list[str]:
    keys = ["uniqueID", "type"]
    keys.extend(operation["read_key"] for operation in operations if operation.get("read_key"))
    if any(str(operation.get("property", "")).startswith("playlist/") for operation in operations):
        keys.append("mode")
    if any(operation.get("property") in {"duration", "tempDuration"} for operation in operations):
        keys.append("allowsEditingDuration")
    return list(dict.fromkeys(keys))


def planned_write_capabilities(dry_run_default: bool) -> dict[str, Any]:
    catalog = profile_catalog()
    update_cues_capability = {
        "planned": True,
        "tool": "qlab_edit_cues",
        "batch": {
            "min_items": 1,
            "max_items": 50,
            "requires_concrete_cue_refs": True,
            "ambiguous_refs_allowed": False,
            "preflight_before_any_setter": True,
            "setter_target": "cue_id",
        },
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
        "available_capability_gates": sorted(CAPABILITY_GATES),
        "dry_run_default": dry_run_default,
    }
    return {
        "create_cue": {
            "planned": True,
            "cue_types": [
                "memo", "group", "wait", "audio", "mic", "video", "camera", "text", "light",
                "fade", "network", "midi", "midi_file", "timecode", "start", "stop", "pause",
                "load", "reset", "devamp", "goto", "target", "arm", "disarm",
            ],
            "initialization": "qlab_cue_template_defaults",
            "operational_state": "reported_separately_from_structural_creation",
            "dry_run_default": dry_run_default,
            "placement": {
                "after_cue_id": "exact_uuid_anchor_for_existing_cue",
                "parent_container_id": "exact_uuid_for_empty_cue_list_group_or_cart",
                "selection": "exactly_one_of_after_cue_id_or_parent_container_id",
                "cue_list": "currentCueListID_then_new_without_anchor",
                "group": "new_after_group_then_move_to_index_zero",
                "cue_cart": "new_inside_cart_request_0_0_readback_1_1_on_qlab_5_5_10",
                "cue_cart_rejects": ["group"],
                "parent_id": "verified_from_structural_snapshot",
                "index": "anchor_index_plus_one_or_zero_for_empty_container",
                "confirm_token": "confirm:createCue:v2",
            },
        },
        "create_cues": {
            "planned": True,
            "cue_types": [
                "memo", "group", "wait", "audio", "mic", "video", "camera", "text", "light",
                "fade", "network", "midi", "midi_file", "timecode", "start", "stop", "pause",
                "load", "reset", "devamp", "goto", "target", "arm", "disarm",
            ],
            "sequence": {
                "max_items": 50,
                "one_new_per_item": True,
                "anchor": "previous_created_cue_id",
                "stops_on_ambiguity": True,
                "rollback": False,
            },
            "initial_placement": "same_as_create_cue",
            "initialization": "qlab_cue_template_defaults",
            "properties": [],
        },
        "batch_update_cues": update_cues_capability,
        "edit_existing_cue": {
            **update_cues_capability,
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
    video_phase2_profiles = {"video_basic", "camera_basic", "text_basic"}
    if normalized_mode == "live" and profile in video_phase2_profiles:
        raise UnsafeWriteOperationError("Video-family editing blocks live mode; use saved mode for dry-run planning")
    normalized_args = _normalize_args(spec, raw_args, source=source)
    path = _render_path(spec, normalized_args)
    if normalized_mode == "live":
        path = f"{path}/live"
    osc_args = (
        list(normalized_args["value"])
        if spec.name == "quaternion"
        else [normalized_args[arg_name] for arg_name in spec.osc_args]
    )
    operation = {
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
        "capability_gate": spec.capability_gate,
        "readback": spec.readback,
        "contextual_requirements": list(spec.contextual_requirements),
    }
    if profile in video_phase2_profiles and spec.name in VIDEO_PHASE2_DRY_RUN_PROPERTY_NAMES:
        operation.update(
            {
                "real_write_possible": False,
                "requires_confirm_token": False,
                "future_gate_requirements": [
                    "future_versioned_confirm_token",
                    "single_cue_single_property",
                    "saved_mode",
                    "fresh_baseline",
                    "exact_readback",
                    "manual_rollback_plan",
                    *(["verify_first_character_inherited_format"] if spec.name == "text" else []),
                ],
            }
        )
    elif not spec.real_write_enabled:
        operation["confirm_token"] = _confirm_token(profile, spec.name, path, normalized_mode, osc_args)
    return operation


def _confirm_token(profile: str, property_name: str, path: str, mode: str, args: list[Any]) -> str:
    payload = {
        "profile": profile,
        "property": property_name,
        "path": path,
        "mode": mode,
        "args": args,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    return f"confirm:{property_name}:{digest[:16]}"


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
        if spec.name == "resetRotation" and len(spec.args) == 0:
            if raw_args is not True:
                raise UnsafeWriteOperationError("resetRotation property form must be true")
            return {}
        if len(spec.args) != 1 or spec.args[0][0] != "value":
            raise UnsafeWriteOperationError(f"{spec.name} requires operations[] because it has structured arguments")
        return {"value": _validate_named_value(spec.name, spec.args[0][1], raw_args)}
    if spec.name == "quaternion" and len(spec.args) == 1 and spec.args[0][0] == "value":
        if isinstance(raw_args, dict):
            if set(raw_args) != {"value"}:
                raise UnsafeWriteOperationError("quaternion args must contain only value")
            raw_args = raw_args["value"]
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
        value = str(args[arg_name])
        if "/" in value:
            raise UnsafeWriteOperationError(f"{spec.name}.{arg_name} must not contain '/'")
        path = path.replace(f"{{{arg_name}}}", value)
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
    if validator == "decibel":
        return _decibel(value)
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
    if validator == "text_font_size":
        number = _number(value, "value must be a finite number greater than 0 and at most 1000")
        if not math.isfinite(float(number)) or number <= 0 or number > 1000:
            raise UnsafeWriteOperationError("value must be a finite number greater than 0 and at most 1000")
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
        number = _number(value, "opacity must be a number from 0 to 1")
        if not math.isfinite(float(number)) or number < 0 or number > 1:
            raise UnsafeWriteOperationError("opacity must be a number from 0 to 1")
        return number
    if validator == "video_layer":
        return _int_range(value, 0, 1000, "value must be an integer from 0 to 1000")
    if validator == "video_fill_style":
        return _int_range(value, 0, 2, "value must be 0 for fit, 1 for fill, or 2 for stretch")
    if validator == "quaternion":
        return _quaternion(value)
    if validator == "video_blend_mode":
        return _blend_mode(value)
    if validator == "video_clock_type":
        if value not in {"audio", "video"}:
            raise UnsafeWriteOperationError("value must be exactly audio or video")
        return value
    if validator == "continue_mode":
        return _continue_mode(value)
    if validator == "color_condition":
        return _int_range(value, 0, 2, "value must be 0, 1, or 2")
    if validator == "second_trigger_action":
        return _int_range(value, 0, 7, "value must be a second trigger action index from 0 to 7")
    if validator == "timecode_part":
        return _int_range(value, 0, 99, "value must be a non-negative timecode component")
    if validator == "group_mode":
        return _group_mode(value)
    if validator == "color_name":
        return _color_name(value)
    if validator == "audio_object_color_name":
        return _audio_object_color_name(value)
    if validator == "audio_level_row":
        return _int_range(value, 0, 24, "value must be an integer from 0 to 24")
    if validator == "audio_output_ref":
        return _channel_ref(value, minimum=0, maximum=128, name="cue output")
    if validator == "device_output_ref":
        return _channel_ref(value, minimum=1, maximum=128, name="device output")
    if validator == "audio_patch_channel_count":
        return _int_range(value, 1, 128, "value must be an integer from 1 to 128")
    if validator == "audio_object_ref":
        return _non_empty_string(value, "value must be a non-empty object name or ID")
    if validator == "timecode_output_type":
        return _int_range(value, 0, 1, "value must be 0 for MTC or 1 for LTC")
    if validator == "timecode_framerate":
        return _int_range(value, 0, 7, "value must be a timecode frame rate index from 0 to 7")
    if validator == "target_mode":
        return _int_range(value, 0, 1, "value must be 0 for cue target or 1 for patch target")
    if validator == "fade_mode":
        return _int_range(value, 0, 1, "value must be 0 or 1")
    if validator == "fade_type":
        return _int_range(value, 1, 2, "value must be 1 for 1D Curve or 2 for 2D Path")
    if validator == "network_fade_type":
        return _int_range(value, 0, 2, "value must be 0, 1, or 2")
    if validator == "fade_number_type":
        return _int_range(value, 0, 1, "value must be 0 for integers or 1 for floats")
    if validator == "network_fps":
        return _int_range(value, 1, 120, "value must be an integer from 1 to 120")
    if validator == "rotation_type":
        return _int_range(value, 0, 3, "value must be an integer from 0 to 3")
    if validator == "devamp_type":
        return _int_range(value, 1, 2, "value must be 1 for current slice or 2 for looping cue")
    if validator == "cue_target_id":
        return _cue_target_id(value)
    if validator == "cue_target_number":
        return _non_empty_string(value, "value must be a non-empty cue target number")
    if validator == "target_id":
        return _non_empty_string(value, "value must be a non-empty target ID")
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
    if validator == "midi_message_type":
        return _int_range(value, 1, 3, "value must be 1 for MIDI voice, 2 for MSC, or 3 for SysEx")
    if validator == "midi_status":
        return _int_range(value, 0, 6, "value must be an integer from 0 to 6")
    if validator == "midi_timecode_format":
        return _int_range(value, 0, 3, "value must be 0 for 24 fps, 1 for 25 fps, 2 for 30 fps drop, or 3 for 30 fps non-drop")
    if validator == "midi_time_part":
        return _int_range(value, 0, 127, "value must be an integer from 0 to 127")
    if validator == "unit_interval":
        number = _number(value, "value must be a number from 0 to 1")
        if number < 0 or number > 1:
            raise UnsafeWriteOperationError("value must be a number from 0 to 1")
        return number
    if validator == "dict_or_json_string":
        if isinstance(value, (dict, list)) or isinstance(value, str):
            return value
        raise UnsafeWriteOperationError("value must be a dict, list, or JSON string")
    if validator == "list_or_json_string":
        if isinstance(value, list) or isinstance(value, str):
            return value
        raise UnsafeWriteOperationError("value must be a list or JSON string")
    if validator == "json_value":
        return _json_value(value)
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
        elif message.startswith("colorName must"):
            message = message.replace("colorName must", f"{name} must", 1)
        raise UnsafeWriteOperationError(message, error_code=exc.error_code) from exc


def _group_mode(value: Any) -> int:
    number = _int(value, "value must be 1, 2, 3, 4, or 6")
    if number not in {1, 2, 3, 4, 6}:
        raise UnsafeWriteOperationError("value must be 1, 2, 3, 4, or 6")
    return number


def _number(value: Any, message: str) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeWriteOperationError(message)
    if isinstance(value, int):
        if not -(2**31) <= value <= 2**31 - 1:
            raise UnsafeWriteOperationError(message, error_code="osc_value_out_of_range")
        return value
    if not math.isfinite(value):
        raise UnsafeWriteOperationError(message, error_code="osc_value_out_of_range")
    try:
        struct.pack(">f", value)
    except (OverflowError, struct.error) as exc:
        raise UnsafeWriteOperationError(message, error_code="osc_value_out_of_range") from exc
    return value


def _quaternion(value: Any) -> list[int | float]:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise UnsafeWriteOperationError("value must be an array of exactly four finite numbers")
    quaternion: list[int | float] = []
    for component in value:
        quaternion.append(_number(component, "value must be an array of exactly four finite numbers"))
    return quaternion


def _decibel(value: Any) -> int | float | str:
    if isinstance(value, bool):
        raise UnsafeWriteOperationError("value must be a number or '-inf'")
    if isinstance(value, (int, float)):
        return _number(value, "value must be a number or '-inf'")
    if isinstance(value, str) and value.strip().casefold() == "-inf":
        return "-inf"
    raise UnsafeWriteOperationError("value must be a number or '-inf'")


def _int(value: Any, message: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UnsafeWriteOperationError(message)
    if not -(2**31) <= value <= 2**31 - 1:
        raise UnsafeWriteOperationError(message, error_code="osc_value_out_of_range")
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


def _blend_mode(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("value must be a QLab video blend mode")
    if value not in QLAB_BLEND_MODES:
        allowed = ", ".join(QLAB_BLEND_MODES.values())
        raise UnsafeWriteOperationError(f"value must be one of: {allowed}")
    return value


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise UnsafeWriteOperationError("value must be JSON-compatible")
        return {key: _json_value(item) for key, item in value.items()}
    raise UnsafeWriteOperationError("value must be JSON-compatible")


def _non_empty_string(value: Any, message: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise UnsafeWriteOperationError(message)
    return value.strip()


def _cue_target_id(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("value must be a cue target ID string")
    normalized = value.strip()
    if normalized == "" or normalized.casefold() == "none":
        return normalized
    return normalized


def _channel_ref(value: Any, *, minimum: int, maximum: int, name: str) -> int | str:
    message = f"value must be an integer from {minimum} to {maximum} or a {name} name"
    if isinstance(value, bool):
        raise UnsafeWriteOperationError(message)
    if isinstance(value, int):
        if minimum <= value <= maximum:
            return value
        raise UnsafeWriteOperationError(message)
    if isinstance(value, str) and value.strip():
        return value.strip()
    raise UnsafeWriteOperationError(message)


def _color_name(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("colorName must be a string")
    normalized = value.strip()
    if normalized.casefold() not in QLAB_COLOR_NAMES:
        allowed = ", ".join(sorted(QLAB_COLOR_NAMES))
        raise UnsafeWriteOperationError(f"colorName must be one of: {allowed}")
    return normalized


def _audio_object_color_name(value: Any) -> str:
    if not isinstance(value, str):
        raise UnsafeWriteOperationError("value must be an audio object color name")
    normalized = value.strip()
    if normalized.casefold() not in AUDIO_OBJECT_COLOR_NAMES:
        allowed = ", ".join(sorted(AUDIO_OBJECT_COLOR_NAMES))
        raise UnsafeWriteOperationError(f"value must be one of: {allowed}")
    return normalized


_CONTINUE_MODE_VALUES = {
    0: 0,
    1: 1,
    2: 2,
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


def _continue_mode_comparison_value(value: Any) -> Any:
    if isinstance(value, str):
        normalized = value.strip().casefold().replace(" ", "_")
        return _CONTINUE_MODE_VALUES.get(normalized, value)
    return _CONTINUE_MODE_VALUES.get(value, value)


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
