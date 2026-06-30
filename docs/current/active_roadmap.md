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

## Safety boundary

Phase 3E, Phase 4C, Phase 6, and Phase 7 are runtime validated and closed.
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
  `fillStage` and `fillStyle` on `Video`, `Camera`, and `Text`
- `fileTarget`, camera/video-input patch, rotation, quaternion, resetRotation,
  and shutter writes
- rich text format, font name, text/background/shadow colors, aggregate shadow
  offset, `doOpacity`, and clock-type real writes
- batch and multi-property Video-family real writes

Phase 6 is closed only for the exact `inputIntensity` scalar path above. It
does not authorize `inputPower`, `Choose_Effect`, any other parameter,
Camera/Text FX, name targeting, enabled/disabled, add/delete/move/reorder,
aggregate params, color/structured/string/enum/list/dict values, cue-number real
writes, batch/multi-property, `/live`, Workspace Video, stages/routes/surfaces,
patches, `fileTarget`, warping/control points, or playback/show-control.
