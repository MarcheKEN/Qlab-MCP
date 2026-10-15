# Triggers: inventory for splitting Edit Cues

Date: 2026-09-30. Research; no implementation or real setters.

## Evidence

- Computer Use: Triggers inspector of Fade 37, `FADE VIDEO - OPACITY ABS`, in `redacted-workspace-6b31c91e.qlab5`.
- Workspace UUID: `8E86FE91-668B-560C-B738-4D581B5A7498`.
- Cue UUID: `9A7F81E3-0216-593E-AD6B-CF72C7D4093B`.
- Observed path: `<redacted-local-path-851cab375f>.qlab5`.
- Connected MCP: `qlab_get_cue_details(profile="inspector_safe")` and `qlab_edit_cues(profile="common", dry_run=true)` on that identity.
- The dry run accepted eight scalar properties, read their previous values and returned `executed_operations=[]`. This does not demonstrate that their setters work.
- No cues were executed or triggers enabled. Only the Second Trigger and Wall Clock weekday menus were opened and closed.

## UI and documented OSC writes

| Inspector block | OSC | Project status |
| --- | --- | --- |
| Hotkey: activation and key combination | No documented endpoints found | No configuration implemented |
| MIDI: activation, message, channel, bytes and Capture | No documented configuration endpoints found | Do not confuse this with editing a MIDI cue that sends messages |
| Wall Clock: activation, time, format and days | No documented endpoints found | No configuration implemented |
| Timecode: time | `timecodeTrigger/text` and hours/minutes/seconds/frames/bits components | Existing read; common editing catalog with tokens |
| Timecode: checkbox and display format | No documented setters found | Do not infer activation from the time |
| Timecode Capture | `captureTimecode` | Outside the Edit catalog; listed as an action in the allowlist |
| Fade & Stop | `fadeAndStopOthers`, `fadeAndStopOthersTime` | Existing read; common catalog with tokens |
| Duck/Boost | `duckOthers`, `duckLevel`, `duckTime` | Existing read; common catalog with tokens |
| Second Trigger | `secondTriggerAction`, `secondTriggerOnRelease` | Existing read; common catalog with tokens |

OSC specifies Fade & Stop modes 0–3; Duck/Boost level from -120 to +12 dB; Second Trigger 0–7, with 6–7 exclusive to Playlist Groups. The aggregated `/timecodeTrigger` is **read-only**. Capture depends on incoming timecode and is not a deterministic setter of a requested value.

