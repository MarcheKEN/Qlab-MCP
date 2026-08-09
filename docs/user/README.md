# User Guide

QLab MCP 0.2.0 inspects QLab 5 and provides narrowly gated write workflows. It
does not expose playback or raw OSC.

## Start

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run qlab-mcp
```

`qlab-mcp` is the only public start command. Inspect the MCP contract without
connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```

## Safe orientation

1. Call `qlab_check_connection`.
2. If several workspaces are open, select one by exact UUID.
3. Read `qlab_get_workspace_overview`.
4. Read `qlab_get_workspace_status`.
5. Use `qlab_get_workspace_settings(mode="summary")`.
6. Find cues with `qlab_query_cues`; inspect them with
   `qlab_get_cue_details`.

Use `safe`, `basic_safe`, or `inspector_safe` profiles for normal work.
Technical, sensitive, and exhaustive profiles can expose local show data.

## Writes

Writes are disabled by default. Before any authorized write:

1. Use an explicit workspace UUID.
2. Call `qlab_check_write_readiness`.
3. Review a dry-run.
4. Supply only the exact confirmation token required by that operation.
5. Send one intended setter and require fresh readback.
6. Roll back with a new dry-run and new token when the workflow requires one.

`qlab_create_cue` requires an exact `after_cue_id` anchor. Review its dry-run,
then pass the returned dedicated `confirm:createCue:v2` token for real
creation. Use exactly one of `after_cue_id` or `parent_container_id`; the
latter handles the first cue in an empty Cue List, Group, or Cue Cart with the
container-specific OSC route. Cue Cart creation requests `0,0`; QLab 5.5.10
reports that first cell as `1,1`, which is verified as the expected readback.
Edit tokens belong to individual `updates[].confirm_gates`; Move and
Delete use one dedicated tool-level token. Restarting the MCP invalidates
process-bound tokens.

Create sends `/new` at most once. If QLab times out or returns an identity that
cannot be proven, stop without applying properties or retrying. The result may
set `cleanup_required=true`; inspect the workspace manually and use a fresh
Delete dry-run/token only after the created UUID is unambiguous. Create has no
automatic cleanup or fallback backend. Workorder 031 runtime evidence covers
only one blank anchored Wait; the other allowlisted types and property families
remain source/test-supported but runtime-uncertified.

See the [13 public tools](tools.md), the
[runtime Create checklist](../development/runtime-validation/create-cues.md), and the
[runtime edit checklist](../development/runtime-validation/edit-cues.md).
