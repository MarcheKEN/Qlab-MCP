# Video Phase 8B - Video Embedded Audio Time & Loops

Status: local implementation added; runtime validation pending MCP restart.

## Sources

- `docs/references/qlab_osc_dictionary.md`
- `docs/current/workorders/020_video_embedded_audio_research.md`
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`
- `src/qlab_mcp/write/registry.py`
- `src/qlab_mcp/write/operations.py`
- `src/qlab_mcp/cues/profiles.py`
- `tests/test_write_mode.py`

## Research Summary

QLab documents Audio cue messages as mostly applying to Mic, Video, and Camera
cues. It also documents that Video cues respond to Audio cue messages, while
some audio messages have no effect when the target video has no audio track.
QClass Day 2 describes Video cues with soundtrack as having a built-in Audio cue
surface: audio format, output patch, clock, Levels, Objects, Trim, and Audio FX.

Phase 8B therefore implements only scalar saved-state Time & Loops properties
with stable readback and rollback. It does not trigger playback and does not use
GO, start, stop, audition, raw OSC, `/live`, or workspace save.

## UI to OSC Mapping

| UI control | MCP property | OSC path | Type | Read/write | Video scope | Phase 8B |
|---|---|---|---|---|---|---|
| Start Time | `startTime` | `/cue/{cue_number}/startTime {number}` | seconds, finite `>= 0` | read/write | Video with embedded audio evidence | implemented |
| End Time | `endTime` | `/cue/{cue_number}/endTime {number}` | seconds, finite `>= 0` | read/write | Video with embedded audio evidence | implemented |
| Play count | `playCount` | `/cue/{cue_number}/playCount {number}` | positive integer `>= 1` | read/write | Video with embedded audio evidence | implemented |
| Infinite Loop | `infiniteLoop` | `/cue/{cue_number}/infiniteLoop {boolean}` | boolean | read/write | Video with embedded audio evidence | implemented |
| Rate | `rate` | `/cue/{cue_number}/rate {number}` | finite number `0.03..33.0` | read/write; `/live` exists | Video with embedded audio evidence | implemented, saved only |
| Preserve Pitch | `preservePitch` | `/cue/{cue_number}/preservePitch {boolean}` | boolean | read/write | Video with embedded audio evidence | implemented |
| Hold at End | `holdLastFrame` | `/cue/{cue_number}/holdLastFrame {boolean}` | boolean | read/write | Video-only visual playback state | implemented as official property name |
| Integrated Fade | `doFade` | `/cue/{cue_number}/doFade {boolean}` | boolean | read/write | Shared Audio route | blocked |
| Linear Curve / fade curve | no isolated scalar confirmed | tied to integrated fade curve model | unclear | unclear | Shared Audio/Fade behavior | blocked |
| Slices / loops / vamps / devamps | `sliceMarker/*`, `addSliceMarker`, `deleteSliceMarker*` | indexed routes/actions | mixed | read/write/action | Shared Audio route | blocked |

## Implemented Properties

Phase 8B adds `video_basic` gated candidates:

- `startTime`
- `endTime`
- `playCount`
- `infiniteLoop`
- `rate`
- `preservePitch`
- `holdLastFrame`

Token family:

- `confirm:videoAudioTime:v1:`

Scope:

- `Video` cue only
- `video_basic` only
- saved mode only
- exact cue UUID only
- one cue
- one property
- healthy inactive cue
- fresh baseline readback
- fresh post-write readback
- fresh-token rollback
- no batch, multi-property, cue number/name, `/live`, raw OSC, playback, show-control, or save

## Validators

- `startTime`: finite number `>= 0`
- `endTime`: finite number `>= 0`
- `playCount`: positive integer `>= 1`
- `infiniteLoop`: boolean only
- `rate`: finite number `0.03..33.0`
- `preservePitch`: boolean only
- `holdLastFrame`: boolean only

Strings, booleans for numeric fields, numbers for boolean fields, `null`,
lists, dictionaries, `NaN`, and infinity are rejected before any setter.
For `preservePitch`, user input remains strict boolean (`true`/`false` only),
but QLab readback may return numeric `0` or `1`; MCP normalizes those internally
to `false` and `true` for baseline, token, verification, and rollback
comparison. Numeric readback values other than `0` or `1` are rejected.

## Embedded Audio Evidence

For the audio timing routes (`startTime`, `endTime`, `playCount`,
`infiniteLoop`, `rate`, `preservePitch`), dry-run and real write require at
least one readable embedded-audio signal:

- non-empty `audioTrackFormats`
- `numChannelsIn > 0`
- non-empty `levels`

`holdLastFrame` is the official Video Hold at End route. It is included in this
UI phase but does not prove embedded audio by itself.

## Rollback Strategy

Each supported property is scalar or boolean. Rollback is a second dry-run from
current value back to the original baseline, using a fresh
`confirm:videoAudioTime:v1:` token and exact fresh readback.

Setter timeout, or a QLab setter error reply, remains acceptable only when
post-write fresh readback matches the requested value. The result stays
warning-visible (`setter_timeout_but_readback_matched` or
`setter_error_but_readback_matched`). No mutating retry is allowed, and errors
without matching readback remain failures.

## Blocked / Future Only

- `doFade`: integrated fade changes playback envelope behavior and needs its
  own curve/baseline proof.
- Linear Curve: no isolated safe OSC scalar was confirmed for the Time & Loops
  checkbox/curve behavior.
- `lockFadeToCue`: fade coupling affects cue playback behavior.
- `sliceMarker/*`, `addSliceMarker`, `deleteSliceMarker*`: slice editing is
  multi-route/indexed and can change loop/vamp/devamp semantics.
- Levels matrix, `sliderLevel`, `level`, `gang`, `setDefaultLevels`,
  `setSilentLevels`, mute/solo, Objects, Audio FX, Trim, fileTarget, stage/patch
  definitions, `/live`, raw OSC, playback/show-control.

## Runtime Validation Plan

Use one healthy inactive Video cue with known embedded audio.

For each implemented property:

1. Confirm workspace readiness and running/paused/auditioning are `0/0/0`.
2. Read target cue fresh; prove `Video`, healthy, inactive, exact UUID.
3. Prove embedded-audio evidence for audio timing routes.
4. Record baseline.
5. Dry-run one tiny safe change; require `confirm:videoAudioTime:v1:` and
   `executed_operations=[]`.
6. Real write with exact fresh token.
7. Fresh readback must match requested value.
8. Dry-run rollback to original baseline; require fresh v1 token.
9. Real rollback; fresh readback must match original baseline.

No raw OSC, playback, `/live`, save, batch, multi-property, or commit.
