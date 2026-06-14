# qlab_update_cues Runtime Checklist

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
- `fileTarget` real writes require `QLAB_ALLOWED_FILE_ROOTS` to include the
  intended test media root.
- Run `dry_run=true` before any `dry_run=false` write.

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
3. Run `qlab_update_cues(..., dry_run=true)` using profile `common` and safe properties:
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

1. Run `qlab_update_cues(..., dry_run=true)` with the exact before values.
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
2. Run `qlab_update_cues(..., dry_run=true)`.
3. If the field's read key is readable, expect planned operations and
   `executed_operations=[]`. Some cataloged dry-run-only fields may instead fail
   read-before preflight because their read key is intentionally not exposed by
   the safe read allowlist.
4. Run the exact same field with `dry_run=false`.
5. Expected real-write block:
   - clean preflight exception or failed result before setters
   - no mutating setter execution
   - no playback/control/raw OSC

Playlist Group smoke:

1. Pick one disposable Group cue whose `mode` is not `6`.
2. Run `qlab_update_cues(..., dry_run=false)` for
   `playlist/crossfade/duration`.
3. Expected block:
   - preflight fails before setters
   - error says Playlist setters require Playlist mode `(mode 6)`
4. Pick or create a disposable Playlist Group cue whose `mode` is already `6`.
5. Run `dry_run=true`, then `dry_run=false`, for:
   - `playlist/doCrossfade`
   - `playlist/crossfade/duration`
6. Expected real write:
   - setter uses `/cue_id/{uniqueID}/playlist/...`
   - read-after-write confirms values
   - small floating-point readback differences are accepted

Mic input routing smoke:

1. Run `qlab_update_cues(..., dry_run=true)` for `mic_basic.channelOffset`.
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
2. Run `qlab_update_cues(..., dry_run=false)` for `duration`.
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
2. Run `qlab_update_cues(..., dry_run=true)` for `cueTargetID` with
   `confirm_gates=["target_resolution"]`.
3. Run the same with `dry_run=false`.
4. Expected real write:
   - preflight reads the target cue before setters
   - setter uses `/cue_id/{uniqueID}/cueTargetID`
   - read-after-write confirms target ID
5. Repeat with a missing target ID.
6. Expected block:
   - no `/cueTargetID` setter is sent
   - error says target could not be resolved
7. Repeat with `cueTargetName`.
8. Expected block:
   - no `/cueTargetName` setter is sent
   - error says name resolution is unsupported; use `cueTargetID` or `cueTargetNumber`

Capability gate smoke:

1. Pick one disposable cue and one high-risk property whose
   `planned_operations[]` includes a `capability_gate`.
2. Run `qlab_update_cues(..., dry_run=true)` with no `confirm_gates`.
3. Run the same update with `dry_run=false` and no `confirm_gates`.
4. Expected block:
   - no setter sent
   - error names the required gate
5. Run the same update with `dry_run=false` and
   `updates[].confirm_gates=[required_gate]`.
6. Expected gated write:
   - setter uses `/cue_id/{uniqueID}/...`
   - fresh read-after-write verifies the requested value when the property is readable
   - report any property that cannot be read back as inconclusive, not passed

Recommended gate order on a dummy workspace:

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
- count of `qlab_update_cues` calls
- count of real-write calls
- count of timeout-confirmed cues
- any unexpected `executed_operations`
- verdict: OK, needs fix, or inconclusive
