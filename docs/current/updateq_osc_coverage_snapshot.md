# UpdateQ OSC Coverage Snapshot

Source of truth: `docs/references/qlab_osc_dictionary.md`.

Generated view: `extract_cue_osc_inventory(...)` + `registry_coverage(...)` against
`profile_catalog()`.

The summary table is registry baseline coverage for mutating OSC routes in the
official dictionary. It does not count specialized runtime token exceptions
implemented above the registry gate, such as the closed Phase 4C
`Video` `videoEffectIndex/0/parameter/inputRadius` real write, Phase 6
`inputIntensity`, and Phase 7 `fillStage`/`fillStyle`. Those exceptions are
listed in Current Invariants.

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
  setters. Phase 3F Text Style candidates are blocked because QLab 5.5.10 did
  not return reliable fresh baselines/readback; no `confirm:textStyle:v1:` token
  is emitted. Phase 4C exposes one runtime-validated Video FX scalar exception:
  `Video`, exact cue UUID, saved mode, `videoEffectIndex/0/parameter/inputRadius`,
  finite numeric scalar only.
- `fileTarget`, videoInputPatchName/Number/ID, Workspace Video, and all Video FX
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
- `inputPower`, `Choose_Effect`, all other params, Camera/Text FX, name
  targeting, enabled/disabled, add/delete/move/reorder, aggregate params,
  color/structured/string/enum/list/dict values, `/live`, cue-number real
  writes, batch/multi-property, Workspace Video, stages/routes/surfaces, patches,
  `fileTarget`, rotation, quaternion, resetRotation, shutters,
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
