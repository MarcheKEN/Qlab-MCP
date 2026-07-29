# Current Docs

Use this folder for active status and docs that still guide implementation.

- `active_roadmap.md` - current phase status and safety boundary.
- `coverage/` - current coverage snapshots and internal matrices.
- `workorders/` - active/status-audit workorders and completed workorder history.
- `architecture/` - current architecture snapshots.
- `plans/` - current refactor or execution plans.
- `research/` - project research that is not official reference material.

Historical plans that no longer guide current work belong under `docs/archive/`.

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
