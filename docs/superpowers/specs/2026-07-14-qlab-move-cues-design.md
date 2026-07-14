# QLab Move Cues Design

## Goal

Expose one gated FastMCP tool, `qlab_move_cues`, that plans and executes one to ten ordered QLab cue moves. It never claims atomicity.

## Public contract

```python
qlab_move_cues(
    workspace_id: WorkspaceId,
    moves: list[MoveCueInput],  # 1..10
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> MoveCuesResult
```

`MoveCueInput` uses concrete UUID strings only. A List or Group destination accepts exactly one of `destination_index`, `before_cue_id`, `after_cue_id`, or `position` (`first` or `last`). A Cue Cart destination requires `destination_parent_id`, `cart_row`, and `cart_column`, and rejects every linear placement field.

## Supported and blocked behavior

Documented linear route: `/workspace/{id}/move/{cue_id} {new_index} [new_parent_cue_id]`. Documented Cart-only route: `/cue/{cart}/moveCartCue/{child} {row} {column}`. Carts are two-dimensional and have no ordering; Groups cannot be placed in Carts.

Linear index base, same-parent removal semantics, Cart cross-parent behavior, Cart coordinate base, top-level Cue List moves, and identity/property preservation require disposable-workspace proof. Until each case is proven, real execution rejects it with an explicit blocked status; dry-run may report it as runtime-blocked without emitting a setter.

## Internal design

Keep public surface to one tool. Add an isolated structural move module with `plan_single_move`, `simulate_move_batch`, `execute_single_move`, `execute_move_batch`, `verify_move_batch`, and `build_inverse_move_batch`.

Batch interpreter processes moves in supplied order. It reads a compact ordered tree, normalizes placement, updates an in-memory tree after each simulated move, and rejects duplicate sources, self references, cycles, ambiguous descendant moves, changing unresolved references, and unresolvable same-position requests.

Dedicated `confirm:moveCues:v1:` token binds workspace, normalized move list, initial/final neighbors, ordered-child fingerprints, source parent/index or Cart cell, health/activity snapshot, version, and expiry. Generic, stale, malformed, and wrong-family tokens fail before any setter.

Real execution repeats readiness and dependency reads, sends one typed setter per move in deterministic order, stops on first genuine failure, verifies final tree independently, and returns per-move evidence. Setter timeout is success only after matching fresh readback. Rollback is separately confirmed inverse batch in reverse order; no atomicity claim.

## Safety and scope

Require Edit Mode, write readiness, activity `0 / 0 / 0`, healthy inactive source/destination, exact workspace and cue UUIDs, no `/live`, no save, no playback control, and no raw OSC. Stop on unexpected activity, structure, or readback.

Do not change property registry semantics, existing public tools, deletion, duplication, save, playback, raw OSC, cross-workspace movement, or ten-move ceiling. Reuse existing FastMCP/Pydantic models, QLab client, readiness checks, response shape, and `Client` tests. No FastAPI endpoint or dependency.
