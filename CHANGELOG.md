# Changelog

## Unreleased

- Adds `qlab_get_cue_lists` and UUID-only `qlab_get_cue_list_details`, with
  typed identity/state, playhead, incoming timecode and bounded ordered contents.
  Technical reads retain typed sections and add a redacted allowlisted payload.
  Cue Carts remain separate. Public inventory: 22 tools (16 read-only, 6 writes).
- Removes Cue List detail reads from `qlab_get_cue_details`. Single and batch
  calls return an actionable structured redirect to `qlab_get_cue_list_details`;
  Cue Cart reads remain supported by the generic tool.

- Extends exact Audio Output Patch reads with routing, cue-output count and
  names, mute/solo state, and an optional single matrix crosspoint selected by
  strict `input_channel` and `output_channel` arguments. The matrix is never
  scanned automatically.
- Replaces generic Workspace Settings detail payloads with typed Audio, Light,
  Network, MIDI, choice, and empty-inventory models while retaining redacted
  technical payloads where QLab's shape is variable.
- Removes Audio Maps from the public Audio settings schema and overview reads.
  Audio patch device presence is now explicit when known and remains unknown
  when OSC omits device evidence.
- Hardens OSC and settings reads against malformed status/data/workspace
  identities, trailing bytes, invalid payload shapes, non-finite numbers, and
  unsafe credential fields. Workspace UUID matching is case-insensitive while
  preserving QLab's canonical UUID.
- Adds strict public scan limits, actionable settings-selection and Cue Details
  errors, and promotes detected Video routing problems into Workspace Status.
- Types the Workspace Status response and enriches its partial Warnings section
  with cue flags, explicit evidence provenance, and sampled known Video Settings
  problems without adding OSC reads or a new public tool.
- Splits Video reads into the compact `qlab_get_workspace_video_settings`
  overview and UUID-only `qlab_get_video_stage` and
  `qlab_get_video_output_route` tools. This intentionally removes the overview's
  `view`, `ref`, and `profile` inputs; exact reads offer `safe` and `technical`.
  This split brought the inventory to 20 tools before the Cue List additions.
  Video overview uses three bulk reads without per-stage region queries.
  Device metadata remains limited to assigned route destinations.
- Replaces the broad `qlab_get_workspace_settings` and
  `qlab_get_workspace_setting_details` public tools with six typed read tools
  for General, Audio, Video, Light, Network, and MIDI. This is an intentional
  breaking API change; the internal shared settings readers remain in use.
- Adds the documented Audio volume-limit reads (`maxVolume` and `minVolume`).
  Controls, Audition, Collaboration, and Templates remain unexposed because
  QLab provides no complete documented settings-read API for those panels.
- Adds the gated `qlab_edit_workspace_settings` tool for the single proven
  `general.minGoTime` saved-setting operation. The scope is intentionally
  complete for this PR; other Workspace Settings writes remain deferred until
  separately researched and approved.
- Defines the local threat model, security invariants, reportable findings, and
  accepted risks in `SECURITY.md`.
- Documents the PR-1 through PR-4 input limits, canonical script profile
  contract, UDP source-port limitation, and QLab 5.5.10 evidence boundary.
- Records delayed UDP reply correlation as a separate follow-up from source-port
  authenticity.

## 0.3.0

- Establishes the 13-tool public FastMCP contract for QLab inspection and gated
  Create, Edit, Move, and Delete workflows.
- Removes the breaking `qlab_update_cues` compatibility alias; use
  `qlab_edit_cues` for cue edits.
- Removes the duplicate `batch_update_cues` readiness capability key; use
  `edit_existing_cue` as the canonical Edit capability.
- Marks Edit and Move as conservatively destructive MCP metadata hints; runtime
  safety gates, confirmation tokens, execution, and QLab behavior are unchanged.
- Adds a direct Delete route for one exact inactive empty Group while preserving
  the existing leaf and root-preserving recursive routes. Lists and Carts remain
  recursive-only.
- Carries forward sequential Create, recursive Delete, hardened write/readback,
  and release CI/packaging checks. The new Group route has fixture-specific
  QLab 5.5.10 evidence; it is not a general show-readiness claim.
- Clarifies partial overview follow-up, missing settings/cue recovery guidance,
  and sequential Create count semantics without changing the 13-tool surface,
  status vocabulary, write gates, tokens, or runtime behavior.

## 0.2.0

- Exposes 13 public MCP tools for QLab inspection and gated cue creation,
  editing, movement, and leaf deletion.
- Keeps read operations safe by default and writes disabled, dry-run-first, and
  protected by readiness checks, exact targeting, confirmation gates, and
  fresh readback.
- Makes `qlab_edit_cues` the preferred edit tool while retaining
  `qlab_update_cues` as a compatible alias.
- Adds intentional Move and Delete tools with dedicated, process-bound
  confirmation tokens.
- Separates OSC transport, cache, tokens, result construction, timeouts, and
  several write families while preserving the public contract.

Earlier development plans and phase records are available in
[`docs/archive/`](docs/archive/README.md).
