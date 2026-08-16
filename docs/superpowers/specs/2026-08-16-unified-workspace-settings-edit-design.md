# Unified Workspace Settings Edit Design

## Goal

Replace the branch-local `qlab_edit_general_settings` surface with exactly one
public `qlab_edit_workspace_settings` tool. Wave 1 exposes only the proven,
enabled `general.minGoTime` operation while establishing an extensible typed
architecture for later settings operations.

## Current State

The repository currently has fourteen public tools and one Workspace Settings
write path for `general.minGoTime`. The implementation already provides exact
workspace UUID resolution, readiness and activity gates, dry-run confirmation
tokens, one setter, cache invalidation, and fresh readback. The current public
tool name is branch-local and has not shipped from `main`.

`general.selectionIsPlayhead` is readable and documented by QLab, but it has
not received the required independent runtime and operator-workflow proof. It
is therefore research-only and is not an executable or public Wave 1
operation.

## Public API Decision

The public tool is:

```python
def qlab_edit_workspace_settings(
    workspace_id: UUID,
    operation: WorkspaceSettingsOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    ...
```

Wave 1 uses one concrete operation model:

```python
class GeneralMinGoTimeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["general.minGoTime"]
    value: Annotated[StrictInt | StrictFloat, Field(ge=0)]


WorkspaceSettingsOperation = GeneralMinGoTimeOperation
```

The request contains a nested typed `operation` object. It accepts no raw OSC
path, address, generic setter, or arbitrary value field. The alias is promoted
to a real discriminated union only when a second operation is implemented and
approved.

## Alternatives Considered

### Approach A: One typed operation per MCP call

This is the selected approach. It preserves one-setter confirmation, makes
baseline and readback deterministic, gives agents a small schema, and lets
each operation declare its own validation, equality, timeout, and risk gates.

### Approach B: Typed list of operations

This would improve multi-change workflow ergonomics, but would immediately
require ordering, partial-failure, no-atomicity, per-item token, and recovery
semantics. It is deferred.

### Approach C: Domain patch object

This would be compact, but omitted-field semantics, mixed-risk confirmation,
canonical token payloads, and per-property readback would be ambiguous. It is
rejected for this surface.

## Recommended Request Model

```json
{
  "workspace_id": "exact-UUID",
  "operation": {
    "kind": "general.minGoTime",
    "value": 1.25
  },
  "dry_run": true,
  "confirm_token": null
}
```

The operation model uses strict numeric validation, rejects booleans and
strings, enforces non-negative finite OSC-representable values, and forbids
extra keys. Unknown operation kinds fail schema validation before the reader
or transport is called.

## Operation Model

Each future typed operation must define, in its implementation wave:

- qualified operation ID and domain;
- input payload and strict validators;
- exact setter and readback path owned by the registry;
- normalization and equality rules;
- risk tier and capability-specific prerequisites;
- timeout policy and result/error mapping;
- runtime evidence and tests.

Wave 1 defines only `general.minGoTime`.

## Registry / Handler Architecture

The executable registry contains exactly one entry:

```text
general.minGoTime
```

Its specification owns the exact OSC setter/readback path, saved-setting mode,
numeric value kind, Tier 2 risk classification, activity policy, and registry
version. The common lifecycle in `settings/write_operations.py` performs
preflight, token handling, one setter, and fresh readback. Domain-specific
modules are added only when an operation has sufficient evidence; no generic
path dispatcher is introduced.

The capability/research matrix is separate from executable dispatch. Research
entries do not become accepted public operations or registry entries merely
because QLab exposes a read endpoint.

## Safety Model

Every real call follows:

1. exact workspace UUID resolution;
2. readiness check;
3. fresh baseline read;
4. capability-specific activity gate;
5. fresh dry-run token;
6. immediate readiness, identity, baseline, and activity recheck;
7. exactly one setter;
8. cache invalidation;
9. fresh no-argument readback;
10. normalized comparison.

Timeouts and uncertain setter replies are never retried automatically. Rollback
is a separate operation with a new dry-run and token. No atomicity is claimed.

## Mutation Granularity

One confirmed call performs at most one setting mutation. A single public tool
does not imply a batch of mutations.

If a future batch is ever justified, it requires a separate approved design
covering ordering, per-item gates, partial completion, tokens, and explicit
non-atomic semantics.

## Confirmation Token Model

The `workspaceSettings:v1` token binds the canonical workspace UUID, qualified
operation ID, target identifiers where applicable, canonical baseline,
requested value and wire type, registry version, expiry, and nonce. Tokens are
single-use and replay-protected.

## Result / Error Model

The existing result envelope is retained, including baseline, readback, planned
and executed operations, readiness, activity, verification, timeout
confirmation, retry safety, errors, and suggested action.

Wave 1 supports `dry_run`, `unchanged`, `updated`,
`updated_with_confirmed_timeouts`, `preflight_failed`,
`verification_failed`, and `verification_inconclusive`. `unsupported` remains
reserved for defensive/internal registry failures; no deferred operation is
advertised in the Wave 1 schema.

Unknown or non-enabled operation kinds fail closed before execution and produce
zero setters.

## Workspace Settings Capability Matrix