Sources: [OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/) and local copy `docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`, common cue property sections. [Inspector manual](https://qlab.app/docs/v5/fundamentals/inspector/#the-triggers-tab).

## Comparison with the open cue

| Field | UI | MCP |
| --- | --- | --- |
| Second Trigger | panics | `secondTriggerAction=1` |
| On release | off | `secondTriggerOnRelease=false` |
| Duck | off; amount 0; time 1 s | `duckOthers=false`, `duckLevel=0`, `duckTime=1` |
| Fade & Stop | off; time 1 s; disabled peers menu | `fadeAndStopOthers=false`, `fadeAndStopOthersTime=1` |
| Timecode | checkbox off | Time `1:00:00:00`; activation not included |

The boolean Fade & Stop response does not identify a numeric mode. This observation with the option disabled does not demonstrate what QLab returns for each enabled scope. Before writing or verifying Peers/List/All, all three variants must be checked and state distinguished from scope.

## What is actually implemented

`write/registry.py` contains these properties in `COMMON_CATALOG_PROPERTIES`. It marks them `real_write_enabled=false`, but generates tokens. `real_write_permission_errors()` accepts scalar operations with their exact token. The `write/operations.py` flow invokes that generic authorization. Therefore the label does not constitute a permanent block: a token authorization path exists, still without live validation in this investigation.

The generic `inspector_safe` read returns the fields in `properties`. Some family reads include them through `ControlBasics`; Audio/Mic and other structures do not provide a uniform Triggers section. `editable_update_capabilities()` combines profiles, whereas an edit request uses a specific profile: a capability advertised by `common` may be absent from the family profile.

## Mismatches reproduced in code, without networking

With `normalize_update_request('common', ...)` and `real_write_permission_errors()`:

- `fadeAndStopOthers=99` is accepted; its validator is `number`, without a mode restriction.
- `secondTriggerAction=7` is accepted without checking Group Playlist in this authorization.
- `timecodeTrigger/minutes=99` is accepted; all components share the range 0–99.
- `timecodeTrigger/text='invalid'` is accepted; the validator is a generic string.
- The catalog generates a five-argument operation on `timecodeTrigger`, although that endpoint is read-only. It also lacks `read_key`, and generic authorization blocks its write because deterministic readback is unavailable.
- For the scalar cases above, the permission check returns errors without a token and `{}` with the exact token. This is local code evidence, not a QLab execution test.

Check executed with `PYTHONPATH=src .venv/bin/python`; it does not use OSC transport. The suite was not run because there are no implementation changes.

## AppleScript: additional documented capabilities

As a future alternative, the dictionary provides `hotkey trigger` to enable the checkbox, MIDI configuration (`midi trigger`, channel, command and bytes), Wall Clock time and activation, and Timecode activation/format/time. No documented properties were found for assigning the Hotkey combination or Wall Clock weekdays. The current server excludes AppleScript writes; using them would require explicitly extending the transport and public policy. They have not been tested live.

Source: [AppleScript dictionary, cue class](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/#cue) and local copy `docs/sources/qlab-5-applescript/applescript_dictionary_v5.local.html`.

## Refactor proposal

1. Include a common Triggers block in Edit tools by type; reuse the current engine.
2. Expose documented OSC fields first, with typed operations and current values. Separate Timecode time from unknown activation.
3. Remove the read-only aggregate from the future setter catalog; correct modes, components, text and Playlist context before extending writes.
4. Give family reads a consistent Triggers section, with unknown fields and explicit coverage limits.
5. Validate scalar setters and scope reads in a fixture before declaring them operational. Keep dry run, confirmation and fresh readback; no ambiguous resend.
6. Evaluate AppleScript separately for options without OSC; do not promise complete inspector coverage.

A tool per tab is unnecessary: the block can be part of the agreed family tools. The UI and MCP sampling in this investigation covers one Fade cue; it does not validate every family or mode.

## Implementation and verification: Control cues (2026-09-30)

The earlier audit describes the previous state. `qlab_edit_control_cues` now
implements the ten agreed types, Basics, OSC Triggers and targets with signed
five-minute tokens and reservation of the entire batch. Target/Devamp and the
AppleScript path remain outside this phase. The generic tool remains.

Findings in QLab 5.5.10 that changed the implementation:

- `valuesForKeys` converts `fadeAndStopOthers` to a boolean, but the exact scalar
  query returns 0, 1, 2 and 3. Control Get and the writer use the scalar read.
  Scope is blocked if that read does not return a reliable integer mode.
  The UI confirmed `all` for 3 and disabled for 0.
- Reset must receive `targetMode` before `patchTargetID` or `cueTargetID` when
  changing mode. A trial with the opposite order failed readback and stopped
  the batch without resending; its fixture was removed. The corrected order
  confirmed the patch UUID and the UI showed the System Output patch.
- `patchTargetID=""` is a valid observed previous state; it does not enable a
  clear request. Request validation differs from previous-read validation.
- A query by an unassigned number returns an error, not an empty identity.
  New number availability is checked through the complete fresh workspace
  structural inventory, reusing its existing reader.
- Timecode text is normalized on read (`01` → `1`). Comparison preserves
  its components and verifies the format; it does not enable the Triggers checkbox.

Shared validators restrict Fade & Stop to 0–3, Second Trigger 6–7 to Group
Playlist, and Timecode components/text to the containing list format, and
reject the read-only `timecodeTrigger` aggregate. The dedicated writer rejects
6–7 and `captureTimecode`. It does not interpret the time as activation.

Evidence and limitations: [validation record](../runtime-validation/2026-09-30-control-cues.md).
AppleScript writes, Load Time, Hotkey, MIDI Trigger and Wall Clock have not
been implemented or tested. No cues were executed or incoming signals enabled.


## Devamp and Target extension (2026-09-30)

Implemented `qlab_edit_devamp_cues` and `qlab_edit_target_cues` by reusing the
Control writer. The models share Basics and Triggers; Devamp adds
`devampType`, `startNextCueWhenSliceEnds` and `stopTargetWhenSliceEnds`. Target
only adds UUID target selection; the Cue Number tab has no documented OSC
setter and is not implemented through execution or temporary retargeting.

Sources: [Devamp](https://qlab.app/docs/v5/other-cues/devamp-cues/),
[Target](https://qlab.app/docs/v5/other-cues/target-cues/),
[OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
and the local dictionary copy. Devamp requires an Audio/Video target; Target
requires a cue that supports cue targets and excludes Fade. Stop target is
validated against Start next. Previous profile restrictions and tokens are unchanged.

The first test on a new Devamp confirmed that `fadeAndStopOthers` can remain
boolean **even in the scalar query**, before receiving an integer setter.
The batch was blocked without Devamp setters, and the fixtures were cleaned up.
The boolean is not converted to a mode and the field is not silently initialized.
The later test confirmed the other documented properties, keeping scope blocked.
The capability read exposes that block for each cue.

[Devamp/Target validation](../runtime-validation/2026-09-30-devamp-target-cues.md).
