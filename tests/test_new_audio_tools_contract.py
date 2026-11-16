"""Public audio tools expose the task-oriented surface."""
import asyncio
from fastmcp import Client
from qlab_mcp.server import mcp


def test_audio_tools_replace_legacy_public_surface():
    async def names():
        async with Client(mcp) as client:
            return {item.name for item in await client.list_tools()}

    tools = asyncio.run(names())
    assert {"qlab_get_workspace_audio_settings", "qlab_get_audio_patch",
            "qlab_edit_audio_patch", "qlab_edit_workspace_audio_settings"} <= tools
    assert not {"qlab_get_saved_audio_patches", "qlab_edit_saved_audio_patches",
                "qlab_edit_audio_output_patch"} & tools
