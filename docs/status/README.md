# Project Status

This folder contains only current project status:

- [Roadmap](roadmap.md) — supported, pending, and blocked work.
- [Coverage](coverage/README.md) — technical OSC and feature coverage.
- [Workorders](workorders/README.md) — active and blocked tasks.

Historical plans, completed workorders, research, and audits belong under
[`docs/archive/`](../archive/README.md).

## Evidence Labels

Current claims use these labels:

- **documented** — stated by official QLab documentation.
- **source-confirmed** — verified in this repository's current code or tests.
- **runtime-proven** — observed in the named QLab version and bounded runtime
  procedure.
- **inferred** — reasoned from available evidence but not directly verified.
- **unsupported** — deliberately outside the exposed MCP capability.

Newer QLab documentation does not promote a capability to runtime-proven or
writable. QLab 5.6.x support remains unclaimed until the same bounded,
reversible runtime proof used for the 5.5.10 baseline is repeated there.
