# Video Embedded Audio Research

Status: research complete; superseded for implementation by
`docs/current/workorders/021_video_audio_time_loops.md`.

## Scope

This workorder maps QLab Video cues with embedded audio to OSC routes and the
current MCP write registry. It is intentionally research-first. No runtime code
or tests are changed here.

## Sources

- Local QLab OSC Dictionary:
  `docs/references/qlab_osc_dictionary.md`
- QClass 5.5 Day 1 audio sections:
  `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`
- QClass 5.5 Day 2 video sections:
  `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`
- Current registry and write gates:
  `src/qlab_mcp/write/registry.py`
  `src/qlab_mcp/write/operations.py`
- Current cue read profiles:
  `src/qlab_mcp/cues/profiles.py`
- Current tests:
  `tests/test_write_mode.py`

## Research Summary

QLab documents Audio cue messages as mostly also working with Mic, Video, and
Camera cues. It separately documents that Video cues respond to Audio cue
messages, although some Audio messages have no effect if the target video file
has no audio track.

QClass Day 2 confirms the UI model: a Video cue without soundtrack has no audio
I/O. A Video cue with at least one audio track exposes audio format selection,
audio output patch selection, clock choice, Levels, Objects, Trim, and Audio FX.
QClass describes such a cue as effectively a Video cue with a built-in Audio cue.

The safe MCP implication is narrow:

- Video cue audio playback timing routes are real OSC properties with stable
  readback and rollback shape.
- Audio level matrix, object audio, trim, and Audio FX are real/important, but
  high-risk and should remain future-only until runtime readback and rollback
  are deliberately scoped.
- `/live` variants must stay blocked.
- Video cues without audio tracks can accept some Audio cue messages but may
  have no effect, so runtime validation must use a Video cue whose target file
  actually has audio.

## UI to OSC Mapping

| QLab UI area | OSC family | Video cue applicability | Safe now? |
|---|---|---:|---:|
| I/O audio output patch | `audioOutputPatchID` | Video with embedded audio; also already Phase 8A | Already implemented |
| I/O audio track metadata | `audioTrackFormats`, `audioTrackID` | Video-specific usefulness | Read-only only |
| I/O clock choice | `clockType` | Video cue with audio can use `audio` or `video` | Runtime-probe only |
| Time & Loops | Audio cue timing routes | Video responds; meaningful with audio track | Safe candidate subset |
| Integrated fade | `doFade`, `lockFadeToCue` | Shared Audio route | Block for now |
| Levels | `levels`, `sliderLevel`, `level`, `gang`, `setDefaultLevels`, `setSilentLevels` | Shared Audio route | Block for now except possible future main slider |
| Objects | `objects`, `objectLevel`, `object/position`, `object/spread` | Shared Audio route | Block |
| Trim | UI final adjustment layer | QClass says un-remote-controllable/un-fadable | Block |
| Audio FX | Audio Unit effects | Available on Video with audio | Block |
| Hold at end | `holdLastFrame` | Video-specific, not audio | Already geometry catalog/gated elsewhere |

## Time and Loops Matrix

| Property | OSC path | Type | Read/write | Current MCP | Recommendation |
|---|---|---|---|---|---|
| `startTime` | `/cue/{cue_number}/startTime {number}` | non-negative number seconds | read/write | real-write only in `audio_basic` | Safe candidate for Video audio phase |
| `endTime` | `/cue/{cue_number}/endTime {number}` | non-negative number seconds | read/write | real-write only in `audio_basic` | Safe candidate for Video audio phase |
| `duration` / `tempDuration` | common cue paths | non-negative number | read/write when cue allows duration editing | common real-write | Already common behavior, not embedded-audio-specific |
| `playCount` | `/cue/{cue_number}/playCount {number}` | positive integer | read/write | real-write only in `audio_basic` | Safe candidate |
| `infiniteLoop` | `/cue/{cue_number}/infiniteLoop {boolean}` | boolean | read/write | real-write only in `audio_basic` | Safe candidate |
| `rate` | `/cue/{cue_number}/rate {number}` and `/live` variant | 0.03..33.0 | read/write | real-write only in `audio_basic` | Safe candidate, saved only |
| `preservePitch` | `/cue/{cue_number}/preservePitch {boolean}` | boolean | read/write | real-write only in `audio_basic` | Safe candidate |
| `doFade` | `/cue/{cue_number}/doFade {boolean}` | boolean | read/write | planned-only | Block initially |
| `lockFadeToCue` | `/cue/{cue_number}/lockFadeToCue {boolean}` | boolean | read/write | planned-only | Block initially |
| `sliceMarker/*` | `/sliceMarker`, `/addSliceMarker`, `/deleteSliceMarker*` | indexed time/play count actions | read/write/action | planned-only | Block |
| `clockType` | `/cue/{cue_number}/clockType {audio|video}` | enum string | read/write | Video planned-only | Runtime-probe only |
| `holdLastFrame` | `/cue/{cue_number}/holdLastFrame {boolean}` | boolean | read/write | Video planned-only/gated elsewhere | Not part of audio phase |

