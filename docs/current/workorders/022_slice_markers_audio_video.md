# Video Phase 8C - Slice Markers for Audio and Video

Status: status audit needed. This workorder records Phase 8C/8C.2 local
hardening; confirm current validation status in `docs/current/active_roadmap.md`.

## Sources

- `docs/references/qlab_osc_dictionary.md`
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 1.md`
- `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`
- `src/qlab_mcp/cues/profiles.py`
- `src/qlab_mcp/write/registry.py`
- `src/qlab_mcp/write/operations.py`
- `tests/test_write_mode.py`
- `tests/test_qlab_reader.py`

## Route Facts

QLab documents slice markers under Audio cue OSC, with the note that most Audio
messages also work with Video and Camera cues. QClass notes describe slicing as
available for Audio and Video cues.

| Purpose | OSC path | Type | Phase 8C status |
|---|---|---|---|
| Read all markers | `/cue/{cue_number}/sliceMarkers` | array of `{time, playCount}` | read exposed |
| Set marker time/count together | `/cue/{cue_number}/sliceMarker/{index}` | time + playCount | blocked |
| Set marker time | `/cue/{cue_number}/sliceMarker/{index}/time` | finite seconds | Video write candidate |
| Set marker play count | `/cue/{cue_number}/sliceMarker/{index}/playCount` | positive int or `-1` | Video write candidate |
| Add marker | `/cue/{cue_number}/addSliceMarker` | time + playCount | Video write candidate |
| Delete one marker | `/cue/{cue_number}/deleteSliceMarker/{index}` | action by index | Video write candidate |
| Delete all markers | `/cue/{cue_number}/deleteSliceMarkers` | destructive action | Video write candidate |
| Last slice play count | `/cue/{cue_number}/lastSlicePlayCount` | positive int or `-1` | Video write candidate |
| Last slice infinite loop | `/cue/{cue_number}/lastSliceInfiniteLoop` | boolean | blocked |

## Read Support

Audio and Video cue detail profiles now use a canonical slice read path for
`sliceMarkers`, `lastSlicePlayCount`, and `lastSliceInfiniteLoop`. If a normal
profile asks for `sliceMarkers` and `valuesForKeys` omits it, MCP reads
`/sliceMarkers` directly before reporting a value. This fixes the V5 runtime
mismatch where `auto`/`editable`/`inspector_safe` reported `[]` while
`exhaustive` and write dry-run saw the real markers.

If the slice route is intentionally queried and QLab omits `sliceMarkers`, the
read output normalizes it to `[]`. MCP no longer reports `sliceMarkers: []`
just because a profile did not ask for the route.

`sliceMarkers` readback is normalized only enough for inspection:

- each item gets `index`
- raw `time` and `playCount` are preserved
- `playCount == -1` is labeled `loopMode: infinite`
- positive integer `playCount` is labeled `loopMode: finite`
- `0`, missing values, or malformed entries are labeled `loopMode: unknown`
- malformed non-list `sliceMarkers` readback is preserved as malformed data,
  not silently treated as `[]`

Phase 8C does not treat `0` as skip unless QLab documentation/runtime later
proves that semantic.

## Implemented Write Support

Video-only saved-mode candidates use:

- token family: `confirm:videoSlices:v1:`
- profile: `video_basic`
- cue type: `Video`
- exact cue UUID only
- one cue
- one operation
- one marker
- healthy inactive cue
- fresh `sliceMarkers` baseline
- fresh token from dry-run
- fresh post-write `sliceMarkers` readback
- no batch, no multi-property, no cue name/number, no `/live`

Supported operations:

- existing marker `sliceMarker/{index}/playCount`
- existing marker `sliceMarker/{index}/time`
- `addSliceMarker`
- `deleteSliceMarker/{index}`
- `deleteSliceMarkers`
- `lastSlicePlayCount`

`lastSlicePlayCount` represents the play count of the final implicit slice
after the last marker. Runtime evidence for V5 visually showed `2 / 4 / 2`:
the first two counts are marker play counts and the final count is
`lastSlicePlayCount = 2`. Exact slice copy must preserve marker times and this
last-slice value.

For Video slice write gates, a missing `sliceMarkers` baseline on a healthy,
inactive Video cue is treated as `[]` only for safe slice operations. That
allows `addSliceMarker` to create the first marker. Existing-marker operations
still reject against an empty baseline:

- `sliceMarker/{index}/playCount` index `0` rejects when no marker exists
- `sliceMarker/{index}/time` index `0` rejects when no marker exists
- `deleteSliceMarker/{index}` index `0` rejects when no marker exists
- `deleteSliceMarkers` rejects empty baseline as a no-op

## Validators

`playCount`:

- allow positive integers
- allow `-1` for infinite
- reject `0`
- reject floats, strings, booleans, null, lists, and dictionaries

`time`:

- finite non-negative number
- must fit known cue `startTime`/`endTime` or `duration` bounds when available
- must remain at least `0.05s` from every other marker

Baseline:

- `sliceMarkers` must be readable, or missing on Audio/Video and therefore
  normalized to `[]`
- each marker must have finite `time`
- each marker must have valid `playCount`
- malformed existing `sliceMarkers` values are rejected for writes

## Rollback Strategy

Rollback is explicit and operation-specific:

- `playCount`: write original playCount back with fresh token
- `time`: write original time back with fresh token
- `addSliceMarker`: delete the newly added marker by fresh readback index; add is
  rejected if another marker is within `0.05s`, so rollback target is unique
- `deleteSliceMarker`: add the deleted marker back with its original time and
  playCount, then require exact final marker list
- `deleteSliceMarkers`: capture the full baseline marker list, delete all
  markers, require fresh readback `[]`, then roll back by re-adding each marker
  in original order with original `time` and `playCount`; final readback must
  match the baseline exactly, with normal float tolerance for times

Setter timeout or QLab setter error is acceptable only when fresh
`sliceMarkers` readback exactly matches the expected marker list. The result
stays warning-visible and no mutating retry is allowed.

For `deleteSliceMarkers` verification only, expected `sliceMarkers: []` also
accepts a fresh readback where QLab omits `sliceMarkers` after the delete. This
is treated as empty only in the confirmed slice-read context; malformed
non-list readback still fails.

## Blocked / Future Only

- Audio real writes
- Camera real writes
- combined `/sliceMarker/{index}` time + playCount write
- `lastSliceInfiniteLoop`
- vamps/devamps and Devamp cue behavior
- `/live`
- batch or multi-property writes
- raw OSC, playback/show-control, workspace save

Devamp is deliberately omitted. `devampType`,
`startNextCueWhenSliceEnds`, and `stopTargetWhenSliceEnds` belong to Devamp cue
behavior and can affect playback/show-control flow. They need a separate phase,
separate safety gates, and runtime proof.

`lastSliceInfiniteLoop` remains blocked even though the OSC dictionary documents
the route. The missing proof is rollback semantics: setting `true` likely maps
the final slice to infinite looping, but docs do not say whether writing
`false` restores the previous finite `lastSlicePlayCount` or merely clears the
checkbox. MCP therefore keeps boolean last-slice loop writes future-only until
runtime proves safe rollback.

Exact-time copy is the only supported copy model for future visible swaps:
marker times such as `0.3963851631` and `1.7845422029` must be copied as-is
when they fit the target cue bounds. Proportional duration scaling is not
implemented.

Combined `/sliceMarker/{index} {time} {play_count}` remains blocked because the
current safe model is one structured operation with one readback expectation.
It can be added later as a dedicated structured operation only if it binds both
requested values and the full baseline marker in one token without opening
generic multi-property writes.

`playCount: 0` remains blocked for writes. Existing readback with `0` is kept
visible as unknown/skip-like data, but runtime must prove OSC write behavior
before MCP authorizes it.

## Tests Added

- Audio cue readback with empty `sliceMarkers`
- Video cue readback with finite and infinite marker play counts
- malformed/unknown readback handling, including unresolved `playCount: 0`
- missing Audio/Video `sliceMarkers` normalizes to `[]`
- Video `addSliceMarker` can create the first marker from missing/empty baseline
- empty-baseline add/edit/delete flow returns final `[]`
- edit/delete index `0` reject on empty baseline
- dry-run token emission for Video write candidates
- real-write OSC path and readback verification for Video write candidates
- `deleteSliceMarkers` delete-all route, readback `[]`, and rollback by
  re-adding the full baseline in order
- `deleteSliceMarkers` verification accepts missing/omitted `sliceMarkers` as
  `[]` only after a confirmed delete expected empty readback
- dry-run token and real write/readback for `lastSlicePlayCount`
- invalid play counts: `< -1`, `0`, float, string, boolean, null, list, dict
- missing/non-existing marker index rejection
- invalid time rejection: before start, after end, too close to previous/next,
  crossing marker order, `NaN`/infinity, non-scalar values
- add-marker too-close/out-of-range rejection
- wrong token family, fake token, stale/wrong value token, wrong cue, cue
  number, non-Video cue, batch, and multi-operation rejection
- setter timeout and setter error accepted only when fresh `sliceMarkers`
  readback matches
- fresh-token rollback restores the baseline marker list for playCount, time,
  add, and delete

## Runtime Validation Plan

Use disposable cues in a test workspace only.

Read-only checks:

1. Confirm workspace readiness and running/paused/auditioning are `0/0/0`.
2. Read Audio cue with no markers; expect `sliceMarkers: []`.
3. Read Video cue with no markers; expect `sliceMarkers: []`.
4. Read Video cue with one marker; confirm `index`, `time`, and `playCount`.
5. Read Video cue with multiple markers; confirm zero-based order.
6. Read Audio cue with markers; confirm same read shape.
7. Read Video cue without embedded audio if available; confirm whether
   `sliceMarkers` is readable and do not infer write safety from it.

Video write checks, one marker/property/action at a time:

1. Read target cue fresh; prove exact UUID, `Video`, healthy, inactive.
2. Record baseline `sliceMarkers`.
3. Dry-run and real-write index `0` `sliceMarker/playCount`; readback must
   match. Roll back with fresh token; final readback must equal baseline.
4. Dry-run and real-write index `0` `sliceMarker/time`; readback must match.
   Roll back with fresh token; final readback must equal baseline.
5. Dry-run and real-write `playCount: -1`; readback must match. Roll back with
   fresh token.
6. Probe `playCount: 0` only as exploratory rejection; it must not mutate unless
   separate documentation/runtime proof authorizes skip semantics.
7. Dry-run and real-write `addSliceMarker`; readback must identify exactly one
   new unique marker. Roll back by deleting the actual new index.
8. Dry-run and real-write `deleteSliceMarker`; readback must remove exactly one
   marker. Roll back by adding the original marker back.
9. Dry-run and real-write `deleteSliceMarkers` only on a cue with at least one
   marker; readback must become `[]`. Roll back by re-adding every baseline
   marker in order with fresh tokens; final readback must equal baseline.
10. On `Sin slices`, confirm readback exposes `sliceMarkers: []`; add marker
    `2.0/1`, add marker `4.0/-1`, edit marker `0` playCount `1 -> 2`, edit
    marker `0` time `2.0 -> 2.1`, delete marker `1`, delete marker `0`, and
    require final readback `[]`.
11. Dry-run and real-write `lastSlicePlayCount`; readback must match. Roll back
    with a fresh token.
12. Probe `lastSliceInfiniteLoop` only as blocked/future; no mutation until
    rollback semantics are proven.

Later exact-copy validation should read V5 as `2 / 4 / 2`, add V5 marker times
unchanged to V8, copy `lastSlicePlayCount`, verify V8 reconstructs `2 / 4 / 2`,
then clean back to `[]`. Do not do proportional timing.

No raw OSC, playback, `/live`, save, batch, multi-property, or commit.
Stop immediately if a cue becomes broken or rollback fails.
