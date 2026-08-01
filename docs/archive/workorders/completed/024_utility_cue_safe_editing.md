# Utility Cue Safe Editing

Status: runtime validated and closed for exact `cueTargetID` on listed utility cues.

## Scope

The `qlab_edit_cues` saved configuration path supports a token-gated
`cueTargetID` update for these exact QLab readback types:

- `Start`, `Stop`, `Pause`, `Load`, `Goto`, `Arm`, `Disarm` via `target_basic`
- `Reset` via `reset_basic`

`Wait` and `Memo` remain Basics-only. Memo uses generic `notes`; QLab has no
documented Memo-specific text setter. Wait has no target and its timing remains
under the existing common duration guard.

## Gate

The only promoted target route is saved
`/workspace/{workspace_id}/cue_id/{source_uuid}/cueTargetID`.

- exact source UUID, one cue, one property, saved mode
- source and requested target must be healthy and inactive
- source must expose `hasCueTargets`; target must exist in the same workspace
- self-target and target-by-name/number are rejected
- fresh baseline and exact fresh readback are required
- `confirm:utilityTarget:v1:` binds workspace, source UUID/type, profile,
  property, baseline target, and requested target
- rollback uses a newly issued token; clearing to an empty baseline is allowed
  only from a non-empty current baseline

## Blocked

- `cueTargetNumber`, `cueTargetName`, temporary targets
- Reset `patchTargetID`, `audioMapTargetID`, and `targetMode`
- `Target` cue target writes; Devamp saved configuration is tracked in
  `025_devamp_network_osc_safe_editing.md`
- actions such as `/start`, `/stop`, `/pause`, `/load`, `/go`, `/reset`
- `/live`, batch/multi-property real writes, raw OSC, playback, and save

## Evidence

Research matrix:
`docs/archive/research/cue-editing/utility_cue_editing.md`.

Local tests cover profile/type mismatch, source/target validation, token
binding and rejection, batch/multi-property rejection, saved-mode enforcement,
fresh readback, and fresh-token rollback. Runtime validation passed for exact
source/target assignment and final `0/0/0` activity. Names, numbers, temporary
targets, Reset patch/map targets, actions, `/live`, batches, and unsupported
families remain blocked.
