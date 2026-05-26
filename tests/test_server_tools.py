from __future__ import annotations

import asyncio

from fastmcp import Client
from fastmcp.exceptions import ToolError

from qlab_mcp.errors import QLabReplyError
from qlab_mcp.server import (
    CHECK_CONNECTION_TIMEOUT,
    CREATE_CUE_TIMEOUT,
    CUE_DETAILS_TIMEOUT,
    QUERY_CUES_TIMEOUT,
    UPDATE_CUE_TIMEOUT,
    WORKSPACE_OVERVIEW_TIMEOUT,
    WORKSPACE_SETTING_DETAILS_TIMEOUT,
    WORKSPACE_SETTINGS_TIMEOUT,
    WRITE_READINESS_TIMEOUT,
    _run_tool,
    mcp,
    qlab_query_cues,
)


def test_tool_metadata_exposes_titles_descriptions_and_read_only_annotations() -> None:
    async def list_tools():
        async with Client(mcp) as client:
            return await client.list_tools()

    tools = {tool.name: tool for tool in asyncio.run(list_tools())}
    assert set(tools) == {
        "qlab_check_connection",
        "qlab_get_workspace_overview",
        "qlab_get_workspace_settings",
        "qlab_get_workspace_setting_details",
        "qlab_query_cues",
        "qlab_get_cue_details",
        "qlab_check_write_readiness",
        "qlab_create_cue",
        "qlab_update_cue",
    }

    check = tools["qlab_check_connection"]
    assert check.title == "Check QLab Connection"
    assert "passcode" in check.description
    assert "/connect permission scopes" in check.description
    assert check.annotations.readOnlyHint is True
    assert check.annotations.destructiveHint is False

    overview = tools["qlab_get_workspace_overview"]
    assert overview.title == "Get QLab Workspace Overview"
    assert "first structural read" in overview.description
    assert overview.inputSchema["properties"]["cue_index_profile"]["default"] == "minimal"
    assert overview.inputSchema["properties"]["max_index_cues"]["maximum"] == 5000
    assert overview.annotations.readOnlyHint is True
    assert overview.annotations.destructiveHint is False
    assert overview.annotations.idempotentHint is True
    assert overview.annotations.openWorldHint is True

    settings = tools["qlab_get_workspace_settings"]
    assert settings.title == "Get QLab Workspace Settings"
    assert "Workspace Settings" in settings.description
    assert settings.annotations.readOnlyHint is True
    assert settings.annotations.destructiveHint is False
    assert "profile" not in settings.inputSchema["properties"]

    setting_details = tools["qlab_get_workspace_setting_details"]
    assert setting_details.title == "Get QLab Workspace Setting Details"
    assert "default safe profile" in setting_details.description
    assert setting_details.inputSchema["properties"]["profile"]["default"] == "safe"
    assert setting_details.annotations.readOnlyHint is True
    assert setting_details.annotations.destructiveHint is False

    query = tools["qlab_query_cues"]
    assert query.title == "Query QLab Cues"
    assert "optional AND filters" in query.description
    assert query.inputSchema["properties"]["max_results"]["default"] == 500
    assert query.inputSchema["properties"]["max_results"]["maximum"] == 5000
    assert query.inputSchema["properties"]["max_cues_scanned"]["default"] == 500
    assert query.inputSchema["properties"]["max_cues_scanned"]["maximum"] == 5000
    query_filters = set(query.inputSchema["properties"]["primary_filter"]["enum"])
    assert {"name_empty", "displayName_empty", "number_empty", "ambiguous_label", "flagged_or_broken"} <= query_filters
    assert query.annotations.readOnlyHint is True
    assert query.annotations.destructiveHint is False

    details = tools["qlab_get_cue_details"]
    assert details.title == "Get QLab Cue Details"
    assert "valuesForKeys" in details.description
    assert "editable" in details.inputSchema["properties"]["profile"]["enum"]
    assert details.annotations.readOnlyHint is True

    readiness = tools["qlab_check_write_readiness"]
    assert readiness.title == "Check QLab Write Readiness"
    assert "without sending any mutating OSC commands" in readiness.description
    assert readiness.annotations.readOnlyHint is True
    assert readiness.annotations.destructiveHint is False
    assert "workspace_id" in readiness.inputSchema["required"]

    create = tools["qlab_create_cue"]
    assert create.title == "Create QLab Cue"
    assert "dry-run plan" in create.description
    assert create.annotations.readOnlyHint is False
    assert create.annotations.destructiveHint is False
    assert create.annotations.idempotentHint is False
    assert create.inputSchema["properties"]["cue_type"]["enum"] == [
        "memo",
        "group",
        "wait",
        "audio",
    ]
    assert "dry_run" in create.inputSchema["properties"]
    assert "workspace_id" in create.inputSchema["required"]
    assert "cue_type" in create.inputSchema["required"]

    update = tools["qlab_update_cue"]
    assert update.title == "Update QLab Cue"
    assert "Dry-run planning" in update.description
    assert update.annotations.readOnlyHint is False
    assert update.annotations.destructiveHint is False
    assert update.annotations.idempotentHint is False
    assert "workspace_id" in update.inputSchema["required"]
    assert "cue_ref" in update.inputSchema["required"]
    assert "properties" not in update.inputSchema["required"]
    assert "operations" in update.inputSchema["properties"]
    assert update.inputSchema["properties"]["profile"]["enum"] == [
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
    ]


def test_server_masks_internal_error_details_and_sets_tool_timeouts() -> None:
    async def tool_timeouts():
        return {
            name: (await mcp.get_tool(name)).timeout
            for name in (
                "qlab_check_connection",
                "qlab_get_workspace_overview",
                "qlab_get_workspace_settings",
                "qlab_get_workspace_setting_details",
                "qlab_query_cues",
                "qlab_get_cue_details",
                "qlab_check_write_readiness",
                "qlab_create_cue",
                "qlab_update_cue",
            )
        }

    assert mcp._mask_error_details is True
    assert asyncio.run(tool_timeouts()) == {
        "qlab_check_connection": CHECK_CONNECTION_TIMEOUT,
        "qlab_get_workspace_overview": WORKSPACE_OVERVIEW_TIMEOUT,
        "qlab_get_workspace_settings": WORKSPACE_SETTINGS_TIMEOUT,
        "qlab_get_workspace_setting_details": WORKSPACE_SETTING_DETAILS_TIMEOUT,
        "qlab_query_cues": QUERY_CUES_TIMEOUT,
        "qlab_get_cue_details": CUE_DETAILS_TIMEOUT,
        "qlab_check_write_readiness": WRITE_READINESS_TIMEOUT,
        "qlab_create_cue": CREATE_CUE_TIMEOUT,
        "qlab_update_cue": UPDATE_CUE_TIMEOUT,
    }


def test_expected_tool_errors_are_sanitized() -> None:
    def denied_with_sensitive_payload() -> None:
        raise QLabReplyError(
            "denied",
            {"fileTarget": "/Users/stage/secret.wav", "passcode": "1234"},
            "/workspace/ws-1/settings/network/patchList",
        )

    try:
        _run_tool(denied_with_sensitive_payload)
    except ToolError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ToolError")

    assert "denied" in message
    assert "secret.wav" not in message
    assert "1234" not in message
    assert "patchList" not in message


def test_tool_wrapper_converts_validation_errors_to_tool_error() -> None:
    try:
        qlab_query_cues("ws-1", "type", "Audio", max_results=0)
    except ToolError as exc:
        assert "max_results must be 1 or greater" in str(exc)
    else:
        raise AssertionError("Expected ToolError")
