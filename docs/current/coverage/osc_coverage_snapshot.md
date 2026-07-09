# OSC Coverage Snapshot

Source of truth: `docs/references/qlab_osc_dictionary.md`.

Generated view: `extract_cue_osc_inventory(...)` + `registry_coverage(...)` against
`profile_catalog()`.

The summary table is registry baseline coverage for mutating OSC routes in the
official dictionary. It does not count specialized runtime token exceptions
implemented above the registry gate, such as Text cue `confirm:textBasic:v1:`
exceptions, the closed Phase 4C
`Video` `videoEffectIndex/0/parameter/inputRadius` real write, Phase 6
`inputIntensity`, Phase 7 `fillStage`/`fillStyle`, Phase 7B `layer`, the
Phase 7D local `quaternion` candidate, the Phase 7E local `resetRotation`
action candidate, the Phase 7F local `smooth` candidate, and the Phase 8A local
cue I/O ID candidates, and the Phase 8B local Video embedded-audio Time & Loops
candidates, and the Phase 8C local Video slice marker candidates. Those
exceptions are listed in Current Invariants.

## Summary

| Section | Real write | Gated | Planned only | Missing |
|---|---:|---:|---:|---:|
| common/global cue properties | 15 | 21 | 0 | 0 |
| Group/List/Cart | 7 | 0 | 6 | 0 |
| Audio | 6 | 65 | 0 | 0 |
| Mic | 3 | 4 | 0 | 0 |
| Video | 0 | 79 | 0 | 0 |
| Camera | 2 | 4 | 0 | 0 |
| Text | 0 | 19 | 0 | 0 |
| Light | 0 | 11 | 0 | 0 |
| Fade | 0 | 25 | 0 | 0 |
| Network | 0 | 20 | 0 | 0 |
| MIDI | 0 | 29 | 0 | 0 |
| MIDI File | 1 | 4 | 0 | 0 |
| Timecode | 3 | 6 | 2 | 0 |
| Reset | 0 | 3 | 0 | 0 |
| Devamp | 0 | 3 | 0 | 0 |
| Script | 0 | 1 | 0 | 0 |

## Current Invariants

- `missing` must stay zero for mutating cue OSC routes parsed from the official dictionary.
- `scriptSource` and `scriptText` stay `not_editable_by_osc`; `compileSource` is gated by `script_compile`.
- `duration` and `tempDuration` are real-write capable only when `allowsEditingDuration=true`.
- `playlist/*` real writes require Group mode `6` (Playlist mode).
- `cueTargetID`, `cueTargetNumber`, and temporary target refs require target resolution before real writes.
- `cueTargetName` remains blocked for real writes; callers must use `cueTargetID` or `cueTargetNumber`.
- `Mic.channelOffset` is gated by `patch_routing` until input patch bounds validation exists.
- Dangerous output families remain gated: audio output, patch routing, video visual/effects, text rich format, fade targets, light output, network output, MIDI output, script compile.
- Video Phases 3A–3E expose only their documented token-gated scalar/Text
  setters. The Text expansion gates `Text`-only saved writes under
  `confirm:textBasic:v1:` for runtime-confirmed `text`, `fixedWidth`,
  `text/format/alignment`, `text/format/fontName`, `text/format/fontSize`,
  `text/format/lineSpacing`, and `text/format/color`.
  `text/format/backgroundColor`, `text/format/shadowColor`,
  `text/format/strikethroughColor`, and `text/format/underlineColor` stay
  planned-only/runtime-blocked because QLab did not expose reliable readable
  baseline/readback on the safe Text cue.
  Phase 3F Text Style candidates are blocked
  because QLab 5.5.10 did not return reliable fresh baselines/readback for
  shadow offset/blur and decoration style routes; no `confirm:textStyle:v1:`
  token is emitted. Phase 4C exposes one runtime-validated Video FX scalar
  exception: `Video`, exact cue UUID, saved mode,
  `videoEffectIndex/0/parameter/inputRadius`, finite numeric scalar only.
- Phase 3D `blendMode` is a Video FX tab control but remains a visual appearance
  write, not a Video FX parameter write. OSC uses
  `/cue/{cue_number}/blendMode {string}` with the full QLab blend mode name from
  the Parameter Reference. MCP keeps it under `confirm:videoAppearance:v1:`;
  only exact official strings are accepted. Lowercase aliases, trimmed values,
  partial names, numeric enum values, and Video FX scalar tokens are not
  accepted.
