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
    assert overview.annotations.readOnlyHint is True
    assert overview.annotations.destructiveHint is False
    assert overview.annotations.idempotentHint is True
    assert overview.annotations.openWorldHint is True

    query = tools["qlab_query_cues"]
    assert query.title == "Query QLab Cues"
    assert "optional AND filters" in query.description
    assert query.annotations.readOnlyHint is True
    assert query.annotations.destructiveHint is False

    details = tools["qlab_get_cue_details"]
    assert details.title == "Get QLab Cue Details"
    assert "valuesForKeys" in details.description
    assert details.annotations.readOnlyHint is True
