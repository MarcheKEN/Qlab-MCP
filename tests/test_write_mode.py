from __future__ import annotations

import math
from pathlib import Path
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
from qlab_mcp.write.registry import QLAB_BLEND_MODES, UPDATE_PROFILE_NAMES, profile_catalog


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
            self._set_property(
                property_name,
                list(args) if property_name == "quaternion" else (args[0] if args else None),
            )
            if property_name == self.timeout_set_property:
                raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
            return SimpleNamespace(data=None, status="ok")
        raise AssertionError(f"Unexpected fake write request: {address}")

    def _set_property(self, property_name: str, value: Any) -> None:
        if property_name == "resetRotation":
            self.cue_values["quaternion"] = [1, 0, 0, 0]
            return
        parameter_prefix = "videoEffectIndex/0/parameter/"
        if property_name.startswith(parameter_prefix):
            parameter_key = property_name.removeprefix(parameter_prefix)
            effects = self.cue_values.setdefault("videoEffects", [])
            while len(effects) <= 0:
                effects.append({})
            effect = effects[0]
            if isinstance(effect, dict):
                parameters = effect.get("parameters")
                if isinstance(parameters, dict) and parameter_key in parameters:
                    parameters[parameter_key] = value
                else:
                    effect[parameter_key] = value
                return
        self.cue_values[property_name] = value

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
        error_after_apply_properties: set[tuple[str, str]] | None = None,
        timeout_set_property: tuple[str, str] | None = None,
        timeout_set_properties: set[tuple[str, str]] | None = None,
        timeout_without_apply: bool = False,
        timeout_without_apply_properties: set[tuple[str, str]] | None = None,
        delay_on_timeout: bool = False,
        timeout_apply_after_reads: int | None = None,
        ignore_set_property: tuple[str, str] | None = None,
        missing_refs: set[str] | None = None,
        show_mode_data: Any = False,
        connect_data: str = "ok:view|edit",
        workspace_id: str = "ws-1",
        light_patch: dict[str, Any] | None = None,
        light_patch_error: bool = False,
        video_stages: list[dict[str, Any]] | None = None,
        video_stage_regions: dict[str, list[dict[str, Any]]] | None = None,
        broken_stage_ids: set[str] | None = None,
        numeric_bool_readback_properties: set[str] | None = None,
        omit_slice_markers_after_delete: bool = False,
    ):
        self.config = config
        self.cues = {cue_id: dict(values, uniqueID=cue_id) for cue_id, values in cues.items()}
        self.cue_numbers = cue_numbers or {}
        self.fail_set_property = fail_set_property
        self.error_after_apply_properties = error_after_apply_properties or set()
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
        self.connect_data = connect_data
        self.workspace_id = workspace_id
        self.light_patch = light_patch or {"instruments": [], "groups": []}
        self.light_patch_error = light_patch_error
        self.video_stages = video_stages or []
        self.video_stage_regions = video_stage_regions or {}
        self.broken_stage_ids = broken_stage_ids or set()
        self.numeric_bool_readback_properties = numeric_bool_readback_properties or set()
        self.omit_slice_markers_after_delete = omit_slice_markers_after_delete
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
            return SimpleNamespace(data=[{"uniqueID": self.workspace_id, "displayName": "demo.qlab5"}], status="ok")
        self.requests.append((address, args, workspace_id))
        self.reply_timeouts.append(reply_timeout)
        if address == "/workspaces":
            return SimpleNamespace(data=[{"uniqueID": self.workspace_id, "displayName": "demo.qlab5"}], status="ok")
        if address == f"/workspace/{self.workspace_id}/connect":
            return SimpleNamespace(data=self.connect_data, status="ok")
        if address == f"/workspace/{self.workspace_id}/showMode":
            return SimpleNamespace(data=self.show_mode_data, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/light/patch":
            if self.light_patch_error:
                raise QLabReplyError("error", "Light Patch unavailable", address)
            return SimpleNamespace(data=self.light_patch, status="ok")
        if address == f"/workspace/{self.workspace_id}/settings/video/stages":
            return SimpleNamespace(data=self.video_stages, status="ok")
        stage_prefix = f"/workspace/{self.workspace_id}/settings/video/stageID/"
        if address.startswith(stage_prefix) and address.endswith("/regions"):
            stage_id = address.removeprefix(stage_prefix).removesuffix("/regions")
            return SimpleNamespace(data=self.video_stage_regions.get(stage_id, []), status="ok")
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
                        self._set_property(pending_cue_id, pending_prop, pending_value)
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
                    self._set_property(cue_id, prop, self._request_value(prop, args))
                else:
                    self.pending_timeout_applies[(cue_id, prop)] = self._request_value(prop, args)
            raise OscTimeoutError(f"Timed out waiting for QLab reply to {address}")
        if self.ignore_set_property == (cue_id, prop):
            return SimpleNamespace(data=None, status="ok")
        self._set_property(cue_id, prop, self._request_value(prop, args))
        if (cue_id, prop) in self.error_after_apply_properties:
            raise QLabReplyError("error", f"Failed setting {prop}", address)
        return SimpleNamespace(data=None, status="ok")

    @staticmethod
    def _request_value(prop: str, args: tuple[Any, ...]) -> Any:
        if prop in {"quaternion", "addSliceMarker"}:
            return list(args)
        return args[0] if args else None

    def _set_property(self, cue_id: str, prop: str, value: Any) -> None:
        if prop == "resetRotation":
            self.cues[cue_id]["quaternion"] = [1, 0, 0, 0]
            return
        if prop.startswith("sliceMarker/") and prop.endswith("/time"):
            index = int(prop.split("/")[1])
            self.cues[cue_id]["sliceMarkers"][index]["time"] = value
            return
        if prop.startswith("sliceMarker/") and prop.endswith("/playCount"):
            index = int(prop.split("/")[1])
            self.cues[cue_id]["sliceMarkers"][index]["playCount"] = value
            return
        if prop == "addSliceMarker":
            time_value, play_count = value
            markers = self.cues[cue_id].setdefault("sliceMarkers", [])
            markers.append({"time": time_value, "playCount": play_count})
            markers.sort(key=lambda marker: marker["time"])
            return
        if prop == "deleteSliceMarkers":
            if self.omit_slice_markers_after_delete:
                self.cues[cue_id].pop("sliceMarkers", None)
            else:
                self.cues[cue_id]["sliceMarkers"] = []
            return
        if prop.startswith("deleteSliceMarker/"):
            index = int(prop.split("/")[1])
            del self.cues[cue_id]["sliceMarkers"][index]
            return
        if prop == "stageID":
            self.cues[cue_id]["isBroken"] = value in self.broken_stage_ids
        if prop in self.numeric_bool_readback_properties and isinstance(value, bool):
            value = int(value)
        if prop.startswith("sliderLevel/"):
            channel = int(prop.split("/")[1])
            levels = list(self.cues[cue_id].setdefault("sliderLevels", []))
            while len(levels) <= channel:
                levels.append(0)
            levels[channel] = value
            self.cues[cue_id]["sliderLevels"] = levels
            return
        if prop.startswith("level/"):
            _, in_channel_text, out_channel_text = prop.split("/", 2)
            in_channel = int(in_channel_text)
            out_channel = int(out_channel_text)
            matrix = [list(row) if isinstance(row, list) else [] for row in self.cues[cue_id].setdefault("levels", [])]
            while len(matrix) <= in_channel:
                matrix.append([])
            row = list(matrix[in_channel])
            while len(row) <= out_channel:
                row.append(0)
            row[out_channel] = value
            matrix[in_channel] = row
            self.cues[cue_id]["levels"] = matrix
            return
        if prop.startswith("inputChannelName/"):
            self.cues[cue_id][prop] = value
            return
        if prop.startswith("gang/"):
            self.cues[cue_id][prop] = value
            return
        if prop.startswith("mute/channel/") and prop != "mute/channel/clear":
            output = int(prop.split("/")[-1])
            channels = set(self.cues[cue_id].setdefault("muteChannels", []))
            if value:
                channels.add(output)
            else:
                channels.discard(output)
            self.cues[cue_id]["muteChannels"] = sorted(channels)
            return
        if prop == "mute/channel/clear":
            self.cues[cue_id]["muteChannels"] = []
            return
        if prop.startswith("solo/") and prop != "solo/channel/clear":
            output = int(prop.split("/")[-1])
            channels = set(self.cues[cue_id].setdefault("soloChannels", []))
            if value:
                channels.add(output)
            else:
                channels.discard(output)
            self.cues[cue_id]["soloChannels"] = sorted(channels)
            return
        if prop == "solo/channel/clear":
            self.cues[cue_id]["soloChannels"] = []
            return
        parameter_prefix = "videoEffectIndex/0/parameter/"
        if prop.startswith(parameter_prefix):
            parameter_key = prop.removeprefix(parameter_prefix)
            effects = self.cues[cue_id].setdefault("videoEffects", [])
            while len(effects) <= 0:
                effects.append({})
            effect = effects[0]
            if isinstance(effect, dict):
                parameters = effect.get("parameters")
                if isinstance(parameters, dict) and parameter_key in parameters:
                    parameters[parameter_key] = value
                else:
                    effect[parameter_key] = value
                return
        self.cues[cue_id][prop] = value

    def _cue_id_and_property(self, address: str) -> tuple[str | None, str | None]:
        cue_id_prefix = f"/workspace/{self.workspace_id}/cue_id/"
        cue_number_prefix = f"/workspace/{self.workspace_id}/cue/"
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
        if operation["operation"] in {"set_property", "action"}
    }


def assert_no_confirm_token(value: Any) -> None:
    if isinstance(value, dict):
        assert "confirm_token" not in value
        for nested in value.values():
            assert_no_confirm_token(nested)
    elif isinstance(value, list):
        for nested in value:
            assert_no_confirm_token(nested)


def normalized_light_patch_fixture() -> dict[str, Any]:
    front = {
        "name": "Front",
        "parameters": {"0": {"name": "intensity"}},
        "definition": {
            "name": "Dimmer",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}},
        },
    }
    red = {
        "name": "Red Fixture",
        "parameters": {"0": {"name": "intensity"}, "1": {"name": "red"}},
        "definition": {
            "name": "RGB",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}, "1": {"name": "red"}},
        },
    }
    dimmer = {
        "name": "Dimmer Only",
        "parameters": {"0": {"name": "intensity"}},
        "definition": {
            "name": "Dimmer",
            "defaultParameter": 0,
            "parameters": {"0": {"name": "intensity"}},
        },
    }
    return {
        "instruments": [front, red, dimmer],
        "groups": [
            {"name": "Back", "instruments": [red, dimmer]},
            {"name": "all", "instruments": [front, red, dimmer]},
        ],
    }


def confirm_token_for(reader: QLabReader, cue_ref: str, update: dict[str, Any], profile: str = "common") -> str:
    dry_result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_ref, "profile": profile, **update}],
        dry_run=True,
    )
    setters = planned_setters(dry_result["results"][0])
    return setters[next(iter(setters))]["confirm_token"]


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

