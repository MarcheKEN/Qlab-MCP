# Workspace authoring audit — 2026-10-08

## Result and boundaries

The installed MCP can construct the tested audio/image/light sequence using its
existing public tools. A new disarmed list with nine disarmed cues was created
and left for review. Fresh health reads report all nine healthy, inactive and
without warnings. This proves the tested saved configuration, not playback,
hardware output or musical suitability.

The audit found one confirmed writer defect and one unresolved reader issue.
Neither was fixed in source during this audit. No new tools were implemented.

Evidence: [sanitized MCP records](2026-10-08-workspace-authoring-audit.json).
Exact private workspace/cue UUIDs and media paths are replaced with placeholders.

## Baseline and preservation

- One open QLab 5.5.10 test workspace; path observed in Computer Use; exact UUID
  resolved through MCP. Edit Mode and View/Edit/Control access confirmed.
- Connected MCP and source registry have identical tool names: 73 tools,
  46 reads and 27 gated writers.
- Initial map: 417 items, including 24 roots; UI: 393 cues, 23 Lists and 1 Cart.
- Final map: 427 items; UI: 402 cues, 24 Lists and 1 Cart.
- All 417 original index rows match the final rows by UUID, number, name,
  display name, type, list name, parent, containing list and depth.
  This comparison is structural, not a snapshot of every Inspector property.
- Recorded setters target only the new list and its new cues. No original cue
  setter, workspace-setting mutation, deletion or media-file modification.
- The list and all nine cues remain disarmed; zero running or paused cues.
  Cue creation and UI inspection change selection/playhead, as expected.
- Four existing Video routes are reported disconnected. The test uses the
  existing Stage 9 linked to the integrated display, confirmed in the UI.
- Existing Audio Patch 1 and Light instruments/groups were reused. No invented
  device or instrument configuration. No broad media search was necessary:
  file paths came from healthy existing cue details.

## Reference scene and observed configuration

Times below describe the intended armed sequence starting from Audio, not the
current disarmed arrangement. Memo is a manual documentation boundary.

| Cue | Intended start | Configuration verified |
|---|---:|---|
| Memo | Manual | Instructions; do not continue |
| Audio | 0 s | Existing stereo MP3, Patch 1, start 0/end 17, Main approximately -12 dB, one play, auto-continue |
| Video | 0 s | Existing 1024×1536 PNG, Stage 9, duration 17, opacity 0.8, Custom geometry, translation 0/0, scale 0.7/0.7, identity rotation after reset; auto-continue |
| Light entrance | 0 s | Duration 2; Group1=30, Group2=5; all nine RGB components explicit; auto-follow |
| Wait | 2 s | Duration 10, auto-follow; QLab also returns postWait=10 |
| Audio Fade | 12 s | Exact Audio target; Main activation enabled separately, destination silence, duration 3, stop target when done; auto-continue |
| Video Fade | 12 s | Exact Video target; opacity activation enabled separately, destination 0, duration 3, stop target when done; auto-follow |
| Light black | 15 s | Duration 2; the two groups and all nine RGB components set to zero; auto-follow |
| Stop | 17 s | Exact Audio target; do not continue |

