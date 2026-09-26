# Delete cues runtime validation — 2026-09-26

## Environment and scope

- Checkout: `/Users/filarmonica/Documents/Qlab/qlab-mcp-osc`.
- Branch: `codex/cue-editing-tools`; base: `3378ca6c2e70894d9abc0394c7d719f008ef5f24`.
- QLab 5.5.10; workspace `mcp_prueba.qlab5`, UUID `95F0A03D-140E-4673-974A-E76748EBB023`.
- User authorized testing in this workspace. Real cue mutations used public
  FastMCP Create/Delete tools with exact UUIDs, readiness, reviewed dry-runs,
  dedicated tokens, one execution and independent structural readback.
- Corrected runtime tested through a newly instantiated in-process FastMCP
  client. The already running installed MCP has not been restarted.

## Reproduced failures and fixes

1. Installed Delete returned `preflight_failed`, zero deleted cues and
   `errors.always_reply = "QLab successful reply JSON missing data"`.
   No `/delete_id` was sent. The client rejected QLab's documented status-only
   acknowledgement. The correction permits absent `data` for `/alwaysReply`
   writes and `/delete_id/{id}` replies on UDP/TCP. Normal read replies retain
   their `data` requirement, address matching and workspace identity checks.
2. With only acknowledgement handling fixed, each real deletion needed roughly
   10.1 seconds for confirmation. Child snapshots were cached for the configured
   TTL, despite structural writes requiring fresh preflight and readback.
   `get_cue_children` now bypasses the cache on both read paths.
   Final real readbacks took **27–39 ms** and reported `deleted_immediately`.

Both regressions were reproduced by failing automated tests before fixes.
Source: [QLab 5 OSC Dictionary, alwaysReply](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/#alwaysreply-number).

## Live matrix

| Case | Observed result |
| --- | --- |
| Empty request, malformed UUID, missing UUID, duplicates | Rejected without deletion |
| More than ten explicit IDs, mixed selectors, recursive without container | Rejected without deletion |
| Group passed as a leaf; direct Cue List/Cart deletion | Rejected |
| Missing or invalid confirmation token | Rejected without deletion |
| Memo and Wait individual deletion | Disappearance confirmed |
| Mixed leaf batches of 10, 10 and 3 | All 23 deleted in order |
| All 24 supported Create types | Created and subsequently deleted; Group through container/recursive mode |
| Empty Group becomes nonempty after planning | Old direct-delete request rejected |
| Token for another target | Rejected without deletion |
| Nested Group recursive deletion, 29 descendants | Deepest-first deletion; requested root preserved |
| Recursive delete of empty Group | Verified no-op; root preserved |
| Replay of consumed no-op token | Rejected |
| Direct deletion of the emptied Group | Group disappearance confirmed |
| Cue List/Cart recursive dry-runs | One descendant planned in each; no mutation |
| Final full workspace child-tree comparison | Original structure preserved; all fixtures absent |

The final matrix created and deleted **55 temporary cues**. An earlier run
created and deleted 31 temporary cues while isolating the cache issue. Its cart
fixture setup stopped at a guard: the cart named "Cue cart vacia" was nonempty.
The corrected final run completed its final structural comparison successfully.

## Automated checks and limits

`.venv/bin/python -m pytest -q`: **3057 passed, 47 subtests passed**.
`git diff --check`: passed.
The first sandboxed full-suite attempt was interrupted after local socket
fixtures were denied. The full suite passed with local socket access.
Existing Delete tests also cover timeouts confirmed by absence, delayed
convergence, active cues, partial failure, stale parent order and nonconvergence.

No GO, playback, load, panic or save was sent. Transport faults and active-cue
rejection were tested with automated fixtures rather than deliberately breaking
the live connection or starting cues. Actual Cue List/Cart emptying was not
performed: all available roots had existing contents, which were preserved.
Script cues cannot be created by the public Create tool and were not live fixtures.
The 500-descendant limit and every possible QLab/environment failure are not
claimed live-validated. Child reads now trade caching for current structural state.
