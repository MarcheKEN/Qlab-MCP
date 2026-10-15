# Raw OSC root Cue List and Cue Cart validation — 2026-09-27

Workspace: `8E86FE91-668B-560C-B738-4D581B5A7498` (`redacted-workspace-6b31c91e.qlab5`).
QLab 5.5.10. Tests used the raw OSC MCP on `127.0.0.1:53000`, with replies
configured to port `53001`, and Computer Use on the QLab process serving that
workspace. No GO, playback, Save, Panic, or original-cue deletion was used.

## Move

Two disposable root fixtures were created by OSC:

- Cue List `A16AFFF8-DDDE-5E84-A0BE-F7A9B9704F04`
- Cue Cart `0AD516A9-B9C4-5A13-AB19-0D0D421F8833`

An OSC bundle contained:

```text
/workspace/<workspace>/move/<list-uuid> 0
/workspace/<workspace>/move/<cart-uuid> 1
```

QLab returned two independent `status=ok` replies. Both replies reported
`parent_cue_id=__root__`; a fresh `/cueLists/shallow` read and Computer Use
showed the List at root position 0 and the Cart at root position 1. The bundle
was processed with separate replies. This does not establish atomicity or
rollback behavior; callers must not assume either.

## Delete

Sending one raw `/delete_id/<uuid>` for either root fixture returned no OSC
reply. QLab opened a modal confirmation. While the modal was open, OSC reads
were not a reliable completion signal. Computer Use showed:

```text
Delete Cue List — Permanently delete Cue List 'RAW_OSC_LIST'?
Delete Cue List — Permanently delete Cart 'RAW_OSC_CART'?
```

Confirming the disposable fixture in the GUI removed it; fresh OSC inventory
then recovered. A bundle containing two root List deletes produced no OSC
replies, opened the first modal, then opened the second only after the first
was confirmed. This is sequential confirmation, not batch deletion.

## Cleanup and result

All temporary Lists and Carts were confirmed deleted. Final `/cueLists/shallow`
reported 18 roots (17 Cue Lists and 1 Cue Cart), with the exact original UUID
order and no `RAW_OSC_*` fixture. Computer Use reported `241 cues in 18 lists
and carts`.

## Consequence for future tools

Root Move is technically available through OSC and can be verified with a
fresh root inventory. Root Delete is not an unattended OSC operation in this
QLab setup: it requires a GUI confirmation and has no immediate OSC success
reply. A `Move QList` implementation can therefore use ordered root plans and
post-readback. A `Delete QList` implementation must either expose an explicit
interactive confirmation boundary or remain unsupported for direct root
deletion; an OSC bundle does not remove that boundary.

The repository OSC dictionary documents `/move/{cue_id}` and
`/delete_id/{cue_id}`. QLab's [Cue Lists manual](https://qlab.app/docs/v5/fundamentals/cue-lists/)
also confirms that deleting a Cue List removes its contents.

## Follow-up: completing deletion inside an MCP tool

Direct AppleScript was tested on disposable root List
`ED30381E-DE74-5E2E-A8CB-C46C6DE0DB1E` and Cart
`0291D725-AD8B-5E69-B471-DE0CC64A7FF6`. The workspace was resolved by
`unique id`; root cues were resolved by `uniqueID` (these are distinct property
names). Both deletes opened the same modal as OSC. With a five-second
AppleEvent timeout, both calls returned error `-1712`. Neither was resent.
Computer Use confirmed and removed the disposable fixtures. Fresh OSC
inventory matched the original 18 UUIDs in their original order; the GUI
still reported 241 cues.

The documented OSC delete variants provide no confirmation argument or
dialog-accept command. No documented confirmation preference was found in
the sources reviewed; this is not proof that no undocumented setting exists.
Changing UDP to TCP can improve transport handling but is not evidence of
different application confirmation behavior. Emptying roots cannot replace
deleting them: even the empty fixtures required confirmation. Script cues
do not offer a useful shortcut: OSC `scriptSource` is read-only, and executing
a Script cue would add show-control behavior to an editing operation.

A future MCP can complete the operation by owning a narrowly scoped local
macOS Accessibility adapter. Proposed flow: review all target UUIDs and
descendant impact, bind the plan to a confirmation token, resolve the exact
QLab PID/workspace, ensure no existing modal, send one OSC delete, validate
the resulting modal and target text, press its Delete button, then verify
UUID disappearance and the complete remaining root order through OSC.
Process one root at a time. Unknown dialogs, ambiguous names/workspace,
timeouts, missing permissions, or failed readback must stop the batch without
resending. Preserve confirmed, pending, and uncertain results.