- `fileTarget`, videoInputPatchName/Number, Workspace Video, and all Video FX
  real writes remain blocked except the Phase 4C `inputRadius` exception and
  the Phase 6 `inputIntensity` exception.
- Video FX dry-run planning is limited to enabled state and existing scalar
  parameters by exact name/index. QLab 5.5.10 flat effect payload keys are
  treated as parameter-like fields for index dry-runs. The closed Phase 4C
  `inputRadius` candidate emits `confirm:videoFxScalar:v1:` and may execute a
  single saved setter. The closed Phase 6 `inputIntensity` candidate emits
  `confirm:videoFxScalar:v2:` and may execute one saved setter for `Video`
  exact cue UUID, `video_basic`, `videoEffectIndex/0/parameter/inputIntensity`,
  finite numeric scalar only. Other FX plans emit no token and execute no setter.
- Phase 4C runtime validation used QLab 5.5.10, changed `inputRadius` `10 -> 11`,
  rolled back `11 -> 10` with a fresh token, and accepted QLab setter timeout
  only because fresh readback matched with `setter_timeout_but_readback_matched`.
  The stale/used-token probe rejected before mutation via no-op baseline rather
  than an explicit consumed-token diagnostic.
- Phase 5 is docs/audit only. Phase 6 is runtime validated and closed for one
  path above the registry gate: `Video` exact-UUID saved
  `videoEffectIndex/0/parameter/inputIntensity` with
  `confirm:videoFxScalar:v2:`.
- Phase 6 runtime validation used `mcp_prueba.qlab5`
  (`95F0A03D-140E-4673-974A-E76748EBB023`) and `v11 dorado.png`
  (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`). The happy path changed
  `inputIntensity` from `2.6191787554229933` to `2.7191787554229934`; the setter
  timeout was accepted only because fresh readback matched
  `2.7191786766052246`. Rollback used a fresh token and restored
  `2.6191787719726562` within QLab float precision. Workspace
  running/paused/auditioning was `0/0/0`; pre-existing broken cues outside the
  target were not blockers.
- Phase 6 rejection sweep rejected fake v2 token, malformed v1-looking token,
  valid v2 token with changed value, valid v2 token for `inputPower`, valid v2
  token for `Choose_Effect`, cue ref `v11` instead of UUID, and a multi-property
  call. All rejection probes had `executed_operations=[]`, and final readback
  remained baseline exactly.
- Phase 7 is runtime validated and closed above the registry gate. It emits
  `confirm:videoGeometry:v1:` for `fillStage` and `fillStyle` on `Video`,
  `Camera`, and `Text` cues only when dry-run sees a readable valid baseline.
  Real write is saved-mode, exact-UUID, one cue, one property, fresh-token only,
  with fresh readback and fresh-token rollback required.
- Phase 7 runtime validation used `mcp_prueba.qlab5`
  (`95F0A03D-140E-4673-974A-E76748EBB023`) with `Video` `Fill stage`
  (`BF24AB14-43D2-43BD-BBE7-1BC87DDB5107`), `Camera` `Camare1`
  (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`), and `Text` `Text1`
  (`193FB551-7985-4381-9C2D-CF4218C03FB9`). All `fillStage`/`fillStyle` writes
  and fresh-token rollbacks passed, final baselines were restored, and workspace
  running/paused counts were `0/0`.
- Phase 7 rejection probes blocked cue-number real write, `/live`,
  multi-property real write, `rotation`, and `shutterTop` before mutation/OSC as
  applicable. QLab setter timeout was accepted only when fresh readback matched
  with `setter_timeout_but_readback_matched`; no mutating retry occurred.
- Phase 7B is runtime validated and closed above the registry gate for `layer`
  only. It exposes `layer` as a saved-mode exact-UUID one-cue/one-property
  real-write candidate for `Video`, `Camera`, and `Text`, with integer
  `0..1000` validation and `confirm:videoGeometry:v2:`. Existing
  `confirm:videoGeometry:v1:` remains valid only for `fillStage` and
  `fillStyle`.
