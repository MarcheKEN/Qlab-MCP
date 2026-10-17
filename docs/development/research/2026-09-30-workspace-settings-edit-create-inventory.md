# Workspace Settings: editing and creation through OSC or AppleScript

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-09-30. Scope: installed QLab 5.5.10. Research; no setters sent or objects created. Audio Maps remains excluded by project decision.

## Result

The five current public Edit tools cover the **persistent, bounded** Workspace Settings writes found in the OSC dictionary for General, Audio Output Patch and existing video objects. Neither OSC nor the installed AppleScript SDEF documents creation of patches, stages, routes, virtual devices, instruments, groups, definitions or MSC destinations. A `New…` button in QLab does not imply a scripting operation.

The dictionary does include additional reset actions, which can change several values at once. They are not considered verifiable single-property edits until all affected state can be read and restored. `/workspace/{id}/alwaysAudition`, `auditionMonitors` and `liveFadePreview` are operational workspace controls; **they do not edit output configuration in Workspace Settings → Audition**.

## Matrix by section

| UI section | Native editing found | Native creation found | MCP tool recommended now |
|---|---|---|---|
| General, File Management, Display | OSC `minGoTime` and `selectionIsPlayhead`; no setters found for other controls | Not applicable | Keep `qlab_edit_workspace_general_settings`; do not advertise complete General coverage |
| Controls: Keyboard, Workspace MIDI, OSC | No assignment setters found | Not applicable | No new Edit tool |
| Audition | No setters found for redirection by output type | Not applicable | No Audition Edit tool; `alwaysAudition` is a separate operational mode |
| Collaboration | No connection or permission setters found | Not applicable | No new Edit tool |
| Templates | No cue template setters found; Workspace Template Manager is a separate feature | No template creation found | No new Edit/Create tool |
| Audio Outputs | OSC: patch name, cue output count, crosspoint level, mute/solo and clearing | No `New Output Patch` found | Keep `qlab_edit_audio_output_patch` |
| Audio Inputs | OSC `/settings/mic/patchList` only reads name and UUID | No `New Input Patch` found | No new Edit/Create tool |
| Video Outputs | OSC: stage name and properties of an existing region | No `New Video Stage` or region creation found | Keep `qlab_edit_video_stage` and `qlab_edit_video_region` |
| Video Output Routing | OSC: existing route `enableGuides` | No `New Output Route` found | Keep `qlab_edit_video_output_route` |
| Video Output Devices | Destination metadata in route reads; no setters found | No `New Virtual Device` found | No new Edit/Create tool |
| Video Inputs | OSC `/settings/video/inputPatchList` only reads name and UUID | No `New Input Patch` found | No new Edit/Create tool |
| Light Patch, Definitions, Dashboard MIDI | OSC `/settings/light/patch` is a read; `/dashboard/setLight` controls Dashboard values, not patch editing | No `New Instrument`, `New Group` or `New` Definition found | No new Edit/Create tool |
| Network Outputs, OSC Access | OSC `/settings/network/patchList` is a read; no patch or OSC access setter found | No `New Network Patch` found | No new Edit/Create tool |
| MIDI Outputs, MSC Broadcast | OSC `/settings/midi/patchList` is a read; no patch or MSC destination setter found | No `New MIDI Patch` or `New Destination` found | No new Edit/Create tool |

In Audio Output, the name was tested in a disposable copy despite the ambiguous permission cell in the local dictionary. All five Edit tools were also tested there with subsequent readback and restoration; setter responses timed out, but were not resent. See the [validation record](../runtime-validation/2026-09-29-workspace-settings.md). This does not validate any new constructor.

## Exactly what can be written

- General: `/settings/general/minGoTime` and `/settings/general/selectionIsPlayhead`.
- Audio Output Patch by UUID: `name`, `cueOutputChannels` (1–128), `level/{in}/{out}`, `mute/{output}`, `solo/{output}`, `mute/clear`, `solo/clear`. MCP only accepts the literal `-inf` as a nonnumeric level.
- Video Output Route by UUID: `enableGuides`.
- Video Stage by UUID: `name`. `size` and its components are explicitly read-only.
- Video Region of a stage by UUID: `bounds`, `origin`, `size`, `x/y/width/height` components, control point by indices, `enableGrid`, `enableGuide`. OSC coordinates are used; they differ from the UI origin in the observed example.

Some `/cue/.../stage/...` commands modify the shared stage referenced by a cue. Most duplicate the operations above; `moveBy` allows decimal offsets. An earlier test showed warping-point translation and incomplete restoration, so no tool based on that shortcut is published. See [audio and video research](2026-09-29-workspace-audio-video-osc-applescript-capabilities.md) and the [`moveBy` test](../runtime-validation/2026-09-29-video-region-moveby.md).

`/settings/audio/patchID/{id}/reset`, `routing/reset` and `/settings/video/stageID/{id}/regionID/{id}/resetControlPoints` are documented, but affect sets of values. Undo/redo act on shared history. They are not substitutes for parameter Create/Edit.

## AppleScript: actual limitation

The installed SDEF declares `cue list` and `cue` elements for `workspace`, and state properties such as `edit mode`, `show mode`, `always audition` and `live fade preview`. Its QLab `make` takes a workspace and a **cue type**; it can create cue lists/carts, not Settings objects. The properties `audio output patch id`, `stage id`, `midi patch id` and `network patch id` belong to cues and select an existing object. There are no scriptable classes for Audio/Video/Network/MIDI patches, stages, routes, regions, instruments, definitions or MSC destinations. `setLight` acts on cues or Light Dashboard. The preference controller is commented out in the installed SDEF.

Using AppleScript with `System Events` to click `New…` would be UI automation, not a capability of the QLab AppleScript dictionary. It would change a tool's contract: it depends on focus, windows, language and visual state, and would require separate design and testing.

## Evidence and limitations

- [Official Workspace Settings manual](https://qlab.app/docs/v5/fundamentals/workspace-settings/): describes ten sections and each panel's creation buttons. The Network/MIDI manual calls them `New Output Patch`; the installed UI shows `New Network Patch` and `New MIDI Patch`.
- [Official OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/) and [local copy](../../references/qlab_osc_dictionary.md): `Workspace Settings messages` section, lines 1195–2545. Light, Mic, MIDI, Network and Video Input listings are read-only. `/workspace/{id}/new` (lines 1021–1039) creates a cue, not a Settings object.
- [Official AppleScript dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/) and installed SDEF `/Applications/QLab.app/Contents/Resources/QLab.sdef`: `workspace` class, lines 628–727; `make` command, lines 1887–1892.
- [Registered tools](../../../src/qlab_mcp/server.py): five `qlab_edit_*settings/patch/route/stage/region` functions around lines 1971–2073; [typed operations](../../../src/qlab_mcp/models.py) around lines 139–265.
- Computer Use: Workspace Settings was opened in an already open workspace; all ten sections and the cited `New…` buttons were observed, without activating them. Settings was closed afterward. No values changed or cues executed. This confirms the UI of this installation, not a hidden API.

The stated absence means **no documented operation in the two dictionaries examined**, not an absolute inability to automate QLab through other mechanisms. No reverse-engineering search or undocumented-command test was performed. There is no new tool to implement reliably within this scope. Extending toward complete creation requires choosing and validating another mechanism before designing MCP schemas.
