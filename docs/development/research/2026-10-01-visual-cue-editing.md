# Video, Camera and Text inspector editing — 2026-10-01

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Evidence and scope

Implementation sources are `write/registry.py`, the generic `write/operations.py`,
the existing visual write-family modules, `write/control.py`, and the new
`write/visual.py`. The local official OSC dictionary is
`docs/references/qlab_osc_dictionary.md` (Video: geometry/I/O/effects around
4750–5275; Camera 5275–5315; Text 5315–5520; shared audio timing/levels/slices
around 4200–4600). No new dependency, package version or release.

Computer Use consulted the running `<redacted-local-path-2e4542d9aa>.app`,
QLab 5.5.10. `/Applications/QLab.app` was a different instance with a port-conflict
alert; it was not used for workspace testing. The inspected test workspace was
`<redacted-local-path-851cab375f>.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`, Edit Mode, zero active cues. Other open
workspaces were untouched. UI use only selected cues, lists and inspector tabs.

## Inspector comparison

| Inspector area | Observed UI | Specialized editing |
| --- | --- | --- |
| Basics | Text/Camera duration editable; video clip duration derived; image duration editable | Common Basics plus duration only when allowsEditingDuration is true |
| Triggers | Hotkey, MIDI, Wall Clock, Timecode, Fade & Stop, Duck, Second Trigger | OSC duck/fade-time/second-trigger/timecode values; scope requires integer readback; external trigger setup and activation excluded |
| I/O | Camera video input, audio input, input count/offset, stage and audio output | Exact workspace UUID routing; input count/offset remain blocked pending reliable device bounds |
| Geometry | Fill Stage or custom positioning, layer, opacity, smooth, fit/fill/stretch | Composite or individual geometry, unit quaternion, rotation reset, saved framing |
| Video Time & Loops | Trim times, loop count, rate, preserve pitch, hold, integrated fade, slices | Existing scalar timing gates migrated; indexed slice edits use the existing spacing/trim validator |
| Levels | Audio main/outputs/crosspoints and mute/solo | One selected indexed cell/channel per property; patch cueOutputChannels bounds; clears verify empty lists |
| Text | Content, font/color/background, alignment, width, line spacing | Typed attributes; full fragments establish prior style; absent or mixed scalar baseline blocks its setter |
| Audio FX / Video FX | Effect inspector tabs | Existing effect enabled scalar by index; creation/deletion/reordering/parameters and Audio FX remain pending |
| Objects / audio maps | Inspector exposes related spatial/routing controls | Audio Maps excluded; spatial-object editing not added |

Direct UI examples: Text v1 `Mcp video text`, center alignment and automatic width;
Camera v6 video input Patch 1, audio input unpatched, one input at channel 1,
stage marked missing, audio output Patch 1; Video v8 displayed 04:44.080,
start zero, rate 1, one play, hold/integrated-fade/preserve-pitch off. Several
fixtures are broken; healthy fixtures were chosen for writes. UI agreement does
not establish GO readiness or every possible inspector combination.

## Migration and remaining catalog entries

The dedicated tools use 1–50 distinct exact UUIDs and typed properties, with no
public profile or raw address. They reuse the sequential Control writer and
its signed five-minute single-use tokens. All items preflight before the first
setter. Pairs of coordinate components are consolidated into one composite setter.
Unknown values, incorrect types, active cues or stale dependencies block
writes. Each setter prepares alwaysReply on the same connection and verifies
fresh state; no automatic retry or rollback. Generic editing is preserved.

All previously executable visual families are represented: opacity,
translation, geometry/scalars, appearance, I/O, timing, integrated fade, slices,
audio levels, metadata, mute/solo and the approved Text style scalars. The full
generic catalog also contains actions with no validated generic real-write
path; exposing an inventory entry does not make it executable. Those remain
pending/excluded, rather than being converted to raw OSC writes.

Text scalar style edits require every fragment to contain the same requested
attribute. Fragment ranges are preserved in baseline evidence; content writes
verify first-character format inheritance. No guessed defaults are introduced.
File targets require existing absolute files under QLAB_ALLOWED_FILE_ROOTS.
Retargeting and media-dependent changes require separate calls. Audio numeric
readback tolerates 0.001 dB, matching existing QLab quantization handling.
Camera channelOffset/channels are typed but explicitly blocked, since this
implementation lacks validated input-device bounds.

