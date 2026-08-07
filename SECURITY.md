# Security Policy

## System and Scope

QLab MCP is a local FastMCP server that inspects QLab 5 workspaces and exposes
narrowly gated cue-editing workflows over OSC. The supported deployment is on
the operator's machine, with QLab reachable through `QLAB_HOST`.

This policy covers the shipped MCP server, its OSC transport, read profiles,
workspace/cue resolution, input validation, and gated write paths. It does not
turn QLab into a remote show-control surface: GO, playback, Dashboard, panic,
raw OSC, broad `/live` writes, and AppleScript fallback are not supported.

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
operation is resolved. Environment values such as `QLAB_PASSCODE` and local
file roots are operator configuration, not tool arguments.

## Security Invariants

- Invalid or over-limit input is rejected with an MCP error; it is never
  silently truncated, rounded, saturated, or converted.
- Validation that can be completed locally happens before workspace resolution,
  token creation, or OSC traffic.
- A failed validation sends zero OSC messages.
- Workspace settings details accept at most 50 requests and six sections.
- Sensitive cue detail/query responses are capped at 50 cues and 1 MiB.
- `lightCommandText` is limited to 65,536 UTF-8 bytes, 2,000 lines, and 2,000
  analysis results.
- OSC numeric values must be representable by the OSC wire format. Values are
  rejected rather than clamped or rounded.
- `scriptSource` is the canonical script field. `scriptText` is not a public
  OSC/read-profile field. Script contents are exposed only through explicit
  sensitive profiles.
- Writes are disabled by default and remain protected by dry-run, a fresh
  confirmation token, passcode/readiness checks, connection scope, Edit Mode,
  one intended setter, fresh readback, and rollback with a new token.
- A timed-out setter is never retried automatically. Matching fresh readback
  may confirm it; otherwise the result remains failed or inconclusive.
- Tokens are single-use and process-bound where the operation requires it.
- The server does not execute cues or expose GO, playback, Dashboard, panic,
  raw OSC, or an AppleScript write fallback.

## UDP and Reply Integrity

UDP replies are currently accepted only after sender-IP and OSC reply/address
matching. The source port is intentionally not filtered: QLab documents the
client's reply destination, but the project has no verified QLab 5.5.10 source
port guarantee.

This is a defense-in-depth limitation, not an authentication claim. A hostile
same-network process is outside the initial scope. Separately, a delayed reply
for an earlier request must not be accepted as the fresh reply for a later
request with the same OSC address. That correlation property is still subject
to a controlled fake-UDP investigation before any production change.

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
- AppleScript as an alternate backend;
- schema tightening that would break existing MCP clients without an explicit
  compatibility decision.

These exclusions do not waive the integrity requirement for stale or
misattributed replies, nor the requirement that all supported writes remain
fail-closed.

## Known Limitations and Evidence

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
