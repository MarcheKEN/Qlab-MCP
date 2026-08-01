# 02 — MCP Tool Catalog

## Verdict

The public surface is coherent and still manageable: 13 tools, of which eight are read-only (including write readiness) and five mutate or alias mutation. The main problems are contract consistency rather than tool count: one duplicate compatibility alias, one union result wrapped differently by FastMCP, loose string schemas, uncapped settings-detail batches, and incorrect `destructiveHint=false` annotations on Edit and Move.

No additional public tool is justified now. Expansion should occur inside the existing read/query/detail/edit tools, backed by one versioned capability manifest. If static capability discovery becomes useful, expose a resource generated from that manifest rather than another operational tool.

## Shared behavior

- Registration and schemas: `src/qlab_mcp/server.py:348-1119`; Pydantic result/input models: `src/qlab_mcp/models.py:78-596`.
- Every handler is synchronous and creates a fresh `QLabReader`; FastMCP's decorator timeout does not preempt its worker thread. Internal OSC timeouts still apply.
- Read tools use workspace UUID or display name and fail closed when omission is ambiguous. Real writes require an explicit workspace and resolve cue references to exact UUIDs before setters.
- Read tools may use a 10-second process cache. Real writes clear/bypass it and verify with fresh reads; setters are not retried.
- Error payloads usually carry `ok/status/error_code/message/received/allowed`, but some `_run_tool` paths raise `ToolError`; clients therefore see two error shapes.
- Tests: `tests/test_server_tools.py` covers metadata/schema hashes and selected wrappers; domain suites test underlying behavior. The full suite passed 2,345 tests with one skip.

## Inventory

| Tool | Implementation; purpose; mode | Input and output contract | QLab representation and OSC | Targeting, validation, timeout/retry/readback | Evidence, documentation, maturity |
| --- | --- | --- | --- | --- | --- |
| `qlab_check_connection` | `server.py:348-383`; diagnose QLab/workspace/passcode/read access; read | Optional `workspace_id`, `require_read_access`; `QlabConnectionCheckResult` | `/workspaces`, optional `/workspace/{id}/connect`, `/showMode`, `/cueLists/shallow`, application override reads | Workspace omission allowed only for exactly one workspace; no retry/readback; decorator timeout plus per-request OSC timeout | Live: QLab 5.5.10, workspace UUID, scopes and 11 lists confirmed. Documented in README/tool metadata. **Complete** |
| `qlab_get_workspace_overview` | `server.py:386-497`; bounded structure/index/live summary; read | Depth/cue/index limits and profiles; `WorkspaceOverviewResult` | `/cueLists/shallow`, recursive `/children/shallow`, `/cueLists/uniqueIDs`, selected/running reads, batched `valuesForKeys` | Optional strict workspace; depth/count validation is partly runtime (schema does not express documented 0..5); cached reads, no retry | Live: 185 items, 11 lists, selected/playhead evidence. Broad reader tests. **Complete** |
| `qlab_get_workspace_status` | `server.py:500-557`; derived operational status; read | Explicit workspace; summary/technical, timecode and scan/sample limits; `WorkspaceStatusResult` | Cue `valuesForKeys` plus settings reads; reports unsupported QLab Status sections as `not_exposed` | Strict workspace; bounded scan; no retry; cached inputs | Live: 56 broken, one warning, eight flagged, three timecode-config cues, no running/paused cues. **Complete** |
| `qlab_get_workspace_settings` | `server.py:560-635`; settings inventory or batched detail; read | `mode`, sections, `requests`, profile; `WorkspaceSettingsResult` | `/settings/...` for audio patches/maps, video routes/stages/inputs, network/MIDI/light/general; large Light data can use TCP | Exact workspace; redaction and item ambiguity checks; **requests list has no schema cap**; no retry except explicit large-read UDP→TCP fallback | Live summary and four detail requests confirmed. **Complete**, with input-bound gap |
| `qlab_get_workspace_setting_details` | `server.py:638-706`; single-request compatibility wrapper; read | section/kind/ref/profile; `WorkspaceSettingDetailsResult` | Same `/settings/...` operations as previous tool | Same targeting/normalization; no independent behavior | Live confirmed but adds no capability. Documented as backwards-compatible. **Duplicated by another tool** |
| `qlab_query_cues` | `server.py:709-800`; filter up to 5,000 cue IDs; read | Required filter/value, optional AND filters, profile and limits; `CueQueryResult` | `/cueLists/uniqueIDs`, batched cue `valuesForKeys` | Exact workspace; filter/value normalization occurs at runtime; cached reads; no retry | Live Memo/filter queries confirmed. Strong reader tests. **Complete** |
| `qlab_get_cue_details` | `server.py:803-848`; one cue or batch ≤50; read | Exact workspace, string or list cue ref, profile; union of `CueDetailsResult`/`CueDetailsBatchResult` | `/cue/{ref}/valuesForKeys` with per-property fallback; optional settings-derived sections | Cue number/UUID and read aliases allowed; ambiguous `active` may yield several cues but aggregation is unverified; no retry beyond fallback; cached unless live/sensitive | Live number/UUID matched. FastMCP wraps this union as `{"result":...}` unlike flat tools. **Mostly complete** |
| `qlab_check_write_readiness` | `server.py:851-869`; non-mutating write preflight; read | Explicit workspace; `WriteReadinessResult` | `/workspaces`, `/connect`, `/showMode` plus local env/capability checks | Exact workspace; passcode presence, edit scope, Edit Mode and enable flag; no setter/readback | Live ready state confirmed. Strong safety tests. **Complete** |
| `qlab_create_cue` | `server.py:872-932`; create one blank Memo/Group/Wait/Audio; change | Cue type, safe initial properties, dry-run, optional planned-only placement; `CreateCueResult` | `/cueLists/{target}/new` followed by allowlisted `/cue_id/{uuid}/{property}` setters and reads | Explicit workspace; readiness and allowlists; no confirm token; no setter retry; exact placement is dry-run-only | Automated plan/write tests; no real create in this review. Narrow by design and placement incomplete. **Partially complete** |
| `qlab_edit_cues` | `server.py:935-981`; batch plan/edit up to 50; change | `CueUpdateInput[]`, dry-run; `UpdateCuesResult` | Registry-driven `/cue_id/{uuid}/{property}` plus specialized cue-family routes; read-before/diff/fresh readback | Concrete cue refs only; all-batch preflight; per-operation signed gates for high risk; one setter; readback delays, rollback only for designed recovery paths | Very strong write suite and historical runtime proofs, but many catalogued routes remain planned-only. Live dry-run in this review was approval-blocked. **Mostly complete** |
| `qlab_update_cues` | `server.py:984-1018`; deprecated compatibility call to Edit; change | Same inputs/output as Edit | Identical | Identical | Tested/documented as alias. **Duplicated by another tool**; retain for compatibility, omit from new examples |
| `qlab_move_cues` | `server.py:1021-1068`; sequential move of 1–10 exact UUID cues; change | Placement model, dry-run, tool-level signed token; `MoveCuesResult` | Structural QLab move routes for List/Group/Cart, followed by structure readback | Exact UUIDs; inactive/healthy checks, fresh structure-bound token, no retry, convergence polling, explicitly non-atomic | Strong automated and prior List/Group runtime proof; Cart remains blocked/unverified. **Mostly complete** |
| `qlab_delete_cues` | `server.py:1071-1119`; sequential leaf deletion of 1–10 cues; change | UUID list, dry-run, tool-level signed token; `DeleteCuesResult` | `/cue_id/{uuid}/delete`, followed by existence reads | Leaf-only, inactive, exact UUID, structure-bound token; no retry; absence verification; non-atomic | Strong automated/runtime-oriented tests; destructive scope intentionally narrow. **Complete for its declared scope** |

