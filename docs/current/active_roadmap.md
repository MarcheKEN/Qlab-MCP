# Active Roadmap

Status: 2026-07-14

## Closed

- Video Phase 1 — inventory, dry-run, and write-safety closure.
- Video Phase 1D — lightweight Video read summaries.
- Video Phase 2A — scalar dry-run matrix and blocked-family cleanup.
- Video Phase 2B — UpdateQ plan format.
- Video Phase 2C — future gate vectors.
- Video Phase 3A — saved `opacity` real write for `Video`, `Camera`, and `Text`.
- Video Phase 3B — saved `translation/x` and `translation/y` real write for
  `Video`, `Camera`, and `Text`.
- Video Phase 3C — saved visual scalar real writes for `Video`, `Camera`, and
  `Text`: `scale/x`, `scale/y`, `anchor/x`, `anchor/y`, `cropTop`,
  `cropBottom`, `cropLeft`, and `cropRight`.
- Video Phase 3D — saved visual appearance real writes for `Video`, `Camera`,
  and `Text`: `blendMode` and `preserveAspectRatio`.
- Video Phase 3E — saved Text Basics real writes for `Text` cues:
  `text`, `text/format/fontSize`, and `text/format/alignment`.
- Text cue expansion — runtime-confirmed `text`, `fixedWidth`, alignment,
  `fontName`, `fontSize`, `lineSpacing`, and `text/format/color` saved writes
  for exact-UUID `Text` cues; the remaining RGBA routes stay planned-only.
- Video Phase 4C — saved Video FX scalar real write for `Video` cues only:
  exact cue UUID only, `videoEffectIndex/0/parameter/inputRadius`, finite
  numeric scalar, saved mode only.
- Video Phase 6 — saved Video FX scalar v2 real write for `Video` cues only:
  exact cue UUID only, `videoEffectIndex/0/parameter/inputIntensity`, finite
  numeric scalar, saved mode only.
- Video Phase 7 — saved geometry completion real writes for `Video`, `Camera`,
  and `Text`: `fillStage` and `fillStyle`, exact cue UUID only, one cue, one
  property, saved mode only.

Phase 3A runtime validation confirmed token-gated single-property writes, fresh
readback, new-token rollback, and restored baselines for all three cue types.
QLab setter timeout with matching readback is accepted as success with warning
`setter_timeout_but_readback_matched`.

Phase 3B runtime validation confirmed token-gated writes and new-token rollback
for both axes on healthy `Video`, `Camera`, and `Text` cues.

Phase 3C runtime validation confirmed 8/8 properties on each healthy `Video`,
`Camera`, and `Text` cue. Each write used `confirm:videoScalar:v1:`, one saved
setter, matching fresh readback, and a new-token rollback restoring baseline.
QLab setter timeout with matching readback was accepted as confirmed success
with warning `setter_timeout_but_readback_matched`.

Phase 3D runtime validation confirmed 6/6 real writes and 6/6 new-token
rollbacks across healthy `Video`, `Camera`, and `Text` cues. All 22/22 rejection
probes blocked before mutation. Final baselines were intact, with no unrelated
writes and zero running, paused, or auditioning cues. QLab setter timeout with
matching fresh readback was accepted as confirmed success with warning
`setter_timeout_but_readback_matched`; no mutating retry occurred.
The follow-up blend mode audit confirmed `blendMode` is a Video FX tab control
but not an MCP Video FX parameter write: OSC uses the full blend mode name as a
string at `/cue/{cue_number}/blendMode`, and the existing
`confirm:videoAppearance:v1:` boundary remains correct. The validator now
requires exact official strings only; lowercase, trimmed, partial, unknown, and
numeric values are rejected instead of canonicalized.

