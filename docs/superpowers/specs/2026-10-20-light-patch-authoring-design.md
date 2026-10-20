# Light Patch authoring design

Status: implemented in PR #19 with the bounded capabilities below.
See the [native acceptance record](../../development/runtime-validation/2026-10-20-light-patch-authoring.md).
Date: 2026-10-20.

## Goal

Let an agent turn an explicit lighting patch into instruments, groups, output
assignments and workspace Light Definitions in the existing `.qlab5` document.
The tool is `qlab_edit_light_patch`.

The owner has approved automatic save, close and reopen of the same workspace
as the design for this feature. That decision does not authorize unrelated
document changes or live lighting output during development.

## Scope

| Area | Intended support | Release condition |
|---|---|---|
| Instruments | Create, update, rename, delete | Native batch and reopen/readback accepted |
| Groups | Create, update, rename, delete; nested memberships | Native batches accepted; existing member ranges preserved |
| Addresses | Explicit start address and footprint validation | Captures establish native encoding and boundaries |
| Art-Net | Net, Sub-Net and Universe | Independent nonzero-value reference captures |
| USB-DMX | Explicit serial, label and device universe | Native serialization and synthetic-identity reopen accepted; no compatible device detected |
| Workspace Light Definitions | Create/update/rename/delete; scalar 8/16-bit and RGB | Native parameter interpretation checked for used definitions |

Light Dashboard MIDI edits, global Light Library edits, playback, stage editing
and cue edits are excluded. Rename/delete are included; cue references may
remain pending for later repair. Existing excluded data
must survive unchanged. Omitting an object from a request never deletes it.

All requested output types remain part of the goal. A type with insufficient
evidence must be rejected explicitly rather than silently converted or claimed
as supported.

## Evidence boundary

Historical local research observed one externally edited archive accepted and
displayed by QLab **5.5.10, build 5510**. It contained six active instruments,
four active groups, definitions and Art-Net assignments. The exact writer was
not retained. Two generic reserializations were rejected without an isolated
cause. This proves a concrete feasibility case, not a reusable writer.

Read-only inspection of three retained archives on 2026-10-20 found Art-Net
backend classes but no USB backend example. The accepted archive had 329 inner
objects and ten active `itemList` entries; counting class instances would
incorrectly include inactive objects. That initial design pass performed no new native reopen or hardware test.
The linked implementation acceptance record supersedes the writer/reopen gaps;
hardware output remains unverified.

Retained private evidence fingerprints, for matching locally held artifacts:

| Artifact | SHA-256 |
|---|---|
| Baseline | `b7007f8f1a3284b59e069b0285e8cc9c25af465f8e73943cda4ff2eae077e867` |
| Before external edit | `fd506258e61117eec4870f5bf64cb80d4932c421754e6eb5a173ffb8ad129afd` |
| Accepted external edit | `935f9bae82cb594b894045a003c0a6b424893fe6d175a0f50ee5fd27ecb2bbc6` |

Private workspaces, imported references, local paths and application binaries
are not proposed for publication. These hashes identify historical evidence;
they are not committed regression fixtures or a substitute for reproducible
acceptance evidence.

## Interface

Inputs are an exact workspace UUID, typed operations, `dry_run=true` by default,
and a fresh signed single-use confirmation token for execution. There is no
arbitrary archive-key mapping, script input, raw OSC or alternate output path.
The strict discriminated operation models are in `light_patch/models.py`.

The agent resolves missing manufacturer, model, mode, channel map, numbering
convention and USB identity before planning. It must not invent a personality
from a fixture's marketing name.

The plan returns explicit additions, updates, reused objects, warnings,
dependency changes and occupied addresses. An identical request is a no-op:
no duplicate objects, file rewrite or document lifecycle events.

Validation must reject:

- Ambiguous or duplicate names and unresolved definition/group references.
- Group cycles and unresolved references inside the final patch. Cue references
  are warnings only; Light cues are never rewritten or used to block a patch edit.
- Address footprints outside a universe or overlapping another instrument on
  the same output address space, including instruments outside the request.
- Shared-definition updates without including every affected consumer in the
  dependency snapshot and recomputing its footprint.
- Unsupported archive classes, versions, parameter types or output backends
  on the edited graph.

