# QLab MCP 0.3.0 Agent UX and Edit Cleanup Implementation Plan

> **Execution gate:** This plan is not authorization to implement. Obtain explicit
> user approval, then execute task by task. Do not run QLab mutations.

**Goal:** Finish the pre-release 0.3.0 interface cleanup with one canonical
internal Edit path, accurate FastMCP server metadata, a clearer 13-tool contract,
and progressive human/agent documentation without changing QLab write behavior.

**Architecture:** Keep the fixed 13-tool public surface. Move the existing batch
implementation from `QLabWriteMixin.update_cues()` into
`QLabWriteMixin.edit_cues()` without rewriting its helpers. Centralize universal
agent rules in concise FastMCP server instructions, retain operation-specific
rules in each tool and schema, and reuse the existing documentation hierarchy.

**Primary evidence:**
`docs/development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md`

**Stack:** Python 3.11+, FastMCP 3.3.1, MCP 1.27.1, Pydantic 2.x, pytest, uv,
Markdown.

## Global constraints

- No QLab setters, creation, editing, movement, deletion, GO, playback, audition,
  panic, raw OSC, AppleScript writes, or `/live` writes.
- Do not push, create a PR, merge, tag, publish, or change branch protection
  without separate authorization.
- Preserve exactly 13 public tools. Do not add or remove a tool in this plan.
- Preserve all dry-run, readiness, confirmation, timeout, readback, cleanup, and
  fail-closed behavior.
- Preserve `docs/archive/**`, `docs/qclass/**`, imported references, and historical
  changelog wording.
- Do not introduce managers, factories, a metadata DSL, dynamic toolsets, or a new
  schema framework.
- Treat description, annotation, input schema, output schema, error shape, and
  server initialization metadata as public contract.
- Keep this distinction explicit:

  ```text
  planned structure
  != runtime validated
  != show ready for GO
  ```

## Approval decisions before Task 1

The executor must record the user's answer to both decisions. If either is
unresolved, stop without editing production.

1. **Undocumented Python compatibility:** accept removal of
   `QLabReader.update_cues()` with no deprecated alias. Recommended: yes, because
   the stated target requires the exact plural symbol to disappear.
2. **Readiness response duplication:** decide whether the publicly observable
   `batch_update_cues` capability key is removed in 0.3.0, leaving
   `edit_existing_cue`. Recommended: yes for conceptual consistency, but it is a
   separate response-contract break and must have changelog/tests. If not
   approved, retain both keys and still complete the method cleanup.

Do not expand these decisions into renaming `updates`, `updated_count`,
`UpdateCuesResult`, `QLAB_UPDATE_*`, `QLAB_UPDATE_DEBUG`, `updateq_plan`, or
`update_capabilities`. Those are observable generic update/result contracts and
are outside this minimal legacy-layer removal.

---

## Task 1: Freeze the pre-change MCP and Edit behavior

**Goal:** Add small characterization tests before moving the implementation.

**Why:** The safest rename is a literal control-flow move protected by behavioral
and wire-contract evidence. Current schema hashes alone do not prove calls still
route through the same batch engine.

**Files:**

- Modify: `tests/test_server_tools.py`
- Modify: `tests/test_write_mode.py`
- Inspect only: `src/qlab_mcp/server.py`
- Inspect only: `src/qlab_mcp/write/operations.py`

**Functions/classes:**

- `test_fastmcp_public_inventory_excludes_control_and_raw_osc_surface`
- `_tool_contract_snapshot`
- `qlab_edit_cues`
- `QLabWriteMixin.edit_cues`
- `QLabWriteMixin.update_cues`

**Behavior before:** Public inventory and schemas are snapshotted, but hundreds of
batch tests call the historical method directly. There is no focused assertion
that the public route and canonical internal route are the same behavior.

**Behavior after:** Tests state the desired public/internal boundary before the
implementation moves. No production behavior changes.

**Implementation steps:**

1. Confirm clean baseline and record:

   ```bash
   git status --short --branch
   git rev-parse HEAD
   git rev-list --left-right --count HEAD...origin/main
   ```

2. Run the current public contract test and save the literal result in the task
   notes, not in runtime claims:

   ```bash
   .venv/bin/pytest -q tests/test_server_tools.py
   ```

3. Add one test that monkeypatches a reader's batch boundary and confirms
   `qlab_edit_cues` delegates to `reader.edit_cues`, never to an exposed public
   alias. Reuse existing `_reader`/Client fixtures; do not build new scaffolding.
