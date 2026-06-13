from __future__ import annotations

import time
from types import SimpleNamespace
from typing import Any

import pytest

from qlab_mcp.config import QLabConfig
from qlab_mcp.errors import OscTimeoutError, QLabReplyError, UnsafeWriteOperationError
from qlab_mcp.models import CreateCueResult, UpdateCuesResult, WriteReadinessResult
from qlab_mcp.qlab import QLabReader
from qlab_mcp.runtime.read_cache import shared_read_cache
import qlab_mcp.write.operations as write_operations
from qlab_mcp.write.registry import UPDATE_PROFILE_NAMES, profile_catalog


class FakeWriteClient:
    def __init__(
        self,
        config: QLabConfig,
        created_cue_id: str | None = None,
        existing_cue_id: str | None = None,
        cue_values: dict[str, Any] | None = None,
        connect_data: str = "ok:view|edit",
        connect_status: str = "ok",
        show_mode_data: Any = False,
        show_mode_status: str = "ok",
        fail_set_property: str | None = None,
        timeout_set_property: str | None = None,
        missing_cue: bool = False,
    ):
        self.config = config
        self.created_cue_id = created_cue_id
        self.existing_cue_id = existing_cue_id
        self.cue_values = cue_values or {
            "uniqueID": existing_cue_id or created_cue_id,
            "number": "1",
            "name": "Stale",
            "displayName": "1 Stale",
            "type": "Memo",
            "armed": True,
            "flagged": False,
        }
        self.connect_data = connect_data
        self.connect_status = connect_status
        self.show_mode_data = show_mode_data
        self.show_mode_status = show_mode_status
        self.fail_set_property = fail_set_property
        self.timeout_set_property = timeout_set_property
        self.missing_cue = missing_cue
        self.created = False
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []
        self.reply_timeouts: list[float | None] = []

    def request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        if address == "/workspace/ws-1/connect":
            return SimpleNamespace(data=self.connect_data, status=self.connect_status)
        if address == "/workspace/ws-1/showMode":
            return SimpleNamespace(data=self.show_mode_data, status=self.show_mode_status)
        if address == "/workspace/ws-1/new":
            self.created = True
            self.cue_values["uniqueID"] = self.created_cue_id
            return SimpleNamespace(data={"uniqueID": self.created_cue_id}, status="ok")
        known_ids = {value for value in (self.created_cue_id, self.existing_cue_id) if value}
        if any(address.startswith(f"/workspace/ws-1/cue_id/{cue_id}/") for cue_id in known_ids) or address.startswith(
            "/workspace/ws-1/cue/1/"
        ):
            if self.missing_cue:
                raise QLabReplyError("error", "No cue found", address)
            if address.endswith("/valuesForKeys"):
                if self.created and self.created_cue_id:
                    self.cue_values["name"] = self.cue_values.get("name", "Created")
                return SimpleNamespace(
                    data=dict(self.cue_values),
                    status="ok",
                )
            property_name = self._property_name_from_address(address, known_ids)
            if property_name == self.fail_set_property:
                raise QLabReplyError("error", f"Failed setting {property_name}", address)
            self.cue_values[property_name] = args[0] if args else None
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake write request: {address}")

    @staticmethod
    def _property_name_from_address(address: str, known_ids: set[str]) -> str:
        for cue_id in known_ids:
            prefix = f"/workspace/ws-1/cue_id/{cue_id}/"
            if address.startswith(prefix):
                return address.removeprefix(prefix)
        return address.removeprefix("/workspace/ws-1/cue/1/")


class BatchFakeWriteClient:
    def __init__(
        self,
        config: QLabConfig,
        cues: dict[str, dict[str, Any]],
        cue_numbers: dict[str, str] | None = None,
        fail_set_property: tuple[str, str] | None = None,
        timeout_set_property: tuple[str, str] | None = None,
        timeout_set_properties: set[tuple[str, str]] | None = None,
        timeout_without_apply: bool = False,
        timeout_without_apply_properties: set[tuple[str, str]] | None = None,
        delay_on_timeout: bool = False,
        timeout_apply_after_reads: int | None = None,
        ignore_set_property: tuple[str, str] | None = None,
        missing_refs: set[str] | None = None,
        show_mode_data: Any = False,
    ):
        self.config = config
        self.cues = {cue_id: dict(values, uniqueID=cue_id) for cue_id, values in cues.items()}
        self.cue_numbers = cue_numbers or {}
        self.fail_set_property = fail_set_property
        self.timeout_set_property = timeout_set_property
        self.timeout_set_properties = timeout_set_properties or set()
        self.timeout_without_apply = timeout_without_apply
        self.timeout_without_apply_properties = timeout_without_apply_properties or set()
        self.delay_on_timeout = delay_on_timeout
        self.timeout_apply_after_reads = timeout_apply_after_reads
        self.ignore_set_property = ignore_set_property
        self.pending_timeout_applies: dict[tuple[str, str], Any] = {}
        self.after_read_counts: dict[str, int] = {}
        self.missing_refs = missing_refs or set()
        self.show_mode_data = show_mode_data
        self.requests: list[tuple[str, tuple[Any, ...], str | None]] = []
        self.reply_timeouts: list[float | None] = []

    def request(
        self,
        address: str,
        *args: Any,
        workspace_id: str | None = None,
        reply_timeout: float | None = None,
    ) -> Any:
        if address == "/workspaces" and not self.config.enable_write:
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": "ws-1", "displayName": "demo.qlab5"}], status="ok")
        if address == "/workspace/ws-1/connect":
            return SimpleNamespace(data="ok:view|edit", status="ok")
        if address == "/workspace/ws-1/showMode":
            return SimpleNamespace(data=self.show_mode_data, status="ok")
        cue_id, prop = self._cue_id_and_property(address)
        if cue_id is None or prop is None:
            raise AssertionError(f"Unexpected fake batch request: {address}")
        if cue_id in self.missing_refs:
            raise QLabReplyError("error", "No cue found", address)
        if prop == "valuesForKeys":
            self.after_read_counts[cue_id] = self.after_read_counts.get(cue_id, 0) + 1
            if self.timeout_apply_after_reads is not None:
                for (pending_cue_id, pending_prop), pending_value in list(self.pending_timeout_applies.items()):
                    if pending_cue_id == cue_id and self.after_read_counts[cue_id] >= self.timeout_apply_after_reads:
                        self.cues[pending_cue_id][pending_prop] = pending_value
                        del self.pending_timeout_applies[(pending_cue_id, pending_prop)]
            return SimpleNamespace(data=dict(self.cues[cue_id]), status="ok")
        if self.fail_set_property == (cue_id, prop):
            raise QLabReplyError("error", f"Failed setting {prop}", address)
        if self.timeout_set_property == (cue_id, prop) or (cue_id, prop) in self.timeout_set_properties:
            timeout_without_apply = self.timeout_without_apply or (cue_id, prop) in self.timeout_without_apply_properties
            if self.delay_on_timeout and reply_timeout is not None:
                time.sleep(reply_timeout)
            if not timeout_without_apply:
                if self.timeout_apply_after_reads is None:
                    self.cues[cue_id][prop] = args[0] if args else None
                else:
                    self.pending_timeout_applies[(cue_id, prop)] = args[0] if args else None
            raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
        if self.ignore_set_property == (cue_id, prop):
            return SimpleNamespace(data=None, status="ok")
        self.cues[cue_id][prop] = args[0] if args else None
        return SimpleNamespace(data=None, status="ok")

    def _cue_id_and_property(self, address: str) -> tuple[str | None, str | None]:
        cue_id_prefix = "/workspace/ws-1/cue_id/"
        cue_number_prefix = "/workspace/ws-1/cue/"
        if address.startswith(cue_id_prefix):
            rest = address.removeprefix(cue_id_prefix)
            cue_id, _, prop = rest.partition("/")
            return cue_id, prop
        if address.startswith(cue_number_prefix):
            rest = address.removeprefix(cue_number_prefix)
            number, _, prop = rest.partition("/")
            return self.cue_numbers.get(number), prop
        return None, None


def planned_setters(result_item: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        operation["property"]: operation
        for operation in result_item["planned_operations"]
        if operation["operation"] == "set_property"
    }


PROFILE_TEST_CUE_TYPES = {
    "common": "Memo",
    "memo_basic": "Memo",
    "wait_basic": "Wait",
    "group_basic": "Group",
    "audio_basic": "Audio",
    "mic_basic": "Mic",
    "video_basic": "Video",
    "camera_basic": "Camera",
    "text_basic": "Text",
    "light_basic": "Light",
    "fade_basic": "Fade",
    "network_basic": "Network",
    "midi_basic": "MIDI",
    "midi_file_basic": "MIDI File",
    "timecode_basic": "Timecode",
    "target_basic": "Start",
    "reset_basic": "Reset",
    "devamp_basic": "Devamp",
    "script_basic": "Script",
}


def _base_cue_values(cue_id: str, cue_type: str) -> dict[str, Any]:
    return {
        "uniqueID": cue_id,
        "number": "1",
        "name": "Stale",
        "displayName": "1 Stale",
        "type": cue_type,
        "armed": True,
        "flagged": False,
        "colorName": "none",
    }


def _valid_value_for_validator(validator: str) -> Any:
    return {
        "any": {"value": True},
        "audio_level_row": 1,
        "audio_object_color_name": "blue",
        "audio_object_ref": "object-1",
        "audio_output_ref": 1,
        "audio_patch_channel_count": 2,
        "boolean": True,
        "byte": 64,
        "byte_combo": 1024,
        "color_condition": 1,
        "color_name": "blue",
        "continue_mode": "auto_continue",
        "cue_target_id": "target-id",
        "cue_target_number": "1",
        "decibel": -6,
        "devamp_type": 1,
        "device_output_ref": 1,
        "dict_or_json_string": {"fontSize": 24},
        "fade_mode": 1,
        "fade_number_type": 1,
        "fade_type": 1,
        "group_mode": 1,
        "int": 1,
        "int_or_minus_one": 1,
        "json_value": {"value": 1},
        "list": [1, 2],
        "list_or_json_string": [1, 2],
        "midi_time_part": 1,
        "midi_channel": 1,
        "midi_message_type": 1,
        "midi_status": 1,
        "midi_timecode_format": 1,
        "network_fade_type": 1,
        "network_fps": 24,
        "non_empty_string": "value",
        "non_negative_int": 1,
        "non_negative_number": 1,
        "number": 1,
        "opacity": 0.5,
        "patch_ref": "Patch 1",
        "positive_int": 2,
        "positive_number": 2,
        "rate": 1,
        "rotation_type": 1,
        "second_trigger_action": 1,
        "string": "value",
        "target_id": "target-id",
        "target_mode": 1,
        "text_alignment": "center",
        "text_line_style": "single",
        "timecode_framerate": 1,
        "timecode_part": 1,
        "timecode_output_type": 1,
        "unit_interval": 0.5,
        "video_blend_mode": "normal",
        "video_clock_type": "video",
        "video_fill_style": 1,
        "video_layer": 1,
    }[validator]


def _invalid_value_for_validator(validator: str) -> Any:
    return {
        "any": object(),
        "audio_level_row": 25,
        "audio_object_color_name": "not-a-color",
        "audio_object_ref": "",
        "audio_output_ref": -1,
        "audio_patch_channel_count": 0,
        "boolean": "yes",
        "byte": 128,
        "byte_combo": 16384,
        "color_condition": 3,
        "color_name": "not-a-color",
        "continue_mode": "bad",
        "cue_target_id": 123,
        "cue_target_number": "",
        "decibel": "loud",
        "devamp_type": 3,
        "device_output_ref": 0,
        "dict_or_json_string": 1,
        "fade_mode": 2,
        "fade_number_type": 2,
        "fade_type": 3,
        "group_mode": 0,
        "int": 1.5,
        "int_or_minus_one": 0,
        "json_value": {1: "bad"},
        "list": "not-list",
        "list_or_json_string": 1,
        "midi_time_part": 128,
        "midi_channel": 17,
        "midi_message_type": 4,
        "midi_status": 7,
        "midi_timecode_format": 4,
        "network_fade_type": 3,
        "network_fps": 0,
        "non_empty_string": "",
        "non_negative_int": -1,
        "non_negative_number": -1,
        "number": "not-number",
        "opacity": 2,
        "patch_ref": -1,
        "positive_int": 0,
        "positive_number": 0,
        "rate": 0.01,
        "rotation_type": 4,
        "second_trigger_action": 8,
        "string": 123,
        "target_id": "",
        "target_mode": 2,
        "text_alignment": "middle",
        "text_line_style": "triple",
        "timecode_framerate": 8,
        "timecode_part": 100,
        "timecode_output_type": 2,
        "unit_interval": 2,
        "video_blend_mode": "not-a-blend",
        "video_clock_type": "wall",
        "video_fill_style": 3,
        "video_layer": 1001,
    }[validator]


def _request_for_catalog_property(
    prop_name: str,
    prop: dict[str, Any],
    *,
    invalid_arg: str | None = None,
    invalid_value: Any = None,
) -> dict[str, Any]:
    args = prop["args"]
    if len(args) == 1 and args[0]["name"] == "value":
        value = invalid_value if invalid_arg == "value" else _valid_value_for_validator(args[0]["validator"])
        return {"properties": {prop_name: value}}

    operation_args = {}
    for arg in args:
        operation_args[arg["name"]] = (
            invalid_value
            if invalid_arg == arg["name"]
            else _valid_value_for_validator(arg["validator"])
        )
    return {"operations": [{"property": prop_name, "args": operation_args}]}


