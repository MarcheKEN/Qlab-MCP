# QLab Computer Use — workspace audit

**Date:** 2026-08-24
**Status:** GUI research snapshot; no production code changed.
**Method:** Computer Use through `@oai/sky` (`get_app_state`, clicks, and field inspection). No QLab OSC or AppleScript calls were made.

## Executive summary

The workspace named in the request, `MCP_bajada_Prueba`, was not visible in QLab's Launcher/Recent Workspaces and no matching file was found in the local QLab/Documents/Downloads search. The QLab instance that is linked to this repository had another workspace open:

```text
/Users/filarmonica/Documents/Qlab/5.5/mcp_prueba/mcp_prueba.qlab5
Window: mcp_prueba.qlab5 — delete list
Workspace ID: 95F0A03D-140E-4673-974A-E76748EBB023
```

The observed workspace is a useful fixture/reference workspace, but it is not evidence about the requested `MCP_bajada_Prueba` workspace. It contains 232 cues in 17 lists/carts and 117 broken cues/warnings. The principal engineering signal is that cue validity depends on the infrastructure graph (files, patches, stages, routes, targets, and devices), not only on cue properties.

Two harmless cues were added to the existing empty `Cue List` because the request explicitly asked to create cues. No real audio/video/light/MIDI/network cue was fired, no settings were changed, and nothing was deleted.

## 1. Workspace identity and scope

| Requested | Observed |
|---|---|
| `MCP_bajada_Prueba` | Not present in QLab Launcher/Recent Workspaces or local filename search. |
| Project-linked QLab instance | `/Applications/QLab.app` |
| Open file | `mcp_prueba.qlab5` |
| Open list/window | `delete list` |
| Exact workspace UUID | `95F0A03D-140E-4673-974A-E76748EBB023` |
| Other running QLab instance | `/Users/filarmonica/Desktop/QLab.app`, `FILARMONICA.qlab5` (not inspected) |

This identity mismatch is the most important limitation. Any future MCP operation should resolve and verify the exact workspace UUID before reading or writing; a filename or human alias is not sufficient.

## 2. Workspace inventory

Initial UI inventory: **232 cues in 17 lists and carts**.

| List/cart | Children |
|---|---:|
| Main Cue List | 25 |
| MCP_LIGHT_WRITE_FIXTURE | 9 |
| MCP_VIDEO_WRITE_FIXTURE | 20 |
| MCP_AUDIO_WRITE_FIXTURE | 17 |
| MCP_GROUP_WRITE_FIXTURE | 7 |
| MCP_OTHER_WRITE_FIXTURE | 13 |
| fade | 22 |
| move | 1 |
| delete | 17 |
| delete list | 0 |
| Radar Spot 2026 | 7 |
| Proyeccion | 1 |
| Cue list vacia | 1 |
| Cue list cue group vacia | 2 |
| Cue cart vacia | 1 |
| PRUEBA List | 1 |
| Cue List | 0 |

The main window exposes Edit/Show mode, a GO button and standby display, the cue toolbox, the cue list, the sidebar, the inspector, Workspace Status, and Workspace Settings. The toolbox exposes Group, Audio, Mic, Video, Camera, Text, Light, Fade, Network, MIDI, MIDI File, Timecode, Start, Stop, Pause, Load, Reset, Devamp, GoTo, Target, Arm, Disarm, Wait, Memo, and Script.

## 3. Workspace Status and diagnostics

Workspace Status reported **117 Broken Cues and Warnings**. The visible categories included:

- missing audio, video, and MIDI files;
- missing audio input/output patches and missing MIDI patches;
- offline/missing video stages, routes, and output devices;
- a camera patch with no input device;
- invalid timecode output channel;
- missing cue targets and missing new targets;
- flagged light cues and a flagged group;
- invalid Light commands referencing unknown instruments;
- an invalid OSC Network cue whose custom message was not a legal OSC address;
- disconnected video routes to a missing destination.

The Logs tab was enabled but all logging toggles were off and the log area was empty. The Triggers tab showed QLab's default keyboard mappings (GO, preview, audition, load, panic, pause/resume, and cue-property editing). Art-Net discovery showed no nodes on the network. Video Metrics had no active rows.

The status screen is therefore a useful readiness source, but it is not a show-ready proof: it contains a mixture of missing assets, infrastructure defects, and intentional fixture warnings.

## 4. Workspace Settings observed (read-only)

No setting was edited.

### General

- Start a cue when the workspace opens: off.
- Start a cue before closing: off.
- Minimum time between GO: `0` seconds.
- Require key-up before re-arming GO: on.
- Panic duration: `1` second.
- Auto-number new cues: on, increment `1`.
- Auto-load new cues: off.
- Lock playhead to selection: on.
- File Management: automatic backups on, backup-before-save on, copy files into project folder on, rotate backups on.
- Display: medium cue-list rows and medium cart buttons; Active Cues sorted most-recently-started-last.

