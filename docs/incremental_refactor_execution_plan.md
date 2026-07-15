# Incremental Refactor Execution Plan

This plan converts the Deep Research report into small, reviewable work for this repository. Treat the report as guidance, not as an order. Verify each recommendation against current code before editing.

## Contract Rules

- The FastMCP tools in `src/qlab_mcp/server.py` are public contract.
- Do not rename tools, rename public parameters, change Pydantic response models, or change schema hashes without an explicit public-contract reason.
- Never update contract snapshots or schema hashes just to make tests pass. If a hash changes, explain exactly what changed in the public contract and get approval unless that public change was explicitly requested.
- Keep write mode disabled-by-default, gated, and dry-run-first.
- Do not add GO, playback, stop, panic, raw OSC, ungated deletion, ambiguous deletion, container deletion, or cascade deletion tools. Preserve the existing exact-UUID, dry-run-first, token-gated, leaf-only `qlab_delete_cues` boundary unless an explicit public-contract change is separately approved.
- Do not allow write targets that use ambiguous refs such as `selected`, `active`, `playhead`, or `playbackPosition`.

## Verified Hotspots

- `src/qlab_mcp/server.py`: FastMCP entrypoint and public tool contract.
- `src/qlab_mcp/models.py`: public request/response model contracts.
- `src/qlab_mcp/qlab.py`: compatibility facade over read and write mixins.
- `src/qlab_mcp/write/operations.py`: main write-mode hotspot with planning, validation, execution, verification, result building, tokens, and timeout handling.
- `src/qlab_mcp/write/registry.py`: data-driven update profile registry.
- `tests/test_server_tools.py`: public tool schema, annotation, timeout, and error-contract coverage.
- `tests/test_write_mode.py`: write-mode dry-run, confirm-token, real-write, timeout, and verification coverage.

## First PR Sequence

1. Docs-only execution plan.
   - Touch only this file.
   - No runtime tests required.
2. Server error/response helper extraction.
   - Touch `src/qlab_mcp/server.py` and a small helper module.
   - Do not move `@mcp.tool` declarations, signatures, annotations, timeouts, or models.
   - Run `uv run pytest tests/test_server_tools.py`.
3. Write timeout helper extraction.
   - Touch `src/qlab_mcp/write/operations.py` and a small timeout helper module.
   - Extract timeout/budget responsibility only.
   - Do not split cue families, planning, validation, execution, verification, tokens, registry, or result builders.
   - Run `uv run pytest tests/test_write_mode.py tests/test_update_registry_coverage.py`.

After these PRs, continue one responsibility at a time: result building, planning, validation, execution, then verification.

## PR Splitting Rules

- Keep docs, tests, registry changes, runtime logic, and operation-specific behavior in separate PRs unless a small coupling is unavoidable.
- Treat PR #9 as the example of what not to repeat: one oversized mixed-concern PR spanning docs, tests, registry, runtime, and operation behavior.
- Avoid PRs that change `server.py`, `models.py`, and `write/operations.py` together.
- For write-mode refactors, extract one responsibility at a time. Do not split many cue families in the same PR.

## Deferred Recommendations

Do not execute these yet:

- Split `models.py`.
- Change `QLabReader` from mixins to composition.
- Reorganize all tests.
- Add automatic registration in `write/registry.py`.
- Move many tools out of `server.py`.
- Split all of `write/operations.py`.

Each deferred item needs characterization tests, a small PR plan, behavior validation, and human review first.
