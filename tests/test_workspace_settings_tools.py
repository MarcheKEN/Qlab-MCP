from __future__ import annotations

import asyncio
import json
import math
from uuid import UUID

import pytest

from fastmcp import Client
from pydantic import ValidationError

import qlab_mcp.server as server_module
from qlab_mcp.models import (
    AudioPatchLevel,
    WorkspaceAudioSettingsOverview,
    WorkspaceGeneralSettingsData,
    WorkspaceVideoSettingsResult,
)
from qlab_mcp.server import mcp


def test_workspace_settings_tools_replace_generic_surface() -> None:
    async def list_tool_names() -> set[str]:
        async with Client(mcp) as client:
            return {tool.name for tool in await client.list_tools()}

    tool_names = asyncio.run(list_tool_names())
    expected = {
        "qlab_get_workspace_general_settings",
        "qlab_get_workspace_audio_settings",
        "qlab_get_workspace_video_settings",
        "qlab_get_video_stage",
        "qlab_get_video_output_route",
        "qlab_get_workspace_light_settings",
        "qlab_get_workspace_network_settings",
        "qlab_get_workspace_midi_settings",
    }

    assert expected <= tool_names
    assert "qlab_get_workspace_settings" not in tool_names
    assert "qlab_get_workspace_setting_details" not in tool_names
    assert len(tool_names) == 48


def test_legacy_workspace_settings_python_tools_are_removed() -> None:
    assert not hasattr(server_module, "qlab_get_workspace_settings")
    assert not hasattr(server_module, "qlab_get_workspace_setting_details")


def test_workspace_settings_tool_schemas_are_domain_specific() -> None:
    async def list_tools() -> dict[str, object]:
        async with Client(mcp) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    tools = asyncio.run(list_tools())
    expected_parameters = {
        "qlab_get_workspace_general_settings": {"workspace_id"},
        "qlab_get_workspace_audio_settings": {
            "workspace_id", "view", "ref", "profile", "input_channel", "output_channel",
        },
        "qlab_get_workspace_video_settings": {"workspace_id"},
        "qlab_get_video_stage": {"workspace_id", "stage_id", "profile"},
        "qlab_get_video_output_route": {"workspace_id", "route_id", "profile"},
        "qlab_get_workspace_light_settings": {"workspace_id", "profile"},
        "qlab_get_workspace_network_settings": {"workspace_id", "ref", "profile"},
        "qlab_get_workspace_midi_settings": {"workspace_id", "ref", "profile"},
    }

    for tool_name, parameters in expected_parameters.items():
        tool = tools[tool_name]
        assert set(tool.inputSchema["properties"]) == parameters
        assert {"section", "mode", "sections", "requests", "kind"}.isdisjoint(parameters)
        assert "data" in tool.outputSchema["properties"]
        assert "domain" in tool.outputSchema["properties"]
        assert "coverage" in tool.outputSchema["properties"]

    assert tools["qlab_get_workspace_audio_settings"].inputSchema["properties"]["view"]["enum"] == [
        "overview",
        "output_patch",
        "input_patch",
    ]
    assert "audio_maps" not in json.dumps(tools["qlab_get_workspace_audio_settings"].outputSchema)
    for tool_name, ref_field in (("qlab_get_video_stage", "stage_id"), ("qlab_get_video_output_route", "route_id")):
        properties = tools[tool_name].inputSchema["properties"]
        assert properties[ref_field]["format"] == "uuid"
        assert properties["profile"]["enum"] == ["safe", "technical"]
        assert {"workspace_id", ref_field} <= set(tools[tool_name].inputSchema["required"])
    for tool_name in expected_parameters.keys() - {"qlab_get_workspace_general_settings", "qlab_get_workspace_video_settings", "qlab_get_video_stage", "qlab_get_video_output_route"}:
        assert tools[tool_name].inputSchema["properties"]["profile"]["enum"] == [
            "safe",
            "technical",
            "exhaustive",
        ]
        assert "safe" in tools[tool_name].inputSchema["properties"]["profile"]["description"]

    for tool_name in {
        "qlab_get_workspace_audio_settings",
        "qlab_get_workspace_network_settings",
        "qlab_get_workspace_midi_settings",
    }:
        assert "name or UUID" in tools[tool_name].inputSchema["properties"]["ref"]["description"]

    assert "overview" in tools["qlab_get_workspace_audio_settings"].inputSchema["properties"]["view"]["description"]
    audio_properties = tools["qlab_get_workspace_audio_settings"].inputSchema["properties"]
    assert audio_properties["input_channel"]["anyOf"][0] == {"maximum": 128, "minimum": 1, "type": "integer"}
    assert audio_properties["output_channel"]["anyOf"][0] == {"minimum": 1, "type": "integer"}