### Implemented typed properties

**Video**: `addSliceMarker`, `anchor`, `anchor/x`, `anchor/y`, `armed`, `audioOutputPatchID`, `autoLoad`, `blendMode`, `clockType`, `colorName`, `continueMode`, `crop`, `cropBottom`, `cropLeft`, `cropRight`, `cropTop`, `deleteSliceMarker`, `deleteSliceMarkers`, `doFade`, `duckLevel`, `duckOthers`, `duckTime`, `duration`, `endTime`, `fadeAndStopOthers`, `fadeAndStopOthersTime`, `fileTarget`, `fillStage`, `fillStyle`, `flagged`, `gang`, `holdLastFrame`, `infiniteLoop`, `inputChannelName`, `lastSlicePlayCount`, `layer`, `level`, `lockFadeToCue`, `mute/channel`, `mute/channel/clear`, `name`, `notes`, `number`, `opacity`, `origin`, `origin/x`, `origin/y`, `playCount`, `postWait`, `preWait`, `preserveAspectRatio`, `preservePitch`, `quaternion`, `rate`, `resetRotation`, `scale`, `scale/x`, `scale/y`, `secondColorName`, `secondTriggerAction`, `secondTriggerOnRelease`, `skipIfDisarmed`, `sliceMarker/playCount`, `sliceMarker/time`, `sliderLevel`, `smooth`, `solo/channel`, `solo/channel/clear`, `stageID`, `startTime`, `timecodeTrigger/bits`, `timecodeTrigger/frames`, `timecodeTrigger/hours`, `timecodeTrigger/minutes`, `timecodeTrigger/seconds`, `timecodeTrigger/text`, `translation`, `translation/x`, `translation/y`, `useSecondColor`, `videoEffectIndex/enabled`.

**Camera**: `anchor`, `anchor/x`, `anchor/y`, `armed`, `audioInputPatchID`, `audioOutputPatchID`, `autoLoad`, `blendMode`, `channelOffset`, `channels`, `colorName`, `continueMode`, `crop`, `cropBottom`, `cropLeft`, `cropRight`, `cropTop`, `duckLevel`, `duckOthers`, `duckTime`, `duration`, `fadeAndStopOthers`, `fadeAndStopOthersTime`, `fillStage`, `fillStyle`, `flagged`, `gang`, `inputChannelName`, `layer`, `level`, `mute/channel`, `mute/channel/clear`, `name`, `notes`, `number`, `opacity`, `origin`, `origin/x`, `origin/y`, `postWait`, `preWait`, `preserveAspectRatio`, `quaternion`, `resetRotation`, `scale`, `scale/x`, `scale/y`, `secondColorName`, `secondTriggerAction`, `secondTriggerOnRelease`, `skipIfDisarmed`, `sliderLevel`, `smooth`, `solo/channel`, `solo/channel/clear`, `stageID`, `timecodeTrigger/bits`, `timecodeTrigger/frames`, `timecodeTrigger/hours`, `timecodeTrigger/minutes`, `timecodeTrigger/seconds`, `timecodeTrigger/text`, `translation`, `translation/x`, `translation/y`, `useSecondColor`, `videoEffectIndex/enabled`, `videoInputPatchID`.