def _real_write_property_cases() -> list[Any]:
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            if prop["real_write_enabled"]:
                cases.append(
                    pytest.param(
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        id=f"{profile}:{prop_name}",
                    )
                )
    return cases


def _dry_run_only_property_cases() -> list[Any]:
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            if not prop["real_write_enabled"]:
                cases.append(
                    pytest.param(
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        id=f"{profile}:{prop_name}",
                    )
                )
    return cases


def _validator_negative_cases() -> list[Any]:
    seen = set()
    cases = []
    for profile, spec in profile_catalog().items():
        for prop_name, prop in spec["properties"].items():
            for arg in prop["args"]:
                validator = arg["validator"]
                if validator in seen or validator == "any":
                    continue
                seen.add(validator)
                cases.append(
                    pytest.param(
                        validator,
                        profile,
                        PROFILE_TEST_CUE_TYPES[profile],
                        prop_name,
                        prop,
                        arg["name"],
                        id=f"{validator}:{profile}:{prop_name}.{arg['name']}",
                    )
                )
    return cases


def _assert_update_profile_names_and_shape(catalog: dict[str, Any]) -> None:
    assert set(UPDATE_PROFILE_NAMES) == {
        "common",
        "memo_basic",
        "wait_basic",
        "group_basic",
        "audio_basic",
        "mic_basic",
        "video_basic",
        "camera_basic",
        "text_basic",
        "light_basic",
        "fade_basic",
        "network_basic",
        "midi_basic",
        "midi_file_basic",
        "timecode_basic",
        "target_basic",
        "reset_basic",
        "devamp_basic",
        "script_basic",
    }
    for profile in catalog.values():
        assert "properties" in profile
        assert "risk_tier" in profile
        assert "real_write_enabled" in profile


def _assert_planned_only_props(catalog: dict[str, Any], profile: str, props: tuple[str, ...]) -> None:
    for prop in props:
        assert catalog[profile]["properties"][prop]["real_write_enabled"] is False
        assert catalog[profile]["properties"][prop]["planned_only_reason"]


def _assert_absent_props(catalog: dict[str, Any], profile: str, props: tuple[str, ...]) -> None:
    for prop in props:
        assert prop not in catalog[profile]["properties"]


def _assert_audio_group_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["audio_basic"]["properties"]["level"]["planned_only_reason"]
    assert catalog["audio_basic"]["properties"]["fileTarget"]["planned_only_reason"]
    assert catalog["audio_basic"]["properties"]["level"]["args"] == [
        {"name": "inChannel", "validator": "audio_level_row"},
        {"name": "outChannel", "validator": "audio_output_ref"},
        {"name": "decibel", "validator": "decibel"},
    ]
    assert catalog["audio_basic"]["properties"]["sliderLevel"]["args"] == [
        {"name": "channel", "validator": "audio_output_ref"},
        {"name": "decibel", "validator": "decibel"},
    ]
    _assert_planned_only_props(
        catalog,
        "audio_basic",
        (
            "setDefaultLevels",
            "setSilentLevels",
            "deleteSliceMarker",
            "deleteSliceMarkers",
            "objectIDLevel",
            "audioOutputPatch/level",
            "audioMap/objectID/position",
        ),
    )
    assert catalog["group_basic"]["properties"]["mode"]["args"] == [{"name": "value", "validator": "group_mode"}]
    _assert_planned_only_props(
        catalog,
        "group_basic",
        (
            "playhead",
            "playbackPosition",
            "playbackPositionID",
            "playhead/next",
            "playbackPosition/previousSequence",
            "moveCartCue",
            "playlist/currentCue",
            "playlist/currentCueID",
            "playlistLoop",
            "playlistShuffle",
            "playlistCrossfade",
            "playlistCrossfadeDuration",
        ),
    )
    _assert_absent_props(
        catalog,
        "group_basic",
        ("cartRows", "cartColumns", "cartPosition", "cartPosition/row", "cartPosition/column"),
    )
    _assert_absent_props(
        catalog,
        "group_basic",
        (
            "alwaysCollate",
            "collateAndStart",
            "go",
            "start",
            "stop",
            "hardStop",
            "load",
            "pause",
            "playlist/next",
            "playlist/previous",
        ),
    )


def _assert_media_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["mic_basic"]["real_write_enabled"] is True
    assert catalog["mic_basic"]["properties"]["channels"]["real_write_enabled"] is True
    assert catalog["video_basic"]["real_write_enabled"] is True
    assert catalog["video_basic"]["properties"]["translation/x"]["real_write_enabled"] is True
    assert catalog["video_basic"]["properties"]["crop"]["planned_only_reason"]
    assert catalog["video_basic"]["properties"]["blendMode"]["args"][0]["validator"] == "video_blend_mode"
    assert catalog["video_basic"]["properties"]["clockType"]["args"][0]["validator"] == "video_clock_type"
    _assert_planned_only_props(
        catalog,
        "video_basic",
        (
            "layer",
            "fillStage",
            "fillStyle",
            "holdLastFrame",
            "preserveAspectRatio",
            "smooth",
            "stageName",
            "videoEffects/add",
            "videoEffect/parameter",
            "videoEffect/parameters",
        ),
    )
    assert catalog["camera_basic"]["real_write_enabled"] is True
    assert catalog["camera_basic"]["properties"]["videoEffectIndex/parameter"]["planned_only_reason"]
    assert catalog["text_basic"]["properties"]["text/format/fontFamilyAndStyle"]["planned_only_reason"]
    _assert_planned_only_props(
        catalog,
        "text_basic",
        (
            "text/format/backgroundColor",
            "text/format/shadowOffset",
            "text/format/lineSpacing",
            "text/format/shadowBlurRadius",
            "text/format/underlineStyle",
        ),
    )