| Domain | Setting / surface | Readable | Writable | Official setter | Type | Risk | Evidence | Proposed operation | Status |
|---|---|---:|---:|---|---|---|---|---|---|
| General | `minGoTime` | Yes | Yes | Exact OSC R/W | non-negative number | Tier 2 | Runtime-proven | `general.minGoTime` | IMPLEMENTED |
| General | `selectionIsPlayhead` | Yes | Documented | Exact OSC R/W | boolean | Tier 2 | Runtime/UX proof missing | `general.selectionIsPlayhead` | NEEDS_RUNTIME_RESEARCH |
| General | Undo/redo actions | Limited | No safe setting setter | Action endpoints | action | Tier 2 | Scope/persistence unresolved | Deferred | NOT_SUPPORTED |
| Controls | Keyboard/MIDI/OSC mappings, panic, hard stop | Partial | No settings family | None established | mixed | Tier 3-4 | No exact settings object | Deferred | NOT_SUPPORTED |
| Audition | `alwaysAudition`, monitors, alternate routes | Partial | Not approved | Adjacent controls | boolean/routing | Tier 4 | Output-routing proof missing | Deferred | HIGH_RISK_DEFER |
| Collaboration | Enablement, permissions, clients | Partial | No documented setter | None | policy | Tier 4 | Connectivity/security risk | Deferred | NOT_SUPPORTED |
| Templates | Cue/Workspace Templates, import/export, backups | Partial | No granular setter | None | workflow | Tier 3-4 | Broad structural effects | Deferred | HIGH_RISK_DEFER |
| Audio | Inventories and patch details | Yes | No | Read-only surfaces | metadata | Tier 0 | Read-only evidence | None | NOT_WRITABLE |
| Audio | Channels, levels, maps, test object | Partial | Ambiguous | Property-specific only | mixed | Tier 3-4 | Permission/runtime proof missing | Future typed operations | NEEDS_MORE_EVIDENCE |
| Video | Input/topology inventory | Yes | No | Read-only surfaces | metadata | Tier 0 | Read-only evidence | None | NOT_WRITABLE |
| Video | Route `enableGuides`, stage name | Yes | Documented | Exact scalar setters | boolean/string | Tier 2-3 | Stable IDs/runtime proof missing | Future typed operations | NEEDS_RUNTIME_RESEARCH |
| Video | Region geometry | Yes | Documented | Exact bounded setters | integer geometry | Tier 3-4 | Disposable visual proof missing | Future typed operations | NEEDS_MORE_EVIDENCE |
| Light | Patch, definitions, DMX/Art-Net | Yes | No documented setter | None | infrastructure | Tier 4 | Physical-output risk | Deferred | NOT_SUPPORTED |
| Network | Patches, OSC Access, ports, passcodes | Partial | No documented setter | None | security/routing | Tier 4 | Connectivity/security risk | Deferred | NOT_SUPPORTED |
| MIDI | Output patches, MSC, timecode devices | Partial | No documented setter | None | infrastructure | Tier 3-4 | External-device proof missing | Deferred | NOT_SUPPORTED |

The matrix is research and roadmap documentation, not an executable allowlist.

## Risk Classification

- Tier 0: read-only metadata and inventories.
- Tier 1: low-risk metadata with exact readback.
- Tier 2: operator/workspace behavior such as `minGoTime`.
- Tier 3: routing, device, or system behavior.
- Tier 4: show-critical, external, security, or disruptive behavior.

## Domain-Specific Safety Requirements

Tier 3 requires a disposable inactive workspace, zero relevant activity,
capability-specific confirmation, one setter, fresh readback, and a physical
or visual verification plan. Tier 4 remains plan-only until dedicated QLab
5.5.10 evidence exists and must never be exercised against a connected
show-critical system.

## Public Rename Strategy

Rename `qlab_edit_general_settings` to `qlab_edit_workspace_settings` without
an alias. The old name is not on `main` and has no released compatibility
obligation. The public tool count remains fourteen.

## Compatibility Analysis

Update current server, tests, README, and user workflow references. Preserve
historical runtime reports and prior plans as historical evidence where they
describe the old branch-local name. `qlab_update_cues` remains absent.

## Runtime Validation Strategy

Only after explicit runtime authorization, use a disposable QLab 5.5.10
workspace: capture baseline, dry-run, use one fresh token, send one setter,
read back freshly, restore with a new token, and independently verify. Do not
press GO, start playback, use `/live`, or touch connected show-critical output.

## Implementation Waves

1. Rename the public tool, introduce the nested typed model, qualify the
   registry ID, and preserve only `general.minGoTime` as executable.
2. Research and validate `selectionIsPlayhead`; only then add its model, union
   variant, registry entry, handler, tests, and evidence in one wave.
3. Evaluate narrowly scoped Video operations.
4. Evaluate Audio operations property by property.
5. Keep high-risk and unsupported domains deferred until exact reversible
   surfaces are proven.

## PR #16 Strategy

Use the existing `feature/workspace-settings-write` branch. Keep PR #16 open,
do not merge it, and do not modify `main`. Push only the bounded implementation
follow-up after tests and documentation are complete.

## Non-Goals

No batch settings writes, generic paths, raw OSC, AppleScript fallback, GO,
playback, panic, `/live`, automatic rollback, version bump, release, publish,
or additional Workspace Settings capability in Wave 1.

## Open Questions

`selectionIsPlayhead`, Video, and Audio candidates require independent runtime,
operator, identity, permission, and readback evidence before their own
implementation waves. These questions do not block the Wave 1 `minGoTime`
rename and architecture.

## Definition of Done

- `qlab_edit_workspace_settings` is the only public Workspace Settings write tool.
- `qlab_edit_general_settings` is absent.
- `WorkspaceSettingsOperation` exposes only `general.minGoTime`.
- `general.selectionIsPlayhead` remains documented as `NEEDS_RUNTIME_RESEARCH` and is absent from the public operation schema.
- Unknown/non-enabled operation kinds fail closed before execution and result in zero setters.
- The executable registry contains only enabled operations.
- The capability/research matrix remains separate from executable dispatch.
- Exactly fourteen public tools remain.
- No additional Workspace Settings write capability is added.
