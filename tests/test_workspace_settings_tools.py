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
    WorkspaceGeneralSettingsData,
    WorkspaceVideoSettingsResult,
)
from qlab_mcp.server import mcp
from qlab_mcp.settings.summarizers import _summarize_audio_patch, _summarize_network_patch


WORKSPACE_ID = "11111111-1111-4111-8111-111111111111"
PATCH_ID = "22222222-2222-4222-8222-222222222222"


@pytest.mark.parametrize("osc_failure", [False, True])
def test_light_public_tool_keeps_typed_saved_patch_when_osc_fails(monkeypatch, osc_failure):
    from qlab_mcp.light_patch import reader as light_reader
    from qlab_mcp.light_patch.inspection import inspect_saved_patch
    from test_light_patch_archive import workspace

    saved = inspect_saved_patch(workspace())
    saved.update(status="ready", source="saved_archive", freshness="last_saved", document_modified=False)

    class FakeReader:
        def get_workspace_setting_details(self, **kwargs):
            assert kwargs["section"] == "light" and kwargs["profile"] == "safe"
            if osc_failure:
                raise ValueError("OSC unavailable")
            return dict(ok=True, status="ok", partial=False, workspace_id=saved["workspace_id"],
                        details={"summary": {"patch_present": True}, "instruments": []})

    monkeypatch.setattr(server_module, "_reader", FakeReader)
    monkeypatch.setattr(light_reader, "_saved", lambda reader, workspace_id: saved)
    result = server_module.qlab_get_workspace_light_settings(saved["workspace_id"])
    assert result.ok
    assert result.partial is osc_failure
    assert result.data.saved_patch.instruments[0].name == "Door"
    assert result.data.saved_patch.definitions[0].parameters[0].channel == 0
    assert result.data.pagination.byte_limit == 2 * 1024 * 1024


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
    assert len(tool_names) == 90


def test_network_destination_absence_is_unknown() -> None:
    assert _summarize_network_patch({"name": "Patch", "uniqueID": "id"})["destination_present"] is None
    assert _summarize_network_patch({"name": "Patch", "destination": "redacted"})["destination_present"] is True
    assert _summarize_network_patch({"name": "Patch", "uniqueID": "id"})["passcode_present"] is None
    assert _summarize_network_patch({"name": "Patch", "passcode": "redacted"})["passcode_present"] is True


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
        "qlab_get_workspace_audio_settings": {"workspace_id", "profile", "offset", "limit"},
        "qlab_get_audio_patch": {
            "workspace_id", "patch_type", "patch_id", "profile", "input_channel",
            "output_channel", "cell_offset", "cell_limit",
        },
        "qlab_get_workspace_video_settings": {"workspace_id", "section", "offset", "limit"},
        "qlab_get_video_stage": {"workspace_id", "stage_id", "profile", "offset", "limit", "expected_sha256"},
        "qlab_get_video_output_route": {"workspace_id", "route_id", "profile"},
        "qlab_get_workspace_light_settings": {"workspace_id", "profile", "section", "offset", "limit"},
        "qlab_get_workspace_network_settings": {"workspace_id", "ref", "profile"},
        "qlab_get_workspace_midi_settings": {"workspace_id", "ref", "profile"},
    }

    for tool_name, parameters in expected_parameters.items():
        tool = tools[tool_name]
        assert set(tool.inputSchema["properties"]) == parameters
        assert {"mode", "sections", "requests", "kind"}.isdisjoint(parameters)
        if tool_name not in {"qlab_get_workspace_light_settings", "qlab_get_workspace_video_settings"}:
            assert "section" not in parameters
        if tool_name not in {"qlab_get_workspace_audio_settings", "qlab_get_audio_patch"}:
            assert "data" in tool.outputSchema["properties"]
            assert "domain" in tool.outputSchema["properties"]
            assert "coverage" in tool.outputSchema["properties"]

    audio_patch_properties = tools["qlab_get_audio_patch"].inputSchema["properties"]
    assert audio_patch_properties["patch_type"]["enum"] == ["input", "output"]
    assert audio_patch_properties["patch_id"]["format"] == "uuid"
    assert {"workspace_id", "patch_type", "patch_id"} <= set(
        tools["qlab_get_audio_patch"].inputSchema["required"]
    )
    assert audio_patch_properties["cell_limit"]["maximum"] == 256
    assert tools["qlab_get_workspace_audio_settings"].inputSchema["properties"]["limit"]["maximum"] == 128
    assert "audio_effects" not in json.dumps(tools["qlab_get_workspace_audio_settings"].outputSchema)
    for tool_name, ref_field in (("qlab_get_video_stage", "stage_id"), ("qlab_get_video_output_route", "route_id")):
        properties = tools[tool_name].inputSchema["properties"]
        assert properties[ref_field]["format"] == "uuid"
        assert properties["profile"]["enum"] == ["safe", "technical"]
        assert {"workspace_id", ref_field} <= set(tools[tool_name].inputSchema["required"])
    for tool_name in expected_parameters.keys() - {
        "qlab_get_workspace_general_settings", "qlab_get_workspace_video_settings",
        "qlab_get_video_stage", "qlab_get_video_output_route",
    }:
        assert tools[tool_name].inputSchema["properties"]["profile"]["enum"] == [
            "safe",
            "technical",
            "exhaustive",
        ]
        assert "safe" in tools[tool_name].inputSchema["properties"]["profile"]["description"]

    for tool_name in {"qlab_get_workspace_network_settings", "qlab_get_workspace_midi_settings"}:
        assert "name or UUID" in tools[tool_name].inputSchema["properties"]["ref"]["description"]

    assert audio_patch_properties["input_channel"]["anyOf"][0] == {
        "maximum": 128, "minimum": 0, "type": "integer",
    }
    assert audio_patch_properties["output_channel"]["anyOf"][0] == {
        "maximum": 128, "minimum": 0, "type": "integer",
    }


