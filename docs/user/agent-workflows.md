# Agent Workflows

This guide describes how an agent should discover QLab state and request gated
structural writes. It is workflow guidance, not a replacement for the tool
schemas or the server-side safety checks.

For a staged review, dependency-aware edits and organization examples, use
[Workspace review and authoring](workspace-authoring.md). The project
[qlab-workspace-authoring skill](../../.agents/skills/qlab-workspace-authoring/SKILL.md)
routes agents to that guide without adding a new MCP tool.

## Choose the tool

Start with connection and a bounded overview. Use family inventories and exact
details when type/list are known; Query handles cross-family discovery. Read
settings only for the relevant infrastructure. [Light and Group](#light-and-group-cues)
and the [selection table](#tool-selection) below cover specialized choices.

## Light and Group cues

See also [Control and organization cues](#control-and-organization-cues).

Resolve workspace and Cue List UUIDs, then call `qlab_get_light_cues` or
`qlab_get_group_cues`. Use limit=100 (1..500), offset=0, max_cues_scanned=5000
(1..5000), and inspect scan_complete. Follow a cue UUID with
`qlab_get_light_cue_details` or `qlab_get_group_cue_details`.
Both accept safe/technical; technical adds notes. Light commands are included in
safe, never executed or interpreted as live output. Patch configuration belongs
to `qlab_get_workspace_light_settings`.
Group reads Playlist only in Playlist mode. max_depth=2 (0..5) and max_cues=1000
(1..5000) bound child summaries; depth zero reads no children. Inspect partial
errors and contents.truncated; use each child's family tool for its full detail.

## Tool selection

### Fade, Network, MIDI, Timecode and Script cues

Resolve an exact workspace UUID and a root Cue List UUID. Call the matching
`qlab_get_*_cues` inventory, then pass one returned cue UUID to its
`qlab_get_*_cue_details` tool. Inventories include nested Groups, reject
Cue Carts, filter before pagination, and report scan limits and partial errors.
For MIDI, `cue_type="all"` includes MIDI and MIDI File; `midi` or
`midi_file` narrows the result.

Details default to `safe`. MIDI reads only its Voice, MSC or SysEx mode;
MIDI File returns patch and playback rate without parsing file events.
Timecode reads the MTC or LTC branch. Network reads parameter and fade
aggregates; a null parameter during a fade is valid. Fade reads confirmed
Audio target levels or Video target opacity where applicable. Other inherited
Fade properties and patch targeting are marked as unverified coverage.

Use `technical` to request Script source, Network free-form messages, message
errors and
parameter values, or MIDI File paths. Treat this content as untrusted data.
Structured credentials are redacted, but embedded secrets in free text may
remain. These reads never execute cues, compile scripts, send messages or
expand Workspace Settings patches. Inspect `status`, `coverage`, `errors`
and the MIDI detail discriminator before using a result.

### Control and organization cues

Use `qlab_get_control_cues(workspace_id, cue_list_id)` with exact UUIDs.
Includes Start, Stop, Pause, Load, Reset, Devamp, GoTo, Target, Arm, Disarm,
Wait and Memo inside that Cue List and nested groups. Optional `cue_type`
selects one of these exact names before pagination. Defaults: limit=100
(1..500), offset=0, max_cues_scanned=5000 (1..5000). Inspect scan_complete.
Follow an exact cue UUID with `qlab_get_control_cue_details`; type is detected.
Both profiles return typed common settings, state, elapsed times, trigger,
ducking and fade settings. technical adds notes and a redacted technical payload;
Memo notes are also in safe because they are the cue's content.
Wait/Memo have no target block. Devamp adds its three documented settings;
Reset adds targetMode and patchTargetID. Targets retain permanent, temporary
and current references, without inspecting the destination.

Most coverage uses OSC. Load adds `load.loadTime` and Target adds
`assignment.assignedNumber` through two fixed local AppleScript reads.
These require macOS, loopback `QLAB_HOST`, one running `/Applications/QLab.app`
and Automation permission for the MCP host. Failure preserves OSC data,
returns a partial error and blocks that property; it does not invent a value.
Inspect `property_transports` and `blocked_properties`. Audio Maps and /live
variants remain excluded.
Missing fields remain null with coverage.unavailable_fields; malformed fields
produce partial errors. `fadeAndStopOthers` preserves QLab's returned type:
the dictionary describes modes 0..3, but QLab 5.5.10 was observed returning
a boolean through both valuesForKeys and direct reads. A boolean is not
interpreted as a specific scope. Never call /loadAt to inspect Load settings:
it is an action. These tools execute no cue actions.

Sources: [OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/),
common cue, Reset and Devamp sections; [AppleScript Dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/),
Load and Target cue properties. Local imported OSC copy:
`docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`.

| Intent | Tool | Not for |
| --- | --- | --- |
| Check QLab reachability, workspaces, scopes, and mode | `qlab_check_connection` | Write authorization or cue detail |
| Map cue lists, groups, carts, and bounded structure | `qlab_get_workspace_overview` | Deep properties or operational status |
| Read derived cue warnings, known Video Settings problems, and timecode context | `qlab_get_workspace_status` | A complete QLab Workspace Status clone |
| Read documented General settings | `qlab_get_workspace_general_settings` | The complete General panel |
| Read Audio settings or one exact output/input patch | `qlab_get_workspace_audio_settings` | Audio Maps or patch mutation |
| Inventory Video inputs, stages, and output routes | `qlab_get_workspace_video_settings` | Exact object detail |
| Inspect one stage and its regions by UUID | `qlab_get_video_stage` | Name selection or mutation |
| Inspect one output route and destination by UUID | `qlab_get_video_output_route` | Independent device inventory or mutation |
| Read the Light Patch | `qlab_get_workspace_light_settings` | Light Definitions or Dashboard settings |
| Read Network Patch inventory or one exact patch | `qlab_get_workspace_network_settings` | The complete Network panel |
| Read MIDI Patch inventory or one exact patch | `qlab_get_workspace_midi_settings` | The complete MIDI panel |
| Find a bounded set of cues with filters | `qlab_query_cues` | Full Inspector payloads |
| List Audio cues within an exact Cue List UUID | `qlab_get_audio_cues` | Carts or whole-workspace inventory |
| Inspect one exact Audio cue UUID | `qlab_get_audio_cue_details` | Audio Maps or indexed effect scans |
| Find Cue List / Cue Cart UUIDs and the current container | `qlab_get_cue_lists` | Child inspection |
| Inspect one Cue List and its bounded contents | `qlab_get_cue_list_details` | Cue Cart details or mutation |
| Inspect one Cue Cart and its occupied grid cells | `qlab_get_cue_cart_details` | Cue List playhead or deep child Inspector |
| Inspect generic health, targets, or editable fields | `qlab_get_cue_details` | Prefer family detail for a known type |
| Check write-mode preconditions without mutating | `qlab_check_write_readiness` | Confirmation or authorization by itself |
| Create one to 100 ordered cues from templates | `qlab_create_cues` | Initial setters, playback, GO, or automatic rollback |
| Edit saved properties and typed operations | Family-specific cue editors | Create, Move, Delete, playback, or raw OSC |
| Edit one Workspace Settings property | `qlab_edit_workspace_general_settings`, `qlab_edit_audio_output_patch`, `qlab_edit_video_output_route`, `qlab_edit_video_stage`, `qlab_edit_video_region` | Audio Maps, `/live`, GO, or raw OSC |
| Move existing cues structurally | `qlab_move_cues` | Playback or Cart writes not runtime-proven |
| Delete leaves, empty a container, or explicitly remove a Group and descendants | `qlab_delete_cues` | Cue List/Cue Cart root deletion or automatic rollback |

## Read sequence

1. Call `qlab_check_connection` and select one workspace by exact UUID when
   several candidates are available.
2. Call `qlab_get_workspace_overview` for the bounded structural map. Use
   `qlab_get_workspace_status` for derived operational context. Call only the
   relevant General, Audio, Video, Light, Network, or MIDI settings tool for
   the infrastructure context needed by the task.
3. Use the family inventory inside an exact Cue List for a known cue type;
   use `qlab_query_cues` for cross-type discovery.
4. Prefer the matching family detail tool with the returned UUID. Keep
   `qlab_get_cue_details` for generic health, target, or editable diagnostics.
   Do not turn `selected`, `playhead`, or `active` into a write target.

Audio defaults to `view="overview"`; use `output_patch` or `input_patch` with an
exact name/UUID `ref` when needed. Audio Maps are intentionally not public.
An exact Output Patch also returns routing, cue-output count/names, mute, and
solo. To read one matrix value, provide both `input_channel` (0–128) and
`output_channel` (at least 0) with `view="output_patch"`; neither profile scans
the complete matrix. `(0, 0)` reads Main; `(input, 0)` reads input gain,
`(0, output)` reads output gain, and two positive channels read a crosspoint.
Known patch capacity further constrains channels.
Network and MIDI accept an optional exact `ref`.
For Video, call `qlab_get_workspace_video_settings(workspace_id)` first, then
pass a returned UUID as `stage_id` to `qlab_get_video_stage` or as `route_id` to
`qlab_get_video_output_route`. Both exact tools default to `profile="safe"`;
use `technical` for the redacted raw payload. The overview has no profile,
view, or ref parameter. Video input patches expose only name and UUID, and
device information is limited to destinations assigned to output routes.
Prefer the default profile of each tool; use technical or exhaustive reads only
when justified. Workspace Status uses `summary` or `technical`, not `safe`.

`qlab_get_workspace_status.sections.warnings_summary` has partial coverage. It
combines cue warning, broken, and flagged categories with problems derived from
documented Video Settings reads. These categories can overlap, so do not sum
them as a unique warning total. `evidence_sources` and the two
`*_evidence_available` flags show which reads succeeded. Logs, Art-Net discovery,
Video Metrics, and QLab's complete Warnings list are not exposed by documented
read-only OSC or AppleScript APIs.

## Audio cues

1. Resolve the workspace UUID with `qlab_check_connection`, then use
   `qlab_get_cue_lists` to select a root whose type is `Cue List` (not a Cart).
2. Call `qlab_get_audio_cues(workspace_id, cue_list_id, limit=100, offset=0)`.
   The list UUID is required. Nested groups are included; other lists and carts
   are not traversed. Only returned Audio cues receive summary-property reads.
3. Follow `next_offset` while `has_more` is true. `matched_count` counts matches
   in the scanned portion, not a guaranteed list total: check `scan_complete`,
   `truncated`, `truncation_reasons` and errors. A larger `max_cues_scanned`
   (maximum 5000) may be necessary. Offsets are fresh observations, not snapshots.
4. Call `qlab_get_audio_cue_details(workspace_id, cue_id)` for one exact UUID.
   Non-Audio targets are rejected. The typed result contains identity, immediate
   parent, basics, state, timing, slices, patch reference, mute/solo and levels.
   Containing-list identity comes from the inventory; detail does not rescan it.
5. Use `profile="technical"` only when notes, media paths and variable
   `audioTrackFormats` metadata are needed. Structured credentials are redacted;
   free-text notes and paths may still be sensitive.

Both profiles read `/levels` as one aggregate matrix, never one request per cell.
For a crosspoint, supply both `input_channel` (0–24) and `output_channel`
(0–128); zero denotes main controls. Missing properties remain unknown in
`coverage`; malformed secondary values produce partial results. Optional
`inspections` read up to 50 requested scalar or indexed fields, including
cue-owned Audio Objects. Audio Maps, live metrics and indexed effect exploration
remain excluded. Generic discovery and detail reads remain available.

## Mic cues

Resolve the workspace and Cue List UUIDs as in the Audio workflow, then call
`qlab_get_mic_cues(workspace_id, cue_list_id, limit=100, offset=0)`. The same
pagination, nested-group traversal and scan limits apply; Cue Carts are excluded.
Use `qlab_get_mic_cue_details(workspace_id, cue_id)` for one exact Mic UUID.
It returns input/output patch references, input `channels`, zero-based
`channelOffset`, timing, state, mute/solo and the aggregate levels matrix.
Both optional crosspoint selectors have the same ranges as Audio; no per-cell
scan occurs. `profile="technical"` adds notes and normalized technical payload,
not file metadata or Audio-only looping properties. Missing values stay unknown;
malformed secondary fields produce partial results. Optional `inspections` read
up to 50 requested fields, including cue-owned Audio Objects. Audio Maps, live
metrics and indexed effects remain excluded. Full patch configuration belongs
to `qlab_get_workspace_audio_settings`, not cue details.

## Video, Text and Camera cues

Resolve an exact workspace and root Cue List UUID, then choose
`qlab_get_video_cues`, `qlab_get_text_cues` or `qlab_get_camera_cues`.
Each uses the Audio/Mic pagination contract: limit 1–500 (default 100),
non-negative offset and scan limit 1–5000 (default 5000). Nested groups are
included; carts and other lists are excluded. Check scan_complete and next_offset.

Use the matching `qlab_get_video_cue_details`, `qlab_get_text_cue_details` or
`qlab_get_camera_cue_details` with an exact cue UUID. All expose typed geometry,
stage references and the aggregate effect inventory. Video adds file timing,
loops and audio; Camera adds video/audio input references and channel selection.
Video and Camera accept the same paired matrix selectors as Audio/Mic. Video,
Camera and Text also accept up to 50 optional `video_effects` selectors for
requested saved parameters. Each selector uses a zero-based index and may
include an exact effect type and key; if type is omitted, the Get discovers it
from native indexed identity or reports ambiguity. They do not scan every
effect automatically.

Text safe details include full content, output size, fixed width and format
runs with ranges; text may contain sensitive show content. Aggregate formatting
preserves mixed styles; individual style getters describe only what OSC returns.
Optional background, shadow and decoration summaries come from format fragments.
Missing or mixed attributes remain null with fragment detail; a failed or invalid
format query still produces a partial result. No defaults are substituted.

Technical mode retains typed data and adds notes, redacted aggregate effects and,
for Video, file paths and audio metadata. Full stages/routes and patches remain
in their specialized workspace tools. Audio Maps, Objects and live metrics are
excluded. Camera/Text do not read file-playback
properties; Text does not read audio. Existing generic tools remain available.

## Cue Lists

Call `qlab_get_cue_lists(workspace_id)` for a compact inventory, then
`qlab_get_cue_list_details(workspace_id, cue_list_id)` with a returned exact UUID.
Names and cue numbers are not accepted as `cue_list_id`. The `cue_lists` array
includes both Cue Lists and Cue Carts, distinguished by `type`. `cue_list_count`
counts lists only, `cue_cart_count` counts carts, and `container_count` counts both.
The legacy `excluded_cue_cart_count` is always zero. `current_container_id` may identify a Cart;
`current_cue_list_id` is null in that case. Missing shallow health fields stay null.
Root positions are zero-based.

For a Cue Cart, pass its UUID as `cue_cart_id` to `qlab_get_cue_cart_details`.
This shares identity, basics, state and timecode reads with List details, but returns
`grid.rows`, `grid.columns` and bounded occupied `grid.cells` with OSC row/column
coordinates. It has no playhead or depth parameter: carts cannot contain Groups.
Inspect `grid.complete`, `contents.truncated` and per-cell errors before inferring
empty cells. Missing positions remain null. Use generic Cue Details for the deep
Inspector of each contained cue. Notes are available only with `profile="technical"`.
Technical payload redaction is key-based; free-text notes may contain sensitive text.

Source: [Cue Carts](https://qlab.app/docs/v5/fundamentals/cue-carts/) and the
repository OSC Dictionary, Group cue/List/Cart and cartPosition messages.

Details include typed identity/state, playhead and playback-position aliases,
incoming timecode and an ordered bounded tree. Default `max_depth=2` reads two
child layers; `0` skips children. `max_cues=1000` counts descendants only (range
1..5000); depth is limited to 0..5. Inspect `contents.truncated`, reasons and
`coverage` before claiming complete contents. A missing child count is unknown,
not zero. Reads are sequential observations, not an atomic show snapshot.

Use `profile="technical"` to add the redacted allowlisted OSC payload while
retaining typed sections. MTC/LTC mode does not prove sync is enabled. OSC does
not document the sync-enabled flag, MTC device or LTC input/channel for this
read family; current timecode can be absent when not receiving timecode.
See the [OSC Dictionary](../references/qlab_osc_dictionary.md), Cue List/Group
messages, for enumerations and documented read conditions.

Example call arguments (substitute UUIDs returned by the inventory):

```json
{"workspace_id": "<workspace UUID>", "cue_list_id": "<Cue List UUID>", "profile": "safe", "max_depth": 2, "max_cues": 1000}
```

Overview retains structural context, Query retains list filtering and Status
retains aggregate operational information. `qlab_get_cue_details` returns a
structured redirect for Cue Lists, including in batches; use the dedicated
tool with the exact UUID. Cue Cart reads remain available through the generic
tool.

## Common write gate

Every real write to an existing workspace follows this shape:

1. Resolve one explicit workspace and exact cue/container UUIDs.
2. Call `qlab_check_write_readiness`. This is a read-only preflight, not a
   confirmation token.
3. Request a dry-run with `dry_run=true` and inspect its plan, diff, warnings,
   and errors. Confirm that `executed_operations` is empty.
4. Pass only the fresh token or per-operation gates returned by that dry-run.
5. Execute once. Never automatically retry a timeout, identity ambiguity, or
   placement ambiguity.
6. Require fresh structural or property readback and interpret partial results
   before deciding on a recovery action.

Document opening has no existing workspace for this preflight. Follow the
[separate native Open workflow](#workspace-documents), which requires write-enable,
an empty inventory, a file fingerprint and a document token.

Writes to existing workspaces are disabled by default and remain subject to server-side environment,
passcode, `/connect` Edit permission, and Edit Mode checks. MCP annotations and
descriptions help clients choose a tool; they are not authorization.

## Create and Edit Cue Lists and Carts

Use `qlab_create_cue_lists` for 1–50 ordered `cue_list` / `cue_cart` roots.
Dry-run returns a five-minute `confirm:createCueLists:v1` token bound to the
workspace, requested order, and complete root structure. Real execution sends
one `/new` at a time, requires its UUID, and verifies the new root's type,
position, and empty contents before continuing. QLab defaults are preserved.
Creation can change the current container and selection. Use
`qlab_move_cue_lists` afterwards when an exact sidebar position is required.

Use `qlab_edit_cue_lists` with exact root UUIDs for common properties and typed
incoming-timecode settings. The tool reuses the existing Edit executor and its
fresh property readback. Supported timecode fields constrain OSC enumerations
and freewheel to 0..2 seconds. Playhead, playback, List/Cart conversion, Cart
grid resizing, sync-enabled state, MTC source, and LTC patch/channel are
excluded because they are control state, read-only, or unavailable through the
documented OSC routes.

Both batches stop at the first failure and have no rollback. Inspect
`pending_indices`, `uncertain_indices`, and `batch_verified` for Create, and the
normal per-item Edit result for updates.

## Create cues

`qlab_create_cues` accepts 1–100 ordered cue types, including mixed types. Supply
exactly one `cue_list_id`, `group_id`, or `cue_cart_id`. Lists and Groups append
by default; `after_cue_id` inserts after a direct child. An empty Cue Cart accepts
one non-Group cue, without an anchor. Obtain list/cart UUIDs with
`qlab_get_cue_lists`. Review the dry-run and use its exact
`confirm:createCues:v2` token. Earlier tokens require a new dry-run.

Each cue uses its workspace Cue Template; creation adds no initial setters and
the MCP sends no cue number. QLab's General setting can auto-number new cues,
but the [QLab documentation](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
says cues created via OSC are not auto-numbered. In the workspaces tested for
this MCP, fresh readback nevertheless returned numbered cues. Treat numbering
as workspace/runtime-specific: do not predict it from the setting or template.
The create result guarantees a UUID, not a cue number; use a fresh cue read to
discover the number. QLab selects each new cue, and the first cue in an empty
list can change the active Cue List. A created cue can still be broken or
otherwise unready for GO.

The sequence stops on the first timeout, identity ambiguity, placement mismatch,
or other failure. Earlier items remain; there is no retry or automatic rollback.

The public timeout is 300 seconds; execution has a 270-second internal budget.
A request for 100 cues is accepted, but may stop early on a large or slow workspace.
No new creation starts after the budget is exhausted. `pending_indices` are the
zero-based requested items not attempted; a failed attempted item remains in
`results`. `uncertain_indices` identify creations that may have been sent but
were not verified, even when a UUID is known. `created_count` counts confirmed
items only; it is not proof that no other cue exists. `batch_verified` is true
only after the final complete structure and inactive state have been verified.
A final verification failure preserves all confirmed results and counts.

In the result, requested_count and created_count count logical cues.
planned_count counts generated plan operations, including each cue's creation
and identity/structure verification steps. Use planned_operations for the exact
operation list; do not compare planned_count directly with the number of cue
requests.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_types": ["memo", "wait"],
  "cue_list_id": "<cue-list-uuid>",
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_types": ["memo", "wait"],
  "cue_list_id": "<cue-list-uuid>",
  "group_id": "<group-uuid>",
  "confirm_token": "<old-or-mismatched-token>",
  "dry_run": false
}
```

Do not retry an ambiguous `/new`. If the result requires cleanup, inspect the
workspace and use a new Delete dry-run/token only after the created UUID is
unambiguous.

## Edit existing cues

Use the editor for the cue family and exact `cue_id` UUIDs. Each call edits
1–50 cues; split mixed-family batches into separate editor calls. Control
supports its documented mixed control types. `qlab_edit_cues` has been removed
from the public API; number references and public profiles are not accepted.

Every setter requires the exact signed, five-minute, single-use token from its
dry-run `planned_operations`, supplied in the item's `confirm_gates`. The whole
batch is checked and tokens reserved before any setter. Execution is sequential,
not atomic: inspect applied, failed and pending operations. Each setter prepares
`/alwaysReply` on its own connection and requires fresh readback. Never retry an
uncertain timeout. Restoration requires a new dry run and fresh tokens.

```json
{
  "workspace_id": "<workspace-uuid>",
  "updates": [{"cue_id": "<fade-cue-uuid>", "properties": {"duration": 2.0}}],
  "dry_run": true
}
```

Temporary duration/targets, playback navigation, captures, Script source,
Audio Maps and `/live` are excluded. A token cannot enable a blocked operation.
Consult each detail tool's edit capabilities and reasons before planning.

## Edit workspace settings

Choose the Edit tool for the object: General settings, Audio output patch,
Video output route, stage, or region. First read the current value with the
matching Get. Supply exact workspace and object UUIDs, one typed operation,
and `dry_run=true`. Review the current value and planned OSC setter, then
submit the returned `confirm:workspaceSettings:v1:` token once.

Each edit reads the exact OSC property and object identity, checks write
readiness and `runningOrPausedCues`, and binds the token to the UUID, previous
value and requested value. Execution rechecks them, sends one setter, then
reads the property again. The client enables `/alwaysReply` on the setter's
connection and accepts its status-only acknowledgement. If preparation fails,
`executed_operations=[]`; obtain a new dry-run token. A timeout never triggers a second setter. Inspect
QLab before any recovery if readback is unavailable or differs.

The activity gate requires zero running or paused cues before token issuance
and again before the setter. The activity reader cannot prove workspace-wide
Audition state, so keep Audition disabled. Region coordinates are OSC
coordinates: the QLab interface can show a different origin. Use
`qlab_get_video_region` for one region and optionally one control point;
there is no automatic matrix or point scan. Audio Maps, `/live`, undo/redo,
and UI-only controls are excluded.

For an Audio patch level, supply both channel selectors: `(0,0)` is Main,
`(input,0)` is an input gain, `(0,output)` is an output gain, and positive
indices select a crosspoint. Cue-output rows are 0–128; existing positive rows
must fit the patch's current cue-output count. An exact readable cell is required
before editing. Mute and solo still use positive device-output channels.
A nonnumeric level must be the literal `-inf`.
QLab 5.5.10 returns the configured minimum volume (`-60 dB` in the test
workspace) after that setter; the result exposes the raw readback and warns
that OSC cannot distinguish `-inf` from the same numeric floor. The token
also binds the observed minimum volume.
A numeric floor therefore does not skip a requested `-inf` setter; only an
explicit `-inf` baseline proves that no change is needed. Region bounds
readbacks must contain int32 coordinates. Control-point readings may contain
finite decimals, preserved without rounding; requested point coordinates remain
int32 integers within the OSC output area. Malformed values block token issuance
or execution, and malformed post-write values are inconclusive.
For patch renaming, use `detail.name_property` from the Audio Get as the exact
OSC baseline; `detail.name` can include device information in QLab's display.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "operation": {
    "kind": "general.minGoTime",
    "value": 0.5
  },
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "selected",
  "operation": {
    "kind": "general.unknown",
    "value": 0.5
  },
  "dry_run": false
}
```

The invalid example uses a non-UUID workspace target, an unsupported operation,
and skips the reviewed dry-run/token flow.

## Workspace documents

`qlab_get_workspace_document` reads a native local inventory by exact workspace
UUID and returns the complete fresh native inventory in `readback`, including
other open workspaces’ paths, names, UUIDs, modes, dirty flags and active cue IDs.
Treat that response as deliberately sensitive when logging or sharing it.

`qlab_open_workspace` accepts an existing absolute `.qlab5` path, but only
when the native inventory is empty; it fingerprints the file/package and binds
that state to a five-minute token. Opening is one event, followed by a fresh
inventory. It does not create documents or open alongside an existing workspace.

`qlab_save_workspace` saves all pending edits to the current path; it has no
Save As or selective-save mode. Its token includes the current document state
and a bounded file fingerprint. The QLab `modified` flag is a dirty indicator,
not an edit revision, so concurrent edits while already dirty are not detected.
`qlab_close_workspace` accepts only a clean document and uses `saving no`; it
will never discard dirty changes. Both require an inactive workspace in Edit
Mode, use one native event and verify a new inventory. Do not retry a timeout;
inspect QLab and call Get again first. These tools need the local `/Applications/QLab.app`
process and macOS Automation permission, and are unavailable for remote QLab.

Open requires `QLAB_ENABLE_WRITE=true`; it does not call existing-workspace
OSC readiness or require a passcode for a workspace that is not open. Save and
Close do require that readiness. Open and Save fingerprints allow at most
64 MiB of cumulative file data and 4,096 package entries including the root;
package symlinks and unsupported entries are rejected. Close does not fingerprint
the file. Do not disable these gates to force an oversized or ambiguous target.

Preview the chosen document operation with `dry_run=true`, review
`planned_operations` and the fresh inventory, then repeat the same arguments
with `dry_run=false` and its exact `confirm_token`. Document tokens use
`confirm:workspaceDocument:v1:`, expire after five minutes and are single-use
and process-bound; cue-editor `confirm_gates` do not apply. A confirmed no-send
response is blocked without counting an event. A missing send acknowledgement
stays uncertain even when the document already matches the desired state.
Readback can confirm a timed-out or errored attempted event; inspect the explicit
status and never resend automatically. Native Get, Save preview and dirty-Close/
nonempty-Open blocking have [bounded live evidence](../development/runtime-validation/2026-10-17-installed-mcp-acceptance.md);
actual Open/Save/Close events remain unvalidated by these reports.

## Move Cue Lists and Carts

Use `qlab_move_cue_lists` to reorder 1–50 root Cue Lists or Cue Carts within
one exact workspace. Resolve UUIDs through `qlab_get_cue_lists`; its underlying
mixed root inventory includes both types. Specify exactly one placement per
item: `destination_index`, `before_cue_id`, `after_cue_id`, or `position`
(`first`/`last`). Indices start at zero after removing the source; each item
uses the order simulated by earlier items. No destination parent is accepted.

```json
{
  "workspace_id": "<workspace-uuid>",
  "moves": [
    {"cue_id": "<list-uuid>", "position": "first"},
    {"cue_id": "<cart-uuid>", "after_cue_id": "<list-uuid>"}
  ],
  "dry_run": true
}
```

Review the complete plan, then repeat the same request with `dry_run=false`
and the exact `confirm:moveCueLists:v1` token. It expires after five minutes
and binds the reviewed root order, moved contents, workspace and placements.
Pass the returned token value directly; copying or shortening it by hand
invalidates its signature before any OSC command is sent.
Real execution requires write readiness, Edit Mode and an idle workspace.
Fresh full root order and moved-container contents must match before and after
each operation and at the final audit. Already-satisfied placements skip OSC
but still undergo verification. Health warnings are informational.

The batch is sequential and non-atomic. On failure inspect confirmed results,
`pending_cue_ids` and `uncertain_cue_ids`; do not resend an ambiguous operation.
Moving a Cart in the sidebar does not reposition its cells. Existing
`qlab_move_cues` continues to block root moves and Cart cell execution.

**Delete QList is deferred.** Empty root List and Cart deletions via OSC and
AppleScript both opened a modal confirmation; AppleScript also timed out.
No documented OSC confirmation bypass was found. Completing this inside the
MCP would require a macOS Accessibility adapter and permission for its host
process. That integration is outside this implementation. See the
[raw OSC and AppleScript evidence](../development/runtime-validation/2026-09-27-raw-osc-root-list-cart.md).

## Move existing cues

Shallow structural reads omit health fields; Move reads them separately with
uncached `valuesForKeys` before issuing or accepting its confirmation token.

`qlab_move_cues` accepts 1–50 UUID-only source cues. For List/Group placement,
provide exactly one of `destination_index`, `before_cue_id`, `after_cue_id`, or
`position`; Cart coordinates require both `cart_row` and `cart_column` and no
linear placement field. Use the exact `confirm:moveCues:v1` token from the
reviewed dry-run.

Each source `cue_id` must be unique within the batch. An anchor
(`before_cue_id`/`after_cue_id`) or `destination_parent_id` cannot point to a cue
that is also being moved in that batch. These shapes fail preflight before OSC;
the batch does not support dependencies between moved cues. Use an unaffected
anchor or separate calls with a fresh read and dry-run for each step.

Source/destination health is read fresh and reported in the plan. Broken or
warning cues can still be moved structurally; warnings do not establish
playback readiness. Missing or invalid health data blocks preflight.

Moves execute sequentially and are non-atomic. Fresh parent/order readback is
required before and after each move: complete affected parent orders and the
contents of a moved Group must match the simulated structure. A final batch
audit verifies those structures again. An already-satisfied placement skips its OSC setter
but still requires fresh position readback; its result reports
`reply_status=skipped_no_op`, and it counts toward `moved_count`.
Cue Cart execution remains runtime-blocked by the
current QLab 5.5.10 evidence boundary; this is a repository policy, not a
claim that QLab itself has no Cart operation.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "moves": [
    {
      "cue_id": "<cue-uuid>",
      "destination_parent_id": "<list-uuid>",
      "position": "last"
    }
  ],
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "moves": [
    {
      "cue_id": "<cue-uuid>",
      "destination_index": 0,
      "position": "first"
    }
  ],
  "dry_run": false
}
```

The invalid example supplies two linear placement forms and no reviewed token.

## Delete cues

Delete acknowledgement handling and fresh child readback are corrected locally.
QLab 5.5.10 validation covers individual leaves, mixed batches, empty Groups and
nested recursive deletion; see the [runtime report](../development/runtime-validation/2026-09-26-delete-cues.md).
Those live results predate the latest structural/progress hardening and opt-in
Group removal; see the [hardening report](../development/runtime-validation/2026-09-27-move-delete-hardening.md).
The [October 17 installed-MCP pass](../development/runtime-validation/2026-10-17-installed-mcp-acceptance.md)
adds explicit-leaf batch and empty-Group deletion with complete structural
restoration. It does not validate recursive Group-root removal or provide UI
comparison of that hardening.
Do not retry an error blindly.

`qlab_delete_cues` accepts either 1–50 explicit leaf UUIDs, one exact empty
`Group` through `container_id` with `recursive=false`, or one container with
`recursive=true`. Direct Group deletion removes the Group itself only when it
is empty and inactive. Recursive mode deletes descendants deepest-first and
preserves the requested root by default. To remove a Group and its contents,
omit `cue_ids` and set `container_id`, `recursive=true`, and
`delete_container=true`. Descendants are deleted first and the Group last; any
failure stops the batch before remaining deletes. This mode allows at most 500
total deletion operations, including the Group. Root-preserving mode retains
its 500-descendant limit. Cue List and Cue Cart root deletion remains blocked.
Use the exact `confirm:deleteCues:v1` token from
the dry-run.

Deletion is sequential and non-atomic, with no automatic rollback. Fresh
existence readback must verify disappearance of every requested UUID and the
planned preservation or removal of the root. Group emptiness is checked again
immediately before deletion. Do not retry after timeout or identity ambiguity.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_ids": ["<cue-uuid>"],
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_ids": ["<cue-uuid>"],
  "container_id": "<container-uuid>",
  "recursive": true,
  "dry_run": false
}
```

The invalid example mixes leaf and recursive targets and skips the fresh
Delete token. The requested root is never an implicit delete target.

## Failure and evidence boundaries

Read every batch result item. `partial_failed`, `verification_failed`, timeout
statuses, cleanup requirements, and warnings describe the observed operation;
they do not authorize an automatic retry. Recovery starts with a fresh read and,
when supported, a new dry-run and new token.

Move and Delete return `pending_cue_ids` for setters not sent and
`uncertain_cue_ids` for attempted operations without a confirmed outcome.
Confirmed item results and counts survive intermediate or final read failures.
A final audit failure does not duplicate the last confirmed item; `failed_count`
continues to count unconfirmed operations, so it can be zero when the final
audit fails. These responses cannot guarantee delivery after a disconnected
client or process interruption.

QLab behavior and MCP policy are different layers. QLab supports more controls
than this server intentionally exposes. This server requires exact targets,
Edit Mode, dry-run review, confirmation, and readback, and exposes no GO, stop,
panic, playback, Audition, raw OSC, arbitrary AppleScript, or `/live` workflow.

Keep this distinction in every report:

```text
planned structure
!= runtime validated
!= show ready for GO
```

Maintainer-only runtime evidence lives in the
[Create checklist](../development/runtime-validation/create-cues.md),
[Edit checklist](../development/runtime-validation/edit-cues.md), and related
runtime-validation documents. Those checklists are not proof that a new show is
ready for GO.

### Optional Text attributes and LTC channel zero

Optional Text background, shadow, underline and strikethrough attributes are
read from `text.fragments`. Their top-level summary is present only when every
fragment contains the same value. Absent or mixed values produce `null` and
coverage notes, not an OSC error. Failed or malformed format reads still produce
partial results. No default formatting is inferred.

A Timecode LTC channel of zero is preserved as observed configuration. It does
not prove a usable output; inspect `isBroken` and patch references separately.

## Edit Group cues

Use `qlab_edit_group_cues(workspace_id, updates, dry_run)` for 1–50 distinct
Group, Cue List, Cue Cart or Cart UUIDs. Read `qlab_get_group_cue_details` first;
its `edit_capabilities` reports Playlist properties only for mode 6.

Typed Basics may be batched. A Group mode or Playlist change must be the sole
property for one cue in that call. Preview first, then copy its exact
`confirm_token` into `confirm_gates` and repeat the request within five minutes.
The existing Group confirmation binds the ordered child snapshot and is
single-use. Writes are sequential, non-atomic, freshly read back, and never
rolled back automatically. No cue is executed. Playhead/current-cue navigation,
deprecated Playlist aliases and Cart cell movement remain outside this tool.

## Edit control cues

Use `qlab_edit_control_cues(workspace_id, updates, dry_run)` for 1–50 mixed
Start, Stop, Pause, Load, Reset, GoTo, Arm, Disarm, Wait and Memo cues.
Resolve exact UUIDs with `qlab_get_control_cues`; inspect Basics, Triggers and
`edit_capabilities` using `qlab_get_control_cue_details`. Unknown fields, duplicate
cue UUIDs and public profile arguments are rejected.

1. Build each item as `{"cue_id": "<UUID>", "properties": {"name": "New name"}}`.
2. Set `dry_run=true`. Check every prior value, requested value and ordered setter.
   All cues, applicable properties, targets, patches, Edit access, Edit Mode and
   workspace inactivity must pass before any write. No setters run during preview.
3. Copy every `planned_operations[].confirm_token` into the corresponding item's
   `confirm_gates`; repeat the same properties with `dry_run=false` within five
   minutes. Tokens are signed, single-use and bound to the whole cue request,
   baseline, type and target dependencies. All tokens are reserved before writing.
4. Inspect per-operation status and fresh `after` values. The batch is sequential,
   non-atomic. Applied changes remain if a later operation fails; pending setters
   are not sent. Request a new dry run after a failed/consumed confirmation.
   A timeout never causes a setter resend. A matching fresh readback can confirm
   a timed-out setter; mismatches and uncertain results stop the batch.

Properties retain OSC names. Only Wait has editable `duration`; Wait and Memo
have no targets. Use `cueTargetID` with a workspace cue UUID or `""` to clear it.
Reset also accepts a workspace Audio Output Patch UUID as `patchTargetID` and
`targetMode` 0 (Cue) / 1 (Patch). Target assignment inserts the required mode
setter **before** the target setter; contradictory modes and patch clearing fail.
Audio Maps are excluded. New nonempty cue numbers must be free in a fresh
complete workspace inventory; renumbering cycles are not supported.

OSC Triggers include Duck/Boost, Fade & Stop (0–3), Second Trigger (0–5), and
`timecodeTrigger/text` or individual hours/minutes/seconds/frames/bits. Timecode
validation uses the containing list's SMPTE format, including drop-frame labels;
a configured time does not prove activation. Text and components cannot be mixed
in one cue item. The aggregate `timecodeTrigger` is read-only. `captureTimecode`
is excluded. Second Trigger 6–7 is reserved for Group Playlist. Fade & Stop uses
its exact scalar read: QLab 5.5.10 bulk reads return a
boolean that cannot identify scope. If exact mode readback is unavailable, edits
of that scope are blocked.

Target and Devamp use their dedicated [Edit tools](#edit-devamp-and-target-cues).
Load `loadTime` uses fixed local AppleScript: finite seconds, including negative
values measured back from the end of the target cue/sequence. It edits saved
configuration; it never loads a cue. Change `cueTargetID` separately and obtain
a new dry run before editing `loadTime`. Basics and Triggers may accompany the
field. Unassigned Load placeholders can be configured, but remain broken.
Native MIDI/Wall Clock configuration and Timecode activation/display use the
bounded [native Trigger workflow](#native-cue-triggers).

## Native cue Triggers

Every specialized cue-family Get accepts `include_native_triggers=true` to add
one fixed local AppleScript snapshot to its `triggers` section. The default is
false, preserving the ordinary OSC read cost. Unknown or failed native reads
remain null and block the corresponding capability; Automation errors preserve
the OSC data and make the requested read partial. This does not extend the root
Cue List/Cart editors or the generic diagnostic Get.

Existing family editors accept these common properties in `updates[].properties`:

| Properties | Values |
| --- | --- |
| `midiTriggerCommand` | 0 Note Off, 1 Note On, 2 Key Pressure, 3 Control Change, 4 Program Change, 5 Channel Pressure; no Pitch Bend |
| `midiTriggerChannel` | -1 any channel, 0 workspace channel, 1–16 explicit channel |
| `midiTriggerByte1`, `midiTriggerByte2` | Integers 0–127; byte 2 unavailable for one-byte commands |
| `midiTriggerByte1String`, `midiTriggerByte2String` | `any`, decimal 0–127, `<n` or `>n`; never combine both aliases of a byte |
| `wallClockHours`, `wallClockMinutes`, `wallClockSeconds` | 0–23, 0–59, 0–59, respectively |
| `midiTriggerEnabled`, `wallClockTriggerEnabled`, `timecodeTriggerEnabled` | Strict booleans, subject to activation gates |
| `timecodeShowAsTimecode` | Strict boolean; true Timecode, false Real Time |
| `hotkeyTriggerEnabled` | Disabling only; enabling requires unreadable key/modifier dependencies and is blocked |

The installed QLab 5.5.10 SDEF defines numeric MIDI trigger bytes as integers;
the published dictionary's byte-one string type differs. Reads preserve native
numeric and display representations, including comparator baselines. Numeric
setters preserve an existing comparison operator (`<70` becomes `<0`
when setting its numeric byte to zero). Use the string setter, such as `"0"`,
to request exact matching; inspect both representations after every change. These
properties configure *incoming triggers*, distinct from a MIDI cue's outgoing
`status`, `byte1`, `byte2` and `channel`.

Example, after resolving the exact cue UUID and reading its native configuration:

```json
{
  "workspace_id": "00000000-0000-4000-8000-000000000001",
  "dry_run": true,
  "updates": [{
    "cue_id": "00000000-0000-4000-8000-000000000002",
    "properties": {
      "midiTriggerChannel": 4,
      "midiTriggerByte1": 60,
      "midiTriggerByte2String": "any"
    }
  }]
}
```

Use the destination cue's family editor and obtain fresh signed tokens for every
setter. Configuration requires its trigger disabled. Change MIDI command alone,
read its bytes again, then prepare another call. Change activation separately;
enabling requires disarmed, `continueMode=0` and `skipIfDisarmed=false`.
Disarmed cues can still auto-continue/follow, so disarming alone is insufficient.
Safety controls and OSC Timecode values cannot share a native Trigger call.
Timecode activation/display also requires a readable containing-list format and
valid saved Timecode. Hotkey assignment, weekday selection and Capture remain
unavailable. Display changes can alter text representations without changing
the saved time; reread before another Timecode edit.

Every token binds the full native/safety snapshot. Each setter rechecks it inside
the fixed script and verifies both the requested value and neighboring fields.
Unexpected changes or uncertainty stop the batch without retry. No signals,
global input overrides, GO or capture are sent. Subsequent arming is a separate
operator decision; this configuration is not a playback certification.

## Edit Devamp and Target cues

Use `qlab_edit_devamp_cues` or `qlab_edit_target_cues` with the same
`workspace_id`, 1–50 UUID `updates`, typed `properties`, `confirm_gates` and
`dry_run` workflow described for [Control edits](#edit-control-cues). All
confirmations are signed, single-use, expire after five minutes and bind the
specific tool as well as the baseline and dependencies. They cannot migrate
between families. Whole-batch preflight, same-connection `/alwaysReply` for OSC, fresh
readback, stop-on-failure and no automatic resend/rollback are shared.

Both expose Basics and supported OSC/native Triggers, plus `cueTargetID` (exact UUID or `""` to
clear). Neither accepts duration, patches, target modes or temporary targets.
`qlab_get_control_cue_details` advertises the appropriate Edit tool and per-cue
blocked properties. Fade & Stop scope remains blocked if its exact query returns
boolean: some newly created QLab 5.5.10 cues do so even on the scalar endpoint.

Devamp additionally exposes `devampType` (1: looping slice; 2: looping cue),
`startNextCueWhenSliceEnds` and `stopTargetWhenSliceEnds`. Settings changes
require a healthy inactive Audio/Video target. Requesting Stop target enabled
requires Start next enabled in the resulting settings. The start-next setter
precedes stop-target when both are present. Basics can be edited on an untargeted
cue; assigning a target repairs an untargeted cue without executing it.

Target requires a healthy inactive target that accepts cue targets; Fade targets
are rejected. **`number` means this Target cue's own number.** The separate Cue
Number tab's `assignedNumber` uses fixed local AppleScript. Supply an existing,
unique workspace cue number or `""` to clear it. The server resolves and binds
that number to an exact cue UUID; nonexistent, ambiguous and self assignments
are rejected. Setting this text does not change the receiver's current target.
It configures the temporary target to be applied only if the Target cue is
later run by the operator. Untargeted placeholders remain broken.
Change `cueTargetID` or renumber a referenced cue in a separate call with a new
dry run. No Target cue is executed. The generic editor has been removed.

Both native fields use the same five-minute signed tokens as other edits.
Their plans explicitly report `transport="applescript"` and `address=null`;
there is no fictional OSC endpoint. Every setter is sent once and followed by
fresh readback. A script timeout can be confirmed by that readback; an uncertain
result stops the batch. Restart the MCP process after updating its source.


## Edit Video, Camera and Text cues

Use `qlab_edit_video_cues`, `qlab_edit_camera_cues` or `qlab_edit_text_cues` with
one exact workspace UUID and 1–50 distinct cue UUIDs of that type. First read the
matching `qlab_get_*_cue_details` and its `triggers` and `edit_capabilities`.

Each update contains `cue_id`, typed `properties`, and `confirm_gates`.
Run `dry_run=true`, review every previous value and OSC setter, then copy all
fresh `confirm_token` values from that cue's `planned_operations` into its
`confirm_gates` and execute with `dry_run=false`. Tokens expire in five minutes,
are single-use and cannot move between these tools. A stale cue value, type,
routing reference or workspace activity invalidates the preflight.

The tools cover Basics and documented OSC Triggers, stage routing by UUID,
geometry, opacity and framing. Video adds file targeting (existing absolute
paths), audio output routing, timing/loops,
integrated fade, indexed slices and audio levels/channel metadata. Camera adds
video/audio input and audio output routing. Text adds content, width, font,
color, alignment, shadow and decoration attributes with readable format
fragments. `text` inherits the first character's format; verification checks it.
Coordinates are OSC coordinates; opacity is 0–1, colors are RGBA 0–1, layer is
0–1000 and quaternion must be a unit quaternion. Composite geometry and its
components cannot be supplied together.

For indexed properties, supply the typed selector and requested value inside
the property object, for example `level: {inChannel: 1, outChannel: 1, decibel: -12}`
or `translation: {x: 12.5, y: -3.25}`. Audio channels must fit the observed input
and patch output bounds. Only `-inf` is accepted as a nonnumeric audio level.
Mute/solo cleanup and rotation reset take exactly `true`.

A batch validates all cues before its first setter, then writes sequentially.
It is non-atomic and has no automatic rollback. Inspect applied, failed and
pending operations. A timeout permits only a fresh readback; never resend an
uncertain setter. Cue health and runtime readiness remain separate from editing.
Repair broken media/routing separately before visual changes.

`crop` uses `{top, bottom, left, right}` for requests and previous/verified values,
although QLab's OSC getter returns a four-element list. Integer `preservePitch`
readbacks are normalized to booleans; requests still require actual booleans.
Timecode validation reads the containing List/Cart's format with fresh
identity-checked `valuesForKeys`; setting a time does not activate the trigger.

For a nonuniform aggregate scale, request `preserveAspectRatio=false`.
When restoring a scale pair and enabling aspect preservation together, the
scale setter precedes enabling the lock. Supply both scale components in that
case. A single component can still change with an existing aspect lock; QLab
may update the other component too. The lock is a fresh confirmation dependency.

A cue with a warning can remove confirmed mutes/solos or clear their readable
inventories, provided it is inactive and explicitly unbroken. Other visual edits
still require healthy state. Clearing returns the freshly observed empty list.

Missing OSC slice inventory remains unknown, not an empty list; those edits are
blocked in capabilities and preflight. QLab 5.5.10 can return an error at the exact
media end even when fresh readback equals the requested value. The tool retains
the error, stops the batch and never resends. Keep end-time restoration separate
from unrelated changes and inspect the fresh result. See the
[live investigation](../development/runtime-validation/2026-10-02-visual-cue-fixes.md).

Unreadable/mixed Text attributes block their scalar setters. Fade & Stop scope
requires integer readback. Camera input channel count/offset remain blocked
until input bounds can be verified. Typed FX operations require native index/type
proof and a complete fresh stack. Text formatting limits are described below.
Audio FX and default/silent bulk levels remain pending. Stage/region edits use
Workspace Settings tools. Supported MIDI/Wall Clock configuration and guarded
MIDI/Wall Clock/Timecode activation follow the separate
[native Trigger workflow](#native-cue-triggers). Hotkey assignment/enabling,
capture, Audio Maps, `/live` and playback remain excluded. Retarget media
separately before changing media-dependent properties.


## Edit Audio, Mic, Light, Fade, Network, MIDI, MIDI File, Timecode and Script cues

Read the matching `qlab_get_*_cue_details` first. MIDI details distinguish MIDI
from MIDI File. Optional `inspections` reads at most 50 explicitly requested
scalar/indexed destinations, with typed selectors and no setter values. It does
not enumerate every crosspoint, object or parameter. Use the technical profile
for free text and file paths. Inspect errors, unknown values and capabilities.

All nine editors keep `workspace_id`, `updates`, `dry_run`. Supply 1–50 distinct
UUIDs of the same family. Each update contains optional typed `properties`,
optional typed `operations` (at most 50 per cue), and `confirm_gates`. An indexed
operation contains `property` and its typed `args`. Operations-only requests are
supported. Empty edits, null properties, arbitrary OSC, duplicate destinations,
overlapping aggregates/components and aliases addressing the same setter fail.

Example Audio dry run (replace UUIDs with resolved exact values):

```json
{
  "workspace_id": "8E86FE91-668B-560C-B738-4D581B5A7498",
  "updates": [{
    "cue_id": "C45EE972-F0E8-5241-8D10-28F86D5F05EC",
    "properties": {"rate": 1.1, "duckOthers": true},
    "operations": [
      {"property": "level", "args": {"inChannel": 1, "outChannel": 1, "decibel": -3}},
      {"property": "level", "args": {"inChannel": 2, "outChannel": 2, "decibel": -4}}
    ]
  }],
  "dry_run": true
}
```

Review every baseline, requested value, setter order and error. Copy all emitted
`confirm_token` values into that cue's `confirm_gates`, then execute once with
`dry_run=false`. Every setter requires a signed, tool-bound, five-minute,
single-use token binding workspace, cue/type, canonical indexed destination,
old/new values and dependencies. Generic editor tokens cannot authorize these
family edits. Basics, OSC Triggers and supported family settings share this flow.

The complete batch is validated before the first setter and all confirmations
are reserved together. Before each setter, identity, inactivity, dependencies,
access/Edit Mode and the exact baseline are rechecked. Preparation of
`/alwaysReply` uses the setter's own UDP socket/TCP session; preparation failure
sends no setter. Empty acknowledgements are accepted only for known setters.
Queries still require data. Each setter is sent once and read back immediately;
a timeout may succeed only with matching fresh verification. Never retry an
uncertain setter. Pending operations remain unsent after failure or budget expiry.
Execution is sequential, non-atomic, with no automatic rollback. Restore tests
through a new dry run and new tokens.

Selectors (file, patch, target, MIDI mode/status, Timecode mode/frame rate,
Network fade mode) can reset dependent inspector values. Their snapshots are
read before/after; do not combine them with dependent family settings or duration.
Read again and prepare a second call. Common Basics/Triggers may accompany a
selector if their dependencies remain valid. Cross-cue dependency edits must be
split into separate batches. Slice reordering also requires a separate call;
multiple play-count edits verify the full cumulative slice inventory.

| Family | Conditions and limits |
| --- | --- |
| Audio | Healthy media for timing; exact output patch and known channel bounds for Levels. Cue-owned objects require a matching UUID inventory and proven absence of an Audio Map. Integrated Fade exposes saved flags, not undocumented curves. |
| Mic | Exact input/output patch selection, Levels and cue-owned Objects. `channels`/`channelOffset` stay blocked without a readable input capacity. |
| Light | Commands must resolve completely against the current workspace Light patch. Collate/Subcontroller/duration use the same confirmations; no light execution. |
| Fade | Cue/patch targets must resolve in the workspace. Values and activation flags must fit the target; relative silence and removing the last active parameter are rejected. Capture from target stays excluded without a complete expected snapshot. |
| Network | `customString` is opaque saved text. Patch UUID membership is required, not a guessed patch-name protocol. Fades need readable mode/bounds; Device Definition parameters stay pending and blocked without metadata. |
| MIDI | Saved Voice/MSC/SysEx only. Byte aliases/status, 7/14-bit ranges and compatible fade commands are checked. MSC command-dependent fields stay blocked without activation metadata. SysEx uses 7-bit hexadecimal payload without F0/F7. |
| MIDI File | Existing absolute file path, MIDI Type 0/1 header, healthy readable timing. Type 2 is rejected. |
| Timecode | `startTime` and `endTime` are SMPTE strings such as `"01:00:01:00"`, not numeric seconds. The current cue format validates SMPTE/drop-frame. Positive LTC channels require a known patch output bound; observed channel zero is not writable. QLab may normalize end time on frame-rate change while preserving duration. |
| Script | Basics and supported OSC/native Triggers. Source remains read-only; no compilation. |

Capabilities distinguish `gated`, `blocked`, `pending_validation` and
`unavailable_via_osc`; a pending property is not in `allowed_properties`.
`setDefaultLevels` stays blocked without readable template results. Cleanups and
bulk operations require a complete affected snapshot. Audio/Mic `doLevel` and
`doObjectIDLevel` are Fade-only routes and are blocked. Unknown/mixed values are
not defaults. Fade & Stop scope stays blocked if OSC returns only a boolean.

Small dB quantization is verified with the existing 0.001 dB tolerance. QLab 5.5.10
returned −59.01564 for a Fade slider request of −59: the tool reported failed
verification, retained the observed value and sent no retry. It was restored with
a fresh confirmation. This low-level boundary is not declared exact/verified.

Audio Maps, `/live`, playback, external signals, capture, Hotkey assignment/enabling,
Trim, Audio FX and undocumented curves remain out of scope. Supported incoming
MIDI/Wall Clock configuration and guarded activation use the
[native Trigger workflow](#native-cue-triggers); they do not send signals or run
cues. The generic editor has been removed. See the
[live evidence and pending fixtures](../development/runtime-validation/2026-10-05-remaining-cue-completion.md).

## FX and Text fragment operations

`qlab_get_video_effect_catalogue` lists documented effect names, parameter
keys, types, enums and numeric bands in pages. It is static reference data, not
proof that a native instance can be identified or written. Follow it with an
exact cue UUID and selected indexed Get. Missing native attributes have no
inferred aliases or defaults. Native Linear Key and Drop Shadow creation stays
blocked; edits require readable values and a uniquely identified instance.

Video, Camera and Text editors accept typed `operations`, up to 50 per cue,
with optional `properties`. Details accept up to 50 `video_effects` selectors
(zero-based `index`, optional `effect_type` assertion and optional `key`). If
`effect_type` is omitted, the Get resolves it from native indexed identity;
ambiguous identity stays blocked. Only requested parameters are returned;
preflight verifies the complete stack before any write.

FX identity requires native metadata or a documented named getter matching one
unique indexed payload. Keys only limit candidate queries; UI names never
validate a setter. Duplicate/ambiguous instances remain blocked. Parameters
use the published write bands; reads preserve out-of-band values. JSON is
generated internally. The catalogue contains 60 effects and 262 destinations;
this does not mean all their defaults or structural operations are live tested.
Call `qlab_get_video_effect_catalogue(offset=0, limit=10)` and follow
`next_offset` until it is null. `limit` is 1–10 (default 10), not the total
catalogue size. Optional `effect_types` accepts 1–10 exact types and filters
before pagination. This catalogue is static metadata; it takes no workspace UUID.
Vector/boolean parameter operations use an internally generated JSON setter
and aggregate native reads; numeric/enum operations retain scalar routes.

Structural changes require one operation per cue, without other changes.
QLab must be 5.5.10. Creation defaults have native evidence for 58 effects;
LinearKey and DropShadow add/insert are blocked because neither route created
an effect during testing. Adding a repeated type is blocked. An effect without recorded native defaults
remains blocked; the editor does not invent defaults.
These creation blocks do not prevent editing an existing instance with native
identity and readable parameters. LinearKey and DropShadow created manually by
the user passed reversible OSC edits in 5.5.10. DropShadow uses `Color` in its
native aggregate and inspector tooltip, although the reference says `inputColor`.
Use `key: "Color"` for its typed selector/parameter operation; RGBA components
must be finite numbers in 0–1. Capabilities expose this native spelling in
`native_parameter_aliases`; the MCP does not translate a request for `inputColor`
into `Color`. Requests for both spellings in one update are rejected as conflicts.
Runtime key differences are preserved. A parameter absent from the native
aggregate cannot be written, even when the reference lists it. Deletion requires
complete reconstruction proof, so unknown, unwritable attributes can still block
it. In the source editor, a native attribute without a setter is reconstructable
only when it exactly matches that effect's recorded 5.5.10 creation default;
otherwise deletion remains blocked. Only documented parameters are sent during
reconstruction. Verify the updated MCP in QLab before relying on this path.
Move requires a fully identified stack. Insert/delete/move also require a complete fresh cue
inventory with no Fade targeting the source cue. Neighbors, parameters, order
and dependencies are checked again after the setter. No automatic rollback.

Text uses `property: "text/format"` and typed `args.selector` / `args.attributes`.
Full and range selectors use UTF-16 units, never split surrogate pairs, and
accept length `-1` for the remainder. Typed percentages resolve using nearest
rounding. Word selection is zero-based: ASCII alphanumeric and Latin words
may be separated by spaces, tabs, CR/LF, NBSP, guillemets `«»`, curly double
quotes `“”` or an em dash `—`. Other punctuation, contractions, combining marks
in words and other scripts require explicit ranges or further native evidence.
Range/full selections may contain ASCII/Latin characters or combining marks;
color-only operations additionally accept the verified NBSP, `«»`, `“”` and `—` characters.
Emoji/other scripts remain blocked even for color: QLab can change font metadata
through fallback. The full effective format, including every companion attribute,
must match after the setter.

```json
{"cue_id":"<text-cue-uuid>","operations":[
 {"property":"text/format","args":{
  "selector":{"kind":"range","index":{"percent":25},"length":{"percent":25}},
  "attributes":{"fontSize":48}
 }}
]}
```

Call `qlab_get_fonts(workspace_id)` to read exact application-wide PostScript
names and family/style inventories over TCP. They do not map each name to its
family/style or prove glyph coverage. Partial `fontName` or
`fontFamilyAndStyle: {"family":"Helvetica Neue","style":"Regular"}` changes
require a complete, unambiguous name/family/style tuple already observed in the
same cue's runs. A previously unseen font cannot be introduced through that
partial operation. Full runs and all observed extras are preserved and bound
to tokens; equivalent native run splitting/merging is accepted.

Separate content replacement and formatting. Missing attributes never acquire
invented defaults. Shadows remain blocked if fragment attributes are absent,
JSON transport is unverified, or partial-line behavior cannot be read back.
The verifier checks every attribute and stops on unrequested font
normalization, with no setter retry. See the
[live evidence](../development/runtime-validation/2026-10-09-osc-text-fonts-video-fx.md)
for experimental fixture preparation versus production tests and restoration.
See also the [Text selection follow-up](../development/runtime-validation/2026-10-11-text-selections.md).

## File targets

Obtain conversational consent for the needed files. Reuse authorization already
granted for this task and scope; ask if it is missing or the scope changes.
The server cannot verify conversation consent. After authorization, use `qlab_search_media_files(query="trueno", max_results=20)`
to find files by case-insensitive filename substring in the MCP user's home
folder. It returns absolute paths and file sizes, skips symlinks, and stops
after 20,000 entries, five seconds or the result limit.
`truncated=true` means the result is incomplete; warnings identify directories
that could not be fully inspected. Results are candidates, not proof of a valid
media format. macOS permissions still apply to the account running the MCP.

Assign the chosen absolute path using `properties.fileTarget` in
`qlab_edit_audio_cues`, `qlab_edit_video_cues` or `qlab_edit_midi_file_cues`.
Use the exact workspace and cue UUID, dry-run, fresh confirmation tokens and
fresh readback. Retarget first; change media-dependent timing or levels in a
subsequent call. Editors check file existence and file metadata.
Audio, Video and MIDI File verification additionally requires `isBroken=false`.
MIDI File supports Type 0/1 and rejects Type 2. The tools reference existing
local files; they do not copy or download them. iCloud files must be locally
available, and supplied paths must use their actual filesystem location.


## Audio file analysis

After conversational file access consent, get `fileTarget` from the exact Audio
cue's technical detail or use `qlab_search_media_files`. Call:

```json
{"path":"/absolute/path/song.mp3","resolution_ms":100}
```

This is a file read, independent of QLab, with no OSC connection or playback.
Optional installation: `uv sync --locked --no-editable --python 3.11 --extra audio --extra dev`; FFmpeg and ffprobe
must resolve inside the MCP process PATH. Missing components return
`dependency_missing`; the base MCP and other tools remain usable. Supported
containers: WAV, AIFF, MP3, M4A, FLAC, OGG; one audio stream, 1–8 channels,
8–192 kHz. Attached cover art is allowed; actual video/multiple tracks are not.

Every tuple follows `timeline.columns` and `timeline.units`:

| Column | Meaning |
| --- | --- |
| `start_s`, `end_s` | Source-file interval, seconds |
| `rms_dbfs` | Mean sample power across channels, converted to dBFS |
| `peak_dbfs` | Largest absolute original sample across channels; not true peak |
| `low_ratio`, `mid_ratio`, `high_ratio` | Relative spectral power in 20–250, 250–2000, 2000–analysis Nyquist Hz |
| `centroid_hz` | Frequency average weighted by channel-mean magnitude |
| `onset_strength` | Maximum positive mel-band dB change; fixed reference, not probability |
| `delta_rms_db` | Difference from the preceding row at this same resolution; first/undefined difference is null |
| `silent` | RMS at or below −60 dBFS; this is a threshold, not a semantic label |

Digital silence has null dBFS/ratios/centroid, not fabricated finite levels.
Silence regions require 300 ms on a 10 ms base grid before clipping to the page.
Original channels are preserved: antiphase stereo does not disappear through
mono summation. Spectral processing resamples to min(source rate, 22050 Hz),
with Hann FFT 1024 and hop 256 (at 22050 Hz: 46.44 ms / 11.61 ms). Output at
10 ms does not promise 10 ms detection accuracy. Parameters are returned.
Onset/beat arrays contain individual estimated times, not 100 ms rounding.
BPM uses context onset autocorrelation over 40–240 BPM with a log2 prior around
120 BPM, then librosa beat tracking. It can select half/double tempo; calibrated
confidence is unavailable.

### Pages and scope

At most 5000 rows and 512 KiB of result JSON per call. All measurements/events
are included in that budget. If `timeline.complete=false`, repeat the same
path/range/resolution using `timeline.next_offset` and the previous
`analysis_id` as `expected_analysis_id`. Identity derives from resolved path
and stat metadata plus algorithm version; it is **not a content hash**.
Changed/replaced files require a new first page. Resolution options are
10, 20, 50, 100, 250, 500, 1000 ms. Ranges use millisecond integers divisible
by 10; `offset` addresses rows within that requested interval.

Thirty minutes at 100 ms gives 18,000 rows. Thirty minutes is a tested use case,
not a hard duration limit. A source block spans up to 300 seconds, with up to
15 seconds of context at each side. Only requested blocks are decoded; cached
features (not PCM) are capped at four blocks / 128 MiB / ten minutes. One new
calculation runs at a time; valid cached reads can proceed. Per-call computation
budget is 260 seconds, public timeout 300 seconds; interrupted/failed processes
are terminated and reaped. Partial completed work has an explicit continuation.

`summary` covers the returned page only. `loudness_regions` measure the fixed
source blocks (or whole source when it fits one block), using FFmpeg loudnorm
**input** LUFS/LRA/true peak; no normalized file is saved. Never average LUFS
across blocks. Rhythm estimates publish their separate context scope.
`complete` means interval coverage; `status=partial`/`errors` still disclose an
unavailable loudness measurement. No confidence, defaults or semantic labels
are invented. `duration_reported_s` and `duration_decoded_s` remain distinct;
the latter is known after a block reaching the actual end has been decoded.
Codec padding/duration interpretation can differ from QLab; the checked song
differed by about 12 ms. Do not assume decoder times are sample-exact QLab timing.

Stable error codes: `invalid_request`, `file_not_found`, `file_unreadable`,
`unsupported_media`, `dependency_missing`, `resource_limit`, `analysis_busy`,
`analysis_timeout`, `source_changed`, `decode_failed`.

### Use with QLab

Read cue timing before deriving light-cue positions. For simple forward playback
without loops/slices, an event's action position is
`(event_time_s - startTime) / rate`; add `preWait` when timing from GO. Only
source events within the trim apply. Loops/slices require choosing the occurrence
and reading their configuration; this formula is not a universal mapping.
Then use existing cue editors with their dry run/confirmation/readback protocol.
Computer Use can contrast the file path and duration, but a waveform screenshot
cannot validate frequency ratios, LUFS or beats. Lyrics, transcription, key,
downbeats, event classifiers and execution remain outside this tool.
