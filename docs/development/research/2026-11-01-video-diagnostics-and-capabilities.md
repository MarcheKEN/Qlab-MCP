# Video diagnostics and capabilities — 2026-11-01

This change reviews existing Qlab-REA documentation, including additions dated
October 31 and November 1. No new reverse engineering, QLab access, playback or
native mutation was performed for this review. Tests use synthetic fixtures.

## Evidence and decisions

The separate Qlab-REA research folder's
`qlab-research/video/ARCHIVE_SNAPSHOT_2026-10-29.md` includes later sections
“Saved VideoCue field census, 1 November”, “Missing-stage warning and broken
status: static conditions”, “Linear Key in the newer saved archive (2026-10-31)”
and “Drop Shadow in the newer saved archive (2026-10-31)”.

- The saved census contains armed objects with zero opacity. It is not a live
  inventory or proof of a defect. Video details now report zero opacity and
  disarming as bounded observations derived only from existing current reads.
  They do not change QLab health flags, response status or write permissions.
- The static warning paths describe multiple possible causes for broken Video
  cues. An assigned file target does not prove file existence, accessibility or
  compatibility. Health guidance preserves its existing fields/statuses and
  directs agents to media, stage and actual QLab warnings without assigning an
  unobserved cause. Internal warning numbers and license state are not inferred.
- The native-effect sections corroborate structures relevant to the already
  supported LinearKey/DropShadow archive insertion. Capabilities now distinguish
  that Video-only route from blocked OSC creation and publish its exact types.
  Existing [native configuration evidence](../runtime-validation/2026-10-26-cue-settings-completion.md)
  remains the acceptance reference; static samples do not enable new writes.

The external `BLEND_MODES_QLAB_5_5_10.md` (November 1) distinguishes 28 internal
modes from the 24 scripting names already allowed by this project. The snapshot's
“Partial-screen detection and saved-layout boundary” describes a decoder edge
that this project's strict `index < width * height` validation already rejects.
Neither finding requires expanding the current write surface.

Research files remain in their original folder. No workspace, projection or
private evidence is bundled. See the [agent workflow](../../user/agent-workflows.md#video-text-and-camera-cues)
for the read, inspect, confirm a cause, guarded edit and fresh-read sequence.
