# Video Phase 3C — Visual Scalar Bundle

Status: runtime validated and closed on 2026-06-24.

## Scope

Token-gated saved writes for `Video`, `Camera`, and `Text`:

- `scale/x`, `scale/y`
- `anchor/x`, `anchor/y`
- `cropTop`, `cropBottom`, `cropLeft`, `cropRight`

The crop names are QLab's canonical OSC paths for the requested crop
top/bottom/left/right scalars.

Token family: `confirm:videoScalar:v1:`.

## Gate

- one cue and one property
- UUID cue reference
- exact cue type/profile/property/value binding
- saved mode only
- finite numeric value
- healthy, inactive cue
- fresh baseline hash
- exactly one setter
- fresh readback
- new dry-run/token for rollback
- no mutating retry after an uncertain result

Setter timeout plus matching readback is confirmed success with warning
`setter_timeout_but_readback_matched`.

## Still blocked

Playback, `/live`, batch and multi-property writes, rotation, stage,
`fileTarget`, Video FX, camera/video-input patch, text/font formatting,
`blendMode`, `clockType`, raw OSC, and Workspace Video writes.

## Runtime validation result

- `Video`: 8/8 properties passed.
- `Camera`: 8/8 properties passed.
- `Text`: 8/8 properties passed.
- Every real write used one saved setter and a reviewed
  `confirm:videoScalar:v1:` token.
- Fresh readback matched each requested value.
- Every rollback used a new dry-run/token and restored baseline.
- Setter timeouts with matching readback returned confirmed success with
  `setter_timeout_but_readback_matched`.
- Rejection probes sent no setter.
- Final running, paused, and auditioning counts were zero.
