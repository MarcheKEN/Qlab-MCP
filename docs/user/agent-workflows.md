# Agent Workflows

This guide describes how an agent should discover QLab state and request gated
structural writes. It is workflow guidance, not a replacement for the tool
schemas or the server-side safety checks.

## Choose the tool

| Intent | Tool | Not for |
| --- | --- | --- |
| Check QLab reachability, workspaces, scopes, and mode | `qlab_check_connection` | Write authorization or cue detail |
| Map cue lists, groups, carts, and bounded structure | `qlab_get_workspace_overview` | Deep properties or operational status |
| Read derived status, warnings, and timecode context | `qlab_get_workspace_status` | A full QLab Workspace Status clone |
| Read settings summary or independent detail requests | `qlab_get_workspace_settings` | Mutating patches or routes |
| Read one settings item | `qlab_get_workspace_setting_details` | Batch settings discovery |
| Find a bounded set of cues with filters | `qlab_query_cues` | Full Inspector payloads |
| Inspect exact cue properties | `qlab_get_cue_details` | Resolving an ambiguous write target |
| Check write-mode preconditions without mutating | `qlab_check_write_readiness` | Confirmation or authorization by itself |
| Create one cue from a template | `qlab_create_cue` | Initial setters, playback, or GO |
| Create an ordered sequence | `qlab_create_cues` | Atomic transactions or automatic rollback |
| Edit allowlisted properties and operations | `qlab_edit_cues` | Create, Move, Delete, playback, or raw OSC |
| Move existing cues structurally | `qlab_move_cues` | Playback or Cart writes not runtime-proven |
| Delete leaves, one empty Group, or empty one preserved container | `qlab_delete_cues` | Deleting the requested root or automatic rollback |

## Read sequence

1. Call `qlab_check_connection` and select one workspace by exact UUID when
   several candidates are available.
2. Call `qlab_get_workspace_overview` for the bounded structural map. Use
   `qlab_get_workspace_status` for derived operational context and
   `qlab_get_workspace_settings(mode="summary")` for infrastructure context.
3. Use `qlab_query_cues` to discover a bounded set of targets.
4. Use `qlab_get_cue_details` with exact cue numbers or unique IDs for the
   properties needed by a later decision. Do not turn `selected`, `playhead`,
   or `active` into a write target.

Read profiles and limits are part of each tool schema. Prefer compact profiles;
use technical or exhaustive reads only when the result is justified.

## Common write gate

Every real write follows this shape:

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

Writes are disabled by default and remain subject to server-side environment,
passcode, `/connect` Edit permission, and Edit Mode checks. MCP annotations and
descriptions help clients choose a tool; they are not authorization.

## Create one cue

`qlab_create_cue` accepts one template-backed cue type and exactly one placement
selector: an existing `after_cue_id`, or an empty `parent_container_id`.
The dry-run token is `confirm:createCue:v2`. Creation verifies identity and
placement but does not configure files, targets, patches, or initial setters.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_type": "wait",
  "after_cue_id": "<cue-uuid>",
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_type": "wait",
  "after_cue_id": "<cue-uuid>",
  "parent_container_id": "<container-uuid>",
  "dry_run": false
}
```

The invalid example supplies both placement selectors and skips the reviewed
dry-run/token. A created cue can still be `broken` or `warning`; structural
creation is not runtime validation and is not a GO-ready claim.

## Create a sequence

`qlab_create_cues` accepts 1–50 ordered cue types. Use one initial placement
selector and the exact `confirm:createCues:v1` token. Each verified created UUID
becomes the next anchor. The batch token is not interchangeable with the
single-create token. The sequence stops on the first timeout, identity
ambiguity, placement mismatch, or other failure; earlier items remain and there
is no automatic rollback.

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
  "parent_container_id": "<container-uuid>",
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "cue_types": ["memo", "wait"],
  "after_cue_id": "<cue-uuid>",
  "parent_container_id": "<container-uuid>",
  "confirm_token": "<single-create-token>",
  "dry_run": false
}
```

Do not retry an ambiguous `/new`. If the result requires cleanup, inspect the
workspace and use a new Delete dry-run/token only after the created UUID is
unambiguous.

## Edit existing cues

`qlab_edit_cues` accepts 1–50 update items. Resolve each `cue_ref` to a concrete
cue number or unique ID; `selected`, `active`, `playhead`, and
`playbackPosition` are not write targets. Use `qlab_get_cue_details(profile="editable")`
to discover compatible profiles and properties.

Edit has no global confirmation token. A dry-run returns per-operation
`confirm_gates`; copy only the exact gates required by the reviewed plan into
that item. The batch is non-atomic: one item can succeed while another fails.
Require fresh readback after each item. A timeout confirmed by readback is not a
reason to retry the setter; an inconclusive timeout requires inspection first.

Good shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "updates": [
    {
      "cue_ref": "<cue-uuid>",
      "profile": "fade_basic",
      "properties": {"duration": 2.0}
    }
  ],
  "dry_run": true
}
```

Invalid or unsafe shape:

```json
{
  "workspace_id": "<workspace-uuid>",
  "updates": [{"cue_ref": "selected", "properties": {"name": "Guess"}}],
  "dry_run": false
}
```

The invalid example uses an implicit selection and skips readiness, dry-run, and
per-operation confirmation. Edit does not expose Create, Move, Delete,
playback, or raw OSC operations.

## Move existing cues

`qlab_move_cues` accepts 1–10 UUID-only source cues. For List/Group placement,
provide exactly one of `destination_index`, `before_cue_id`, `after_cue_id`, or
`position`; Cart coordinates require both `cart_row` and `cart_column` and no
linear placement field. Use the exact `confirm:moveCues:v1` token from the
reviewed dry-run.

Moves execute sequentially and are non-atomic. Fresh parent/order readback is
required after each move. Cue Cart execution remains runtime-blocked by the
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

`qlab_delete_cues` accepts either 1–10 explicit leaf UUIDs, one exact empty
`Group` through `container_id` with `recursive=false`, or one container with
`recursive=true`. Direct Group deletion removes the Group itself only when it
is empty and inactive. Recursive mode deletes descendants deepest-first and
preserves the requested root. Use the exact `confirm:deleteCues:v1` token from
the dry-run.

Deletion is sequential and non-atomic, with no automatic rollback. Fresh
existence readback must verify disappearance of every requested leaf and
preservation of the root. Do not retry after timeout or identity ambiguity.

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

QLab behavior and MCP policy are different layers. QLab supports more controls
than this server intentionally exposes. This server requires exact targets,
Edit Mode, dry-run review, confirmation, and readback, and exposes no GO, stop,
panic, playback, Audition, raw OSC, AppleScript write, or `/live` workflow.

Keep this distinction in every report:

```text
estructura programada
!= runtime validado
!= show listo para GO
```

Maintainer-only runtime evidence lives in the
[Create checklist](../development/runtime-validation/create-cues.md),
[Edit checklist](../development/runtime-validation/edit-cues.md), and related
runtime-validation documents. Those checklists are not proof that a new show is
ready for GO.
