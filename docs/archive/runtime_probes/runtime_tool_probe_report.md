# QLab MCP Runtime Tool Probe Report

Probe date: 2026-06-17

Workspace used: `<TEST_WORKSPACE_NAME>`

Workspace ID: `<TEST_WORKSPACE_UUID>`

QLab version: `5.5.10`

## 1. Executive Summary

Empirical probe ran against an open QLab fixture workspace. No GO, playback,
stop, panic, audition, preview, raw OSC, deletion, or real write was executed.
All write probes used `dry_run=true`.

The MCP surface exposed in this session contains 9 QLab tools:

- `qlab_check_connection`
- `qlab_get_workspace_overview`
- `qlab_get_workspace_settings`
- `qlab_get_workspace_setting_details`
- `qlab_query_cues`
- `qlab_get_cue_details`
- `qlab_check_write_readiness`
- `qlab_create_cue`
- `qlab_update_cues`

Runtime MCP does **not** expose `qlab_get_workspace_status`, settings
`mode="summary"/"details"`, `confirm_gates`, cue-detail batch input, or
`exhaustive`/`inspector_safe` profiles, even though current `README.md` and
`src/qlab_mcp/server.py` mention newer API shapes. Per instruction, this report
treats the MCP-exposed schema as authoritative.

Initial workspace selection without `workspace_id` returned
`status="workspace_ambiguous"` because two workspaces were open:

- `<TEST_WORKSPACE_NAME>`
- `<TEST_WORKSPACE_NAME>`

Chosen fixture workspace connection result:

- `ok=true`
- `status="ready"`
- `passcode_configured=true`
- `passcode_status="accepted"`
- `/connect` scopes: `["view", "edit", "control"]`
- `/showMode`: `show_mode=false`, `mode="edit"`

`qlab_check_write_readiness` was informational only. It returned
`ok=false`, `status="show_mode_unknown"` during one probe because `/showMode`
timed out, despite `qlab_check_connection` confirming Edit Mode before and
after. Because readiness was not clean and the task allowed real-write only
optionally, no real-write test was attempted.

Robustness finding: QLab/MCP is sensitive to concurrent tool pressure. One batch
of 8 parallel `qlab_query_cues` calls timed out at 120 seconds. Later serial or
smaller parallel calls mostly recovered, but one robustness round returned a
partial settings summary with `errors.audio.patchList`.

## 2. Tool Table

| Tool | Exposed args/schema | Kind | Requires `workspace_id` | Empirical result |
| --- | --- | --- | --- | --- |
| `qlab_check_connection` | `workspace_id?: string|null`, `require_read_access?: boolean` | Read-only | Optional, required when multiple workspaces open | Without ID: `ok=false`, `status="workspace_ambiguous"`, `workspace_count=2`. With fixture ID: `ok=true`, `status="ready"`, read access OK. |
| `qlab_get_workspace_overview` | `workspace_id?: string|null`, `max_depth?: int`, `max_cues?: int`, `include_live_state?: bool`, `include_cue_index?: bool`, `max_index_cues?: int`, `cue_index_profile?: "minimal"|"health"` | Read-only | Optional but practically required with multiple workspaces | Valid calls returned cue tree, summary, optional `cue_index`, `editorial_health`, `limits`, `warnings`. `max_cues=5000` rejected by schema: max is `1000`. One heavy live-state/index call timed out. |
| `qlab_get_workspace_settings` | `workspace_id: string`, `sections?: ["audio"|"video"|"network"|"midi"|"light"|"general"][]|null` | Read-only | Yes | Returned `sections`, `summary`, `redactions`, `errors`. No `mode` arg in runtime MCP. One robustness call returned partial audio patch data with `errors.audio.patchList`. |
| `qlab_get_workspace_setting_details` | `workspace_id: string`, `section`, `kind?`, `ref?`, `profile?: "safe"|"technical"` | Read-only | Yes | Safe details worked for audio output patch, audio map, video stage, video route, network patch, MIDI patch empty, light patch. |
| `qlab_query_cues` | `workspace_id: string`, `primary_filter`, `primary_value`, `optional_filters?`, `profile?`, `max_results?`, `max_cues_scanned?` | Read-only | Yes | Type, flagged, broken queries worked. Parallel stress caused timeouts. `isBroken=true` returned 5 cues. |
| `qlab_get_cue_details` | `workspace_id: string`, `cue_ref: string`, `profile?: auto/basic_safe/basic/technical/health/timing/status/targets/group/type_specific/editable/full/full_sensitive` | Read-only | Yes | `auto`, `basic_safe`, `basic`, `technical`, `health`, `timing`, `status`, `targets`, `group`, `editable` worked in representative cases. `type_specific`, `full`, and `full_sensitive` were schema-visible but rejected by runtime allowlist for tested cues. |
| `qlab_check_write_readiness` | `workspace_id: string` | Read-only readiness check | Yes | Returned capabilities and gates. Probe result: `ok=false`, `status="show_mode_unknown"` due `/showMode` timeout. |
| `qlab_create_cue` | `workspace_id: string`, `cue_type: memo/group/wait/audio`, `properties?`, `dry_run?`, `after_cue_id?` | Dry-run/write gated | Yes | `dry_run=true` worked for `memo`, `group`, `wait`, `audio`. Returned `planned_operations`, no `executed_operations`. No real create attempted. |
| `qlab_update_cues` | `workspace_id: string`, `updates: [{cue_ref, profile?, properties?, operations?}]`, `dry_run?` | Dry-run/write gated | Yes | `dry_run=true` worked for safe and type-specific probes. Returned `before`, `diff`, `planned_operations`, `real_write_enabled`, `planned_only_reason`. No `confirm_token` observed in exposed MCP runtime. No real update attempted. |

