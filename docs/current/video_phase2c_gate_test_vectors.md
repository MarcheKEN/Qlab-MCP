# Video Phase 2C — Future Gate Test Vectors

## Purpose

Phase 2C documents the future confirmation-gate contract for Video Phase 3A. It does not implement the gate.

Phase 3A first real-write candidate is intentionally narrow:

- Profiles: `video_basic`, `camera_basic`, `text_basic`
- Property: `opacity`
- Mode: `saved`
- Value: number `0..1`
- Scope: exactly one cue and one property
- Cue reference: UUID only
- Readback tolerance: `abs=1e-5`, `rel=1e-6`

## Non-goals

- No token generation.
- No token validation.
- No setters.
- No real writes.
- No runtime QLab.
- No `real_write_possible=true`.
- No change to current Phase 2 behavior.

## Why no real writes yet

Phase 2 keeps Video, Camera, and Text edits plan-only. The runtime-validated contract remains:

- `updateq_plan.status="planned"` for allowed dry-runs.
- `updateq_plan.status="rejected"` for blocked families.
- No `confirm_token`.
- `executed_operations=[]`.
- `safety.will_modify_qlab=false`.
- Baseline unchanged after validation.

Phase 2C only records the Phase 3A gate shape so implementation can be tested against fixed vectors later.

## Future Phase 3A token contract

Future token format should follow the existing Light HMAC pattern, but must be Video-specific.

Token prefix:

```text
confirm:videoOpacity:v1:<base64url-json-payload>:<hmac-sha256>
```

Payload fields:

| Field | Meaning |
|---|---|
| `version` | Token payload version, starting at `1`. |
| `operation_kind` | Must equal `video_phase3_opacity_write`. |
| `workspace_id` | QLab workspace UUID. |
| `cue_id` | Canonical QLab cue `uniqueID`. |
| `cue_ref` | Original request reference. Phase 3A still requires UUID-only refs, so normally equals `cue_id`. |
| `cue_type` | Fresh-read cue type: `Video`, `Camera`, or `Text`. |
| `profile` | `video_basic`, `camera_basic`, or `text_basic`. |
| `property` | Must equal `opacity`. |
| `path` | Must equal `opacity`. |
| `mode` | Must equal `saved`. |
| `baseline` | Fresh opacity value read during reviewed dry-run. |
| `baseline_sha256` | SHA-256 of canonical baseline JSON. |
| `requested` | Normalized requested opacity. |
| `risk_tier` | Must equal `high`. |
| `capability_gate` | Must equal `video_visual`. |
| `mcp_secret_version` | Process-secret/version marker. Restart invalidates tokens. |

Canonical hash rule:

```python
json.dumps(value, sort_keys=True, separators=(",", ":"))
sha256(canonical_json.encode("utf-8")).hexdigest()
```

Hash examples:

| Value | Canonical JSON | SHA-256 |
|---:|---|---|
| `1` | `1` | `6b86b273ff34fce19d6b804eff5a3f5747ada4eaa22f1d49c01e52ddb7875b4b` |
| `0.8` | `0.8` | `d6c7ef32e2fc586fb5798b55f0a2a037813fdc7e209ab9c0d177ecdc7877b09c` |
| `0.6000000238418579` | `0.6000000238418579` | `7118993b95c3104053c43e234535fca32e5e5a3492ee8944a3fbfc8e63826657` |

## Future real-write gates

Phase 3A real write must pass every gate:

- Exactly one update item.
- Exactly one property.
- `cue_ref` must be a UUID.
- Fresh `uniqueID` must equal `cue_ref`.
- Profile must match cue type:
  - `video_basic` → `Video`
  - `camera_basic` → `Camera`
  - `text_basic` → `Text`
- Property/path must be `opacity`.
- Mode must be `saved`.
- `/live` must be rejected.
- Cue must not be broken.
- Cue must not be running, paused, or auditioning.
- Requested opacity must be finite and in `0..1`.
- Fresh baseline must match token `baseline` and `baseline_sha256`.
- Requested value must match token `requested`.
- Setter must execute once only.
- Readback must match requested value using `abs=1e-5`, `rel=1e-6`.
- No mutating retry after mismatch, timeout, or uncertain result.

`armed=false` may remain notice-only unless Phase 3A explicitly tightens this.

## Accept vector

