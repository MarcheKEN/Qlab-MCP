# Video Embedded Audio Research

Status: Phase 9A runtime validated; Phase 9B minimal matrix crosspoint runtime
validated for its exact narrow scope; Phase 9C `inputChannelName` and scoped
`gang` runtime validated. `clockType`, `doFade`, and `lockFadeToCue` are
locally implemented with token-gated saved writes. The relaxed `clockType`
no-audio gate is local-only pending MCP restart/runtime validation.
`setDefaultLevels` and `setSilentLevels` remain planned-only.

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
| I/O clock choice | `clockType` | Video cue can use `audio` or `video`; no OSC-documented embedded-audio prerequisite | Local token-gated implementation; relaxed no-audio gate runtime pending |
| Time & Loops | Audio cue timing routes | Video responds; meaningful with audio track | Safe candidate subset |
| Integrated fade | `doFade`, `lockFadeToCue` | Shared Audio route; internal curve UI has no confirmed direct OSC route | Local token-gated implementation for checkboxes; points/curve blocked |
| Levels | `levels`, `sliderLevel`, `level`, `gang`, `setDefaultLevels`, `setSilentLevels` | Shared Audio route | Phase 9A slider, Phase 9B matrix crosspoint, and Phase 9C metadata real-writes validated |
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
| `doFade` | `/cue/{cue_number}/doFade {boolean}` | boolean | read/write | `confirm:videoIntegratedFade:v1:` | Local implementation; runtime pending |
| `lockFadeToCue` | `/cue/{cue_number}/lockFadeToCue {boolean}` | boolean | read/write | `confirm:videoIntegratedFade:v1:` | Local implementation; runtime pending |
| `sliceMarker/*` | `/sliceMarker`, `/addSliceMarker`, `/deleteSliceMarker*` | indexed time/play count actions | read/write/action | planned-only | Block |
| `clockType` | `/cue/{cue_number}/clockType {audio|video}` | enum string | read/write | `confirm:videoClockType:v1:` | Local implementation; no-audio runtime pending |
| `holdLastFrame` | `/cue/{cue_number}/holdLastFrame {boolean}` | boolean | read/write | Video planned-only/gated elsewhere | Not part of audio phase |

`clockType`, `doFade`, and `lockFadeToCue` now have local token-gated saved
write support only for healthy inactive `Video` cues. `clockType` requires a
readable baseline and exact `audio`/`video` value, but no embedded-audio
evidence. `doFade` and `lockFadeToCue` remain embedded-audio gated.

Integrated Fade envelope points, Custom Curve, and Linear Curve remain blocked.
The OSC Dictionary exposes the internal Integrated Fade checkbox state through
`doFade` and `lockFadeToCue`, but no direct Audio/Video Integrated Fade
point/curve route with deterministic readback and rollback was found.
`fadeEntries`, `fadeType`, `fadeFrom`, and `fadeTo` are not reused because the
dictionary documents them under Fade/Network cue fade shape/path behavior, not
the Audio/Video internal Integrated Fade envelope.

## Levels Matrix

| Route | OSC path | Type | Readback | Current MCP | Recommendation |
|---|---|---|---|---|---|
| all levels | `/cue/{cue_number}/levels` | array-of-arrays | read-only | read key allowlisted | Read-only baseline source |
| slider levels | `/cue/{cue_number}/sliderLevels` | array row 0 | read-only | allowlisted/tests | Read-only baseline source |
| one slider | `/cue/{cue_number}/sliderLevel/{channel} {decibel}` | finite number only in MCP Phase 9A; channel integer only; 0 = main | yes via `sliderLevels[channel]` | `confirm:videoAudioLevels:v1:` | Runtime validated |
| one matrix crosspoint | `/cue/{cue_number}/level/{inChannel}/{outChannel} {decibel}` | finite number only in MCP Phase 9B; rows `1..numChannelsIn`; outputs integer only | yes via `levels[inChannel][outChannel]` | `confirm:videoAudioMatrix:v1:` | Runtime validated |
| gangs | `/cue/{cue_number}/gang/{inChannel}/{outChannel} {gang}` | string | yes | `confirm:videoAudioLevelMeta:v1:` | Runtime validated for one saved crosspoint |
| set defaults | `/cue/{cue_number}/setDefaultLevels` | action | indirect | planned-only | Block |
| set silent | `/cue/{cue_number}/setSilentLevels` | action | indirect | planned-only | Block |
| mute/solo | `/mute*`, `/solo*` | boolean/actions | partial | planned-only | Block |

