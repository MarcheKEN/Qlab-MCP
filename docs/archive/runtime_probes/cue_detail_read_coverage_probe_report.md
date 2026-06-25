# Cue Detail Read Coverage Probe Report

Date: 2026-06-17

Workspace under test: `mcp_prueba.qlab5`

Workspace ID: `95F0A03D-140E-4673-974A-E76748EBB023`

QLab version: 5.5.10

Safety scope: read-only cue inspection plus one `qlab_update_cues(dry_run=true)`
planning batch. No GO, playback, stop, panic, audition, preview, raw OSC, or
real writes were used. Max observed concurrency was 3.

## Executive Summary

`qlab_get_cue_details` was tested against one representative cue for each
available cue type in the fixture workspace: 20 cue types total.

All requested exposed profiles succeeded for all representatives:

- `basic_safe`
- `auto`
- `basic`
- `technical`
- `health`
- `timing`
- `status`
- `targets`
- `group`
- `editable`
- `full`
- `full_sensitive`
- `inspector_safe`
- `exhaustive`

No schema errors, allowlist rejections, timeouts, cue-incompatibility failures,
missing-media failures, or missing-hardware failures occurred during profile
reads. Cue-specific limitations were represented as safe partial data, empty
type-specific sections, broken cue state, or explicit coverage gaps.

Best practical default profiles:

- `basic_safe` / `basic`: compact identity and status.
- `auto`: safe type-aware cue details.
- `inspector_safe`: broader non-sensitive Inspector-style context.
- `editable`: update capability discovery only; it does not imply writes are
  enabled.
- `exhaustive`: deepest allowlisted read-only profile, but still not full OSC
  dictionary parity.

`exhaustive` reported coverage metadata from the QLab OSC dictionary:

- 509 readable routes considered.
- 290 allowlisted properties.
- 192 total gaps.
- Gap classes: 90 indexed read gaps, 66 live-value omissions, 33 read gaps, and
  3 runtime read gaps.

MIDI, MIDI File, Timecode, Light, Network, and other hardware-dependent or
external-system-dependent behaviors were not fully testable in this fixture.
They were inspected only through safe read profiles and dry-run planning.

Final baseline matched the initial operational state: 30 scanned cue items, 9
broken, 0 warnings, 2 flagged, 1 disarmed, 0 running, and 0 paused.

## Exposed Tools

| Tool | Purpose | Used |
| --- | --- | --- |
| `qlab_check_connection` | Verify QLab reachability, workspace choices, read access, passcode state, connect scopes, and Edit/Show mode. | Yes |
| `qlab_get_workspace_overview` | Read bounded workspace map and cue index. | Yes |
| `qlab_get_workspace_status` | Read compact operational status from safe documented reads. | Yes |
| `qlab_get_workspace_settings` | Read settings summary or focused details. | Not needed for this cue-detail probe |
| `qlab_get_workspace_setting_details` | Backwards-compatible single settings detail wrapper. | Not needed |
| `qlab_query_cues` | Search cues by type/state/targets/health. | Yes |
| `qlab_get_cue_details` | Read single or batch cue details by profile. | Yes |
| `qlab_check_write_readiness` | Check write-mode readiness without mutation. | Not needed |
| `qlab_create_cue` | Dry-run or create one blank allowlisted cue. | No |
| `qlab_update_cues` | Dry-run or update concrete cues through editing registry. | Dry-run only |

## Baseline

`qlab_check_connection` without a workspace ID was ambiguous because two QLab
workspaces were open. All probe calls used the explicit `mcp_prueba.qlab5`
workspace ID above.

| Metric | Initial | Final |
| --- | ---: | ---: |
| Cue items scanned | 30 | 30 |
| Cue types observed | 20 | 20 |
| Broken cues | 9 | 9 |
| Warnings | 0 | 0 |
| Running cues | 0 | 0 |
| Paused cues | 0 | 0 |
| Disarmed cues | 1 | 1 |
| Flagged cues | 2 | 2 |
| Settings errors in status summary | 0 | 0 |