- Phase 7B runtime validation used `mcp_prueba.qlab5`
  (`95F0A03D-140E-4673-974A-E76748EBB023`) with `Video` `v11 dorado.png`
  (`680CB8B6-CA66-4D15-AC15-0A92FC3E89FE`), `Camera` `v6 Camare1`
  (`EE632A41-FB3B-4CFA-BC27-00A4CEC54692`), and `Text` `v1 Text1`
  (`193FB551-7985-4381-9C2D-CF4218C03FB9`). Each cue passed
  `1000 -> 11 -> 1000` with fresh-token rollback.
- All Phase 7B real writes and rollbacks returned
  `setter_timeout_but_readback_matched`; each was accepted only because fresh
  readback matched, with no mutating retry. Rejection probes blocked fake v2
  token, v1 geometry token for `layer`, cue number, and `/live` before setter
  with `executed_operations=[]`. Final workspace running/paused/auditioning was
  `0/0/0`; unrelated pre-existing broken cues were not blockers.
- Phase 7B keeps top/bottom layer aliases blocked because no documented cue OSC
  route exists; numeric `layer` is the only ordering write candidate. It keeps
  `origin` blocked as deprecated `anchor` alias, `rotation` blocked as Fade cue
  geometry and shutters blocked because no QLab 5 cue OSC route was found.
  Stage/region/surface/warping/control-point writes stay blocked pending
  dedicated routing and rollback proof. `quaternion` moved to Phase 7D and
  `resetRotation` moved to Phase 7E.
- Phase 7C audited rotation, quaternion, resetRotation, and shutter geometry.
  `rotation`/`rotationType` remain Fade/single-axis geometry, not direct
  Video/Camera/Text real-write candidates. `quaternion` has dictionary read and
  write routes and is now a Phase 7D local real-write candidate only.
  `rotate/x`, `rotate/y`, and `rotate/z` are relative action-style quaternion
  changes and stay blocked, including `/live` variants. `resetRotation` is an
  action/button with no scalar baseline; Phase 7E now exposes only the
  protected action form with quaternion backup/readback/rollback. Shutters stay
  blocked because no direct QLab 5 cue OSC route was found in the local
  dictionary.
- Phase 7D emits `confirm:videoGeometry:v3:` only for saved-mode exact-UUID
  one-cue/one-property `quaternion` writes on `Video`, `Camera`, and `Text`.
  The value must be an array of exactly four finite non-boolean numbers. v1/v2
  geometry tokens do not authorize `quaternion`, and v3 does not authorize
  `fillStage`, `fillStyle`, `layer`, `resetRotation`, or any other property.
  Runtime validation is closed for `Video`, `Camera`, and `Text`.
- Phase 7E emits `confirm:videoGeometryReset:v1:` only for saved-mode
  exact-UUID one-cue/one-action `resetRotation` on `Video`, `Camera`, and
  `Text`. It requires fresh readable baseline `quaternion`, calls
  `/resetRotation` once, verifies fresh post-action quaternion readback, and
  rolls back by writing the original baseline quaternion with a fresh v3 token.
  `resetRotation: false`, non-boolean values, cue numbers, `/live`, batch,
  multi-property, fake tokens, and v1/v2/v3 geometry tokens are rejected before
  action. Runtime validation is closed for `Video`, `Camera`, and `Text`.
- Phase 7F emits `confirm:videoGeometry:v4:` only for saved-mode exact-UUID
  one-cue/one-property `smooth` writes on `Video`, `Camera`, and `Text`. The
  value must be boolean. v1/v2/v3 geometry tokens do not authorize `smooth`,
  and v4 does not authorize `fillStage`, `fillStyle`, `layer`, `quaternion`,
  `resetRotation`, or any other property. Runtime validation is required before
  Phase 7F closure.
- Phase 8A emits `confirm:videoIO:v1:` only for saved-mode exact-UUID
  one-cue/one-property cue-level I/O ID selection. `Video` supports `stageID`
  and `audioOutputPatchID`; `Camera` supports `stageID`, `audioOutputPatchID`,
  `videoInputPatchID`, and `audioInputPatchID`; `Text` supports `stageID`.
  Values must be non-empty string IDs. Name/number refs, deprecated
  `cameraPatch`, unpatch values, workspace stage/patch definition edits, `/live`,
  batch, multi-property, raw OSC, playback/show-control, and save remain
  blocked. Unknown IDs cannot be reported as success because post-write fresh
  readback must match the requested ID. Existing but currently disconnected
  stages are allowed for `stageID`; results warn with `stage_route_disconnected`
  when settings expose disconnected route/device metadata. If that write leaves
  the cue broken, only an exact same-cue `stageID` rollback to the recorded
  baseline is allowed; arbitrary broken-cue edits remain blocked.