def test_audio_overview_is_fixed_to_audio_and_normalized(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_workspace_settings(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "workspace_id": "ws-1",
                "profile": "safe",
                "sections": {
                    "audio": {
                        "output_patches": [],
                        "input_patches": [],
                        "cue_output_channel_counts": {},
                        "output_channel_names": {},
                        "max_volume": 12.0,
                        "min_volume": -120.0,
                    }
                },
                "redactions": [],
                "warnings": [],
                "errors": None,
            }

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = server_module.qlab_get_workspace_audio_settings("ws-1")

    assert reader.calls == [
        {
            "workspace_id": "ws-1",
            "mode": "summary",
            "sections": ["audio"],
            "profile": "safe",
        }
    ]
    assert result.domain == "audio"
    assert result.coverage == "partial"
    assert result.data is not None
    assert result.data.overview is not None
    assert result.data.overview.max_volume == 12.0
    assert result.data.overview.min_volume == -120.0


def test_audio_overview_rejects_ref_without_constructing_reader(monkeypatch) -> None:
    def unexpected_reader():
        raise AssertionError("invalid overview/ref combination must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    result = server_module.qlab_get_workspace_audio_settings("ws-1", "overview", "missing")

    assert result.ok is False
    assert result.status == "error"
    assert result.error_code == "validation_failed"
    assert result.data is None
    assert result.received == {"view": "overview", "ref": "missing", "profile": "safe"}


def test_audio_patch_reports_unknown_device_presence() -> None:
    overview = WorkspaceAudioSettingsOverview.model_validate(
        {
            "output_patches": [
                {
                    "name": "Main",
                    "uniqueID": "patch-1",
                    "routing_present": True,
                    "routing_count": 2,
                    "device_presence_known": False,
                    "device_present": None,
                }
            ],
            "input_patches": [],
            "max_volume": 12,
            "min_volume": -60,
        }
    )

    patch = overview.output_patches[0]
    assert patch.device_presence_known is False
    assert patch.device_present is None


@pytest.mark.parametrize("value", ["12", True, math.nan, math.inf, -1])
def test_general_min_go_time_rejects_invalid_numbers(value) -> None:
    with pytest.raises(ValidationError):
        WorkspaceGeneralSettingsData.model_validate({"minGoTime": value, "selectionIsPlayhead": True})


@pytest.mark.parametrize("field", ["max_volume", "min_volume"])
@pytest.mark.parametrize("value", ["12", True, math.nan, math.inf])
def test_audio_volume_limits_reject_non_finite_or_coerced_values(field, value) -> None:
    with pytest.raises(ValidationError):
        WorkspaceAudioSettingsOverview.model_validate({field: value})


def test_audio_patch_level_accepts_negative_infinity_marker() -> None:
    level = AudioPatchLevel.model_validate({
        "input_channel": 1, "output_channel": 2, "decibels": "-inf",
    })
    assert level.decibels == "-inf"


def test_video_route_preserves_attention_and_guides_presence() -> None:
    result = WorkspaceVideoSettingsResult.model_validate(
        {
            "ok": True,
            "status": "ok",
            "partial": False,
            "workspace_id": "ws-1",
            "domain": "video",
            "view": "overview",
            "data": {
                "overview": {
                    "routes": [
                        {
                            "uniqueID": "route-1",
                            "name": "Output 1",
                            "connected": False,
                            "guides_present": True,
                            "attention": {
                                "status": "disconnected",
                                "message": "Video route is configured but QLab reports it is not connected.",
                            },
                        }
                    ]
                }
            },
        }
    )

    route = result.data.overview.routes[0]
    assert route.guides_present is True
    assert route.attention.status == "disconnected"


def test_audio_detail_uses_only_audio_selector(monkeypatch) -> None:
    class FakeReader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_workspace_setting_details(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "workspace_id": "ws-1",
                "section": "audio",
                "kind": "output_patch",
                "ref": "Main",
                "profile": "safe",
                "details": {"name": "Main", "uniqueID": "patch-1"},
                "choices": [],
                "redactions": [],
                "warnings": [],
                "errors": None,
            }

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = server_module.qlab_get_workspace_audio_settings("ws-1", "output_patch", "Main")

    assert reader.calls == [
        {
            "workspace_id": "ws-1",
            "section": "audio",
            "kind": "output_patch",
            "ref": "Main",
            "profile": "safe",
        }
    ]
    assert result.view == "output_patch"
    assert result.data is not None
    assert result.data.detail.name == "Main"
    assert result.data.detail.uniqueID == "patch-1"


def test_audio_output_patch_forwards_one_level_query(monkeypatch) -> None:
    calls = []

    class FakeReader:
        def get_workspace_setting_details(self, **kwargs):
            calls.append(kwargs)
            return {
                "workspace_id": "ws-1",
                "section": "audio",
                "kind": "output_patch",
                "ref": "patch-1",
                "profile": "safe",
                "details": {
                    "name": "Main",
                    "uniqueID": "patch-1",
                    "routing": [1, 2],
                    "cue_output_count": 2,
                    "output_channel_names": [{"channel": 1, "name": "Left"}],
                    "mute_channels": [2],
                    "solo_channels": [],
                    "device_presence_known": False,
                    "device_present": None,
                    "level": {"input_channel": 1, "output_channel": 2, "decibels": -6.0},
                },
                "choices": [], "redactions": [], "warnings": [], "errors": None,
            }

    monkeypatch.setattr(server_module, "_reader", FakeReader)

    result = server_module.qlab_get_workspace_audio_settings(
        "ws-1", "output_patch", "patch-1", "safe", 1, 2,
    )

    assert calls == [{
        "workspace_id": "ws-1", "section": "audio", "kind": "output_patch",
        "ref": "patch-1", "profile": "safe", "input_channel": 1, "output_channel": 2,
    }]
    assert result.data.detail.level.decibels == -6.0


@pytest.mark.parametrize(
    ("view", "input_channel", "output_channel"),
    [("overview", 1, 1), ("input_patch", 1, 1), ("output_patch", 1, None), ("output_patch", None, 1)],
)
def test_audio_channel_query_rejects_invalid_combinations_before_reader(
    monkeypatch, view, input_channel, output_channel,
) -> None:
    def unexpected_reader():
        raise AssertionError("invalid channel query must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    result = server_module.qlab_get_workspace_audio_settings(
        "ws-1", view, "patch-1", "safe", input_channel, output_channel,
    )

    assert result.ok is False
    assert result.error_code == "validation_failed"


@pytest.mark.parametrize("field", ["input_channel", "output_channel"])
@pytest.mark.parametrize("value", [0, -1, True, 1.5, "1"])
def test_audio_channel_schema_rejects_invalid_values_before_reader(monkeypatch, field, value) -> None:
    def unexpected_reader():
        raise AssertionError("invalid channel must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    async def rejected() -> None:
        arguments = {
            "workspace_id": "ws-1",
            "view": "output_patch",
            "ref": "patch-1",
            "input_channel": 1,
            "output_channel": 1,
        }
        arguments[field] = value
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("qlab_get_workspace_audio_settings", arguments)

    asyncio.run(rejected())


@pytest.mark.parametrize(("tool_name", "kind", "ref_field"), [
    ("qlab_get_video_stage", "stage", "stage_id"),
    ("qlab_get_video_output_route", "route", "route_id"),
])
def test_exact_video_errors_preserve_reader_contract(monkeypatch, tool_name, kind, ref_field) -> None:
    identifier = UUID("11111111-1111-4111-8111-111111111111")
    calls = []

    class FakeReader:
        def get_video_setting(self, **kwargs):
            calls.append(kwargs)
            return {
                "ok": False,
                "status": "error",
                "workspace_id": "ws-1",
                "section": "video",
                "kind": kind,
                "ref": str(identifier),
                "profile": "technical",
                "details": None,
                "choices": [],
                "error_code": "video_stage_not_found" if kind == "stage" else "video_output_route_not_found",
                "suggested_action": "Call qlab_get_workspace_video_settings to list exact UUIDs.",
                "redactions": [],
                "warnings": [],
                "errors": {"video": "Not found"},
            }

    monkeypatch.setattr(server_module, "_reader", FakeReader)
    result = getattr(server_module, tool_name)("ws-1", **{ref_field: identifier, "profile": "technical"})
    assert calls == [{"workspace_id": "ws-1", "kind": kind, "ref": str(identifier), "profile": "technical"}]
    assert result.ok is False
    assert result.status == "error"
    assert result.partial is False
    assert result.error_code == ("video_stage_not_found" if kind == "stage" else "video_output_route_not_found")
    assert "qlab_get_workspace_video_settings" in result.suggested_action
    assert result.data is None


@pytest.mark.parametrize(("tool_name", "ref_field"), [
    ("qlab_get_video_stage", "stage_id"),
    ("qlab_get_video_output_route", "route_id"),
])
def test_exact_video_rejects_names_and_exhaustive_before_reader(monkeypatch, tool_name, ref_field) -> None:
    def unexpected_reader():
        raise AssertionError("Invalid input must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    async def rejected():
        async with Client(mcp) as client:
            for arguments in (
                {"workspace_id": "ws-1", ref_field: "Main"},
                {"workspace_id": "ws-1", ref_field: "11111111-1111-4111-8111-111111111111", "profile": "exhaustive"},
            ):
                with pytest.raises(Exception, match="(?i)validation|uuid|literal|input"):
                    await client.call_tool(tool_name, arguments)

    asyncio.run(rejected())


@pytest.mark.parametrize("profile", ["safe", "technical"])
def test_video_stage_partial_data_survives_fastmcp(monkeypatch, profile) -> None:
    identifier = "11111111-1111-4111-8111-111111111111"

    class FakeReader:
        def get_video_setting(self, **kwargs):
            return {
                "ok": True, "status": "partial", "partial": True,
                "workspace_id": "ws-1", "profile": profile,
                "details": {"detail": {"uniqueID": identifier, "name": "Stage", "regions": None},
                            "technical_payload": {"stage": {"uniqueID": identifier}, "regions": None} if profile == "technical" else None},
                "errors": {"video.stage.regions": "timeout"},
            }

    monkeypatch.setattr(server_module, "_reader", FakeReader)

    async def call():
        async with Client(mcp) as client:
            return await client.call_tool("qlab_get_video_stage", {
                "workspace_id": "ws-1", "stage_id": identifier, "profile": profile,
            })

    payload = asyncio.run(call()).structured_content
    assert payload["status"] == "partial"
    assert payload["partial"] is True
    assert payload["data"]["detail"]["uniqueID"] == identifier
    assert payload["data"]["detail"]["regions"] is None


def test_video_overview_distinguishes_failed_from_empty_collections(monkeypatch) -> None:
    class FakeReader:
        def get_workspace_settings(self, **kwargs):
            return {
                "workspace_id": "ws-1", "profile": "safe",
                "sections": {"video": {"input_patches": [], "routes": [], "stages": []}},
                "errors": {"video.routes": "timeout"},
            }

    monkeypatch.setattr(server_module, "_reader", FakeReader)
    result = server_module.qlab_get_workspace_video_settings("ws-1")
    assert result.status == "partial"
    assert result.data.overview.routes is None
    assert result.data.overview.stages == []
    assert result.data.overview.input_patches == []
