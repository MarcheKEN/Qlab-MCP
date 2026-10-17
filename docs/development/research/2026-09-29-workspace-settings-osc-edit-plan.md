# Workspace Settings OSC: research and editing plan

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

**Date:** 2026-09-29. **Status:** research and plan; no changes to QLab or tools.

## Scope and sources

Goal: replace the public `qlab_edit_workspace_settings` tool with specific editing for everything QLab documents through OSC in Workspace Settings, **except Audio Maps**. The `/settings/*` paths in the [official QLab 5 OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/), its [local copy](../../references/qlab_osc_dictionary.md), the [Workspace Settings manual](https://qlab.app/docs/v5/fundamentals/workspace-settings/) and the current MCP implementation were audited. The local copy declares “QLab 5; exact patch unknown” in [`manifest.json`](../../references/manifest.json); the current website includes QLab 5.6 material. Candidate paths require testing against the QLab version to be used. “Documented” does not mean “tested live.”

All writes must use `/workspace/{uuid}/settings/...`. An unprefixed path can reach multiple workspaces. The `patchID`, `routeID`, `stageID` and `regionID` selectors avoid name changes and variable indices. Verification reads use the exact property without arguments, except as noted below. The dictionary allows several loose boolean formats; the MCP API must accept strict booleans. Do not use `toggle`, `/live` or `+/-` variants as substitutes for the saved-value setter.

## Complete inventory excluding Audio Maps

**R/W** means the dictionary's `edit` column explicitly marks `read/write`. **Ambiguous** means a command is described but its edit permission is empty or inconsistent. Name/index forms are aliases of the same capability; the most stable selector is shown here.

| Area | Path relative to `/workspace/{uuid}` | Value, read and classification |
| --- | --- | --- |
| General | `/settings/general/minGoTime` | Finite number ≥ 0; read without a value; **R/W**. Already implemented. |
| General | `/settings/general/selectionIsPlayhead` | Boolean; read without a value; **R/W**. Changes the selection/playhead link. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/cueOutputChannels` | Integer 1–128; read without a value; **R/W**. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/level/{in}/{out}` | Numeric decibels or `-inf`; read without a value; **R/W**. Any string is interpreted as `-inf`, so MCP must only accept the literal `-inf`. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/mute/{output}` | Boolean for one physical output; read without a value; **R/W**. A form with channel and value as arguments also exists. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/solo/{output}` | Boolean for one physical output; read without a value; **R/W**. A form with channel and value as arguments also exists. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/name` | String; the text says “Set,” but the entire permission row is empty; read the name through patch detail; **ambiguous**. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/mute/clear`, `/solo/clear` | Actions on all outputs; the **current web dictionary marks `edit=read/write`**. Verify the result through `muteChannels`/`soloChannels`. The local copy loses the initial empty cell and visually shifts the row. |
| Audio, output patch | `/settings/audio/patchID/{patch_id}/reset`, `/routing/reset` | Actions described with empty permissions; **ambiguous**. Restore faded parameters rather than editing one specific property. |
| Video, route | `/settings/video/routeID/{route_id}/enableGuides` | Boolean; read without a value; **R/W**. |
| Video, stage | `/settings/video/stageID/{stage_id}/name` | String; read without a value; **R/W**. |
| Video, region | `/settings/video/stageID/{stage_id}/regionID/{region_id}/bounds` | Integer `x, y, width, height`; read without arguments; **R/W**. A string alternative exists. |
| Video, region | `.../bounds/origin`, `.../bounds/origin/x`, `.../bounds/origin/y` | Pair `x, y` or integer scalar; read without arguments; **R/W**. |
| Video, region | `.../bounds/size`, `.../bounds/size/width`, `.../bounds/size/height` | Pair `width, height` or integer scalar; read without arguments; **R/W**. |
| Video, region | `.../subregionIndex/{i}/controlPointIndex/{j}` | Integer pair `x, y`; read without arguments; **R/W**. These two subobjects are selected by index even when UUIDs select stage and region. |
| Video, region | `.../enableGrid`, `.../enableGuide` | Booleans; read without a value; **R/W**. |
| Video, region | `.../resetControlPoints` | Action described with empty permissions; **ambiguous**. |

Geometry and control-point integers must stay within the corresponding stage or area bounds. Composite and scalar forms of `bounds`, `origin` and `size` are alternative ways to modify the same geometry; they do not need duplicate MCP operations to cover that capability. Audio level has an additional `/live` form, marked `control`: it modifies the active value without editing the saved initial state or generating Undo. It is excluded from these saved-settings tools. Persistence semantics of `mute` and `solo` require checking in QLab.

**Read-only or no documented settings setter:** Audio `cueOutputChannelCounts`, `maxVolume`, `minVolume`, channel names, patch list/detail/routing, Mic input list; Video input patch list, routes, stages, stage size, route destination/device; Light Patch; Network and MIDI patch lists. There is no settings setter for audio device/routing, patch creation, video destination, Light Patch, OSC Access, Network Patch or MIDI Patch. The manual allows several of these to be edited in the UI, but that does not establish an OSC path.

**Cross-cutting actions:** `/settings/{general,audio,light,mic,midi,network,video}/undo` and `/redo` have empty permission rows and modify the area's shared history. They are not value setters with a unique postcondition. Outside `/settings`, `alwaysAudition`, `auditionMonitors` and `showMode` have OSC writes, but are operational controls; `/dashboard/setLight` controls lighting levels, not Light Settings editing. Controls, Audition, Collaboration and Templates have no documented `/settings/...` setter family. Audio Maps, including their test objects and `testObjectFileTarget`, remain outside scope by decision.

## Public tool decision

| Proposed tool | Operations | Reason |
| --- | --- | --- |
| `qlab_edit_workspace_general_settings` | `minGoTime`, `selectionIsPlayhead` | Two properties of the workspace itself. Replaces the current generic tool. |
| `qlab_edit_audio_output_patch` | `cueOutputChannels`, `level`, `mute`, `solo`, `clear_mutes`, `clear_solos` | All confirmed non-map Audio setters identify **one output patch**. The two clearing actions have verifiable collective postconditions. No global operation justifies another `qlab_edit_workspace_audio_settings`. |
| `qlab_edit_video_output_route` | `enableGuides` | Route UUID and existing `qlab_get_video_output_route` read. |
| `qlab_edit_video_stage` | `name` | Stage UUID and existing `qlab_get_video_stage` read. |
| `qlab_edit_video_region` | `bounds` or its parts, control point, `enableGrid`, `enableGuide` | Requires stage and region UUIDs and geometry validation different from route/stage validation. |

This separation covers the confirmed capability without duplicating operations in root `Audio Settings` or `Video Settings` tools. If a future version documents area-wide setters, add its root tool then. Do not create empty `Edit Light/Network/MIDI Settings` tools.

## Implementation plan

1. **Contract and General.** Replace `qlab_edit_workspace_settings` with `qlab_edit_workspace_general_settings`; move `minGoTime` without changing its tested behavior and add `selectionIsPlayhead` with a strict boolean. Update schema, contract tests and active documentation in the same change. Keep dated historical documents as historical evidence.
2. **Typed safety core.** Extract only what the new objects reuse: exact UUID, readiness, activity check, dry run, single-use token bound to workspace, object, property, baseline and requested value; one setter; fresh readback and an explicit timeout result. Current [`write_operations.py`](../../../src/qlab_mcp/settings/write_operations.py) compares `float32` and reads numbers; do not reuse that comparison for booleans, strings, `-inf` or tuples.
3. **Audio, one patch.** Obtain the UUID from `qlab_get_workspace_audio_settings`, read that patch with `view="output_patch"` and validate channels against it. Add the four R/W properties and two R/W clearing actions; the latter first read `muteChannels` or `soloChannels` and require an empty list after one action. Verify separately that level, mute and solo do not cause unexpected effects on an active output. Do not call `/live` or repeat a write with an ambiguous result.
4. **Video by object.** Add route `enableGuides`, stage `name` and region geometry/visibility. Read stage bounds before accepting coordinates; for control points, check that the selected indices still exist immediately before writing. One MCP call changes one property or one point. Verify by fresh readback and then on a test surface. The [QLab 5.5.10 comparison](2026-09-29-workspace-settings-live-comparison.md) shows different UI and OSC region coordinates: explicitly accept and return OSC coordinates without translating them to the UI until the transformation is demonstrated.
5. **Ambiguous commands.** Investigate `patch name`, `reset`, `routing/reset` and `resetControlPoints` in a disposable workspace only if that test with effects is expressly authorized. Record effective permissions, previous value, effect, independent readback and restoration. Publish only operations with reliable semantics and verification; global reset/undo actions do not automatically belong in property-editing tools.
6. **Contract closure.** Compare `Client(mcp).list_tools()` with documentation; run focused domain tests, the full suite and `git diff --check`; compare each tool against the actual QLab version before describing it as validated live.

**Planned files:** [`server.py`](../../../src/qlab_mcp/server.py), [`models.py`](../../../src/qlab_mcp/models.py), [`settings/write_registry.py`](../../../src/qlab_mcp/settings/write_registry.py), [`settings/write_operations.py`](../../../src/qlab_mcp/settings/write_operations.py), settings and contract tests, README, tool catalog, active architecture, status and safety policy. This investigation changes no code.

**Validation gates:** current OSC documentation → local schema/validation → dry run → QLab test in a rehearsal workspace with controlled effects → fresh readback → public documentation review. Documentary evidence alone never proves that QLab accepted or persisted a setter.

## Subsequent review: stage and patch creation — 2026-09-29

The local copy was compared against the [current official OSC dictionary](https://reference.qlab.app/docs/v5/scripting/osc-dictionary-v5/). No documented commands create stages, regions or audio patches. `/workspace/{id}/new` creates cues, lists or carts; its supported types do not include these Workspace Settings objects.

- **Existing stage:** `name` write; `size`, `size/width`, `size/height` and `regions` are reads. Editing region bounds does not change stage size or create a region.
- **Existing region:** bounds and components, control point by indices and grid/guide visibility. No setter is documented here for assigning its output route or changing its entire configuration.
- **Existing audio output patch:** name, cue output count, one crosspoint level, mute/solo and their clearing actions. Creating a patch or assigning another audio device is not documented.

Creation is documented in the UI: [New Video Stage](https://qlab.app/docs/v5/video/video-output/) and [New Output Patch](https://qlab.app/docs/v5/fundamentals/workspace-settings/). A future creation tool would require an additional path, researched and validated separately; wrapping existing OSC commands is insufficient.

Code review fixed omission of a `-inf` setter after a numeric minimum read and shared strict coordinate validation between region Get and Edit. These fixes have simulated-transport tests; they do not constitute new QLab write validation.