4. Add one direct behavior-equivalence characterization for dry-run batch Edit
   using the existing write-mode fixture. It must assert representative status,
   plan, `executed_operations=[]`, and no OSC setter.
5. Do not change current schema hashes or production code in this task.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py tests/test_write_mode.py
```

**Verification:** Existing 13-tool snapshot remains byte/semantic equivalent.

**Risks:** A new test may accidentally duplicate a large existing fixture. Reuse
the smallest existing representative dry-run case.

**Rollback:** Revert only the added characterization tests.

**Dependencies:** Explicit approval decisions above.

**Stop conditions:** Current tests fail before the new assertions, public inventory
is not 13, or current branch/HEAD differs unexpectedly.

---

## Task 2: Make `edit_cues()` the sole plural batch implementation

**Goal:** Remove the exact internal plural `update_cues()` layer without changing
batch behavior.

**Why:** The public name is already Edit, but control flow still terminates in the
historical method. This is nominal debt, not duplicate logic.

**Files:**

- Modify: `src/qlab_mcp/write/operations.py`
- Modify: `tests/test_write_mode.py`
- Modify: `tests/test_server_tools.py`
- Inspect/modify only if exact calls exist: `tests/test_qlab_reader.py`
- Inspect only: `tests/test_update_registry_coverage.py`

**Functions/classes:**

- `QLabWriteMixin.update_cues`
- `QLabWriteMixin.edit_cues`
- `QLabWriteMixin.update_cue`
- batch test functions named `test_*update_cues*`
- `test_update_cues_fastmcp_schema_keeps_batch_contract`

**Behavior before:** `edit_cues()` is a one-line wrapper around
`update_cues()`. The singular adapter also calls `update_cues()`.

**Behavior after:** `edit_cues()` contains the byte-for-byte-equivalent existing
batch body; `update_cues()` is absent; `update_cue()` delegates to `edit_cues()`;
tests exercise the canonical name.

**Implementation steps:**

1. In `operations.py`, rename the existing `def update_cues(...)` declaration to
   `def edit_cues(...)`; keep its arguments, body, order, exception behavior,
   timing, helpers, and return shapes unchanged.
2. Delete the later one-line `edit_cues()` wrapper.
3. Change only the call inside `update_cue()` from `self.update_cues(...)` to
   `self.edit_cues(...)`.
4. Do not rename private helpers such as `_plan_update_batch_dry_run` in this task.
   They describe update mechanics and are not a compatibility route.
5. Mechanically replace batch calls `reader.update_cues(...)` with
   `reader.edit_cues(...)` in `tests/test_write_mode.py`.
6. Rename test functions whose subject is the batch MCP/Edit path from
   `update_cues` to `edit_cues`. Do not rename test data/status strings.
7. Rename the FastMCP schema test to
   `test_edit_cues_fastmcp_schema_keeps_batch_contract` without changing expected
   schema content.
8. Search exact symbols outside history:

   ```bash
   rg -n '\b(update_cues|qlab_update_cues)\b' src tests \
     -g '*.py'
   ```

   Expected: no exact plural symbol in `src/` or `tests/`.
9. Leave `UpdateCuesResult`, `UpdateCueStatus`, `updates`, `updated_count`, error
   codes, debug env, and registry names untouched.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py
.venv/bin/pytest -q tests/test_write_mode.py
.venv/bin/pytest -q tests/test_qlab_reader.py tests/test_update_registry_coverage.py
```

**Verification:**

- all existing batch dry-run, preflight, timeout, confirmation, setter, readback,
  and result tests pass through `edit_cues()`;
- FastMCP schema hashes do not change;
- no exact plural symbol remains in current Python sources/tests.

**Risks:** Undocumented third-party Python consumers may call
`QLabReader.update_cues()`. This is the intended compatibility break; MCP clients
are unaffected.

**Rollback:** Restore the old declaration name and wrapper; no data migration or
runtime rollback exists because this task performs no QLab call.

**Dependencies:** Task 1 green.

**Stop conditions:** Any behavior/schema hash changes, any test needs safety logic
changes, or the method has callers not recorded by the research audit.

---

## Task 3: Remove only approved legacy capability metadata

**Goal:** Align readiness discovery with one Edit concept if the user approved
removing `batch_update_cues`.

**Why:** The two readiness keys currently contain equivalent metadata. Unlike the
method rename, this is publicly observable and must be isolated.

**Files:**