Observed cue type counts:

| Type | Count |
| --- | ---: |
| Cue List | 1 |
| Audio | 2 |
| Mic | 1 |
| Camera | 1 |
| Text | 1 |
| MIDI File | 1 |
| MIDI | 1 |
| Timecode | 1 |
| Devamp | 1 |
| Target | 1 |
| Video | 2 |
| Group | 7 |
| Fade | 2 |
| Light | 1 |
| Network | 1 |
| Memo | 1 |
| Script | 1 |
| Pause | 1 |
| Reset | 2 |
| Start | 1 |

Final status confirmed `running_count=0` and `paused_count=0`. The dry-run
batch reported `updated_count=0` and `executed_operations=[]`.

## Cue Type Matrix

| Type | Cue ref / number | Name / display | uniqueID | State | Targets | Testability |
| --- | --- | --- | --- | --- | --- | --- |
| Cue List | empty number | `Main Cue List` | `CC4DF6DC-175E-4346-92A1-43CCB6062390` | broken=true | no file/cue target | Readable as list root; broken state inherited/reported by QLab. |
| Audio | `2` | `AUDIO_VALID` | `9AFA9C07-2434-4C3A-ABD9-ED1EC6428509` | ok | file target present | Fully readable for fixture purposes; sensitive profiles expose local media path. |
| Mic | `1.5` | `(Untitled Mic Cue)` | `1B704EC9-7F54-4A44-AFBE-9D2B4B7D1DC2` | ok | no file/cue target | Readable; hardware input behavior not exercised. |
| Camera | `1.6` | `(Untitled Camera Cue)` | `3F05AE34-21EE-46CF-9668-5536CD6DCAC4` | ok | no file/cue target | Readable; camera hardware behavior not exercised. |
| Text | `1.7` | `Text` | `084D2D69-FC8C-4F40-9EFB-AD572E11E672` | ok | no file/cue target | Readable; text and stage fields exposed in type-specific profiles. |
| MIDI File | `1.8` | `(Untitled MIDI File Cue)` | `A2B5F72B-1407-4682-9C10-8D5B25E21565` | broken=true | file target present | Not fully testable; broken media/hardware-dependent cue. |
| MIDI | `1.9` | `MIDI note on` | `66357970-7FDB-4867-A960-D2E3FA79903B` | broken=true | no file/cue target | Not fully testable; no MIDI patch/hardware validation. |
| Timecode | `1.95` | `1:00:00:00` | `C21CDCC0-CC71-44CC-A003-241840277837` | broken=true | no file/cue target | Not fully testable; timing fields readable, timecode output not exercised. |
| Devamp | `1.96` | `devamp AUDIO_VALID` | `755C11D0-5605-4B8C-B9C1-F4E21F13A138` | ok | targets Audio `2` | Readable target relationship. |
| Target | `1.97` | `(Untitled Target Cue)` | `1F1F5E68-8854-4913-885D-6D2DB9E4ED61` | broken=true | `hasCueTargets=true`, empty target ID/number | Not fully testable; cue reports missing/broken target. |
| Video | `4` | `VIDEO_VALID` | `01538A14-D86A-4F74-8467-ED7F24D2299B` | ok | file target present | Fully readable for fixture purposes; sensitive profiles expose local media path. |
| Group | `5` | `GROUP_NESTED_LEVEL_1` | `619A9B19-7769-4F4E-A107-A8001B34863D` | ok | no file/cue target | Readable group/list fields. |
| Fade | `10` | `FADE_VALID_TARGET` | `97043637-DF4B-44E3-BB36-D29366268926` | flagged=true | targets Audio `2` | Readable; high-risk target/fade edits dry-run only. |
| Light | `12` | `LIGHT_DISARMED_BROKEN` | `A1B43231-CA7A-466A-A7E6-C1974D875D2A` | broken=true, armed=false | no file/cue target | Not fully testable; light output/hardware not exercised. |
| Network | `13` | `NETWORK_VALID` | `BA42C1B4-5DDE-44EC-9C49-3A3B295D697D` | ok | network patch present | Not fully testable; external network output not sent. |
| Memo | `14` | `MEMO_LONG_TEXT` | `7E9D9152-A0E6-41AD-8D48-131521028B24` | ok | no file/cue target | Readable; long text may be truncated by compact profiles. |
| Script | `15` | `SCRIPT_SAFE_HIDDEN` | `EE71F73E-804C-4D89-9302-6D98E7140D64` | ok | no file/cue target | Readable; script source exposed only by sensitive/deep profiles and not executed. |
| Pause | emoji number | `UNICODE_EMOJI_...` | `8E1451DF-8648-4E46-AFFF-4BA95501291F` | ok | targets Memo `14` | Readable target relationship and Unicode number/name behavior. |
| Reset | `NBSP_A B_TEST` | `NBSP_A B` | `E2F7CFB6-C52D-4DFF-9A89-7CEEF9221FE6` | ok | targets Pause cue | Readable target relationship and spacing edge case. |
| Start | `tuu` | `LONG_NOTES` | `562834C6-25FD-4B43-B73D-5DAB2C177349` | ok | targets Reset cue | Readable target relationship; long notes require sensitive/deep profile. |

