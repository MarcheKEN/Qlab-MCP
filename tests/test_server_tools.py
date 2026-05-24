from __future__ import annotations

import asyncio

from fastmcp import Client

from qlab_mcp.server import mcp


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
    }

    check = tools["qlab_check_connection"]
    assert check.title == "Check QLab Connection"
    assert "passcode" in check.description
    assert "edit/control" in check.description
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
    assert query.annotations.readOnlyHint is True
    assert query.annotations.destructiveHint is False

    details = tools["qlab_get_cue_details"]
    assert details.title == "Get QLab Cue Details"
    assert "valuesForKeys" in details.description
    assert details.annotations.readOnlyHint is True