### Controls and access

- Workspace MIDI: Musical MIDI voice messages on, channel Any; MIDI Show Control on, device ID 0; no command mappings configured.
- Workspace OSC custom-command fields were blank and capture was off.
- OSC Access: OSC connections on; listening port `53000` TCP/UDP; Plain Text `53535` UDP. One passcode-protected access row had View/Edit/Control enabled. Passcode values are intentionally not recorded.
- Network Outputs: one OSC Message patch, UDP, `localhost:53000`, with an optional passcode. Passcode values are intentionally not recorded.
- Collaboration: enabled; ask before new collaborator on; Show Mode view-only restriction on; no connected collaborators.

### Templates

The Cue Templates screen listed all cue families. Defaults observed in the template inspector included:

- Light: duration `00:05.000`.
- Fade: duration `00:03.000`, target mode Cue.
- Wait: action duration `1` second and post-wait `1` second.
- Network: name template `1 · Patch 1 - {custom}`.
- Timecode: name `1:00:00:00`, action duration `01:00:03.600`.
- Audio, Video, MIDI File: file target required before duration becomes active.
- Group, Audio, Video, Camera, Text, MIDI, Start/Stop/Pause/Load/Reset/Devamp/GoTo/Target/Arm/Disarm/Memo/Script: zero or disabled duration depending on the cue type.

### Audio, video, and light infrastructure

- Audio Outputs: one MacBook Air system output patch, 2 channels, max `+12 dB`, min `-60 dB`.
- Audio Inputs: one MacBook Air system input patch, 1 channel.
- Audio Map `Stereo`: 1000×1000 map, marks Left `(-400,0)` and Right `(400,0)`, Patch 1 MacBook Air 2 Out. The monitor window was opened and closed without changing settings.
- Video stages: eight named stages routed to an offline `T749-fHD720` device plus `Stage 9` on the integrated Retina display.
- Output routes: integrated Retina, missing `22B1W`, NDI, missing Syphon, and missing `T749-fHD720`; all were Show off.
- Video devices: integrated Retina 2940×1912 at 60 fps and NDI 1920×1080.
- Video inputs: MacBook Air, OBS Virtual Camera, and an unselected third patch.
- Light patch: Art-Net instruments and groups (`Grupo1`, `Grupo2`, `LED1`–`LED3`, `bombilla`, `k`, `peluca`, `sombrerorito`, `Tejado`, and numbered instruments). Light definitions included American DJ `64B LED Pro - 3 channel` and Generic `Dimmer`. Dashboard MIDI showed no MIDI device.

## 5. Cue behavior observed

### Light fixture

`MCP_LIGHT_WRITE_FIXTURE` contained a Memo plus eight light cues. `L1` (`01 · Amanecer frío`) had duration 3 seconds and was flagged. Its Levels tab showed commands for `Grupo1`, `Grupo2`, `LED1.red`, `LED2.blue`, and `LED3.green`; collate previous light cues was on. The Curve tab reported a custom curve. This is a concrete example of a cue whose semantic payload is a set of instrument/channel values rather than a single scalar.

### Video and camera

`v5` (`Con slices`) targeted `video/Spot_Rumano.mp4`, used `Follow video clock`, Stage 3 (NDI), Fill Stage geometry, top layer, opacity 100%, media slicing, and visible slice loop counts. Its audio path used the MacBook Air patch. A camera cue used Video Input Patch 1 (MacBook Air) and an unpatched audio input, with output to a Syphon stage. A text cue contained `**Mcp video text` with centered alignment and a 507×152 cue size.

### Audio and fades

The valid Jungkook audio cue targeted `audio/Jungkook - Standing Next to You.mp3`, was flagged, used Patch 1 MacBook Air, and showed sliced playback, integrated fade, preserve pitch, and a non-unity main level. Its Fade cue targeted the audio cue, used a 3-second absolute fade, set levels from the target, and stopped the target when done. This demonstrates that Fade carries target and post-action semantics in addition to curve/level data.

### Groups and playlists

`MCP_GROUP_WRITE_FIXTURE` contained nested groups and two playlists. One playlist had Auto-shuffle, Loop-until-stopped, and Crossfade enabled with a 3-second crossfade and S-curves. A nested group (`grupo cuidado` → `subgrupo`) contained two audio cues, one with a long pre-wait. The group inspector exposed Timeline mode and the “start all children simultaneously and advance playhead” behavior.

### Cue List versus Cue Cart

