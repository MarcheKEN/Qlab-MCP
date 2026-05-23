# QLab MCP

Read-only FastMCP server for QLab 5 cue information over OSC.

## What this first phase supports

- Check whether QLab, open workspace candidates, passcode permissions, and read access are ready.
- Build a bounded first-pass workspace overview plus a compact cue index that maps the full show.
- Read compact workspace settings infrastructure, then inspect one setting item in detail when needed.
- Query cues in bulk with one required filter plus optional AND filters.
- Read type-aware cue details using `auto`, `basic_safe`, `basic`, `health`, `technical`, `timing`, `status`, `targets`, `group`, `type_specific`, `full`, or `full_sensitive`.
- Compose internal read-only OSC calls for workspaces, cue lists, cue IDs, children, settings, and `valuesForKeys`.

This phase does not expose playback, editing, deletion, raw OSC, or other mutating commands.

## Tool overview

- `qlab_check_connection(workspace_id=None, require_read_access=True)`
- `qlab_get_workspace_overview(workspace_id=None, max_depth=2, max_cues=1000, include_live_state=False, include_cue_index=True, max_index_cues=1000)`
- `qlab_get_workspace_settings(workspace_id, sections=None)`
- `qlab_get_workspace_setting_details(workspace_id, section, kind=None, ref=None, profile="safe")`
- `qlab_query_cues(workspace_id, primary_filter, primary_value, optional_filters=None, profile="basic_safe", max_results=500, max_cues_scanned=500)`
- `qlab_get_cue_details(workspace_id, cue_ref, profile="auto")`

For setup diagnostics, start with `qlab_check_connection(...)`. It verifies that QLab answers `/workspaces`, returns `available_workspaces`, resolves the intended workspace when possible, reports UDP host/ports, and by default confirms that the MCP can read `/cueLists/shallow`; this catches passcode, View permission, OSC port, and workspace-open problems before a larger scan. The result includes a `permissions` block: View can be confirmed safely with `safe_to_probe=true`, while Edit and Control are reported as `not_checked` with `safe_to_probe=false` because QLab does not expose passcode scopes through a read-only OSC query.

For first-pass orientation, continue with `qlab_get_workspace_overview(...)`. It uses shallow child reads and explicit limits so a client can understand what the show contains and how it is organized: workspace metadata, a bounded cue-list tree preview, cue IDs, numbers, names, types, basic status, type counts, and truncation status without requesting every property of every cue. By default both the tree preview and `cue_index` are capped at 1000 cues. The tree preview is intentionally bounded by `max_depth`/`max_cues`; the `cue_index` is the compact `columns`/`rows` map up to `max_index_cues`, with identity, parent/list/depth, armed/flagged/color, broken/warning state, and `continueModeLabel`. Set `include_live_state=true` only when you also need a shallow snapshot of selected and running-or-paused cues.

For infrastructure inventory, use `qlab_get_workspace_settings(...)`. It reads QLab Workspace Settings via read-only OSC endpoints such as `/settings/audio/patchList`, `/settings/video/stages`, `/settings/video/routes`, `/settings/network/patchList`, and `/settings/midi/patchList`, then returns a compact safe overview with names, IDs, counts, routing presence, stage/route relationships, connection state, and general settings. It does not call the potentially heavy `/settings/light/patch`; the light section reports that detailed inspection is available. When `qlab_get_workspace_setting_details(...)` reads the light patch, the MCP tries UDP first and falls back to QLab's TCP OSC transport if UDP times out, because QLab documents this endpoint as verbose and large replies can exceed UDP datagram limits. The light patch summary includes `read_transport` when the read succeeds, so callers can tell whether UDP or `tcp_fallback` was used.

For deep infrastructure inspection, use `qlab_get_workspace_setting_details(...)` after the compact settings overview. It can inspect one audio patch/map, video stage/route/input patch, network patch, MIDI patch, or the light patch. If `ref` is omitted and several candidates exist, it returns choices instead of guessing. The default `safe` profile is normalized and compact: video stages return stage/region/route summaries instead of raw control points, audio maps report marks/objects/filters without long level arrays, and light patches return a group list plus an `instrument_index` instead of the full nested patch. Use `technical` only for explicit audits; it can include diagnostic IPs, ports, interfaces, device details, raw video regions, geometry, mesh/warp, audio-map levels, light-patch payloads, and routing payloads. Passcodes and credentials are always redacted.

