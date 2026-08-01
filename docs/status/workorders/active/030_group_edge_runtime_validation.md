# Group Edge Runtime Validation

Status: active; bounded edge validation remains.

The implemented and runtime-validated Group contract is preserved in
[`028_group_cue_safe_editing.md`](../../../archive/workorders/completed/028_group_cue_safe_editing.md).

## Local deterministic evidence

On 2026-08-01, branch `validation/group-edge-runtime` added focused local
coverage for the 200-child ordered snapshot, warning-but-not-broken fail-closed
behavior, exact-shortest-child crossfade, zero-duration crossfade, and
process-bound token invalidation. The suite passes with `2451 passed, 41
subtests passed`.

This does not close the runtime workorder. QLab 5.5.10 runtime proof remains
pending. The current read-only readiness probe selected disposable workspace
`mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`), confirmed Edit Mode,
healthy inactive target fixtures, and recorded DMX output enabled without
changing it. The active MCP dry-run process did not return a Group confirmation
token, so no real Group setter was attempted; restart/reload the active MCP
process before runtime writes. The workspace currently has no approximately
200-child Group fixture, so that case remains blocked until a disposable
fixture exists outside MCP mutation.

## Pending scope

- Repeat consumed-token replay validation after a confirmed MCP restart and
  verify `confirmation_already_consumed` is returned before no-op detection.
- Validate a Group with approximately 200 direct children.
- Validate Loop rejection with a zero-duration child.
- Validate rejection when crossfade exceeds the shortest child.
- Validate the minimum accepted crossfade duration.
- Validate a warning-but-not-broken Group.
- Validate token expiry in a live MCP process.

## Required procedure

- Disposable workspace and exact workspace/Group UUIDs.
- Group and all children inactive and healthy enough for the selected case.
- Confirm `running/paused/auditioning = 0/0/0`.
- Dry-run, fresh token, one setter when a setter is expected, fresh Group and
  child readback, and fresh-token rollback.
- No GO, playback, audition, raw OSC, panic, deletion, or unrelated mutation.

## Historical or blocked only

Playback, active or auditioning Groups, undocumented curve setters, Timeline
inspector gestures, and playhead/control routes are not part of this workorder.
