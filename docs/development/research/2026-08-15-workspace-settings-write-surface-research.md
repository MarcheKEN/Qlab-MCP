# QLab MCP — Workspace Settings Write Surface Research

**Date:** 2026-08-15
**Status:** Research-only. No production code, public MCP tool, QLab workspace, branch, PR, or version was changed.
**Scope:** QLab 5.5 Workspace Settings writes, with the current QLab MCP OSC architecture as the constraint.

Evidence labels used below:

- **D** — official QLab documentation/reference.
- **O** — imported QLab OSC dictionary in this repository.
- **A** — official QLab AppleScript dictionary/reference.
- **Q** — imported QClass 5.5 transcript evidence.
- **R** — repository code, tests, or policy.
- **F** — FastMCP/MCP contract research.
- **I** — interpretation or recommendation, not a runtime claim.

## Executive Summary

QLab documents ten user-facing Workspace Settings sections: General, Controls,
Audition, Collaboration, Templates, Audio, Video, Light, Network, and MIDI.
Settings persist with the workspace, but the public automation surfaces are
uneven. OSC exposes a small, exact subset of saved settings and many read-only
inventories. AppleScript does not expose a usable Workspace Settings container;
its useful entries are mostly cue properties or operational controls.

The preferred future backend is therefore **capability-specific OSC**, with no
AppleScript fallback and no raw OSC escape hatch. The first real write candidate
is the documented General `minGoTime` scalar. `selectionIsPlayhead` is also a
documented setter, but it changes the operator's selection/playhead workflow and
should follow a separate human/runtime proof. Audio, Video, Light, Network, and
MIDI settings require separate capability gates; many are read-only, unsupported,
or have ambiguous permission rows in the imported dictionary.

The recommended MCP shape is an internal, typed settings-operation registry plus
small fixed public domain tools. Do not begin with a generic path/value tool, a
dynamic tool factory, arbitrary AppleScript, or a cross-domain batch API. Keep the
existing read contract read-only. A first public settings write would be an
additive contract change and should ship as **0.4.0**, not a patch release.

The safety invariant remains:

> exact workspace UUID → readiness → baseline → dry-run → fresh operation token →
> one setter → fresh readback → explicit recovery/rollback plan.

No timeout retry, atomicity claim, automatic rollback, GO/playback operation, or
“show-ready” claim is justified by this research.

## Research Boundary and Evidence Quality

This is an architecture and evidence pass, not an implementation plan approval.
The supplied implementation SHA `f94de272...` was not present in the current
checkout, so it is recorded only as user-provided context. The locally verified
checkout is `de03a8f` on `codex/docs`; no claim below depends on the supplied SHA.

The QClass material is instructional and demonstrative. It is useful for
operational sequencing and hazards, but it is not a protocol conformance test.
The imported OSC dictionary is the primary local protocol source; its blank
permission cells are intentionally treated as **UNKNOWN**, never as write
permission. AppleScript claims are limited to entries present in the official
dictionary; absence there is not proof that an undocumented private interface
cannot exist.

## Current MCP Baseline

### Public contract

The repository is version **0.3.0** (`pyproject.toml:3`,
`src/qlab_mcp/__init__.py:5`). `src/qlab_mcp/server.py` owns the FastMCP
instance, schemas, annotations, timeouts, and exactly 13 decorated tools
(`docs/development/architecture.md:17-22`):

1. `qlab_check_connection`
2. `qlab_get_workspace_overview`
3. `qlab_get_workspace_status`
4. `qlab_get_workspace_settings`
5. `qlab_get_workspace_setting_details`
6. `qlab_query_cues`
7. `qlab_get_cue_details`
8. `qlab_check_write_readiness`
9. `qlab_create_cue`
10. `qlab_create_cues`
11. `qlab_edit_cues`
12. `qlab_move_cues`
13. `qlab_delete_cues`

The settings reader currently advertises exactly six sections:
`audio`, `video`, `network`, `midi`, `light`, and `general`
(`src/qlab_mcp/server.py:116-130`, `src/qlab_mcp/settings/workspace.py:32-64`).
Controls, Audition, Collaboration, and Templates are not currently part of the
MCP read model. That is an implementation boundary, not a claim that QLab lacks
those settings.

The server instruction block explicitly says that the current release exposes
read-only inspection plus gated structural writes over OSC; it excludes GO,
stop, panic, playback, audition, `/live` writes, AppleScript writes, and raw OSC
passthrough (`src/qlab_mcp/server.py:218-232`).

### Existing safety path to preserve

The current write path already supplies the required primitives:

- strict workspace resolution and exact IDs (`write/safety.py:32-216`);
- `QLAB_ENABLE_WRITE`, `QLAB_PASSCODE`, `/connect` Edit permission, and Edit
  Mode checks (`write/safety.py:32-216`);
- HMAC/versioned confirmation tokens (`write/tokens.py`);
- bounded convergence/deadline handling without setter retry
  (`write/timeouts.py`);
- structured operation results (`write/results.py`);
- fresh readback and cache invalidation around writes
  (`docs/development/architecture.md:41-62`);
- policy-level invariants, including no retry after timeout and no GO/panic/raw
  OSC/AppleScript write fallback (`SECURITY.md:35-70`).

