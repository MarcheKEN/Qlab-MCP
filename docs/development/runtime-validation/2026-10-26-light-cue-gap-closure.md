# Light cue audit follow-up — 2026-10-26

## Implemented scope

Three audit gaps are closed in source without adding tools or dependencies:

- `qlab_get_light_cue_details` includes `saved_curves`: separate saved-archive
  provenance, hash, QLab version/build, dirty freshness, up/down types, parameters,
  points, resolution, mirror and domain metadata. Unknown classes/fields remain
  inspectable with explicit partial coverage. Reads do not save or reopen.
- `qlab_edit_light_cue_curves` accepts point replacement for Linear as well as
  Custom. Other curve kinds retain their existing point restrictions. Existing
  archive transaction, identity, confirmation and recovery checks are retained.
- The shared Light command analyzer handles compact numeric and matching-prefix
  ranges, including bracketed selectors. Exact instrument/group names containing
  hyphens take precedence. Parsing and expansion are bounded.
- Cue-native AppleScript targets exactly one already-running QLab installation,
  verifies path/PID/bundle/version/build, and checks identity around setters.
  Trigger snapshots and scalar Load Time/Target dependencies bind that identity
  into confirmations. The application dictionary at `/Applications/QLab.app`
  remains a compile-time dependency, not the runtime event target.

Curve detail is limited to 4,096 points per side and the existing 2 MiB response
budget. Counts, truncation and omitted enrichment are explicit. A dirty document
returns last-saved data labelled possibly stale; concurrent document/file changes
discard the enrichment. OSC detail survives unavailable archive enrichment.

## Native source acceptance

Target: `mcp_prueba.qlab5`, workspace
`95F0A03D-140E-4673-974A-E76748EBB023`, QLab **5.5.10/build 5510**.
The running installation was `/Users/filarmonica/Desktop/QLab.app`.

Public FastMCP Client calls against current source checked the clean, inactive
document in Edit Mode, then read Light cue
`A1B43231-CA7A-466A-A7E6-C1974D875D2A` (number 12,
`LIGHT_DISARMED_BROKEN`). Both saved Custom curves were readable.

A fresh preview and confirmation applied an ascending Linear curve with points
`(0, 0)`, `(0.4, 0.7)`, `(1, 1)`. Execution reported `verified`, document reopened,
and saved curve verified. Fresh detail agreed. Computer Use observed Linear in
the native Curve inspector and its intermediate point at 2 seconds/70% on the
5-second cue. No cue was executed.

A separate preview and fresh confirmation restored the original ascending Custom
curve and its two points. The subsequent reader assertion matched both original
curve sides, including their metadata. Recovery was retained. Rewriting a keyed
archive does not imply byte-identical restoration.

On October 26, another public source read with native triggers returned `ok`,
no errors and ready saved curves from the Desktop installation. The clean saved
file hash was `954a8d88970ba3c10509527008b6bf663b1c986c493fc4a671a2af92a6bdff01`;
it was identical before and after that read. The restored curves were Custom.
This follow-up did not exercise a native trigger activation or scalar setter.

## Automated and installed verification

Full suite: **2,338 passed, 35 skipped, 61 subtests passed**. Tests cover stable
and dirty reads, concurrent changes, unknown fields/classes, point/byte limits,
Linear edits, exact hyphen names, compact/named ranges, long adversarial input,
application identity validation and changed-process confirmation rejection for
triggers, Load Time and Target assigned numbers. Contract inspection retains
**87 tools: 52 reads and 35 gated writes**. `git diff --check` passed.

The non-editable package was rebuilt explicitly and its changed runtime files
were compared byte-for-byte with source. After the user restarted the MCP, direct
attached calls returned connection `ready`, the exact clean/inactive document
and the Desktop installation, PID 11477. Light details with native triggers
returned `ok`, `partial=false`, no errors, and both restored Custom curves with
`saved_curves.status=ready`. Their hash matched the hash above and a fresh file
hash after the read. This attached follow-up performed no setters; the actual
Linear write/reopen/UI/restore acceptance used the public source Client above.
An attached dry run of the same three-point Linear request returned `planned`,
the expected Custom-to-Linear diff and empty `executed_operations`.

## Remaining boundaries

This does not establish complete Settings UI parity. New NDI/Syphon/Blackmagic
input assignment needs backend-specific native serialization and reopen evidence;
Blackmagic also needs the relevant hardware. The complete process device registry
and unlicensed global output selector have no validated public read/write backend.
LinearKey/DropShadow effect creation and compound virtual-control command syntax
still need accepted native samples; existing effect-instance handling is unchanged.

Global/personal library writes, Dashboard/live operation, playback and physical
signal remain outside scope. AppleEvents addressed by application path retain a
process-exit/resolution race; identity checks reject changed-process writes, but
do not constitute a guarantee that macOS can never resolve or launch an app.
Unknown outcomes must be read back, never automatically retried.
