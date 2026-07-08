# Workorder 014 - Rotation, Quaternion, ResetRotation, and Shutter Geometry

Status: audited. `quaternion` moved to Phase 7D local implementation; all other
Phase 7C routes remain blocked.

## Scope

Cue types:

- `Video`
- `Camera`
- `Text`

Investigated routes:

- `rotation`
- `quaternion`
- `rotate/x`, `rotate/y`, `rotate/z`
- `resetRotation`
- shutter/shutters

## Findings

Source of truth: `docs/references/qlab_osc_dictionary.md`.

| Route | Cue types | OSC path | Readback available? | Setter available? | Value type | Status | Reason | Runtime validation needed? |
|---|---|---|---|---|---|---|---|---|
| `rotation` | Fade; not accepted for Video/Camera/Text write profiles | `/cue/{cue_number}/rotation` | Yes, but only when cue is using single-axis rotation; otherwise returns `0` | Yes, but only affects single-axis rotation; otherwise no effect | number, degrees | blocked for Video/Camera/Text | Semantics are Fade/single-axis dependent and can no-op; not a safe direct Video/Camera/Text property | yes, before any future route |
| `rotationType` | Fade | `/cue/{cue_number}/rotationType` | yes | yes | integer `0..3` | blocked for Video/Camera/Text | Fade geometry mode selector, not direct Video/Camera/Text geometry | yes, before any future route |
| `quaternion` | Video/Camera/Text dictionary section | `/cue/{cue_number}/quaternion {a} {b} {c} {d}` | yes, array of four numbers | yes, four decimal numbers | 4-number quaternion | Phase 7D local candidate | Absolute route implemented behind `confirm:videoGeometry:v3:`; runtime validation still required before closure | yes |
| `rotate/x` | Video/Camera/Text dictionary section | `/cue/{cue_number}/rotate/x {number}` and `/live` variant | no stable scalar baseline; action-style relative change | yes, relative add to quaternion | decimal number | blocked | Incremental action, not absolute property; rollback is not safely derived from inverse increments | yes |
| `rotate/y` | Video/Camera/Text dictionary section | `/cue/{cue_number}/rotate/y {number}` and `/live` variant | no stable scalar baseline; action-style relative change | yes, relative add to quaternion | decimal number | blocked | Incremental action, not absolute property; rollback is not safely derived from inverse increments | yes |
| `rotate/z` | Video/Camera/Text dictionary section | `/cue/{cue_number}/rotate/z {number}` and `/live` variant | no stable scalar baseline; action-style relative change | yes, relative add to quaternion | decimal number | blocked | Incremental action, not absolute property; rollback is not safely derived from inverse increments | yes |
| `resetRotation` | Video/Camera/Text dictionary section | `/cue/{cue_number}/resetRotation` | no scalar readback on the action itself | action only | none | blocked | Destructive action/button shape; reversible only through separate quaternion baseline/readback proof | yes |
| shutters | none found as direct cue OSC routes | none found | no | no | unknown | blocked | No direct QLab 5 cue OSC route found in local dictionary; shutter appears as Video FX domain, not a direct geometry property | yes, if implemented through Video FX later |

## Decision

Option B remains for all Phase 7C routes except `quaternion`, which Phase 7D
promotes to an ultra-limited local real-write candidate.

Existing tokens stay scoped:

- `confirm:videoGeometry:v1:` authorizes only `fillStage` and `fillStyle`.
- `confirm:videoGeometry:v2:` authorizes only `layer`.
- `confirm:videoGeometry:v3:` authorizes only `quaternion`.

## Safety Boundary

Phase 7C itself does not add real writes. Phase 7D separately implements the
absolute `quaternion` candidate because it can satisfy these local gates before
runtime validation:

- exact cue UUID only
- saved mode only
- one cue
- one property
- healthy inactive cue
- fresh baseline exists
- validated value type
- known setter path
- fresh readback confirms result
- rollback to baseline is possible
- no raw OSC
- no `/live`
- no playback/show-control

Hard blocked:

- `/live`
- batch and multi-property
- stage/region/surface
- warping/control points
- video/camera patches
- `fileTarget`
- raw OSC
- playback, GO, start, stop, audition, panic

## Tests

Local tests cover:

- Video/Camera/Text rejection for `rotation`
- Video/Camera/Text `quaternion` moved to Phase 7D token-gated tests
- Video/Camera/Text rejection for `rotate/x`, `rotate/y` live, and related rotation family routes
- Video/Camera/Text rejection for `resetRotation`
- Video/Camera/Text rejection for `shutterTop`, `shutterBottom`, `shutterLeft`, and `shutterRight`
- no confirm token emitted for still-blocked Phase 7C routes
- no setter/request sent before rejection

Required checks:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "rotation or shutter or geometry or video"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```