def _assert_show_control_profile_catalog(catalog: dict[str, Any]) -> None:
    assert catalog["midi_file_basic"]["properties"]["rate"]["real_write_enabled"] is True
    assert catalog["network_basic"]["properties"]["customString"]["planned_only_reason"]
    assert catalog["network_basic"]["properties"]["parameterValue"]["planned_only_reason"]
    assert catalog["network_basic"]["properties"]["parameterValue"]["path"] == "parameterValue/{parameter}"
    assert catalog["network_basic"]["properties"]["parameterValues"]["args"][0]["validator"] == "list"
    assert catalog["network_basic"]["real_write_enabled"] is True
    _assert_absent_props(catalog, "network_basic", ("message", "messageType", "protocol", "resend", "oscMessage"))
    assert catalog["midi_basic"]["properties"]["note"]["path"] == "byte1"
    assert catalog["midi_basic"]["real_write_enabled"] is True
    assert catalog["midi_basic"]["properties"]["messageType"]["args"][0]["validator"] == "midi_message_type"
    assert catalog["midi_basic"]["properties"]["status"]["args"][0]["validator"] == "midi_status"
    assert catalog["midi_basic"]["properties"]["timecodeFormat"]["args"][0]["validator"] == "midi_timecode_format"
    assert catalog["midi_basic"]["properties"]["doFade"]["planned_only_reason"]
    assert catalog["timecode_basic"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["properties"]["outputType"]["real_write_enabled"] is True
    assert catalog["timecode_basic"]["properties"]["timecodeFrameRate"]["path"] == "framerate"
    assert catalog["timecode_basic"]["properties"]["timecodeFrameRate"]["args"][0]["validator"] == "timecode_framerate"
    assert catalog["timecode_basic"]["properties"]["ltcChannel"]["planned_only_reason"]
    assert catalog["timecode_basic"]["properties"]["timecodeString"]["planned_only_reason"]
    assert catalog["timecode_basic"]["properties"]["timecodeFormat"]["planned_only_reason"]
    _assert_planned_only_props(
        catalog,
        "target_basic",
        ("cueTargetID", "cueTargetNumber", "cueTargetName", "tempCueTargetID", "tempCueTargetNumber", "targetMode"),
    )
    assert catalog["target_basic"]["properties"]["cueTargetID"]["args"][0]["validator"] == "cue_target_id"
    assert catalog["target_basic"]["properties"]["cueTargetNumber"]["args"][0]["validator"] == "cue_target_number"
    assert catalog["target_basic"]["properties"]["targetMode"]["args"][0]["validator"] == "target_mode"
    _assert_planned_only_props(
        catalog,
        "reset_basic",
        ("cueTargetID", "cueTargetNumber", "patchTargetID", "audioMapTargetID", "targetMode"),
    )
    assert catalog["reset_basic"]["properties"]["patchTargetID"]["args"][0]["validator"] == "target_id"
    _assert_planned_only_props(
        catalog,
        "devamp_basic",
        (
            "cueTargetID",
            "cueTargetNumber",
            "cueTargetName",
            "tempCueTargetID",
            "tempCueTargetNumber",
            "targetMode",
            "devampType",
            "startNextCueWhenSliceEnds",
            "stopTargetWhenSliceEnds",
        ),
    )
    assert catalog["devamp_basic"]["properties"]["devampType"]["args"][0]["validator"] == "devamp_type"


def _assert_light_profile_catalog(catalog: dict[str, Any]) -> None:
    light_properties = catalog["light_basic"]["properties"]
    light_specific = set(light_properties) - set(catalog["common"]["properties"])
    assert light_specific == {
        "alwaysCollate",
        "collateAndStart",
        "lightCommandText",
        "prune",
        "pruneCommands",
        "removeLightCommandsMatching",
        "replaceLightCommand",
        "safeSort",
        "safeSortCommands",
        "setLight",
        "subcontroller",
    }
    for prop in light_specific:
        assert light_properties[prop]["real_write_enabled"] is False
        assert light_properties[prop]["planned_only_reason"]
        assert light_properties[prop]["risk_tier"] == "high"
    assert light_properties["lightCommandText"]["args"][0]["validator"] == "string"
    assert light_properties["alwaysCollate"]["args"][0]["validator"] == "boolean"
    assert light_properties["subcontroller"]["args"][0]["validator"] == "boolean"
    assert light_properties["setLight"]["path"] == "setLight"
    assert light_properties["setLight"]["args"] == [
        {"name": "instrument_or_group", "validator": "non_empty_string"},
        {"name": "setting", "validator": "json_value"},
    ]
    assert light_properties["replaceLightCommand"]["args"] == [
        {"name": "oldCommand", "validator": "non_empty_string"},
        {"name": "newCommand", "validator": "non_empty_string"},
    ]
    assert light_properties["removeLightCommandsMatching"]["args"] == [
        {"name": "match", "validator": "non_empty_string"}
    ]
    for forbidden_light_prop in (
        "parameterValues",
        "parameterFadesEnabled",
        "removeLightCommand",
        "dashboard/setLight",
        "dashboard/updateLatestCue",
        "dashboard/updateSelectedCues",
        "lightPatch",
    ):
        assert forbidden_light_prop not in light_properties


def _assert_fade_script_profile_catalog(catalog: dict[str, Any]) -> None:
    _assert_planned_only_props(
        catalog,
        "fade_basic",
        (
            "stopTargetWhenDone",
            "audioMapTargetID",
            "patchTargetID",
            "targetMode",
            "levelsMode",
            "geoMode",
            "mode",
            "fadeType",
            "pathHeight",
            "pathWidth",
            "rotation",
            "rotationType",
            "doOpacity",
            "doRate",
            "doRotation",
            "doScale",
            "doTranslation",
            "doLevel",
            "doObjectLevel",
            "doObjectIDLevel",
            "setGeometryFromTarget",
            "setLevelsFromTarget",
            "willFade",
        ),
    )
    assert catalog["fade_basic"]["properties"]["targetMode"]["args"][0]["validator"] == "target_mode"
    assert catalog["fade_basic"]["properties"]["levelsMode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["geoMode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["mode"]["path"] == "geoMode"
    assert catalog["fade_basic"]["properties"]["mode"]["args"][0]["validator"] == "fade_mode"
    assert catalog["fade_basic"]["properties"]["fadeType"]["args"][0]["validator"] == "fade_type"
    assert catalog["fade_basic"]["properties"]["rotationType"]["args"][0]["validator"] == "rotation_type"
    assert catalog["fade_basic"]["properties"]["pathHeight"]["args"][0]["validator"] == "positive_number"
    assert catalog["fade_basic"]["properties"]["pathWidth"]["args"][0]["validator"] == "positive_number"
    assert catalog["fade_basic"]["properties"]["doLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "column", "validator": "audio_output_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["doObjectLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "object", "validator": "audio_object_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["doObjectIDLevel"]["args"] == [
        {"name": "row", "validator": "audio_level_row"},
        {"name": "objectID", "validator": "audio_object_ref"},
        {"name": "value", "validator": "boolean"},
    ]
    assert catalog["fade_basic"]["properties"]["willFade"]["planned_only_reason"] == "deprecated_use_doLevel"
    _assert_absent_props(catalog, "fade_basic", ("fadeEntries", "fadeFrom", "fadeTo", "fps"))
    assert catalog["script_basic"]["real_write_enabled"] is True
    assert catalog["script_basic"]["properties"]["scriptSource"]["planned_only_reason"] == "not_editable_by_osc"


def test_update_registry_covers_all_profiles_and_planned_only_risk() -> None:
    catalog = profile_catalog()

    _assert_update_profile_names_and_shape(catalog)
    _assert_audio_group_profile_catalog(catalog)
    _assert_media_profile_catalog(catalog)
    _assert_show_control_profile_catalog(catalog)
    _assert_light_profile_catalog(catalog)
    _assert_fade_script_profile_catalog(catalog)


@pytest.mark.parametrize("profile", UPDATE_PROFILE_NAMES)
def test_update_cues_dry_run_contract_covers_every_profile(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_type = PROFILE_TEST_CUE_TYPES[profile]
    prop_name, prop = next(iter(profile_catalog()[profile]["properties"].items()))
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True, (profile, result)
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(("profile", "cue_type", "prop_name", "prop"), _real_write_property_cases())
def test_update_cue_real_write_contract_covers_every_real_write_property(
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    result = reader.update_cue(
        "ws-1",
        cue_id,
        update.get("properties"),
        dry_run=False,
        profile=profile,
        operations=update.get("operations"),
    )

    assert result["ok"] is True, (profile, prop_name, result)
    assert result["status"] == "updated", (profile, prop_name, result)
    assert result["executed_operations"], (profile, prop_name, result)
    assert result["errors"] is None, (profile, prop_name, result)
    for key, value in result["properties"].items():
        assert result["after"][key] == value, (profile, prop_name, key, result)


@pytest.mark.parametrize(("profile", "cue_type", "prop_name", "prop"), _dry_run_only_property_cases())
def test_update_cue_dry_run_only_contract_plans_then_blocks_real_write_before_osc(
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    dry_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    dry_reader = QLabReader(dry_client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(prop_name, prop)

    dry_result = dry_reader.update_cue(
        "ws-1",
        cue_id,
        update.get("properties"),
        dry_run=True,
        profile=profile,
        operations=update.get("operations"),
    )

    assert dry_result["executed_operations"] == []
    if dry_result["ok"]:
        setters = planned_setters(dry_result)
        assert prop_name in setters, (profile, prop_name, dry_result)
        assert setters[prop_name]["real_write_enabled"] is False
        assert setters[prop_name]["planned_only_reason"]
    else:
        assert dry_result["status"] == "dry_run_preflight_failed", (profile, prop_name, dry_result)
        assert dry_result["planned_operations"] == []
        assert "read_before" in dry_result["errors"], (profile, prop_name, dry_result)

    real_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    real_reader = QLabReader(real_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        real_reader.update_cue(
            "ws-1",
            cue_id,
            update.get("properties"),
            dry_run=False,
            profile=profile,
            operations=update.get("operations"),
        )
    assert real_client.requests == []


@pytest.mark.parametrize(
    ("validator", "profile", "cue_type", "prop_name", "prop", "arg_name"),
    _validator_negative_cases(),
)
def test_update_cues_validator_contract_rejects_one_bad_value_without_plan_or_osc(
    validator: str,
    profile: str,
    cue_type: str,
    prop_name: str,
    prop: dict[str, Any],
    arg_name: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, cue_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = _request_for_catalog_property(
        prop_name,
        prop,
        invalid_arg=arg_name,
        invalid_value=_invalid_value_for_validator(validator),
    )

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False, (validator, profile, prop_name, result)
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert not any("/cue/" in address or "/cue_id/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize("profile", [name for name in UPDATE_PROFILE_NAMES if name != "common"])
def test_update_cues_profile_mismatch_contract_has_no_plan_or_setters(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    expected_type = PROFILE_TEST_CUE_TYPES[profile]
    mismatched_type = "Wait" if expected_type == "Memo" else "Memo"
    prop_name, prop = next(iter(profile_catalog()[profile]["properties"].items()))
    update = _request_for_catalog_property(prop_name, prop)
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=_base_cue_values(cue_id, mismatched_type),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": profile,
                **update,
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False, (profile, result)
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert "profile" in result["results"][0]["errors"]


def test_write_config_defaults_to_disabled_and_dry_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QLAB_ENABLE_WRITE", raising=False)
    monkeypatch.delenv("QLAB_WRITE_DRY_RUN_DEFAULT", raising=False)
    monkeypatch.delenv("QLAB_UPDATE_DEBUG", raising=False)

    config = QLabConfig.from_env()

    assert config.enable_write is False
    assert config.write_dry_run_default is True
    assert config.update_debug is False


def test_write_config_reads_update_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QLAB_UPDATE_DEBUG", "true")

    config = QLabConfig.from_env()

    assert config.update_debug is True


def test_check_write_readiness_reports_disabled_without_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "write_disabled"
    assert result["blockers"] == ["write_disabled"]
    assert result["error_code"] == "QLAB_WRITE_WRITE_DISABLED"
    assert result["suggested_action"] == "Set QLAB_ENABLE_WRITE=true only for a deliberate write session."
    assert result["passcode_configured"] is True
    assert result["capabilities"]["create_cue"]["dry_run_default"] is True
    assert result["capabilities"]["batch_update_cues"]["tool"] == "qlab_update_cues"
    assert result["capabilities"]["batch_update_cues"]["batch"] == {
        "min_items": 1,
        "max_items": 50,
        "requires_concrete_cue_refs": True,
        "ambiguous_refs_allowed": False,
        "preflight_before_any_setter": True,
        "setter_target": "cue_id",
    }
    assert result["capabilities"]["edit_existing_cue"]["legacy_alias_for"] == "batch_update_cues"
    assert client.requests == []


def test_check_write_readiness_requires_passcode_without_leaking_secret() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "passcode_missing"
    assert result["blockers"] == ["passcode_missing"]
    assert result["error_code"] == "QLAB_WRITE_PASSCODE_MISSING"
    assert "QLAB_PASSCODE" in result["suggested_action"]
    assert "passcode" in result["checks"]
    assert "secret" not in str(result)
    assert client.requests == []


def test_check_write_readiness_requires_edit_confirmed_by_connect() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert result["error_code"] is None
    assert result["suggested_action"] is None
    assert result["checks"]["workspace_resolution"]["ok"] is True
    assert result["checks"]["edit_permission"]["status"] == "confirmed"
    assert result["checks"]["connect"]["scopes"] == ["view", "edit"]
    assert result["checks"]["show_mode"]["mode"] == "edit"
    assert client.requests == [
        ("/workspaces", (), None),
        ("/workspace/ws-1/connect", ("server-pass",), None),
        ("/workspace/ws-1/showMode", (), "ws-1"),
    ]


@pytest.mark.parametrize("connect_data", ["ok:view", "ok:view|control", "ok:admin"])
def test_check_write_readiness_blocks_without_edit_scope(connect_data: str) -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data=connect_data)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "edit_not_confirmed"
    assert result["blockers"] == ["edit_not_confirmed"]
    assert result["error_code"] == "QLAB_WRITE_EDIT_NOT_CONFIRMED"
    assert result["checks"]["edit_permission"]["ok"] is False


def test_check_write_readiness_blocks_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "workspace_in_show_mode"
    assert result["blockers"] == ["workspace_in_show_mode"]
    assert result["suggested_action"] == "Switch the QLab workspace to Edit Mode before real writes."
    assert result["checks"]["show_mode"]["mode"] == "show"


def test_check_write_readiness_blocks_unknown_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data="nope")
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("ws-1")

    assert result["ok"] is False
    assert result["status"] == "show_mode_unknown"
    assert result["blockers"] == ["show_mode_unknown"]
    assert result["checks"]["show_mode"]["status"] == "unexpected_data"


def test_check_write_readiness_invalid_workspace_fails_before_edit_checks() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.check_write_readiness("missing-ws")

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["checks"]["workspace_resolution"]["ok"] is False
    assert result["checks"]["connect"] is None
    assert result["checks"]["show_mode"] is None
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_write_readiness_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = WriteReadinessResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "write_enabled": True,
                "dry_run_default": True,
                "passcode_configured": True,
                "capabilities": {},
                "checks": {},
                "blockers": [status],
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert "passcode" not in str(result.model_dump().get("errors", ""))


def test_create_cue_disabled_blocks_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Write mode is disabled"):
        reader.create_cue("ws-1", "audio", properties={"name": "Intro"}, dry_run=False)

    assert client.requests == []


def test_create_cue_dry_run_sends_no_mutating_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue(
        "ws-1",
        "audio",
        properties={"name": "Intro", "continueMode": "auto_follow"},
        dry_run=True,
        after_cue_id="cue-before",
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["cue_type"] == "Audio"
    assert result["properties"]["continueMode"] == 2
    assert result["placement"]["after_cue_id"] == "cue-before"
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "new",
        "move_after",
        "set_property",
        "set_property",
        "verify",
    ]
    assert client.requests == []


def test_create_cue_dry_run_invalid_workspace_has_no_plan() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.create_cue(
        "missing-ws",
        "memo",
        properties={"name": "Nope"},
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert "workspace_resolution" in result["errors"]
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_create_cue_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = CreateCueResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "cue_type": "Memo",
                "dry_run": True,
                "properties": {},
                "planned_operations": [],
                "executed_operations": [],
                "errors": {"workspace_resolution": "Workspace not found: INVALID"},
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert result.planned_operations == []
        assert result.executed_operations == []


def test_create_cue_rejects_unallowlisted_cue_type_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "script", dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
        reader.create_cue("ws-1", "video", dry_run=True)

    assert client.requests == []


def test_create_cue_rejects_unallowlisted_properties_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
        reader.create_cue("ws-1", "audio", properties={"fileTarget": "/tmp/secret.wav"}, dry_run=True)

    assert client.requests == []


def test_create_cue_rejects_invalid_property_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="duration must be a non-negative number"):
        reader.create_cue("ws-1", "audio", properties={"duration": -1}, dry_run=True)

    assert client.requests == []


def test_create_cue_real_with_after_cue_id_fails_safely_without_passcode_leak() -> None:
    secret = "server-super-secret"
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode=secret))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError) as exc_info:
        reader.create_cue("ws-1", "audio", dry_run=False, after_cue_id="cue-before")

    message = str(exc_info.value)
    assert "after_cue_id" in message
    assert secret not in message
    assert client.requests == []


def test_create_cue_real_blocks_without_confirmed_edit() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), connect_data="ok:view|control")
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="edit permission"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == ["/workspaces", "/workspace/ws-1/connect"]


def test_create_cue_real_blocks_in_show_mode() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), show_mode_data=True)
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.create_cue("ws-1", "memo", dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]
    assert client.requests[-1][2] == "ws-1"


def test_create_cue_real_creates_applies_properties_and_verifies_fresh_details() -> None:
    shared_read_cache().clear()
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        created_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    stale = reader.get_cue_details("ws-1", cue_id, "auto")
    assert stale["properties"]["name"] == "Stale"

    result = reader.create_cue(
        "ws-1",
        "memo",
        properties={"name": "Created", "number": "1", "armed": True, "continueMode": 1},
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "created"
    assert result["cue_type"] == "Memo"
    assert result["created_cue_id"] == cue_id
    assert result["verification"]["properties"]["name"] == "Created"
    assert "/workspace/ws-1/connect" in addresses
    assert "/workspace/ws-1/showMode" in addresses
    assert next(request[2] for request in client.requests if request[0] == "/workspace/ws-1/showMode") == "ws-1"
    assert "/workspace/ws-1/new" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/number" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/continueMode" in addresses
    assert addresses.count(f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys") >= 2


def test_update_cue_dry_run_sends_no_mutating_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=True)

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["dry_run"] is True
    assert result["before"]["name"] == "Stale"
    assert result["diff"]["name"] == {"before": "Stale", "requested": "New"}
    assert [operation["operation"] for operation in result["planned_operations"]] == [
        "read_before",
        "set_property",
        "set_property",
        "verify",
    ]
    assert [request[0] for request in client.requests] == [f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys"]


def test_update_cues_batch_dry_run_allows_mixed_profiles() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    text_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old", "flagged": False},
            audio_id: {"type": "Audio", "name": "Audio old", "rate": 1.0},
            text_id: {"type": "Text", "text": "Old", "text/format/fontSize": 24},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "profile": "common", "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
            {"cue_ref": text_id, "profile": "text_basic", "properties": {"text/format/fontSize": 32}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["requested_count"] == 3
    assert result["planned_count"] == 3
    assert result["updated_count"] == 0
    assert [item["profile"] for item in result["results"]] == ["common", "audio_basic", "text_basic"]
    assert all(item["executed_operations"] == [] for item in result["results"])
    assert all(request[0].endswith("/valuesForKeys") for request in client.requests)


def test_update_cues_single_item_real_uses_unique_id_and_one_readiness_check() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "flagged": False}},
        cue_numbers={"1": cue_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": "1", "properties": {"name": "New"}}], dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["updated_count"] == 1
    assert addresses.count("/workspaces") == 1
    assert addresses.count("/workspace/ws-1/connect") == 1
    assert addresses.count("/workspace/ws-1/showMode") == 1
    assert "/workspace/ws-1/cue/1/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert "/workspace/ws-1/cue/1/name" not in addresses


def test_update_cues_rejects_empty_and_over_limit() -> None:
    client = BatchFakeWriteClient(QLabConfig(enable_write=False), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="updates must be a list"):
        reader.update_cues("ws-1", "not-a-list", dry_run=True)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="at least one"):
        reader.update_cues("ws-1", [], dry_run=True)

    with pytest.raises(UnsafeWriteOperationError, match="at most 50"):
        reader.update_cues(
            "ws-1",
            [{"cue_ref": str(index), "properties": {"name": "x"}} for index in range(51)],
            dry_run=True,
        )

    assert client.requests == []


def test_update_cues_dry_run_reports_invalid_property_value_per_item() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    group_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            group_id: {"type": "Group", "preWait": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo old"}},
            {"cue_ref": group_id, "properties": {"preWait": -1}},
        ],
        dry_run=True,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["dry_run"] is True
    assert result["requested_count"] == 2
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "preWait must be a non-negative number"
    assert result["results"][1]["planned_operations"] == []
    assert f"/workspace/ws-1/cue_id/{memo_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/preWait" not in addresses


def test_update_cues_dry_run_rejects_unknown_color_name_without_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "colorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"colorName": "banana"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "colorName must be one of" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []


def test_update_cues_dry_run_accepts_known_color_name() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "colorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"colorName": "blue"}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert result["results"][0]["properties"]["colorName"] == "blue"
    assert result["results"][0]["planned_operations"]


def test_update_cues_dry_run_invalid_workspace_has_no_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "notes": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "missing-ws",
        [{"cue_ref": cue_id, "properties": {"notes": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "workspace_not_found"
    assert result["planned_count"] == 0
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert "workspace_resolution" in result["errors"]
    assert [request[0] for request in client.requests] == ["/workspaces"]


def test_workspace_resolution_statuses_validate_for_update_cues_model() -> None:
    for status in ("workspace_not_found", "workspace_ambiguous", "workspace_unavailable"):
        result = UpdateCuesResult.model_validate(
            {
                "ok": False,
                "status": status,
                "workspace_id": "INVALID",
                "dry_run": True,
                "requested_count": 1,
                "planned_count": 0,
                "updated_count": 0,
                "failed_count": 1,
                "timeout_confirmed_count": 0,
                "results": [],
                "errors": {"workspace_resolution": "Workspace not found: INVALID"},
                "warnings": [],
                "error_code": status,
                "suggested_action": "Call qlab_check_connection and pass one of available_workspaces[].uniqueID.",
                "message": "Workspace could not be resolved.",
            }
        )

        assert result.status == status
        assert result.planned_count == 0
        assert result.results == []


def test_update_cues_dry_run_reports_video_opacity_validation_per_item() -> None:
    video_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={video_id: {"type": "Video", "opacity": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 0.8}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 80}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["requested_count"] == 2
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][0]["properties"]["opacity"] == 0.8
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "opacity must be a number from 0 to 1"


def test_update_cues_dry_run_reports_video_text_extended_validation_per_item() -> None:
    video_id = "11111111-1111-4111-8111-111111111111"
    text_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            video_id: {"type": "Video", "blendMode": "Normal", "clockType": "video"},
            text_id: {"type": "Text", "text/format/shadowBlurRadius": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"blendMode": "not a blend mode"}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"clockType": "wall"}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"layer": 1001}},
            {"cue_ref": video_id, "profile": "video_basic", "properties": {"fillStyle": 4}},
            {"cue_ref": text_id, "profile": "text_basic", "properties": {"text/format/shadowBlurRadius": -1}},
            {
                "cue_ref": video_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "videoEffect/parameter", "args": {"name": "ColorControls", "parameterKey": "inputBrightness"}}
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 6
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert "blendMode must be one of:" in result["results"][0]["errors"]["validation"]
    assert result["results"][1]["errors"]["validation"] == "clockType must be audio or video"
    assert result["results"][2]["errors"]["validation"] == "layer must be an integer from 0 to 1000"
    assert result["results"][3]["errors"]["validation"] == "fillStyle must be 0 for fit, 1 for fill, or 2 for stretch"
    assert result["results"][4]["errors"]["validation"] == "text/format/shadowBlurRadius must be a non-negative number"
    assert "videoEffect/parameter args missing required key: setting" in result["results"][5]["errors"]["validation"]


def test_update_cues_dry_run_reports_text_rgba_validation_per_item() -> None:
    valid_text_id = "11111111-1111-4111-8111-111111111111"
    invalid_text_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            valid_text_id: {"type": "Text"},
            invalid_text_id: {"type": "Text"},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": valid_text_id,
                "profile": "text_basic",
                "operations": [
                    {"property": "text/format/color", "args": {"red": 1, "green": 0.5, "blue": 0, "alpha": 1}}
                ],
            },
            {
                "cue_ref": invalid_text_id,
                "profile": "text_basic",
                "operations": [
                    {"property": "text/format/color", "args": {"red": 255, "green": 0, "blue": 0, "alpha": 1}}
                ],
            }
        ],
        dry_run=True,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "text/format/color.red must be a number from 0 to 1"
    assert "read_before" not in result["results"][1]["errors"]
    assert result["results"][1]["planned_operations"] == []
    assert f"/workspace/ws-1/cue_id/{valid_text_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{invalid_text_id}/valuesForKeys" not in addresses


def test_update_cues_dry_run_unresolved_ref_has_no_planned_operations() -> None:
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": missing_id, "properties": {"notes": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["updated_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "read_before" in result["results"][0]["errors"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_dry_run_mixed_unresolved_ref_keeps_valid_plan_only() -> None:
    valid_id = "11111111-1111-4111-8111-111111111111"
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={valid_id: {"type": "Memo", "notes": "Old"}},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": valid_id, "properties": {"notes": "Ok"}},
            {"cue_ref": missing_id, "properties": {"notes": "Nope"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 1
    assert result["updated_count"] == 0
    assert result["results"][0]["status"] == "dry_run"
    assert result["results"][0]["planned_operations"]
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "read_before" in result["results"][1]["errors"]
    assert result["results"][1]["planned_operations"] == []
    assert result["results"][1]["executed_operations"] == []


def test_update_cues_dry_run_reports_invalid_continue_mode_per_item() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "continueMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"continueMode": "bad_mode"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["validation"] == (
        "continueMode must be 0, 1, 2, do_not_continue, auto_continue, or auto_follow"
    )


def test_update_cues_transport_target_profiles_dry_run_plan_documented_targets() -> None:
    start_id = "11111111-1111-4111-8111-111111111111"
    reset_id = "22222222-2222-4222-8222-222222222222"
    devamp_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            start_id: {"type": "Start", "cueTargetID": "", "cueTargetNumber": "", "targetMode": 0},
            reset_id: {"type": "Reset", "patchTargetID": "old-patch", "audioMapTargetID": "old-map", "targetMode": 0},
            devamp_id: {
                "type": "Devamp",
                "cueTargetID": "",
                "cueTargetNumber": "",
                "targetMode": 0,
                "devampType": 1,
                "startNextCueWhenSliceEnds": False,
                "stopTargetWhenSliceEnds": True,
            },
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": start_id,
                "profile": "target_basic",
                "properties": {
                    "cueTargetID": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    "cueTargetNumber": "LX1",
                    "tempCueTargetID": "none",
                    "tempCueTargetNumber": "LX2",
                    "targetMode": 0,
                },
            },
            {
                "cue_ref": reset_id,
                "profile": "reset_basic",
                "properties": {
                    "cueTargetID": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    "cueTargetNumber": "RST1",
                    "patchTargetID": "patch-1",
                    "audioMapTargetID": "map-1",
                    "targetMode": 1,
                },
            },
            {
                "cue_ref": devamp_id,
                "profile": "devamp_basic",
                "properties": {
                    "cueTargetID": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                    "cueTargetNumber": "DV1",
                    "tempCueTargetID": "",
                    "tempCueTargetNumber": "DV2",
                    "targetMode": 0,
                    "devampType": 2,
                    "startNextCueWhenSliceEnds": True,
                    "stopTargetWhenSliceEnds": False,
                },
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 3
    assert [item["profile"] for item in result["results"]] == ["target_basic", "reset_basic", "devamp_basic"]
    assert all(item["executed_operations"] == [] for item in result["results"])

    planned_by_item = [
        {
            operation["property"]: operation
            for operation in item["planned_operations"]
            if operation["operation"] == "set_property"
        }
        for item in result["results"]
    ]
    assert set(planned_by_item[0]) == {
        "cueTargetID",
        "cueTargetNumber",
        "tempCueTargetID",
        "tempCueTargetNumber",
        "targetMode",
    }
    assert set(planned_by_item[1]) == {"cueTargetID", "cueTargetNumber", "patchTargetID", "audioMapTargetID", "targetMode"}
    assert set(planned_by_item[2]) == {
        "cueTargetID",
        "cueTargetNumber",
        "tempCueTargetID",
        "tempCueTargetNumber",
        "targetMode",
        "devampType",
        "startNextCueWhenSliceEnds",
        "stopTargetWhenSliceEnds",
    }
    assert all(operation["real_write_enabled"] is False for item in planned_by_item for operation in item.values())
    assert planned_by_item[0]["tempCueTargetID"]["args"] == ["none"]
    assert planned_by_item[2]["tempCueTargetID"]["args"] == [""]


def test_update_cues_transport_target_validators_fail_without_plan() -> None:
    start_id = "11111111-1111-4111-8111-111111111111"
    devamp_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            start_id: {"type": "Start", "targetMode": 0},
            devamp_id: {"type": "Devamp", "devampType": 1, "startNextCueWhenSliceEnds": False},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": start_id, "profile": "target_basic", "properties": {"targetMode": 2}},
            {"cue_ref": start_id, "profile": "target_basic", "properties": {"cueTargetNumber": ""}},
            {"cue_ref": devamp_id, "profile": "devamp_basic", "properties": {"devampType": 3}},
            {"cue_ref": devamp_id, "profile": "devamp_basic", "properties": {"startNextCueWhenSliceEnds": "banana"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 4
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert result["results"][0]["errors"]["validation"] == "targetMode must be 0 for cue target or 1 for patch target"
    assert result["results"][1]["errors"]["validation"] == "cueTargetNumber must be a non-empty cue target number"
    assert result["results"][2]["errors"]["validation"] == "devampType must be 1 for current slice or 2 for looping cue"
    assert result["results"][3]["errors"]["validation"] == "startNextCueWhenSliceEnds must be a boolean"
    assert client.requests == []


def test_update_cues_target_profile_type_mismatch_fails_cleanly_without_plan() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={memo_id: {"type": "Memo", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": memo_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "target_basic update profile requires cue type" in result["results"][0]["errors"]["profile"]
    assert result["results"][0]["planned_operations"] == []


def test_update_cues_group_basic_dry_run_plans_documented_group_list_cart_paths() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    list_id = "22222222-2222-4222-8222-222222222222"
    cart_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            group_id: {"type": "Group", "mode": 3, "playlist/doLoop": False},
            list_id: {"type": "Cue List", "playbackPosition": "1", "playbackPositionID": "child-old"},
            cart_id: {"type": "Cue Cart", "mode": 5},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": group_id,
                "profile": "group_basic",
                "properties": {
                    "mode": 6,
                    "playlist/doLoop": True,
                    "playlist/doShuffle": True,
                    "playlist/doCrossfade": True,
                    "playlist/crossfade/duration": 2.5,
                    "playlist/currentCue": "A1",
                    "playlist/currentCueID": "child-new",
                    "playlistLoop": False,
                    "playlistShuffle": False,
                    "playlistCrossfade": False,
                    "playlistCrossfadeDuration": 1.25,
                },
            },
            {
                "cue_ref": list_id,
                "profile": "group_basic",
                "properties": {
                    "playhead": "next",
                    "playheadID": "none",
                    "playbackPosition": "previous",
                    "playbackPositionID": "child-id",
                },
                "operations": [{"property": "playhead/next"}, {"property": "playbackPosition/previousSequence"}],
            },
            {
                "cue_ref": cart_id,
                "profile": "group_basic",
                "operations": [{"property": "moveCartCue", "args": {"child": "child-id", "row": 2, "column": 3}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    planned_by_item = [
        {
            operation["property"]: operation
            for operation in item["planned_operations"]
            if operation["operation"] == "set_property"
        }
        for item in result["results"]
    ]
    assert planned_by_item[0]["mode"]["address"] == f"/workspace/ws-1/cue_id/{group_id}/mode"
    assert planned_by_item[0]["mode"]["args"] == [6]
    assert planned_by_item[0]["playlist/currentCueID"]["address"] == f"/workspace/ws-1/cue_id/{group_id}/playlist/currentCueID"
    assert planned_by_item[0]["playlist/currentCueID"]["planned_only_reason"] == "playlist_navigation_needs_dedicated_validation"
    assert planned_by_item[0]["playlistLoop"]["address"] == f"/workspace/ws-1/cue_id/{group_id}/playlistLoop"
    assert planned_by_item[0]["playlistLoop"]["planned_only_reason"] == "deprecated_use_playlist_doLoop"
    assert planned_by_item[1]["playhead"]["address"] == f"/workspace/ws-1/cue_id/{list_id}/playhead"
    assert planned_by_item[1]["playhead/next"]["address"] == f"/workspace/ws-1/cue_id/{list_id}/playhead/next"
    assert planned_by_item[1]["playbackPosition/previousSequence"]["address"] == (
        f"/workspace/ws-1/cue_id/{list_id}/playbackPosition/previousSequence"
    )
    assert planned_by_item[2]["moveCartCue"]["address"] == f"/workspace/ws-1/cue_id/{cart_id}/moveCartCue/child-id"
    assert planned_by_item[2]["moveCartCue"]["args"] == [2, 3]
    for item in result["results"]:
        assert item["executed_operations"] == []


def test_update_cues_group_basic_invalid_values_have_no_plan() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    list_id = "22222222-2222-4222-8222-222222222222"
    cart_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            group_id: {"type": "Group", "mode": 3},
            list_id: {"type": "Cue List", "playbackPosition": "1"},
            cart_id: {"type": "Cue Cart", "mode": 5},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"mode": 0}},
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/doLoop": "yes"}},
            {"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": -0.1}},
            {"cue_ref": list_id, "profile": "group_basic", "properties": {"playhead": ""}},
            {
                "cue_ref": cart_id,
                "profile": "group_basic",
                "operations": [{"property": "moveCartCue", "args": {"child": "child", "row": -1, "column": 0}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["failed_count"] == 5
    assert result["results"][0]["errors"]["validation"] == "mode must be 1, 2, 3, 4, or 6"
    assert result["results"][1]["errors"]["validation"] == "playlist/doLoop must be a boolean"
    assert result["results"][2]["errors"]["validation"] == "playlist/crossfade/duration must be a non-negative number"
    assert result["results"][3]["errors"]["validation"] == "playhead must be a non-empty string"
    assert result["results"][4]["errors"]["validation"] == "moveCartCue.row must be a non-negative integer"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_group_basic_real_blocks_planned_only_before_setters() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={group_id: {"type": "Group", "playbackPosition": "1"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        reader.update_cues(
            "ws-1",
            [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playbackPosition": "next"}}],
            dry_run=False,
        )

    assert client.requests == []


def test_update_cues_group_basic_profile_mismatch_fails_cleanly() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo", "mode": 3}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "group_basic", "properties": {"mode": 3}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["errors"]["profile"] == "group_basic update profile requires cue type: Group, Cue List, Cue Cart"


def test_update_cues_fade_basic_dry_run_plans_documented_fade_fields() -> None:
    fade_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            fade_id: {
                "type": "Fade",
                "targetMode": 0,
                "levelsMode": 0,
                "geoMode": 0,
                "fadeType": 1,
                "pathHeight": 1,
                "pathWidth": 1,
                "rotationType": 0,
                "stopTargetWhenDone": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "properties": {
                    "targetMode": 1,
                    "levelsMode": 1,
                    "mode": 0,
                    "fadeType": 2,
                    "stopTargetWhenDone": True,
                    "pathHeight": 1.5,
                    "pathWidth": 2.5,
                    "rotation": 15,
                    "rotationType": 3,
                    "doOpacity": True,
                    "doRate": True,
                    "doRotation": True,
                    "doScale": True,
                    "doTranslation": True,
                    "audioMapTargetID": "map-1",
                    "patchTargetID": "patch-1",
                },
                "operations": [
                    {"property": "doLevel", "args": {"row": 1, "column": 1, "value": True}},
                    {"property": "doObjectLevel", "args": {"row": 1, "object": "object-a", "value": True}},
                    {"property": "doObjectIDLevel", "args": {"row": 1, "objectID": "object-id", "value": True}},
                    {"property": "setGeometryFromTarget", "args": {}},
                    {"property": "setLevelsFromTarget", "args": {}},
                    {"property": "willFade", "args": {"row": 1, "column": 1, "value": False}},
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []
    setters = [op for op in result["results"][0]["planned_operations"] if op["operation"] == "set_property"]
    setter_by_property = {setter["property"]: setter for setter in setters}
    assert setter_by_property["mode"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/geoMode"
    assert setter_by_property["doLevel"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/doLevel/1/1"
    assert setter_by_property["doObjectLevel"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/doObjectLevel/1/object-a"
    assert setter_by_property["doObjectIDLevel"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/doObjectIDLevel/1/object-id"
    assert setter_by_property["setGeometryFromTarget"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/setGeometryFromTarget"
    assert setter_by_property["setLevelsFromTarget"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/setLevelsFromTarget"
    assert setter_by_property["willFade"]["address"] == f"/workspace/ws-1/cue_id/{fade_id}/willFade/1/1"
    assert setter_by_property["doLevel"]["args"] == [True]
    assert setter_by_property["setGeometryFromTarget"]["args"] == []
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert all(setter["planned_only_reason"] for setter in setters)
    assert len(client.requests) == 1
    address, args, workspace_id = client.requests[0]
    assert address == f"/workspace/ws-1/cue_id/{fade_id}/valuesForKeys"
    assert workspace_id == "ws-1"
    for key in ("geoMode", "pathHeight", "pathWidth", "fadeType", "patchTargetID"):
        assert f'"{key}"' in args[0]


def test_update_cues_fade_basic_validators_fail_without_plan() -> None:
    fade_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={fade_id: {"type": "Fade", "targetMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"targetMode": 99}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"levelsMode": 2}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"geoMode": -1}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"fadeType": 3}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"rotationType": 4}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"pathHeight": 0}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"pathWidth": -1}},
            {"cue_ref": fade_id, "profile": "fade_basic", "properties": {"doOpacity": "banana"}},
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doLevel", "args": {"row": 25, "column": 1, "value": True}}],
            },
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doLevel", "args": {"row": 1, "column": 129, "value": True}}],
            },
            {
                "cue_ref": fade_id,
                "profile": "fade_basic",
                "operations": [{"property": "doObjectLevel", "args": {"row": 1, "object": "", "value": True}}],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 11
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert result["results"][0]["errors"]["validation"] == "targetMode must be 0 for cue target or 1 for patch target"
    assert result["results"][1]["errors"]["validation"] == "levelsMode must be 0 or 1"
    assert result["results"][2]["errors"]["validation"] == "geoMode must be 0 or 1"
    assert result["results"][3]["errors"]["validation"] == "fadeType must be 1 for absolute or 2 for relative"
    assert result["results"][4]["errors"]["validation"] == "rotationType must be an integer from 0 to 3"
    assert result["results"][5]["errors"]["validation"] == "pathHeight must be a positive number"
    assert result["results"][6]["errors"]["validation"] == "pathWidth must be a positive number"
    assert result["results"][7]["errors"]["validation"] == "doOpacity must be a boolean"
    assert result["results"][8]["errors"]["validation"] == "doLevel.row must be an integer from 0 to 24"
    assert result["results"][9]["errors"]["validation"] == (
        "doLevel.column must be an integer from 0 to 128 or a cue output name"
    )
    assert result["results"][10]["errors"]["validation"] == "doObjectLevel.object must be a non-empty object name or ID"
    assert client.requests == []


def test_update_cues_fade_profile_type_mismatch_fails_cleanly_without_plan() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={memo_id: {"type": "Memo", "targetMode": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": memo_id, "profile": "fade_basic", "properties": {"targetMode": 0}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["errors"]["profile"] == "fade_basic update profile requires a Fade cue"


def test_update_cues_dry_run_reports_invalid_cue_ref_per_item_without_reading() -> None:
    client = BatchFakeWriteClient(QLabConfig(enable_write=False), cues={})
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": "selected", "properties": {"name": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "concrete cue" in result["results"][0]["errors"]["cue_ref"]
    assert client.requests == []


def test_update_cues_dry_run_reports_invalid_profile_per_item() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "bad_profile", "properties": {"name": "Nope"}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "update profile is not allowed" in result["results"][0]["errors"]["profile"]
    assert client.requests == []


def test_update_cues_real_preflight_failure_blocks_all_setters() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            audio_id: {"type": "Memo", "rate": 1.0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["failed_count"] == 1
    assert "Audio cue" in result["results"][1]["errors"]["profile"]
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{audio_id}/rate" not in addresses


def test_update_cues_real_preflight_invalid_value_blocks_all_setters_without_secret_leak() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    group_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            group_id: {"type": "Group", "preWait": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": group_id, "properties": {"preWait": -1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["dry_run"] is False
    assert result["requested_count"] == 2
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "planned"
    assert result["results"][1]["status"] == "preflight_failed"
    assert result["results"][1]["errors"]["validation"] == "preWait must be a non-negative number"
    assert "read_before" not in result["results"][1]["errors"]
    assert result["message"] == "Batch cue update was blocked during preflight; no mutating OSC commands were sent."
    assert f"/workspace/ws-1/cue_id/{memo_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/valuesForKeys" not in addresses
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" not in addresses
    assert f"/workspace/ws-1/cue_id/{group_id}/preWait" not in addresses
    assert "server-pass" not in repr(result)


def test_update_cues_real_updates_mixed_safe_profiles() -> None:
    memo_id = "11111111-1111-4111-8111-111111111111"
    audio_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            memo_id: {"type": "Memo", "name": "Memo old"},
            audio_id: {"type": "Audio", "rate": 1.0, "startTime": 0},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 0
    assert addresses.count("/workspaces") == 1
    assert addresses.count("/workspace/ws-1/connect") == 1
    assert addresses.count("/workspace/ws-1/showMode") == 1
    assert f"/workspace/ws-1/cue_id/{memo_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{audio_id}/rate" in addresses
    assert result["results"][0]["after"]["name"] == "Memo new"
    assert result["results"][1]["after"]["rate"] == 1.1


def test_update_cues_uses_configured_update_debug() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", update_debug=True),
        cues={cue_id: {"type": "Memo", "name": "Old"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"name": "New"}}], dry_run=False)

    assert result["ok"] is True
    assert result["results"][0]["debug"]["properties_match"] is True
    assert result["results"][0]["debug"]["requested_properties"] == {"name": "New"}


def test_update_cues_real_blocks_dry_run_only_property_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        reader.update_cues(
            "ws-1",
            [
                {
                    "cue_ref": cue_id,
                    "profile": "audio_basic",
                    "operations": [
                        {"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}
                    ],
                }
            ],
            dry_run=False,
        )

    assert client.requests == []


def test_update_cues_real_blocks_target_refs_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        reader.update_cues(
            "ws-1",
            [{"cue_ref": cue_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
            dry_run=False,
        )

    assert client.requests == []


def test_update_cues_real_blocks_missing_cue_before_any_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    missing_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old"}, missing_id: {"type": "Memo", "name": "Missing"}},
        missing_refs={missing_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"name": "New"}},
            {"cue_ref": missing_id, "properties": {"name": "Nope"}},
        ],
        dry_run=False,
    )

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][1]["status"] == "preflight_failed"
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" not in addresses


def test_update_cues_real_timeout_confirmed_by_after_read() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "flagged": False}},
        timeout_set_property=(cue_id, "flagged"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"flagged": True}}], dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 1
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert result["results"][0]["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][0]["executed_operations"][0]["status"] == "timeout_pending_verification"
    assert result["results"][0]["after"]["flagged"] is True


def test_update_cues_many_setter_timeouts_are_bounded_and_confirmed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(write_operations, "UPDATE_SETTER_REPLY_TIMEOUT_CAP_SECONDS", 0.001)
    monkeypatch.setattr(write_operations, "UPDATE_SETTER_REPLY_TOTAL_BUDGET_SECONDS", 0.012)
    monkeypatch.setattr(write_operations, "UPDATE_AFTER_READ_TIMEOUT_CAP_SECONDS", 0.01)
    cues = {
        f"{index:08d}-1111-4111-8111-111111111111": {
            "type": "Memo",
            "flagged": False,
            "colorName": "none",
        }
        for index in range(12)
    }
    timeout_properties = {
        (cue_id, prop)
        for cue_id in cues
        for prop in ("flagged", "colorName")
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", timeout=5.0),
        cues=cues,
        timeout_set_properties=timeout_properties,
        delay_on_timeout=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    started = time.monotonic()
    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"flagged": True, "colorName": "blue"}}
            for cue_id in cues
        ],
        dry_run=False,
    )
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 12
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 12
    assert all(item["status"] == "updated_with_confirmed_timeouts" for item in result["results"])
    assert all(
        operation["status"] == "timeout_pending_verification"
        for item in result["results"]
        for operation in item["executed_operations"]
    )
    assert all(item["after"]["flagged"] is True and item["after"]["colorName"] == "blue" for item in result["results"])
    setter_timeouts = [
        timeout
        for (address, _, _), timeout in zip(client.requests, client.reply_timeouts, strict=True)
        if "/cue_id/" in address and not address.endswith("/valuesForKeys")
    ]
    assert setter_timeouts
    assert max(timeout for timeout in setter_timeouts if timeout is not None) <= 0.001


def test_update_cues_confirmed_timeouts_do_not_count_as_failures_across_batch() -> None:
    clean_id = "11111111-1111-4111-8111-111111111111"
    timeout_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            clean_id: {"type": "Memo", "name": "Old clean"},
            timeout_id: {"type": "Memo", "name": "Old timeout"},
        },
        timeout_set_property=(timeout_id, "name"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": clean_id, "properties": {"name": "New clean"}},
            {"cue_ref": timeout_id, "properties": {"name": "New timeout"}},
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert [item["status"] for item in result["results"]] == ["updated", "updated_with_confirmed_timeouts"]
    assert result["warnings"]


def test_update_cues_unconfirmed_timeout_counts_as_failure() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "flagged": False}},
        timeout_set_property=(cue_id, "flagged"),
        timeout_without_apply=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"flagged": True}}], dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["updated_count"] == 0
    assert result["failed_count"] == 1
    assert result["timeout_confirmed_count"] == 0
    assert result["results"][0]["status"] == "partial_failed"
    assert "flagged" in result["results"][0]["errors"]


def test_update_cues_timed_out_setter_without_after_confirmation_reports_property() -> None:
    confirmed_id = "11111111-1111-4111-8111-111111111111"
    unconfirmed_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            confirmed_id: {"type": "Memo", "colorName": "none"},
            unconfirmed_id: {"type": "Memo", "colorName": "none"},
        },
        timeout_set_properties={(confirmed_id, "colorName"), (unconfirmed_id, "colorName")},
        timeout_without_apply_properties={(unconfirmed_id, "colorName")},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": confirmed_id, "properties": {"colorName": "blue"}},
            {"cue_ref": unconfirmed_id, "properties": {"colorName": "green"}},
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["updated_count"] == 1
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "updated_with_confirmed_timeouts"
    assert result["results"][1]["status"] == "partial_failed"
    assert result["results"][1]["after"]["colorName"] == "none"
    assert "colorName" in result["results"][1]["errors"]


def test_update_cues_retries_after_read_for_late_timeout_application() -> None:
    cues = {
        f"{index:08d}-1111-4111-8111-111111111111": {"type": "Memo", "name": f"Old {index}"}
        for index in range(30)
    }
    timeout_id = list(cues)[17]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues=cues,
        timeout_set_property=(timeout_id, "name"),
        timeout_apply_after_reads=3,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "properties": {"name": f"[CODEX30] {index}"}}
            for index, cue_id in enumerate(cues)
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated_with_confirmed_timeouts"
    assert result["updated_count"] == 30
    assert result["failed_count"] == 0
    assert result["timeout_confirmed_count"] == 1
    assert result["results"][17]["status"] == "updated_with_confirmed_timeouts"


def test_update_cues_after_read_mismatch_reports_requested_and_after_values() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old"}},
        ignore_set_property=(cue_id, "name"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"name": "New"}}], dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert result["updated_count"] == 0
    assert result["failed_count"] == 1
    assert result["results"][0]["status"] == "verification_failed"
    assert result["error_code"] == "QLAB_UPDATE_VERIFICATION_FAILED"
    assert "compare requested versus after" in result["suggested_action"]
    assert "requested" in result["results"][0]["errors"]["verification"]
    assert "after" in result["results"][0]["errors"]["verification"]


def test_update_cues_verification_accepts_numeric_normalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "duration": 1.0}},
        ignore_set_property=(cue_id, "duration"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues("ws-1", [{"cue_ref": cue_id, "properties": {"duration": 1}}], dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_verification_accepts_continue_mode_labels() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "continueMode": "auto_continue"}},
        ignore_set_property=(cue_id, "continueMode"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"continueMode": "auto_continue"}}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_verification_accepts_safe_enum_string_normalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "colorName": "RED", "text/format/alignment": "Center"}},
        ignore_set_property=(cue_id, "colorName"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "properties": {"colorName": "red", "text/format/alignment": "center"},
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["errors"] is None


def test_update_cues_mixed_clean_confirmed_timeout_and_real_error_counts_only_error() -> None:
    clean_id = "11111111-1111-4111-8111-111111111111"
    timeout_id = "22222222-2222-4222-8222-222222222222"
    error_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            clean_id: {"type": "Memo", "name": "Old clean"},
            timeout_id: {"type": "Memo", "flagged": False},
            error_id: {"type": "Memo", "armed": True},
        },
        timeout_set_property=(timeout_id, "flagged"),
        fail_set_property=(error_id, "armed"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": clean_id, "properties": {"name": "New clean"}},
            {"cue_ref": timeout_id, "properties": {"flagged": True}},
            {"cue_ref": error_id, "properties": {"armed": False}},
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["error_code"] == "QLAB_UPDATE_PARTIAL_FAILED"
    assert result["updated_count"] == 2
    assert result["failed_count"] == 1
    assert result["timeout_confirmed_count"] == 1
    assert [item["status"] for item in result["results"]] == [
        "updated",
        "updated_with_confirmed_timeouts",
        "partial_failed",
    ]
    assert "armed" in result["results"][2]["errors"]


def test_update_cues_real_reports_partial_failure_during_execution() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "name": "Old", "armed": True}},
        fail_set_property=(cue_id, "armed"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "properties": {"name": "New", "armed": False}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert result["failed_count"] == 1
    assert [operation["property"] for operation in result["results"][0]["executed_operations"]] == ["name"]
    assert "armed" in result["results"][0]["errors"]
    assert result["results"][0]["after"]["name"] == "New"


def test_update_cue_rejects_ambiguous_refs_and_bad_properties_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="concrete cue"):
        reader.update_cue("ws-1", "selected", {"name": "Nope"}, dry_run=True)

    planned = reader.update_cue("ws-1", "1", {"fileTarget": "/tmp/nope.wav"}, dry_run=True)
    assert planned["ok"] is True
    assert planned_setters(planned)["fileTarget"]["capability_gate"] == "file_target_access"

    with pytest.raises(UnsafeWriteOperationError, match="gated or dry-run only"):
        reader.update_cue("ws-1", "1", {"fileTarget": "/tmp/nope.wav"}, dry_run=False)


def test_update_cue_audio_basic_dry_run_allows_small_audio_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"rate": 1.25, "startTime": 1, "endTime": 9, "preservePitch": False},
        dry_run=True,
        profile="audio_basic",
    )

    planned_setters = [
        operation["property"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["profile"] == "audio_basic"
    assert planned_setters == ["rate", "startTime", "endTime", "preservePitch"]
    assert result["executed_operations"] == []


def test_update_cue_audio_last_slice_properties_dry_run_reads_before_and_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "lastSlicePlayCount": 1,
            "lastSliceInfiniteLoop": False,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "properties": {"lastSlicePlayCount": -1, "lastSliceInfiniteLoop": True},
            }
        ],
        dry_run=True,
    )

    item = result["results"][0]
    setters = [operation for operation in item["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert item["before"]["lastSlicePlayCount"] == 1
    assert item["before"]["lastSliceInfiniteLoop"] is False
    assert [setter["property"] for setter in setters] == ["lastSlicePlayCount", "lastSliceInfiniteLoop"]
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert item["executed_operations"] == []


def test_update_cues_audio_last_slice_invalid_values_have_no_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Audio", "lastSlicePlayCount": 1, "lastSliceInfiniteLoop": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "audio_basic", "properties": {"lastSlicePlayCount": 0}},
            {"cue_ref": cue_id, "profile": "audio_basic", "properties": {"lastSliceInfiniteLoop": "banana"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "lastSlicePlayCount must be a positive integer or -1" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "lastSliceInfiniteLoop must be a boolean" in result["results"][1]["errors"]["validation"]
    assert result["results"][1]["planned_operations"] == []


def test_update_cue_audio_basic_real_updates_and_verifies() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Audio",
            "rate": 1.0,
            "startTime": 0,
            "endTime": 10,
            "playCount": 1,
            "infiniteLoop": False,
            "preservePitch": True,
        },
        timeout_set_property="rate",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"rate": 1.25}, dry_run=False, profile="audio_basic")

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == "audio_basic"
    assert result["before"]["rate"] == 1.0
    assert result["after"]["rate"] == 1.25
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"


def test_update_cue_audio_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="rate"):
        reader.update_cue("ws-1", "1", {"rate": 0.01}, dry_run=True, profile="audio_basic")

    with pytest.raises(UnsafeWriteOperationError, match="endTime"):
        reader.update_cue(
            "ws-1",
            "1",
            {"startTime": 5, "endTime": 5},
            dry_run=True,
            profile="audio_basic",
        )

    with pytest.raises(UnsafeWriteOperationError, match="infiniteLoop"):
        reader.update_cue(
            "ws-1",
            "1",
            {"infiniteLoop": True, "playCount": 2},
            dry_run=True,
            profile="audio_basic",
        )

    assert client.requests == []


