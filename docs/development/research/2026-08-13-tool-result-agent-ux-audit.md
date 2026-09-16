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
understandable MCP result
≠
runtime validated
≠
show ready for GO
```

## Completion record

This section completes the audit specification without changing any result
model, tool implementation, test, QLab state, or remote repository.

### Current baseline

| Item | Evidence |
| --- | --- |
| Branch | codex/docs |
| HEAD | e59854c84f6de1b8950209e9523f27d05e1ac70b |
| origin/main cache | ccb2f45ed5e55e60c83aa2ba568b765726b3c86d |
| Divergence | 25 commits ahead, 0 behind |
| Package/server version | 0.3.0 |
| Local FastMCP contract | 13 tools; Client(mcp).list_tools() |
| Public names | exact inventory below |
| qlab_update_cues | absent from the public catalog |
| QLabReader.update_cues() | absent from src/ and tests/ |
| Production changes in this audit | none |
| QLab mutations in this audit | none |

Exact local public inventory:

~~~
qlab_check_connection
qlab_check_write_readiness
qlab_create_cue
qlab_create_cues
qlab_get_cue_details
qlab_get_workspace_overview
qlab_get_workspace_setting_details
qlab_get_workspace_settings
qlab_get_workspace_status
qlab_query_cues
qlab_edit_cues
qlab_move_cues
qlab_delete_cues
~~~

Local annotation matrix is current: eight read-only tools expose
readOnlyHint=true, Create exposes destructiveHint=false, and Edit, Move, and
Delete expose destructiveHint=true. The active app catalog did not expose
wire-level initialize or generic tools/list; those facts remain local
contract evidence, not live protocol evidence.

### Evidence accounting

The matrix below contains 26 representative result cases:

- LIVE_READ: current read-only MCP call;
- LIVE_DRY_RUN: current planning call with no mutating OSC;
- LIVE_PREFLIGHT_FAILURE: current validation or gate rejection;
- LIVE_RUNTIME_EVIDENCE_REUSED: prior bounded QLab 5.5.10 proof;
- LOCAL_CONTRACT_TEST: local FastMCP/model/test evidence;
- SOURCE_CHARACTERIZATION: source-only characterization of an unforced
  transport/error path.

No new real Create, Edit, Move, or Delete was performed for this audit. No GO,
playback, Audition, stop, Panic, raw OSC, AppleScript write, or /live write was
used.

### Rating legend

CLEAR means the result supports a safe interpretation. PARTIAL means an agent
can continue with bounded inference or an additional read. AMBIGUOUS means the
result can plausibly cause a wrong decision. NA means the dimension does not
apply. NO_SOURCE_NEEDED is the target; SOURCE_HELPFUL means source clarifies an
edge case but is not required; SOURCE_REQUIRED would be a release-significant
defect.

### Detailed result matrix

| Tool | Case | Evidence | Result | Mutation | Target | Verification | Error | Safety | Continuation | Source independence | Classification | Severity |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| qlab_check_connection | one workspace, ready | LIVE_READ | CLEAR | NA | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_check_connection | invalid workspace UUID | LIVE_PREFLIGHT_FAILURE | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_check_connection | QLab unavailable path | SOURCE_CHARACTERIZATION | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | SOURCE_HELPFUL | KEEP | — |
| qlab_check_write_readiness | ready, no blockers | LIVE_READ | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_check_write_readiness | invalid workspace / blocked preflight | LIVE_PREFLIGHT_FAILURE | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_workspace_overview | bounded tree, partial depth/health | LIVE_READ | CLEAR | NA | PARTIAL | NA | CLEAR | NA | PARTIAL | NO_SOURCE_NEEDED | IMPROVE TEXT | P2 |
| qlab_get_workspace_status | activity/warning/broken counts, unavailable sections | LIVE_READ | CLEAR | NA | PARTIAL | PARTIAL | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_workspace_settings | safe summary | LIVE_READ | CLEAR | NA | CLEAR | NA | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_workspace_settings | details batch with invalid request | LIVE_READ | CLEAR | NA | PARTIAL | NA | PARTIAL | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_workspace_setting_details | valid focused item | LIVE_READ | CLEAR | NA | CLEAR | NA | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_workspace_setting_details | missing ref | LIVE_READ | CLEAR | NA | CLEAR | NA | PARTIAL | NA | PARTIAL | NO_SOURCE_NEEDED | IMPROVE TEXT | P2 |
| qlab_query_cues | matching cue, exact UUID | LIVE_READ | CLEAR | NA | CLEAR | NA | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_query_cues | complete zero-match | LIVE_READ | CLEAR | NA | CLEAR | CLEAR | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_cue_details | editable known cue | LIVE_READ | CLEAR | NA | CLEAR | CLEAR | CLEAR | NA | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_get_cue_details | nonexistent cue ref | LIVE_READ | PARTIAL | CLEAR | CLEAR | NA | PARTIAL | NA | PARTIAL | SOURCE_HELPFUL | INCONSISTENT | P2 |
| qlab_create_cue | dry-run with exact anchor | LIVE_DRY_RUN | CLEAR | CLEAR | CLEAR | PARTIAL | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_create_cue | missing confirmation token | LIVE_PREFLIGHT_FAILURE | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_create_cues | two-item chained dry-run | LIVE_DRY_RUN | CLEAR | CLEAR | PARTIAL | PARTIAL | CLEAR | CLEAR | PARTIAL | NO_SOURCE_NEEDED | IMPROVE STRUCTURE | P2 |
| qlab_create_cues | missing batch token | LIVE_PREFLIGHT_FAILURE | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_edit_cues | dry-run with before/diff/plan | LIVE_DRY_RUN | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_edit_cues | timeout then matching readback | LIVE_RUNTIME_EVIDENCE_REUSED | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | SOURCE_HELPFUL | KEEP | — |
| qlab_move_cues | dry-run with parent/order fingerprints | LIVE_DRY_RUN | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_move_cues | converged same/cross-parent move | LIVE_RUNTIME_EVIDENCE_REUSED | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | SOURCE_HELPFUL | KEEP | — |
| qlab_delete_cues | leaf/empty Group dry-run | LIVE_DRY_RUN | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_delete_cues | non-empty Group, List/Cart, missing UUID | LIVE_PREFLIGHT_FAILURE | CLEAR | CLEAR | CLEAR | NA | CLEAR | CLEAR | CLEAR | NO_SOURCE_NEEDED | KEEP | — |
| qlab_delete_cues | root-preserving recursive/empty Group convergence | LIVE_RUNTIME_EVIDENCE_REUSED | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | CLEAR | SOURCE_HELPFUL | KEEP | — |

### Per-tool conclusions

Each tool has at least one representative case in the matrix. Priority write
tools have dry-run/preflight coverage and reused runtime convergence evidence.

| Tool | Strong point | Weak point | Best case | Most ambiguous case | Next action | Recommendation | 0.3.0 blocker |
| --- | --- | --- | --- | --- | --- | --- | --- |
| qlab_check_connection | Exact workspace, reachability, scopes, mode | Unreachable path not induced | One workspace ready | None observed | YES | KEEP | NO |
| qlab_check_write_readiness | Blockers/capabilities/gates explicit | Ready path has no action text, correctly | Ready with blockers=[] | Invalid workspace | YES | KEEP | NO |
| qlab_get_workspace_overview | IDs, limits, health coverage | Partial follow-up inferred from warnings | Bounded overview with warnings | Partial tree treated complete | WITH HELP | IMPROVE TEXT | NO |
| qlab_get_workspace_status | Activity, warnings, not_exposed sections | Derived status could be mistaken for native UI | Complete activity summary | Derived/native confusion | YES | KEEP | NO |
| qlab_get_workspace_settings | Compact redacted summary and independent details | Mixed-error action text varies | Safe summary then details | Mixed detail batch | YES | KEEP | NO |
| qlab_get_workspace_setting_details | Focused identity/details/choices | Missing ref lacks stable action code | Valid focused item | Invalid ref vs unavailable | WITH HELP | IMPROVE TEXT | NO |
| qlab_query_cues | Exact IDs, counts, completeness, zero-match success | Large profiles intentionally opt-in | Complete match/zero-match | Truncated scan | YES | KEEP | NO |
| qlab_get_cue_details | Editable identity and update capabilities | Missing ref nested result wrapper | Editable known cue | Nonexistent/mixed ref | WITH HELP | INCONSISTENT | NO |
| qlab_create_cue | Plan/token/placement/readback fields | Real success remains fixture-scoped | Dry-run then runtime success | None observed | YES | KEEP | NO |
| qlab_create_cues | Ordered items and stop/no-rollback contract | planned_count includes verification steps | Two-item dry-run | planned_count=6 for 2 cues | WITH HELP | IMPROVE STRUCTURE | NO |
| qlab_edit_cues | Before/diff/gates/execution/readback | Partial batches require item inspection | Confirmed timeout | Partial batch | YES | KEEP | NO |
| qlab_move_cues | Parent/order/convergence/rollback data | Generic item maps; Cart blocked | Linear converged move | Partial batch | YES for linear moves | KEEP | NO |
| qlab_delete_cues | Exact target, root preservation, convergence | Sequential partial recovery is item-driven | Root-preserving convergence | Timeout partial | YES with fresh readback | KEEP | NO |

### Status semantic map

This map describes top-level statuses. Nested values such as
timeout_pending_verification, manual_review_required, and
new_dry_run_and_fresh_token_required are item diagnostics, not top-level
operation states.

| Status | Tools | Mutation happened? | Verified? | Safe to retry? | Correct next action |
| --- | --- | ---: | ---: | ---: | --- |
| ready | connection/readiness | No | Readiness checked | Yes, read-only | Resolve exact workspace, then dry-run |
| ok / available | reads | No | Read/coverage result | Yes | Use IDs/details or continue |
| partial | bounded reads/mixed details | No | Bounded only | After inspecting limits | Follow warnings or query exact IDs |
| error | reads | No | No mutation | Fix input/state first | Read error_code/message; do not write |
| unavailable / not_exposed | status/settings sections | No | Not available | With supported route | Treat as limitation |
| workspace_not_found / workspace_ambiguous | connection/readiness/writes | No | No target | Fix workspace first | Call connection with one exact ID |
| workspace_unavailable / qlab_unreachable | connection/readiness/writes | No | No QLab proof | No write retry | Restore QLab/OSC, then reconnect |
| write_disabled / passcode_missing / edit_not_confirmed | readiness | No | Gate failed | After gate fix | Fresh readiness check |
| workspace_in_show_mode / show_mode_unknown | readiness | No | Write mode unproven | No | Confirm Edit Mode, fresh readiness |
| dry_run | Create, batch Create, Edit | No | Plan/readback only | Fresh dry-run | Review plan, then exact token |
| dry_run_preflight_failed | Edit item paths | No | No setter | After new dry-run | Fix input; discard old plan |
| planned | Move/Delete | No | Plan/readback only | Fresh plan required | Review token; execute once if authorized |
| preflight_failed | writes | No | No mutator | After fresh plan | Fix input; do not reuse token |
| created | Create | Yes | Identity/placement | No automatic retry | Use returned UUID; inspect/clean up |
| updated | Edit | Yes | Fresh after-read | No automatic retry | Continue from verified state |
| updated_with_confirmed_timeouts | Edit | Yes | Readback matched | No retry | Treat as changed; continue fresh |
| moved / moved_after_convergence | Move | Yes | Parent/order matched | No retry | Continue from final location |
| deleted / deleted_immediately / deleted_after_convergence | Delete | Yes | Absence/root readback | No retry | Confirm absence and preservation |
| verification_failed | Create/Edit/Move/Delete | Maybe | No | No | Fresh readback/manual inspection |
| verification_inconclusive / indeterminate | Edit/Move/Delete | Unknown | No | No | Stop; never retry blindly |
| partial_failed / failed | batch writes | Some may change | Per-item | No | Inspect all results and state |
| runtime_blocked | Move | No | Not attempted | Use supported route | Do not circumvent |
| rollback_required / rollback_failed | Move | Possibly | Recovery incomplete | No | Stop; new plan/token for rollback |

The key invariant is: ok=true is not proof that a real setter ran; planned or
dry_run is not a mutation; verification failure means mutation state may be
unknown.

### Cross-contract semantic findings

| Field/concept | Current meaning | Evidence | Finding |
| --- | --- | --- | --- |
| ok | Domain outcome, not transport reachability | LIVE_READ/LIVE_DRY_RUN | Keep; inspect status/items |
| status | Family-specific state machine | LOCAL_CONTRACT_TEST/LIVE_* | Keep per family; no fake universal enum |
| message | Human/agent-readable summary | LIVE_* | Useful; improve only where action unclear |
| error_code | Stable code where implemented | LOCAL_CONTRACT_TEST/LIVE_PREFLIGHT_FAILURE | Missing in some models; broad normalization deferred |
| errors | Batch/item-local diagnostics | LIVE_READ/LIVE_PREFLIGHT_FAILURE | Keep; correlation matters more than envelope sameness |
| warnings | Non-fatal limitation/safety notice | LIVE_READ/LIVE_DRY_RUN | Keep separate from errors |
| partial | Some result available, not full success | LIVE_READ/LOCAL_CONTRACT_TEST | Clear when paired with counts/results |
| suggested_action | Optional next step | LIVE_READ/LOCAL_CONTRACT_TEST | Missing on successful paths is harmless |
| planned_operations | Intended OSC/readback sequence | LIVE_DRY_RUN/LIVE_RUNTIME_EVIDENCE_REUSED | Clear with dry-run/status |
| executed_operations | Operations actually sent | LIVE_DRY_RUN/LIVE_PREFLIGHT_FAILURE/LIVE_RUNTIME_EVIDENCE_REUSED | Strong safety signal; dry-runs/blocks were empty |
| verification | Fresh postcondition evidence | LIVE_DRY_RUN/LIVE_RUNTIME_EVIDENCE_REUSED | Clear for Create/Edit aggregates |
| verification_status | Item convergence/indeterminate state | LOCAL_UNIT_TEST/LIVE_RUNTIME_EVIDENCE_REUSED | Useful; typed promotion can wait |
| confirm_token | Operation-specific fresh approval artifact | LIVE_DRY_RUN/LOCAL_CONTRACT_TEST | Correctly non-interchangeable |
| confirm_gates | Per-item Edit gates/tokens | LOCAL_CONTRACT_TEST/LIVE_DRY_RUN | Correctly distinct from discovery metadata |
| planned_count | Family-specific aggregate | LIVE_DRY_RUN/LOCAL_CONTRACT_TEST | Ambiguous in sequential Create |
| created/updated/moved/deleted_count | Completed item counts | LIVE_RUNTIME_EVIDENCE_REUSED/LOCAL_CONTRACT_TEST | Clear with requested count and results |
| cleanup_required | Possible mutation with incomplete proof | LOCAL_CONTRACT_TEST/LIVE_RUNTIME_EVIDENCE_REUSED | Important and clear |

Observed domain failures remained structured results with ok=false or item-level
failure data while the MCP call remained callable. Transport/framework call
completion is not domain-operation success. No ToolError, isError, or
structured-content redesign is made here.

Fresh readback remains the authoritative QLab write postcondition. A timeout
with matching readback is confirmed convergence and must not be retried.
Timeout or identity ambiguity without matching readback is indeterminate.

### Error recoverability decisions

| Result | Correct reaction | Discoverability |
| --- | --- | --- |
| Partial/truncated read | GET_FRESH_STATE or raise limit | Clear; action text could improve |
| Complete zero-match query | CHOOSE_DIFFERENT_TOOL or stop | Clear; not an error |
| Missing workspace/cue/setting | FIX_INPUT_AND_RETRY_READ | Clear enough |
| Missing/wrong token | GET_FRESH_TOKEN after fresh dry-run | Clear |
| Preflight failure before setter | FIX_INPUT_AND_RETRY_DRY_RUN | Clear |
| Planned/dry-run | Review; do not claim mutation | Clear |
| Verified mutation | Continue from returned identity/readback | Clear |
| Timeout with matching readback | DO_NOT_RETRY | Clear |
| Inconclusive timeout/readback | READBACK_FIRST / DO_NOT_RETRY | Clear |
| Partial batch | READBACK_FIRST; inspect every item | Clear enough |
| Runtime-blocked/unsupported route | CHOOSE_DIFFERENT_TOOL / UNSUPPORTED | Clear |

### Priorities

#### MUST FIX BEFORE 0.3.0

None found. No P0/P1 result-UX defect was observed. The current
token/plan/executed-operation/readback contract prevents blind mutation
retries in audited paths.

#### NICE TO FIX IN 0.3.0

- Add direct bounded follow-up text to overview partial results.
- Add targeted action text/error codes for missing settings refs.
- Document that sequential Create planned_count counts plan operations, while
  requested_count/created_count count cues.

These are P2 and should not delay a frozen release.

#### DEFER TO 0.3.1+

- Typed result-item models for Create/Move/Delete.
- Normalize cue-details nested result wrapper.
- Split Create cue-operation and verification-operation counters.
- Universal BaseResult/next_action envelope.
- Broad ToolError/isError redesign.
- Schema-level XOR/range redesign for placement/batch constraints.

These are public contract changes requiring a separate proposal and migration
plan.

### Release decision

Current result UX is sufficient for QLab MCP 0.3.0: all 13 tools have evidence,
priority writes have dry-run/preflight/reused runtime coverage, no P0/P1
finding remains, claims stay scoped to QLab 5.5.10 and named fixtures, and
production source/tests remained unchanged. The report recommends work only;
it does not implement any recommendation.

### Audit verification

git diff --check: PASS
git diff --name-status: audit document only
git diff -- src tests: empty
local FastMCP Client(mcp).list_tools(): 13 tools, version 0.3.0
rg update_cues in src/tests: no matches

No push, PR, merge, tag, branch-protection change, or other remote action was
performed.

## 0.3.0 polish resolution

The implementation pass reviewed every non-KEEP finding against current source
and tests:

| Finding | Disposition | Resolution |
| --- | --- | --- |
| Partial overview follow-up | IMPLEMENTED_0_3_0 / FIX_NOW_TEXT | Partial overview results now expose targeted guidance to inspect warnings, use qlab_query_cues, and raise bounded overview limits. |
| Missing setting ref | IMPLEMENTED_0_3_0 / FIX_NOW_TEXT | Detail results now return setting_ref_not_found plus the safe discovery/retry path. |
| Missing cue detail ref | IMPLEMENTED_0_3_0 / FIX_NOW_TEXT | Existing cue_ref_unresolved results now include qlab_query_cues to qlab_get_cue_details guidance. |
| Nested cue-details result wrapper | DEFERRED_0_3_1 / DEFER_0_3_1 | Wrapper was not flattened; current fields preserve cue_ref/error correlation and the audit found no P0/P1 decision risk. |
| Sequential Create planned_count | IMPLEMENTED_0_3_0 / FIX_NOW_DOCS | Existing field preserved. Pydantic description, result messages, user workflow, and contract test state that it counts generated plan operations, while requested_count/created_count count cues. |
| Generic result-item models | DEFERRED_0_3_1 / DEFER_0_3_1 | No broad typed-model migration. |
| Universal next_action/envelope/schema redesign | DEFERRED_0_3_1 / DEFER_0_3_1 | No new field, base model, status rename, or XOR redesign. |

Contract impact: public tool names remain exactly 13; version remains 0.3.0;
status values, confirmation tokens, dry-run behavior, executed_operations,
fresh readback, and QLab runtime behavior are unchanged. The only output
schema change is descriptive metadata for the existing Create batch
planned_count field; no result field was added or renamed.
