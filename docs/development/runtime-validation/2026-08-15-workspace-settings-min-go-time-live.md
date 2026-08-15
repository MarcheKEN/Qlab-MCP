# Workspace Settings `minGoTime` Runtime Validation

Date: 2026-08-15  
Result: bounded runtime validation completed; one positive activity-gate case was safely skipped; workspace restored.

## Environment

- QLab: 5.5.10
- Workspace: `mcp_prueba.qlab5`
- Workspace UUID: `95F0A03D-140E-4673-974A-E76748EBB023`
- MCP connection: reachable and readable
- `/connect` scopes: `view`, `edit`, `control`
- Workspace mode: Edit Mode (`show_mode=false`)
- Write readiness: ready; write enabled and passcode configured

## MCP Contract

The loaded MCP contract exposed exactly 14 public tools. `qlab_edit_general_settings` was present and `qlab_update_cues` was absent.

## Workspace

The workspace was selected by the exact UUID returned by `qlab_check_connection`. No display-name target, selected workspace, playhead, GO, playback, panic, AppleScript, raw OSC, or `/live` operation was used.

## Original Baseline

Fresh read-only settings read returned:

- `general.minGoTime`: `0`
- `general.selectionIsPlayhead`: `true`

The sections through `## Limitations` below preserve the initial stale-process attempt for audit history. The post-fix runtime evidence that supersedes its blocked/skipped outcomes starts at `## Resumed Campaign Evidence`.

## Dry-run Evidence

The first reviewed dry-run requested `minGoTime=0.5` seconds. It returned `dry_run_preflight_failed` before token issuance or mutation:

- error: `workspace_id must exactly match one QLab workspace uniqueID; display names are not accepted.`
- planned operations: one `set_workspace_setting` entry
- executed operations: zero
- confirmation token: absent
- setter requests: zero

The failure was reproducible on a second dry-run after the local fix because the already-running MCP server process had not reloaded the updated source.

Root cause found locally: Pydantic normalizes the UUID field to lowercase, while the settings resolver compared it case-sensitively with QLab's case-preserved uppercase `uniqueID`. The minimal local fix compares UUID identity case-insensitively and preserves QLab's returned casing for the qualified OSC address, result, and token binding. A lifecycle regression test covers this case.

## Real Write Evidence

Not run. The required dry-run gate did not produce a token, so no real setter was authorized.

## Independent Readback

A fresh independent settings read after both failed dry-runs returned `general.minGoTime=0`. This confirms that the validation attempts did not mutate QLab.

## Replay Test

Skipped: no confirmation token was issued.

## Invalid Input Tests

Skipped live: the core dry-run gate failed before an input campaign could be meaningful. Automated contract tests cover negative, boolean, string, null, non-finite, and non-representable numeric values.

## TOCTOU / Stale Baseline Test

Skipped live: no token was issued and no real write was reached. Automated tests cover stale baseline, changed request, changed workspace, expiry, and replay.

## Activity Gate

Read-only status reported `running_count=0` and `paused_count=0`. The status read was partial and also reported pre-existing sampled broken cues; no cue was started, stopped, or edited. A safe MCP-only method to create running/paused state without meaningful playback was not available, so the positive activity-blocking path remains automated-only.

## Timeout / Convergence

Skipped live. No unsafe network failure was manufactured. Automated tests cover one setter attempt, timeout confirmation by fresh readback, mismatch, unavailable readback, and `retry_unsafe` behavior.

## Restoration

No restoration write was needed: the original value remained `0` throughout, confirmed by fresh readback. No temporary cue or workspace state was created.

## Final Workspace State

- `general.minGoTime`: `0` (original value)
- running cues: `0` in the partial status scan
- paused cues: `0` in the partial status scan
- no GO/playback/panic operation was called
- workspace remained in Edit Mode
- status retained the pre-existing warning that the sampled workspace contains broken cues; this was not changed by the campaign

## Passed Cases

- QLab 5.5.10 connection and exact workspace identity read
- read access and write-readiness preflight
- 14-tool MCP inventory, new tool present, legacy alias absent
- fresh baseline read
- dry-run blocked before token/setter
- independent readback unchanged
- local focused settings tests: 44 passed
- local feature-focused suite: 2,311 passed
- local full suite: 2,642 passed, 41 subtests

## Skipped Cases

- real setter and fresh write readback
- replay protection
- live invalid-input transport proof
- live stale-baseline/TOCTOU proof
- live timeout/convergence proof
- activity-positive blocking proof

## Failed Cases

- Initial live dry-run exposed the UUID case-mismatch defect described above. It was fixed locally with a focused regression test. The loaded MCP process could not be restarted in this session, so the corrected implementation has not yet been runtime-proven.

## Limitations

This report is not runtime validation of a successful settings write. It is bounded preflight evidence plus a reproducible defect report. The current tool process must be restarted from the corrected branch before the dry-run, one-setter, readback, replay, TOCTOU, and restoration campaign can continue.

Continuation note (2026-08-15): a subsequent audit reproduced the same preflight failure on the supposedly restarted server. The two stale local `qlab_mcp.server` processes were terminated to request a clean reload; the MCP transport then closed before a replacement became available. The last independent QLab read remained `general.minGoTime=0`, and no setter or other QLab mutation was issued.

