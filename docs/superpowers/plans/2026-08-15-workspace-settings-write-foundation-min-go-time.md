# Workspace Settings Write Foundation + `minGoTime` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Add the first gated Workspace Settings write capability, `qlab_edit_general_settings`, supporting only `general.minGoTime`.

**Architecture:** A dedicated settings-write registry and operation module, reusing existing readiness, token, timeout, workspace-resolution, comparison, and readback primitives. No generic raw settings writer.

**Tech Stack:** Existing FastMCP, Pydantic, QLab OSC client, pytest, and current packaging tooling.

## Global Constraints

- Do not implement any other Workspace Settings write.
- Do not add raw OSC, raw AppleScript, `/live`, GO, playback, panic, or generic path/value arguments.
- Require exact workspace UUID input.
- Preserve read-only-by-default behavior.
- Preserve `dry_run → fresh token → one setter → fresh readback`.
- Never retry a mutating setter after timeout or reply uncertainty.
- Do not bump the package version during implementation.
- Do not create a feature branch until authoritative `main` is verified.
- Do not perform repository-wide cleanup.

# Goal

Add one safe vertical slice:

```text
qlab_edit_general_settings(
    workspace_id,
    operation="minGoTime",
    value,
    dry_run=None,
    confirm_token=None,
)
```

It supports exact workspace UUID targeting, operation `minGoTime`, finite non-negative seconds, dry-run planning, a fresh confirmation token, one exact OSC setter, fresh no-argument readback, and typed success/timeout/failure/inconclusive results.

# Non-goals

Do not implement `selectionIsPlayhead`, Controls, Audition, Collaboration, Templates, Audio, Video, Light, Network, MIDI, batch settings writes, generic settings paths, automatic rollback, `/live`, raw OSC, AppleScript fallback, GO, playback, panic, version publication, or runtime QLab mutation.

# Baseline

Implementation starts from verified `main` at `f94de272a2e29a7cb52e542f62de1e0e0a9e2204`, version `0.3.0`, with exactly 13 tools and no `qlab_update_cues`. The feature branch must have no feature commits before implementation.

# Research Decisions Adopted

- Use only `/workspace/{canonical_workspace_uuid}/settings/general/minGoTime`.
- Read with no argument and write one numeric argument.
- Use OSC only; no AppleScript fallback.
- Keep settings writes separate from cue-edit operations.
- Reuse existing readiness, token, timeout, comparison, and fresh-readback conventions.
- Treat implementation, runtime validation, and GO readiness as separate evidence levels.

# Public Contract

```python
qlab_edit_general_settings(
    workspace_id: UUID,
    operation: Literal["minGoTime"],
    value: NonNegativeFiniteNumber,
    dry_run: bool | None = None,
    confirm_token: str | None = None,
) -> GeneralSettingsEditResult
```

No `path`, `updates`, arbitrary operation, or generic value map. Reject booleans, strings, null, NaN, infinities, negatives, and values not representable by the repository's actual OSC numeric encoder. Do not invent a QLab-specific maximum.

Use annotations `readOnlyHint=False`, `destructiveHint=True`, `idempotentHint=False`, `openWorldHint=True` and tags `qlab`, `settings`, `general-settings`, `write-mode`, `gated-write`.

Create a dedicated typed result with fields for `ok`, status, workspace, operation, dry-run, requested value, baseline, readback, planned/executed operations, token, readiness, activity, verification, timeout confirmation, retry safety, errors, warnings, error code, suggested action, and message. Use existing project status vocabulary where semantically correct: `dry_run`, `dry_run_preflight_failed`, `updated`, `updated_with_confirmed_timeouts`, `preflight_failed`, `verification_failed`, and `verification_inconclusive`.

# Internal Architecture

Create `src/qlab_mcp/settings/write_registry.py` with exactly one typed entry for `minGoTime`, including its fixed OSC/readback path, numeric validator, Tier 2 risk, saved mode, activity policy, real-write flag, and `workspace-settings-v1` registry version.

Create `src/qlab_mcp/settings/write_operations.py` with a `WorkspaceSettingsWriteMixin.edit_general_settings` method. Compose it into `QLabReader` beside the settings reader. Resolve the exact UUID, run readiness, read fresh baseline/activity, issue a settings-specific token in dry-run, revalidate all state in real mode, consume the token immediately before one setter, then perform a fresh uncached readback.

If no shared numeric comparison helper exists, extract the existing cue comparison policy into `src/qlab_mcp/write/comparison.py` and update cue code to import it unchanged; do not add a generic settings framework.

# Safety Model

- Dry-run establishes readiness, exact workspace, fresh baseline, requested value, planned operation, activity snapshot, and fresh token; failures produce no token and no setter.
- Real execution repeats readiness, exact UUID, fresh baseline, and activity checks.
- Require zero running/paused cues before token issuance and again before mutation as a conservative MCP policy; do not claim this proves Audition is disabled.
- The registry is the only source of the setter path.
- The real path makes exactly one mutating request, with no fallback, retry, rollback, or hidden setter.

