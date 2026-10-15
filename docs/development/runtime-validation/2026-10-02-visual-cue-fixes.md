# Visual editor fixes and remaining QLab limits — 2026-10-02

QLab 5.5.10, workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`, path
`<redacted-local-path-851cab375f>.qlab5`.
Only one workspace was reported open. Its path was independently confirmed by
Computer Use. Target: Video cue 4 `VIDEO_VALID`,
`4CC5ADC7-D124-58A3-B8CE-95A42CEADC50`. All writes used actual MCP tool calls
through source-loaded FastMCP `Client(mcp)` and authenticated OSC TCP, with dry
runs, signed tokens, one setter per operation and fresh readback. Computer Use
only selected lists/cues/inspector tabs and observed values. No cues or external
signals were triggered. The installed MCP requires restart to load these fixes.

## Corrected in the server

| Failure | Cause and correction | Live result |
| --- | --- | --- |
| Aggregate `crop` | OSC returns `[top,bottom,left,right]`; the writer expected a typed object. Normalize and validate the observed list at the shared visual read boundary, retaining strict public requests. | `{12,8,16,4}` applied with one setter, read back correctly and matched the four inspector crop fields. Restored to zero. |
| `preservePitch` | OSC returns integer `0/1`. Normalize only those observed values to booleans; do not accept integer requests. | False → true → false verified. Time & Loops showed Preserve pitch on, then off. |
| Timecode preflight | The direct containing-list format query timed out although fresh `valuesForKeys` supplied format `3`. The visual writer also repeated the shared immediate format check. Read UUID/type/format through `valuesForKeys`, retain SMPTE/drop-frame validation and perform one immediate format check. | `1:00:00:00` → `1:02:03:04` → baseline, verified with fresh OSC reads. Trigger remained disabled. The UI field stays blank while disabled, so UI did not independently confirm the stored text. |
| Mute warning recovery | Broad visual health rejection also blocked removing the mute that caused the warning. Reuse the existing removal/cleanup validator; require readable channels, inactivity and explicitly unbroken health. | Channel 2 mute → unmute worked in the specialized tool. A separate mute → no-argument clear also worked and verified `[]`. Clear Mutes became disabled; warning cleared. |
| Scale restoration | Enabling Preserve Aspect Ratio changes scale before a later scale setter, invalidating its previous value. Put the explicit scale pair first when enabling the lock, bind/recheck the lock and reject contradictory pairs before writing. | `(1,1)` → unlocked `(1.25,.75)` → locked `(1,1)` restored without a partial abort. Single `scale/x=1.1` with an existing lock also worked; QLab changed both axes, then both were restored. |

The local OSC dictionary documents crop component order, preservePitch,
sliceMarkers and List/Cart timecode formats. See
[`qlab_osc_dictionary.repository.md`](../../sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md).

## Remaining limitations, not declared fixed

### Slices without a reliable inventory

On `VIDEO_VALID`, the raw `valuesForKeys` payload **omits** `sliceMarkers`;
the direct `/sliceMarkers` query returns QLab status `error`. The generic
inspector's `[]` is derived by existing fallback behavior, not proof of an
observed empty inventory. Another existing cue, `Con slices`
(`236C5D6C-59CA-5C8A-B82F-43E71F6603DD`), returned two actual markers with times
`0.39638516306877136` and `1.784542202949524` and play counts 2 and 4. Thus the
collection is readable for some cues; it cannot safely be inferred for this one.

The specialized editor still fails preflight with no setters when it cannot
read the inventory. Its capabilities now block slice operations when detail
reads lack that inventory. No default markers, mutation-only probes or GUI
edits were used to work around the missing baseline. `Con slices` is broken and
was only read; no healthy fixture with an existing marker collection was edited.

### `endTime` near the exact media end

The original end time is `80.86666666666666`. These distinct MCP requests were
observed, with no automatic resend:

| Requested time / encoding | Readback | Outcome |
| --- | --- | --- |
| `75.5`, float32 | `75.5` | Normal acknowledgement and verification |
| `80.86`, float32 | `80.86000061035156` | Normal acknowledgement and verification |
| `80.86666666666666`, float32 | Original media end | QLab error, matching readback, batch stopped |
| `80.86666107177734`, float32 | Original media end | QLab error, matching within numeric tolerance, batch stopped |
| `75.5`, experimental float64 | Unchanged original media end | Timeout, verification mismatch; experiment removed |

Float32 encodes the original value as `80.86666870117188`, slightly above the
media duration. However, the lower representable value also failed. Wire
rounding alone therefore does not establish QLab's internal cause; the observed
failure is at the media boundary. A float64 no-op experiment initially matched
readback after a timeout, but the subsequent **actual change** failed, disproving
it as a usable fix. No float64 setter support remains in production.

An exact baseline restoration produced QLab status `error` while fresh readback
confirmed the original end time. That error is retained as
`verification_inconclusive` at cue level / `partial_failed` at batch level.
No response-error suppression, covert truncation or setter retry was added.
Restorations were separate, newly planned requests following distinct changes.

## Verification and final state

- Regressions first reproduced crop, pitch, Timecode read selection, duplicate
  format checks, warning recovery and scale ordering. Tests cover strict invalid
  crop/boolean inputs, healthy versus broken recovery, exact readback after a
  setter error, and preserving single-component scale edits.
- Focused visual/control/read tests: 156 passed. UDP/TCP transport regressions
  also passed outside the sandbox (sandbox socket binding was denied).
- Final full suite: **3393 passed, 61 subtests passed**.
- `Client(mcp).list_tools()`: 62 tools; Video, Camera and Text edit batch schemas
  retain limits 1–50. Public names and arguments unchanged.
- `git diff --check` passed. Existing checkout changes were preserved; no new
  dependency, package version change or release.
- Final fresh MCP reads confirmed crop zero, scale `(1,1)`, aspect lock and Fill
  Stage enabled, pitch false, baseline Timecode, original end time, empty
  mute/solo lists, and no warning/broken/running/paused state on the target.
- Final UI showed start `00:00.000`, end `01:20.867`, pitch off, play count 1,
  disabled Clear Mutes and **0 Active Cues**. UI selection ended on cue 4.

The result proves the corrected paths on this fixture, not every Video property
or actual playback. Detailed bounded results, previous values, unique setters,
errors and restorations are in
[`2026-10-02-visual-cue-fixes.json`](2026-10-02-visual-cue-fixes.json).
