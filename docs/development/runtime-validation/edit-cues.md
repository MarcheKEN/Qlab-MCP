# qlab_edit_cues Runtime Checklist

`qlab_edit_cues` is the only public cue-edit tool.

Use this checklist only on a disposable editable QLab test workspace.

Hard limits:

- Use only QLab MCP tools.
- Use explicit `workspace_id` on every tool call.
- Do not use raw OSC.
- Do not run GO, playback, start, stop, pause, load, or panic commands.
- Test high-risk real writes only in a disposable workspace with dummy/disabled
  outputs, one capability family at a time.
- `scriptSource` and `scriptText` are not editable by documented OSC; only
  `compileSource` can be planned behind `script_compile`.
- `fileTarget` and file path writes are blocked by default; real writes require
  both the exact dry-run `confirm_token` and `QLAB_ALLOWED_FILE_ROOTS` covering
  the intended test media root.
- Run `dry_run=true` before any `dry_run=false` write.

Public write-tool confirmation boundaries:

- `qlab_create_cue` / `qlab_create_cues`: review the dry-run first, pass the
  exact dedicated token, and follow the separate [`create-cues.md`](create-cues.md)
  checklist. Anchors must be inactive and structurally stable, but may be
  broken or warning; ambiguous `/new` results are never retried.
- `qlab_edit_cues`: copy exact relevant
  `planned_operations[].confirm_token` values into the same update item's
  `confirm_gates`; there is no tool-level Edit token.
- `qlab_move_cues` and `qlab_delete_cues`: after an eligible reviewed dry-run,
  pass its exact dedicated tool-level `confirm_token`. Restarting the MCP
  invalidates previously issued Move and Delete tokens.

Preflight:

1. `qlab_check_connection(require_read_access=true)`.
2. Select a clearly disposable/test workspace. Stop if ambiguous.
3. `qlab_check_write_readiness(workspace_id=...)`.
4. Continue only when:
   - `write_enabled=true`
   - `passcode_configured=true`
   - `/connect` confirms edit permission
   - `/showMode` reports Edit Mode
   - `blockers=[]`

Batch timeout smoke:

1. Pick 20-50 existing disposable test cues with concrete cue IDs.
2. Read current `flagged` and `colorName` with `qlab_get_cue_details(profile="basic_safe")`.
3. Run `qlab_edit_cues(..., dry_run=true)` using profile `common` and safe properties:
   - `flagged=true`
   - `colorName="blue"`
4. Expected dry-run:
   - `ok=true`
   - `status="dry_run"`
   - `planned_count` equals cue count
   - `executed_operations=[]`
5. Run the same batch with `dry_run=false`.
6. Expected real write when QLab setter replies time out but after-read confirms:
   - The MCP tool returns normal JSON before the host/tool timeout.
   - `ok=true`
   - `status="updated_with_confirmed_timeouts"`
   - `updated_count` equals cue count
   - `failed_count=0`
   - `timeout_confirmed_count` equals cue count when every cue had at least one setter timeout
   - Each timed-out setter has `status="timeout_pending_verification"`.
   - Each result `after` confirms requested values.

Rollback smoke:

1. Run `qlab_edit_cues(..., dry_run=true)` with the exact before values.
2. Expected rollback dry-run:
   - `ok=true`
   - `status="dry_run"`
   - `executed_operations=[]`
3. Run rollback with `dry_run=false`.
4. Expected rollback real write:
   - normal JSON response
   - `ok=true`
   - `status="updated"` or `status="updated_with_confirmed_timeouts"`
   - `failed_count=0`
5. Verify final values with `qlab_get_cue_details(profile="basic_safe")`.

Safety block smoke:

1. Pick one returned `dry_run_only_properties` field from
   `qlab_get_cue_details(profile="editable")`, preferably a clear test cue.