Safe first phase should not include slices, integrated fade, or clock changes.
Those can affect playback semantics more deeply and need their own targeted
validation.

## Levels Matrix

| Route | OSC path | Type | Readback | Current MCP | Recommendation |
|---|---|---|---|---|---|
| all levels | `/cue/{cue_number}/levels` | array-of-arrays | read-only | read key allowlisted | Read-only baseline source |
| slider levels | `/cue/{cue_number}/sliderLevels` | array row 0 | read-only | allowlisted/tests | Read-only baseline source |
| one slider | `/cue/{cue_number}/sliderLevel/{channel} {decibel}` | number or `-inf`; channel 0..128 or output name; 0 = main | yes | planned-only | Future candidate: main slider only |
| one matrix crosspoint | `/cue/{cue_number}/level/{inChannel}/{outChannel} {decibel}` | number or `-inf`; rows 0..24, outputs 0..128/name | yes | planned-only | Block |
| gangs | `/cue/{cue_number}/gang/{inChannel}/{outChannel} {gang}` | string | yes | planned-only | Block |
| set defaults | `/cue/{cue_number}/setDefaultLevels` | action | indirect | planned-only | Block |
| set silent | `/cue/{cue_number}/setSilentLevels` | action | indirect | planned-only | Block |
| mute/solo | `/mute*`, `/solo*` | boolean/actions | partial | planned-only | Block |

`-inf` is documented for level and sliderLevel. Any string is coerced by QLab
to `-inf`, so the MCP must keep validating exactly number or literal `-inf`.

Main slider `sliderLevel/0` is the only plausible level write for a small future
phase. It still needs a dedicated token, exact `sliderLevels` readback, and
runtime proof on an inactive Video cue with embedded audio. Matrix crosspoints
should stay blocked.

## Trim Matrix

QClass Day 1 describes Trim as an un-remote-controllable, un-fadable final
adjustment layer. The local OSC dictionary exposes many cue audio level and
patch routes, but no clearly named direct trim route was found in the inspected
dictionary.

Recommendation: block Trim. Do not emulate it through levels. Do not support
per-output trim or delay-style trim until an official, readable, writable OSC
route is found and rollback is proven.

## Objects Matrix

| Family | Examples | Read/write | Current MCP | Recommendation |
|---|---|---|---|---|
| object inventory | `objects`, `object/{name}`, `objectID/{id}` | read-only for inventory | present in catalog | Read-only only |
| object position | `object/{name}/position`, `/live` variants | read/write | planned-only | Block |
| object spread | `object/{name}/spread`, `/live` variants | read/write | planned-only | Block |
| object levels | `objectLevel`, `objectIDLevel`, `/live` variants | read/write | planned-only | Block |
| audio map objects | `audioMap/object*` | mixed read/write | planned-only | Block |

QClass says Video cues with audio tracks can use the audio-land tabs, including
Objects. That does not make object writes safe. Object references by name/ID,
map visibility, `/live` variants, and spatial output consequences need a
dedicated phase.

## Audio FX Matrix

QClass confirms Video cues with audio tracks expose Audio FX like Audio cues.
The inspected local OSC dictionary did not reveal a simple cue-level `audioFX`
parameter route analogous to Video FX. Audio effects are plugin-dependent,
insert-order-dependent, channel-count-dependent, and can decay after playback.

