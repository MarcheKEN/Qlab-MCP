# QLab MCP

Read-only FastMCP server for QLab 5 cue information over OSC.

## What this first phase supports

- List open QLab workspaces.
- Read cue lists and cue carts for an explicit workspace.
- Read all cue unique IDs in a workspace through `/cueLists/uniqueIDs`.
- Build a workspace cue inventory, optionally with detail profiles for every cue.
- Read selected cues.
- Read running or paused cues.
- Read children of a cue list, cue cart, or group cue.
- Read grouped cue details using `basic`, `timing`, `status`, `targets`, `group`, `type_specific`, or `full`.
- Read custom batches of allowlisted cue state using QLab's `valuesForKeys` method.
- Read one allowlisted cue property.

This phase does not expose playback, editing, deletion, raw OSC, patches/settings inventory, or other mutating commands.

## Tool overview

- `qlab_get_workspaces()`
- `qlab_get_cue_lists(workspace_id, include_children=True)`
- `qlab_get_workspace_cue_ids(workspace_id, include_children=True)`
- `qlab_get_workspace_cue_inventory(workspace_id, include_details=False, detail_profile="basic")`
- `qlab_get_selected_cues(workspace_id, include_children=True)`
- `qlab_get_running_cues(workspace_id, include_paused=True, include_children=True)`
- `qlab_get_cue_children(workspace_id, cue_ref, shallow=False, ids_only=False)`
- `qlab_get_cue_details(workspace_id, cue_ref, profile="basic")`
- `qlab_get_cue_values(workspace_id, cue_ref, keys=[...])` - keys must be allowlisted read-only cue properties.
- `qlab_read_cue_property(workspace_id, cue_ref, property_path)`

For a full workspace scan, start with `qlab_get_workspace_cue_inventory(..., include_details=False)` to get IDs cheaply. Then call `qlab_get_cue_details` or `qlab_get_cue_values` only for the cues that need deeper inspection. This avoids very large UDP replies.

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
4. Call `qlab_get_workspaces` and copy the workspace `uniqueID`.
5. Call `qlab_get_workspace_cue_ids` with that `workspace_id`.
6. Call `qlab_get_workspace_cue_inventory` with `include_details=true` and `detail_profile="basic"`.
7. Select a cue in QLab and call `qlab_get_selected_cues`.
8. Run or pause a cue and call `qlab_get_running_cues`.
9. Call `qlab_get_cue_values` for a known cue number, for example with keys `name`, `type`, and `duration`.

For passcode-protected workspaces, set `QLAB_PASSCODE` before starting the MCP.

