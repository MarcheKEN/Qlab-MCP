# Active Roadmap

Status: 2026-08-13 — 0.3.0 preparation

## Current state snapshot

The canonical dated inventory is [`current-state.md`](current-state.md). The
current snapshot is provisional on the preparation branch; a docs-only PR will
replace it after the 0.3.0 merge into `main` and before the release tag.

Current focused verification: `2245 passed, 1 skipped` for the MCP/write
contract suite. The full local suite passed with `2584 passed, 41 subtests
passed` outside the managed socket sandbox. FastMCP inspection reports 13 tools
and wheel/sdist builds report `0.3.0`; Linux CI remains the external release
gate. Artifact-membership checks passed locally.

Evidence terms follow [Current Docs](README.md): documented,
source-confirmed, runtime-proven, inferred, and unsupported. Runtime claims
below apply only to their named QLab version and procedure. The local reference
snapshot is documented QLab 5 material with unknown exact patch and retrieval
date; its first repository import date is inferred provenance only. QLab 5.6.x
runtime support is not claimed.

## Security hardening status

- PR-1 through PR-4 are implemented and validated locally and against the
  documented QLab 5.5.10 runtime evidence: settings batches are bounded,
  numeric OSC values are wire-format validated, script profiles use canonical
  `scriptSource` rules, and `lightCommandText` analysis is bounded.
- The repository threat model and accepted risks are defined in the root
  [`SECURITY.md`](../../SECURITY.md). The local caller may provide malformed or
  oversized arguments; QLab, `QLAB_HOST`, and the operator are trusted, and a
  hostile same-network process is outside the initial scope.
- UDP source-port filtering is intentionally pending. QLab 5.5.10 packet
  capture could not be completed because macOS capture permissions were
  unavailable. A fake-UDP test for delayed same-address replies is the next
  transport investigation and is separate from source-port authenticity.
- No new schema limits, AppleScript fallback, raw OSC, playback, GO, Dashboard,
  or broad write surface is planned from this security pass without new
  evidence and an explicit compatibility decision.

## Active workorders and release gates

The five active workorders are implementation-local or runtime-pending work;
none is closed by inference during the 0.3.0 preparation:

- [017 — Geometry smooth/defaults](workorders/active/017_geometry_completion_smooth_and_defaults.md): implemented locally; runtime validation pending.
- [019 — Video I/O selection](workorders/active/019_video_io_selection_edit_cues.md): implemented locally; Audio/Mic runtime validation pending.
- [021 — Video audio time and loops](workorders/active/021_video_audio_time_loops.md): implemented locally; runtime validation pending.
- [022 — Audio/Video slice markers](workorders/active/022_slice_markers_audio_video.md): implemented locally; runtime validation pending.
- [029 — Video audio runtime validation](workorders/active/029_video_audio_runtime_validation.md): active runtime validation after MCP restart.

Release gates for this preparation are the 13-tool contract, current docs,
portable Linux CI, packaging checks, and the final post-merge snapshot. No new
QLab runtime probe is part of these gates.

## Locally implemented; runtime validation pending

- [Video audio validation](workorders/active/029_video_audio_runtime_validation.md)
  covers `clockType`, Integrated Fade checkboxes, and bounded channel
  mute/solo candidates.
- Playlist navigation, playback actions, `/shuffle`, deprecated aliases,
  Timeline UI pseudo-properties, and undocumented crossfade curve setters
  remain blocked.
- Any further QLab 5.5 probing must use a disposable workspace, inactive cues,
  explicit UUIDs, reversible changes, and finish with
  running/paused/auditioning `0/0/0`; no GO, playback, raw OSC, panic, or
  deletion.

## Closed

- Group edge runtime validation — QLab 5.5.10 runtime evidence for exact-UUID
  Group `mode 3 -> 6 -> 3`, one-setter timeout/readback handling, structured
  MCP results, child `continueMode` side effects, fresh-token rollback,
  finite and mixed zero/finite Playlist Loop, and complete ordered snapshots
  of `378` direct Wait children. Consumed-token replay is rejected with zero
  setters; isolated fresh-process tests reject old tokens by signature.
  Crossfade requests for `1 s` and `2 s` retained/read back as `3 s` in the
  named QLab 5.5.10 fixture, while an effective duration above the shortest
  child was rejected during dry-run with zero setters. These are observed
  fixture/version results, not a global API minimum. Live MCP restart
  invalidation remains a documented follow-up because no safe restart API was
  available.

