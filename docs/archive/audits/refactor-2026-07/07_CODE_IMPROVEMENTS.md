# 07 — Code Improvements

## Verdict

The highest-value work is correctness at the OSC/cache boundary, then deletion of repeated write-family machinery. The project does not need a new framework, dependency, service layer or wholesale rewrite. A conservative simplification can remove roughly 875 non-overlapping lines while preserving schemas and safety behavior.

## Ranked opportunities

### 1. Prevent late identical UDP reply misattribution

- **Affected files:** `src/qlab_mcp/osc/client.py`, `tests/test_osc.py` or new transport suite.
- **Current design:** new fixed-port UDP socket per serialized request; correlation by sender IP and invoked address.
- **Observed difficulty/evidence:** reproduced request 2 receiving request 1 payload after request 1 timed out; `05_RUNTIME_BEHAVIOR.md`.
- **Recommended design:** first land the scheduled-reply regression. Prefer TCP for operations where post-timeout freshness is safety-critical, or implement a bounded UDP quarantine/drain design proven by the regression. Do not remove serialization as a “fix.”
- **Benefit/drawback/complexity:** removes a P0 stale-read correctness risk; may add latency or transport selection logic; **Medium**.
- **Required tests:** late/duplicate same address, unrelated addresses, timeout then retry, setter-timeout readback; real QLab smoke.

### 2. Fix UDP reply-port and idle authentication lifecycle

- **Affected files:** `config.py`, `osc/client.py`, transport tests.
- **Current design:** configurable reply port is bound locally without `/udpReplyPort`; connected workspaces never expire inside a client.
- **Evidence:** official dictionary requirements; no `/udpReplyPort`, `/forgetMeNot`, `/udpKeepAlive`, `/disconnect` or reconnect-on-denial in source.
- **Recommended design:** send `/udpReplyPort` when non-default, and either expire UDP auth before 61 seconds/reconnect on denial or use a scoped keepalive only for genuinely long operations. Avoid a background manager.
- **Benefit/drawback/complexity:** makes documented configuration and long calls reliable; adds a small protocol state machine; **Medium**.
- **Required tests:** custom port, fake clock at 60/61+ seconds, denial reconnect, TCP unaffected; real custom-port/idle check.

### 3. Make cache invalidation generation-safe and bounded

- **Affected files:** `runtime/read_cache.py`, reader tests.
- **Current design:** process-global TTL/single-flight cache; active factory stores after `clear()`; expired unique keys persist.
- **Evidence:** reproduced clear-during-flight returned `post_clear_value=stale`; source only evicts on matching-key access.
- **Recommended design:** add one generation integer; owners store only if their captured generation matches. Opportunistically prune expired entries on access and cap waiter duration.
- **Benefit/drawback/complexity:** prevents post-write stale reappearance and long-process growth; a few synchronization branches; **Small**.
- **Required tests:** clear race, factory error/waiters, different keys, fake-clock expiry, namespace separation.

### 4. Share one signed-token codec

- **Affected files:** `write/operations.py`, `moves.py`, `deletes.py`, `groups.py`, new small `write/tokens.py` only if needed.
- **Current design:** 24 encode/decode variants repeat JSON canonicalization, URL-safe base64, HMAC signature/version/error mechanics.
- **Evidence:** AST/search found roughly 400 production lines of codec repetition.
- **Recommended design:** one internal codec for envelope/signature/version; each operation family retains its payload schema, binding, expiry, consumption and semantic validation.
- **Benefit/drawback/complexity:** ~400 lines removed, one audited security primitive; migration is security-sensitive; **Medium**.
- **Required tests:** all existing tamper/binding/expiry/reuse tests unchanged plus codec vectors per family.

### 5. Replace repeated edit-family hook chains with ordered data

- **Affected files:** mainly `write/operations.py`, registry and write tests.
- **Current design:** `update_cues()` and many helpers repeatedly detect, annotate, validate, mark, reject, refresh and execute Phase 3/7/8/9 families.
- **Evidence:** 12,063-line file, 409 functions, `update_cues()` over 2,000 lines; similarity scans found repeated hook shapes.
- **Recommended design:** extract **one coherent family at a time** behind an explicit ordered tuple of plain internal handlers. Each handler owns match/plan/validate/execute/readback for that family; keep batch orchestration and safety order centralized. No discovery, plugin manager or factories.
- **Benefit/drawback/complexity:** estimated ~350 additional lines removed and safer incremental feature work; ordering is safety-critical; **Large incrementally**.
- **Required tests:** golden plan order, all-batch preflight, setter once, readback/rollback, token gates, unchanged public schemas; one family per PR.

### 6. Make the registry the source for route membership

- **Affected files:** `write/registry.py`, `write/operations.py`, coverage tests/docs.
- **Current design:** 32 phase/property constants overlap about 100 names already in registry specs.
- **Evidence:** AST registry-overlap scan and repeated constants such as Video Phase 3/7 and Text Phase 3E/3F.
- **Recommended design:** add small static metadata fields to existing specs and derive membership sets once. Do not make registry execution dynamic.
- **Benefit/drawback/complexity:** 50–80 lines removed and fewer feature edits; malformed metadata could affect routing; **Medium** after one family extraction.
- **Required tests:** exact derived membership snapshots, registry-to-handler completeness, no duplicate route owner.

### 7. Consolidate exact duplicate helpers only