def test_audio_overview_keeps_live_and_saved_sources_separate(monkeypatch) -> None:
    from qlab_mcp import audio_patch_reader

    class FakeReader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_workspace_settings(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "ok": True,
                "workspace_id": WORKSPACE_ID,
                "profile": "safe",
                "sections": {
                    "audio": {
                        "output_patches": [{
                            "name": "Main now", "uniqueID": PATCH_ID, "routing": [1, 2],
                        }],
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

    saved_read = {
        "status": "ready", "freshness": "possibly_stale", "document_modified": True,
        "sha256": "saved-hash", "issues": [],
        "saved": {
            "workspace_id": WORKSPACE_ID,
            "output_patches": [{
                "id": PATCH_ID, "name": "Main when saved", "patch_type": "output",
                "routing_matrix": {
                    "status": "available", "cells": [{"row": 1, "column": 1}],
                    "total_cells": 1, "truncated": False,
                },
                "cue_output_buses": [{"index": 1, "name": "Bus", "channels": 2}],
            }],
            "input_patches": [],
        },
    }
    saved_calls = []
    monkeypatch.setattr(
        audio_patch_reader, "read_saved_audio_patches",
        lambda reader, workspace_id, **kwargs: saved_calls.append((workspace_id, kwargs)) or saved_read,
    )
    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = server_module.qlab_get_workspace_audio_settings(WORKSPACE_ID, offset=0, limit=1)

    assert reader.calls == [
        {
            "workspace_id": WORKSPACE_ID,
            "mode": "summary",
            "sections": ["audio"],
            "profile": "safe",
        }
    ]
    assert saved_calls == [(WORKSPACE_ID, {"patch_type": "all"})]
    live = result["sources"]["live_osc"]
    saved = result["sources"]["saved_archive"]
    assert live["status"] == "available"
    assert live["data"]["output_patches"][0]["routing"] == [1, 2]
    assert "routing_matrix" not in live["data"]["output_patches"][0]
    assert saved["freshness"] == "possibly_stale"
    assert saved["document_modified"] is True
    saved_patch = saved["data"]["output_patches"][0]
    assert saved_patch["routing_matrix"]["cells"] == []
    assert saved_patch["routing_matrix"]["cells_omitted"] is True
    assert "cue_output_buses" not in saved_patch
    assert saved_patch["cue_output_bus_count"] == 1
    assert result["comparison"]["status"] == "not_comparable"
    assert result["source_status"]["atomic_snapshot"] is False


def test_empty_audio_routing_is_unknown_without_known_device() -> None:
    patch = _summarize_audio_patch({"name": "Disconnected patch", "routing": []})

    assert patch["routing"] is None
    assert patch["routing_present"] is None
    assert patch["routing_count"] is None
    assert patch["device_present"] is None


@pytest.mark.parametrize("value", ["12", True, math.nan, math.inf, -1])
def test_general_min_go_time_rejects_invalid_numbers(value) -> None:
    with pytest.raises(ValidationError):
        WorkspaceGeneralSettingsData.model_validate({"minGoTime": value, "selectionIsPlayhead": True})


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


def test_audio_patch_reads_exact_input_uuid_from_both_sources(monkeypatch) -> None:
    from qlab_mcp import audio_patch_reader

    class FakeReader:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        def get_workspace_setting_details(self, **kwargs):
            self.calls.append(kwargs)
            return {
                "ok": True,
                "workspace_id": WORKSPACE_ID,
                "section": "audio",
                "kind": "input_patch",
                "ref": PATCH_ID,
                "profile": "safe",
                "details": {"name": "Mic input", "uniqueID": PATCH_ID},
                "choices": [],
                "redactions": [],
                "warnings": [],
                "errors": None,
            }

    saved = {
        "status": "ready", "freshness": "possibly_stale", "document_modified": True,
        "sha256": "saved-hash", "issues": [],
        "saved": {
            "input_patches": [{"id": PATCH_ID, "name": "Mic input", "patch_type": "input"}],
            "output_patches": [],
        },
    }
    saved_calls = []
    monkeypatch.setattr(
        audio_patch_reader, "read_saved_audio_patches",
        lambda reader, workspace_id, **kwargs: saved_calls.append((workspace_id, kwargs)) or saved,
    )
    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    result = server_module.qlab_get_audio_patch(WORKSPACE_ID, "input", PATCH_ID)

    assert reader.calls == [
        {
            "workspace_id": WORKSPACE_ID,
            "section": "audio",
            "kind": "input_patch",
            "ref": PATCH_ID,
            "profile": "safe",
        }
    ]
    assert saved_calls == [(WORKSPACE_ID, {"patch_type": "input", "ref": PATCH_ID})]
    assert result["sources"]["live_osc"]["data"]["uniqueID"] == PATCH_ID
    assert result["sources"]["saved_archive"]["data"]["id"] == PATCH_ID
    assert result["sources"]["saved_archive"]["freshness"] == "possibly_stale"


def test_audio_output_patch_forwards_paired_level_query(monkeypatch) -> None:
    from qlab_mcp import audio_patch_reader

    calls = []

    class FakeReader:
        def get_workspace_setting_details(self, **kwargs):
            calls.append(kwargs)
            return {
                "ok": True,
                "workspace_id": WORKSPACE_ID,
                "section": "audio",
                "kind": "output_patch",
                "ref": PATCH_ID,
                "profile": "safe",
                "details": {
                    "name": "Main",
                    "uniqueID": PATCH_ID,
                    "name_property": "Main",
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

    saved = {
        "status": "ready", "freshness": "last_saved", "document_modified": False,
        "sha256": "saved-hash", "issues": [],
        "saved": {
            "output_patches": [{
                "id": PATCH_ID, "name": "Main", "patch_type": "output",
                "routing_matrix": {
                    "status": "available",
                    "cells": [{"row": 1, "column": 2, "initial_level": -4.0}],
                    "total_cells": 1, "truncated": False,
                },
            }],
            "input_patches": [],
        },
    }
    monkeypatch.setattr(
        audio_patch_reader, "read_saved_audio_patches", lambda *args, **kwargs: saved,
    )
    monkeypatch.setattr(server_module, "_reader", FakeReader)

    result = server_module.qlab_get_audio_patch(
        WORKSPACE_ID, "output", PATCH_ID, "safe", 1, 2,
    )

    assert calls == [{
        "workspace_id": WORKSPACE_ID, "section": "audio", "kind": "output_patch",
        "ref": PATCH_ID, "profile": "safe", "input_channel": 1, "output_channel": 2,
    }]
    assert result["cell"]["live_osc"]["data"]["decibels"] == -6.0
    assert result["cell"]["saved_archive"]["data"] == {
        "row": 1, "column": 2, "initial_level": -4.0,
    }
    assert result["sources"]["live_osc"]["data"]["routing"] == [1, 2]
    assert "routing_matrix" not in result["sources"]["live_osc"]["data"]


@pytest.mark.parametrize(
    ("patch_type", "input_channel", "output_channel"),
    [("input", 1, 1), ("output", 1, None), ("output", None, 1)],
)
def test_audio_channel_query_rejects_invalid_combinations_before_reader(
    monkeypatch, patch_type, input_channel, output_channel,
) -> None:
    class FakeReader:
        calls = []

        def get_workspace_setting_details(self, **kwargs):
            self.calls.append(kwargs)
            raise AssertionError("invalid query must not reach OSC")

    reader = FakeReader()
    monkeypatch.setattr(server_module, "_reader", lambda: reader)

    with pytest.raises(Exception):
        server_module.qlab_get_audio_patch(
            WORKSPACE_ID, patch_type, PATCH_ID, "safe", input_channel, output_channel,
        )

    assert reader.calls == []


@pytest.mark.parametrize("field", ["input_channel", "output_channel"])
@pytest.mark.parametrize("value", [-1, True, 1.5, "1", 129])
def test_audio_channel_schema_rejects_invalid_values_before_reader(monkeypatch, field, value) -> None:
    def unexpected_reader():
        raise AssertionError("invalid channel must not construct a reader")

    monkeypatch.setattr(server_module, "_reader", unexpected_reader)

    async def rejected() -> None:
        arguments = {
            "workspace_id": WORKSPACE_ID,
            "patch_type": "output",
            "patch_id": PATCH_ID,
            "input_channel": 1,
            "output_channel": 1,
        }
        arguments[field] = value
        async with Client(mcp) as client:
            with pytest.raises(Exception):
                await client.call_tool("qlab_get_audio_patch", arguments)

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