The current cue registry is a useful pattern, not a place to mix settings
operations blindly. Settings need a separate allowlist because their stable IDs,
saved/live behavior, readback forms, and risk classes differ from cue property
edits.

## QLab Workspace Settings Model

QLab's official Workspace Settings documentation describes ten sections and says
settings belong to the front-most workspace, persist, and travel with that
workspace. See [Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/).

| Section | Main contents | Persistence / state | Operational risk | Automation observation |
|---|---|---|---|---|
| General | GO timing, selection/playhead, file management, display, backups | Saved workspace settings; some UI state is operational | Low to Tier 2; file/backup changes can be destructive or noisy | OSC exposes `minGoTime` and `selectionIsPlayhead`; other controls are not established |
| Controls | Keyboard, Workspace MIDI, OSC mappings, panic/hard-stop behavior | Saved mappings; actions can affect running output | Tier 2–4 | No Workspace Settings OSC family or AppleScript settings object established |
| Audition | Alternate/suppressed audio, video, MIDI, timecode, network, lighting routes | Policy is saved; audition state is operational/transient | Tier 4 when alternate patches or output suppression affect a show | OSC exposes adjacent `alwaysAudition`/monitor controls, not a complete Audition settings object |
| Collaboration | Enablement, permissions, clients, identities, Show Mode view-only behavior | Saved policy plus connected-client state | Tier 3–4; can disconnect clients or grant control | No documented settings write surface; defer |
| Templates | Cue defaults and Workspace Templates containing settings/cues/scripts/media references | Saved templates and imported settings | Tier 3–4; creation/import can overwrite or create future structure | No settings object or safe granular setter established |
| Audio | Output/input patches, routing, maps, effects, volume limits | Saved infrastructure; levels can be live | Tier 3–4; physical sound and routing | Many reads; a few setters; map write permissions are ambiguous in the local dictionary |
| Video | Outputs, routes, devices, inputs, stages, regions, warping | Saved infrastructure; visual output can be live | Tier 3–4 | Route guides, stage name, and region geometry have documented OSC setters; topology is mostly read-only |
| Light | Light patch, definitions, groups, Dashboard MIDI | Saved patch/definitions; DMX/Art-Net can be live | Tier 4 | Local OSC documents reads and undo/redo, not patch setters |
| Network | Network patches and OSC Access permissions, ports, passcodes | Saved infrastructure and access policy | Tier 4; can disconnect or grant external control | Patch list is read-only; access configuration writes are not documented |
| MIDI | MIDI output patches, MSC Broadcast, timecode-related configuration | Saved infrastructure; external devices may react immediately | Tier 3–4 | Patch list is read-only; no documented patch/device setters |

The ten sections do not imply ten future MCP tools. A section is a product/UI
boundary; an MCP operation should exist only where the protocol, identity,
readback, and safety evidence are complete.

### Adjacent features that are not ordinary scalar settings

Settings import/export, Cue Templates, Workspace Templates, backups, and
audition/override controls are workflow features. QClass shows them as useful for
preparation and rehearsal, but their write semantics are broader than a single
allowlisted property. They should not be smuggled into a generic “settings edit”
tool.

## QClass 5.5 Operational Findings

The repository instructions require reading `docs/qclass/README.md` first and
preserving transcript wording. The timestamps below are navigation evidence into
the imported Day 1–3 transcripts; interpretation and limits are kept separate.

### Evidence

| Area | Timestamped evidence | Operational signal |
|---|---|---|
| Audio patches | Day 1 Audio 3:22:29–3:25:57; Audio Patches 5:43:20–5:59:15 | Patches isolate device/routing choices from cues; disconnected devices may remain remembered; `no device` produces no sound |
| Audio limits/maps | Day 1 Volume Limits 6:01:52–6:08:46; Object Audio 6:17:04–6:20:20; Audio Maps 6:43:06–6:50:48; Day 2 Object Audio 5:25–14:56 | Maps need a cue and audio patch; test objects and physical listening are part of validation; map objects persist beyond a cue |
| MIDI/timecode | Day 2 MIDI/MSC/MTC/LTC/OSC 1:33:18–1:37:58; Timecode 1:02:43–1:06:42; MIDI timecode cue 2:03:10–2:05:24 | Patch/device/frame-rate/cabling preparation precedes cue capture and runtime confirmation |
| Network/OSC | Day 2 Network patches 2:18:06–2:31:48; Override Controls 2:40:29–2:46:27; OSC Access 2:47:14–2:51:46; Workspace Status 6:14:28–6:16:44 | Interface/IP/port/passcode and remote permissions matter; overrides suppress external output during holds; logs help diagnose delivery |
| Video | Day 2 Video I/O 5:26:30–5:29:43; Output Routes 5:46:21–6:08:54; Camera 6:57:21–7:03:46 | The chain is cues → stages → regions → routes → devices; route/stage isolation avoids rewriting cues when hardware changes; visual/physical confirmation is required |
| Lighting | Day 3 Lighting 15:34–45:05; Light Patch 57:51–1:27:26; Art-Net/interfaces 1:39:13–1:47:16 | Definition, DMX address, output, node discovery, and physical fixture mode must agree; dashboard/status/physical lights confirm behavior |
| Templates/import | Day 3 Cue Templates 49:19–51:23; Workspace Templates 6:27:18–6:30:49; Light definitions 1:46:48–1:47:16 | Templates and settings files transport preparation state but may include cues, scripts, media, or definitions |
| Collaboration | Day 3 Collaboration 4:53:16–4:58:09 | Closed local networks and explicit access configuration are recommended before clients connect |
| Rehearsal controls | Day 3 Load to Time 5:56:09–5:59:38; Cue Carts 2:46:37–2:55:47; Auditioning 7:04:22–7:12:19; Workspace Status 6:09:58–6:20:47; backups 6:46:33–7:02:31 | Rehearsal uses audition, carts, overrides, status, media copying, and backups to separate testing from public output |

