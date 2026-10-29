# Video Settings authoring — 2026-10-25

The later [attached-MCP audit](2026-10-25-light-video-audit.md) supersedes the
restart/FPS follow-up status below; this report retains the initial source test.

## Scope and environment

Source FastMCP acceptance in QLab **5.5.10/build 5510**, running from the Desktop
installation, against the authorized `mcp_prueba.qlab5` (workspace UUID
`95F0A03D-140E-4673-974A-E76748EBB023`). Fixed document operations verified the
single running bundle/process and reopened the same path. No second QLab app
was launched. The public Open tool retains its empty-inventory restriction.

Native tests called the public tool functions through a real in-process
FastMCP `Client(mcp)` loaded from this checkout. The separately attached MCP
process must be restarted to advertise the new tools; source acceptance is not
proof that an older attached process has loaded them.

## Accepted configuration operations

- Route rename and restoration; create two routes sharing one NDI destination;
  Center/Fit/Stretch/Fill, 0/90/180/270 degrees, rear projection, full and 2×2
  partial layout. Device rename/raster/rate changes propagated to both routes.
- Stage creation/deletion, region creation, route reassignment, layer 50,
  keep-rendering disabled, an existing PNG mask assignment/removal, and Scale
  resize. Native UI agreed with the name, layer, dimensions, mask and rendering
  flag on the test stage.
- Perspective, Linear and Bézier; 2×2 and 2×1 meshes; point edits, shared seam
  movement, explicit unlink/relink, and reset to a 1×1 mesh. Recursive native OSC
  readback checked geometry, topology, point coordinates and link identifiers.
- Native UI Crop/Pad from 400×300 to 300×200 provided a golden sample: edited
  leaves retained their controls; pristine leaves were reset according to their
  new stage bounds. The source planner reproduced the native result and passed
  recursive OSC comparison. Automated regression tests retain this behavior.
- NDI and Syphon configured-device creation, update and unused deletion. Native
  UI showed the configured dimensions/rate; NDI audio remained 2 channels,
  48 kHz and 512 samples in the accepted shared-route example.
- Empty and OBS input patches; local camera assignment, explicit 1280×720 at
  30 fps Y'CbCr 4:2:0, return to Auto, patch ordering and deletion. Native UI
  showed both that manual mode and OBS Auto. Original three patches retained
  their assignments and Auto settings.
- Deleting a route in use returned `blocked`, with no close/reopen. Automated
  tests additionally cover used device/cue dependencies, stale references,
  domain separation, strict bounds/nulls, no-op, invalid topology and preservation
  of unknown input configuration.

All execution attempts used a fresh preview and one confirmation. Archive
acceptance checks exact saved output and fresh native identities/properties;
legacy OSC setters retain their existing confirmation flow.

## Preservation and failure coverage

Native Save can reorder keyed-archive dictionaries and regenerate runtime Light
output IDs; raw file equality is therefore not the preservation criterion across
an intentional native Save. A normalized comparison after Save found identical
cue content and Audio, Network, MIDI and General settings. Original video stages,
routes and inputs matched the saved baseline; only the temporary stage differed.
The Light comparison identified regenerated `lightOutputID` values; video archive
plans do not write the Light archive. Synthetic tests assert cue bytes unchanged
by the planner and preserve unrequested route/graph data.

Shared transaction regressions cover dirty documents, expiry/reuse, file/document
races, failed Close/Open/replacement, preservation of other documents and retained
recovery. A domain-verifier test ensures video does not invoke the Light reader;
changed external dependencies and oversized generated files block before Close.
Unrecognized replaceable mesh/point data blocks rather than silently dropping it.

Temporary stages, routes, configured devices and input patches were removed
through the same public editors in dependency order. Recovery samples stay local;
no real archive, vendor payload, credentials or native bookmarks are committed.

## Verification

- Full suite: **2,268 passed, 35 skipped, 61 subtests passed** (local test sockets
  enabled). `git diff --check` passed.
- FastMCP inspection: **87 tools — 52 reads and 35 gated writes**.
- Typed schemas retain both batch outputs and legacy setter output fields.
  Legacy stage/route forms and batch forms are mutually exclusive.
- An independent read-only review identified route-readback, shared-route warp,
  linked-group and supported-FPS issues. The later attached audit corrected the
  initial FPS-range assumption to QLab-selectable endpoints, with native evidence.

## Explicit limits

The process-shared QLab Output Devices table accumulated duplicate unreferenced
Syphon entries after repeated close/reopen, although the saved archive contained
one such device. Native Save retained one configured object, not the extra rows.
REA `QLAB-VIDEO-064/065` already distinguishes this registry from saved settings.
The tools author saved configuration; they do not promise to reconcile every
transient registry row. A QLab application restart may be needed to clear stale
process entries; it was not performed because it could affect other user work.

Viewport layer/mask, rendering flags, configured device parameters and input
modes are checked in the saved archive where OSC exposes no equivalent. Native
UI supplies representative corroboration, not an exhaustive proof of every
parameter combination. All nine resize anchors, all frame rates/audio formats,
all grid sizes and arbitrarily nested/shared geometries have not received separate
native acceptance; their validated encodings and bounded invariants have tests.

No cue, Monitor, Show, capture session, network discovery or physical signal test
was requested. QLab itself may initialize device backends when reopening a
configured document. Accepted configuration does not establish zero output,
working capture, successful rendering or physical video signal. New network input
sources and Blackmagic assignment remain excluded. Keep the PR in draft.
