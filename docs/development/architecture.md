# Current Architecture

This describes the current QLab MCP 0.4.0 development surface. Historical graphs and refactor
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

Fixed native properties use `control_applescript.py`: Load `loadTime`, Target
`assignedNumber` and supported native cue Triggers. Native Trigger reads are
opt-in through `include_native_triggers`; failed native reads preserve OSC data
and report unavailable coverage. The fixed script receives JSON arguments, checks local
app/workspace/cue identity and setter preconditions, and returns JSON independent
of the macOS numeric locale. They share the signed Control executor and expose
their transport explicitly; no arbitrary script or new public tool exists.

Fade, Network, MIDI/MIDI File, Timecode, and Script also use the family
executor. A conditional extension reads only the fields of the selected
message, output, fade, or target mode, then rechecks identity and selector.
Failures in secondary reads preserve confirmed identity as partial data.
Sensitive Network text and Script source require the technical profile.

`src/qlab_mcp/server.py` owns the FastMCP instance, the 85 decorated tools
(52 read-only and 35 gated writes),
their schemas, annotations, timeouts, and result models. QLab-backed calls
create a fresh `QLabReader` and close it after the operation; local media tools
do not use that reader. `qlab-mcp` maps to
`qlab_mcp.server:main`.

`fastmcp_entrypoint.py` is a repository-only inspection wrapper. It and
`fastmcp.json` are deliberately excluded from wheel and sdist; they do not add
another public start command.

## Read path

The public Light settings tool supplements its OSC result through
`light_patch/reader.py`. It resolves only the requested local document, reads
stable saved bytes and delegates known archive fields to `light_patch/inspection.py`.
The decoder reuses `Archive` without invoking writer preconditions or modifying
the document. Typed saved data and OSC data retain distinct source/freshness
metadata; section pagination bounds the final serialized model. The internal
OSC results used by cue editors and their signed dependencies are not enriched.

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
Technical profiles are opt-in and can expose paths, notes and Script/Network
content. Generic `full_sensitive` and `exhaustive` responses have separate
50-cue/1-MiB bounds; those are not a universal technical-family byte cap.
Text details include visible text in safe mode.
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

## Transport, deadlines and response boundaries

Without a passcode, ordinary requests use a fresh UDP socket bound to an
ephemeral port and announce `/udpReplyPort`. `QLAB_REPLY_PORT` is not the
normal fixed listener in this path. Configured passcodes select a persistent
TCP/SLIP session for the reader, with workspace authentication and session
discard on protocol/transport/preparation failures. Selected read paths use
a separate one-shot TCP helper; this is distinct from the protected session.
Read-only calls can send protocol setup such as `/connect` and `/udpReplyPort`;
they do not modify saved cue properties or execute cues.

`QLAB_TIMEOUT` bounds individual OSC transactions and native script invocations.
The server also declares per-tool call budgets; OSC operations and cache waits
respect the reader deadline. MCP startup timeout belongs to the client and is
a third separate limit. Native lifecycle subprocesses use the configured
per-invocation timeout; they do not acquire the OSC deadline automatically.

`server_responses.py` normalizes structured operation results and errors.
`sanitizer.py` removes internal diagnostic paths/stack fields; settings redaction
also protects credentials and device/network fields. These are separate from
the opt-in disclosure of show data in technical profiles. Schema validation
errors remain distinct from structured QLab/runtime errors.

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

## Local documents and media

`workspace_documents.py` uses its own fixed AppleScript bridge, invoked through
the normal fresh-reader wrapper. Get returns the selected document and the
full local inventory, including other open documents’ paths and names.
Save/Close require existing-workspace write readiness, Edit Mode and inactivity;
Close rejects dirty documents, and Save includes all pending edits. The dirty
flag is not a revision identifier. Open requires an empty native inventory,
write-enable, a readable `.qlab5`, a bounded fingerprint and a document token;
there is no existing UUID for OSC readiness before opening.

Open/Save fingerprints are bounded to 64 MiB and 4,096 entries, with unsupported
package entries/symlinks rejected. Document tokens expire after five minutes
and are single-use/process-bound. Every attempted event requires fresh native
readback; a no-send acknowledgement is blocked and an unacknowledged response
stays uncertain. No automatic event retry is performed. The native bridge
verifies and targets the unique running local QLab installation and requires
Automation permission. Its compile-time terminology uses the installed
`/Applications/QLab.app` dictionary; cue-native helpers retain their own guards.

`media.py` searches home by filename with entry/time/result bounds and skips
symlinks. `audio_analysis.py` resolves an authorized file, lazily loads optional
Python dependencies, invokes bounded FFmpeg/ffprobe subprocesses without a
shell and returns paged source-relative measurements. Conversational consent
is an agent obligation; the server cannot verify it. OS access checks remain.

## Sources of truth

- Public MCP contract: `src/qlab_mcp/server.py`, models, and
  `tests/test_server_tools.py`.
- Write capability policy: write registry/allowlist and write-mode tests.
- Imported QLab protocol: `docs/references/` plus checksum tests.
- Current project state: `docs/status/`.
- Historical plans: `docs/archive/`; dated runtime/research/review evidence also
  remains under indexed `docs/development/` directories. Original counts and
  failed observations do not override current source or establish new proof.
- Agent-facing contract research:
  [`2026-08-13-mcp-agent-ux-and-edit-cleanup.md`](research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md).

### Light Definition catalogues and authoring

`light_patch/catalogue.py` reads the bounded local bundled LZ4/keyed archive and
personal `.qlablight` JSON sources. Source/content IDs disambiguate identical
names. Workspace catalogue entries reuse stable last-saved inspection. Compact
pages exclude parameters; an exact definition ID selects full details.

`light_patch/definitions.py` owns definition-only batches and validated native
imports. It reuses the archive planner and document transaction, with a separate
`lightDefinitions` token family and catalogue fingerprint dependencies rechecked
before Close. Public patch batches contain instruments/groups only. Native
channel positions and extended RGB outputs are retained; unsupported variants
remain visible but blocked. Libraries are never written.

### Light cue curves

`light_patch/curves.py` plans bounded, exact-UUID edits against active cue-list
containment. Changed Fade/shape branches and point chains use copy-on-write;
non-containment cue references do not make residual objects active. The separate
public tool shares the document transaction but has its own token family and a
saved-archive postcondition checked before replacement and after reopening.
OSC-visible patch verification remains separate from curve verification.

Passive video inventories share the stable saved-video decoder and existing OSC
summary readers. `video_native.py` isolates fixed CoreGraphics/AVFoundation
metadata getters in a bounded subprocess, using only the Python standard library
and system frameworks. It does not open capture sessions or output devices.
`video_settings.py` retains separate source identities, validates saved stability
around metadata enumeration and budgets every serialized inventory page. Native
metadata is never substituted for a remote QLab host's hardware inventory.

### Video archive writes

`video_models.py` defines strict typed batches; `video_archive.py` plans graph
edits using the existing NSKeyedArchiver decoder. `video_geometry.py` implements
validated stage/mesh transforms. `video_editing.py` binds passive source/display
and mask dependencies and checks native OSC readback. `workspace_archive.py`
contains the shared lock/token/recovery/close/exchange/reopen transaction;
`light_patch/transaction.py` retains the lighting entry point. Existing single
stage/route/region OSC setters and internal OSC readers remain independent.