```json
{
  "name": "accept_video_opacity_exact_context",
  "workspace_id": "95F0A03D-140E-4673-974A-E76748EBB023",
  "cue_id": "1EE5940A-858B-4F63-BE6A-2CA3D2B8C7F2",
  "cue_ref": "1EE5940A-858B-4F63-BE6A-2CA3D2B8C7F2",
  "cue_type": "Video",
  "profile": "video_basic",
  "property": "opacity",
  "mode": "saved",
  "baseline": 0.6000000238418579,
  "baseline_sha256": "7118993b95c3104053c43e234535fca32e5e5a3492ee8944a3fbfc8e63826657",
  "requested": 0.55,
  "risk_tier": "high",
  "capability_gate": "video_visual",
  "expected": "accept"
}
```

Expected Phase 3A result:

- One setter to `/workspace/{workspace_id}/cue_id/{cue_id}/opacity`.
- One post-write readback.
- `status="updated"` only if readback matches tolerance.

## Reject vectors

| Name | Mutation from accept vector | Expected reason |
|---|---|---|
| `reject_malformed_token` | Token cannot be decoded. | malformed token |
| `reject_tampered_signature` | HMAC mismatch. | invalid signature |
| `reject_wrong_version` | `version=2` or prefix `v2`. | unsupported version |
| `reject_wrong_workspace` | Different `workspace_id`. | token context mismatch |
| `reject_wrong_cue_id` | Different `cue_id`. | token context mismatch |
| `reject_cue_number_ref` | Request `cue_ref="v4"`. | UUID-only required |
| `reject_wrong_profile` | `profile="camera_basic"` for fresh `Video`. | profile/type mismatch |
| `reject_wrong_cue_type` | Fresh `cue_type="Audio"`. | unsupported cue type |
| `reject_wrong_property` | Property `translation/x`. | Phase 3A only allows opacity |
| `reject_opacity_out_of_range` | Requested opacity `<0` or `>1`. | opacity must be `0..1` |
| `reject_opacity_non_finite` | Requested opacity `NaN`, `Infinity`, or `-Infinity`. | opacity must be finite |
| `reject_live_mode` | `mode="live"` or `/live` path. | saved mode required |
| `reject_wrong_requested` | Request `0.56`, token says `0.55`. | requested mismatch |
| `reject_stale_baseline` | Fresh baseline changed. | stale baseline |
| `reject_broken_cue` | Fresh `isBroken=true`. | unhealthy cue |
| `reject_running_cue` | Fresh `isRunning=true`. | active cue |
| `reject_paused_cue` | Fresh `isPaused=true`. | active cue |
| `reject_auditioning_cue` | Fresh `isAuditioning=true`. | active cue |
| `reject_batch` | Two update items. | one cue required |
| `reject_second_property` | `opacity` plus another property. | one property required |
| `reject_readback_mismatch` | Setter returns, readback differs beyond tolerance. | verification failed |
| `reject_readback_timeout` | Setter/readback uncertain. | verification failed; no retry |
| `reject_old_rollback_token` | Reuse forward token for rollback. | requested/baseline mismatch |

All rejects must have no mutating OSC request unless the vector is specifically a post-setter readback failure. Readback failure must not retry the setter.

Timeout policy:

- Setter timeout plus readback matches requested value within tolerance: confirmed success with warning.
- Setter timeout plus missing or mismatched readback: uncertain failure; no mutating retry.

## Rollback rules

Rollback is a new edit, not an undo shortcut.

1. Read fresh current opacity.
2. Dry-run requested rollback value.
3. Generate new Phase 3A token from the new baseline.
4. Execute one setter.
5. Verify readback with numeric tolerance.

Old tokens must not authorize rollback because baseline and requested value differ.

## Later Phase 3A runtime validation

After Phase 3A implementation and MCP restart:

1. Capture baseline for healthy Video, Camera, and Text cues.
2. Dry-run opacity only; confirm token appears only in Phase 3A.
3. Execute one Video opacity write with reviewed token.
4. Verify one setter and exact workspace/cue UUID-qualified address.
5. Verify readback within tolerance.
6. Run reject vectors that must fail before setter.
7. Restore original opacity through new dry-run and new token.
8. Confirm final baseline equals initial baseline.
9. Confirm no playback, `/live`, Dashboard, raw OSC mutation, or Workspace Video writes.

## Current Phase 2 invariants

Until Phase 3A starts, tests must continue proving:

- Video/Camera/Text Phase 2 dry-runs emit no `confirm_token`.
- `real_write_possible=false`.
- `requires_confirm_token=false`.
- `executed_operations=[]`.
- `dry_run=false` with fake `confirm_gates` rejects before OSC.
- Audio, Light, Fade, and common-property behavior unchanged.
