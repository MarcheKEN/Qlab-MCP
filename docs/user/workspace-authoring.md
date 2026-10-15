# Workspace review and authoring

Use this workflow to review a workspace, prepare an organization change, or
configure a scene with the existing MCP tools. Review is read-only by default.
A request to review or suggest improvements does not authorize edits.

The project skill is [qlab-workspace-authoring](../../.agents/skills/qlab-workspace-authoring/SKILL.md).
It is available to agents that discover project skills; the Python package does
not install it globally. The [tool catalogue](tools.md) and current tool schemas
define the API; [Agent Workflows](agent-workflows.md) explains each writer.

## 1. Resolve the scope and collect evidence

1. Call `qlab_check_connection` and resolve one exact workspace UUID. With
   multiple candidates, use the user's named workspace or ask which to inspect.
   Selection, playhead and active cues are not write identities.
2. Agree the scope: exact cues, one list, or the workspace. Use
   `qlab_get_workspace_overview` for structure and
   `qlab_get_workspace_status` for derived health and infrastructure context.
3. Use `qlab_query_cues` to find relevant cues across families. For one list,
   use `primary_filter="cue_list_id"` and its UUID; this can include the list
   root as well as descendants. Do not count every returned row as a leaf cue.
4. Read the matching family details for each issue or proposed edit. Resolve
   target UUIDs in the same workspace and read their health and capabilities.
   Read the relevant workspace settings only for referenced patches, stages
   and routes. Do not scan all matrices, objects or FX parameters.
5. Track `partial`, errors, coverage, scan completeness and truncation on each
   response. Overview's tree preview and cue index have separate limits; a
   truncated preview can coexist with a complete index. Shallow health and
   editorial summaries are clues, not substitutes for authoritative detail.

Start with default limits. Follow the returned pagination of family inventories;
Query has no offset pagination, so narrow its filters or raise its documented
limits when necessary. Stop at the tool's maximum and identify omitted branches
or cues. Report sections that OSC does not expose, even if `partial=false`.
Do not claim a complete audit from a sample or an unreadable field.

### What to check

| Area | Evidence and next action |
| --- | --- |
| Media | File-capable cue, assigned-file presence, health and readable file diagnostics. A missing path in a safe profile is not proof of a missing file. Resolve a replacement only after the user authorizes local file access; reuse existing consent for the same task. Do not change or search media during a review alone. |
| Targets | Permanent cue/patch UUID, workspace membership, target type, health and mode. Names and cue numbers are labels. Do not turn temporary/current targets into permanent assignments. |
| Destinations | Referenced patch/stage/route details and connection evidence. Unknown connection status stays unknown; a configured route can be disconnected. Selecting an existing object does not create or repair hardware. |
| Fade | Target-compatible activation flags and destination values. A saved level/opacity without its flag does not prove that the parameter will fade. Read only the requested indexed elements. |
| Timing | Pre-wait, duration, post-wait, continue mode, loops and Group mode. A configured Timecode time does not prove its trigger is enabled. |
| Organization | Number collisions, structure, names and explicitly requested common properties. Empty names and duplicate labels may be intentional; propose changes rather than treating them as broken cues. |

Read `edit_capabilities` before proposing a setter. Distinguish available with
confirmation, blocked, pending validation and unavailable by OSC. A token or
documented endpoint cannot override a blocked capability. Leave LinearKey and
DropShadow creation blocked; existing-instance editing has separate coverage.

### Report format

- **Reviewed scope:** workspace/list/cue UUIDs, tools and limits, completeness.
- **Confirmed problems:** object UUID, observed field/value, evidence source,
  impact and next action. Separate inferred causes from observed failures.
- **Proposed improvements:** requested or optional changes, absolute before/after
  values, dependencies and editor. No writes during review.
- **Pending checks:** unreadable fields, omitted cues, unsupported properties,
  physical outputs and playback. A healthy saved cue is not proof of output.

For example, `route.connected=false` supports a disconnected-route finding;
`route.connected=null` supports a pending check. Keep cue warnings and settings
problems separate: counts may overlap and are not a unique warning total.
Fresh state takes precedence over historical reports, cue names or Memo notes.

## 2. Stage authorized changes

After the user authorizes the actual changes, use this dependency order:

1. **Files and destinations:** repair media and choose existing patches/stages.
2. **Targets and modes:** resolve exact objects and compatible cue/patch modes.
3. **Activation and dependent settings:** enable the requested Fade parameters.
4. **Final values and organization:** levels, geometry, times, numbers or moves.
5. **Fresh reads:** check affected cues, dependencies and the whole intended scene.

Separate calls when file, patch, target or mode changes can reset dependent
properties. Read the resulting state and obtain a new dry run before the next
phase. Group mode changes follow their dedicated child-snapshot restrictions.
Do not combine setters merely because their fields share an inspector tab.

For real writes, call `qlab_check_write_readiness`, then submit `dry_run=true`
to the matching editor. Review every baseline, dependency, planned operation,
warning and error; `executed_operations` must be empty. Split cue edits by
family, at most 50 per call; the Control editor supports its documented mixed
control types. Indexed edits retain their per-cue operation limit.

For the family editors, copy each cue result's
`planned_operations[].confirm_token` into that update's `confirm_gates`, keep
the request otherwise unchanged, and set `dry_run=false`. Signed tokens expire
after five minutes and are single-use. Other structural writers have their
own confirmation shape; do not apply this recipe to Create, Move or Delete.

