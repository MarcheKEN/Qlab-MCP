# Current Project State

Provisional preparation snapshot: **2026-08-13 Europe/Madrid**.

This document describes the QLab MCP 0.3.0 preparation branch. The definitive
canonical snapshot will be updated through a docs-only PR after the merge into
`main`, before the `v0.3.0` tag.

## Preparation Git State

```text
branch: codex/docs
HEAD: local preparation; run `git rev-parse HEAD` to query it
base: origin/main verified before starting; the branch contains local preparation commits
worktree: local 0.3.0 preparation commit; snapshot still provisional
```

The remote reference was verified with `git fetch origin` and
`git ls-remote origin refs/heads/main` before starting.

## Preparation Objective

- contractual version `0.3.0`;
- exactly 13 public FastMCP tools;
- `qlab_edit_cues` as the only public edit tool;
- reproducible CI in a clean checkout;
- current documentation and audited workorders;
- architectural audit without speculative refactoring.

## Verification State

The temporary environments `pip install -e ".[dev]"` and
`uv sync --locked --no-editable --python 3.11 --extra dev` installed
successfully during the initial comparison. The final local preflight passed the
full suite with `2595 passed, 41 subtests passed` outside the managed sandbox.
Linux CI verification remains pending.

FastMCP inspection reported 13 tools, and `uv build` generated the `0.3.0`
wheel and sdist. The wheel was installed in a temporary Python 3.11
environment independent of the checkout; the STDIO entry point initialized with
version `0.3.0`, exactly 13 tools, and no `qlab_update_cues`. The final
post-merge snapshot remains pending.

A clean checkout generated with `git archive` passed the reproducible flow with
`2580 passed, 4 skipped, 41 subtests passed`; the skips correspond to missing
local `.codex/agents/` fixtures. This local result does not replace GitHub CI.

## Active Workorders

Workorders 017, 019, 021, and 022 are classified as local implementation with
runtime validation pending. Workorder 029 remains active runtime-validation
work. The only new runtime mutation in this iteration was bounded Delete
validation on two disposable empty Groups; it is documented in
[`empty-group-delete-2026-08-13.md`](../development/runtime-validation/empty-group-delete-2026-08-13.md).

The bounded architectural audit is documented in
[`architecture-audit-0.3.0.md`](architecture-audit-0.3.0.md) and concludes
`no extraction for 0.3.0`.

The agent-facing and Edit cleanup research is documented in
[`2026-08-13-mcp-agent-ux-and-edit-cleanup.md`](../development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md).

## Evidence Boundary

```text
local implementation
≠
runtime validated
≠
show ready for GO
```

No setters, Create, Edit, Move, playback, GO, `/live`, or raw OSC were run.
The bounded Delete of two empty Groups used only the MCP
dry-run/token/one-execution/readback flow and left the temporary prefix with no
results; it does not turn other workorders into runtime evidence.
Historical references and prior runtime evidence remain under
`docs/archive/` and are not reused as new evidence for this release.

## Reproducible Verification

```bash
cd <repo-root>
uv sync --locked --no-editable --python 3.11 --extra dev
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider
uv lock --check
uv run fastmcp inspect fastmcp.json
uv build --out-dir /tmp/qlab-mcp-build
git diff --check
git status --short --branch
```

The final snapshot will replace this provisional state after the main PR, the
merge into `main`, the final docs-only PR, and verification of the commit that
will receive `v0.3.0`.