VIDEO_PHASE2_ALLOWED_PROPERTIES = {
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
    "holdLastFrame",
    "infiniteLoop",
    "fixedWidth",
    "layer",
    "opacity",
    "playCount",
    "preservePitch",
    "preserveAspectRatio",
    "rate",
    "scale/x",
    "scale/y",
    "level",
    "sliderLevel",
    "inputChannelName",
    "gang",
    "lockFadeToCue",
    "mute/channel",
    "solo/channel",
    "mute/channel/clear",
    "solo/channel/clear",
    "smooth",
    "stageID",
    "startTime",
    "endTime",
    "text",
    "text/format/alignment",
    "text/format/fontName",
    "text/format/fontSize",
    "text/format/shadowBlurRadius",
    "text/format/shadowOffset/width",
    "text/format/shadowOffset/height",
    "text/format/underlineStyle",
    "text/format/strikethroughStyle",
    "translation/x",
    "translation/y",
    "audioInputPatchID",
    "audioOutputPatchID",
    "videoInputPatchID",
    "sliceMarker/time",
    "sliceMarker/playCount",
    "addSliceMarker",
    "deleteSliceMarker",
    "deleteSliceMarkers",
    "lastSlicePlayCount",
    "lastSliceInfiniteLoop",
}
VIDEO_PHASE3C_SCALAR_PROPERTIES = {
    "scale/x",
    "scale/y",
    "anchor/x",
    "anchor/y",
    "cropTop",
    "cropBottom",
    "cropLeft",
    "cropRight",
}
VIDEO_PHASE3D_APPEARANCE_PROPERTIES = {"blendMode", "preserveAspectRatio"}
PHASE3E_TEXT_BASIC_PROPERTIES = {
    "text",
    "text/format/alignment",
    "text/format/fontSize",
}
PHASE3F_TEXT_STYLE_VALUES = {
    "text/format/shadowBlurRadius": 2,
    "text/format/shadowOffset/width": 1,
    "text/format/shadowOffset/height": -1,
    "text/format/underlineStyle": "none",
    "text/format/strikethroughStyle": "single",
}
VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES = {
    "videoEffect/enabled",
    "videoEffectIndex/enabled",
    "videoEffect/parameter",
    "videoEffectIndex/parameter",
}
VIDEO_PHASE2_REQUESTED_VALUES = {
    "anchor/x": 12.5,
    "anchor/y": -4.5,
    "blendMode": "Normal",
    "clockType": "video",
    "cropBottom": 2.5,
    "cropLeft": 3.5,
    "cropRight": 4.5,
    "cropTop": 1.5,
    "fixedWidth": 640,
    "opacity": 0.75,
    "preserveAspectRatio": False,
    "scale/x": 125,
    "scale/y": 90,
    "text": "New title",
    "text/format/alignment": "CENTER",
    "text/format/fontName": "Helvetica",
    "text/format/fontSize": 56,
    "translation/x": 10.5,
    "translation/y": -20.5,
}
VIDEO_PHASE2_NORMALIZED_VALUES = {
    **VIDEO_PHASE2_REQUESTED_VALUES,
    "blendMode": "Normal",
    "clockType": "video",
    "preserveAspectRatio": False,
    "text/format/alignment": "center",
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
        "quaternion": [0, 0, 0, 1],
        "rate": 1,
        "rotation_type": 1,
        "second_trigger_action": 1,
        "string": "value",
        "target_id": "target-id",
        "target_mode": 1,
        "text_alignment": "center",
        "text_font_size": 24,
        "text_line_style": "single",
        "timecode_framerate": 1,
        "timecode_part": 1,
        "timecode_output_type": 1,
        "unit_interval": 0.5,
        "video_blend_mode": "Normal",
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
        "quaternion": [0, 0, 0],
        "rate": 0.01,
        "rotation_type": 4,
        "second_trigger_action": 8,
        "string": 123,
        "target_id": "",
        "target_mode": 2,
        "text_alignment": "middle",
        "text_font_size": 0,
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
    assert catalog["group_basic"]["properties"]["playlist/crossfade/duration"]["contextual_requirements"] == [
        "group_mode_is_playlist"
    ]
    assert catalog["memo_basic"]["properties"]["duration"]["contextual_requirements"] == ["allows_editing_duration"]
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
    assert catalog["video_basic"]["properties"]["translation/x"]["real_write_enabled"] is False
    assert catalog["video_basic"]["properties"]["translation/x"]["planned_only_reason"] == (
        "video_phase2_dry_run_only"
    )
    assert "rotation" not in catalog["video_basic"]["properties"]
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
    assert "rotation" not in catalog["camera_basic"]["properties"]
    assert catalog["camera_basic"]["properties"]["videoEffectIndex/parameter"]["planned_only_reason"]
    assert catalog["text_basic"]["properties"]["text/format/fontFamilyAndStyle"]["planned_only_reason"]
    assert catalog["text_basic"]["properties"]["text"]["real_write_enabled"] is False
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
    assert catalog["target_basic"]["properties"]["cueTargetID"]["contextual_requirements"] == ["target_ref_resolves"]
    assert catalog["target_basic"]["properties"]["cueTargetName"]["contextual_requirements"] == [
        "target_name_resolution_unsupported"
    ]
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
    cue_values = _base_cue_values(cue_id, cue_type)
    if profile == "group_basic" and prop_name.startswith("playlist/"):
        cue_values["mode"] = 6
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
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
    cue_values = _base_cue_values(cue_id, cue_type)
    if prop_name in {"translation/x", "translation/y"} | VIDEO_PHASE3C_SCALAR_PROPERTIES:
        cue_values[prop_name] = 0
    elif prop_name == "fillStage":
        cue_values[prop_name] = False
    elif prop_name == "fillStyle":
        cue_values[prop_name] = 0
    elif prop_name == "layer":
        cue_values[prop_name] = 10
    elif prop_name == "quaternion":
        cue_values[prop_name] = [0, 0, 0, 1]
    elif prop_name == "resetRotation":
        cue_values["quaternion"] = [0, 0, 0, 1]
    elif prop_name == "blendMode":
        cue_values[prop_name] = "Multiply"
    elif prop_name == "preserveAspectRatio":
        cue_values[prop_name] = True
    elif prop_name == "smooth":
        cue_values[prop_name] = False
    elif prop_name in {"stageID", "audioOutputPatchID", "videoInputPatchID", "audioInputPatchID"}:
        cue_values[prop_name] = "old-id"
    elif profile == "video_basic" and prop_name in {
        "rate",
        "startTime",
        "endTime",
        "playCount",
        "infiniteLoop",
        "preservePitch",
        "holdLastFrame",
    }:
        cue_values.update(
            {
                "rate": 1.0,
                "startTime": 0,
                "endTime": 10,
                "playCount": 1,
                "infiniteLoop": False,
                "preservePitch": True,
                "holdLastFrame": False,
                "audioTrackFormats": [{"channels": 2}],
            }
        )
    elif profile == "video_basic" and prop_name == "sliderLevel":
        cue_values.update(
            {
                "sliderLevels": [0.0, 0.0],
                "audioTrackFormats": [{"channels": 2}],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name == "level":
        cue_values.update(
            {
                "levels": [[0.0, 0.0], [0.0, 0.0]],
                "numChannelsIn": 1,
                "audioTrackFormats": [{"channels": 2}],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name in {"clockType", "doFade", "lockFadeToCue"}:
        cue_values.update(
            {
                "audioTrackFormats": [{"channels": 2}],
                "numChannelsIn": 2,
                "clockType": "video",
                "doFade": False,
                "lockFadeToCue": False,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name in {
        "inputChannelName",
        "gang",
        "mute/channel",
        "solo/channel",
        "mute/channel/clear",
        "solo/channel/clear",
    }:
        cue_values.update(
            {
                "audioTrackFormats": [{"channels": 2}],
                "numChannelsIn": 2,
                "sliderLevels": [0.0, 0.0],
                "levels": [[0.0, 0.0], [0.0, 0.0], [0.0, 0.0]],
                "inputChannelName/2": "R",
                "gang/1/1": "music",
                "muteChannels": [1],
                "soloChannels": [1],
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "video_basic" and prop_name in {
        "sliceMarker/time",
        "sliceMarker/playCount",
        "addSliceMarker",
        "deleteSliceMarker",
        "deleteSliceMarkers",
        "lastSlicePlayCount",
        "lastSliceInfiniteLoop",
    }:
        cue_values.update(
            {
                "sliceMarkers": [{"time": 0.0, "playCount": 1}, {"time": 6.0, "playCount": 2}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        )
    elif profile == "text_basic" and prop_name in PHASE3E_TEXT_BASIC_PROPERTIES:
        cue_values[prop_name] = {
            "text": "Old text",
            "text/format/alignment": "left",
            "text/format/fontSize": 48,
        }[prop_name]
    elif profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES:
        cue_values[prop_name] = PHASE3F_TEXT_STYLE_VALUES[prop_name]
    dry_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
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
        video_phase2_blocked = (
            profile in {"video_basic", "camera_basic", "text_basic"}
            and prop_name not in VIDEO_PHASE2_ALLOWED_PROPERTIES
            and prop_name not in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES
        )
        if video_phase2_blocked:
            assert "blocked even for dry-run by Video-family policy" in dry_result["errors"][prop_name]
            assert dry_client.requests == []
        elif prop_name in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES:
            assert prop_name in dry_result["errors"]
        elif profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES:
            assert "baseline/readback is unavailable" in dry_result["errors"][prop_name]
        else:
            assert "read_before" in dry_result["errors"], (profile, prop_name, dry_result)

    real_client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values=cue_values,
    )
    real_reader = QLabReader(real_client)  # type: ignore[arg-type]
    if profile == "text_basic" and prop_name in PHASE3F_TEXT_STYLE_VALUES:
        real_result = real_reader.update_cue(
            "ws-1",
            cue_id,
            update.get("properties"),
            dry_run=False,
            profile=profile,
            operations=update.get("operations"),
        )
        assert real_result["status"] == "preflight_failed"
        assert real_result["executed_operations"] == []
        assert_no_confirm_token(real_result)
        assert not any(address.endswith(f"/{prop_name}") for address, _, _ in real_client.requests)
    else:
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
    assert result["capabilities"]["batch_update_cues"]["tool"] == "qlab_edit_cues"
    assert result["capabilities"]["batch_update_cues"]["legacy_tool_aliases"] == ["qlab_update_cues"]
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
            text_id: {"type": "Text", "name": "Text old", "text": "Old", "text/format/fontSize": 24},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": memo_id, "profile": "common", "properties": {"name": "Memo new"}},
            {"cue_ref": audio_id, "profile": "audio_basic", "properties": {"rate": 1.1}},
            {"cue_ref": text_id, "profile": "text_basic", "properties": {"name": "Text new"}},
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
    assert all("updateq_plan" not in item for item in result["results"])
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

    valid = reader.update_cues(
        "ws-1",
        [{"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )
    invalid = reader.update_cues(
        "ws-1",
        [{"cue_ref": video_id, "profile": "video_basic", "properties": {"opacity": 80}}],
        dry_run=True,
    )

    assert valid["ok"] is True
    assert valid["results"][0]["status"] == "dry_run"
    assert valid["results"][0]["properties"]["opacity"] == 0.8
    assert invalid["ok"] is False
    assert invalid["results"][0]["status"] == "dry_run_preflight_failed"
    assert invalid["results"][0]["errors"]["validation"] == "opacity must be a number from 0 to 1"


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
    assert result["results"][1]["errors"]["validation"] == "clockType must be exactly audio or video"
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
    assert result["results"][0]["status"] == "dry_run_preflight_failed"
    assert result["results"][1]["status"] == "dry_run_preflight_failed"
    assert "rich text formatting" in result["results"][0]["errors"]["text/format/color"]
    assert result["results"][1]["errors"]["validation"] == "text/format/color.red must be a number from 0 to 1"
    assert "read_before" not in result["results"][1]["errors"]
    assert result["results"][1]["planned_operations"] == []
    assert f"/workspace/ws-1/cue_id/{valid_text_id}/valuesForKeys" not in addresses
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

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playbackPosition": "next"}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["playbackPosition"]
    assert client.requests == []


def test_update_cues_group_basic_real_blocks_playlist_setters_without_playlist_mode() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={group_id: {"type": "Group", "mode": 3, "playlist/crossfade/duration": 3}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": 2.5}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {
        "playlist/crossfade/duration": "Playlist setters require the Group cue to already be in Playlist mode (mode 6)."
    }
    assert all(not request[0].endswith("/playlist/crossfade/duration") for request in client.requests)


def test_update_cues_group_basic_real_allows_playlist_setters_for_playlist_mode() -> None:
    group_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={group_id: {"type": "Group", "mode": 6, "playlist/crossfade/duration": 3}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": group_id, "profile": "group_basic", "properties": {"playlist/crossfade/duration": 2.5}}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["playlist/crossfade/duration"] == 2.5


def test_update_cues_real_blocks_duration_when_cue_duration_is_not_editable() -> None:
    wait_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={wait_id: {"type": "Wait", "duration": 0, "allowsEditingDuration": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": wait_id, "profile": "wait_basic", "properties": {"duration": 3}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"duration": "duration requires a cue with editable duration."}
    assert all(not request[0].endswith("/duration") for request in client.requests)


def test_update_cues_real_allows_duration_when_cue_duration_is_editable() -> None:
    audio_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={audio_id: {"type": "Audio", "duration": 0, "allowsEditingDuration": True}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": audio_id, "profile": "audio_basic", "properties": {"duration": 3}}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["duration"] == 3


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
    assert "updateq_plan" not in result["results"][0]
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
    assert f"/workspace/ws-1/cue_id/{memo_id}/valuesForKeys" not in addresses
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

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["level"]
    assert client.requests == []


def test_update_cues_real_blocks_target_refs_before_osc() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "target_basic", "properties": {"cueTargetID": "target-id"}}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "dry-run only" in result["results"][0]["errors"]["cueTargetID"]
    assert client.requests == []


def test_update_cues_real_blocks_unresolved_target_ref_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}, target_id: {"type": "Memo"}},
        missing_refs={target_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetID": target_id}})

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": target_id},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "cueTargetID target could not be resolved before update."}
    assert all(not request[0].endswith("/cueTargetID") for request in client.requests)


def test_update_cues_real_blocks_self_target_ref_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetID": cue_id}})

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": cue_id},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {"cueTargetID": "cueTargetID target cannot be the cue being updated."}
    assert all(not request[0].endswith("/cueTargetID") for request in client.requests)


def test_update_cues_real_allows_resolved_target_ref_with_gate() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    target_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetID": ""}, target_id: {"type": "Memo"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetID": target_id}})

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetID": target_id},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["cueTargetID"] == target_id


def test_update_cues_real_blocks_target_name_resolution_with_gate_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Start", "cueTargetName": ""}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(
        reader, cue_id, {"profile": "target_basic", "properties": {"cueTargetName": "Target by name"}}
    )

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "target_basic",
                "properties": {"cueTargetName": "Target by name"},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"] == {
        "cueTargetName": "cueTargetName real writes require cueTargetID or cueTargetNumber; name resolution is not supported."
    }
    assert all(not request[0].endswith("/cueTargetName") for request in client.requests)


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


def test_update_cues_verification_accepts_qlab_float_precision() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Audio", "rate": 1.0099999904632568, "startTime": 0.10000000149011612}},
        ignore_set_property=(cue_id, "rate"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "audio_basic",
                "properties": {"rate": 1.01, "startTime": 0.1},
            }
        ],
        dry_run=False,
    )

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
        cues={cue_id: {"type": "Text", "colorName": "RED"}},
        ignore_set_property=(cue_id, "colorName"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "properties": {"colorName": "red"},
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


def test_update_cue_rejects_file_target_symlink_escape(tmp_path: Any) -> None:
    allowed_root = tmp_path / "allowed"
    outside_root = tmp_path / "outside"
    allowed_root.mkdir()
    outside_root.mkdir()
    target = outside_root / "secret.wav"
    target.write_text("secret")
    symlink_path = allowed_root / "linked.wav"
    symlink_path.symlink_to(target)
    client = FakeWriteClient(
        QLabConfig(
            enable_write=True,
            passcode="server-pass",
            allowed_file_roots=(str(allowed_root),),
        ),
        existing_cue_id="11111111-1111-4111-8111-111111111111",
        cue_values={
            "uniqueID": "11111111-1111-4111-8111-111111111111",
            "number": "1",
            "name": "Audio",
            "displayName": "1 Audio",
            "type": "Audio",
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = confirm_token_for(reader, "1", {"properties": {"fileTarget": str(symlink_path)}})

    with pytest.raises(UnsafeWriteOperationError, match="outside QLAB_ALLOWED_FILE_ROOTS"):
        reader.update_cue(
            "ws-1",
            "1",
            {"fileTarget": str(symlink_path)},
            dry_run=False,
            confirm_gates=[token],
        )


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
    assert "updateq_plan" not in result


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

    updates = {
        "text": "New title",
        "fixedWidth": 640,
        "text/format/alignment": "center",
        "text/format/fontName": "Courier New",
        "text/format/fontSize": 56,
    }
    for property_name, value in updates.items():
        result = reader.update_cue(
            "ws-1", cue_id, {property_name: value}, dry_run=True, profile="text_basic"
        )
        assert result["ok"] is True
        assert list(planned_setters(result)) == [property_name]
        assert result["executed_operations"] == []


def test_update_cue_text_font_name_real_write_is_blocked_before_osc() -> None:
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
        timeout_set_property="text/format/fontName",
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="current Video write policy"):
        reader.update_cue(
            "ws-1",
            cue_id,
            {"text/format/fontName": "Courier New"},
            dry_run=False,
            profile="text_basic",
        )

    assert client.requests == []


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


def test_video_phase2c_gate_vectors_doc_preserves_non_mutating_contract() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    doc_path = repo_root / "docs/current/video_phase2c_gate_test_vectors.md"
    if not doc_path.exists():
        doc_path = repo_root / "docs/archive/video/video_phase2c_gate_test_vectors.md"
    doc = doc_path.read_text()

    for required in (
        "No token generation.",
        "No token validation.",
        "No setters.",
        "No real writes.",
        "No runtime QLab.",
        "No `real_write_possible=true`.",
        "No change to current Phase 2 behavior.",
        "`cue_id` | Canonical QLab cue `uniqueID`.",
        "`cue_ref` | Original request reference. Phase 3A still requires UUID-only refs",
        "`reject_opacity_out_of_range`",
        "`reject_opacity_non_finite`",
        "Setter timeout plus readback matches requested value within tolerance: confirmed success with warning.",
        "Setter timeout plus missing or mismatched readback: uncertain failure; no mutating retry.",
        "Video/Camera/Text Phase 2 dry-runs emit no `confirm_token`.",
        "`real_write_possible=false`.",
        "`requires_confirm_token=false`.",
        "`executed_operations=[]`.",
    ):
        assert required in doc


def test_camera_phase2_non_gated_property_emits_no_token_and_fabricated_token_cannot_unlock_real_write() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Camera", "clockType": "video"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    dry_run = reader.update_cue(
        "ws-1", cue_id, {"clockType": "audio"}, dry_run=True, profile="camera_basic"
    )
    setter = planned_setters(dry_run)["clockType"]
    assert_no_confirm_token(dry_run)
    assert "confirm_token" not in setter
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    client.requests.clear()

    real_attempt = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "camera_basic",
                "properties": {"clockType": "audio"},
                "confirm_gates": ["confirm:clockType:fabricated"],
            }
        ],
        dry_run=False,
    )

    assert real_attempt["ok"] is False
    assert "no confirm_token can authorize" in real_attempt["results"][0]["errors"]["clockType"]
    assert_no_confirm_token(real_attempt)
    assert real_attempt["results"][0]["planned_operations"] == []
    assert real_attempt["results"][0]["executed_operations"] == []
    assert client.requests == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "properties", "operations"),
    [
        ("video_basic", "Video", "fileTarget", {"fileTarget": "/tmp/video.mov"}, None),
        (
            "video_basic",
            "Video",
            "translation",
            None,
            [{"property": "translation", "args": {"x": 1, "y": 2}}],
        ),
        ("video_basic", "Video", "stage/name", {"stage/name": "Stage 2"}, None),
        ("camera_basic", "Camera", "cameraPatch", {"cameraPatch": 1}, None),
        (
            "text_basic",
            "Text",
            "text/format",
            None,
            [{"property": "text/format", "args": {"format": {"fontName": "Helvetica"}}}],
        ),
        (
            "text_basic",
            "Text",
            "text/format/color",
            None,
            [
                {
                    "property": "text/format/color",
                    "args": {"red": 1, "green": 1, "blue": 1, "alpha": 1},
                }
            ],
        ),
        (
            "text_basic",
            "Text",
            "text/format/shadowOffset",
            None,
            [{"property": "text/format/shadowOffset", "args": {"width": 1, "height": 2}}],
        ),
        (
            "camera_basic",
            "Camera",
            "videoInputPatchName",
            {"videoInputPatchName": "Patch 1"},
            None,
        ),
        (
            "camera_basic",
            "Camera",
            "videoInputPatchNumber",
            {"videoInputPatchNumber": 1},
            None,
        ),
        (
            "video_basic",
            "Video",
            "videoEffects/add",
            None,
            [{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffects/insert",
            None,
            [{"property": "videoEffects/insert", "args": {"name": "ColorControls", "index": 0}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/delete",
            None,
            [{"property": "videoEffect/delete", "args": {"name": "ColorControls"}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/delete",
            None,
            [{"property": "videoEffectIndex/delete", "args": {"index": 0}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/move",
            None,
            [{"property": "videoEffect/move", "args": {"name": "ColorControls", "newIndex": 1}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/move",
            None,
            [{"property": "videoEffectIndex/move", "args": {"index": 0, "newIndex": 1}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/enabled",
            None,
            [{"property": "videoEffect/enabled", "args": {"name": "ColorControls", "value": True}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/enabled",
            None,
            [{"property": "videoEffectIndex/enabled", "args": {"index": 0, "value": True}}],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/parameter",
            None,
            [
                {
                    "property": "videoEffect/parameter",
                    "args": {"name": "ColorControls", "parameterKey": "inputBrightness", "setting": 0.5},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/parameter",
            None,
            [
                {
                    "property": "videoEffectIndex/parameter",
                    "args": {"index": 0, "parameterKey": "inputBrightness", "setting": 0.5},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffect/parameters",
            None,
            [
                {
                    "property": "videoEffect/parameters",
                    "args": {"name": "ColorControls", "parameters": {"inputBrightness": 0.5}},
                }
            ],
        ),
        (
            "video_basic",
            "Video",
            "videoEffectIndex/parameters",
            None,
            [
                {
                    "property": "videoEffectIndex/parameters",
                    "args": {"index": 0, "parameters": {"inputBrightness": 0.5}},
                }
            ],
        ),
    ],
)
def test_video_phase2_dry_run_rejects_explicitly_blocked_families_before_osc(
    profile: str,
    cue_type: str,
    property_name: str,
    properties: dict[str, Any] | None,
    operations: list[dict[str, Any]] | None,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": cue_type, "videoEffects": []},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    result = reader.update_cue(
        "ws-1",
        cue_id,
        properties,
        dry_run=True,
        profile=profile,
        operations=operations,
    )

    assert result["ok"] is False
    assert result["status"] == "dry_run_preflight_failed"
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)
    if property_name in VIDEO_PHASE4_FX_DRY_RUN_PROPERTIES:
        assert "effect" in result["errors"][property_name].casefold()
        assert any(address.endswith("/valuesForKeys") for address, _, _ in client.requests)
    else:
        assert "blocked even for dry-run by Video-family policy" in result["errors"][property_name]
        assert client.requests == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name"),
    [
        *[
            (profile, cue_type, property_name)
            for profile, cue_type in (
                ("video_basic", "Video"),
                ("camera_basic", "Camera"),
                ("text_basic", "Text"),
            )
            for property_name in VIDEO_PHASE2_REQUESTED_VALUES
            if property_name
            not in {
                "fixedWidth",
                "opacity",
                "text",
                "text/format/alignment",
                "text/format/fontName",
                "text/format/fontSize",
                *PHASE3F_TEXT_STYLE_VALUES,
            }
            and property_name not in {"translation/x", "translation/y"}
            and property_name not in VIDEO_PHASE3C_SCALAR_PROPERTIES
            and property_name not in VIDEO_PHASE3D_APPEARANCE_PROPERTIES
            and property_name != "layer"
            and property_name != "clockType"
        ],
        *[
            ("text_basic", "Text", property_name)
            for property_name in (
                "fixedWidth",
                "text/format/fontName",
            )
        ],
    ],
)
def test_video_phase2_scalar_matrix_plans_normalized_diff_without_token(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    before_value = "Old title" if property_name == "text" else 1
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": cue_type, property_name: before_value},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {property_name: VIDEO_PHASE2_REQUESTED_VALUES[property_name]},
        dry_run=True,
        profile=profile,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    normalized = VIDEO_PHASE2_NORMALIZED_VALUES[property_name]
    assert result["properties"] == {property_name: normalized}
    assert result["before"][property_name] == before_value
    assert result["diff"] == {property_name: {"before": before_value, "requested": normalized}}
    setter = planned_setters(result)[property_name]
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert setter["mode"] == "saved"
    assert setter["risk_tier"] == "high"
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    assert setter["planned_only_reason"] == (
        "video_phase2_text_format_inheritance_risk"
        if property_name == "text"
        else "video_phase2_dry_run_only"
    )
    expected_requirements = {
        "future_versioned_confirm_token",
        "single_cue_single_property",
        "saved_mode",
        "fresh_baseline",
        "exact_readback",
        "manual_rollback_plan",
    }
    assert expected_requirements <= set(setter["future_gate_requirements"])
    assert ("verify_first_character_inherited_format" in setter["future_gate_requirements"]) is (
        property_name == "text"
    )
    assert_no_confirm_token(result)
    assert result["after"] is None
    assert result["executed_operations"] == []


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "before_value", "requested_value"),
    [
        ("text_basic", "Text", "fixedWidth", 500, 640),
    ],
)
def test_video_phase2_success_includes_updateq_plan(
    profile: str,
    cue_type: str,
    property_name: str,
    before_value: Any,
    requested_value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "number": "v1",
            "name": "Fixture cue",
            "type": cue_type,
            property_name: before_value,
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1", cue_id, {property_name: requested_value}, dry_run=True, profile=profile
    )

    plan = result["updateq_plan"]
    assert plan["status"] == "planned"
    assert plan["cue"] == {
        "uniqueID": cue_id,
        "number": "v1",
        "name": "Fixture cue",
        "type": cue_type,
    }
    assert plan["property"] == property_name
    assert plan["profile"] == profile
    assert plan["mode"] == "saved"
    assert plan["before"] == before_value
    assert plan["requested"] == requested_value
    assert plan["diff"] == {"before": before_value, "requested": requested_value}
    assert plan["risk_tier"] == "high"
    assert plan["real_write_enabled"] is False
    assert plan["real_write_possible"] is False
    assert plan["requires_confirm_token"] is False
    assert plan["why_not_written"]
    assert plan["safety"] == {
        "no_live": True,
        "no_playback": True,
        "no_workspace_video_write": True,
        "no_executed_operations": True,
        "will_modify_qlab": False,
    }
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("cue_state", "error_key"),
    [
        ({"isBroken": True}, "health"),
        ({"isWarning": True}, "health"),
        ({"isRunning": True}, "active"),
        ({"isPaused": True}, "active"),
        ({"isAuditioning": True}, "active"),
    ],
)
def test_video_phase2_dry_run_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any], error_key: str
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1, **cue_state},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cue(
        "ws-1", cue_id, {"opacity": 0.8}, dry_run=True, profile="video_basic"
    )

    assert result["ok"] is False
    assert error_key in result["errors"]
    assert result["planned_operations"] == []
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)


def test_video_phase2_disarmed_cue_is_notice_not_blocker() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "scale/x": 1, "armed": False},
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1", cue_id, {"scale/x": 0.8}, dry_run=True, profile="video_basic"
    )

    assert result["ok"] is True
    assert result["notices"] == ["cue_disarmed"]
    assert result["executed_operations"] == []
    assert result["updateq_plan"]["notices"] == ["cue_disarmed"]
    assert "playback readiness" in result["updateq_plan"]["notice_explanations"]["cue_disarmed"]
    assert result["updateq_plan"]["safety"]["will_modify_qlab"] is False
    setter = planned_setters(result)["scale/x"]
    assert setter["confirm_token"].startswith("confirm:videoScalar:v1:")
    assert setter["real_write_possible"] is True


def _phase3_opacity_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    baseline: float = 1.0,
    requested: float = 0.8,
    ignore_readback: bool = False,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "opacity": baseline}},
        ignore_set_property=(cue_id, "opacity") if ignore_readback else None,
        timeout_set_property=(cue_id, "opacity") if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": profile, "properties": {"opacity": requested}}
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase3a_opacity_dry_run_candidate_emits_confirm_token(profile: str, cue_type: str) -> None:
    client, reader, cue_id, update, _ = _phase3_opacity_fixture(profile=profile, cue_type=cue_type)
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["opacity"]
    payload, error = write_operations._decode_phase3_video_opacity_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["phase3_video_opacity_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"] == "video_opacity_requires_confirm_token"
    assert setter["confirm_token"].startswith("confirm:videoOpacity:v1:")
    assert plan["results"][0]["updateq_plan"]["real_write_possible"] is True
    assert plan["results"][0]["updateq_plan"]["requires_confirm_token"] is True
    assert plan["results"][0]["updateq_plan"]["intent"] == (
        f"Preview saved opacity change on {cue_type} cue."
    )
    assert plan["results"][0]["updateq_plan"]["safety"]["no_executed_operations"] is True
    assert plan["results"][0]["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert plan["results"][0]["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3_opacity_write"
    assert payload["cue_id"] == cue_id
    assert payload["cue_ref"] == cue_id
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == "opacity"
    assert payload["mode"] == "saved"
    assert payload["baseline"] == 1.0
    assert payload["requested"] == 0.8
    assert payload["risk_tier"] == "high"
    assert payload["capability_gate"] == "video_visual"
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase3a_opacity_real_write_with_token_sets_once_and_verifies(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture(
        profile=profile,
        cue_type=cue_type,
    )

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    address = f"/workspace/ws-1/cue_id/{cue_id}/opacity"
    item = result["results"][0]
    setter = planned_setters(item)["opacity"]
    plan = item["updateq_plan"]
    assert result["status"] == "updated"
    assert item["after"]["opacity"] == 0.8
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["operations"][0]["real_write_enabled"] is True
    assert item["operations"][0]["real_write_possible"] is True
    assert item["operations"][0]["requires_confirm_token"] is True
    assert "planned_only_reason" not in item["operations"][0]
    assert plan["status"] == "updated"
    assert plan["real_write_enabled"] is True
    assert plan["real_write_possible"] is True
    assert plan["requires_confirm_token"] is True
    assert plan["intent"] == f"Executed saved opacity change on {cue_type} cue."
    assert "why_not_written" not in plan
    assert plan["safety"]["no_executed_operations"] is False
    assert plan["safety"]["will_modify_qlab"] is True
    assert plan["safety"]["no_live"] is True
    assert plan["safety"]["no_playback"] is True
    assert plan["safety"]["no_workspace_video_write"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any(
        forbidden in address.casefold()
        for address, _, _ in client.requests
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview", "/live")
    )


def test_phase3a_opacity_token_cannot_authorize_other_value_workspace_or_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"opacity": 0.7}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    wrong_workspace_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        workspace_id="ws-2",
    )
    wrong_workspace = QLabReader(wrong_workspace_client).update_cues(  # type: ignore[arg-type]
        "ws-2", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.cues[cue_id]["opacity"] = 0.9
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_workspace["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_video_opacity_baseline" in stale["results"][0]["errors"]["opacity"]
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)
    assert not any(address.endswith("/opacity") for address, _, _ in wrong_workspace_client.requests)


@pytest.mark.parametrize("token_mutator", [
    lambda token: "not-a-token",
    lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
    lambda token: token.replace(":v1:", ":v2:", 1),
])
def test_phase3a_opacity_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3_opacity_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


def test_phase3a_opacity_real_attempt_requires_uuid_single_property_and_token() -> None:
    client, reader, cue_id, update, token = _phase3_opacity_fixture()
    client.cue_numbers["1"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "1", "confirm_gates": [token]}],
        [{**update, "properties": {"opacity": 0.8, "translation/x": 1}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/opacity") for address, _, _ in client.requests)


def test_phase3a_opacity_setter_timeout_with_matching_readback_is_updated_warning() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        timeout_set_property=(cue_id, "opacity"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    item = result["results"][0]
    setter = planned_setters(item)["opacity"]
    assert item["status"] == "updated"
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["verification"]["readback_matched"] is True
    assert item["updateq_plan"]["safety"]["no_executed_operations"] is False
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert item["executed_operations"][0]["status"] == "timeout_pending_verification"


def test_phase3a_opacity_setter_timeout_mismatch_is_uncertain_failure_no_retry() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "opacity": 1.0}},
        timeout_set_property=(cue_id, "opacity"),
        timeout_without_apply=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])["opacity"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "partial_failed"
    assert result["timeout_confirmed_count"] == 0
    assert result["results"][0]["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/opacity")]) == 1


@pytest.mark.parametrize("value", [-0.1, 1.1, float("nan"), float("inf"), float("-inf")])
def test_phase3a_opacity_rejects_out_of_range_and_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    reader = QLabReader(  # type: ignore[arg-type]
        FakeWriteClient(
            QLabConfig(enable_write=False, passcode=None),
            existing_cue_id=cue_id,
            cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1},
        )
    )

    with pytest.raises(UnsafeWriteOperationError, match="opacity must be a number from 0 to 1"):
        reader.update_cue("ws-1", cue_id, {"opacity": value}, dry_run=True, profile="video_basic")


def _phase3b_translation_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "translation/x",
    baseline: float = 10.0,
    requested: float = 20.0,
    timeout: bool = False,
    timeout_without_apply: bool = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
        ignore_set_property=(cue_id, property_name) if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name"),
    [
        (profile, cue_type, property_name)
        for profile, cue_type in (
            ("video_basic", "Video"),
            ("camera_basic", "Camera"),
            ("text_basic", "Text"),
        )
        for property_name in ("translation/x", "translation/y")
    ],
)
def test_phase3b_translation_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, _ = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase3_video_translation_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoTranslation:v1:")
    assert setter["phase3b_video_translation_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert item["updateq_plan"]["real_write_possible"] is True
    assert item["updateq_plan"]["requires_confirm_token"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert payload == {
        "version": 1,
        "operation_kind": "video_phase3b_translation_write",
        "workspace_id": "ws-1",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "cue_type": cue_type,
        "profile": profile,
        "property": property_name,
        "path": property_name,
        "mode": "saved",
        "baseline": 10.0,
        "baseline_sha256": write_operations._video_translation_sha256(10.0),
        "requested": 20.0,
        "risk_tier": "high",
        "capability_gate": "video_visual",
        "mcp_secret_version": 1,
    }
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name"),
    [
        (profile, cue_type, property_name)
        for profile, cue_type in (
            ("video_basic", "Video"),
            ("camera_basic", "Camera"),
            ("text_basic", "Text"),
        )
        for property_name in ("translation/x", "translation/y")
    ],
)
def test_phase3b_translation_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    plan = item["updateq_plan"]
    assert result["status"] == "updated"
    assert item["after"][property_name] == 20.0
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert plan["status"] == "updated"
    assert plan["real_write_enabled"] is True
    assert plan["real_write_possible"] is True
    assert plan["requires_confirm_token"] is True
    assert plan["intent"] == f"Executed saved {property_name} change on {cue_type} cue."
    assert plan["safety"]["no_executed_operations"] is False
    assert plan["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3b_translation_token_rejects_context_mismatch_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"translation/x": 21.0}, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_axis = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "properties": {"translation/y": 20.0},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )
    client.cues[cue_id]["translation/x"] = 11.0
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_workspace_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "translation/x": 10.0}},
        workspace_id="ws-2",
    )
    wrong_workspace = QLabReader(wrong_workspace_client).update_cues(  # type: ignore[arg-type]
        "ws-2",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_axis["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert wrong_workspace["status"] == "preflight_failed"
    assert "stale_video_translation_baseline" in stale["results"][0]["errors"]["translation/x"]
    assert not any(
        address.endswith(("/translation/x", "/translation/y"))
        for address, _, _ in client.requests
    )
    assert not any(
        address.endswith("/translation/x")
        for address, _, _ in wrong_workspace_client.requests
    )


def test_phase3b_translation_token_rejects_wrong_cue_profile_and_type() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    other_cue_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_cue_id] = {
        "uniqueID": other_cue_id,
        "type": "Video",
        "translation/x": 10.0,
    }
    wrong_cue = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": other_cue_id, "confirm_gates": [token]}],
        dry_run=False,
    )
    wrong_profile = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_cue["status"] == "preflight_failed"
    assert wrong_profile["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert all(
        item["executed_operations"] == []
        for result in (wrong_cue, wrong_profile, wrong_type)
        for item in result["results"]
    )
    assert not any(
        address.endswith("/translation/x")
        for address, _, _ in client.requests
    )


def test_phase3b_translation_token_is_bound_to_camera_type_and_profile() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture(
        profile="camera_basic",
        cue_type="Camera",
    )
    client.cues[cue_id]["type"] = "Text"

    result = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "profile": "text_basic",
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert "does not match" in result["results"][0]["errors"]["translation/x"]
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3b_translation_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3b_translation_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


def test_phase3b_translation_real_attempt_requires_video_uuid_single_saved_property() -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [
            {
                **update,
                "properties": {"translation/x": 20.0, "translation/y": 30.0},
                "confirm_gates": [token],
            }
        ],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {
                        "property": "translation/x",
                        "args": {"value": 20.0},
                        "mode": "live",
                    }
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3b_translation_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3b_translation_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/translation/x") for address, _, _ in client.requests)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_phase3b_translation_rejects_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "translation/x": 10.0}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "properties": {"translation/x": value},
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3b_translation_setter_timeout_matching_readback_is_updated_warning(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
        timeout=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["verification"]["readback_matched"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True


def test_phase3b_translation_setter_timeout_mismatch_is_uncertain_no_retry() -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert result["timeout_confirmed_count"] == 0
    assert len(
        [address for address, _, _ in client.requests if address.endswith("/translation/x")]
    ) == 1


def test_phase3b_translation_normal_setter_readback_mismatch_fails_without_retry() -> None:
    client, reader, _, update, token = _phase3b_translation_fixture(ignore_readback=True)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "verification_failed"
    assert len(
        [address for address, _, _ in client.requests if address.endswith("/translation/x")]
    ) == 1


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3b_translation_rollback_requires_new_token(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, forward_token = _phase3b_translation_fixture(
        profile=profile,
        cue_type=cue_type,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"translation/x": 10.0}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["translation/x"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["translation/x"] == 10.0


PHASE3C_SCALAR_CASES = [
    (profile, cue_type, property_name)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name in (
        "scale/x",
        "scale/y",
        "anchor/x",
        "anchor/y",
        "cropTop",
        "cropBottom",
        "cropLeft",
        "cropRight",
    )
]


def _phase3c_scalar_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "scale/x",
    baseline: float = 1.0,
    requested: float = 1.25,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("profile", "cue_type", "property_name"), PHASE3C_SCALAR_CASES)
def test_phase3c_scalar_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, _ = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase3_video_scalar_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoScalar:v1:")
    assert setter["phase3c_video_scalar_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is False
    assert payload["operation_kind"] == "video_phase3c_scalar_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["path"] == property_name
    assert payload["baseline"] == 1.0
    assert payload["requested"] == 1.25
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("profile", "cue_type", "property_name"), PHASE3C_SCALAR_CASES)
def test_phase3c_scalar_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
) -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    assert result["status"] == "updated"
    assert item["after"][property_name] == 1.25
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3c_scalar_token_rejects_wrong_property_type_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    wrong_property = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"scale/y": 1.25}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Video"
    client.cues[cue_id]["scale/x"] = 1.1
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_property["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    stale_item = stale["results"][0]
    assert "stale_video_scalar_baseline" in stale_item["errors"]["scale/x"]
    assert stale_item["operations"][0]["planned_only_reason"] == "video_scalar_requires_confirm_token"
    assert "Video Phase 2" not in stale_item["updateq_plan"]["intent"]
    assert not any(address.endswith(("/scale/x", "/scale/y")) for address, _, _ in client.requests)


def test_phase3c_scalar_token_cannot_cross_camera_and_text() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture(
        profile="camera_basic",
        cue_type="Camera",
    )
    client.cues[cue_id]["type"] = "Text"

    result = reader.update_cues(
        "ws-1",
        [{**update, "profile": "text_basic", "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3c_scalar_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


def test_phase3c_scalar_real_attempt_requires_uuid_single_saved_property() -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [
            {
                **update,
                "properties": {"scale/x": 1.25, "scale/y": 1.25},
                "confirm_gates": [token],
            }
        ],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "scale/x", "args": {"value": 1.25}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3c_scalar_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3c_scalar_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/scale/x") for address, _, _ in client.requests)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_phase3c_scalar_rejects_non_finite_values(value: float) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "scale/x": 1.0}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "properties": {"scale/x": value},
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3c_scalar_timeout_matching_readback_is_updated_warning(
    profile: str,
    cue_type: str,
) -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
        timeout=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    assert result["status"] == "updated"
    assert result["timeout_confirmed_count"] == 1
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert item["updateq_plan"]["verification"]["readback_matched"] is True


def test_phase3c_scalar_timeout_mismatch_is_uncertain_no_retry() -> None:
    client, reader, _, update, token = _phase3c_scalar_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/scale/x")]) == 1


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_phase3c_scalar_rollback_requires_new_token(profile: str, cue_type: str) -> None:
    client, reader, _, update, forward_token = _phase3c_scalar_fixture(
        profile=profile,
        cue_type=cue_type,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"scale/x": 1.0}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["scale/x"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["scale/x"] == 1.0


PHASE3D_APPEARANCE_CASES = [
    (profile, cue_type, property_name, baseline, requested)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name, baseline, requested in (
        ("blendMode", "Normal", "Multiply"),
        ("preserveAspectRatio", True, False),
    )
]

OFFICIAL_BLEND_MODE_NAMES = [
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
]


def test_phase3d_blend_mode_allows_official_full_name_strings_only() -> None:
    assert list(QLAB_BLEND_MODES.values()) == OFFICIAL_BLEND_MODE_NAMES

    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    for mode in OFFICIAL_BLEND_MODE_NAMES:
        valid = reader.update_cues(
            "ws-1",
            [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": mode}}],
            dry_run=True,
        )
        assert valid["status"] == "dry_run"
        assert valid["results"][0]["properties"]["blendMode"] == mode


@pytest.mark.parametrize("bad_value", [1, 1.0, True, False, None, [], {}, "screen", " Screen ", "Scr", "Screen-ish", ""])
def test_phase3d_blend_mode_rejects_non_official_values(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert result["results"][0]["planned_operations"] == []


def test_phase3d_blend_mode_rejects_old_case_insensitive_canonicalization() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Video", "blendMode": "Normal"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"blendMode": " screen "}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def _phase3d_appearance_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "blendMode",
    baseline: Any = "Normal",
    requested: Any = "Multiply",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE3D_APPEARANCE_CASES,
)
def test_phase3d_appearance_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase3d_appearance_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase3_video_appearance_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAppearance:v1:")
    assert setter["phase3d_video_appearance_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3d_appearance_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE3D_APPEARANCE_CASES,
)
def test_phase3d_appearance_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3d_appearance_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAppearance:v1:fake"]}],
        [{**update, "properties": {"preserveAspectRatio": False}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"blendMode": "Multiply", "opacity": 0.5}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "blendMode", "args": {"value": "Multiply"}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/blendMode", "/preserveAspectRatio")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase3d_appearance_tampered_token_rejects_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase3d_appearance_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in client.requests)


def test_phase3d_appearance_rejects_wrong_type_profile_cue_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {"type": "Video", "blendMode": "Normal"}
    wrong_cue = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": other_id, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Camera"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "profile": "camera_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id].update({"type": "Video", "blendMode": "Screen"})
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_cue["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_video_appearance_baseline" in stale["results"][0]["errors"]["blendMode"]
    assert all(
        item["executed_operations"] == []
        for result in (wrong_cue, wrong_type, stale)
        for item in result["results"]
    )


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3d_appearance_rejects_unhealthy_or_active_cue(cue_state: dict[str, Any]) -> None:
    client, reader, cue_id, update, token = _phase3d_appearance_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in client.requests)


def test_phase3d_appearance_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase3d_appearance_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"blendMode": "Normal"}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["blendMode"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["blendMode"] == "Normal"


def test_phase3d_appearance_timeout_mismatch_is_uncertain_no_retry() -> None:
    client, reader, _, update, token = _phase3d_appearance_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/blendMode")]) == 1


PHASE7_GEOMETRY_CASES = [
    (profile, cue_type, property_name, baseline, requested)
    for profile, cue_type in (
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    )
    for property_name, baseline, requested in (
        ("fillStage", False, True),
        ("fillStyle", 0, 1),
        ("layer", 10, 11),
        ("quaternion", [0, 0, 0, 1], [0, 0, 0.1, 0.995]),
        ("smooth", False, True),
    )
]


def _phase7_geometry_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "fillStage",
    baseline: Any = False,
    requested: Any = True,
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def _phase7_reset_rotation_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    baseline: list[int | float] | None = None,
    timeout: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    baseline = baseline or [0, 0, 0.1, 0.995]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "quaternion": baseline}},
        timeout_set_property=(cue_id, "resetRotation") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {"resetRotation": True},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["resetRotation"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase3d_blend_mode_token_boundaries_reject_fx_and_geometry_tokens() -> None:
    appearance_client, appearance_reader, _, appearance_update, appearance_token = _phase3d_appearance_fixture()
    _, _, _, _, geometry_token = _phase7_geometry_fixture(property_name="fillStage")

    fx_cue_id = "11111111-1111-4111-8111-111111111111"
    fx_client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={
            fx_cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    fx_reader = QLabReader(fx_client)  # type: ignore[arg-type]
    fx_update = {
        "cue_ref": fx_cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    fx_plan = fx_reader.update_cues("ws-1", [fx_update], dry_run=True)
    fx_token = planned_setters(fx_plan["results"][0])["videoEffectIndex/parameter"]["confirm_token"]

    for wrong_token in (geometry_token, fx_token):
        result = appearance_reader.update_cues(
            "ws-1",
            [{**appearance_update, "confirm_gates": [wrong_token]}],
            dry_run=False,
        )
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    geometry_client, geometry_reader, _, geometry_update, _ = _phase7_geometry_fixture(property_name="fillStage")
    wrong_family = geometry_reader.update_cues(
        "ws-1",
        [{**geometry_update, "confirm_gates": [appearance_token]}],
        dry_run=False,
    )

    assert wrong_family["status"] == "preflight_failed"
    assert wrong_family["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/blendMode") for address, _, _ in appearance_client.requests)
    assert not any(address.endswith("/fillStage") for address, _, _ in geometry_client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE7_GEOMETRY_CASES,
)
def test_phase7_geometry_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase7_geometry_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase7_video_geometry_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    expected_version = (
        4 if property_name == "smooth" else 3 if property_name == "quaternion" else 2 if property_name == "layer" else 1
    )
    assert setter["confirm_token"].startswith(f"confirm:videoGeometry:v{expected_version}:")
    assert setter["phase7_video_geometry_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert setter["args"] == (requested if property_name == "quaternion" else [requested])
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase7_geometry_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["version"] == expected_version
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type", "property_name", "baseline", "requested"),
    PHASE7_GEOMETRY_CASES,
)
def test_phase7_geometry_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase7_geometry_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase7_geometry_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase7_geometry_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoGeometry:v1:fake"]}],
        [{**update, "properties": {"fillStyle": 1}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"fillStage": True, "opacity": 0.5}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [
                    {"property": "fillStage", "args": {"value": True}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/fillStage", "/fillStyle")) for address, _, _ in client.requests)


def test_phase7b_layer_rejects_v1_token_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    layer_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {"layer": 11},
    }

    result = reader.update_cues(
        "ws-1",
        [{**layer_update, "confirm_gates": [v1_token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/layer") for address, _, _ in client.requests)


def test_phase7d_quaternion_rejects_v1_v2_and_v3_cross_tokens_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0, 1]
    quaternion_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {"quaternion": [0, 0, 0.1, 0.995]},
    }
    v3_plan = reader.update_cues("ws-1", [quaternion_update], dry_run=True)
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]

    cases = [
        {**quaternion_update, "confirm_gates": [v1_token]},
        {**quaternion_update, "confirm_gates": [v2_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [v3_token]},
    ]
    client.requests.clear()

    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/quaternion", "/fillStage", "/layer")) for address, _, _ in client.requests)


def test_phase7f_smooth_rejects_old_geometry_tokens_before_setter() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0, 1]
    v3_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [0, 0, 0.1, 0.995]}}],
        dry_run=True,
    )
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]
    client.cues[cue_id]["smooth"] = False
    smooth_update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": True}}
    v4_plan = reader.update_cues("ws-1", [smooth_update], dry_run=True)
    v4_token = planned_setters(v4_plan["results"][0])["smooth"]["confirm_token"]
    client.requests.clear()

    cases = [
        {**smooth_update, "confirm_gates": [v1_token]},
        {**smooth_update, "confirm_gates": [v2_token]},
        {**smooth_update, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [v4_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [v4_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [0, 0, 0.1, 0.995]}, "confirm_gates": [v4_token]},
    ]
    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/smooth", "/fillStage", "/layer", "/quaternion")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [None, 1, 0, "true", [], {}])
def test_phase7f_smooth_invalid_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "smooth": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/smooth") for address, _, _ in client.requests)


PHASE8_IO_CASES = [
    ("video_basic", "Video", "stageID", "stage-old", "stage-new"),
    ("video_basic", "Video", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("camera_basic", "Camera", "stageID", "stage-old", "stage-new"),
    ("camera_basic", "Camera", "audioOutputPatchID", "audio-out-old", "audio-out-new"),
    ("camera_basic", "Camera", "videoInputPatchID", "video-in-old", "video-in-new"),
    ("camera_basic", "Camera", "audioInputPatchID", "audio-in-old", "audio-in-new"),
    ("text_basic", "Text", "stageID", "stage-old", "stage-new"),
]


def _phase8_io_fixture(
    *,
    profile: str = "video_basic",
    cue_type: str = "Video",
    property_name: str = "stageID",
    baseline: str = "stage-old",
    requested: str = "stage-new",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {property_name: requested},
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("profile", "cue_type", "property_name", "baseline", "requested"), PHASE8_IO_CASES)
def test_phase8a_video_io_dry_run_emits_bound_token(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: str,
    requested: str,
) -> None:
    client, reader, cue_id, update, _ = _phase8_io_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase8_video_io_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoIO:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8_io_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert payload["workspace_validation"] == "post_write_fresh_readback_required"
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("profile", "cue_type", "property_name", "baseline", "requested"), PHASE8_IO_CASES)
def test_phase8a_video_io_real_write_sets_once_and_verifies(
    profile: str,
    cue_type: str,
    property_name: str,
    baseline: str,
    requested: str,
) -> None:
    client, reader, cue_id, update, token = _phase8_io_fixture(
        profile=profile,
        cue_type=cue_type,
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": property_name, "value": baseline}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase8a_video_io_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8_io_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoIO:v1:fake"]}],
        [{**update, "properties": {"stageID": "stage-other"}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"stageID": "stage-new", "smooth": False}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"smooth": False}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/stageID", "/smooth")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [None, 1, True, "", "none", [], {}])
def test_phase8a_video_io_invalid_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "stageID": "stage-old"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"stageID": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/stageID") for address, _, _ in client.requests)


def test_phase8a_video_io_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase8_io_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**update, "properties": {"stageID": "stage-old"}}
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["stageID"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["stageID"] == "stage-old"


def test_phase8a_stageid_disconnected_stage_warns_but_still_plans() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "stageID": "stage-old"}},
        video_stages=[{"uniqueID": "stage-new", "name": "Stage 2"}],
        video_stage_regions={
            "stage-new": [
                {"name": "A", "route": {"name": "Output 2", "connected": False, "device": {"present": False}}}
            ]
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-new"}}],
        dry_run=True,
    )

    item = result["results"][0]
    setter = planned_setters(item)["stageID"]
    assert result["status"] == "dry_run"
    assert setter["confirm_token"].startswith("confirm:videoIO:v1:")
    assert setter["warning_metadata"]["code"] == "stage_route_disconnected"
    assert "stage_route_disconnected" in item["notices"]
    assert any("currently disconnected" in warning for warning in item["warnings"])


def test_phase8a_stageid_broken_after_write_allows_exact_recovery_rollback_only() -> None:
    write_operations._PHASE8_STAGEID_RECOVERY_BASELINES.clear()
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "stageID": "stage-old", "isBroken": False}},
        broken_stage_ids={"stage-bad"},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    forward_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-bad"}}
    forward_plan = reader.edit_cues("ws-1", [forward_update], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["stageID"]["confirm_token"]
    forward = reader.edit_cues("ws-1", [{**forward_update, "confirm_gates": [forward_token]}], dry_run=False)

    wrong_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-third"}}
    wrong = reader.edit_cues("ws-1", [wrong_update], dry_run=True)
    rollback_update = {"cue_ref": cue_id, "profile": "text_basic", "properties": {"stageID": "stage-old"}}
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["stageID"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "stageid_write_result_is_broken" in forward["results"][0]["warnings"]
    assert wrong["status"] == "preflight_failed"
    assert wrong["results"][0]["executed_operations"] == []
    assert rollback_plan["status"] == "dry_run"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["stageID"] == "stage-old"
    assert rollback["results"][0]["after"]["isBroken"] is False


PHASE8B_VIDEO_AUDIO_TIME_CASES = [
    ("startTime", 0, 0.5),
    ("endTime", 10, 9.5),
    ("playCount", 1, 2),
    ("infiniteLoop", False, True),
    ("rate", 1.0, 1.25),
    ("preservePitch", True, False),
    ("holdLastFrame", False, True),
]


def _phase8b_video_audio_time_fixture(
    *,
    property_name: str = "rate",
    baseline: Any = 1.0,
    requested: Any = 1.25,
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue_values: dict[str, Any] = {"type": cue_type, property_name: baseline}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, property_name) if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "properties": {property_name: requested},
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("property_name", "baseline", "requested"), PHASE8B_VIDEO_AUDIO_TIME_CASES)
def test_phase8b_video_audio_time_dry_run_emits_bound_token(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase8b_video_audio_time_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase8b_video_audio_time_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioTime:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8b_audio_time_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == property_name
    assert payload["baseline"] == baseline
    assert payload["requested"] == requested
    assert payload["workspace_validation"] == "post_write_fresh_readback_required"
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(("property_name", "baseline", "requested"), PHASE8B_VIDEO_AUDIO_TIME_CASES)
def test_phase8b_video_audio_time_real_write_sets_once_and_verifies(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": property_name, "value": baseline}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize(("baseline", "requested", "readback"), [(0, True, 1), (1, False, 0)])
def test_phase8b_preserve_pitch_accepts_numeric_qlab_readback(
    baseline: int,
    requested: bool,
    readback: int,
) -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture(
        property_name="preservePitch",
        baseline=baseline,
        requested=requested,
    )
    client.numeric_bool_readback_properties.add("preservePitch")
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    payload, error = write_operations._decode_phase8b_video_audio_time_confirm_token(
        planned_setters(plan["results"][0])["preservePitch"]["confirm_token"]
    )
    assert error is None
    assert payload["baseline"] is bool(baseline)
    assert payload["requested"] is requested

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["preservePitch"] == readback


def test_phase8b_preserve_pitch_rejects_invalid_numeric_baseline() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "preservePitch": 2, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"preservePitch": True}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


def test_phase8b_video_audio_time_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8b_video_audio_time_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, appearance_update, appearance_token = _phase3d_appearance_fixture()
    _, _, _, io_update, io_token = _phase8_io_fixture(property_name="audioOutputPatchID")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioTime:v1:fake"]}],
        [{**update, "properties": {"rate": 1.5}, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"rate": 1.25, "playCount": 2}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {"rate": 1.25}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [appearance_token]}],
        [{**update, "confirm_gates": [io_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**appearance_update, "confirm_gates": [token]}],
        [{**io_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith(("/rate", "/playCount", "/smooth", "/blendMode", "/audioOutputPatchID")) for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "bad_value"),
    [
        ("rate", 0),
        ("rate", math.nan),
        ("rate", math.inf),
        ("startTime", -0.1),
        ("endTime", math.nan),
        ("playCount", 0),
        ("playCount", 1.5),
        ("infiniteLoop", 1),
        ("preservePitch", "true"),
        ("preservePitch", 0),
        ("preservePitch", 1),
        ("holdLastFrame", None),
    ],
)
def test_phase8b_video_audio_time_invalid_values_reject_before_setter(property_name: str, bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    baseline = False if property_name in {"infiniteLoop", "holdLastFrame"} else True if property_name == "preservePitch" else 1
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", property_name: baseline, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {property_name: bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_phase8b_video_audio_time_requires_embedded_audio_evidence_for_audio_routes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "rate": 1.0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"rate": 1.25}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["rate"] == "Phase 8B Video audio time requires readable embedded-audio evidence."
    assert_no_confirm_token(result)


@pytest.mark.parametrize("cue_type", ["Text", "Camera", "Audio"])
def test_phase8b_video_audio_time_rejects_wrong_cue_type(cue_type: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "rate": 1.0, "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"rate": 1.25}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/rate") for address, _, _ in client.requests)


def test_phase8b_video_audio_time_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase8b_video_audio_time_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**update, "properties": {"rate": 1.0}}
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["rate"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["rate"] == 1.0


def test_phase8b_end_time_setter_error_matching_readback_is_updated_warning() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "endTime": 10, "audioTrackFormats": [{"channels": 2}]}},
        error_after_apply_properties={(cue_id, "endTime")},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"endTime": 9.5}}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["endTime"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["endTime"] == 9.5
    assert result["results"][0]["errors"] is None
    assert "setter_error_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8b_end_time_setter_error_mismatched_readback_fails() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "endTime": 10, "audioTrackFormats": [{"channels": 2}]}},
        fail_set_property=(cue_id, "endTime"),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"endTime": 9.5}}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["endTime"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "partial_failed"
    assert result["results"][0]["after"]["endTime"] == 10
    assert result["results"][0]["errors"]["endTime"]


def _phase9a_video_audio_level_fixture(
    *,
    channel: int = 0,
    baseline: float = 0.0,
    requested: float = -1.0,
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
    slider_levels: list[Any] | None = None,
    num_channels_in: int | None = None,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    levels = list(slider_levels) if slider_levels is not None else [baseline, 0.0]
    cue_values: dict[str, Any] = {"type": cue_type, "sliderLevels": levels}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    if num_channels_in is not None:
        cue_values["numChannelsIn"] = num_channels_in
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, f"sliderLevel/{channel}") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "sliderLevel", "args": {"channel": channel, "decibel": requested}}],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["sliderLevel"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase9a_video_audio_level_dry_run_emits_bound_token() -> None:
    client, reader, cue_id, update, _ = _phase9a_video_audio_level_fixture(channel=0, baseline=0.0, requested=-1.0)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)["sliderLevel"]
    payload, error = write_operations._decode_phase9a_video_audio_level_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioLevels:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/0"
    assert setter["args"] == [-1.0]
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase9a_audio_level_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == "sliderLevel"
    assert payload["channel"] == 0
    assert payload["baseline"] == 0.0
    assert payload["requested"] == -1.0
    assert payload["workspace_validation"] == "post_write_fresh_sliderLevels_readback_required"
    assert not any(address.endswith("/sliderLevel/0") for address, _, _ in client.requests)


def test_phase9a_video_audio_level_accepts_num_channels_audio_evidence() -> None:
    client, reader, _, update, _ = _phase9a_video_audio_level_fixture(audio_evidence=False, num_channels_in=2)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    setter = planned_setters(result["results"][0])["sliderLevel"]
    assert setter["confirm_token"].startswith("confirm:videoAudioLevels:v1:")
    assert setter["real_write_possible"] is True
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/sliderLevel/0") for address, _, _ in client.requests)


def test_phase9a_video_audio_level_real_write_sets_once_and_verifies_channel_readback() -> None:
    client, reader, cue_id, update, token = _phase9a_video_audio_level_fixture(
        channel=1,
        baseline=0.0,
        requested=-1.5,
        slider_levels=[0.0, 0.0],
    )

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)["sliderLevel"]
    address = f"/workspace/ws-1/cue_id/{cue_id}/sliderLevel/1"
    assert result["status"] == "updated"
    assert item["after"]["sliderLevels"] == [0.0, -1.5]
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {"property": "sliderLevel", "args": {"channel": 1, "decibel": 0.0}}
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)
    assert not any("/level/" in request[0] for request in client.requests)
    assert not any(request[0].endswith(("/setDefaultLevels", "/setSilentLevels")) for request in client.requests)


def test_phase9a_video_audio_level_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase9a_video_audio_level_fixture()
    _, _, _, time_update, time_token = _phase8b_video_audio_time_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, io_update, io_token = _phase8_io_fixture(property_name="audioOutputPatchID")
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioLevels:v1:fake"]}],
        [{**update, "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -2.0}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "rate", "args": 1.25}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio_basic", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [time_token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [io_token]}],
        [{**time_update, "confirm_gates": [token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**io_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/sliderLevel/" in address or address.endswith(("/rate", "/smooth", "/audioOutputPatchID")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [True, "0", "-inf", math.nan, math.inf, None, [], {}])
def test_phase9a_video_audio_level_invalid_decibels_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0], "audioTrackFormats": [{"channels": 2}]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": bad_value}}],
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/sliderLevel/" in address for address, _, _ in client.requests)


def test_phase9a_video_audio_level_rejects_missing_evidence_and_unreadable_channel() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    no_evidence = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )
    channel_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "sliderLevels": [0.0], "audioTrackFormats": [{"channels": 2, "format": "AAC"}]}},
    )
    channel_reader = QLabReader(channel_client)  # type: ignore[arg-type]
    missing_channel = channel_reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 1, "decibel": -1.0}}]}],
        dry_run=True,
    )

    assert no_evidence["status"] == "preflight_failed"
    assert no_evidence["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable embedded-audio evidence."
    client.cues[cue_id]["levels"] = [[0.0]]
    levels_only = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )
    assert levels_only["status"] == "preflight_failed"
    assert levels_only["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable embedded-audio evidence."
    assert missing_channel["status"] == "preflight_failed"
    assert missing_channel["results"][0]["errors"]["sliderLevel"] == "Phase 9A Video audio level requires readable sliderLevels baseline for channel."
    assert_no_confirm_token(no_evidence)
    assert_no_confirm_token(levels_only)
    assert_no_confirm_token(missing_channel)


def test_phase9a_video_audio_level_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase9a_video_audio_level_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {
        **update,
        "operations": [{"property": "sliderLevel", "args": {"channel": 0, "decibel": 0.0}}],
    }
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["sliderLevel"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliderLevels"][0] == 0.0


def _phase9b_video_audio_matrix_fixture(
    *,
    in_channel: int = 1,
    out_channel: int = 0,
    baseline: float = 0.0,
    requested: float = -1.0,
    cue_type: str = "Video",
    timeout: bool = False,
    audio_evidence: bool = True,
    levels: list[Any] | None = None,
    num_channels_in: int | None = 2,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "22222222-2222-4222-8222-222222222222"
    matrix = [list(row) for row in levels] if levels is not None else [[0.0, 0.0], [baseline, 0.0], [0.0, 0.0]]
    cue_values: dict[str, Any] = {"type": cue_type, "levels": matrix}
    if audio_evidence:
        cue_values["audioTrackFormats"] = [{"channels": 2, "format": "AAC"}]
    if num_channels_in is not None:
        cue_values["numChannelsIn"] = num_channels_in
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue_values},
        timeout_set_property=(cue_id, f"level/{in_channel}/{out_channel}") if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {"property": "level", "args": {"inChannel": in_channel, "outChannel": out_channel, "decibel": requested}}
        ],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["level"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_phase9b_video_audio_matrix_dry_run_emits_bound_token() -> None:
    client, reader, cue_id, update, _ = _phase9b_video_audio_matrix_fixture(requested=-1.0)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)["level"]
    payload, error = write_operations._decode_phase9b_video_audio_matrix_confirm_token(setter["confirm_token"])

    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoAudioMatrix:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/level/1/0"
    assert setter["args"] == [-1.0]
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase9b_audio_matrix_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == "level"
    assert payload["inChannel"] == 1
    assert payload["outChannel"] == 0
    assert payload["baseline"] == 0.0
    assert payload["requested"] == -1.0
    assert payload["workspace_validation"] == "post_write_fresh_levels_matrix_readback_required"
    assert not any(address.endswith("/level/1/0") for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_real_write_sets_once_and_verifies_crosspoint_readback() -> None:
    client, reader, cue_id, update, token = _phase9b_video_audio_matrix_fixture(requested=-1.5)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)["level"]
    address = f"/workspace/ws-1/cue_id/{cue_id}/level/1/0"
    assert result["status"] == "updated"
    assert item["after"]["levels"][1][0] == -1.5
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["rollback"] == {
        "property": "level",
        "args": {"inChannel": 1, "outChannel": 0, "decibel": 0.0},
    }
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)
    assert not any("/sliderLevel/" in request[0] for request in client.requests)
    assert not any(request[0].endswith(("/setDefaultLevels", "/setSilentLevels")) for request in client.requests)


