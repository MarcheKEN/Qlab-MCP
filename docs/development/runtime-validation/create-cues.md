# `qlab_create_cue` Runtime Checklist

Use this checklist only in a disposable editable QLab workspace. Workorder 031
runtime proof covers one blank anchored Wait cue. Create uses only QLab's Cue
Template defaults; it does not accept initial properties or send setters.
First-cue creation also supports an empty Cue List, Group, or Cue Cart through
the container-specific OSC route.

## Hard limits

- Use only QLab MCP tools; do not send raw OSC.
- Use an explicit workspace UUID and exactly one placement selector: an exact
  anchor cue UUID or an exact empty-container UUID.
- Require Edit Mode, an empty target (or inactive, structurally stable anchor
  inside a linear Cue List or Group), and `running/paused/auditioning = 0/0/0`.
- Record DMX Output before writing and verify it is unchanged afterward.
- Do not use GO, playback, Audition, Stop, Panic, `/live`, workspace save, or
  automatic cleanup.
- Send `/new` once at most. Never retry after a timeout.

## Create procedure

1. Call `qlab_check_connection(require_read_access=true)` and resolve exactly
   one workspace UUID.
2. Read the workspace overview, status, settings, and anchor details. Confirm
   Edit Mode, zero activity, anchor UUID, parent, and current sibling order.
   `isBroken`/`isWarning` are informational and do not block placement.
3. Run:

   ```text
   qlab_create_cue(
       workspace_id=<workspace UUID>,
       cue_type="wait",
       after_cue_id=<anchor UUID>,  # or parent_container_id=<empty UUID>
       dry_run=true,
   )
   ```

4. Require structured content, `status="dry_run"`, a fresh
   `confirm:createCue:v2` token, a container-specific placement plan,
   parent/order fingerprints, and `executed_operations=[]`.
5. Execute exactly one real Create with the exact token. Require
   `status="created"`, a valid `created_cue_id`, and
   `cleanup_required=false`. `created` certifies identity and placement; it does
   not certify readiness for GO. Broken or warning health is informational.
6. Perform fresh readback of the created UUID/`uniqueID`, type, parent, health,
   `isRunning`, `isPaused`, `isAuditioning`, and placement. Confirm either
   immediate-after anchor order, container index `0`, or Cart request `0,0`
   with QLab 5.5.10 readback coordinates `1,1`.

Stop immediately on timeout ambiguity, structural drift, missing structured
content, invalid identity/type, wrong parent/order, active-state verification,
or any unexpected extra cue. A broken/warning cue is still a valid Create
result. Never send setters or retry after an ambiguous `/new` result.

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

For ordered sequences use `qlab_create_cues` with `cue_types=[...]`. The first
item uses the initial placement selector; each later item uses the previous
verified UUID. Review one batch dry-run/token, expect one `/new` per item, and
stop on the first failure without rollback.

## Evidence boundary

Real Create uses one generic `/new` path for all enabled non-script, non-container
cue types. 031 runtime evidence certifies only blank `Wait`; it does not certify
every type's operational readiness. Empty-container placement is limited to the
  documented Cue List, Group, and Cart routes above. An experimental raw-OSC
  smoke in disposable QLab 5.5.10 confirmed Group index `0` and Cart request
  `0,0` with readback `1,1`; this is transport evidence, not a replacement for
  the MCP-tool checklist above.
“Blank” means Create does not provide an initial-properties input; Cue
Templates and QLab normalization may affect readback.
