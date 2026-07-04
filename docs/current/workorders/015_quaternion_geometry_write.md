# Workorder 015 - Quaternion Geometry Real Write

Status: runtime validated and closed for `Video`, `Camera`, and `Text`.

## Scope

Implemented real-write candidate:

- cue types: `Video`, `Camera`, `Text`
- property: `quaternion`
- OSC path: `/cue/{cue_number}/quaternion {a} {b} {c} {d}`
- MCP path: saved `quaternion`
- token: `confirm:videoGeometry:v3:`
- value: array of exactly four finite non-boolean numbers

QLab UI shows Rotation X/Y/Z controls, but MCP implements the absolute OSC
rotation route, `quaternion`, because it has direct readback and direct setter
semantics in QLab's OSC Dictionary.

## Official Route Finding

Source: `docs/references/qlab_osc_dictionary.md`.

- `/cue/{cue_number}/quaternion {a} {b} {c} {d}` reads an array of four
  numbers when no args are supplied and writes four decimal numbers when args
  are supplied.
- `/cue/{cue_number}/rotate/x|y|z {number}` and `/live` variants are relative
  action routes that add to current quaternion rotation.
- `/cue/{cue_number}/resetRotation` is a separate action. Phase 7E implements
  it behind `confirm:videoGeometryReset:v1:` with quaternion backup/readback/
  rollback. Identity quaternion is not treated as a substitute for QLab's reset
  action.
- `/cue/{cue_number}/rotation` and `/cue/{cue_number}/rotationType` belong to
  Fade/single-axis semantics, not the safe Video/Camera/Text geometry path.
- shutter controls are not Geometry OSC routes. Geometry uses crop; Shutter is
  a Video FX effect family.

## Token Contract

`confirm:videoGeometry:v3:` authorizes only `quaternion`.

Existing token scope remains unchanged:

- `confirm:videoGeometry:v1:` authorizes only `fillStage` and `fillStyle`.
- `confirm:videoGeometry:v2:` authorizes only `layer`.
- `confirm:videoGeometry:v3:` does not authorize `fillStage`, `fillStyle`,
  `layer`, or any other property.

The v3 payload binds:

- workspace UUID
- cue UUID and cue type
- profile
- saved mode
- exact property/path `quaternion`
- baseline quaternion
- requested quaternion
- baseline hash
- token version `3`
- operation kind and risk gate

## Safety Gates

Real write requires:

- exact cue UUID only
- saved mode only
- one cue
- one property
- matching `Video`, `Camera`, or `Text` cue type/profile
- healthy cue without warnings
- inactive cue
- fresh readable baseline quaternion
- valid requested quaternion
- fresh token generated from current baseline
- one setter to `/quaternion`
- fresh readback match
- fresh-token rollback to baseline
- no mutating retry

Setter timeout may be accepted only when fresh readback matches, producing
`setter_timeout_but_readback_matched`.

## Still Blocked

- `rotation`
- `rotationType`
- `rotate/x`
- `rotate/y`
- `rotate/z`
- `resetRotation` outside the dedicated Phase 7E reset action flow
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

Runtime validation passed on `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`):

- Text `Probar quaternion` (`796D1FB7-42B7-4B52-90D0-9379EC2BB951`) was reset
  to identity and then wrote `[0.965925826, 0, 0, 0.258819045]`; fresh readback
  matched within float tolerance and the cue was left rotated for inspection.
- Video `v11 dorado.png` (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`) wrote
  `[0.965925826, 0, 0, 0.258819045]`, fresh readback matched
  `[0.9659258127212524, 0, 0, 0.258819043636322]`, then Phase 7E reset left it
  `[0, 0, 0, 1]`.
- Camera `v6 Camare1` (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`) wrote
  `[0.965925826, 0, 0, 0.258819045]`, fresh readback matched
  `[0.9659258127212524, 0, 0, 0.258819043636322]`, then Phase 7E reset left it
  `[0, 0, 0, 1]`.

All real writes used exact cue UUIDs, saved mode, fresh v3 tokens, one setter,
fresh readback, and no `/live`, raw OSC, playback, save, or commit. QLab setter
timeouts were accepted only when fresh readback matched
`setter_timeout_but_readback_matched`.

## Local Tests

Required checks:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "quaternion or rotation or geometry or video"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```
