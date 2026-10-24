# Contributing

## Environment

Requirements: Python 3.11 or newer and `uv`.

```bash
uv sync --locked --no-editable --python 3.11 --extra dev
.venv/bin/python -c "import qlab_mcp; print(qlab_mcp.__version__)"
```

The locked non-editable installation matches the CI development environment.
Python 3.11 is the CI baseline; the package requires Python 3.11 or newer.
A successful run on one interpreter is not proof of every supported version.

For numerical audio integration tests, add `--extra audio` and provide FFmpeg
and ffprobe in the test process PATH. Without those prerequisites, optional
tests skip; a passing base suite does not validate decoding or audio measurements.
Keep generated fixtures and build outputs in temporary directories.

## Checks

```bash
.venv/bin/python -m pytest -q
uv lock --check
uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env
uv build --out-dir /tmp/qlab-mcp-build
git diff --check
```

CI runs the locked Python 3.11 base suite, lockfile verification and wheel/sdist
builds on Ubuntu. FastMCP inspection and documentation-link checks are additional
maintainer checks, not CI jobs. Some native/macOS, local-fixture and optional
audio tests skip on CI; record the observed skip count rather than treating
it as full runtime coverage.

The project does not currently configure a separate linter or type checker.
Do not add substitute checks as if they were official.

The FastMCP inspection must expose exactly the 83 tools listed in
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
- Put superseded implementation plans under `docs/archive/`. Dated research,
  runtime captures and reviews may remain in their development indexes for
  traceability; mark them as historical evidence and link current guidance.
- Do not edit imported QClass transcripts or OSC references.
- Keep historical commands literal; explain old paths in an index.
- New public prose and captures must use synthetic identities and generic paths.
  Keep original private evidence outside Git; preserve equality relationships and
  recorded outcomes when redacting. Historical screenshots and external/user
  quotations can retain user data; inspect them before any further redistribution.
- Do not replace old test totals or failed probes with current results. Add a
  dated supersession note and cite the source or bounded runtime evidence.
- Review all relevant source, schemas, examples, links and coverage tables when
  changing a documented contract; README alone is not an API audit.

Documentation-only checks must not connect to QLab. Use a temporary local link
scan, focused tests, and a temporary package build.

`skills/` and `.superpowers/` are optional ignored local directories, not
distributed repository requirements. Canonical QLab references remain under
`docs/references/` and `docs/sources/`. Reference extraction checks the canonical
Markdown by default; `--skill-copy` explicitly opts into a local portable copy.

## QLab safety

Tests are local fakes unless a separate runtime procedure is explicitly
authorized. Never use a real show for development writes. Runtime validation
requires exact workspace and cue UUIDs, inactive disposable cues, dry-run,
fresh tokens where required, one setter, fresh readback, and deterministic
rollback. Do not use playback, GO, Audition, raw OSC, Stop, or Panic.
