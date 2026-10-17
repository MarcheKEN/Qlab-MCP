# Inspector audit: Control, Devamp and Target

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-09-30. QLab 5.5.10. Verification of reads, dry runs and reversible Devamp editing. No cues were executed.

Workspace: `redacted-workspace-6b31c91e.qlab5`, UUID `8E86FE91-668B-560C-B738-4D581B5A7498`, path `<redacted-local-path-851cab375f>.qlab5`.

## Evidence and scope

Computer Use compared Start Basics/Triggers and Devamp Settings/Triggers against MCP reads. The earlier audit of the twelve types also covered Load Time and Target Cue Number. In this verification, Devamp 1.96 was restored to Start Next off and Stop Target off. The UI ended on Memo 38.95, Basics, with 252 cues in 18 lists/carts and zero active cues. The sample does not validate every combination of options.

## The Target limitation

A Target cue contains two distinct references:

1. Basics / Target: the cue whose target will change. Configured through `cueTargetID`.
2. Cue Number: the number of the new target assigned when Target executes.

Example: Target T points to Start S; Cue Number contains the number of Video V. Executing T temporarily changes the target of S to V. This investigation did not execute T.

The `number` property changes the number of T, not the second field. OSC provides `/cue/{id}/cueTargetID` and `/cue/{id}/cueTargetNumber`, but both edit the first reference: the cue that Target will retarget. Despite its similar name, `/cueTargetNumber` is not the inspector Cue Number field. The OSC dictionary provides neither reading nor writing of `assignedNumber`.

In QLab, Target 38.6 appears broken: MCP reads an empty `cueTargetID` and the UI shows `No target cue` and an empty Cue Number. This confirms it is incomplete, but does not isolate which of the two empty values independently determines the broken state. It was not executed. Therefore `qlab_edit_target_cues` can change the first reference but cannot complete `assignedNumber`; Get cannot read it through OSC either, as declared by `edit_capabilities.unavailable_via_osc`. Target 1.97 also reports broken and an empty `cueTargetID` in MCP.

AppleScript does document `assigned number`, a read/write text property of `target cue`. It also appears in the installed QLab 5.5.10 dictionary (`/Applications/QLab.app/Contents/Resources/QLab.sdef`, code `qASN`, key `targetCueNumber`). Its write behavior has not been tested live. The absence is a limitation of the OSC-only phase, not a general QLab limitation or a transport problem.

Sources: [Target cues](https://qlab.app/docs/v5/other-cues/target-cues/) and [AppleScript dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/).

## Inspector coverage

| Area | Current coverage and limitations |
| --- | --- |
| Common Basics | Name, own number, notes, colors, armed, flagged, auto-load, skip-if-disarmed, waits and continue mode have editing properties. |
| Control targets | Cue assignment/clearing by UUID. Reset adds mode and patch, validated against the inventory. Audio Maps remain excluded. |
| Wait / Memo | Wait supports duration. Wait and Memo reject targets; Memo does not support duration editing. |
| Devamp Settings | `devampType`, `startNextCueWhenSliceEnds` and `stopTargetWhenSliceEnds`; preflight now validates the final combination. |
| Target / Assigned Number | Missing from documented OSC; AppleScript provides `assigned number`. |
| Load Time | Outside documented OSC; AppleScript provides read/write `load time`. |
| OSC Triggers | Duck/Boost, Fade & Stop time, Second Trigger, Timecode text/components. The local model now preserves the text in `triggers`. |
| Fade & Stop scope | In this sample QLab returns a boolean when off; some earlier trials returned an integer. The writer only allows mode 0–3 editing when the current read is a reliable integer; a boolean blocks it. |
| Other Triggers | Hotkey, MIDI, Wall Clock and Timecode activation/display are not covered by these OSC writers. AppleScript documents several related properties; they require their own inventory and validation. Complete hotkey assignment and weekdays have not been tested. |

A configured Timecode does not imply an enabled trigger: in the sample the UI shows activation off and hides the time, while OSC preserves `1:00:00:00`. Capture remains excluded because it depends on an incoming signal.

Sources: [inspector](https://qlab.app/docs/v5/fundamentals/inspector/), [Devamp](https://qlab.app/docs/v5/other-cues/devamp-cues/), local dictionaries in `docs/references/` and current code.

## Fixes and verification

### 1. Timecode text in Triggers

All twelve reads have `timing.timecodeTriggerText="1:00:00:00"`, but `triggers.timecodeTriggerText=null`, without an error. The aggregated components are present.

`cues/family.py::_section` normalizes the OSC alias to a field name before building the model. `ControlTiming` already accepted field names through `populate_by_name=True`; `ControlTriggers` did not.

Fix: enable `populate_by_name` in `ControlTriggers`. A full-result regression checks all twelve types and both profiles. After the latest restart, the active MCP returns `triggers.timecodeTriggerText="1:00:00:00"`, matching `timing.timecodeTriggerText`; the original failure no longer reproduces.

### 2. Final Devamp validation

`write/control.py::_preflight` now calculates Start next and Stop target by combining previous and requested values, and rejects the request if Stop target remains enabled without Start next.

Regression with a simulated Reader: starting with both flags enabled, the local dry run that only disables Start next fails without a setter. In the first MCP instance, the same invalid case was planned; after the latest restart, the opposite check—enabling Stop Target while Start Next is off—ends in `preflight_failed`, with zero planned or executed operations. Devamp 1.96 remains in looping slice mode, targeting Audio 2, with both flags off in MCP and the UI. The cue was not executed.

## Verification

- Focused regressions: **102 passed**.
- Full suite: **3326 passed, 61 subtests passed**.
- `Client(mcp).list_tools()`: **59 tools**; includes `qlab_edit_control_cues`, `qlab_edit_devamp_cues`, `qlab_edit_target_cues` and `qlab_get_control_cue_details`.
- Revalidation after restart found readiness `ready`, QLab 5.5.10, the exact UUID, Edit permission, Edit Mode and three open workspaces. Reads of the ten Control types, Devamp and Target returned specific capabilities; all three edit tools passed dry run with one planned setter and zero executed.
- Two current negative dry runs sent no setters: Fade & Stop scope is blocked because this Start returns a boolean, and Stop Target is blocked when Start Next is off. Subsequent Devamp readback preserves both flags off.
- Computer Use confirmed Start 37.5 in Triggers: Timecode Trigger is off although MCP preserves `1:00:00:00`; Fade & Stop scope appears disabled with Fade & Stop off. Wait 38.9 shows Duration and Post-Wait of 1 second, matching MCP. Memo 38.95 shows disabled duration. Devamp 1.96 shows mode, target and flags matching MCP.
- Target 38.6 shows `No target cue` in Basics and an empty Cue Number field in its own tab. MCP reads `cueTargetID=""`, but cannot read `assignedNumber`; the UI confirms these are separate fields. Final selection was restored to Memo 38.95/Basics. Workspace: 252 cues, 18 lists/carts and zero active cues. No writes or execution occurred during this revalidation.

The remaining limitations are specific: `assignedNumber` and Load Time require AppleScript; Hotkey/MIDI/Wall Clock and Timecode activation/format are not exposed by this OSC writer; Fade & Stop scope is allowed only when its previous read returns a reliable integer. None prevents the OSC writes advertised as available.