Phase 3E was independently runtime validated on `v1 Text1` in the test
workspace. All 3/3 real writes and 3/3 fresh-token rollbacks passed. All 12/12
rejection probes blocked before mutation with `executed_operations=[]`. The
final text, font-size, and alignment baseline was restored exactly; the cue was
healthy and inactive, with global running, paused, and auditioning counts
0/0/0. All six setters timed out, matching fresh readback confirmed each result
as `status="updated"` with warning `setter_timeout_but_readback_matched`, and
no mutating retry occurred. No GO, playback, audition, `/live`, raw OSC, save,
or unrelated mutation was used.

Phase 4C was independently runtime validated on `v11 dorado.png`
(`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`) in `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`) with QLab 5.5.10. The only supported
real write is `Video` `videoEffectIndex/0/parameter/inputRadius` in saved mode,
using an exact cue UUID and a finite numeric scalar. Baseline `10` changed to
`11`, fresh readback matched, then rollback used a fresh token and restored
`10`. Rejection probes blocked fake token, stale/used token, wrong value, wrong
index, wrong parameter, cue number, Camera cue, Text cue, `/live`, batch,
multi-property, name-based effect targeting, enabled/disabled, string/color/
structured value, and broken cue before mutation with `executed_operations=[]`.
QLab setter timeout with matching fresh readback was accepted as confirmed
success with warning `setter_timeout_but_readback_matched`; no mutating retry
occurred. Stale/used-token rejection was observed as a no-op baseline rejection,
not an explicit consumed-token diagnostic.

Phase 6 was independently runtime validated on `v11 dorado.png`
(`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`) in `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`). The supported path is
`Video` exact-UUID, saved-mode, finite-numeric
`videoEffectIndex/0/parameter/inputIntensity` only, with
`confirm:videoFxScalar:v2:`. The happy path changed
`2.6191787554229933 -> 2.7191787554229934`; rollback restored
`2.6191787719726562` within QLab float precision. Rejection probes rejected
fake v2, malformed v1-looking token, changed value, `inputPower`,
`Choose_Effect`, cue-number ref, and multi-property attempts with
`executed_operations=[]`. `inputPower` requires separate proof; `Choose_Effect`
stays out.

