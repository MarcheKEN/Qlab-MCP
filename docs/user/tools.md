# Public MCP Tools

QLab MCP 0.3.0 exposes exactly 13 tools. This page is a compact human
catalogue; decorated functions, generated schemas, and
`tests/test_server_tools.py` remain the source of truth for exact parameters,
annotations, and result models.

| Tool | Purpose | Not for | Workflow |
| --- | --- | --- | --- |
| `qlab_check_connection` | Reachability, workspace candidates, scopes, and mode | Write readiness or cue details | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_overview` | Bounded cue-list/group/cart structure | Deep properties or operational status | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_status` | Derived status, warnings, and timecode context | A full QLab Status-window clone | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_settings` | Settings summary or independent detail requests | Mutating patches/routes | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_setting_details` | One settings detail request | Batch settings discovery | [Read](agent-workflows.md#read-sequence) |
| `qlab_query_cues` | Bounded filtered cue discovery | Full Inspector payloads | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_cue_details` | Exact cue properties and health | Ambiguous write target resolution | [Read](agent-workflows.md#read-sequence) |
| `qlab_check_write_readiness` | Read-only preflight before any write | Confirmation or authorization alone | [Common write gate](agent-workflows.md#common-write-gate) |
| `qlab_create_cue` | One template-backed structural creation | Initial setters, playback, or GO | [Create](agent-workflows.md#create-one-cue) |
| `qlab_create_cues` | Ordered sequential creation, 1–50 items | Atomic transaction or rollback | [Create batch](agent-workflows.md#create-a-sequence) |
| `qlab_edit_cues` | Allowlisted property/operation edits, 1–50 items | Create, Move, Delete, playback, or raw OSC | [Edit](agent-workflows.md#edit-existing-cues) |
| `qlab_move_cues` | Sequential structural moves, 1–10 UUID targets | Playback or unproven Cart writes | [Move](agent-workflows.md#move-existing-cues) |
| `qlab_delete_cues` | Explicit leaves, one empty Group, or root-preserving recursive emptying | Root deletion or automatic rollback | [Delete](agent-workflows.md#delete-cues) |

## Shared contract

- Writes default to dry-run and require readiness, exact targets, fresh
  confirmation, and post-write readback.
- Edit confirmation is per planned operation; Create, Move, and Delete use
  dedicated token families.
- Batches are sequential/non-transactional unless a tool description says
  otherwise. Timeout or identity ambiguity means inspect first; do not retry.
- `destructiveHint` is MCP metadata, not authorization. Runtime gates remain
  authoritative.
- The server intentionally exposes no GO, stop, panic, playback, Audition,
  raw OSC, AppleScript write, or `/live` workflow.

For full examples and failure handling, use the
[agent workflow guide](agent-workflows.md). For maintainer evidence, use the
[Create](../development/runtime-validation/create-cues.md) and
[Edit](../development/runtime-validation/edit-cues.md) checklists.

Inspect the generated contract without connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```
