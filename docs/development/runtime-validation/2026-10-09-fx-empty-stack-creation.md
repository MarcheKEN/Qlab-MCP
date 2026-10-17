# Video FX: creation and restoration of 58 effects

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-10-09. QLab 5.5.10.

## Environment and procedure

Single workspace: `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`, path checked in the preceding UI audit:
`<redacted-local-path-851cab375f>.qlab5`.
MCP checks verified identity, Edit Mode, Edit access and absence of activity before
writing. No cues, Preview or signals were executed.

The list `Codex — Video FX 60 (pruebas, desarmadas)`, UUID
`E0C6E403-447C-5F5C-83DC-EE1D89E8B57D`, was created. Video fixtures use
`<redacted-local-path-b5e5675827>.png` and are disarmed. They remain in the
workspace for later inspection.

All writes used the public tools through `FastMCP Client(mcp).call_tool` and the
connector configuration. This proves updated source behavior; the installed MCP
process requires a restart. No setters were sent through an unrestricted OSC
client. Each change used a dry run, fresh token, one setter, full readback and
restoration with another token.

The [JSON evidence](2026-10-09-fx-empty-stack-creation.json) preserves calls,
setters, errors, reads and restorations; it omits tokens and credentials. It
includes experiments preceding the final contract. In particular, the final
contract requires registered defaults: it retains no path for learning unknown
defaults during a production write.

## Results

- **58/60 effects** added and identified with a native getter by name and indexed
  inventory. Their complete initial parameters were recorded in
  `video_fx_catalogue.json`; values were not invented from documentation.
- All **58 enabled** states changed true → false → true, with one write per step
  and verification of the full stack.
- **55 effects** could be deleted and reinserted, preserving complete defaults.
  Deletion of FalseColor, GlassLozenge and ReflectedTiles was blocked by native
  attributes without a verifiable documented setter.
- Parameters changed and restored: ColorControls/inputBrightness,
  WhitePoint/inputColor, NinePartTiled/inputFlipYTiles, Screen/Choose_Effect,
  GlassLozenge/inputRadius, ReflectedTiles/inputWidth and Window/Size_W.
  These cover numbers, vectors, booleans, enums and native shape differences.
- ColorControls was added to a nonempty Gamma stack, moved from index 1 to 0 and
  deleted; the original Gamma stack was restored without changes to parameters
  or neighboring effects.
- **LinearKey and DropShadow:** all four documented `add` and `insert` tests
  returned OSC `status=error`; fresh reads confirmed an empty stack. QLab's
  filtered log records `unrecognized video effect name` for both names, although
  the UI and dictionary give those same names. The final version rejects both
  before sending a setter.

## Native differences and corrections

Keys only narrow candidates; a native getter must prove the type. Reads preserve
all attributes, including extras and values outside documented bands. A documented
key absent from the aggregate has no writable baseline.

| Effect | Difference observed in 5.5.10 |
| --- | --- |
| FalseColor | Aggregate has inputColor0/inputColor1; the catalogue publishes no setters. |
| GlassLozenge | Native Point_1/Point_2 versus documented Point_0/Point_1. |
| ReflectedTiles | Native _inputX/_inputY versus _protocolInput_X/_protocolInput_Y. |
| Window | Four components present; aggregate inputRectangle absent. |

No aliases were inferred for these keys. Present, documented components can be
edited; the rest remain blocked or read-only.

Scalar vector getters did not provide a reliable baseline. NinePartTiled's scalar
boolean setter made its fixture unreadable. Vector and boolean parameters now
use internally generated JSON and aggregate getters. WhitePoint and NinePartTiled
passed changes and restoration through this path.

The user explicitly authorized deleting **only** the NinePartTiled fixture
`70B9C83D-D41F-584B-A6FE-5EB6E3D8262C`. It was deleted with a dry run and fresh
token; its replacement is `A63DA827-BDC7-59E2-BCD3-690E814558F8`. Evidence
preserves the original failure and that replacement; no other cues were deleted.

## Validation limits

This does not prove all 262 parameter setters, submode combinations, duplicate
instances or visual playback results. New tests used Video; Camera/Text share
the engine, with automated regressions and earlier Text evidence, but all 58
creations were not repeated for each family. No new UI comparison occurred in
this series: the preceding audit compared menu and catalogue with Computer Use.

Failure to create LinearKey/DropShadow is observed: QLab 5.5.10 returns
`status=error` for both documented endpoints, and its log says
`unrecognized video effect name` for each. UI tooltips and the dictionary document
exactly those names; the symptom points to QLab's OSC creation resolver. The
deeper internal cause is unidentified. Other OSC creations worked in the same
workspace and transport. Both remain blocked. Version, unambiguous identity,
known defaults, documented bands and reconstruction-before-deletion restrictions
remain.

## Final checks

- Focused tests: **123 passed**.
- Full suite: **1688 passed, 35 skipped, 61 subtests passed**.
  Transport tests required local UDP/TCP connections; the restricted attempt
  failed to open sockets without demonstrating a regression.
- `Client(mcp).list_tools()`: **74 tools**, generic editor removed and all three
  visual editors include the 60 effect names in their schema.
- Final MCP reads of all **58 fixtures**: disarmed, correct type, parameters
  equal to their registered defaults.
- Final state: **0 running, 0 paused**, one workspace; `git diff --check` has no
  errors. Preexisting workspace warnings were not corrected.

## Later deletion-guard correction

The first version blocked deletion of FalseColor, GlassLozenge and ReflectedTiles
because it tried to validate their undocumented native attributes as writable
parameters. Source now permits reconstruction planning only when every
nonwritable attribute matches its recorded QLab 5.5.10 creation default. Only
documented parameters enter the setter; differences in unknown attributes still
block. Regressions cover the three defaults, a changed documented parameter and
unknown attributes differing from their defaults.

