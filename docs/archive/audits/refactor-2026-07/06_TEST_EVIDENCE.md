# 06 — Automated Test Evidence

## Verdict

The repository has an unusually strong write-safety behavior suite, but transport correctness and maintainability lag behind its raw test count. Of 2,346 collected cases, 2,084 (88.8%) and 67.9% of test LOC live in `tests/test_write_mode.py`. Passing the suite proves extensive planner/gate/readback behavior against fakes; it does not prove protocol-faithful concurrency or a reversible real-QLab workflow.

## Executed checks

| Command | Exit | Duration | Result |
| --- | ---: | ---: | --- |
| `/usr/bin/time -p .venv/bin/pytest -q` in managed sandbox | 2 | 109.32 s | Environment prevented loopback socket binds; interrupted after 51 failed, 56 passed, 48 warnings, 4 subtests. This is not a product failure. |
| `.venv/bin/pytest -q` outside socket-restricted sandbox | 0 | 20.41 s | 2,345 passed, 1 skipped, 37 subtests |
| Independent full run `.venv/bin/pytest -q --tb=short` | 0 | 20.97 s pytest / 21.75 s wall | Same pass/skip counts |
| `.venv/bin/pytest -q --tb=short --durations=20` | 0 | 21.38 s pytest / 22.26 s wall | Same; identified real-sleep timeout tests |
| Focused transport/cache set | 0 | 0.12 s | 14 passed |
| `tests/test_osc.py tests/test_update_registry_coverage.py` | 0 | 0.30 s | 20 passed |
| `tests/test_server_tools.py` focused run | 0 | 1.26 s | 23 passed |
| Empty Phase 2 scalar matrix test | 0 | 0.27 s | 1 skipped: empty parameter set |
| `uv build --out-dir engineering-review/build-artifacts` in sandbox | 2 | <1 s | uv cache path permission denied; environment-only |
| Same build with approved external execution | 0 | 4.04 s | wheel and sdist built |
| `uv lock --check` with writable review cache | 2 | <1 s | Lockfile needs update |
| `git diff --check`; `git diff --cached --check` | 0 | <1 s | Clean whitespace/staging checks |

No lint, formatter, type checker or coverage tool is configured. A coverage probe failed with `No module named coverage`; this is an absent check, not a failed quality gate.

Fresh continuation verification: `.venv/bin/pytest -q` exited 0 with **2,345 passed, 1 skipped, 37 subtests passed in 21.62 seconds**. A second fresh run in the same continuation also exited 0 with 2,345 passed, 1 skipped and 37 subtests.

## Test inventory and strength

| Suite | Size / cases | What it proves | Main limitation |
| --- | --- | --- | --- |
| `test_delete_mode.py` | 326 LOC / 12 | Token binding, leaf/container rejection, ordered delete, delayed absence readback, stop-on-failure | Fake transport only |
| `test_light_command_analyzer.py` | 202 LOC / 26 collected | Pure Light command parsing | Not QLab Light execution |
| `test_osc.py` | 145 LOC / 9 | Basic OSC/SLIP roundtrip, reply parsing/matching, mocked TCP | No late/duplicate/out-of-order/fragmented protocol server |
| `test_qlab_reader.py` | 5,894 LOC / 179 + 37 subtests | Broad reads, settings, filters, cache, redaction | Sequential fake hardcodes one workspace and immediate replies |
| `test_read_coverage.py` | 50 LOC / 2 | Static dictionary/allowlist counts | No actual QLab reads; local snapshot can be stale |
| `test_server_tools.py` | 1,146 LOC / 23 | All 13 metadata/schema hashes, selected wrapper/error shapes | Hash alarm is opaque; several wrappers snapshot-only |
| `test_update_registry_coverage.py` | 217 LOC / 11 | Local dictionary/registry/docs consistency | Can be green while official QLab has new routes |
| `test_write_mode.py` | 16,862 LOC / 2,084 collected | Extensive dry-run, gates, signed tokens, validators, setter-once, fresh readback, rollback, timeouts, profiles | Giant fake and phase-copied tests; no OSC byte/E2E proof |

## Strongly evidenced behavior

- Dry-run never sends setters; real paths bind exact workspace/cue/profile/property context.
- Confirmation-token tampering, reuse and cross-family misuse fail closed.
- Real edit batches preflight before setters and use cue UUIDs.
- Setter-once assertions exist for common, Group, phase families, Move and Delete.
- Timed-out setters are not retried; fresh after-state polling determines known success versus uncertain failure.
- Move/Delete use structural/existence readback and report non-atomic sequential behavior.
- Registry validators and many enum/range normalizations are exercised.
- Safe-cache bypass for live/sensitive/fresh reads and identical-key single-flight are covered.
- Unknown/ambiguous workspace resolution and many invalid cue/property combinations are covered.

