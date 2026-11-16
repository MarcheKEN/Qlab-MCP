# Roadmap — current development snapshot

## Current contract

QLab MCP **0.4.0** exposes 90 tools: 53 reads and 37 gated writes. The [tool catalogue](../user/tools.md)
and generated schemas define their arguments; [architecture](../development/architecture.md)
describes implementation. Generic `qlab_edit_cues` and `qlab_edit_workspace_settings`
are retired. Use the typed cue-family and scoped workspace-settings editors.

Family editors share signed `confirm:controlCue:v1:` confirmations, exact UUIDs,
whole-batch preflight, sequential setters and fresh readback. They accept 1–50
unique cues and supported multiple properties; individual operations impose
additional restrictions. No automatic mutation retry or rollback is provided.
Legacy workspace-settings setters use `confirm:workspaceSettings:v1:` and one
operation per request. Video archive editors additionally accept typed batches
with their own domain-bound confirmation. Native document operations have a separate token and preflight.

The [October 17 installed-MCP pass](../development/runtime-validation/2026-10-17-installed-mcp-acceptance.md)
invoked the then-current 79 tools and exercised real writes through 26 of the 30 writers.
Its coverage is representative; remaining per-operation gaps below are not
closed by tool invocation alone. This dated pass predates the later Video Settings
archive editors, saved-cue settings and Light Patch writers. It changed no code
and tested no playback.

## Supported work and remaining gates

The [settings follow-up](../development/runtime-validation/2026-10-25-settings-extensions.md)
adds full readable definition details, root stage/route ordering, empty input
names, five NDI audio sample rates and bounded local Syphon candidates. Import
eligibility remains stricter than readability; the complete QLab process
registry, NDI discovery and Blackmagic remain outside this delivery.