### Interpretation

The recurring workflow is **prepare infrastructure → verify IDs/routes/devices →
exercise in rehearsal/audition → inspect logs/status → confirm physical or visual
and auditory output**. Settings writes that alter routing, access, patch
definitions, or audition outputs are therefore operational changes even if the
OSC value is a simple scalar.

The QClass material supports a capability-level backend decision: use the patch or
route abstraction where it isolates infrastructure from cue programming, but do
not infer that a successfully written property makes a show runtime-valid or
ready for GO.

### Limits

QClass is an instructional demonstration, not a guarantee for every device,
plugin, network, fixture, projector, or QLab build. It contains known behavioral
warnings (for example, a possible cue-object deletion anomaly) and does not prove
MCP-level acknowledgement, timeout, atomicity, or convergence.

## OSC Capability Matrix

Primary local source: `docs/references/qlab_osc_dictionary.md`. Workspace
qualification and UUID preference are documented at lines 1195–1214. Omitting
`/workspace/{id}` broadcasts to all listening workspaces; MCP must never use an
unqualified address for a write.

The matrix uses these classifications:

- **Documented R/W** — the dictionary has an explicit read/write permission row
  and a read form suitable for fresh verification.
- **Read-only** — the dictionary explicitly says read-only.
- **Unknown** — prose mentions a write or setter but the permission row is blank,
  conflicting, or otherwise insufficient for a public MCP mutation.
- **Unsupported** — no documented Workspace Settings endpoint was found.

| Section / object | Property or action | OSC surface and stable selector | AppleScript surface | Candidate / phase | Risk and evidence |
|---|---|---|---|---|---|
| General | `minGoTime` | `/workspace/{uuid}/settings/general/minGoTime {number}`; read with no arg; edit R/W, view/control read; number ≥ 0 (`qlab_osc_dictionary.md:1987-1993`) | No Workspace Settings property | **Real first slice** | Tier 2 operational policy; scalar, exact readback; O/D |
| General | `selectionIsPlayhead` | `/workspace/{uuid}/settings/general/selectionIsPlayhead {boolean}`; edit R/W, control R/W; no-arg read; toggle action also documented (`:1996-2008`) | No Settings property; related workspace UI state only | Planned after UX proof | Tier 2; changes selection/playhead workflow; O/D |
| General | Undo/redo | `/settings/general/undo` and `/redo` actions | No matching Settings command | Defer | Action semantics and scope need runtime proof; O |
| Audition | `alwaysAudition`, audition monitors | Workspace-level `/workspace/{uuid}/alwaysAudition {boolean}` and `/auditionMonitors {boolean}` are documented adjacent controls | `workspace.always audition` is get/set | Defer; not a complete settings model | Tier 4 when alternate/suppressed outputs are involved; O/A/Q |
| Controls | Keyboard/MIDI/OSC mappings, panic/hard stop | No documented `/settings/controls/*` family | Some workspace/control properties and actions, but no Settings object | Unsupported | Tier 3–4; no exact settings object; O/A/D |
| Collaboration | Enablement, client permissions, identities | No documented `/settings/collaboration/*` setter | No Collaboration Settings object | Unsupported | Tier 4; can disconnect/grant control; O/A/D/Q |
| Templates | Cue/Workspace Templates, import/export | No documented granular `/settings/templates/*` setter | No Templates object | Unsupported | Tier 3–4; broad structural effects; O/A/D/Q |
| Audio | `cueOutputChannelCounts`, output names, max/min volume | Read-only endpoints (`:1216-1233`, `:1782-1815`) | Cue-level audio patch refs only, not patch definitions | Read only | Tier 0 read; O/A |
| Audio | Output patch inventory/detail/routing | `/settings/audio/patch/{name}` or `patchID/{id}` read-only (`:1817-1834`) | Cue-level patch name/number/id only | Read only | Routing is infrastructure; no setter documented; O/A/Q |
| Audio | `cueOutputChannels` | Documented R/W integer 1–128 on audio output patch; exact permission/readback must be checked in the surrounding dictionary and runtime | No patch-definition object | Plan-only | Tier 3; output routing/physical sound; O/Q |
| Audio | Patch level, mute, solo, names/actions | Some prose documents R/W or actions; live variants and permission rows differ | Cue matrix controls and cue-level properties only | Plan-only per property | Tier 3–4; never batch by assumption; O/A/Q |
| Audio | Maps, filters, marks, objects | Inventories/details read-only; many property prose sections say write but permission cells are blank (`:1235-1248` onward) | No map/mark/object Settings classes | **Unknown; no public write** | Tier 3; resolve permission and runtime convergence first; O/A/Q |
| Audio | Test object | File target and some level/position/running prose appear writable, but permissions are incomplete; start/stop are actions | No equivalent Settings object | Defer | Tier 4 operational audio; O/A/Q |
| Video | Input patches, route inventory, route destination/device fields | Input patches and routes are read-only (`:2233-2270`) | No video input/route object | Read only | Tier 3–4 topology; O/A/Q |
| Video | Route `enableGuides` | R/W route property with route ID/name selectors; readback documented | No route Settings object | Possible later scalar | Tier 2–3 visual workflow; O/D |
| Video | Stage name | `/settings/video/stageID/{id}/name {string}` R/W (`:2340-2352`) | Cue stage refs only; no stage object | Possible later metadata slice | Tier 2; stable stage ID required; O/A |
| Video | Region bounds/origin/size/control points/grid/guides | R/W integer geometry with stage + region ID/name selectors; bounds must remain within stage (`:2400-2470` and following) | No region/stage object | Later, disposable-stage proof | Tier 3–4 visual output; exact validation and fresh visual confirmation; O/Q |
| Video | Stage size, region creation/deletion, input setters | No documented setter for topology/creation/deletion | No object model | Unsupported | Tier 4; O/A |
| Light | Light patch inventory/details/undo/redo | Local dictionary documents read-only patch surfaces and actions, not patch/instrument/address setters | No Light Patch/instrument/DMX object | Unsupported | Tier 4 DMX/Art-Net; O/A/Q |
| Network | Network patch inventory | Read-only patch list; no documented detail/setter for destination, port, protocol, or device descriptions | Cue-level network patch refs/custom messages only | Unsupported | Tier 4 external control; O/A/Q |
| Network | OSC Access permissions/passcodes/ports | No documented Workspace Settings setter | Application-level OSC override controls exist but are not a safe settings model | Unsupported | Tier 4 security/connectivity; O/A/Q |
| MIDI | MIDI patch list and MSC broadcast | Read-only patch list; no documented device/patch/MSC setter | Cue-level MIDI patch refs; cue-list timecode properties | Unsupported | Tier 3–4 external show control; O/A/Q |