- Modify: `src/qlab_mcp/write/registry.py`
- Modify: `tests/test_write_mode.py`
- Modify: `tests/test_server_tools.py` if output schema/content expectations change
- Modify: `CHANGELOG.md`

**Functions/classes:**

- `planned_write_capabilities`
- local `update_cues_capability`
- readiness response assertions

**Behavior before:** Readiness returns both `batch_update_cues` and
`edit_existing_cue` with the same capability payload.

**Behavior after:** If approved, readiness returns only `edit_existing_cue`; the
local variable becomes `edit_cues_capability`. If not approved, only rename the
local variable and retain both response keys.

**Implementation steps:**

1. Add/modify a focused test for the exact approved capability keys.
2. Rename the local variable to `edit_cues_capability`.
3. If approved, delete the `batch_update_cues` response entry. Do not modify the
   capability contents.
4. Add a clear 0.3.0 changelog bullet naming the readiness response key removal.
5. Do not rename `update_capabilities` returned by cue detail profiles or any
   schema/result field.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_write_mode.py -k 'readiness or capabilit'
.venv/bin/pytest -q tests/test_server_tools.py
```

**Verification:** Readiness response contains exactly the approved keys and the
same profiles/properties/gates as before.

**Risks:** Existing agents may read the removed JSON key. The canonical tool and
Edit capability remain, but this is still a breaking response change.

**Rollback:** Restore the duplicate response key; no production state involved.

**Dependencies:** Task 2; explicit decision 2.

**Stop conditions:** The two keys are not actually equivalent on the execution
branch, or a documented client depends on the legacy key and no break was
approved.

---

## Task 4: Correct FastMCP initialization metadata and universal instructions

**Goal:** Make initialization report QLab MCP `0.3.0` and teach universal rules
once without weakening tool-local safety.

**Why:** Current initialization reports framework version `3.3.1` as the server
version. Instructions are supported but currently repeat a mini-manual and call
the read surface “seven inspector tools” despite eight read-only tools including
readiness.

**Files:**

- Modify: `src/qlab_mcp/server.py`
- Modify: `tests/test_server_tools.py`
- Read only: `src/qlab_mcp/__init__.py`

**Functions/classes:**

- `mcp = FastMCP(...)`
- package `__version__`
- new/extended initialization contract test using `Client(mcp)`

**Behavior before:** `InitializeResult.serverInfo.version` is `3.3.1`; instructions
are 3,249 characters with repeated per-tool detail.

**Behavior after:** Server info version is `0.3.0`; instructions contain the
concise universal contract. Critical operation-specific rules remain in each
write description and code.

**Implementation steps:**

1. Import package `__version__` using the existing relative-import style. Verify
   no circular import; `__init__.py` must remain side-effect free.
2. Pass `version=__version__` to `FastMCP(...)`.
3. Rewrite instructions to cover only:
   - exact QLab MCP scope and exclusions;
   - connection/orientation order;
   - one workspace and exact UUIDs for writes;
   - readiness → dry-run → exact operation token → execute once → readback;
   - no automatic retry after timeout/identity ambiguity;
   - non-transactional batch warning;
   - structural result vs runtime validation vs GO readiness;
   - QLab 5.5.10 runtime-evidence boundary.
4. Do not include detailed argument lists, every settings profile, or per-tool
   token mechanics in the server instructions.
5. Add semantic assertions for required concepts and forbidden overclaim; do not
   snapshot the entire prose string.
6. Add an in-memory initialization assertion for name, project version, and
   instructions presence.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py -k 'instruction or initialize or contract'
PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format mcp
```

**Verification:** Wire initialization names QLab MCP version 0.3.0; inventory stays
13; critical write description assertions still pass independently.

**Risks:** Some hosts ignore server instructions. This is accepted because code
gates and local descriptions remain authoritative.

**Rollback:** Remove `version=` and restore previous instructions text.

**Dependencies:** Task 2; no dependency on docs redesign.

**Stop conditions:** Import cycle, changed tool inventory, or any safety concept
would exist only in server instructions after the edit.

---

## Task 5: Redesign read-tool metadata without changing behavior

**Goal:** Make the eight read-only tools easier to select and sequence.

**Why:** Reads are generally strong, but generated schemas lose some parameter
meaning and descriptions do not consistently name the next tool.

**Files:**

- Modify: `src/qlab_mcp/server.py`
- Modify only where field descriptions are owned there: `src/qlab_mcp/models.py`
- Modify: `tests/test_server_tools.py`

**Functions/tools:**

