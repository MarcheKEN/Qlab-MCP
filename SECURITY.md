# Security Policy

## System and Scope

QLab MCP is a local FastMCP server that inspects QLab 5 workspaces and exposes
narrowly gated cue-editing workflows over OSC. The supported deployment is on
the operator's machine, with QLab reachable through `QLAB_HOST`.

This policy covers the shipped MCP server, its OSC transport, read profiles,
workspace/cue/settings resolution, input validation, and gated write paths. It
does not turn QLab into a remote show-control surface: GO, playback,
Dashboard, panic, raw OSC, broad `/live` writes, and arbitrary AppleScript are
not supported.

## Threat Model and Trust Boundaries

The initial trust model is deliberately local:

- QLab, `QLAB_HOST`, and the operator's machine are trusted.
- The MCP caller is not trusted with respect to arguments. It may send
  malformed, unexpected, nested, or extremely large values.
- A hostile process on the same network is outside the initial threat model.
- QLab 5.5.10 is the runtime evidence boundary. Other QLab versions require
  separate verification.

The primary boundary is:

```text
MCP caller arguments -> FastMCP validation -> QLab MCP validation -> OSC/QLab
```

Workspace and cue identifiers must remain explicit and unambiguous before an
operation is resolved. `QLAB_PASSCODE` is operator configuration, not a tool
argument. Local file access follows the MCP process account and OS permissions.

## Security Invariants

- Invalid or over-limit input is rejected with an MCP error; it is never
  silently truncated, rounded, saturated, or converted.
- Validation that can be completed locally happens before workspace resolution,
  token creation, or OSC traffic.
- A failed validation sends zero OSC messages.
- Workspace settings reads use six domain-specific tools; no public settings
  batch or arbitrary section selector is exposed.
- Sensitive cue detail/query responses are capped at 50 cues and 1 MiB.
- `lightCommandText` is limited to 65,536 UTF-8 bytes, 2,000 lines, and 2,000
  analysis results.
- OSC numeric values must be representable by the OSC wire format. Values are
  rejected rather than clamped or rounded.
- `scriptSource` is the canonical script field. `scriptText` is not a public
  OSC/read-profile field. Script contents are exposed only through explicit
  technical family profiles or explicit sensitive generic profiles.
- Writes are disabled by default. Their universal safety sequence is defined
  below; token cardinality, atomicity, and rollback vary by operation.
- A timed-out setter is never retried automatically. Matching fresh readback
  may confirm it; otherwise the result remains failed or inconclusive.
- Tokens are single-use and process-bound where the operation requires it.
- The server does not execute cues or expose GO, playback, Dashboard, panic,
  raw OSC, or arbitrary AppleScript.

### Fixed local AppleScript fields

Load `loadTime`, Target `assignedNumber` and fixed native cue Triggers use AppleScript. The existing
editors require the same OSC Edit permission, Edit Mode, inactive workspace,
whole-batch preflight and signed single-use confirmations as their OSC fields.
The bridge requires macOS, a loopback `QLAB_HOST` and exactly one running QLab
instance at `/Applications/QLab.app`; it never launches QLab. macOS Automation
permission belongs to the actual MCP host process and is not bypassed.

The script is fixed: arguments are JSON data passed to `osascript` without a
shell, never script source. Only explicitly allowlisted saved setters exist. Workspace and
cue UUID/type, previous value, target, Edit Mode and activity are checked inside
the script before its single setter. Nonempty assigned numbers resolve to a
unique cue UUID in the same workspace and are bound to the confirmation.
Remote OSC configurations have no local AppleScript fallback. Timeouts and
unexpected exits after a possible setter are uncertain and never resent;
fresh readback is still required. A proven preparation failure sends no setter
and requires a new dry run after token reservation.

### Workspace document lifecycle

Document inventory/open/save/close use a separate fixed local AppleScript
bridge. Open requires an empty native workspace inventory and fingerprints an
existing `.qlab5` file/package with bounded size and entry limits; execution
rechecks the fingerprint and inventory before one `open` event. Save is limited
to the current path, saves all unsaved changes, and binds the token to a bounded
fingerprint. Close uses `saving no` only after a fresh clean-state check; dirty
documents are never discarded. Every event requires local write readiness and
a single-use token, then a fresh native inventory. A timeout is never retried.