Type-specific fields observed in `auto`, `inspector_safe`, `full`,
`full_sensitive`, or `exhaustive`:

| Type | Type-specific fields observed |
| --- | --- |
| Cue List | Cart/list playback-position style fields, playlist/list mode fields, playhead context, child flag state. |
| Audio | Audio output patch name/number/ID; deeper profiles add audio levels/control details and media-path context where sensitive profile permits. |
| Mic | Audio input/output patch context where available. |
| Camera | Stage, video input patch, geometry, translation, scale, opacity, and video-style visual fields. |
| Text | Text content, output size, stage/geometry, translation, scale, opacity, and text visual fields. |
| MIDI File | MIDI file target presence and MIDI patch-style fields; fixture cue remains broken and not fully testable. |
| MIDI | MIDI patch name/number/ID-style fields; fixture has no usable MIDI patch and remains broken. |
| Timecode | Output type, start/end time, frame rate, LTC channel, audio output patch, and MIDI patch fields. |
| Devamp | Cue target ID/number and target relationship fields. |
| Target | Cue target ID/number, temp/current target fields; fixture has empty target refs and broken state. |
| Video | Stage, route/input patch context, dimensions, duration, translation, scale, opacity, and video effect fields. |
| Group | Group mode and list/cart/playlist fields. |
| Fade | Target mode, cue target ID/number, fade mode, level/geometry booleans, path height/width, and stop-target behavior. |
| Light | Light command text, collation settings, and subcontroller fields. |
| Network | Network patch name/number/ID, custom message string, parameter values, and message error fields. |
| Memo | No special safe type-specific fields beyond text/notes in sensitive or deep profiles. |
| Script | Script source in sensitive/deep profiles; no execution performed. |
| Pause | Cue target ID/number and temp/current target fields. |
| Reset | Cue target ID/number and temp/current target fields. |
| Start | Cue target ID/number and temp/current target fields. |

## Profile Matrix

