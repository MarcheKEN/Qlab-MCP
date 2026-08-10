from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs/references/qlab_applescript_dictionary.md"
HTML = ROOT / "docs/sources/qlab-5-applescript/applescript_dictionary_v5.local.html"
SKILL_COPY = ROOT / "skills/qlab-5-applescript/references/qlab_applescript_dictionary.md"
SKILL_MANIFEST = ROOT / "skills/qlab-5-applescript/references/source-manifest.json"


_EXTRACTOR_SPEC = importlib.util.spec_from_file_location(
    "qlab_applescript_extractor", ROOT / "scripts/extract_qlab_applescript.py"
)
assert _EXTRACTOR_SPEC and _EXTRACTOR_SPEC.loader
_EXTRACTOR = importlib.util.module_from_spec(_EXTRACTOR_SPEC)
sys.modules[_EXTRACTOR_SPEC.name] = _EXTRACTOR
_EXTRACTOR_SPEC.loader.exec_module(_EXTRACTOR)
to_markdown = _EXTRACTOR.to_markdown


def _section_entries(markdown: str, section: str, next_section: str | None) -> list[str]:
    start = re.search(rf"^# {re.escape(section)}$", markdown, re.MULTILINE)
    assert start
    end = re.search(rf"^# {re.escape(next_section)}$", markdown[start.end() :], re.MULTILINE) if next_section else None
    body = markdown[start.end() : start.end() + end.start()] if end else markdown[start.end() :]
    return re.findall(r"^## (.+)$", body, re.MULTILINE)


def test_dictionary_snapshot_has_expected_shape_and_lookup_fixtures() -> None:
    markdown = DOC.read_text(encoding="utf-8")
    assert HTML.stat().st_size > 1_000_000
    assert "# Commands" in markdown
    assert "# Classes" in markdown
    assert "# Enumerations" in markdown
    assert "# Records" in markdown
    assert not re.search(r"<(?:div|span|button|svg|table|script|style)(?:\s|>)", markdown)
    assert len(_section_entries(markdown, "Commands", "Classes")) == 52
    assert len(_section_entries(markdown, "Classes", "Enumerations")) == 23
    assert len(_section_entries(markdown, "Enumerations", "Records")) == 15
    assert len(_section_entries(markdown, "Records", None)) == 6
    for fixture in ("go", "load", "newCueWithChanges", "workspace", "fontName", "text format", "rgba color record", "com.figure53.QLab.5"):
        assert fixture in markdown
    assert markdown.count("```applescript") >= 100
    assert markdown.count("](#") >= 100
    assert "](#workspace)" in markdown
    assert "](#make)" in markdown
    assert "![" not in markdown  # the dictionary article currently has no embedded image


def test_each_command_keeps_a_syntax_block() -> None:
    markdown = DOC.read_text(encoding="utf-8")
    commands = _section_entries(markdown, "Commands", "Classes")
    command_section = re.search(r"^# Commands$", markdown, re.MULTILINE)
    classes_section = re.search(r"^# Classes$", markdown, re.MULTILINE)
    assert command_section and classes_section
    body = markdown[command_section.end() : classes_section.start()]
    for command in commands:
        match = re.search(rf"^## {re.escape(command)}$", body, re.MULTILINE)
        assert match, command
        next_heading = re.search(r"^## ", body[match.end() :], re.MULTILINE)
        entry = body[match.end() : match.end() + next_heading.start()] if next_heading else body[match.end() :]
        assert "```applescript" in entry, command


def test_portable_skill_copy_and_manifest_are_consistent() -> None:
    assert DOC.read_bytes() == SKILL_COPY.read_bytes()
    manifest = json.loads(SKILL_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["source_url"].endswith("applescript-dictionary-v5/")
    for item in manifest["files"]:
        path = ROOT / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]


def test_skill_and_agent_metadata_point_to_the_reference() -> None:
    skill = (ROOT / "skills/qlab-5-applescript/SKILL.md").read_text(encoding="utf-8")
    metadata = (ROOT / "skills/qlab-5-applescript/agents/openai.yaml").read_text(encoding="utf-8")
    agent = tomllib.loads((ROOT / ".codex/agents/qlab-applescript-researcher.toml").read_text(encoding="utf-8"))
    assert "name: qlab-5-applescript" in skill
    assert "references/qlab_applescript_dictionary.md" in skill
    assert "display_name: \"QLab 5 AppleScript\"" in metadata
    assert agent["name"] == "qlab_applescript_researcher"
    assert agent["sandbox_mode"] == "read-only"
    assert "qlab_applescript_dictionary.md" in agent["developer_instructions"]


def test_dictionary_agents_explicitly_load_their_skills() -> None:
    apple = (ROOT / ".codex/agents/qlab-applescript-researcher.toml").read_text(encoding="utf-8")
    osc = (ROOT / ".codex/agents/qlab-osc-researcher.toml").read_text(encoding="utf-8")
    assert "skills/qlab-5-applescript/SKILL.md" in apple
    assert "skills/qlab-5-applescript/chapters/navigation.md" in apple
    assert "skills/qlab-5-5-10-osc/SKILL.md" in osc
    assert "skills/qlab-5-5-10-osc/chapters/navigation.md" in osc
    assert "skills/qlab-5-5-10-osc/references/qlab_osc_dictionary.md" in osc


def test_converter_preserves_inline_links_and_images() -> None:
    source = """
    <div class="markdown markdown-table-docs docs-container">
      <h1 id="commands">Commands</h1>
      <p>See <a href="/docs/v5/scripting/applescript-dictionary-v5/#go">go</a>.
      <img alt="diagram" src="/assets/diagram.png"/></p>
    </div>
    """
    markdown = to_markdown(source)
    assert "[go](#go)" in markdown
    assert "![diagram](https://qlab.app/assets/diagram.png)" in markdown