## Cross-cutting contract findings

1. `GATED_CREATE_QLAB_TOOL` sets `destructiveHint=false`. That is accurate for Create, but Edit and Move can replace values or alter structure; their annotation is semantically wrong. Give them a separate annotation with `destructiveHint=true` while retaining `idempotentHint=false`.
2. `qlab_get_cue_details` is the only union-return handler. FastMCP 3.3.1 exposes it under a `result` envelope, which clients must special-case. Prefer one stable response model with `results` for batch and a consistent top-level shape.
3. Many fields are `str`/`int` despite closed aliases/ranges implemented later. Export `Literal`/enums and numeric constraints where they are stable; keep runtime validation for cross-field rules.
4. `qlab_get_workspace_settings(mode="details")` should cap `requests` to a small bounded value, matching cue-detail and write batches.
5. `qlab_update_cues` is intentional compatibility debt. Keep it through a stated deprecation window, but generate metadata/docs from the canonical Edit definition so it cannot drift.
6. Internal capability discovery already exists through the registry and `editable` detail profile. Do not add one tool per cue type or property.
7. The surface is broad enough. The scaling bottleneck is the 12,063-line edit implementation and duplicated capability/documentation definitions, not MCP discovery.

## Practical additions not exposed

- Update subscriptions, relative `+/-` setters, raw OSC and playback controls are intentionally absent or unsupported. They should not be exposed until lifecycle/safety designs and protocol tests exist.
- A static, versioned capability/resource document would be useful to clients, but it should be generated from the registry/dictionary snapshot, not hand-maintained as another tool.
- There is no evidence that adding narrower public tools for individual cue types would improve operator workflows; it would multiply schemas and documentation.