## 3. Initial vs. Final Baseline

| Metric | Initial | Final | Notes |
| --- | ---: | ---: | --- |
| Total cue IDs | 22 | 22 | From full overview `summary.total_cue_ids`. |
| Inspected cues | 22 | 22 | Full overview, `max_depth=5`. |
| Cue lists | 1 | 1 | Main Cue List. |
| Armed | 21 | 21 | Full overview. |
| Disarmed | 1 | 1 | `LIGHT_DISARMED_BROKEN`. |
| Flagged | 2 | 2 | `FADE_VALID_TARGET`, `FLAGGED_CUE`. |
| Broken | 5 by query | 5 by query/inferred | `Cue List`, `AUDIO_MISSING_FILE`, `VIDEO_MISSING_FILE`, `FADE_BROKEN_TARGET`, `LIGHT_DISARMED_BROKEN`. |
| Warnings | 0 observed | 0 observed | `isWarning=true` parallel stress timed out; cue index rows all showed false. |
| Running | 0 observed | 0 observed | Representative details returned `isRunning=false`; parallel `isRunning` query timed out. |
| Paused | 0 observed | 0 observed | Representative details returned `isPaused=false`; parallel `isPaused` query timed out. |

Representative cue types from full overview:

| Type | Count | Representative cue |
| --- | ---: | --- |
| Cue List | 1 | Main Cue List |
| Audio | 2 | `1` `AUDIO_MISSING_FILE`, `2` `AUDIO_VALID` |
| Video | 2 | `3` `VIDEO_MISSING_FILE`, `4` `VIDEO_VALID` |
| Group | 7 | `5` `GROUP_NESTED_LEVEL_1`, `14?` no, `NO_NUMBER`, `FLAGGED_CUE` |
| Fade | 2 | `10` `FADE_VALID_TARGET`, `11` `FADE_BROKEN_TARGET` |
| Light | 1 | `12` `LIGHT_DISARMED_BROKEN` |
| Network | 1 | `13` `NETWORK_VALID` |
| Memo | 1 | `14` `MEMO_LONG_TEXT` |
| Script | 1 | `15` `SCRIPT_SAFE_HIDDEN` |
| Pause | 1 | `🤣🤐🤐` `UNICODE_EMOJI_🤣` |
| Reset | 2 | `NBSP_A B_TEST`, `ÑÑó` |
| Start | 1 | `tuu` `LONG_NOTES` |

No baseline mutation was observed. All dry-run update results had
`executed_operations=[]`.

## 4. Read-Only Probe Details

### `qlab_get_workspace_overview`

Calls:

```json
{"workspace_id":"<TEST_WORKSPACE_UUID>","max_depth":1,"max_cues":100,"include_cue_index":false,"include_live_state":false}
{"workspace_id":"<TEST_WORKSPACE_UUID>","max_depth":5,"max_cues":1000,"include_cue_index":true,"max_index_cues":1000,"cue_index_profile":"health","include_live_state":false}
{"workspace_id":"<TEST_WORKSPACE_UUID>","max_depth":2,"max_cues":1000,"include_cue_index":true,"max_index_cues":1000,"cue_index_profile":"health","include_live_state":true}
{"workspace_id":"<TEST_WORKSPACE_UUID>","max_depth":5,"max_cues":5000,"include_cue_index":true,"max_index_cues":5000,"cue_index_profile":"minimal","include_live_state":false}
```

Results:

- `max_depth=1`: OK, `cue_count=22`, `inspected_cues=18`,
  `limits.truncated=true`, `truncation_reasons=["max_depth"]`.
- `max_depth=5`: OK, `cue_count=22`, `inspected_cues=22`,
  `cue_index.indexed_count=22`, `cue_index.truncated=false`,
  `editorial_health.number_empty.count=2`.
- `include_live_state=true` with index: timeout.
- `max_cues=5000`: schema validation error:
  `Input should be less than or equal to 1000`.

### `qlab_get_workspace_settings`

Calls:

```json
{"workspace_id":"<TEST_WORKSPACE_UUID>"}
{"workspace_id":"<TEST_WORKSPACE_UUID>","sections":["audio","video","network","midi","light","general"]}
```

Normal result summary:

- `section_count=6`
- `audio_output_patch_count=1`
- `audio_input_patch_count=1`
- `audio_map_count=1`
- `video_route_count=1`
- `video_stage_count=1`
- `network_patch_count=1`
- `midi_patch_count=0`
- `redaction_count=3`

Robustness round 3 returned partial/inconsistent summary:

- `audio.output_patches=[]`
- `audio_output_patch_count=0`
- `errors.audio.patchList="Timed out waiting for QLab reply to .../connect"`

### `qlab_get_workspace_setting_details`

Calls and results:

| Args | Result summary |
| --- | --- |
| `section="audio", kind="output_patch", profile="safe"` | OK. Patch `Patch 1 - System Output - Altavoces del MacBook Air - (2 Out)`, `cue_outputs=12`, `routing_present=true`, `routing_count=2`. |
| `section="audio", kind="audio_map", profile="safe"` | OK. Map `Stereo`, size `1000x1000`, `mark_count=2`, marks `Left` and `Right`, omitted `marks[].levels`. |
| `section="video", kind="stage", profile="safe"` | OK. Stage `Stage 1`, size `2940x1912`, `region_count=1`, route `Output 1`, redacted destination info. |
| `section="video", kind="route", profile="safe"` | OK. Route `Output 1`, `connected=true`, `destination_type="Display"`, redacted `destinationInfo`. |
| `section="network", kind="network_patch", profile="safe"` | OK. Patch `OSC Message - Patch 1`, `destination_present=false`, `passcode_present=false`. |
| `section="midi", kind="midi_patch", profile="safe"` | OK empty: `details=null`, message `No matching settings items were returned by QLab.` |
| `section="light", kind="light_patch", profile="safe"` | OK. `patch_present=true`, `instrument_count=0`, `group_count=0`, `read_transport="udp"`. |

### `qlab_query_cues`

Calls included:

```json
{"primary_filter":"type","primary_value":"Audio","profile":"basic_safe","max_results":20,"max_cues_scanned":100}
{"primary_filter":"flagged","primary_value":true,"profile":"basic_safe","max_results":20,"max_cues_scanned":100}
{"primary_filter":"isBroken","primary_value":true,"profile":"basic_safe","max_results":20,"max_cues_scanned":30}
{"primary_filter":"isWarning","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"isRunning","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"isPaused","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"disarmed","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"hasFileTargets","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"hasCueTargets","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
{"primary_filter":"number_empty","primary_value":true,"profile":"basic_safe","max_results":50,"max_cues_scanned":100}
```

Observed successful results:

- Type `Audio`: `matched_count=2`, `returned_count=2`, no truncation.
- `flagged=true`: `matched_count=2`, `returned_count=2`, no truncation.
- `isBroken=true`: `matched_count=5`, `returned_count=5`, no truncation.

Parallel stress result:

- 8 simultaneous query calls all timed out at `tools/call` after 120 seconds.
- Later serial/smaller calls recovered.

### `qlab_get_cue_details`

Successful profile probes:

| Cue/Profile | Result summary |
| --- | --- |
| `cue_ref="1", profile="auto"` | Audio details with `sections.identity`, `sections.status`, `sections.timing`, `sections.targets`, `sections.type_specific`; `isBroken=true`, `fileTargetPresent=true`. |
| `cue_ref="2", profile="basic_safe"` | Compact identity/status only: `uniqueID`, `number`, `name`, `displayName`, `type`, `armed`, `flagged`, `colorName`. |
| `cue_ref="2", profile="technical"` | Includes sensitive media path: `fileTarget="<LOCAL_MEDIA_FIXTURE_PATH>"`. |
| `cue_ref="10", profile="targets"` | Returns `cueTargetID`, `currentCueTargetID`, `cueTargetNumber="2"`, `hasCueTargets=true`. |
| `cue_ref="5", profile="group"` | Returns group playback/cart/playlist/timecode fields, including `mode=3`, `cartRows=4`, `cartColumns=4`. |
| `cue_ref="14", profile="editable"` | Returns `update_capabilities` for `common` and `memo_basic`, with safe real-write properties and validators. |
| `cue_ref="1", profile="basic"` | Adds `notes` to basic identity/status. |
| `cue_ref="1", profile="health"` | Returns health fields and derived `health_summary.status="broken"`. |
| `cue_ref="1", profile="timing"` | Returns timing elapsed/current fields. |
| `cue_ref="1", profile="status"` | Returns running/loaded/paused/broken/warning status and health summary. |

Rejected despite being exposed in schema:

- `profile="type_specific"` on Light cue: `The requested cue property or profile is not allowed for read-only access.`
- `profile="full_sensitive"` on Script cue: same error.
- `profile="full"` on Audio cue: same error.

`exhaustive` was not exposed by the MCP schema in this session, so it was not
callable through this MCP surface.

## 5. Table by Cue Type

| Type | Representative cue | Read profile tested | Update dry-run tested | Notes |
| --- | --- | --- | --- | --- |
| Audio | `2` `AUDIO_VALID` | `basic_safe`, `technical` | `audio_basic`: `rate`, `startTime`, `endTime`, `playCount` | Safe/medium one-value setters planned with `real_write_enabled=true`. |
| Video | `4` `VIDEO_VALID` | Overview/detail by type | `video_basic`: `opacity`, `translation/x`, `translation/y` | Planned as `risk_tier="medium"`, `real_write_enabled=true`. |
| Group | `5` `GROUP_NESTED_LEVEL_1` | `group` | Create dry-run `group`; common update path available | `group` profile returns playlist/cart/timecode fields. |
| Fade | `10` `FADE_VALID_TARGET` | `targets` | `fade_basic`: `stopTargetWhenDone=false` | High-risk, `real_write_enabled=false`, `planned_only_reason="fade_target_behavior_needs_validation"`. |
| Light | `12` `LIGHT_DISARMED_BROKEN` | health via overview/query | `light_basic`: `lightCommandText` | High-risk, `real_write_enabled=false`, `planned_only_reason="light_commands_can_affect_visual_output"`. |
| Network | `13` `NETWORK_VALID` | settings/network; cue overview | `network_basic`: `message` | High-risk, `real_write_enabled=false`, `planned_only_reason="network_messages_can_trigger_external_systems"`. |
| Memo | `14` `MEMO_LONG_TEXT` | `auto`, `editable` | `common`: name/notes/flags/timing/status props | Safe real-write properties discovered; dry-run only executed. |
| Script | `15` `SCRIPT_SAFE_HIDDEN` | `full_sensitive` rejected | `script_basic`: `scriptSource` | High-risk, `real_write_enabled=false`, `planned_only_reason="script_execution_risk"`. Existing script text contains audition/preview command, not executed. |
| MIDI | none in fixture | MIDI settings empty | `midi_basic` against Network cue | Dry-run preflight failed: profile requires MIDI cue. |

## 6. `qlab_update_cues` Property Table