Art-Net address spaces are distinguished by Net/Sub-Net/Universe; USB address
spaces by stable device identity and device universe. UI numbering is explicit;
an archived zero-based observation is not a universal conversion rule.

## Archive requirements

The observed format is a binary plist containing an `NSKeyedArchiver`. Its
nested dictionaries `settings` → `Light` → `patch` lead to `NSData` containing
a second keyed archive. `settings.Light.patch` denotes this path, not a literal
dictionary key.

Preserve object identities, UIDs, class metadata, ordering, shared references,
unknown fields and unreachable objects. Inventory follows root reachability
through `LightPatch.itemList`, not all instances in `$objects`.

Observed group members use names/ranges; `lightOutputID` is distinct from DMX
address. Normal instrument decoding in QLab allocates runtime IDs; native reopen/save
confirmed regeneration. New archived instruments use a provisional zero ID;
identity is the exact name bound to the source snapshot, never a runtime ID.
Do not derive an identity from an address or assume `max + 1`.
Do not ship a generic `plistlib.dumps` rewrite as an accepted writer without
native acceptance evidence.

Workspace definitions and the Mac's global `.qlablight` library are separate
stores. Only the workspace collection is edited. Preserve MIDI fields
opaquely; exclusion from editable scope does not permit clearing them.

## Same-path document lifecycle

1. Resolve exact UUID, canonical path, supported QLab build, native document
   state and OSC write readiness. Require local QLab, Edit Mode, write enable,
   existing authorization and no running/paused cues.
2. A dirty document yields `needs_save`. A dry run never saves or closes.
   Use the existing signed Save flow, disclosing that it saves all pending
   edits, then obtain a fresh Light Patch plan from the saved bytes.
3. Bind the plan token to source identity/hash, operations, dependency snapshot,
   native baseline and build. Recheck before consuming it and before closing.
4. Close only the clean target. Verify its absence and unchanged source file.
5. Construct a sibling temporary result and validate graph integrity and
   semantic preservation outside the authorized changes.
6. Preserve one bounded recovery artifact and durable operation state. Replace
   the original path atomically within the same filesystem, with required
   permissions and metadata preserved. An unresolved recovery blocks another
   transaction from overwriting its evidence.
7. Reopen the original path and verify exact workspace identity, native state
   and the edited patch. Report file replacement, reopen and QLab readback as
   separate outcomes. Successful parsing alone is not execution success.

Only file replacement is atomic. The complete save/close/edit/open operation
is not. Hash checks do not provide exclusion against an uncooperative external
writer. Reject unsupported links, packages or metadata conditions until the
corresponding preservation strategy is established.

### Existing Open restriction

`workspace_documents.py` currently permits Open only with no workspace open.
Simply chaining existing tools cannot reopen the target while other documents
remain open. Preserve that public contract.

The eventual feature needs a narrowly scoped internal reopen with parsed file
UUID, exact path/hash, collision checks and unchanged other-document inventory.
The internal path was accepted with another document open and its inventory
unchanged. Never close another document automatically.

### Recovery

Record whether the target was saved, closed, replaced, reopened and verified.
After a timeout or ambiguous event, inspect fresh state and never automatically
retry a mutation. If a failure leaves the document closed or replaced, report
that state and retain recovery material. Restoration must check current
identity/hash and must not overwrite subsequent user changes.

Reopening may affect lighting output; absence of a GO command is not proof of
physical silence. Native acceptance and hardware validation are distinct gates.

## Delivery and acceptance

The [implementation plan](../plans/2026-10-20-light-patch-authoring.md) records
implementation and acceptance. The public contract now exposes 80 tools
(49 reads and 31 gated writes). Acceptance is bounded to the recorded paths and
QLab version; no hardware or unimplemented parameter-type claim is made.

## Official references

- [Light Patch Editor](https://qlab.app/docs/v5/lighting/light-patch-editor/):
  patch fields, groups and definitions. DMX universes have 512 addresses;
  Art-Net Net/Sub-Net/Universe ranges are 0–127/0–15/0–15. Addresses must be
  unique per device and universe.
- [Light Library](https://qlab.app/docs/v5/lighting/light-library/): distinguishes
  workspace definitions from global custom JSON `.qlablight` files.

The current web manual can describe releases newer than 5.5.10. It is not a
specification of that version's private serialized format.
