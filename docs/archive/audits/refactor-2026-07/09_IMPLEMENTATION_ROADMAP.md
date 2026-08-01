# 09 — Implementation Roadmap

## Phase A — Correctness blockers

### A1. Late identical UDP reply isolation

- **Priority:** P0 — Confirmed correctness blocker
- **Problem/evidence:** a scheduled loopback probe made a second `/version` request return the first timed-out request's payload; matching is sender/address only in `osc/client.py`.
- **Affected modules:** `osc/client.py`, transport tests, safety-critical fresh-read callers.
- **Approach:** add the failing regression first; isolate post-timeout same-address traffic using the smallest proven design, with TCP considered for safety-critical fresh reads.
- **Benefit:** prevents stale data being treated as current setter readback.
- **Dependencies:** none.
- **Complexity:** Medium.
- **Automated tests:** late/duplicate reply, timeout→same/different address, unrelated datagrams, no setter retry.
- **QLab checks:** repeated identical read after induced timeout if safely reproducible; no mutation required.
- **Tradeoffs:** TCP or quarantine can add latency; correctness wins.

### A2. Deterministic release contents and single version

- **Priority:** P0 — Release correctness/data-leak blocker
- **Problem/evidence:** sdist included local ignored/untracked `.codex/` and review material; pyproject/artifacts are 0.2.0 while module/lock are 0.1.0; lock check fails.
- **Affected modules:** `pyproject.toml`, `uv.lock`, `__init__.py`, build/CI config.
- **Approach:** choose one version source, refresh lock, explicit Hatch sdist/wheel includes, clean-temporary-checkout build smoke.
- **Benefit:** reproducible, non-leaking install artifacts.
- **Dependencies:** release-version decision.
- **Complexity:** Small.
- **Automated tests:** build, member allowlist, install/import/version, `uv lock --check`.
- **QLab checks:** none.
- **Tradeoffs:** explicit include list must be updated when legitimate package assets change.

## Phase B — Runtime reliability and protocol contract

### B1. Custom UDP reply port and 61-second authentication

- **Priority:** P1 — Runtime reliability
- **Problem/evidence:** configured reply port is never announced via `/udpReplyPort`; UDP connected state has no expiry/keepalive/reconnect despite documented 61-second forgetting.
- **Affected modules:** `config.py`, `osc/client.py`.
- **Approach:** announce non-default reply port; expire/re-auth or reconnect on denial. Add keepalive only if a real long-lived client needs it.
- **Benefit:** documented configuration and long operations work reliably.
- **Dependencies:** A1 transport tests.
- **Complexity:** Medium.
- **Automated tests:** custom port, fake-clock auth expiry, denial reconnect, per-workspace state, TCP unaffected.
- **QLab checks:** real non-default reply port and >61-second idle read.
- **Tradeoffs:** slightly more auth traffic.

### B2. Generation-safe cache invalidation

- **Priority:** P1 — Runtime reliability
- **Problem/evidence:** an in-flight owner stores stale data after `ReadCache.clear()`; reproduced locally.
- **Affected modules:** `runtime/read_cache.py`.
- **Approach:** generation counter plus store-if-current; opportunistic expiry pruning and bounded waits.
- **Benefit:** fresh post-write reads stay fresh; state cannot grow indefinitely.
- **Dependencies:** none.
- **Complexity:** Small.
- **Automated tests:** clear race, exception wakeup, different keys, expiry, two-workspace namespaces.
- **QLab checks:** optional read→write→concurrent-read integration after approval.
- **Tradeoffs:** an invalidated in-flight result is returned to its original caller but not cached; document this.

### B3. Cooperative end-to-end deadlines

- **Priority:** P1 — Runtime reliability
- **Problem/evidence:** FastMCP timeout on a sync handler did not preempt 200 ms work at a 50 ms limit; broad reads can outlive clients.
- **Affected modules:** server handlers, cue scans/details/settings fallback, `write/timeouts.py`.
- **Approach:** one monotonic budget propagated before starting further OSC calls; explicit partial/timed-out results.
- **Benefit:** predictable resource use and cancellation behavior.
- **Dependencies:** result-contract decision in E2.
- **Complexity:** Medium.
- **Automated tests:** budget exhaustion at every loop/fallback, disconnect/cancel, no late setter start.
- **QLab checks:** bounded large read; no mutation.
- **Tradeoffs:** partial-result semantics become public contract.

### B4. Protocol-faithful UDP/TCP contract suite

- **Priority:** P1 — Runtime reliability
- **Problem/evidence:** current fake is immediate/sequential; TCP core is mocked; late/duplicate/out-of-order cases absent.
- **Affected modules:** `tests/transport`, OSC client/message modules.
- **Approach:** small scheduled UDP server and real loopback TCP/SLIP server with deterministic fake clock where possible.
- **Benefit:** prevents regressions at the highest-risk boundary.
- **Dependencies:** A1/B1 designs.
- **Complexity:** Medium.
- **Automated tests:** fragmentation, several frames, malformed data, sender mismatch, duplicate/late/out-of-order replies, close/reset.
- **QLab checks:** read-only smoke only.
- **Tradeoffs:** loopback tests need unsandboxed/CI socket permission.

