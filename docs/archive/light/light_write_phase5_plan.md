# LIGHT PLAN Phase 5 — saved Light Cue flags

## Scope

Phase 5 enables real writing of one saved Boolean property—`alwaysCollate` or `subcontroller`—on one cue of exact type `Light` through `qlab_update_cues`, with `profile="light_basic"` and `saved` mode.

It does not enable live actions, Dashboard, playback, raw OSC, the Light Patch, combined `lightCommandText`, or any other Light operation.

## Contract and preflight

A confirmable dry-run returns `real_write_possible=true`, `requires_confirm_token=true`, `phase5_light_behavior_candidate=true`, `real_write_enabled=false`, `planned_only_reason="light_behavior_requires_confirm_token"`, and token `confirm:lightBehavior:v1:...`.

Real writing requires write mode enabled, a passcode, `/connect` with edit scope, QLab Edit Mode, an explicit workspace UUID, one cue, one property, an exact token, a fresh Boolean baseline, and a cue of type `Light`. Batches, mixed properties, and live mode are blocked before any setter.

The HMAC token binds the version, `operation_kind="phase5_light_behavior_flag_write"`, workspace, cue ref/UUID, profile, property, path, mode, baseline, requested, risk, and capability gate. It is valid for the lifetime of the process and is not single-use. Rollback requires a new dry-run and a new token.

After the setter, the cache is cleared and an exact Boolean readback is required. A changed baseline returns `stale_light_behavior_baseline`; a different readback returns `verification_failed`.

## Blocked operations

- `alwaysCollate` and `subcontroller` together.
- Either of them together with `lightCommandText` or another property.
- `collateAndStart`, `setLight`, `replaceLightCommand`, `removeLightCommandsMatching`, `safeSort`, `prune`, and aliases.
- Dashboard, playback, GO, start, stop, panic, audition, preview, raw OSC, and patch/DMX edits.

## Test matrix

The fake client covers both directions of both flags, token/context, rollback, stale baseline, a non-Light or missing cue, batches, mixed operations, live mode, readiness, readback mismatch, and the absence of prohibited addresses. Phase 4 remains mandatory regression coverage.

## Phase 5B runtime protocol

Use only `<TEST_WORKSPACE_NAME>`, with an explicit workspace UUID and without running cues:

1. Confirm readiness and a fresh baseline.
2. L1: `alwaysCollate false → true`; read back; run a new dry-run/token; roll back `true → false`; read back the final value.
3. L2: `subcontroller true → false`; read back; run a new dry-run/token; roll back `false → true`; read back the final value.
4. Abort on an unexpected baseline, failed preflight, or mismatch. Do not continue after a failure.
