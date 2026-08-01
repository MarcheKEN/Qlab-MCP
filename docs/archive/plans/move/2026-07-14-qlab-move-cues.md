# QLab Move Cues Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one safe, non-atomic `qlab_move_cues` tool for ordered batches of one to ten QLab cue moves.

**Architecture:** New structural-move code owns normalization, simulation, token binding, execution, verification, and inverse planning. `server.py` only exposes typed FastMCP input/output; existing QLab reader/client performs typed OSC calls. Unknown runtime semantics remain real-write blocked until disposable-workspace evidence promotes them.

**Tech Stack:** Python 3.11, FastMCP 3.3.1, Pydantic 2, pytest, QLab OSC.

## Global Constraints

- Public tool only: `qlab_move_cues`; no `qlab_move_cue` alias.
- `moves` accepts 1..10 entries; batch is sequential, never atomic.
- No FastAPI, new dependency, raw OSC tool, `/live`, save, playback control, cross-workspace moves, or commit.
- Preserve existing dirty worktree changes.
- TDD: every production behavior begins with a focused failing test.
- Real moves require runtime-proven semantics, readiness, Edit Mode, inactive healthy cues, exact tokens, and fresh readback.

---

### Task 1: Typed public contract and schema tests

**Files:**

- Modify: `src/qlab_mcp/models.py`
- Modify: `src/qlab_mcp/server.py`
- Test: `tests/test_server_tools.py`

**Produces:** `MoveCueInput`, `MoveCuesResult`, and `qlab_move_cues`.

- [ ] **Step 1: Write failing schema test**

```python
def test_move_cues_fastmcp_schema_limits_and_nested_model() -> None:
    tool = asyncio.run(mcp.get_tool("qlab_move_cues"))
    moves = tool.inputSchema["properties"]["moves"]
    assert moves["minItems"] == 1
    assert moves["maxItems"] == 10
    assert "MoveCueInput" in tool.inputSchema["$defs"]
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_server_tools.py -k move_cues_fastmcp_schema -q --tb=short`

Expected: FAIL because tool does not exist.

- [ ] **Step 3: Add minimum models and facade**

```python
class MoveCueInput(BaseModel):
    cue_id: str
    destination_parent_id: str | None = None
    destination_index: int | None = None
    before_cue_id: str | None = None
    after_cue_id: str | None = None
    position: Literal["first", "last"] | None = None
    cart_row: int | None = None
    cart_column: int | None = None

@mcp.tool(title="Move QLab Cues", tags={"qlab", "write-mode", "cue-move", "gated-write"}, annotations=GATED_CREATE_QLAB_TOOL, timeout=UPDATE_CUES_TIMEOUT)
def qlab_move_cues(workspace_id: WorkspaceId, moves: Annotated[list[MoveCueInput], Field(min_length=1, max_length=10)], dry_run: bool | None = None, confirm_token: str | None = None) -> MoveCuesResult:
    return _run_tool(lambda: MoveCuesResult.model_validate(_reader().move_cues(workspace_id, [move.model_dump() for move in moves], dry_run, confirm_token)))
```

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_server_tools.py -k move_cues_fastmcp_schema -q --tb=short`

Expected: PASS.

### Task 2: Planning, normalization, and in-memory simulation

**Files:**

- Create: `src/qlab_mcp/write/moves.py`
- Modify: `src/qlab_mcp/qlab.py`
- Test: `tests/test_write_mode.py`

**Produces:** `plan_single_move`, `simulate_move_batch`, and `MovePlan`.

- [ ] **Step 1: Write failing ordered-simulation test**

```python
def test_simulate_move_batch_applies_moves_in_input_order() -> None:
    tree = {"list": ["a", "b", "c"], "group": []}
    result = simulate_move_batch(tree, [
        {"cue_id": "a", "destination_parent_id": "list", "position": "last"},
        {"cue_id": "b", "destination_parent_id": "group", "position": "first"},
    ])
    assert result.children_by_parent == {"list": ["c", "a"], "group": ["b"]}
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_write_mode.py -k simulate_move_batch -q --tb=short`

Expected: FAIL because `simulate_move_batch` is missing.

- [ ] **Step 3: Add fail-closed simulation**

Validate strict UUIDs; exactly one linear placement field; Cart-field exclusivity; duplicate/self/reference/cycle checks; sequential tree mutation; neighbor fingerprints. Return `runtime_blocked` before a setter whenever index or Cart semantics are unproven.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_write_mode.py -k "simulate_move_batch or move_contract" -q --tb=short`

