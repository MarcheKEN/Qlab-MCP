# Active Roadmap

Status: 2026-06-28

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

## In local validation

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

Video Phase 8A — Edit Cues and cue-level I/O selection:

- local implementation exposes preferred `qlab_edit_cues` while keeping
  `qlab_update_cues` as a compatibility alias
- adds saved ID-only I/O real-write candidates using `confirm:videoIO:v1:`
- `Video`: `stageID`, `audioOutputPatchID`
- `Camera`: `stageID`, `audioOutputPatchID`, `videoInputPatchID`,
  `audioInputPatchID`
- `Text`: `stageID`
- exact cue UUID only, one cue, one property, saved mode, healthy inactive cue,
  fresh baseline, fresh token, and fresh readback required
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
- Integrated Fade, Linear Curve, `doFade`, `lockFadeToCue`, slices/vamps/
  devamps, levels, objects, Audio FX, Trim, `/live`, raw OSC, playback, batch,
  multi-property, and save remain blocked
- runtime validation is required before closure

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
  `lastSliceInfiniteLoop`, vamps/devamps, `/live`, batch, multi-property, raw
  OSC, playback, and save remain blocked
- runtime validation is required before closure

See:

- `workorders/002_close_phase3a_docs.md`
- `workorders/003_plan_phase3b_translation.md`
- `workorders/004_implement_phase3c_visual_scalars.md`
- `workorders/005_implement_phase3d_visual_appearance.md`
- `workorders/006_implement_phase3e_text_basics.md`
- `workorders/007_text_style_and_video_fx_read_plan.md`
- `workorders/008_video_fx_real_write_candidate.md`
- `workorders/009_video_completion_matrix.md`
- `workorders/010_video_docs_consistency_cleanup.md`
- `workorders/011_video_fx_scalar_v2_candidate.md`
- `workorders/012_geometry_completion_video_camera_text.md`
- `workorders/013_full_geometry_completion_video_camera_text.md`
- `workorders/014_rotation_quaternion_shutter_geometry.md`
- `workorders/015_quaternion_geometry_write.md`
- `workorders/016_safe_reset_rotation.md`
- `workorders/017_geometry_completion_smooth_and_defaults.md`
- `workorders/018_blend_mode_audit_and_completion.md`
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
- rich text format, font name, text/background/shadow colors, aggregate shadow
  offset, `doOpacity`, and clock-type real writes
- batch and multi-property Video-family real writes

Phase 6 is closed only for the exact `inputIntensity` scalar path above. It
does not authorize `inputPower`, `Choose_Effect`, any other parameter,
Camera/Text FX, name targeting, enabled/disabled, add/delete/move/reorder,
aggregate params, color/structured/string/enum/list/dict values, cue-number real
writes, batch/multi-property, `/live`, Workspace Video, stages/routes/surfaces,
patches, `fileTarget`, warping/control points, or playback/show-control.
