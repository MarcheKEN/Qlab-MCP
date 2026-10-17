# Workspace authoring workflow validation

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-10-10. QLab 5.5.10, one authorized test workspace, Edit Mode.
The saved path and exact workspace UUID were verified privately through MCP
and Computer Use. Private identities, names and paths are omitted from this
report. [Compact evidence](2026-10-10-workspace-authoring-workflow.json).

## Delivery

The [canonical guide](../../user/workspace-authoring.md) and project
[skill](../../../.agents/skills/qlab-workspace-authoring/SKILL.md) define bounded
reviews, staged dependency changes, report structure and three organization
examples. Reviews default to read-only; actual edits require user authorization.
The skill is project-local, with no global installation or packaging change.
No runtime source, dependency, tool name, argument or package version changed.

## Reviewed scope and confirmed problems

MCP Overview returned a complete 493-item index, including 25 List roots and
one Cart root. Computer Use showed 467 cues in 26 lists/carts: these counts
agree after excluding roots. Its 40-node tree preview was intentionally
truncated; shallow health remained unknown and was not called healthy.
Status scanned all 493 items and reported 114 broken-category entries,
four warning-category entries and four known disconnected Video routes.
These overlapping categories are not a unique issue count. Even though
Status had `partial=false`, its warnings coverage was explicitly partial.

Selected family reads and inspector contrast established:

- An Audio cue was broken and had no assigned File Target. Its safe-profile
  path was null; the empty UI target prompt established that it was unassigned,
  rather than proving an existing file was unreadable. Proposed action: resolve
  an authorized replacement and preview assignment, without editing here.
- A configured display route returned `connected=false`, a present destination
  and 1920 x 1080 size. UI showed the configured display as missing with that
  size. Proposed action: operator checks the display or requests reassignment
  to a suitable existing stage; no hardware repair was claimed.
- An Audio-target Fade had Main enabled and output 1 disabled. Its UI showed
  Main highlighted and the output inactive; editing that output's level was
  correctly blocked until activation. UI Main displayed -INF while OSC returned
  -60; raw numbers were preserved, without claiming identical numeric labels.
- Wait returned duration/post-wait 10 seconds, pre-wait zero and
  `continueMode=2`; UI showed 10 seconds, Auto-follow and Armed on. The guide
  treats the displayed follow wait as linked, not an extra ten-second delay.
- All nine cues in the reviewed scene were currently armed, although its Memo
  still said all disarmed. Current MCP/UI evidence superseded the historical
  notes; no armed state or note was changed.

## Previews and rejected plans

All requests used the installed MCP tools and `dry_run=true`; no token was
submitted for execution. Accepted requests planned two free-number changes,
one copied name and one absolute pre-wait computed from a relative increment.
The documented fictitious color/pre-wait copy and two-cue relative requests
were separately checked against public schemas; their exact fictitious values
were not written into the live workspace.

| Case | Observed result |
| --- | --- |
| Free numbers | Two setters planned; no executed operations. |
| Copy selected property | Source name read, destination name planned; source excluded from the write. |
| Relative time | Baseline zero plus 0.5 planned as absolute 0.5; no setters. |
| Occupied number | Preflight rejected the number already assigned to Wait. |
| Nonexistent target | Preflight rejected fresh identity resolution. Membership in the complete index was absent; the error alone does not establish every possible cause of an identity failure. |
| Disabled Fade output | Rejected: `Fade level requires its crosspoint to be enabled.` |
| Negative relative result | Public input validation rejected pre-wait -0.5 before writer execution. |
| Partial read | A one-item Query scan returned partial/truncated and no scene rows; no clean-scene conclusion was drawn. |

A separate visual Fade opacity preview stopped earlier because its target
health/inactivity was unavailable. That rejection was preserved; it did not
serve as proof of the later opacity activation check.

Every returned edit result had `executed_operations=[]`. The negative scalar
request returned a tool validation error and never entered the writer.

## Preservation and checks

- The final complete cue index was identical to the initial index.
- Fresh Wait/Memo identity, Basics, timing and state matched their baselines;
  the entire scene health query also matched.
- Zero running/paused cues; Computer Use displayed zero Active Cues.
- The initial list, selected cue and Basics tab were restored after inspection.
  Navigation temporarily changes selection/playhead; it does not edit cues.
- Focused docs, Control, remaining-family and token checks: **107 passed**.
- Skill `quick_validate.py`: valid. Tests check relative links/frontmatter,
  all guide tool references and the three JSON requests against live local
  `Client(mcp).list_tools()` schemas without connecting to QLab.
- Local registry: **74 tools**, generic editor absent, no new tool added.

The final local link scan checked **14 links**; evidence JSON parsing and
`git diff --check` passed. Full-suite and packaging checks were not repeated for this documentation
and skill-only change. An initial direct Python import lacked the project on
its path; setting `PYTHONPATH=src` allowed the registry inspection without
changing the environment or installing dependencies.

## Pending checks and boundary

No real setters, GO, Preview, Send, signals, `/live`, AppleScript, media search,
Script compilation or physical output occurred. This proves schema coherence,
live review/preview behavior and inspector agreement for selected facts, not
show readiness, every property, automatic skill discovery in a new client
session or an independent model's adherence to the workflow. The two blocked
FX constructors and unvalidated Text/FX cases remain unchanged.
