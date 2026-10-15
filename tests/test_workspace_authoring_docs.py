from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from fastmcp import Client
from jsonschema import Draft202012Validator
import yaml

from qlab_mcp.server import mcp


ROOT = Path(__file__).resolve().parents[1]
GUIDE = ROOT / "docs/user/workspace-authoring.md"
SKILL = ROOT / ".agents/skills/qlab-workspace-authoring/SKILL.md"


def test_workspace_authoring_examples_match_public_schemas() -> None:
    async def inventory():
        async with Client(mcp) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    tools = asyncio.run(inventory())
    text = GUIDE.read_text(encoding="utf-8")
    references = set(re.findall(r"`(qlab_[a-z_]+)`", text))
    assert references <= tools.keys(), references - tools.keys()
    examples = re.findall(
        r"Request tool: `(qlab_[a-z_]+)`\s+```json\n(.*?)\n```",
        text,
        re.DOTALL,
    )
    assert len(examples) == 3
    for name, raw in examples:
        payload = json.loads(raw)
        Draft202012Validator(tools[name].inputSchema).validate(payload)
        assert payload["dry_run"] is True
        assert all(not update.get("confirm_gates") for update in payload["updates"])


def test_workspace_authoring_skill_and_local_links() -> None:
    text = SKILL.read_text(encoding="utf-8")
    header = yaml.safe_load(text.split("---", 2)[1])
    assert header["name"] == SKILL.parent.name
    assert isinstance(header["description"], str) and header["description"]
    linked = []
    for path in (GUIDE, SKILL):
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if "://" in target or target.startswith("#"):
                continue
            resolved = (path.parent / target.split("#", 1)[0]).resolve()
            assert resolved.is_file(), (path, target)
            linked.append(resolved)
    assert GUIDE.resolve() in linked
    assert SKILL.resolve() in linked
