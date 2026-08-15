# QLab MCP — Workspace Settings Write Pre-PR Audit

Audit date: 2026-08-16
Repository: `MarcheKEN/Qlab-MCP`
Branch: `feature/workspace-settings-write`
Version: `0.3.0`

## Executive Verdict

**READY_FOR_DRAFT_PR**

The feature is bounded and the implementation/runtime evidence is coherent.
The initial local `git ls-remote origin refs/heads/main` check was blocked by
DNS resolution for `github.com`; subsequent authoritative GitHub verification
confirmed `main` at `f94de272a2e29a7cb52e542f62de1e0e0a9e2204`. The cached local
ref and merge base match that authoritative SHA.

The two runtime fixes that were previously only in the worktree are now in a
local commit, and the missing one-setter regression assertion is covered.
Nothing was pushed, merged, tagged, published, or mutated in QLab.

## Audited Baseline

- Expected base: `f94de272a2e29a7cb52e542f62de1e0e0a9e2204`.
- Local `main`: expected SHA.
- Cached `origin/main`: expected SHA.
- Authoritative GitHub `refs/heads/main`: expected SHA (subsequently verified).
- Merge base: expected SHA.
- Package version: `0.3.0`.
- Source and clean-cache FastMCP inspection: 14 tools.
- `qlab_edit_general_settings`: present.
- `qlab_update_cues`: absent.

The first audit inspection using the normal uv cache reported the old 13-tool
package. Root-cause investigation showed a stale cached build. Re-running with
an isolated `UV_CACHE_DIR` rebuilt the local package and reported 14 tools and
the current six-write-tool instructions. The stale-cache result is retained as
an environment reproducibility caveat, not treated as a source contract
failure.

## Branch / Commit State

Before audit fixes, `HEAD` was `1633e0b0a910789a94704be65500d6f310707853`, ten
feature commits ahead of the verified base. The audit fixes were committed
locally as `84e59aa` (`Fix workspace settings runtime validation regressions`).
Closure `HEAD` is `54b83d45cf09137b79314505fdba6183dc9f729d`; it descends from
the expected base and the worktree is clean.
The commit contains:

- strict public `StrictInt | StrictFloat` validation;
- case-insensitive UUID identity matching with QLab-canonical casing;
- UUID and strict-input regression coverage;
- exact setter/readback assertions;
- inconclusive-readback one-setter coverage.

The research, implementation-plan, and runtime-validation artifacts are
intended feature evidence and are included with the audit documentation. The
four `.superpowers/sdd` reports are retained as process evidence and are listed
explicitly rather than treated as production code.

## Scope Review

The public feature exposes only `general.minGoTime`. No other Workspace
Settings operation, generic path/value map, batch settings write, `/live`
route, raw OSC, AppleScript fallback, GO, playback, panic, or unrelated QLab
operation is reachable.

## Public FastMCP Contract

The source registry and clean-cache inspection expose exactly 14 tools. The
new tool has the flat fields `workspace_id`, `operation`, `value`, `dry_run`,
and `confirm_token`; UUID targeting; the single literal operation
`minGoTime`; and a finite non-negative numeric value. No arbitrary path,
address, update map, or generic operation field exists.

The output is `GeneralSettingsEditResult` with the documented statuses and
fields. Annotations are `readOnlyHint=False`, `destructiveHint=True`,
`idempotentHint=False`, and `openWorldHint=True`. Tags are exactly:
`qlab`, `settings`, `general-settings`, `write-mode`, and `gated-write`.

## Architecture Review

Workspace Settings writes use the dedicated `settings/write_registry.py` and
`settings/write_operations.py` boundary. The registry contains one frozen
allowlist entry. `QLabReader` composes the settings writer separately from cue
write operations. The shared numeric comparison helper is used without
reintroducing settings-to-cue coupling.

## QLab OSC Review

The only setter route is the exact qualified address:

`/workspace/{canonical_uuid}/settings/general/minGoTime`

The setter sends one numeric argument. Readback uses the same address with no
argument. The route is registry-derived and excludes `/live`, `+`, `-`,
unqualified, display-name, raw-OSC, and AppleScript paths. Integer and float
wire types remain distinct and are checked against OSC int32/float32 limits.

## UUID Identity Review

Input is a canonical hyphenated UUID. Matching is case-insensitive against
QLab's returned `uniqueID`, while the returned QLab casing is preserved in the
address, result, and token payload. Display names, implicit targets, selected
workspaces, and ambiguous matches fail closed.

## Numeric Validation Review

Booleans, strings, null, NaN, infinities, negatives, int32 overflow, and
float32 overflow are rejected before transport. Public FastMCP validation now
uses strict integer/float types; direct model validation preserves the numeric
wire type and float32 representation checks.

## Token Security

Settings tokens use the isolated `confirm:workspaceSettings:v1:` family, a
process-specific HMAC secret, a 300-second expiry, and a consumed-token lock.
Bindings include canonical workspace UUID, operation, canonical float32
baseline, canonical float32 requested value, requested input/wire type, and
registry version. Consumed real-write tokens are not returned.

## TOCTOU