def test_update_cue_audio_basic_rejects_non_audio_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "rate": 1.0},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Audio cue"):
        reader.update_cue("ws-1", cue_id, {"rate": 1.2}, dry_run=False, profile="audio_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/rate" not in addresses


def test_update_cue_text_basic_dry_run_allows_small_text_profile() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {
            "text": "New title",
            "fixedWidth": 640,
            "text/format/alignment": "center",
            "text/format/fontName": "Courier New",
            "text/format/fontSize": 56,
        },
        dry_run=True,
        profile="text_basic",
    )

    planned_setters = [
        operation["property"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["profile"] == "text_basic"
    assert planned_setters == [
        "text",
        "fixedWidth",
        "text/format/alignment",
        "text/format/fontName",
        "text/format/fontSize",
    ]
    assert result["executed_operations"] == []


def test_update_cue_text_basic_real_updates_and_verifies_slash_properties() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text": "Old title",
            "fixedWidth": 500,
            "text/format/alignment": "left",
            "text/format/fontName": "Helvetica",
            "text/format/fontSize": 48,
        },
        timeout_set_property="text/format/fontSize",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"text/format/alignment": "right", "text/format/fontSize": 60},
        dry_run=False,
        profile="text_basic",
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == "text_basic"
    assert result["after"]["text/format/alignment"] == "right"
    assert result["after"]["text/format/fontSize"] == 60
    assert result["errors"] is None
    assert result["executed_operations"][1]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/text/format/fontSize"
    assert result["executed_operations"][1]["status"] == "timeout_pending_verification"