This correction passed automated tests, but has not yet been verified with a
structural operation in QLab. The installed MCP must load the new code; live
validation remains pending and must not be described as verified.

## Follow-up: remaining parameter coverage

The source MCP tested and restored 76 additional baseline-backed destinations
across 58 Video cues: 50 cues/63 setters, then 8 cues/13 setters. Both batches
completed, and fresh reads confirmed all 58 original values, cue identities,
disarmed state and healthy state. Combined with the earlier 181 unique
destinations, 257 of 262 catalogue destinations now have reversible write
coverage. Five still lack a readable baseline: GlassLozenge `Point_0_X` and
`Point_0_Y`, ReflectedTiles `_protocolInput_X` and `_protocolInput_Y`, and
Window `inputRectangle`.

Computer Use inspected all 58 changed cues and matched their selected effect
identities; all 73 changed scalar values were visible in the inspector. The
boolean and color-vector controls were also inspected. Final MCP inventory
reports all 65 test-list cues disarmed and healthy; workspace status reports
zero running and zero paused cues. No cues were executed.

The full suite, before the final status-reporting refinement, returned 1541
passed, 188 failed, 36 skipped and 30 subtests passed. Representative transport
failures could not start the local UDP test server in this environment. The
focused Video FX/visual suite passed after the refinement (134 tests).
`git diff --check` passed.

The installed MCP still blocks a dry-run deletion of FalseColor (#270) with
`FalseColor/inputColor0: unknown catalogue destination.` It planned or sent no
setter. This confirms the local reconstruction-guard fix is not loaded in the
active connector. Do not run the three pending delete/reinsert checks until the
MCP reloads the updated source.

## Follow-up: multi-effect edit and stack round trip

On 2026-10-09, the active connector edited cue #297
(`8CC4E312-185A-565C-A75E-173612FE5461`) in the same 65-cue test list. The cue
was disarmed, healthy and not running. Its original stack was ColorControls,
WhitePoint, NinePartTiled, Screen.

One MCP call sent four operations across indices 0–3: a numeric value, RGBA
vector, boolean and a two-key JSON update (enum plus number). Fresh readback
matched every requested value. Computer Use showed the same values in the
inspector: saturation 0.750; White Point color `[0.85,0.4,0.2,1]`; Flip
Vertically off; Screen sharpness 0.800 and `Line Screen`. A new dry run/token
restored the original four values; fresh MCP reads and the inspector then
matched the baseline, including `Dot Screen` and saturation 1.000.

The same cue passed reversible stack checks. Screen moved from index 3 to 1,
then returned to index 3 with fresh tokens. The UI showed the changed order;
MCP full-stack readbacks preserved all four types, enabled states and parameters.
WhitePoint was then deleted at index 1 and reinserted there. MCP and UI showed
the three neighboring effects during deletion and the original order after
insertion. Because insertion restores the recorded creation default rather
than this cue's custom color, a separate confirmed `inputColor` edit restored
`[1,0.5,0.25,1]`; final MCP and UI reads matched exactly.

During the temporary inserted default, MCP read `inputColor=[1,0.2527676,1,1]`
while the accessibility color summary showed `rgb 1 0 1 1`. The color panel did
not expose numeric components to Computer Use, so this temporary default's
UI/OSC precision comparison remains unresolved. The cue was restored to its
pre-test value. Final scan: all 65 cues in the test list remained disarmed and
healthy; zero cues were running or paused. No cue was executed.

## Follow-up: current workspace recheck

The active connection still resolves exactly one `redacted-workspace-6b31c91e.qlab5` workspace
in QLab 5.5.10, Edit Mode, with write readiness `ready`. A fresh scan read all
65 cues in the FX test list; all are disarmed, healthy and not running. The 60
FX fixtures comprise 59 numbered cues and the replacement NinePartTiled cue
#296. MCP detail reads confirmed all 60 exact effect types and identities. All
58 effects with registered creation defaults match their complete recorded
parameter payloads (floating values compared within 1e-6). The manually added
LinearKey and DropShadow have no registered creation defaults; their current
parameter reads matched the QLab inspector.

The installed MCP performed a reversible `NinePartTiled/inputFlipYTiles`
boolean edit on cue #296: `false → true → false`, with a fresh dry run/token,
one setter per step, and fresh readback after each. Computer Use showed the
toggle on and then off at the corresponding steps. No cue was executed.

Fresh reads of the four-effect stack on cue #297 and UI inspection agreed on
order and values: ColorControls, WhitePoint, NinePartTiled, Screen. The active
MCP again rejected dry-run deletion of FalseColor #270, GlassLozenge #280 and
ReflectedTiles #285 before planning or sending any setter because their native
attributes are absent from the active connector's catalogue. The local source
contains the restoration guard fix, but this running connector has not loaded
it; those three delete/reinsert checks remain pending a connector restart.

## Follow-up: four-effect edit and restoration

In a fresh run, one MCP call edited four indexed effects in cue #297:
ColorControls saturation `1 → 0.85`, WhitePoint color
`[1,0.5,0.25,1] → [0.8,0.45,0.2,1]`, NinePartTiled vertical flip
`true → false`, and Screen width `6 → 7`. The dry run planned four setters;
the execution sent four setters once. Fresh MCP reads matched all four values.
Computer Use selected each effect in the inspector and showed the same values.

A second fresh dry run/token restored all four baselines in one MCP call.
Readback and UI matched: saturation `1`, WhitePoint `[1,0.5,0.25,1]`,
vertical flip on, Screen width `6`. The final MCP scan read 65/65 cues in the
test list, all disarmed and healthy; no cue was running or paused. No GO,
Preview, or external signal was sent.