| Area | Current scope | Remaining evidence or capability limits |
| --- | --- | --- |
| Visual geometry | Typed components/aggregates, crop, smooth, aspect ratio, blend, quaternion/reset | [Video geometry](../development/runtime-validation/2026-10-01-visual-cues.md) and [restoration fixes](../development/runtime-validation/2026-10-02-visual-cue-fixes.md) have bounded proof. Camera/Text combinations require their individual evidence; relative rotate, shutter and additional reset actions remain excluded. |
| I/O and media | Existing stage/input/output selections and typed Audio/Video/MIDI File file targets | [Mic input restoration](../development/runtime-validation/2026-10-05-remaining-cue-completion.md) does not validate every patch combination. Unknown capacity/ownership blocks dependent channel/object edits. |
| Video timing/audio | Timing, loops, clock, Integrated Fade flags, readable levels and mute/solo | [October 27](../development/runtime-validation/2026-10-27-video-follow-up.md) verified solo/clear and 8→9.922 seconds on one Video fixture. Exact-media-end behavior for other media and combinations remains unproven. Integrated envelopes use guarded saved-cue editors; Trim and level reset actions remain excluded. |
| Slices | Typed Audio/Video marker operations with fresh inventory | [October 27](../development/runtime-validation/2026-10-27-video-follow-up.md) verified add, time, play-count, delete, clear and last-slice count on one healthy Video fixture. Other media and combinations remain unproven. Missing inventory is not an empty baseline. |
| Text | Full/fragment formatting, UTF-16 ranges, percentages, bounded Latin words and observed font mappings | [October 29](../development/runtime-validation/2026-10-27-video-follow-up.md#scalar-font-fallback-follow-up--2026-10-29) records bounded CJK and font cases. Exact-font gates, emoji/unsupported fallback and unreadable shadow limits remain. |
| Video FX | 60-effect/262-parameter catalogue, indexed metadata and typed parameter/stack edits | [58 creation defaults and 55 restorations](../development/runtime-validation/2026-10-09-fx-empty-stack-creation.md) are fixture-specific. LinearKey/DropShadow OSC creation remains blocked; guarded saved-file insertion is separately supported. Ambiguous identity, unknown native keys and unverified reconstruction remain blocked. |
| Group and root containers | Typed Group/Playlist, Cue List/Cart create/edit/reorder | Mode/child-snapshot checks remain. Cart cell Move execution and unattended root List/Cart deletion remain blocked; moving sidebar roots does not move cells. |
| Other cue families | Audio/Mic/Light/Fade/Network/MIDI/MIDI File/Timecode/Script typed editors | The [completion report](../development/runtime-validation/2026-10-05-remaining-cue-completion.md) records individual live gaps. Unknown device/command/range metadata blocks MSC/Device Definition operations. Script source/compilation is excluded. |
| Native cue fields | Fixed local Load Time, assigned number and opt-in native Triggers | [October 26](../development/runtime-validation/2026-10-26-cue-settings-completion.md) records disabled Hotkey assignment, separate activation and weekday edits through the guarded saved-cue editor. Trigger capture and arbitrary scripts remain excluded. |
| Audio patches | `qlab_get_audio_patch` distinguishes current OSC and saved archive views; `qlab_edit_audio_patch` handles current output values and saved input/output fields as separate operations; `qlab_edit_workspace_audio_settings` handles saved patch structure and a separate `VolumeLimits` edit | Saved archive freshness can be stale while the workspace is dirty. Before a file edit, `needs_save` signals prior unsaved changes; save them and get a fresh preview. Confirmed archive edits persist after reopen. Blank patch creation remains unavailable; Audio FX and Audio Maps remain outside the public surface. `VolumeLimits` pairs (-80,+6), (-180,+60), (-40,-30) dB were saved, reopened and checked via OSC on QLab 5.5.10 temporary copy; (-80.1,+6.1) read back within 0.0001 dB. |
| Workspace Settings | General settings, Audio patch structure and `VolumeLimits`, and four video archive editors for stages/regions, routes, NDI/Syphon devices and local/OBS inputs | [October 25](../development/runtime-validation/2026-10-25-video-authoring.md) covers same-path batches, masks/resize/meshes, shared routes and input modes. Physical output/capture, Blackmagic and new network input assignment remain excluded. The unlicensed “Video output for all cues” selector is not modelled. Audio Maps and Network/MIDI writers remain excluded. |
| Light Patch | Local 5.5.10/build 5510 instrument/group edits and separate definition CRUD; Art-Net, explicit USB-DMX identity or unpatched assignments | USB-DMX device discovery, compatible-device availability and output remain unvalidated. Definition parameters include scalar, RGB/lime, CMY, HSI, Pan/Tilt and acyclic One-to-Many; unknown variants remain blocked. Cues are preserved with partial reference warnings. File routing verification and limited OSC-visible readback are distinct; hardware output is unclaimed. See the [workflow](../user/agent-workflows.md#edit-the-light-patch). |
| Native documents | Exact local inventory, bounded Open/Save/clean-Close | Document Get, Save preview and dirty-Close/nonempty-Open blocking were observed in the October 17 pass. Actual Open/Save/Close events remain unvalidated by these reports. |
| Local analysis | Consent-based media search and optional paged audio analysis | Optional Python dependencies and FFmpeg/ffprobe are required for real decoding. Measurements are source-relative; they do not classify lyrics or establish playback/hardware behavior. |
| Light curves | Separate guarded saved-file Custom/S-Curve/Parametric/Linear up/down editor | QLab 5.5.10/build 5510; mirrored/unknown shapes are blocked. Saved archive postconditions and bounded native visual acceptance do not prove playback or DMX. |

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
unclaimed. The October 17 acceptance pass does not cover the later Light Patch writer.

## Historical plans

The [historical phase roadmap](../archive/plans/2026-10-14-historical-phase-roadmap.md)
preserves earlier plans, counts and tokens. Its old one-cue/one-property rules,
blanket Workspace Video/FX bans and pending statements are superseded by the
current public contract above, while its dated observations remain evidence.
