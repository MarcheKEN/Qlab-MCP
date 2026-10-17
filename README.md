# QLab MCP

Original project code and authored documentation are licensed under
[MIT](LICENSE), copyright 2026 MarcheKEN. Imported QLab/QClass references and
other third-party material are excluded; see [NOTICE](NOTICE).

QLab MCP `0.4.0` is a FastMCP server for inspecting QLab 5 workspaces over OSC
and requesting narrowly gated cue, settings and local document changes. It is read-only by default;
write mode is disabled unless explicitly configured and remains dry-run-first.

The public surface is intentionally focused: 49 read-only tools and 30 gated write
tools. The server exposes no playback or raw-protocol escape hatch.

## Capability boundaries

| Capability | Included | Contract |
| --- | --- | --- |
| Read-only inspection | Yes | Workspace, settings, cue discovery, cue details, and write readiness |
| Structural Create/Edit/Move/Delete | Yes, gated | Exact targets, readiness, dry-run, confirmation, and fresh readback |
| Workspace document lifecycle | Yes, limited and gated | Open only with no workspace open; save existing path; close clean documents only |
| Root Cue List/Cart create and edit | Yes, gated | Default empty creation and typed OSC property edits by exact UUID |
| Root Cue List/Cart reorder | Yes, gated | `qlab_move_cue_lists`; mixed sidebar order and contents verified |
| Root Cue List/Cart deletion | Deferred | OSC and AppleScript require a graphical confirmation; no Accessibility integration |
| GO, playback, stop, panic, Audition | No | Intentionally outside this MCP surface |
| Load Time / Target assigned number | Yes, gated | Fixed local AppleScript inside existing editors; macOS Automation permission required |
| Native cue Triggers | Yes, bounded | Optional MIDI/Wall Clock/Timecode reads and edits; safe activation; Hotkey disabling only |
| Raw OSC, arbitrary AppleScript, `/live` control | No | No arbitrary protocol or playback writes |
| Implicit `selected`, `active`, or `playhead` writes | No | Write targets must be exact UUIDs |

See [`SECURITY.md`](SECURITY.md) for the threat model, invariants, accepted
risks, and QLab 5.5.10 evidence boundary.

## Quick start

Use the documented non-editable Python 3.11 environment:

```bash
uv sync --locked --no-editable --python 3.11 --extra dev
.venv/bin/python -m qlab_mcp.server
```

Inspect the generated MCP contract without connecting to QLab:

```bash
uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env
```

For a read-only orientation session:

