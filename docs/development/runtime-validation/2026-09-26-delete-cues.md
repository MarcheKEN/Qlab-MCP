# Delete cues runtime validation — 2026-09-26

## Environment and scope

- Checkout: `/Users/filarmonica/Documents/Qlab/qlab-mcp-osc`.
- Branch: `codex/cue-editing-tools`; base: `3378ca6c2e70894d9abc0394c7d719f008ef5f24`.
- QLab 5.5.10; workspace `mcp_prueba.qlab5`, UUID `95F0A03D-140E-4673-974A-E76748EBB023`.
- User authorized testing in this workspace. Real cue mutations used public
  FastMCP Create/Delete tools with exact UUIDs, readiness, reviewed dry-runs,
  dedicated tokens, one execution and independent structural readback.
- Initial corrected runtime tested through a newly instantiated in-process
  FastMCP client; the post-restart MCP run is recorded below.

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

## Installed MCP after restart

After the user restarted the MCP, `qlab_check_connection` and
`qlab_check_write_readiness` confirmed QLab 5.5.10, the same workspace, Edit
Mode and edit permission. The exact `delete` Cue List began with 17 direct
children. Through the restarted MCP:

- Delete returned `reply_status="ok"`, confirmed fresh absence and completed
  in 52 ms. A second single delete confirmed in 50 ms.
- Invalid inputs again rejected empty or malformed IDs, missing UUIDs,
  duplicates, Group-as-leaf, direct Cue List/Cart requests, invalid selector
  combinations, and recursive-without-container. No target was deleted.
- Missing and malformed confirmation tokens were rejected. A token for the
  temporary Memo was rejected for the temporary Wait, which remained present.
  Adding a sibling after planning invalidated the old token before deletion.
- A mixed batch of ten Memo/Wait leaves deleted in order. Every readback
  confirmed absence in 28–89 ms. A partially invalid batch was rejected while
  all ten temporary cues remained readable. A new mixed batch of Memo/Wait
  cues then deleted successfully.
- Recursive deletion removed two nested leaves while preserving their Group.
  Recursive deletion of the now-empty Group was a verified no-op; replaying
  that token was rejected; direct deletion then removed the empty temporary
  Group.
- The list's final child UUIDs and order exactly matched its initial 17 cues.
  All 20 cues created during this post-restart run were absent afterwards.

### Nonempty Cue List recursion and Create control

To test recursive deletion on a nonempty Cue List without losing its original
Memo, it was temporarily moved to an empty Group in `delete`, then moved back
after the test. An anchored Memo Create in the nonempty list succeeded at index
1. Recursive Delete planned and removed exactly that temporary Memo, confirmed
its absence and preservation of the Cue List, then the original Memo was
restored. Final reads showed the original Memo in its list, the Group empty, no
playhead in that Cue List, and the `delete` list back at its original 17 UUIDs
and order.

A separate Create dry-run against an empty Cue List planned
`set_current_cue_list` followed by `/new`, but execution returned
`verification_failed`; `errors.current_cue_list` was exactly
`QLab successful reply JSON missing data`. It returned `created_count=0` and
`executed_operations=[]`. No `/new` was sent and the empty list remained
unchanged. This is an observed Create issue, outside the
Delete fix. One Move call was blocked before QLab because its confirmation
token did not match the reviewed dry-run; a fresh plan's exact token was then
used successfully.

An initial cross-target token check supplied a temporary Memo's token while
naming a pre-existing Disarm cue. Automatic approval review rejected the call
before execution. The same check was rerun against a temporary Wait created for
the test; it was rejected by QLab preflight and the Wait remained present.

## Automated checks and limits

`.venv/bin/python -m pytest -q`: **3057 passed, 47 subtests passed**.
`git diff --check`: passed.
The first sandboxed full-suite attempt was interrupted after local socket
fixtures were denied. The full suite passed with local socket access.
Existing Delete tests also cover timeouts confirmed by absence, delayed
convergence, active cues, partial failure, stale parent order and nonconvergence.

No GO, playback, load, panic or save was sent. Transport faults and active-cue
rejection were tested with automated fixtures rather than deliberately breaking
the live connection or starting cues. Recursive deletion of a Cue List with one
temporary child was performed after moving its original child aside, then
restoring it. Cart emptying was not performed because the available Cart
contained original content. Script cues cannot be created by the public Create
tool and were not live fixtures.
The 500-descendant limit and every possible QLab/environment failure are not
claimed live-validated. Child reads now trade caching for current structural state.
