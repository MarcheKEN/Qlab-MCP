# Workorder 002 — Close Video Phase 3A

Status: closed

## Final scope

Video Phase 3A enables one saved real-write property:

- property: `opacity`
- cue types: `Video`, `Camera`, `Text`
- profiles: `video_basic`, `camera_basic`, `text_basic`
- value: finite number in `0..1`
- shape: one UUID-addressed cue and one property
- token: `confirm:videoOpacity:v1:...`

## Runtime results

Validation used QLab 5.5.10, test workspace `mcp_prueba`, and cue list
`MCP_VIDEO_WRITE_FIXTURE`.

- Video `v4 Video2`: opacity changed from `0.6000000238418579` to `0.55`;
  fresh readback matched; new-token rollback restored
  `0.6000000238418579`.
- Camera `v6 Camare1`: opacity changed from `1` to `0.85`; fresh readback
  matched; new-token rollback restored `1`.
- Text `v1 Text1`: opacity changed from `1` to `0.8`; fresh readback matched;
  new-token rollback restored `1`.

Each successful write executed exactly one saved `/opacity` setter. Unrelated
Camera geometry/input-patch fields and Text content/font/geometry fields stayed
unchanged.

## Accepted deviation

QLab may time out while replying to the setter even when the saved change was
applied. Phase 3A policy:

- setter timeout + matching fresh readback: `status="updated"` with warning
  `setter_timeout_but_readback_matched`
- setter timeout + missing or mismatched readback: uncertain failure; no
  mutating retry

This timeout-with-matching-readback case is accepted as confirmed success.

## Safety confirmation

Validation used no playback, GO, `/live`, Dashboard, raw OSC, Workspace Video
writes, Video FX, `fileTarget`, camera patch, stage, rotation,
translation/scale/crop/text/font real writes, or cue lifecycle changes.

Running, paused, and auditioning cue counts remained zero. Final opacity
baselines were restored.

## Closure

Phase 3A is closed for `Video`, `Camera`, and `Text` opacity. The reporting-only
intent wording fix uses the fresh-read cue type and does not alter token, gate,
setter, registry, or write behavior.