The native `modified` flag is not a revision counter: edits made while it is
already true cannot be detected by comparing that flag. Save therefore can
include edits made after its dry run. Opening beside an already open document
is blocked because this bridge cannot prove unique internal workspace identity
before QLab assigns the new UUID. These lifecycle tools require exactly one
running `/Applications/QLab.app`; they do not control a remote instance.

Native Trigger reads are opt-in (`include_native_triggers=true`). A complete
snapshot includes all supported Trigger fields, MIDI display/numeric aliases,
Timecode components, armed state, continue mode and skip-if-disarmed. Tokens
bind that snapshot; the script repeats it immediately before its one setter,
and verification checks neighboring fields. Configuration requires the relevant
trigger disabled. Enabling MIDI, Wall Clock or Timecode requires a disarmed cue,
Do not continue and Skip if disarmed off; those safety fields and activation
cannot share a call. Disarming alone does not stop auto-continue/auto-follow.
Hotkey enabling is blocked because key/modifier identity is not scriptable;
disabling is supported. No incoming signals, capture or global overrides are
sent by these tools. These gates do not certify safety after subsequent arming.

## Write Workflow

The FastMCP response cache is restricted to static `tools/list` definitions
(five-minute TTL, one-MiB item limit). Tool calls, resource and prompt operations
are explicitly excluded. It does not cache readiness, dry runs, tokens or setter
results, and does not disable input/output validation. Existing safe OSC read
TTLs and write invalidation remain in place; expiry-scan scheduling does not
extend the lifetime of any observed value.

All real Create, Edit, Move, Delete, and Workspace Settings write requests use
this universal sequence:

1. Resolve one explicit workspace and exact cue/container identifiers.
2. Run `qlab_check_write_readiness` and stop on any blocker.
3. Run `dry_run=true`; review the plan, diff, warnings, errors, and confirm that
   `executed_operations=[]`.
4. Use only the fresh token or per-operation gates returned by that plan.
5. Execute once. Never automatically retry a timeout or identity ambiguity.
6. Require fresh structural or property readback before declaring the result
   verified or choosing recovery.

### Create

`qlab_create_cues` is the public cue creation tool. It accepts one to 100 ordered
types and exactly one destination UUID (Cue List, Group, or Cue Cart), with an
optional direct-child insertion anchor for a List or Group. Cue Cart creation
is restricted to one non-Group cue in an empty cart, without an anchor.
The `confirm:createCues:v2` token binds order, destination, placement, and fresh
structure. Execution chains verified UUIDs and stops without automatic rollback
when a sequence item fails. It applies no initial setters or cue numbers and
does not claim GO readiness. QLab may assign numbers through workspace defaults.

`qlab_create_cue_lists` separately creates one to 50 empty root Cue Lists or
Cue Carts with QLab defaults. Its confirmation token binds the root structure;
execution verifies each new UUID, type, position, and empty contents. Creation
is sequential and has no automatic rollback.

### Edit

Family editors require a signed five-minute, single-use confirmation for every
setter. Tokens bind the tool, workspace, cue identity/type, indexed operation,
prior/requested values and dependencies. The complete batch is validated and
reserved before mutation. Tokens cannot authorize excluded or unverified setters.
OSC setters prepare `/alwaysReply` on the same UDP socket/TCP session. The two
fixed AppleScript setters check their preconditions inside the script.
Both verify fresh saved state. No automatic retry or rollback; restoration uses new tokens.
`qlab_edit_cues` is no longer public. FX structure requires a complete stack and
verified effect identity; Text formatting preserves all observed run attributes
and compares effective intervals, including unchanged neighbors.

### General settings

