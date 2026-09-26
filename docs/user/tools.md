# Public MCP Tools

QLab MCP exposes exactly 48 tools on the current development branch. This page is a compact human
catalogue; decorated functions, generated schemas, and
`tests/test_server_tools.py` remain the source of truth for exact parameters,
annotations, and result models.

| Tool | Purpose | Not for | Workflow |
| --- | --- | --- | --- |
| `qlab_get_control_cues` | Scoped inventory of twelve control/organization types, optionally filtered by type | Carts, whole workspace or executing controls | [Control cues](agent-workflows.md#control-and-organization-cues) |
| `qlab_get_control_cue_details` | Common OSC fields plus type-specific target, Reset and Devamp configuration | Executing actions, Audio Maps or patch expansion | [Control cues](agent-workflows.md#control-and-organization-cues) |
| `qlab_get_fade_cues` | Scoped Fade inventory | Cue Carts or target expansion | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_fade_cue_details` | Exact Fade target, mode and documented levels/geometry | Actions or unverified inherited fields | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_network_cues` | Scoped Network inventory | Cue Carts or patch expansion | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_network_cue_details` | Network patch, fade and parameter configuration | Sending messages; message text and errors require technical | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_midi_cues` | Scoped MIDI and MIDI File inventory with type filter | Cue Carts | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_midi_cue_details` | MIDI Voice/MSC/SysEx or MIDI File, selected by concrete type | Sending MIDI or inspecting file events | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_timecode_cues` | Scoped Timecode inventory | Cue Carts | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_timecode_cue_details` | MTC/LTC configuration and relevant patch reference | Generating timecode or patch expansion | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_script_cues` | Scoped Script inventory | Cue Carts | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_script_cue_details` | Common cue detail; script source in technical | Compiling or executing scripts | [Remaining cues](agent-workflows.md#fade-network-midi-timecode-and-script-cues) |
| `qlab_get_light_cues` | Scoped Light inventory | Carts or patch expansion | [Light/Group](agent-workflows.md#light-and-group-cues) |
| `qlab_get_light_cue_details` | Command text, collate, subcontroller, state and timing | Executing commands or computing DMX | [Light/Group](agent-workflows.md#light-and-group-cues) |
| `qlab_get_group_cues` | Scoped Group inventory | Lists/carts as Groups | [Light/Group](agent-workflows.md#light-and-group-cues) |
| `qlab_get_group_cue_details` | Mode, Playlist and bounded children | Full descendant details | [Light/Group](agent-workflows.md#light-and-group-cues) |
| `qlab_get_video_cues` | Compact Video inventory within a required Cue List UUID | Carts, other lists or deep properties | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_video_cue_details` | Exact Video cue geometry, timing, loops and audio | Stage/patch expansion, live or indexed effects | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_text_cues` | Compact Text inventory within a required Cue List UUID | Carts, other lists or deep properties | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_text_cue_details` | Exact Text cue geometry, content and formatted fragments | Stage/patch expansion, live or indexed effects | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_camera_cues` | Compact Camera inventory within a required Cue List UUID | Carts, other lists or deep properties | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_camera_cue_details` | Exact Camera cue geometry, input patch references and audio | Stage/patch expansion, live or indexed effects | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_audio_cues` | Compact paged Audio inventory within one required Cue List UUID, including groups | Carts, whole-workspace queries or deep properties | [Audio](agent-workflows.md#audio-cues) |
| `qlab_get_mic_cues` | Compact paged Mic inventory within one required Cue List UUID, including groups | Carts or whole-workspace queries | [Mic](agent-workflows.md#mic-cues) |
| `qlab_get_mic_cue_details` | Exact Mic cue input/output patch references, channels, state, timing and levels | Patch configuration, Audio Maps, Objects or indexed effects | [Mic](agent-workflows.md#mic-cues) |
| `qlab_get_audio_cue_details` | Exact Audio cue identity, state, timing, patch reference, slices and levels | Audio Maps, Audio Objects or effect-index scans | [Audio](agent-workflows.md#audio-cues) |
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
| `qlab_get_cue_details` | Generic health, target, and editable diagnostics | Prefer family details for a known type | [Read](agent-workflows.md#read-sequence) |
| `qlab_check_write_readiness` | Read-only preflight before any write | Confirmation or authorization alone | [Common write gate](agent-workflows.md#common-write-gate) |
| `qlab_create_cues` | One to 50 ordered template-backed cues in an exact Cue List, Group, or empty Cue Cart | Initial setters, GO, atomic transaction, or rollback | [Create](agent-workflows.md#create-cues) |
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
[historical single-cue Create](../development/runtime-validation/create-cues.md) and
[Edit](../development/runtime-validation/edit-cues.md) checklists.

The catalogue lists implemented contracts, not universal runtime validation.
Known Move/Delete runtime findings are recorded in [current state](../status/current-state.md)
and the write workflow sections; a dry-run alone does not close those findings.

Inspect the generated contract without connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```
