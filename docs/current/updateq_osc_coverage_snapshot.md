# UpdateQ OSC Coverage Snapshot

Source of truth: `docs/references/qlab_osc_dictionary.md`.

Generated view: `extract_cue_osc_inventory(...)` + `registry_coverage(...)` against
`profile_catalog()`.

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
- Video Phase 1 keeps every Video/Text visual setter dry-run only; generic confirm tokens cannot authorize real writes.
- Video Phase 1 rejects fileTarget, videoInputPatchName/Number/ID, and every Video FX mutation before dry-run planning or any OSC read/write.

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
