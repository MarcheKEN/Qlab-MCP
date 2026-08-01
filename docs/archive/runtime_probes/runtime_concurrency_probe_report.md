# Runtime Concurrency Probe Report

Date: 2026-06-17

Workspace under test: `<TEST_WORKSPACE_NAME>`

Workspace ID: `<TEST_WORKSPACE_UUID>`

QLab version: 5.5.10

## Executive Summary

The MCP/QLab pair handled normal read-only parallel workloads up to concurrency
5 on this 30-cue fixture. Concurrency 8 is the first observed failure point.

Recommended default for agents: concurrency 3 for normal work, concurrency 5
for bounded read batches, and no default use of concurrency 8. `qlab_query_cues`
passed at concurrency 8, but `qlab_check_connection` plus light
`qlab_get_workspace_overview` saturated at concurrency 8 with multiple
timeouts.

First failure level: concurrency 8 in the connection/overview block. QLab/MCP
recovered on its own after a 5-second pause: `qlab_check_connection`,
`qlab_query_cues`, and `qlab_get_cue_details` returned to near-baseline latency.

No playback, GO, stop, panic, audition, preview, raw OSC, or real write was
used. `qlab_update_cues` was tested only with `dry_run=true`; every dry-run
result reported `executed_operations=[]`.

## Exposed QLab MCP Tools

Tool discovery after reset exposed:

- `qlab_check_connection`
- `qlab_get_workspace_overview`
- `qlab_get_workspace_status`
- `qlab_get_workspace_settings`
- `qlab_get_workspace_setting_details`
- `qlab_query_cues`
- `qlab_get_cue_details`
- `qlab_check_write_readiness`
- `qlab_create_cue`
- `qlab_update_cues`

## Baseline

`qlab_check_connection` without an explicit workspace was ambiguous because two
QLab workspaces were open. All probe calls therefore used the explicit fixture
workspace ID.

| Metric | Initial | Final |
| --- | ---: | ---: |
| Total cue items scanned | 30 | 30 |
| Broken cues | 9 | 9 |
| Warnings | 0 | 0 |
| Running cues | 0 | 0 |
| Paused cues | 0 | 0 |
| Disarmed cues | 1 | 1 |
| Flagged cues | 2 | 2 |

Cue types observed:

- Cue List
- Audio
- Mic
- Camera
- Text
- MIDI File
- MIDI
- Timecode
- Devamp
- Target
- Video
- Group
- Fade
- Light
- Network
- Memo
- Script
- Pause
- Reset
- Start

Baseline serial latencies:

| Call | Result | Approx wall time | Summary |
| --- | --- | ---: | --- |
| `qlab_check_connection` | ok | 0.03-0.04s | Ready, readable, passcode accepted, scopes `view`, `edit`, `control`, Edit mode. |
| `qlab_get_workspace_overview` light | ok, partial tree | 0.03-0.04s | 26 inspected in bounded tree, 25 cues in 1 list, 2 flagged, 1 disarmed. |
| `qlab_get_workspace_overview` with cue index | ok, partial tree | 0.03-0.04s | 30 indexed cue items; cue index not truncated. |
| `qlab_get_workspace_status` | ok | 0.08s | 30 scanned, 9 broken, 2 flagged, 0 running, 0 paused. |
| `qlab_query_cues` type Audio | ok | 0.06s | 2 matched, complete scan. |
| `qlab_query_cues` `isBroken=true` | ok | 0.06s | 9 matched, complete scan. |
| `qlab_query_cues` `flagged=true` | ok | 0.03-0.06s | 2 matched, complete scan. |
| `qlab_get_cue_details` `basic_safe` | ok | 0.01-0.02s | Audio/Memo identity reads. |
| `qlab_get_cue_details` `health` | ok | 0.01-0.02s | Light cue reported broken, not running/paused. |
| `qlab_get_cue_details` `technical` | ok | 0.02s | Audio detail, includes technical media-path context. |
| `qlab_get_cue_details` `editable` | ok | 0.03-0.06s | Memo update capability discovery. |
| `qlab_get_workspace_settings(mode="summary")` | ok | 0.04-0.07s | 6 settings sections, 0 errors, 3 redactions. |
| `qlab_update_cues(dry_run=true)` | ok, dry run | 0.03s | Planned Memo `notes` change, `updated_count=0`, `executed_operations=[]`. |

Serial note: one early baseline sampling group was executed as a small parallel
set while collecting context. The individual tool results and wall times above
are still from successful tool responses; no error occurred.

## Concurrency Blocks