- `qlab_check_connection`
- `qlab_get_workspace_overview`
- `qlab_get_workspace_status`
- `qlab_get_workspace_settings`
- `qlab_get_workspace_setting_details`
- `qlab_query_cues`
- `qlab_get_cue_details`
- `qlab_check_write_readiness`

**Behavior before:** All tools have titles/tags/annotations, but some ranges/enums
are prose-only, `cue_ref` meaning is weak in the generated schema, and sequencing
is uneven.

**Behavior after:** Each description answers purpose, when/not, key prerequisite,
and next tool in compact prose. Parameter fields carry exact semantics. No reader,
OSC, response, or error behavior changes.

**Implementation steps:**

1. Establish a per-tool text budget as a review aid, not an enforced character
   limit. Prefer one compact paragraph plus `Before:`/`After:` sentences.
2. Connection: state “first orientation tool”; distinguish it from full write
   readiness.
3. Overview: state bounded structure purpose, truncation, and cue-details/query
   follow-up.
4. Status: state derived operational view and `not_exposed` boundary; do not imply
   a full QLab Workspace Status clone.
5. Settings: distinguish summary vs batch details and name the single-detail tool
   only as a compatibility convenience.
6. Setting details: explicitly say single request and point batch users back to
   settings mode `details`.
7. Query: distinguish filtered discovery from deep inspection; point exact
   results to cue details.
8. Cue details: restore exact `cue_ref` semantics in the generated input schema.
   First try moving/repeating the `Field` description at the signature boundary;
   do not create a request model solely for this.
9. Readiness: state it is read-only preflight, not authorization, and must precede
   every real write.
10. Use existing `Literal` types or min/max constraints only when doing so exactly
    matches runtime acceptance and does not require wrapper models. Record every
    intentional schema change.
11. Add parameter-level semantic assertions for IDs, profiles, limits, and
    follow-up names. Update only affected schema hashes.
12. Add `Client.call_tool` shape characterization for the eight reads with existing
    reader mocks. In particular freeze the observed cue-details single/batch shape;
    do not change the wrapper in this task.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py
PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format mcp
```

**Verification:** Eight tools remain read-only/idempotent; no QLab write calls can
be reached; output shapes are unchanged; only reviewed description/schema hashes
move.

**Risks:** Tightening an enum/range can reject inputs previously accepted by
runtime normalization. Skip any constraint without exact equivalence evidence.

**Rollback:** Revert one tool's metadata and associated expectations at a time.

**Dependencies:** Task 4 establishes universal text location.

**Stop conditions:** Fixing `cue_ref` requires a new request architecture, a
metadata edit changes runtime behavior, or cue-details shape proves client-
breaking and needs a separate design.

---

## Task 6: Redesign write-tool metadata and workflow cues

**Goal:** Make all five write tools independently safe and correctly sequenced
without repeating the full server policy.

**Why:** Create single is verbose, while Create batch, Edit, Move, and Delete omit
different prerequisite/follow-up details. Schema-valid calls can still violate
runtime-only relationships.

**Files:**

- Modify: `src/qlab_mcp/server.py`
- Modify: `src/qlab_mcp/models.py` only for field descriptions/simple equivalent constraints
- Modify: `tests/test_server_tools.py`
- Modify: `docs/development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md`
  only if the approved annotation decision differs from the research recommendation

**Functions/tools:**

- `qlab_create_cue`
- `qlab_create_cues`
- `qlab_edit_cues`
- `qlab_move_cues`
- `qlab_delete_cues`
- `CueUpdateInput`, `MoveCueInput`, write result models

**Behavior before:** Runtime gates are strong; agent-facing sequencing and schema
constraints are uneven. Edit/Move annotations say non-destructive.

**Behavior after:** Each write description states use/not-use, exact prerequisite,
dry-run/confirmation semantics, atomicity/rollback, no-retry rule, and post-write
readback in the minimum local prose. No token or runtime behavior changes.

**Implementation steps:**

1. Add a table-driven semantic test specification for the five tools. Test
   concepts, not exact paragraphs.
2. Create single:
   - shorten repeated server policy;
   - retain template-only creation, exact one placement selector, token v2,
     one-`/new` limit, and structural-not-GO-ready postcondition.
3. Create batch:
   - state 1–50 limit, sequential stop-on-failure, no automatic rollback, token
     family v1, and per-item readback;
   - do not imply single and batch tokens are interchangeable.
4. Edit:
   - state concrete cue UUID/ref resolution and editable capability discovery;
   - state per-item/per-operation gates, not a global token;
   - state non-atomic batch behavior, fresh verification, and timeout ambiguity;
   - explicitly exclude Create/Move/Delete/playback.
5. Move:
   - state UUID-only targets, exact one destination form, token v1, sequential
     non-atomic execution, and parent/order readback;
   - preserve current Cart evidence boundary.
6. Delete:
   - state exact leaves or recursive root-preserving mode, token v1, deepest-first
     sequential execution, no automatic rollback/retry, and disappearance/root
     verification.
7. Add simple `Field` constraints only where they mirror current runtime exactly
   (UUID format, list length, positive coordinates). Do not introduce compound
   Pydantic request wrappers solely to encode XOR.
8. For XOR/conditional rules that cannot be expressed simply, strengthen the
   relevant field/tool descriptions and retain runtime validation.
9. Decide annotations explicitly:
   - Create tools: keep `destructiveHint=false`;
   - Delete: keep `true`;
   - Edit and Move: recommended `true` because MCP `false` means additive-only.
     If changed, record as conservative metadata correction in changelog.
10. Do not change idempotence hints: all writes remain non-idempotent.
11. Do not add examples to descriptions. Add only tiny `Field(examples=[...])`
    for an ambiguous token/UUID format if a current client exposes them and the
    example is tested; otherwise leave examples to user docs.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py
.venv/bin/pytest -q tests/test_write_mode.py
PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format fastmcp
PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format mcp
```

