# 027 — Move cues safe editing

Status: local implementation complete; runtime semantics pending

## Public boundary

- One public FastMCP tool: `qlab_move_cues`.
- It accepts one to ten UUID-addressed moves and never claims atomicity.
- Linear List/Group placement accepts exactly one of `destination_index`,
  `before_cue_id`, `after_cue_id`, `first`, or `last`.
- Cue Carts require `destination_parent_id`, `cart_row`, and `cart_column` and
  reject linear placement fields.
- There is no public single-cue move tool, raw OSC tool, playback action, or
  workspace-save action.

## Implemented local gates

- Strict workspace and cue UUID resolution.
- Duplicate sources, source/reference equality, top-level List/Cart moves,
  parent-type errors, cycles, broken/warning sources or destinations, and
  active cues are rejected before a setter.
- The batch is simulated in input order. References to a cue moved in the same
  batch and container/descendant pairs are rejected rather than guessed.
- Each linear setter uses its own simulated intermediate insertion index, not
  the final batch index.
- Dry-run produces `confirm:moveCues:v1:` with workspace, ordered plan,
  original and resulting neighbors, child-order fingerprints, health, activity,
  and expiry bound into its signed payload.
- Real linear execution rechecks write readiness and activity, executes one
  setter at a time, performs a fresh structural readback after each setter, and
  stops at the first error or mismatch. A timeout is successful only when that
  readback proves the expected move.
- Partial failure returns inverse UUID moves in reverse order and requires a
  fresh dry-run/token before rollback. It never auto-rolls back or claims an
  atomic recovery.

## Runtime boundary

The QLab 5.5.10 disposable workspace must establish before promotion:

1. zero- versus one-based `new_index` and same-parent up/down semantics;
2. List/Group transfer, nested Group, UUID/property preservation, and invalid
   parent/index replies;
3. Cue Cart row/column readback and whether a cross-parent Cart transfer needs
   one or two routes;
4. Cart-to-List/Group restoration and top-level Cue List behavior.

Until this matrix is recorded, real Cue Cart writes remain explicitly
`runtime_blocked`. Runtime trials use only fresh harmless dummy cues in Edit
Mode with readiness and activity `0 / 0 / 0`; no GO, playback, audition,
`/live`, raw OSC interface, or workspace save.

Current runtime fixture: `MCP_MOVE_RUNTIME_GROUP` plus Memo cues `A`, `B`, and
`C` in `mcp_prueba.qlab5`. The first dry-run exposed an unlabelled structural
read error before any move setter: QLab requires the uppercase UUID spelling it
returned in OSC cue paths. The reader now compares UUIDs canonically while
preserving QLab's original spelling in every OSC route/parent argument; reload
MCP before retrying it.
