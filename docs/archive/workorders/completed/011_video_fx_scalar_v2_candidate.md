# Video Phase 6 - Video FX Scalar v2 Runtime Closure

Status: runtime validated and closed for the exact `inputIntensity` scope below.

Goal: add exactly one more ultra-limited Video FX scalar real-write path without
broadening the Video FX write surface.

Only this Phase 6 path may emit a v2 real-write token:

- token: `confirm:videoFxScalar:v2:`
- cue type: `Video`
- profile: `video_basic`
- cue ref: exact cue UUID only
- property: `videoEffectIndex/parameter`
- effect index: `0`
- parameter key: `inputIntensity`
- value: finite number
- mode: saved only
- batch shape: one cue, one operation
- token binding: fresh baseline/readback plus raw effect payload hash
- retry policy: no mutating retry

Phase 4C remains unchanged:

- `confirm:videoFxScalar:v1:` means `inputRadius` only.
- v1 must not authorize v2.
- v2 must not authorize v1.

## Runtime validation

Runtime workspace:

- workspace: `<TEST_WORKSPACE_NAME>`
- workspace UUID: `<TEST_WORKSPACE_UUID>`
- cue: `<TEST_VIDEO_CUE_NAME>`
- cue UUID: `<TEST_VIDEO_CUE_UUID>`
- property: `videoEffectIndex/0/parameter/inputIntensity`
- token family: `confirm:videoFxScalar:v2:`

Happy-path proof:

- baseline: `2.6191787554229933`
- later fresh baseline: `2.6191787719726562`
- requested: `2.7191787554229934`
- write passed; setter timeout was accepted only because fresh readback matched
  `2.7191786766052246`
- rollback passed; setter timeout was accepted only because fresh readback
  matched `2.6191787719726562`
- final target restored within QLab float precision
- workspace running/paused/auditioning: `0/0/0`
- pre-existing broken cues outside the target were noted and were not blockers

Rejection sweep:

- fake v2 token rejected
- malformed v1-looking token rejected
- valid v2 token with changed value rejected
- valid v2 token for `inputPower` rejected
- valid v2 token for `Choose_Effect` rejected
- cue ref `v11` instead of exact UUID rejected
- multi-property call rejected
- all rejection probes had `executed_operations=[]`
- final readback remained baseline exactly: `2.6191787719726562`

## Safety behavior

- fresh dry-run baseline from `videoEffects`
- flat QLab 5.5.10 payload only
- raw effect payload hash in token
- exact workspace, cue UUID, profile, property, index, parameter, mode, value,
  baseline, and risk context bound into token
- real write sends one saved setter only after matching token
- setter timeout accepted only when fresh readback matches
- no mutating retry

## Must stay blocked

- `inputPower`
- `Choose_Effect`
- any other parameter
- Camera FX
- Text FX
- effect targeting by name
- enabled/disabled
- add/insert/delete/move/reorder
- aggregate `videoEffect*/parameters`
- string, enum, color, list, or dict values
- `/live`
- batch
- multi-property
- cue-number real writes
- Workspace Video, stages/routes/surfaces, video input/camera patches,
  `fileTarget`, warping/control points, playback/show-control actions

## Local checks

Covered by `tests/test_write_mode.py -k "video_fx"`:

- v2 dry-run token only for exact `Video` `videoEffectIndex/0/parameter/inputIntensity`
- v2 real write sends exactly one saved setter
- setter timeout plus matching readback yields `setter_timeout_but_readback_matched`
- v1 remains `inputRadius` only
- v1/v2 cross-token attempts reject before mutation
- stale baseline and raw payload drift reject before setter
- blocked families and wrong shapes reject before mutation