### OSC-specific conclusions

1. The documented exact setters are narrow. `minGoTime`,
   `selectionIsPlayhead`, route guides, stage name, and selected video-region
   properties are materially different operations and must not share an
   untyped path/value API.
2. A blank `query` column does not mean “no readback.” The dictionary describes
   no-argument reads for several setters; the implementation must use a fresh,
   exact property read after the setter rather than a presumed setter reply.
3. `/alwaysReply` may help status acknowledgement where supported, but it is not
   a postcondition. It cannot replace a fresh no-argument readback.
4. `/live` is an explicit, separate form where documented. It is not a safe
   default and remains outside the current MCP public contract.
5. Names are selectors only when the OSC character restrictions are satisfied;
   UUIDs are the required MCP target. Map/stage/route IDs must be read first and
   bound into the operation token.

### Field-complete shortlist

The following compact view makes the required decision fields explicit for the
operations most likely to be discussed in an implementation review. “Unknown” is
deliberate: it means research has not earned a public mutation.

| Section | Sub-object | Property/action | User meaning | QClass context | OSC read/write/address/permission | AppleScript read/write/object | Preferred backend | Readback | Stable ID | Risk | MCP candidate | Phase | Evidence / confidence / notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| General | Workspace | `minGoTime` | Minimum seconds between GO presses | QClass treats timing and rehearsal controls as operator/show workflow, not output routing | Read: `/workspace/{uuid}/settings/general/minGoTime`; write same path with number; view R, edit R/W, control R | No matching Settings property/object | OSC only | Same path with no argument, fresh | Workspace UUID | T2 | Yes, narrow fixed domain tool | Slice 1 | O/D high; Q medium; runtime convergence still unproven |
| General | Workspace UI | `selectionIsPlayhead` | Lock or unlock selection to playhead | QClass separates inspection/rehearsal state from live output; selection changes can surprise an operator | Read/write same path with boolean; view R, edit R/W, control R/W; toggle action also documented | No Settings property; related UI state only | OSC only if approved | Same path with no argument, fresh | Workspace UUID | T2 | Possible, one operation only | Slice 2 | O/D high for endpoint; Q medium; UX/runtime proof required |
| Video | Output route | `enableGuides` | Show or hide route guides during setup | QClass says routes isolate display infrastructure and visual confirmation matters | Route name/ID selector; documented R/W property; exact route endpoint in local dictionary | No route object | OSC only | Same route property, fresh | Route UUID | T2–T3 | Later fixed video tool | Later | O/D medium-high; visual confirmation required |
| Video | Stage | `name` | Rename a stage without changing its geometry | QClass uses stages as infrastructure abstraction | `/settings/video/stageID/{stage_id}/name {string}`; edit R/W, view/control R | No stage object; cue stage refs only | OSC only | Same stage name path, fresh | Stage UUID | T2 | Later fixed video tool | Later | O/D high endpoint; Q medium operational context |
| Video | Stage region | `bounds`, origin, size | Change region position/size within stage | QClass requires visual adjustment on the real surface | Stage + region ID/name; documented R/W; integers must remain within stage bounds | No region object | OSC only | Same property/detail read, fresh; then visual check | Stage UUID + region UUID | T3–T4 | Planned-only until disposable visual proof | Later | O/D high endpoint; Q medium; geometry typo/limits need runtime check |
| Audio | Output patch | `cueOutputChannels`, level/mute/solo | Change audio patch output or level behavior | QClass: patch separates infrastructure from cues; physical listening and limits matter | Some individual paths document R/W; patch inventory/detail is read-only; exact permissions vary by property | Cue-level patch refs/matrix only, no patch object | OSC where each property is explicitly allowlisted | Same property/detail read, fresh; physical audio check where relevant | Audio patch UUID | T3–T4 | No public tool yet | Later | O/Q medium; property-by-property review required |
| Audio | Map/filter/mark/object | Scalar map attributes | Adjust spatial map geometry or object behavior | QClass: map needs cue + audio patch; test object and listening validate result | Read inventories/details; prose writes exist but permission cells are blank/UNKNOWN | No map object | OSC only after access/runtime proof | Exact property/detail read, fresh; auditory/visual check | Map/filter/mark/object UUIDs | T3 | Planned-only | Later | O/Q medium-low; do not infer R/W from prose |
| Light | Light patch | Definition/address/output | Configure DMX/Art-Net infrastructure | QClass requires definition, DMX address, node discovery, dashboard and physical fixture agreement | Local dictionary read-only patch surfaces; no documented setter | No Light Patch object; Dashboard is operational/opaque | None currently | N/A until API exists | Patch/fixture IDs not proven | T4 | No | Deferred | O/A/Q high for risk, unsupported surface |
| Network | Patch / OSC Access | Destination, port, protocol, permission, passcode | Connect or authorize external OSC/network control | QClass requires interface/IP/port/passcode and remote permission agreement | Patch list read-only; no documented detail/setter/access configuration | Cue-level patch refs/custom message only; application overrides are not Settings | None currently | N/A until API exists | Patch/access IDs not proven | T4 | No | Deferred | O/A/Q high for risk, unsupported surface |
| MIDI | Output patch / MSC | Device, patch, MSC/timecode configuration | Connect external MIDI/show-control equipment | QClass requires device, channel, frame rate and cabling verification | Patch list read-only; no documented patch/device setter | Cue-level patch/timecode properties only | None currently | N/A until API exists | Patch/device IDs not proven | T3–T4 | No | Deferred | O/A/Q high for external-control risk |
| Controls | Keyboard/MIDI/OSC mappings | Mapping/panic/hard-stop policy | Change how operators or controllers trigger QLab | QClass treats overrides and controls as rehearsal/live safeguards | No documented `/settings/controls/*` family | Some UI/control properties, no Settings object | None currently | N/A | Mapping IDs not proven | T3–T4 | No | Deferred | D/O/A/Q medium-high; broad operational scope |
| Audition | Alternate outputs | `alwaysAudition`, monitors, alternate patches | Redirect/suppress outputs for rehearsal | QClass uses Audition to separate rehearsal from public output | Adjacent workspace endpoints exist, but not complete Audition settings; `/live` excluded | `workspace.always audition` get/set and actions | None for first slice | Same endpoint possible, but not sufficient proof | Workspace UUID | T4 | No | Deferred | O/A/Q medium; output-routing mutation |