# Token and TOCTOU Model

Use a new HMAC-authenticated, process-bound, expiring, single-use family `confirm:workspaceSettings:v1:` with a 300-second TTL. Bind canonical workspace UUID, operation, canonical baseline, canonical requested value, registry version, and expiry. Reject missing, malformed, expired, wrong-family/version, wrong-workspace, wrong-operation, wrong-value, stale-baseline, and replayed tokens. Consume only immediately before mutation.

# Timeout / Convergence Model

Attempt the setter once. After every attempt, perform a fresh no-argument readback. Reuse bounded read-only convergence helpers where appropriate. Matching readback after a normal response is `updated`; matching readback after timeout is `updated_with_confirmed_timeouts`; mismatch is `verification_failed`; unavailable/nonconvergent readback is `verification_inconclusive` with `retry_unsafe=True`. Never retry the setter.

# Result Semantics

Successful dry-run has one planned operation, zero executed operations, and a fresh token. Real results report exactly one attempted setter when mutation was reached. Never imply rollback, atomicity, GO readiness, or complete Audition safety.

# TDD Task Sequence

1. Verify authoritative baseline and preserve local research.
2. Add failing tests for strict input and typed result schema; implement the minimum models and validators.
3. Add failing tests for numeric comparison/transport behavior; reuse or minimally extract the existing comparison policy.
4. Add failing registry/address tests; implement the one-entry registry and exact qualified path.
5. Add failing dry-run/readiness/activity/token tests; implement the settings token family and preflight.
6. Add failing execution/readback tests; implement fresh TOCTOU checks, one setter, and readback mapping.
7. Add failing timeout/replay/stale-state tests; implement bounded read convergence without mutating retry.
8. Register the FastMCP tool and update contract tests from 13 to 14 tools.
9. Run focused tests, full suite, lock, inspection, packaging, and `git diff --check`.
10. Run Task X bounded cleanup only after all feature tests are green.

For each behavioral task: write the RED test first, run it and verify the expected failure, implement the smallest behavior, then run focused tests until GREEN.

# Task X — bounded cleanup / refactor

After feature behavior and focused/full tests are GREEN, review only feature-introduced or directly touched code. Remove duplicated validation/address construction, dead imports/helpers, unnecessary wrappers, repeated safe token/result boilerplate, and accidental settings-to-cue coupling. Improve names or module boundaries only where clearly justified.

Do not perform repository-wide cleanup, unrelated P2/P3 fixes, or abstraction that increases complexity. After each meaningful cleanup, run the smallest relevant focused suite. Finish with full `pytest` and `git diff --check`. Preserve schemas, output models, token family/version/payload, statuses, annotations, tool count, and the one-setter invariant.

# File-by-File Change Plan

Expected new files: `src/qlab_mcp/settings/write_registry.py`, `src/qlab_mcp/settings/write_operations.py`, and `tests/test_workspace_settings_write.py`. Create `src/qlab_mcp/write/comparison.py` only if required to remove direct coupling. Modify only directly relevant models, reader composition, server registration, focused tests, and user/security/architecture documentation. Preserve the research artifact and keep unrelated files out of the diff.

# FastMCP Contract Changes

Register exactly one new public tool, producing 14 tools total while leaving the original 13 unchanged. Expose only the fixed flat schema and typed result. Do not expose raw OSC or AppleScript writes.

# Documentation Changes

Update only directly relevant server instructions, `docs/user/tools.md`, `docs/user/agent-workflows.md`, `SECURITY.md`, and architecture documentation where necessary. Document units, UUID-only targeting, dry-run/token flow, one setter, fresh readback, timeout convergence, unsafe retry prohibition, readiness, conservative activity policy, Audition limitation, and no GO/playback behavior. Do not claim runtime validation or deferred settings as implemented.

# Verification Matrix

Verify baseline and post-change tool counts, exact schema and annotations, strict validation, exact qualified address, readiness, activity, dry-run token, TOCTOU, replay, one setter, fresh readback, timeout convergence, failure semantics, regressions, packaging, documentation, cleanup invariants, full suite, and `git diff --check`.

# Runtime Validation Gate

Do not mutate QLab. Runtime validation is a separately authorized future task using QLab 5.5.10 and a disposable workspace. Keep implementation, runtime validation, and GO readiness distinct.

# Versioning / PR Strategy

Do not bump the package version during implementation. The intended future release is 0.4.0, but do not tag, publish, merge, push, or create a PR.

# Deferred Capabilities

All Workspace Settings writes except `general.minGoTime`, including `selectionIsPlayhead`, remain deferred.

# Risks / Open Questions

Confirm the actual OSC numeric encoding before deciding whether float32 representability is public validation. QLab ACK behavior, float32 readback behavior, and workspace-wide Audition state remain runtime limitations.

# Execution Stop Conditions

Stop if the branch/base contract changes, exact UUID/path cannot be enforced, arbitrary paths appear, a token family collides, more than one setter is possible, a setter retry appears, readback is cached/omitted, tests fail after cleanup, or unrelated scope enters the diff.