## Phase C — Simplify while preserving behavior

### C1. Shared signed-token envelope codec

- **Priority:** P2 — Maintainability
- **Problem/evidence:** 24 repeated codec helpers, approximately 400 production lines.
- **Affected modules:** `write/operations.py`, `moves.py`, `deletes.py`, `groups.py`.
- **Approach:** one internal canonical JSON/base64/HMAC/version codec; family payload/binding/expiry/consumption stays local.
- **Benefit:** one auditable primitive and smaller change surface.
- **Dependencies:** green full suite and security test inventory.
- **Complexity:** Medium.
- **Automated tests:** fixed vectors, tamper/version errors, every existing family binding/reuse test.
- **QLab checks:** none; behavior-preserving refactor.
- **Tradeoffs:** simultaneous migration increases risk; move one family at a time.

### C2. Extract one ordered edit-family handler

- **Priority:** P2 — Maintainability
- **Problem/evidence:** `operations.py` is 12,063 lines; router and phase hooks repeat detect/annotate/validate/execute/readback shapes.
- **Affected modules:** `write/operations.py`, one new/existing family module, registry/tests.
- **Approach:** choose one cohesive proven family; explicit ordered handler tuple; keep batch orchestration and safety ordering unchanged. Repeat only after measured improvement.
- **Benefit:** lowers feature-edit fan-out; expected ~350 lines across later extractions.
- **Dependencies:** C1 optional but helpful; B reliability complete.
- **Complexity:** Large incrementally.
- **Automated tests:** unchanged schema, dry-run/gates, all-preflight, setter once, timeout/readback/rollback, route ownership.
- **QLab checks:** one dedicated safe saved-property proof and rollback.
- **Tradeoffs:** wrong ordering can weaken safety; golden order tests mandatory.

### C3. Registry-derived route membership and exact constants

- **Priority:** P2 — Maintainability
- **Problem/evidence:** 32 phase constants overlap ~100 registry property names; container/continue constants and workspace resolvers duplicate.
- **Affected modules:** registry, operations, moves/deletes, connection/status.
- **Approach:** derive only static membership sets from registry metadata; share exact duplicate constants/resolver; leave tiny local helpers alone.
- **Benefit:** fewer coordinated edits and 75–120 lines removed.
- **Dependencies:** C2 establishes handler ownership.
- **Complexity:** Medium.
- **Automated tests:** manifest membership, no duplicate owner, resolver/container/continue contracts.
- **QLab checks:** read-only workspace/cue targeting smoke.
- **Tradeoffs:** registry becomes more important; keep data explicit and validated.

## Phase D — High-value QLab workflows

### D1. Current-version capability manifest

- **Priority:** P3 — High-value QLab foundation
- **Problem/evidence:** local dictionary provenance missing; green tests miss official 5.6 `/pathSmooth` and `/pathLoop`; docs ledgers conflict.
- **Affected modules:** reference docs, OSC inventory, registry, generated capability docs/resource.
- **Approach:** record URL/version/date/checksum; structured manifest combines implemented/read/write/planned/runtime-proof status; deterministic generation.
- **Benefit:** release drift is visible and clients/operators get one truth source.
- **Dependencies:** supported QLab-version policy.
- **Complexity:** Medium.
- **Automated tests:** manifest schema, snapshot diff, generated files exact, registry ownership.
- **QLab checks:** representative reads/writes on declared supported versions.
- **Tradeoffs:** official updates require deliberate snapshot refresh.

### D2. Exact-placement blank cue creation

- **Priority:** P3 — Operator workflow
- **Problem/evidence:** `after_cue_id` is planned-only for real creation, limiting safe authoring workflows.
- **Affected modules:** create planner/executor, structure resolution/readback.
- **Approach:** exact UUID destination, dry-run structural snapshot, one create then one placement, convergence verification and cleanup guidance; keep cue types narrow.
- **Benefit:** usable fixture/placeholder authoring without broad write expansion.
- **Dependencies:** A/B reliability, reversible integration fixture.
- **Complexity:** Medium.
- **Automated tests:** destination drift, creation success/timeout, placement failure reporting, orphan handling, exact final structure.
- **QLab checks:** create dedicated Memo, verify placement, delete only with explicit approved cleanup.
- **Tradeoffs:** create+move is non-atomic; report orphan/partial state honestly.

### D3. Productize pre-show audit and cue-list cleanup

