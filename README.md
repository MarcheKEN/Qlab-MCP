# QLab MCP

QLab MCP `0.2.0` is a FastMCP server for safely inspecting QLab 5 workspaces
over OSC.

**Read-only by default.** The normal tools inspect workspace state, cues,
settings, patches, and routes. They do not expose playback or mutation controls.
Optional write-mode tools are separate, disabled unless explicitly gated, and
dry-run-first.

## What It Does

- Workspace overview and status: cue lists, groups, counts, Edit/Show mode,
  optional live state, cue warnings, trigger/timecode summaries, and settings
  summary.
- Cue search and cue details: find cues by type, state, color, name, number,
  target presence, timing, and health; inspect one cue or a batch of up to 50.
- Workspace settings diagnostics: compact settings summaries plus focused
  patch, route, stage, audio, video, network, MIDI, and light details.
- Optional gated write tools: dry-run-first blank cue creation, allowlisted cue
  editing, structural List/Group moves, and exact-UUID leaf deletion.

## What It Does Not Do

- No GO, playback, stop, or panic controls.
- No ungated deletion, container deletion, or cascade deletion.
- No raw OSC tool.
- No broad `/live` write surface. The sole narrow exception is the allowlisted
  `secondColorName` edit; every other `/live` write remains blocked.
- No ambiguous selected, active, playhead, or playback-position edits.
- No ungated high-risk writes. High-risk families require dry-run review plus
  exact `planned_operations[].confirm_token` values when supported, or they
  remain blocked.

## Quick Start

Install and run with the existing project commands:

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run qlab-mcp
```

`qlab-mcp` is the public server command. To inspect its FastMCP contract without
connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```

`fastmcp.json` uses the repository-only `fastmcp_entrypoint.py` wrapper so
FastMCP imports the installed package correctly. Neither file is included in
the wheel or sdist.

If an existing `.venv` cannot import `qlab_mcp`, rebuild it safely:

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run python -c "import qlab_mcp; print(qlab_mcp.__version__)"
```

The observed import failure is related to the editable project installation in
the environment, not specifically to Python 3.12. Use the non-editable sync
command above for a reproducible Python 3.11 development environment.

Manual QLab check:

1. Open QLab 5.
2. Open or create a workspace with at least one cue list and one cue.
3. Enable OSC access for the workspace if needed.
4. Start this MCP server.
5. Call `qlab_check_connection`.
6. If several workspaces are open, pass a `workspace_id` from
   `available_workspaces`.

For passcode-protected workspaces, set `QLAB_PASSCODE` before starting the MCP.

## Recommended Workflows

Read-only inspection flow:

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_status`
4. `qlab_get_workspace_settings(mode="summary")`
5. `qlab_query_cues`
6. `qlab_get_cue_details`
7. `qlab_get_workspace_settings(mode="details")`

Cue edit flow:

1. `qlab_check_connection`
2. `qlab_check_write_readiness`
3. `qlab_query_cues` and `qlab_get_cue_details(profile="editable")`
4. `qlab_edit_cues(..., dry_run=true)`
5. Review `planned_operations`, `diff`, warnings, and per-item errors.
6. Use `dry_run=false` only in a deliberate gated write session.
7. Verify after with `qlab_get_cue_details`, `qlab_query_cues`, or other read
   tools.

## Tool Groups

### Connection And Status

| Tool | Purpose |
| --- | --- |
| `qlab_check_connection` | Confirms QLab is reachable, resolves workspace choices, verifies safe read access, and reports passcode state, `/connect` scopes, and Edit/Show mode. |
| `qlab_get_workspace_status` | Returns compact operational status: cue warnings, trigger/timecode summaries, settings summary, and explicit unavailable sections. |

### Workspace Overview And Settings

