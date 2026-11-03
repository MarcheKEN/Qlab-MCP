# Light Definition catalogue and authoring acceptance — 2026-10-21

## Scope

QLab **5.5.10/build 5510**, local macOS. Calls used a real FastMCP Client against
this checkout, with the existing configured QLab connection. No passcode, vendor
library payload or private workspace archive is included in the repository.
The connected desktop MCP still needs a restart to discover the new tool schema.

Two public tools were added:

- `qlab_get_light_definitions`: compact source-aware catalogue, exact detail,
  filters and pagination. Workspace definitions use the last saved archive.
- `qlab_edit_light_definitions`: workspace-only definition CRUD and validated
  native imports, using the existing document transaction with separate tokens.

Definition actions were removed from public patch batches. The internal archive
planner retains them for shared implementation and synthetic fixtures.

## Catalogue observations

- The installed bundled library decoded read-only through macOS LZ4 and
  NSKeyedArchiver to **5,793** `.qlablight` JSON records.
- The personal library contained four definitions. Source-aware IDs distinguish
  personal and bundled definitions independently of matching display names.
- Detail for `BAC500 - 7` returned seven physical scalar channels and a virtual
  color control with red/green/blue/white/warmwhite/amber bindings, default -2.
- Channels, names, units, homes, width, default and virtual bindings were
  compared with the native Light Definitions window. Its seven physical rows
  and six virtual component bindings agreed with the imported configuration.
- Native CMY/HSI/Pan-Tilt/Muxer and other unsupported variants remain readable
  with explicit import blocks. The catalogue does not claim universal import.

## Native transaction tests

The authorized test workspace had an unresolved recovery from an earlier patch
write. That recovery was not removed, marked verified or rolled back. Acceptance
used a bounded temporary copy, closing/opening through document MCP tools. The
first temporary import reproduced the older post-reopen OSC verification issue;
its file and recovery were retained, and the setter was not resent.

Root cause: closing/reopening the document invalidated its authenticated OSC
session. The transaction now discards that client session before fresh readback;
this is a connection reset, not a setter retry. A regression covers its ordering.
A second temporary file retained the first result for continued acceptance.

Confirmed through gated previews, executions and fresh reads:

- Import of the full known `BAC500 - 7` definition, including channel positions,
  default virtual color and extended white/warm-white/amber bindings.
- Creation of an unpatched instrument using the imported definition; execution
  returned `verified` with `native_patch_verified=true`.
- One definition batch created a custom 16-bit scalar with raw-DMX home 257,
  imported a bundled 16-bit definition under a new name, updated the assigned
  RGB definition manufacturer and renamed that definition.
- The rename updated its instrument reference, and native/file readback matched.
- Attempting to delete the assigned definition was blocked before any execution.
- A separate batch deleted both unused 16-bit test definitions and returned
  `verified`. The remaining renamed definition was returned by exact saved detail.
- Existing cues, other patch objects and Dashboard MIDI were not edited by the
  definition operations. The original workspace bytes were hash-verified before
  reopening the original path; original recovery remained untouched.

All test instruments introduced by acceptance had **no output**. No GO, audition,
playback or physical DMX test was performed. Temporary-file audio warnings do not
establish media problems in the original project.

## Automated coverage

Synthetic tests cover source identity, filters/detail/pages, independent source
failure, invalid/duplicate JSON, size limits, links, unknown variants, 16-bit
channel gaps, extended RGB bindings, default validation, duplicate names,
footprints, in-use deletion, rename references, dirty/no-op states, expired/reused
confirmations, changed catalogue dependencies and rechecking before Close.
Existing transaction tests cover file drift, other documents, uncertain lifecycle
phases, recovery and single-use token behavior. FastMCP contract tests cover both
new tools and rejection of definition operations by the public patch tool.

The final test result and FastMCP inventory are recorded in current-state.md.
Physical output, other QLab builds and unsupported native import variants remain
outside this acceptance.