- Safe Create lifecycle (Workorder 031) — Create is template-only: it accepts
  no initial properties, sends one `/new` at most, and performs fresh identity,
  health, and structure readback. QLab 5.5.10 runtime proof covers one blank
  anchored Wait: `confirm:createCue:v2`, returned UUID/type/parent/health/
  inactivity, immediate-after order, manual Delete with a fresh token, baseline
  restoration, activity `0/0/0`, and unchanged DMX. Empty-container Create now
  routes Cue Lists through `currentCueListID` plus unanchored `/new`, Groups
  through anchored `/new` plus one `/move`, and Cue Carts through direct
  `/new` row/column placement. Experimental raw-OSC smoke in QLab 5.5.10
  confirmed Group index `0` and Cart request `0,0` with readback `1,1`;
  automatic cleanup and an AppleScript fallback remain outside this closure.
  Structural `created` is separate from operational readiness: healthy,
  broken, warning, or unknown health is returned as information, not treated
  as failed Create. Active-state readback remains a safety failure.

- Sequential Create and recursive Delete — `qlab_create_cues` chains each
  verified UUID into the next `/new` and stops without rollback on the first
  ambiguity. `qlab_delete_cues` can empty a container deepest-first with a
  fresh token and readback while preserving the requested root. Broken or
  warning anchors remain valid structural references when inactive.

- Authenticated request/reply handling uses invocation-owned TCP sessions,
  fresh post-timeout verification sessions, and deterministic cleanup. Packet
  tests and a bounded reversible QLab 5.5.10 proof passed on 2026-07-28 after
  reloading the MCP process: exact workspace/cue UUIDs, dry-run tokens, one
  setter for the candidate and one for rollback, timeout-confirmed fresh
  readback for both setters, baseline restored, and final
  running/paused/auditioning `0/0/0`.
- Group safe editing through existing `qlab_edit_cues` / `group_basic`:
  QLab 5.5 runtime validation covers modes `1`, `2`, `3`, `4`, and `6`; canonical
  Playlist `doLoop`, `doShuffle`, `doCrossfade`, and crossfade duration; common
  Basics `notes`, `flagged`, `preWait`, `postWait`, and `continueMode`
  (`0 -> 1 -> 0`). Mode/Playlist writes use exact UUIDs, fresh mode and child
  snapshots, atomic single-use tokens, one setter, fresh scalar/child readback,
  and fresh-token rollback. Confirmed setter timeouts return
  `updated_with_confirmed_timeouts`; QLab child order, `continueMode`, and
  `postWait` effects are reported and never restored implicitly.
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

Phase 3E was independently runtime validated on `<TEST_TEXT_CUE_NAME>` in the test
workspace. All 3/3 real writes and 3/3 fresh-token rollbacks passed. All 12/12
rejection probes blocked before mutation with `executed_operations=[]`. The
final text, font-size, and alignment baseline was restored exactly; the cue was
healthy and inactive, with global running, paused, and auditioning counts
0/0/0. All six setters timed out, matching fresh readback confirmed each result
as `status="updated"` with warning `setter_timeout_but_readback_matched`, and
no mutating retry occurred. No GO, playback, audition, `/live`, raw OSC, save,
or unrelated mutation was used.

Phase 4C was independently runtime validated on `<TEST_VIDEO_CUE_NAME>`
(`<TEST_VIDEO_CUE_UUID>`) in `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`) with QLab 5.5.10. The only supported
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

Phase 6 was independently runtime validated on `<TEST_VIDEO_CUE_NAME>`
(`<TEST_VIDEO_CUE_UUID>`) in `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`). The supported path is
`Video` exact-UUID, saved-mode, finite-numeric
`videoEffectIndex/0/parameter/inputIntensity` only, with
`confirm:videoFxScalar:v2:`. The happy path changed
`2.6191787554229933 -> 2.7191787554229934`; rollback restored
`2.6191787719726562` within QLab float precision. Rejection probes rejected
fake v2, malformed v1-looking token, changed value, `inputPower`,
`Choose_Effect`, cue-number ref, and multi-property attempts with
`executed_operations=[]`. `inputPower` requires separate proof; `Choose_Effect`
stays out.

Phase 7 was independently runtime validated on `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`) with one healthy inactive cue per type:
`Video` `<TEST_FILL_VIDEO_CUE_NAME>` (`<TEST_FILL_VIDEO_CUE_UUID>`), `Camera`
`<TEST_CAMERA_CUE_NAME>` (`<TEST_CAMERA_CUE_UUID>`), and `Text`
`<TEST_TEXT_CUE_NAME>` (`<TEST_TEXT_CUE_UUID>`). All 6/6 writes and 6/6 fresh-token
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

