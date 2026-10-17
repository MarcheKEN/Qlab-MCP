# Video Phase 5 - Docs Consistency Cleanup

> Historical evidence or dated plan. Use the [current tools](../../../user/tools.md) and
> [roadmap](../../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Status: local docs cleanup for Phase 5.

Purpose: make current Video docs match the implemented safety state before any
Video FX scalar v2 work.

## Cleanups

| Area | Problem | Resolution |
|---|---|---|
| `007_text_style_and_video_fx_read_plan.md` | Text Style local-validation bullets contradicted the runtime decision by saying dry-runs emitted `confirm:textStyle:v1:` tokens. | State that Text Style candidates reject without token or setter until reliable fresh readback exists. |
| `current/coverage/osc_coverage_snapshot.md` | Generated registry table shows `Video` real writes as `0`, while Phase 4C has one specialized runtime-validated exception. | Clarify that the table is registry baseline coverage and specialized token gates are documented as exceptions below the table. |
| `active_roadmap.md` | Next macro step was implicit. | Add Phase 5 as docs/audit-only and keep Phase 6 separate from the matrix work. |
| `docs/README.md` | Current docs list did not include Phase 5 workorders. | Add `009` and `010`. |

## Non-changes

- no runtime code
- no write logic
- no token logic
- no writable property expansion
- no runtime QLab tools
- no raw OSC
- no commit

## Resulting phase split

- Phase 5: Completion Matrix and Closure Audit.
- Phase 6: Video FX scalar v2 candidate, separate implementation and runtime proof.
