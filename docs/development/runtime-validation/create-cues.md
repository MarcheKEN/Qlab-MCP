# `qlab_create_cue` Runtime Checklist

Use this checklist only in a disposable editable QLab workspace. Workorder 031
runtime proof is limited to one blank anchored Wait cue.

## Hard limits

- Use only QLab MCP tools; do not send raw OSC.
- Use an explicit workspace UUID and an exact anchor cue UUID.
- Require Edit Mode, a healthy inactive anchor inside a linear Cue List or
  Group, and `running/paused/auditioning = 0/0/0`.
- Record DMX Output before writing and verify it is unchanged afterward.
- Do not use GO, playback, Audition, Stop, Panic, `/live`, workspace save, or
  automatic cleanup.
- Send `/new` once at most. Never retry after a timeout.

## Create procedure

1. Call `qlab_check_connection(require_read_access=true)` and resolve exactly
   one workspace UUID.
2. Read the workspace overview, status, settings, and anchor details. Confirm
   Edit Mode, zero activity, anchor health, parent, and current sibling order.
3. Run:

   ```text
   qlab_create_cue(
       workspace_id=<workspace UUID>,
       cue_type="wait",
       after_cue_id=<anchor UUID>,
       dry_run=true,
   )
   ```

4. Require structured content, `status="dry_run"`, a fresh
   `confirm:createCue:v1` token, an anchored placement plan, parent/order
   fingerprints, and `executed_operations=[]`.
5. Execute exactly one real Create with the exact token. Require
   `status="created"`, a valid `created_cue_id`, and
   `cleanup_required=false`.
6. Perform fresh readback of the created UUID/`uniqueID`, type, parent, health,
   `isRunning`, `isPaused`, `isAuditioning`, and sibling order. Confirm the new
   cue is immediately after the anchor and that no unexpected cue exists.

Stop immediately on timeout ambiguity, structural drift, missing structured
content, invalid identity/type, wrong parent/order, failed health/activity
verification, or any unexpected extra cue. Do not apply properties after an
ambiguous `/new` result.

## Manual cleanup

Only after the new UUID is proven unambiguous:

1. Run `qlab_delete_cues` dry-run for that UUID only.
2. Confirm the plan contains one exact leaf cue and a fresh
   `confirm:deleteCues:v1` token.
3. Execute the Delete once with that token.
4. Read back non-existence of the created UUID, continued existence of the
   anchor, original parent children, `0/0/0` activity, and unchanged DMX.

Create never performs automatic cleanup. `cleanup_required=true` means manual
inspection is required; it is not permission to guess or retry. `/new` timeout
or invalid identity is indeterminate because QLab may have created the cue.
The Create token is consumed before `/new`; replay is rejected and recovery
requires workspace inspection plus a fresh dry-run/token. There is no idempotency
key or public AppleScript fallback backend.

## Evidence boundary

The allowlist currently includes blank `memo`, `group`, `wait`, and `audio`, but
031 runtime evidence certifies only blank `Wait`. It does not certify new cue
types or property families. Real placement is limited to `after_cue_id`; Group-
empty insertion, Cue Cart row/column placement, `parent_id + position`, and
arbitrary index placement require separate workorders. “Blank” means no initial
properties were supplied; Cue Templates and QLab Wait normalization may affect
readback.

