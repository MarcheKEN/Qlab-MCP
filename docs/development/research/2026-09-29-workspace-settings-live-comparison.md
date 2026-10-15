# Workspace Settings: comparison of MCP, QLab and code

**Date:** 2026-09-29. **Observed workspace:** `redacted-workspace-6b31c91e.qlab5`, UUID `8E86FE91-668B-560C-B738-4D581B5A7498`, QLab 5.5.10. **Method:** read-only MCP tools, QLab inspection through Computer Use, code reading and five OSC queries without arguments to one region. No setters were sent, cues executed or workspace saved. The settings window was closed afterward. No screenshots or credentials were stored.

Capability sources: [official OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/), [Workspace Settings manual](https://qlab.app/docs/v5/fundamentals/workspace-settings/) and [earlier inventory and plan](2026-09-29-workspace-settings-osc-edit-plan.md). Live observations apply to QLab 5.5.10; the website may describe a later version.

## Observations

| Area | MCP / OSC in this workspace | QLab UI | Editing supported by OSC according to the dictionary |
| --- | --- | --- | --- |
| General | `minGoTime=0`, `selectionIsPlayhead=true`. | `0` seconds and “Lock playhead to selection” enabled: matching. Also includes GO key-up, panic duration, autoload, numbering, open/close actions, backups and display. | Only `minGoTime` and `selectionIsPlayhead`. The current public tool only writes `minGoTime`. |
| Audio Outputs | One output patch, its own UUID, 12 cue outputs, two outputs in routing, global limits +12/−60 dB. MCP detail: empty mutes and solos; crosspoint 1→1 at 0 dB. | One patch with 12 cue outputs, a two-output device, crosspoint matrix, Mute/Solo buttons, name, effects, channel names and +12/−60 dB limits. Comparable values match. | Per patch: `cueOutputChannels`, crosspoint `level`, `mute`, `solo`, clear mutes/solos. Global limits, effects, channel names, device and routing have no confirmed settings setter. The patch name command has undetermined permissions. |
| Audio Inputs | One input patch with a UUID. The connected MCP server incorrectly adds output-patch-only operations to input patch detail; local code no longer advertises them. | One input patch for the Mac microphone; the row only exposes Name and Device. | The Mic list is read-only; no input patch setter is documented. |
| Audio Maps | QLab has a dedicated screen. | Maps were not inspected or edited. | Excluded by scope. |
| Video Outputs | Nine stages and their UUIDs. One checked stage measures 960 × 110 and contains region A. | Nine stages. In the editor, that stage measures 960 × 110 and contains A. The UI also supports layer, size, mask, rendering, blend and route assignment. | Stage name; region geometry, control points and guides/grid. No OSC setter for overall size, mask, layer or stage/region creation/deletion. |
| Video Routing | Five routes and UUIDs. “Output 5” is disconnected and `enableGuides=false`. | Five routes; “Output 5” has no available device and guide “Show” is off. The editor offers name, resolution, rotation, rear projection, scaling and device. | Route `enableGuides`. Other visible fields have no confirmed OSC settings setter. |
| Video Inputs | Three input patches. | The Video Inputs section exists; not every patch was opened. | Read-only inventory. |
| Light | `qlab_get_workspace_light_settings` summarizes 28 instruments and 3 groups; items do not provide stable UUIDs in the normalized result. | Light Patch shows editable instruments, groups, addresses and outputs; Light Definitions and Light Dashboard MIDI also exist. | `/settings/light/patch` is a read. Light Dashboard commands control output levels, not Light Patch. |
| Network | One Network Patch with name/UUID. The connected MCP server returns `destination_present=null`, `destination_count=null` and `passcode_present=false`; local code returns `null` for both indicators when OSC omits those fields. | The patch has a `localhost` destination with a configured port; OSC Access shows configurable permissions and ports. The UI also shows a configured passcode, whose value was not copied. | The dictionary exposes the patch list, not destination or OSC Access setters. **`null` means the OSC payload cannot establish presence; it does not mean the value is missing in QLab.** The connected server's passcode `false` indicator contradicts the UI. |
| MIDI | The MCP list is empty. | MIDI Outputs is also empty; MSC Broadcast is enabled, with no destinations listed. | The patch list is read-only; no patch or broadcast setter is documented. |
| Controls, Audition, Collaboration, Templates | No MCP tools read these settings. | All four sections exist. Shortcuts/MIDI/OSC control, audition policies per output, collaboration permissions and cue templates were observed. | No equivalent `/settings/...` families exist in the OSC dictionary. Operational audition controls do not edit those policies. |

## Decisive finding: region coordinates

For region A of “Cuadro Superior” (stage `A41F907E-3E01-570E-A4BC-0B86C6A1922E`, region `8BBA6421-9F0E-5B2B-95F9-A99A99059A71`):

| View | Origin | Size |
| --- | --- | --- |
| QLab graphical editor, “Lower left” | `(-480, -55)` | `960 × 110` |
| `qlab_get_video_stage`, `boundsOnStage` | `(0, 0)` | `960 × 110` |
| Direct OSC `/settings/video/stageID/{stage}/regionID/{region}/bounds` and `/bounds/origin` | `(0, 0)` | `960 × 110` |

Direct OSC reads of `/bounds/size`, `/enableGrid` and `/enableGuide` also responded correctly; size was `960 × 110` and both booleans were `false`. The MCP summarizer copies `boundsOnStage` from the OSC payload without transforming coordinates ([`summarizers.py`](../../../src/qlab_mcp/settings/summarizers.py)). This is a difference between UI and OSC coordinate systems, not a discrepancy introduced by MCP. **The transformation was not tested at other positions**: the edit tool must clearly state that it accepts OSC coordinates and verify every value through the exact OSC property before offering UI equivalents.

## Implementation consequences

1. Current code only registers `general.minGoTime` as writable ([`write_registry.py`](../../../src/qlab_mcp/settings/write_registry.py)); the handler in [`write_operations.py`](../../../src/qlab_mcp/settings/write_operations.py) reads and compares numbers, so booleans, `-inf`, strings and geometry require new validation and comparison. Workspace Edit authorization observed through `qlab_check_connection` does not make a read-only path writable.
2. The actual hierarchy supports one General tool, another targeting **one audio output patch** by UUID, and video tools targeting a route, stage or region. Root-level `Edit Workspace Audio Settings` or `Edit Workspace Video Settings` would duplicate operations or be empty with documented OSC.
3. Current Get tools help discover UUIDs and some baselines, but a write requires reading the **exact property**: video overview does not include `enableGuides`; route detail does. Stage Get includes a region and `boundsOnStage`, but does not replace direct reading of `/bounds` or a selected control point.
4. The Network reader calculates `destination_present` by looking for destination keys in the received item ([`summarizers.py`](../../../src/qlab_mcp/settings/summarizers.py)); QLab 5.5.10 only returned name and ID. Treat that `false` as “not observed in OSC,” particularly in documentation or preflight. Do not use it to assert an absence of configuration in the UI.
5. Additional visible fields in General, Audio, Video, Light, Network, MIDI and Controls/Audition/Collaboration/Templates require another surface beyond documented OSC setters. An OSC editing tool must not promise complete screen coverage.

**Validation boundary:** reads and UI presence were verified; no new setter, persistence, physical effect, convergence or restoration was tested. The OSC inventory and plan remain documentary evidence for editing operations.

## Implementation review — 2026-09-29

Write validation in the disposable copy is recorded in `../runtime-validation/2026-09-29-workspace-settings.md`. This review inspected Audio → Audio Inputs and Network again through Computer Use, without editing their values. In Audio Inputs the UI only presents name and device; the connected server therefore exposes an incorrect contract by offering `name`, `cueOutputChannels`, `level`, `mute` and `solo` operations for that object. Local code and tests correctly separate Input Patch from Output Patch.

A fresh read of the connected server still gives `passcode_present=false`, although the UI shows the configured field; its value was deliberately omitted from the record. Local code and the focused test interpret an absent OSC key as unknown (`null`). For the destination, QLab shows a configured address while OSC omits the field: `destination_present=null` is correct. The connected server does not yet include every local fix; the MCP process must be reloaded to check them again on that surface.