`-inf` is documented for level and sliderLevel. Any string is coerced by QLab
to `-inf`, so Phase 9A and planned Phase 9B intentionally reject strings,
including `"-inf"`, and accept finite numeric dB only.

Phase 9A runtime validation passed on `v5 Con slices`
(`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`.
`sliderLevel/0` and `sliderLevel/1` were written to a small finite value and
rolled back with fresh readback. QLab setter timeouts were accepted only because
fresh `sliderLevels[channel]` readback matched
(`setter_timeout_but_readback_matched`).

The Phase 9A evidence gate was corrected after runtime validation found that
`v11 dorado.png` (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`) exposes readable
`levels` and `sliderLevels` despite `numChannelsIn = 0` and
`audioTrackFormats = {}`. Therefore `levels` and `sliderLevels` are only
baseline/readback data, not embedded-audio evidence. Phase 9A token eligibility
requires `numChannelsIn > 0` or non-empty `audioTrackFormats`.

Final Phase 9A scope: Video cue only, `video_basic`, saved mode only, exact UUID
only, one cue, one operation, healthy inactive cue, real embedded-audio evidence,
readable `sliderLevels[channel]`, finite numeric dB only, fresh
`confirm:videoAudioLevels:v1:` token, fresh readback, rollback with fresh token,
no `/live`, raw OSC, playback, save, batch, multi-property, output names, or
`-inf`.

Phase 9B minimal runtime validation passed on `v5 Con slices`
(`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`. Lower-matrix
`level/1/0` baseline `0` changed to `-1.0`, fresh readback matched
`-1.000009003387651`, rollback restored `0`, and setter timeout was accepted
only because fresh readback matched with
`setter_timeout_but_readback_matched`.

Phase 9B remains limited to one lower-matrix crosspoint with
`confirm:videoAudioMatrix:v1:` and must exclude row `0` because row `0` is the
top slider row already handled by Phase 9A.

Phase 9C `gang` runtime validation passed on `v5 Con slices`
(`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`. The validated
flow used `gang/1/0` baseline `""`, dry-run token
`confirm:videoAudioLevelMeta:v1:`, real write to `"MCPG"`, fresh readback
`"MCPG"`, fresh rollback token, real rollback to `""`, and fresh readback `""`.
Both real writes timed out at the setter but were accepted only because fresh
readback matched (`setter_timeout_but_readback_matched`).

Final Phase 9C `gang` scope: Video cue only, `video_basic`, saved mode only,
exact UUID only, one cue, one operation, healthy inactive cue, real
embedded-audio evidence, readable `levels` bounds, `inChannel` integer
`1..numChannelsIn`, integer `outChannel` within the row, string gang value up
to 64 characters with no control characters, fresh metadata token, fresh
readback, and rollback. Row `0`, output names, `/live`, raw OSC, playback,
save, batch, multi-property, Audio/Camera/Text promotion, and Video cues
without embedded audio remain blocked.

`setDefaultLevels` and `setSilentLevels` are documented QLab actions. They
remain planned-only because docs do not prove every affected saved value or a
complete deterministic rollback contract, and the MCP does not yet implement
bounded internal restoration of captured `sliderLevels` and `levels` after
these bulk actions. They should not use another bulk action as rollback.

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

## Runtime Pending

- `clockType` (`audio`/`video`): locally implemented with
  `confirm:videoClockType:v1:` for saved exact-UUID one-cue/one-operation
  Video writes with strict enum validation, fresh readback, and rollback plan.
  No embedded-audio evidence is required. Relaxed no-audio gate runtime
  validation pending after MCP restart.
- `doFade` and `lockFadeToCue`: locally implemented with
  `confirm:videoIntegratedFade:v1:` for saved exact-UUID
  one-cue/one-operation Video writes with embedded-audio evidence, strict
  boolean validation, fresh readback, and rollback plan. Runtime validation
  pending.
- `level/{inChannel}/{outChannel}`: Phase 9B minimal validated only for
  `inChannel` `1..numChannelsIn`, integer output columns present in the fresh
  `levels` matrix, saved mode, finite numeric dB, exact UUID, fresh token,
  readback, and rollback.

## Blocked / Future-Only

- `/live` variants
- broad `levels` matrix writes; only one scoped Phase 9B crosspoint may be
  considered
- `setDefaultLevels`
- `setSilentLevels`
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
