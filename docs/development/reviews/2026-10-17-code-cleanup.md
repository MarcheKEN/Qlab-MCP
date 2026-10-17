# Code cleanup — 2026-10-17

Baseline: `11b3040`. Scope: structural inventory of all 70 source modules,
two scripts and 46 existing test modules, followed by targeted semantic review
of shared readers, settings dispatch, writers and their callers. This is not
a line-by-line proof of every module.

## Changes

- Reuse existing workspace metadata, container classification and boolean
  normalization helpers, preserving priority, falsey values and errors.
- Reuse exact-key settings lookup before the existing case-insensitive fallback.
- Combine identical Video collection dispatch and cue creation branches; remove
  unreachable General detail handling.
- Inherit identical visual/control fields instead of redeclaring them, retaining
  named model classes, field order and schemas.
- Add 48 focused regression cases. Source changes remove 62 net lines across
  seven modules; no new dependencies or public API changes.

## Verification

- Baseline: 1,894 tests passed, 35 skipped, 61 subtests passed.
- Final: 1,942 tests passed, 35 skipped, 61 subtests passed.
- All 79 MCP tool definitions exactly match the baseline, including descriptions,
  annotations and input/output schemas. Eight affected Pydantic models retain
  identical schemas, field order and field definitions.
- Incremental focused suites, `git diff --check`, `uv lock --check`, wheel and
  source distribution builds passed. Independent final code review found no
  blocker.

## Boundaries

Security gates, preflight/readback calls, confirmation handling, deadlines and
cache behavior were retained. Larger writer splits and speculative optimizations
were rejected because they would add state transfer or alter validation order.
GitNexus and pygount were unavailable; a standard-library AST inventory was used
without adding dependencies. There is no configured lint/type-check gate.
No new live QLab, playback or hardware validation was performed. The passing
automated suite does not establish those runtime properties.