Inspect execution results and read the edited properties freshly. Batches are
sequential and non-atomic: applied changes remain if a later operation fails.
Stop on failure or uncertainty; never resend an ambiguous setter or roll back
automatically. Reconcile fresh state before preparing any further authorized
change. Computer Use, if requested, only contrasts UI values; no GO, Preview,
Send, cue execution, external signals, `/live`, arbitrary AppleScript or compilation.

## 3. Three organization examples

All UUIDs below are fictitious. Replace them with freshly resolved identities.
These requests are previews, not instructions to modify a real show. In each
example: read both cues, check capabilities and dependencies, review the preview,
then use the confirmation procedure above only for an authorized real change.
After execution, reread both cues and compare every requested value.

### Renumber two cues into free numbers

Suppose two inactive Control-family cues currently have numbers `10` and `11`.
Inspect a fresh, complete workspace cue index and establish that `901` and `902`
are free, including outside the chosen list. The writer also validates number
availability. If the inventory is incomplete, do not claim the numbers are free.
Keep requested numbers distinct; swaps and cycles such as `10 -> 11 -> 10`
are outside this recipe. Changing a number does not move a cue or its UUID target.

Request tool: `qlab_edit_control_cues`

```json
{
  "workspace_id": "11111111-1111-4111-8111-111111111111",
  "updates": [
    {"cue_id": "22222222-2222-4222-8222-222222222222", "properties": {"number": "901"}},
    {"cue_id": "33333333-3333-4333-8333-333333333333", "properties": {"number": "902"}}
  ],
  "dry_run": true
}
```

Expected plan: two number changes, no executed operations. Verify numbers `901`
and `902` after execution; preserve UUIDs, parent and order. An occupied number
is a preflight rejection, not permission to overwrite or choose another number.

### Copy explicitly selected properties

Suppose the user asks to copy `colorName` and `preWait` from one Wait cue to
another. `qlab_get_control_cue_details` observes source values `blue` and `1.25`,
and destination values `none` and `0`. Both properties must be editable for the
destination. Only the destination belongs in the write request:

Request tool: `qlab_edit_control_cues`

```json
{
  "workspace_id": "11111111-1111-4111-8111-111111111111",
  "updates": [
    {"cue_id": "33333333-3333-4333-8333-333333333333", "properties": {"colorName": "blue", "preWait": 1.25}}
  ],
  "dry_run": true
}
```

Expected plan: destination color/pre-wait only; verify `blue` and `1.25` and
that the source stayed unchanged. Reread the source immediately before executing
if the request means its current values: destination tokens do not bind this
independently read source. If it changed, rebuild the request and dry run.
Do not copy whole Get payloads, UUIDs, parents, temporary overrides, read-only
fields or unrelated triggers. Cross-family copies use each destination editor
and its capabilities. The request means copied values, not a persistent link.

### Increase pre-wait by a relative amount

Suppose two inactive Wait cues have pre-waits `1.25` and `0.5` seconds. The user
requests `+0.5` seconds. Calculate absolute requests `1.75` and `1.0`; OSC is
not given a relative expression:

Request tool: `qlab_edit_control_cues`

```json
{
  "workspace_id": "11111111-1111-4111-8111-111111111111",
  "updates": [
    {"cue_id": "22222222-2222-4222-8222-222222222222", "properties": {"preWait": 1.75}},
    {"cue_id": "33333333-3333-4333-8333-333333333333", "properties": {"preWait": 1.0}}
  ],
  "dry_run": true
}
```

Expected plan: two pre-waits with those fresh baselines and absolute values;
verify both after execution. Recompute if a baseline changes before preview
or confirmation. Reject negative/non-finite/out-of-range results; do not clamp.
For finite level adjustments, preserve the field's units (for example dB),
inspect the exact indexed baseline and channel capacity, and use its family
operation. Do not perform arithmetic on `-inf`, null or unknown values.

## 4. Static timing and final review

- Pre-wait delays a cue's action after it is triggered.
- `continueMode=0` requires another trigger for the next cue; `1` auto-continues
  when the current cue begins its action, after pre-wait, using post-wait as
  the delay to triggering the next cue. `2` auto-follows after action completion.
- For an auto-follow Wait, duration and the displayed post-wait represent the
  linked wait, not two consecutive delays. With zero pre-wait and a 10-second
  Wait, the next cue is expected after 10 seconds, not 20.
- Calculate an intended timeline only when durations, ordering and continuation
  are known. A manual trigger boundary has no absolute time until its trigger
  is specified. Infinite loops, external triggers, GoTo, Devamp and Group modes
  may prevent a finite deterministic timeline; label it indeterminate.
- Check armed/skip-if-disarmed and current overrides without modifying them.
  Saved timing is a model, not a playback measurement. Include explicit Light
  RGB values for the instruments involved when the scene must not depend on
  prior color state; do not assume an intensity command resets color.

Finish with fresh identity, health, target/destination and affected-property
reads. Report applied, failed and pending changes separately, plus coverage
limits. Optional UI contrast confirms inspector agreement; it does not certify
musical synchronization, rendered FX or physical output.

Compare the actual inspector values and units, not raw accessibility slider
fractions. Preserve OSC baselines when UI labels are rounded or differ (for
example a displayed silence label); record the difference instead of silently
normalizing a value or claiming exact numeric agreement.

Timing references: imported [OSC dictionary](../references/qlab_osc_dictionary.md),
[Inspector](https://qlab.app/docs/v5/fundamentals/inspector/) and
[Wait cues](https://qlab.app/docs/v5/other-cues/wait-cues/).