Recommendation: block. Treat Audio FX as future-only until official OSC routes
and a parameter readback model are identified.

## Existing Implementation Audit

Already implemented or cataloged:

- `audio_basic` real-write safe properties:
  `rate`, `startTime`, `endTime`, `playCount`, `infiniteLoop`,
  `preservePitch`.
- `audio_basic` planned-only audio behavior:
  `doFade`, `lockFadeToCue`, slices, levels, slider levels, gangs, mute/solo,
  object levels, object position/spread, audio map edits.
- `video_basic` currently does not include `AUDIO_SAFE_PROPERTIES`; it only
  includes Video catalog properties plus common properties.
- `video_basic` has `audioOutputPatchID` via Phase 8A `confirm:videoIO:v1:`.
- `camera_basic` includes Mic/Audio catalog properties plus Video catalog
  properties.
- Read profiles currently expose Video/Camera `audioOutputPatchName` and
  `audioOutputPatchID`, but not the full Audio safe timing key set for Video by
  default.

Do not duplicate Phase 8A I/O selection. Do not reuse Geometry, Appearance,
Video FX, or Video I/O tokens for embedded audio writes.

## Recommended Implementation Scope

Option A is viable, but only as a small first phase:

Phase 8B: Video embedded audio timing basics.

Properties:

- `startTime`
- `endTime`
- `playCount`
- `infiniteLoop`
- `rate`
- `preservePitch`

Cue/profile:

- `Video` cue only
- `video_basic`
- saved mode only
- exact cue UUID only
- one cue, one property
- healthy inactive cue
- target must have readable embedded audio evidence:
  `audioTrackFormats` non-empty or `numChannelsIn > 0`/`levels` present
- fresh baseline readback
- fresh post-write readback
- rollback with fresh token

Token:

- `confirm:videoAudioTime:v1:`

Token must not authorize:

- Audio levels or object audio
- Integrated fade
- Slices
- Clock type
- Trim
- Audio FX
- Geometry
- Appearance/blend mode
- Video I/O
- Video FX
- playback/show-control/raw OSC

## Future Runtime-Probe Only

- `clockType` (`audio`/`video`): meaningful for Video with audio but can change
  sync behavior. Probe separately.
- `doFade` and `lockFadeToCue`: integrated fade is useful but has curve state
  and timing semantics not represented by a single safe scalar.
- `sliderLevel/0`: possible small level phase, but only after stable
  `sliderLevels` baseline/readback and rollback are proven.

## Blocked / Future-Only

- `/live` variants
- `levels` matrix write via `level/{row}/{output}`
- `setDefaultLevels`
- `setSilentLevels`
- `gang`
- `mute` / `solo`
- slice creation/deletion/editing
- object audio position/spread/levels
- audio maps and map-object editing
- trim
- Audio FX
- audio patch definition edits
- output patch routing edits
- `audioOutputPatch/*` patch-level edits
- file target changes
- `audioTrackID` switching unless official write route is found
- Camera audio behavior unless separately scoped

## Required Tests for Phase 8B

- registry exposes Video audio timing properties as gated candidates
- dry-run emits only `confirm:videoAudioTime:v1:`
- value validation for rate range, positive play count, non-negative start/end,
  booleans
- rejects cue name/number for real write
- rejects wrong cue type, unless explicitly extended later
- rejects fake/stale/wrong token family
- existing Geometry/Appearance/Video I/O/Video FX tokens cannot authorize Video
  audio writes
- Video audio token cannot authorize other families
- rejects `/live`
- rejects batch and multi-property
- real write sends one setter
- timeout accepted only if fresh readback matched
- rollback path uses fresh token and restores baseline

## Runtime Validation Plan

Use one healthy inactive Video cue with a target file that definitely contains
audio.

For each Phase 8B property:

1. Confirm workspace readiness and no running/paused/auditioning cues.
2. Read cue fresh and prove embedded audio evidence.
3. Record baseline.
4. Dry-run one tiny safe change and require `confirm:videoAudioTime:v1:`.
5. Real write with exact token and exact cue UUID.
6. Fresh readback must match.
7. Roll back immediately with a fresh dry-run token.
8. Fresh readback must match original baseline.

No raw OSC, `/live`, playback, save, batch, or multi-property writes.
