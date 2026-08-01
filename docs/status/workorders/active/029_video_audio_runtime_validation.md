# Video Audio Runtime Validation

Status: active; runtime validation pending after MCP restart.

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
