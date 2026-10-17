# Create hardening — 2026-09-27

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Implemented, locally verified

`qlab_create_cues` accepts 1–100 ordered mixed types from workspace templates.
All 24 existing types and destination restrictions remain. It uses OSC, the
existing one-use `confirm:createCues:v2` token and five-minute expiry. No initial
properties, AppleScript backend, new dependency or new tool was introduced.

UDP and TCP accept status-only acknowledgements for workspace-qualified
currentCueListID writes and move writes. Existing alwaysReply/delete exceptions
remain. Read replies and `/new` still require data; creation requires a UUID.
List selection and Group movement are read back before continuing. Writes are
journaled before dispatch, including failures. A denied empty-list selection
stops before `/new`.

The public timeout is 300 seconds; the internal execution budget is 270.
Mutating requests now use the existing reader request path, which bounds reply
waiting to the remaining deadline. A budget check also precedes `/new` and each
next item. Results preserve confirmed UUIDs/counts after failures and expose:

- `pending_indices`: zero-based items not attempted. A failed attempted item
  stays in results and is not repeated as pending.
- `uncertain_indices`: items whose creation may have been sent but was not
  verified. A known UUID can still have uncertain placement/state.
- `batch_verified`: true only after final complete structure/root order and
  inactive-state verification. Final failure retains all confirmed results.

No retry or rollback is sent. Local callers of the internal single-cue executor
now receive structured preflight failures for readiness/placement errors rather
than escaping exceptions; the public MCP schema is extended compatibly.

## Checks

- Focused checks: 2379 tests and 18 subtests passed.
- Full suite: 3173 tests and 57 subtests passed in 38.81 seconds. Socket-based
  transport tests ran outside the sandbox to allow localhost sockets.
- FastMCP Client registry: 49 tools, Create maxItems=100, timeout=300, all three
  result fields present. Readiness capabilities also report max_items=100.
- Tests cover real executor flows against local fixtures: 1/50/100 mixed cues,
  empty/nonempty Lists and Groups, exact ordering, Cart restrictions, consumed/
  expired/mismatched tokens, drift/activity, denied selection, protocol errors,
  UUID errors, lost replies, escaping item errors, final read/order/activity
  failures, and simulated execution-budget exhaustion. UDP/TCP acknowledgement
  tests preserve strict read and `/new` parsing.
- `git diff --check` passed after the documentation update.

These durations measure automated fixture tests, not live QLab creation speed.
Read patterns were retained; optimization requires installed measurements.

## Installed and visual validation — 2026-09-27

The restarted registry exposed 49 tools and `qlab_create_cues` accepted the
100-item schema. One UDP batch containing all 24 types plus 76 alternating
Memo/Wait cues took 15.291 seconds and created all 100 items. Every item was
individually verified. The batch response incorrectly reported
`partial_failed`/`batch_verified=false` because the final simulator compared
uppercase result UUIDs against lowercase UUIDs from the structural snapshot.
Independent readback and Computer Use confirmed all IDs, types, parent and
order were correct. The regression is fixed locally by normalizing UUIDs before
the final comparison. After a second user-confirmed restart, the identical
100-item request passed in 15.274 seconds: `ok=true`, `status=created`,
`created_count=100`, `batch_verified=true`, no pending or uncertain indices.
Independent MCP readback and Computer Use confirmed the requested order.
Cleanup removed all 100 fixtures; complete cue-index rows, root order, list
contents, current Cue List and output overrides matched the baseline, with
zero active cues. Computer Use showed the original 241 cues and empty Group.
The [restart recheck capture](2026-09-27-create-installed-100-recheck.json)
preserves the successful response separately from the earlier failure.

The test used the empty Group `7EFFB592-6447-5BD5-9E78-D8B2C1CCE30D` in
`MCP_GROUP_WRITE_FIXTURE`. Reviewed recursive Delete removed exactly the 100
created UUIDs and preserved the Group. Final MCP and Computer Use checks
confirmed 18 roots, the original 241 child cues, unchanged root/list structure,
the original active Cue List and no active cues. Full sanitized per-item Create
results and compact cleanup records are in
[the installed capture](2026-09-27-create-installed-100.json); the remaining
live coverage is listed in [the checklist](create-cues.md).

Two app instances pointed at the same workspace path. Only
`<redacted-local-path-2e4542d9aa>.app` reflected the OSC writes; the
`/Applications/QLab.app` view remained stale until cleanup. Computer Use
validation used the former. No GO, playback or Save was used.