- Phase 8B emits `confirm:videoAudioTime:v1:` only for saved-mode exact-UUID
  one-cue/one-property `Video` `video_basic` Time & Loops writes:
  `startTime`, `endTime`, `playCount`, `infiniteLoop`, `rate`,
  `preservePitch`, and official Hold at End route `holdLastFrame`. Audio timing
  routes require readable embedded-audio evidence (`audioTrackFormats`,
  `numChannelsIn`, or `levels`); `holdLastFrame` is Video-only and does not
  itself prove audio. Values are strict scalar/boolean types: finite
  non-negative start/end times, positive integer play count, finite
  `0.03..33.0` rate, and booleans for the flags. `preservePitch` accepts only
  boolean user input, but QLab readback `0`/`1` is normalized internally for
  baseline, verification, and rollback. `NaN`, infinity, strings,
  wrong token families, cue name/number real writes, `/live`, batch,
  multi-property, raw OSC, playback/show-control, Integrated Fade, Linear
  Curve, slices/vamps/devamps, levels, objects, Audio FX, Trim, fileTarget, and
  save remain blocked. Setter timeout or QLab setter error is warning-confirmed
  success only when fresh readback matches. Runtime validation is required
  before Phase 8B closure.
- Phase 9A emits `confirm:videoAudioLevels:v1:` only for saved-mode exact-UUID
  one-cue/one-operation `Video` `video_basic.sliderLevel/{channel}` writes.
  Runtime validation passed on `v5 Con slices`, including rollback. Embedded
  audio evidence for this gate is now only `numChannelsIn > 0` or non-empty
  `audioTrackFormats`; `levels` and `sliderLevels` are not evidence because
  `v11 dorado.png` exposed them with `numChannelsIn = 0` and
  `audioTrackFormats = {}`. They remain required only for baseline/readback.
  Phase 9A accepts finite numeric dB only and blocks `-inf`, output names,
  `/live`, raw OSC, playback/show-control, save, batch, and multi-property.
- Phase 9B is runtime validated for one saved
  `level/{inChannel}/{outChannel}` matrix crosspoint using
  `confirm:videoAudioMatrix:v1:`. Row `0` remains Phase 9A territory because
  `/levels[0]` is equivalent to `sliderLevels`. Broad matrix editing, `/live`,
  names, `-inf`, mute/solo/default/silent actions, Objects, Trim, Audio FX,
  Audio Maps, and routing/patch editor writes remain blocked.
- Phase 9C `gang/{inChannel}/{outChannel}` is runtime validated for one saved
  metadata crosspoint using `confirm:videoAudioLevelMeta:v1:`. Validation
  proved empty baseline rollback: `gang/1/0` `"" -> "MCPG" -> ""` on
  `v5 Con slices`. Scope remains Video-only, exact UUID, one cue, one
  operation, healthy inactive cue, real embedded-audio evidence, integer
  indexes, row `1..numChannelsIn`, no output names, no control characters, no
  `/live`, no batch, and no multi-property.
- Video `clockType` is locally implemented with
  `confirm:videoClockType:v1:` for saved exact-UUID one-cue/one-operation
  Video writes with strict `audio`/`video` values, fresh readback, and rollback
  plan. It no longer requires embedded-audio evidence; the OSC Dictionary
  documents `/cue/{cue_number}/clockType` as a direct Video clock route.
  Runtime validation of the relaxed no-audio gate is pending after MCP restart.
- Video Integrated Fade `doFade` and `lockFadeToCue` are locally implemented
  with `confirm:videoIntegratedFade:v1:` for saved exact-UUID
  one-cue/one-operation Video writes with real embedded-audio evidence, strict
  booleans, fresh readback, and rollback plan. Runtime validation is pending.
- Internal Integrated Fade curve/shape/point editing remains blocked. No
  documented Audio/Video Integrated Fade OSC route was found beyond `doFade`
  and `lockFadeToCue`; `fadeEntries`/`fadeType`/`fadeFrom`/`fadeTo` stay out of
  scope because they are documented under Fade/Network cue shape/path behavior,
  not this internal envelope.
- `setDefaultLevels` and `setSilentLevels` stay planned-only. QLab documents
  both as actions, but the MCP does not yet have a proven complete rollback
  contract for all affected saved level values.
