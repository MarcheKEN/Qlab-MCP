from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_qlab_docs_agent_loads_global_and_project_reference_skills() -> None:
    instructions = (ROOT / ".codex/agents/qlab-docs-researcher.toml").read_text(encoding="utf-8")
    assert "qlab-docs-assistant/SKILL.md" in instructions
    assert "qlab-docs-assistant/references/official-source-map.md" in instructions
    assert "skills/qlab-5-5-10-reference/SKILL.md" in instructions
    assert "skills/qlab-5-5-10-reference/chapters/" in instructions
    assert "qlab_applescript_researcher" in instructions


def test_fastmcp_agent_loads_the_installed_fastmcp_skill() -> None:
    instructions = (ROOT / ".codex/agents/fastmcp-mcp-researcher.toml").read_text(encoding="utf-8")
    assert "fastmcp/SKILL.md" in instructions
    assert "fastmcp/references/fastmcp-cli.md" in instructions
    assert "do not scaffold" in instructions
    assert "pyproject.toml and uv.lock" in instructions