**Verification:** Five public names and all runtime outputs remain stable; only
approved descriptions/annotations/equivalent schema constraints change; dry-run
tests send no setters.

**Risks:** Annotation correction can make clients ask for more confirmation.
Schema tightening can be client-visible. Both changes require explicit snapshots
and changelog entries.

**Rollback:** Revert metadata per tool; never alter safety implementation to make
old metadata tests pass.

**Dependencies:** Tasks 4–5; annotation decision recorded.

**Stop conditions:** Any requested text is false for one write family, any schema
constraint is stricter than current runtime, or a change requires token/readback
implementation changes.

---

## Task 7: Add the agent workflow guide

**Goal:** Put full multi-tool workflows and examples in one user document.

**Why:** Tools must be independently understandable, but long examples and
recovery procedures are wasteful in every description and overwhelming in the
README.

**Files:**

- Create: `docs/user/agent-workflows.md`
- Modify: `docs/user/README.md`
- Modify: `docs/user/tools.md`

**Sections:**

- choosing the right tool;
- Read, Create, Edit, Move, Delete workflows;
- dry-run and confirmation meanings;
- timeout and partial-failure interpretation;
- good vs invalid calls;
- runtime evidence and GO-readiness boundary.

**Behavior before:** Workflow fragments are repeated across README, server
instructions, tool descriptions, security, and runtime checklists.

**Behavior after:** One user guide owns full agent workflows; tools own local
contracts; developer checklists own validation procedures.

**Implementation steps:**

1. Write a compact chooser table mapping intent to one of 13 tools and explicit
   “not for” cases.
2. Document the read sequence:
   connection → overview/status → query → details.
3. Document each write sequence using exact current token family and postcondition.
4. Include one minimal good and one invalid/unsafe example per write family. Use
   placeholders such as `<workspace-uuid>` and `<cue-uuid>`; no personal paths or
   live identifiers.
5. State that Edit confirmation is per planned operation, not global.
6. State that batches are non-transactional and must not be automatically retried.
7. Separate QLab behavior from stricter MCP policy.
8. Link runtime-validation checklists for maintainers; do not reproduce their
   fixture evidence.
9. Reduce `docs/user/tools.md` back to a catalog with short purpose, risk, and
   workflow links. Remove its long Create tutorial.
10. Rework the `Writes` block in `docs/user/README.md` into short linked subsections.

**Tests:**

```bash
rg -n '<workspace-uuid>|<cue-uuid>' docs/user/agent-workflows.md
! rg -n '/Users/|mcp_prueba' docs/user/agent-workflows.md
rg -n 'selected|playhead|active' docs/user/agent-workflows.md
```

The final command may match examples explaining forbidden refs, but must not
present ambiguous refs as valid write targets.

**Verification:** Every tool name referenced exists in the 13-tool inventory;
tokens match code; no new runtime claim appears.

**Risks:** Duplication with runtime checklists. Link to them; do not copy their
step-by-step mutation protocol.

**Rollback:** Remove the new file and restore the two index links/paragraphs.

**Dependencies:** Final wording from Tasks 4–6.

**Stop conditions:** An example requires real UUIDs, implies a QLab mutation was
tested, or contradicts code/test evidence.