| Tool | Purpose |
| --- | --- |
| `qlab_get_workspace_overview` | Returns a bounded show map: cue lists, groups, cue counts, Edit/Show mode, optional live state, optional cue index, and optional global count. |
| `qlab_get_workspace_settings` | Reads compact settings summary or batched setting details. Use `mode="summary"` first, then `mode="details"` for focused diagnostics. |
| `qlab_get_workspace_setting_details` | Backwards-compatible wrapper for one settings detail request. |

### Cue Query And Details

| Tool | Purpose |
| --- | --- |
| `qlab_query_cues` | Searches cues by type, state, color, name, number prefix, target presence, timing, or health. |
| `qlab_get_cue_details` | Inspects one cue or a batch of up to 50 cues. Use `profile="editable"` to discover update capabilities. |

### Gated Write-Mode

| Tool | Purpose |
| --- | --- |
| `qlab_check_write_readiness` | Checks disabled-by-default write readiness without mutation. |
| `qlab_create_cue` | Dry-runs or creates one blank allowlisted cue with safe initial properties. |
| `qlab_edit_cues` | Dry-runs or updates 1-50 concrete cues through the cue editing registry. |
| `qlab_update_cues` | Compatibility alias for older prompts, tests, and clients. |
| `qlab_move_cues` | Dry-runs or moves 1-10 exact UUID-addressed cues within or between Lists and Groups. |
| `qlab_delete_cues` | Dry-runs or deletes 1-10 exact leaf-cue UUIDs; container and cascade deletion is blocked. |

## Read Model

The server is designed to inspect QLab workspaces without dumping the whole show
at once.

- `qlab_get_workspace_overview` gives a bounded tree and optional compact cue
  index.
- `cue_index_profile="minimal"` returns identity and position columns.
- `cue_index_profile="health"` adds armed, flagged, color, broken/warning, and
  continue-mode diagnostics.
- `qlab_get_workspace_settings(mode="summary")` returns infrastructure
  summaries plus `available_detail_requests`.
- `qlab_get_workspace_settings(mode="details")` goes deeper only for requested
  settings items.
- `technical`, `full_sensitive`, and `exhaustive` are explicit audit modes, not
  normal defaults.

For large shows, `qlab_query_cues` defaults to `max_results=500` and
`max_cues_scanned=500`. Callers can raise either limit up to `5000`. Results
report `truncated`, `truncation_reasons`, `scanned_all_cues`, and
`result_limited`.

## Write-Mode Safety

Write mode is deliberately gated:

- Pass an explicit `workspace_id` and run `qlab_check_write_readiness` before
  every real write session.
- `QLAB_ENABLE_WRITE=true` is required before real write commands can run.
- `QLAB_PASSCODE` is a server-side credential only. It is never a tool argument.
- `dry_run=true` is the default through `QLAB_WRITE_DRY_RUN_DEFAULT=true`.
- `qlab_check_write_readiness` does not mutate anything.
- Real writes require `/connect` to confirm `edit` and `/showMode` to confirm
  Edit Mode.
- Write preflight must pass before setters.
- If any item fails real-write preflight, zero setters are sent for the whole
  batch.
- Once real setters start, batch writes are not transactional. Later failures
  are reported per item and require normal readback or manual review.
- Real writes bypass and clear the read cache before fresh verification.
- `qlab_create_cue` has no `confirm_token` argument. Review its dry-run before
  real creation.
- `qlab_edit_cues` may return tokens for individual planned high-risk
  operations. Copy each exact relevant `planned_operations[].confirm_token`
  into that update item's `confirm_gates`; there is no tool-level Edit token.
- An eligible reviewed dry-run for `qlab_move_cues` or `qlab_delete_cues`
  returns one dedicated tool-level `confirm_token`. Real execution must receive
  that exact token.
- Move tokens bind the reviewed workspace structure and move batch. Delete
  tokens bind the reviewed deletion plan and fresh workspace structure.
- Move and Delete tokens are process-bound; restarting the MCP invalidates
  tokens issued by the previous process.
