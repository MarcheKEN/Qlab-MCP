# `qlab_create_cues` Runtime Checklist

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Current contract

One call accepts 1–100 ordered mixed cue types from workspace Cue Templates.
Specify one exact Cue List, Group, or empty Cart UUID. Lists and Groups append
by default; `after_cue_id` inserts after a direct child. A Cart accepts only
one non-Group cue. No initial setters or cue numbers are sent. Structural
creation does not prove readiness for GO.

Review a dry run and its exact `confirm:createCues:v2` token (five minutes,
one use). Each `/new` must return a valid UUID, verified before proceeding.
The first cue in an empty Cue List changes the active list; QLab selects new
cues. Selecting the empty List can require control permission. Status-only
write acknowledgements are accepted only on documented routes and verified
by fresh reads; reads and `/new` require data.

Public timeout is 300 seconds; execution budget is 270 seconds. An accepted
100-cue request can stop early. Results preserve confirmed cues and their UUIDs:
`pending_indices` identify unattempted requested positions; `uncertain_indices`
identify attempted creations not verified, potentially without a UUID.
`created_count` counts confirmed items, not all possibly-created items.
`batch_verified` certifies the final simulated structure and inactive state.
Final read failures retain all confirmed counts. No mutation is retried and
there is no automatic rollback or cleanup.

## Installed validation — 2026-09-27

The restarted MCP exposed 49 tools, Create maxItems=100 and all three new result
fields. On QLab 5.5.10, the UDP workspace `redacted-workspace-6b31c91e.qlab5` was ready in Edit
Mode with no active cues. A 100-item mixed batch (all 24 types, then 76 Memo/
Wait items) was planned and sent once to the previously empty Group
`7EFFB592-6447-5BD5-9E78-D8B2C1CCE30D`.

QLab created all 100 cues. Per-item results and independent MCP readback
confirmed every UUID, type, parent and position; Computer Use showed cue 125
with 100 children, the requested type order and no active cues. The tool still
returned `partial_failed`, `batch_verified=false`, with
`Final Create structure differs from the complete simulated batch.` The cause
was UUID casing: QLab's returned UUIDs were uppercase, while structural reads
normalize them to lowercase. The final simulator compared them literally.
The fix canonicalizes those UUIDs. After the next user-confirmed restart,
the same mixed 100-item batch completed in 15.274 seconds with `ok=true`,
`status=created`, `created_count=100`, `batch_verified=true`, and empty
pending/uncertain indices. Independent readback matched every UUID and type
in order; Computer Use showed all 100 children and the 341-cue total.
Reviewed cleanup deleted exactly those 100 fixtures in 10.708 seconds.
Fresh full cue-index rows, root order, list contents, current Cue List and
output overrides matched the baseline; Computer Use returned to 241 cues,
zero children in Group 125 and zero active cues. See the
[restart recheck capture](2026-09-27-create-installed-100-recheck.json).

Delete's reviewed recursive dry-run listed exactly those 100 fixture UUIDs and
preserved the original Group. The single cleanup deleted all 100. Fresh MCP
readback and Computer Use confirmed the Group empty, its seven original
siblings/order intact, 18 roots, 241 cues, the original active Cue List and no
active cues. Sanitized per-item Create results and compact Delete records are
in [the runtime capture](2026-09-27-create-installed-100.json).

Two QLab app instances showed the same workspace path. The instance at
`<redacted-local-path-2e4542d9aa>.app` reflected the MCP changes (341 cues during
the test, 241 after cleanup); `/Applications/QLab.app` stayed at the old
241-cue view during the run. Computer Use validation used the live instance.
Both windows were returned to the original active Cue List; no GO, playback,
Save, or settings change occurred.

## Remaining live coverage

The mixed 100-item restart recheck and cleanup passed. The live 50-item case,
rejected 0/101 requests, expired or
replayed tokens, empty-List selection, Cart creation, TCP acknowledgements and
budget exhaustion were not tested against the installed MCP. Local tests cover
the simulated validation and error cases; they do not replace these live cases.

Use `scripts/capture_move_delete.py` with `tool=qlab_create_cues` to capture
one reviewed call, elapsed time and errors. Tokens/sensitive fields are
redacted; exclusive output creation prevents overwriting prior evidence.
Execution requires `--execute`, `dry_run=false` and its reviewed token. The
script never retries.

## Evidence boundary

Previous Workorder 031 runtime evidence covered one anchored Wait. Raw OSC
experiments covered Group insertion and Cart coordinates (request 0,0,
QLab 5.5.10 readback 1,1). An installed Create attempt on 2026-09-27 failed
with `QLab successful reply JSON missing data` while selecting an empty List;
this motivated acknowledgement handling. These are historical observations,
not installed validation of the new 100-item contract. Local fixture tests
cannot establish real QLab batch duration or operational readiness.
