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

## Limits

The nonempty native sample was decoded from saved bytes, not reopened for a
new live OSC/UI comparison. The live one-call validation covered the existing
empty, dirty workspace. These are separate evidence scopes. No physical DMX,
USB device availability or compatibility with other QLab builds was tested.