def test_update_cue_text_basic_rejects_invalid_values_before_osc() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="alignment"):
        reader.update_cue("ws-1", "1", {"text/format/alignment": "middle"}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontSize"):
        reader.update_cue("ws-1", "1", {"text/format/fontSize": 0}, dry_run=True, profile="text_basic")

    with pytest.raises(UnsafeWriteOperationError, match="fontName"):
        reader.update_cue("ws-1", "1", {"text/format/fontName": ""}, dry_run=True, profile="text_basic")

    assert client.requests == []


def test_update_cue_video_opacity_uses_qlab_unit_interval() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="opacity must be a number from 0 to 1"):
        reader.update_cue("ws-1", "1", {"opacity": 80}, dry_run=True, profile="video_basic")

    assert client.requests == []


def test_update_cue_text_color_components_use_qlab_unit_interval() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="text/format/color.red must be a number from 0 to 1"):
        reader.update_cue(
            "ws-1",
            "1",
            operations=[{"property": "text/format/color", "args": {"red": 255, "green": 0, "blue": 0, "alpha": 1}}],
            dry_run=True,
            profile="text_basic",
        )

    assert client.requests == []


def test_update_cue_text_basic_rejects_non_text_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "text": "Not a Text cue"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Text cue"):
        reader.update_cue("ws-1", cue_id, {"text": "New text"}, dry_run=False, profile="text_basic")

    addresses = [request[0] for request in client.requests]
    assert f"/workspace/ws-1/cue_id/{cue_id}/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/text" not in addresses


