# LIGHT PLAN Phase 4A — limited `lightCommandText` write

## 1. Scope

Phase 4A enables one mutation only: update `lightCommandText` on one cue of exact type `Light` through `qlab_update_cues` with `profile="light_basic"`.

The repository's OSC dictionary documents `/cue/{cue_number}/lightCommandText {string}` as read/write. The implementation uses its stable workspace-qualified variant: `/workspace/{workspace_id}/cue_id/{cue_unique_id}/lightCommandText`.

It adds no MCP tools. It does not enable Dashboard, playback, raw OSC, the Light Patch, or other Light setters.

## 2. Confirmable dry-run

A dry-run produces a Phase 4 candidate only when:

- `light_command_analysis.overall_status == "valid"`;
- requested text is non-empty;
- the current baseline is a string;
- the cue has a resolved `uniqueID`.

Resulting operation:

```json
{
  "property": "lightCommandText",
  "risk_tier": "high",
  "real_write_enabled": false,
  "real_write_possible": true,
  "requires_confirm_token": true,
  "phase4_real_write_candidate": true,
  "planned_only_reason": "light_command_requires_valid_analysis_and_confirm_token",
  "confirm_token": "confirm:lightCommandText:v1:..."
}
```

`real_write_enabled=false` prevents bypassing the general registry. Only the specialized Phase 4 flow accepts the token.

Empty text may analyze as `valid`, but is not confirmable: `phase4_real_write_candidate=false`, `real_write_possible=false`, no token, and reason `empty_light_command_text_not_writeable`.

`warning`, `invalid`, `unsupported`, and `unavailable` states also generate neither a token nor a real-write path.

## 3. Exact real preflight

If any item mentions `lightCommandText`, the entire call is subject to Phase 4 rules:

1. Explicit, resolvable workspace.
2. One item only.
3. `profile="light_basic"`.
4. One property/operation: `lightCommandText`, identical path, and `saved` mode.
5. Exactly one reviewed `confirm_token`.
6. Normal readiness: writes enabled, passcode, `edit` scope via `/connect`, and QLab Edit Mode (`showMode=false`).
7. Cleared read cache; fresh type, `uniqueID`, and baseline read.
8. Exact type `Light`.
9. Fresh safe Light Patch read; requested text re-analyzed and still `valid`.
10. Valid token signature and context.
11. Fresh baseline hash matches the signed hash. If it changes: `stale_light_command_baseline`; zero setters.
12. One setter for the `cue_id`.
13. Cleared cache and fresh readback. Success requires exact equality with the requested string.

Readback mismatch returns `verification_failed`, including `requested` and `after`. Any failure before the setter leaves `executed_operations=[]` for the item.

## 4. Token

Self-contained HMAC-SHA256 token with a per-process random secret. Payload:

- `version=1`;
- `operation_kind="phase4_light_command_text_write"`;
- `workspace_id`, `cue_ref`, `cue_id`;
- `profile`, `property`, `path`, `mode`;
- SHA-256 of the baseline and requested value;
- `risk_tier`, `capability_gate`, `analysis_status="valid"`.

It contains no plaintext LCL text. Restarting the MCP changes the secret and invalidates previous tokens. Tokens are not single-use within the same process. Rollback always requires reading the current baseline, running a new dry-run, and using a new token.

## 5. Blocked operations

- `alwaysCollate`, `subcontroller`, `collateAndStart`;
- `setLight`, `replaceLightCommand`, `removeLightCommandsMatching`;
- `safeSort`, `safeSortCommands`, `prune`, `pruneCommands`;
- batch or mixing with additional properties;
- Dashboard/live lighting;
- GO, playback, start, stop, panic, audition, preview;
- raw OSC;
- changes to the Light Patch, instruments, groups, definitions, or DMX.

## 6. Fake-client test matrix

| Case | Expected result |
|---|---|
| Valid/non-empty dry-run | High-risk candidate and token |
| Valid write | One setter; exact readback |
| Rollback | New dry-run and token; baseline restored |
| Empty/warning/invalid/unsupported/unavailable | No token or real path |
| Non-Light, missing cue, patch/read failure | Preflight blocked; zero setters |
| Two items or additional property | Entire call blocked before OSC |
| Other Light setter | Remains dry-run only |
| Malformed token, invalid signature or version | Blocked |
| Different workspace/ref/cue/request/context | Blocked |
| Stale baseline | `stale_light_command_baseline`; zero setters |
| Different readback | `verification_failed` with requested/after |
| No edit scope or Show Mode | Blocked before setter |
| Observed addresses | No Dashboard, playback, or OSC without a workspace |

## 7. Phase 4B runtime protocol — not executed

Use only `<TEST_WORKSPACE_NAME>` after identifying its explicit UUID. Choose an isolated, disarmed Light Cue. Do not use show cues, Dashboard, or playback.

1. Confirm connection, workspace UUID, Edit Mode, and `edit` scope.
2. Read the cue and save its `uniqueID`, type, and original `lightCommandText`.
3. Read the safe Light Patch. Abort if the patch is empty, the read is partial, or the test target does not exist.
4. Run a dry-run with a minimal valid, non-empty change.
5. Review the analysis, diff, baseline, `phase4_real_write_candidate`, and token.
6. Make exactly one real call with the same workspace/cue/property/value and token.
7. Verify `updated`, one setter, and exact readback.
8. For rollback, run a new dry-run from the current value to the original text. Review the new token.
9. Execute one rollback and verify the exact original readback.
10. On any mismatch, do not retry the write; record the response and stop.

Exact Phase 4B prompt:

```text
Use only read-only MCP tools except for the two explicitly described `qlab_update_cues` calls. Work only in <TEST_WORKSPACE_NAME> using its explicit workspace_id UUID. Do not use GO, playback, start, stop, panic, audition, preview, Dashboard, or raw OSC. Identify an isolated, disarmed Light Cue; read and preserve its original lightCommandText. Read the safe Light Patch and abort if it is empty/partial or does not offer a valid simple target. Run `dry_run=true` to change only lightCommandText to a minimal valid, non-empty command. Review overall_status=valid, phase4_real_write_candidate=true, diff, baseline, and confirm_token. If everything matches, make exactly one real `qlab_update_cues` call with one item, profile=light_basic, only lightCommandText, and that token. Verify one setter and exact readback. Then create a new dry-run from the current value to the original text, obtain a new token, and execute one rollback. Verify the exact original readback. On any error, stale baseline, invalid analysis, or mismatch, make no further writes and report it. Do not change any other cue, patch, instrument, group, definition, or DMX address.
```

Phase 4B is not part of this delivery and has not been executed.
