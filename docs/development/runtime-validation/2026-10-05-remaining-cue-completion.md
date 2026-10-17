# Nine cue editors — family-specific live validation

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

QLab **5.5.10**, one open workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`.
Computer Use confirmed its exact path:
`<redacted-local-path-851cab375f>.qlab5`.
Edit Mode, `/connect` permissions and zero active cues were verified before writes.
The final workspace retained **251 cues and 19 containers** (18 lists, one cart).

All writes called the public tools through source `fastmcp.Client(mcp)`, with the
configured OSC transport and normal readiness/preflight/tokens/readback. No raw
setters, GO, Preview, Send, playback, signals, Audio Map editing or compilation.
Computer Use was used only for reading and inspector/list navigation.

## Verified changes and restoration

Each successful case used observed baseline → dry run with zero setters → fresh
confirmation → one send per property → fresh readback → UI contrast → new-token
restoration. The [sanitized call ledger](2026-10-05-remaining-cue-completion.json)
retains failed/partial cases as well as successful cases. No ambiguous setter
was automatically resent. Final independent Get inspections assert restoration
of every property modified in the eight families below.

| Family | Changes actually tested | Inspector/readback comparison |
| --- | --- | --- |
| Audio | Rate 1→1.1, Duck Others false→true, crosspoints 1/1 and 2/2 to −3/−4 dB in one four-setter call; two slice play counts 1/5→2/3 in one call | Levels −3/−4; Time & Loops counts 2/3; full cumulative slice inventory verified. Rate, flags, cells and counts restored. |
| Mic | Input patch empty→`4C64F17D-5B4C-5E69-9CE9-DEFE6F7FD12A` | I/O showed System Input, one channel, start channel 1; patch selector snapshot read. Empty original input patch restored. |
| Light | Always Collate true→false; Subcontroller false→true; command `Grupo1 = 30`→`Grupo1 = 31` in the existing five-line command block | Levels showed flags off/on and command 31; command analysis resolved against Light patch. Flags and exact text restored. |
| Fade | Stop Target When Done true→false; duration 3→3.1 plus Duck Others and Main slider −60→−6; target changed to the healthy Audio fixture and back | Curve flag off; duration 3.10; Levels screenshot −6; selector snapshots verified. Target, flags, duration and Main restored. |
| Network | Saved opaque message `/cue/12/flagged Yes`→`/cue/12/flagged No`, Duck level 0→−3 | Settings showed the saved No message. No Send. Original message and level restored. |
| MIDI | Voice bytes 60/64→61/65; mode Voice→MSC; MSC GO/device 0→STOP/device 1; mode Voice→SysEx and back | Settings showed Voice bytes, MSC STOP/device 1, then SysEx with empty payload. No message sent. Bytes, mode and hidden MSC command/device restored. |
| Timecode | Frame rate 29.97 non-drop→30 non-drop, retaining start 1:00:00:00 and duration 3603.6 s | Settings showed 30 fps and normalized end 2:00:03:18. Restored 29.97 non-drop/end 2:00:00:00. LTC zero remained unchanged. |
| Script | Pre-wait 0→0.5 and duck time 1→1.5 in one call | Basics 00:00.500 and Triggers 00:01.5; both restored. Source untouched. |

UUIDs and baseline details are in the call ledger. Validation establishes saved
configuration/readback, not playback readiness. The Mic, MIDI and LTC fixtures
return to their original unpatched/broken state; this is intentional restoration.

## Failures that informed corrections

- Initial Audio crosspoint verification rejected QLab's tiny float quantization.
  Numeric dB verification now uses 0.001 dB tolerance, with regression coverage.
- An initial slice read timed out after one setter. The batch stopped and was
  restored with a fresh token. Preparing each scalar read on its own connection
  allowed the subsequent complete two-marker edit and restoration to verify.
- Initial Timecode verification incorrectly expected unchanged end time when
  changing frame rate. Observations established duration-preserving normalization;
  corrected runs and restoration both returned `updated` with one setter each.
- Early MIDI-mode plans failed before any setter during identity reads. Exact
  UUID/type scalar reads, prepared in the same connection, corrected that path.
  Subsequent MSC and SysEx selector tests verified and restored successfully.
- Fade Main request −59 returned **−59.01564025878906**. The tool reported
  `partial_failed` after that single level setter, preserved fresh readback and
  sent no retry. All earlier successful fields and that level were restored via
  new tokens. This boundary remains a documented verification limitation;
  −6 verified within tolerance. No tolerance widening hides the discrepancy.

## Pending live fixtures and retained blocks

- MIDI File: Main cue `655C8326-B4E7-5D75-A204-08A5D34EE902` has no file and is
  broken. Its timing edit was blocked before setters. The OTHER test list contained
  no MIDI/MIDI File cues. A healthy Type 0/1 fixture is still required for file/timing
  mutation coverage; Type 2 rejection has simulated regression coverage.
- SysEx payload mutation: the available saved payload is empty. Only selecting
  SysEx was tested; nonempty payload validation/readback has simulated coverage.
- Cue-owned Objects, Audio mute/solo/bulk cleanup, Integrated Fade flags, Mic
  Levels, Network fades/patch reassignment, MIDI patch routing and Timecode mode/
  positive LTC output: these specific setters have no completed live mutation
  evidence here. They require their declared readable dependencies and remain
  unverified live, rather than inferred from family-level success.
- Mic input count/offset stays blocked: UI shows capacity but OSC does not supply
  an authoritative input bound. Audio Maps are excluded. Objects with unknown/map
  ownership are blocked. Network Device Definition fields and MSC command-dependent
  fields remain blocked without activation/type/range metadata.
- `setDefaultLevels`, captures from target and boolean Fade & Stop scope remain
  blocked. Source/Trim/Audio FX/undocumented curves are unavailable in this OSC phase.
- The 50-cue/50-indexed-operation limits are schema/simulation coverage, not a
  50-cue live stress test. An execution budget can leave later operations pending.

## Acceptance

Full suite: **3612 passed, 61 subtests passed**. Focused family regressions also passed (198 tests before the final two target/media regressions).
`Client(mcp).list_tools()` inspected **72 tools**, retained `qlab_edit_cues`, and
confirmed the nine typed 1–50 schemas. Indexed families (Audio/Mic/Fade/Network)
allow at most 50 operations per cue; scalar-only families expose `operations=[]`.
See [schema evidence](2026-10-05-remaining-cue-schemas.json).
[Final test evidence and source hashes](2026-10-05-remaining-cue-tests.json) records the complete suite. `git diff --check` passed. No dependency, package version or release was changed
by this implementation; preexisting checkout changes were preserved.

Source-client validation does not reload an already running installed MCP.
Restart it to use the updated argument schemas and executor.
