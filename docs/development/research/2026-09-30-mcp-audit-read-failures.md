# Investigation of MCP audit failures

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-09-30. Scope: investigation; no code changes or QLab writes. Code, tests, the local QLab 5.5.10 OSC dictionary and audit observations were compared. Text and the raw LTC value were queried again through MCP.

## 1. Control point coordinates — confirmed

`settings/workspace.py::_osc_geometry_values` also requires int32 integers on reads. The audit received valid decimal coordinates for a redacted-show-workspace point, for example `[948.9149903942621, 217.85067072331196]`. The function rejects that value. `get_video_region` and preflight in `settings/object_writes.py` share this validation: both reading and editing with that previous state are blocked.

The dictionary requires integers when **writing** the point, but does not impose that restriction on the read response. The test `test_invalid_point_blocks_get_and_edit` even considers `[1.0, 2]` invalid, reinforcing the incorrect restriction.

Proposed fix: separate read validation from setter input validation; preserve finite numeric coordinates without rounding, reject booleans and malformed values, and retain documented integer requirements and bounds for writes. Also review comparison and the token baseline. Minimum test: read a decimal point and prepare an integer write against that state, without sending a setter during dry run.

## 2. Zero LTC channel — confirmed

The MCP `exhaustive` read of cue `FE1D267E-B24D-5511-AC94-AC4E4BEEAC2B` in workspace `8E86FE91-668B-560C-B738-4D581B5A7498` returns `ltcChannel=0`. `cues/remaining.py::LTCPatch` requires `ge=1`, discards the value and produces a partial result. The rejection was reproduced by instantiating the model locally.

MTC/LTC separation already works and has a specific test. The issue is not querying LTC on an MTC cue. The observed cue also reports `isBroken=true`; accepting zero on read does not mean considering its playback configuration valid.

Proposed fix: preserve zero in the read model as an observed state; retain usable-channel validation in any write. Minimum test: an LTC cue with channel zero preserves the value and its broken state without a deserialization error.

## 3. Optional Text attributes — failure reproduced, QLab cause pending

The fresh query of cue `3F11DC3A-7BC7-5A58-917F-78A6108E07FD` returns text, typography and runs, but QLab responds `error` to eight individual queries: backgroundColor, shadowColor, shadowBlurRadius, shadowOffset, strikethroughColor, underlineColor, strikethroughStyle and underlineStyle.

`cues/family.py` requests all those fields even when the runs do not contain them. The paths are documented in the dictionary. Their correspondence with absent attributes suggests QLab does not return a scalar value when they are not configured; this does not yet prove that cause. Comparison with an existing cue that has those attributes is still needed, without modifying it.

Proposed fix: investigate the `text/format` aggregate as the source of attributes per run, preserving the difference between an absent attribute and a failed query. Do not invent defaults or indiscriminately hide OSC error responses. Cover text with multiple formats and actual transport errors before changing result classification.

## 4. Settings setter timeouts — protocol gaps confirmed

The writers `settings/write_operations.py` and `settings/object_writes.py` wait for a setter response without enabling `/alwaysReply`. The cue writer does enable it. The dictionary states that QLab does not acknowledge messages that do not generate a response by default, and that `/alwaysReply` affects the sending client.

Also, `osc/client.py::_allows_empty_ack` allows acknowledgements without `data` for `/alwaysReply` and certain structural actions, but not for Settings setters. Enabling responses without adjusting that contract may replace the timeout with `QLab successful reply JSON missing data`.

The audit observed setters applied and confirmed by fresh readback after timeout. This is consistent with the identified gaps, although this investigation has not tested whether all endpoints acknowledge with `/alwaysReply` enabled. No setters were sent to check this.

Proposed fix: reuse the existing protocol to enable responses on the same client and accept acknowledgements without `data` only for known setters with arguments. Queries must continue requiring data. Retain a single send and fresh verification, without automatic retry. Test with simulated transport, then with a reversible operation in a disposable copy.

## Evidence and limitations

- Dictionary: `docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`, `/alwaysReply`, control point, `/ltcChannel` and `/text/format` sections.
- Local reproduction without changes: decimal coordinate rejection, zero LTC rejection, and lack of empty-ack support for a Settings setter.
- Fresh MCP reads: partial Text with the eight paths listed above and raw LTC channel zero.
- Write results and redacted-show-workspace coordinates come from the earlier audit; writes were not repeated in this investigation.
- The full suite was not run: no code was changed. The existing tests reviewed explain why the two read restrictions were not detected.

## Subsequent implementation (2026-09-30)

All four fixes were implemented with regressions. Fresh Text and Timecode reads
through `Client(mcp)` in redacted-test-workspace return `status=ok`, and LTC preserves
channel zero. All five Settings families returned `ok` acknowledgements
without timeout in reversible changes; every value was restored. The user
explicitly allowed testing directly in redacted-test-workspace with the other workspaces
open, replacing the earlier isolated-copy requirement. See
`docs/development/runtime-validation/2026-09-30-audit-fixes.json`.

These results verify the specific operations tested, not every QLab setter.
The internal cause of error responses for absent Text attributes remains
unestablished; the fix uses the documented runs.