2. Run `qlab_edit_cues(..., dry_run=true)`.
3. If the field's read key is readable, expect planned operations and
   `executed_operations=[]`. Some cataloged dry-run-only fields may instead fail
   read-before preflight because their read key is intentionally not exposed by
   the safe read allowlist.
4. Run the exact same field with `dry_run=false`.
5. Expected real-write block:
   - structured failed result before setters
   - no mutating setter execution
   - no playback/control/raw OSC

Playlist Group smoke:

1. Use only a disposable workspace and explicit workspace/cue UUIDs. The Group
   and every direct child must be inactive; do not use GO, playback, audition,
   raw OSC, panic, deletion, or unrelated mutations.
2. Record fresh Group mode, health/activity, Playlist scalars, ordered direct
   children, child timing/continue state, and global running/paused/auditioning
   counts. Stop unless the counts are `0/0/0`.
3. Run exactly one `group_basic` property with `dry_run=true`. Eligible mode
   writes emit `confirm:groupMode:v1:`; eligible Playlist writes emit
   `confirm:groupPlaylist:v1:` only when fresh mode is `6`.
4. Review the exact UUID address, baseline/requested value, health checks,
   ordered child fingerprint, duration constraints, and rollback requirement.
   Any broken Group or child must fail closed before a setter.
5. Use the fresh token once for the real write. The token must be consumed
   atomically immediately before exactly one setter send. Require fresh scalar
   and child readback. A confirmed timeout must return
   `updated_with_confirmed_timeouts`; never retry the mutating setter. Any child
   order/timing/continue/health change must be surfaced in both `side_effects`
   and `group_child_readback`; it must not be restored implicitly.
6. Roll back only with a new dry-run and new token. Confirm the original scalar
   and every affected child field with fresh readback.
7. Finish only when running/paused/auditioning counts are again `0/0/0`.
8. Replay the accepted token once before and once after rollback. Both attempts
   must execute zero setters; after baseline restoration the error must identify
   the consumed confirmation. Stop if replay is accepted.

Crossfade curve shapes remain blocked because the local OSC dictionary has no
documented deterministic setter/readback. Timeline inspector gestures are
child edits, not Group scalar properties, and are outside this smoke check.
Workorder 030 closed the bounded QLab 5.5.10 cases with a disposable
`378`-child Group, finite and mixed zero/finite Playlist Loop, exact-UUID
single-setter timeout/readback/rollback, consumed-token replay, and
crossfade-over-shortest preflight rejection. Requested `1 s` and `2 s`
crossfade durations retained/read back as `3 s` in that fixture; this is an
observed fixture/version mismatch, not a documented global minimum, so
short/equal active crossfade behavior remains unconfirmed. All-zero-child
Loop, warning-only Groups, active/auditioning Groups, live token expiry, and
live MCP restart invalidation remain separate follow-up limits.

Mic input routing smoke:

1. Run `qlab_edit_cues(..., dry_run=true)` for `mic_basic.channelOffset`.
2. Expected dry-run:
   - planned setter exists
   - `real_write_enabled=false`
   - `capability_gate="patch_routing"`
3. Run the same with `dry_run=false` and no `confirm_gates`.
4. Expected block:
   - no `/channelOffset` setter is sent
   - error names `patch_routing`

Editable duration smoke:

1. Pick one disposable Wait or Memo cue where
   `qlab_get_cue_details(profile="editable")` reports
   `allowsEditingDuration=false`.
2. Run `qlab_edit_cues(..., dry_run=false)` for `duration`.
3. Expected block:
   - preflight fails before setters
   - no `/duration` setter is sent
   - error says `duration requires a cue with editable duration`
4. Pick one disposable Audio/Video/Fade cue where
   `allowsEditingDuration=true`.
5. Run `dry_run=true`, then `dry_run=false`, for a reversible `duration`
   value.
6. Expected real write:
   - setter uses `/cue_id/{uniqueID}/duration`
   - read-after-write confirms value within numeric tolerance