Phase 7B was independently runtime validated on `<TEST_WORKSPACE_NAME>`
(`<TEST_WORKSPACE_UUID>`) with `Video` `<TEST_VIDEO_CUE_NAME>`
(`<TEST_VIDEO_CUE_UUID>`), `Camera` `<TEST_CAMERA_CUE_NAME>`
(`<TEST_CAMERA_CUE_UUID>`), and `Text` `<TEST_TEXT_CUE_NAME>`
(`<TEST_TEXT_CUE_UUID>`). All 3/3 writes and 3/3 fresh-token
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
`<TEST_WORKSPACE_NAME>` (`<TEST_WORKSPACE_UUID>`) with `Text`
`<TEST_QUATERNION_TEXT_CUE_NAME>` (`<TEST_QUATERNION_TEXT_CUE_UUID>`), `Video`
`<TEST_VIDEO_CUE_NAME>` (`<TEST_VIDEO_CUE_UUID>`), and `Camera`
`<TEST_CAMERA_CUE_NAME>` (`<TEST_CAMERA_CUE_UUID>`). Quaternion writes used
fresh v3 tokens and matching fresh readback; reset actions used fresh reset v1
tokens, executed exactly one `/resetRotation`, and ended with reset quaternion
readback. Final workspace running/paused/auditioning was `0/0/0`; no raw OSC,
playback, `/live`, save, commit, or unrelated mutation was used.

## Runtime-validated additions and remaining boundaries

Public write-tool confirmation boundaries:

- Create is dry-run-first, requires exactly one of `after_cue_id` or
  `parent_container_id`, and uses a dedicated `confirm:createCue:v2` token
  bound to the reviewed workspace structure.
- Edit uses exact per-operation dry-run tokens copied into each update item's
  `confirm_gates`; it has no tool-level token.
- Eligible reviewed Move and Delete dry-runs each return a dedicated tool-level
  `confirm_token`; real execution requires that exact token. Their tokens are
  process-bound and become invalid after an MCP restart.

Utility cue editing (runtime validated and closed):

- only the local `cueTargetID` gate for `Start`, `Stop`, `Pause`, `Load`, `Reset`,
  `Goto`, `Arm`, and `Disarm`, using `confirm:utilityTarget:v1:`
- exact source/target UUIDs only; one inactive source and healthy inactive
  target; initial assignment may clear the source's broken state only when its
  saved target is empty and it has no warning; saved mode; fresh
  baseline/readback; fresh-token rollback; already-targeted or otherwise broken
  sources remain blocked
- initial broken-empty assignment is locally and live covered; the active MCP
  process must be restarted to expose the updated guard to other clients
- Wait and Memo remain Basics-only
- target names/numbers, temporary targets, Reset patch/map targets, target
  mode, actions, `/live`, playback, raw OSC, batch/multi-property writes, and
  save remain blocked
- exact target assignment, fresh readback, fresh-token rollback, and final
  `0/0/0` activity passed; names/numbers/actions and unsupported targets remain
  blocked

Devamp saved configuration (implemented locally; runtime validation pending):

- local `confirm:devamp:v1:` gate for exact-UUID, saved, one-property
  `cueTargetID`, `devampType`, `startNextCueWhenSliceEnds`, and
  `stopTargetWhenSliceEnds` updates
- source and resolved target must be healthy/inactive; targets are exact
  existing `Audio` or `Video` cue UUIDs only
- Stop target requires Start next already enabled; Start next cannot be disabled
  while Stop target is true, avoiding an implicit multi-property change
- fresh baseline/readback and fresh-token rollback are required for closure;
  no new runtime evidence is claimed here. Slices and actions remain blocked.

Network OSC Message (planned-only pending runtime evidence):

- saved `customString` remains planned-only: source/tests can build the
  `confirm:networkOscMessage:v1:` candidate, but no current runtime evidence
  proves the patch classification and readback path for release claims
- `networkPatchID` reassignment remains blocked/planned-only because the tested
  reassignment read back but left the cue broken
- fades and device-description parameters remain planned-only
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

- local implementation exposes `qlab_edit_cues` as the only public cue-edit tool
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
- runtime validation passed on `<TEST_VIDEO_AUDIO_CUE_NAME>`
  (`<TEST_VIDEO_AUDIO_CUE_UUID>`) in `<TEST_WORKSPACE_NAME>`:
  `sliderLevel/0` baseline `0` -> `-1.0` -> fresh readback
  `-1.000009003387651` -> rollback `0`; `sliderLevel/1` previously passed
  with the same write/readback/rollback pattern
