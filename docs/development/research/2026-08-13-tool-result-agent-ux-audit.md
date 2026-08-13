# QLab MCP 0.3.0 — Tool Result Agent UX Audit

Date: 2026-08-13 (Europe/Madrid)

This is a read-only contract and runtime audit. It evaluates whether an agent
can choose the next safe call from the MCP result and catalog alone. It does
not change code, execute QLab mutations, playback, GO, raw OSC, or AppleScript.

## Evidence boundary

- MCP contract: local FastMCP `0.3.0`, exactly 13 tools.
- Runtime workspace: `mcp_prueba.qlab5`, QLab `5.5.10`, one workspace.
- Readiness: `ready`; `/connect` scopes `view/edit/control`; Edit Mode.
- Runtime calls: connection, overview, status, settings, setting details,
  query, cue details, write readiness, and dry-runs/preflight failures.
- Existing runtime write reports were reused; no new setter, create, move, or
  delete was executed for this audit.

## Rubric

| Dimension | Question |
| --- | --- |
| Result | Is success or failure immediately clear? |
| Mutation | Is it clear whether QLab changed? |
| Target | Are affected UUIDs and placement/parent data available? |
| Verification | Is the postcondition explicit? |
| Safety | Is the token/gate/no-retry rule clear? |
| Error | Is the cause and severity actionable? |
| Continuation | Is the next safe call clear? |
| Independence | Can this be understood without source code? |

## Runtime observations

### Read-only tools

- `qlab_check_connection`: `ok=true`, `status=ready`, exact workspace UUID,
  QLab version, scopes, mode, and capabilities are clear. `KEEP`.
- `qlab_check_write_readiness`: blockers, readiness checks, dry-run default, and
  write capabilities are clear. On the observed ready path,
  `suggested_action=null` is acceptable; blocked paths already provide action
  text. `KEEP`.
- `qlab_get_workspace_overview`: `status=partial` and truncation reasons are
  clear, but the result is very large and `suggested_action=null`; an agent can
  infer the bounded follow-up from warnings, but should not need to infer it.
  `IMPROVE TEXT`.
- `qlab_get_workspace_status`: counts are clear (`running_count=0`,
  `paused_count=0`), unavailable sections explicitly say `not_exposed`, and
  warnings are visible. `KEEP`, with a minor text improvement for the next
  call when warnings/broken cues exist.
- `qlab_get_workspace_settings` and
  `qlab_get_workspace_setting_details`: compact, redacted, and independently
  actionable. Missing refs return `ok=false`, `status=error`, and a clear
  message, but no `error_code` or `suggested_action`. `IMPROVE TEXT`.
- `qlab_query_cues`: complete zero-match and bounded-match responses expose
  `matched_count`, `returned_count`, completeness, truncation, and exact UUIDs.
  `KEEP`.
- `qlab_get_cue_details`: successful editable details expose identity,
  structure, activity, health, and update capabilities. Unresolved refs return
  a nested `result` wrapper with `error_code=cue_ref_unresolved` but no
  `suggested_action`. `INCONSISTENT` with the other read tools; improve the
  wrapper/action text later.

### Write readiness and dry-run/preflight tools

- `qlab_create_cue`: dry-run clearly states no mutation, returns the token,
  planned operations, placement, and `message` telling the agent to review
  before disabling dry-run. `KEEP`.
- `qlab_create_cues`: dry-run clearly chains the sequence and returns
  `executed_operations=[]`, but `planned_count=6` for two requested cues counts
  verification operations as well as creations. The distinction is visible in
  `planned_operations`, but the aggregate is potentially misleading.
  `IMPROVE STRUCTURE`.
- `qlab_edit_cues`: dry-run exposes before/diff/planned operations and explicitly
  says no setters were sent. It lacks a batch-level `suggested_action` on the
  successful path, which is acceptable, but failure actions are richer than
  neighboring tools. `KEEP` with cross-tool consistency follow-up.
- `qlab_move_cues`: dry-run exposes source/destination parent, original/final
  neighbors, indexes, token, and non-atomic warning. `KEEP`.
- `qlab_delete_cues`: dry-run exposes exact target/type, neighbors, empty
  descendant list, root-preservation fields, token, and no-mutation warning.
  Direct non-empty Group, Cue List, Cue Cart, and missing UUID errors explain
  the safe alternative. `KEEP`.

## Cross-tool findings

| Finding | Classification | Scope |
| --- | --- | --- |
| Exact status/ok/dry-run semantics | `KEEP` | All tools |
| `suggested_action` absent on several actionable read errors | `IMPROVE TEXT` | Overview, settings, details |
| Nested `result` wrapper for cue details | `INCONSISTENT` | Cue details vs other reads |
| Batch `planned_count` can count verify steps | `IMPROVE STRUCTURE` | Sequential Create |
| Result items use generic dictionaries for Create/Move/Delete | `DEFER` | Contract migration too broad for 0.3.0 |
| Request XOR/range constraints mostly prose/runtime-only | `DEFER` | Schema redesign separate from this audit |
| Timeout/convergence fields | `KEEP` | Existing runtime evidence and tests |
| Generic `next_action` field | `DEFER` | Avoid redundant envelope until text gaps are measured |

## Matrix

| Tool | Representative cases | Disposition |
| --- | --- | --- |
| `qlab_check_connection` | ready | `KEEP` |
| `qlab_check_write_readiness` | ready | `KEEP` |
| `qlab_get_workspace_overview` | partial/truncated | `IMPROVE TEXT` |
| `qlab_get_workspace_status` | complete with warnings and not-exposed sections | `KEEP` |
| `qlab_get_workspace_settings` | summary | `KEEP` |
| `qlab_get_workspace_setting_details` | missing ref, success | `IMPROVE TEXT` |
| `qlab_query_cues` | complete match and complete zero-match | `KEEP` |
| `qlab_get_cue_details` | success and missing UUID | `INCONSISTENT` |
| `qlab_create_cue` | dry-run, missing token preflight | `KEEP` |
| `qlab_create_cues` | chained dry-run, missing token preflight | `IMPROVE STRUCTURE` |
| `qlab_edit_cues` | dry-run, missing token protection | `KEEP` |
| `qlab_move_cues` | dry-run, Cart warning | `KEEP` |
| `qlab_delete_cues` | dry-run, non-empty/unsupported/missing UUID rejection | `KEEP` |

## Conclusion

The current result contract is usable by an agent without reading source code
for the normal read, dry-run, and guarded-delete paths. The main gaps are
action text on some read failures, the nested cue-details result shape, and the
ambiguous aggregate meaning of sequential Create `planned_count`.

No output field or envelope is changed by this audit. The smallest follow-up is
to improve error text and document aggregate-count semantics; typed result
models, a universal `next_action`, and schema XOR redesign remain deferred.

```text
resultado MCP comprensible
≠
runtime validado
≠
show listo para GO
```