Real execution rechecks readiness, workspace identity, baseline, and activity
before token consumption and mutation. Changed baseline, requested value,
workspace, expiry, malformed signature, wrong family/version, and replay fail
closed before a setter. Runtime evidence covers two stale-baseline cycles and
replay.

## Activity Safety

The gate requires zero running or paused cues and rejects explicitly identified
auditioning cues. Workspace-wide Audition state is not exposed by the current
reader, so the implementation documents that limitation. A positive activity
runtime injection was skipped because no safe MCP-only method exists without
GO/playback/show impact; automated coverage remains authoritative.

## Setter / Timeout Safety

The real path has one mutating transport call and no retry, rollback, or
fallback. It clears the relevant cache and performs fresh read-only
convergence. Matching readback after a timeout maps to
`updated_with_confirmed_timeouts`; mismatch maps to `verification_failed`;
unavailable/nonconvergent readback maps to `verification_inconclusive` with
`retry_unsafe=true`.

## Automated Test Evidence

- Focused feature/write/token/server tests after audit hardening: `2318 passed`.
- Full suite with loopback access: `2649 passed, 41 subtests passed`.
- Initial sandbox full-suite attempt failed only because UDP/TCP fixtures could
  not bind localhost (`PermissionError: [Errno 1] Operation not permitted`).
- `uv lock --check`: passed.
- Packaging tests: `2 passed`.
- `uv build`: wheel and sdist for `0.3.0` built successfully.
- `git diff --check`: passed.

The audit added exact qualified setter/readback assertions, public invalid
input coverage, and an explicit one-setter assertion for inconclusive
readback.

## Runtime Evidence

The existing QLab 5.5.10 report records both campaigns against disposable
workspace `mcp_prueba.qlab5`, UUID
`95F0A03D-140E-4673-974A-E76748EBB023`. It records the 14-tool contract,
strict UUID behavior, strict invalid-input rejection, dry-run/token flow, one
setter per real write, timeout-confirmed fresh readback, replay rejection,
TOCTOU rejection, sequential values, same-value behavior, and final
restoration to `general.minGoTime=0` with sampled activity `0` running / `0`
paused.

No additional runtime mutation was performed during this audit. Positive
activity injection, synthetic timeout, and forced expiry were intentionally
skipped for safety; the report distinguishes implementation evidence, runtime
validation, and GO readiness.

## Documentation Review

README, user tools/workflow docs, security guidance, and architecture docs
describe the UUID-only `minGoTime` write, readiness gates, token flow, one
setter, fresh readback, timeout/no-retry behavior, Audition limitation, and
the implementation/runtime/GO-readiness boundary. Dated status documents that
say 0.3.0/13 tools are historical records and were not rewritten.

## Versioning Recommendation

Keep version `0.3.0` for this feature branch. Prepare any `0.4.0` release
metadata separately after Draft PR review and authorization.

## Git / Commit Review

The feature branch is based on the expected main SHA and has no merge or rebase
of main. The audit created only local commits. The earlier local DNS failure is
preserved in this report; it was superseded by the subsequent authoritative
GitHub ref verification.

## Secrets / Repository Hygiene

The audit found no API keys, passcodes, private keys, credentials, QLab files,
media, or build artifacts in the feature diff. Environment passcode examples
are placeholders/documentation, and the runtime UUID is explicitly documented
test evidence rather than a secret.

## P0 Findings

None.

## P1 Findings

None. The remote-baseline P1 is resolved by the subsequent authoritative
GitHub verification. The optional local retry remained DNS-blocked, which does
not contradict the independently verified authoritative ref.

## P2 Findings

- Workspace resolution uses the existing ten-second read cache during the
  second real-execution identity check. The fully qualified setter and token
  bindings prevent redirection, but strict freshness is weaker than a fresh
  uncached workspace listing.
- Registry metadata is immutable and correct but is not redundantly asserted
  at each execution call.
- Historical status pages still mention the dated 13-tool release baseline.
- `.superpowers/sdd` reports are process artifacts outside the normal feature
  file list; they are retained and explicitly identified rather than silently
  deleted.
- Positive activity, synthetic timeout, and forced-expiry runtime cases remain
  safely skipped and are covered by automated tests.

## P3 Findings

- `edit_general_settings` remains a long but cohesive method; no speculative
  refactor was justified.
- Existing family-local numeric helpers outside the feature boundary were not
  touched.
- Existing feature commits use the local machine author identity; no history
  rewrite was needed for correctness.

## Changes Made During Audit

- Committed the strict public numeric validation fix.
- Committed case-insensitive UUID matching with canonical QLab casing.
- Added/strengthened direct and public regression tests.
- Added this durable audit report.
- Preserved the research, implementation-plan, runtime-validation, and
  process-evidence artifacts.

## Deferred Items

- No additional Workspace Settings writes.
- No cache architecture change without evidence of an actual identity
  redirect.
- No runtime activity injection, synthetic timeout, or GO/show validation.
- No version bump, push, PR, merge, tag, release, or publish.

## Draft PR Readiness

`READY_FOR_DRAFT_PR`. All local implementation, contract, test, packaging,
runtime-report, hygiene, and authoritative-base gates are documented.

## Next Gate

Await user authorization to push `feature/workspace-settings-write` and create
a Draft PR against `main`. No merge authorization exists.
