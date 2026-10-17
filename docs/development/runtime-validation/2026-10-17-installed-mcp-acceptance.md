# Installed MCP acceptance — 2026-10-17

## Scope

This report records the preceding authorized MCP-only session against QLab
5.5.10 and one existing test workspace. No repository code, source media or
dependencies were changed. No cues were executed. File access was explicitly
authorized for this test. Public prose omits private document paths and UUIDs;
they must be resolved again for any future operation.

The development checkout was `9a346bc`. The installed connector exposed all
79 tools, but its process/source fingerprint was not captured: this report
does not prove byte identity between the running installation and that commit.
Evidence consists of the session's MCP responses and fresh readbacks; no new
machine-readable capture or UI comparison is committed with this report.

**All tools were invoked; not every possible operation, argument combination
or failure mode was tested.** A preview or expected block is not execution proof.

## Results

| Area | Observed coverage |
| --- | --- |
| Connection and readiness | One explicit workspace, accepted passcode, confirmed Edit permission and Edit Mode; zero active cues. |
| Read tools | All 49 tools invoked, including 13 scoped family inventories and their details, lists/carts, six settings domains, exact Video objects, fonts and native document inventory. |
| Queries and profiles | All 29 Query filters, an AND-filter case, eight generic detail profiles and technical/native-trigger family reads. Bounded results disclosed truncation. |
| Pagination | Scoped inventory offsets, all six ten-effect catalogue pages (60 effects), and audio continuation with `expected_analysis_id`. |
| Media | Home-folder search returned no match before its 20,000-entry cap; that is an incomplete search, not proof of file absence. A separately resolved authorized MP3 decoded and produced measurements and continuation pages. |
| Cue creation and editing | Created 24 template-backed cue types. All 16 family editors performed confirmed real writes on representative fields; some operations changed only common Basics, not every family setting. Audio and Video file assignments repaired missing-media placeholders in separate calls. |
| Native fields | Load `loadTime=1.25`, Target `assignedNumber="2"`, and Wall Clock hour configuration on a disarmed Audio cue with its trigger disabled matched readback. No incoming signals or activation were tested. |
| Other representative edits | Camera opacity, Text content/font size, Mic duration, Network saved text, Timecode SMPTE start, Group mode and Fade/Devamp target assignment. A MIDI note alias setter verified the unchanged requested value of 60. Playlist looping was blocked for a zero-duration child. |
| Structural writes | Renamed/restored a Cue List, moved a temporary Memo into a Group, reordered/restored the original root list, deleted 23 explicit temporary leaves, then deleted the empty temporary Group. Fresh structural readback confirmed results. |
| Workspace settings | Changed/restored General minimum GO time, Audio patch Main level, stage name, region grid and output guides. Final Gets returned the original values. |

Real writes succeeded through **26 of the 30 write tools**. The remaining four:

- `qlab_create_cue_lists`: previewed List/Cart creation only; no new roots were
  created, because unattended root deletion is unsupported.
- `qlab_save_workspace`: preview succeeded; execution was omitted because it
  would also save the operator's pre-existing unsaved edits.
- `qlab_close_workspace`: correctly blocked the dirty document.
- `qlab_open_workspace`: correctly blocked opening while a workspace was open.

## Rejections and incidents

Reused confirmations were rejected with zero updates. Hotkey enabling was
blocked without readable key/modifier identity. Cart creation rejected a
nonempty Cart; cross-parent Cart moves remained blocked. Missing healthy
media/targets blocked dependent settings, and Target rejected an incompatible
receiver. Broken Video rejected visual edits while a separate file assignment
was permitted. Invalid Query boolean `"on"`, numeric Timecode `startTime`, and
catalogue `limit=60` were rejected; valid requests then used the documented types
and page limit. These malformed caller inputs are not implementation failures.

One Script preview failed to confirm Edit permission. A fresh readiness check
returned `ready`; a new preview, execution and restoration then succeeded.
This transient observation remains recorded; its underlying cause was not
established and no ambiguous mutation was retried.

Four configured Video routes reported disconnected. That observation does not
diagnose the USB-C connection or establish physical output behavior.

## Cleanup and limits

All 24 temporary cues were deleted with fresh confirmation and disappearance
readback. The final structural index exactly matched all **493 original rows**,
including identifiers, numbers, labels, types, parents and order. Root order
also matched. Pre-existing cue names and the five edited settings were restored.
The workspace stayed open in Edit Mode, dirty as before, with zero active cues.

Selection changed from one original cue to empty after creation/deletion. It
was not restored: this MCP exposes no selection setter. Structural equality
therefore must not be described as complete UI-state restoration.

No Save/Open/Close event, new root creation, Cart cell mutation, recursive
Group-root removal, full matrix/FX-parameter exercise, playback, rendering,
hardware output or other QLab version was validated by this pass. Existing
dated evidence for other cases remains separate. Current contracts are in the
[catalogue](../../user/tools.md) and [workflows](../../user/agent-workflows.md).
