# Public MCP Tools

QLab MCP exposes exactly 23 tools on the current development branch. This page is a compact human
catalogue; decorated functions, generated schemas, and
`tests/test_server_tools.py` remain the source of truth for exact parameters,
annotations, and result models.

| Tool | Purpose | Not for | Workflow |
| --- | --- | --- | --- |
| `qlab_check_connection` | Reachability, workspace candidates, scopes, and mode | Write readiness or cue details | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_overview` | Bounded cue-list/group/cart structure | Deep properties or operational status | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_status` | Derived cue warnings, known Video Settings problems, and timecode context | A complete QLab Status-window warning total | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_general_settings` | Minimum GO time and selection/playhead lock | The complete General panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_audio_settings` | Audio overview or exact output/input patch; optional single output-patch crosspoint | Audio Maps, full-matrix scans, or patch mutation | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_video_settings` | Compact Video inputs, routes, and stages | Exact object detail | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_video_stage` | Exact stage UUID and its regions, safe or technical | Stage mutation or name selection | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_video_output_route` | Exact output route UUID and destination, safe or technical | Independent device inventory or mutation | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_light_settings` | Light Patch summary or redacted technical payload | Light Definitions or Dashboard settings | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_network_settings` | Network Patch inventory or exact patch | The complete Network panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_midi_settings` | MIDI Patch inventory or exact patch | The complete MIDI panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_query_cues` | Bounded filtered cue discovery | Full Inspector payloads | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_cue_lists` | Compact combined Cue List / Cue Cart inventory and current container | Child or deep container details | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_list_details` | Exact list identity, state, playhead, incoming timecode and bounded tree | AppleScript-only timecode source settings | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_cart_details` | Exact cart identity, state, timecode, grid and occupied cell positions | Playhead, nested Groups or deep child Inspector | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_details` | Exact cue properties and health | Ambiguous write target resolution | [Read](agent-workflows.md#read-sequence) |
| `qlab_check_write_readiness` | Read-only preflight before any write | Confirmation or authorization alone | [Common write gate](agent-workflows.md#common-write-gate) |
| `qlab_create_cue` | One template-backed structural creation | Initial setters, playback, or GO | [Create](agent-workflows.md#create-one-cue) |
| `qlab_create_cues` | Ordered sequential creation, 1–50 items | Atomic transaction or rollback | [Create batch](agent-workflows.md#create-a-sequence) |
| `qlab_edit_cues` | Allowlisted property/operation edits, 1–50 items | Create, Move, Delete, playback, or raw OSC | [Edit](agent-workflows.md#edit-existing-cues) |
| `qlab_edit_workspace_settings` | One exact `general.minGoTime` write in seconds | Other settings writes, playback, GO, or raw OSC | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_move_cues` | Sequential structural moves, 1–10 UUID targets | Playback or unproven Cart writes | [Move](agent-workflows.md#move-existing-cues) |
| `qlab_delete_cues` | Explicit leaves, one empty Group, or root-preserving recursive emptying | Root deletion or automatic rollback | [Delete](agent-workflows.md#delete-cues) |

## Shared contract

- Writes default to dry-run and require readiness, exact targets, fresh
  confirmation, and post-write readback.
- Edit confirmation is per planned operation; Create, Move, Delete, and
  `qlab_edit_workspace_settings` use dedicated confirmation flows.
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
