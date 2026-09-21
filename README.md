# QLab MCP

QLab MCP `0.3.0` is a FastMCP server for inspecting QLab 5 workspaces over OSC
and requesting narrowly gated structural writes. It is read-only by default;
write mode is disabled unless explicitly configured and remains dry-run-first.

The public surface is intentionally focused: 16 read-only tools and 6 gated write
tools. The server exposes no playback or raw-protocol escape hatch.

## Capability boundaries

| Capability | Included | Contract |
| --- | --- | --- |
| Read-only inspection | Yes | Workspace, settings, cue discovery, cue details, and write readiness |
| Structural Create/Edit/Move/Delete | Yes, gated | Exact targets, readiness, dry-run, confirmation, and fresh readback |
| GO, playback, stop, panic, Audition | No | Intentionally outside this MCP surface |
| Raw OSC, AppleScript writes, `/live` control | No | No arbitrary protocol or playback writes |
| Implicit `selected`, `active`, or `playhead` writes | No | Write targets must be concrete numbers or UUIDs |

See [`SECURITY.md`](SECURITY.md) for the threat model, invariants, accepted
risks, and QLab 5.5.10 evidence boundary.

## Quick start

Use the documented non-editable Python 3.11 environment:

```bash
uv sync --no-editable --python 3.11 --extra dev
uv run qlab-mcp
```

Inspect the generated MCP contract without connecting to QLab:

```bash
uv run fastmcp inspect fastmcp.json
```

For a read-only orientation session:

1. Open QLab and enable the workspace's OSC access if required.
2. Start the server and call `qlab_check_connection`.
3. If multiple workspaces are returned, choose one by exact UUID.
4. Follow the [agent read workflow](docs/user/agent-workflows.md#read-sequence).

Set `QLAB_PASSCODE` in the server environment for a passcode-protected
workspace. The passcode is never a tool argument.

## Tool Groups

The table below is the authoritative human inventory. Generated schemas and
`tests/test_server_tools.py` define exact arguments, result models, and
annotations.

| Tool | Purpose | Risk / boundary |
| --- | --- | --- |
| `qlab_check_connection` | Reachability, workspace candidates, scopes, and mode | Read-only; not write authorization |
| `qlab_get_workspace_overview` | Bounded cue-list/group/cart structure | Read-only; not deep Inspector detail |
| `qlab_get_workspace_status` | Derived cue warnings, known Video Settings problems, and timecode context | Read-only; warning coverage is partial, not a full Status-window clone |
| `qlab_get_workspace_general_settings` | Documented General settings | Partial OSC coverage: minimum GO time and selection/playhead lock |
| `qlab_get_workspace_audio_settings` | Audio overview; exact patch routing, mute/solo, and one optional matrix crosspoint | Read-only; Audio Maps and full-matrix scans are excluded |
| `qlab_get_workspace_video_settings` | Compact Video input, route, and stage inventory | Read-only; three bulk OSC reads |
| `qlab_get_video_stage` | One stage and its regions | Read-only; exact stage UUID, safe or technical profile |
| `qlab_get_video_output_route` | One output route and its destination | Read-only; exact route UUID, safe or technical profile |
| `qlab_get_workspace_light_settings` | Light Patch summary or redacted technical payload | Read-only; no Light Definitions or Dashboard settings |
| `qlab_get_workspace_network_settings` | Network Patch inventory or exact patch | Partial OSC coverage; not the complete Network panel |
| `qlab_get_workspace_midi_settings` | MIDI Patch inventory or exact patch | Partial OSC coverage; not the complete MIDI panel |
| `qlab_query_cues` | Bounded filtered cue discovery | Read-only; not full payload inspection |
| `qlab_get_cue_lists` | Compact Cue List inventory and current container | Read-only; excludes Cue Carts and children |
| `qlab_get_cue_list_details` | Exact Cue List state, playhead, timecode and bounded contents | Read-only; UUID-only; safe or technical |
| `qlab_get_cue_details` | Exact cue properties and health | Read-only; use exact refs for later writes |
| `qlab_check_write_readiness` | Preflight before any real write | Read-only report; not a confirmation token |
| `qlab_create_cue` | One template-backed structural creation | Gated, additive structural write; not initial setters or GO |
| `qlab_create_cues` | Ordered sequential creation, 1–50 items | Gated, non-atomic batch; no automatic rollback |
| `qlab_edit_cues` | Allowlisted property/operation edits, 1–50 items | Gated, per-operation confirmation, non-atomic |
| `qlab_edit_workspace_settings` | One exact `general.minGoTime` saved-setting write | Gated, one setter, fresh token, fresh readback |
| `qlab_move_cues` | Sequential structural moves, 1–10 UUID targets | Gated, destructive metadata hint, non-atomic |
| `qlab_delete_cues` | Explicit leaves, one empty Group, or root-preserving recursive emptying | Gated destructive, sequential, non-atomic |

## Read Model

The normal read path is progressive rather than a full-show dump:

1. `qlab_get_workspace_overview` maps bounded structure.
2. `qlab_get_workspace_status` adds derived operational context.
3. Use the relevant `qlab_get_workspace_*_settings` tool for infrastructure.
4. `qlab_query_cues` finds a bounded target set.
5. `qlab_get_cue_details` inspects exact properties.

For Cue Lists, use `qlab_get_cue_lists` followed by `qlab_get_cue_list_details`
with a returned UUID. Generic Cue Details returns a structured redirect for
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

Every real Create, Edit, Move, Delete, or Workspace Settings write follows this
compact sequence:

1. Resolve one explicit workspace and exact cue/container UUIDs.
2. Call `qlab_check_write_readiness`.
3. Run `dry_run=true` and review plan, diff, warnings, errors, and empty
   `executed_operations`.
4. Supply only the fresh token or per-operation gates returned by that plan.
5. Execute once; never automatically retry timeout or identity ambiguity.
6. Require fresh structural/property readback before deciding on recovery.

`qlab_edit_workspace_settings` is intentionally narrower than cue editing: it
accepts one exact workspace UUID and a typed `operation` object with
`kind="general.minGoTime"` plus a finite non-negative seconds value. The dry-run returns one fresh
`confirm:workspaceSettings:v1:` token and one exact saved-settings setter plan.
Real execution rechecks readiness, exact workspace identity, baseline, and
zero running/paused cues, then sends exactly one qualified
`/workspace/{uuid}/settings/general/minGoTime` setter and requires a fresh
no-argument readback. The current activity reader cannot prove workspace-wide
Audition state, so keep Audition disabled. Timeout-confirmed and inconclusive
results are evidence states, not GO or playback authorization.

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
QLAB_ALLOWED_FILE_ROOTS=
```

`QLAB_ENABLE_WRITE` must be explicitly enabled for real writes. Keep
`QLAB_WRITE_DRY_RUN_DEFAULT=true` unless a deliberate session requires another
default. `QLAB_UPDATE_DEBUG` adds optional Edit diagnostics and does not weaken
gates or verification. Configuration behavior is implemented in
`src/qlab_mcp/config.py`; this list is only the entry-point summary.

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
- [14-tool catalogue](docs/user/tools.md)
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
uv run fastmcp inspect fastmcp.json
```
