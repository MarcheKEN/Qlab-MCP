# Project and documentation review — 2026-10-17

## Scope and authority

The baseline was commit `17aa6f2`: 448 tracked files, including 70 Python source
modules, 46 test files and 173 Markdown files. Inventory covered source, tests,
scripts, configuration, authored documentation, historical records, structured
captures, assets and imported references. Large modules were reviewed by public
contracts, control flow and relevant tests; this is not a claim of line-by-line
proof of every implementation or image pixel.

Current source and generated MCP schemas define implemented behavior. Existing
dated runtime reports establish only their own version/fixture observations.
The review does not turn static inspection or simulated tests into new live
acceptance. QLab was not contacted for this documentation task.

## Reconciled areas

| Area | Source/evidence compared | Documentation result |
| --- | --- | --- |
| Public contract | `server.py`, Pydantic models, generated 79-tool catalogue, server contract tests | README/catalogue retain all 79 tools; instructions and lifecycle descriptions distinguish native Open from existing-workspace readiness. |
| Read and transport | `qlab.py`, cue/settings/runtime/OSC modules and fake-server/cache tests | Architecture explains ephemeral UDP, passcode-selected reader TCP, separate fallback reads, deadlines, cache and response/redaction boundaries. |
| Cue/settings writes | Family/structural executors, token/registry/safety modules and regression tests | Current signed tokens and typed batch rules supersede legacy phase gates. Existing-workspace readiness, non-atomic execution and no automatic mutation retry remain explicit. |
| Native properties/documents | Fixed AppleScript bridges, lifecycle guards, fingerprints, acknowledgements and tests | Document Get discloses full local inventory; Open has its own preflight; Save includes all edits; Close refuses dirty state. Fingerprint and token limits are documented. |
| Local files/audio | Discovery, analysis/models, dependency and process tests | Scoped conversational consent can be reused; server enforcement is not implied. Optional backends, process PATH and measurement scope remain explicit. |
| Status/workorders | Current source versus October 1–14 reports | Clock/fade/mute proof is reconciled; solo, slice fixtures, unsupported native fields and other residual limits remain open. |
| Historical material | Dated research, plans, reviews, captures and archive indexes | Superseded phase roadmap archived with rebased links; standalone records link to current guidance. Original observations and counts remain dated. |
| Installation/maintenance | `pyproject.toml`, lockfile, entrypoint, CI, packaging and scripts | Locked non-editable commands, optional audio prerequisites and startup diagnosis have current guidance. CI and extra maintainer checks are distinguished. |

## Corrections and preservation

Architecture's obsolete 74-tool count is now 79 (49 reads, 30 writes). The two
retired generic editors have documented replacements. The user guide now covers
explicit recursive Group-root removal and distinguishes it from blocked root
Cue List/Cart deletion. Roadmap's old blanket Workspace Video/FX/batch bans are
historical rather than current policy.

Only documentation, MCP instruction text and tool docstrings are changed in
Python source; executable AST is compared after removing those text fields.
Imported reference/transcript/source bytes and captured JSON/images remain
unchanged. Historical screenshots and original-language excerpts are retained
as evidence, without claiming they received a new visual privacy audit.

## Verification

- Generated MCP inventory: 79 tools, 49 read-only and 30 gated writes.
- README and public catalogue tool rows are checked against that inventory.
- Final inventory: 455 files, including 180 Markdown files. All 931 relative
  documentation destinations and 99 current-guide heading links resolve.
- Reference checksums and source/execution preservation are checked separately.
- Lockfile verification and wheel/sdist build succeeded in temporary output.
- Final suite: **1,894 passed, 35 skipped, 61 subtests passed** in 32.33 seconds
  on local Python 3.11.15. Focused documentation/server/reference checks also
  passed (157 tests). Optional skips are not backend acceptance.
- Executable AST matches the baseline after excluding docstrings and the MCP
  instruction string. All 12 imported reference/source/transcript files checked
  retain their baseline bytes.
- Independent source/document review found no blocker in the canonical guides,
  architecture, roadmap, workorders and navigation. This is not an exhaustive
  semantic revalidation of historical captures or screenshot pixels.

This is a documentation/source review. No new cue writes, native document
events, playback, rendering or physical output were validated. Optional tests
can skip when their local fixtures or backend executables are unavailable.

## Final clarity review and runtime handoff — 2026-10-17

After code cleanup at `9a346bc`, a final documentation pass found two stale
blanket exclusions of native MIDI/Wall Clock configuration and Trigger
activation in the user workflows. They now refer to the existing guarded native
workflow; Hotkey assignment/enabling, capture and playback stay excluded.
The guide also states the FX catalogue's 1–10 page limit and distinguishes
Timecode SMPTE strings from Audio/Video seconds. No executable code changed.

The preceding [installed-MCP acceptance session](../runtime-validation/2026-10-17-installed-mcp-acceptance.md)
is now recorded and linked from current state, roadmap and development indexes.
It distinguishes 79 invoked tools from 26 executed writers, documents the four
preview/block-only writers, transient permission failure, incomplete media
search and selection change, and preserves untested runtime boundaries.
The final documentation pass itself made no live QLab calls.

Fresh checks covered all 182 repository Markdown files for local destinations:
**1,483 relative links** and **101 canonical-guide heading links** resolve;
all **18 JSON examples** parse successfully. Both 79-row public catalogues match the current in-process
registry (49 reads, 30 writes). Focused server, reference and authoring-document
checks passed: **145 tests**. Tool definitions remain identical to the pre-edit
snapshot. Historical records retain their dated counts and observations;
imported references, transcripts and captures were not rewritten.

The scope includes canonical guides, current status/workorders, source/schema
cross-checks, repository navigation and historical authority labels. It does
not claim a new semantic audit of every historical sentence, screenshot or
external website, or acceptance of every tool parameter combination.