---

## Task 8: Redesign README with progressive disclosure

**Goal:** Turn README into a scannable technical landing page.

**Why:** It currently serves too many roles and repeats detailed safety/runtime
material available elsewhere.

**Files:**

- Modify: `README.md`
- Read/link only: `SECURITY.md`, `docs/user/*`, `docs/development/*`, `docs/status/*`

**Sections before:** Large Write-Mode Safety, family-specific implementation/
runtime evidence, profiles, configuration, diagnostic limits, signatures.

**Sections after:** Purpose, capability/boundary matrix, quick start, compact tool
overview, universal workflow, safety/evidence boundary, deeper links.

**Implementation steps:**

1. Preserve install/config commands that are current and tested.
2. Replace long opening prose with one factual paragraph.
3. Add a compact matrix:
   - read-only inspection;
   - gated Create/Edit/Move/Delete;
   - intentionally unsupported GO/playback/panic/raw OSC.
4. Keep one short Quick Start that reaches a read-only connection check.
5. Keep the authoritative 13-tool table; use one-line purposes and risk class.
6. Replace detailed write sections with one six-step universal flow and links to
   agent workflows/security.
7. Keep the three-level evidence distinction prominently.
8. Move, do not delete, useful detailed content:
   - operational examples → agent workflows;
   - token/security internals → `SECURITY.md` or development docs;
   - fixture/runtime facts → status/runtime-validation docs;
   - detailed signatures → generated tool catalog/docs.
9. Preserve configuration variables in the most appropriate single source and
   link from README; do not duplicate the full list twice.
10. Use short paragraphs, no decorative badges or marketing claims, and no
    architecture diagram unless it explains a relationship not clear in prose.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py -k readme
rg -n '^## ' README.md
rg -n 'qlab_update_cues|14 public tools|0\.2\.0' README.md
```

**Verification:** All 13 tools appear exactly once in the authoritative README
catalog; unsupported capabilities remain explicit; links resolve locally.

**Risks:** Valuable edge-case detail may be lost during shortening. Use a move map
in the diff review: every removed factual block must either be redundant or have
a deeper destination.

**Rollback:** Revert README only; deeper documents remain additive.

**Dependencies:** Task 7 provides destinations.

**Stop conditions:** Any current safety/evidence statement has no remaining home,
or README would claim runtime validation broader than current status.

---

## Task 9: Repair current documentation truth and navigation

**Goal:** Make current user/developer/status docs agree without reorganizing
history.

**Why:** Current indexes omit canonical documents, roadmap mixes closed history,
and coverage contains known contradictions.

**Files:**

- Modify: `docs/README.md`
- Modify: `docs/development/README.md`
- Modify: `docs/development/architecture.md`
- Modify headings only as needed: `docs/development/runtime-validation/edit-cues.md`
- Modify: `docs/status/README.md`
- Modify: `docs/status/roadmap.md`
- Modify: `docs/status/coverage/osc_coverage_snapshot.md`
- Modify: `SECURITY.md`
- Modify: `CHANGELOG.md`
- Move after recording supersession: `docs/superpowers/plans/2026-08-12-qlab-mcp-0-3-0.md`
  to `docs/archive/plans/`

**Behavior before:** Current documents disagree about active work, runtime coverage,
and the universal write sequence. The older release plan explicitly preserves the
internal method and is now superseded.

**Behavior after:** Current indexes link the canonical state/audit/research; roadmap
contains active/blocked decisions with links to history; coverage agrees with
current evidence; security distinguishes universal and tool-specific rules; old
plan is preserved as history.

**Implementation steps:**

1. Link `current-state.md`, `architecture-audit-0.3.0.md`, and this research report
   from the appropriate existing indexes.
2. Reduce roadmap's active section to the five real workorders and explicit gates.
   Link closed phase history to archive instead of embedding hundreds of lines.
3. Repair stale workorder paths using their current archive/blocked locations.
4. Reconcile the four audited coverage contradictions using code, tests, roadmap,
   and dated runtime evidence. If evidence is insufficient, mark pending; never
   infer validation.
5. In `SECURITY.md`, make the universal sequence dry-run/review/execute once/fresh
   readback. Move token cardinality and rollback wording into Create/Edit/Move/
   Delete-specific subsections.
6. Add Markdown `##`/`###` hierarchy to the Edit runtime checklist without
   changing procedure or evidence.
7. Mark the 2026-08-12 plan as superseded, then preserve it under archive rather
   than rewriting its historical recommendation.
