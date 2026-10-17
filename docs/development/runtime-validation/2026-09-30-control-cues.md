# qlab_edit_control_cues validation — 2026-09-30

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Environment and authorization

QLab **5.5.10**; workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`, path checked with Computer Use:
`<redacted-local-path-851cab375f>.qlab5`.
The user authorized changes to this test workspace while other workspaces stayed
open. Every write message included the exact UUID; the other workspaces were
untouched. The preflight protocol checked Edit Mode and absence of activity.
Computer Use only inspected and selected tabs/cues; it did not edit properties
or execute actions.

## Verified operations

[JSON record without confirmation tokens](2026-09-30-control-cues.json).
It records previous values, single setters, fresh readback and per-operation states.

- Batch of **ten prepared types**: Start 37.5, Stop 37.6, Pause 37.7,
  Load 37.8, Reset 37.9, GoTo 38.5, Arm 38.7, Disarm 38.8, Wait 38.9 and Memo 38.95.
  **36 setters** confirmed by fresh reads: names, eight targets pointing to Video
  29, Wait duration 2.5, Memo notes and Start Basics/Triggers.
- Start: pre/post wait, continue mode, flag, auto-load, skip-if-disarmed, colors
  and second color, Duck/Boost enable/level/time, Second Trigger action and
  on-release, Fade & Stop time and Timecode text. UI: Duck −6 over 0.5 s, Second
  Trigger `stops`, on-release checked, Fade time 0.5 s. Timecode stayed disabled;
  writing its time was not treated as enabling it.
- Batch restoration: **36 setters**, fresh reads, ten `updated` results.
  Empty targets, Wait 1 s and all other original values restored.
- Reset patch: temporary fixture with a new UUID to preserve the original cue's
  empty patch state. One test rejected the empty baseline; another showed that
  assigning the patch before its mode was ignored. Both fixtures were cleaned
  up; the uncertain setter was not resent.
- With the corrected order, the new fixture confirmed `targetMode=1`, Audio
  Output Patch name and UUID. The UI showed `Patch 1 - System Output`.
- Fixture experiment: scalar Fade & Stop setters 0, 1, 2, 3 returned exact integer
  readbacks. The UI showed scope `all` for 3.
- Integrated tool on that fixture: **10 setters** for Cue mode, Video 29 target,
  Fade & Stop 0, Timecode components (2h3m4s5frames6bits), armed false and a new
  number. All had fresh readback. Get Control returned `ok=true`, no errors,
  scope 0 and editing capabilities. UI confirmed Cue mode, target 29, new number,
  disarmed state and disabled Fade & Stop.
- Only fixtures created for this test were deleted. The UI returned to **252
  cues**, fade to **33 children**, and the original Memo 38.95/Basics selection
  was restored. No cues, capture or external signals were executed.

## Automated verification

- Full suite: **3306 tests and 61 subtests pass**.
- `Client(mcp).list_tools()` contract: **57 tools**, including the new tool;
  the previous 56 remain. Schemas, annotations, catalogue and README checked.
- Regressions: mixed/50-item batches, types/UUIDs/properties, targets/patches/modes,
  scalar scope versus grouped boolean, Timecode/drop-frame, expired/reused/changed
  confirmations, full preflight without setters, failed preparation, confirmed
  timeout without resending, and failure with pending operations.
- UDP/TCP transport and same-connection confirmation tests pass. Socket tests
  required execution outside the sandbox that denies `bind`; the first restricted
  run is not an acceptance result.
- `git diff --check` passes. No new dependencies, version or release.

## Limits

Live validation used TCP; UDP was checked with simulated servers. Batches are
sequential, non-atomic and do not roll back. Patch clearing, Target, Devamp, Load
Time and AppleScript trigger configuration are excluded. Fade & Stop stays blocked
when the scalar query cannot identify its mode. This record describes local
source; restarting MCP loads the new tool.
