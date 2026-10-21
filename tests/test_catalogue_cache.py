"""Cache static tool definitions without caching tool execution or its data."""

import asyncio

from fastmcp import Client
from fastmcp.server.middleware.caching import ResponseCachingMiddleware
from fastmcp.server.middleware.dereference import DereferenceRefsMiddleware

import qlab_mcp.server as server


def test_catalogue_reuses_schemas_but_tool_calls_stay_fresh(monkeypatch):
    caches = [item for item in server.mcp.middleware if isinstance(item, ResponseCachingMiddleware)]
    assert len(caches) == 1
    cache = caches[0]
    for settings in (cache._call_tool_settings, cache._read_resource_settings, cache._get_prompt_settings,
                     cache._list_resources_settings, cache._list_prompts_settings):
        assert settings["enabled"] is False

    expansions = []
    original = DereferenceRefsMiddleware.on_list_tools

    async def record(self, context, call_next):
        expansions.append(1)
        return await original(self, context, call_next)

    monkeypatch.setattr(DereferenceRefsMiddleware, "on_list_tools", record)
    calls = []

    def search(*args):
        calls.append(args)
        return {"files": [], "scanned_entries": len(calls), "truncated": False, "warnings": []}

    monkeypatch.setattr(server, "search_media_files", search)

    async def run():
        async with Client(server.mcp) as client:
            first = await client.list_tools()
            second = await client.list_tools()
            assert [tool.model_dump() for tool in first] == [tool.model_dump() for tool in second]
            assert len(first) == 82
            for expected in (1, 2):
                result = await client.call_tool("qlab_search_media_files", {"query": "fixture"})
                assert result.structured_content["scanned_entries"] == expected
            monkeypatch.setattr(server, "search_media_files", lambda *args: None)
            invalid = await client.call_tool("qlab_search_media_files", {"query": "fixture"}, raise_on_error=False)
            assert invalid.is_error

    asyncio.run(run())
    assert len(expansions) <= 1
    assert len(calls) == 2
