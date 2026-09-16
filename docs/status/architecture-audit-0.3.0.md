# Architectural Audit 0.3.0

Date: 2026-08-13

## Result

`no extraction for 0.3.0`.

The audit found no unambiguous extraction that would reduce risk without mixing
FastMCP contract, token, validation, or runtime changes. The current
architecture is retained for this release.

## Evidence

```text
src/qlab_mcp/write/operations.py  11,516 lines / 490,785 bytes
src/qlab_mcp/write/registry.py     2,555 lines / 124,438 bytes
src/qlab_mcp/server.py             1,306 lines / 50,260 bytes
```

`operations.py` concentrates the write mixin, Create, Edit, Move, Delete,
preflight, confirmation tokens, execution, and readback for several QLab
families. Its helpers share state, result contracts, and safety boundaries; a
separation during 0.3.0 could alter preflight order, token consumption, or
post-operation verification.

`registry.py` concentrates property specifications, normalization, validators,
gates, and the capability catalogue. It is a natural boundary for a later
review, but not a safe extraction of a single family without changing the
profile and operation contract.

`server.py` maintains the FastMCP boundary: tool registration, schemas,
annotations, timeouts, and response models. Removing the public alias is a
localized reduction; it does not justify restructuring the registry in this
release.

## Criteria for After 0.3.0

A future extraction must isolate a complete family, preserve imports and public
schemas, retain the same gates and token payloads, and first pass that
family's contract and write tests. Until that boundary exists, stability and
release evidence take priority.