- Broad capability gate names are discovery labels, not real-write approval
  tokens.
- Operations without deterministic readback must be blocked or reported
  inconclusive, not clean success.

Allowed cue creation is intentionally narrow:

- Only blank cue creation is allowed in this preface.
- Allowed cue types are `memo`, `group`, `wait`, and `audio`.
- Safe initial properties are `name`, `number`, `armed`, `flagged`, `colorName`,
  `preWait`, `postWait`, `duration`, and `continueMode`.
- `after_cue_id` placement is dry-run planning only.

Cue updates use concrete cue numbers or unique IDs. `selected`, `active`,
`playhead`, and `playbackPosition` are rejected for updates.

`qlab_edit_cues` supports these update profiles:

```text
common
memo_basic
wait_basic
group_basic
audio_basic
mic_basic
video_basic
camera_basic
text_basic
light_basic
fade_basic
network_basic
midi_basic
midi_file_basic
timecode_basic
target_basic
reset_basic
devamp_basic
script_basic
```

Current specialized write support is intentionally token-gated:

- `group_basic`: common Basics remain normal guarded writes. Group `mode`
  values `1`, `2`, `3`, `4`, and `6` require an exact-UUID, one-property
  `confirm:groupMode:v1:` token. Canonical Playlist scalars
  `playlist/doLoop`, `playlist/doShuffle`, `playlist/doCrossfade`, and
  `playlist/crossfade/duration` require `confirm:groupPlaylist:v1:` and a
  freshly verified Playlist mode (`6`). Both token families expire after five
  minutes, are atomically single-use within the MCP process, and bind the
  ordered direct-child snapshot. Tokens are consumed immediately before the
  one setter send and remain consumed after timeout or failed verification;
  rollback always needs a new dry-run/token. Fresh post-write child differences
  are reported as side effects; no hidden restoration occurs.
  QLab 5.5 runtime validation covers modes `1`, `2`, `3`, `4`, and `6`; the four
  canonical Playlist scalars; common Basics `notes`, `flagged`, `preWait`,
  `postWait`, and `continueMode` (`0 -> 1 -> 0`). Expected QLab child order,
  `continueMode`, and `postWait` changes are surfaced through `side_effects`
  and `group_child_readback`. Setter timeout with matching fresh readback is
  `updated_with_confirmed_timeouts`, with no mutating retry. Timeline UI edits,
  Playlist navigation/actions, deprecated aliases, and crossfade curve shapes
  are not real-write surfaces. QLab 5.5.10 runtime validation now covers the
  disposable `378`-child ordered snapshot, finite and mixed zero/finite
  Playlist Loop, one-setter timeout/readback/rollback behavior, consumed-token
  replay, and preflight rejection when crossfade exceeds the shortest child.
  Requests for `1 s` and `2 s` crossfade retained/read back as `3 s` in the
  named fixture; this is fixture/version-specific evidence, not a global API
  minimum, so short/equal active crossfade behavior remains unconfirmed.
  All-zero-child Loop, warning-only Groups, active/auditioning Groups, live
  token expiry, and live MCP restart invalidation remain follow-up limits.
- `video_basic`: safe cue metadata is the only normal real-write surface.
  Visual, embedded-audio, and slice edits are dry-run-first candidates with
  specialized confirm tokens. This includes opacity, translation, anchor/scale
  and crop scalars, blend/fit appearance, selected geometry flags, stage/audio
  output IDs, time/loop fields, video audio levels/mute/solo metadata, and slice
  marker edits. Video FX real-write support is deliberately narrow and only
  applies when dry-run marks an exact scalar candidate such as the validated
  `videoEffectIndex/0/parameter/inputRadius` or `inputIntensity` paths.
- `camera_basic`: supports safe camera `channels`; camera visual geometry and
  I/O fields follow the same dry-run/confirm-token model as visual cue edits.
