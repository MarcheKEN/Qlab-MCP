# Fixed native cue Triggers

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Accepted scope

Extend the existing family Gets and Editors with saved MIDI trigger configuration,
Wall Clock time, and Hotkey/MIDI/Wall Clock/Timecode enable state and Timecode
display mode. Reuse the local fixed AppleScript bridge, exact UUIDs, signed
five-minute single-use confirmations, whole-batch preflight and fresh readback.
No new tools, dependencies, arbitrary scripts, capture, signals, playback or release.
Hotkey key assignment and Wall Clock weekdays have no located dictionary property.

## Tasks and shared interfaces

1. Add failing regressions for strict inputs, native snapshots, denied/partial
   reads, dependency changes, safe activation and sequential timeout handling.
2. Extend the fixed JSON bridge with a single bounded native trigger snapshot
   and explicit setters. Validate installed SDEF types and MIDI command context.
3. Integrate common typed fields, native planning/reading and capability gating
   across the existing cue family editors; preserve prior Control fields.
4. Run focused/full tests, inspect public schemas, validate source MCP against
   disarmed fixtures and Computer Use, restore values and update active docs.

Pre-flight: bridge returns a typed snapshot; readers preserve OSC data on native
failure; writers bind the full snapshot and safety state to each confirmation.
Native parameter changes require their trigger disabled. Enabling requires a
disarmed cue, continueMode=0 and skipIfDisarmed=false; safety controls cannot
change in the same call. MIDI command changes and Timecode display/time changes
are separated from dependent configuration. No global input override is changed.
The native script repeats identity, Edit Mode, activity and baseline checks before
its single setter. Unexpected neighboring changes stop the batch without retry.

## Review focus and rulings

Review enum conversion, integer/string MIDI aliases and comparator baselines,
local/app/UUID identity, pre/post-send errors, snapshot freshness, mixed native/OSC
batch bookkeeping, partial-read capabilities and external-trigger safety.
Preserve the dirty checkout; no commits or worktree reset are part of this task.
Live evidence is distinct from documented setters and automated coverage.

## Completion — 2026-10-11

Implemented the 14 fixed native fields in the existing 16 family editors and
13 opt-in detail Gets, without adding tools or dependencies. Independent review
found and corrected the blocked/gated capability overlap. Live checks exposed
and corrected AppleScript expression precedence and a redundant context-only
visual identity query; regressions preceded the final corrections.

Focused visual/native checks: 118 passed. Full suite: 1788 passed, 35 skipped,
61 subtests passed. Source tool schemas and the guide example were inspected.
Control, Group, Mic and Text changes were contrasted with the inspector and
restored. Hotkey enabling/assignment, weekdays and capture retain their limits.
See the [runtime report](../../development/runtime-validation/2026-10-10-native-triggers.md).