def test_update_cue_operations_dry_run_builds_structured_osc_paths() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {
                "property": "level",
                "args": {"inChannel": 1, "outChannel": 2, "decibel": -6},
                "mode": "live",
            }
        ],
        dry_run=True,
        profile="audio_basic",
    )

    setters = [operation for operation in result["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert result["properties"] == {}
    assert setters == [
        {
            "operation": "set_property",
            "property": "level",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/level/1/2/live",
            "args": [-6],
            "mode": "live",
            "risk_tier": "high",
            "real_write_enabled": False,
            "planned_only_reason": "audio_levels_can_affect_live_output",
            "capability_gate": "audio_output",
        }
    ]
    assert result["executed_operations"] == []


def test_update_cue_audio_dry_run_builds_slice_level_object_and_patch_paths() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
            {"property": "deleteSliceMarker", "args": {"index": 2}},
            {"property": "deleteSliceMarkers", "args": {}},
            {"property": "setDefaultLevels", "args": {}},
            {"property": "sliderLevel", "args": {"channel": 0, "decibel": "-inf"}, "mode": "live"},
            {"property": "objectIDLevel", "args": {"row": 0, "objectID": "obj-1", "decibel": -12}},
            {"property": "objectID/position", "args": {"objectID": "obj-1", "x": 1.25, "y": -2}},
            {"property": "audioOutputPatch/level", "args": {"inChannel": 0, "outChannel": 1, "decibel": -3}},
            {"property": "audioOutputPatch/routing/reset", "args": {}},
            {"property": "audioMap/objectID/colorName", "args": {"objectID": "map-obj-1", "colorName": "sky blue"}},
        ],
        dry_run=True,
        profile="audio_basic",
    )

    setters = [operation for operation in result["planned_operations"] if operation["operation"] == "set_property"]
    assert result["ok"] is True
    assert [setter["address"] for setter in setters] == [
        f"/workspace/ws-1/cue_id/{cue_id}/sliceMarker/0/time",
        f"/workspace/ws-1/cue_id/{cue_id}/sliceMarker/0/playCount",
        f"/workspace/ws-1/cue_id/{cue_id}/deleteSliceMarker/2",
        f"/workspace/ws-1/cue_id/{cue_id}/deleteSliceMarkers",
        f"/workspace/ws-1/cue_id/{cue_id}/setDefaultLevels",
        f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/0/live",
        f"/workspace/ws-1/cue_id/{cue_id}/objectIDLevel/0/obj-1",
        f"/workspace/ws-1/cue_id/{cue_id}/objectID/obj-1/position",
        f"/workspace/ws-1/cue_id/{cue_id}/audioOutputPatch/level/0/1",
        f"/workspace/ws-1/cue_id/{cue_id}/audioOutputPatch/routing/reset",
        f"/workspace/ws-1/cue_id/{cue_id}/audioMap/objectID/map-obj-1/colorName",
    ]
    assert [setter["args"] for setter in setters] == [
        [1.5],
        [-1],
        [],
        [],
        [],
        ["-inf"],
        [-12],
        [1.25, -2],
        [-3],
        [],
        ["sky blue"],
    ]
    assert all(setter["real_write_enabled"] is False for setter in setters)
    assert result["executed_operations"] == []


