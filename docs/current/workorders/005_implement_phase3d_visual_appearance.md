# Video Phase 3D — Visual Appearance Bundle

Status: runtime validated + closed.

## Support matrix

| Property | Cue types | OSC setter/readback | Value | Decision |
|---|---|---|---|---|
| `blendMode` | Video, Camera, Text | `/cue/{cue_number}/blendMode` | QLab full-name blend mode string | implement |
| `preserveAspectRatio` | Video, Camera, Text | `/cue/{cue_number}/preserveAspectRatio` | boolean | implement |
| `rotation` | none in this bundle | scalar `/rotation` is documented under Fade cues and depends on single-axis mode | number | skip |
| `shutterTop` | none | no QLab 5 OSC dictionary entry | unknown | skip |
| `shutterBottom` | none | no QLab 5 OSC dictionary entry | unknown | skip |
| `shutterLeft` | none | no QLab 5 OSC dictionary entry | unknown | skip |
| `shutterRight` | none | no QLab 5 OSC dictionary entry | unknown | skip |
| `doOpacity` | Fade only | `/cue/{cue_number}/doOpacity` | boolean | skip; wrong cue family |

QLab documents Video cue messages as also working with most Camera and Text
cues. Both implemented properties already have matching read keys and
validators in the MCP Video-family profiles.

## Scope

Token-gated saved writes for `Video`, `Camera`, and `Text`:

- `blendMode`
- `preserveAspectRatio`

Token family: `confirm:videoAppearance:v1:`.

`blendMode` belongs to QLab's Video FX tab, but it is not a Video FX parameter
write in MCP. OSC writes the full blend mode name as a string, for example
`Screen` or `Source Atop Compositing`; it is not a numeric enum. The registry
canonicalizes existing case-insensitive full-name input to QLab's official
spelling and rejects unknown names, partial names, numbers, booleans, lists,
dicts, and nulls.

## Gate

- one cue and one property
- UUID cue reference
- exact workspace, cue, type, profile, property, path, value, and risk binding
- saved mode only
- validated enum/boolean request
- healthy, inactive cue
- fresh baseline and canonical baseline hash
- exactly one setter
- fresh exact readback
- new dry-run/token for rollback
- no mutating retry after uncertain result

Setter timeout plus matching readback is confirmed success with warning
`setter_timeout_but_readback_matched`.

## Still blocked

Playback, `/live`, batch and multi-property writes, scalar/quaternion rotation,
shutters, Fade `doOpacity`, stage/surface/route writes, `fileTarget`, Video FX,
camera/video-input patches, text/font writes, raw OSC, and Workspace Video
writes.

## Runtime validation

Validated in the test workspace with one healthy `Video`, `Camera`, and `Text`
cue:

- 6/6 real writes passed: `blendMode` and `preserveAspectRatio` on all three cue
  types.
- 6/6 rollbacks passed using a fresh dry-run and new
  `confirm:videoAppearance:v1:` token.
- 22/22 rejection probes passed before mutation with no executed operation.
- every accepted write used exactly one saved, UUID-qualified setter;
  `/live` was never used.
- setter timeouts with matching fresh readback returned `status="updated"` and
  warning `setter_timeout_but_readback_matched`; no mutating retry occurred.
- final baselines were intact, unrelated fields were unchanged, and running,
  paused, and auditioning counts were 0/0/0.
- no playback, GO, Dashboard, raw OSC, Workspace Video, Video FX, `fileTarget`,
  camera/video-input patch, stage, rotation, geometry, opacity, text, or font
  writes were used.

## Next candidate phase

Phase 3E — Text Basics, for later design and implementation only:

- Text cues only
- `text`
- `fontSize`
- `alignment`
- color only if clearly supported by the OSC dictionary and exact readback
