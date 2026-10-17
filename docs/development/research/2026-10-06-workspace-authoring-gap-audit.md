# Pending capability audit: workspace authoring

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-10-06. Scope: reading, creation and persistent editing; no cue execution, `/live`, external signals, Audio Maps or Script compilation.

Subsequent deeper analysis: [generic-tool migration, FX/Text, Group and AppleScript](2026-10-06-cue-edit-migration-fx-text-plan.md) and [Video FX catalog](2026-10-06-video-fx-parameter-inventory.md). The detailed comparison also identifies the limited FX gate still in the generic tool and accidental exposure through its fallback: do not confuse a planned catalog with an effective executor block.

## Conclusion

**Implementable extensions remain. There is no documented API to reproduce the entire Workspace Settings interface.** The next useful work is to complete existing editors, migrate old confirmations and add a bounded AppleScript path for properties OSC does not expose.

This audit cross-checks current code and registry, local OSC/AppleScript dictionaries, installed SDEF, official documentation and QClass. It performs no writes or new QLab validation. Previous runtime evidence corresponds to QLab 5.5.10; QLab 5 documentation entries alone do not prove the behavior of that patch release.

## 1. Current state and removals

Inspection with `Client(mcp).list_tools()` returns **72 tools: 44 read tools and 28 authorized write tools**. The tool inventory exposed in this session matches that count. Registry presence does not demonstrate that each internal operation is enabled or validated live.

- There are Gets by family, structure and Settings; 16 specialized cue editors and five object-specific Settings editors.
- `qlab_edit_cues` remains available. The generic path has not been removed.
- `qlab_create_cues` currently accepts 1–100 cues of 24 types; Script is not in its allowlist. Group creation is already included.
- Cue Lists and Carts can be created; lists can be edited and moved, and cues can be moved/deleted. Cart cell movement and root list/Cart deletion remain blocked.
- The current backend is OSC. No AppleScript writer is implemented.

API changes recorded in [CHANGELOG](../../../CHANGELOG.md):

| Removed or replaced | Current state |
|---|---|
| `qlab_edit_workspace_settings` | Five specific Edits: General, Audio Output Patch, Video Stage, Output Route and Region. |
| `qlab_get_workspace_settings`, `qlab_get_workspace_setting_details` | Six section-specific Settings Gets. |
| `qlab_create_cue` | `qlab_create_cues`. |
| Alias `qlab_update_cues` | `qlab_edit_cues`. |
| Audio Maps in the public contract | Excluded by a scope decision. |

These are not forgotten features: execution, `/live`, signal-dependent capture, shared undo/redo and Script source writes with recompilation were deliberately excluded. Deprecated OSC aliases do not justify new tools either.

## 2. Concrete OSC extensions

| Area | What is actually missing | Reasonable minimum implementation |
|---|---|---|
| Video FX | Adding, inserting, deleting and ordering effects; editing parameters. The current typed editor only includes enabled by index. | Extend visual editors and their Gets with a complete stack inventory, revalidated identity/indices and official types/ranges. |
| Text | Formatting by ranges, words and fragments; global attributes do not represent mixed formatting. | Typed `/text/format` operations, with a complete snapshot and preservation of formatting outside the requested range. |
| Group Triggers | Setters already exist through `qlab_edit_cues`/`common`, but are missing from the typed Group editor. | Migrate them to the signed protocol with expiry and single use. Second Trigger 6–7 only in Group Playlist. |
| Fonts | A native inventory is missing for typography validation. | Read `/fontNames` and `/fontFamiliesAndStyles`; this can be integrated into an existing Get. |
| Save document | `/workspace/{id}/save` exists, with no current tool. | Verify identity, path and modified state through AppleScript/file inspection. The OSC ack does not demonstrate which file was saved. |
| Script creation | `/new script` is documented, excluded from create. | Investigate templates and compilation during creation first. Do not enable it on the assumption it starts empty. |
| Organization | Cart movement and root deletion have a plan or documented address, but remain blocked. | Specific validation of semantics, dependencies, the last list and restoration; do not advertise them as available. |

Precise sources: [OSC dictionary](../../references/qlab_osc_dictionary.md), Video FX lines 5191–5268; Text 5315–5358; fonts 231–291; save 1137–1140; new 1021–1039; delete 891–897. Code: `write/visual.py:160,567`, `write/group.py:15`, `write/allowlist.py:24`, `write/moves.py:279`, `write/deletes.py:609`.