- `text_basic`: text content, `fixedWidth`, alignment, `fontName`, `fontSize`,
  `lineSpacing`, text color, and shared visual geometry are gated candidates.
  Rich text shadows, decoration, and unreliable color/readback paths remain
  planned-only unless a dry-run emits a concrete confirm token.
- `light_basic`: `lightCommandText` can become a real-write candidate only for a
  single Light cue after safe Light Patch analysis returns valid. `alwaysCollate`
  and `subcontroller` are separate saved-mode behavior candidates. Other Light
  operations such as `setLight`, replace/remove, sort, and prune remain
  dry-run planning surfaces unless the dry-run says otherwise.

For these families, the dry-run is the contract. Only trust
`planned_operations[]` fields such as `real_write_possible`,
`requires_confirm_token`, and `confirm_token`; broad profile names or
`capability_gate` labels are not approval to mutate.

All update profiles can exist for planning and targeting, but real writes are
limited to safe properties unless the item explicitly lists the exact
`confirm_token` values from reviewed dry-run `planned_operations`. Some
properties have no safe OSC write path, such as `scriptSource`, and remain
non-editable by OSC.

High-risk profiles and unvalidated properties are cataloged for dry-run
planning and require exact confirmation when real write is supported: routing,
targets, file paths, light commands, network/MIDI output, scripts, audio levels,
slices, objects, live variants, text ranges/colors, and multi-argument geometry.

`fileTarget` and local file paths are blocked by default. Real writes require
both a reviewed dry-run `confirm_token` and a path inside
`QLAB_ALLOWED_FILE_ROOTS`. Paths outside those roots are blocked before OSC.

If a setter times out but a fresh after-read confirms the requested value,
`qlab_edit_cues` reports `updated_with_confirmed_timeouts` with a warning. If
fresh verification cannot prove the requested value, the result is failed or
inconclusive.

### Utility and Network cues

Utility real writes support only saved `cueTargetID` assignment for exact-UUID
source and target cues through `confirm:utilityTarget:v1:`. `cueTargetNumber`,
`cueTargetName`, temporary targets, Reset patch/map targets, and target actions
remain blocked.

An initially untargeted source may be `isBroken=true` only for this first
assignment when its saved `cueTargetID` is empty and the requested target is an
exact UUID. The source must still be inactive and warning-free, the target must
be healthy and inactive, and the normal fresh-token/readback gate still applies.
Already-targeted or otherwise broken sources remain blocked.

Network OSC Message `customString` is runtime validated for an exact healthy,
inactive cue whose current patch is freshly classified as `OSC Message`. It
uses the item-level `confirm:networkOscMessage:v1:` Edit flow.
`networkPatchID` reassignment remains blocked/planned-only: the tested
reassignment read back but left the cue broken. Patch definitions,
destinations, fades, device descriptions, raw OSC, and `/live` remain blocked.

### Fade cues

`qlab_edit_cues` supports gated Fade Basics and duration, exact UUID cue targets,
and promoted direct target types Audio, Mic, Video, Camera, and Text. Group and
Cue List fanout, patches, maps, Objects, Audio FX, Video FX, Curve internals,
Geometry Path, unsupported resets, and planned-only actions remain out of scope.

Supported fields include absolute/relative `levelsMode`, `doLevel`, `level`,
`sliderLevel`, `gang`, `inputChannelName`, `stopTargetWhenDone`, and supported
visual Geometry fields. `-inf` is accepted only for absolute Levels and maps to
workspace Audio minimum on readback. Dedicated token families are
`confirm:fadeBasic:v1:`, `confirm:fadeTarget:v1:`, `confirm:fadeGeometry:v1:`,
`confirm:fadeAudio:v1:`, `confirm:fadeBehavior:v1:`,
`confirm:fadeSetup:v1:`, and `confirm:fadeRecovery:v1:`. Promoted writes require
fresh readback, health/activity gates, one setter, and fresh verification.