def test_phase9b_video_audio_matrix_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase9b_video_audio_matrix_fixture()
    _, _, _, slider_update, slider_token = _phase9a_video_audio_level_fixture()
    client.cue_numbers["v5"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoAudioMatrix:v1:fake"]}],
        [{**update, "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": -2.0}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": "v5", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "rate", "args": 1.25}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio_basic", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [slider_token]}],
        [{**slider_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/level/" in address or "/sliderLevel/" in address or address.endswith("/rate") for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [True, "0", "-inf", math.nan, math.inf, None, [], {}])
def test_phase9b_video_audio_matrix_invalid_decibels_reject_before_setter(bad_value: Any) -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": [[0.0], [0.0]], "numChannelsIn": 1}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": bad_value}}],
            }
        ],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/level/" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("args", "levels", "num_channels_in", "expected_error"),
    [
        ({"inChannel": 0, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix row 0 is blocked; use Phase 9A sliderLevel."),
        ({"inChannel": 2, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0], [0.0]], 1, "Phase 9B Video audio matrix requires inChannel within numChannelsIn."),
        ({"inChannel": 2, "outChannel": 0, "decibel": -1.0}, [[0.0], [0.0]], 2, "Phase 9B Video audio matrix requires readable levels baseline for crosspoint."),
        ({"inChannel": 1, "outChannel": 2, "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix requires readable levels baseline for crosspoint."),
        ({"inChannel": 1, "outChannel": "Main", "decibel": -1.0}, [[0.0], [0.0]], 1, "Phase 9B Video audio matrix requires integer outChannel."),
    ],
)
def test_phase9b_video_audio_matrix_rejects_unsafe_indexing(
    args: dict[str, Any],
    levels: list[Any],
    num_channels_in: int,
    expected_error: str,
) -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": levels, "numChannelsIn": num_channels_in}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "level", "args": args}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"]["level"] == expected_error
    assert_no_confirm_token(result)
    assert not any("/level/" in address for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_rejects_missing_evidence_live_batch_and_blocked_actions() -> None:
    cue_id = "22222222-2222-4222-8222-222222222222"
    operation = {"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": -1.0}}
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "levels": [[0.0], [0.0]], "sliderLevels": [0.0]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    no_evidence = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}],
        dry_run=True,
    )
    live = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{**operation, "mode": "live"}]}],
        dry_run=True,
    )
    batch = reader.edit_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]},
            {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]},
        ],
        dry_run=True,
    )
    multi = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation, {"property": "sliderLevel", "args": {"channel": 0, "decibel": -1.0}}]}],
        dry_run=True,
    )

    assert no_evidence["status"] == "preflight_failed"
    assert no_evidence["results"][0]["errors"]["level"] == "Phase 9B Video audio matrix requires readable embedded-audio evidence."
    assert live["status"] == "preflight_failed"
    assert batch["status"] == "preflight_failed"
    assert multi["status"] == "preflight_failed"
    for result in [no_evidence, live, batch, multi]:
        assert_no_confirm_token(result)
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/level/" in address or "/live" in address for address, _, _ in client.requests)


