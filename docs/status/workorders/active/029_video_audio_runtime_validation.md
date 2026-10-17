# Video Audio Runtime Validation

Status (2026-10-17): partially runtime-proven. The [October 1 deeper pass](../../../development/runtime-validation/2026-10-01-visual-cues.md)
records clock, Integrated Fade/lock and one mute with restoration; the
[October 2 follow-up](../../../development/runtime-validation/2026-10-02-visual-cue-fixes.md)
records specialized mute/unmute and mute-clear recovery. This documentation
review ran no new QLab probe.

## Remaining validation

- `solo/channel` and `solo/channel/clear`, with complete captured state and restoration.
- Other specifically selected combinations without their own dated evidence.
- Exact-media-end `endTime` remains an explicit QLab error case.

Already recorded clock/fade/mute cases require repetition for a new fixture,
version or acceptance requirement, not because their evidence is absent.
Use exact disposable UUIDs, inactivity, fresh baseline, reviewed dry-run/token,
one setter, fresh readback and a separately authorized restoration. Never retry
an ambiguous setter. This bounded validation procedure excludes playback and
batch/multi-property exercises; the public editor supports validated batches.

## Historical validation plan

The original pending statements below predate the reports above. Legacy tokens
and phase-wide exclusions are not the current family-editor contract.

Status (2026-10-07): active for the selected Video embedded-audio settings and
mute/solo cases below. The current connector exposes the family editors; these
particular setter/readback cases still need bounded runtime validation.

Historical research and completed Phase 8B/9A–9C evidence remain in
[`020_video_embedded_audio_research.md`](../../../archive/workorders/research/020_video_embedded_audio_research.md).

## Pending scope

- Validate `clockType` with exact `audio`/`video` values. Embedded-audio
  evidence is not required.
- Validate `doFade` and `lockFadeToCue` on a Video cue with embedded audio.
- Validate one `mute/channel` and one `solo/channel` saved edit.
- Validate `mute/channel/clear` and `solo/channel/clear` only if the complete
  channel state can be captured and restored deterministically.

## Required procedure

- Disposable workspace and one healthy inactive Video cue.
- Exact workspace and cue UUIDs.
- Confirm `running/paused/auditioning = 0/0/0`.
- Fresh baseline, dry-run, exact fresh token, one setter, fresh readback.
- Rollback through a new dry-run and token, followed by final readback.
- No automatic mutating retry after timeout.

## Excluded

`setDefaultLevels`, `setSilentLevels`, Objects, Trim, Audio FX, slices, patch
changes, `/live`, playback, show control, raw OSC, save, batch, and
multi-property writes.