Runtime validation covers Fade Audio targeting Mic, absolute/relative Levels,
`doLevel`, `level`, `sliderLevel`, semantic `-inf` mapped to workspace minimum,
`stopTargetWhenDone`, fresh readback, and `0.001 dB` tolerance. No runtime
claim is made for `inputChannelName`, gangs, visual Geometry, setup/recovery,
special resets, or listed out-of-scope features.

### Move cues

`qlab_move_cues` accepts one workspace UUID and 1–10 strict cue UUID moves.
Linear placement uses exactly one of `destination_index`, `before_cue_id`,
`after_cue_id`, `position="first"`, or `position="last"`, within or between
Cue Lists and Groups. Execution is ordered and sequential. Dry-run returns
`confirm:moveCues:v1:`; structural simulation binds parent/order fingerprints,
rejects cycles and invalid parents, preserves UUIDs and cue properties, and
never claims OSC atomicity. Results distinguish partial failure, verification,
timeout, and indeterminate outcomes.

QLab may acknowledge a move before readable tree update. Convergence polls at
approximately 0, 250, 500 ms, 1, 2, 4, 6, 8, and 10 seconds; next move waits
for prior convergence. Cue Cart fields are schema-supported, but real Cart
execution remains runtime-blocked. Linear List/Group movement is runtime
validated; QLab tree convergence can take approximately 4–10 seconds, so moves
are sequential and not atomic.
Large batches can take several seconds per cue. Local tests cover same-parent
up/down, List/Group transfers, nested Groups, first/last/before/after, batches
of 2 and 10, and structural/property preservation.

### Delete cues

`qlab_delete_cues` accepts one workspace UUID and 1–10 exact leaf-cue UUIDs.
Dry-run returns `confirm:deleteCues:v1:`. Duplicate, invalid, active, container,
parent/descendant, cascade, Group, Cue List, and Cue Cart requests are rejected.
Deletes are sequential, stop on unresolved failure, use independent existence
and neighbor readback, have no automatic rollback, and are destructive and
non-idempotent.

Tokens bind workspace, requested UUID order, cue type, parent, sibling index,
previous/next neighbors, parent-order and deletion-impact fingerprints,
readiness/activity, operation version, and expiry. Deletion convergence polls
over bounded 0–10 second window. Result states include `deleted_immediately`,
`deleted_after_convergence`, `indeterminate`, `failed`, and `partial_failed`.
Permanent container/descendant deletion remains out of scope. Local tests cover
leaf/batch deletion, neighbor preservation, stale and wrong-family tokens,
container guards, and no cascade.

Runtime validation covers individual and sequential batch leaf deletion,
approximately 4–10 second convergence, neighbor preservation, stale-token and
wrong-family token rejection, and container/cascade blocking. Move and Delete
confirmation tokens are process-bound; restarting the MCP invalidates tokens
issued by the previous process.

## Privacy Profiles

`safe` is the normal workspace settings profile. It redacts sensitive
infrastructure where possible: destinations, routes, devices, passcodes,
credentials, and similar details.

`technical` is for deliberate technical audits. It can reveal IP addresses,
ports, interfaces, screens, devices, routes, raw regions, mesh/warp data,
audio-map levels, light patch payloads, and routing payloads.

For workspace settings, `exhaustive` is the deepest allowlisted read-only
settings profile. It may return large payloads and always includes warnings.
Passcodes and credentials remain redacted.

`full_sensitive` can expose cue notes, local media paths, scripts, and heavy
stage payloads. Use it only when that exposure is intentional.

Cue detail profiles are tiered:

- `basic` / `basic_safe`: compact identity/status, no large notes, scripts, or
  media paths.
- `auto` / `inspector_safe`: operational cue data; type-specific fields are
  summarized and compact.
- `editable`: capability discovery for `qlab_edit_cues`, including
  dry-run-only properties and dry-run confirmation tokens; it does not imply
  real writes are enabled.