def test_phase9b_video_audio_matrix_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase9b_video_audio_matrix_fixture(timeout=True)
    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {
        **update,
        "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 0, "decibel": 0.0}}],
    }
    old_token = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["level"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["levels"][1][0] == 0.0


def _phase9_levels_fixture(
    operation: dict[str, Any],
    *,
    cue_values: dict[str, Any] | None = None,
    timeout_property: str | None = None,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "33333333-3333-4333-8333-333333333333"
    values = {
        "type": "Video",
        "audioTrackFormats": [{"channels": 2, "format": "AAC"}],
        "numChannelsIn": 2,
        "sliderLevels": [0.0, 0.0, 0.0],
        "levels": [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]],
        "inputChannelName/1": "L",
        "inputChannelName/2": "R",
        "gang/1/0": "music",
        "muteChannels": [2],
        "soloChannels": [1],
    }
    if cue_values:
        values.update(cue_values)
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: values},
        timeout_set_property=(cue_id, timeout_property) if timeout_property else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def test_video_clock_type_dry_run_real_write_and_rollback() -> None:
    operation = {"property": "clockType", "args": {"value": "audio"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation, cue_values={"clockType": "video"})

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    rollback_update = {**update, "operations": [{"property": "clockType", "args": {"value": "video"}}]}
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["clockType"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert planned_setters(plan["results"][0])["clockType"]["confirm_token"].startswith("confirm:videoClockType:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["clockType"] == "audio"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["clockType"] == "video"
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/clockType") == 2


@pytest.mark.parametrize("property_name", ["doFade", "lockFadeToCue"])
@pytest.mark.parametrize("requested", [True, False])
def test_video_integrated_fade_dry_run_and_real_write(property_name: str, requested: bool) -> None:
    operation = {"property": property_name, "args": {"value": requested}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(
        operation,
        cue_values={"doFade": False, "lockFadeToCue": False},
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert planned_setters(plan["results"][0])[property_name]["confirm_token"].startswith(
        "confirm:videoIntegratedFade:v1:"
    )
    assert result["status"] == "updated"
    assert result["results"][0]["after"][property_name] is requested
    assert result["results"][0]["updateq_plan"]["rollback"] == {"property": property_name, "args": {"value": False}}
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{property_name}") == 1


@pytest.mark.parametrize("value", ["Audio", "VIDEO", "sound", "", None, True, 1, [], {}])
def test_video_clock_type_rejects_invalid_values(value: Any) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "audioTrackFormats": [{"channels": 2}], "clockType": "video"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "clockType", "args": {"value": value}}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["doFade", "lockFadeToCue"])
@pytest.mark.parametrize("value", ["true", "false", 1, 0, None, [], {}])
def test_video_integrated_fade_rejects_invalid_values(property_name: str, value: Any) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "audioTrackFormats": [{"channels": 2}],
                "doFade": False,
                "lockFadeToCue": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": property_name, "args": {"value": value}}]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert_no_confirm_token(result)


def test_video_clock_and_integrated_fade_reject_cross_tokens_batch_wrong_type_and_no_audio() -> None:
    clock_client, clock_reader, cue_id, clock_update, clock_token = _phase9_levels_fixture(
        {"property": "clockType", "args": {"value": "audio"}},
        cue_values={"clockType": "video"},
    )
    _, _, _, fade_update, fade_token = _phase9_levels_fixture(
        {"property": "doFade", "args": {"value": True}},
        cue_values={"doFade": False},
    )
    cases = [
        [{**clock_update, "confirm_gates": [fade_token]}],
        [{**fade_update, "confirm_gates": [clock_token]}],
        [{**clock_update, "confirm_gates": ["confirm:videoClockType:v1:fabricated"]}],
        [{**clock_update, "confirm_gates": [clock_token]}, {**clock_update, "confirm_gates": [clock_token]}],
        [{**clock_update, "cue_ref": "v5", "confirm_gates": [clock_token]}],
        [{**clock_update, "operations": [*clock_update["operations"], {"property": "doFade", "args": {"value": True}}], "confirm_gates": [clock_token]}],
    ]
    for case in cases:
        result = clock_reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])

    live = clock_reader.edit_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": "clockType", "mode": "live", "args": {"value": "audio"}}],
            }
        ],
        dry_run=True,
    )
    assert live["status"] == "preflight_failed"
    assert_no_confirm_token(live)

    for cue_type in ("Audio", "Camera", "Text"):
        client = BatchFakeWriteClient(
            QLabConfig(enable_write=True, passcode="server-pass"),
            cues={cue_id: {"type": cue_type, "audioTrackFormats": [{"channels": 2}], "clockType": "video"}},
        )
        reader = QLabReader(client)  # type: ignore[arg-type]
        result = reader.edit_cues("ws-1", [clock_update], dry_run=True)
        assert result["status"] == "preflight_failed"
        assert_no_confirm_token(result)

    no_audio = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "audioTrackFormats": [], "numChannelsIn": 0, "clockType": "video", "doFade": False}},
    )
    reader = QLabReader(no_audio)  # type: ignore[arg-type]
    for update in (clock_update, fade_update):
        result = reader.edit_cues("ws-1", [update], dry_run=True)
        assert result["status"] == "preflight_failed"
        assert_no_confirm_token(result)
    assert not any("/clockType" in address or "/doFade" in address for address, _, _ in clock_client.requests)


def test_phase9c_input_channel_name_dry_run_and_real_write() -> None:
    operation = {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["inputChannelName"]
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert setter["confirm_token"].startswith("confirm:videoAudioLevelMeta:v1:")
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/inputChannelName/1"
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["inputChannelName/1"] == "Dialog"
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "inputChannelName",
        "args": {"number": 1, "name": "L"},
    }
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/inputChannelName/1") == 1