The empty `Cue List` used a GO button and a vertical cue list. Its Continue control was disabled with the reason “Cue Lists must be set to Do not continue.” The `Cue cart vacia` opened a different grid UI: a Preview button, 16 visible grid slots, one Memo cue in the first slot, and 15 empty cue buttons. Its inspector likewise disabled Continue with the reason “Cue Carts must be set to Do not continue.” `Cue list cue group vacia` was a Group cue container with two children, not a cart.

### Control cues

`MCP_OTHER_WRITE_FIXTURE` showed Start, Stop, Pause, Load, Reset, GoTo, Target, Arm, Disarm, Wait, and audio cues. The Target fixture had no target and was warned. A separate MIDI cue had an unpatched MIDI output, Musical MIDI Voice Message mode, Note On, channel 1, byte 1 `60`, and byte 2 `64`. The Timecode fixture displayed name `1:00:00:00` and duration `01:00:03.600`.

### Network cue

The fixture Network cue (`58`, `1 · Patch 1 - {custom}`) showed a Settings tab with Patch 1, OSC Message / UDP routing, no fade, and an editable custom OSC Message field. The cue's visible warning was the invalid `{custom}` address. The UI exposed a Send/Preview button; it was not pressed.

## 6. Explicit test-cue mutation

The empty `Cue List` was selected before mutation and showed **0 children**.

Created through the QLab toolbox:

1. Cue `120`, Wait cue, renamed `CUA_RESEARCH_WAIT`. Defaults observed: action duration `00:01.000`, post-wait `00:01.000`, no target, Do not continue, armed.
2. Cue `121`, Memo cue, renamed `CUA_RESEARCH_MEMO`. Duration `0`, no target, Do not continue, armed.

After creation the workspace showed **234 cues**, and `Cue List` showed 2 children. The list GO button was clicked once to observe the no-output behavior. After the wait/memo sequence finished, QLab showed `[no cue on standby]`, no active cues, and no selected cue. No audio, video, light, MIDI, or network output was intentionally triggered.

The two cues were left in the workspace; they were not deleted because deletion was outside the requested scope.

## 7. Implications for the MCP project

1. **Resolve identity first.** Require exact workspace UUID/readiness before a query or write; surface a clear mismatch when a requested alias such as `MCP_bajada_Prueba` is not the front-most/open workspace.
2. **Make status part of readiness.** Aggregate missing files, patches, stages, routes, targets, invalid OSC addresses, and offline devices into typed warning categories. A green transport response cannot imply show readiness.
3. **Model infrastructure separately from cue fields.** Audio patches, video stages/routes/devices, light instruments/groups, MIDI patches, OSC patches, and file targets are separate dependencies and should be validated before cue mutation.
4. **Preserve typed cue families.** Group/Playlist, Fade, Network, MIDI, Timecode, Light, and sliced Audio/Video cues expose different settings and defaults. Avoid a generic unvalidated property bag.
5. **Expose safe fixture workflows.** A dedicated empty list with no-output Wait/Memo cues is a useful GUI/runtime smoke fixture. Keep it separate from lists containing external outputs.
6. **Redact access secrets.** OSC passcodes appeared in QLab's inspector/settings UI but are not copied into reports, tool results, logs, or prompts.
7. **Separate inspection from playback.** GUI inspection and Preview/Send controls are distinct. The investigation did not use real cue playback; an MCP read or readiness tool should not implicitly GO, preview, panic, or send output.
8. **Improve observability.** Workspace Status, Logs, Art-Net discovery, and Video Metrics are valuable evidence channels and should be represented as diagnostics with freshness/limitations, not as unqualified booleans.

## 8. Limits and follow-up

- This is a snapshot of `mcp_prueba.qlab5`, not the requested `MCP_bajada_Prueba` workspace.
- The GUI was inspected through accessibility state; no live OSC round-trip, MCP tool call, or AppleScript query was used during this pass.
- No physical output, external device, or network receiver was validated.
- The 117 warnings may include intentionally incomplete fixture cues; they are evidence for readiness classification, not proof that the entire workspace is unusable.
- Follow-up should first identify/open the exact `MCP_bajada_Prueba` file, record its workspace UUID, and repeat the same inventory with the same no-output boundary.

## References

- Repository-local QLab 5.5 manual snapshot: [`docs/sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf`](../../sources/qlab-5.5.10/reference/QLab_5_Reference_Manual.local-snapshot.pdf)
- Repository-local OSC dictionary: [`docs/sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md`](../../sources/qlab-5.5.10/osc/qlab_osc_dictionary.repository.md)
- Repository-local AppleScript dictionary: [`docs/sources/qlab-5-applescript/applescript_dictionary_v5.local.html`](../../sources/qlab-5-applescript/applescript_dictionary_v5.local.html)
- [QLab 5 Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