Phase 7 was independently runtime validated on `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`) with one healthy inactive cue per type:
`Video` `Fill stage` (`BF24AB14-43D2-43BD-BBE7-1BC87DDB5107`), `Camera`
`Camare1` (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`), and `Text` `Text1`
(`193FB551-7985-4381-9C2D-CF4218C03FB9`). All 6/6 writes and 6/6 fresh-token
rollbacks passed: `Video` `fillStage true -> false -> true`, `Video`
`fillStyle 0 -> 1 -> 0`, `Camera` `fillStage true -> false -> true`, `Camera`
`fillStyle 0 -> 1 -> 0`, `Text` `fillStage false -> true -> false`, and `Text`
`fillStyle 0 -> 1 -> 0`. QLab setter timeout with matching fresh readback was
accepted as confirmed success with warning `setter_timeout_but_readback_matched`;
no mutating retry occurred. Rejection probes blocked cue-number real write,
`/live`, multi-property real write, `rotation`, and `shutterTop` before
mutation/OSC as applicable. Final baselines were restored, with running and
paused counts `0/0`; no playback, raw OSC, `/live` write, save, commit, or
unrelated mutation was used.

- Video Phase 7B — saved `layer` real write for `Video`, `Camera`, and `Text`:
  exact cue UUID only, one cue, one property, integer `0..1000`, saved mode
  only, `confirm:videoGeometry:v2:`.
- Video Phase 7C — rotation/quaternion/resetRotation/shutter geometry audit:
  audited; `quaternion` moved to Phase 7D, other advanced routes remain blocked.

Phase 7B was independently runtime validated on `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`) with `Video` `v11 dorado.png`
(`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`), `Camera` `v6 Camare1`
(`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`), and `Text` `v1 Text1`
(`193FB551-7985-4381-9C2D-CF4218C03FB9`). All 3/3 writes and 3/3 fresh-token
rollbacks passed: `1000 -> 11 -> 1000` for each cue. All real writes and
rollbacks returned `setter_timeout_but_readback_matched`; each was accepted only
because fresh readback matched, with no mutating retry. Rejection probes blocked
fake v2 token, v1 geometry token for `layer`, cue number, and `/live` before
setter with `executed_operations=[]`. Final workspace running/paused/auditioning
was `0/0/0`; unrelated pre-existing broken cues were not blockers.

- Video Phase 7D — saved `quaternion` real write for `Video`, `Camera`, and
  `Text`: exact cue UUID only, one cue, one property, four finite non-boolean
  numbers, saved mode only, `confirm:videoGeometry:v3:`.
- Video Phase 7E — protected saved `resetRotation: true` action for `Video`,
  `Camera`, and `Text`: exact cue UUID only, one cue, one action, saved mode
  only, `confirm:videoGeometryReset:v1:`.

Phase 7D and Phase 7E were independently runtime validated on
`mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`) with `Text`
`Probar quaternion` (`796D1FB7-42B7-4B52-90D0-9379EC2BB951`), `Video`
`v11 dorado.png` (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`), and `Camera`
`v6 Camare1` (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`). Quaternion writes used
fresh v3 tokens and matching fresh readback; reset actions used fresh reset v1
tokens, executed exactly one `/resetRotation`, and ended with reset quaternion
readback. Final workspace running/paused/auditioning was `0/0/0`; no raw OSC,
playback, `/live`, save, commit, or unrelated mutation was used.

## Runtime-validated additions and remaining boundaries

Utility cue editing (runtime validated and closed):

- local `cueTargetID` gate for `Start`, `Stop`, `Pause`, `Load`, `Reset`,
  `Goto`, `Arm`, and `Disarm`, using `confirm:utilityTarget:v1:`
- exact source/target UUIDs only; one healthy inactive source and target; saved
  mode; fresh baseline/readback; fresh-token rollback
- Wait and Memo remain Basics-only
- target names/numbers, temporary targets, Reset patch/map targets, target
  mode, actions, `/live`, playback, raw OSC, batch/multi-property writes, and
  save remain blocked
- exact target assignment, fresh readback, fresh-token rollback, and final
  `0/0/0` activity passed; names/numbers/actions and unsupported targets remain
  blocked

Devamp saved configuration (runtime validated and closed for listed properties):

- local `confirm:devamp:v1:` gate for exact-UUID, saved, one-property
  `cueTargetID`, `devampType`, `startNextCueWhenSliceEnds`, and
  `stopTargetWhenSliceEnds` updates
- source and resolved target must be healthy/inactive; targets are exact
  existing `Audio` or `Video` cue UUIDs only
- Stop target requires Start next already enabled; Start next cannot be disabled
  while Stop target is true, avoiding an implicit multi-property change
- fresh baseline/readback and fresh-token rollback passed; slices and actions
  remain blocked

Network OSC Message:

- `customString`, `networkPatchID`, fades, and device-description parameters
  remain planned-only because documented network patch readback does not prove
  `OSC Message` mode
- no patch definitions, destination settings, raw OSC, playback, or save

Video Phase 3F — Text Style:

- blocked after QLab 5.5.10 runtime validation did not return reliable fresh
  baselines/readback for `shadowBlurRadius`, `shadowOffset/width`,
  `shadowOffset/height`, `underlineStyle`, or `strikethroughStyle`
- no `confirm:textStyle:v1:` tokens emitted
- no Text Style setters enabled

Video Phase 4A/4B — Video FX read model and dry-run planner:

- lightweight safe effect/parameter summaries
- dry-run only for enabled state and existing scalar parameters by name/index;
  QLab 5.5.10 flat `videoEffects` payload keys are treated as parameter-like
  fields when addressed by index
- no token and no Video FX real write

Video Phase 5 — Completion Matrix and Closure Audit:

- docs/audit-only macro phase
- no runtime QLab tools, no raw OSC, no new setters, no write-scope expansion,
  no token changes
- classify every remaining Video-family route/family as runtime-validated real
  write, safe dry-run/planned-only, read-only, or blocked with explicit reason
- clean docs inconsistencies before any Video FX scalar expansion

Video Phase 7F — Smooth Geometry:

- local implementation adds saved `smooth` as a real-write candidate for
  `Video`, `Camera`, and `Text`
- `smooth` uses `confirm:videoGeometry:v4:`
- value must be boolean `true` or `false`
- v1/v2/v3 geometry tokens and reset tokens cannot authorize `smooth`; v4
  cannot authorize other geometry properties or `resetRotation`

Cue I/O Phase 8A — Edit Cues and cue-level I/O selection:

- local implementation exposes preferred `qlab_edit_cues` while keeping
  `qlab_update_cues` as a compatibility alias
- adds saved ID-only I/O real-write candidates using `confirm:videoIO:v1:`
- `Video`: `stageID`, `audioOutputPatchID`
- `Camera`: `stageID`, `audioOutputPatchID`, `videoInputPatchID`,
  `audioInputPatchID`
- `Text`: `stageID`
- `Audio`: `audioOutputPatchID`
- `Mic`: `audioOutputPatchID`, `audioInputPatchID`
- exact cue UUID only, one cue, one property, saved mode, healthy inactive cue,
  fresh baseline, fresh token, and fresh readback required
- Audio/Mic patch IDs must also be current members of
  `settings/audio/patchList` or `settings/mic/patchList`: dry-run refuses an
  absent/unreadable ID before issuing a token when the one-cue/one-property
  gate is eligible, and real-write preflight checks
  the same list again before the setter
- currently disconnected existing stages remain selectable by `stageID`, but
  results warn with `stage_route_disconnected` when route/device metadata is
  available; if the write makes the cue broken, only exact rollback to the
  recorded baseline `stageID` is allowed
- workspace stage/patch definitions, name/number convenience refs, unpatch,
  `/live`, batch/multi-property, raw OSC, playback, and save remain blocked
- official reset routes were found only for `resetRotation`; crop,
  translation, scale, anchor, and opacity synthetic reset actions remain
  future-only pending separate proof
- runtime validation is required before closure

Video Phase 8B — Video embedded-audio Time & Loops:

- local implementation adds saved `video_basic` real-write candidates using
  `confirm:videoAudioTime:v1:`
- `Video` only: `startTime`, `endTime`, `playCount`, `infiniteLoop`, `rate`,
  `preservePitch`, and official Hold at End route `holdLastFrame`
- audio timing routes require readable embedded-audio evidence:
  non-empty `audioTrackFormats`, `numChannelsIn > 0`, or non-empty `levels`
- `holdLastFrame` is included as the Video Time & Loops Hold at End route but
  does not itself prove embedded audio
- exact cue UUID only, one cue, one property, saved mode, healthy inactive cue,
  fresh baseline, fresh token, fresh readback, and fresh-token rollback required
- `preservePitch` user input remains strict boolean, while QLab readback `0`/`1`
  is normalized internally for baseline, verification, and rollback
- setter timeout or QLab setter error is accepted only when fresh readback
  matches, and remains warning-visible
- Linear Curve, Audio/Video slice/vamp/devamp routes outside the dedicated
  Devamp saved-configuration gate, levels, objects, Audio FX, Trim, `/live`,
  raw OSC, playback, batch, multi-property, and save remain blocked for
  Phase 8B. `doFade` and `lockFadeToCue` moved to their own local
  token-gated implementation, with runtime validation pending.
- runtime validation is required before closure

Video Phase 9A — Video embedded-audio Levels top-row sliders:

- local implementation adds saved `video_basic.sliderLevel` real-write
  candidates using `confirm:videoAudioLevels:v1:`
- runtime validation passed on `v5 Con slices`
  (`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`:
  `sliderLevel/0` baseline `0` -> `-1.0` -> fresh readback
  `-1.000009003387651` -> rollback `0`; `sliderLevel/1` previously passed
  with the same write/readback/rollback pattern
- setter timeout is accepted only with warning
  `setter_timeout_but_readback_matched` when fresh readback matches
- token eligibility requires real embedded-audio evidence:
  `numChannelsIn > 0` or non-empty `audioTrackFormats`
- `levels` and `sliderLevels` may be readable on Video cues without embedded
  audio, so they are baseline/readback data only, not evidence gates; this was
  validated on `v11 dorado.png`
  (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`)