def test_phase9c_gang_dry_run_and_real_write() -> None:
    operation = {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "speech"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["gang/1/0"] == "speech"
    assert result["results"][0]["updateq_plan"]["rollback"] == {
        "property": "gang",
        "args": {"inChannel": 1, "outChannel": 0, "gang": "music"},
    }
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/gang/1/0") == 1


def test_phase9c_gang_allows_empty_baseline_and_empty_rollback() -> None:
    operation = {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "MCPG"}}
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation, cue_values={"gang/1/0": ""})

    forward = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    rollback_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": ""}}],
    }
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["gang"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert forward["results"][0]["after"]["gang/1/0"] == "MCPG"
    assert forward["results"][0]["updateq_plan"]["rollback"] == {
        "property": "gang",
        "args": {"inChannel": 1, "outChannel": 0, "gang": ""},
    }
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["gang/1/0"] == ""
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/gang/1/0") == 2


@pytest.mark.parametrize(
    ("operation", "cue_values", "expected_error"),
    [
        (
            {"property": "inputChannelName", "args": {"number": 3, "name": "Bad"}},
            {},
            "Phase 9C inputChannelName number must be within numChannelsIn and starts at 1.",
        ),
        (
            {"property": "inputChannelName", "args": {"number": 1, "name": "Bad\nName"}},
            {},
            "Phase 9C inputChannelName requires a 1-64 character string without control characters.",
        ),
        (
            {"property": "gang", "args": {"inChannel": 0, "outChannel": 0, "gang": "g"}},
            {},
            "Phase 9C gang row 0 is blocked; row 0 belongs to sliderLevels.",
        ),
        (
            {"property": "gang", "args": {"inChannel": 1, "outChannel": 0, "gang": "bad\nname"}},
            {},
            "Phase 9C gang requires a string up to 64 characters without control characters.",
        ),
    ],
)
def test_phase9c_level_metadata_rejects_unsafe_values(
    operation: dict[str, Any],
    cue_values: dict[str, Any],
    expected_error: str,
) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    values = {
        "type": "Video",
        "numChannelsIn": 2,
        "sliderLevels": [0.0],
        "levels": [[0.0], [0.0]],
        "inputChannelName/1": "L",
        "gang/1/0": "music",
        **cue_values,
    }
    client = BatchFakeWriteClient(QLabConfig(enable_write=True, passcode="server-pass"), cues={cue_id: values})
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues("ws-1", [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["errors"][operation["property"]] == expected_error
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("operation", "read_key", "expected", "expected_path"),
    [
        (
            {"property": "mute/channel", "args": {"output": 1, "value": True}},
            "muteChannels",
            [1, 2],
            "mute/channel/1",
        ),
        (
            {"property": "solo/channel", "args": {"output": 1, "value": False}},
            "soloChannels",
            [],
            "solo/1",
        ),
    ],
)
def test_phase9d_mute_solo_real_write_uses_channel_routes(
    operation: dict[str, Any],
    read_key: str,
    expected: list[int],
    expected_path: str,
) -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    setter = planned_setters(plan["results"][0])[operation["property"]]
    assert setter["confirm_token"].startswith("confirm:videoAudioMuteSolo:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == expected
    assert not any("/object" in address or "/mute/clear" in address or "/solo/clear" in address for address, _, _ in client.requests)
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{expected_path}") == 1


@pytest.mark.parametrize(
    ("operation", "expected_error"),
    [
        ({"property": "mute/channel", "args": {"output": "Main", "value": True}}, "Phase 9D mute/solo requires integer output within readable sliderLevels."),
        ({"property": "solo/channel", "args": {"output": 99, "value": True}}, "Phase 9D mute/solo requires integer output within readable sliderLevels."),
        ({"property": "mute/channel", "args": {"output": 1, "value": "true"}}, "value must be a boolean"),
    ],
)
def test_phase9d_mute_solo_rejects_names_bounds_and_non_booleans(operation: dict[str, Any], expected_error: str) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "numChannelsIn": 2,
                "sliderLevels": [0.0, 0.0],
                "muteChannels": [],
                "soloChannels": [],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues("ws-1", [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert expected_error in str(result["results"][0]["errors"])
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("operation", "cue_values", "read_key"),
    [
        ({"property": "mute/channel", "args": {"output": 1, "value": False}}, {"muteChannels": [1]}, "muteChannels"),
        ({"property": "solo/channel", "args": {"output": 1, "value": False}}, {"soloChannels": [1]}, "soloChannels"),
    ],
)
def test_phase9d_mute_solo_can_rollback_self_induced_warning(
    operation: dict[str, Any],
    cue_values: dict[str, Any],
    read_key: str,
) -> None:
    client, reader, _, update, token = _phase9_levels_fixture(
        operation,
        cue_values={"isWarning": True, **cue_values},
    )

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert planned_setters(plan["results"][0])[operation["property"]]["confirm_token"].startswith(
        "confirm:videoAudioMuteSolo:v1:"
    )
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == []


@pytest.mark.parametrize(
    ("operation", "read_key", "rollback", "expected_path"),
    [
        (
            {"property": "mute/channel/clear", "args": {}},
            "muteChannels",
            [{"property": "mute/channel", "args": {"output": 2, "value": True}}],
            "mute/channel/clear",
        ),
        (
            {"property": "solo/channel/clear", "args": {}},
            "soloChannels",
            [{"property": "solo/channel", "args": {"output": 1, "value": True}}],
            "solo/channel/clear",
        ),
    ],
)
def test_phase9e_channel_clear_real_write_and_rollback_plan(
    operation: dict[str, Any],
    read_key: str,
    rollback: list[dict[str, Any]],
    expected_path: str,
) -> None:
    client, reader, cue_id, update, token = _phase9_levels_fixture(operation)

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    setter = planned_setters(plan["results"][0])[operation["property"]]
    assert setter["confirm_token"].startswith("confirm:videoAudioLevelBulk:v1:")
    assert result["status"] == "updated"
    assert result["results"][0]["after"][read_key] == []
    assert result["results"][0]["updateq_plan"]["rollback"] == rollback
    assert result["results"][0]["executed_operations"][0]["operation"] == "action"
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/{expected_path}") == 1


@pytest.mark.parametrize("property_name", ["setDefaultLevels", "setSilentLevels"])
def test_phase9e_default_and_silent_levels_stay_planned_only(property_name: str) -> None:
    cue_id = "33333333-3333-4333-8333-333333333333"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "numChannelsIn": 2, "sliderLevels": [0.0], "levels": [[0.0], [0.0]]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": property_name, "args": {}}]}],
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    setter = planned_setters(result["results"][0])[property_name]
    assert setter["planned_only_reason"] == "video_audio_level_bulk_requires_full_runtime_validation"


def test_phase9c_9d_9e_reject_cross_tokens_and_batch_before_setter() -> None:
    meta_client, meta_reader, cue_id, meta_update, meta_token = _phase9_levels_fixture(
        {"property": "inputChannelName", "args": {"number": 1, "name": "Dialog"}}
    )
    _, _, _, mute_update, mute_token = _phase9_levels_fixture(
        {"property": "mute/channel", "args": {"output": 1, "value": True}}
    )
    _, _, _, clear_update, clear_token = _phase9_levels_fixture({"property": "mute/channel/clear", "args": {}})
    cases = [
        [{**meta_update, "confirm_gates": [mute_token]}],
        [{**mute_update, "confirm_gates": [clear_token]}],
        [{**clear_update, "confirm_gates": [meta_token]}],
        [{**meta_update, "confirm_gates": [meta_token]}, {**meta_update, "confirm_gates": [meta_token]}],
        [{**meta_update, "cue_ref": "v5", "confirm_gates": [meta_token]}],
    ]
    meta_client.cue_numbers["v5"] = cue_id

    for case in cases:
        result = meta_reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/inputChannelName/" in address or "/mute/channel/" in address for address, _, _ in meta_client.requests)


PHASE8C_VIDEO_SLICE_CASES = [
    (
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
        [{"time": 1.5, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "sliceMarker/0/time",
        [1.5],
    ),
    (
        {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
        [{"time": 1.0, "playCount": -1}, {"time": 3.0, "playCount": 2}],
        "sliceMarker/0/playCount",
        [-1],
    ),
    (
        {"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}},
        [{"time": 1.0, "playCount": 1}, {"time": 2.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "addSliceMarker",
        [2.0, 1],
    ),
    (
        {"property": "deleteSliceMarker", "args": {"index": 1}},
        [{"time": 1.0, "playCount": 1}],
        "deleteSliceMarker/1",
        [],
    ),
    (
        {"property": "deleteSliceMarkers", "args": {}},
        [],
        "deleteSliceMarkers",
        [],
    ),
]


def _phase8c_video_slice_fixture(
    operation: dict[str, Any] | None = None,
    *,
    cue_type: str = "Video",
    cue_ref: str | None = None,
    timeout: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    operation = operation or {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}}
    prop_path = operation["property"]
    if prop_path == "sliceMarker/playCount":
        prop_path = f"sliceMarker/{operation.get('args', {}).get('index', 0)}/playCount"
    elif prop_path == "sliceMarker/time":
        prop_path = f"sliceMarker/{operation.get('args', {}).get('index', 0)}/time"
    elif prop_path == "deleteSliceMarker":
        prop_path = f"deleteSliceMarker/{operation.get('args', {}).get('index', 0)}"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": cue_type,
                "sliceMarkers": [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
        timeout_set_property=(cue_id, prop_path) if timeout else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_ref or cue_id,
        "profile": "video_basic",
        "operations": [operation],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"] if plan["status"] == "dry_run" else ""
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(("operation", "expected", "path", "args"), PHASE8C_VIDEO_SLICE_CASES)
def test_phase8c_video_slice_dry_run_emits_bound_token(
    operation: dict[str, Any],
    expected: list[dict[str, Any]],
    path: str,
    args: list[Any],
) -> None:
    client, reader, cue_id, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[operation["property"]]
    payload, error = write_operations._decode_phase8c_video_slice_confirm_token(setter["confirm_token"])

    assert result["status"] == "dry_run"
    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoSlices:v1:")
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{path}"
    assert setter["args"] == args
    assert setter["phase8c_expected_slice_markers"] == expected
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase8c_slice_marker_write"
    assert payload["cue_type"] == "Video"
    assert payload["profile"] == "video_basic"
    assert payload["property"] == operation["property"]
    assert payload["baseline"] == [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}]
    assert payload["expected"] == expected
    assert payload["workspace_validation"] == "post_write_fresh_sliceMarkers_readback_required"
    assert not any(address.endswith(path) for address, _, _ in client.requests)


@pytest.mark.parametrize(("operation", "expected", "path", "args"), PHASE8C_VIDEO_SLICE_CASES)
def test_phase8c_video_slice_real_write_sets_once_and_verifies(
    operation: dict[str, Any],
    expected: list[dict[str, Any]],
    path: str,
    args: list[Any],
) -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    item = result["results"][0]
    setter = planned_setters(item)[operation["property"]]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{path}"
    assert result["status"] == "updated"
    assert item["after"]["sliceMarkers"] == expected
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


@pytest.mark.parametrize("bad_play_count", [-2, 0, 1.5, "1", True, None, [], {}])
def test_phase8c_video_slice_rejects_invalid_play_count_before_setter(bad_play_count: Any) -> None:
    operation = {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": bad_play_count}}
    client, reader, _, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any("/sliceMarker/0/playCount" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "operation",
    [
        {"property": "sliceMarker/playCount", "args": {"playCount": 1}},
        {"property": "sliceMarker/time", "args": {"time": 1.5}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": -0.1}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 11.0}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 2.98}},
        {"property": "sliceMarker/time", "args": {"index": 1, "time": 1.03}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 3.5}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": math.inf}},
        {"property": "addSliceMarker", "args": {"time": 1.03, "playCount": 1}},
        {"property": "addSliceMarker", "args": {"time": 11.0, "playCount": 1}},
        {"property": "deleteSliceMarker", "args": {"index": 99}},
    ],
)
def test_phase8c_video_slice_rejects_unsafe_marker_shape_before_setter(operation: dict[str, Any]) -> None:
    client, reader, _, update, _ = _phase8c_video_slice_fixture(operation)

    result = reader.edit_cues("ws-1", [update], dry_run=True)

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def test_phase8c_video_slice_rejects_wrong_scope_tokens_and_shape_before_setter() -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture()
    _, _, _, geometry_update, geometry_token = _phase7_geometry_fixture(property_name="smooth")
    _, _, _, audio_time_update, audio_time_token = _phase8b_video_audio_time_fixture()
    other_cue_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_cue_id] = {
        "uniqueID": other_cue_id,
        "type": "Video",
        "sliceMarkers": [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        "startTime": 0,
        "endTime": 10,
        "isBroken": False,
        "isWarning": False,
        "isRunning": False,
        "isPaused": False,
        "isAuditioning": False,
    }
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "confirm_gates": ["confirm:videoSlices:v1:fake"]}],
        [{**update, "operations": [{"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}}], "confirm_gates": [token]}],
        [{**update, "cue_ref": other_cue_id, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "operations": [update["operations"][0], {"property": "deleteSliceMarker", "args": {"index": 1}}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "audio", "operations": update["operations"], "confirm_gates": [token]}],
        [{**update, "confirm_gates": [geometry_token]}],
        [{**update, "confirm_gates": [audio_time_token]}],
        [{**geometry_update, "confirm_gates": [token]}],
        [{**audio_time_update, "confirm_gates": [token]}],
    ]

    for case in cases:
        result = reader.edit_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any("/sliceMarker/0/playCount" in address for address, _, _ in client.requests)


def test_phase8c_video_slice_rejects_non_video_cues_and_malformed_baseline() -> None:
    non_video_client, non_video_reader, _, non_video_update, _ = _phase8c_video_slice_fixture(cue_type="Audio")
    malformed_client, malformed_reader, cue_id, _, _ = _phase8c_video_slice_fixture()
    malformed_client.cues[cue_id]["sliceMarkers"] = [{"time": 1.0, "playCount": 0}]

    non_video = non_video_reader.edit_cues("ws-1", [non_video_update], dry_run=True)
    malformed = malformed_reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 1}}]}],
        dry_run=True,
    )

    assert non_video["status"] == "preflight_failed"
    assert malformed["status"] == "preflight_failed"
    assert_no_confirm_token(non_video)
    assert_no_confirm_token(malformed)


def test_phase8c_video_slice_missing_baseline_allows_first_marker_add_and_rollback() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}}],
    }

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["addSliceMarker"]["confirm_token"]
    write = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    write_markers = [dict(marker) for marker in write["results"][0]["after"]["sliceMarkers"]]
    rollback_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "deleteSliceMarker", "args": {"index": 0}}],
    }
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["deleteSliceMarker"]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert plan["status"] == "dry_run"
    assert planned_setters(plan["results"][0])["addSliceMarker"]["phase8c_expected_slice_markers"] == [
        {"time": 2.0, "playCount": 1}
    ]
    assert write["status"] == "updated"
    assert write_markers == [{"time": 2.0, "playCount": 1}]
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliceMarkers"] == []


@pytest.mark.parametrize(
    "operation",
    [
        {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}},
        {"property": "sliceMarker/time", "args": {"index": 0, "time": 2.1}},
        {"property": "deleteSliceMarker", "args": {"index": 0}},
        {"property": "deleteSliceMarkers", "args": {}},
    ],
)
def test_phase8c_video_slice_existing_marker_operations_reject_missing_empty_baseline(operation: dict[str, Any]) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


def test_phase8c_video_slice_empty_baseline_add_edit_delete_flow_returns_empty() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    def apply(operation: dict[str, Any]) -> list[dict[str, Any]]:
        update = {"cue_ref": cue_id, "profile": "video_basic", "operations": [operation]}
        plan = reader.edit_cues("ws-1", [update], dry_run=True)
        token = planned_setters(plan["results"][0])[operation["property"]]["confirm_token"]
        result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
        assert result["status"] == "updated"
        return result["results"][0]["after"]["sliceMarkers"]

    assert apply({"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}}) == [
        {"time": 2.0, "playCount": 1}
    ]
    assert apply({"property": "addSliceMarker", "args": {"time": 4.0, "playCount": -1}}) == [
        {"time": 2.0, "playCount": 1},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 2}}) == [
        {"time": 2.0, "playCount": 2},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "sliceMarker/time", "args": {"index": 0, "time": 2.1}}) == [
        {"time": 2.1, "playCount": 2},
        {"time": 4.0, "playCount": -1},
    ]
    assert apply({"property": "deleteSliceMarker", "args": {"index": 1}}) == [{"time": 2.1, "playCount": 2}]
    assert apply({"property": "deleteSliceMarker", "args": {"index": 0}}) == []


def test_phase8c_video_slice_delete_all_can_be_rolled_back_by_readding_baseline() -> None:
    client, reader, _, delete_update, delete_token = _phase8c_video_slice_fixture(
        {"property": "deleteSliceMarkers", "args": {}}
    )

    deleted = reader.edit_cues("ws-1", [{**delete_update, "confirm_gates": [delete_token]}], dry_run=False)
    assert deleted["status"] == "updated"
    assert deleted["results"][0]["after"]["sliceMarkers"] == []

    for marker in [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}]:
        rollback_update = {
            **delete_update,
            "operations": [{"property": "addSliceMarker", "args": marker}],
        }
        rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
        rollback_token = planned_setters(rollback_plan["results"][0])["addSliceMarker"]["confirm_token"]
        rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)
        assert rollback["status"] == "updated"

    final = reader.get_cue_details("ws-1", delete_update["cue_ref"], "auto")
    assert final["properties"]["sliceMarkers"] == [
        {"index": 0, "time": 1.0, "playCount": 1, "loopMode": "finite", "isInfinite": False},
        {"index": 1, "time": 3.0, "playCount": 2, "loopMode": "finite", "isInfinite": False},
    ]


def test_phase8c_last_slice_play_count_dry_run_emits_bound_token_and_writes() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSlicePlayCount": -1}}

    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lastSlicePlayCount"]
    payload, error = write_operations._decode_phase8c_video_slice_confirm_token(setter["confirm_token"])
    write = reader.edit_cues("ws-1", [{**update, "confirm_gates": [setter["confirm_token"]]}], dry_run=False)

    assert plan["status"] == "dry_run"
    assert error is None
    assert setter["confirm_token"].startswith("confirm:videoSlices:v1:")
    assert payload["property"] == "lastSlicePlayCount"
    assert payload["baseline"] == 1
    assert payload["expected"] == -1
    assert write["status"] == "updated"
    assert write["results"][0]["after"]["lastSlicePlayCount"] == -1
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/lastSlicePlayCount") == 1


def test_phase8c_last_slice_infinite_loop_remains_planned_without_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSliceInfiniteLoop": True}}],
        dry_run=True,
    )
    item = result["results"][0]
    setter = planned_setters(item)["lastSliceInfiniteLoop"]

    assert result["status"] == "dry_run"
    assert item["executed_operations"] == []
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"]
    assert_no_confirm_token(result)


@pytest.mark.parametrize("bad_value", [-2, 0, 1.5, "1", True, None, [], {}])
def test_phase8c_last_slice_play_count_rejects_invalid_values_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "lastSlicePlayCount": 1,
                "lastSliceInfiniteLoop": False,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.edit_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"lastSlicePlayCount": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/lastSlicePlayCount") for address, _, _ in client.requests)


def test_phase8c_video_slice_timeout_confirmed_by_slice_marker_readback() -> None:
    client, reader, _, update, token = _phase8c_video_slice_fixture(timeout=True)

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["sliceMarkers"][0]["playCount"] == -1
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8c_video_slice_setter_error_matching_readback_is_updated_warning() -> None:
    client, reader, cue_id, update, token = _phase8c_video_slice_fixture()
    client.error_after_apply_properties.add((cue_id, "sliceMarker/0/playCount"))

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["sliceMarkers"][0]["playCount"] == -1
    assert result["results"][0]["errors"] is None
    assert "setter_error_but_readback_matched" in result["results"][0]["warnings"]


def test_phase8c_delete_slice_markers_missing_readback_counts_as_empty_after_confirmed_query() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "sliceMarkers": [{"time": 1.0, "playCount": 1}],
                "startTime": 0,
                "endTime": 10,
                "isBroken": False,
                "isWarning": False,
                "isRunning": False,
                "isPaused": False,
                "isAuditioning": False,
            }
        },
        timeout_set_property=(cue_id, "deleteSliceMarkers"),
        omit_slice_markers_after_delete=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [{"property": "deleteSliceMarkers", "args": {}}],
    }
    plan = reader.edit_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["deleteSliceMarkers"]["confirm_token"]

    result = reader.edit_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert "sliceMarkers" not in result["results"][0]["after"]
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]


