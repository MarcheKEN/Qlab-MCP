---
name: fastmcp-python
description: Help users learn, design, build, test, and debug Python MCP servers, clients, tools, resources, prompts, transports, and configuration using the FastMCP framework. Use when the user asks about FastMCP, creating MCPs in Python, exposing Python functions as MCP tools, adding resources or prompts, running stdio or HTTP MCP servers, using the FastMCP Client, generating MCP JSON configuration, or choosing FastMCP patterns for an MCP project.
---

# FastMCP Python

## Overview

Use this skill to help users build practical MCP servers and clients with FastMCP in Python. Prefer small working examples, clear architecture choices, and verification steps.

The FastMCP docs reflect the project's `main` branch and may include unreleased features. When exact APIs matter, verify against the linked official docs before finalizing code.

## References

- `references/fastmcp-quick-guide.md`: local summary of core patterns and gotchas.
- `references/official-docs-index.md`: official documentation links to inspect for current details.

## Workflow

1. Identify the target: server, client, app UI, deployment, integration, or learning explanation.
2. For a server, start with `FastMCP("Name", instructions=...)`, then add the smallest useful set of tools, resources, and prompts.
3. Use tools for actions or computations the model should invoke. Use resources for read-only data. Use prompts for reusable message templates.
4. Add type annotations and concise docstrings to every tool/prompt. FastMCP uses them to generate schemas and descriptions.
5. Choose a transport deliberately:
   - `stdio`: local desktop/CLI integrations and single-user tools.
   - `http`: remote services, web deployment, and multiple clients.
   - `sse`: legacy compatibility only.
   - in-memory `Client(mcp)`: tests and development.
6. Include a verification path. Prefer `Client(mcp)` for fast in-process tests, or `fastmcp run server.py:mcp --transport http --port 8000` plus a client call for HTTP.
7. If the user asks for production or auth, consult the official docs index first. Do not guess auth/provider details from memory.

## Server Template

Use this as the default starting point for a simple server:

```python
from fastmcp import FastMCP

mcp = FastMCP(
    "ExampleServer",
    instructions="Use the available tools to answer questions about this service.",
)


@mcp.tool
def greet(name: str) -> str:
    """Return a friendly greeting for a person by name."""
    return f"Hello, {name}!"


if __name__ == "__main__":
    mcp.run()
```

For HTTP:

```python
if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8000)
```

CLI equivalents:

```bash
fastmcp run server.py:mcp
fastmcp run server.py:mcp --transport http --port 8000
fastmcp run server.py:mcp --reload
```

## Tools

Use `@mcp.tool` for executable capabilities. Keep schemas simple and explicit:

```python
from typing import Annotated
from pydantic import Field

@mcp.tool
def search_catalog(
    query: Annotated[str, Field(description="Search text provided by the user")],
    limit: Annotated[int, Field(10, ge=1, le=50, description="Maximum results")],
) -> list[dict]:
    """Search the product catalog."""
    return []
```

Guidelines:

- Do not use `*args` or `**kwargs`; FastMCP needs complete parameter schemas.
- Prefer async tools for I/O-heavy work.
- Sync tools run in a thread pool by default. For thread-affine libraries such as Windows COM, use `@mcp.tool(run_in_thread=False)` and keep the function short.
- Use `strict_input_validation=True` on the server only when type coercion would be unsafe.
- Return `dict`, Pydantic models, or dataclasses when the client needs structured output.
- Use `fastmcp.utilities.types.Image`, `Audio`, or `File` for media/file returns.
- Use `Depends()` for injected values that should not appear in the LLM-facing tool schema.

## Resources

Use `@mcp.resource("scheme://path")` for read-only data:

```python
import json

@mcp.resource("data://config")
def get_config() -> str:
    """Return application configuration as JSON."""
    return json.dumps({"theme": "dark", "version": "1.0"})
```

Use resources for data that the model reads, not actions it performs. Set `mime_type` explicitly for non-text or important structured data.

## Prompts

Use `@mcp.prompt` for reusable message templates:

```python
@mcp.prompt
def analyze_data(data_points: list[float]) -> str:
    """Create a prompt asking an LLM to analyze numeric data."""
    return f"Analyze these data points: {data_points}"
```

Use prompts when the server should package a repeatable instruction pattern, not when it should execute code.

## Client Testing

Use FastMCP's asynchronous client for deterministic tests:

```python
import asyncio
from fastmcp import Client
from server import mcp


async def main():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        result = await client.call_tool("greet", {"name": "Ada"})
        print(tools)
        print(result)


asyncio.run(main())
```

Notes:

- Always use `async with Client(...)` before calling operations.
- Use `Client(mcp)` for in-memory tests.
- Use `Client("server.py")` for stdio subprocess testing.
- Use `Client("http://localhost:8000/mcp")` for HTTP testing.
- STDIO subprocesses do not inherit all environment assumptions; pass required env explicitly when needed.

## Installation And Versioning

Install with:

```bash
pip install fastmcp
```

or:

```bash
uv add fastmcp
```

Verify with:

```bash
fastmcp version
```

For production projects, pin exact versions because FastMCP follows semantic versioning with pragmatic MCP ecosystem exceptions.

## When To Consult Official Docs

Open `references/official-docs-index.md` and inspect the linked page when the user asks about:

- Auth or OAuth providers.
- Deployment beyond local stdio or simple HTTP.
- Apps, interactive UI, or `app=True` tools.
- MCP JSON configuration for a specific client.
- FastAPI, OpenAPI, ChatGPT, Claude, Cursor, Gemini, or other integrations.
- Background tasks, elicitation, sampling, roots, middleware, providers, transforms, or custom routes.
- Version-specific behavior or migration from FastMCP 1/2 or the low-level MCP SDK.