Resume note: an external restart was reported, but this session still returns `Transport closed` for `qlab_check_connection`; no live contract, workspace, or activity assertion was accepted from that claim, and no QLab operation was attempted.

## Conclusion

Implementation evidence and automated tests are green. The corrected UUID behavior was runtime-proven after the external restart: the canonical uppercase QLab UUID was accepted and preserved in the qualified address, result, and token binding. A single `minGoTime` setter changed `0` to `0.5`; QLab's reply timed out, but a fresh matching readback confirmed the update without a setter retry. A fresh token then restored `minGoTime` to `0`, again with matching readback.

## Resumed Campaign Evidence (2026-08-15)

The restarted MCP contract again exposed exactly 14 public tools, including `qlab_edit_general_settings` and excluding `qlab_update_cues`. QLab 5.5.10 was reachable at the exact workspace UUID above, write readiness was ready, the initial setting was `0`, and the sampled activity state was `0` running / `0` paused.

The corrected dry-run for `minGoTime=0.5` returned one planned setter, zero executed operations, a fresh settings token, and the exact address:

`/workspace/95F0A03D-140E-4673-974A-E76748EBB023/settings/general/minGoTime`

An independent settings read remained `0`. The real write attempted exactly one setter. QLab's reply timed out, so the operation was marked timeout-pending-verification; a fresh no-argument read returned `0.5`, producing `updated_with_confirmed_timeouts` with no mutating retry. An independent settings read also returned `0.5`.

Replay protection was observed twice: reuse after a changed baseline failed closed with a token-binding mismatch, and reuse after a fresh same-value write returned `QLAB_SETTINGS_CONFIRM_TOKEN_REPLAY` with zero executed operations.

## Strict Input Defect and Corrective Action

Live public-tool checks showed that string `"0.6"` and boolean `true` were coerced before the handler (`0.6` and `1`) and incorrectly reached successful dry-run planning. Negative input was rejected by the public schema. The campaign stopped at this genuine contract defect; no invalid-input setter was issued.

The minimum fix changed the public `value` annotation to `StrictInt | StrictFloat` and added a regression test proving that coercible strings and booleans fail before the settings handler. Focused settings/server/write/token tests pass (`2,313 passed`); the full suite passes (`2,644 passed, 41 subtests`). The MCP process must be restarted from this corrected worktree before resuming live validation.

After the required restart from the corrected worktree, the public tool rejected string `"0.6"`, boolean `true`, null, and negative `-0.1` at the MCP validation boundary. None issued a token or setter. This closes the previously observed runtime input defect.

## Restoration and Current State

A fresh dry-run/token/write/readback cycle restored the original `general.minGoTime=0`; the restore also attempted exactly one setter and was confirmed by fresh readback after a timeout. An independent settings read returned `0`. Final sampled activity remained `0` running / `0` paused. No cues, GO, playback, panic, AppleScript, raw OSC, `/live`, or unrelated QLab operation was used.

TOCTOU is runtime-proven: a fresh token with baseline `0` was invalidated after a separate one-setter write changed the baseline to `0.5`, with zero executed operations on stale-token use. Replay is runtime-proven with `QLAB_SETTINGS_CONFIRM_TOKEN_REPLAY` and zero executed operations. Timeout/convergence has live evidence from multiple writes, each with one setter and matching fresh readback; no synthetic timeout was manufactured. A positive activity-blocking case remains safely skipped because the MCP surface exposes no non-show-impacting way to create running/paused cues. `implementation exists` is not yet `show ready for GO`, and neither implies complete show readiness.

Continuation note (2026-08-15): after one stale-process probe, a later verified restart from the corrected worktree rejected string and boolean inputs before handler execution. The campaign then completed the fresh dry-run, one-setter/readback, replay, strict invalid-input, stale-baseline, and restoration checks. Final independent read remained `general.minGoTime=0`; final sampled activity remained `0` running / `0` paused.

## Second Runtime Confidence Pass (2026-08-16)

The MCP process was freshly verified before mutation: exactly 14 public tools were loaded, `qlab_edit_general_settings` was present, `qlab_update_cues` was absent, QLab 5.5.10 resolved the exact canonical UUID, write readiness was ready, `general.minGoTime` was `0`, and sampled activity was `0` running / `0` paused. The original value captured for this pass was `0`.

### Happy path and numeric matrix

All real rows used a fresh read, dry-run, fresh token, exactly one setter, and fresh readback. Each non-zero row was restored to `0` with a new dry-run/token cycle before the next row.