- Phase 8C exposes Audio/Video `sliceMarkers` readback in cue detail profiles
  using a canonical slice read path shared with write dry-run. Missing
  Audio/Video `sliceMarkers` is normalized to `[]` only after the slice route
  was intentionally queried, and unqueried profiles no longer invent empty
  marker state. MCP emits `confirm:videoSlices:v1:` only for saved-mode
  exact-UUID one-cue, one-operation/property `Video` `video_basic` slice writes:
  `sliceMarker/{index}/time`, `sliceMarker/{index}/playCount`,
  `addSliceMarker`, `deleteSliceMarker/{index}`, `deleteSliceMarkers`, and
  `lastSlicePlayCount`.
  Real writes require a
  healthy inactive Video cue, fresh readable baseline, valid existing marker
  index where applicable, exact fresh readback, and fresh-token rollback.
  Missing Video `sliceMarkers` is treated as `[]`
  only for safe first-marker add; edit/delete on empty baseline rejects.
  `deleteSliceMarkers` requires a non-empty baseline and rollback by re-adding
  all captured markers in order; omitted post-delete `sliceMarkers` readback is
  accepted as `[]` only when empty readback was expected. `playCount` accepts
  positive integers and
  `-1`; `0`, floats, strings, booleans, null, lists, and dictionaries are
  rejected. Marker times must be finite, in known cue bounds, and at least
  `0.05s` from other markers. Audio/Camera real writes, combined
  `/sliceMarker/{index}`, `lastSliceInfiniteLoop`, vamps/devamps, `/live`,
  batch, multi-property, raw OSC, playback/show-control, and save remain
  blocked. Exact-time copy is the selected future V5/V8 model; proportional
  timing copy is not implemented. Runtime validation is required before Phase
  8C closure.
- No official OSC reset action was found for crop, translation, scale, anchor,
  or opacity. Synthetic reset actions for those defaults remain future-only
  until a separate token family, multi-field baseline/readback, rollback, and
  runtime validation plan exists.
- `inputPower`, `Choose_Effect`, all other params, Camera/Text FX, name
  targeting, enabled/disabled, add/delete/move/reorder, aggregate params,
  color/structured/string/enum/list/dict values, `/live`, cue-number real
  writes, batch/multi-property, Workspace Video, stage/route/surface/patch
  definition edits, name/number I/O refs, unpatch, `fileTarget`, rotation,
  quaternion outside Phase 7D, resetRotation outside
  Phase 7E, smooth outside Phase 7F, Video audio time outside Phase 8B, slice
  marker writes outside Phase 8C, shutters,
  warping/control points, and playback/show-control remain blocked.

## Gate Map

| Gate | Families |
|---|---|
| `audio_output` | Audio levels, mute/solo, integrated fade controls |
| `patch_routing` | File/patch/audio-map/MIDI/network target routing and Mic channel offset |
| `slice_editing` | Audio slice marker creation/deletion/editing |
| `spatial_audio` | Audio object naming, positions, spread, object levels |
| `video_visual` | Geometry, crop, stage, region, surface/patch visual changes |
| `video_effects` | Video effect add/delete/move/enabled/parameters |
| `text_rich_format` | Text format, colors, font pair, decoration, shadow |
| `fade_targets` | Fade level/geometry/target behavior |
| `light_output` | Light command text, setLight, sort/prune/collate actions |
| `network_output` | Network payload and parameter fade/value edits |
| `midi_output` | MIDI bytes, MSC/timecode fields, sysex/raw payloads |
| `target_resolution` | Cue target/reset/devamp target behavior |
| `cue_behavior` | Ducking, second trigger, timecode trigger, fade-and-stop |
| `script_compile` | Script compile action only |
| `deprecated_osc` | Deprecated aliases retained for planning/audit |

## Regenerate

```bash
PYTHONPATH=src .venv/bin/python - <<'PY'
from pathlib import Path
from qlab_mcp.write.osc_inventory import extract_cue_osc_inventory, registry_coverage, coverage_summary
from qlab_mcp.write.registry import profile_catalog

root = Path.cwd()
dictionary = root / "docs" / "references" / "qlab_osc_dictionary.md"
coverage = registry_coverage(extract_cue_osc_inventory(dictionary.read_text()), profile_catalog())
print(coverage_summary(coverage))
print([entry for entry in coverage if entry["registry_status"] == "missing"])
PY
```
