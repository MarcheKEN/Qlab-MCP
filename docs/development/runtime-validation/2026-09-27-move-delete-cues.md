# Move and Delete validation — 2026-09-27

Branch: `codex/cue-editing-tools`. Completed bounded live matrix on QLab 5.5.10.

## Confirmed Move health regression

Workspace `95F0A03D-140E-4673-974A-E76748EBB023` (`mcp_prueba.qlab5`),
QLab 5.5.10. Audio `A506D566-8390-487A-A453-DDC5BBD63116`.

The installed MCP's health read returned `isBroken=true`. Its Move dry-run
nevertheless returned `planned`, with both source and destination health marked
false. No real move was executed. The structural `/children/shallow` records
omit these health fields, which were previously treated as false.

The source now reads `isBroken` and `isWarning` with uncached `valuesForKeys`
for each distinct source and destination after structural validation, during
both planning and execution preflight. Missing or invalid health fails closed.
An intermediate fix returned `preflight_failed` for this Audio and its broken
parent list, without mutation. Further testing showed that this gate prevents
normal structural editing of incomplete shows. The final policy reads and
reports health accurately but treats broken/warning state as information, like
Create. A broken Audio was successfully moved into another broken List and
restored to its original parent/index, with exact structural readback.
The already-running installed MCP still needs a restart to load source changes;
the final public surface was verified separately through a fresh FastMCP Client.

## Fifty-cue batches

Move and explicit leaf Delete now accept up to 50 UUIDs, including the public
FastMCP schemas. Regression tests execute 50 sequential moves, verify their
final order, and execute 50 deletes with independent disappearance checks.
Real 50-cue batches subsequently passed in all three authorized workspaces.

The full suite after the health fix, batch expansion, no-op fix, and contract
updates passed: **3067 tests and 47 subtests**.

## Real-workspace matrix

The same source implementations used by the public tools were invoked through
`QLabReader`, connected to QLab over OSC. Each write had a fresh readiness
check, dry-run validation, exact confirmation token, and structural readback.
This matrix did not restart the installed MCP process.

| Workspace UUID | 50 into nested Group | 50 reorder | 50 out of nested Group across lists | 50 explicit deletes |
| --- | ---: | ---: | ---: | ---: |
| `95F0A03D-140E-4673-974A-E76748EBB023` | 1.637 s | 1.588 s | 1.820 s | 1.917 s |
| `2BE85FBF-91A8-49AE-9617-C58B3332BF92` | 1.318 s | 1.279 s | 1.351 s | 1.494 s |
| `A192C068-0974-4624-90BD-56D68BF0286B` | 4.297 s | 4.566 s | 4.452 s | 5.378 s |

All three also passed single and 49-cue cross-list moves into Groups; rejection
of duplicate sources, cycles, parent/descendant batches, foreign-workspace
destinations, and stale Move tokens; recursive nested Group emptying with root
preservation; and subsequent direct deletion of the empty Groups.

The first and third workspaces additionally passed Group-to-List, List-to-List,
List-to-Group, and moving a populated Group into/out of another Group. All
root Cue Lists in the second workspace reported `isBroken=true`, so the
initial policy blocked them as destinations; cross-list moves into healthy
Groups in that workspace did pass. After correcting that policy, additional
50-cue Group-to-List, List-to-List, and List-to-Group batches passed against
these broken lists. Before/after anchors, explicit index, and two different
destinations in one batch passed as well.

The matrix created and removed **162 temporary cues**. Fresh structure reads
confirmed that all fixture UUIDs disappeared and original parent/order
relationships were restored. The second and third workspaces used persisted
pre-test baselines. After the interrupted first-workspace run, its baseline
was reconstructed by removing only the known fixture UUIDs from fresh state;
no original cue had been moved or deleted during that run.

Raw diagnostic evidence and the temporary harness are stored at
`/private/tmp/qlab-move-delete-live.jsonl` and
`/private/tmp/qlab-move-delete-live.py`; they are not durable repository artifacts.

## Confirmed no-op Move regression

The first 50-cue reorder initially failed on its first cue: QLab returned an
error when asked to move that cue to index 0, where it already was. No move
was confirmed and fresh state still showed the original order. The source
now compares the simulated structures before/after each step, skips the OSC
setter for unchanged placement, and still requires independent fresh position
readback. Such an item reports `reply_status=skipped_no_op`; `moved_count`
counts satisfied placements, including these verified unchanged placements.
The corrected full 50-cue reorder passed in all three workspaces.

## Documentation sources

The repository's QLab 5.5.10 OSC dictionary documents `/move/{cue_id}` with
an index and optional destination Group, Cart, or List UUID, and
`/delete_id/{cue_id}` for deletion. It does not establish root Cue List
reordering semantics. The [official Cue Lists manual](https://qlab.app/docs/v5/fundamentals/cue-lists/)
confirms that deleting a list also deletes its contents. That differs from
the existing recursive Delete mode, which preserves the root container.

QClass Day 1 at 1:30:50–1:31:14 describes moving cut cues into a separate list
to preserve them for later restoration. At 1:36:42–1:37:03 it explains that
Show Mode disallows cue moves/additions/deletions. These support the workflow
and Edit Mode gate; they do not establish OSC root-list reordering behavior.

## UUID anchor regression

Direct source calls with uppercase `before_cue_id` or `after_cue_id` initially
failed simulation even when the anchor was a valid sibling. Validation parsed
the UUID but the normalized move retained the original string. Both anchors
are now canonicalized consistently with tree keys. Red/green regressions and
the real before/after cases passed after the fix.

## Public MCP verification

A fresh in-process `Client(mcp)` exposed **48 tools**, with Move and Delete
schemas accepting 50 items. Public Create, Move, and Delete calls created 50
Memo cues, moved all 50 between broken Cue Lists, and deleted all 50. Both
write schemas rejected 51 items before execution. Fresh readback independently
confirmed disappearance and restoration of the original structure.

In total these matrices created/deleted **263 temporary cues**, plus the one
temporary root Cue List described below. All fixture UUIDs were cleared. No
GO, playback, save, or original-cue deletion was performed. Structural success
does not establish playback readiness. Temporary evidence for the additional
and public matrices is in `/private/tmp/qlab-move-additional-live.jsonl` and
`/private/tmp/qlab-public-mcp-live.jsonl`.

## Root Cue List experiment and recommendation

Native OSC created temporary empty root List
`117123FB-BC50-469A-9083-89ADB41DB8B6`. `/move/{uuid} 0` succeeded, returning
`{"index":0,"parent_cue_id":"__root__"}`. Fresh inventory confirmed index 0
and preserved the relative order of all original roots.

`/delete_id/{uuid}` opened QLab's **Delete Cue List** confirmation dialog.
The request timed out, and subsequent OSC reads timed out while the dialog
was open. The mutation was not resent. The authorized temporary-list deletion
was completed by confirming the existing dialog in the GUI. Fresh OSC then
confirmed the root UUID absent and exact original root order restored.

Recommendation: keep root List operations separate from normal cue moves and
root-preserving recursive emptying. A future root reorder tool should bind the
ordered root inventory and verify `__root__` placement. A future root delete
tool must include all descendant impact in its reviewed plan and explicitly
handle QLab's GUI confirmation requirement; this experiment does not establish
unattended OSC root deletion. No new public root-write tools were added.

Current Group deletion is verified in two stages: recursively empty the Group
while preserving it, then delete the empty Group with `container_id` and
`recursive=false`. It is not advertised as one-call deletion of a populated
root Group. Cue Cart writes remain outside the proven Move boundary.