@pytest.mark.parametrize(
    ("forward_operation", "rollback_operation", "final_markers"),
    [
        (
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": -1}},
            {"property": "sliceMarker/playCount", "args": {"index": 0, "playCount": 1}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.5}},
            {"property": "sliceMarker/time", "args": {"index": 0, "time": 1.0}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "addSliceMarker", "args": {"time": 2.0, "playCount": 1}},
            {"property": "deleteSliceMarker", "args": {"index": 1}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
        (
            {"property": "deleteSliceMarker", "args": {"index": 1}},
            {"property": "addSliceMarker", "args": {"time": 3.0, "playCount": 2}},
            [{"time": 1.0, "playCount": 1}, {"time": 3.0, "playCount": 2}],
        ),
    ],
)
def test_phase8c_video_slice_fresh_token_rollback_restores_baseline(
    forward_operation: dict[str, Any],
    rollback_operation: dict[str, Any],
    final_markers: list[dict[str, Any]],
) -> None:
    client, reader, _, forward_update, forward_token = _phase8c_video_slice_fixture(forward_operation)
    forward = reader.edit_cues("ws-1", [{**forward_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_update = {**forward_update, "operations": [rollback_operation]}
    stale = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [forward_token]}], dry_run=False)
    rollback_plan = reader.edit_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])[rollback_operation["property"]]["confirm_token"]
    rollback = reader.edit_cues("ws-1", [{**rollback_update, "confirm_gates": [rollback_token]}], dry_run=False)

    assert forward["status"] == "updated"
    assert stale["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["sliceMarkers"] == final_markers


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase7e_reset_rotation_dry_run_emits_bound_reset_token(profile: str, cue_type: str) -> None:
    baseline = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, _ = _phase7_reset_rotation_fixture(
        profile=profile,
        cue_type=cue_type,
        baseline=baseline,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    action = planned_setters(item)["resetRotation"]
    payload, error = write_operations._decode_phase7_video_geometry_confirm_token(
        action["confirm_token"],
        expected_family="videoGeometryReset",
    )

    assert error is None
    assert action["confirm_token"].startswith("confirm:videoGeometryReset:v1:")
    assert action["operation"] == "action"
    assert action["address"] == f"/workspace/ws-1/cue_id/{cue_id}/resetRotation"
    assert action["args"] == []
    assert action["phase7_video_geometry_candidate"] is True
    assert payload["operation_kind"] == "video_phase7_geometry_write"
    assert payload["cue_type"] == cue_type
    assert payload["profile"] == profile
    assert payload["property"] == "resetRotation"
    assert payload["action"] == "resetRotation"
    assert payload["path"] == "resetRotation"
    assert payload["baseline"] == baseline
    assert payload["requested"] == "resetRotation"
    assert item["executed_operations"] == []
    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [("video_basic", "Video"), ("camera_basic", "Camera"), ("text_basic", "Text")],
)
def test_phase7e_reset_rotation_real_write_action_and_quaternion_rollback(profile: str, cue_type: str) -> None:
    baseline = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, reset_token = _phase7_reset_rotation_fixture(
        profile=profile,
        cue_type=cue_type,
        baseline=baseline,
    )

    reset = reader.update_cues("ws-1", [{**update, "confirm_gates": [reset_token]}], dry_run=False)
    rollback_update = {
        "cue_ref": cue_id,
        "profile": profile,
        "properties": {"quaternion": baseline},
    }
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [reset_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["quaternion"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    reset_address = f"/workspace/ws-1/cue_id/{cue_id}/resetRotation"
    quaternion_address = f"/workspace/ws-1/cue_id/{cue_id}/quaternion"
    assert reset["status"] == "updated"
    assert reset["results"][0]["executed_operations"][0]["operation"] == "action"
    assert reset["results"][0]["executed_operations"][0]["args"] == []
    assert reset["results"][0]["after"]["quaternion"] == [1, 0, 0, 0]
    assert reset["results"][0]["updateq_plan"]["rollback"] == {"property": "quaternion", "value": baseline}
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["quaternion"] == baseline
    assert [request[0] for request in client.requests].count(reset_address) == 1
    assert [request[0] for request in client.requests].count(quaternion_address) == 1


def test_phase7e_reset_rotation_token_boundaries_reject_before_action() -> None:
    client, reader, cue_id, _, v1_token = _phase7_geometry_fixture(
        property_name="fillStage",
        baseline=False,
        requested=True,
    )
    client.cues[cue_id]["layer"] = 10
    v2_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}}],
        dry_run=True,
    )
    v2_token = planned_setters(v2_plan["results"][0])["layer"]["confirm_token"]
    client.cues[cue_id]["quaternion"] = [0, 0, 0.1, 0.995]
    v3_plan = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [1, 0, 0, 0]}}],
        dry_run=True,
    )
    v3_token = planned_setters(v3_plan["results"][0])["quaternion"]["confirm_token"]
    reset_update = {"cue_ref": cue_id, "profile": "video_basic", "properties": {"resetRotation": True}}
    reset_plan = reader.update_cues("ws-1", [reset_update], dry_run=True)
    reset_token = planned_setters(reset_plan["results"][0])["resetRotation"]["confirm_token"]
    cases = [
        {**reset_update, "confirm_gates": [v1_token]},
        {**reset_update, "confirm_gates": [v2_token]},
        {**reset_update, "confirm_gates": [v3_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": [1, 0, 0, 0]}, "confirm_gates": [reset_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"fillStage": True}, "confirm_gates": [reset_token]},
        {"cue_ref": cue_id, "profile": "video_basic", "properties": {"layer": 11}, "confirm_gates": [reset_token]},
    ]
    client.requests.clear()

    for update in cases:
        result = reader.update_cues("ws-1", [update], dry_run=False)
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []

    assert not any(address.endswith(("/resetRotation", "/quaternion", "/fillStage", "/layer")) for address, _, _ in client.requests)


@pytest.mark.parametrize("bad_value", [False, None, 1, "true", {}, [], [True]])
def test_phase7e_reset_rotation_invalid_property_values_reject_before_action(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "quaternion": [0, 0, 0.1, 0.995]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"resetRotation": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


def test_phase7e_reset_rotation_structure_rejections_before_action() -> None:
    client, reader, cue_id, update, token = _phase7_reset_rotation_fixture()
    client.cue_numbers["v4"] = cue_id
    cases = [
        [{**update, "cue_ref": "v4", "confirm_gates": [token]}],
        [{**update, "properties": {"resetRotation": True, "quaternion": [1, 0, 0, 0]}, "confirm_gates": [token]}],
        [{**update, "properties": {"resetRotation": True, "fillStage": True}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [{"cue_ref": cue_id, "profile": "video_basic", "operations": [{"property": "resetRotation", "args": {}, "mode": "live"}], "confirm_gates": [token]}],
        [{**update, "confirm_gates": ["confirm:videoGeometryReset:v1:fake"]}],
    ]
    client.requests.clear()

    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])

    assert not any(address.endswith("/resetRotation") for address, _, _ in client.requests)


def test_phase7e_reset_rotation_timeout_accepts_only_fresh_quaternion_readback() -> None:
    client, reader, cue_id, update, token = _phase7_reset_rotation_fixture(timeout=True)

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["quaternion"] == [1, 0, 0, 0]
    assert "setter_timeout_but_readback_matched" in result["results"][0]["warnings"]
    assert [request[0] for request in client.requests].count(f"/workspace/ws-1/cue_id/{cue_id}/resetRotation") == 1


@pytest.mark.parametrize("property_name", ["fillStage", "fillStyle", "layer", "quaternion", "smooth"])
def test_phase7_geometry_invalid_baseline_or_value_rejects_before_setter(property_name: str) -> None:
    values = {
        "fillStage": (False, True),
        "fillStyle": (0, 1),
        "layer": (10, 11),
        "quaternion": ([0, 0, 0, 1], [0, 0, 0.1, 0.995]),
        "smooth": (False, True),
    }
    baseline, requested = values[property_name]
    client, reader, cue_id, update, token = _phase7_geometry_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )
    client.cues[cue_id][property_name] = "bad" if property_name != "fillStyle" else 3

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "bad_value",
    [
        1,
        "0,0,0,1",
        {"a": 0, "b": 0, "c": 0, "d": 1},
        [0, 0, 1],
        [0, 0, 0, 1, 2],
        [0, 0, float("nan"), 1],
        [0, 0, float("inf"), 1],
        [0, 0, [0], 1],
        [0, 0, False, 1],
    ],
)
def test_phase7d_quaternion_invalid_requested_values_reject_before_setter(bad_value: Any) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "quaternion": [0, 0, 0, 1]}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"quaternion": bad_value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/quaternion") for address, _, _ in client.requests)


def test_phase7_geometry_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"fillStage": False}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["fillStage"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["fillStage"] is False


def test_phase7b_layer_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(
        property_name="layer",
        baseline=10,
        requested=11,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"layer": 10}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["layer"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["layer"] == 10


def test_phase7d_quaternion_timeout_and_rollback_contract() -> None:
    baseline = [0, 0, 0, 1]
    requested = [0, 0, 0.1, 0.995]
    client, reader, cue_id, update, forward_token = _phase7_geometry_fixture(
        property_name="quaternion",
        baseline=baseline,
        requested=requested,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"quaternion": baseline}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["quaternion"]["confirm_token"]
    client.timeout_set_property = None
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )
    address = f"/workspace/ws-1/cue_id/{cue_id}/quaternion"

    assert forward["status"] == "updated"
    assert forward["results"][0]["after"]["quaternion"] == requested
    assert forward["results"][0]["executed_operations"][0]["args"] == requested
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["quaternion"] == baseline
    assert [request[0] for request in client.requests].count(address) == 2


def test_phase7f_smooth_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase7_geometry_fixture(
        property_name="smooth",
        baseline=False,
        requested=True,
        timeout=True,
    )
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"smooth": False}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["smooth"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["smooth"] is False


@pytest.mark.parametrize("profile", ["video_basic", "camera_basic", "text_basic"])
def test_phase7c_keeps_rotation_reset_and_shutters_blocked_before_setter(profile: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cases = [
        {"properties": {"rotation": 1}},
        {"properties": {"rotationType": 1}},
        {"operations": [{"property": "rotate/x", "args": {"value": 1}}]},
        {"operations": [{"property": "rotate/y", "args": {"value": 1}, "mode": "live"}]},
        {"properties": {"shutterTop": 1}},
        {"properties": {"shutterBottom": 1}},
        {"properties": {"shutterLeft": 1}},
        {"properties": {"shutterRight": 1}},
    ]

    for case in cases:
        client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
        reader = QLabReader(client)  # type: ignore[arg-type]
        try:
            result = reader.update_cues(
                "ws-1",
                [{"cue_ref": cue_id, "profile": profile, **case}],
                dry_run=True,
            )
        except UnsafeWriteOperationError:
            assert client.requests == []
            continue
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []
        assert_no_confirm_token(result)
        assert client.requests == []


def test_phase7b_stage_region_geometry_remains_blocked_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Video", "stageName": "Stage 1"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    cases = [
        {"properties": {"stageName": "Stage 2"}},
        {
            "operations": [
                {
                    "property": "stage/regionIndex/moveBy",
                    "args": {"index": 0, "x": 1, "y": 1},
                    "mode": "saved",
                }
            ]
        },
        {
            "operations": [
                {
                    "property": "stage/regionIndex/resetControlPoints",
                    "args": {"index": 0},
                    "mode": "saved",
                }
            ]
        },
    ]

    for case in cases:
        result = reader.update_cues(
            "ws-1",
            [{"cue_ref": cue_id, "profile": "video_basic", **case}],
            dry_run=False,
        )
        assert result["status"] == "preflight_failed"
        assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    "property_name",
    ["rotation", "shutterTop", "shutterBottom", "shutterLeft", "shutterRight", "doOpacity"],
)
def test_phase3d_skipped_candidates_remain_unregistered(property_name: str) -> None:
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
        reader.update_cue(
            "ws-1",
            "11111111-1111-4111-8111-111111111111",
            {property_name: 1},
            dry_run=True,
            profile="video_basic",
        )


PHASE3E_TEXT_BASIC_CASES = [
    ("text", "Old text", "New\ntext"),
    ("text/format/fontSize", 48, 56),
    ("text/format/alignment", "left", "center"),
]


def _phase3e_text_basic_fixture(
    *,
    property_name: str = "text",
    baseline: Any = "Old text",
    requested: Any = "New text",
    timeout: bool = False,
    timeout_without_apply: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: baseline}},
        timeout_set_property=(cue_id, property_name) if timeout else None,
        timeout_without_apply=timeout_without_apply,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    PHASE3E_TEXT_BASIC_CASES,
)
def test_phase3e_text_basic_dry_run_emits_bound_token(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, _ = _phase3e_text_basic_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues("ws-1", [update], dry_run=True)
    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    payload, error = write_operations._decode_phase3e_text_basic_confirm_token(
        setter["confirm_token"]
    )

    assert error is None
    assert setter["confirm_token"].startswith("confirm:textBasic:v1:")
    assert setter["phase3e_text_basic_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["address"] == f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert item["executed_operations"] == []
    assert payload["operation_kind"] == "video_phase3e_text_basic_write"
    assert payload["cue_type"] == "Text"
    assert payload["profile"] == "text_basic"
    assert payload["property"] == property_name
    assert payload["requested"] == (
        float(requested) if property_name == "text/format/fontSize" else requested
    )
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    PHASE3E_TEXT_BASIC_CASES,
)
def test_phase3e_text_basic_real_write_sets_once_and_verifies(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture(
        property_name=property_name,
        baseline=baseline,
        requested=requested,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    item = result["results"][0]
    setter = planned_setters(item)[property_name]
    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert item["after"][property_name] == requested
    assert setter["real_write_enabled"] is True
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert "planned_only_reason" not in setter
    assert item["updateq_plan"]["status"] == "updated"
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert [request[0] for request in client.requests].count(address) == 1
    assert not any("/live" in request[0] for request in client.requests)


def test_phase3e_text_basic_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    client.cue_numbers["v1"] = cue_id
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {"type": "Text", "text": "Old text"}
    cases = [
        [{**update, "confirm_gates": []}],
        [{**update, "confirm_gates": ["confirm:textBasic:v1:fake"]}],
        [{**update, "properties": {"text/format/alignment": "center"}, "confirm_gates": [token]}],
        [{**update, "cue_ref": other_id, "confirm_gates": [token]}],
        [{**update, "cue_ref": "v1", "confirm_gates": [token]}],
        [{**update, "properties": {"text": "New text", "text/format/fontSize": 56}, "confirm_gates": [token]}],
        [{**update, "confirm_gates": [token]}, {**update, "confirm_gates": [token]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "operations": [{"property": "text", "args": {"value": "New text"}, "mode": "live"}],
                "confirm_gates": [token],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert not any(address.endswith("/text") for address, _, _ in client.requests)


def test_phase3e_text_basic_rejects_wrong_profile_type_and_stale_baseline() -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    wrong_profile = reader.update_cues(
        "ws-1",
        [{**update, "profile": "video_basic", "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id]["type"] = "Video"
    wrong_type = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.cues[cue_id].update({"type": "Text", "text": "Changed baseline"})
    stale = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_profile["status"] == "preflight_failed"
    assert wrong_type["status"] == "preflight_failed"
    assert stale["status"] == "preflight_failed"
    assert "stale_text_basic_baseline" in stale["results"][0]["errors"]["text"]
    assert all(
        item["executed_operations"] == []
        for result in (wrong_profile, wrong_type, stale)
        for item in result["results"]
    )


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3e_text_basic_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any],
) -> None:
    client, reader, cue_id, update, token = _phase3e_text_basic_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/text") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text", {"rich": "object"}),
        ("text/format/fontSize", 0),
        ("text/format/fontSize", 1001),
        ("text/format/fontSize", math.nan),
        ("text/format/fontSize", math.inf),
        ("text/format/alignment", "middle"),
    ],
)
def test_phase3e_text_basic_rejects_invalid_values(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text/format", {"fontSize": 56}),
        ("text/format/fontName", "Helvetica"),
        ("text/format/color", {"red": 1, "green": 1, "blue": 1, "alpha": 1}),
        ("text/format/shadowColor", {"red": 0, "green": 0, "blue": 0, "alpha": 1}),
    ],
)
def test_phase3e_rich_text_properties_remain_blocked(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "text": "Old text"}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []


def test_phase3e_text_basic_timeout_and_rollback_contract() -> None:
    client, reader, _, update, forward_token = _phase3e_text_basic_fixture(timeout=True)
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_update = {**update, "properties": {"text": "Old text"}}
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [forward_token]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["text"]["confirm_token"]
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": [rollback_token]}],
        dry_run=False,
    )

    assert forward["status"] == "updated"
    assert "setter_timeout_but_readback_matched" in forward["results"][0]["warnings"]
    assert old_token["status"] == "preflight_failed"
    assert rollback["status"] == "updated"
    assert rollback["results"][0]["after"]["text"] == "Old text"


def test_phase3e_text_basic_timeout_mismatch_is_uncertain_no_retry() -> None:
    client, reader, _, update, token = _phase3e_text_basic_fixture(
        timeout=True,
        timeout_without_apply=True,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "partial_failed"
    assert len([address for address, _, _ in client.requests if address.endswith("/text")]) == 1


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    [
        ("text/format/shadowBlurRadius", 2, 4),
        ("text/format/shadowOffset/width", 1, 3),
        ("text/format/shadowOffset/height", -1, 2),
        ("text/format/underlineStyle", "none", "single"),
        ("text/format/strikethroughStyle", "single", "double"),
    ],
)
def test_phase3f_text_style_dry_run_token_real_write_and_readback(
    property_name: str,
    baseline: Any,
    requested: Any,
) -> None:
    """Phase 3F stays blocked until QLab returns reliable fresh readback."""
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", property_name: baseline}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: requested},
    }

    plan = reader.update_cues("ws-1", [update], dry_run=True)
    client.requests.clear()
    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert plan["status"] == "preflight_failed"
    assert plan["results"][0]["planned_operations"] == []
    assert "baseline/readback is unavailable" in plan["results"][0]["errors"][property_name]
    assert plan["results"][0]["executed_operations"] == []
    assert_no_confirm_token(plan)
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith(f"/{property_name}") for address, _, _ in client.requests)


def test_phase3f_text_style_rejects_fake_stale_batch_and_non_text() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    other_id = "22222222-2222-4222-8222-222222222222"
    property_name = "text/format/underlineStyle"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {"type": "Text", property_name: "none"},
            other_id: {"type": "Video", property_name: "none"},
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: "single"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    assert plan["status"] == "preflight_failed"
    assert_no_confirm_token(plan)
    client.cues[cue_id][property_name] = "double"

    cases = [
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}, {**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "cue_ref": other_id,
                "profile": "video_basic",
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)


def _phase3f_text_style_fixture() -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any]]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    property_name = "text/format/underlineStyle"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Text",
                property_name: "none",
                "text/format/strikethroughStyle": "none",
            }
        },
        cue_numbers={"v1": cue_id},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "text_basic",
        "properties": {property_name: "single"},
    }
    client.requests.clear()
    return client, reader, cue_id, update


def test_phase3f_text_style_token_binding_and_structure_rejections() -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    other_id = "22222222-2222-4222-8222-222222222222"
    client.cues[other_id] = {
        "uniqueID": other_id,
        "type": "Text",
        "text/format/underlineStyle": "none",
    }
    cases = [
        [{**update, "confirm_gates": []}],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "properties": {"text/format/underlineStyle": "double"}, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "properties": {"text/format/strikethroughStyle": "single"},
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "cue_ref": other_id, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [{**update, "cue_ref": "v1", "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                **update,
                "properties": {
                    "text/format/underlineStyle": "single",
                    "text/format/strikethroughStyle": "single",
                },
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}, {**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        [
            {
                "cue_ref": cue_id,
                "profile": "text_basic",
                "operations": [
                    {
                        "property": "text/format/underlineStyle",
                        "args": {"value": "single"},
                        "mode": "live",
                    }
                ],
                "confirm_gates": ["confirm:textStyle:v1:fake"],
            }
        ],
        [{**update, "profile": "video_basic", "confirm_gates": ["confirm:textStyle:v1:fake"]}],
    ]
    for case in cases:
        result = reader.update_cues("ws-1", case, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize("cue_type", ["Video", "Camera"])
def test_phase3f_text_style_rejects_video_and_camera_cues(cue_type: str) -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    client.cues[cue_id]["type"] = cue_type

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


def test_phase3f_text_style_token_is_bound_to_workspace() -> None:
    _, _, cue_id, update = _phase3f_text_style_fixture()
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Text", "text/format/underlineStyle": "none"}},
        workspace_id="ws-2",
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-2",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    "cue_state",
    [
        {"isBroken": True},
        {"isWarning": True},
        {"isRunning": True},
        {"isPaused": True},
        {"isAuditioning": True},
    ],
)
def test_phase3f_text_style_rejects_unhealthy_or_active_cue(
    cue_state: dict[str, Any],
) -> None:
    client, reader, cue_id, update = _phase3f_text_style_fixture()
    client.cues[cue_id].update(cue_state)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


def test_phase3f_text_style_rollback_requires_fresh_token() -> None:
    client, reader, _, update = _phase3f_text_style_fixture()
    forward = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )
    rollback_update = {
        **update,
        "properties": {"text/format/underlineStyle": "none"},
    }
    old_token = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )
    rollback_plan = reader.update_cues("ws-1", [rollback_update], dry_run=True)
    rollback = reader.update_cues(
        "ws-1",
        [{**rollback_update, "confirm_gates": ["confirm:textStyle:v1:fake"]}],
        dry_run=False,
    )

    assert forward["status"] == "preflight_failed"
    assert old_token["status"] == "preflight_failed"
    assert rollback_plan["status"] == "preflight_failed"
    assert rollback["status"] == "preflight_failed"
    assert_no_confirm_token(rollback_plan)
    assert_no_confirm_token(rollback)
    assert not any(address.endswith("/text/format/underlineStyle") for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("property_name", "value"),
    [
        ("text/format/shadowBlurRadius", -1),
        ("text/format/shadowBlurRadius", math.nan),
        ("text/format/shadowOffset/width", math.inf),
        ("text/format/underlineStyle", "thick"),
        ("text/format/strikethroughStyle", ""),
    ],
)
def test_phase3f_text_style_rejects_invalid_values(
    property_name: str,
    value: Any,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    result = QLabReader(  # type: ignore[arg-type]
        FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    ).update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "text_basic", "properties": {property_name: value}}],
        dry_run=True,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


@pytest.mark.parametrize(
    ("operation", "expected_before", "expected_requested"),
    [
        (
            {
                "property": "videoEffect/enabled",
                "args": {"name": "ColorControls", "value": False},
            },
            True,
            False,
        ),
        (
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputBrightness", "setting": 0.75},
            },
            0.5,
            0.75,
        ),
    ],
)
@pytest.mark.parametrize(
    ("profile", "cue_type"),
    [
        ("video_basic", "Video"),
        ("camera_basic", "Camera"),
        ("text_basic", "Text"),
    ],
)
def test_video_fx_phase4b_dry_run_plans_only_known_scalar_change(
    operation: dict[str, Any],
    expected_before: Any,
    expected_requested: Any,
    profile: str,
    cue_type: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": cue_type,
            "videoEffects": [
                {
                    "name": "ColorControls",
                    "enabled": True,
                    "parameters": {"inputBrightness": 0.5, "mode": "normal"},
                }
            ],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile=profile,
        operations=[operation],
    )

    item_plan = result["updateq_plan"]
    setter = planned_setters(result)[operation["property"]]
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert_no_confirm_token(result)
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    assert setter["planned_only"] is True
    assert setter["video_fx_plan"]["before"] == expected_before
    assert setter["video_fx_plan"]["requested"] == expected_requested
    assert setter["video_fx_plan"]["planned_only"] is True
    assert setter["video_fx_plan"]["expected_setter_address"] == (
        f"/workspace/ws-1/cue_id/{cue_id}/{setter['video_fx_plan']['path']}"
    )
    assert setter["video_fx_plan"]["expected_readback_address"] == (
        setter["video_fx_plan"]["expected_setter_address"]
    )
    assert item_plan["video_fx"]["will_modify_qlab"] is False
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase4b_rejects_unknown_or_non_scalar_parameter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [
                {
                    "name": "ColorControls",
                    "parameters": {
                        "inputVector": [0, 1],
                        "inputColor": [1, 0, 0, 1],
                    },
                }
            ],
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    for parameter_key in ("missing", "inputVector", "inputColor"):
        result = reader.update_cue(
            "ws-1",
            cue_id,
            dry_run=True,
            profile="video_basic",
            operations=[
                {
                    "property": "videoEffect/parameter",
                    "args": {
                        "name": "ColorControls",
                        "parameterKey": parameter_key,
                        "setting": 0.5,
                    },
                }
            ],
        )
        assert result["status"] == "dry_run_preflight_failed"
        assert result["planned_operations"] == []
        assert result["executed_operations"] == []
        assert_no_confirm_token(result)


def test_video_fx_phase4c_dry_run_emits_token_for_flat_input_radius_by_index() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    )

    setter = planned_setters(result)["videoEffectIndex/parameter"]
    payload, error = write_operations._decode_phase4c_video_fx_scalar_confirm_token(setter["confirm_token"])
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert setter["video_fx_plan"]["before"] == 10
    assert setter["video_fx_plan"]["requested"] == 12
    assert setter["video_fx_plan"]["parameters_source"] == "flat_payload"
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["planned_only_reason"] == "video_fx_scalar_requires_confirm_token"
    assert setter["confirm_token"].startswith("confirm:videoFxScalar:v1:")
    assert error is None
    assert payload["operation_kind"] == "video_phase4c_fx_scalar_write"
    assert payload["cue_type"] == "Video"
    assert payload["effect_index"] == 0
    assert payload["parameter_key"] == "inputRadius"
    assert payload["baseline"] == 10.0
    assert payload["requested"] == 12.0
    assert result["updateq_plan"]["real_write_possible"] is True
    assert result["updateq_plan"]["requires_confirm_token"] is True
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase4c_real_write_updates_single_flat_input_radius() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputRadius"] == 12
    assert item["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "videoEffectIndex/parameter",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/videoEffectIndex/0/parameter/inputRadius",
            "args": [12],
            "mode": "saved",
            "capability_gate": "video_effects",
            "status": "ok",
        }
    ]
    assert item["updateq_plan"]["real_write_enabled"] is True
    assert item["updateq_plan"]["safety"]["will_modify_qlab"] is True
    assert not any("/live" in address for address, _, _ in client.requests)