- setter timeout is accepted only with warning
  `setter_timeout_but_readback_matched` when fresh readback matches
- token eligibility requires real embedded-audio evidence:
  `numChannelsIn > 0` or non-empty `audioTrackFormats`
- `levels` and `sliderLevels` may be readable on Video cues without embedded
  audio, so they are baseline/readback data only, not evidence gates; this was
  validated on `<TEST_VIDEO_CUE_NAME>`
  (`<TEST_VIDEO_CUE_UUID>`)
- runtime-validated scope: Video only, `sliderLevel/{channel}` only, saved mode, exact UUID,
  one cue, one operation, healthy inactive cue, readable `sliderLevels`,
  finite numeric dB only, fresh token/readback/rollback; `/live`, raw OSC,
  playback, save, batch, multi-property, output names, and `-inf` remain blocked

Video Phase 9B — Video embedded-audio Matrix Crosspoints:

- research confirms `/cue/{cue_number}/levels` is read-only matrix readback and
  `/cue/{cue_number}/level/{inChannel}/{outChannel} {decibel}` is read/write
- `/levels[0]` maps to the top-row slider levels handled by Phase 9A, so first
  Phase 9B scope must reject `inChannel = 0`
- minimal runtime validation passed on `<TEST_VIDEO_AUDIO_CUE_NAME>`
  (`<TEST_VIDEO_AUDIO_CUE_UUID>`) in `<TEST_WORKSPACE_NAME>`:
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
- `gang/{inChannel}/{outChannel}` runtime validation passed on
  `<TEST_VIDEO_AUDIO_CUE_NAME>` (`<TEST_VIDEO_AUDIO_CUE_UUID>`) in
  `<TEST_WORKSPACE_NAME>`:
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

- [`002_close_phase3a_docs.md`](../archive/workorders/completed/002_close_phase3a_docs.md)
- [`003_plan_phase3b_translation.md`](../archive/workorders/completed/003_plan_phase3b_translation.md)
- [`004_implement_phase3c_visual_scalars.md`](../archive/workorders/completed/004_implement_phase3c_visual_scalars.md)
- [`005_implement_phase3d_visual_appearance.md`](../archive/workorders/completed/005_implement_phase3d_visual_appearance.md)
- [`006_implement_phase3e_text_basics.md`](../archive/workorders/completed/006_implement_phase3e_text_basics.md)
- [`007_text_style_and_video_fx_read_plan.md`](workorders/blocked/007_text_style_and_video_fx_read_plan.md)
- [`008_video_fx_real_write_candidate.md`](../archive/workorders/completed/008_video_fx_real_write_candidate.md)
- [`009_video_completion_matrix.md`](../archive/workorders/completed/009_video_completion_matrix.md)
- [`010_video_docs_consistency_cleanup.md`](../archive/workorders/completed/010_video_docs_consistency_cleanup.md)
- [`011_video_fx_scalar_v2_candidate.md`](../archive/workorders/completed/011_video_fx_scalar_v2_candidate.md)
- [`012_geometry_completion_video_camera_text.md`](../archive/workorders/completed/012_geometry_completion_video_camera_text.md)
- [`013_full_geometry_completion_video_camera_text.md`](../archive/workorders/completed/013_full_geometry_completion_video_camera_text.md)
- [`014_rotation_quaternion_shutter_geometry.md`](../archive/workorders/completed/014_rotation_quaternion_shutter_geometry.md)
- [`015_quaternion_geometry_write.md`](../archive/workorders/completed/015_quaternion_geometry_write.md)
- [`016_safe_reset_rotation.md`](../archive/workorders/completed/016_safe_reset_rotation.md)
- [`017_geometry_completion_smooth_and_defaults.md`](workorders/active/017_geometry_completion_smooth_and_defaults.md)
- [`018_blend_mode_audit_and_completion.md`](../archive/workorders/completed/018_blend_mode_audit_and_completion.md)
- [`019_video_io_selection_edit_cues.md`](workorders/active/019_video_io_selection_edit_cues.md)
- [`020_video_embedded_audio_research.md`](../archive/workorders/research/020_video_embedded_audio_research.md)
- [`021_video_audio_time_loops.md`](workorders/active/021_video_audio_time_loops.md)
- [`022_slice_markers_audio_video.md`](workorders/active/022_slice_markers_audio_video.md)
- [`029_video_audio_runtime_validation.md`](workorders/active/029_video_audio_runtime_validation.md)

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
