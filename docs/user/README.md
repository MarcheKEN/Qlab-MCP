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
3. Read `qlab_get_workspace_status` for derived operational context and call
   only the relevant `qlab_get_workspace_*_settings` domain tools for infrastructure.
4. Use the cue-family inventories and UUID detail tools for a known type and Cue
   List. Use `qlab_query_cues` for cross-type discovery and `qlab_get_cue_details`
   for generic health, target, or editable diagnostics.

Use compact profiles for normal work. Technical, sensitive, and exhaustive
profiles can expose larger or more sensitive show data.

For reviewing dependencies, planning a scene, renumbering, copying selected
properties or calculating relative changes, follow
[Workspace review and authoring](workspace-authoring.md). Reviews stay read-only
unless the user authorizes the changes. A project skill links to the same guide;
it is not installed by the Python package.

For document lifecycle, use the local inventory and gated open/save/clean-close
tools only after reviewing the [workspace document workflow](agent-workflows.md#workspace-documents).

## Writes

Writes default to dry-run. The complete multi-tool sequences and good/invalid
examples live in the [agent workflow guide](agent-workflows.md).

### Preflight

Use `qlab_check_write_readiness` before every real Create, Edit, Move, Delete,
or Workspace Settings write.
It is a read-only preflight, not a confirmation token.

### Create

Use [`qlab_create_cues`](agent-workflows.md#create-cues) for one to 100 ordered
template-backed cues in an exact Cue List, Group, or empty Cue Cart. Creation verifies structure and placement;
it does not configure initial setters or claim GO readiness.

### Edit

Family-specific cue editors resolve exact UUIDs and apply typed saved properties
with signed per-operation confirmation. See [cue editing](agent-workflows.md#edit-existing-cues).
The public generic editor has been removed.

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

See the [public tool catalogue](tools.md),
[security policy](../../SECURITY.md), and
[Create checklist](../development/runtime-validation/create-cues.md) and
[Cue editor runtime checklist](../development/runtime-validation/edit-cues.md).