8. Add changelog bullets for only approved public metadata/response changes.
9. Do not finalize `current-state.md` with a release SHA in this task. That remains
   the post-merge docs-only release step already defined by the release plan.

**Tests:**

```bash
rg -n 'Devamp|Fade|customString|cueTargetNumber' \
  docs/status/coverage/osc_coverage_snapshot.md docs/status/roadmap.md README.md
rg -n 'qlab_update_cues|update_cues' README.md docs/user docs/development docs/status \
  -g '*.md' -g '!research/**'
git diff --check
```

Historical matches in `CHANGELOG.md`, `docs/archive/**`, and the research report
are valid.

**Verification:** Current docs agree on 13 tools, current runtime boundary, active
workorders, and Edit naming; archive contents remain historically intact.

**Risks:** Moving closed roadmap prose can obscure history. Preserve it in archive
or link existing archived evidence before deleting from the active roadmap.

**Rollback:** Restore individual current documents and old plan location; no code
or runtime state involved.

**Dependencies:** Tasks 2–8; workorder classifications from current state.

**Stop conditions:** A coverage conflict requires new runtime evidence, an archive
edit would change historical truth, or current-state finalization would require a
SHA not yet available.

---

## Task 10: Add semantic contract guards and measure context

**Goal:** Protect agent usability without brittle full-prose snapshots.

**Why:** Tool text and metadata are API. Existing hashes catch drift but do not
explain semantic regressions.

**Files:**

- Modify: `tests/test_server_tools.py`
- Modify: `tests/test_write_mode.py`
- Modify only if packaging docs inventory is checked there: `tests/test_packaging.py`

**Functions/classes:**

- `_tool_contract_snapshot`
- new parametrized semantic metadata tests
- new instructions/version test
- read/write `Client.call_tool` characterization tests

**Behavior before:** Exact hashes and a few required phrases protect the catalog;
instructions, all read call shapes, cross-tool references, and error-channel
semantics are not fully characterized.

**Behavior after:** Small table-driven tests protect names, metadata semantics,
workflow concepts, critical parameter meaning, public call shapes, and project
version while allowing prose edits.

**Implementation steps:**

1. Keep the exact 13-tool set and schema hashes.
2. Replace duplicated phrase assertions with one data table per tool containing
   required concepts, not full sentences.
3. Assert all cross-referenced tool names exist.
4. Assert annotation matrix by risk class and the approved Edit/Move decision.
5. Assert every title is non-empty and tags include `qlab` plus one functional/
   risk grouping.
6. Assert universal instructions contain scope, no-playback boundary, UUID,
   readiness, dry-run, no-retry, readback, and evidence boundary.
7. Characterize all eight read tool call shapes and cue-details wrapper behavior.
8. Characterize one structured domain error: document whether MCP `isError` is
   false while payload `ok/status` indicates failure. Do not change behavior here.
9. Add a source guard for exact plural method symbols in Python sources/tests.
   Exclude history and natural-language documents deliberately.
10. Add a deterministic test/helper that reports description, instruction, input,
    and output schema byte counts. Use it as a review report, not a hard token
    budget unless a future regression threshold is evidence-based.
11. Compare before/after component sizes. Require removal of duplicate prose and
    no unexplained schema growth; do not require a model-specific token count.

**Tests:**

```bash
.venv/bin/pytest -q tests/test_server_tools.py tests/test_write_mode.py tests/test_packaging.py
```

**Verification:** A deliberate metadata/schema change fails with an actionable
assertion; harmless wording changes can pass if concepts remain.

**Risks:** Semantic phrase tests can still become editorial. Limit each to safety,
selection, sequencing, or output concepts that change agent behavior.

**Rollback:** Revert only newly added assertions/report helper; retain existing
hash coverage.

**Dependencies:** Final tool/docs contract from Tasks 4–9.

**Stop conditions:** Tests need to import private FastMCP internals, measurements
vary nondeterministically, or the suite starts snapshotting complete prose.

---

## Task 11: Full non-mutating release verification

**Goal:** Prove the implementation and documentation iteration is release-ready
without touching QLab or remote Git state.

**Why:** The work changes a public agent-facing contract and an internal routing
name. It needs full local/CI/package verification.

**Files:** No planned edits. If a check fails, return to the owning task.

**Behavior before/after:** No runtime QLab behavior is exercised. The final local
tree must contain only approved 0.3.0 changes and planning history.

**Implementation steps:**

