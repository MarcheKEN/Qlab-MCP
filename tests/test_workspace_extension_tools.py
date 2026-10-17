import asyncio

from fastmcp import Client

from qlab_mcp.server import mcp


def test_documentary_fx_catalogue_needs_no_reader(monkeypatch):
    from qlab_mcp import server
    monkeypatch.setattr(server, '_reader', lambda: (_ for _ in ()).throw(AssertionError('No QLab connection')))

    async def run():
        async with Client(mcp) as client:
            result = await client.call_tool_mcp('qlab_get_video_effect_catalogue', {'effect_types': ['Window']})
            assert result.structuredContent['effect_count'] == 60
            assert result.structuredContent['effects'][0]['type'] == 'Window'
            tools = {tool.name: tool for tool in await client.list_tools()}
            assert tools['qlab_get_video_effect_catalogue'].annotations.readOnlyHint
    asyncio.run(run())


def test_workspace_document_tools_publish_typed_signed_contracts():
    async def run():
        async with Client(mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
        expected = {
            'qlab_get_workspace_document': {'workspace_id'},
            'qlab_open_workspace': {'path', 'dry_run', 'confirm_token'},
            'qlab_save_workspace': {'workspace_id', 'dry_run', 'confirm_token'},
            'qlab_close_workspace': {'workspace_id', 'dry_run', 'confirm_token'},
        }
        assert set(expected) <= set(tools)
        for name, fields in expected.items():
            tool = tools[name]
            assert set(tool.inputSchema['properties']) == fields
            assert tool.outputSchema
            assert tool.annotations.readOnlyHint is (name == 'qlab_get_workspace_document')
        assert tools['qlab_open_workspace'].annotations.destructiveHint is False
        assert tools['qlab_save_workspace'].annotations.destructiveHint is True
        assert tools['qlab_close_workspace'].annotations.destructiveHint is True
    asyncio.run(run())
