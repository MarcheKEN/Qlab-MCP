# Video region moveBy: investigation

## Documented capability

The local OSC dictionary, lines 5063–5067, documents
`/cue/{cue_number}/stage/regionID/{id}/moveBy {x} {y}` with decimal numbers
allowed. There is no documented no-argument getter on this action, or equivalent
under `/settings/video/stageID/...`. Do not probe it with missing arguments or
zero displacement as a substitute for a read: it is a mutation command.

This changes the shared stage region referenced by the cue. It does not move
the cue itself. A UUID-based tool would need an explicit intermediary cue UUID
and fresh proof that its stage matches the requested stage UUID before sending.
Existing bounds/origin operations are absolute; `moveBy` is relative and must
never be automatically resent following an uncertain timeout.

## Current read-only runtime evidence

2026-09-29, QLab 5.5.10, workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`. A bounded query scanned at most 30
cues and returned one Video cue: `VIDEO_MISSING_FILE`, number 3, UUID
`29297185-C627-5B18-A08D-A4BE89394778`. The query was partial, not a complete
inventory. Its broken media target does not prevent reading its stage reference;
it was not started or loaded.

No-argument reads using the repository's TCP OSC client returned:

| Workspace-qualified path after `/cue_id/{cue_UUID}` | Result |
|---|---|
| `/uniqueID` | Exact cue UUID above |
| `/stageID` | `A0CA9B3F-A783-54BF-9B36-25572F3C93EF` |
| `/stage/uniqueID` | Same stage UUID |
| `/stage/regions` | Region A, UUID `39112667-4656-53AE-9782-D1C1908047D7`, bounds `(0,0,2940,1912)`, mesh 1×1 |

These reads prove the intermediary identity chain for this fixture. They do not
prove `moveBy` execution, decimal rounding, range handling, or its complete
postcondition. The full-stage bounds leave no room for a positive Layout-origin
shift under the existing bounds constraints; this fixture must not be used for
an arbitrary move without first preparing a smaller region in a disposable copy.

## Pending validation before implementation

Use a disposable workspace with originals closed and pending user changes
resolved. Prepare a smaller region through the existing gated bounds operation,
record its full region/mesh/route state, then send one documented moveBy with a
bounded displacement. Compare bounds, control points, and other region fields
to determine exactly what moves. Verify fractional behavior separately. Restore
the complete affected state with single, verified operations; exclude the action
if its state cannot be restored reliably.

Do not add a public operation based only on the matching identity reads. Main
and marginal gains in Audio remain the first validation priority. No moveBy,
cue playback, or other setter was sent during this investigation.

## Subsequent disposable-copy write evidence

After user authorization resolved the original workspace closures, Computer Use
confirmed `/private/tmp/mcp_settings_expansion_20260929.qlab5`, Edit, and zero
active cues. Each call revalidated one open workspace, its UUID and copy name,
write readiness, activity, cue UUID, cue stage assignment, and region identity.
The full region object was captured for baseline and fresh verification.

1. A gated bounds edit prepared `(0,0,2930,1902)` from `(0,0,2940,1912)`.
   It changed bounds and meshSubregions; the four pristine points followed size.
2. One `moveBy(1,1)` changed only meshSubregions: all four outputPoints gained
   (1,1), and their `pristine` flags became false. Layout bounds stayed unchanged.
3. One `moveBy(-1,-1)` restored point coordinates but left `pristine=false`.
4. One `moveBy(0.5,0.5)` retained fractional coordinates exactly in the payload.
5. One inverse `moveBy(-0.5,-0.5)` restored coordinates, still non-pristine.
6. A gated bounds edit restored the original Layout dimensions. The complete
   original region state was not restored; see preserved JSON evidence.

Every call sent one setter, timed out, and was confirmed by fresh reads without
resending. No cue was started. This demonstrates a **warping point translation**,
not a Layout bounds translation. A bounds-only postcondition would falsely
report no change. Fractional points also need a different readback contract from
the current int32 Settings geometry tools.

Decision: do not publish moveBy in this increment. Inverse translation does not
restore all observed state, and a verified implementation would need to account
for pristine/link/shadow-point state and complete mesh postconditions. Resets
remain deferred. Discard the disposable workspace changes rather than save the
partially restored test state. Audio Main/marginal gains are the verified API
extension delivered by this increment.

The remaining differences after restoring Layout dimensions were the four
`pristine` flags and three corner coordinates still using 2930/1902 instead of
2940/1912. Computer Use closed the disposable copy with Don't Save and reopened
the original `redacted-test-workspace` path. No test changes were saved. The evidence JSON
is [retained beside this report](2026-09-29-video-region-moveby.json) with snapshots restricted to region/mesh data;
device metadata is omitted.
