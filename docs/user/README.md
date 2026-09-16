# User Guide

QLab MCP 0.3.0 inspects QLab 5 and provides narrowly gated structural writes.
It does not expose playback or raw OSC.

## Start

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run qlab-mcp
```

Inspect the MCP contract without connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```

## Safe orientation

1. Call `qlab_check_connection` and choose one workspace by exact UUID.
2. Read `qlab_get_workspace_overview` for bounded structure.
3. Read `qlab_get_workspace_status` for derived operational context and
   `qlab_get_workspace_settings(mode="summary")` for infrastructure context.
4. Discover targets with `qlab_query_cues`; inspect exact properties with
   `qlab_get_cue_details`.

Use compact profiles for normal work. Technical, sensitive, and exhaustive
profiles can expose larger or more sensitive show data.

## Writes

Writes default to dry-run. The complete multi-tool sequences and good/invalid
examples live in the [agent workflow guide](agent-workflows.md).

### Preflight

Use `qlab_check_write_readiness` before every real Create, Edit, Move, Delete,
or Workspace Settings write.
It is a read-only preflight, not a confirmation token.

### Create

Use [`qlab_create_cue`](agent-workflows.md#create-one-cue) for one
template-backed cue, or [`qlab_create_cues`](agent-workflows.md#create-a-sequence)
for an ordered non-atomic sequence. Creation verifies structure and placement;
it does not configure initial setters or claim GO readiness.

### Edit

[`qlab_edit_cues`](agent-workflows.md#edit-existing-cues) resolves exact cues
and uses per-operation confirmation gates. Batches are non-atomic.

### Move

[`qlab_move_cues`](agent-workflows.md#move-existing-cues) uses UUID-only targets,
one placement form, sequential execution, and fresh parent/order readback.

### Delete

[`qlab_delete_cues`](agent-workflows.md#delete-cues) deletes explicit leaves,
one exact empty Group, or empties one container deepest-first while preserving
its root.

## Evidence boundary

Keep this distinction explicit:

```text
planned structure
!= runtime validated
!= show ready for GO
```

See the [14-tool catalogue](tools.md),
[security policy](../../SECURITY.md), and
[Create checklist](../development/runtime-validation/create-cues.md) and
[Edit checklist](../development/runtime-validation/edit-cues.md).
