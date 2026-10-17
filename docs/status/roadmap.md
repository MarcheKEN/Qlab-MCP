# Roadmap — 2026-10-17

## Current contract

QLab MCP **0.4.0** exposes 79 tools: 49 reads and 30 gated writes. The [tool catalogue](../user/tools.md)
and generated schemas define their arguments; [architecture](../development/architecture.md)
describes implementation. Generic `qlab_edit_cues` and `qlab_edit_workspace_settings`
are retired. Use the typed cue-family and scoped workspace-settings editors.

Family editors share signed `confirm:controlCue:v1:` confirmations, exact UUIDs,
whole-batch preflight, sequential setters and fresh readback. They accept 1–50
unique cues and supported multiple properties; individual operations impose
additional restrictions. No automatic mutation retry or rollback is provided.
Workspace-settings editors use `confirm:workspaceSettings:v1:` and one operation
per request. Native document operations have a separate token and preflight.

The [October 17 installed-MCP pass](../development/runtime-validation/2026-10-17-installed-mcp-acceptance.md)
invoked every tool and exercised real writes through 26 of the 30 writers.
Its coverage is representative; remaining per-operation gaps below are not
closed by tool invocation alone. The pass changed no code and tested no playback.

## Supported work and remaining gates

| Area | Current scope | Remaining evidence or capability limits |
| --- | --- | --- |
| Visual geometry | Typed components/aggregates, crop, smooth, aspect ratio, blend, quaternion/reset | [Video geometry](../development/runtime-validation/2026-10-01-visual-cues.md) and [restoration fixes](../development/runtime-validation/2026-10-02-visual-cue-fixes.md) have bounded proof. Camera/Text combinations require their individual evidence; relative rotate, shutter and additional reset actions remain excluded. |
| I/O and media | Existing stage/input/output selections and typed Audio/Video/MIDI File file targets | [Mic input restoration](../development/runtime-validation/2026-10-05-remaining-cue-completion.md) does not validate every patch combination. Unknown capacity/ownership blocks dependent channel/object edits. |
| Video timing/audio | Timing, loops, clock, Integrated Fade flags, readable levels and mute/solo | [October 1](../development/runtime-validation/2026-10-01-visual-cues.md) records clock/fade/lock/mute; [October 2](../development/runtime-validation/2026-10-02-visual-cue-fixes.md) records pitch and mute recovery/clear. Solo/solo-clear still need proof. Exact-media-end `endTime` can return an explicit error despite matching restoration readback. Envelope curves, Audio FX, Trim and level reset actions remain excluded. |
| Slices | Typed Audio/Video marker operations with fresh inventory | [Two Audio count changes](../development/runtime-validation/2026-10-05-remaining-cue-completion.md) were restored. A healthy Video fixture with readable markers and other creation/deletion/time/last-slice cases remain to be tested. Missing inventory is not an empty baseline. |
| Text | Full/fragment formatting, UTF-16 ranges, percentages, bounded Latin words and observed font mappings | [October 11 selectors](../development/runtime-validation/2026-10-11-text-selections.md) and [October 14 limits](../development/runtime-validation/2026-10-14-editor-completion.md) retain emoji/non-Latin fallback and unreadable shadow gates. |
| Video FX | 60-effect/262-parameter catalogue, indexed metadata and typed parameter/stack edits | [58 creation defaults and 55 restorations](../development/runtime-validation/2026-10-09-fx-empty-stack-creation.md) are fixture-specific. LinearKey/DropShadow creation, ambiguous identity, unknown native keys and unverified reconstruction remain blocked. |
| Group and root containers | Typed Group/Playlist, Cue List/Cart create/edit/reorder | Mode/child-snapshot checks remain. Cart cell Move execution and unattended root List/Cart deletion remain blocked; moving sidebar roots does not move cells. |
| Other cue families | Audio/Mic/Light/Fade/Network/MIDI/MIDI File/Timecode/Script typed editors | The [completion report](../development/runtime-validation/2026-10-05-remaining-cue-completion.md) records individual live gaps. Unknown device/command/range metadata blocks MSC/Device Definition operations. Script source/compilation is excluded. |
| Native cue fields | Fixed local Load Time, assigned number and opt-in native Triggers | [Field](../development/runtime-validation/2026-10-10-control-applescript.md) and [Trigger](../development/runtime-validation/2026-10-10-native-triggers.md) proof is bounded. Hotkey enabling/assignment needs key/modifier identity; weekdays, capture and arbitrary scripts remain excluded. |
| Workspace Settings | General, Audio output patch, Video route/stage/region edits | [September 29](../development/runtime-validation/2026-09-29-workspace-settings.md) gives limited reversible proof; the October 17 pass repeats one operation through each of the five editors. Audio Maps and Light/Network/MIDI settings writers remain excluded. |
| Native documents | Exact local inventory, bounded Open/Save/clean-Close | Document Get, Save preview and dirty-Close/nonempty-Open blocking were observed in the October 17 pass. Actual Open/Save/Close events remain unvalidated by these reports. |
| Local analysis | Consent-based media search and optional paged audio analysis | Optional Python dependencies and FFmpeg/ffprobe are required for real decoding. Measurements are source-relative; they do not classify lyrics or establish playback/hardware behavior. |

## Active validation

- [017 — Camera/Text smooth and geometry limits](workorders/active/017_geometry_completion_smooth_and_defaults.md).
- [019 — Remaining I/O combinations](workorders/active/019_video_io_selection_edit_cues.md).
- [021 — Remaining timing cases and media-end behavior](workorders/active/021_video_audio_time_loops.md).
- [022 — Readable marker fixtures and untested operations](workorders/active/022_slice_markers_audio_video.md).
- [029 — Video solo and remaining audio recovery cases](workorders/active/029_video_audio_runtime_validation.md).
- [007 — Residual Text/FX prerequisites](workorders/blocked/007_text_style_and_video_fx_read_plan.md).

Use the [staged authoring workflow](../user/workspace-authoring.md) for reviews
and authorized edits. Capabilities, deterministic plans and automated tests do
not prove every setter works in every show. QLab 5.5.10 reports establish only
their stated fixtures; playback, hardware output and QLab 5.6 support remain
unclaimed. This documentation refresh performs no live QLab writes.

## Historical plans

The [historical phase roadmap](../archive/plans/2026-10-14-historical-phase-roadmap.md)
preserves earlier plans, counts and tokens. Its old one-cue/one-property rules,
blanket Workspace Video/FX bans and pending statements are superseded by the
current public contract above, while its dated observations remain evidence.