- runtime-validated scope: Video only, `sliderLevel/{channel}` only, saved mode, exact UUID,
  one cue, one operation, healthy inactive cue, readable `sliderLevels`,
  finite numeric dB only, fresh token/readback/rollback; `/live`, raw OSC,
  playback, save, batch, multi-property, output names, and `-inf` remain blocked

Video Phase 9B — Video embedded-audio Matrix Crosspoints:

- research confirms `/cue/{cue_number}/levels` is read-only matrix readback and
  `/cue/{cue_number}/level/{inChannel}/{outChannel} {decibel}` is read/write
- `/levels[0]` maps to the top-row slider levels handled by Phase 9A, so first
  Phase 9B scope must reject `inChannel = 0`
- minimal runtime validation passed on `v5 Con slices`
  (`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`:
  lower-matrix `level/1/0` baseline `0` -> `-1.0` -> fresh readback
  `-1.000009003387651` -> rollback `0`
- runtime-validated minimal scope: one saved `level/{inChannel}/{outChannel}` operation,
  `Video` cue only, exact UUID, one cue, one operation, healthy inactive cue,
  real embedded-audio evidence, readable matrix, finite numeric dB only, integer
  indexes only, fresh `confirm:videoAudioMatrix:v1:` token, fresh readback, and
  rollback
- setter timeout is accepted only with warning
  `setter_timeout_but_readback_matched` when fresh readback matches
- `/live`, raw OSC, playback, save, batch, multi-property, output names,
  `-inf`, row `0`, `setDefaultLevels`, `setSilentLevels`, `mute`, `solo`,
  Trim, Objects, Audio FX, Audio Maps, Object Audio,
  and routing/patch editor writes remain blocked

Audio/Mic Edit Cues — local I/O and core Levels candidates:

- `audio_basic.audioOutputPatchID`, `mic_basic.audioOutputPatchID`, and
  `mic_basic.audioInputPatchID` reuse the Phase 8A saved exact-ID gate. The
  historical `confirm:videoIO:v1:` prefix remains, but its signed payload binds
  cue type and profile, so tokens cannot cross-authorize cue families. Audio
  output IDs are checked against the fresh workspace output-patch list and Mic
  input IDs against the fresh input-patch list during dry-run and again before
  the real setter.
- `audio_basic.sliderLevel` and `mic_basic.sliderLevel` reuse the Phase 9A
  saved scalar contract with readable `sliderLevels`, finite numeric dB,
  integer channel, exact UUID, healthy inactive cue, one cue/operation, fresh
  token/readback, and fresh-token rollback. Audio and Mic do not require
  Video's embedded-audio evidence gate.
- `audio_basic.level` and `mic_basic.level` reuse the Phase 9B lower-matrix
  contract with readable `levels`, `numChannelsIn` bounds, finite numeric dB,
  integer indexes, row `0` blocked, exact UUID, healthy inactive cue, one
  cue/operation, fresh token/readback, and fresh-token rollback. They use the
  existing `confirm:videoAudioLevels:v1:` and
  `confirm:videoAudioMatrix:v1:` token families with type/profile-bound
  payloads.
- `audio_basic.inputChannelName` / `mic_basic.inputChannelName` and
  `audio_basic.gang` / `mic_basic.gang` reuse the Phase 9C saved metadata
  contract: dynamic fresh baseline/readback, `numChannelsIn` and matrix bounds,
  exact UUID, healthy inactive cue, one cue/operation, strict bounded strings,
  fresh token, and rollback. Audio and Mic do not require Video's
  embedded-audio evidence; the historical `confirm:videoAudioLevelMeta:v1:`
  payload binds type and profile.
- Automated contract tests pass locally. No Audio or Mic runtime write has
  been attempted; validation remains pending until a manual MCP restart and
  the recorded readback/rollback plans are run through MCP only.
- Audio Time & Loops remains the existing `audio_basic` saved-write scope;
  Mic does not inherit it. Mic supports only I/O and Levels in this scope.
- Mic Format is not promoted: `channelOffset` (Input Starting Channel) and
  `channels` remain gated until the selected input patch's channel capacity can
  be read and checked. The documented `settings/mic/patchList` exposes only
  input-patch ID/name, while `channelOffset`, `channels`, and `numChannelsIn`
  describe the cue rather than patch capacity; no static channel bound is safe
  because QLab permits starting channels above 64. Object Audio, Audio FX,
  `doLevel`, Trim mute/solo and clears, reset actions, `/live`, patch
  definitions, and patch routing remain outside this scope.

Video Phase 9C — Video embedded-audio Levels metadata:

- `inputChannelName/{number}` runtime validation passed for saved exact-UUID
  Video cues with real embedded-audio evidence
- `gang/{inChannel}/{outChannel}` runtime validation passed on `v5 Con slices`
  (`D68AA7F9-2C5B-4D3A-A860-78E5F522ACD8`) in `mcp_prueba.qlab5`:
  `gang/1/0` baseline `""` -> `"MCPG"` -> fresh readback `"MCPG"` ->
  rollback `""`
- final scope: one saved gang crosspoint, `Video` cue only, exact UUID, one cue,
  one operation, healthy inactive cue, real embedded-audio evidence, readable
  `levels` bounds, integer indexes only, `inChannel` `1..numChannelsIn`,
  string up to 64 chars without control characters, fresh
  `confirm:videoAudioLevelMeta:v1:` token, fresh readback, and rollback
- setter timeout is accepted only with warning
  `setter_timeout_but_readback_matched` when fresh readback matches
- `/live`, row `0`, output names, batch, multi-property, raw OSC, playback,
  save, Camera/Text promotion, and Video cues without embedded audio remain
  blocked. The recorded QLab validation remains Video-only; the local Audio/Mic
  Phase 9C candidates above still require their own MCP readback/rollback run.

Video clock type and Integrated Fade:

- `clockType` is locally implemented for saved exact-UUID `Video` cue writes
  with strict `audio`/`video` values, fresh `confirm:videoClockType:v1:`
  token, fresh readback, and rollback plan; it does not require embedded-audio
  evidence because QLab documents `/clockType` directly for Video cues without
  that prerequisite
- `doFade` and `lockFadeToCue` are locally implemented for saved exact-UUID
  `Video` cue writes with real embedded-audio evidence, strict boolean values,
  fresh `confirm:videoIntegratedFade:v1:` token, fresh readback, and rollback
  plan
- Integrated Fade envelope points, Custom Curve, and Linear Curve remain
  blocked/planned-only. The OSC Dictionary exposes `doFade` and
  `lockFadeToCue` for the internal Integrated Fade checkboxes, but does not
  expose a documented Audio/Video Integrated Fade point/curve route with clear
  readback and rollback. `fadeEntries`, `fadeType`, `fadeFrom`, and `fadeTo`
  are not reused here because the dictionary places them in Fade/Network cue
  shape/path behavior, not the Audio/Video Integrated Fade envelope.
- runtime validation is pending until Codex/Code/MCP restart; no QLab runtime
  validation was attempted in this local implementation pass
- `/live`, raw OSC, playback/show-control, save, batch, multi-property,
  Audio/Camera/Text promotion, wrong token families, fake/stale tokens, and
  Video cues without embedded audio remain blocked for Integrated Fade only

Video Phase 9D/9E — local Video audio mute/solo candidates:

- `mute/channel` and `solo/channel` use `confirm:videoAudioMuteSolo:v1:`;
  `mute/channel/clear` and `solo/channel/clear` use
  `confirm:videoAudioLevelBulk:v1:`.
- These saved, exact-UUID, one-cue, one-operation candidates require embedded
  audio evidence, fresh channel baseline/readback, and a fresh-token rollback.
- Automated contract tests cover the real-write and rollback flows; QLab runtime
  validation is still pending.

Light cue token-gated editing:

- `lightCommandText` is a real-write candidate only after valid safe Light Patch
  analysis; `alwaysCollate` and `subcontroller` are separate saved-mode
  candidates.
- All require one exact-UUID Light cue, one property, saved mode, a fresh
  baseline, a reviewed confirm token, and fresh readback. Automated contract
  tests pass; QLab runtime validation is not recorded here.

Video Phase 9F — Video embedded-audio Levels reset actions:

- `/cue/{cue_number}/setDefaultLevels` and
  `/cue/{cue_number}/setSilentLevels` are documented QLab actions, not scalar
  properties
- they remain planned-only because docs do not prove a complete deterministic
  rollback contract for every affected `levels`/`sliderLevels` value, and the
  MCP does not yet implement bounded internal per-cell rollback for these bulk
  actions

Video Phase 8C — Slice Markers for Audio/Video:

- local read support exposes `sliceMarkers`, `lastSlicePlayCount`, and
  `lastSliceInfiniteLoop` in Audio and Video detail profiles when QLab returns
  them; normal profiles now use the same canonical slice read path as
  exhaustive/write dry-run, so real markers are not hidden as `[]`
- missing Audio/Video `sliceMarkers` is normalized to `[]` only after the slice
  route was intentionally queried; unqueried profiles no longer invent
  `sliceMarkers: []`
- `sliceMarkers` entries include `index`, preserve raw `time` and `playCount`,
  and label play-count mode as `finite`, `infinite`, or `unknown`; malformed
  non-list readback is not treated as empty
- local Video-only write candidates use `confirm:videoSlices:v1:`
- implemented saved `video_basic` candidates:
  `sliceMarker/{index}/time`, `sliceMarker/{index}/playCount`,
  `addSliceMarker`, `deleteSliceMarker/{index}`, `deleteSliceMarkers`, and
  `lastSlicePlayCount`
- exact cue UUID only, one healthy inactive `Video` cue, one operation, one
  marker/property, saved mode, fresh baseline, fresh token, and exact fresh
  readback required
- missing `sliceMarkers` on healthy inactive Video is accepted as empty baseline
  only for safe `addSliceMarker`; existing-marker edits/deletes still reject
- `deleteSliceMarkers` requires a non-empty baseline and rollback by re-adding
  every captured marker in order; omitted/missing post-delete `sliceMarkers`
  readback is accepted as `[]` only when expected empty readback was requested
- `playCount` accepts positive integers and `-1`; `0`, floats, strings,
  booleans, null, lists, and dictionaries are rejected
- marker times must be finite, in known cue bounds, and at least `0.05s` from
  other markers
- exact-time copy is the selected future V5/V8 model; no proportional timing
  copy is implemented
- Audio/Camera real writes, combined `/sliceMarker/{index}`,
  `lastSliceInfiniteLoop`, Audio/Video vamps/devamps outside the dedicated
  Devamp saved-configuration gate, `/live`, batch, multi-property, raw
  OSC, playback, and save remain blocked
- runtime validation is required before closure

See:

- `workorders/completed/002_close_phase3a_docs.md`
- `workorders/completed/003_plan_phase3b_translation.md`
- `workorders/completed/004_implement_phase3c_visual_scalars.md`
- `workorders/completed/005_implement_phase3d_visual_appearance.md`
- `workorders/completed/006_implement_phase3e_text_basics.md`
- `workorders/007_text_style_and_video_fx_read_plan.md`
- `workorders/completed/008_video_fx_real_write_candidate.md`
- `workorders/completed/009_video_completion_matrix.md`
- `workorders/completed/010_video_docs_consistency_cleanup.md`
- `workorders/completed/011_video_fx_scalar_v2_candidate.md`
- `workorders/completed/012_geometry_completion_video_camera_text.md`
- `workorders/completed/013_full_geometry_completion_video_camera_text.md`
- `workorders/completed/014_rotation_quaternion_shutter_geometry.md`
- `workorders/completed/015_quaternion_geometry_write.md`
- `workorders/completed/016_safe_reset_rotation.md`
- `workorders/017_geometry_completion_smooth_and_defaults.md`
- `workorders/completed/018_blend_mode_audit_and_completion.md`
- `workorders/019_video_io_selection_edit_cues.md`
- `workorders/020_video_embedded_audio_research.md`
- `workorders/021_video_audio_time_loops.md`
- `workorders/022_slice_markers_audio_video.md`

## Safety boundary

Phase 3E, Phase 4C, Phase 6, Phase 7, Phase 7B, Phase 7D, and Phase 7E are
runtime validated and closed for their exact scopes. Phase 7F is local-code
complete for `smooth` but requires MCP restart and runtime validation before
closure.
Phase 8C is local-code complete for Video slice marker write candidates and
Audio/Video slice marker readback, but requires MCP restart and runtime
validation before closure.
Phase 3F remains blocked because runtime readback was unavailable; Phase 4A/4B
remain read/dry-run only except for the closed Phase 4C and Phase 6 candidates.
Keep blocked:

- playback, GO, Dashboard, raw OSC, and `/live`
- Workspace Video writes
- stage, region, route, warping, and control-point writes
- all Video FX real writes except the Phase 4C closed `Video` exact-UUID,
  saved-mode, finite-numeric `videoEffectIndex/0/parameter/inputRadius`
  candidate and the Phase 6 closed `Video` exact-UUID, saved-mode,
  finite-numeric `videoEffectIndex/0/parameter/inputIntensity` candidate; FX
  add/insert/delete/move, enabled/disabled, name-targeted writes, Camera/Text FX,
  aggregate parameter planning, color/structured/string/enum/list/dict
  parameters, and `/live`
- future Video FX candidates are limited to more scalar `Video` parameters,
  Camera/Text FX after separate proof, and enabled/disabled after stable
  readback; color and structured parameters remain blocked
- Phase 7 is closed only for saved-mode, exact-UUID, one-cue, one-property
  `fillStage` and `fillStyle` on `Video`, `Camera`, and `Text`; Phase 7B is
  closed only for saved-mode, exact-UUID, one-cue, one-property integer `layer`
  on `Video`, `Camera`, and `Text`
- Phase 7C keeps `rotation`, `rotationType`, `rotate/x`, `rotate/y`,
  `rotate/z`, and shutter writes blocked. Phase 7D promotes only `quaternion`
  behind `confirm:videoGeometry:v3:`, Phase 7E promotes only `resetRotation`
  behind `confirm:videoGeometryReset:v1:`, and Phase 7F promotes only `smooth`
  behind `confirm:videoGeometry:v4:`.
- `fileTarget` and camera/video-input patch writes outside Phase 8A
- Audio/Camera slice marker real writes, combined slice marker updates,
  last-slice routes, vamps/devamps, and slice marker `/live` writes outside
  Phase 8C
- rich text format other than the closed Text Basics routes, aggregate shadow
  offset, `doOpacity`, and unvalidated rich-text color routes
- batch and multi-property Video-family real writes

Phase 6 is closed only for the exact `inputIntensity` scalar path above. It
does not authorize `inputPower`, `Choose_Effect`, any other parameter,
Camera/Text FX, name targeting, enabled/disabled, add/delete/move/reorder,
aggregate params, color/structured/string/enum/list/dict values, cue-number real
writes, batch/multi-property, `/live`, Workspace Video, stages/routes/surfaces,
patches, `fileTarget`, warping/control points, or playback/show-control.