QLab's auto-follow displays duration as a post-wait reminder; it does not add
another equal delay. Wait duration and post-wait are linked. See
[Inspector timing](https://qlab.app/docs/v5/fundamentals/inspector/) and
[Wait cues](https://qlab.app/docs/v5/other-cues/wait-cues/).
The local Day 1 QClass transcript explains auto-follow at 1:02:36–1:02:50.
No trigger activation or signal was enabled; default timecode values do not
prove an active trigger.

Light RGB was completed after inspection exposed that partial color commands
would depend on previous channel state. The black is scoped to the instruments
used by this scene, not every instrument in the workspace.

## Mutation protocol and UI contrast

All writes used readiness, exact UUIDs, explicit dry run, reviewed plans and
fresh confirmation tokens. Creation: one root and nine cues, structurally
verified. Editing: 60 setters, including three list setters. Recorded results
contain one send per planned operation; no ambiguous setter was resent.

Required dependency order was demonstrated:
1. Repair media/routing first, before assigning those cues as targets.
2. Separate Video repair from armed/geometry edits while health is broken.
3. Separate patch selectors from dependent timing/Levels edits.
4. Enable Fade Main/opacity first; request destination values in a fresh call.
5. Use Custom geometry when translation/scale should affect the image.

Computer Use was observation/navigation only: workspace path and counts,
Audio patch device and workspace volume limits, Light Patch instrument/group
names, existing Video destinations, all nine list rows, Wait Basics, Stop target,
Audio file and Main -12 display, Video file/Stage 9/opacity/Custom scale,
Light command texts, and both Fade targets/settings. Fade Main displayed -INF
and stop-on-completion; Video Fade displayed enabled opacity 0% and stop-on-completion.
GO, Preview, Send, monitors and playback controls were not invoked.

## Findings

### A1 — Confirmed quaternion verification defect

Input quaternion [1,0,0,0] was sent once and freshly read back as [1,0,0,0],
but the editor reported partial_failed / setter verification failed. Its
returned requested properties contained quaternion=1 instead of the vector.
Source inspection confirms shared visual preflight assigns args[0] to values
outside its structured/color sets; quaternion is absent from those sets.

The failed operation was not resent. A new resetRotation operation was planned
against fresh state and confirmed [0,0,0,1]. Final rotation is restored.
Video is runtime-proven here; Camera/Text impact is inferred from shared code.

**Priority 1:** Preserve the complete quaternion through normalization, token
binding and verification. Add a regression for all visual family models and
revalidate a reversible rotation in QLab.

### A2 — Image infiniteLoop read remains unresolved

A fresh Video detail read on the PNG returned partial=true with
infiniteLoop: Invalid OSC value for this field. Health and requested geometry
were available; the generic timing read and Inspector agree on duration 17.
No false default or setter was used to suppress this diagnostic.

**Priority 2:** Investigate the exact OSC reply for still-image loops, compare
movie fixtures, and define conditional applicability without weakening boolean
validation. Runtime fixture above records the issue; cause is not established.

### A3 — Agent orchestration needs explicit dependency guidance

Several legitimate requests were rejected because repair/target assignment,
patch/dependent settings or Fade activation/destination were combined.
Existing diagnostics allowed recovery, but one nonexistent target produced
the broad error Fresh cue identity could not be verified.

**Priority 3:** Add a small authoring workflow/skill with these stages, typed
operation argument examples (doLevel uses row/column), timing rules, explicit
RGB state, and a final cross-cue audit. Improve target diagnostics if necessary.
No additional broad editor is justified by this scene.

## Negative cases and checks

Dry runs rejected a nonexistent target, a target on Wait, and an unknown
property. A mixed valid/invalid Control batch returned preflight_failed with
executed_operations=[] for both cues. The valid sentinel name did not apply.
These are live dry-run checks, not deliberate live transport failures.

Existing automated tests were run for the signed Control, visual and remaining
family paths: 162 passed; token-codec tests: another 6 passed, including
wrong-secret and tampered-signature rejection. These cover expiry, token reuse/stale baseline,
preflight failure and timeout without resend. No new regression was written
because source fixes are outside this audit scope.

## Acceptance and remaining limits

Creation, media assignment, routing references, timing, Light commands, targets,
Fade activation/values, fresh health and UI contrast are verified for this scene.
Known failure A1 and partial read A2 remain explicitly open.
Original structures are preserved; the disarmed test list is retained.
No GO/Preview/Send, incoming signals, AppleScript, compilation, /live, Audio Maps,
rollback, release or package-version change. End-to-end playback and physical
output remain untested.

## Follow-up fixes — 2026-10-09

A1 and A2 are now corrected; the original findings above describe the earlier
audit. Changes are limited to shared visual normalization and the existing
read-side handling of documented boolean fields. Public tools and write input
types are unchanged.

### Quaternion

The visual preflight now takes the canonical normalized `value`, rather than
the first OSC argument. All four components survive planning, signed token
binding and immediate verification. Regressions cover Video, Camera and Text,
integer requests with decimal readback, and tokens invalidated by a change to
the requested vector or its observed baseline.

The current source was exercised through `FastMCP Client(mcp)` against QLab
5.5.10 over UDP. Computer Use confirmed the saved workspace path, cue 225,
Edit Mode and zero active cues. The audit image was healthy and inactive; its
current armed state was preserved. Each change used its own dry run and fresh
token, with no setters during planning:

- Baseline quaternion: `[0,0,0,1]`.
- Apply: one `/quaternion 1 0 0 0`, `updated`, fresh readback `[1.0,0.0,0.0,0.0]`.
- UI: the Geometry inspector showed the image upside down.
- Restore: one `/quaternion 0 0 0 1`, `updated`, fresh readback `[0.0,0.0,0.0,1.0]`.
- UI: original orientation and Memo selection restored; zero active cues.

Both setters requested same-connection `alwaysReply` and narrowly accepted
empty acknowledgement data. Identity, Basics, state, timing, Geometry/FX,
Audio and Triggers matched the initial observation after restoration. No
setter retry, playback, signal activation or workspace file save was performed.
Camera/Text quaternion writes were regression-tested, not revalidated live here.

### Still-image `infiniteLoop`

Fresh grouped and scalar reads both returned integer `1` for the PNG, versus
boolean `false` for the movie and Audio fixtures. Strict boolean validation was
the cause of the partial image result. The existing integer `0/1` conversion for
`preservePitch` now also covers `infiniteLoop` in family details and visual
writer baselines/readback. Strings, floats and other integers remain invalid;
write requests still require actual booleans.

The updated source returned `infiniteLoop=true` and `partial=false`, with no
errors, for the image; the movie also remained non-partial. This is an observed
OSC value, not an invented default or a conclusion about playback behavior.
The image inspector has no loop control to compare directly. Its I/O tab showed
`Video Format: No audio`, confirming the reason loop writes remain blocked. Its
file target, 17-second duration and geometry were contrasted with UI. The existing block
on image time/loop editing without readable embedded audio remains unchanged.

### Checks and runtime scope

- Focused visual reader/writer, Audio and field-validation tests: 151 passed.
- Complete suite: 1654 passed, 35 skipped, 61 subtests passed.
- Local `Client(mcp).list_tools()`: 73 tools; no generic cue editor registration.
- `git diff --check`: passed.

Socket tests initially encountered sandbox `Operation not permitted`; the
complete suite passed when local socket access was permitted. The source MCP
was tested before restart. The public MCP was restarted and
retested on 2026-10-09; it accepted a one-setter quaternion write and read it
back. Computer Use showed the expected upside-down image. A fresh dry run and
token restored `[0,0,0,1]`; readback and the UI showed the original upright
image, with zero active cues. The public read returned `infiniteLoop=true`,
`partial=false`, and no errors. This confirms the running MCP now serves the
fixes. Camera/Text rotation was not written live. See `post_restart_2026_10_09`
in the companion JSON for the compact verification result. No dependencies,
package version or release were changed.
