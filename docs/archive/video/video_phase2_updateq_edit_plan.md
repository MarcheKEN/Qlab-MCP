# Video Phase 2 — UpdateQ Video Edit Dry-run and Gate Design

## Scope

Phase 2 formalizes plan-only Video, Camera, and Text edits through the existing `qlab_update_cues` endpoint.

- Dry-run only.
- No setters or real QLab mutations.
- No `confirm_token`.
- No playback, `/live`, raw OSC, Dashboard, or Workspace Video writes.
- No new public endpoint.

Sources:

- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
- [Video Cues](https://qlab.app/docs/v5/video/video-cues/)
- [Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- `Osc.guia.video.md`
- `docs/references/qlab_osc_dictionary.md`

## Property matrix

Allowed for dry-run only:

| Profiles | Properties | Validation |
|---|---|---|
| Video, Camera, Text | `opacity` | number `0..1` |
| Video, Camera, Text | `translation/x`, `translation/y` | finite number |
| Video, Camera, Text | `scale/x`, `scale/y` | finite number |
| Video, Camera, Text | `anchor/x`, `anchor/y` | finite number |
| Video, Camera, Text | `cropTop`, `cropBottom`, `cropLeft`, `cropRight` | finite number |
| Video, Camera, Text | `blendMode` | existing QLab blend-mode allowlist |
| Video, Camera, Text | `clockType` | `audio` or `video` |
| Text only | `fixedWidth` | non-negative number; `0` means automatic width |
| Text only | `text/format/alignment` | `left`, `center`, `right`, `justify` |
| Text only | `text/format/fontName` | non-empty string |
| Text only | `text/format/fontSize` | positive number |
| Text only | `text` | string; high-risk notice for first-character format inheritance |

All candidates remain `risk_tier="high"` and `real_write_enabled=false`.

Blocked even for dry-run:

- Aggregate `anchor`, `translation`, `scale`, and `crop`.
- `/live` and increment/decrement live forms.
- Stage assignment: `stageID`, `stageName`, `stageNumber`, `stage/name`.
- Regions, bounds, guides, grids, warping, and control points.
- `fileTarget`.
- `videoInputPatchName`, `videoInputPatchNumber`, `videoInputPatchID`, and `cameraPatch`.
- Every `videoEffects/*`, `videoEffect/*`, and `videoEffectIndex/*` mutation.
- `rotation`, `quaternion`, `rotate/x|y|z`, and `resetRotation`.
- Full `text/format`, colors, shadows, underline, and strikethrough.
- Workspace Video, Dashboard, GO/playback, and raw OSC.

## Dry-run contract

Request requirements:

- Explicit workspace UUID.
- Exactly one update item.
- Exact cue UUID as `cue_ref`; cue number is rejected in Phase 2.
- Exact profile: `video_basic`, `camera_basic`, or `text_basic`.
- Exactly one normalized allowed property.
- `dry_run=true`.
- `mode="saved"`; `live` rejected during normalization.
- Empty `confirm_gates`.

Fresh preflight:

1. Read uncached `uniqueID`, `type`, property baseline, and health fields.
2. Require returned UUID to equal requested UUID.
3. Validate profile against cue type.
4. Require cue not broken or active:
   - `isBroken=false`
   - `isRunning=false`
   - `isPaused=false`
   - `isAuditioning=false`
5. Keep warnings blocked in Phase 2: `isWarning=false`.
6. Do not reject `armed=false`; return notice `cue_disarmed`.
7. Normalize requested value with registry validator.
8. Build plan; send no setter.

Response preserves current API:

- `before`: fresh baseline.
- `properties`: normalized request.
- `diff[property] = {before, requested}`.
- Planned setter:
  - workspace-qualified `/cue_id/{uuid}/...` address;
  - `mode="saved"`;
  - `risk_tier`;
  - `real_write_enabled=false`;
  - `real_write_possible=false`;
  - `requires_confirm_token=false`;
  - `planned_only_reason`;
  - `future_gate_requirements`.
- `notices`: includes `cue_disarmed` when applicable.
- `after=null`.
- `executed_operations=[]`.
- No `confirm_token` anywhere in the response.

Reasons:

- Visual/style properties: `video_phase2_dry_run_only`.
- `text`: `video_phase2_text_format_inheritance_risk`.
- Blocked properties: family-specific preflight error and empty plan.

## Implementation

### Phase 2A — Matrix and blocked-property cleanup

- Update Phase 1 planned-only reasons to Phase 2 in `src/qlab_mcp/write/registry.py`.
- Keep only scalar candidates in the Phase 2 allowlist.
- Expand the explicit dry-run blocklist in `src/qlab_mcp/write/operations.py` to every blocked family above.
- Preserve Audio, Light, Fade, and non-video registry behavior.
- Strip the generic registry `confirm_token` from Phase 2 candidate operations before response construction.
- Reject real attempts before OSC, including fabricated `confirm_gates`.
- Treat `armed=false` as notice-only; keep broken, warning, running, paused, and auditioning cues blocked.

### Phase 2B — UpdateQ plan shape

- Reuse current `before`, `properties`, `diff`, and `planned_operations` fields.
- Add `real_write_possible=false`, `requires_confirm_token=false`, and fixed `future_gate_requirements` to Phase 2 setters.
- Requirements:
  - `future_versioned_confirm_token`
  - `single_cue_single_property`
  - `saved_mode`
  - `fresh_baseline`
  - `exact_readback`
  - `manual_rollback_plan`
- For `text`, add `verify_first_character_inherited_format`.
- No changes to `cues/details.py`, `cues/profiles.py`, server schema, or public endpoint unless existing response validation proves this unavoidable.

### Phase 2C — Future gate specification only

Future token design, not implementation:

- Versioned HMAC-SHA256.
- Bound to workspace UUID, cue UUID, profile, property, normalized requested value, mode, and canonical baseline hash.
- Server-held secret; restart invalidates tokens.
- Exactly one cue and one property; saved mode only.
- Baseline reread immediately before setter; hash mismatch rejects.
- Post-write readback:
  - exact equality for strings, enums, and booleans;
  - numeric tolerance `abs=1e-5`, `rel=1e-6`.
- No mutating retry after mismatch or uncertain result.
- Rollback requires a new dry-run, fresh baseline, and new token.
- Phase 2 emits no token and implements no setter.

## Tests

Add parameterized coverage for:

- Every allowed property under every valid cue profile/type.
- Value normalization and correct `before`, `requested`, and `diff`.
- `text` risky reason and future requirement.
- One cue, one property, UUID-only.
- Properties and saved structured-operation forms.
- Batch, second property, and aggregate operations rejected.
- Wrong profile/type rejected.
- Live mode and `/live` rejected.
- Broken, warning, running, paused, and auditioning cues rejected.
- Disarmed cue accepted with `cue_disarmed` notice.
- Every blocked family rejected before mutating OSC.
- `confirm_gates` rejected; no `confirm_token` anywhere.
- Every success and rejection has `executed_operations=[]`.
- Real attempt rejected before OSC, including fabricated token.
- Fresh read uses `cacheable=false`.
- Audio, Light, Fade, and common-property contracts unchanged.
- Full suite green.

Commands:

```bash
.venv/bin/pytest -q tests/test_write_mode.py tests/test_update_registry_coverage.py
.venv/bin/pytest -q
```

## Runtime validation after implementation and MCP restart

Use the expanded video fixture only:

1. Capture read-only baseline.
2. Healthy Text: dry-run each Text candidate separately.
3. Healthy Video: dry-run each visual scalar separately.
4. Healthy Camera: dry-run one geometry scalar.
5. Confirm UUID-qualified address, saved mode, normalized diff, no token, and no execution.
6. Confirm a disarmed healthy cue succeeds with `cue_disarmed` notice.
7. Confirm aggregate, live, stage, patch, file, FX, rotation, and rich-text families fail.
8. Confirm broken, warning, and active cues fail.
9. Re-read every tested cue; require exact baseline equality.
10. Confirm no playback or live-state activity.

## Rollout

1. Phase 2A: scalar matrix, blocklist, token removal, and disarmed notice.
2. Phase 2B: plan metadata and UX.
3. Phase 2C: future-gate test vectors; still no token exposure or writes.
4. Phase 3A: opacity real write only.
5. Phase 3B: translation and scale.
6. Phase 3C: crop.
7. Later: Text style, camera patch, stage assignment, Video FX, Workspace Video, and live control.

## Deferred questions

None block Phase 2.

- Validate `fontName` against QLab `/fontNames` before real writes.
- Define first-character formatting baseline/readback for `text`.
- Recheck blend-mode allowlist against target QLab release.
- Later, UpdateQ may resolve cue number to UUID before dry-run; internal plans must remain UUID-bound.

## First implementation step

Implement Phase 2A in `registry.py` and `operations.py`: scalar-only allowlist, full blocklist, UUID/single-property preflight, token removal, and disarmed notice. Add focused tests before UX metadata.