| Profile | Result | Top-level shape | Sections | Type-specific behavior | Redactions / warnings | Completeness |
| --- | --- | --- | --- | --- | --- | --- |
| `basic_safe` | 20/20 ok | `properties`, no `sections` | none | identity/status only | no sensitive paths/scripts/notes | minimal |
| `basic` | 20/20 ok | same compact shape as `basic_safe` | none | identity/status only | no sensitive paths/scripts/notes | minimal |
| `auto` | 20/20 ok | `properties`, `sections` | identity, structure, status, timing, targets, type_specific | good safe defaults for cue type fields | no sensitive file paths or script source | partial practical |
| `technical` | 20/20 ok | broad properties and sections | broad diagnostic sections | includes route/path-style diagnostics where allowed | can expose local media path/technical data; long fields may truncate | partial diagnostic |
| `health` | 20/20 ok | health-focused properties | minimal/health summary | identifies broken/warning/running/paused state | no sensitive data | minimal focused |
| `timing` | 20/20 ok | timing properties | timing only | no cue-type expansion | no sensitive data | minimal focused |
| `status` | 20/20 ok | status properties | status only | no cue-type expansion | no sensitive data | minimal focused |
| `targets` | 20/20 ok | target/file presence properties | target-focused | file target presence and cue target IDs/numbers where safe | no file paths | minimal focused |
| `group` | 20/20 ok | group/list fields when relevant | group/list focused | useful for Cue List and Group; most non-group cues return empty type-specific data | no failures for incompatible cue types | minimal focused |
| `editable` | 20/20 ok | `properties`, `sections`, `update_capabilities` | same safe sections as `auto` plus edit registry metadata | compatible update profiles and property risk tiers | does not imply real writes enabled | partial plus capabilities |
| `full` | 20/20 ok | broad saved/operational properties | broad sections | richer cue type data than `auto` | no notes, script source, or file paths observed | broad partial |
| `full_sensitive` | 20/20 ok | broad sensitive properties | broad sensitive sections | exposes notes, local media paths, scripts, heavy stage payloads where available | sensitive by design | broad sensitive partial |
| `inspector_safe` | 20/20 ok | Inspector-style safe properties | identity, structure, status, timing, targets, type_specific | broad non-sensitive Inspector context | no file paths/scripts | broad safe partial |
| `exhaustive` | 20/20 ok | deepest allowlisted properties plus `read_coverage` | deepest sections | most complete current cue detail read | warning: large/sensitive/heavy payloads; still not OSC dictionary parity | deepest partial |

Common per-cue result keys included:

- `ok`
- `status`
- `partial`
- `workspace_id`
- `cue_ref`
- `profile`
- `cue_type`
- `properties`
- `sections`
- `update_capabilities` for `editable`
- `warnings`
- `errors`
- `read_coverage` for `exhaustive`

No profile returned a tool-level failure. Cue limitations were data limitations,
not call failures.

## Editable Without Writing

`profile="editable"` worked for every representative cue. It returned
`update_capabilities` with compatible profiles, recommended profile, real-write
properties, dry-run-only properties, gated/dry-run-only properties, validators,
risk tiers, planned-only reasons, and required write gates.

Common safe real-write properties reported by the registry:

- `name`
- `number`
- `notes`
- `armed`
- `flagged`
- `colorName`
- `preWait`
- `postWait`
- `duration`
- `tempDuration`
- `continueMode`
- `skipIfDisarmed`
- `autoLoad`
- `secondColorName`
- `useSecondColor`

Common dry-run-only or gated families included target references, file targets,
duck/fade-and-stop behavior, second-trigger behavior, timecode trigger fields,
patch/routing references, and type-specific high-risk fields.

Write gates reported by editable metadata:

- `QLAB_ENABLE_WRITE`
- `QLAB_PASSCODE`
- `edit_scope_via_connect`
- `edit_mode_via_showMode`

The dry-run batch used five high-risk examples and sent no mutating OSC:

| Cue type | Profile | Property | planned_only_reason | capability_gate | confirm_token observed | Executed |
| --- | --- | --- | --- | --- | --- | --- |
| Light | `light_basic` | `lightCommandText` | `light_commands_can_affect_visual_output` | `light_output` | `confirm:lightCommandText:d3c65d2fa84dff9c` | no |
| Network | `network_basic` | `customString` | `network_messages_can_trigger_external_systems` | `network_output` | `confirm:customString:8e1e6093ef4f29fb` | no |
| Fade | `fade_basic` | `cueTargetID` | `fade_target_refs_need_dedicated_resolution` | `target_resolution` | `confirm:cueTargetID:8a90fb6deae4251b` | no |
| Target | `target_basic` | `cueTargetID` | `target_refs_need_dedicated_resolution` | `target_resolution` | `confirm:cueTargetID:43756a3ce6f1eb3f` | no |
| Script | `script_basic` | `scriptSource` | `not_editable_by_osc` | none | `confirm:scriptSource:d7186ca8c5f4583f` | no |

