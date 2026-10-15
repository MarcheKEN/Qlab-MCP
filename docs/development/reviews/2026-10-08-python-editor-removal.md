# Python editor compatibility removal — 2026-10-08

The user authorized removal of `QLabReader.edit_cues()` and
`QLabReader.update_cue()`. Both are absent from the reader and write mixin;
production callers use the family editors and shared signed executor. Obsolete
phase-specific writer modules are removed. Common helpers needed by creation,
movement, deletion and family editors remain. Test fixtures no longer emulate
the retired methods. The API change is documented in Unreleased and the tool
catalogue; direct Python callers must migrate.

Documentation was reconciled with the source registry: 73 tools, 46 read-only
and 27 gated writes. Both catalogue tables match `Client(mcp).list_tools()`.
Workspace Audio selector zero semantics and the Workspace Status profile were
corrected; historical editor phase instructions are explicitly separated from
current instructions. Registry coverage is metadata, not write authorization.

## Verification

- Full suite: 1625 passed, 35 skipped, 61 subtests passed.
- Final focused run after fixture cleanup: 299 passed, including the
  removed-method regression, family adapters and public schemas.
- Local path/heading link scan: 482 authored links checked, zero broken links.
  Imported reference material was preserved, not rewritten.
- `git diff --check` and `git diff --cached --check`: passed.
- No new dependencies, package version change or release.

The initial sandbox run could not bind local UDP/TCP test sockets. The complete
passing run used local simulated transports outside that restriction. No QLab
workspace writes, cue execution or live UI validation were performed for this
change. Skipped tests remain unverified by this run.
