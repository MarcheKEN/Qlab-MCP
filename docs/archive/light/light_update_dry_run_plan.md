# LIGHT PLAN Phase 3 — LCL analysis in dry-run

Date: 2026-06-19

## 1. Executive summary

Phase 3 integrates the internal helper `analyze_light_command_text(command_text, light_patch)` into `qlab_update_cues` `dry_run` planning for `profile=light_basic` updates to `lightCommandText`.

The plan reads the cue, confirms that it is a Light cue, retrieves the `safe` Light Patch, analyzes the new text, and attaches results plus a summary of affected instruments/parameters. No setters are sent. Every `lightCommandText` update remains blocked in real mode during this phase, even with `confirm_token`.

Official references: [Light Cues](https://qlab.app/docs/v5/lighting/light-cues/), [Lighting Command Language](https://qlab.app/docs/v5/lighting/lighting-command-language/), and [OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/).

## 2. Current update flow

`QLabReader.update_cues`:

1. Normalizes the batch, profile, properties, and allowed operations.
2. Binds confirmation tokens.
3. In `dry_run`, resolves `workspace_id` and reads current values through `update_safe`.
4. Validates that `light_basic` applies only to a Light cue.
5. Builds `before`, `after`, `diff`, and `planned_operations`.
6. Always returns `executed_operations=[]`.

The registry already includes `lightCommandText` in `light_basic` as a plannable setter with `read_key=lightCommandText`, high risk, and real writing disabled.

## 3. Exact analysis point

The helper is called only in the `dry_run` branch, after `_try_read_update_values` and `_validate_profile_for_before`, and before `_batch_item_result`.

Conditions:

- The normalized operation contains `property=lightCommandText`.
- The cue read produced no errors.
- The profile confirmed a Light cue type.

The Light Patch is obtained with `_get_workspace_setting_details_single(..., section="light", kind="light_patch", profile="safe")`, using the already-resolved explicit `workspace_id`. It is loaded lazily once per batch and reused for all LCL operations. Other `light_basic` setters do not read the patch.

## 4. Proposed and implemented response

The planned setter preserves the existing `before`, `after`, and `diff`, and adds:

```json
{
  "operation": "set_property",
  "property": "lightCommandText",
  "risk_tier": "high",
  "real_write_enabled": false,
  "real_write_possible": true,
  "requires_confirm_token": true,
  "planned_only_reason": "light_command_real_write_not_enabled",
  "confirm_token": "...",
  "light_command_analysis": {
    "availability": "available",
    "overall_status": "valid",
    "line_count": 1,
    "analyzed_count": 1,
    "status_counts": {
      "valid": 1,
      "warning": 0,
      "invalid": 0,
      "unsupported": 0
    },
    "affected_instruments": ["Front"],
    "affected_parameters": ["intensity"],
    "affected_pair_count": 1,
    "skipped_member_count": 0,
    "results": []
  }
}
```

`results` contains the helper's complete per-line output. The summary deduplicates instrument/parameter pairs and does not calculate look, fade, collation, Dashboard, or DMX.

## 5. Risk and gates

| Overall result | Dry-run | `real_write_possible` | Reason |
| --- | --- | ---: | --- |
| `valid` | OK | `true` | `light_command_real_write_not_enabled` |
| `warning` | OK with warning | `true` | `light_command_real_write_not_enabled` |
| `invalid` | OK with warning | `false` | `light_command_analysis_failed` |
| `unsupported` | OK with warning | `false` | `unsupported_light_command_syntax` |
| `unavailable` | OK with warning | `false` | `light_command_analysis_unavailable` |

Decision: warnings do not add a separate gate. The per-line result and summary must be reviewed, but a future write would use the normal gates and `confirm_token`. Avoiding a second mechanism reduces states and preserves the current contract.

During Phase 3, `real_write_possible=true` means only that the analysis found no semantic block. It does not enable writing. `real_write_enabled` remains `false`, and real preflight always rejects `lightCommandText`, even when it receives the token issued by dry-run.

For `invalid`, `unsupported`, or `unavailable`, `confirm_token` is omitted.

## 6. Error handling

- Patch read/normalization failure: `unavailable` analysis, code `light_patch_read_failed`.
- Internal helper exception: `unavailable` analysis, code `light_command_analyzer_failed`.
- Missing cue, failed read, or non-Light type: preserve existing preflight; do not read the patch or run the helper.
- Empty patch: the helper returns invalid targets; dry-run remains inspectable.
- Batches: at most one patch read; a shared failure is represented per operation.

Analysis failures do not crash or become setters. `executed_operations` remains empty.

## 7. Tests

Implemented coverage:

- Valid analysis attached with `before`/`after`/`diff`, high risk, and token.
- Warning result retains future possibility and token.
- Invalid and unsupported block future possibility, change the reason, and omit the token.
- Patch read occurs only once for multiple cues in the batch.
- Patch failure and helper exception are non-fatal.
- A Light setter other than `lightCommandText` does not read the patch.
- Invalid profile/type does not reach analysis.
- A real attempt with a token fails in preflight before any OSC.
- The pure helper unit suite covers the MVP grammar and unsupported cases.

## 8. Out of scope

- Public MCP tool for analyzing LCL.
- Integration into `qlab_get_cue_details`.
- Expanding the LCL grammar.
- Executing `lightCommandText` setters.
- `safeSort`, `prune`, `replace`, or other real operations.
- Dashboard, live lighting, raw OSC, GO, playback, start, stop, panic, audition, or preview.
- Modifying the patch, instruments, groups, definitions, or DMX addresses.

## 9. Recommended next steps

1. Keep Phase 3 in dry-run until responses are validated against varied real patches.
2. Review warnings and observed unsupported syntax before expanding the grammar.
3. Design deterministic post-write verification for `lightCommandText`.
4. Only then decide whether to enable real writing after the normal gates and token.