def test_update_cues_audio_invalid_structured_operation_has_no_plan() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [
                    {"property": "level", "args": {"inChannel": 25, "outChannel": 1, "decibel": -6}}
                ],
            },
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [
                    {"property": "sliderLevel", "args": {"channel": 1, "decibel": "loud"}}
                ],
            },
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["planned_count"] == 0
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert "level.inChannel must be an integer from 0 to 24" in result["results"][0]["errors"]["validation"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "sliderLevel.decibel must be a number or '-inf'" in result["results"][1]["errors"]["validation"]
    assert result["results"][1]["planned_operations"] == []


def test_update_cue_operations_support_video_text_and_midi_dry_run_shapes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    video_result = video.update_cue(
        "ws-1",
        cue_id,
        properties={"blendMode": "Normal", "clockType": "video"},
        operations=[
            {"property": "crop", "args": {"top": 1, "bottom": 2, "left": 3, "right": 4}},
            {"property": "videoEffects/add", "args": {"name": "ColorControls"}},
            {
                "property": "videoEffect/parameter",
                "args": {"name": "ColorControls", "parameterKey": "inputBrightness", "setting": 0.25},
            },
        ],
        dry_run=True,
        profile="video_basic",
    )

    text_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Text"},
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    text_result = text.update_cue(
        "ws-1",
        cue_id,
        operations=[
            {
                "property": "text/format/color",
                "args": {"red": 1, "green": 0.5, "blue": 0, "alpha": 1},
            },
            {
                "property": "text/format/shadowOffset",
                "args": {"width": 2, "height": 4},
            }
        ],
        dry_run=True,
        profile="text_basic",
    )

    midi_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "MIDI"},
    )
    midi = QLabReader(midi_client)  # type: ignore[arg-type]
    midi_result = midi.update_cue(
        "ws-1",
        cue_id,
        properties={"channel": 1, "byte1": 64},
        dry_run=True,
        profile="midi_basic",
    )

    video_setters = [op for op in video_result["planned_operations"] if op["operation"] == "set_property"]
    text_setters = [op for op in text_result["planned_operations"] if op["operation"] == "set_property"]
    midi_setters = [op["address"] for op in midi_result["planned_operations"] if op["operation"] == "set_property"]
    assert [(op["property"], op["address"], op["args"]) for op in video_setters] == [
        ("blendMode", f"/workspace/ws-1/cue_id/{cue_id}/blendMode", ["Normal"]),
        ("clockType", f"/workspace/ws-1/cue_id/{cue_id}/clockType", ["video"]),
        ("crop", f"/workspace/ws-1/cue_id/{cue_id}/crop", [1, 2, 3, 4]),
        ("videoEffects/add", f"/workspace/ws-1/cue_id/{cue_id}/videoEffects/add", ["ColorControls"]),
        (
            "videoEffect/parameter",
            f"/workspace/ws-1/cue_id/{cue_id}/videoEffect/ColorControls/parameter/inputBrightness",
            [0.25],
        ),
    ]
    assert [(op["property"], op["address"], op["args"]) for op in text_setters] == [
        ("text/format/color", f"/workspace/ws-1/cue_id/{cue_id}/text/format/color", [1, 0.5, 0, 1]),
        ("text/format/shadowOffset", f"/workspace/ws-1/cue_id/{cue_id}/text/format/shadowOffset", [2, 4]),
    ]
    assert midi_setters == [f"/workspace/ws-1/cue_id/{cue_id}/channel", f"/workspace/ws-1/cue_id/{cue_id}/byte1"]


def test_update_cue_real_blocks_dry_run_only_profiles_and_properties_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"

    video_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        video.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "crop", "args": {"top": 1, "bottom": 2, "left": 3, "right": 4}}],
            dry_run=False,
            profile="video_basic",
        )
    assert video_client.requests == []

    video_fx_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "videoEffects": []},
    )
    video_fx = QLabReader(video_fx_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        video_fx.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
            dry_run=False,
            profile="video_basic",
        )
    assert video_fx_client.requests == []

    text_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Text", "text/format/shadowOffset": [0, 0]},
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        text.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "text/format/shadowOffset", "args": {"width": 2, "height": 4}}],
            dry_run=False,
            profile="text_basic",
        )
    assert text_client.requests == []

    audio_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio"},
    )
    audio = QLabReader(audio_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        audio.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
            dry_run=False,
            profile="audio_basic",
        )
    assert audio_client.requests == []

    for profile, cue_type, properties in (
        ("light_basic", "Light", {"lightCommandText": "1 thru 5 @ 80"}),
        ("network_basic", "Network", {"customString": "/eos/cue/1/fire"}),
        ("midi_basic", "MIDI", {"note": 64}),
        ("timecode_basic", "Timecode", {"timecodeString": "01:00:00:00"}),
        ("fade_basic", "Fade", {"targetMode": 0}),
        ("script_basic", "Script", {"scriptSource": "display dialog \"blocked\""}),
    ):
        client = FakeWriteClient(
            QLabConfig(enable_write=True, passcode="server-pass"),
            existing_cue_id=cue_id,
            cue_values={"uniqueID": cue_id, "type": cue_type},
        )
        reader = QLabReader(client)  # type: ignore[arg-type]
        with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
            reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)
        assert client.requests == []

    light_op_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Light"},
    )
    light_op = QLabReader(light_op_client)  # type: ignore[arg-type]
    with pytest.raises(UnsafeWriteOperationError, match="dry-run only"):
        light_op.update_cue(
            "ws-1",
            cue_id,
            operations=[{"property": "setLight", "args": {"instrument_or_group": "1", "setting": 50}}],
            dry_run=False,
            profile="light_basic",
        )
    assert light_op_client.requests == []


def test_update_cue_real_allows_gated_common_property_with_explicit_gate() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Memo", "duckLevel": -12},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"duckLevel": -6},
        dry_run=False,
        confirm_gates=["cue_behavior"],
    )

    assert result["ok"] is True
    assert result["after"]["duckLevel"] == -6
    assert result["confirm_gates"] == ["cue_behavior"]
    assert result["executed_operations"][0]["capability_gate"] == "cue_behavior"


def test_update_cue_timecode_frame_rate_uses_documented_framerate_path() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Timecode", "framerate": 3},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"timecodeFrameRate": 0},
        dry_run=True,
        profile="timecode_basic",
    )

    planned_setters = [
        operation for operation in result["planned_operations"] if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert result["properties"] == {"framerate": 0}
    assert planned_setters == [
        {
            "operation": "set_property",
            "property": "timecodeFrameRate",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/framerate",
            "args": [0],
            "mode": "saved",
            "risk_tier": "medium",
            "real_write_enabled": True,
            "capability_gate": None,
        }
    ]


def test_update_cue_timecode_rejects_invalid_output_type_and_frame_rate() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="outputType must be 0 for MTC or 1 for LTC"):
        reader.update_cue("ws-1", "1", {"outputType": 2}, dry_run=True, profile="timecode_basic")

    with pytest.raises(UnsafeWriteOperationError, match="timecodeFrameRate must be a timecode frame rate index"):
        reader.update_cue("ws-1", "1", {"timecodeFrameRate": 8}, dry_run=True, profile="timecode_basic")

    assert client.requests == []


