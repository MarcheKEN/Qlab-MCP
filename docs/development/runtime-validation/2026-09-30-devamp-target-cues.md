# Edit Devamp / Target validation — 2026-09-30

## Environment

QLab **5.5.10**, `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`.
Computer Use confirmed the path
`<redacted-local-path-851cab375f>.qlab5`.
Other workspaces stayed open as authorized by the user; no setters targeted them.
TCP tests used temporary cues in the fade list; originals were not edited. No GO,
cue execution, capture or external signals. Computer Use only inspected the UI
and selected cues/tabs.

## Results

[JSON record without confirmations](2026-09-30-devamp-target-cues.json).

- Temporary Start: two setters for its name and Video 29 target, preparing a
  healthy cue suitable as the Target cue's target.
- Devamp: **11 setters**, all `verified`, for name, Video 29 target,
  `devampType=2`, Start next and Stop target enabled; Duck −3/0.5 s/enabled,
  Second Trigger 2, Fade & Stop time 0.5 s and Timecode text.
- Target: **7 setters**, all `verified`, for name, temporary Start target,
  notes, Second Trigger 1/on-release, Fade & Stop time and Timecode text.
- Technical Get Control returned identities, type-specific settings, Triggers
  and capabilities pointing to the new tools.
- Target UI: Start 38.96 target and FAMILY TEST Start name; Cue Number stayed
  empty and was not edited. Devamp UI: Devamp looping cue, Start next and Stop
  target checked, Video 29 target.
- Both tools confirmed clearing `cueTargetID=""` with one setter each and fresh
  readback.
- Only the three fixtures created for this test were deleted, using the confirmed
  Delete protocol. Final UI: **252 cues**, fade **33 children**, Memo 38.95/Basics
  selection restored.

An initial Devamp fixture returned a boolean from the scalar Fade & Stop scope
query. Preflight blocked that batch before any Devamp setter, and the three
fixtures from that attempt were removed. The later attempt used fresh fixtures,
omitting the scope change; no ambiguous setter was resent. The tool retains the
block when it cannot identify a reliable integer mode. This qualifies the earlier
Control result: the scalar endpoint can return an integer, but this is not
guaranteed for every new cue.

## Automated verification

- **3325 tests and 61 subtests pass**, including Control and other tool regressions
  and UDP/TCP transport with simulated servers.
- **59 tools** in `Client(mcp).list_tools()`. Schema contracts, catalogue, README,
  descriptions and annotations validated.
- Each new tool was invoked through `Client(mcp).call_tool()` in tests.
  Live validation used the registered writer with TCP transport.
- Regressions cover strict schemas, excluded types, Devamp dependencies,
  unsuitable/Fade targets, assignment and clearing, assignedNumber blocking and
  reuse of the confirmation engine. Tokens include the tool name.
- `git diff --check` passes. No new dependencies, version or release.

## Scope

Basics, OSC Triggers, target selection and the three documented Devamp Settings.
Target's Cue Number (`assignedNumber`) has no documented OSC setter; `number`
edits the Target cue's own number, not that field. No AppleScript, temporary
retargeting or Target execution to simulate editing.

Sources: [Devamp](https://qlab.app/docs/v5/other-cues/devamp-cues/),
[Target](https://qlab.app/docs/v5/other-cues/target-cues/),
[OSC](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/).
MCP must restart to load both tools in the installed client.
