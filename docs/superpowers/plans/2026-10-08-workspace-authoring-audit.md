# Workspace Authoring Audit Plan

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

**Goal:** Determine whether the current MCP lets an agent build and inspect a
coherent audio/video/light scene, and identify concrete missing capabilities.

**Approach:** Exercise existing tools before proposing new ones. Separate source
contracts, live MCP observations, UI observations and unverified assumptions.
This is an audit plan, not authorization to implement new server functionality.

**Scope:** Workspace inspection, cue creation, saved edits, structure, targets,
media, timing and verification. No playback, GO, Preview, Send, incoming signals,
compilation, Script source, Audio Maps, `/live` or AppleScript writes.

## 1. Establish the runtime baseline

- [x] Inspect the connected MCP catalogue; compare it with source and current docs.
- [x] Discover the workspace and resolve exact UUID, path and QLab version.
- [x] Check Edit access, Edit Mode and absence of running/paused cues.
- [x] Inventory lists, relevant patches/stages and available test media.
- [x] Contrast names, counts, routing and relevant inspector fields using Computer
      Use for observation only. Record differences, not assumed defaults.

**Output:** Runtime identity and a table of confirmed available capabilities.
Do not mutate while identity or readiness is uncertain.

## 2. Define one small reference scene

- [x] Specify a scene with an audio file, a video or still image, a light look,
      coordinated fades and a control cue targeting a cue created in the scene.
- [x] Define cue hierarchy, routing, saved values and intended timing before writes.
- [x] Choose valid existing patches/stages. If a required Light fixture or device
      is absent, mark that part blocked; do not invent instruments or routing.
- [x] Use a new clearly named test list, approximately 6–10 cues. Keep the test
      arrangement disarmed and leave original lists and cues untouched.

**Output:** A reviewable expected-state checklist. Audio analysis may inform
musical timing, but beat estimates do not prove artistic suitability.

## 3. Build with the existing MCP tools

- [x] Create the empty list and cues through their current confirmation protocols.
- [x] Edit by family using exact UUIDs, explicit dry runs and fresh tokens.
- [x] Assign media, routing, levels, geometry, light commands, targets and timing
      only where capabilities and baselines can be verified.
- [x] Keep dependency-changing edits separate when the editor requires it.
- [x] After each write, read fresh state. Never retry a setter after an ambiguous
      result. Record applied, failed and pending operations; no automatic rollback.
- [x] Contrast the resulting structure and inspectors with Computer Use.

**Output:** An expected-versus-observed table with evidence per change. Creation
and editing success must be distinguished from a dry run and UI appearance.

## 4. Audit the resulting scene

- [x] Check missing media, broken cues and reported warnings.
- [x] Check target existence, type, workspace membership and relevant dependencies.
- [x] Check output assignment and known channel/geometry bounds.
- [x] Compare saved waits, durations and continuation modes with the intended
      timeline. Mark unknown media durations or unbounded loops as unresolved.
- [x] Distinguish intentionally disarmed test cues from accidental disarming;
      do not treat every flagged or disarmed cue as an error.
- [x] Identify fields unavailable through OSC and fields that require UI contrast.

**Output:** Findings classified as confirmed error, possible issue, unavailable
information or intentional configuration. Do not equate static consistency with
correct playback, hardware output or musical synchronization.

## 5. Exercise bounded failure cases

- [x] Submit invalid target and unsupported-property requests as dry runs only.
- [x] Check that a preflight error prevents all setters for that batch.
- [x] Verify that diagnostics tell the agent what to read or change next.
- [x] Reuse existing automated tests for forged/expired tokens and ambiguous
      timeouts; do not deliberately induce transport failures in the live workspace.

**Output:** Evidence that the agent can detect and explain failures safely.

## 6. Report and choose the next implementation

- [x] Record tools used, expected/observed state, UI contrast and unresolved limits
      in `docs/development/runtime-validation/2026-10-08-workspace-authoring-audit.md`.
      Use placeholders for private paths and UUIDs in distributable documentation.
- [x] Classify each obstacle: agent workflow, missing read, blocked setter,
      implementation defect, missing fixture or protocol limitation.
- [x] Propose at most three priorities, each tied to an observed obstacle and an
      acceptance check. Prefer a workflow/skill when existing tools already suffice.
- [x] Leave the test list clearly labelled and disarmed for review. Deletion or
      modifications to original cues require separate explicit authorization.

**Acceptance:** Every scene requirement is either verified with fresh MCP and UI
observations or explicitly blocked with a reason. No cue execution occurred, no
original cue changed, and no speculative new tool was implemented.

**Execution:** Directly in this session after approval of this plan. Code fixes
and new tools require a subsequent scoped implementation proposal.

**Executed:** 2026-10-08. All audit steps completed; source defects remain open.
See [runtime audit](../../development/runtime-validation/2026-10-08-workspace-authoring-audit.md).