def test_update_cues_mic_basic_dry_run_plans_documented_mic_and_audio_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Mic", "channels": 1, "channelOffset": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "mic_basic",
                "properties": {
                    "channels": 2,
                    "channelOffset": 1,
                    "audioInputPatchID": "input-patch",
                    "audioOutputPatchName": "Main",
                },
                "operations": [
                    {"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}},
                    {"property": "mute", "args": {"output": 1, "value": True}},
                ],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["channels"]["real_write_enabled"] is True
    assert setters["channelOffset"]["real_write_enabled"] is True
    for prop in ("audioInputPatchID", "audioOutputPatchName", "level", "mute"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]
    assert setters["level"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/level/1/1"
    assert setters["level"]["args"] == [-6]
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_mic_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    mic_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={mic_id: {"type": "Mic"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channels": 0}},
            {"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channelOffset": -1}},
            {
                "cue_ref": mic_id,
                "profile": "mic_basic",
                "operations": [{"property": "level", "args": {"inChannel": 25, "outChannel": 1, "decibel": -6}}],
            },
            {"cue_ref": memo_id, "profile": "mic_basic", "properties": {"channels": 2}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert [item["status"] for item in result["results"]] == ["dry_run_preflight_failed"] * 4
    assert result["results"][0]["errors"]["validation"] == "channels must be a positive integer"
    assert result["results"][1]["errors"]["validation"] == "channelOffset must be a non-negative integer"
    assert "level.inChannel must be an integer from 0 to 24" in result["results"][2]["errors"]["validation"]
    assert result["results"][3]["errors"]["profile"] == "mic_basic update profile requires a Mic cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_timecode_basic_dry_run_plans_ltc_mtc_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Timecode", "outputType": 1, "framerate": 3, "ltcChannel": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "timecode_basic",
                "properties": {
                    "outputType": 0,
                    "timecodeFrameRate": 7,
                    "startTime": "01:00:00:00",
                    "endTime": "01:00:10:00",
                    "ltcChannel": 2,
                    "midiPatchID": "midi-patch",
                    "audioOutputPatchNumber": 1,
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["timecodeFrameRate"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/framerate"
    assert setters["timecodeFrameRate"]["real_write_enabled"] is True
    assert setters["outputType"]["real_write_enabled"] is True
    for prop in ("ltcChannel", "midiPatchID", "audioOutputPatchNumber"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]


def test_update_cues_timecode_basic_invalid_ltc_and_profile_mismatch_have_no_plan() -> None:
    timecode_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={timecode_id: {"type": "Timecode"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": timecode_id, "profile": "timecode_basic", "properties": {"ltcChannel": 0}},
            {"cue_ref": memo_id, "profile": "timecode_basic", "properties": {"outputType": 0}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "ltcChannel must be a positive integer"
    assert result["results"][1]["errors"]["profile"] == "timecode_basic update profile requires a Timecode cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_midi_file_basic_dry_run_plans_playback_and_patch_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "MIDI File", "rate": 1, "playCount": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "midi_file_basic",
                "properties": {
                    "fileTarget": "/show/foo.mid",
                    "rate": 1.25,
                    "startTime": 0,
                    "endTime": 8,
                    "duration": 8,
                    "playCount": 2,
                    "midiPatchName": "Synth",
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    for prop in ("rate", "startTime", "endTime", "duration", "playCount"):
        assert setters[prop]["real_write_enabled"] is True
    for prop in ("fileTarget", "midiPatchName"):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]


def test_update_cues_midi_file_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    midi_file_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={midi_file_id: {"type": "MIDI File"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"rate": 0.01}},
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"playCount": 0}},
            {"cue_ref": midi_file_id, "profile": "midi_file_basic", "properties": {"duration": -1}},
            {"cue_ref": memo_id, "profile": "midi_file_basic", "properties": {"rate": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert "rate must be a number from 0.03 to 33.0" in result["results"][0]["errors"]["validation"]
    assert result["results"][1]["errors"]["validation"] == "playCount must be a positive integer"
    assert result["results"][2]["errors"]["validation"] == "duration must be a non-negative number"
    assert result["results"][3]["errors"]["profile"] == "midi_file_basic update profile requires a MIDI File cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_midi_basic_dry_run_plans_documented_message_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "MIDI", "messageType": 1, "status": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "midi_basic",
                "properties": {
                    "midiPatchID": "midi-patch",
                    "messageType": 2,
                    "channel": 16,
                    "command": 1,
                    "commandFormat": 2,
                    "status": 6,
                    "note": 64,
                    "velocity": 100,
                    "programChange": 10,
                    "pitchBend": 8192,
                    "byte1": 65,
                    "byte2": 66,
                    "byteCombo": 1024,
                    "controlNumber": 7,
                    "controlValue": 127,
                    "deviceID": 1,
                    "endValue": 127,
                    "macro": 2,
                    "rawString": "7E 7F 09 01",
                    "qList": "1",
                    "qNumber": "2",
                    "qPath": "3",
                    "timecodeString": "01:00:00:00",
                    "timecodeFormat": 3,
                    "doFade": True,
                },
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["note"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byte1"
    assert setters["velocity"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byte2"
    assert setters["pitchBend"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/byteCombo"
    for setter in setters.values():
        assert setter["real_write_enabled"] is False
        assert setter["planned_only_reason"]


def test_update_cues_midi_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    midi_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={midi_id: {"type": "MIDI"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"messageType": 4}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"channel": 17}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"byte1": 128}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"byteCombo": 16384}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"status": 7}},
            {"cue_ref": midi_id, "profile": "midi_basic", "properties": {"timecodeFormat": 4}},
            {"cue_ref": memo_id, "profile": "midi_basic", "properties": {"channel": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "messageType must be 1 for MIDI voice, 2 for MSC, or 3 for SysEx"
    assert result["results"][1]["errors"]["validation"] == "channel must be an integer from 1 to 16"
    assert result["results"][2]["errors"]["validation"] == "byte1 must be an integer from 0 to 127"
    assert result["results"][3]["errors"]["validation"] == "byteCombo must be an integer from 0 to 16383"
    assert result["results"][4]["errors"]["validation"] == "status must be an integer from 0 to 6"
    assert result["results"][5]["errors"]["validation"] == (
        "timecodeFormat must be 0 for 24 fps, 1 for 25 fps, 2 for 30 fps drop, or 3 for 30 fps non-drop"
    )
    assert result["results"][6]["errors"]["profile"] == "midi_basic update profile requires a MIDI cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_network_basic_dry_run_plans_documented_non_ambiguous_fields() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Network", "customString": "/cue/1/start"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "network_basic",
                "properties": {
                    "customString": "/eos/cue/1/fire",
                    "networkPatchID": "net-patch",
                    "parameterValues": [1, "go"],
                },
                "operations": [{"property": "parameterValue", "args": {"parameter": "cueName", "value": "Intro"}}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["parameterValue"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/parameterValue/cueName"
    assert setters["parameterValue"]["args"] == ["Intro"]
    for setter in setters.values():
        assert setter["real_write_enabled"] is False
        assert setter["planned_only_reason"]


def test_update_cues_network_basic_invalid_values_and_unsupported_fields_have_no_plan() -> None:
    network_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={network_id: {"type": "Network"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"parameterValues": "not-list"}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"networkPatchNumber": -1}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"message": "/unsupported"}},
            {"cue_ref": network_id, "profile": "network_basic", "properties": {"protocol": "udp"}},
            {"cue_ref": memo_id, "profile": "network_basic", "properties": {"customString": "/go"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "parameterValues must be a list"
    assert result["results"][1]["errors"]["validation"] == "networkPatchNumber must be a non-negative integer"
    assert "not allowlisted" in result["results"][2]["errors"]["validation"]
    assert "not allowlisted" in result["results"][3]["errors"]["validation"]
    assert result["results"][4]["errors"]["profile"] == "network_basic update profile requires a Network cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_light_basic_dry_run_plans_documented_light_cue_messages() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "1 = 50", "alwaysCollate": False, "subcontroller": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {
                    "lightCommandText": "1 = 50",
                    "alwaysCollate": True,
                    "subcontroller": False,
                },
                "operations": [
                    {"property": "setLight", "args": {"instrument_or_group": "front.intensity", "setting": 50}},
                    {
                        "property": "replaceLightCommand",
                        "args": {"oldCommand": "1 = 50", "newCommand": "1 = 60"},
                    },
                    {"property": "removeLightCommandsMatching", "args": {"match": "2 = 0"}},
                    {"property": "safeSort"},
                    {"property": "safeSortCommands"},
                    {"property": "prune"},
                    {"property": "pruneCommands"},
                ],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert result["results"][0]["executed_operations"] == []
    setters = planned_setters(result["results"][0])
    assert setters["setLight"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/setLight"
    assert setters["setLight"]["args"] == ["front.intensity", 50]
    assert setters["replaceLightCommand"]["args"] == ["1 = 50", "1 = 60"]
    assert setters["removeLightCommandsMatching"]["args"] == ["2 = 0"]
    for prop in (
        "lightCommandText",
        "alwaysCollate",
        "subcontroller",
        "setLight",
        "replaceLightCommand",
        "removeLightCommandsMatching",
        "safeSort",
        "safeSortCommands",
        "prune",
        "pruneCommands",
    ):
        assert setters[prop]["real_write_enabled"] is False
        assert setters[prop]["planned_only_reason"]
    assert all(request[0].endswith("/valuesForKeys") for request in client.requests)


def test_update_cues_light_basic_invalid_values_and_profile_mismatch_have_no_plan() -> None:
    light_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={light_id: {"type": "Light"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"alwaysCollate": "yes"}},
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"subcontroller": "yes"}},
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [{"property": "setLight", "args": {"instrument_or_group": "1"}}],
            },
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [
                    {"property": "replaceLightCommand", "args": {"oldCommand": "", "newCommand": "1 = 60"}}
                ],
            },
            {
                "cue_ref": light_id,
                "profile": "light_basic",
                "operations": [{"property": "removeLightCommandsMatching", "args": {"match": ""}}],
            },
            {"cue_ref": light_id, "profile": "light_basic", "properties": {"parameterValues": {"intensity": 80}}},
            {"cue_ref": memo_id, "profile": "light_basic", "properties": {"lightCommandText": "1 = 50"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "alwaysCollate must be a boolean"
    assert result["results"][1]["errors"]["validation"] == "subcontroller must be a boolean"
    assert result["results"][2]["errors"]["validation"] == "setLight args missing required key: setting"
    assert result["results"][3]["errors"]["validation"] == "replaceLightCommand.oldCommand must be a non-empty string"
    assert (
        result["results"][4]["errors"]["validation"]
        == "removeLightCommandsMatching.match must be a non-empty string"
    )
    assert "not allowlisted" in result["results"][5]["errors"]["validation"]
    assert result["results"][6]["errors"]["profile"] == "light_basic update profile requires a Light cue"
    assert all(item["planned_operations"] == [] for item in result["results"])
    assert all(item["executed_operations"] == [] for item in result["results"])


def test_update_cues_script_basic_dry_run_plans_source_alias_without_execution() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Script", "scriptSource": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "script_basic",
                "properties": {"scriptSource": "display dialog \"planned\""},
                "operations": [{"property": "scriptText", "args": "display dialog \"alias\""}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    setters = planned_setters(result["results"][0])
    assert setters["scriptSource"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/scriptSource"
    assert setters["scriptText"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/scriptSource"
    assert all(setter["real_write_enabled"] is False for setter in setters.values())
    assert all(setter["planned_only_reason"] == "not_editable_by_osc" for setter in setters.values())
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_script_basic_invalid_value_and_profile_mismatch_have_no_plan() -> None:
    script_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={script_id: {"type": "Script"}, memo_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": script_id, "profile": "script_basic", "properties": {"scriptSource": 123}},
            {"cue_ref": memo_id, "profile": "script_basic", "properties": {"scriptSource": ""}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "scriptSource must be a string"
    assert result["results"][1]["errors"]["profile"] == "script_basic update profile requires a Script cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_update_cues_wait_and_memo_basic_stay_common_only() -> None:
    catalog = profile_catalog()
    safe_common = set(catalog["memo_basic"]["properties"])
    assert set(catalog["wait_basic"]["properties"]) == safe_common
    assert safe_common < set(catalog["common"]["properties"])
    assert "duckLevel" not in safe_common
    assert "fileTarget" not in safe_common

    wait_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={wait_id: {"type": "Wait", "duration": 0}, memo_id: {"type": "Memo", "notes": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": 3, "continueMode": "auto_follow"}},
            {"cue_ref": memo_id, "profile": "memo_basic", "properties": {"name": "Memo", "notes": "Operator note"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["planned_count"] == 2
    assert planned_setters(result["results"][0])["continueMode"]["args"] == [2]
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][1]["executed_operations"] == []


def test_update_cues_wait_and_memo_invalid_common_values_have_no_plan() -> None:
    wait_id = "11111111-1111-4111-8111-111111111111"
    memo_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={wait_id: {"type": "Wait", "duration": 0}, memo_id: {"type": "Memo", "duration": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": -1}},
            {"cue_ref": memo_id, "profile": "memo_basic", "properties": {"continueMode": "bad"}},
            {"cue_ref": memo_id, "profile": "wait_basic", "properties": {"duration": 1}},
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert result["planned_count"] == 0
    assert result["results"][0]["errors"]["validation"] == "duration must be a non-negative number"
    assert "continueMode must be" in result["results"][1]["errors"]["validation"]
    assert result["results"][2]["errors"]["profile"] == "wait_basic update profile requires a Wait cue"
    assert all(item["planned_operations"] == [] for item in result["results"])


def test_create_cue_dry_run_reviews_supported_and_unsupported_non_light_types() -> None:
    supported_client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    supported_reader = QLabReader(supported_client)  # type: ignore[arg-type]
    for cue_type in ("memo", "group", "wait", "audio"):
        result = supported_reader.create_cue("ws-1", cue_type, properties={"name": cue_type}, dry_run=True)
        assert result["ok"] is True
        assert result["status"] == "dry_run"
        assert result["planned_operations"][0]["operation"] == "new"
    assert supported_client.requests == []

    unsupported_client = FakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"))
    unsupported_reader = QLabReader(unsupported_client)  # type: ignore[arg-type]
    for cue_type in ("mic", "midi", "midi file", "network", "script", "timecode"):
        with pytest.raises(UnsafeWriteOperationError, match="cue_type is not allowed"):
            unsupported_reader.create_cue("ws-1", cue_type, dry_run=True)
    assert unsupported_client.requests == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "properties"),
    [
        ("mic_basic", "Mic", {"channels": 2, "channelOffset": 1}),
        ("video_basic", "Video", {"translation/x": 100, "opacity": 0.8, "cropTop": 5}),
        ("camera_basic", "Camera", {"scale/x": 1.2, "rotation": 15, "channels": 2}),
        ("midi_file_basic", "MIDI File", {"rate": 1.1, "startTime": 0, "endTime": 8, "playCount": 2}),
        ("timecode_basic", "Timecode", {"outputType": 1, "startTime": "01:00:00:00"}),
        ("target_basic", "Start", {"name": "Start cue renamed"}),
        ("reset_basic", "Reset", {"name": "Reset cue renamed"}),
        ("devamp_basic", "Devamp", {"name": "Devamp cue renamed"}),
        ("light_basic", "Light", {"name": "Light cue renamed"}),
        ("fade_basic", "Fade", {"name": "Fade cue renamed"}),
        ("network_basic", "Network", {"name": "Network cue renamed"}),
        ("midi_basic", "MIDI", {"name": "MIDI cue renamed"}),
        ("script_basic", "Script", {"name": "Script cue renamed"}),
    ],
)
def test_update_cue_real_updates_new_safe_profiles(profile: str, cue_type: str, properties: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values = {
        "uniqueID": cue_id,
        "type": cue_type,
        "name": "Stale",
        "channels": 1,
        "channelOffset": 0,
        "translation/x": 0,
        "opacity": 1,
        "cropTop": 0,
        "scale/x": 1,
        "rotation": 0,
        "rate": 1,
        "startTime": 0,
        "endTime": 10,
        "playCount": 1,
        "outputType": 0,
    }
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, properties, dry_run=False, profile=profile)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["profile"] == profile
    for key, value in properties.items():
        assert result["after"][key] == value
        assert f"/workspace/ws-1/cue_id/{cue_id}/{key}" in [request[0] for request in client.requests]


def test_update_cue_real_blocks_missing_cue_before_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        missing_cue=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" not in [request[0] for request in client.requests]


def test_update_cue_real_blocks_when_before_has_no_unique_id() -> None:
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=None,
        cue_values={"number": "1", "name": "Stale", "type": "Memo"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is False
    assert result["status"] == "cue_not_found"
    assert result["executed_operations"] == []
    assert "/workspace/ws-1/cue/1/name" not in addresses


def test_update_cue_real_updates_and_verifies_fresh_details() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["before"]["name"] == "Stale"
    assert result["after"]["name"] == "New"
    assert result["diff"]["armed"] == {"before": True, "requested": False, "after": False}
    assert result["verification"]["properties"]["name"] == "New"
    assert "/workspace/ws-1/connect" in addresses
    assert "/workspace/ws-1/showMode" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/armed" in addresses


def test_update_cue_real_accepts_setter_timeout_when_after_read_confirms_value() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass", cache_ttl=10),
        existing_cue_id=cue_id,
        timeout_set_property="flagged",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"flagged": True}, dry_run=False)

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["after"]["flagged"] is True
    assert result["diff"]["flagged"] == {"before": False, "requested": True, "after": True}
    assert result["errors"] is None
    assert result["executed_operations"][0]["status"] == "timeout_pending_verification"
    assert result["warnings"] == ["One or more setters did not reply, but fresh after-read confirmed requested values."]


def test_update_cue_real_resolves_number_to_unique_id_for_setters() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", "1", {"name": "New"}, dry_run=False)

    addresses = [request[0] for request in client.requests]
    planned_setters = [
        operation["address"]
        for operation in result["planned_operations"]
        if operation["operation"] == "set_property"
    ]
    assert result["ok"] is True
    assert "/workspace/ws-1/cue/1/valuesForKeys" in addresses
    assert f"/workspace/ws-1/cue_id/{cue_id}/name" in addresses
    assert "/workspace/ws-1/cue/1/name" not in addresses
    assert planned_setters == [f"/workspace/ws-1/cue_id/{cue_id}/name"]


def test_update_cue_real_blocks_in_show_mode() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        show_mode_data=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="Show Mode"):
        reader.update_cue("ws-1", cue_id, {"name": "New"}, dry_run=False)

    assert [request[0] for request in client.requests] == [
        "/workspaces",
        "/workspace/ws-1/connect",
        "/workspace/ws-1/showMode",
    ]


def test_update_cue_real_reports_partial_failure() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        fail_set_property="armed",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue("ws-1", cue_id, {"name": "New", "armed": False}, dry_run=False)

    assert result["ok"] is False
    assert result["status"] == "partial_failed"
    assert [operation["property"] for operation in result["executed_operations"]] == ["name"]
    assert "armed" in result["errors"]
    assert result["after"]["name"] == "New"
