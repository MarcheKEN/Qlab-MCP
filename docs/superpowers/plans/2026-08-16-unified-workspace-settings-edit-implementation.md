# Unified Workspace Settings Edit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task.

**Goal:** Rename the public Workspace Settings write tool and expose only the implemented `general.minGoTime` operation in Wave 1.

**Architecture:** Use a nested typed operation object backed by one concrete
Wave 1 Pydantic model, an executable registry containing only enabled
operations, and the existing single-setter/token/readback lifecycle. Keep
future researched operations in documentation until their own implementation
wave.

**Tech Stack:** Python 3.11, Pydantic, FastMCP, OSC, pytest.

## Global Constraints

- One operation and at most one setter per confirmed call.
- Wave 1 accepts only `general.minGoTime`.
- `general.selectionIsPlayhead` is research-only and absent from the public schema.
- Unknown/non-enabled operation kinds fail before transport and produce zero setters.
- No raw OSC path/value, generic setter, AppleScript fallback, `/live`, GO, playback, panic, retry, merge, release, or version bump.
- Public tool count remains exactly fourteen.

---

### Task 1: Implement the Wave 1 request models

**Files:**

- Modify: `src/qlab_mcp/models.py`
- Test: `tests/test_workspace_settings_write.py`

**Interfaces:**

```python
class GeneralMinGoTimeOperation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["general.minGoTime"]
    value: Annotated[StrictInt | StrictFloat, Field(ge=0)]


WorkspaceSettingsOperation = GeneralMinGoTimeOperation


class WorkspaceSettingsEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workspace_id: UUID
    operation: WorkspaceSettingsOperation
    dry_run: bool | None = None
    confirm_token: str | None = None
```

- [x] Write failing tests for nested `kind`/`value`, strict numeric input,
  exact UUIDs, extra-key rejection, and deferred operation rejection.
- [x] Run `pytest -q tests/test_workspace_settings_write.py` and observe the
  import/schema failure before implementation.
- [x] Implement the concrete model alias and preserve finite, non-negative,
  OSC int32/float32 validation.
- [x] Add `unchanged` and defensive `unsupported` result states without adding
  any deferred operation to the request schema.
- [x] Verify `pytest -q tests/test_workspace_settings_write.py`.

### Task 2: Qualify and narrow the executable registry

**Files:**

- Modify: `src/qlab_mcp/settings/write_registry.py`
- Test: `tests/test_workspace_settings_write.py`

The registry key and specification operation ID are exactly:

```text
general.minGoTime
```

- [x] Change the registry key from `minGoTime` to `general.minGoTime`.
- [x] Keep the exact `settings/general/minGoTime` setter/readback paths.
- [x] Keep the registry limited to one enabled operation.
- [x] Test unknown and research-only IDs fail before transport.
- [x] Verify zero setter calls for rejected requests.

### Task 3: Rename and adapt the write lifecycle

**Files:**

- Modify: `src/qlab_mcp/settings/write_operations.py`
- Test: `tests/test_workspace_settings_write.py`

Implement:

```python
def edit_workspace_settings(
    self,
    request: WorkspaceSettingsEditRequest,
) -> WorkspaceSettingsEditResult:
    ...
```

- [x] Extract `operation.kind` and `operation.value` only after Pydantic
  validation.
- [x] Preserve exact workspace resolution, readiness, activity, baseline,
  token, one-setter, timeout, cache, and fresh-readback behavior.
- [x] Bind tokens and result records to `general.minGoTime`.
- [x] Return `unchanged` from dry-run when the fresh baseline already matches,
  with no token, plan, or setter.
- [x] Verify timeout-confirmed, inconclusive, mismatch, replay, stale-baseline,
  activity, and canonical-UUID tests.

### Task 4: Rename the FastMCP tool

**Files:**

- Modify: `src/qlab_mcp/server.py`
- Test: `tests/test_server_tools.py`

Expose only:

```python
def qlab_edit_workspace_settings(
    workspace_id: UUID,
    operation: WorkspaceSettingsOperation,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> WorkspaceSettingsEditResult:
    ...
```

- [x] Remove the old public function name.
- [x] Construct `WorkspaceSettingsEditRequest` and call
  `reader.edit_workspace_settings`.
- [x] Verify the nested FastMCP schema has only the `general.minGoTime`
  operation, no artificial one-item `oneOf`, and no `selectionIsPlayhead`.
- [x] Verify invalid operation kinds fail before handler execution.
- [x] Verify the public tool count remains fourteen and `qlab_update_cues`
  remains absent.

### Task 5: Update current documentation and artifacts

**Files:**

- Modify: `README.md`
- Modify: `docs/user/tools.md`
- Modify: `docs/user/agent-workflows.md`
- Modify: `docs/development/architecture.md`
- Create: `docs/superpowers/specs/2026-08-16-unified-workspace-settings-edit-design.md`
- Create: `docs/superpowers/plans/2026-08-16-unified-workspace-settings-edit-implementation.md`

- [x] Document the new public tool and nested request shape.
- [x] Document one operation/one setter and qualified IDs.
- [x] Keep `selectionIsPlayhead` only in research/capability documentation as
  `NEEDS_RUNTIME_RESEARCH`.
- [x] State that adding a future operation to the public model is part of that
  operation's implementation wave.
- [x] Preserve historical reports as historical evidence where applicable.

### Task 6: Verify and hand off

Run:

```bash
./.venv/bin/pytest -q tests/test_workspace_settings_write.py tests/test_server_tools.py
uv run fastmcp inspect fastmcp.json
./.venv/bin/pytest -q
git diff --check
git status --short --untracked-files=all
```

- [ ] Confirm no QLab mutation occurred.
- [ ] Confirm the final public tool inventory is fourteen tools.
- [ ] Confirm PR #16 remains open and unmerged.
- [ ] Create one bounded follow-up commit only after all verification passes.
- [ ] Push only `feature/workspace-settings-write`; never merge PR #16.
