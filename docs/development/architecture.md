# Current Architecture

This describes the current QLab MCP development surface based on 0.3.0. Historical graphs and refactor
analysis live under [`docs/archive/`](../archive/README.md).

The historical 0.3.0 architecture audit concluded
[`no extraction for 0.3.0`](../status/architecture-audit-0.3.0.md): that release retained its write boundaries. The current family modules and
shared executor are described below.

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
family. Devamp and Reset detail reads are typed blocks sharing the transport;
Devamp editing has its own public tool.

Two saved Control fields use `control_applescript.py`: Load `loadTime` and
Target `assignedNumber`. The fixed script receives JSON arguments, checks local
app/workspace/cue identity and setter preconditions, and returns JSON independent
of the macOS numeric locale. They share the signed Control executor and expose
their transport explicitly; no arbitrary script or new public tool exists.

Fade, Network, MIDI/MIDI File, Timecode, and Script also use the family
executor. A conditional extension reads only the fields of the selected
message, output, fade, or target mode, then rechecks identity and selector.
Failures in secondary reads preserve confirmed identity as partial data.
Sensitive Network text and Script source require the technical profile.

`src/qlab_mcp/server.py` owns the FastMCP instance, the 74 decorated tools
(47 read-only and 27 gated writes),
their schemas, annotations, timeouts, and result models. QLab-backed calls
create a fresh `QLabReader` and close it after the operation; local media tools
do not use that reader. `qlab-mcp` maps to
`qlab_mcp.server:main`.

`fastmcp_entrypoint.py` is a repository-only inspection wrapper. It and
`fastmcp.json` are deliberately excluded from wheel and sdist; they do not add
another public start command.

## Read path

`QLabReader` is the reader facade composed from focused mixins:

- `runtime/connection.py` — discovery, authentication, mode, and readiness;
- `cues/` — overview, bounded indexes, queries, profiles, and cue details;
- `cues/family.py` — shared scoped inventory and exact typed detail execution
  for Audio, Mic, Video, Text, Camera, Light, Group, Control, Fade, Network,
  MIDI/MIDI File, Timecode and Script; family models constrain requested keys
  and optional indexed inspections;
- `media.py` — bounded local file discovery, with truncation reported explicitly;
- `audio_analysis.py` — optional, read-only local-file analysis independent of
  OSC and `QLabReader`; its dependencies load only when called;
- `settings/` — settings inventory, detail normalization, and redaction;
- `status.py` — derived workspace status;
- `runtime/read_cache.py` — short-lived safe-read cache and single-flight,
  pruning only when an entry can expire;
- `osc/` — address validation, OSC encoding, UDP/TCP request sessions, sender-IP
  and OSC reply matching, deadlines, and socket cleanup. UDP source-port
  filtering remains intentionally unimplemented pending QLab 5.5.10 evidence.

Reads use explicit workspace qualification once a workspace is selected.
The family and Cue List parsers share bounded compiled field validators;
this cache contains schemas, not OSC values. Unescaped TCP reply frames avoid
byte-by-byte decoding. See the [performance measurements](runtime-validation/2026-10-08-mcp-performance.md).
The static `tools/list` catalogue uses native FastMCP caching for five minutes,
before schema dereferencing. Tool calls, resources and prompts are excluded
from that middleware's cache; published schemas and validation are preserved.
Technical profiles are opt-in; Text details include visible text in safe mode.
Cache entries are invalidated around writes;
verification reads are fresh.

Workspace Settings reads use six domain tools and the shared domain executor.
Video has a three-query overview plus UUID-only Stage, Output Route, and Region
tools.
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
handles Cue creation and shared read helpers; `write/control.py` runs the
signed family edit batches, with `write/group.py`, `write/visual.py`, and
`write/remaining.py` providing family rules. The former generic Python cue
editor and its phase-specific modules have been removed. `write/tokens.py` and
`write/timeouts.py` provide shared token and deadline behavior.

Root Cue List/Cart creation and editing use `write/cue_lists.py`; root reordering
shares the Move executor. Move, Delete, and Workspace Settings writes have
dedicated modules and public tools. `settings/write_registry.py` and
`settings/write_operations.py` retain the established `minGoTime` writer;
`settings/object_writes.py` handles the other typed settings edits. The public
`qlab_edit_workspace_settings` tool was replaced by five object-specific Edit
tools. Real writes require
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