The generic Group path uses old deterministic confirmations derived from profile/property/path/arguments (`write/registry.py:2155–2170`), without a secret signature, expiry, baseline or single use. **Having a setter does not mean the safety migration is complete.** Preflight retains Playlist, Timecode and exact Fade & Stop readback restrictions (`write/operations.py:9709–9719`).

The Light transformations `/pruneCommands`, `/safeSortCommands`, `/removeLightCommandsMatching`, `/replaceLightCommand` and saved-cue `/setLight` are documented (OSC dictionary:5571–5604). Many can be composed with Get + existing `lightCommandText` editing; they do not require one tool per command. The Dashboard with live output is out of scope.

## 3. What AppleScript adds

These are documented capabilities awaiting a backend and runtime validation, not features currently exposed by MCP:

| Object | Additional documented capability | Limit |
|---|---|---|
| Load cue | `load time`, read and write. | No documented OSC equivalent was found. |
| Target cue | `assigned number`, text in the Cue Number tab. | This is the new target the Target cue will assign to its own destination cue; it is not the Basics number and does not renumber cues. |
| Triggers | MIDI configuration, Wall Clock activation and time, Timecode activation/format; integer Fade & Stop. | Activations require addressing the risk of incoming signals. Boolean OSC readback does not distinguish Fade & Stop modes. |
| Hotkey | `hotkey trigger` activation. | No documented key/modifier assignment was found. |
| Cue List Timecode | Supplementary reads/configuration of MTC source, LTC channel and synchronization. | OSC editing of list format and behaviors already exists; enabling sync can execute cues through an external signal. |
| Existing document | `open`, `save`, `close`; path, name and `modified`. | No documented constructor for a new workspace. Save/save as does not automatically imply copying media. |
| Navigation | Current list, selection, inspector and modes. | Not required for editing by UUID; assess usefulness before adding surface area. |

Evidence: local AppleScript dictionary, cue:2253–2325; cue list:2388–2401; Load:2732; Target:3149; make:702–738. SDEF `/Applications/QLab.app/Contents/Resources/QLab.sdef`: document:79–99, open:157–159, close:175–185, save:258–268, Load:1849–1853, Target:1866–1870, make:1887–1892. [Official AppleScript dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/).

Qualifications that prevent promising full coverage:

- MIDI Trigger accepts bytes and display strings; no documented grammar for velocity `greater/less/any` was found. The snapshot describes one byte as string and the installed SDEF as integer: resolve through the installed contract and a trial, without assuming syntax.
- No Wall Clock weekday selector was found.
- Script `script source` explicitly recompiles. It is out of scope; nor is there a documentary guarantee that Script creation bypasses templates or compilation.
- Standard `duplicate` is commented out in the SDEF. No native QLab copy/paste commands or Cart grid/cell setter were found in AppleScript.
- `make` creates cues, Cue Lists and Carts inside a workspace; it does not create documents, patches, stages or instruments.

## 4. Workspace Settings: coverage and limits

| Section | Currently available | No documented operation found |
|---|---|---|
| General | `minGoTime`, `selectionIsPlayhead`. | Rest of the panel, file options, backups and display. |
| Audio | Inventory and editing of an existing output patch: name, cue outputs, Main/crosspoints, levels and mute/solo. | Create input/output patches, assign devices, patch Audio FX. |
| Video | Inventory; Stage name; Route guides; Region geometry and existing points. | Create stage/region/route/virtual/input devices; stage resize/mask; warp type, subdivisions and edge blends; hardware selection. |
| Light | Patch reading and cue command editing. | Create/configure Light instruments, groups and definitions through a native API found in this research. |
| Network / MIDI | Inventories and cue configuration toward existing patches. | Create/configure shared patches or MSC destinations. |
| Controls / Collaboration / Templates | No complete reader or editor for these panels. | No native setters equivalent to their UI controls were found. |

