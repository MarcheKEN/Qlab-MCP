# Active Roadmap

Status: 2026-06-25

## Closed

- Video Phase 1 — inventory, dry-run, and write-safety closure.
- Video Phase 1D — lightweight Video read summaries.
- Video Phase 2A — scalar dry-run matrix and blocked-family cleanup.
- Video Phase 2B — UpdateQ plan format.
- Video Phase 2C — future gate vectors.
- Video Phase 3A — saved `opacity` real write for `Video`, `Camera`, and `Text`.
- Video Phase 3B — saved `translation/x` and `translation/y` real write for
  `Video`, `Camera`, and `Text`.
- Video Phase 3C — saved visual scalar real writes for `Video`, `Camera`, and
  `Text`: `scale/x`, `scale/y`, `anchor/x`, `anchor/y`, `cropTop`,
  `cropBottom`, `cropLeft`, and `cropRight`.
- Video Phase 3D — saved visual appearance real writes for `Video`, `Camera`,
  and `Text`: `blendMode` and `preserveAspectRatio`.
- Video Phase 3E — saved Text Basics real writes for `Text` cues:
  `text`, `text/format/fontSize`, and `text/format/alignment`.

Phase 3A runtime validation confirmed token-gated single-property writes, fresh
readback, new-token rollback, and restored baselines for all three cue types.
QLab setter timeout with matching readback is accepted as success with warning
`setter_timeout_but_readback_matched`.

Phase 3B runtime validation confirmed token-gated writes and new-token rollback
for both axes on healthy `Video`, `Camera`, and `Text` cues.

Phase 3C runtime validation confirmed 8/8 properties on each healthy `Video`,
`Camera`, and `Text` cue. Each write used `confirm:videoScalar:v1:`, one saved
setter, matching fresh readback, and a new-token rollback restoring baseline.
QLab setter timeout with matching readback was accepted as confirmed success
with warning `setter_timeout_but_readback_matched`.

Phase 3D runtime validation confirmed 6/6 real writes and 6/6 new-token
rollbacks across healthy `Video`, `Camera`, and `Text` cues. All 22/22 rejection
probes blocked before mutation. Final baselines were intact, with no unrelated
writes and zero running, paused, or auditioning cues. QLab setter timeout with
matching fresh readback was accepted as confirmed success with warning
`setter_timeout_but_readback_matched`; no mutating retry occurred.

Phase 3E was independently runtime validated on `v1 Text1` in the test
workspace. All 3/3 real writes and 3/3 fresh-token rollbacks passed. All 12/12
rejection probes blocked before mutation with `executed_operations=[]`. The
final text, font-size, and alignment baseline was restored exactly; the cue was
healthy and inactive, with global running, paused, and auditioning counts
0/0/0. All six setters timed out, matching fresh readback confirmed each result
as `status="updated"` with warning `setter_timeout_but_readback_matched`, and
no mutating retry occurred. No GO, playback, audition, `/live`, raw OSC, save,
or unrelated mutation was used.

## Next

Video Phase 3F — Text Style. Optional future candidate only:

- `fontName`
- text color
- background color
- shadow
- underline and strikethrough

Do not implement unless the OSC dictionary and exact deterministic readback are
clear for each property.

See:

- `workorders/002_close_phase3a_docs.md`
- `workorders/003_plan_phase3b_translation.md`
- `workorders/004_implement_phase3c_visual_scalars.md`
- `workorders/005_implement_phase3d_visual_appearance.md`
- `workorders/006_implement_phase3e_text_basics.md`

## Safety boundary

Phase 3E is runtime validated and closed. Keep blocked:

- playback, GO, Dashboard, raw OSC, and `/live`
- Workspace Video writes
- stage, region, route, warping, and control-point writes
- Video FX, `fileTarget`, camera/video-input patch, rotation, and shutter writes
- rich text format, font name, text/background/shadow colors, text
  decorations, `doOpacity`, and clock-type real writes
- batch and multi-property Video-family real writes