This would let the agent use only the public MCP tool, while that tool uses
OSC plus local Accessibility internally. Computer Use proved that these
dialogs expose text and an actionable Delete button; an Accessibility
adapter inside this server has not been implemented or runtime-tested.
It would require macOS Accessibility permission for the actual server host
process, not merely the existing Codex Computer Use permission. It also
changes the server's currently documented OSC-only write boundary.

## Decision: root Delete deferred, root Move implemented

Delete QList is intentionally omitted. No Accessibility adapter, AppleScript
write backend or Mac configuration change is included. Root deletion remains
blocked in the existing cue Delete tool. The confirmations observed above
make direct OSC unsuitable for unattended root deletion in this tested setup.

`qlab_move_cue_lists` adds the proven root reorder route. It shares the existing
Move simulator, readiness gate, activity checks and sequential executor, with
a dedicated `confirm:moveCueLists:v1` token and full root/content audits.
Root List and Cart placements use one zero-based insertion index or a root
UUID anchor, resolving each move against the previous simulated result.
The ordinary cue Move route keeps its root and Cart-cell execution blocks.

Local tests use a disposable in-memory reader and a fresh FastMCP Client.
They verify root List/Cart placement, no-op moves, 50-item execution, token
family/expiry/content/order binding, invalid requests, activity, concurrency,
timeouts and preservation of confirmed progress. The local registry exposes
49 tools.

Local acceptance completed: **3140 tests and 47 subtests passed**, including
33 dedicated root-Move cases and a real FastMCP Client call against an
in-memory fixture reader. `fastmcp inspect fastmcp.json --skip-env` confirmed
49 tools; `git diff --check` passed. Socket-based transport tests required
execution outside the filesystem/network sandbox. No live QLab mutation was
performed during this implementation phase.

## Installed MCP validation — 2026-09-27

After the latest restart, the installed MCP exposes `qlab_move_cue_lists` and
49 QLab tools total (43 read-only and 6 gated writes). W1
`8E86FE91-668B-560C-B738-4D581B5A7498` was ready in Edit Mode with no active
cues. Its baseline had 18 roots (17 Cue Lists, 1 Cue Cart) and current Cue List
`7D2A06A3-B4BD-52D6-87A3-E7C27B7197AE`.

The first installed version had rejected same-batch moved-root anchors before
writing. The local fix permits this only for root moves, preserving the
existing restriction for regular cue moves. After the subsequent MCP restart,
the same batch passed: move Cue List
`236E4CCA-7E75-50D8-88C1-FA1C0C80DFB1` to `first`, then move Cue Cart
`2652E4DC-9483-5AF2-9DAE-E931ED037D51` after that List. Dry run and execution
both passed; execution returned `status=moved`, `moved_count=2`, and no pending
or uncertain UUIDs. Fresh reads confirmed the List at index 0 and Cart at
index 1.

The List contained Memo
`09B04FF8-0E7B-52D6-AF94-7A858C7CE77D`. MCP readback before and after the move
confirmed that exact child UUID remained inside it. The Cart remained empty.
Computer Use visually confirmed the order and Memo. A prior `qlab_create_cues`
attempt had failed with `QLab successful reply JSON missing data`; this run
created the Memo using raw OSC and verified its UUID through MCP.

Both root fixtures were returned to indices 18 and 19. The original 18-root
UUID order and current Cue List were confirmed before cleanup. Cleanup sent one
OSC `/delete_id/<uuid>` per fixture; Computer Use inspected each matching
confirmation dialog before accepting it. Final MCP inventory is exactly the
original 18 roots, 17 Lists and 1 Cart, and Computer Use showed 241 cues. The
temporary List, Cart, and Memo UUIDs are absent; no original cue was removed.
QLab's [Cue Lists manual](https://qlab.app/docs/v5/fundamentals/cue-lists/)
and [Cue Carts manual](https://qlab.app/docs/v5/fundamentals/cue-carts/) state
that deletion can be undone.

Local checks passed: `pytest tests/test_move_cue_lists.py -q` (35 passed),
`pytest -q` (3142 passed, 47 subtests), and `git diff --check`. The first
full-suite run inside the sandbox could not bind localhost sockets; rerunning
outside it passed. Runtime failure injection, rollback, GO, playback, Save,
and root deletion through the public MCP tool were not tested. The public root
Delete tool remains deferred because QLab presents a graphical confirmation.

Use `scripts/capture_move_delete.py` with `tool=qlab_move_cue_lists` to capture
one reviewed call, complete responses and errors, with tokens and sensitive
fields redacted. It never retries. Real writes require `--execute`,
`dry_run=false` and the reviewed token; output files are created exclusively
to prevent accidentally overwriting prior evidence.