Dry-run result:

- `status="dry_run"`
- `requested_count=5`
- `planned_count=5`
- `updated_count=0`
- `failed_count=0`
- `executed_operations=[]`

Real high-risk writes would require exact `planned_operations[].confirm_token`
values from a reviewed dry-run, but this probe intentionally performed no real
writes.

## Gap Table

`exhaustive` returned read coverage for the deepest cue detail profile.

| Gap class | Count | Example routes | Meaning |
| --- | ---: | --- | --- |
| `indexed_read_gap` | 90 | `playhead/{string}`, `audioOutputPatch/level/{inChannel}/{outChannel}`, `gang/{inChannel}/{outChannel}`, `inputChannelName/{number}` | Route needs channel, object, or index arguments and is not modeled as a cue detail family yet. |
| `live_omitted` | 66 | `colorName/live`, `secondColorName/live`, `level/{inChannel}/{outChannel}/live`, `object/{name}/position/live` | Live active values are intentionally outside saved exhaustive details today. |
| `read_gap` | 33 | `isCrossfadingOut`, `isNextInPlaylist`, `audioOutputPatch/mute`, `audioOutputPatch/solo`, `audioOutputPatch/uniqueID` | Documented readable route is not represented in the current cue detail allowlist. |
| `runtime_read_gap` | 3 | `currentFileTime`, `liveAverageLevel/{outputChannel}`, `liveAverageLevel/{outputChannel}/{low}/{high}` | Runtime metric is not represented in saved cue details. |

Coverage status counts:

| Status | Count |
| --- | ---: |
| `direct` | 293 |
| `covered_by_aggregate` | 20 |
| `covered_by_structural_reader` | 4 |
| `indexed_read_gap` | 90 |
| `live_omitted` | 66 |
| `read_gap` | 33 |
| `runtime_read_gap` | 3 |

Largest section-level gaps:

| Section | Notable gaps |
| --- | --- |
| Audio | Indexed channel/object routes, live levels, mute/solo routes, runtime level metrics. |
| Video | Indexed geometry/region routes and live visual values. |
| Text | Live text/visual values omitted. |
| Fade | Indexed fade target/level routes and target validation gaps. |
| Network | Indexed parameter/fade routes and external-output safety gaps. |
| Common/global | Live colors and a small number of unmodeled state routes. |

## Recommended Next PRs

1. Add indexed route readers for channel/object/indexed families where the cue
   detail API can accept explicit indexes safely.
2. Add an optional live-value profile for `/live` routes, clearly separated from
   saved cue detail reads.
3. Add allowlist coverage for low-risk read gaps such as `isCrossfadingOut`,
   `isNextInPlaylist`, and audio patch mute/solo state.
4. Add a runtime metrics profile for `currentFileTime` and
   `liveAverageLevel...`, with clear running-cue semantics.
5. Improve Target cue diagnostics for empty or broken target references.
6. Add hardware-aware fixture notes/tests for MIDI, MIDI File, Timecode, Light,
   Network, Mic, and Camera without triggering external output.
7. Keep high-risk write families dry-run-first and gated; do not expand real
   writes until deterministic readback and safety semantics are proven.

## Safety Confirmation

- No MCP code changed.
- No commit or PR was made.
- Only this report file was created for this probe.
- No GO, playback, stop, panic, audition, preview, raw OSC, or real write was
  used.
- `qlab_update_cues` was used only with `dry_run=true`.
- The dry-run batch reported `updated_count=0` and `executed_operations=[]`.
- Final workspace status confirmed 30 scanned cues, 0 running, and 0 paused.
