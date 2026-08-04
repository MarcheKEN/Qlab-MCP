# Workorder 031 — Safe Create lifecycle runtime validation

Status: completed 2026-08-04; implementation and bounded QLab runtime evidence
are closed with explicit limits.

## Scope

Workorder 031 hardened the lifecycle for creating one cue:

```text
dry-run → fresh token → /new → UUID discovery → fresh readback → placement verification
```

Create reuses Edit Cues' property normalization, validation, setter planning,
timeout handling, and fresh readback. Create-only behavior covers the dedicated
`confirm:createCue:v1` token, exact anchor, structural fingerprints, UUID
identity validation, partial states, and manual cleanup guidance. No production
backend abstraction or public AppleScript backend was added.

## Public contract

- `qlab_create_cue` accepts one blank allowlisted `memo`, `group`, `wait`, or
  `audio` cue.
- `after_cue_id` is required and must be an exact cue UUID in a linear Cue List
  or Group. It is the only real placement mode in this workorder.
- Dry-run returns a dedicated `confirm:createCue:v1` token bound to the fresh
  workspace/anchor structure, activity, cue type, and properties. Real Create
  requires that exact token and consumes it before `/new`.
- Real Create uses one workspace-qualified `/new`, validates the returned UUID,
  reads the cue fresh, and verifies parent/order/health/inactivity.
- `cleanup_required=false` is returned only after complete verification.
  Ambiguous identity or partial failure returns `cleanup_required=true` and
  manual-review guidance. No automatic cleanup or mutating retry is performed.

The OSC source documents `/workspace/{id}/new {cue_type} {cue_ID}` and states
that the optional cue ID inserts after that cue. See
[`qlab_osc_dictionary.md`](../../../references/qlab_osc_dictionary.md#L1021-L1036)
and the [official QLab OSC Dictionary](https://reference.qlab.app/docs/v5/scripting/osc-dictionary-v5/).
QLab's selection of the new cue is treated as transient state; verification uses
the returned UUID and fresh structure instead.

## Runtime evidence

### 031A — blank Wait smoke

QLab 5.5.10 was used with a disposable workspace and no playback activity. One
blank Wait (`EDACEA06-4D48-48DD-9C60-500A1D271F35`) was created and manually
deleted. Its UUID, type, parent, health, and inactivity were confirmed.
Placement was `null` in this pre-anchor smoke and is not evidence of
deterministic placement.

### 031B — anchored blank Wait

Validated in QLab 5.5.10, workspace `7317A766-7905-45EA-BC2A-B54AD6841507`
(`Untitled Workspace`), in Edit Mode:

- Anchor: Wait `39A81382-4CC6-4090-BC29-347EA0298EBF`.
- Parent Cue List: `DE865C82-9D70-4745-8151-17351F381BB3`.
- Created cue: Wait `7B0B3505-5A53-4A50-BA41-CDA4C19176BA`.
- Exactly one real `/new` was sent with the exact anchor UUID.
- The result had structured content, `status=created`, no warnings/errors, and
  `cleanup_required=false`.
- Fresh readback confirmed the returned UUID/`uniqueID`, type `Wait`, parent,
  healthy state, inactivity, and index `1` immediately after the anchor.
- The created cue was deleted manually through a fresh Delete dry-run and
  `confirm:deleteCues:v1` token. Delete returned
  `deleted_after_convergence`, `deleted_count=1`, `failed_count=0`.
- The anchor remained intact and the workspace returned to its original
  structure. Final activity was `0/0/0`; DMX Output remained unchanged.

No GO, playback, Audition, Stop, Panic, `/live`, raw OSC, workspace save,
automatic cleanup, anchor deletion, or retry was used.

## Evidence boundaries and follow-ups

Runtime proof covers only blank anchored Wait creation. It does not certify new
cue types, new property families, or setter behavior for Create. Group-empty
insertion, Cue Cart placement, `parent_id + position`, arbitrary index
placement, and any fallback placement route remain out of scope.

An `/new` timeout or invalid identity remains indeterminate: it may have created
a cue, so no setter or retry is safe. The token is already consumed; recovery is
manual inspection followed by a fresh dry-run/token. Token expiry, replay, and
process binding are source/test contracts, not live MCP-restart proof.

There is no automatic cleanup, idempotency key, or fallback backend. AppleScript
remains an internal comparison path only. “Blank” means no initial properties
were supplied; workspace Cue Templates and QLab Wait normalization may affect
fresh readback (including duration/post-wait behavior).

Follow-up workorders should cover Create type/property expansion, ambiguous
`/new` and partial-failure probes, and a separate List/Group/Cart placement
matrix. Do not fold those capabilities into Workorder 031.

## Closure verification

- Focused Create tests: `18 passed`.
- Focused FastMCP/schema tests: `33 passed`.
- Full `.venv/bin/pytest -q`: `2479 passed, 41 subtests passed in 6.35s`.
- `PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp.json --skip-env` reports
  13 tools; Create requires `workspace_id`, `cue_type`, and `after_cue_id`,
  accepts `confirm_token`, and exposes the documented `CreateCueResult` fields.
- `git diff --check`, final diff review, and clean Git status pass.