For cue searches, use `qlab_query_cues(...)` instead of creating separate tools for each cue type or health state. It reads IDs with `/cueLists/uniqueIDs`, asks each cue for allowlisted values with `valuesForKeys`, then filters locally. The required `primary_filter` can be `type`, `flagged`, `armed`, `disarmed`, `isBroken`, `isWarning`, `isRunning`, `isPaused`, `isLoaded`, `isOverridden`, `isAuditioning`, `colorName`, `name_contains`, `number_prefix`, `cue_list_id`, `parent_id`, `hasFileTargets`, `hasCueTargets`, `skipIfDisarmed`, `autoLoad`, `continueMode`, `hasPreWait`, `hasPostWait`, or `hasDuration`; `optional_filters` use the same names and are combined with AND. By default the tool scans and returns up to 500 cues, and reports `truncated=true` with counts when more data exists. Use the overview `cue_index` for the broader compact map up to 1000 cues.

For detailed inspection, use `qlab_query_cues` to find candidate cue IDs, then call `qlab_get_cue_details` only for the cues that need deeper inspection. The default `auto` profile first reads safe common cue state, detects the cue type, then adds safe type-specific sections such as audio routing, compact video/stage fields, light command text, network message, MIDI/timecode patch, group playback state, or cue-target transport fields. It keeps a flat `properties` object for compatibility and adds `cue_type` plus `sections.identity`, `sections.structure`, `sections.status`, `sections.timing`, `sections.targets`, and `sections.type_specific`. `auto`, `health`, and `targets` do not return `notes`, `fileTarget`, or `scriptSource`; they report file-target presence without local file paths. Large video stage payloads such as `stage` and `stage/regions` are excluded from `auto`, `type_specific`, and `full`. Use `technical` for notes, routing, targets, local file paths, and heavy stage diagnostics; reserve `full_sensitive` for deep audits because it can expose notes, local paths, scripts, and heavy stage payloads.

The public interface is intentionally limited to six read-only tools. Lower-level reads such as workspaces, cue lists, cue IDs, children, selected/running cues, settings endpoints, custom values, and single-property reads remain internal implementation details.

## Configuration

The server reads QLab connection settings from environment variables:

```text
QLAB_HOST=127.0.0.1
QLAB_OSC_PORT=53000
QLAB_REPLY_PORT=53001
QLAB_TIMEOUT=2.0
QLAB_PASSCODE=
```

QLab listens for OSC on port `53000` by default and sends UDP replies to `53001` by default.

`QLAB_REPLY_PORT=0` is useful in automated tests with a fake OSC server that replies to the source port. It is not recommended with real QLab unless the client explicitly negotiates the reply port, because QLab's default UDP reply port is `53001`.

## Run

```bash
uv sync --extra dev
uv run qlab-mcp
```

or:

```bash
uv run fastmcp run src/qlab_mcp/server.py:mcp
```

## Manual QLab check

1. Open QLab 5.
2. Open or create a workspace with at least one cue list and one cue.
3. Enable OSC access for the workspace if needed.
4. Call `qlab_check_connection`; pass `workspace_id` if multiple workspaces are open, using one of the returned `available_workspaces`.
5. Call `qlab_get_workspace_overview` with that `workspace_id`, or omit `workspace_id` if exactly one workspace is open.
6. Call `qlab_get_workspace_settings` when you need compact patches, routes, stages, network/MIDI/light infrastructure, or general settings.
7. Call `qlab_get_workspace_setting_details` for one patch, route, stage, map, or light patch that needs deeper inspection.
8. Call `qlab_query_cues` for filtered sets, for example `primary_filter="type"`, `primary_value="Audio"`.
9. Call `qlab_get_cue_details` for a specific `uniqueID` returned by the overview or query result.

For passcode-protected workspaces, set `QLAB_PASSCODE` before starting the MCP.

