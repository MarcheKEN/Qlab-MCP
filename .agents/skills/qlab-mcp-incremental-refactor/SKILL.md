---
name: qlab-mcp-incremental-refactor
description: Use when working in this QLab-MCP repository on incremental refactoring, modularization, hotspot reduction, oversized PR splitting, changes in src/qlab_mcp/server.py, write/operations.py, Pydantic models, public contract tests, or implementation of docs/references/deep-research-report.md recommendations. Guides small safe PRs that preserve the public FastMCP/MCP contract and gated QLab write-mode safety.
---

# QLab-MCP Incremental Refactor

Use this skill to plan and execute cautious refactoring work in this repository. Treat the Deep Research report as guidance, not an order.

## Verified Project Facts

- QLab-MCP is a FastMCP server for QLab 5 over OSC.
- `src/qlab_mcp/server.py` creates the `FastMCP` server, registers public tools with `@mcp.tool`, masks error details, and documents that the server exposes no GO, stop, panic, raw OSC, or playback control.
- MCP tool names, tool parameters, annotations, timeouts, input schemas, and output schemas are public contract protected by `tests/test_server_tools.py`.
- `src/qlab_mcp/qlab.py` is the compatibility facade. It uses mixins for workspace connection, cues, settings, status, query/details, and write mode.
- `src/qlab_mcp/models.py` contains public Pydantic request/response models for read and write tools.
- `src/qlab_mcp/write/operations.py` is large and high risk. It handles dry-run planning, write readiness, confirm tokens, execution, and verification.
- `src/qlab_mcp/write/registry.py` is data-driven update-profile registry code. `src/qlab_mcp/write/allowlist.py` is a compatibility facade over registry validation.
- Read-only behavior is the default. Write mode is separate, gated, disabled unless configured, and dry-run-first.

## Non-Negotiable Rules

- Preserve the public FastMCP/MCP contract.
- Do not rename tools without explicit approval.
- Do not rename public parameters without explicit approval.
- Do not change public Pydantic response models without a concrete reason and contract-test plan.
- Do not change contract snapshots or hashes unless the public change is intentional and explained.
- Never update contract snapshots or schema hashes just to make tests pass. If a snapshot or hash changes, first explain exactly what public contract changed and ask for approval unless the public change was explicitly requested.
- Keep read-only tools read-only.
- Keep write mode separate, gated, and dry-run-first.
- Do not add GO, playback, stop, panic, delete, or raw OSC tools.
- Do not allow write targets that use ambiguous cue refs such as `selected`, `active`, `playhead`, or `playbackPosition`.
- Do not mix refactoring with behavior changes unless unavoidable.
- Do not perform large-scale refactors. Reduce broad requests to the smallest safe first PR.

## High-Risk Files

Treat these as hotspots:

- `src/qlab_mcp/server.py`
- `src/qlab_mcp/models.py`
- `src/qlab_mcp/qlab.py`
- `src/qlab_mcp/write/operations.py`
- `src/qlab_mcp/write/registry.py`
- `src/qlab_mcp/write/allowlist.py`
- `tests/test_server_tools.py`
- `tests/test_write_mode.py`
- `tests/test_qlab_reader.py`

When touching any hotspot:

- Explain why the touch is necessary.
- Keep the diff small.
- Avoid formatting-only churn.
- Avoid combining unrelated concerns.
- Run the focused protective tests.
- Summarize remaining risk.

## First Response Workflow

When this skill is used for a future task, do not edit code immediately. First respond with:

1. Recommended first safe phase.
2. Files to touch.
3. Tests to run.
4. Risks.
5. Out of scope.

Only modify code after the user explicitly asks to proceed.

## Working Process

1. Read the user task.
2. Read the relevant part of `docs/references/deep-research-report.md` if available.
3. Verify the recommendation against the real code before accepting it.
4. Identify affected files.
5. Identify protective tests.
6. Propose the smallest safe plan.
7. If the request is too broad, reduce it to the first reviewable PR.
8. Preserve external behavior unless the user explicitly requests a behavior change.
9. Keep docs-only, tests-only, and runtime changes separate when practical.
10. End with changes, tests, behavior preserved, risks, and next phase.

## Treat These Report Ideas As Later-Phase

Require characterization tests, small PRs, behavior validation, and human review before doing any of these:

- Split `models.py`.
- Change `QLabReader` from mixins to composition.
- Reorganize the whole `tests/` directory.
- Add automatic registration in `write/registry.py`.
- Move many tools out of `server.py`.
- Split all of `write/operations.py` at once.

These may be useful later, but they are risky as first steps.

## Preferred Small PR Shapes

Favor one small concern per PR:

- Characterization-tests-only PR.
- Architecture-documentation-only PR.
- Server error/response helper extraction PR.
- Write planning extraction PR.
- Write validation extraction PR.
- Write execution or verification extraction PR.
- Documentation update PR.
- Preparation-only PR for a later phase.

Treat PR #9 as an example of an oversized mixed-concern PR. Future work of that shape should be split into smaller PRs that separate docs, tests, registry changes, runtime logic, and operation-specific behavior.

Avoid:

- Huge PRs.
- PRs that mix docs, runtime code, tests, and roadmap updates unnecessarily.
- PRs that change `server.py`, `models.py`, and `write/operations.py` together.
- Splitting `models.py` as the first step.
- Changing `QLabReader` mixins to composition as the first step.
- Introducing automatic registry behavior without a prior test-safety phase.

## Extracting From `write/operations.py`

Prefer extracting one responsibility at a time:

- Planning.
- Validation.
- Execution.
- Verification.
- Result building.
- Timeout handling.

Do not split many cue families in the same PR.

## Protective Tests

Choose the smallest relevant check:

```bash
uv run pytest tests/test_server_tools.py
```

Use for FastMCP tool, schema, annotation, timeout, or `server.py` changes.

```bash
uv run pytest tests/test_write_mode.py
uv run pytest tests/test_update_registry_coverage.py
```

Use for write-mode, registry, allowlist, dry-run, confirm-token, execution, or verification changes.

```bash
uv run pytest tests/test_qlab_reader.py
```

Use for `QLabReader`, workspace resolution, read caching, cue/settings/status/query/detail read behavior, or OSC read fallback changes.

```bash
uv run pytest tests/test_osc.py
```

Use for OSC encoding, decoding, addressing, transport, port, timeout, or SLIP changes.

```bash
uv run pytest
```

Use for broad changes or any change crossing public contract plus write behavior.

If tests cannot run, explain why and state the smallest alternative check performed.

## Final Response Format

End with:

- Summary of changes.
- Files touched.
- Behavior preserved.
- Tests run.
- Risks or open questions.
- Suggested next phase.
