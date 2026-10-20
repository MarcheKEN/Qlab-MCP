# Light Patch Authoring Implementation Plan

> Execute in the dedicated feature branch. This plan contains research gates;
> it does not authorize guessing the private archive format or mutating a user's
> working show. No implementation step below has been completed by this PR.

**Goal:** Add `qlab_edit_light_patch` for the existing workspace and original path.

**Architecture:** Reuse document readiness, fixed native lifecycle operations
and signed confirmation conventions. Add a bounded archive editor and typed
patch planner only after reproducing QLab's accepted persistence behavior.

**Tech stack:** Existing Python 3.11/FastMCP/Pydantic stack; standard-library
plist inspection and filesystem primitives. No new dependency is selected.

**Spec:** [Light Patch authoring design](../specs/2026-10-20-light-patch-authoring-design.md).

## Global constraints

- Initial native acceptance target: QLab 5.5.10, build 5510.
- Instruments, Groups, Art-Net, USB-DMX and workspace Light Definitions are the
  intended scope. Dashboard MIDI is preserved but not edited.
- Same final path; one bounded recovery plus temporary output.
- Dry run never saves, closes or writes. Dirty state requires Save followed by
  a fresh plan. No raw protocol/script escape hatch or automatic mutation retry.
- Preserve other documents and existing public Open behavior.
- No public writer registration before the relevant native acceptance gates.

## 1. Establish reproducible persistence evidence — first blocking gate

**Relevant files:** new isolated synthetic fixtures and a dated report under
`docs/development/runtime-validation/`; no private workspace or binary imports.

- [ ] Produce QLab-created before/after samples for one instrument using an
  existing simple definition. Record application build, source/result hashes,
  active graph and precise UI change.
- [ ] Reproduce a no-change archive round trip and one minimal edit accepted
  after closing/reopening in 5.5.10. Capture the writer source and commands;
  a historical screenshot is insufficient.
- [ ] Compare rejected generic serialization with an accepted result to isolate
  format/graph differences. Retain the outcome even if the cause remains
  unknown; no writer is released while reproducibility is missing.
- [ ] Establish `lightOutputID` allocation and reopen/save persistence. Check
  multiple allocations and collision behavior, not only a single sample ID.

**Exit:** Reviewable writer procedure and repeatable same-version native
acceptance. If unavailable, keep this PR draft and record the blocker.

## 2. Capture complete patch encodings

**Relevant files:** synthetic reference fixtures and the same dated report.

- [ ] Capture Art-Net Net, Sub-Net and Universe independently at nonzero values.
- [ ] Capture USB-DMX device identity, backend metadata and per-device universe;
  distinguish stored configuration from device detection and actual output.
- [ ] Capture address boundaries, physical 8/16-bit footprints, group membership,
  nested groups and ranges. Check name dependencies in existing Light cues.
- [ ] Capture each supported definition parameter type independently, including
  home/percentage and virtual-parameter links. Track shared-definition consumers.
- [ ] Include inert existing MIDI data and unknown fields in preservation cases.

**Exit:** Every supported typed operation has source-bound encoding evidence.
Missing types remain explicitly blocked; no backend conversion or invented map.

## 3. Implement bounded archive reading and editing

**Proposed files:** `src/qlab_mcp/light_patch/archive.py` and focused synthetic
regression coverage when verification is authorized. Finalize function
signatures from the accepted writer obtained in step 1.

- [ ] Enforce file/object/collection bounds and UID validity before traversal.
- [ ] Resolve nested settings/Light/patch and active `itemList` reachability.
- [ ] Preserve graph topology, shared references, unknowns and unrelated data.
- [ ] Implement only the encodings established by steps 1–2.
- [ ] Preserve no-op bytes and validate semantic differences before replacement.

**Exit:** Reproducible output for synthetic fixtures, rejected malformed inputs,
preserved unrelated projections and native acceptance for all edited types.

## 4. Implement typed planning and dependencies

**Proposed files:** `src/qlab_mcp/light_patch/models.py` and
`src/qlab_mcp/light_patch/planner.py`; reuse existing validation conventions.

- [ ] Define strict create-definition, create-instrument, instrument-update and
  group-membership operations. Reject unknown fields and unsupported variants.
- [ ] Validate exact definition/mode, names, memberships/cycles, output identity,
  numbering, occupied ranges and all shared-definition consumers.
- [ ] Generate explicit additions/updates/reuse/no-op results and dependencies.
- [ ] Bind the operation plan and source/build/native baseline into the token.

**Exit:** Invalid or ambiguous input cannot produce an executable plan; unchanged
requests require no file or native events.

## 5. Implement document transaction and recovery

**Proposed files:** `src/qlab_mcp/light_patch/transaction.py`;
`src/qlab_mcp/workspace_documents.py` only for a justified fixed internal reopen.

- [ ] Reuse local identity, readiness and token checks; enforce `needs_save`
  without implicit mutation during dry run.
- [ ] Recheck clean target, exact path/hash and absence after Close.
- [ ] Write/verify sibling temporary output; preserve metadata, synchronize
  recovery/journal state and atomically replace only the expected source.
- [ ] Keep a single unresolved recovery; reject unsafe links/packages and races.
- [ ] Reopen exact identity and read back the patch. Preserve other workspaces
  with a separately validated internal reopen, or block before closing target.
- [ ] Exercise failures before/after close, replacement and reopen. No blind
  retry, silent rollback or cleanup of unresolved recovery evidence.

**Exit:** Each failure reports the actual phase and preserves a recoverable
state without overwriting newer changes. Native readback confirms success.

## 6. Expose the MCP tool and reconcile documentation

**Relevant existing files:** `src/qlab_mcp/server.py`,
`tests/test_server_tools.py`, `README.md`, `SECURITY.md`, `CHANGELOG.md`,
`docs/user/tools.md`, `docs/user/agent-workflows.md`,
`docs/status/current-state.md`, `docs/status/coverage/README.md` and
`docs/status/roadmap.md`. Locate all count/contract consumers before editing.

- [ ] Register a strictly typed, dry-run-first destructive write tool with a
  bounded timeout and explicit evidence/capability descriptions.
- [ ] Reconcile generated input/output schemas, annotations and tool inventory.
- [ ] Document dirty-save semantics, tokens, supported versions/types, output
  behavior, recovery and privacy of local document access.
- [ ] Keep historical acceptance records dated; do not upgrade old claims.

**Exit:** The advertised surface matches the actual registered capability set.

## 7. Verification and PR readiness

Verification commands are a future acceptance checklist; none were run for
this documentation-only PR. Run them only when verification is authorized.

- [ ] Run focused archive/planner/transaction and document-lifecycle coverage.
- [ ] Run public MCP contract checks and inspect with the project's documented
  `uv run --locked --no-editable --extra dev fastmcp inspect fastmcp.json --skip-env`.
- [ ] Call the new tool through MCP for a read-only preview before executing an
  explicitly authorized synthetic native case.
- [ ] Record file preservation, native reopen/readback and hardware checks as
  different results. Do not label hardware behavior verified from archive data.
- [ ] Review the whole branch, close safety/correctness findings, update this
  checklist with exact results and mark the PR ready only after acceptance.

The first two steps intentionally precede executable-code instructions: their
results determine the private writer format. An end-to-end code plan written
before those results would require inventing unsupported behavior.
