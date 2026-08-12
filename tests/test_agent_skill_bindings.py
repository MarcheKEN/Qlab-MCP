from __future__ import annotations

from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
AGENT_FILES = (
    ROOT / ".codex/agents/qlab-docs-researcher.toml",
    ROOT / ".codex/agents/fastmcp-mcp-researcher.toml",
)
LOCAL_AGENT_FIXTURES = pytest.mark.skipif(
    not all(path.is_file() for path in AGENT_FILES),
    reason="project-local .codex/agents fixtures are not part of the repository",
)


@LOCAL_AGENT_FIXTURES
def test_qlab_docs_agent_loads_global_and_project_reference_skills() -> None:
    instructions = (ROOT / ".codex/agents/qlab-docs-researcher.toml").read_text(encoding="utf-8")
    assert "qlab-docs-assistant/SKILL.md" in instructions
    assert "qlab-docs-assistant/references/official-source-map.md" in instructions
    assert "skills/qlab-5-5-10-reference/SKILL.md" in instructions
    assert "skills/qlab-5-5-10-reference/chapters/" in instructions
    assert "qlab_applescript_researcher" in instructions


@LOCAL_AGENT_FIXTURES
def test_fastmcp_agent_loads_the_installed_fastmcp_skill() -> None:
    instructions = (ROOT / ".codex/agents/fastmcp-mcp-researcher.toml").read_text(encoding="utf-8")
    assert "fastmcp/SKILL.md" in instructions
    assert "fastmcp/references/fastmcp-cli.md" in instructions
    assert "do not scaffold" in instructions
    assert "pyproject.toml and uv.lock" in instructions