**Text**: `anchor`, `anchor/x`, `anchor/y`, `armed`, `autoLoad`, `blendMode`, `colorName`, `continueMode`, `crop`, `cropBottom`, `cropLeft`, `cropRight`, `cropTop`, `duckLevel`, `duckOthers`, `duckTime`, `duration`, `fadeAndStopOthers`, `fadeAndStopOthersTime`, `fillStage`, `fillStyle`, `fixedWidth`, `flagged`, `layer`, `name`, `notes`, `number`, `opacity`, `origin`, `origin/x`, `origin/y`, `postWait`, `preWait`, `preserveAspectRatio`, `quaternion`, `resetRotation`, `scale`, `scale/x`, `scale/y`, `secondColorName`, `secondTriggerAction`, `secondTriggerOnRelease`, `skipIfDisarmed`, `smooth`, `stageID`, `text`, `text/format/alignment`, `text/format/backgroundColor`, `text/format/color`, `text/format/fontFamilyAndStyle`, `text/format/fontName`, `text/format/fontSize`, `text/format/lineSpacing`, `text/format/shadowBlurRadius`, `text/format/shadowColor`, `text/format/shadowOffset`, `text/format/shadowOffset/height`, `text/format/shadowOffset/width`, `text/format/strikethroughColor`, `text/format/strikethroughStyle`, `text/format/underlineColor`, `text/format/underlineStyle`, `timecodeTrigger/bits`, `timecodeTrigger/frames`, `timecodeTrigger/hours`, `timecodeTrigger/minutes`, `timecodeTrigger/seconds`, `timecodeTrigger/text`, `translation`, `translation/x`, `translation/y`, `useSecondColor`, `videoEffectIndex/enabled`.

### Additional generic inventory

This table preserves all registry entries beyond the typed specialized surface.
A generic catalog entry can describe a deprecated, read-only, pending or unsafe
action. Its reason is evidence of the current policy, not a new API promise.

