# Public MCP Tools

QLab MCP exposes exactly 80 tools on the current development branch: 49 reads and 31 gated writes. This page is a compact human
catalogue; decorated functions, generated schemas, and
`tests/test_server_tools.py` remain the source of truth for exact parameters,
annotations, and result models.

| Tool | Purpose | Not for | Workflow |
| --- | --- | --- | --- |
| `qlab_analyze_audio_file` | Levels, frequency bands, silence and estimated onsets/beats from a local audio file; 100 ms default | Playback, QLab processing, lyrics or event classification | [Audio analysis](agent-workflows.md#audio-file-analysis) |
| `qlab_search_media_files` | Find absolute file paths by filename substring in the MCP user's home folder | Arbitrary filesystem search, downloads or media format validation | [File targets](agent-workflows.md#file-targets) |
| `qlab_get_fonts` | Application-wide PostScript names and families/styles over TCP | Glyph coverage or inferred name-to-family mapping | [FX/Text](agent-workflows.md#fx-and-text-fragment-operations) |
| `qlab_get_video_effect_catalogue` | Paginated documentary parameter metadata for known Video FX | Live availability or writable identity | [FX/Text](agent-workflows.md#fx-and-text-fragment-operations) |
| `qlab_get_control_cues` | Scoped inventory of twelve control/organization types, optionally filtered by type | Carts, whole workspace or executing controls | [Control cues](agent-workflows.md#control-and-organization-cues) |
| `qlab_get_control_cue_details` | Common OSC fields, Triggers, capabilities, targets and local AppleScript Load Time/Target assigned number | Executing actions, Audio Maps or patch expansion | [Control cues](agent-workflows.md#control-and-organization-cues) |
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
| `qlab_get_video_cue_details` | Exact Video cue geometry, timing, loops, audio and optional indexed FX selectors | Stage/patch expansion, live metrics or automatic FX scans | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_text_cues` | Compact Text inventory within a required Cue List UUID | Carts, other lists or deep properties | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_text_cue_details` | Exact Text cue geometry, content, formatted fragments and optional indexed FX selectors | Stage/patch expansion, live metrics or automatic FX scans | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_camera_cues` | Compact Camera inventory within a required Cue List UUID | Carts, other lists or deep properties | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_camera_cue_details` | Exact Camera cue geometry, input patches, audio and optional indexed FX selectors | Stage/patch expansion, live metrics or automatic FX scans | [Visual cues](agent-workflows.md#video-text-and-camera-cues) |
| `qlab_get_audio_cues` | Compact paged Audio inventory within one required Cue List UUID, including groups | Carts, whole-workspace queries or deep properties | [Audio](agent-workflows.md#audio-cues) |
| `qlab_get_mic_cues` | Compact paged Mic inventory within one required Cue List UUID, including groups | Carts or whole-workspace queries | [Mic](agent-workflows.md#mic-cues) |
| `qlab_get_mic_cue_details` | Exact Mic cue input/output patches, channels, state, timing, levels and optional cue-owned object inspections | Patch configuration, Audio Maps or indexed effects | [Mic](agent-workflows.md#mic-cues) |
| `qlab_get_audio_cue_details` | Exact Audio cue identity, state, timing, patch, slices, levels and optional cue-owned object inspections | Audio Maps or effect-index scans | [Audio](agent-workflows.md#audio-cues) |
| `qlab_check_connection` | Reachability, workspace candidates, scopes, and mode | Write readiness or cue details | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_overview` | Bounded cue-list/group/cart structure | Deep properties or operational status | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_status` | Derived cue warnings, known Video Settings problems, and timecode context | A complete QLab Status-window warning total | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_general_settings` | Minimum GO time and selection/playhead lock | The complete General panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_audio_settings` | Audio overview or exact output/input patch, including exact `name_property`; optional Main/input/output/crosspoint level | Audio Maps or full-matrix scans | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_video_settings` | Compact Video inputs, routes, and stages | Exact object detail | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_video_stage` | Exact stage UUID and its regions, safe or technical | Stage mutation or name selection | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_video_output_route` | Exact output route UUID and destination, safe or technical | Independent device inventory or mutation | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_video_region` | Exact OSC bounds, grid/guide and optional one control point | Full point scan or UI-coordinate conversion | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_light_settings` | Light Patch summary or redacted technical payload | Light Definitions or Dashboard settings | [Read](agent-workflows.md#read-sequence) |
| `qlab_edit_light_patch` | One signed batch of 1–100 instrument, group and workspace-definition operations, with same-path close/edit/reopen | Cue repair, global Library, Dashboard MIDI, USB device discovery/hardware proof or unvalidated parameter creation | [Light Patch](agent-workflows.md#edit-the-light-patch) |
| `qlab_get_workspace_network_settings` | Network Patch inventory or exact patch | The complete Network panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_workspace_midi_settings` | MIDI Patch inventory or exact patch | The complete MIDI panel | [Read](agent-workflows.md#read-sequence) |
| `qlab_query_cues` | Bounded filtered cue discovery | Full Inspector payloads | [Read](agent-workflows.md#read-sequence) |
| `qlab_get_cue_lists` | Compact combined Cue List / Cue Cart inventory and current container | Child or deep container details | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_list_details` | Exact list identity, state, playhead, incoming timecode and bounded tree | AppleScript-only timecode source settings | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_cart_details` | Exact cart identity, state, timecode, grid and occupied cell positions | Playhead, nested Groups or deep child Inspector | [Read](agent-workflows.md#cue-lists) |
| `qlab_get_cue_details` | Generic health, target, and editable diagnostics | Prefer family details for a known type | [Read](agent-workflows.md#read-sequence) |
| `qlab_check_write_readiness` | Read-only preflight for existing-workspace writes | Confirmation or authorization alone | [Common write gate](agent-workflows.md#common-write-gate) |
| `qlab_create_cue_lists` | Create 1–50 empty root Cue Lists/Carts with QLab defaults | Initial properties, exact placement, atomic transaction, or rollback | [Cue List writes](agent-workflows.md#create-and-edit-cue-lists-and-carts) |
| `qlab_edit_cue_lists` | Typed common and incoming-timecode edits on 1–50 root Lists/Carts | Playhead, mode conversion, Cart grid resize, or AppleScript-only sync fields | [Cue List writes](agent-workflows.md#create-and-edit-cue-lists-and-carts) |
| `qlab_create_cues` | One to 100 ordered template-backed cues in an exact Cue List, Group, or empty Cue Cart | Initial setters, GO, atomic transaction, or rollback | [Create](agent-workflows.md#create-cues) |
| `qlab_edit_devamp_cues` | Typed Devamp Basics, OSC Triggers, Audio/Video target and Settings, 1–50 UUIDs | Playback, /live, patches and capture | [Devamp/Target edits](agent-workflows.md#edit-devamp-and-target-cues) |
| `qlab_edit_target_cues` | Typed Target Basics, OSC Triggers, target and local AppleScript assigned number, 1–50 UUIDs | Applying temporary targets, Fade targets and playback | [Devamp/Target edits](agent-workflows.md#edit-devamp-and-target-cues) |
| `qlab_edit_video_cues` | Typed Video inspector edits; 1–50 UUIDs | Audio Maps, /live, unreadable slice/baseline state; media-end errors stop the batch | [Visual edits](agent-workflows.md#edit-video-camera-and-text-cues) |
| `qlab_edit_camera_cues` | Typed Camera inspector edits; 1–50 UUIDs | Audio Maps, /live and unreadable baselines | [Visual edits](agent-workflows.md#edit-video-camera-and-text-cues) |
| `qlab_edit_text_cues` | Typed Text inspector edits; 1–50 UUIDs | Audio Maps, /live and unreadable baselines | [Visual edits](agent-workflows.md#edit-video-camera-and-text-cues) |
| `qlab_edit_control_cues` | Typed Basics, OSC/native Triggers, targets and local AppleScript Load Time for 1–50 mixed control cues by UUID | Target/Devamp, unsafe activation, Audio Maps, /live, playback | [Control edits](agent-workflows.md#edit-control-cues) |
| `qlab_edit_group_cues` | Typed Basics/OSC Triggers with signed tokens; mode or Playlist setting one at a time | Playhead navigation, deprecated aliases, Cart cell movement | [Group edits](agent-workflows.md#edit-group-cues) |
| `qlab_edit_audio_cues` | Typed Audio Basics, Triggers and saved family settings, 1–50 UUIDs | Audio Maps, Audio FX, Trim, playback or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_mic_cues` | Typed Mic Basics, Triggers and saved family settings, 1–50 UUIDs | Audio Maps, Audio FX, Trim, playback or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_light_cues` | Typed Light Basics, Triggers and saved family settings, 1–50 UUIDs | Playback, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_fade_cues` | Typed Fade Basics, Triggers and saved family settings, 1–50 UUIDs | Playback, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_network_cues` | Typed Network Basics, Triggers and saved family settings, 1–50 UUIDs | Sending messages, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_midi_cues` | Typed MIDI Basics, Triggers and saved family settings, 1–50 UUIDs | Sending MIDI, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_midi_file_cues` | Typed MIDI File Basics, Triggers and saved family settings, 1–50 UUIDs | Playback, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_timecode_cues` | Typed Timecode Basics, Triggers and saved family settings, 1–50 UUIDs | Generating timecode, `/live`, raw OSC or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_script_cues` | Typed Script Basics, Triggers and saved family settings, 1–50 UUIDs | Script source, compilation, execution or blocked capabilities | [Remaining family edits](agent-workflows.md#edit-audio-mic-light-fade-network-midi-midi-file-timecode-and-script-cues) |
| `qlab_edit_workspace_general_settings` | Minimum GO time or selection/playhead lock | Other General settings | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_get_workspace_document` | Selected document plus full fresh native inventory, including other documents’ paths/names | Save, close or filesystem edits | [Workspace documents](agent-workflows.md#workspace-documents) |
| `qlab_open_workspace` | Open an existing local `.qlab5` by absolute path when no workspace is open | Creating a document, opening alongside another workspace, or running cues | [Workspace documents](agent-workflows.md#workspace-documents) |
| `qlab_save_workspace` | Save an exact inactive workspace at its existing path | Save As, selective save, or recovery of earlier contents | [Workspace documents](agent-workflows.md#workspace-documents) |
| `qlab_close_workspace` | Close an exact inactive, clean workspace | Discarding unsaved edits or implicit save | [Workspace documents](agent-workflows.md#workspace-documents) |
| `qlab_edit_audio_output_patch` | Patch name, cue output count, one Main/input/output/crosspoint level, mute/solo, or clear | Audio Maps and full matrix scans | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_edit_video_output_route` | Route guide visibility | Other route properties | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_edit_video_stage` | Stage name | Stage geometry | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_edit_video_region` | Region geometry, one control point, grid/guide | UI coordinates or point scans | [Workspace settings](agent-workflows.md#edit-workspace-settings) |
| `qlab_move_cue_lists` | Reorder 1–50 root Cue Lists/Carts | Moving Cart cells, cross-workspace moves or root deletion | [Root Move](agent-workflows.md#move-cue-lists-and-carts) |
| `qlab_move_cues` | Sequential structural moves, 1–50 UUID targets | Playback or unproven Cart writes | [Move](agent-workflows.md#move-existing-cues) |
| `qlab_delete_cues` | 1–50 explicit leaves, one empty Group, or recursive deletion with optional Group removal | Cue List/Cue Cart root deletion or automatic rollback | [Delete](agent-workflows.md#delete-cues) |

## Shared contract

- Existing-workspace writes default to dry-run and require readiness, exact
  targets, fresh confirmation and post-write readback. Native document Open
  instead requires write-enable, an empty local inventory, a bounded fingerprint
  and a document token; it cannot run existing-workspace OSC readiness.
- Edit confirmation is per planned operation; Create, Move, Delete, and
  Workspace Settings Edit tools use dedicated confirmation flows. Light Patch
  uses one source-bound `confirm:lightPatch:v1:` token for the complete batch.
- Batches are sequential/non-transactional unless a tool description says
  otherwise. Timeout or identity ambiguity means inspect first; do not retry.
- `destructiveHint` is MCP metadata, not authorization. Runtime gates remain
  authoritative.
- The server intentionally exposes no GO, stop, panic, playback, Audition,
  raw OSC, arbitrary AppleScript, or `/live` workflow.

For full examples and failure handling, use the
[agent workflow guide](agent-workflows.md). For maintainer evidence, use the
[Create checklist](../development/runtime-validation/create-cues.md) and
[Edit](../development/runtime-validation/edit-cues.md) checklists.

The catalogue lists implemented contracts, not universal runtime validation.
Known Move/Delete runtime findings are recorded in [current state](../status/current-state.md)
and the write workflow sections; a dry-run alone does not close those findings.

Inspect the generated contract without connecting to QLab:

```bash
uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env
```

## Cue editing migration (2026-10-06)

Public `qlab_edit_cues` and `qlab_edit_workspace_settings` are removed.
Replace the former with the matching cue-family editor, and the latter with
`qlab_edit_workspace_general_settings` or the Audio/Video object editor.

Use the existing family editors with exact UUIDs and per-operation signed tokens; split mixed families. Group includes OSC
Triggers, with Second Trigger 6–7 limited to Playlist. Video/Camera/Text expose
bounded FX selectors and typed operations, with native named-getter identity proof
when inventory metadata is absent. Native creation defaults are verified for
58 effects on QLab 5.5.10. LinearKey/DropShadow creation remains blocked after
documented add/insert produced empty stacks. Deletion still requires complete
restoration proof; unavailable parameter baselines and ambiguous instances stay
blocked. Existing LinearKey/DropShadow instances can be read and edited. For
DropShadow color, select the observed native key `Color`, shown in the QLab
5.5.10 inspector and aggregate; `inputColor` is the documentary spelling.
`native_parameter_aliases` publishes this relationship without rewriting OSC
keys or inventing a missing baseline. Text supports
UTF-16 ranges, percentages and Latin word selections with verified whitespace,
guillemet/curly-quote/em-dash delimiters. Color-only edits also allow
NBSP, guillemets, curly double quotes and em dashes; emoji and other scripts
remain blocked. Partial fonts
require a complete mapping already observed in the same cue. See
[fragment editing](agent-workflows.md#fx-and-text-fragment-operations) for limits,
font inventory and the emoji font-normalization boundary.

Python callers must also use the family editors: `QLabReader.edit_cues()` and
`QLabReader.update_cue()` have been removed.

Specialized cue-family detail tools accept `include_native_triggers=true`; their
editors share the [native Trigger contract](agent-workflows.md#native-cue-triggers).
Root List/Cart edits and generic diagnostic Get are outside this extension.