## AppleScript Capability Matrix

Primary source: [QLab AppleScript Dictionary v5](https://reference.qlab.app/docs/v5/scripting/applescript-dictionary-v5/).
The repository’s imported dictionary was used for the absence and property
claims below.

| Area | Dictionary observation | Read/write status | Safety implication |
|---|---|---|---|
| `application.preferences` | A `preferences controller` reference exists, but the class has no defined properties, elements, or settings commands | Unresolved; not evidence of a Settings API | Do not probe or expose as a generic object |
| General `minGoTime`, `selectionIsPlayhead` | No entries found | Unsupported by documented AppleScript surface | OSC only if runtime-proven |
| Audio patch/map definitions | Cue-level audio patch name/number/id and cue matrix properties exist; no patch/map definition classes | Cue properties only | Do not confuse cue routing with Workspace Settings infrastructure |
| Video stage/region/route | Cue stage name/number/id and cue geometry exist; no stage/region/route classes | Cue properties only | OSC is the only candidate for documented stage/region setters |
| Light patch/DMX/Art-Net | No Light Patch/instrument/interface object; Dashboard properties are opaque and `setLight` is operational | Not a Settings API | Tier 4; no AppleScript fallback |
| Network patches | Cue-level patch refs, parameter values, and custom messages exist | Cue properties only | No destination/port/protocol Settings write |
| MIDI patches | Cue-level patch refs and cue-list timecode settings exist | Cue properties only | No MIDI output patch/device object |
| Audition | `workspace.always audition` get/set and audition actions are present | Narrow operational control | Not equivalent to the ten-section Settings model; do not expose in first slice |
| Controls/UI | Workspace edit/show mode, inspector visibility, selected/current cue list, and overrides are present | UI/operational state | Frontmost/UI dependence and live-output risk |
| Templates/collaboration | No documented Settings object | Unsupported | Defer |
| Scripting | `script cue.script source` is a cue property | Cue-only; not arbitrary source execution | Never provide arbitrary AppleScript source or fallback |

AppleScript also carries TCC Automation permission, frontmost/workspace state,
stale object references, opaque records, and no documented MCP-grade timeout,
acknowledgement, convergence, or atomicity contract. The correct conclusion is
not “AppleScript is impossible”; it is “AppleScript is not a justified backend
for this Settings write surface without a separate capability proof.”

## OSC vs AppleScript Backend Comparison

| Criterion | OSC | AppleScript |
|---|---|---|
| Exact workspace qualification | Explicit `/workspace/{uuid}`; unqualified form broadcasts | Workspace/application object resolution; frontmost/UI sensitivity |
| Stable identity | QLab exposes workspace and many settings object UUIDs | Workspace UUID is readable, but Settings object model is absent |
| Readback | Documented no-arg reads for several setters; fresh read is practical | Getter behavior varies by object; no Settings container |
| Permission model | View/edit/control rows in dictionary; blanks remain UNKNOWN | macOS TCC plus QLab/UI state; no per-setting contract |
| Headless/automation fit | Existing MCP transport and OSC client | Requires Automation entitlement/user approval and UI assumptions |
| Timeout/ack semantics | Existing bounded OSC client; still must verify convergence | Not documented for these settings |
| Safety boundary | Exact address can be allowlisted | Arbitrary script/source would be an unsafe escape hatch |
| Current evidence | Specific General/Video setters; many read-only inventories | Mostly cue-level properties and operational controls |

**Decision:** OSC wins wherever the exact endpoint, permission, stable ID, input
validation, and fresh readback are all documented and runtime-proven. Neither
backend currently justifies Controls, Collaboration, Templates, Light patch,
Network patch/access, or MIDI patch settings writes. A hybrid backend may be
revisited per capability, but “try OSC then AppleScript” is explicitly rejected.

## Risk Classification and Gates

| Tier | Examples | Minimum gate |
|---|---|---|
| 0 | Read-only inventories/details | Existing read access, redaction, bounded response |
| 1 | Non-operational metadata with exact readback | Readiness + fresh token + one setter + fresh readback |
| 2 | `minGoTime`, selection/playhead, stage name, route guides | All Tier 1 gates plus explicit operator confirmation and activity check appropriate to the property |
| 3 | Audio levels/channels/maps, video geometry, patch-level routing | Disposable/inactive workspace, zero relevant activity, capability-specific token, no batch, physical/visual verification plan |
| 4 | Light/DMX, video topology/devices, Network/MIDI infrastructure, OSC Access, collaboration, audition alternate patches, panic/open/close | Planned-only until dedicated human and QLab 5.5.10 runtime evidence; no live show or connected show-critical system |

Readiness must remain layered. The existing universal check proves write mode,
exact workspace resolution, `/connect` Edit permission, and Edit Mode. It does
not prove that a workspace is inactive, that no collaborator is connected, that
an output route is disposable, or that an external device is safe. Those checks
belong to a capability-specific gate, not an overloaded universal “ready” flag.

Rollback is always a new operation: capture the baseline, produce a new dry-run,
obtain a new token, set the prior value once, and fresh-read it. No automatic
rollback or atomic transaction is implied.

## Existing Repository Architecture to Reuse

The smallest coherent future change is a new settings-specific write family,
not a rewrite of the server or cue registry:

1. Reuse strict workspace resolution and exact UUID handling.
2. Reuse `check_write_readiness` / `ensure_write_ready` for universal gates.
3. Add a separate allowlisted settings registry with fields such as:
   `operation_id`, exact OSC route template, typed args, exact readback route,
   stable selector kind, saved/live classification, risk tier, capability gate,
   numeric/range validation, and `real_write` policy.
4. Reuse dry-run/result conventions, but bind settings tokens to a new family and
   operation version. Do not reuse a cue-edit token merely because both are OSC.
5. Preserve one setter per real operation, fresh cache-bypassing readback, and
   timeout no-retry behavior.
6. Keep the implementation in a small settings-write module. Do not enlarge
   `write/operations.py` into a universal orchestration layer.

The current architecture explicitly retains family boundaries until a future
extraction proves contract and safety preservation (`docs/development/architecture.md:50-62`).

## FastMCP and MCP Architecture Options

Local research was performed against the repository’s FastMCP/MCP contract and
the current 13-tool schema/test snapshots.

| Option | Result | Decision |
|---|---|---|
| Generic `path`, `args`, or `value: dict` tool | Raw escape hatch; impossible to make the allowlist and readback contract clear | Reject |
| Giant typed union for every section | Strong typing but unstable, large schema and difficult per-operation safety | Reject for first slice |
| Dynamically generated public tools | Tool inventory and schemas become runtime-dependent; clients cache discovery | Reject |
| One fixed tool per independently validated domain | Stable discovery and clear safety boundary | Recommend |
| Internal registry + fixed tools, with a later bounded generic tool | Reuses backend policy without exposing paths; supports future growth | Recommend as the long-term shape |
| Cross-domain batch tool now | Non-atomic failure and partial-show state are too easy to misread | Defer |

MCP annotations are advisory metadata, not authorization. Mutation remains in a
tool with a typed input and structured output; read-only capability catalogs may
be tools or resources, but must not become a dynamic mutation surface.

## Recommended MCP Architecture

### Public surface

Keep `qlab_get_workspace_settings` and
`qlab_get_workspace_setting_details` read-only. Add no generic settings editor
until one domain has a complete capability proof.

The first public tool should be a fixed domain tool, conceptually:

```text
qlab_edit_general_settings(
    workspace_id: exact UUID,
    operation: "minGoTime",
    value: non-negative finite number,
    dry_run: true | false,
    confirm_token: optional fresh token
) -> typed result
```

The first implementation should allow exactly one operation per call. If
`selectionIsPlayhead` later joins the tool, use a typed discriminated operation
model with property-specific validation and gates; do not silently turn the
tool into a multi-setter batch.

### Internal registry

Each candidate operation should declare, in one place:

- public operation ID and registry version;
- exact workspace-qualified OSC path and argument encoder;
- readback path and normalization/comparison rule;
- stable target selector requirements;
- documented permission and evidence status;
- saved versus live behavior;
- risk tier and capability-specific readiness checks;
- allowed value/range/finite-number validation;
- real-write support versus planned-only status.

This registry is internal policy. It must not be serialized into a raw address or
used to accept an unrecognized operation from the caller.

### Tokens and batching

Use a new versioned token family such as `workspaceSettings:v1`, bound to the
workspace UUID, operation ID, target ID, baseline, requested value, registry
version, and expiry. A token for `minGoTime` must not authorize
`selectionIsPlayhead` or a different workspace.

Default maximum batch size is one. A later batch, if justified by a real workflow,
must preflight every item, execute sequentially, read back each item freshly, stop
on first failure, report partial completion, and make no atomicity claim. Per-item
gates are safer than one broad batch token.

### Result semantics

Results must distinguish at least `planned`, `executed`, `confirmed`, `failed`,
`timeout`, and `inconclusive`. A timeout means “setter was sent but outcome is
unknown,” not “safe to retry.” A fresh read may later confirm it. A structural or
property readback is not runtime validation, and runtime validation is not GO
readiness.

## Proposed Contract for the First Slice

The public schema should be intentionally narrow:

- exact `workspace_id` (UUID returned by connection/read tools);
- one literal `operation`, initially only `minGoTime`;
- typed finite non-negative `value` in seconds;
- `dry_run` defaulting to `true`;
- optional server-issued fresh `confirm_token`;
- structured plan/result with baseline, requested value, exact operation, warnings,
  errors, readback, and status.

The tool must reject unknown operations, name-based/broadcast targets, raw OSC
addresses, arbitrary AppleScript, `/live`, and multiple setters in one request.

The dry-run must include the baseline read, exact planned endpoint (in a safe
redacted representation), validation result, required capability gates, and an
empty executed-operation list. Real execution requires a new readiness check,
the fresh token from that plan, exactly one setter, and fresh no-arg readback.

## Recommended First Implementation Slice

### Slice 0 — internal proof scaffolding

No public tool. Define the settings registry shape, token family/version, typed
comparison/readback helpers, and contract tests against fixtures. This keeps the
public 13-tool surface unchanged while the policy is reviewed.

### Slice 1 — `minGoTime`

This is the strongest first real candidate:

- exact documented OSC setter and no-argument readback;
- scalar non-negative validation;
- no object topology, device selection, or external routing mutation;
- easy baseline capture and inverse rollback;
- still operational, so it requires Edit Mode, explicit confirmation, and a
  disposable/inactive QLab 5.5.10 workspace for runtime proof.

### Slice 2 — `selectionIsPlayhead`, only after operator proof

The endpoint is technically documented, but it changes selection/playhead
behavior and can surprise an operator during inspection. Prove the workflow with
human confirmation and an exact readback before exposing it.

### Later slices

1. Video route `enableGuides` or stage name, only after stable route/stage IDs and
   property readback are proven.
2. Selected video-region scalar geometry, only with integer bounds validation and
   disposable visual output.
3. Selected audio scalar properties, only after permission rows and live/saved
   behavior are resolved individually.
4. Audio maps/test objects only after the blank permission rows are resolved by
   runtime evidence; no creation/deletion/routing batch.
5. Light, Network, MIDI, Collaboration, Templates, and OSC Access remain
   deferred until QLab exposes a documented, exact, reversible write surface.

## Validation Protocol (Research Plan, Not Executed)

For each candidate:

1. Open a disposable QLab 5.5.10 workspace with no active cues, no GO, no
   playback, no Dashboard output, and no connected show-critical external system.
2. Resolve the exact workspace UUID and target IDs through read tools.
3. Capture the baseline with a fresh read and record the current mode/activity.
4. Run a dry-run and verify `executed_operations=[]`, exact target, value/range,
   risk tier, and capability gates.
5. Obtain a fresh operation token; execute one setter once.
6. Perform a fresh, un-cached no-argument readback and compare normalized value.
7. Verify persistence after a safe workspace/settings reload where applicable;
   do not treat persistence as runtime output proof.
8. Roll back with a new dry-run/token and fresh readback.
9. Separately test invalid values, stale tokens, wrong workspace UUID, wrong
   target ID, replayed tokens, Show Mode, missing Edit permission, unavailable
   QLab, timeout, and ambiguous readback. Confirm fail-closed behavior and no
   automatic setter retry.
10. Record physical/visual/auditory confirmation only where the property can
    affect output; label it as runtime evidence, never as GO readiness.

The research did not execute this protocol. The current environment therefore
contains no new QLab runtime proof.

## Versioning and Public Tool Impact

Adding a public settings mutation tool changes the FastMCP tool inventory,
schemas, instructions, contract snapshots, and client discovery. It should be a
minor release, **0.4.0**, with updated docs/tests and explicit migration notes.
It is not a `0.3.1` patch: the change is additive but materially expands the
mutation surface and safety contract.

The research artifact itself does not change the package version or tool count.

## High-Risk and Deferred Areas

- OSC Access passcodes, ports, permissions, and collaboration: external control
  and connectivity/security impact.
- Light patch, Art-Net/DMX output, definitions, and auto-patching: physical
  output and fixture-address risk.
- Video output devices/routes/topology and arbitrary warping: physical display
  and geometry risk; only narrow scalar properties are candidates.
- Audio patch routing, maps, test objects, and output levels: physical sound and
  ambiguous local permission documentation.
- MIDI patches, MSC, MTC/LTC, and external synchronization: external show
  control and timing risk.
- Audition alternate patches and output suppression: rehearsal safety is useful,
  but it is still an output-routing mutation.
- Templates/import/export, backups, and file management: broad or destructive
  scope that does not fit a single-property setter.
- AppleScript fallback, arbitrary source, `/live`, GO/panic/playback, and raw OSC:
  outside the supported public boundary.

## Open Questions

1. On QLab 5.5.10, do audio map/test-object prose setters accept the same edit
   scope implied by their blank permission cells, and what exact readback follows?
2. For each documented setter, does QLab emit a reliable acknowledgement under
   `/alwaysReply`, and does the property converge before the fresh read returns?
3. Which settings persist immediately, and which require a workspace/settings
   reload to prove persistence?
4. What stable-ID lifecycle applies to audio map objects, video stages, regions,
   and routes after import, duplication, or template creation?
5. What activity snapshot is sufficient for Tier 2/3 writes, especially with
   collaborators, running cues, overrides, or connected external devices?
6. Does AppleScript’s unresolved `application.preferences` reference behave
   differently in a specific QLab 5.5.10 build or with TCC approval? This needs a
   separate, user-visible Automation test and is not a reason to add a fallback.
7. Which FastMCP clients consume the proposed discriminated schema reliably, and
   what compatibility tests are required before exposing a new tool?
8. Which QLab version drift (5.5.10 versus later 5.x) changes endpoints,
   permissions, or section behavior? Claims here are scoped to the documented
   QLab 5 surface and must be rechecked before implementation.

## Evidence and Sources

### Repository sources

- `docs/qclass/README.md` and the three imported Day 1–3 transcripts (timestamps
  cited above; transcripts remain immutable).
- `docs/references/qlab_osc_dictionary.md:1195-1214` for workspace addressing;
  `:1987-2008` for General setters; `:2233-2470` for Video surfaces; the
  surrounding Audio/Light/Network/MIDI sections for access rows.
- `src/qlab_mcp/server.py:116-130,218-232` for the current read sections,
  instructions, and exclusions.
- `src/qlab_mcp/settings/workspace.py:32-64` for settings read bounds.
- `src/qlab_mcp/write/safety.py:32-216`, `write/tokens.py`,
  `write/timeouts.py`, and `write/results.py` for reusable safety primitives.
- `docs/development/architecture.md:17-62` and `SECURITY.md:35-70,152-165`
  for the public boundary, write sequence, timeout policy, and evidence limits.
- `tests/test_server_tools.py`, `tests/test_qlab_reader.py`,
  `tests/test_write_mode.py`, and `tests/test_tokens.py` for the current contract
  and safety-test surfaces.

### Official web sources

- [QLab 5 Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
- [QLab 5 AppleScript Dictionary](https://reference.qlab.app/docs/v5/scripting/applescript-dictionary-v5/)
- [QLab 5 Light documentation](https://qlab.app/docs/v5/lighting/)
- [QLab 5 MIDI documentation](https://qlab.app/docs/v5/midi/)

### Confidence labels

- **High:** exact official section list; local OSC endpoint and permission row;
  current repository tool/safety inventory.
- **Medium:** QClass operational sequencing; AppleScript absence claims; future
  FastMCP shape.
- **Low until runtime-tested:** convergence timing, setter acknowledgement,
  persistence timing, audio map permissions, cross-device behavior, and any
  claim involving physical output.

## Next Step

Stop here for research review. A separate user-approved implementation plan may
turn Slice 0 and the `minGoTime` proof into work. Until then, the public MCP
surface remains the 0.3.0, 13-tool, read-plus-gated-cue-write contract.