Workspace Settings writes are split among General, Audio output patch, Video
output route, stage, and region tools. Each targets exact UUIDs and one typed
property or one mute/solo cleanup. They use a dedicated
`confirm:workspaceSettings:v1` token bound to object, operation, baseline and
requested value. The tools require zero running or paused cues before token
issuance and again before the setter, send exactly one qualified saved-settings
setter, then require fresh no-argument readback. Before sending the setter,
`/alwaysReply` is enabled on that same UDP socket or TCP session. Preparation
failure sends no setter and requires a new dry-run if the token was consumed.
Status-only acknowledgements are accepted explicitly for known Settings setters;
read queries still require data. A timed-out setter is never
retried. Matching readback
may confirm the outcome; mismatch or unavailable readback remains failed or
inconclusive. The zero-activity gate is a conservative MCP safety policy, not
an asserted QLab requirement. The current activity reader cannot prove
workspace-wide Audition state, so Audition must remain disabled by operator
policy.

### Move

`qlab_move_cues` uses exact UUID targets and one dedicated
`confirm:moveCues:v1` token. Moves are sequential and non-atomic; fresh
parent/order readback determines whether a timeout converged. Recovery requires
inspection and a new dry-run/token.

### Delete

`qlab_delete_cues` uses exact leaf UUIDs, one exact empty `Group`, or one
root-preserving recursive container request with `confirm:deleteCues:v1`.
Direct container deletion is limited to an inactive empty `Group`; Cue Lists
and Cue Carts remain recursive-only. Deletes run sequentially and have no
automatic rollback. Fresh existence readback must confirm disappearance and,
for recursive requests, root preservation.

## UDP and Reply Integrity

UDP replies are currently accepted only after sender-IP and OSC reply/address
matching. The source port is intentionally not filtered: QLab documents the
client's reply destination, but the project has no verified QLab 5.5.10 source
port guarantee.

This is a defense-in-depth limitation, not an authentication claim. A hostile
same-network process is outside the initial scope. Separately, a delayed reply
for an earlier request must not be accepted as the fresh reply for a later
request with the same OSC address. Request-scoped reply sessions and the fake-UDP
regressions in `tests/test_osc_transport.py` exercise this correlation property;
they do not establish source-port authentication or universal runtime proof.

## Reportable Findings

Report a finding when a supported path demonstrates one of these impacts:

- bypassing a write gate or confirmation token;
- sending OSC after validation has failed;
- targeting a different workspace or cue than the explicit request;
- exposing script contents, local paths, credentials, or other sensitive data
  outside an explicitly sensitive profile;
- accepting an OSC value that cannot be represented on the wire;
- allowing unbounded caller-controlled work to cause material local resource
  exhaustion;
- accepting an obsolete UDP response as authoritative fresh readback.

Severity depends on reachability, the local trust model, whether QLab can be
mutated or output activated, and whether the behavior is a documented explicit
operator choice.

## Out of Scope and Accepted Risk

The following are outside the initial security boundary unless the product
threat model changes:

- injection by a hostile process on the same network;
- physical output, playback, GO, Dashboard, panic, and show-control behavior;
- broad OSC feature coverage, `/live`, relative setters, raw OSC, and
  unrestricted scripts or file-target edits;
- arbitrary AppleScript or fields outside the fixed saved-setting allowlist;
- schema tightening that would break existing MCP clients without an explicit
  compatibility decision.

These exclusions do not waive the integrity requirement for stale or
misattributed replies, nor the requirement that all supported writes remain
fail-closed.

## Known Limitations and Evidence

- Delete acknowledgement and Move shallow-health fixes have bounded live
  evidence in [`docs/status/current-state.md`](docs/status/current-state.md)
  and its linked dated reports. Those tests do not prove all future QLab states.
- UDP source-port behavior has not been captured from QLab 5.5.10 because macOS
  capture permissions were unavailable. No source-port filter should be added
  until reproducible packet evidence exists.
- Runtime evidence uses disposable workspaces, exact UUIDs, inactive cues, and
  the sequence dry-run -> fresh token -> one setter -> fresh readback ->
  rollback. No GO, playback, Dashboard, or physical output is part of that
  evidence.
- Large QLab replies may use the existing TCP fallback. This does not imply
  degraded physical playback or output failure.
- Read profiles and public result shapes are compatibility contracts. The
  server may return structured runtime errors while FastMCP/Pydantic may reject
  malformed schema-level input before the handler runs.

Security policy changes require review against the supported QLab version, the
local threat model, and the write-safety invariants above.

### Mixed control cue edits

