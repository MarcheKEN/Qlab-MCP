# Contributing

## Environment

Requirements: Python 3.11 or newer and `uv`.

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run python -c "import qlab_mcp; print(qlab_mcp.__version__)"
```

The observed import failure is related to the editable project installation in
the environment, not specifically to Python 3.12. The non-editable sync above
provides the reproducible Python 3.11 development environment.

## Checks

```bash
.venv/bin/pytest -q
uv lock --check
uv run fastmcp inspect fastmcp.json
uv build --out-dir /tmp/qlab-mcp-build
git diff --check
```

The project does not currently configure a separate linter or type checker.
Do not add substitute checks as if they were official.

The FastMCP inspection must expose exactly the 14 tools listed in
[`docs/user/tools.md`](docs/user/tools.md). The schemas and contract tests in
`tests/test_server_tools.py` remain authoritative.

## Language policy

English is the canonical language of the QLab MCP repository. All
repository-authored source comments, docstrings, MCP-facing text, documentation,
tests, skills, agent instructions, process artifacts, and project-configuration
prose must be written in English.

Non-English content is permitted only when it is intentionally preserved user
data, multilingual test input, an external or source quotation, a proper name,
or a protocol/API literal. Future contributions must follow this rule.

## Documentation

- Put user operation material under `docs/user/`.
- Put maintenance and validation material under `docs/development/`.
- Put current roadmap, coverage, and unfinished work under `docs/status/`.
- Put completed, superseded, or evidentiary material under `docs/archive/`.
- Do not edit imported QClass transcripts or OSC references.
- Keep historical commands literal; explain old paths in an index.
- Never include local paths, real workspace names, media paths, or QLab UUIDs.

Documentation-only checks must not connect to QLab. Use a temporary local link
scan, focused tests, and a temporary package build.

## QLab safety

Tests are local fakes unless a separate runtime procedure is explicitly
authorized. Never use a real show for development writes. Runtime validation
requires exact workspace and cue UUIDs, inactive disposable cues, dry-run,
fresh tokens where required, one setter, fresh readback, and deterministic
rollback. Do not use playback, GO, Audition, raw OSC, Stop, or Panic.
