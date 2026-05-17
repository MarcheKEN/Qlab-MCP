# QLab MCP

Read-only FastMCP server for QLab 5 cue information over OSC.

## What this first phase supports

- Check whether QLab, open workspace candidates, passcode permissions, and read access are ready.
- Build a bounded first-pass workspace overview that maps the show structure.
- Query cues in bulk with one required filter plus optional AND filters.
- Read grouped cue details using `basic_safe`, `basic`, `health`, `technical`, `timing`, `status`, `targets`, `group`, `type_specific`, `full`, or `full_sensitive`.
- Compose internal read-only OSC calls for workspaces, cue lists, cue IDs, children, and `valuesForKeys`.

This phase does not expose playback, editing, deletion, raw OSC, patches/settings inventory, or other mutating commands.

## Tool overview

- `qlab_check_connection(workspace_id=None, require_read_access=True)`
- `qlab_get_workspace_overview(workspace_id=None, max_depth=2, max_cues=200, include_live_state=False)`
- `qlab_query_cues(workspace_id, primary_filter, primary_value, optional_filters=None, profile="basic_safe", max_results=100, max_cues_scanned=1000)`
- `qlab_get_cue_details(workspace_id, cue_ref, profile="basic_safe")`

For setup diagnostics, start with `qlab_check_connection(...)`. It verifies that QLab answers `/workspaces`, returns `available_workspaces`, resolves the intended workspace when possible, reports UDP host/ports, and by default confirms that the MCP can read `/cueLists/shallow`; this catches passcode, View permission, OSC port, and workspace-open problems before a larger scan. The result includes a `permissions` block: View can be confirmed safely with `safe_to_probe=true`, while Edit and Control are reported as `not_checked` with `safe_to_probe=false` because QLab does not expose passcode scopes through a read-only OSC query.

For first-pass orientation, continue with `qlab_get_workspace_overview(...)`. It uses shallow child reads and explicit limits so a client can understand what the show contains and how it is organized: workspace metadata, cue lists, nested cues, cue IDs, numbers, names, types, basic status, type counts, and truncation status without requesting every property of every cue. Set `include_live_state=true` only when you also need a shallow snapshot of selected and running-or-paused cues.

For cue searches, use `qlab_query_cues(...)` instead of creating separate tools for each cue type or health state. It reads IDs with `/cueLists/uniqueIDs`, asks each cue for allowlisted values with `valuesForKeys`, then filters locally. The required `primary_filter` can be `type`, `flagged`, `armed`, `isBroken`, `isWarning`, `isRunning`, `isPaused`, `colorName`, `name_contains`, `number_prefix`, `cue_list_id`, or `parent_id`; `optional_filters` use the same names and are combined with AND.

For detailed inspection, use `qlab_query_cues` to find candidate cue IDs, then call `qlab_get_cue_details` only for the cues that need deeper inspection. Detail profiles are batched internally with QLab `valuesForKeys` when possible. Prefer `basic_safe` or `health` first; use `technical` for notes, routing, and targets; use `full` for a broad non-sensitive read; reserve `full_sensitive` for deep audits because it can expose notes, local paths, or scripts.

The public interface is intentionally limited to four tools. Lower-level reads such as workspaces, cue lists, cue IDs, children, selected/running cues, custom values, and single-property reads remain internal implementation details.

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
6. Call `qlab_query_cues` for filtered sets, for example `primary_filter="type"`, `primary_value="Audio"`.
7. Call `qlab_get_cue_details` for a specific `uniqueID` returned by the overview or query result.

For passcode-protected workspaces, set `QLAB_PASSCODE` before starting the MCP.

