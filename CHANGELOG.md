# Changelog

## Unreleased

- Defines the local threat model, security invariants, reportable findings, and
  accepted risks in `SECURITY.md`.
- Documents the PR-1 through PR-4 input limits, canonical script profile
  contract, UDP source-port limitation, and QLab 5.5.10 evidence boundary.
- Records delayed UDP reply correlation as a separate follow-up from source-port
  authenticity.

## 0.3.0

- Establishes the 13-tool public FastMCP contract for QLab inspection and gated
  Create, Edit, Move, and Delete workflows.
- Removes the breaking `qlab_update_cues` compatibility alias; use
  `qlab_edit_cues` for cue edits.
- Removes the duplicate `batch_update_cues` readiness capability key; use
  `edit_existing_cue` as the canonical Edit capability.
- Marks Edit and Move as conservatively destructive MCP metadata hints; runtime
  safety gates, confirmation tokens, execution, and QLab behavior are unchanged.
- Adds a direct Delete route for one exact inactive empty Group while preserving
  the existing leaf and root-preserving recursive routes. Lists and Carts remain
  recursive-only.
- Carries forward sequential Create, recursive Delete, hardened write/readback,
  and release CI/packaging checks. The new Group route has fixture-specific
  QLab 5.5.10 evidence; it is not a general show-readiness claim.

## 0.2.0

- Exposes 13 public MCP tools for QLab inspection and gated cue creation,
  editing, movement, and leaf deletion.
- Keeps read operations safe by default and writes disabled, dry-run-first, and
  protected by readiness checks, exact targeting, confirmation gates, and
  fresh readback.
- Makes `qlab_edit_cues` the preferred edit tool while retaining
  `qlab_update_cues` as a compatible alias.
- Adds intentional Move and Delete tools with dedicated, process-bound
  confirmation tokens.
- Separates OSC transport, cache, tokens, result construction, timeouts, and
  several write families while preserving the public contract.

Earlier development plans and phase records are available in
[`docs/archive/`](docs/archive/README.md).
