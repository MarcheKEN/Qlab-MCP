# Workorder 030 — Group Edge Runtime Validation

Status: completed 2026-08-03; bounded runtime evidence archived.

The implemented Group contract remains documented in
[`028_group_cue_safe_editing.md`](028_group_cue_safe_editing.md). This workorder
records the additional QLab 5.5.10 edge validation only; it did not change
production behavior, safety gates, tools, or the public API.

## Runtime evidence

Validated on branch `validation/group-edge-runtime`, commit
`73f3e716a124f80bc7e732e141c22d075a585145`, using QLab 5.5.10 workspace
`MATADERO - FILAR.qlab5`
(`A192C068-0974-4624-90BD-56D68BF0286B`) and disposable Cue List
`__MCP GROUP TEST FIXTURES`
(`D118BA19-726D-447A-9EE1-B08D2F852FBE`). All probes used Edit Mode, exact
UUIDs, healthy inactive cues, DMX output recorded but unchanged, and global
`running/paused/auditioning = 0/0/0`.

Fixtures:

- Group `763619DA-DFD2-4D5B-A429-71D99C1E31E3`: Wait children `2 s` and `5 s`.
- Group `F33C55AC-2CE7-4D68-8FB7-34D238302E8A`: Wait children `0 s` and `3 s`.
- Group `2EB66F76-C861-4AC9-A987-528AA3BB45CB`: `378` direct Wait children.

The following were runtime validated:

- Two reproducible Group `mode 3 → 6 → 3` cycles.
- Exactly one setter per mutation, with canonical workspace-qualified UUID
  addresses.
- Setter timeout followed by reliable fresh Group and ordered-child readback;
  structured MCP results returned `updated_with_confirmed_timeouts`.
- QLab child `continueMode` side effects surfaced in `side_effects` and
  `group_child_readback`.
- Exact rollback using a new dry-run and confirmation token; Group, child
  state, order, duration, and activity restored.
- Finite Playlist Loop (`2 s + 5 s`) and mixed zero/finite Playlist Loop
  (`0 s + 3 s`), each with one setter per direction and exact restoration.
- Two complete ordered snapshots of all `378` direct children: no duplicates,
  all `Wait`, identical order.
- Consumed-token replay protection: replay returned
  `confirmation_already_consumed` with zero setters.
- Cross-process token signature invalidation: an independently imported
  process rejected the old token with `groupMode confirm_token signature is
  invalid.`; focused tests cover the same contract.

Crossfade probes used the finite Group's shortest child (`2 s`):

- Requests for `1 s` and `2 s` each sent one setter, then read back `3 s` and
  returned `partial_failed`; no mutating retry occurred and no side effect was
  observed.
- Enabling crossfade with effective duration `3 s` was rejected during
  dry-run because it exceeded the shortest child; zero setters were sent.

## Known follow-up limitations (not blockers)

- QLab 5.5.10 retained a `3 s` crossfade when `1 s` or `2 s` was requested.
  This is fixture/version-specific requested-vs-readback evidence, not a
  documented or global `3 s` minimum. Short/equal active crossfade behavior
  therefore remains unconfirmed.
- Live MCP restart token invalidation was not tested because no safe restart API
  was available. Cross-process signature invalidation is covered by tests and
  isolated process proof; no QLab restart, MCP kill, or unsafe host action was
  used.
- All-zero-child Loop behavior, warning-only Groups, active/auditioning Groups,
  playback, live token expiry, and undocumented crossfade curve setters remain
  outside this bounded closure and require separate authorization/evidence.

## Verification

- Focused Group tests: `101 passed`.
- Focused FastMCP contract tests: `6 passed`.
- Full suite: `2467 passed, 41 subtests passed in 11.27s`.
- Git working tree was clean before closure staging and is rechecked after the
  closure commit.

## Safety contract

No GO, playback, Audition, Stop, Panic, raw OSC, workspace save, cue creation,
deletion, movement, automatic retry, or unrelated mutation was used. Future
runtime work must retain exact UUID targeting, dry-run-first tokens, one setter,
fresh readback, and deterministic rollback.
