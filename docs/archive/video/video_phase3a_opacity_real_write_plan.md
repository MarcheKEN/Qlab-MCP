# Video Phase 3A — Opacity Real Write Gate

## A. Markdown path

`docs/archive/video/video_phase3a_opacity_real_write_plan.md`

## B. Summary / scope

Phase 3A enables the first Video-family real write: `opacity` only.

Allowed:

- Cue types: `Video`, `Camera`, `Text`
- Profiles: `video_basic`, `camera_basic`, `text_basic`
- Property/path: `opacity`
- Mode: `saved`
- Value: finite number `0..1`
- Shape: exactly one cue, exactly one property, exact cue UUID only

Blocked:

- `/live`
- playback, GO, Dashboard, raw OSC mutation
- Workspace Video writes
- batch writes
- multi-property writes
- all properties except `opacity`
- Video FX, `fileTarget`, camera patch, stage changes, rotation
- text, translation, scale, crop, anchor, blend mode, clock type

Official QLab docs confirm `/cue/{cue_number}/opacity` is read/write and accepts a decimal `0..1`; they also document `/cue/{cue_number}/opacity/live`, which Phase 3A must reject because live messages operate on active/live values rather than saved workspace state.

Sources:

- QLab 5 Documentation, “QLab’s OSC Dictionary”, `/cue/{cue_number}/opacity`: https://qlab.app/docs/v5/scripting/osc-dictionary-v5/
- QLab 5 Documentation, “Video Cues”, opacity inspector meaning: https://qlab.app/docs/v5/video/video-cues/
- QLab 5 Documentation, “QLab’s OSC Dictionary”, “How To Read This Dictionary” live-form notes: https://qlab.app/docs/v5/scripting/osc-dictionary-v5/

## C. Gate / token contract

Use the existing Light Phase 4/5 HMAC pattern. Do not introduce a generic gate framework yet.

New constants in `src/qlab_mcp/write/operations.py`:

- `PHASE3_VIDEO_OPACITY_TOKEN_VERSION = 1`
- `PHASE3_VIDEO_OPACITY_OPERATION_KIND = "video_phase3_opacity_write"`
- token prefix: `confirm:videoOpacity:v1:...`
- reuse existing process secret pattern; either reuse current write-token secret or rename only if no broad churn is needed

Dry-run operation metadata for eligible opacity:

- `real_write_enabled=false`
- `real_write_possible=true`
- `requires_confirm_token=true`
- `planned_only_reason="video_opacity_requires_confirm_token"`
- `phase3_video_opacity_candidate=true`
- `confirm_token="confirm:videoOpacity:v1:<payload>:<signature>"`

`real_write_possible=true` is allowed only when the dry-run passes every Phase 3A gate:

- cue type is `Video`, `Camera`, or `Text`
- profile is `video_basic`, `camera_basic`, or `text_basic`
- property/path is `opacity`
- mode is `saved`
- `cue_ref` is an exact UUID
- exactly one cue and one property
- cue is healthy and inactive

All non-opacity Video/Camera/Text operations remain Phase 2 dry-run-only: no token, `real_write_possible=false`.

Token payload fields:

| Field | Required value |
|---|---|
| `version` | `1` |
| `operation_kind` | `video_phase3_opacity_write` |
| `workspace_id` | workspace UUID |
| `cue_id` | canonical QLab `uniqueID` from fresh read |
| `cue_ref` | original request ref; Phase 3A still requires UUID-only refs, so equals `cue_id` |
| `cue_type` | `Video`, `Camera`, or `Text` |
| `profile` | matching update profile |
| `property` | `opacity` |
| `path` | `opacity` |
| `mode` | `saved` |
| `baseline` | fresh opacity before value |
| `baseline_sha256` | canonical JSON SHA-256 of baseline |
| `requested` | normalized requested opacity |
| `risk_tier` | `high` |
| `capability_gate` | `video_visual` |
| `mcp_secret_version` | process-secret marker, e.g. `1` |

