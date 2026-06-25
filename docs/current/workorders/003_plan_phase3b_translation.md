# Workorder 003 — Plan Video Phase 3B Translation

Status: implemented locally; runtime validation pending

Phase 3B code enables token-gated saved real writes for Video, Camera, and
Text `translation/x` and `translation/y`. Video runtime validation passed.
Camera/Text runtime use requires MCP restart and separate validation.

## Official basis

QLab 5 documents these Video cue messages as read/write with decimal numeric
values:

- `/cue/{cue_number}/translation/x {number}`
- `/cue/{cue_number}/translation/y {number}`

The dictionary also documents `/live` forms. Phase 3B must reject them because
this phase edits saved workspace state only.

Sources:

- QLab 5 OSC Dictionary, “Video cue messages”:
  https://qlab.app/docs/v5/scripting/osc-dictionary-v5/
- QLab 5 Video Cues, Geometry / Translation:
  https://qlab.app/docs/v5/video/video-cues/

## Scope

Current implementation:

- cue/profile pairs:
  - `Video` / `video_basic`
  - `Camera` / `camera_basic`
  - `Text` / `text_basic`
- properties: `translation/x` or `translation/y`
- mode: `saved`
- `cue_ref`: exact UUID only
- exactly one cue and one property
- requested value: finite number
- risk tier: `high`
- capability gate: `video_visual`

## Gate contract

Valid dry-run candidate:

1. Normalize one finite numeric value.
2. Fresh-read cue UUID, type, health/activity fields, and selected translation
   axis.
3. Require returned `uniqueID == cue_ref`.
4. Require exact cue type/profile match.
5. Reject broken, warning, running, paused, or auditioning cues.
6. Keep disarmed state notice-only.
7. Return a review token; execute no setter.

Token prefix:

```text
confirm:videoTranslation:v1:
```

Payload:

| Field | Required value |
|---|---|
| `version` | `1` |
| `operation_kind` | `video_phase3b_translation_write` |
| `workspace_id` | workspace UUID |
| `cue_id` | canonical QLab `uniqueID` |
| `cue_ref` | original UUID-only request reference |
| `cue_type` | `Video`, `Camera`, or `Text` |
| `profile` | matching `video_basic`, `camera_basic`, or `text_basic` |
| `property` | `translation/x` or `translation/y` |
| `path` | same scalar property path |
| `mode` | `saved` |
| `baseline` | fresh selected-axis value |
| `baseline_sha256` | SHA-256 of canonical baseline JSON |
| `requested` | normalized finite number |
| `risk_tier` | `high` |
| `capability_gate` | `video_visual` |
| `mcp_secret_version` | process-secret/version marker |

Do not reuse `confirm:videoOpacity:v1:`.

## Real-write flow

Real write must:

1. Require exactly one matching `confirm:videoTranslation:v1:` token.
2. Fresh-read and revalidate UUID, type/profile, health/activity, property,
   requested value, and baseline hash.
3. Execute exactly one saved setter:
   `/workspace/{workspace_id}/cue_id/{cue_id}/translation/x` or
   `/workspace/{workspace_id}/cue_id/{cue_id}/translation/y`.
4. Fresh-read the same scalar property.
5. Confirm with numeric tolerance `abs=1e-5`, `rel=1e-6`.

Timeout policy:

- setter timeout + matching readback: `status="updated"` with warning
  `setter_timeout_but_readback_matched`
- setter timeout + missing or mismatched readback: uncertain failure; no
  mutating retry

Rollback requires a new dry-run, fresh baseline, new token, one setter, and
verified readback.

## Explicitly blocked

- `scale/x`, `scale/y`
- crop and aggregate `crop`
- anchor and aggregate geometry
- scalar rotation, quaternion, `rotate/x|y|z`, `resetRotation`
- stage assignment, regions, bounds, routes, warping, guides, control points
- Video FX
- `fileTarget`
- camera patch and video-input patch
- Text `text` and formatting
- `/live`
- playback, GO, Dashboard, raw OSC
- Workspace Video writes
- batch and multi-property writes

Non-translation Video/Camera/Text properties keep current behavior.

## Acceptance tests

- Valid Video/Camera/Text `translation/x` dry-run emits
  `confirm:videoTranslation:v1:` and executes nothing.
- Valid Video/Camera/Text `translation/y` dry-run does the same.
- Candidate metadata sets `real_write_possible=true` and
  `requires_confirm_token=true` only for exact valid candidates.
- Real write executes one axis setter and verifies readback.
- Timeout plus matching readback succeeds with warning.
- Missing/mismatched readback fails uncertain with no retry.
- New-token rollback restores baseline.
- Wrong token family, workspace, cue, profile, property, axis, value, mode, or
  baseline rejects before setter.
- Cue number, `/live`, batch, second property, unhealthy cue, active cue, NaN,
  and infinity reject before setter.
- Phase 3A opacity and non-Video behavior do not regress.

## Runtime validation handoff

After Camera/Text extension and manual MCP restart:

1. Use test workspace `mcp_prueba` and one healthy Camera and Text cue.
2. Capture both translation axes and unrelated visual baseline.
3. Test one axis at a time with dry-run, reviewed token, real write, readback,
   and new-token rollback.
4. Confirm exactly one saved setter per real write.
5. Confirm final baseline and unrelated fields are unchanged.
6. Do not use MCP to start Audition or playback. Use a test workspace, test
   display, and non-show output.
7. Video is already validated; confirm its behavior remains unchanged.

## Next step

Restart MCP, then validate Camera and Text `translation/x` and `translation/y`
using one axis per token and a new token for rollback.
