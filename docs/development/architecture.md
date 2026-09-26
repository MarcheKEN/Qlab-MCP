# Current Architecture

This describes the current QLab MCP development surface based on 0.3.0. Historical graphs and refactor
analysis live under [`docs/archive/`](../archive/README.md).

The 0.3.0 architecture audit concluded
[`no extraction for 0.3.0`](../status/architecture-audit-0.3.0.md): the current
write boundaries are retained until a future family-level extraction can prove
contract and safety preservation.

The supported threat model and accepted risks are defined in the repository
root [`SECURITY.md`](../../SECURITY.md). The current hardening rejects
invalid domain settings inputs, non-representable OSC numbers, massive or
sensitive cue payloads, and oversized `lightCommandText` input before OSC
traffic.

## Public boundary

Light and Group reuse the family executor; Group also reuses bounded container
traversal. Playlist reads are mode-dependent and followed by fresh identity/mode
verification. The completed response is size-checked without patch expansion.

Control/organization cues use the same family executor with an accepted-type
set and type-selected models. Filtering precedes pagination; detail reads
verify that the concrete type remains unchanged, including changes within the
family. Devamp and Reset are typed blocks, not separate transports or tools.

Fade, Network, MIDI/MIDI File, Timecode, and Script also use the family
executor. A conditional extension reads only the fields of the selected
message, output, fade, or target mode, then rechecks identity and selector.
Failures in secondary reads preserve confirmed identity as partial data.
Sensitive Network text and Script source require the technical profile.

`src/qlab_mcp/server.py` owns the FastMCP instance, the 48 decorated tools,
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
- `cues/family.py` — shared scoped inventory and exact typed detail execution
  for Audio, Mic, Video, Text, Camera, Light, Group, Control, Fade, Network,
  MIDI/MIDI File, Timecode and Script; family models constrain requested keys;
- `settings/` — settings inventory, detail normalization, and redaction;
- `status.py` — derived workspace status;
- `runtime/read_cache.py` — short-lived safe-read cache and single-flight;
- `osc/` — address validation, OSC encoding, UDP/TCP request sessions, sender-IP
  and OSC reply matching, deadlines, and socket cleanup. UDP source-port
  filtering remains intentionally unimplemented pending QLab 5.5.10 evidence.

Reads use explicit workspace qualification once a workspace is selected.
Technical profiles are opt-in; Text details include visible text in safe mode.
Cache entries are invalidated around writes;
verification reads are fresh.

Workspace Settings reads use six domain tools and the shared domain executor.
Video has a three-query overview plus UUID-only Stage and Output Route tools.
The exact tools reuse the settings transport/redaction helpers and provide typed
summaries with an optional redacted technical payload. Internal settings readers
remain available to Workspace Status and Cue Details; their Video overview uses
embedded regions from the bulk stages response without per-stage queries.
An explicit generic QLab error on an exact Video object triggers one same-domain
inventory read to distinguish confirmed absence from a read failure. Timeouts
and denied replies do not trigger this check or a retry.
Shared validation rejects malformed OSC envelopes and documented settings
payload shapes before summarization. Invalid overview routes become partial
errors; invalid exact reads return `setting_payload_invalid`.

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
first Workspace Settings write separate from cue-edit orchestration. The
`qlab_edit_workspace_settings` tool currently accepts only the typed
`general.minGoTime` operation; future researched operations stay outside the
executable registry until their own implementation wave. Real writes require
exact targeting, readiness, deterministic preflight, the required fresh token,
one setter per operation, cache invalidation, and fresh readback. A timed-out setter is never resent automatically; later reads
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
