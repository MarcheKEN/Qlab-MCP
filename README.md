# QLab MCP

A FastMCP server for inspecting QLab 5 workspaces over OSC, with an optional
gated write-mode preface for dry-run cue creation and batch cue updates.

This project helps an agent understand what is inside an open QLab workspace:
cues, cue lists, cue health, workspace settings, patches, routes, stages, MIDI,
network, and light infrastructure. The default inspector mode does not expose
playback, editing, deletion, raw OSC, or mutating commands.

By default the server remains read-only. Write mode is disabled unless
`QLAB_ENABLE_WRITE=true`, and mutating tools default to dry-run unless
`QLAB_WRITE_DRY_RUN_DEFAULT=false`.

## Best First Flow

Use the tools in this order:

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_settings`
4. `qlab_query_cues`
5. `qlab_get_cue_details`
6. `qlab_get_workspace_setting_details`

The core idea is simple: start broad and compact, then ask for details only
when you know exactly what needs inspection.

## Project Layout

The public entry points stay at the package root:

- `src/qlab_mcp/server.py` exposes the six inspector tools plus three gated write-mode tools.
- `src/qlab_mcp/qlab.py` keeps the compatibility facade for `QLabReader`.
- `src/qlab_mcp/models.py`, `config.py`, `errors.py`, and `allowlist.py` hold shared API types and policy.

Internal readers are grouped by responsibility:

- `src/qlab_mcp/osc/` handles OSC encoding, transport, and addressing.
- `src/qlab_mcp/cues/` handles overview, indexing, querying, profiles, and cue details.
- `src/qlab_mcp/settings/` handles workspace settings, summarizers, and redaction.
- `src/qlab_mcp/runtime/` handles shared reader runtime helpers such as connection diagnostics and read cache.
- `src/qlab_mcp/write/` handles disabled-by-default write readiness, allowlists,
  and gated mutating OSC operations.

Project-local agent skills and transcript scratch files are intentionally not
part of the runtime package. QLab learning/reference material should live in a
clear documentation or reference location, not at the package root.

## Tools

| Tool | Use it for | Default shape |
| --- | --- | --- |
| `qlab_check_connection` | Confirm QLab is reachable, pick a workspace, verify safe read access, and report Edit/Show mode. | Small diagnostic result |
| `qlab_get_workspace_overview` | Get the show map, Edit/Show mode, cue lists, groups, cue counts, and optional cue index. | Bounded tree plus compact index |
| `qlab_get_workspace_settings` | Inventory patches, routes, stages, MIDI, network, light availability, and general settings. | Safe infrastructure summary |
| `qlab_get_workspace_setting_details` | Inspect one patch, route, stage, map, MIDI/network item, or light patch. | `safe` profile |
| `qlab_query_cues` | Search cues by type, state, color, name, number prefix, targets, timing, or health. | Up to 500 scanned/returned cues |
| `qlab_get_cue_details` | Inspect one cue after finding it in overview or query results. | `auto` profile |
| `qlab_check_write_readiness` | Check disabled-by-default write-mode readiness without mutation. | Safety/readiness report |
| `qlab_create_cue` | Dry-run or create one blank allowlisted cue with safe initial properties. | Dry-run by default |
| `qlab_update_cues` | Dry-run or update 1-50 concrete cues through the cue editing registry. | Dry-run by default |

## Compact By Default

The server is designed to make everything accessible without dumping everything
at once.

- Overview gives a bounded tree and a compact cue index.
- When cue_index is enabled, overview also derives editorial health from that
  index: empty labels, duplicate names/numbers, and ambiguous placeholders.
- Settings gives infrastructure summaries without heavy raw payloads.
- Details tools go deeper only when the caller asks for a specific cue or setting.
- `technical` and `full_sensitive` are explicit audit modes, not normal defaults.

For large shows, `qlab_query_cues` keeps `max_results=500` and
`max_cues_scanned=500` by default. Callers can raise either limit up to `5000`.
Results report whether they are complete with:

- `truncated`
- `truncation_reasons`
- `scanned_all_cues`
- `result_limited`

## Cue Index Profiles

`qlab_get_workspace_overview` supports two cue index profiles.

| Profile | Columns |
| --- | --- |
| `minimal` | Identity and position: ID, number, name, display name, type, list name, cue list ID, parent ID, depth |
| `health` | Everything in `minimal`, plus armed, flagged, color, broken/warning state, continue mode, and continue mode label |

The default is `minimal`, so orientation stays fast and readable. Use `health`
when you need a diagnostic map of the whole show.

## Diagnostic Context

QLab reports cue and workspace fields; the MCP derives cautious summaries from
those fields; physical output still needs a human check. A broken cue summary
can include evidence, probable causes, diagnostic hints, and checks such as
mounting media, opening QLab Workspace Status, or checking DMX/Art-Net/sACN
output. These are derived hints, not claims about the actual room output.

The MCP reconstructs health from OSC-readable fields such as `isBroken`,
`isWarning`, cue type, targets, message errors, and settings. It does not claim
to read the full Workspace Status window directly because QLab's documented OSC
dictionary does not expose a single complete Workspace Status warnings endpoint.

## Privacy And Safety

The six inspector tools are read-only. The three write-mode tools are separate,
gated, and disabled by default.

`safe` is the normal profile. It is meant for agent use and redacts sensitive
infrastructure where possible: destinations, routes, devices, passcodes,
credentials, and similar details.

`technical` is for deliberate technical audits. It can reveal IP addresses,
ports, interfaces, screens, devices, routes, raw regions, mesh/warp data,
audio-map levels, light patch payloads, and routing payloads.

`full_sensitive` is deeper still. It can expose cue notes, local media paths,
scripts, and heavy stage payloads. Use it only when that exposure is intentional.

`auto` is designed to be useful for technical inspection and may include compact
type-specific fields such as `lightCommandText`. Use `basic_safe` or `health`
when you want a stricter privacy posture.

Redaction records include an `impact` field so agents can tell which conclusions
are limited, such as exact network destination, display identity, route details,
or hidden credentials.

Write mode is deliberately gated:

- `QLAB_PASSCODE` is a server-side credential and is never a tool argument.
- `qlab_check_connection` uses `/connect` as the source of truth for
  `view`, `edit`, and `control` permission scopes when `QLAB_PASSCODE` is set.
- `qlab_check_connection` and `qlab_get_workspace_overview` read `/showMode`
  so callers can tell whether the workspace is in Edit Mode or Show Mode.
- `qlab_check_write_readiness` does not mutate anything.
- `qlab_check_write_readiness` reports `batch_update_cues` capabilities for
  `qlab_update_cues`; `edit_existing_cue` may appear only as a compatibility
  alias for older callers.
- `qlab_create_cue` and `qlab_update_cues` are blocked unless `QLAB_ENABLE_WRITE=true` and
  `QLAB_PASSCODE` is configured, `/connect` confirms `edit`, and `/showMode`
  confirms the workspace is in Edit Mode.
- `dry_run` defaults to true through `QLAB_WRITE_DRY_RUN_DEFAULT=true`.
- `qlab_create_cue(..., dry_run=true)` and `qlab_update_cues(..., dry_run=true)`
  are planning-only and can run without enabling write mode or configuring a passcode.
- Real writes bypass and clear the read cache before verifying fresh cue details.
- Only blank cue creation is allowed in this preface.
- Allowed cue types are `memo`, `group`, `wait`, and `audio`.
- `qlab_update_cues` uses a registry of cue-family profiles:
  `common`, `memo_basic`, `wait_basic`, `group_basic`, `audio_basic`, `mic_basic`,
  `video_basic`, `camera_basic`, `text_basic`, `light_basic`, `fade_basic`,
  `network_basic`, `midi_basic`, `midi_file_basic`, `timecode_basic`,
  `target_basic`, `reset_basic`, `devamp_basic`, and `script_basic`.
- `qlab_get_cue_details(..., profile="editable")` returns safe current cue
  details plus `update_capabilities` derived from the same update registry, so
  agents can choose compatible edit profiles, real-write properties,
  dry-run-only properties, operation args, validators, and required write gates
  without sending mutating OSC.
- Policy summary: all update profiles can exist for planning and targeting,
  but real write is limited to safe properties only. Dangerous properties are
  dry-run-only and are blocked when `dry_run=false`.
- `properties={...}` remains the simple one-argument setter path.
- `operations=[...]` supports structured setters such as audio levels, crop,
  text colors, and MIDI fields in dry-run plans.
- `qlab_update_cues` accepts 1-50 update items in one MCP call. Each item can
  use a different concrete `cue_ref`, `profile`, `properties`, and `operations`
  set. Real batch writes complete all preflight checks before sending any setter
  and use `/cue_id/{uniqueID}/...` addresses for mutation.
- Every cue-family profile can real-write safe one-argument setters with direct
  fresh readback. This includes common props plus `group_basic` metadata,
  `audio_basic` transport metadata, `text_basic` simple text formatting,
  `mic_basic` channel metadata, `video_basic`/`camera_basic` one-axis geometry,
  `midi_file_basic` playback metadata, and `timecode_basic` metadata.
- High-risk profiles and unvalidated properties are cataloged for dry-run only:
  routing, targets, file paths, light commands, network/MIDI output, scripts,
  audio levels, slices, objects, live variants, text ranges/colors, and
  multi-argument geometry.
- If a setter times out but a fresh after-read confirms the requested value,
  `qlab_update_cues` reports `updated_with_confirmed_timeouts` with a warning
  instead of treating the item as failed.
- When write readiness or batch updates fail, results include stable
  `error_code` and `suggested_action` fields so agents can decide whether to
  fix configuration, retry a smaller batch, or inspect QLab manually.
- Fresh verification tolerates QLab's harmless normalization for numeric values,
  `continueMode` labels, and safe enum-like strings such as `colorName`,
  `blendMode`, `clockType`, and `text/format/alignment`; free text remains
  exact-match.
- Playback control, raw OSC, GO, stop, panic, and ambiguous selected/active
  edits are not exposed. Target edits, file paths, scripts, and routing changes
  are dry-run-only catalog entries.

## Tool Signatures

```text
qlab_check_connection(workspace_id=None, require_read_access=True)
qlab_get_workspace_overview(workspace_id=None, max_depth=2, max_cues=1000, include_live_state=False, include_cue_index=True, max_index_cues=1000, cue_index_profile="minimal")
qlab_get_workspace_settings(workspace_id, sections=None)
qlab_get_workspace_setting_details(workspace_id, section, kind=None, ref=None, profile="safe")
qlab_query_cues(workspace_id, primary_filter, primary_value, optional_filters=None, profile="basic_safe", max_results=500, max_cues_scanned=500)
qlab_get_cue_details(workspace_id, cue_ref, profile="auto")  # profile also supports "editable"
qlab_check_write_readiness(workspace_id)
qlab_create_cue(workspace_id, cue_type, properties=None, dry_run=None, after_cue_id=None)
qlab_update_cues(workspace_id, updates, dry_run=None)
```

`qlab_update_cues` update items use this shape:

```json
{
  "cue_ref": "1",
  "profile": "common",
  "properties": {"name": "New name"},
  "operations": []
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

## Query Filters

`qlab_query_cues` requires one primary filter and accepts optional AND filters.

Common filters:

- `type`
- `flagged`
- `armed`
- `disarmed`
- `isBroken`
- `isWarning`
- `colorName`
- `name_contains`
- `number_prefix`
- `cue_list_id`
- `parent_id`
- `hasFileTargets`
- `hasCueTargets`
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
```

Notes:

- QLab listens for OSC on port `53000` by default.
- QLab sends UDP replies to `53001` by default.
- `QLAB_REPLY_PORT=0` is useful for automated tests with a fake OSC server.
- `QLAB_CACHE_TTL=0` disables the short read cache.
- Live selected/running/active state bypasses the cache.
- Queries using live state filters such as `isRunning`, `isPaused`, `isLoaded`,
  `isOverridden`, or `isAuditioning` bypass the cache.
- Sensitive `technical` and `full_sensitive` reads bypass the cache.
- Write mode is disabled by default. When enabled, real writes require
  `QLAB_PASSCODE`, `edit` confirmed by `/connect`, Edit Mode confirmed by
  `/showMode`, and bypass/clear the read cache before fresh verification.
- `QLAB_UPDATE_DEBUG=true` adds per-cue debug details to `qlab_update_cues`
  results for troubleshooting batch verification.

## Run

```bash
uv sync --extra dev
uv run qlab-mcp
```

or:

```bash
uv run fastmcp run src/qlab_mcp/server.py:mcp
```

## Manual QLab Check

1. Open QLab 5.
2. Open or create a workspace with at least one cue list and one cue.
3. Enable OSC access for the workspace if needed.
4. Start this MCP server.
5. Call `qlab_check_connection`.
6. If several workspaces are open, pass a `workspace_id` from `available_workspaces`.
7. Call `qlab_get_workspace_overview`.
8. Call `qlab_get_workspace_settings`.
9. Use `qlab_query_cues` to find candidate cues.
10. Use `qlab_get_cue_details` or `qlab_get_workspace_setting_details` for focused inspection.

For large lighting workspaces, also check:

```text
qlab_get_workspace_setting_details(section="light", kind="light_patch")
```

The expected safe result should summarize the light patch. If the UDP reply is
too large, the result should still succeed through `read_transport="tcp_fallback"`.
That means TCP was used to retrieve a large response; it does not imply output
failure, missing controllers, or degraded physical playback.

For passcode-protected workspaces, set `QLAB_PASSCODE` before starting the MCP.

For write-mode smoke checks on a copy of a workspace:

1. Set `QLAB_ENABLE_WRITE=true`.
2. Keep `QLAB_WRITE_DRY_RUN_DEFAULT=true`.
3. Set `QLAB_PASSCODE` on the server.
4. Call `qlab_check_write_readiness(workspace_id=...)` and confirm `edit` is
   granted by `/connect`.
5. Call `qlab_create_cue(..., dry_run=true)` or `qlab_update_cues(..., dry_run=true)`
   and inspect `planned_operations`.
6. Only then call the same tool with `dry_run=false` on a safe test workspace.