| case | baseline | requested | dry-run | setter count | readback | expected result | actual result | restored | notes |
|---|---:|---:|---|---:|---:|---|---|---|---|
| happy path | 0 | 0.25 | `dry_run`, 1 planned, 0 executed | 1 | 0.25 | confirmed update | `updated_with_confirmed_timeouts` | yes | independent read 0.25 |
| numeric | 0 | 0 | `dry_run` | 1 | 0 | accepted | `updated_with_confirmed_timeouts` | yes | same-value setter allowed |
| numeric | 0 | 0.001 | `dry_run` | 1 | 0.0010000000474974513 | accepted with float32 tolerance | `updated_with_confirmed_timeouts` | yes | independent read matched |
| numeric | 0 | 0.1 | `dry_run` | 1 | 0.10000000149011612 | accepted with float32 tolerance | `updated_with_confirmed_timeouts` | yes | independent read matched |
| numeric | 0 | 1 | `dry_run` | 1 | 1 | accepted | `updated_with_confirmed_timeouts` | yes | |
| numeric | 0 | 1.0 | `dry_run` | 1 | 1 | accepted | `updated_with_confirmed_timeouts` | yes | wire representation is numeric |
| numeric | 0 | 1.25 | `dry_run` | 1 | 1.25 | accepted | `updated_with_confirmed_timeouts` | yes | |
| numeric | 0 | 10 | `dry_run` | 1 | 10 | accepted | `updated_with_confirmed_timeouts` | yes | no undocumented maximum inferred |
| sequential 1 | 0 | 0.1 | `dry_run` | 1 | 0.10000000149011612 | update | `updated_with_confirmed_timeouts` | intermediate | fresh baseline/readback |
| sequential 2 | 0.10000000149011612 | 0.2 | `dry_run` | 1 | 0.20000000298023224 | update | `updated_with_confirmed_timeouts` | intermediate | fresh baseline/readback |
| sequential 3 | 0.20000000298023224 | 0.3 | `dry_run` | 1 | 0.30000001192092896 | update | `updated_with_confirmed_timeouts` | intermediate | fresh baseline/readback |
| sequential 4 | 0.30000001192092896 | 0 | `dry_run` | 1 | 0 | update | `updated_with_confirmed_timeouts` | yes | final sequence value restored |

### Token, TOCTOU, replay, and no-op cases

- Requested-value mismatch: a token for `0 → 0.1` used with `0.2` returned `QLAB_SETTINGS_CONFIRM_TOKEN_INVALID`; zero setters and no state change.
- Baseline mismatch: a token captured at baseline `0` was used after a separate one-setter write changed the value to `0.2`; it returned `QLAB_SETTINGS_CONFIRM_TOKEN_INVALID` with a baseline-binding error and zero setters.
- Malformed, truncated, and random tokens each returned `QLAB_SETTINGS_CONFIRM_TOKEN_INVALID`; zero setters.
- TOCTOU stress passed twice: stale tokens for `0 → 0.3` and `0 → 0.2` were invalidated after independent writes to `0.4` and `0.1`, respectively. Both stale attempts executed zero setters; each cycle was restored to `0`.
- Timeout replay passed: a same-value `0.1 → 0.1` write returned `updated_with_confirmed_timeouts`; reuse of that consumed token returned `QLAB_SETTINGS_CONFIRM_TOKEN_REPLAY` with zero setters.
- Same-value behavior is characterized: dry-run plans one setter and issues a token; real execution performs one setter and verifies the unchanged value.

### Strict inputs, UUID, and readiness

- Strings `"0.6"` and `"1"`, booleans `true` and `false`, `null`, `-0.1`, and `-1` were rejected before planning. Each produced no token, zero setters, and left `minGoTime=0`.
- Lowercase and uppercase UUID inputs both resolved to QLab's canonical uppercase UUID. Results and the planned address used `/workspace/95F0A03D-140E-4673-974A-E76748EBB023/settings/general/minGoTime` consistently.
- Wrong and nonexistent UUIDs returned `dry_run_preflight_failed` with no token or setter. Malformed UUID input was rejected by the public schema. A real call without a token returned `QLAB_SETTINGS_CONFIRM_TOKEN_INVALID` with zero setters. A dry-run without a token worked normally.

### Timeout, activity, and final restoration

QLab naturally timed out the setter reply throughout this pass. Every real result contained exactly one attempted setter, no mutating retry, and a matching fresh readback, producing `updated_with_confirmed_timeouts`. No packet loss or timeout was manufactured. A positive activity gate was skipped because no safe MCP-only method exists to create running/paused state without GO/playback/show impact; automated coverage remains authoritative for that branch.

The mandatory final cycle began with a fresh read of `0`, performed a fresh dry-run with one planned and zero executed operations, used a new token, attempted exactly one setter, and confirmed `0` by fresh readback and independent settings read. Final sampled activity was `0` running / `0` paused. Existing sampled broken-cue warnings were unchanged.

### Second-pass outcome

Passed runtime: happy path, all requested valid numeric values, float32 readback tolerance, strict invalid inputs, requested-value binding, baseline binding, replay, TOCTOU stress, same-value behavior, sequential writes, UUID canonicalization, readiness failures, timeout convergence, and final restoration.

Passed automated only: token expiry, alternate-workspace binding, and positive activity blocking remain covered by the automated suite rather than this disposable runtime pass.

Skipped: non-finite values were not forced through the MCP serializer; no alternate disposable workspace was available; no unrelated-operation token was manufactured; no synthetic timeout or 300-second expiry wait was performed; positive activity injection was unsafe.

Failed: none in the second pass.