Canonical hash:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"))
hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
```

## D. Real write flow

### Dry-run

1. Normalize request through existing registry.
2. Require Phase 3A shape:
   - one update item
   - one operation
   - profile in `video_basic`, `camera_basic`, `text_basic`
   - property/path `opacity`
   - mode `saved`
   - UUID `cue_ref`
   - empty `confirm_gates`
3. Fresh read with `cacheable=false`:
   - `uniqueID`
   - `number`
   - `name`
   - `type`
   - `armed`
   - `isBroken`
   - `isWarning`
   - `isRunning`
   - `isPaused`
   - `isAuditioning`
   - `opacity`
4. Require:
   - returned `uniqueID == cue_ref`
   - profile matches cue type
   - `isBroken=false`
   - `isWarning=false` for Phase 3A, matching Phase 2 health behavior
   - `isRunning=false`
   - `isPaused=false`
   - `isAuditioning=false`
   - requested opacity finite and `0..1`
5. Keep `armed=false` as `cue_disarmed` notice, not blocker.
6. Generate Phase 3A token from fresh baseline and normalized requested value.
7. Return dry-run plan only:
   - `after=null`
   - `executed_operations=[]`
   - no setter sent

### Real write

1. Reject before any OSC setter unless:
   - `dry_run=false`
   - exactly one `confirm_gates` entry
   - Phase 3A shape is exact
2. Validate token:
   - prefix/version
   - HMAC signature
   - payload object
3. Fresh read before setter using same keys as dry-run.
4. Reject before setter if:
   - workspace/cue/profile/type/property/path/mode mismatch
   - requested value mismatch
   - baseline or `baseline_sha256` mismatch
   - cue broken/warning/active
   - cue UUID mismatch
   - value non-finite or out of range
5. Execute exactly one setter:

```text
/workspace/{workspace_id}/cue_id/{cue_id}/opacity {requested}
```

6. Perform post-write readback with `cacheable=false`.
7. Success only if readback matches requested value with:
   - `abs=1e-5`
   - `rel=1e-6`

Timeout policy:

- Setter returns normally + readback matches: success.
- Setter timeout + readback matches within tolerance: success with `status="updated"`, warning `setter_timeout_but_readback_matched`, and `timeout_confirmed_count += 1`.
- Setter returns normally + readback mismatch/missing: `verification_failed`, no retry.
- Setter timeout + readback missing or mismatched: uncertain failure, no retry.

No mutating retry in Phase 3A.

## E. Rollback flow

Rollback is a new write, not undo.

1. Read current opacity.
2. Dry-run requested rollback opacity.
3. Generate new token from current baseline.
4. Execute one setter with new token.
5. Verify readback.

Old token must fail rollback because requested value and baseline differ.

## F. Implementation plan

### `src/qlab_mcp/write/registry.py`

- Keep Video/Camera/Text opacity registry entry normalized as Phase 2 already does.
- Do not mark registry spec as directly real-write enabled.
- Let `operations.py` annotate Phase 3A candidate metadata and token.
- Tighten `opacity` validator to reject non-finite `NaN`, `Infinity`, and `-Infinity` if not already rejected.

### `src/qlab_mcp/write/operations.py`

Add small Video-specific helpers near Light gate helpers:

- `_phase3_video_opacity_operation(item)`
- `_phase3_video_opacity_call_structure_error(items)`
- `_phase3_video_opacity_token_payload(...)`
- `_phase3_video_opacity_confirm_token(...)`
- `_decode_phase3_video_opacity_confirm_token(token)`
- `_validate_phase3_video_opacity_real_write(workspace_id, item, before)`
- `_annotate_phase3_video_opacity_operation(item, workspace_id, before)`

Behavior changes:

- Detect Phase 3A opacity calls before generic Video Phase 2 real-write rejection.
- Dry-run: annotate only valid Phase 3A opacity candidates with token and `real_write_possible=true`.
- Real write: require exactly one token, validate fresh baseline, then allow setter.
- Keep non-opacity Video/Camera/Text properties Phase 2 dry-run-only with no token and `real_write_possible=false`.
- Keep Phase 2 `updateq_plan` fields; for opacity dry-run, `requires_confirm_token` becomes true in setter metadata and plan only if implementation chooses to expose candidate status there. Do not change rejected-plan shape.

Post-write verification:

- Reuse existing `_property_values_match` numeric tolerance.
- For setter timeout, perform readback before deciding:
  - readback match → success with warning
  - readback missing/mismatch → failure/uncertain, no retry

### Models/schema

- No schema change expected.
- Existing result fields already carry `confirm_token`, planned operations, warnings, and verification data.

## G. Tests required

Add focused tests in `tests/test_write_mode.py`.

Dry-run/token:

- opacity dry-run for Video emits `confirm_token`.
- opacity dry-run for Camera emits `confirm_token`.
- opacity dry-run for Text emits `confirm_token`.
- token prefix is `confirm:videoOpacity:v1:`.
- token payload has all required fields.
- dry-run still has `executed_operations=[]`.
- non-opacity Video/Camera/Text dry-runs still emit no token and remain `real_write_possible=false`.

Real write success:

- valid token allows exactly one `/opacity` setter.
- readback match returns `status="updated"`.
- `armed=false` succeeds with `cue_disarmed` notice.

Token rejects before setter:

- fake token.
- tampered signature.
- wrong version.
- wrong workspace.
- wrong cue UUID.
- wrong profile.
- wrong cue type.
- wrong property/path.
- wrong mode or `/live`.
- stale baseline.
- requested value mismatch.
- cue number instead of UUID.
- batch update.
- second property.
- broken cue.
- warning cue.
- running cue.
- paused cue.
- auditioning cue.
- opacity `<0`, `>1`.
- opacity `NaN`, `Infinity`, `-Infinity`.

Verification/timeout:

- readback mismatch returns verification failure.
- mismatch sends one setter only.
- setter timeout + matching readback succeeds with `status="updated"`, warning `setter_timeout_but_readback_matched`, and timeout-confirmed count.
- setter timeout + missing readback fails uncertain; no retry.
- setter timeout + mismatched readback fails uncertain; no retry.

Rollback:

- forward token cannot authorize rollback.
- rollback succeeds only after new dry-run and new token.

Regression:

- Audio/Light/Fade behavior unchanged.
- Light Phase 4/5 token tests unchanged.
- Phase 2B non-opacity Video/Camera/Text dry-runs unchanged.

Suggested commands:

```bash
.venv/bin/pytest -q tests/test_write_mode.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
```

## H. Runtime validation plan

After implementation and manual MCP restart only:

1. Use workspace `<TEST_WORKSPACE_NAME>`.
2. Use cue list `MCP_VIDEO_WRITE_FIXTURE`.
3. Capture baseline for healthy Video, Camera, and Text cues.
4. Start with healthy Video cue only.
5. Dry-run opacity change with exact cue UUID.
6. Confirm token payload context and workspace-qualified planned setter.
7. Execute one real write with token.
8. Confirm one setter, saved mode, no `/live`, no playback.
9. Read back opacity and verify tolerance.
10. Roll back through new dry-run and new token.
11. Confirm final baseline equals initial baseline.
12. Only after Video passes, repeat same path for Camera and Text.
13. Run rejection probes: fake token, stale baseline, cue number, batch, live, broken cue.
14. Confirm no Workspace Video writes, Video FX, fileTarget, camera patch, stage, rotation, text, translation, scale, or crop mutation.

Safety note for runtime: use a test workspace, test display, or non-show output. Do not use MCP to start Audition or playback.

## I. Risks / open questions

- `NaN` and infinities may currently pass generic numeric validation unless explicitly rejected; fix opacity validation first.
- Setter-timeout semantics need careful status naming so callers can distinguish confirmed success from uncertain failure.
- Existing `_try_read_update_values_with_retries` can retry readback; Phase 3A must not perform mutating retry, but safe read retries are acceptable only if they do not obscure timeout status.
- `isWarning=true` remains blocked to match Phase 2. Relax only after a separate decision.
- `armed=false` stays notice-only.
- Token secret scope should follow existing Light process-secret behavior; no persistent token storage.

## J. Recommended first implementation step

Start in `operations.py` with Phase 3A detection and structure helpers, modeled on Light Phase 5. Then add token payload/decode tests before allowing any real setter path.
