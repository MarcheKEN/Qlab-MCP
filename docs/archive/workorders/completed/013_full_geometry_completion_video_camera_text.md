# Workorder 013 - Full Geometry Completion for Video/Camera/Text

Status: runtime validated and closed for `layer` only.

## Scope

Cue types:

- `Video`
- `Camera`
- `Text`

Runtime-validated Phase 7B real-write candidate:

- `layer`

Existing real-write candidates remain unchanged:

- `opacity`
- `translation/x`, `translation/y`
- `scale/x`, `scale/y`
- `anchor/x`, `anchor/y`
- `cropTop`, `cropBottom`, `cropLeft`, `cropRight`
- `blendMode`
- `preserveAspectRatio`
- `fillStage`
- `fillStyle`

## Geometry Matrix

Editable:

- `layer`: integer `0..1000`, saved mode only, exact cue UUID only, one cue,
  one property, fresh `confirm:videoGeometry:v2:` token, fresh readback, and
  fresh-token rollback. Runtime validated for `Video`, `Camera`, and `Text`.
- `fillStage`: existing `confirm:videoGeometry:v1:` path unchanged.
- `fillStyle`: existing `confirm:videoGeometry:v1:` path unchanged.
- Previous Phase 3 visual properties listed above remain in their existing
  token families.

Dry-run only / planned-only:

- aggregate geometry operations: `anchor`, `translation`, `scale`, `crop`
- `clockType`, `holdLastFrame`, `smooth`
- Video FX geometry/effect families outside their closed scalar exceptions

Read-only:

- cue health and inactive state
- current geometry baselines exposed by cue reads
- `stage`, `stage/regions`, `stage/size`, `stage/uniqueID`
- `surfaceList`, `surfaceSize`

Blocked / future:

- `origin`, `origin/x`, `origin/y`: deprecated aliases of `anchor`; use
  non-deprecated `anchor/x` and `anchor/y`.
- top/bottom layer aliases: no documented cue OSC route found; numeric `layer`
  is the only implemented ordering control.
- `rotation`: dictionary route is under Fade cue geometry, not direct
  Video/Camera/Text geometry.
- `quaternion`: requires separate 3D visual proof and reliable rollback model.
- `resetRotation`: action route has no scalar baseline and needs separate
  reversible runtime proof.
- shutters: no QLab 5 cue OSC route found in the local dictionary.
- `stageName`, `stageNumber`, `stageID`, `surfaceName`, `surfaceID`: routing/
  stage assignment changes need dedicated resolution and rollback proof.
- `stage/region/*` bounds, grid, guide, `moveBy`, and
  `resetControlPoints`: region/stage topology writes; rollback/readback is not
  simple enough for this phase.
- warping and control points: no safe single-property reversible write path
  exposed for this phase.
- `/live`, batch, multi-property, cue-number real writes, raw OSC, playback,
  and workspace save.

## Token Contract

`layer` uses `confirm:videoGeometry:v2:`. The token binds:

- workspace UUID
- cue UUID and cue type
- profile
- property/path
- saved mode
- baseline and baseline hash
- requested value
- risk tier and capability gate
- token version and operation kind

`confirm:videoGeometry:v1:` remains valid only for `fillStage` and `fillStyle`.
It cannot authorize `layer`.

## Runtime Validation

Runtime validation passed on `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`) for `layer` with
`confirm:videoGeometry:v2:`.

Validated scope:

- `Video`, `Camera`, and `Text`
- saved mode only
- exact cue UUID only
- one cue
- one property
- integer layer `0..1000`
- fresh dry-run token
- fresh readback
- rollback to baseline

Cues:

- `Video` `<TEST_VIDEO_CUE_NAME>` (`<TEST_VIDEO_CUE_UUID>`):
  `1000 -> 11 -> 1000`
- `Camera` `<TEST_CAMERA_CUE_NAME>` (`<TEST_CAMERA_CUE_UUID>`):
  `1000 -> 11 -> 1000`
- `Text` `<TEST_TEXT_CUE_NAME>` (`<TEST_TEXT_CUE_UUID>`):
  `1000 -> 11 -> 1000`

All real writes and rollbacks returned `setter_timeout_but_readback_matched`;
this was accepted only because fresh readback matched the requested value. No
mutating setter was retried. Targets were healthy and inactive. Final workspace
running/paused/auditioning was `0/0/0`. Unrelated pre-existing broken cues were
not blockers.

Rejection probes passed before setter with `executed_operations=[]`:

- fake v2 token
- v1 geometry token for `layer`
- cue number instead of UUID
- `/live`

## Tests

Local tests plus runtime validation cover:

- `Video`/`Camera`/`Text` dry-run token emission for `layer`
- `confirm:videoGeometry:v2:` payload binding
- real write sends one setter and verifies readback
- fresh-token rollback for `layer`
- v1 token rejection for `layer`
- fake/stale/wrong property/wrong value/cue-number/`/live`/batch/multi-property
  rejection before setter
- blocked `rotation`, `quaternion`, `resetRotation`, shutters, stage/region
  `moveBy`, and `resetControlPoints`
- existing Phase 3/4/5/6/7 behavior unchanged

Required local checks:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "geometry or video"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```
