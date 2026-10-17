"""Capture one reviewed MCP call, without retries. JSON request on stdin.

Usage: PYTHONPATH=src .venv/bin/python scripts/capture_move_delete.py SERVER OUTPUT.json < request.json
SERVER is a FastMCP client URL or an MCP configuration file. A real write needs
--execute plus dry_run=false and its reviewed confirmation token in request.json.
Keep raw request files private: confirmation tokens are never written to OUTPUT.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

from fastmcp import Client
from qlab_mcp.allowlist import SENSITIVE_CUE_PROPERTIES
from qlab_mcp.sanitizer import sanitize_response


SENSITIVE_KEYS = {key.casefold() for key in SENSITIVE_CUE_PROPERTIES} | {"confirm_token", "passcode", "password", "secret", "token", "authorization"}


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: "[redacted]" if key.casefold() in SENSITIVE_KEYS else redact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (ValueError, TypeError):
            pass
        else:
            if isinstance(parsed, (dict, list)):
                return json.dumps(redact(parsed), ensure_ascii=False)
        return re.sub(r"confirm:[^\s\"'<>]+", "[redacted_token]", value)
    return value


async def capture_call(client: Client, request: dict[str, Any]) -> dict[str, Any]:
    started = time.monotonic()
    try:
        reply = await client.call_tool_mcp(request["tool"], request["arguments"])
        response = reply.model_dump(mode="json", by_alias=True)
    except Exception as exc:
        response = {"exception_type": type(exc).__name__, "error": str(exc)}
    return redact(sanitize_response({"request": request, "response": response,
                                    "elapsed_ms": round((time.monotonic() - started) * 1000)}))


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server")
    parser.add_argument("output", type=Path)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    request = json.load(sys.stdin)
    if request.get("tool") not in {"qlab_create_cues", "qlab_move_cues", "qlab_move_cue_lists", "qlab_delete_cues"}:
        parser.error("Only Create, Move and Delete calls are accepted.")
    arguments = request.get("arguments", {})
    if arguments.get("dry_run") is not True:
        if not args.execute or arguments.get("dry_run") is not False or not arguments.get("confirm_token"):
            parser.error("Execution requires --execute, dry_run=false and a reviewed confirmation token.")
    # Refuse to overwrite existing evidence before sending any call.
    with args.output.open("x", encoding="utf-8") as output:
        try:
            server = json.loads(Path(args.server).read_text()) if Path(args.server).is_file() else args.server
            async with Client(server) as client:
                evidence = await capture_call(client, request)
        except Exception as exc:
            evidence = redact({"exception_type": type(exc).__name__, "error": str(exc)})
        json.dump(evidence, output, ensure_ascii=False, indent=2)
        output.write("\n")


if __name__ == "__main__":
    asyncio.run(main())
