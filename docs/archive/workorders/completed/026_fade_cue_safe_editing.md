# 026 — Fade cue safe editing

Status: runtime validated and closed for exact Audio-targeting-Mic subset.

## Implemented gates

- `confirm:fadeBasic:v1:` — shared Basics.
- `confirm:fadeTarget:v1:` — exact direct cue `cueTargetID`.
- `confirm:fadeGeometry:v1:` — absolute/relative 1D opacity, X/Y translation,
  X/Y scale, and single-axis X/Y/Z rotation; absolute rate and absolute
  quaternion rotation.
- `confirm:fadeAudio:v1:` — absolute/relative Levels mode, exact `doLevel`
  cells, inherited `level` crosspoints, output `sliderLevel`, input channel
  labels, and crosspoint gangs.
- `confirm:fadeBehavior:v1:` — `stopTargetWhenDone`.
- `confirm:fadeSetup:v1:` / `confirm:fadeRecovery:v1:` — narrow broken-Fade
  target/first-parameter setup and exact inverse recovery.

All gates require exact workspace and Fade UUIDs, one cue, one saved property,
`targetMode=0`, `fadeType=1`, an inactive source, a compatible healthy inactive
non-self target, dry-run first, a fresh target/source-bound token, one setter,
and exact readback.

## Phase 0 closure

- Generic, fake, stale, and wrong-family tokens cannot authorize Fade writes.
- Unpromoted Fade properties emit no setter.
- `fadeType` validates `1 = 1D Curve`, `2 = 2D Path`.
- Deprecated `mode` maps to `levelsMode`.
- Video translation/scale detectors are profile-bound and cannot intercept
  `fade_basic` operations.

## Audio constraints

- Targets: Audio, Mic, Video, or Camera with proven readable audio channels.
- Source and target `levels` matrices and source `doLevel` matrix must be fresh.
- Crosspoint indexes must exist in both source and target matrices.
- `sliderLevel` is bound to the equivalent row-0 output and requires its
  `doLevel` cell active.
- `inputChannelName` and `gang` use exact dynamic-route baseline/readback;
  output-name aliases remain blocked in favor of integer indexes.
- Finite dB values are accepted in absolute or relative mode.
- Exact `-inf` silence is accepted only in absolute mode. Its deterministic
  readback is the fresh workspace Audio `minVolume`, which is included in the
  token and verification.
- Disabling the last active Fade parameter is rejected.

## Setup/recovery boundary

Setup is limited to an empty target, a target proven unresolved/incompatible,
the first exact activation flag/crosspoint, or disabling one active source
`doLevel` cell proven absent from the fresh target matrix. A valid target is
not replaceable just because another missing parameter leaves the Fade broken.
It does not bypass health for Basics, modes, destination values, behavior, or
other broken-cue edits. Recovery can restore only the baseline bound to the
preceding setup token and the same target UUID/type/matrix fingerprint.

## Planned-only boundary

- `targetMode`, `fadeType`
- relative quaternion/3D rotation
- relative `rate` value writes because the operator is undocumented
- undocumented Z translation/scale routes
- 2D Path and path points/merge settings
- Curve-tab types, intensity, lock/mirror, and control points
- Objects, Audio FX, Video FX
- patch, map, temporary, name, and number targets
- new Group or Cue List fanout targets; their children cannot be validated by
  one scalar target fingerprint
- ambiguous or unsupported audio matrix routes

## Local acceptance

- Focused Fade positive/negative tests pass.
- Full write-mode, registry-coverage, and FastMCP contract tests pass.
- `git diff --check` and `git diff --cached --check` pass.

## Runtime acceptance

Validate every promoted family one property at a time with fresh readback and
immediate rollback. Then configure `pruebas-fade` without executing it:

1. Video: opacity `1`, post-wait `0`, auto-continue.
2. Fade 1: exact Video target, absolute 1D opacity to `0`, duration `10`,
   post-wait `0`, auto-continue.
3. Fade 2: same Video target, absolute active audio crosspoint(s) to `-inf`,
   duration `12`, `stopTargetWhenDone=true`, do-not-continue.

Final requirements: all cues healthy/inactive, running/paused/auditioning
`0/0/0`, no playback, no `/live`, no raw OSC, no save, no commit.

Runtime status: validated for exact Mic targeting, absolute/relative Levels,
`doLevel`, `level`, `sliderLevel`, semantic `-inf` mapped to workspace minimum,
`stopTargetWhenDone`, fresh readback, and `0.001 dB` tolerance. Source and
target were healthy/inactive; final activity was `0/0/0`. No validation claimed
for `inputChannelName`, gangs, visual Geometry, setup/recovery, or special
reset actions. Curve internals, Path, Objects, FX, patch/map/fanout targets
remain blocked or out of scope.
