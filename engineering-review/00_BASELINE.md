# 00 — Baseline

Captured: 2026-07-18 21:59 CEST

## Repository and runtime

| Field | Value | Evidence |
| --- | --- | --- |
| Repository path | `/Users/filarmonica/Documents/qlab-mcp-osc` | `pwd` |
| Current branch | `codex/refactor` | `git branch --show-current` |
| Current commit | `f370d6719b4f93b39b3cef3ce03c2abbcf6452ef` | `git rev-parse HEAD` |
| Git status before review artifacts | Clean; no tracked or untracked files outside `engineering-review/` | `git status --short -- . ':(exclude)engineering-review'` |
| Pre-existing modified files | None detected | same status check |
| Pre-existing untracked files | None detected | same status check |
| Host runtime | Python 3.14.5 | `python3 --version` |
| Project virtual environment | Python 3.14.5 | `.venv/bin/python --version` |
| Dependency manager | uv 0.11.28 | `uv --version`, `uv.lock` |
| Build system | Hatchling | `pyproject.toml` `[build-system]` |
| Packaging system | PEP 621 `pyproject.toml`, Hatch wheel target | `pyproject.toml` |
| Test framework | pytest >=8 | `pyproject.toml` |
| Linting tools | None configured or documented | `pyproject.toml`, README/docs search |
| Formatting tools | None configured or documented | `pyproject.toml`, README/docs search |
| Type-checking tools | None configured or documented | `pyproject.toml`, README/docs search |
| Main application entry point | `qlab-mcp = qlab_mcp.server:main` | `pyproject.toml` |
| FastMCP object entry point | `src/qlab_mcp/server.py:mcp` | `fastmcp.json` |
| MCP transport | STDIO | `fastmcp.json` |
| Project version | 0.2.0 | `pyproject.toml` |
| FastMCP version | 3.3.1 | installed package metadata |
| MCP SDK version | 1.27.1 | installed package metadata |
| Pydantic version | 2.13.4 | installed package metadata |

No `CONTRIBUTING.md` or `CHANGELOG.md` is present. Repository-local Codex agent configuration exists under `.codex/` and is intentionally ignored through `.git/info/exclude`.

## Live QLab baseline

The baseline used the project's read-only `qlab_check_connection` tool. No playback or mutation occurred.

| Field | Value |
| --- | --- |
| Detected QLab version | 5.5.10 |
| Open workspace name | `mcp_prueba.qlab5` |
| Open workspace unique ID | `95F0A03D-140E-4673-974A-E76748EBB023` |
| Workspace count | 1 |
| Configured OSC input port | 53000 |
| Configured OSC reply port | 53001 |
| Host | 127.0.0.1 |
| Runtime request timeout | 5 seconds reported by connection tool; project configuration default is 2 seconds |
| OSC transport | UDP |
| Passcode | Configured and accepted; value not exposed |
| `/connect` scopes | `view`, `edit`, `control` confirmed |
| Workspace mode | Edit (`show_mode=false`) |
| Safe read probe | `/cueLists/shallow`, 11 cue lists |
| Write readiness | Ready; write enabled, passcode present, edit confirmed, Edit Mode confirmed, dry-run default true |

### Safety consequence

QLab reported all application override output families enabled, including DMX, MIDI, network, MSC, SysEx, and timecode output. The study therefore forbids playback and output-producing cues. Any mutation must be limited to an inactive dedicated test cue, use saved non-output metadata or another proven reversible property, and follow baseline → dry-run → exact token if required → one write → fresh readback → fresh rollback → final readback.

## Project shape

- Production Python: 27,668 lines across 42 files.
- Tests: 24,842 lines across 8 files.
- Total `src/` + `tests/`: 52,510 lines.
- Largest production file: `src/qlab_mcp/write/operations.py` at 12,063 lines.
- Largest test file: `tests/test_write_mode.py` at 16,862 lines.
- Direct runtime dependencies: FastMCP and Pydantic only.

## Guidance read

- User-provided `AGENTS.md` instructions.
- `README.md`.
- `pyproject.toml`, `uv.lock`, and `fastmcp.json`.
- `docs/README.md`, `docs/current/README.md`, current architecture snapshot, active roadmap, references, QClass index/material routes, and workorder indexes.
- `.codex/config.toml` and the three repository-local specialist agent definitions.

The existing architecture graph explicitly labels itself “current-ish” and asks readers to regenerate or audit it. It is treated as a lead, not as proof.