- `full_sensitive` / `exhaustive`: explicit large/sensitive reads; still no MCP
  implementation paths.

Compact profiles truncate long text fields such as notes, memo text, script
text, light commands, and network messages. Truncated fields return
`field_truncated: true` and `original_length`.

## Query Filters

`qlab_query_cues` requires one primary filter and accepts optional AND filters.

Common filters:

- `type`
- `flagged`
- `armed`
- `disarmed`
- `isBroken`
- `isWarning`
- `isRunning`
- `isPaused`
- `isLoaded`
- `isOverridden`
- `isAuditioning`
- `colorName`
- `name_contains`
- `number_prefix`
- `cue_list_id`
- `parent_id`
- `hasFileTargets`
- `hasCueTargets`
- `skipIfDisarmed`
- `autoLoad`
- `continueMode`
- `hasPreWait`
- `hasPostWait`
- `hasDuration`
- `name_empty`
- `displayName_empty`
- `number_empty`
- `ambiguous_label`
- `flagged_or_broken`

Example:

```text
primary_filter="type"
primary_value="Audio"
optional_filters=[{"filter": "isWarning", "value": true}]
```

## Configuration

The server reads QLab connection settings from environment variables.

```text
QLAB_HOST=127.0.0.1
QLAB_OSC_PORT=53000
QLAB_REPLY_PORT=53001
QLAB_TIMEOUT=2.0
QLAB_CACHE_TTL=10.0
QLAB_PASSCODE=
QLAB_ENABLE_WRITE=false
QLAB_WRITE_DRY_RUN_DEFAULT=true
QLAB_UPDATE_DEBUG=false
QLAB_ALLOWED_FILE_ROOTS=
```

Notes:

- QLab listens for OSC on port `53000` by default.
- QLab sends UDP replies to `53001` by default.
- `QLAB_REPLY_PORT=0` is useful for automated tests with a fake OSC server.
- `QLAB_CACHE_TTL=0` disables the short read cache.
- Live selected/running/active state bypasses the cache.
- Queries using live state filters such as `isRunning`, `isPaused`, `isLoaded`,
  `isOverridden`, or `isAuditioning` bypass the cache.
- Sensitive `technical`, `full_sensitive`, and `exhaustive` reads bypass the
  cache.
- `QLAB_UPDATE_DEBUG=true` adds per-item diagnostics to real
  `qlab_edit_cues`/`qlab_update_cues` results, including requested and readback
  values. It is off by default, requires an MCP restart after changing the
  environment, and does not weaken write gates or verification.

## Diagnostic Limits

QLab reports cue and workspace fields. The MCP derives cautious summaries from
those fields. Physical output still needs a human check.

`qlab_get_workspace_status` is not a full clone of QLab's Workspace Status
window. Sections that QLab does not expose as safe read-only OSC endpoints are
returned with `source="not_exposed"` instead of invented values.

When `qlab_get_workspace_overview` cannot read authoritative broken/warning
fields from shallow cue data, health rows are marked partial/non-authoritative.
Use `qlab_get_workspace_status` or `qlab_query_cues` with health filters for
cue-level diagnostics.

For large lighting workspaces, this safe detail read should summarize the light
patch:

```text
qlab_get_workspace_settings(mode="details", requests=[{"section": "light", "kind": "light_patch"}])
```

If the UDP reply is too large, the result should still succeed through
`read_transport="tcp_fallback"`. That means TCP was used to retrieve a large
response; it does not imply output failure, missing controllers, or degraded
physical playback.

## Tool Signatures

