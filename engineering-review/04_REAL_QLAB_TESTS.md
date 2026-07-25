# 04 — Real QLab Tests

## Safety envelope

QLab 5.5.10 was open on `mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`) in Edit Mode. `/connect` confirmed view/edit/control. All output overrides were enabled, so the review did not play cues or exercise Audio, Video, Light, MIDI, Network, timecode or show-control output.

The dedicated inactive fixture chosen for a reversible metadata write was Memo cue `41.6`, UUID `33B90938-AF3B-4D82-8AB1-3179D34B562D`, name `MCP_MOVE_RUNTIME_A`. Baseline and final `notes` were both `""`; it was healthy, armed, not loaded, not running and not paused.

## Read-only interactions

| Interaction | Input / target | Observed result |
| --- | --- | --- |
| Connection/readiness | Explicit workspace UUID | QLab 5.5.10; UDP 53000/53001; passcode accepted; view/edit/control; Edit Mode; 11 lists; write ready, dry-run default true |
| Overview | Bounded tree plus full compact index | 185 cue/list items across 11 cue lists; selected and playhead both Group cue 50; no running cues |
| Workspace status | Summary, 500 cue scan | 185 scanned; 56 broken, one warning, eight flagged, zero running/paused; three configured timecode cues |
| Cue lookup by number | `41.6`, technical | Returned fixture UUID/type/properties |
| Cue lookup by UUID | `33B...562D`, technical | Same identity and values as number lookup |
| Selected/playhead | Live-state overview | Both resolved to Group cue 50; read only |
| Generic/type properties | Memo technical detail | Identity, waits, duration, state, targets, notes and health returned; no unexpected change |
| Cue query | Memo/name/filter probes | Seven healthy Memo fixtures found in the representative query |
| Settings summary | all sections | 1 audio output, 1 input, 1 audio map; 4 video routes, 8 stages, 3 inputs; 1 network patch; 0 MIDI patches |
| Settings details | output patch, audio map, Stage 1, disconnected route | All four independent requests succeeded; route `22B1W` reported disconnected |
| Final cue read | fixture UUID, technical | `notes=""`, inactive and healthy |
| Final status | summary | Still zero running and paused cues; counts unchanged at review scale |

The public MCP does not expose raw OSC or debug packet capture. Exact underlying address families are documented from code, but raw datagrams were not observed and are not claimed.

## Repetition and timing

Timings are approximate wall-clock observations on localhost, not a general benchmark.

| Scenario | Result |
| --- | --- |
| Five simultaneous identical fixture detail reads | 27 ms total; all `ok`, same UUID |
| Ten rapid sequential identical reads | 123 ms total; each 10–20 ms |
| Five simultaneous unrelated high-level reads | 5,343 ms total; one detail 20 ms, others 5,081–5,343 ms |
| Same five unrelated reads sequentially | 500 ms total; 23–201 ms each |

Identical calls benefited from cache/single-flight. Unrelated concurrency was 10.7× slower than sequential execution because their many OSC exchanges interleaved behind the endpoint-wide lock. No stale pending-request registry exists, but a separate loopback probe proved late identical UDP replies can be misattributed; see `05_RUNTIME_BEHAVIOR.md`.

## Safe invalid-input/error probes

| Probe | Result | Assessment |
| --- | --- | --- |
| Unknown workspace | `workspace_not_found`, 15 ms | Accurate and actionable |
| Unknown cue number | `cue_ref_unresolved`, 77 ms | Accurate |
| Invalid cue ID `bad/id` | `validation_failed`, 12 ms | Accurate |
| Memo property `opacity` dry-run | Preflight failed, no operation executed, 4,252 ms | Correct type/property rejection; too much work before local failure |
| Invalid `continueMode=99` | Failed, 2,783 ms | Correct, but schema could reject earlier |
| `preWait=-1` | Failed, 2,116 ms | Correct range enforcement; slow |
| Empty profile | Silently defaulted to `common`; dry-run plan succeeded, 6,033 ms | Inconsistent with “empty invalid” expectation; document or reject explicitly |
| Missing `primary_value` | FastMCP/Pydantic `missing_argument` error | Correct but different error envelope from domain errors |

No invalid probe emitted a setter.

## Initial controlled-write attempt — approval-blocked

The required sequence was prepared as follows:

| Field | Planned/observed value |
| --- | --- |
| MCP tool | `qlab_edit_cues` |
| Input | one `common.notes` change on the dedicated Memo; `dry_run=true` first |
| Workspace | exact UUID above |
| Target cue | exact fixture UUID above |
| Original value | `notes=""` |
| OSC message | Not observed: call was blocked before MCP execution |
| Requested value | Unique temporary review marker |
| Immediate result | Automatic approval reviewer refused the mutating-tool call because the approval/usage allowance is unavailable until 2026-07-25 |
| QLab readback | Fresh final read still `notes=""` |
| Setter messages observed | 0 |
| Readback attempts after setter | 0; no setter occurred |
| Restoration | Not required because QLab was never changed |
| Final QLab value | `notes=""` |
| Final result | **Historical attempt blocked before MCP; superseded by the successful validation below** |

The reviewer blocked even `dry_run=true` because the tool is classified as mutating at the approval boundary. The study did not bypass that control with raw OSC, terminal traffic or a different API. Prior repository tests and historical runtime reports support the safety design, but they are not a substitute for the requested current reversible proof.

## Final workspace safety result

- No cue played or auditioned.
- No output-producing cue or override was changed.
- Only the explicitly listed metadata setters reached QLab; no output-producing cue setter was used.
- Every changed value was restored and independently read back.
- Fresh cue read confirmed the candidate fixture still has its recorded baseline value.
- Fresh workspace status confirmed no cues running or paused.

Remaining real-runtime unknowns: exact saved-versus-live read-key separation for `/live`; custom reply port; idle reconnection; multiple open workspaces; QLab restart/closure; raw packet-level setter counts (the MCP exposes executed operations, not packet capture).

## Continuation availability check — 2026-07-21

A fresh read-only check was attempted before any write call. `qlab_check_connection` returned `status="qlab_unreachable"` after timing out on `/workspaces`; readiness returned the same blocker; the fixture detail read returned `workspace_unavailable`. A local `lsof` probe found no listener on UDP 53000 or 53001, and no Codex app terminal session was attached.

This is a changed external-state condition, not evidence that the previous baseline values changed. Because QLab is not listening, the write proof cannot safely proceed. No mutating tool was submitted in this continuation, and no QLab value was changed.

## Successful controlled validation — current QLab session

QLab subsequently became reachable. Fresh preflight resolved the exact workspace, confirmed QLab 5.5.10, Edit Mode, `view/edit/control`, write readiness, and zero running/paused cues. The dedicated Memo fixture remained healthy and inactive with the following baseline values.

| Property | Mode | Baseline | Requested | Executed OSC address and args | Real result | Independent readback | Rollback and final readback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `notes` | saved | `""` | `MCP_REVIEW_TEMP_20260721` | `/workspace/95F0A03D-140E-4673-974A-E76748EBB023/cue_id/33B90938-AF3B-4D82-8AB1-3179D34B562D/notes` + marker | 1 setter; `updated_with_confirmed_timeouts`; fresh after-read confirmed marker | marker | rollback 1 setter to `""`; final `""` |
| `flagged` | saved | `false` | `true` | same UUID path `/flagged` + `true` | 1 setter; `updated_with_confirmed_timeouts` | `true` | rollback 1 setter to `false`; final `false` |
| `colorName` | saved | `none` | `blue` | same UUID path `/colorName` + `blue` | 1 setter; `updated_with_confirmed_timeouts` | `blue` | rollback 1 setter to `none`; final `none` |
| `preWait` | saved | `0` | `0.25` | same UUID path `/preWait` + `0.25` | 1 setter; `updated_with_confirmed_timeouts` | `0.25` | rollback 1 setter to `0`; final `0` |
| `secondColorName` | live | `none` | `blue` | same UUID path `/secondColorName/live` + `blue` | 1 setter; `updated_with_confirmed_timeouts` | exhaustive read exposed `properties.secondColorName=blue`; no separate `/live` key | rollback 1 setter to `none`; final exhaustive `properties.secondColorName=none` |

Each real setter returned a QLab reply timeout, but the tool's fresh after-read confirmed the requested value. No setter was retried; each real phase reported exactly one `executed_operations` setter. The rollback phases used their own dry-run first and also reported one setter with fresh confirmation. The MCP does not expose raw packet capture, so “one setter” is the executed-operation count, not an independent UDP sniff count.

This validates a generic saved property, boolean, enum-like color, numeric value, and one `/live` address on an inactive Memo without playback or output. The `/live` route is real-write verified; saved-versus-live read-key separation remains a documented limitation because exhaustive read returned only `properties.secondColorName`.