1. Run focused suites first, then full suite:

   ```bash
   .venv/bin/pytest -q tests/test_server_tools.py
   .venv/bin/pytest -q tests/test_write_mode.py
   .venv/bin/pytest -q tests/test_qlab_reader.py tests/test_update_registry_coverage.py
   .venv/bin/pytest -q -p no:cacheprovider
   ```

2. Inspect both FastMCP and wire MCP formats:

   ```bash
   PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format fastmcp
   PYTHONPATH=src .venv/bin/fastmcp inspect fastmcp_entrypoint.py:mcp --format mcp
   ```

3. Verify lock and build using the release environment selected by CI:

   ```bash
   uv lock --check
   uv build --out-dir /tmp/qlab-mcp-build
   ```

4. Inspect wheel/sdist contents and metadata. Confirm version `0.3.0`; exclude
   `.codex/`, `engineering-review/`, `local/`, research attachments, and Git data.
5. Verify exact public/internal surface:

   ```bash
   rg -n '\b(update_cues|qlab_update_cues)\b' src tests -g '*.py'
   git diff --check
   git status --short --branch
   ```

6. Run the existing CI workflow in a clean checkout or let GitHub CI do so only
   after later push authorization. Local clean-checkout verification must not be
   described as GitHub CI.
7. Review `git diff --name-status` and confirm no archive/reference source content
   was rewritten except the approved move of the superseded plan.
8. Create local commits only if explicitly authorized for execution. Keep concerns
   separable: internal Edit cleanup; metadata/contract; documentation.

**Tests:** Commands above.

**Verification acceptance:**

- exactly 13 tools;
- no public or Python plural alias;
- server version 0.3.0;
- approved annotations and schemas;
- full suite green;
- lock/build/package green;
- current docs coherent;
- no QLab call or remote mutation performed.

**Risks:** Local in-memory/STDIO checks do not prove every MCP host refreshes cached
metadata. A real host refresh test may be performed later without QLab mutation.

**Rollback:** Revert the smallest failing task/commit; do not weaken tests or safety
to force release acceptance.

**Dependencies:** Tasks 1–10 complete.

**Stop conditions:** Full suite or CI contradicts focused tests; tool count is not
13; a package contains excluded files; schema/output changes were not approved;
or any verification would require QLab mutation, push, PR, merge, or tag.

---

## Task 12: Preserve the existing release closure sequence

**Goal:** Integrate this iteration with the already approved 0.3.0 release process.

**Why:** This plan does not replace the requirement that the final tag include the
canonical current-state snapshot.

**Files:**

- Final post-merge docs-only change: `docs/status/current-state.md`

**Behavior before:** Preparation branch carries a provisional snapshot.

**Behavior after:** Only after separately authorized merges, the definitive main
SHA, green CI, 13 tools, package verification, and pending workorders are recorded;
`v0.3.0` points at that final commit.

**Implementation steps:**

1. Stop after local implementation/verification and request publication approval.
2. If later authorized, preserve the sequence:

   ```text
   push branch
   -> primary PR and green CI
   -> review
   -> protect main with required pytest check
   -> merge
   -> verify main
   -> docs-only final current-state PR
   -> merge and verify definitive main
   -> tag v0.3.0
   ```

3. Do not update version documentation after the tag.

**Tests:** Full release verification on definitive main.

**Verification:** Tag commit includes the exact final current-state snapshot.

**Risks:** Remote state or required authorization may differ when this phase is
reached.

**Rollback:** Publication actions require their own explicit recovery plan; none
are authorized by this document.

**Dependencies:** Task 11 plus separate remote authorization.

**Stop conditions:** Any missing authorization, red CI, changed main, unresolved
review, or snapshot mismatch.

## Deferred beyond 0.3.0

- new QLab capabilities, GO/playback/panic/raw OSC;
- dynamic toolsets, discovery executors, or an embedded agent;
- removal of `qlab_get_workspace_setting_details`;
- full typed migration of `list[dict[str, Any]]` outputs;
- compound `oneOf` request-model redesign;
- global error-envelope and MCP `isError` migration;
- schema dereferencing/token optimization experiments;
- renaming generic public update/result fields and error codes;
- OSC transport or architecture refactor;
- new runtime validation or broadened QLab version claims;
- mass-moving or rewriting archive/reference/QClass content.

## Final executor handoff

Before starting implementation, read the research report and re-run Task 1's
baseline. Execute one task at a time. After each task, run its focused checks and
inspect the diff. If evidence contradicts a decision, stop and report it; do not
silently widen the plan.