## Highest-risk missing tests

1. **Late or duplicate identical UDP replies.** A review reproduction confirms the next same-address request can accept stale data.
2. **Concurrent different OSC queries and out-of-order replies.** The endpoint lock is unmeasured at the packet layer; current fake cannot schedule replies.
3. **Protocol-faithful TCP.** Missing fragmented/multiple SLIP frames, unrelated frame, malformed escape, remote close and timeout cases.
4. **Wrong sender/source-port filtering.** Sender-IP helper lacks direct/socket tests; source port is not checked.
5. **Cache failure races.** Missing factory exception wakeup, different-key independence, clear-during-flight, fake-clock expiry and cross-workspace namespace cases. The clear race is reproduced.
6. **True multi-workspace transport.** Same cue number in two workspaces, independent auth/cache, and wrong-workspace replies are absent.
7. **Address-embedded relative setters.** Existing “relative” tests concern Fade semantics, not QLab OSC `+/-` syntax.
8. **Actual `/live` setter/readback.** Policy/planning tests exist, but no protocol or real QLab proof distinguishes saved/live values.
9. **Enum reply variations.** Strong input validation, weak normalization contract for numeric versus symbolic QLab replies.
10. **Malformed OSC/reply corpus.** Truncation, padding, typetags, invalid SLIP and malformed JSON object fields need pure tests.
11. **Real reversible integration restoration.** No opt-in fixture guarantees rollback in `finally` after assertion/transport failure.
12. **Current official dictionary drift.** Static coverage is only as current as the local snapshot.

## Quality and maintenance findings

- Permanently skipped: `test_video_phase2_scalar_matrix_plans_normalized_diff_without_token` (`test_write_mode.py:7753-7823`) receives an empty parameter list. Remove it or populate the matrix so the suite has no silent hole.
- Eight timeout-mismatch tests consume roughly 64% of the suite (about 1.7 s each) because they sleep real retry delays. Inject the fake clock already used by Move/Delete.
- `BatchFakeWriteClient` (`test_write_mode.py:470-825`) reimplements QLab state transitions. A matching mistake can exist in both fake and product. Retain behavior tests but add a small encoded-OSC contract layer.
- The full FastMCP schema snapshot uses hashes, which identify drift but not the field. Keep the alarm and add human-readable per-tool assertions for high-risk contracts.
- Several documentation tests check phrase presence in one direction, so stale rows can remain. Generate tables from the manifest or compare exact structured data.
- One giant registry test delegates to helpers spanning ~330 lines, reducing failure locality.
- No exact duplicate test function bodies were found, but Phase 3/7/8/9 token/timeout/rollback families are copy-shaped.
- Production globals are cleared by individual tests rather than an autouse isolation fixture; arbitrary-order behavior was not tested.
- The UDP fake is a daemon thread whose shutdown join is not asserted; failures could leak test state.
- `test_qlab_reader.py` has a UTF-8 BOM and manual `sys.path` manipulation despite pytest `pythonpath` config.

## Packaging evidence

The wheel contains only `qlab_mcp` package files and metadata. The sdist also included ignored/untracked local `.codex/` and `engineering-review/` material, including a build-artifact `.gitignore`. Hatch's default sdist discovery is therefore capable of leaking local agent configuration, review reports or other checkout-only files. This is a release correctness issue even though the build command succeeded.

Version consistency also fails:

- `pyproject.toml` and artifact names: 0.2.0.
- `src/qlab_mcp/__init__.py` and the project record in `uv.lock`: 0.1.0.
- `uv lock --check`: lock requires update.

## Minimal layered target

```text
tests/unit/        config, addressing, OSC codec/parser, cache, validators, results, budgets
tests/contracts/   MCP schemas, registry/dictionary manifest, real reply fixtures
tests/transport/   scheduled UDP and protocol-faithful TCP loopback servers
tests/read/        workspace, overview, query, details, settings
tests/write/       common plus domain families, moves, deletes
tests/integration/ opt-in read-only QLab and reversible-write QLab fixtures
```

Use only three markers: `unit`, `transport`, `qlab`. Add regression tests first; reorganize files mechanically only when it materially improves failure locality. The first QLab write fixture must capture the original value and restore it in `finally`, with a final fresh assertion even after test failure.