Target resolution smoke:

1. Pick one disposable target cue and one disposable Start/Stop/Pause/Load/GoTo/Arm/Disarm cue.
2. If the source is initially untargeted and QLab reports it broken solely
   because the saved target is empty, verify `cueTargetID==""`,
   `isWarning==false`, and inactive activity flags. This is the only broken
   source allowed for initial assignment.
3. Run `qlab_edit_cues(..., dry_run=true)` for `cueTargetID`.
4. Copy the exact `planned_operations[].confirm_token` for `cueTargetID` into
   `updates[].confirm_gates`, then run the same with `dry_run=false`.
5. Expected real write:
   - preflight reads the target cue before setters
   - setter uses `/cue_id/{uniqueID}/cueTargetID`
   - read-after-write confirms target ID
6. Repeat with a missing target ID.
7. Expected block:
   - no `/cueTargetID` setter is sent
   - error says target could not be resolved
8. Repeat with `cueTargetName`.
9. Expected block:
   - no `/cueTargetName` setter is sent
   - Utility real writes allow only `cueTargetID`; `cueTargetName` and
     `cueTargetNumber` remain blocked
   - both source `cue_ref` and requested target must be exact UUIDs
10. Repeat with an already-targeted or warning/broken source; it must remain
    blocked before any setter.

Network OSC Message smoke:

1. Pick one disposable, healthy, inactive Network cue whose current patch is
   freshly classified as `OSC Message`.
2. Run `qlab_edit_cues(..., dry_run=true)` for one saved `customString` change.
3. Copy its exact `confirm:networkOscMessage:v1:` token into that update item's
   `confirm_gates`, run `dry_run=false`, and verify fresh readback.
4. Roll back through a new dry-run and fresh token, then verify final readback.
5. Treat `networkPatchID` reassignment as blocked/planned-only. Do not execute
   it: the tested reassignment left the cue broken.

`QLAB_UPDATE_DEBUG` diagnostics:

- Default is `false`. Set `QLAB_UPDATE_DEBUG=true` before starting the MCP only
  for deliberate Edit diagnostics.
- Real `qlab_edit_cues` result items then include `debug` data such as requested
  properties/values, readback values, match state, timeouts, and errors.
- Treat debug output as potentially sensitive. Disable it after diagnosis.
- This flag changes result diagnostics only; it does not weaken readiness,
  confirmation, health, activity, or readback gates.

Capability gate smoke:

1. Pick one disposable cue and one high-risk property whose
   `planned_operations[]` includes a `capability_gate`.
2. Run `qlab_edit_cues(..., dry_run=true)` with no `confirm_gates`.
3. Confirm the dry-run plan includes `capability_gate` and `confirm_token`.
4. Run the same update with `dry_run=false` and no `confirm_gates`.
5. Expected block:
   - no setter sent
   - error names the exact required `confirm_token`
6. Run the same update with `dry_run=false` and
   `updates[].confirm_gates=[confirm_token_from_dry_run]`.
7. Expected gated write:
   - setter uses `/cue_id/{uniqueID}/...`
   - fresh read-after-write verifies the requested value when the property is readable
   - report any property that cannot be read back as inconclusive, not passed

Recommended dry-run capability labels to exercise on a dummy workspace:

- `cue_behavior`
- `target_resolution`
- `file_target_access`
- `patch_routing`
- `audio_output`
- `slice_editing`
- `spatial_audio`
- `audio_map_editing`
- `video_visual`
- `video_effects`
- `text_rich_format`
- `fade_targets`
- `light_output`
- `network_output`
- `midi_output`
- `script_compile`

Report:

- workspace name and ID
- cue count and cue IDs tested
- dry-run status
- real-write status
- rollback status
- final readback result
- count of `qlab_edit_cues` calls
- count of real-write calls
- count of timeout-confirmed cues
- any unexpected `executed_operations`
- verdict: OK, needs fix, or inconclusive
