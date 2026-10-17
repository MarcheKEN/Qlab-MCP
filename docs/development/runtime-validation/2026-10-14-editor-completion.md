# Editor and workspace follow-up — 2026-10-14

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Scope

This report records source and documentation changes plus live checks for Video
FX, Text formatting, Group Triggers, workspace documents, and workspace
organization. Live cue tests used QLab 5.5.10 and the disposable
`redacted-workspace-6b31c91e.qlab5` workspace (UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`) at
`<redacted-local-path-851cab375f>.qlab5`.
Readiness confirmed write mode, `/connect` edit permission, and Edit Mode. No
cue was executed and no document Save/Open/Close event was sent.

## Video FX

The family Get selectors now carry the selected instance's native enabled flag
and per-key metadata. The documentary catalogue is paginated and describes the
60 known effects and 262 parameter destinations, including types, enums, numeric
bands and whether the key is known to the reference. Documentary metadata does
not grant write permission; the existing native identity, full-stack, baseline,
and post-write checks remain authoritative. Out-of-band observations are
preserved for reading and are not normalized into the published write bands.

Five native fixture keys still have no verified mapping to a documented key:
`GlassLozenge.Point_0_X`, `GlassLozenge.Point_0_Y`,
`ReflectedTiles._protocolInput_X`, `ReflectedTiles._protocolInput_Y`, and
`Window.inputRectangle`. They remain observable where QLab returns them, but
are not promoted to writable aliases. Linear Key and Drop Shadow add/insert
remain blocked by earlier QLab 5.5.10 tests in which the setter acknowledged
without creating the effect. Existing instances are editable only when their
identity and values are fully readable. See the dated
[Video FX closure audit](../research/2026-10-09-video-fx-closure-audit.md).

Indexed Gets on cue 246 (`index=0`, `key=inputContrast`) and cue 291
(`index=0`, `key=Distance`) returned native type identity, enabled state and
parameter values. Existing-instance edits were applied and restored:

- LinearKey cue 246, UUID `7F5D82FF-B324-585E-8968-B1732BB40FD7`:
  `inputContrast` 4.7 → 4.8 → 4.7. Each step used one setter and fresh readback;
  the inspector showed 4.800 and then 4.700.
- DropShadow cue 291, UUID `89398546-0546-59C0-898F-C9557223D902`:
  `Distance` 0 → 2 → 0. Each step used one setter and fresh readback; the
  inspector showed 2.000 and then 0.000.

Both cues remained disarmed and inactive. These checks prove edits to these two
existing instances, not every FX parameter or stack operation. Add/insert for
LinearKey and DropShadow remains blocked because earlier QLab 5.5.10 tests
acknowledged those setters without creating an effect. The unselected aggregate
Get still does not prove effect identity.

## Text

The verified UTF-16 range, percentage and bounded Latin word selectors remain
available. Apostrophes, hyphenated words, combining marks within word
segmentation and other scripts still need native indexing evidence. Emoji color
changes previously caused font fallback, so those selections remain blocked.
Shadows remain blocked when attributes are missing from the fragments, JSON
transport has not been verified, or partial-line scope lacks readback. No
shadow defaults were inferred.

On Text1 (UUID `AF8C54B5-8FEC-5C90-B2E0-E558B2A6C917`), a full-text font size
edit was applied and restored: 72 → 73 → 72. Both calls planned one setter,
readback preserved Helvetica Neue Bold, red color, centered alignment and line
spacing 1.6. Computer Use showed the cue preview change from 507×152 to 514×154
and back to 507×152. The UI did not expose a numeric font-size field, so the
exact 73-point value is confirmed by MCP readback and the preview change, not by
an inspector number.

Text2 (UUID `BAE83B09-DB21-5E2E-99CE-18C3889DBB9F`) was not edited. The
inspector initially displayed 1.6 in a disabled field. Focusing the cue's text
editor refreshed the enabled field and stepper to 1.0, matching the MCP read.
This was a stale inspector display, not a readback mismatch. See the
[2026-10-11 selection evidence](2026-10-11-text-selections.md).

## Workspace documents

Source adds exact native document Get/Open/Save/Close tools. Open requires an
empty native workspace inventory and fingerprints an existing `.qlab5` document
before a single event. Save is bound to the existing path and includes all
unsaved changes. Close rejects a dirty workspace and requests `saving no`. A
single-use token, immediate preflight and fresh inventory are required; timeout
never triggers a retry. The dirty flag is not an edit revision, so edits made
while it is already true cannot be detected.

Computer Use and the in-process FastMCP call
`Client(mcp).call_tool("qlab_get_workspace_document", ...)` now agree on
`redacted-workspace-6b31c91e.qlab5`, its absolute path, Edit Mode and zero active cues. Native
Get returned UUID `8E86FE91-668B-560C-B738-4D581B5A7498` and `modified=true`.
The first elevated
read exposed an AppleScript variable collision: `row` inside QLab's `tell`
block was interpreted as an application command. Renaming it to
`workspaceRecord` fixed the bridge; `osacompile` and 33 document tests pass.
No Open, Save or Close event was sent; Save would include all current unsaved
workspace changes. Earlier dry runs were performed under a write-disabled
configuration and do not verify document lifecycle writes under the current
configuration. Current readiness is enabled, but document lifecycle operations
were outside this live test. `modified=true` was observed and the document was
not saved.

## Read-only UI cross-check

The same open workspace reports `25` Cue Lists and `1` Cart through MCP; QLab's
sidebar shows the same counts, `467` cues total, and `0` active cues. The Video
FX fixture `Codex — Video FX 60 (pruebas, desarmadas)` (UUID
`E0C6E403-447C-5F5C-83DC-EE1D89E8B57D`) returned all 65 cues with a complete
scan. MCP's indexed Get for cue 246 (`LinearKey`) returned enabled=true,
`inputContrast=4.6999998`, `inputCutoff=3`, and `inputKeyColor=0` (Green); the
QLab inspector showed 4.700, 3.000, and Green. Cue 291 (`DropShadow`) returned
enabled=true, black RGBA, alpha 1, blur 10, angle 0 and distance 0; the
inspector showed the same values.

For Text, cue `Text1` (UUID `AF8C54B5-8FEC-5C90-B2E0-E558B2A6C917`) returned
`Mcp video text`, one range `[0, 14]`, Helvetica Neue Bold at 72 points, red
RGBA and centered alignment. The QLab preview showed the same text, red and
centered. Its focused Text inspector reports line spacing `1.6`, matching both
the MCP scalar and its sole formatted fragment. Text2 returned `Otro formato`,
one range `[0, 12]`, white RGBA and centered alignment. Its preview matched.
The inspector first displayed a disabled, stale line-spacing value of `1.6`;
after focusing the text editor, the enabled field and stepper refreshed to `1.0`,
matching OSC. Text2 was not written. OSC omitted background, shadow, underline
and strikethrough attributes in both cues, and the Get returned those fields as
`null`; they remain unavailable rather than inferred. Text1's reversible
font-size test and restoration are recorded above. UI navigation and inspector
viewing changed no other cue properties, files, or playback state.

For Group, cue `subgrupo` (UUID
`EADC45F7-D2FD-578B-8329-E65046FE4565`) returned a complete Timeline read.
The Triggers inspector matched the MCP values for Second Trigger (`does nothing`,
release off), Duck/Boost (off, amount 0, 1-second fade), and Fade & Stop (off,
1-second time). Timecode Trigger was off and its format was Timecode in both
views. Fade & Stop scope remains blocked for editing because the OSC readback is
boolean and cannot identify the selected scope reliably.

The signed Group editor changed Second Trigger from 0 (`does nothing`) to 1
(`panics`) with one setter, then restored it to 0 with a fresh dry run and
token. MCP readback and the Triggers inspector matched after both operations;
the workspace stayed at 0 Active Cues.

## Latest QLab readiness and final state

The current in-process MCP registry contains 79 tools, including the Group,
Video, Camera and Text editors; `qlab_edit_cues` is absent. Readiness for the
exact workspace resolved the document, confirmed `/connect` scopes `view`,
`edit`, `control`, confirmed Edit Mode, and returned no blockers. QLab and the
workspace document both report 0 active cues. Fresh MCP reads confirmed Group
`secondTriggerAction=0`, LinearKey `inputContrast=4.7`, DropShadow `Distance=0`,
and Text1 font size 72 / line spacing 1.6 after restoration. Text2 line spacing
is 1.0 in MCP and the refreshed inspector field; Text2 was not edited.

The document reports `modified=true`; no Save was issued. The test harness's
first Text write attempt created a confirmation token in a separate local
process from the execution request. The server correctly rejected it at
preflight, the value remained 72, and no setter was sent. Re-running dry run and
execution within the same FastMCP client process succeeded. This is a harness
constraint caused by the process-local signing secret, not a QLab setter retry.

## Organization and residual capabilities

Tests now cover signed cue-owned Audio/Mic object edits, exact object UUID and
ownership checks, fresh readback, replay protection, and stopping on divergent
readback. The implementation review found no evidence to widen these gates:

- Cart cell movement still needs verified grid occupancy and neighbor readback;
  grid dimensions and cell position have no documented setter.
- Script creation has a documented `/new` route, but template-inherited initial
  state has not been verified. Script source and compilation remain excluded.
- Mic/Camera channel writes need capacity tied to the exact input device/patch.
- MSC and Device Definition writes need reliable command/type/range metadata.
- Root Cue List deletion still needs a narrowly verified native dialog flow.

These are evidence gates, not claims that every possible workspace edit has
been exhausted. `Client(mcp).list_tools()` returned 79 tools (49 reads, 30
writes). The full suite passed with 1,881 tests, 35 skips and 61 subtests under
Python 3.14.5; loopback was enabled for the suite's local fake OSC servers. No
cue execution, document event, or cue-property change through Computer Use was
performed.