| Block | Call family | Concurrency | Result | Approx max wall time | Timeouts | Observations |
| --- | --- | ---: | --- | ---: | ---: | --- |
| 1 | Connection/overview light | 2 | ok | 0.03s | 0 | Light overview and indexed overview completed. |
| 1 | Connection/overview light | 3 | ok | 0.09s | 0 | Explicit c3 coverage; all calls completed. |
| 1 | Connection/overview light | 5 | ok | 0.10s | 0 | Explicit c5 coverage; all calls completed. |
| 1 | Connection/overview light | 8 | degraded/error | 90.21s | multiple | Some calls completed after long waits; one `qlab_check_connection` returned `workspace_read_timeout`, another returned `workspace_connect_failed`; overview mode checks also timed out. |
| 2 | `qlab_query_cues` | 2 | ok | 0.07s | 0 | Audio and flagged scans complete. |
| 2 | `qlab_query_cues` | 3 | ok | 0.09s | 0 | Audio, broken, flagged scans complete. |
| 2 | `qlab_query_cues` | 5 | ok | 0.09s | 0 | Added Group and cue-target scans; complete. |
| 2 | `qlab_query_cues` | 8 | ok | 0.18s | 0 | Passed, but latency increased most here. |
| 3 | `qlab_get_cue_details` | 2 | ok | 0.02s | 0 | Audio and Memo details completed. |
| 3 | `qlab_get_cue_details` | 3 | ok | 0.02s | 0 | Audio, Light health, and Memo editable details completed. |
| 3 | `qlab_get_cue_details` | 5 | ok | 0.06s | 0 | Single-cue and batch detail reads completed. |
| 4 | Mixed read block | 2 | ok | 0.05s | 0 | Overview + flagged/broken query completed after recovery. |
| 4 | Mixed read block | 5 | ok | 0.12s | 0 | Overview + status + settings + query + details. `qlab_get_workspace_status` was slowest. |
| 5 | `qlab_update_cues(dry_run=true)` | 2 | ok, dry run | 0.03s | 0 | `updated_count=0`, `executed_operations=[]`. |
| 5 | `qlab_update_cues(dry_run=true)` | 3 | ok, dry run | 0.03s | 0 | `updated_count=0`, `executed_operations=[]`. |
| Final | Connection/status | 2 | ok | 0.09s | 0 | Workspace still ready; running/paused remained 0. |

Concurrency levels 2, 3, 5, and 8 were covered across the main read families.
Dry-run update concurrency was capped at 3 by design.

After the c8 connection/overview failure, no further c8 escalation was run.

## Tool Table

| Tool | Serial OK | c2 OK | c3 OK | c5 OK | c8 OK/Error | Recommendation |
| --- | --- | --- | --- | --- | --- | --- |
| `qlab_check_connection` | yes | yes | yes | yes | error/degraded | Run before/after larger work; avoid piling many checks into c8. |
| `qlab_get_workspace_overview` | yes | yes | yes | yes | degraded | Keep bounded; safe through c5, but c8 caused mode-check timeouts. |
| `qlab_get_workspace_status` | yes | mixed yes | not tested | mixed yes | not tested | More expensive than detail reads; avoid high parallelism by default. |
| `qlab_get_workspace_settings` | yes | not tested | not tested | mixed yes | not tested | Summary mode is safe in mixed c5; do deeper details serially unless needed. |
| `qlab_query_cues` | yes | yes | yes | yes | yes | Passed c8 alone, but keep at c3-c5 because connection/overview failed at c8. |
| `qlab_get_cue_details` | yes | yes | yes | yes | not tested after c8 failure | Prefer batch `cue_ref` over many parallel single reads. |
| `qlab_update_cues` dry-run | yes | yes | yes | not tested | not tested | Keep dry-run planning at c1-c3; do not parallelize real writes. |

## Recovery

Timeouts occurred in the c8 connection/overview block.

Exact failed/degraded contexts:

- `qlab_check_connection(workspace_id="<TEST_WORKSPACE_UUID>", require_read_access=true)` returned `status="workspace_read_timeout"` in one c8 call. Timed-out reads included `/showMode`, `/cueLists/shallow`, and override probes.
- `qlab_check_connection(workspace_id="<TEST_WORKSPACE_UUID>", require_read_access=true)` returned `status="workspace_connect_failed"` in another c8 call. `/connect` timed out.
- `qlab_get_workspace_overview(max_depth=1, max_cues=100, include_cue_index=false, include_live_state=false)` returned partial overview data, but its `mode_check` timed out in some c8 calls.

Recovery after a 5-second pause:

- `qlab_check_connection` returned `ok=true`, `status="ready"` in about 0.045s.
- `qlab_query_cues` simple Audio query returned `ok=true` in about 0.069s.
- `qlab_get_cue_details` simple Memo detail returned `ok=true` in about 0.014s.

That indicates the MCP/QLab pair recovered without manual intervention.

If a future timeout occurs, recommended agent action:

1. Stop escalating concurrency.
2. Run `qlab_check_connection`.
3. Run one simple `qlab_query_cues`.
4. Run one simple `qlab_get_cue_details`.
5. Resume only if latency returns near baseline; otherwise serialize all calls.

## Agent Recommendations

- Do not serialize every read call by default. A small queue with concurrency 3
  is a better operating default.
- Allow concurrency 5 for bounded read-only batches with explicit
  `workspace_id`, `max_results`, and `max_cues_scanned`.
- Do not use concurrency 8 operationally. It produced connection/read timeouts
  in this fixture.
- Avoid parallelizing `qlab_get_workspace_status`, deep settings details, or
  sensitive/large profiles unless a load test justifies it.
- Avoid parallelizing repeated `qlab_check_connection` calls; use one check
  before/after a batch instead.
- Prefer `qlab_get_cue_details` batch mode over many parallel detail calls.
- Keep `qlab_update_cues` dry-run planning at c1-c3.
- Never parallelize real writes by default; real batch writes are not
  transactional once setters start.
- After any timeout, drop to serial mode until connection, query, and detail
  latencies return to baseline.

## Safety Confirmation

- No MCP code changed.
- No commit or PR was made.
- No GO/playback/stop/panic/audition/preview action was executed.
- No raw OSC was used.
- No real write was executed.
- `qlab_update_cues` was used only with `dry_run=true`.
- Dry-run update results reported `updated_count=0` and
  `executed_operations=[]`.
- Final workspace status confirmed running cues `0` and paused cues `0`.
