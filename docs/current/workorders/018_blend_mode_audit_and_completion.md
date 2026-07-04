# Blend Mode Audit and Completion

Status: audited; Phase 3D hardened to exact official strings only.

## Finding

`blendMode` is not a numeric enum in OSC. QLab exposes it as:

`/cue/{cue_number}/blendMode {string}`

The string is the full blend mode name from QLab's Parameter Reference. The
current MCP implementation already routes this through the Phase 3D visual
appearance gate for `Video`, `Camera`, and `Text` cues using:

`confirm:videoAppearance:v1:`

No new token family was added.

## Sources

- Official QLab 5 OSC Dictionary, `/cue/{cue_number}/blendMode {string}`:
  read returns the current blend mode; write sets it to the blend mode name
  string from the Parameter Reference.
  <https://qlab.app/docs/v5/scripting/osc-dictionary-v5/#cuecue_numberblendmode-string>
- Official QLab 5 Parameter Reference, `Video Blend Modes`: blend modes are
  scriptable using their full names as strings.
  <https://qlab.app/docs/v5/scripting/parameter-reference/#video-blend-modes>
- Official QLab 5 Video Cues manual, `The Video FX Tab`: the tab sets blend mode
  and live video effects.
  <https://qlab.app/docs/v5/video/video-cues/#the-video-fx-tab>
- Local OSC dictionary:
  `docs/references/qlab_osc_dictionary.md`
- QClass 5.5 Day 2, `Video blend modes`: blend mode controls how a higher-layer
  video signal composites with lower-layer signals; guidance is visual and
  experimental.
  `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`

## Supported Values

The registry accepts only these exact QLab full-name blend modes:

- `Normal`
- `Darken`
- `Multiply`
- `Color Burn`
- `Linear Burn`
- `Lighten`
- `Screen`
- `Color Dodge`
- `Linear Dodge`
- `Overlay`
- `Soft Light`
- `Hard Light`
- `Pin Light`
- `Difference`
- `Exclusion`
- `Subtract`
- `Divide`
- `Hue`
- `Saturation`
- `Color`
- `Luminosity`
- `Addition Compositing`
- `Maximum Compositing`
- `Source Atop Compositing`

Numbers, booleans, nulls, arrays, dicts, empty strings, partial names,
lowercase aliases, leading/trailing spaces, and unknown strings are rejected
before planning or mutation. The MCP no longer canonicalizes values such as
`"screen"` or `" Screen "` to `Screen`.

## Current Safety Contract

- cue types: `Video`, `Camera`, `Text`
- saved mode only
- exact cue UUID only for real writes
- one cue
- one property
- healthy inactive cue
- fresh readable baseline
- fresh dry-run token
- token binds workspace, cue UUID, cue type, profile, property, path, baseline,
  requested value, risk tier, and capability gate
- exactly one `/blendMode` setter
- fresh readback must match requested value
- rollback requires a new dry-run and fresh `confirm:videoAppearance:v1:` token
- setter timeout is accepted only when fresh readback matched
- no `/live`, batch, multi-property, cue name/number real write, raw OSC,
  playback/show-control, or workspace save

## Token Boundaries

`blendMode` stays in `confirm:videoAppearance:v1:` with
`preserveAspectRatio`.

It does not use:

- `confirm:videoFxScalar:v1:`
- `confirm:videoFxScalar:v2:`
- `confirm:videoGeometry:v1:`
- `confirm:videoGeometry:v2:`
- `confirm:videoGeometry:v3:`
- `confirm:videoGeometry:v4:`
- `confirm:videoGeometryReset:v1:`

Those token families cannot authorize `blendMode`, and the appearance token
cannot authorize Video FX scalar or Geometry writes.

## Runtime Status

Phase 3D runtime validation is already closed for `blendMode` and
`preserveAspectRatio` on one healthy inactive `Video`, `Camera`, and `Text` cue.
The validation covered real writes, fresh-token rollback, rejection probes,
setter-timeout/readback behavior, and final baseline restoration.

No new runtime validation is required for this audit unless the registry
validator or token contract changes.

## Verification Added

This audit adds focused tests that:

- assert the supported blend mode list matches the official full-name list
- reject non-string and unknown values
- reject old case-insensitive/trimmed canonicalization behavior
- prove Video FX scalar and Geometry tokens cannot authorize `blendMode`
- prove `confirm:videoAppearance:v1:` cannot authorize Geometry writes

Run:

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k "blendMode or blend or video"
```