- **Priority:** P3 — Operator workflow
- **Problem/evidence:** primitives exist but operator guidance/output composition is scattered.
- **Affected modules:** primarily docs/tool guidance; possibly one result composition path, not new public tools unless proven necessary.
- **Approach:** documented recipes using connection→overview→status/settings→query/details→dry-run edits/moves. Define compact cut-list outputs and exact-target safeguards.
- **Benefit:** immediate theatre value from mature read surface.
- **Dependencies:** D1 and operator guide.
- **Complexity:** Small/Medium.
- **Automated tests:** recipe contract fixtures, bounded output, error guidance.
- **QLab checks:** read-only full audit on representative workspace; safe Memo metadata edit when approved.
- **Tradeoffs:** keep recipes compositional to avoid an oversized “do everything” tool.

### D4. Small Audio/Mic saved-basics tranche

- **Priority:** P3 — Operator workflow
- **Problem/evidence:** practical prep workflows need selected basics, while broad media/output support is unsafe and expensive.
- **Affected modules:** registry, existing edit family, docs/tests.
- **Approach:** select properties from named operator cases; saved values only; dry-run, exact UUID, fresh readback, no playback/live/output.
- **Benefit:** useful show preparation without turning MCP into a show controller.
- **Dependencies:** D1, C2, reversible fixture.
- **Complexity:** Medium.
- **Automated tests:** type/range/enum, raw address/args, gate/readback/rollback.
- **QLab checks:** disabled/inactive dedicated fixtures, one property at a time, restore in `finally`.
- **Tradeoffs:** resist property-count scope creep.

## Phase E — Tests, documentation and developer experience

### E1. Reversible real-QLab integration harness

- **Priority:** P4 — Verification
- **Problem/evidence:** no opt-in end-to-end fixture; current review's dry-run was approval-blocked.
- **Affected modules:** `tests/integration`, operator/developer docs.
- **Approach:** explicit env marker/workspace/cue UUID; preflight readiness; capture baseline; one change; fresh readback; `finally` rollback and final assertion; output overrides required.
- **Benefit:** converts safety claims into current runtime evidence.
- **Dependencies:** user approval and dedicated workspace fixture.
- **Complexity:** Medium.
- **Automated tests:** harness failure paths with fake tool; opt-in QLab marker excluded by default.
- **QLab checks:** the harness itself.
- **Tradeoffs:** cannot be ordinary CI; human/environment coordination remains.

### E2. Stable schemas, errors and MCP annotations

- **Priority:** P4 — Client/developer experience
- **Problem/evidence:** cue-details union envelope, broad string/range schemas, two error paths, unbounded settings requests, Edit/Move marked non-destructive.
- **Affected modules:** `server.py`, `models.py`, response helpers, contract tests/docs.
- **Approach:** one top-level result shape, constrained stable fields, explicit empty semantics, bounded batches, correct annotations; announce compatibility impact.
- **Benefit:** simpler generated clients and earlier useful errors.
- **Dependencies:** version policy.
- **Complexity:** Medium.
- **Automated tests:** readable per-tool schema assertions, old payload fixtures, all error/annotation cases.
- **QLab checks:** invalid/read-only smoke; one approved write dry-run.
- **Tradeoffs:** schema changes may require a minor-version compatibility window.

### E3. Fast, isolated test suite and CI

- **Priority:** P4 — Developer experience
- **Problem/evidence:** one permanent skip, eight real-sleep tests dominate runtime, global-state cleanup is local, no CI/lint/type/coverage policy.
- **Affected modules:** tests, `pyproject.toml`, CI workflow.
- **Approach:** remove/fill skip, fake clock, autouse global isolation, three markers, CI full suite + build/lock/diff. Add lint/type only with an agreed baseline, not as churn.
- **Benefit:** faster trustworthy feedback and release gate.
- **Dependencies:** B4 test layer.
- **Complexity:** Medium.
- **Automated tests:** self-referential full suite, random-order trial, build/install.
- **QLab checks:** integration marker stays opt-in.
- **Tradeoffs:** introducing quality tools can create cleanup scope; phase them.

### E4. Operator/developer documentation baseline

- **Priority:** P4 — Documentation/DX
- **Problem/evidence:** missing runbook and project policies; roadmap/workorders/coverage/architecture drift; QClass index weak.
- **Affected modules:** README/docs, generated tables, release files.
- **Approach:** installation/config UI fields, supported versions, pre-show audit, safe write/rollback, troubleshooting; add LICENSE/CHANGELOG/CONTRIBUTING/SECURITY and update architecture/tool graph from source.
- **Benefit:** lower operator error and contributor friction.
- **Dependencies:** D1/E2 contracts.
- **Complexity:** Medium.
- **Automated tests:** link/generated-doc checks, generic examples/no secrets, public tool-name consistency.
- **QLab checks:** run every documented recipe on test workspace.
- **Tradeoffs:** prose still needs release ownership; generated tables reduce but do not eliminate drift.

## Deferred backlog

Persistent update subscriptions, raw OSC, playback/panic, selected/active writes, broad `/live`, relative setters, Light/MIDI/Network output, patch/stage/warping mutation, unrestricted Script/file paths and MIDI File expansion remain outside this milestone until a concrete operator workflow and safe integration strategy justify them.
