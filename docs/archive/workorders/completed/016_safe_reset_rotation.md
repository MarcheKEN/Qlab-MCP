# Workorder 016 - Safe Reset Rotation Action

Status: runtime validated and closed for `Video`, `Camera`, and `Text`.

## Scope

Implemented real-write candidate:

- cue types: `Video`, `Camera`, `Text`
- action: `resetRotation`
- OSC path: `/cue/{cue_number}/resetRotation`
- MCP property form: saved `resetRotation: true`
- token: `confirm:videoGeometryReset:v1:`

This is an action, not a scalar property. MCP does not substitute
`quaternion = [1, 0, 0, 0]` for QLab's own Reset Rotation action.

## Official Route Finding

Source: `docs/references/qlab_osc_dictionary.md`.

- `/cue/{cue_number}/quaternion {a} {b} {c} {d}` reads a four-number
  quaternion with no args and writes a quaternion with four args.
- `/cue/{cue_number}/resetRotation` resets rotation and takes no value.
- `/cue/{cue_number}/rotate/x|y|z {number}` and `/live` variants are relative
  action routes that add to the current quaternion rotation.

## Token Contract

`confirm:videoGeometryReset:v1:` authorizes only saved `resetRotation`.

Existing token scope remains unchanged:

- `confirm:videoGeometry:v1:` authorizes only `fillStage` and `fillStyle`.
- `confirm:videoGeometry:v2:` authorizes only `layer`.
- `confirm:videoGeometry:v3:` authorizes only `quaternion`.
- `confirm:videoGeometryReset:v1:` does not authorize `quaternion`,
  `fillStage`, `fillStyle`, `layer`, or any other property.

The reset token binds:

- workspace UUID
- cue UUID and cue type
- profile
- saved mode
- exact action/path `resetRotation`
- baseline quaternion
- baseline hash
- token family/version
- operation kind and risk gate

## Safety Gates

Real write requires:

- exact cue UUID only
- saved mode only
- one cue
- one action/property
- matching `Video`, `Camera`, or `Text` cue type/profile
- healthy cue without warnings
- inactive cue
- fresh readable baseline quaternion before action
- fresh reset token generated from current baseline
- one action call to `/resetRotation`
- fresh quaternion readback after action
- rollback by writing the original baseline quaternion with a fresh
  `confirm:videoGeometry:v3:` token
- no identity-quaternion reset shortcut
- no mutating retry

Action timeout may be accepted only when fresh quaternion readback succeeds,
producing `setter_timeout_but_readback_matched`.

## Still Blocked

- `rotation`
- `rotationType`
- `rotate/x`
- `rotate/y`
- `rotate/z`
- `/live`
- shutter/shutters
- stage/region/surface
- warping/control points
- video/camera patches
- `fileTarget`
- raw OSC
- playback/show-control
- batch and multi-property real writes

## Runtime Validation

Runtime validation passed on `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`):

- Text `<TEST_TEXT_CUE_NAME>` (`<TEST_TEXT_CUE_UUID>`) reset from
  `[0.9659258127212524, 0, 0, 0.258819043636322]` to `[0, 0, 0, 1]`.
- Video `<TEST_VIDEO_CUE_NAME>` (`<TEST_VIDEO_CUE_UUID>`) reset from
  `[0.9659258127212524, 0, 0, 0.258819043636322]` to `[0, 0, 0, 1]`.
- Camera `<TEST_CAMERA_CUE_NAME>` (`<TEST_CAMERA_CUE_UUID>`) reset from
  `[0.9659258127212524, 0, 0, 0.258819043636322]` to `[0, 0, 0, 1]`.

Each dry-run emitted `confirm:videoGeometryReset:v1:`. Each real write executed
exactly one `/resetRotation` action, did not use quaternion identity as a reset
substitute, used exact cue UUIDs, stayed saved-mode, and left the cue reset for
visual inspection. Workspace final running/paused/auditioning was `0/0/0`.
QLab action timeouts were accepted only when fresh quaternion readback matched
with `setter_timeout_but_readback_matched`.

## Local Tests

Required checks:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "phase7e or phase7d or phase7_geometry"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```
