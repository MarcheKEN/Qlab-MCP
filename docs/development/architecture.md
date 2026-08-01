# Current Architecture

This describes QLab MCP 0.2.0 at baseline
`83bf9c129fc27af04fcfd7b687f9e789d2cc1d34`. Historical graphs and refactor
analysis live under [`docs/archive/`](../archive/README.md).

## Public boundary

`src/qlab_mcp/server.py` owns the FastMCP instance, the 13 decorated tools,
their schemas, annotations, timeouts, and result models. Each call creates a
fresh `QLabReader` and closes it after the operation. `qlab-mcp` maps to
`qlab_mcp.server:main`.

`fastmcp_entrypoint.py` is a repository-only inspection wrapper. It and
`fastmcp.json` are deliberately excluded from wheel and sdist; they do not add
another public start command.

## Read path

`QLabReader` is the compatibility facade composed from focused mixins:

- `runtime/connection.py` — discovery, authentication, mode, and readiness;
- `cues/` — overview, bounded indexes, queries, profiles, and cue details;
- `settings/` — settings inventory, detail normalization, and redaction;
- `status.py` — derived workspace status;
- `runtime/read_cache.py` — short-lived safe-read cache and single-flight;
- `osc/` — address validation, OSC encoding, UDP/TCP request sessions, reply
  correlation, deadlines, and socket cleanup.

Reads use explicit workspace qualification once a workspace is selected.
Sensitive profiles are opt-in. Cache entries are invalidated around writes;
verification reads are fresh.

## Write path

`write/safety.py`, `write/registry.py`, and `write/allowlist.py` define the
disabled-by-default safety and capability boundary. `write/operations.py`
retains batch planning and orchestration while extracted family modules own
their domain rules. `write/tokens.py`, `write/timeouts.py`, and
`write/results.py` provide shared token, deadline, and result behavior.

Move and Delete have dedicated modules and public tools. Real writes require
exact targeting, readiness, deterministic preflight, the required fresh token,
one setter per operation, cache invalidation, and fresh readback. A timed-out
setter is never resent automatically; later reads determine whether the result
is confirmed or uncertain.

## Sources of truth

- Public MCP contract: `src/qlab_mcp/server.py`, models, and
  `tests/test_server_tools.py`.
- Write capability policy: write registry/allowlist and write-mode tests.
- Imported QLab protocol: `docs/references/` plus checksum tests.
- Current project state: `docs/status/`.
- Historical decisions and runtime evidence: `docs/archive/`.
