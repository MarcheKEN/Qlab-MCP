# Precommit validation — 2026-10-15

This record covers the prepared source, tests, configuration and documentation
for the existing pull request. It records local checks, not new live QLab write
acceptance. Historical runtime reports retain their original dates and limits.

## Scope and compatibility

The public registry exposes 79 tools: 49 reads and 30 gated writes. Compared
with the earlier 48-tool registry, 33 tools were added and exactly two removed:
`qlab_edit_cues` and `qlab_edit_workspace_settings`. Callers of those removed
interfaces must migrate to the documented typed cue editors and object-specific
workspace settings editors; they are not compatibility aliases.

The prepared changes include typed cue and settings editing, Video FX and Text
formatting, Group/native trigger handling, bounded local media/audio analysis,
workspace document operations, read/transport hardening, focused regression
coverage and their documentation. The audio-analysis dependencies remain an
optional `audio` extra; FFmpeg/ffprobe are external executables.

## Checks

- Clean CI-style environment: **1893 passed, 36 skipped, 61 subtests passed**
  in 32.01 seconds. This includes 11 capture redaction regression cases.
- Actual CLI FastMCP inspection: **79 tools**, **49 reads**, **30 writes**.
- `uv lock --check`: passed.
- Wheel and source distribution: built successfully in a temporary output
  directory, without publication or version changes.
- Local documentation links were checked: 376 links, no invalid file links.
  The workorders directory link is intentional.
- The earlier environment with optional dependencies installed returned
  **1883 passed, 35 skipped, 61 subtests passed**, before the 11 capture
  regression cases were added. Focused NumPy timeout and capture cases passed.

Skipped optional/backend-dependent checks do not constitute acceptance of those
backends. In particular, a passing base CI run does not verify FFmpeg behavior,
full media decoding, real playback, hardware output or all QLab property writes.
No new live QLab writes or cue execution were performed for this preparation.

## Publication of historical evidence

Prepared documentation replaces captured workspace/cue UUIDs with deterministic
synthetic UUIDs, workspace names with generic names, and local/media paths with
redacted placeholders. Repeated identifiers retain their relationships across
reports. These published identifiers are not live targets and cannot be used to
repeat writes. Dates, observed values, counts, failures and validation limits
remain historical evidence; redaction does not add runtime verification.

Authored prose is English. Intentional user-data names, external quotations and
protocol/API literals retain their original form where needed for evidence.
