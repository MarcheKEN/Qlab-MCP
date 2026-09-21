# Current Project State

Provisional preparation snapshot: **2026-08-13 Europe/Madrid**.

This document describes the QLab MCP 0.3.0 preparation branch. The definitive
canonical snapshot will be updated through a docs-only PR after the merge into
`main`, before the `v0.3.0` tag.

> Branch update (2026-09-16): PR #16 supersedes the preparation counts below
> with 14 public tools, including the bounded
> `qlab_edit_workspace_settings` write for `general.minGoTime`. That scope is
> complete for the PR; other Workspace Settings operations are deferred and do
> not block review or merge. The dated 13-tool text below is retained as the
> historical preparation snapshot.

Development update (2026-09-20): the current checkout exposes 22 tools
(16 read-only, 6 gated writes) after adding the Cue List inventory and exact
detail readers. Generic Cue Details returns a structured redirect for Cue Lists
and retains Cue Cart support. Cue List details reuse bounded traversal and
expose explicit OSC coverage, including unknown timecode sync activation/source
settings.

Cue List read-only STDIO validation (2026-09-20, QLab 5.5.10): inventory returned
17 lists and 1 excluded Cart in `mcp_prueba.qlab5`, 5 lists in
`Memoria de la nisal - Filarmónica.qlab5`, and 8 lists in `MATADERO - FILAR.qlab5`.
Safe and technical detail passed for `Main Cue List`
(`CC4DF6DC-175E-4346-92A1-43CCB6062390`, 25 direct / 27 returned descendants),
`Master` (`063BD7D0-7105-4FB9-8AE5-53615FBAD173`, 151 / 215), and `Full show`
(`D80B01AB-18D8-466D-9FB7-269FA5337FD1`, 22 / 128). Depth-2 truncation was
explicit for Main and Full show. Current timecode was unavailable in these
samples; MTC configuration was readable. Generic details retained the payload
and returned the deprecation notice in each workspace. These observations used
fresh temporary STDIO processes, the configured MCP credentials where needed,
and disabled write mode; no cue execution, setters or save occurred.
The desktop MCP process still needs a restart to load the added tools.

Historical development update (2026-09-18): the checkout exposed 20 tools
(14 read-only and 6 gated writes), including six Workspace Settings domains
and separate UUID-only Video Stage and Output Route readers. The preparation
snapshot below remains historical; see the current [tool catalog](../user/tools.md).

Video split verification: `PYTHONPATH=src .venv/bin/python -m pytest -q
-p no:cacheprovider` passed with **2681 tests and 41 subtests**. FastMCP
inspection reported 20 tools. Read-only STDIO calls against QLab 5.5.10,
workspace `mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`), returned
3 input patches, 5 routes, and 9 stages. Exact Stage
`4ADC86C9-4975-40A2-A1E7-34E07D55C452` and Route
`A8DCBB7D-309D-479F-B60E-19F1D9B2EFEA` passed both safe and technical reads.
A nonexistent Stage UUID returned `video_stage_not_found` after a same-domain
inventory check. No QLab setters, playback, or save commands were used.
This validates the local checkout; a running MCP process must reload source
changes before it serves the latest error-handling behavior.

Contract-hardening verification (2026-09-19): the full synthetic suite passed
with **2745 tests and 41 subtests**. Audio Maps are no longer public; exact
Output Patch reads cover routing, cue outputs, mute/solo, and one optional
matrix crosspoint. Bounds are schema-enforced, and malformed OSC/settings
payloads are rejected rather than summarized as empty success.

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