| Profile/properties tested | Cue | Dry-run status | Real-write flag | Gates/tokens |
| --- | --- | --- | --- | --- |
| `common`: `name`, `notes`, `armed`, `flagged`, `colorName`, `preWait`, `postWait`, `duration`, `continueMode`, `skipIfDisarmed`, `autoLoad` | Memo `14` | `ok=true`, `status="dry_run"` | All operations `risk_tier="safe"`, `real_write_enabled=true` | No `confirm_token` emitted by this MCP runtime. |
| `audio_basic`: `rate`, `startTime`, `endTime`, `playCount` | Audio `2` | `ok=true`, `status="dry_run"` | All `risk_tier="safe"`, `real_write_enabled=true` | No token. |
| `video_basic`: `opacity`, `translation/x`, `translation/y` | Video `4` | `ok=true`, `status="dry_run"` | `risk_tier="medium"`, `real_write_enabled=true` | No token. |
| `light_basic`: `lightCommandText` | Light `12` | `ok=true`, `status="dry_run"` | `risk_tier="high"`, `real_write_enabled=false` | `planned_only_reason="light_commands_can_affect_visual_output"`; no token. |
| `network_basic`: `message` | Network `13` | `ok=true`, `status="dry_run"` | `risk_tier="high"`, `real_write_enabled=false` | `planned_only_reason="network_messages_can_trigger_external_systems"`; no token. |
| `fade_basic`: `stopTargetWhenDone` | Fade `10` | `ok=true`, `status="dry_run"` | `risk_tier="high"`, `real_write_enabled=false` | `planned_only_reason="fade_target_behavior_needs_validation"`; no token. |
| `script_basic`: `scriptSource` | Script `15` | `ok=true`, `status="dry_run"` | `risk_tier="high"`, `real_write_enabled=false` | `planned_only_reason="script_execution_risk"`; no token. |
| `midi_basic`: `channel` | Network `13` | `ok=false`, `status="preflight_failed"` | Operation planned high-risk false | `errors.profile="midi_basic update profile requires a MIDI cue"`. |

Create dry-run:

| Cue type | Dry-run result | Planned operations |
| --- | --- | --- |
| `memo` | OK | `new`, `set_property name`, `set_property number`, `set_property armed`, `verify` |
| `group` | OK | `new`, `set_property name`, `set_property number`, `verify` |
| `wait` | OK | `new`, `set_property name`, `set_property duration`, `verify` |
| `audio` | OK | `new`, `set_property name`, `set_property number`, `verify` |

## 7. Gaps Relative to Read All / Edit All

- Runtime MCP tool surface is older than local `src/qlab_mcp/server.py` and
  README. Missing exposed runtime tools/features: `qlab_get_workspace_status`,
  settings `mode`, batch cue details, `confirm_gates`, `exhaustive`,
  `inspector_safe`, `include_global_count`.
- `qlab_get_cue_details` advertises `full`, `full_sensitive`, and
  `type_specific`, but tested calls were blocked by allowlist. The schema does
  not communicate that runtime block.
- Settings summary can be partial under load and still return top-level JSON
  with per-section `errors`.
- Concurrent query load can cause long tool-call timeouts.
- No MIDI cue exists in fixture, so MIDI cue detail/update behavior could not be
  empirically validated beyond settings empty and profile mismatch failure.
- No Mic, Camera, Text, MIDI File, Timecode, Target, Devamp cue examples exist
  in fixture, so those type-specific profiles were not validated on matching
  cue types.
- High-risk dry-run operations in exposed MCP runtime did not emit
  `confirm_token`; they stayed `real_write_enabled=false` with
  `planned_only_reason`.
- Real-write verification/rollback was skipped because readiness was not
  consistently clean and the objective made real-write optional.

## 8. Recommended Next PRs

1. Align installed MCP runtime with current `src/qlab_mcp/server.py`, or update
   README to state the deployed/runtime surface separately.
2. Add a read-only `qlab_get_workspace_status` runtime smoke test if that tool
   is meant to be deployed.
3. Make `qlab_get_cue_details` schema reflect blocked profiles, or return a
   structured per-profile capability error instead of a generic allowlist error.
4. Add fixture cues for Mic, Camera, Text, MIDI, MIDI File, Timecode, Target,
   Devamp, and matching MIDI profile validation.
5. Add a concurrency/load note or server-side queue for QLab OSC reads to avoid
   parallel query timeouts.
6. Add stable partial-result semantics to settings summary for section timeouts,
   including whether `summary.*_count=0` means empty or failed.
7. If high-risk real writes are intended, expose `confirm_token` and
   `confirm_gates` in the deployed MCP runtime; otherwise document them as
   unavailable.