| Family | Registry entry | Current registry policy |
| --- | --- | --- |
| video | `tempDuration` | Generic family property; not migrated to typed API |
| video | `setDefaultLevels` | video_audio_level_bulk_requires_full_runtime_validation |
| video | `setSilentLevels` | video_audio_level_bulk_requires_full_runtime_validation |
| video | `lastSliceInfiniteLoop` | last_slice_semantics_need_runtime_validation |
| video | `sliceMarkers` | slice_marker_collection_not_directly_settable_use_sliceMarker_operations |
| video | `stage/name` | stage_name_changes_need_visual_validation |
| video | `stage/region/bounds` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/origin` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/origin` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/origin` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/origin/x` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/origin/x` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/origin/x` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/origin/y` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/origin/y` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/origin/y` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/size` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/size` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/size` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/size/height` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/size/height` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/size/height` | stage_region_changes_need_visual_validation |
| video | `stage/region/bounds/size/width` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/bounds/size/width` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/bounds/size/width` | stage_region_changes_need_visual_validation |
| video | `stage/region/enableGrid` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/enableGrid` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/enableGrid` | stage_region_changes_need_visual_validation |
| video | `stage/region/enableGuide` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/enableGuide` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/enableGuide` | stage_region_changes_need_visual_validation |
| video | `stage/region/moveBy` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/moveBy` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/moveBy` | stage_region_changes_need_visual_validation |
| video | `stage/region/resetControlPoints` | stage_region_changes_need_visual_validation |
| video | `stage/regionID/resetControlPoints` | stage_region_changes_need_visual_validation |
| video | `stage/regionIndex/resetControlPoints` | stage_region_changes_need_visual_validation |
| video | `surfaceID` | surface_refs_need_dedicated_resolution |
| video | `surfaceName` | surface_refs_need_dedicated_resolution |
| video | `stageName` | patch_or_map_refs_need_dedicated_resolution |
| video | `stageNumber` | patch_or_map_refs_need_dedicated_resolution |
| video | `videoOutputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| video | `videoOutputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| video | `videoOutputPatchID` | patch_or_map_refs_need_dedicated_resolution |
| video | `videoEffects/add` | video_effect_changes_need_visual_validation |
| video | `videoEffects/insert` | video_effect_changes_need_visual_validation |
| video | `videoEffect/delete` | video_effect_changes_need_visual_validation |
| video | `videoEffectIndex/delete` | video_effect_changes_need_visual_validation |
| video | `videoEffect/enabled` | video_effect_changes_need_visual_validation |
| video | `videoEffect/move` | video_effect_changes_need_visual_validation |
| video | `videoEffectIndex/move` | video_effect_changes_need_visual_validation |
| video | `videoEffect/parameter` | video_effect_parameters_need_profile_specific_validation |
| video | `videoEffectIndex/parameter` | video_effect_parameters_need_profile_specific_validation |
| video | `videoEffect/parameters` | video_effect_parameters_need_profile_specific_validation |
| video | `videoEffectIndex/parameters` | video_effect_parameters_need_profile_specific_validation |
| camera | `tempDuration` | Generic family property; not migrated to typed API |
| camera | `audioInputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `audioInputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| camera | `fileTarget` | file_paths_need_dedicated_safety_policy |
| camera | `audioOutputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `audioOutputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| camera | `audioMapName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `audioMapNumber` | patch_or_map_refs_need_dedicated_resolution |
| camera | `audioMapID` | patch_or_map_refs_need_dedicated_resolution |
| camera | `doFade` | integrated_fade_changes_playback_behavior |
| camera | `lockFadeToCue` | integrated_fade_changes_playback_behavior |
| camera | `lastSlicePlayCount` | slice_editing_needs_dedicated_validation |
| camera | `lastSliceInfiniteLoop` | slice_editing_needs_dedicated_validation |
| camera | `patch` | deprecated_use_audioOutputPatchNumber |
| camera | `sliceMarkers` | slice_marker_collection_not_directly_settable_use_sliceMarker_operations |
| camera | `doLevel` | audio_levels_can_affect_live_output |
| camera | `mute` | mute_changes_audio_output |
| camera | `solo` | solo_changes_audio_output |
| camera | `mute/clear` | mute_changes_audio_output |
| camera | `mute/object/clear` | mute_changes_audio_output |
| camera | `solo/clear` | solo_changes_audio_output |
| camera | `solo/object/clear` | solo_changes_audio_output |
| camera | `setDefaultLevels` | audio_levels_can_affect_live_output |
| camera | `setSilentLevels` | audio_levels_can_affect_live_output |
| camera | `sliceMarker` | slice_editing_needs_dedicated_validation |
| camera | `sliceMarker/time` | slice_editing_needs_dedicated_validation |
| camera | `sliceMarker/playCount` | slice_editing_needs_dedicated_validation |
| camera | `addSliceMarker` | slice_editing_needs_dedicated_validation |
| camera | `deleteSliceMarker` | destructive_slice_editing_needs_dedicated_validation |
| camera | `deleteSliceMarkers` | destructive_slice_editing_needs_dedicated_validation |
| camera | `object/name` | spatial_audio_changes_output |
| camera | `objectID/name` | spatial_audio_changes_output |
| camera | `object/colorName` | spatial_audio_changes_output |
| camera | `objectID/colorName` | spatial_audio_changes_output |
| camera | `object/position` | spatial_audio_changes_output |
| camera | `objectID/position` | spatial_audio_changes_output |
| camera | `object/position/x` | spatial_audio_changes_output |
| camera | `object/position/y` | spatial_audio_changes_output |
| camera | `objectID/position/x` | spatial_audio_changes_output |
| camera | `objectID/position/y` | spatial_audio_changes_output |
| camera | `object/spread` | spatial_audio_changes_output |
| camera | `objectID/spread` | spatial_audio_changes_output |
| camera | `objectLevel` | audio_levels_can_affect_live_output |
| camera | `objectIDLevel` | audio_levels_can_affect_live_output |
| camera | `doObjectLevel` | audio_levels_can_affect_live_output |
| camera | `doObjectIDLevel` | audio_levels_can_affect_live_output |
| camera | `mute/object` | mute_changes_audio_output |
| camera | `mute/objectID` | mute_changes_audio_output |
| camera | `solo/object` | solo_changes_audio_output |
| camera | `solo/objectID` | solo_changes_audio_output |
| camera | `audioOutputPatch/cueOutputChannels` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/level` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/mute` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/solo` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/mute/clear` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/solo/clear` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/reset` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/routing/reset` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioOutputPatch/name` | audio_patch_routing_needs_dedicated_validation |
| camera | `audioMap/filter/position` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/filter/passthrough` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/name` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/name` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/colorName` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/colorName` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/position` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/position` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/position/x` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/position/y` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/position/x` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/position/y` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/object/spread` | audio_map_editing_needs_dedicated_validation |
| camera | `audioMap/objectID/spread` | audio_map_editing_needs_dedicated_validation |
| camera | `fileTarget` | file_paths_need_dedicated_safety_policy |
| camera | `holdLastFrame` | video_playback_visual_state_needs_validation |
| camera | `clockType` | video_phase2_dry_run_only |
| camera | `stage/name` | stage_name_changes_need_visual_validation |
| camera | `stage/region/bounds` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/origin` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/origin` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/origin` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/origin/x` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/origin/x` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/origin/x` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/origin/y` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/origin/y` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/origin/y` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/size` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/size` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/size` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/size/height` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/size/height` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/size/height` | stage_region_changes_need_visual_validation |
| camera | `stage/region/bounds/size/width` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/bounds/size/width` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/bounds/size/width` | stage_region_changes_need_visual_validation |
| camera | `stage/region/enableGrid` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/enableGrid` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/enableGrid` | stage_region_changes_need_visual_validation |
| camera | `stage/region/enableGuide` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/enableGuide` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/enableGuide` | stage_region_changes_need_visual_validation |
| camera | `stage/region/moveBy` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/moveBy` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/moveBy` | stage_region_changes_need_visual_validation |
| camera | `stage/region/resetControlPoints` | stage_region_changes_need_visual_validation |
| camera | `stage/regionID/resetControlPoints` | stage_region_changes_need_visual_validation |
| camera | `stage/regionIndex/resetControlPoints` | stage_region_changes_need_visual_validation |
| camera | `surfaceID` | surface_refs_need_dedicated_resolution |
| camera | `surfaceName` | surface_refs_need_dedicated_resolution |
| camera | `stageName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `stageNumber` | patch_or_map_refs_need_dedicated_resolution |
| camera | `videoOutputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `videoOutputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| camera | `videoOutputPatchID` | patch_or_map_refs_need_dedicated_resolution |
| camera | `videoEffects/add` | video_effect_changes_need_visual_validation |
| camera | `videoEffects/insert` | video_effect_changes_need_visual_validation |
| camera | `videoEffect/delete` | video_effect_changes_need_visual_validation |
| camera | `videoEffectIndex/delete` | video_effect_changes_need_visual_validation |
| camera | `videoEffect/enabled` | video_effect_changes_need_visual_validation |
| camera | `videoEffect/move` | video_effect_changes_need_visual_validation |
| camera | `videoEffectIndex/move` | video_effect_changes_need_visual_validation |
| camera | `videoEffect/parameter` | video_effect_parameters_need_profile_specific_validation |
| camera | `videoEffectIndex/parameter` | video_effect_parameters_need_profile_specific_validation |
| camera | `videoEffect/parameters` | video_effect_parameters_need_profile_specific_validation |
| camera | `videoEffectIndex/parameters` | video_effect_parameters_need_profile_specific_validation |
| camera | `cameraPatch` | camera_patch_refs_need_dedicated_resolution |
| camera | `videoInputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| camera | `videoInputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| text | `tempDuration` | Generic family property; not migrated to typed API |
| text | `holdLastFrame` | video_playback_visual_state_needs_validation |
| text | `audioOutputPatchID` | video_io_requires_confirm_token |
| text | `clockType` | video_phase2_dry_run_only |
| text | `text/format` | rich_text_format_needs_dedicated_validation |
| text | `fileTarget` | file_paths_need_dedicated_safety_policy |
| text | `holdLastFrame` | video_playback_visual_state_needs_validation |
| text | `audioOutputPatchID` | video_io_requires_confirm_token |
| text | `clockType` | video_phase2_dry_run_only |
| text | `stage/name` | stage_name_changes_need_visual_validation |
| text | `stage/region/bounds` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/origin` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/origin` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/origin` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/origin/x` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/origin/x` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/origin/x` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/origin/y` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/origin/y` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/origin/y` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/size` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/size` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/size` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/size/height` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/size/height` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/size/height` | stage_region_changes_need_visual_validation |
| text | `stage/region/bounds/size/width` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/bounds/size/width` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/bounds/size/width` | stage_region_changes_need_visual_validation |
| text | `stage/region/enableGrid` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/enableGrid` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/enableGrid` | stage_region_changes_need_visual_validation |
| text | `stage/region/enableGuide` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/enableGuide` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/enableGuide` | stage_region_changes_need_visual_validation |
| text | `stage/region/moveBy` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/moveBy` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/moveBy` | stage_region_changes_need_visual_validation |
| text | `stage/region/resetControlPoints` | stage_region_changes_need_visual_validation |
| text | `stage/regionID/resetControlPoints` | stage_region_changes_need_visual_validation |
| text | `stage/regionIndex/resetControlPoints` | stage_region_changes_need_visual_validation |
| text | `surfaceID` | surface_refs_need_dedicated_resolution |
| text | `surfaceName` | surface_refs_need_dedicated_resolution |
| text | `stageName` | patch_or_map_refs_need_dedicated_resolution |
| text | `stageNumber` | patch_or_map_refs_need_dedicated_resolution |
| text | `videoOutputPatchName` | patch_or_map_refs_need_dedicated_resolution |
| text | `videoOutputPatchNumber` | patch_or_map_refs_need_dedicated_resolution |
| text | `videoOutputPatchID` | patch_or_map_refs_need_dedicated_resolution |
| text | `videoEffects/add` | video_effect_changes_need_visual_validation |
| text | `videoEffects/insert` | video_effect_changes_need_visual_validation |
| text | `videoEffect/delete` | video_effect_changes_need_visual_validation |
| text | `videoEffectIndex/delete` | video_effect_changes_need_visual_validation |
| text | `videoEffect/enabled` | video_effect_changes_need_visual_validation |
| text | `videoEffect/move` | video_effect_changes_need_visual_validation |
| text | `videoEffectIndex/move` | video_effect_changes_need_visual_validation |
| text | `videoEffect/parameter` | video_effect_parameters_need_profile_specific_validation |
| text | `videoEffectIndex/parameter` | video_effect_parameters_need_profile_specific_validation |
| text | `videoEffect/parameters` | video_effect_parameters_need_profile_specific_validation |
| text | `videoEffectIndex/parameters` | video_effect_parameters_need_profile_specific_validation |

## Runtime finding

Repeated identical valuesForKeys identity queries on one authenticated TCP
session alternated successful replies and timeouts. This was reproduced using
read-only queries. No setter was sent in those failed attempts. Preparing
alwaysReply before fresh visual identity reads removed the failure in subsequent
full write/restore tests. The protocol documentation describes alwaysReply;
the observed repeated-query behavior is runtime evidence, not a definitive
claim about QLab internals. Getter replies still require data; only known setter
acknowledgements allow empty data. Preparation failures block writing.

## Verification

`docs/development/runtime-validation/2026-10-01-visual-cues.json` contains
redacted MCP results for dry runs, unique setters, fresh verification and
restoration. Live validation uses the source-loaded FastMCP Client against
QLab 5.5.10 over the authenticated TCP client. The installed MCP still requires
restart to load the new public tools. Tests cover schemas, invalid/stale tokens,
strict types, preflight failure, preparation failure, decimal geometry,
quantized levels, content-format binding and timeout without resend. Shared
transport tests cover UDP/TCP. No cue execution or external trigger signals.

A later Text verification test exposed a duplicate immediate `/text/format`
query after a successfully sent content setter. The batch stopped without
resending. A fresh detail read confirmed `Mcp video text audit`; a new restoration
dry run restored `Mcp video text`. Verification now reuses one fresh fragment
read, with a regression asserting exactly one query. A new full content change
and restoration subsequently passed. Both the failure and recovery remain in
the runtime JSON; they are not hidden by the successful final run.

UI recheck of Video v4 after restoration showed Custom Geometry, opacity 60%,
translation (-1035.8, 339.4) rounded by the UI, scale (1,1), anchor (0,0), zero
crop, layer top/1000 and Smooth enabled. Video FX showed Normal blend mode and
no effects. These values agree with the stored exact OSC baselines/readback.

## Follow-up: deep Video failures, 2026-10-02

The shared writer now normalizes OSC crop lists and integer preservePitch
readings, obtains the containing List/Cart Timecode format through fresh
identity-checked valuesForKeys, removes the duplicate immediate format check,
permits narrow mute/solo warning recovery and orders scale restoration before
enabling Preserve Aspect Ratio. Tests and reversible MCP validation confirm
these corrections. Missing slice inventories remain blocked, and QLab's
media-end acknowledgement error is retained even when fresh readback matches.
The float64 experiment failed and was removed; rounding alone is not a proven
internal cause of the boundary error. See
[the investigation and final evidence](../runtime-validation/2026-10-02-visual-cue-fixes.md).