Expected: PASS.

### Task 3: Dedicated token and dry-run path

**Files:**

- Modify: `src/qlab_mcp/write/moves.py`
- Modify: `src/qlab_mcp/qlab.py`
- Test: `tests/test_write_mode.py`

**Produces:** `confirm:moveCues:v1:` encoder/decoder and `QLabReader.move_cues` dry-run result.

- [ ] **Step 1: Write failing token/dry-run test**

```python
def test_move_cues_dry_run_emits_dedicated_token_and_no_setter() -> None:
    result = reader.move_cues("ws-1", [valid_linear_move], dry_run=True, confirm_token=None)
    assert result["status"] == "planned"
    assert result["confirm_token"].startswith("confirm:moveCues:v1:")
    assert client.requests == []
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_write_mode.py -k move_cues_dry_run -q --tb=short`

Expected: FAIL because move planning is absent.

- [ ] **Step 3: Add signed, expiring payload**

Use existing HMAC/canonical JSON conventions. Bind workspace, all normalized moves, initial/final neighbor UUIDs, ordered-child fingerprints, health/activity snapshot, and expiry. Reject generic/wrong-family/malformed/stale tokens before any OSC call.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_write_mode.py -k "move_cues_dry_run or move_token" -q --tb=short`

Expected: PASS.

### Task 4: Typed setters, execution, readback, and inverse plan

**Files:**

- Modify: `src/qlab_mcp/qlab.py`
- Modify: `src/qlab_mcp/write/moves.py`
- Test: `tests/test_write_mode.py`

**Produces:** `execute_move_batch`, `verify_move_batch`, and `build_inverse_move_batch`.

- [ ] **Step 1: Write failing partial-failure test**

```python
def test_move_cues_stops_after_first_failed_setter_and_marks_partial_failed() -> None:
    result = reader.move_cues("ws-1", [first_move, second_move], dry_run=False, confirm_token=token)
    assert result["status"] == "partial_failed"
    assert result["attempted_count"] == 1
    assert result["rollback_required"] is True
```

- [ ] **Step 2: Verify RED**

Run: `.venv/bin/pytest tests/test_write_mode.py -k partial_failed -q --tb=short`

Expected: FAIL because real execution is absent.

- [ ] **Step 3: Add typed routes only after runtime promotion**

Call linear `/workspace/{id}/move/{cue_id}` through `QLabOscClient.request`. Call Cart-internal `/cue_id/{cart}/moveCartCue/{child}` only for runtime-proven Cart semantics. Recheck readiness/activity/dependencies before first setter. Read fresh ordered children after every batch; timeout succeeds only when readback matches. Build inverse moves in reverse order but require fresh rollback token.

- [ ] **Step 4: Verify GREEN**

Run: `.venv/bin/pytest tests/test_write_mode.py -k "move and (partial_failed or confirmed_timeout or rollback)" -q --tb=short`

Expected: PASS.

### Task 5: Disposable runtime matrix and workorder

**Files:**

- Create: `docs/current/workorders/027_move_cues_safe_editing.md`
- Modify: `docs/current/workorders/README.md`
- Test: `tests/test_server_tools.py`

- [ ] **Step 1: Record runtime evidence before promotion**

Use only new harmless dummy cues in `<TEST_WORKSPACE_NAME>`. Before every trial verify readiness and `running/paused/auditioning = 0/0/0`; after every successful trial read back and execute separately confirmed inverse move. Cover linear zero/one base, same-parent up/down, List/Group cross-parent, Group subtree, UUID/property preservation, top-level Lists, Cart coordinates, Cart cross-parent, invalid parent/index, and no activity.

- [ ] **Step 2: Write tests from observations**

Add an assertion for every promoted semantic. Leave unproven operations `runtime_blocked`; do not infer behavior from a single error reply.

- [ ] **Step 3: Document capability boundary**

Write QLab version, routes, supported cases, blockers, token/readback/rollback evidence, and emergency-stop availability. Link workorder from `docs/current/workorders/README.md`.

- [ ] **Step 4: Verify**

Run:

```text
.venv/bin/pytest tests/test_write_mode.py -k "move or Move" -q --tb=short
.venv/bin/pytest tests/test_server_tools.py -k "move or Move" -q --tb=short
.venv/bin/pytest tests/test_write_mode.py tests/test_update_registry_coverage.py tests/test_server_tools.py -q --tb=short
git diff --check
git diff --cached --check
git status --short
```

Expected: selected tests pass; diff checks exit 0; status contains expected move-cues files plus pre-existing user changes.
