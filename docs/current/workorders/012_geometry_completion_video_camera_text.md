# Workorder 012 - Geometry Completion for Video/Camera/Text

Status: runtime validated and closed.

## Scope

Cue types:

- `Video`
- `Camera`
- `Text`

Real-write candidates implemented:

- `fillStage`
- `fillStyle`

Both candidates are saved-mode only, exact cue UUID only, one cue only, one
property only, and require a fresh `confirm:videoGeometry:v1:` token generated
from dry-run baseline/readback.

## Contract

Dry-run emits a plan and token only when the current baseline is readable and
valid:

- `fillStage`: boolean baseline and boolean requested value
- `fillStyle`: integer `0`, `1`, or `2` baseline and requested value

Real write must validate:

- fresh token family `confirm:videoGeometry:v1:`
- matching workspace, cue UUID, cue type, profile, property, path, mode,
  baseline hash, and requested value
- saved mode
- exact UUID cue ref
- no batch
- no multi-property update
- no `/live`

Setter timeout is success only when fresh readback matches the requested value;
the result carries `setter_timeout_but_readback_matched`. The mutating setter is
not retried. Rollback requires a new dry-run token from the changed baseline.

## Blocked

Still blocked:

- `rotation`
- `quaternion`
- `resetRotation`
- shutters
- stage, route, surface, region, warping, and control points
- camera/video patches
- Workspace Video
- `fileTarget`
- `/live`
- batch and multi-property Video-family real writes

`rotation`, `quaternion`, `resetRotation`, and shutters need separate visual
runtime proof before any real-write path.

## Classification

Editable:

- `fillStage`
- `fillStyle`

Dry-run only:

- all other existing Video-family planned visual routes already kept behind
  registry gates

Read-only:

- current cue health/inactive state
- current `fillStage` and `fillStyle` baselines
- stage/route/surface/region/warping/control-point state until a dedicated
  phase defines write safety

Blocked:

- `rotation`, `quaternion`, `resetRotation`, and shutters
- stage/route/surface/region, warping, control points, patches, `fileTarget`,
  `/live`, batch, multi-property, raw OSC, and playback

## Tests

Local tests cover all three cue profiles and both candidates:

- dry-run token payload and no setter
- real write single setter plus readback
- token binding and structure rejections
- invalid baseline rejection before setter
- timeout-with-readback success
- rollback via fresh token
- blocked rotation/reset/shutter families before setter

Required local checks:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "geometry or video"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```

## Runtime

Runtime validation passed on `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`) with one healthy inactive cue per
type:

- `Video` cue `Fill stage` (`BF24AB14-43D2-43BD-BBE7-1BC87DDB5107`)
- `Camera` cue `Camare1` (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`)
- `Text` cue `Text1` (`193FB551-7985-4381-9C2D-CF4218C03FB9`)

Happy-path proof:

- `Video` `fillStage`: `true -> false -> true`
- `Video` `fillStyle`: `0 -> 1 -> 0`
- `Camera` `fillStage`: `true -> false -> true`
- `Camera` `fillStyle`: `0 -> 1 -> 0`
- `Text` `fillStage`: `false -> true -> false`
- `Text` `fillStyle`: `0 -> 1 -> 0`

Each property used baseline read, dry-run with `confirm:videoGeometry:v1:`,
real write, fresh readback, fresh-token rollback, and final readback. QLab
setter timeout was accepted only when fresh readback matched, with
`setter_timeout_but_readback_matched`; no mutating setter was retried.

Small rejection probes passed:

- cue-number real write rejected before setter
- `/live` operation rejected before setter
- multi-property real write rejected before setter
- `rotation` dry-run rejected before OSC
- `shutterTop` dry-run rejected before OSC

Final readback restored all three targets to baseline. Final workspace status
had running and paused counts `0/0`; no playback, raw OSC, `/live` write, save,
commit, or unrelated mutation was used.