`qlab_edit_control_cues` accepts 1–50 distinct cue UUIDs with strict typed
properties; it does not accept profiles, arbitrary operations or cue actions.
All preflight checks and signed five-minute single-use confirmations must pass
before the first setter. Tokens bind workspace, cue identity/type, previous and
requested properties and target dependencies; reservation is atomic within the
server process. A restarted server invalidates existing confirmations.

The batch is sequential and non-atomic. Each setter prepares `/alwaysReply` on
the same connection and accepts a status-only acknowledgement explicitly, then
reads fresh values. Preparation failure sends no setter. Timeout triggers
readback, never resend; mismatches stop pending operations. No automatic rollback
runs. Reset selects the target mode before assigning a validated patch/cue UUID;
patch clearing is blocked. Cue targets require known health and inactivity.
Fade & Stop scope requires a scalar integer readback; bulk boolean replies cannot
confirm scope. Timecode values require the containing list's current SMPTE format
and do not enable triggers. No capture, incoming signals, `/live`, playback or
Audio Maps are enabled by this tool.

The separate `qlab_edit_devamp_cues` and `qlab_edit_target_cues` reuse this same
writer and bind confirmations to their tool names. Strict schemas exclude
patches, target modes, duration and temporary properties. Devamp settings require
an inactive healthy Audio/Video target; Stop target requires Start next enabled.
Target assignment requires an inactive healthy cue accepting cue targets and
rejects Fade. Target's Cue Number tab is unavailable via documented OSC and is
not simulated by cue execution or temporary retargeting. Boolean scope readback
blocks Fade & Stop changes even if returned from the scalar endpoint.


### Saved visual cue editing

`qlab_edit_video_cues`, `qlab_edit_camera_cues` and `qlab_edit_text_cues` share the
Control writer's signed, tool-bound, five-minute single-use confirmations and
batch-wide preflight. Identity, type, exact baseline and routing dependencies
are read fresh; running, paused or auditioning source cues block writes.
The whole workspace must be inactive and have Edit access and Edit Mode.
Each setter prepares alwaysReply on its connection, accepts known status-only
acknowledgements, and verifies fresh state. Preparation failure sends nothing;
timeout never retries a setter. Sequential batches have no automatic rollback.

Media retargets require existing absolute files; no configured root allowlist is
enforced. The agent must obtain conversational permission to access the files.
Audio levels use validated channel bounds and a 0.001 dB verification tolerance
for QLab's saved-level quantization. Rotation reset verifies its quaternion;
mute/solo cleanup verifies empty channel inventories. Text scalar styles require
uniform, present format attributes; content replacement verifies first-character
format inheritance. Unknown baselines and unvalidated channel/effect operations
stay blocked. No /live writes, Audio Maps, cue execution or signal capture.

Visual warning recovery is restricted to removing confirmed mutes/solos or
clearing nonempty readable channel inventories on inactive, explicitly unbroken
cues. Broken/unknown health does not qualify. OSC crop lists and integer
preservePitch readings are normalized at the read boundary; request schemas stay
strict. Timecode format comes from a fresh, UUID-checked List/Cart payload.
Scale edits bind the aspect lock as a dependency; contradictory pairs fail
preflight, and scale restoration precedes enabling the lock. Missing slice
inventories do not prove absence and block slice edits. A non-timeout setter
error remains an error even if readback matches (including QLab's media-end
boundary behavior); no automatic resend or implicit rollback is introduced.