```text
qlab_check_connection(workspace_id=None, require_read_access=True)
qlab_get_workspace_overview(workspace_id=None, max_depth=2, max_cues=1000, include_live_state=False, include_cue_index=True, max_index_cues=5000, cue_index_profile="minimal", include_global_count=False)
qlab_get_workspace_status(workspace_id, profile="summary", include_timecode=True, max_cues_scanned=1000, sample_limit=10)
qlab_get_workspace_settings(workspace_id, mode="summary", sections=None, requests=None, profile="safe")
qlab_get_workspace_setting_details(workspace_id, section, kind=None, ref=None, profile="safe")
qlab_query_cues(workspace_id, primary_filter, primary_value, optional_filters=None, profile="basic_safe", max_results=500, max_cues_scanned=500)
qlab_get_cue_details(workspace_id, cue_ref, profile="auto")
qlab_check_write_readiness(workspace_id)
qlab_create_cue(workspace_id, cue_type, properties=None, dry_run=None, after_cue_id=None)
qlab_edit_cues(workspace_id, updates, dry_run=None)
qlab_update_cues(workspace_id, updates, dry_run=None)  # compatibility alias
qlab_move_cues(workspace_id, moves, dry_run=None, confirm_token=None)
qlab_delete_cues(workspace_id, cue_ids, dry_run=None, confirm_token=None)
```

`qlab_edit_cues` update items use this shape:

```json
{
  "cue_ref": "1",
  "profile": "common",
  "properties": {"name": "New name"},
  "operations": [],
  "confirm_gates": []
}
```

Structured update operations inside each item use this shape:

```json
{
  "property": "level",
  "args": {"inChannel": 1, "outChannel": 1, "decibel": -6},
  "mode": "saved"
}
```

Compact examples:

```json
{"workspace_id":"WORKSPACE_UUID","updates":[{"cue_ref":"FADE_UUID","profile":"fade_basic","operations":[{"property":"level","args":{"inChannel":0,"outChannel":0,"decibel":-6},"mode":"saved"}]}],"dry_run":true}
```

```json
{"workspace_id":"WORKSPACE_UUID","moves":[{"cue_id":"CUE_UUID","destination_parent_id":"GROUP_UUID","position":"last"}],"dry_run":true}
```

```json
{"workspace_id":"WORKSPACE_UUID","moves":[{"cue_id":"CUE_A_UUID","before_cue_id":"CUE_B_UUID"},{"cue_id":"CUE_C_UUID","position":"first"}],"dry_run":true}
```

```json
{"workspace_id":"WORKSPACE_UUID","cue_ids":["LEAF_UUID"],"dry_run":true}
```

```json
{"workspace_id":"WORKSPACE_UUID","cue_ids":["LEAF_UUID"],"dry_run":false,"confirm_token":"confirm:deleteCues:v1:RETURNED_TOKEN"}
```

## Development And References

- `src/qlab_mcp/server.py` exposes the read tools plus gated write-mode tools.
- `fastmcp.json` points FastMCP at the server entry point.
- `src/qlab_mcp/osc/` handles OSC encoding, transport, and addressing.
- `src/qlab_mcp/cues/` handles overview, indexing, querying, profiles, and cue
  details.
- `src/qlab_mcp/settings/` handles workspace settings, summarizers, and
  redaction.
- `src/qlab_mcp/status.py` handles read-only workspace status summaries.
- `src/qlab_mcp/runtime/` handles shared reader runtime helpers such as
  connection diagnostics and read cache.
- `src/qlab_mcp/write/` handles disabled-by-default write readiness,
  allowlists, gated mutating OSC operations, and OSC inventory coverage.

References:

- [Documentation index](docs/README.md)
- [QLab edit cues runtime checklist](docs/development/runtime-validation/edit-cues.md)
- [OSC coverage snapshot](docs/status/coverage/osc_coverage_snapshot.md)
- [QLab OSC dictionary](docs/references/qlab_osc_dictionary.md)
- [QLab OSC queries](docs/references/osc_queries.md)
- [Reference provenance and checksums](docs/references/manifest.json)
- [Historical Video Phase 1 OSC matrix](docs/archive/coverage/video_phase1_osc_matrix.md)