- **Affected files:** `moves.py`, `deletes.py`, `cues/overview.py`, `cues/refs.py`, connection/status resolution.
- **Current design:** duplicate container cue sets and continue-mode values; strict workspace resolution repeated across facades.
- **Evidence:** identical definitions/search results; architecture map.
- **Recommended design:** share canonical container/continue constants and reuse the strict resolver. Leave two-line `_chunk_keys` helpers local because abstraction cost exceeds benefit.
- **Benefit/drawback/complexity:** ~25–40 lines and clearer ownership; low risk; **Small**.
- **Required tests:** target resolution, List/Group/Cart validation, existing read/write suites.

### 8. Enforce cooperative operation deadlines

- **Affected files:** `server.py`, broad read paths, `write/timeouts.py`.
- **Current design:** FastMCP decorator timeouts wrap synchronous worker threads and do not stop work; some write operations have internal budgets, reads do not consistently.
- **Evidence:** 50 ms decorator probe returned after a 200 ms synchronous sleep.
- **Recommended design:** pass a monotonic deadline/budget through high-round-trip reads and check it before new OSC calls. Treat decorator timeout as metadata, not a safety primitive.
- **Benefit/drawback/complexity:** predictable client behavior and less orphan work; partial results need explicit semantics; **Medium**.
- **Required tests:** cancellation/disconnect, budget exhaustion in cue scans/fallbacks, no setter after budget expiry.

### 9. Pin one QLab capability/reference manifest

- **Affected files:** `docs/references`, `write/osc_inventory.py`, registry, coverage/docs generators.
- **Current design:** local dictionary is parsed at runtime/tests but unversioned; multiple docs ledgers separately state support.
- **Evidence:** official 5.6.2 has `/pathSmooth` and `/pathLoop`, absent locally while coverage is green.
- **Recommended design:** store source URL, QLab version, retrieval date and checksum; generate the capability matrix/docs rows from one structured manifest plus runtime-proof status.
- **Benefit/drawback/complexity:** makes release drift visible and reduces documentation edits; generator becomes a small maintained tool; **Medium**.
- **Required tests:** manifest schema, official-snapshot diff, generated-file exactness, installed-wheel behavior.

### 10. Fix public schema/error/annotation consistency

- **Affected files:** `server.py`, `models.py`, `server_responses.py`, server tests.
- **Current design:** broad strings/ranges, two error paths, cue-details union envelope, Edit/Move marked non-destructive, unbounded settings request list.
- **Evidence:** exported schemas and live missing-field/empty-profile probes.
- **Recommended design:** constrained fields for stable enums/ranges, one result envelope, bounded list, separate MCP annotations, explicit empty-string semantics.
- **Benefit/drawback/complexity:** easier client generation and fewer slow invalid calls; potential compatibility change needs versioning; **Medium**.
- **Required tests:** human-readable schemas, old-client fixtures, all error classes, FastMCP structured output.

### 11. Make packaging deterministic and versions singular

- **Affected files:** `pyproject.toml`, `uv.lock`, `src/qlab_mcp/__init__.py`, Hatch include/exclude config.
- **Current design:** project says 0.2.0, module/lock say 0.1.0; default sdist includes ignored/untracked local folders.
- **Evidence:** artifact listing and `uv lock --check` failure.
- **Recommended design:** one version source, refresh lock, explicit sdist include list (`src`, required README/license metadata only), build in a clean temporary checkout in CI.
- **Benefit/drawback/complexity:** prevents release confusion/data leakage; no runtime downside; **Small**.
- **Required tests:** build wheel/sdist, inspect members, install/import/version smoke, lock check.

### 12. Reduce test duration and duplication without weakening safety

- **Affected files:** `tests/test_write_mode.py`, reader/transport tests.
- **Current design:** real sleeps and copy-shaped token/timeout families; one giant fake.
- **Evidence:** eight tests use ~64% of suite time; 16,862-line test file.
- **Recommended design:** fake clock for retry delays; parameterize only shared token mechanics/timeout contracts while retaining cue-family semantic cases. Add scheduled packet-level fakes.
- **Benefit/drawback/complexity:** faster, clearer failures; over-parameterization can hide domain context; **Medium**.
- **Required tests:** suite must retain all setter-once/gate/readback assertions; compare collected semantic cases before/after.

## Change difficulty today

| Change | Current difficulty | Why |
| --- | --- | --- |
| Add MCP tool | Low/medium | Thin handler/model/docs/tests, but schema snapshot and metadata must align |
| Add ordinary property | Medium | Registry plus allowlist/readback/tests/docs; duplicated support ledgers |
| Add cue type/family | High | Central edit router and many phase hooks/constants/tests |
| Add enum | Medium | Validator, schemas, dictionary/docs and reply normalization can diverge |
| Add `/live` | High | Safety, address order and correct live readback are not generalized |
| Add relative setter | High | Inventory knows syntax but public operation semantics/executor/tests do not |
| Support new QLab release | High | Unversioned snapshot and no current-official drift gate |
| Add readback verification | Medium/high | Many family-specific after-state normalizers and recovery rules |
| Add real integration test | Medium | Needs opt-in workspace fixture, output safety, `finally` rollback and approval |
| Update documentation | High friction | Multiple roadmaps/coverage/workorders/transcripts can disagree |

## What not to do

- Do not rewrite `QLabReader`, OSC codec, registry or write readiness.
- Do not split files merely to reduce line count.
- Do not add generic repository/service/factory/plugin layers.
- Do not add dependencies for token encoding, retries, caching or OSC.
- Do not optimize object creation before transport round trips/lock contention.
- Do not implement every official OSC property or update subscriptions for numerical completeness.
