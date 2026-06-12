# qlab_update_cues Runtime Checklist

Use this checklist only on a disposable editable QLab test workspace.

Hard limits:

- Use only QLab MCP tools.
- Use explicit `workspace_id` on every tool call.
- Do not use raw OSC.
- Do not run GO, playback, start, stop, pause, load, or panic commands.
- Do not test live/output fields as real writes: Light commands, Network sends,
  MIDI output payloads, Script source/text, target refs, patch refs, file
  targets, audio levels, dashboard, DMX/Art-Net, or Fade target/output fields.
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
