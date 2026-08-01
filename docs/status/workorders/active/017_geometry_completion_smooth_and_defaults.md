# Workorder 017 - Geometry Completion: Smooth and Defaults

Status: status audit needed. This workorder records the local `smooth`
implementation; confirm current runtime validation status in
`docs/status/roadmap.md` before treating it as open or closed.

## Research Summary

Sources inspected:

- `docs/references/qlab_osc_dictionary.md`
- `docs/references/osc_queries.md`
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`
- workorders 013, 014, 015, and 016
- current write/read code and tests

Finding: QLab's Video/Camera/Text Geometry surface is mostly already covered by
closed token-gated routes. The only small safe missing direct Geometry property
was `smooth`. No official OSC reset action was found for crop, translation,
scale, anchor, or opacity. Only `resetRotation` has an official cue action.

## Geometry UI to OSC Mapping

| UI control | OSC path | Cue types | Value | Readback | Setter | Live | Status |
|---|---|---|---|---|---|---|---|
| Fill Stage / Custom | `/cue/{cue_number}/fillStage` | Video, Camera, Text | boolean | yes | yes | no documented live route | implemented Phase 7, `confirm:videoGeometry:v1:` |
| Fill Style Fit/Fill/Stretch | `/cue/{cue_number}/fillStyle` | Video, Camera, Text | `0`, `1`, `2` | yes | yes | no documented live route | implemented Phase 7, `confirm:videoGeometry:v1:` |
| Layer Bottom/1-999/Top | `/cue/{cue_number}/layer` | Video, Camera, Text | integer `0..1000` | yes | yes | no documented live route | implemented Phase 7B, `confirm:videoGeometry:v2:` |
| Crop | `/cue/{cue_number}/cropTop`, `cropBottom`, `cropLeft`, `cropRight`; aggregate `/crop {top} {bottom} {left} {right}` | Video, Camera, Text | number, pixels inward | yes | yes | yes | scalar edges implemented Phase 3C; aggregate stays dry-run only |
| Opacity | `/cue/{cue_number}/opacity` | Video, Camera, Text | number `0..1` | yes | yes | yes | implemented Phase 3A |
| Smooth | `/cue/{cue_number}/smooth` | Video, Camera, Text | boolean | yes | yes | no documented live route | implemented Phase 7F, `confirm:videoGeometry:v4:` |
| Translation | `/cue/{cue_number}/translation/x`, `/translation/y`; aggregate `/translation {x} {y}` | Video, Camera, Text | number | yes | yes | yes | axis writes implemented Phase 3B; aggregate stays dry-run only |
| Scale | `/cue/{cue_number}/scale/x`, `/scale/y`; aggregate `/scale {x} {y}` | Video, Camera, Text | number | yes | yes | yes | axis writes implemented Phase 3C; aggregate stays dry-run only |
| Scale lock | `/cue/{cue_number}/preserveAspectRatio` | Video, Camera, Text | boolean | yes | yes | no documented live route | implemented Phase 3D |
| Rotation | `/cue/{cue_number}/quaternion {a} {b} {c} {d}` | Video, Camera, Text | four finite numbers | yes | yes | no live variant for quaternion | implemented Phase 7D, `confirm:videoGeometry:v3:` |
| Reset Rotation | `/cue/{cue_number}/resetRotation` | Video, Camera, Text | action, no args | readback through quaternion | action | no | implemented Phase 7E, `confirm:videoGeometryReset:v1:` |
| Relative rotate | `/cue/{cue_number}/rotate/x`, `/rotate/y`, `/rotate/z` | Video, Camera, Text | number increment | no stable scalar baseline | action | yes | blocked |
| Single-axis rotation fields | `/cue/{cue_number}/rotation`, `/rotationType` | Fade geometry | number/enum | yes | yes | unclear/direct Video not safe | blocked for Video/Camera/Text |
| Anchor | `/cue/{cue_number}/anchor/x`, `/anchor/y`; aggregate `/anchor {x} {y}` | Video, Camera, Text | number | yes | yes | yes | axis writes implemented Phase 3C; aggregate stays dry-run only |
| Deprecated origin alias | `/cue/{cue_number}/origin...` | Video, Camera, Text | number | yes | yes | yes | blocked; use `anchor` |

## Already Implemented

- `opacity`: `confirm:videoOpacity:v1:`
- `translation/x`, `translation/y`: `confirm:videoTranslation:v1:`
- `scale/x`, `scale/y`, `anchor/x`, `anchor/y`, `cropTop`, `cropBottom`,
  `cropLeft`, `cropRight`: `confirm:videoScalar:v1:`
- `blendMode`, `preserveAspectRatio`: `confirm:videoAppearance:v1:`
- `fillStage`, `fillStyle`: `confirm:videoGeometry:v1:`
- `layer`: `confirm:videoGeometry:v2:`
- `quaternion`: `confirm:videoGeometry:v3:`
- `resetRotation`: `confirm:videoGeometryReset:v1:`

## Newly Implemented

`smooth` is now a saved-mode real-write candidate for `Video`, `Camera`, and
`Text`.

API shape:

```json
{"cue_ref":"<cue UUID>","profile":"video_basic","properties":{"smooth":true}}
```

Use `camera_basic` or `text_basic` for matching cue types.

Safety gates:

- exact cue UUID only
- one cue
- one property
- saved mode only
- healthy inactive cue
- fresh readable boolean baseline
- fresh dry-run token
- fresh post-write readback
- rollback by writing original boolean with a fresh v4 token
- no `/live`
- no batch or multi-property real write

## Blocked / Future

No official OSC reset action was found for:

- crop
- translation
- scale
- anchor
- opacity

Synthetic reset actions remain future-only:

- `resetCrop: true`
- `resetTranslation: true`
- `resetScale: true`
- `resetAnchor: true`
- `resetOpacity: true`

Reason: these would be MCP-defined multi-setter actions, not official QLab OSC
actions. They need a separate token family, per-field baseline/readback,
rollback proof, and runtime validation before mutation is safe.

Still blocked:

- `rotation`
- `rotationType`
- `rotate/x`, `rotate/y`, `rotate/z`
- `/live`
- shutter/window as Geometry
- stage/region/surface/warping/control points
- video/camera patches
- `fileTarget`
- raw OSC and playback/show-control

## Token Matrix

| Token | Scope |
|---|---|
| `confirm:videoGeometry:v1:` | `fillStage`, `fillStyle` only |
| `confirm:videoGeometry:v2:` | `layer` only |
| `confirm:videoGeometry:v3:` | `quaternion` only |
| `confirm:videoGeometry:v4:` | `smooth` only |
| `confirm:videoGeometryReset:v1:` | `resetRotation` action only |

Old tokens cannot authorize `smooth`. The v4 `smooth` token cannot authorize
older properties or `resetRotation`.

## Notes

- `smooth` is documented as `/cue/{cue_number}/smooth {boolean}`. QClass
  describes it as the Geometry tab checkbox that smooths jagged scaled video;
  it is on by default in the class discussion.
- `layer` mapping is confirmed by the OSC dictionary: `0` is Bottom, `1000` is
  Top, and `1..999` are normal numeric layers.
- Crop is Geometry. Shutter and Window are Video FX workflows, not Geometry
  writes for this phase.
- `preserveAspectRatio` maps to the scale ratio lock. Resetting scale must not
  silently modify it unless a future official source proves QLab does that.
- `anchor` controls the cue pivot/origin point for scale/rotation. Deprecated
  `origin` aliases stay blocked.
- `resetRotation` is the only official reset action implemented here. It must
  call `/resetRotation`; identity-quaternion writes are not substitutes.
- `/live` remains blocked for Video-family real writes because runtime rollback
  and baseline semantics are different from saved Inspector values.

## Runtime Validation Plan

After MCP restart, validate `smooth` on one healthy inactive `Video`, `Camera`,
and `Text` cue:

1. confirm workspace readiness and running/paused/auditioning `0/0/0`
2. read baseline `smooth`
3. dry-run `smooth: !baseline`, require `confirm:videoGeometry:v4:`
4. real write using exact token and cue UUID
5. fresh readback matches requested boolean
6. rollback with fresh v4 token to baseline
7. fresh readback matches baseline
8. reject fake/old tokens, cue number, `/live`, batch, and multi-property before
   setter

## Local Tests

Run:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "smooth or resetCrop or resetTranslation or resetScale or resetAnchor or resetOpacity or geometry or video"
.venv/bin/pytest -q tests/test_write_mode.py tests/test_qlab_reader.py tests/test_read_coverage.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
git diff --check
```
