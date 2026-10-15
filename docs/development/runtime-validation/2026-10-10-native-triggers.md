# Native cue Triggers — QLab 5.5.10

## Scope and environment

Validated the current source MCP with `Client(mcp)` against the authorized
`redacted-test-workspace` workspace, after checking exact path/UUID, Edit Mode and inactivity.
One local `/Applications/QLab.app` instance was running. All fixtures stayed
disarmed with Do not continue and Skip if disarmed off. No cues, incoming signals,
capture, global overrides or output were triggered by the test procedure.
Computer Use only inspected/navigated the inspector.

The installed MCP now advertises the native Trigger schemas. The final
context-only visual read correction still requires a restart. Source validation
does not prove that the installed process loaded that last fix.
The public surface remains 74 tools, with no release/version/dependency
change in this phase.

## Reversible source MCP checks

Each write used baseline → reviewed dry run (zero executed operations) → fresh
signed confirmation → one setter per operation → fresh readback. Restoration
used new dry runs and tokens, never an automatic rollback.

| Family / property | Observed result |
| --- | --- |
| Control / Load incoming MIDI | Channel 2, numeric note 64, velocity `>90`; inspector matched |
| Control / MIDI command | All 0–5 commands changed and read back; inspector matched Note Off/On, Key Pressure, Control Change, Program Change and Channel Pressure |
| Control / MIDI display predicates | `any`, `<70`, `>90` and Any Channel matched the inspector; numeric setters preserved comparison operators |
| Control / Wall Clock | 03:21:45 changed and read back; enabling revealed the same time in the inspector, then disabled |
| Control / MIDI and Timecode activation | Enabled and disabled separately; inspector checkbox states matched, with disarmed/inactive safety state preserved |
| Control / Timecode display | Real Time and Timecode read back; inspector showed Real Time with saved 01:00:00.000 when enabled |
| Group | Incoming channel and Wall Clock minute changed/read back; channel 3 matched inspector |
| Mic | Incoming channel changed/read back; channel 4 matched inspector |
| Text | Incoming channel changed/read back; inspector contrast and restoration recorded in the evidence |

Fresh native reads confirmed restoration of all touched settings, including
numeric/display aliases and safety fields. Configuration is not playback or
physical-output certification.

## Rejections and findings

- Program Change's second-byte write failed preflight with zero setters;
  the inspector showed N/A. Channel Pressure also showed N/A.
- Hotkey enabling failed preflight with zero setters because assigned key and
  modifier identity cannot be read from the dictionary.
- Initial bridge experiments exposed AppleScript boolean/Objective-C expression
  precedence errors before any setter. Fixed by an explicit static key allowlist
  and an independently tested dictionary-comparison handler; fresh confirmations
  were used afterward. Load Time reads still passed.
- Numeric byte writes preserve predicates: `<70` plus numeric zero becomes `<0`.
  Restoring exact matching required a fresh string write `"0"`. Both forms are
  returned by the snapshot; this is documented and covered by a regression.
- Independent review found native fields simultaneously advertised as blocked
  and gated/planned when a Remaining-family Get omitted native reads. The shared
  capability helper now removes blocked entries from the gated/planned mapping;
  a regression demonstrates the corrected contract.
- Closeout on 2026-10-11 reproduced a Text failure before its setter: two
  consecutive identical identity-only `valuesForKeys` reads produced a TCP
  timeout on the second response. Context-only visual reads now return their
  first freshly validated UUID/type result without the redundant final query.
  Property reads retain their final identity check. A failing regression was
  added before this fix, followed by source MCP change/readback/restoration.

## Automated and schema checks

- Focused native regressions: **42 passed**.
- Visual plus native regressions after closeout fix: **118 passed**.
- Full suite after closeout fix: **1788 passed, 35 skipped, 61 subtests passed**.
- Existing UDP/TCP, token, family writer and Control AppleScript regressions pass.
- `Client(mcp).list_tools()`: **74 tools**, **13 opt-in family Gets**, **16 family
  editors** containing the 14 typed native Trigger properties.
- The guide's fictional UUID request validates against the actual public schema;
  no documentation-example setter was executed.
- Local documentation links and `git diff --check` checked at closeout.

## Limits

## Restarted installed MCP follow-up — 2026-10-11

The installed `mcp__qlab_mcp__*` tools confirmed one QLab 5.5.10 workspace,
Edit permission and Edit Mode. Computer Use verified the expected workspace
file path and zero active cues; it was used only for inspection/navigation.

- Text: MIDI channel 0 → 5 → 0 passed dry run, signed execution and fresh
  reads. The inspector showed Channel 5, then Workspace Channel (Any).
  This confirms the context-only identity-query fix in the restarted server.
- Load: one request changed channel to 2, note to 64, velocity predicate to
  `>90` and Wall Clock to 03:21:45. Six setters were individually verified.
  The inspector matched MIDI values. Separate clock activation revealed
  03:21:45 and the enabled checkbox; separate deactivation passed.
- Restoration used fresh dry runs/tokens, including string `"0"` for both
  MIDI predicates. Fresh detail reads matched every original Trigger field
  for Text and Load. The inspector confirmed restoration; initial Wait/Basics
  selection was restored.
- Hotkey activation was rejected in preflight with zero setters.

All six successful edit calls had dry runs with zero executed operations;
the executions recorded 16 setters in total, with no timeout or retry.
No cue was executed and no external signal was supplied. This follow-up
validates configuration, not playback or physical output.

## Remaining limits

Hotkey assignment/enabling, Wall Clock weekdays and capture are blocked or
unavailable. Disabling an already-enabled Hotkey has automated/dictionary
coverage but no live fixture transition in this run. Other family integrations
have automated common-engine coverage; live setter coverage here is bounded to
Control, Group, Mic and Text, not every cue family. Platform/Automation failures
keep ordinary OSC evidence and mark opted-in native reads partial. Remote OSC
cannot use this local bridge. Subsequent arming remains an operator decision.

See [dictionary research and safety rulings](../research/2026-10-10-native-triggers.md),
[usage](../../user/agent-workflows.md#native-cue-triggers) and
[sanitized closeout MCP evidence](2026-10-10-native-triggers.json). The JSON
records the 2026-10-11 Text correction and final restored reads; earlier live
cases are retained as the narrative evidence above.
