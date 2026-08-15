# Current Architecture

This describes QLab MCP 0.3.0 at the security-hardened baseline. Historical graphs and refactor
analysis live under [`docs/archive/`](../archive/README.md).

The 0.3.0 architecture audit concluded
[`no extraction for 0.3.0`](../status/architecture-audit-0.3.0.md): the current
write boundaries are retained until a future family-level extraction can prove
contract and safety preservation.

The supported threat model and accepted risks are defined in the repository
root [`SECURITY.md`](../../SECURITY.md). The current hardening rejects
over-limit settings batches, non-representable OSC numbers, massive or
sensitive cue payloads, and oversized `lightCommandText` input before OSC
traffic.

## Public boundary

`src/qlab_mcp/server.py` owns the FastMCP instance, the 14 decorated tools,
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
- `osc/` — address validation, OSC encoding, UDP/TCP request sessions, sender-IP
  and OSC reply matching, deadlines, and socket cleanup. UDP source-port
  filtering remains intentionally unimplemented pending QLab 5.5.10 evidence.

Reads use explicit workspace qualification once a workspace is selected.
Sensitive profiles are opt-in. Cache entries are invalidated around writes;
verification reads are fresh.

The public read contract keeps sensitive profiles explicit: `scriptSource` is
canonical, `scriptText` is not a public OSC key, and `exhaustive` is available
for cue details rather than mass cue queries. FastMCP/Pydantic schema errors
and structured runtime errors are separate compatibility surfaces.

## Write path

`write/safety.py`, `write/registry.py`, and `write/allowlist.py` define the
disabled-by-default safety and capability boundary. `write/operations.py`
retains batch planning and orchestration while extracted family modules own
their domain rules. `write/tokens.py`, `write/timeouts.py`, and
`write/results.py` provide shared token, deadline, and result behavior.

Move, Delete, and Workspace Settings writes have dedicated modules and public
tools. `settings/write_registry.py` and `settings/write_operations.py` keep the
first Workspace Settings write separate from cue-edit orchestration. Real
writes require exact targeting, readiness, deterministic preflight, the
required fresh token, one setter per operation, cache invalidation, and fresh
readback. A timed-out setter is never resent automatically; later reads
determine whether the result is confirmed or uncertain.

## Sources of truth

- Public MCP contract: `src/qlab_mcp/server.py`, models, and
  `tests/test_server_tools.py`.
- Write capability policy: write registry/allowlist and write-mode tests.
- Imported QLab protocol: `docs/references/` plus checksum tests.
- Current project state: `docs/status/`.
- Historical decisions and runtime evidence: `docs/archive/`.
- Agent-facing contract research:
  [`2026-08-13-mcp-agent-ux-and-edit-cleanup.md`](research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md).