def test_video_fx_phase4c_accepts_setter_timeout_when_readback_matches() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    prop = "videoEffectIndex/0/parameter/inputRadius"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
        timeout_set_property=(cue_id, prop),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputRadius"] == 12
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert result["timeout_confirmed_count"] == 1


def test_video_fx_phase4c_rejects_stale_token_and_wrong_requested_value() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 11
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 10
    wrong_value = {
        **update,
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 13},
            }
        ],
        "confirm_gates": [token],
    }
    wrong = reader.update_cues("ws-1", [wrong_value], dry_run=False)

    assert stale["status"] == "preflight_failed"
    assert "stale_video_fx_scalar_baseline" in stale["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert wrong["status"] == "preflight_failed"
    assert "confirm_token does not match" in wrong["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith("/videoEffectIndex/0/parameter/inputRadius") and args
        for address, args, _ in client.requests
    )


def test_video_fx_phase6_dry_run_emits_v2_token_for_flat_input_intensity_by_index() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    )

    setter = planned_setters(result)["videoEffectIndex/parameter"]
    payload, error = write_operations._decode_phase4c_video_fx_scalar_confirm_token(setter["confirm_token"])
    assert result["ok"] is True
    assert result["executed_operations"] == []
    assert setter["video_fx_plan"]["before"] == 2.5
    assert setter["video_fx_plan"]["requested"] == 3.5
    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["confirm_token"].startswith("confirm:videoFxScalar:v2:")
    assert error is None
    assert payload["version"] == 2
    assert payload["operation_kind"] == "video_phase6_fx_scalar_write"
    assert payload["parameter_key"] == "inputIntensity"
    assert payload["baseline"] == 2.5
    assert payload["requested"] == 3.5
    assert not any("/videoEffect" in address and not address.endswith("/valuesForKeys") for address, _, _ in client.requests)


def test_video_fx_phase6_real_write_updates_single_flat_input_intensity() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputIntensity"] == 3.5
    assert item["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "videoEffectIndex/parameter",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/videoEffectIndex/0/parameter/inputIntensity",
            "args": [3.5],
            "mode": "saved",
            "capability_gate": "video_effects",
            "status": "ok",
        }
    ]
    assert item["updateq_plan"]["after"] == 3.5
    assert not any("/live" in address for address, _, _ in client.requests)


def test_video_fx_phase6_accepts_setter_timeout_when_readback_matches() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    prop = "videoEffectIndex/0/parameter/inputIntensity"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
        timeout_set_property=(cue_id, prop),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    result = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)
    item = result["results"][0]

    assert result["status"] == "updated"
    assert item["status"] == "updated"
    assert item["errors"] is None
    assert item["after"]["videoEffects"][0]["inputIntensity"] == 3.5
    assert "setter_timeout_but_readback_matched" in item["warnings"]
    assert result["timeout_confirmed_count"] == 1


def test_video_fx_scalar_v1_and_v2_tokens_are_not_cross_authorized() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    radius_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": 12},
            }
        ],
    }
    intensity_update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    v1_token = planned_setters(reader.update_cues("ws-1", [radius_update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]
    v2_token = planned_setters(reader.update_cues("ws-1", [intensity_update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    v1_for_v2 = reader.update_cues("ws-1", [{**intensity_update, "confirm_gates": [v1_token]}], dry_run=False)
    v2_for_v1 = reader.update_cues("ws-1", [{**radius_update, "confirm_gates": [v2_token]}], dry_run=False)

    assert v1_for_v2["status"] == "preflight_failed"
    assert v2_for_v1["status"] == "preflight_failed"
    assert "confirm_token does not match" in v1_for_v2["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "confirm_token does not match" in v2_for_v1["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith(("/videoEffectIndex/0/parameter/inputIntensity", "/videoEffectIndex/0/parameter/inputRadius"))
        and args
        for address, args, _ in client.requests
    )


def test_video_fx_phase6_rejects_stale_token_wrong_value_and_payload_drift() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={
            cue_id: {
                "type": "Video",
                "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
            }
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    token = planned_setters(reader.update_cues("ws-1", [update], dry_run=True)["results"][0])[
        "videoEffectIndex/parameter"
    ]["confirm_token"]

    client.cues[cue_id]["videoEffects"][0]["inputIntensity"] = 2.75
    stale = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputIntensity"] = 2.5
    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 11
    drift = reader.update_cues("ws-1", [{**update, "confirm_gates": [token]}], dry_run=False)

    client.cues[cue_id]["videoEffects"][0]["inputRadius"] = 10
    wrong_value = {
        **update,
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 4.0},
            }
        ],
        "confirm_gates": [token],
    }
    wrong = reader.update_cues("ws-1", [wrong_value], dry_run=False)

    assert stale["status"] == "preflight_failed"
    assert drift["status"] == "preflight_failed"
    assert wrong["status"] == "preflight_failed"
    assert "stale_video_fx_scalar_baseline" in stale["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "stale_video_fx_scalar_baseline" in drift["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert "confirm_token does not match" in wrong["results"][0]["errors"]["videoEffectIndex/parameter"]
    assert not any(
        address.endswith("/videoEffectIndex/0/parameter/inputIntensity") and args
        for address, args, _ in client.requests
    )


@pytest.mark.parametrize("parameter_key", ["inputPower", "Choose_Effect", "missing"])
def test_video_fx_phase6_dry_run_does_not_emit_token_for_other_flat_parameters(parameter_key: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputPower": 1, "inputRadius": 10}],
        },
    )
    result = QLabReader(client).update_cue(  # type: ignore[arg-type]
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": parameter_key, "setting": 2},
            }
        ],
    )

    assert result["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize(
    ("update_patch", "cue_values", "expected_fragment"),
    [
        ({"profile": "camera_basic"}, {"type": "Camera"}, "gated or dry-run only"),
        ({"profile": "text_basic"}, {"type": "Text"}, "gated or dry-run only"),
        ({"cue_ref": "v11"}, {"type": "Video"}, "exact cue UUID"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "mode": "live", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "saved mode"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 1, "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffect/parameter", "args": {"name": "Blur", "parameterKey": "inputIntensity", "setting": 3.5}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffectIndex/enabled", "args": {"index": 0, "value": False}}]}, {"type": "Video"}, "gated or dry-run only"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": "high"}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": [1, 0, 0, 1]}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": {"value": 3.5}}}]}, {"type": "Video"}, "finite numeric"),
        ({"operations": [{"property": "videoEffectIndex/parameter", "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5}}, {"property": "opacity", "args": {"value": 0.5}}]}, {"type": "Video"}, "exactly one property"),
        ({}, {"type": "Video", "isBroken": True}, "healthy cue"),
        ({}, {"type": "Video", "isRunning": True}, "inactive cue"),
    ],
)
def test_video_fx_phase6_rejects_blocked_real_write_shapes(
    update_patch: dict[str, Any],
    cue_values: dict[str, Any],
    expected_fragment: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    update = {
        "cue_ref": cue_id,
        "profile": "video_basic",
        "operations": [
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputIntensity", "setting": 3.5},
            }
        ],
        "confirm_gates": ["confirm:videoFxScalar:v2:fake"],
    }
    update.update(update_patch)
    cue = {
        "type": "Video",
        "videoEffects": [{"Choose_Effect": 0, "inputIntensity": 2.5, "inputRadius": 10}],
        **cue_values,
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue},
        cue_numbers={"v11": cue_id},
    )

    result = QLabReader(client).update_cues("ws-1", [update], dry_run=False)  # type: ignore[arg-type]

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert expected_fragment in str(result["results"][0]["errors"])


def test_video_fx_phase4b_rejects_type_mismatch_and_ambiguous_name() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Video",
            "videoEffects": [
                {"name": "Blur", "parameters": {"inputRadius": 5}},
                {"name": "Blur", "parameters": {"inputRadius": 10}},
            ],
        },
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    ambiguous = reader.update_cue(
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffect/parameter",
                "args": {"name": "Blur", "parameterKey": "inputRadius", "setting": 6},
            }
        ],
    )
    mismatch = reader.update_cue(
        "ws-1",
        cue_id,
        dry_run=True,
        profile="video_basic",
        operations=[
            {
                "property": "videoEffectIndex/parameter",
                "args": {"index": 0, "parameterKey": "inputRadius", "setting": "six"},
            }
        ],
    )

    assert "ambiguous" in ambiguous["errors"]["videoEffect/parameter"]
    assert "type mismatch" in mismatch["errors"]["videoEffectIndex/parameter"]
    assert ambiguous["executed_operations"] == []
    assert mismatch["executed_operations"] == []
    assert_no_confirm_token(ambiguous)
    assert_no_confirm_token(mismatch)


def test_video_fx_phase4b_real_live_batch_and_multi_property_stay_blocked() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    cue = {
        "type": "Video",
        "videoEffects": [
            {
                "name": "ColorControls",
                "enabled": True,
                "parameters": {"inputBrightness": 0.5},
            }
        ],
    }
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: cue},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    enabled = {
        "property": "videoEffect/enabled",
        "args": {"name": "ColorControls", "value": False},
    }
    parameter = {
        "property": "videoEffect/parameter",
        "args": {
            "name": "ColorControls",
            "parameterKey": "inputBrightness",
            "setting": 0.75,
        },
    }
    cases = [
        (
            False,
            [{"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]}],
        ),
        (
            True,
            [
                {
                    "cue_ref": cue_id,
                    "profile": "video_basic",
                    "operations": [{**enabled, "mode": "live"}],
                }
            ],
        ),
        (
            False,
            [
                {"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]},
                {"cue_ref": cue_id, "profile": "video_basic", "operations": [enabled]},
            ],
        ),
        (
            False,
            [
                {
                    "cue_ref": cue_id,
                    "profile": "video_basic",
                    "operations": [enabled, parameter],
                }
            ],
        ),
    ]

    for dry_run, updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=dry_run)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)
    assert not any(
        "/videoEffect" in address and not address.endswith("/valuesForKeys")
        for address, _, _ in client.requests
    )


@pytest.mark.parametrize("profile,cue_type", [("video_basic", "Video"), ("camera_basic", "Camera")])
def test_phase3e_text_properties_not_enabled_for_video_or_camera(
    profile: str,
    cue_type: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type}},
    )

    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": profile, "properties": {"text": "Blocked"}}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []


def test_video_phase2_wrong_cue_type_failure_has_no_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Audio", "opacity": 1},
    )
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "profile" in result["results"][0]["errors"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["anchor", "translation", "scale", "crop"])
def test_video_phase2_rejects_aggregate_geometry(property_name: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    args = {"x": 1, "y": 2} if property_name != "crop" else {
        "top": 1,
        "bottom": 2,
        "left": 3,
        "right": 4,
    }
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "video_basic",
                "operations": [{"property": property_name, "args": args, "mode": "saved"}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "aggregate geometry" in result["results"][0]["errors"][property_name]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)
    assert client.requests == []


@pytest.mark.parametrize("cue_ref", ["1", "not-a-uuid"])
def test_video_phase2_requires_exact_cue_uuid(cue_ref: str) -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_ref, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "exact cue UUID" in result["results"][0]["errors"]["video_phase2"]
    assert result["results"][0]["executed_operations"] == []
    assert client.requests == []


def test_video_phase2_rejects_batch_second_property_and_confirm_gates() -> None:
    cue_a = "11111111-1111-4111-8111-111111111111"
    cue_b = "22222222-2222-4222-8222-222222222222"
    reader = QLabReader(FakeWriteClient(QLabConfig(enable_write=False, passcode=None)))  # type: ignore[arg-type]
    cases = [
        [
            {"cue_ref": cue_a, "profile": "video_basic", "properties": {"opacity": 0.8}},
            {"cue_ref": cue_b, "profile": "video_basic", "properties": {"opacity": 0.7}},
        ],
        [
            {
                "cue_ref": cue_a,
                "profile": "video_basic",
                "properties": {"opacity": 0.8, "translation/x": 10},
            }
        ],
        [
            {
                "cue_ref": cue_a,
                "profile": "video_basic",
                "properties": {"opacity": 0.8},
                "confirm_gates": ["confirm:opacity:fabricated"],
            }
        ],
    ]

    for updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=True)
        assert result["ok"] is False
        assert all(item["executed_operations"] == [] for item in result["results"])
        assert all(item["planned_operations"] == [] for item in result["results"])
        assert_no_confirm_token(result)


def test_video_phase2_rejects_fresh_unique_id_mismatch() -> None:
    cue_ref = "11111111-1111-4111-8111-111111111111"
    returned_id = "22222222-2222-4222-8222-222222222222"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_ref,
        cue_values={"uniqueID": returned_id, "type": "Video", "opacity": 1},
    )
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_ref, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "exactly match" in result["results"][0]["errors"]["cue_ref"]
    assert result["results"][0]["planned_operations"] == []
    assert result["results"][0]["executed_operations"] == []
    assert_no_confirm_token(result)


@pytest.mark.parametrize("property_name", ["rotation", "rotate/x", "rotate/y", "rotate/z"])
def test_video_phase2_rejects_unregistered_rotation_family_with_empty_execution(
    property_name: str,
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {property_name: 10}}],
        dry_run=True,
    )

    item = result["results"][0]
    assert result["ok"] is False
    assert "rotation" in item["errors"][property_name]
    assert item["planned_operations"] == []
    assert item["executed_operations"] == []
    assert_no_confirm_token(result)
    assert client.requests == []


@pytest.mark.parametrize(
    ("update", "property_name", "suggestion_fragment"),
    [
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "translation/x", "args": {"value": 1}, "mode": "live"}],
            },
            "translation/x",
            "saved-mode dry-run",
        ),
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "translation", "args": {"x": 1, "y": 2}}],
            },
            "translation",
            "translation/x and translation/y",
        ),
        (
            {"profile": "video_basic", "properties": {"rotation": 10}},
            "rotation",
            "rotation phase",
        ),
        (
            {"profile": "video_basic", "properties": {"fileTarget": "/tmp/video.mov"}},
            "fileTarget",
            "outside current Video write scope",
        ),
        (
            {
                "profile": "video_basic",
                "operations": [{"property": "videoEffects/add", "args": {"name": "ColorControls"}}],
            },
            "videoEffects/add",
            "later Video FX phase",
        ),
    ],
)
def test_video_phase2_rejections_include_updateq_plan(
    update: dict[str, Any], property_name: str, suggestion_fragment: str
) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None), existing_cue_id=cue_id)
    result = QLabReader(client).update_cues(  # type: ignore[arg-type]
        "ws-1", [{"cue_ref": cue_id, **update}], dry_run=True
    )

    item = result["results"][0]
    plan = item["updateq_plan"]
    assert result["ok"] is False
    assert plan["status"] == "rejected"
    assert plan["property"] == property_name
    assert plan["reason"]
    assert plan["planned_mutation"] is False
    assert plan["real_write_enabled"] is False
    assert plan["real_write_possible"] is False
    assert plan["requires_confirm_token"] is False
    assert suggestion_fragment.casefold() in plan["suggestion"].casefold()
    assert plan["safety"]["will_modify_qlab"] is False
    assert item["planned_operations"] == []
    assert item["executed_operations"] == []
    assert_no_confirm_token(result)


def test_video_phase2_fresh_read_is_uncached(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={"uniqueID": cue_id, "type": "Video", "opacity": 1},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    original = reader.read_cue_values
    calls: list[dict[str, Any]] = []

    def spy(*args: Any, **kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        return original(*args, **kwargs)

    monkeypatch.setattr(reader, "read_cue_values", spy)
    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "video_basic", "properties": {"opacity": 0.8}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert calls and calls[0]["cacheable"] is False


def test_video_phase2_rejects_live_and_scalar_rotation_but_keeps_fade_rotation() -> None:
    client = FakeWriteClient(QLabConfig(enable_write=False, passcode=None))
    reader = QLabReader(client)  # type: ignore[arg-type]

    with pytest.raises(UnsafeWriteOperationError, match="does not support mode 'live'"):
        reader.update_cue(
            "ws-1",
            "1",
            dry_run=True,
            profile="video_basic",
            operations=[{"property": "translation/x", "args": {"value": 1}, "mode": "live"}],
        )
    for profile in ("video_basic", "camera_basic"):
        with pytest.raises(UnsafeWriteOperationError, match="not allowlisted"):
            reader.update_cue("ws-1", "1", {"rotation": 10}, dry_run=True, profile=profile)

    assert "rotation" in profile_catalog()["fade_basic"]["properties"]
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
        reader.update_cue("ws-1", cue_id, {"text": "New text"}, dry_run=True, profile="text_basic")

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
    assert setters[0]["confirm_token"].startswith("confirm:level:")
    setters[0].pop("confirm_token")
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
        cue_values={"uniqueID": cue_id, "type": "Video", "blendMode": "Normal"},
    )
    video = QLabReader(video_client)  # type: ignore[arg-type]
    video_updates = [({"blendMode": "Normal"}, None)]
    video_setters = []
    for properties, operations in video_updates:
        result = video.update_cue(
            "ws-1", cue_id, properties=properties, operations=operations, dry_run=True, profile="video_basic"
        )
        video_setters.extend(op for op in result["planned_operations"] if op["operation"] == "set_property")

    text_client = FakeWriteClient(
        QLabConfig(enable_write=False, passcode=None),
        existing_cue_id=cue_id,
        cue_values={
            "uniqueID": cue_id,
            "type": "Text",
            "text/format/alignment": "left",
        },
    )
    text = QLabReader(text_client)  # type: ignore[arg-type]
    text_result = text.update_cue(
        "ws-1",
        cue_id,
        operations=[{"property": "text/format/alignment", "args": {"value": "center"}}],
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

    text_setters = [op for op in text_result["planned_operations"] if op["operation"] == "set_property"]
    midi_setters = [op["address"] for op in midi_result["planned_operations"] if op["operation"] == "set_property"]
    assert [(op["property"], op["address"], op["args"]) for op in video_setters] == [
        ("blendMode", f"/workspace/ws-1/cue_id/{cue_id}/blendMode", ["Normal"]),
    ]
    assert [(op["property"], op["address"], op["args"]) for op in text_setters] == [
        ("text/format/alignment", f"/workspace/ws-1/cue_id/{cue_id}/text/format/alignment", ["center"]),
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
    token = confirm_token_for(reader, cue_id, {"properties": {"duckLevel": -6}})

    result = reader.update_cue(
        "ws-1",
        cue_id,
        {"duckLevel": -6},
        dry_run=False,
        confirm_gates=[token],
    )

    assert result["ok"] is True
    assert result["after"]["duckLevel"] == -6
    assert result["confirm_gates"] == [token]
    assert result["executed_operations"][0]["capability_gate"] == "cue_behavior"


def test_update_cues_real_operation_with_readback_verifies_as_updated() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Memo", "secondColorName": "none"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "common",
                "operations": [{"property": "secondColorName", "args": {"value": "red"}}],
            }
        ],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["status"] == "updated"
    assert result["results"][0]["after"]["secondColorName"] == "red"
    assert result["results"][0]["errors"] is None


def test_update_cues_confirm_token_is_bound_to_cue_ref() -> None:
    cue_a = "11111111-1111-4111-8111-111111111111"
    cue_b = "22222222-2222-4222-8222-222222222222"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_a: {"type": "Audio"}, cue_b: {"type": "Audio"}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "profile": "audio_basic",
        "operations": [{"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -6}}],
    }

    token_a = confirm_token_for(reader, cue_a, update)
    token_b = confirm_token_for(reader, cue_b, update)

    assert token_a.startswith("confirm:level:")
    assert token_a != token_b


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
    assert setters["channelOffset"]["real_write_enabled"] is False
    assert setters["channelOffset"]["capability_gate"] == "patch_routing"
    for prop in ("channelOffset", "audioInputPatchID", "audioOutputPatchName", "level", "mute"):
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


def test_update_cues_mic_channel_offset_blocks_real_write_without_patch_gate() -> None:
    mic_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={mic_id: {"type": "Mic", "channelOffset": 0}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": mic_id, "profile": "mic_basic", "properties": {"channelOffset": 1}}],
        dry_run=False,
    )
    assert result["ok"] is False
    assert result["status"] == "preflight_failed"
    assert "channelOffset" in result["results"][0]["errors"]["channelOffset"]
    assert all(not request[0].endswith("/channelOffset") for request in client.requests)


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


def test_update_cues_rejects_slash_in_path_template_arg() -> None:
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
                "operations": [{"property": "parameterValue", "args": {"parameter": "foo/bar", "value": "Intro"}}],
            }
        ],
        dry_run=True,
    )

    assert result["ok"] is False
    assert "must not contain '/'" in result["results"][0]["errors"]["validation"]


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
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20", "alwaysCollate": False, "subcontroller": False}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {
                    "lightCommandText": "Front = 50",
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
    assert "updateq_plan" not in result["results"][0]
    setters = planned_setters(result["results"][0])
    assert setters["setLight"]["address"] == f"/workspace/ws-1/cue_id/{cue_id}/setLight"
    assert setters["setLight"]["args"] == ["front.intensity", 50]
    assert setters["replaceLightCommand"]["args"] == ["1 = 50", "1 = 60"]
    assert setters["removeLightCommandsMatching"]["args"] == ["2 = 0"]
    analysis = setters["lightCommandText"]["light_command_analysis"]
    assert analysis["overall_status"] == "valid"
    assert analysis["affected_instruments"] == ["Front"]
    assert analysis["affected_parameters"] == ["intensity"]
    assert setters["lightCommandText"]["real_write_possible"] is True
    assert setters["lightCommandText"]["requires_confirm_token"] is True
    assert setters["lightCommandText"]["phase4_real_write_candidate"] is True
    assert setters["lightCommandText"]["real_write_enabled"] is False
    assert setters["lightCommandText"]["planned_only_reason"] == (
        "light_command_requires_valid_analysis_and_confirm_token"
    )
    assert setters["lightCommandText"]["confirm_token"].startswith("confirm:lightCommandText:v1:")
    assert result["results"][0]["diff"]["lightCommandText"] == {
        "before": "Front = 20",
        "requested": "Front = 50",
    }
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
    assert [request[0] for request in client.requests].count("/workspace/ws-1/settings/light/patch") == 1
    assert result["results"][0]["executed_operations"] == []


