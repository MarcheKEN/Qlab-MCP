# 08 — Project Direction

## Technical verdict

The architecture is suitable for continued **controlled** expansion, but not for adding more specialized write families at the current rate. The read surface, exact-target safety, dry-run/gate/readback model, narrow dependencies and 13-tool MCP organization are solid. Stability is blocked by one reproduced UDP stale-reply defect, two other protocol lifecycle gaps, a cache invalidation race, inconsistent release artifacts, and the absence of a current reversible QLab proof.

The project should spend its next milestone on stability and operator workflow, not OSC coverage percentage.

## Direct answers

- **Architecture scalability:** read architecture scales adequately. Write policy scales; the 12,063-line edit implementation does not. Extract one existing family at a time after correctness blockers.
- **MCP organization:** 13 tools is appropriate. There are not too many domain tools, but `qlab_update_cues` and the single-settings detail wrapper are compatibility duplicates. Do not add cue-type-specific tools.
- **First simplifications:** token codec, cache generation, shared exact constants/resolver, then one edit-family handler extraction. Avoid a plugin framework.
- **Mature components to leave alone:** standard-library OSC codec, write readiness, strict workspace/cue resolution policy, registry data model, redaction, result aggregation, Move/Delete boundaries, `QLabReader` facade.
- **Best QLab value next:** reliable pre-show inspection/cut-list workflows, exact-placement cue creation, and a small proven set of Audio/Mic basics. These help operators without triggering a show.
- **Low-value/high-maintenance gaps:** raw OSC, playback/panic, persistent updates, patch/stage/warping writes, broad Light/MIDI/Network output, unrestricted Script/file edits, and property-count expansion.
- **Experimental status:** complete/fix saved edits and live readback before widening; keep `/live` and relative setters unsupported; keep compatibility aliases but stop featuring them.
- **Developer friction:** central edit router, duplicated capability definitions, giant tests, opaque schema hashes, missing toolchain/release policy and inconsistent versions.
- **Operator friction:** no concise installation/runbook/pre-show guide, capability status spread across ledgers, many planned-only routes, UUID-first safety not consistently reflected in schemas, and no opt-in reusable integration fixture.
- **Documentation drift:** high. The architecture graph omits two tools; the capability snapshot can be green against an old dictionary; roadmap/workorders/coverage disagree; local references lack provenance.
- **Common-source generation:** generate tool/capability tables and coverage/workorder statuses from one versioned manifest plus registry/runtime-proof evidence. Keep prose/QClass material hand-written.
- **Before stable:** fix P0/P1 correctness, align version/lock/package contents, current QLab reference and runtime proof, remove permanent skip, add transport regressions and a reversible integration path, publish operator/developer policies.

## Product fit with real theatre workflows

The strongest product identity is a **safe QLab inspection and deliberate editing assistant**, not a remote show controller. Exact workspace/cue UUID targeting, bounded show maps, cue health, settings/routing diagnostics, dry-run diffs, per-operation confirmation and readback are valuable during prep and troubleshooting while respecting live-show risk.

High-value workflow bundles:

1. **Pre-show audit:** connection/mode/scopes, broken/warning/flagged cues, missing media, patch/route health, timecode configuration and explicit unavailable status sections.
2. **Cue-list cleanup:** query by flag/label/type/health, inspect batches, plan common metadata edits, move exact inactive cues, and verify structure.
3. **Fixture-safe authoring:** create Memo/Wait/Group/Audio placeholders with exact placement, then apply a small documented set of saved basics.
4. **Change review:** one structured plan showing original/requested/normalized values, risk/gates and exact readback.

The MCP should continue to refuse GO, panic, raw OSC, ambiguous writes and output-producing tests. Operators can use QLab itself for performance control.

## Documentation and release health

Confirmed drift/friction:

- `pyproject.toml` and artifacts report 0.2.0; module and lock report 0.1.0.
- The lockfile is stale.
- Default sdist discovery included local `.codex/` and `engineering-review/` material.
- Current architecture docs are explicitly “current-ish” and omit Move/Delete.
- Active roadmap is a large validation ledger rather than a prioritized execution plan.
- Coverage snapshots understate some validated Devamp/Fade/Network behavior while still missing current QLab 5.6 additions.
- Workorders contain six “uncertain” items but no clean active/blocked queue.
- Two refactor plans can diverge.
- No `LICENSE`, `CHANGELOG`, `CONTRIBUTING`, `SECURITY` policy or CI workflow is present.
- Project metadata omits several distribution fields.
- QClass content is large and useful but its index is too small to support discovery.

Recommended common source:

```text
versioned QLab reference manifest
          +
write/read registry metadata
          +
runtime-proof records
          ↓
capability resource + docs tables + drift tests + workorder status
```

This should be a small deterministic generator, not a documentation platform.

## Recommended next milestone

### 0.3 — Stability and Operator Workflow

Required scope:

1. Fix late identical UDP reply handling, custom reply port, idle UDP auth and cache clear race.
2. Align project/module/lock versions; explicitly package only release files; add clean build/install smoke.
3. Pin the official QLab reference version and validate the supported surface against QLab 5.6.2 or explicitly retain a documented 5.5 support target.
4. Add scheduled UDP/TCP regressions, cache race tests and one opt-in reversible QLab integration fixture.
5. Produce one capability manifest and regenerate public capability/status tables.
6. Publish an operator guide: install/configure, connection/readiness, pre-show audit, safe dry-run/write/rollback, and troubleshooting.
7. Complete exact-placement creation and only the Audio/Mic basics demanded by the above workflows.
8. Begin one behavior-preserving edit-family extraction and shared token codec after reliability fixes.

Explicitly deferred:

- playback, panic, raw OSC and selected/active writes;
- persistent update subscriptions;
- broad `/live` and relative `+/-` setters;
- Light/MIDI/Network output and patch/stage/warping mutation;
- unrestricted Script/file-target edits;
- broad property coverage and MIDI File expansion.

## Stability exit criteria

- No known P0 transport/readback correctness defect.
- Custom documented ports and UDP idle auth have real regression evidence.
- Cache clear cannot repopulate a pre-clear value.
- One version is reported by metadata, import and lock; clean sdist contains no local material.
- Full tests pass without permanent skips; transport regressions run in CI.
- Current QLab reference provenance is recorded; supported-version policy is public.
- Reversible QLab fixture proves baseline→write→readback→rollback→final readback with cleanup in `finally`.
- Every public tool has one stable result/error shape and accurate annotations.
- Operator runbook and capability status agree with the implementation.
- `operations.py` has at least one family extracted without changing public schemas or safety behavior.
