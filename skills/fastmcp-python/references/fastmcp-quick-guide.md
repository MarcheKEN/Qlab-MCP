# FastMCP Quick Guide

Snapshot based on official FastMCP docs checked on 2026-05-15.

## Core model

FastMCP is a Python framework for building MCP servers, clients, and apps. A `FastMCP` server contains components:

- Tools: Python functions an MCP client can invoke.
- Resources: read-only data sources accessed by URI.
- Prompts: parameterized message templates.

## Minimal server

```python
from fastmcp import FastMCP

mcp = FastMCP("My MCP Server")

@mcp.tool
def greet(name: str) -> str:
    return f"Hello, {name}!"

if __name__ == "__main__":
    mcp.run()
```

Run with:

```bash
python server.py
fastmcp run server.py:mcp
fastmcp run server.py:mcp --transport http --port 8000
```

## Component choices

Use a tool when:

- The client should perform an action.
- The result depends on arguments.
- The operation may call APIs, compute, write, mutate, or trigger side effects.

Use a resource when:

- The client should read data.
- The URI identifies the data.
- The operation should be passive and read-only.

Use a prompt when:

- The server should provide a reusable LLM instruction template.
- Arguments are used to fill the message.

## Validation and schemas

- FastMCP derives input schemas from Python signatures and type annotations.
- Parameters without defaults are required; parameters with defaults are optional.
- Pydantic flexible validation is the default and can coerce compatible values.
- Use `FastMCP(..., strict_input_validation=True)` when coercion is undesirable.
- Avoid `*args` and `**kwargs` in tools and prompts.
- Use `Annotated` and `pydantic.Field` when parameters need descriptions or constraints.

## Return values

- `str` becomes text content.
- `dict`, dataclasses, and Pydantic models are good defaults for structured output.
- Annotate primitive/list returns when clients need structured content.
- Use FastMCP media helper classes for images, audio, and files.

## Transports

- `stdio`: default, best for local clients and desktop integrations.
- `http`: Streamable HTTP, best for remote services and production-style testing.
- `sse`: legacy; avoid for new deployments unless required.
- in-memory client transport: best for tests with `Client(mcp)`.

## Client basics

```python
import asyncio
from fastmcp import Client

client = Client("http://localhost:8000/mcp")

async def main():
    async with client:
        await client.ping()
        tools = await client.list_tools()
        result = await client.call_tool("greet", {"name": "Ada"})
        print(result)

asyncio.run(main())
```

All client operations require the async context manager.

## Common gotchas

- The FastMCP CLI imports the server object; it does not execute the script's `if __name__ == "__main__"` block.
- Use `run_async()` inside an existing async context; use `run()` in normal synchronous scripts.
- STDIO client subprocesses need explicit environment variables if the server depends on secrets or config.
- Sync tools run in a thread pool unless `run_in_thread=False`.
- Use HTTP endpoint `/mcp` when connecting to an HTTP server.
- Pin exact FastMCP versions in production.