1. Open QLab and enable the workspace's OSC access if required.
2. Start the server and call `qlab_check_connection`.
3. If multiple workspaces are returned, choose one by exact UUID.
4. Follow the [agent read workflow](docs/user/agent-workflows.md#read-sequence).

Set `QLAB_PASSCODE` in the server environment for a passcode-protected
workspace. The passcode is never a tool argument.

## Optional audio analysis

Install the `audio` extra and make FFmpeg/ffprobe available in the **MCP process** PATH:

```bash
uv sync --locked --no-editable --python 3.11 --extra audio --extra dev
.venv/bin/python -c 'import librosa, numpy, shutil; assert shutil.which("ffmpeg") and shutil.which("ffprobe")'
```

`qlab_analyze_audio_file` accepts an absolute file path and works independently
of QLab. It returns numeric measurements every 100 ms by default, with individual
estimated onset/beat times. Thirty minutes gives 18,000 rows; use explicit pages
rather than one oversized response. See [audio analysis](docs/user/agent-workflows.md#audio-file-analysis)
for columns, scope, limitations and time conversion. No dependencies install at startup.

## Tool Groups

After asking the user for permission, media discovery searches the MCP user's
home folder. Assign a returned absolute path with `fileTarget` in the Audio,
Video or MIDI File editor.

| Tool | Purpose |
| --- | --- |
| `qlab_get_fonts` | QLab application font names and family/style inventory over TCP |
| `qlab_get_video_effect_catalogue` | Paginated documented Video FX parameter metadata; not live write readiness |
| `qlab_get_control_cues` | Control/organization inventory within one Cue List, optionally filtered by type |
| `qlab_get_control_cue_details` | Exact UUID detail: common fields, targets, Reset/Devamp and local Load Time/assigned number |
| `qlab_get_fade_cues` | Fade inventory within one Cue List |
| `qlab_get_fade_cue_details` | Exact Fade target and documented fade settings |
| `qlab_get_network_cues` | Network inventory within one Cue List |
| `qlab_get_network_cue_details` | Exact Network patch and fade settings; free text requires technical |
| `qlab_get_midi_cues` | MIDI and MIDI File inventory, optionally filtered by type |
| `qlab_get_midi_cue_details` | Exact MIDI message or MIDI File detail, selected by concrete type |
| `qlab_get_timecode_cues` | Timecode inventory within one Cue List |
| `qlab_get_timecode_cue_details` | Exact MTC or LTC settings |
| `qlab_get_script_cues` | Script inventory within one Cue List |
| `qlab_get_script_cue_details` | Exact Script common settings; source requires technical |
| `qlab_get_light_cues` | Light inventory within an exact Cue List UUID |
| `qlab_get_light_cue_details` | Exact Light command text, collate, subcontroller, state and timing |
| `qlab_get_group_cues` | Group inventory within an exact Cue List UUID |
| `qlab_get_group_cue_details` | Exact Group mode, conditional Playlist settings and bounded children |

The tables in this section together are the human inventory. Generated schemas and
`tests/test_server_tools.py` define exact arguments, result models, and
annotations.

| Tool | Purpose | Risk / boundary |
| --- | --- | --- |
| `qlab_check_connection` | Reachability, workspace candidates, scopes, and mode | Read-only; not write authorization |
| `qlab_analyze_audio_file` | Numeric audio levels, bands and estimated attacks/beats, default 100 ms | Read-only local file; paged, no OSC or playback |
| `qlab_search_media_files` | Find files by filename substring in the MCP user's home folder | Read-only; bounded search, no format validation |
| `qlab_get_workspace_overview` | Bounded cue-list/group/cart structure | Read-only; not deep Inspector detail |
| `qlab_get_workspace_status` | Derived cue warnings, known Video Settings problems, and timecode context | Read-only; warning coverage is partial, not a full Status-window clone |
| `qlab_get_workspace_general_settings` | Documented General settings | Partial OSC coverage: minimum GO time and selection/playhead lock |
| `qlab_get_workspace_audio_settings` | Audio overview; exact patch routing, mute/solo, and one optional Main/input/output/crosspoint level | Read-only; Audio Maps and full-matrix scans are excluded |
| `qlab_get_workspace_video_settings` | Compact Video input, route, and stage inventory | Read-only; three bulk OSC reads |
| `qlab_get_video_stage` | One stage and its regions | Read-only; exact stage UUID, safe or technical profile |
| `qlab_get_video_output_route` | One output route and its destination | Read-only; exact route UUID, safe or technical profile |
| `qlab_get_workspace_light_settings` | Light Patch summary or redacted technical payload | Read-only; no Light Definitions or Dashboard settings |
| `qlab_get_workspace_network_settings` | Network Patch inventory or exact patch | Partial OSC coverage; not the complete Network panel |
| `qlab_get_workspace_midi_settings` | MIDI Patch inventory or exact patch | Partial OSC coverage; not the complete MIDI panel |
| `qlab_query_cues` | Bounded filtered cue discovery | Read-only; not full payload inspection |
| `qlab_get_cue_lists` | Compact combined Cue List / Cue Cart inventory and current container | Read-only; no child reads |
| `qlab_get_audio_cues` | Compact Audio inventory inside one required Cue List UUID, including groups | Read-only; bounded and paged |
| `qlab_get_video_cues` | Compact Video inventory inside one required Cue List UUID, including groups | Read-only; bounded and paged |
| `qlab_get_video_cue_details` | Exact Video cue properties, geometry, timing, audio and optional indexed FX reads | Read-only; safe or technical |
| `qlab_get_text_cues` | Compact Text inventory inside one required Cue List UUID, including groups | Read-only; bounded and paged |
| `qlab_get_text_cue_details` | Exact Text cue properties, geometry, formatted text and optional indexed FX reads | Read-only; safe or technical |
| `qlab_get_camera_cues` | Compact Camera inventory inside one required Cue List UUID, including groups | Read-only; bounded and paged |
| `qlab_get_camera_cue_details` | Exact Camera cue properties, geometry, input patches, audio and optional indexed FX reads | Read-only; safe or technical |
| `qlab_get_mic_cues` | Compact Mic inventory inside one required Cue List UUID, including groups | Read-only; bounded and paged |
| `qlab_get_mic_cue_details` | Exact Mic cue input/output patches, channels, timing, levels and optional cue-owned object inspections | Read-only; safe or technical; no Audio Maps |
| `qlab_get_audio_cue_details` | Exact Audio cue timing, slices, patch, levels and optional cue-owned object inspections | Read-only; safe or technical; no Audio Maps |
| `qlab_get_cue_list_details` | Exact Cue List state, playhead, timecode and bounded contents | Read-only; UUID-only; safe or technical |
| `qlab_get_cue_cart_details` | Exact Cue Cart state, timecode, dimensions and occupied cell positions | Read-only; UUID-only; bounded cells; no playhead |
| `qlab_get_cue_details` | Exact cue properties and health | Read-only; use exact refs for later writes |
| `qlab_check_write_readiness` | Preflight for existing-workspace writes | Read-only report; not a confirmation token |
| `qlab_create_cue_lists` | Create 1–50 empty root Cue Lists/Carts with QLab defaults | Gated, sequential, no rollback; position with Move afterwards |
| `qlab_edit_cue_lists` | Typed common and incoming-timecode edits on 1–50 root Lists/Carts | Gated; no playhead, mode conversion, grid resize, or AppleScript-only fields |
| `qlab_create_cues` | One to 100 ordered template-backed cues in an exact Cue List, Group, or empty Cue Cart | Gated, non-atomic creation; no initial setters, GO, or automatic rollback |
| `qlab_edit_devamp_cues` | Devamp Basics, OSC Triggers, Audio/Video target and Settings; 1–50 UUIDs | Signed confirmations and fresh readback |
| `qlab_edit_target_cues` | Target Basics, OSC Triggers, target and assigned number; 1–50 UUIDs | Assigned number requires local AppleScript |
| `qlab_edit_video_cues` | Video Basics, OSC Triggers and saved inspector properties; 1–50 UUIDs | Signed five-minute tokens; fresh readback; no retry |
| `qlab_edit_camera_cues` | Camera Basics, OSC Triggers and saved inspector properties; 1–50 UUIDs | Signed five-minute tokens; fresh readback; no retry |
| `qlab_edit_text_cues` | Text Basics, OSC Triggers and saved inspector properties; 1–50 UUIDs | Signed five-minute tokens; fresh readback; no retry |
| `qlab_edit_control_cues` | Mixed Start/Stop/Pause/Load/Reset/GoTo/Arm/Disarm/Wait/Memo edits, 1–50 UUIDs | Gated, signed single-use confirmations, sequential readback |
| `qlab_edit_group_cues` | Typed Group/Cue List/Cue Cart/Cart Basics; mode and Playlist one property at a time | Gated; child-snapshot-bound confirmation; no cue execution |
| `qlab_edit_audio_cues` | Typed Audio Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_mic_cues` | Typed Mic Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_light_cues` | Typed Light Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_fade_cues` | Typed Fade Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_network_cues` | Typed Network Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_midi_cues` | Typed MIDI Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_midi_file_cues` | Typed MIDI File Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_timecode_cues` | Typed Timecode Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_script_cues` | Typed Script Basics, Triggers and saved family settings; 1–50 UUIDs | Signed confirmation and fresh dependencies; blocked/pending capabilities excluded |
| `qlab_edit_workspace_general_settings` | Minimum GO time or selection/playhead lock | Gated, one setter, fresh token, fresh readback |
| `qlab_get_workspace_document` | Selected document plus full local document inventory | Read-only; may expose other open documents’ paths and names |
| `qlab_open_workspace` | Open an existing local workspace when no workspace is open | Gated, single-use token, fresh inventory |
| `qlab_save_workspace` | Save an inactive workspace at its existing path | Gated, saves all unsaved edits |
| `qlab_close_workspace` | Close an inactive clean workspace | Gated, refuses unsaved edits |
| `qlab_edit_audio_output_patch` | Name, cue outputs, one level or mute/solo output, or clear mutes/solos | Gated; exact patch UUID; no Audio Maps |
| `qlab_edit_video_output_route` | One route's `enableGuides` | Gated; exact route UUID |
| `qlab_edit_video_stage` | One stage's name | Gated; exact stage UUID |
| `qlab_edit_video_region` | Bounds, control point, grid or guide in OSC coordinates | Gated; exact stage and region UUIDs |
| `qlab_get_video_region` | Exact region properties and optional one control point | Read-only; OSC coordinates; no point scan |
| `qlab_move_cue_lists` | Reorder 1–50 root Cue Lists/Carts in mixed sidebar order | Gated, five-minute dedicated token, non-atomic |
| `qlab_move_cues` | Sequential structural moves, 1–50 UUID targets | Gated, destructive metadata hint, non-atomic |
| `qlab_delete_cues` | 1–50 explicit leaves, one empty Group, or recursive deletion with optional Group removal | Gated destructive, sequential, non-atomic |

## Read Model

The normal read path is progressive rather than a full-show dump:

1. `qlab_get_workspace_overview` maps bounded structure.
2. `qlab_get_workspace_status` adds derived operational context.
3. Use the relevant `qlab_get_workspace_*_settings` tool for infrastructure.
4. `qlab_query_cues` finds a bounded target set.
5. Prefer the cue-family inventory and UUID detail tools when the type and Cue List
   are known. Keep `qlab_get_cue_details` for cross-type health, target, and editable
   diagnostics; it is not the default family-detail reader.

For lists and carts, use `qlab_get_cue_lists`, then select `qlab_get_cue_list_details`
or `qlab_get_cue_cart_details` according to the returned type and UUID.
Generic Cue Details returns a structured redirect for
Cue Lists; Cue Cart reads remain supported there.

Workspace Status warnings combine cue warning/broken/flagged fields with known
problems derived from documented Video Settings reads. Category counts may
overlap and are not a unique warning total. QLab does not expose its complete
Warnings list, Logs, Art-Net discovery, or Video Metrics through documented
read-only OSC or AppleScript APIs, so those coverage limits remain explicit.

Audio uses a typed `view` plus optional exact `ref` for focused details.
Video overview supplies UUIDs for `qlab_get_video_stage` and
`qlab_get_video_output_route`; these require exact UUIDs and default to `safe`.
Video input patches expose only names and UUIDs. Output devices are observable
only through route destinations, not an independent device inventory.
Use technical/sensitive profiles only for a deliberate diagnostic.
Query and details limits report truncation or partial results; they do not
silently claim a complete show inventory.

## Safe write flow

Create, Edit, Move, Delete, Workspace Settings and document Save/Close writes
to an existing workspace follow this sequence:

1. Resolve one explicit workspace and exact cue/container UUIDs.
2. Call `qlab_check_write_readiness`.
3. Run `dry_run=true` and review plan, diff, warnings, errors, and empty
   `executed_operations`.
4. Supply only the fresh token or per-operation gates returned by that plan.
5. Execute once; never automatically retry timeout or identity ambiguity.
6. Require fresh structural/property readback before deciding on recovery.

Opening a document is the exception: no workspace exists to resolve or check
through OSC. `qlab_open_workspace` uses its own local empty-inventory preflight,
write-enable setting, file fingerprint and document confirmation token. See the
[document workflow](docs/user/agent-workflows.md#workspace-documents).

Workspace Settings edits are scoped to General, Audio output patches, Video
output routes, stages, and regions. Read the exact object and property, run a
dry run, then submit its single-use `confirm:workspaceSettings:v1:` token.
Execution rechecks identity, baseline and zero running/paused cues, sends one
OSC setter, then reads the exact property again. Region geometry and control
points use OSC coordinates; QLab's interface may display a different origin.
Audio Maps, `/live`, undo/redo and UI-only settings are excluded. The activity
reader cannot prove workspace-wide Audition state, so keep Audition disabled.

Details, good/invalid examples, token families, partial failures, and recovery
guidance live in the [agent workflow guide](docs/user/agent-workflows.md).
Security invariants and threat assumptions live in
[`SECURITY.md`](SECURITY.md).

## Configuration

The server reads these environment variables:

```text
QLAB_HOST=127.0.0.1
QLAB_OSC_PORT=53000
QLAB_REPLY_PORT=53001
QLAB_TIMEOUT=2.0
QLAB_CACHE_TTL=10.0
QLAB_PASSCODE=
QLAB_ENABLE_WRITE=false
QLAB_WRITE_DRY_RUN_DEFAULT=true
QLAB_UPDATE_DEBUG=false
```

`QLAB_ENABLE_WRITE` must be explicitly enabled for real writes. Keep
`QLAB_WRITE_DRY_RUN_DEFAULT=true` unless a deliberate session requires another
default. `QLAB_UPDATE_DEBUG` adds optional Edit diagnostics and does not weaken
gates or verification. Configuration behavior is implemented in
`src/qlab_mcp/config.py`; restart the MCP process after changing these values.
`QLAB_TIMEOUT` is the per-transaction OSC/native-script timeout, separate from
the MCP startup timeout and each tool’s overall call budget. With a passcode,
normal OSC requests use TCP; without one, requests use isolated ephemeral UDP
reply ports rather than binding `QLAB_REPLY_PORT` as a fixed listener.
See [setup and troubleshooting](docs/user/setup-and-troubleshooting.md) for
launch configuration, process environment and startup diagnostics.

## Evidence boundary

QLab supports more controls than this server intentionally exposes. Concrete
runtime observations remain scoped to the documented QLab 5.5.10 fixture and
checklists; they are not universal QLab guarantees.

Keep this distinction explicit:

```text
planned structure
!= runtime validated
!= show ready for GO
```

## Deeper documentation

- [User guide](docs/user/README.md)
- [Setup and troubleshooting](docs/user/setup-and-troubleshooting.md)
- [Public tool catalogue](docs/user/tools.md)
- [Agent workflows](docs/user/agent-workflows.md)
- [Security policy](SECURITY.md)
- [Development architecture](docs/development/architecture.md)
- [Current status](docs/status/current-state.md)
- [Roadmap](docs/status/roadmap.md)
- [Create runtime checklist](docs/development/runtime-validation/create-cues.md)
- [Edit runtime checklist](docs/development/runtime-validation/edit-cues.md)
- [Documentation index](docs/README.md)

Inspect the current machine-readable contract with:

```bash
uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env
```
