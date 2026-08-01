# Group Edge Runtime Validation

Status: active; bounded edge validation remains.

The implemented and runtime-validated Group contract is preserved in
[`028_group_cue_safe_editing.md`](../../../archive/workorders/completed/028_group_cue_safe_editing.md).

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