FX type proof uses native metadata or a named native getter uniquely matching an
indexed payload; parameter keys alone never authorize a write. Structural
5.5.10 writes bind version, full stack and applicable Fade dependency inventory.
Native creation defaults for 58 effects are recorded from isolated QLab 5.5.10
fixtures. LinearKey/DropShadow add/insert are blocked after fresh readbacks proved
no creation. Unknown defaults remain blocked until native evidence is recorded.
Existing LinearKey/DropShadow instances remain editable with full native identity
and baseline proof. DropShadow's observed `Color` key uses the documentary
`inputColor` RGBA validation without changing the requested wire spelling;
both spellings cannot target the same instance in one update. This does not
enable add/insert or deletion without reconstruction evidence.
Documentary keys can differ from runtime keys; named getters must prove identity,
and missing parameter baselines never authorize writes. Deletion still requires
reconstruction proof, including all unknown attributes; ambiguous instances stay
blocked. Vector/boolean parameter setters use internally generated JSON to retain
native types; their baseline and verification use full aggregate readbacks.
Text formatting uses
UTF-16 boundaries, nearest percentages and bounded Latin word selectors with
verified whitespace, guillemet/curly-quote/em-dash delimiters. Color-only edits
also admit the verified NBSP, guillemet, curly-double-quote and em-dash characters. Every observed companion attribute
must be preserved; emoji can trigger fallback even for color. Non-Latin fallback and
partial shadows remain blocked. Partial font changes require a complete mapping
already observed in the cue. Font inventories disclose names/styles, not glyph
coverage or an inferred mapping. No new playback capabilities are exposed.

## Remaining cue family adapters

The nine UUID-only family editors use the signed Control executor for every
write, including family settings and indexed operations. Public profiles/raw
OSC are excluded. Batches contain 1–50 unique UUIDs of one family; at most 50
typed indexed operations per cue. Conflicting aliases/destinations are rejected.
All cues and dependencies are validated before writes, and confirmations are
reserved for the complete batch. Tokens are signed, expire after five minutes,
are single-use/process-bound and bind tool/workspace/cue/type, canonical indexed
property, baseline/request and family dependencies. Generic tokens cannot
authorize these tools. Patch metadata is bound by hash, not copied into tokens.

Every setter rechecks Edit access/mode, workspace inactivity, cue identity,
exact baseline and dependencies. `/alwaysReply` preparation shares the setter's
UDP socket/TCP session; preparation failure records no setter. Empty `data` is
allowed only for known setter acknowledgements; queries retain strict replies.
One setter, one fresh verification, never an automatic retry/rollback. Timeout
success requires matching fresh readback. Failure/uncertainty or the time budget
leaves later operations pending. Batches are sequential and non-atomic.

Selectors that reset fields require a separate dry run from dependent settings.
Before/after snapshots expose their effects. Slice changes verify full expected
inventories; bulk clears require complete affected state. Unknown object ownership,
input capacity, target compatibility, Device Definition/MSC activation metadata,
template defaults or scalar baselines block the corresponding edit. File
existence/format checks and MIDI Type 0/1 validation apply. LTC zero remains
observed only.
Script source/compilation, Audio Maps, /live, cues/signals and unsupported inspector
settings remain excluded. Historical runtime reports do not establish present
runtime readiness or coverage of all setters.

### Local media discovery

Before searching, inspecting or assigning local media, the agent asks the user
directly for permission in the conversation. `qlab_search_media_files` then
searches the MCP user's home folder by filename substring. It is bounded to 20,000 entries,
five seconds and 100 results, and skips symlinks. The operating system still
controls which files the MCP process can read. FileTarget edits retain existing
file, format, confirmation and fresh-readback validation; no folder allowlist
is required.


### Local audio analysis

`qlab_analyze_audio_file` is read-only and independent of OSC/write mode. It
requires existing conversational consent for file access, an absolute regular
local file, strict typed ranges and an optional audio dependency environment.
It never downloads dependencies, plays/normalizes/saves media or executes cues.
FFmpeg/ffprobe are invoked without a shell or caller-provided flags; protocols
are restricted to `file,pipe` and supported container formats are whitelisted
before probing, excluding playlists and indirect network requests.

Probe output/logs, decode ranges, FFT working buffers, feature cache and result
JSON are bounded. Original PCM is streamed; spectral PCM is a bounded temporary
file read in small FFT batches, removed on exit. Cancellation/timeout kills and reaps subprocesses,
then the MCP wrapper waits for worker cleanup. One new calculation at a time
bounds concurrent working memory. The 256 MiB working-buffer allowance does not
represent total Python/library/process RSS. Shared call budget: 260 seconds;
ffprobe limit: ten seconds. Cache: four blocks, 128 MiB, ten-minute TTL.
Stat identity is checked across phases and before returning; it does not provide
cryptographic content integrity against an adversary capable of spoofing the
filesystem metadata. Returned paths/tables describe the authorized source.
