# Fixed AppleScript Control fields

## Accepted scope

Read and edit Load `loadTime` and Target `assignedNumber` through the existing
tools. Reuse exact UUIDs, 1–50 cue batches, whole-batch preflight, five-minute
signed single-use tokens, fresh identity/dependencies and readback. No cue
execution, arbitrary scripts, new dependencies, version change or release.
Preserve existing checkout changes.

## Implementation and validation

1. Check the installed SDEF and official documentation; distinguish saved
   settings from `/loadAt` or running Target. Support documented negative seconds.
2. Add regressions, then a fixed JSON-argument AppleScript bridge. Keep it local,
   do not launch QLab, and preserve OS Automation errors. Treat timeouts and
   unexpected post-send failures as uncertain, with no resend.
3. Integrate typed fields, explicit transports, capabilities, partial reads,
   confirmations and dependency checks into the existing Control executor.
4. Check public schemas and the full suite; test source MCP against QLab 5.5.10,
   inspect UI, and restore both fields with new tokens. Update active docs.

## Interface rulings

- Control executor → bridge: `transport="applescript"`, `address=null`, exact
  UUID/property, previous/requested values and target dependencies. No fake OSC.
- Bridge → reader/executor: JSON scalars with exact native identity/type;
  unavailable native reads preserve OSC data and block that property.
- Change `cueTargetID` separately from either native field; renumber an assigned
  cue separately. These combinations invalidate the assumptions being confirmed.
- A placeholder can store these settings without becoming playback-ready.
  An empty assigned number clears configuration; it never clears another cue's
  current target. Nonempty numbers resolve to a unique workspace UUID.

## Review focus

Review process timeouts and errors before/after a possible setter, argument
injection, local/app identity, signed-token coverage and dependency changes,
cross-cue batch conflicts, partial-read capabilities and restoration semantics.
The checkout includes unrelated prior work: review this phase's integration,
not the entire uncommitted history.

## Completion evidence

Implemented the two typed fields and fixed native bridge in existing tools.
Live source-MCP validation matched the QLab 5.5.10 inspector and restored the
fixtures with fresh tokens: seven native setters, two OSC setters, no actions.
Final reads confirmed restored, disarmed/inactive fixtures and mixed-source
coverage. See the [runtime report](../../development/runtime-validation/2026-10-10-control-applescript.md).

The fresh review's missing-target-evidence finding was reproduced and fixed;
follow-up found no additional actionable issues. Focused checks passed 286
tests; the full suite passed 1745 tests, with 35 skips and 61 subtests.
Public schemas retain 74 tools and require an MCP restart to become connected
runtime evidence. Existing checkout changes, version and dependencies remain
preserved; no release or commit was requested.