def test_update_cues_light_analysis_policies_share_one_patch_read() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Back.red = 50"}},
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Missing = 50"}},
            {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "1 - 3 = 50"}},
        ],
        dry_run=True,
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["planned_count"] == 3
    setters = [planned_setters(item)["lightCommandText"] for item in result["results"]]
    assert [setter["light_command_analysis"]["overall_status"] for setter in setters] == [
        "warning",
        "invalid",
        "unsupported",
    ]
    assert setters[0]["light_command_analysis"]["affected_instruments"] == ["Red Fixture"]
    assert setters[0]["light_command_analysis"]["skipped_member_count"] == 1
    assert setters[0]["real_write_possible"] is False
    assert setters[0]["phase4_real_write_candidate"] is False
    assert setters[0]["planned_only_reason"] == "light_command_analysis_warning"
    assert "confirm_token" not in setters[0]
    assert setters[1]["real_write_possible"] is False
    assert setters[1]["planned_only_reason"] == "light_command_analysis_failed"
    assert "confirm_token" not in setters[1]
    assert setters[2]["real_write_possible"] is False
    assert setters[2]["planned_only_reason"] == "unsupported_light_command_syntax"
    assert "confirm_token" not in setters[2]
    assert [request[0] for request in client.requests].count("/workspace/ws-1/settings/light/patch") == 1
    assert all(item["executed_operations"] == [] for item in result["results"])


def test_update_cues_light_analysis_unavailable_keeps_dry_run_planned() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch_error=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["lightCommandText"]
    assert result["ok"] is True
    assert result["planned_count"] == 1
    assert setter["light_command_analysis"]["availability"] == "unavailable"
    assert setter["light_command_analysis"]["error"]["code"] == "light_patch_read_failed"
    assert setter["real_write_possible"] is False
    assert setter["phase4_real_write_candidate"] is False
    assert setter["planned_only_reason"] == "light_command_analysis_unavailable"
    assert "confirm_token" not in setter
    assert result["results"][0]["errors"] is None


def test_update_cues_light_analyzer_failure_is_nonfatal(monkeypatch: pytest.MonkeyPatch) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    monkeypatch.setattr(write_operations, "analyze_light_command_text", lambda *_: (_ for _ in ()).throw(RuntimeError()))

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}],
        dry_run=True,
    )

    analysis = planned_setters(result["results"][0])["lightCommandText"]["light_command_analysis"]
    assert result["ok"] is True
    assert analysis["availability"] == "unavailable"
    assert analysis["error"]["code"] == "light_command_analyzer_failed"


def test_update_cues_light_non_command_updates_do_not_read_patch() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "alwaysCollate": False}},
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"alwaysCollate": True}}],
        dry_run=True,
    )

    assert result["ok"] is True
    assert "/workspace/ws-1/settings/light/patch" not in [request[0] for request in client.requests]


def test_update_cues_light_command_real_write_with_token_sets_once_and_verifies() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}
    dry_run = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(dry_run["results"][0])["lightCommandText"]["confirm_token"]
    client.requests.clear()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["ok"] is True
    assert result["status"] == "updated"
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 50"
    assert result["results"][0]["executed_operations"] == [
        {
            "operation": "set_property",
            "property": "lightCommandText",
            "address": f"/workspace/ws-1/cue_id/{cue_id}/lightCommandText",
            "args": ["Front = 50"],
            "mode": "saved",
            "capability_gate": "light_output",
            "status": "ok",
        }
    ]
    assert [address for address, _, _ in client.requests].count(
        f"/workspace/ws-1/cue_id/{cue_id}/lightCommandText"
    ) == 1


def test_update_cues_light_command_rollback_uses_new_dry_run_token() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    forward = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 50"}}
    forward_plan = reader.update_cues("ws-1", [forward], dry_run=True)
    forward_token = planned_setters(forward_plan["results"][0])["lightCommandText"]["confirm_token"]
    assert reader.update_cues(
        "ws-1", [{**forward, "confirm_gates": [forward_token]}], dry_run=False
    )["status"] == "updated"

    rollback = {"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": "Front = 20"}}
    rollback_plan = reader.update_cues("ws-1", [rollback], dry_run=True)
    rollback_token = planned_setters(rollback_plan["results"][0])["lightCommandText"]["confirm_token"]
    assert rollback_token != forward_token
    result = reader.update_cues(
        "ws-1", [{**rollback, "confirm_gates": [rollback_token]}], dry_run=False
    )

    assert result["status"] == "updated"
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 20"
    assert client.cues[cue_id]["lightCommandText"] == "Front = 20"


def test_update_cues_empty_light_command_is_valid_but_not_confirmable() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=False),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-1",
        [{"cue_ref": cue_id, "profile": "light_basic", "properties": {"lightCommandText": ""}}],
        dry_run=True,
    )

    setter = planned_setters(result["results"][0])["lightCommandText"]
    assert setter["light_command_analysis"]["overall_status"] == "valid"
    assert setter["real_write_possible"] is False
    assert setter["requires_confirm_token"] is False
    assert setter["phase4_real_write_candidate"] is False
    assert setter["planned_only_reason"] == "empty_light_command_text_not_writeable"
    assert "confirm_token" not in setter


def _phase4_fixture(
    *,
    cue_type: str = "Light",
    connect_data: str = "ok:view|edit",
    show_mode_data: Any = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": cue_type, "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
        connect_data=connect_data,
        show_mode_data=show_mode_data,
        ignore_set_property=(cue_id, "lightCommandText") if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": "Front = 50"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])["lightCommandText"]["confirm_token"]
    client.requests.clear()
    return client, reader, cue_id, update, token


def _light_setter_requests(client: BatchFakeWriteClient) -> list[tuple[str, tuple[Any, ...], str | None]]:
    return [request for request in client.requests if request[0].endswith("/lightCommandText")]


def test_phase4_token_payload_binds_version_kind_and_write_context() -> None:
    _, _, cue_id, _, token = _phase4_fixture()

    payload, error = write_operations._decode_phase4_light_confirm_token(token)

    assert error is None
    assert payload == {
        "analysis_status": "valid",
        "baseline_sha256": write_operations._text_sha256("Front = 20"),
        "capability_gate": "light_output",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "mode": "saved",
        "operation_kind": "phase4_light_command_text_write",
        "path": "lightCommandText",
        "profile": "light_basic",
        "property": "lightCommandText",
        "requested_sha256": write_operations._text_sha256("Front = 50"),
        "risk_tier": "high",
        "version": 1,
        "workspace_id": "ws-1",
    }


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase4_malformed_tampered_or_wrong_version_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_token_cannot_authorize_another_requested_value_or_cue_ref() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()

    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"lightCommandText": "Front = 60"}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    client.cue_numbers["1"] = cue_id
    wrong_ref = reader.update_cues(
        "ws-1",
        [{**update, "cue_ref": "1", "confirm_gates": [token]}],
        dry_run=False,
    )

    assert wrong_value["status"] == "preflight_failed"
    assert wrong_ref["status"] == "preflight_failed"
    assert _light_setter_requests(client) == []


def test_phase4_token_cannot_authorize_another_workspace() -> None:
    _, _, cue_id, update, token = _phase4_fixture()
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        workspace_id="ws-2",
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]

    result = reader.update_cues(
        "ws-2",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "does not match" in result["results"][0]["errors"]["lightCommandText"]
    assert _light_setter_requests(client) == []


def test_phase4_missing_workspace_blocks_before_setter() -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "missing-ws",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "write_readiness" in result["errors"]
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


@pytest.mark.parametrize("command_text", ["Back.red = 50", "Missing = 50", "1 - 3 = 50", ""])
def test_phase4_nonconfirmable_analysis_has_no_real_write_path(command_text: str) -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": command_text},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lightCommandText"]
    client.requests.clear()

    result = reader.update_cues("ws-1", [update], dry_run=False)

    assert setter["real_write_possible"] is False
    assert "confirm_token" not in setter
    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert client.requests == []


def test_phase4_unavailable_analysis_and_multiple_tokens_block_before_setter() -> None:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "lightCommandText": "Front = 20"}},
        light_patch=normalized_light_patch_fixture(),
        light_patch_error=True,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"lightCommandText": "Front = 50"},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])["lightCommandText"]
    client.requests.clear()

    unavailable = reader.update_cues("ws-1", [update], dry_run=False)
    multiple = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": ["one", "two"]}],
        dry_run=False,
    )

    assert setter["light_command_analysis"]["overall_status"] == "unavailable"
    assert "confirm_token" not in setter
    assert unavailable["status"] == "preflight_failed"
    assert multiple["status"] == "preflight_failed"
    assert _light_setter_requests(client) == []


def test_phase4_stale_baseline_blocks_before_setter() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    client.cues[cue_id]["lightCommandText"] = "Front = 30"

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert "stale_light_command_baseline" in result["results"][0]["errors"]["lightCommandText"]
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_readback_mismatch_returns_verification_failure() -> None:
    client, reader, _, update, token = _phase4_fixture(ignore_readback=True)

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["ok"] is False
    assert result["status"] == "verification_failed"
    assert len(_light_setter_requests(client)) == 1
    assert result["results"][0]["after"]["lightCommandText"] == "Front = 20"
    assert result["results"][0]["diff"]["lightCommandText"]["requested"] == "Front = 50"


def test_phase4_batch_or_extra_property_blocks_whole_call_before_osc() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    second_id = "22222222-2222-4222-8222-222222222222"
    client.cues[second_id] = {
        "uniqueID": second_id,
        "type": "Light",
        "lightCommandText": "Front = 20",
    }

    batch = reader.update_cues(
        "ws-1",
        [
            {**update, "confirm_gates": [token]},
            {**update, "cue_ref": second_id, "confirm_gates": [token]},
        ],
        dry_run=False,
    )
    mixed = reader.update_cues(
        "ws-1",
        [
            {
                **update,
                "properties": {"lightCommandText": "Front = 50", "alwaysCollate": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )

    assert batch["status"] == "preflight_failed"
    assert mixed["status"] == "preflight_failed"
    assert all(item["executed_operations"] == [] for item in batch["results"])
    assert mixed["results"][0]["executed_operations"] == []
    assert client.requests == []


@pytest.mark.parametrize(
    ("connect_data", "show_mode_data"),
    [("ok:view", False), ("ok:view|edit", True)],
)
def test_phase4_edit_scope_and_show_mode_block_before_setter(
    connect_data: str,
    show_mode_data: Any,
) -> None:
    client, reader, _, update, token = _phase4_fixture(
        connect_data=connect_data,
        show_mode_data=show_mode_data,
    )

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert _light_setter_requests(client) == []


def test_phase4_non_light_missing_cue_and_patch_failure_block_before_setter() -> None:
    client, reader, cue_id, update, token = _phase4_fixture()
    client.cues[cue_id]["type"] = "Memo"
    non_light = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.cues[cue_id]["type"] = "Light"
    client.missing_refs.add(cue_id)
    missing = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    client.missing_refs.clear()
    client.light_patch_error = True
    patch_failure = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert [non_light["status"], missing["status"], patch_failure["status"]] == [
        "preflight_failed",
        "preflight_failed",
        "preflight_failed",
    ]
    assert _light_setter_requests(client) == []


def test_phase4_success_requests_no_dashboard_playback_or_unqualified_osc() -> None:
    client, reader, _, update, token = _phase4_fixture()

    result = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    addresses = [address for address, _, _ in client.requests]
    assert result["status"] == "updated"
    assert all(address == "/workspaces" or address.startswith("/workspace/ws-1/") for address in addresses)
    assert not any(
        forbidden in address.casefold()
        for address in addresses
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview")
    )


def _phase5_fixture(
    property_name: str = "alwaysCollate",
    *,
    baseline: bool = False,
    requested: bool = True,
    cue_type: str = "Light",
    connect_data: str = "ok:view|edit",
    show_mode_data: Any = False,
    ignore_readback: bool = False,
) -> tuple[BatchFakeWriteClient, QLabReader, str, dict[str, Any], str]:
    cue_id = "11111111-1111-4111-8111-111111111111"
    client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", property_name: baseline}},
        connect_data=connect_data,
        show_mode_data=show_mode_data,
        ignore_set_property=(cue_id, property_name) if ignore_readback else None,
    )
    reader = QLabReader(client)  # type: ignore[arg-type]
    update = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {property_name: requested},
    }
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    token = planned_setters(plan["results"][0])[property_name]["confirm_token"]
    client.cues[cue_id]["type"] = cue_type
    client.requests.clear()
    return client, reader, cue_id, update, token


@pytest.mark.parametrize(
    ("property_name", "baseline", "requested"),
    [
        ("alwaysCollate", False, True),
        ("alwaysCollate", True, False),
        ("subcontroller", False, True),
        ("subcontroller", True, False),
    ],
)
def test_phase5_dry_run_candidate_and_real_write_verify_boolean(
    property_name: str,
    baseline: bool,
    requested: bool,
) -> None:
    client, reader, cue_id, update, token = _phase5_fixture(
        property_name,
        baseline=baseline,
        requested=requested,
    )
    plan = reader.update_cues("ws-1", [update], dry_run=True)
    setter = planned_setters(plan["results"][0])[property_name]
    token = setter["confirm_token"]
    client.requests.clear()

    assert setter["real_write_possible"] is True
    assert setter["requires_confirm_token"] is True
    assert setter["phase5_light_behavior_candidate"] is True
    assert setter["real_write_enabled"] is False
    assert setter["planned_only_reason"] == "light_behavior_requires_confirm_token"
    assert token.startswith("confirm:lightBehavior:v1:")

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token]}],
        dry_run=False,
    )

    address = f"/workspace/ws-1/cue_id/{cue_id}/{property_name}"
    assert result["status"] == "updated"
    assert result["results"][0]["after"][property_name] is requested
    assert [request[0] for request in client.requests].count(address) == 1


def test_phase5_token_payload_binds_kind_property_and_context() -> None:
    _, _, cue_id, _, token = _phase5_fixture()

    payload, error = write_operations._decode_phase5_light_confirm_token(token)

    assert error is None
    assert payload == {
        "baseline": False,
        "capability_gate": "light_output",
        "cue_id": cue_id,
        "cue_ref": cue_id,
        "mode": "saved",
        "operation_kind": "phase5_light_behavior_flag_write",
        "path": "alwaysCollate",
        "profile": "light_basic",
        "property": "alwaysCollate",
        "requested": True,
        "risk_tier": "high",
        "version": 1,
        "workspace_id": "ws-1",
    }


def test_phase5_rollback_requires_new_dry_run_token() -> None:
    client, reader, cue_id, forward, token = _phase5_fixture()
    assert reader.update_cues(
        "ws-1", [{**forward, "confirm_gates": [token]}], dry_run=False
    )["status"] == "updated"

    rollback = {
        "cue_ref": cue_id,
        "profile": "light_basic",
        "properties": {"alwaysCollate": False},
    }
    plan = reader.update_cues("ws-1", [rollback], dry_run=True)
    rollback_token = planned_setters(plan["results"][0])["alwaysCollate"]["confirm_token"]
    result = reader.update_cues(
        "ws-1", [{**rollback, "confirm_gates": [rollback_token]}], dry_run=False
    )

    assert rollback_token != token
    assert result["status"] == "updated"
    assert client.cues[cue_id]["alwaysCollate"] is False


@pytest.mark.parametrize(
    "token_mutator",
    [
        lambda token: "not-a-token",
        lambda token: token[:-1] + ("0" if token[-1] != "0" else "1"),
        lambda token: token.replace(":v1:", ":v2:", 1),
    ],
)
def test_phase5_invalid_token_blocks_before_setter(token_mutator: Any) -> None:
    client, reader, _, update, token = _phase5_fixture()

    result = reader.update_cues(
        "ws-1",
        [{**update, "confirm_gates": [token_mutator(token)]}],
        dry_run=False,
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)


def test_phase5_token_cannot_authorize_other_property_value_workspace_or_cue_ref() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    wrong_value = reader.update_cues(
        "ws-1",
        [{**update, "properties": {"alwaysCollate": False}, "confirm_gates": [token]}],
        dry_run=False,
    )
    client.requests.clear()
    wrong_property = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {"subcontroller": True},
                "confirm_gates": [token],
            }
        ],
        dry_run=False,
    )
    client.requests.clear()
    client.cue_numbers["1"] = cue_id
    wrong_ref = reader.update_cues(
        "ws-1", [{**update, "cue_ref": "1", "confirm_gates": [token]}], dry_run=False
    )
    client.requests.clear()
    other_client = BatchFakeWriteClient(
        QLabConfig(enable_write=True, passcode="server-pass"),
        cues={cue_id: {"type": "Light", "alwaysCollate": False}},
        workspace_id="ws-2",
    )
    other_reader = QLabReader(other_client)  # type: ignore[arg-type]
    wrong_workspace = other_reader.update_cues(
        "ws-2", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert {wrong_value["status"], wrong_property["status"], wrong_ref["status"], wrong_workspace["status"]} == {
        "preflight_failed"
    }
    assert not any(
        address.endswith(("/alwaysCollate", "/subcontroller"))
        for address, _, _ in client.requests + other_client.requests
    )


def test_phase5_stale_baseline_and_readback_mismatch_are_detected() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    client.cues[cue_id]["alwaysCollate"] = True
    stale = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    assert stale["status"] == "preflight_failed"
    assert "stale_light_behavior_baseline" in stale["results"][0]["errors"]["alwaysCollate"]
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)

    mismatch_client, mismatch_reader, _, mismatch_update, mismatch_token = _phase5_fixture(
        ignore_readback=True
    )
    mismatch = mismatch_reader.update_cues(
        "ws-1",
        [{**mismatch_update, "confirm_gates": [mismatch_token]}],
        dry_run=False,
    )
    assert mismatch["status"] == "verification_failed"
    assert sum(address.endswith("/alwaysCollate") for address, _, _ in mismatch_client.requests) == 1


def test_phase5_batch_mixed_properties_and_live_mode_block_whole_call() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    second_id = "22222222-2222-4222-8222-222222222222"
    client.cues[second_id] = {"uniqueID": second_id, "type": "Light", "alwaysCollate": False}
    cases = [
        [
            {**update, "confirm_gates": [token]},
            {**update, "cue_ref": second_id, "confirm_gates": [token]},
        ],
        [
            {
                **update,
                "properties": {"alwaysCollate": True, "subcontroller": True},
                "confirm_gates": [token],
            }
        ],
        [
            {
                **update,
                "properties": {"alwaysCollate": True, "lightCommandText": "Front = 50"},
                "confirm_gates": [token],
            }
        ],
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "operations": [
                    {"property": "alwaysCollate", "args": {"value": True}, "mode": "live"}
                ],
                "confirm_gates": [token],
            }
        ],
    ]

    for updates in cases:
        result = reader.update_cues("ws-1", updates, dry_run=False)
        assert result["status"] == "preflight_failed"
        assert all(item["executed_operations"] == [] for item in result["results"])
    assert client.requests == []


def test_phase5_non_strict_dry_run_has_no_confirmable_token() -> None:
    client, reader, cue_id, _, _ = _phase5_fixture()

    result = reader.update_cues(
        "ws-1",
        [
            {
                "cue_ref": cue_id,
                "profile": "light_basic",
                "properties": {"alwaysCollate": True, "subcontroller": True},
            }
        ],
        dry_run=True,
    )

    setters = planned_setters(result["results"][0])
    for setter in setters.values():
        assert setter["phase5_light_behavior_candidate"] is False
        assert setter["real_write_possible"] is False
        assert setter["requires_confirm_token"] is False
        assert setter["planned_only_reason"] == "light_behavior_requires_single_property"
        assert "confirm_token" not in setter
    assert not any("settings/light/patch" in address for address, _, _ in client.requests)


@pytest.mark.parametrize(
    ("cue_type", "connect_data", "show_mode_data"),
    [
        ("Memo", "ok:view|edit", False),
        ("Light", "ok:view", False),
        ("Light", "ok:view|edit", True),
    ],
)
def test_phase5_non_light_edit_scope_and_show_mode_block_before_setter(
    cue_type: str,
    connect_data: str,
    show_mode_data: Any,
) -> None:
    client, reader, _, update, token = _phase5_fixture(
        cue_type=cue_type,
        connect_data=connect_data,
        show_mode_data=show_mode_data,
    )
    result = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )

    assert result["status"] == "preflight_failed"
    assert result["results"][0]["executed_operations"] == []
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)


def test_phase5_missing_cue_and_safe_addresses_only() -> None:
    client, reader, cue_id, update, token = _phase5_fixture()
    client.missing_refs.add(cue_id)
    missing = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    assert missing["status"] == "preflight_failed"
    assert not any(address.endswith("/alwaysCollate") for address, _, _ in client.requests)

    client.missing_refs.clear()
    success = reader.update_cues(
        "ws-1", [{**update, "confirm_gates": [token]}], dry_run=False
    )
    addresses = [address for address, _, _ in client.requests]
    assert success["status"] == "updated"
    assert all(address == "/workspaces" or address.startswith("/workspace/ws-1/") for address in addresses)
    assert not any(
        forbidden in address.casefold()
        for address in addresses
        for forbidden in ("dashboard", "/go", "/start", "/stop", "panic", "audition", "preview", "settings/light/patch")
    )


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
    assert planned_setters(result["results"][0])["duration"]["contextual_requirements"] == ["allows_editing_duration"]
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
        ("mic_basic", "Mic", {"channels": 2}),
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
