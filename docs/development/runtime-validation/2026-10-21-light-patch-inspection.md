# Combined Light Patch inspection — 2026-10-21

## Implemented boundary

The existing `qlab_get_workspace_light_settings` now returns current OSC data
and typed last-saved archive data in one default call. Only the public read is
enriched; cue-editor dependencies and Light Patch writer guards are unchanged.
The archive reader initially supports QLab 5.5.10/build 5510. Unknown fields,
uninterpretable variants and broken references produce explicit partial coverage.
Pages are bounded to 1,000 records per section and 2 MiB of serialized result.
An individually oversized record is explicitly omitted; continuation can still
reach later records.

## Automated checks

- Final suite: **2,089 passed, 35 skipped, 61 subtests passed** on macOS.
- FastMCP CLI inspection of `fastmcp.json` succeeded against current source.
- Tests cover typed public serialization, source-independent failures,
  clean/dirty documents, concurrent changes, remote/unavailable native access,
  invalid archives, unknown fields and outputs, active versus residual objects,
  unused definitions, nested groups, scalar/RGB parameters, configured USB,
  1,000-instrument inventories, byte limits and continuation progress.
- Writer archive and public-contract regressions passed in the same suite.

The first full-suite attempt ran inside the socket-restricted sandbox and was
interrupted after local fake OSC servers could not bind. The final run used
the approved local-socket environment and passed.

## Native saved-file evidence

The retained native QLab 5.5.10 research sample with SHA-256
`935f9bae82cb594b894045a003c0a6b424893fe6d175a0f50ee5fd27ecb2bbc6`
was read without modification. The new decoder returned six active instruments,
four groups and four stored definitions, with complete known-field coverage and
zero diagnostics. Unreachable residual objects did not inflate the inventory.
The bytes were identical before and after inspection. Private sample files are
not included in the repository.

## Live MCP evidence

A FastMCP `Client` called the current source tool against the already open
authorized test workspace, with write mode disabled. QLab reported version
5.5.10. A single default call returned OSC plus `saved_patch.status="ready"`,
`document_modified=true` and `freshness="possibly_stale"`.
Both sources contained an empty patch; comparison reported agreement only for
its documented observable fields, with `atomic_snapshot=false`. The workspace
file's SHA-256 was identical before and after the call. No Save, Close, Open,
cue execution or output setter was sent.

Computer Use accessibility inspection also observed the empty Light Patch
table. No patch field was changed. A later screenshot showed a different
settings tab, so it is not treated as a screenshot validation of that table.

## Installed MCP acceptance with a nonempty patch

After restarting the installed MCP, an actual tool-driven test was performed
in the authorized disposable workspace. The existing pending edits were saved
through the gated Save tool. A reviewed `qlab_edit_light_patch` batch then
created three instruments, two nested groups and three workspace definitions:

- A 16-bit dimmer at Art-Net Net 2/Sub-Net 3/Universe 4, addresses 511–512,
  raw DMX home 257 and a note.
- An RGB instrument at Net 2/Sub-Net 3/Universe 5, addresses 10–12, three
  physical channels and a virtual color parameter referencing those channels.
- A second RGB instrument with no output assigned.
- A group containing the two patched instruments, and a parent containing
  that group plus the unpatched instrument; both groups had notes.
- An additional definition with no consumers.

The installed `qlab_get_workspace_light_settings` returned all these data in
one default call: three instruments, two explicit saved groups and three
definitions, including the unused definition. Nine explicit assertions checked
inventory, directions/footprints, Art-Net coordinates, virtual parameter width,
unpatched state, direct nested membership, definition deduplication, home/units
and dirty-document freshness. All passed with zero saved-section diagnostics.
The OSC-generated `all` group was correctly separate from the two explicit
saved groups.

Technical and exhaustive calls both retained the OSC payload and returned
the same saved configuration. Calls with `limit=1` reconstructed instruments,
groups and definitions by following the returned continuation requests. Each
section completed in three calls with no lost or duplicate saved records.
All twelve inspection calls reported the same saved-file SHA-256 as the
writer's verified result, so the queries did not rewrite the file.

Computer Use observed QLab's actual Light Patch table: addresses 10–12 and
511–512, matching Art-Net fields and notes, the unpatched instrument and the
parent group's two direct members/three expanded instruments. The native Light
Definitions view listed all three definitions, including the unused one.

The test elements were subsequently removed by a reviewed MCP batch. Fresh
installed-tool readback confirmed zero instruments, zero explicit groups and
zero stored definitions, matching the initial empty patch. The document
remained open. No cue was executed and no global library definition was created.

## Limits

Physical DMX, USB device availability and other QLab builds were not tested.
The nonempty live acceptance used Art-Net and unpatched configuration; it did
not invent a USB device. Large byte-budget cases, malformed archives and
concurrent-change failures remain covered by automated tests rather than
destructive live experiments.