Cue properties `patchID` and `stageID` select existing objects; they do not create them. Import/export Settings and New From Template exist in the UI, but this does not mean the manual provides an endpoint: [Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/), [Workspace Templates](https://qlab.app/docs/v5/fundamentals/workspace-templates/).

Audio `reset`/`routing/reset` restores faded parameters to the saved state: it does not construct or edit the persistent patch. `resetControlPoints` exists, but requires a complete snapshot and verifiable outcome/restoration. Region `moveBy` was excluded after observing warp translation and incomplete restoration; it must not be presented as a nonexistent setter.

“No documented operation found” does not prove absolute impossibility. UI automation would be another backend, with another contract and maintenance burden; it is not the native AppleScript dictionary.

## 5. Implemented, but conditional

- Mic/Camera `channels` and `channelOffset`: blocked when input capability cannot be verified. The UI does not replace that dependency in authorization.
- Audio/Mic Objects: editing by UUID exists; it requires cue ownership and independent Audio Map exclusion. An insufficient fixture does not demonstrate an absent API.
- Network Device Definition and dependent MSC fields: reliable metadata for type, range and activation by command is missing in some cases.
- Defaults, cleanup and captures from target: require a complete snapshot and expected outcome. Do not unblock solely because a setter was found.
- Fade & Stop is not universally blocked: Control obtained integer 0–3 readback; other cues return a boolean and remain blocked.
- MIDI File: Type 2 is rejected; healthy fixtures are missing for some tests. LTC channel 0 is observed, but is not offered as a usable output or restoration write.
- Trim, Audio FX, complete curves/envelopes and Object paths have no documented setter found. **Start/end, rate, slices and final position do support editing**; these are different functions.
- `doLevel`/`doObjectIDLevel` belong to Fade; they are not valid opportunities for Audio/Mic.

Furthermore, Control/Devamp/Target results inherit `real_write_enabled=false` from the exclusive internal profile even though their signed writer can write (`write/control.py:129–132`, `write/registry.py:1684–1686`). Public capability metadata should be reconciled without globally enabling the internal profile.

## 6. Practical cross-check with QClass

QClass explains UI workflows and priorities. **It does not demonstrate API availability.** Transcript references in `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day N.md`:

| Class and timestamp | Workflow | Result for MCP |
|---|---|---|
| Day 1, 3:26:02–3:33:33 and 3:56:28–4:02:32 | Time & Loops, Integrated Fade, Trim and Audio FX. | Existing timing; a checkbox does not equal a complete envelope; FX/Trim have native limits. |
| Day 1, 5:50:32–5:54:18; Day 2, 5:29:16–5:30:22 | Patch/device and cue→stage→region→route→device. | Editing a cue does not configure the whole workspace; documented Settings constructors are missing. |
| Day 1, 7:16:06–7:24:23 | Object paths. | Final position does not cover trajectory editing. |
| Day 2, 36:26–50:00 and 1:05:24–1:11:57 | Triggers, including keys/modifiers, velocity, days and activation. | AppleScript partially supplements OSC; it does not promise the whole inspector. |
| Day 2, section 4:44:45; 6:09:08–6:20:35 | Video FX, Stage mask and warping. | FX is an OSC opportunity; no API was found for mask/type/subdivisions. |
| Day 3, 49:19–50:57 and 1:17:47–1:28:12 | Cue templates, Light instruments/definitions. | Pending UI workflows with no native constructor found. |
| Day 3, 5:54:54–6:04:26 | Batch Edit, paste subset and renumber. | Compose existing Gets and Edits; do not create one tool per UI gesture. |
| Day 3, 6:09:58–6:18:02 | Warnings, dependencies and trigger inventory. | Improve diagnostics by combining available reads; mark unknown causes. |
| Day 3, 6:27:18–7:00:23 | Templates, media and backups. | Existing-document lifecycle is an AppleScript candidate; packaging media/templates is not guaranteed by save. |
| Day 3, 7:21:08–7:23:30 and 7:33:26 | Relative levels and incremental pre-waits. | Read, calculate absolute values and edit; no need to execute Script cues. |

QClass Day 3, 7:43:09–7:44:37 points to the dictionary and Parameter Reference. Its aspiration to make as much as possible accessible is not a guarantee of full UI coverage.

## 7. Recommended order

1. **Consistency and safety:** migrate Group Triggers to their signed typed editor; review what remains in the old generic path; correct Control/Devamp/Target capability metadata.
2. **Complete existing OSC:** Video FX and Text fragments, with complete reads, Parameter Reference validation and fixture testing/restoration.
3. **Reads and workflows:** fonts, trigger/dependency summary, examples of renumbering, property copying and relative changes. Reuse Gets and Edits before adding tools.
4. **Bounded AppleScript:** Load Time and Target assigned number first; then Trigger configuration and document lifecycle. Separate external-signal activation from the scope without execution.
5. **Pending validation:** Cart, roots, Objects, Mic/Camera, MSC/Device Definitions and Script creation only when preconditions, effects and restoration can be checked.

Do not propose empty Settings tools without documented operations. Do not declare an endpoint verified because it appears in a dictionary. This audit adds only this report; it preserves the checkout and workspace.
