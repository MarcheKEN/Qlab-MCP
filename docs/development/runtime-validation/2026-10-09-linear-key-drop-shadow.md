# LinearKey and DropShadow: creation versus existing-instance editing

Date: 2026-10-09. QLab 5.5.10, single workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`. UI path:
`<redacted-local-path-851cab375f>.qlab5`.

## Diagnosis

The previous [creation report](2026-10-09-fx-empty-stack-creation.md) records
four independent add/insert requests. Each received OSC `status=error`, and
the fresh stack remained empty. The OSC replies were generic, but QLab's
filtered unified log gave a diagnostic: `unrecognized video effect name:
LinearKey` and `unrecognized video effect name: DropShadow`.
The source sends the documented effect names unchanged. The official
[parameter reference](https://qlab.app/docs/v5/scripting/parameter-reference/)
lists both names; the [OSC dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
documents add/insert. QLab's inspected menu contains both effects.

At our request the user manually added Linear Key to cue #246
(`7F5D82FF-B324-585E-8968-B1732BB40FD7`) and Drop Shadow to #291
(`89398546-0546-59C0-898F-C9557223D902`). Both stayed healthy and disarmed.
Their inspector tooltips give exactly `LinearKey` and `DropShadow`; native named
OSC getters match the indexed parameter payloads. This rules out incorrect
names and lack of the effects in the UI. Read/edit OSC access works on these
existing instances, so the observed failure is confined to creation. The
`videoEffects/add` and `/insert` routes are documented, but QLab 5.5.10's
creation name resolver rejects these exact documented names. The log identifies
the failing stage, not why that resolver disagrees with the UI and dictionary.
The AppleScript dictionary contains no Video FX creation or parameter API,
so it offers no documented workaround.

Read-only bundle inspection found no `.F53VFX` JSON resource for either effect,
and found their named native classes. ColorControls and Shutter also have no
such resource but passed OSC creation. This is an investigative clue about
different construction paths, not proof of QLab's internal implementation or
an alternative public command. No documented replacement creation route or
deeper internal cause was established. Add/insert remain blocked; no
undocumented names, raw setters or AppleScript workaround were enabled.

## Reversible checks

Installed public MCP tools, with fresh dry runs and signed tokens, performed:

| Existing effect | Parameter | Baseline | Requested | Restored |
| --- | --- | --- | --- | --- |
| LinearKey | inputCutoff | 3 | 2.5 | 3 |
| DropShadow | Distance | 0 | 25 | 0 |

Each step used one setter and fresh full-stack verification. Computer Use
confirmed the requested values and the restored baselines. LinearKey's other
user values stayed `inputContrast=4.7`, `inputKeyColor=0` (Green). These values
are user baselines, not registered creation defaults. Evidence:
[scalar checks](2026-10-09-linear-key-drop-shadow.json).

## DropShadow Color correction

QLab's native aggregate and its inspector OSC-key tooltip both use `Color`.
The static parameter reference calls that parameter `inputColor`. The MCP
previously rejected `Color` as unknown, while `inputColor` had no native
baseline. The correction accepts the explicitly requested native `Color` key
only for DropShadow, borrowing the documented four-component RGBA bounds.
No request spelling or raw attribute is silently rewritten. Conflicting
`Color`/`inputColor` destinations are rejected. `inputColor` continues to need
its own readable native baseline; metadata does not grant one.

Through the updated source's public `Client(mcp)` tools, color changed from
`[0,0,0,1]` to `[0.2,0.3,0.4,1]` and back, using a new dry run/token per step.
Each operation sent exactly one internally generated JSON `/parameters` setter;
all other parameters stayed equal. The inspector displayed both RGBA values.
The native `key="Color"` read selector and capability metadata were checked
through the updated source MCP. Evidence:
[color checks](2026-10-09-linear-key-drop-shadow-color.json).

## Checks and limits

- Current focused run (`test_video_fx_operations.py` and
  `test_visual_cue_writes.py`): **134 passed**; `git diff --check` passed.
- The last recorded full-suite run before the status-classification fix had
  **1541 passed, 188 failed, 36 skipped, 30 subtests passed**. The failures
  were local UDP server startup errors, so the full suite is not claimed green
  for the current source.
- The last recorded `Client(mcp).list_tools()` inspection returned **74 tools**;
  this follow-up did not repeat that inspection.
- Regression coverage: native color types/bounds, alias conflicts, JSON wire
  key, complete stack preservation, selected read and independent creation block.
- Local UDP/TCP checks needed sandbox network escalation; initial source calls
  failed at connection preflight and sent no setter.
- Agent UI actions only inspected/select cues; the user created the two effects.
  No GO, Preview, output signals, defaults reset or cue deletion occurred.
- Creation remains unverified/blocked; deleting these instances still lacks
  verified reconstruction. The successful parameter probes do not test every
  parameter or rendered output.

## Follow-up diagnosis

On 2026-10-09, MCP and Computer Use rechecked the user's manually added
instances. LinearKey (#246) is disarmed and healthy; its inspector values match
MCP: `inputContrast=4.7`, `inputCutoff=3`, `inputKeyColor=0` (Green). DropShadow
(#291) is disarmed and healthy; both show `Color=[0,0,0,1]`, `Alpha=1`,
`BlurRadius=10`, `Distance=0`, `Angle=0`.

The fresh read-only MCP checks in the current session read cue #246 as
`LinearKey` (`inputContrast=4.7`, `inputCutoff=3`, `inputKeyColor=0`) and cue
#291 as `DropShadow` (`Color=[0,0,0,1]`, `Alpha=1`, `BlurRadius=10`,
`Distance=0`, `Angle=0`). Both are disarmed and healthy. Computer Use showed
the same effects and parameters; each inspector tooltip reports the same OSC
name as the dictionary. This confirms the manually created instances and the
MCP readback agree.

The filtered QLab unified log from the four actual creation attempts reports:
`unrecognized video effect name: LinearKey` and
`unrecognized video effect name: DropShadow`. Thus the failure is in QLab's
OSC add/insert name resolution, not the MCP's name serialization, effect
availability, or readback. The exact internal cause remains unknown. Fresh
MCP dry runs stay blocked before any setter, so the agent cannot repeat the
known-failing call. Keep creation blocked; existing instances remain readable
and editable.

The current connector also accepted a dry run for DropShadow's native `Color`
parameter at its current value, planned one setter, and executed none. This
confirms the Color-key correction is loaded; no cue was changed.

The shared writer had a separate reporting defect: after QLab explicitly
rejected a setter, unchanged fresh readback was reported as
`verification_inconclusive`. The source now reports `verification_failed` and
preserves QLab's reply when fresh readback confirms no change. Its focused
regression passes. Current live dry runs stop at the explicit creation block,
so they do not exercise that post-send status path.

Official QLab documentation still specifies these names for Video FX and for
the add/insert commands. Its public changelog currently lists QLab 5.6.3, but
does not mention this specific creation issue. Both installed app copies on
this Mac remain 5.5.10; no newer-version runtime test was possible here.

## Static root cause: omitted name mappings (later investigation)

This evidence supersedes the earlier statements that the internal cause was
unknown. Read-only inspection with macOS `otool` of the arm64 executable in
QLab **5.5.10 (5510)** identifies the exact failing conversion:

1. OSC add/insert in `VideoCue performOscActionForActor:` requires a string
   name and calls `VideoCueInspectorController effectWithName:`.
2. That method calls `effectNumberForName:` followed by `effectWithNumber:`.
3. The name resolver contains **58** explicit mappings. Compared with the
   60-effect documentary catalogue, the missing entries are exactly
   **LinearKey and DropShadow**. An unknown name logs the observed diagnostic
   and returns an invalid sentinel.
4. The numeric factory nevertheless has both constructors: **LinearKey=150**,
   **DropShadow=129**. The UI's `addEffect:` reads the menu item's numeric tag
   and calls this numeric factory directly, bypassing the incomplete resolver.

Thus the two effects exist and can be edited, but the documented OSC creation
path cannot resolve their names. This identifies the implementation omission;
it does not establish why Figure 53 omitted the entries. No alternate spelling
in that table reaches either constructor. The OSC argument type check and
[documented add/insert API](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
require names; internal numeric identifiers are not a public workaround.

The [official download](https://qlab.app/download/) was also inspected without
installing or launching it: **QLab 5.6.3 (5603)** has the same 58 mappings,
the same two omissions, and both numeric constructors. This is static evidence
that the omission persists in that binary, not a new live validation. The disk
image was mounted read-only and detached afterwards; the running 5.5.10 and
workspace were unchanged.

### Solution and current boundary

The direct vendor correction is to map `LinearKey` to 150 and `DropShadow` to
129 in the named creation factory, followed by live add/insert regression
tests. The MCP cannot supply missing entries to QLab's private lookup table.
Do not patch the application binary or expose private identifiers as OSC API.

For now, manually adding the effect permits the already verified MCP reads
and parameter edits. A manually configured Cue Template could potentially
provide the effects for newly created cues, since QLab documents inheritance
of template settings; that alternative was not tested and changes defaults
for the cue family. It does not add an effect to an arbitrary existing cue.
Creation remains blocked until a reliable public route or corrected QLab build
is validated. No production code was changed, no cues were executed, and no
message was sent to Figure 53.

Compact [binary evidence](2026-10-09-video-fx-name-resolver.json) records
versions, SHA-256 hashes, the 58 decoded mappings, call-chain addresses and
checks. Disassembly dumps and the installer remain outside the repository in
`/tmp`. Assertions confirmed exact catalogue differences and equality of the
two resolver tables.
