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
then pass the returned dedicated `confirm:createCue:v1` token for real
creation. Edit tokens belong to individual `updates[].confirm_gates`; Move and
Delete use one dedicated tool-level token. Restarting the MCP invalidates
process-bound tokens.

See the [13 public tools](tools.md) and the
[runtime edit checklist](../development/runtime-validation/edit-cues.md).
