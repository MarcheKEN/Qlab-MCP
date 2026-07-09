# Video Phase 3F + 4A/4B — Text Style and Video FX Planning

Status: local implementation revised after runtime validation gaps.

Source: `docs/references/qlab_osc_dictionary.md` for QLab 5.

## Phase 3F support matrix

Decision: blocked. QLab 5.5.10 did not return reliable fresh baselines for the
candidate Text Style keys during runtime validation. Phase 3F must not emit
`confirm:textStyle:v1:` tokens and must not send setters until exact fresh
readback is proven.

| Property | OSC read/write | Validation | Readback |
|---|---|---|---|
| `text/format/shadowBlurRadius` | documented scalar RW | finite number `>= 0` | unavailable in runtime validation |
| `text/format/shadowOffset/width` | documented scalar RW | finite number | unavailable in runtime validation |
| `text/format/shadowOffset/height` | documented scalar RW | finite number | unavailable in runtime validation |
| `text/format/underlineStyle` | documented enum RW | `none`, `single`, `double` | unavailable in runtime validation |
| `text/format/strikethroughStyle` | documented enum RW | `none`, `single`, `double` | unavailable in runtime validation |

Current behavior:

- dry-run rejects with a clear baseline/readback unavailable reason;
- no confirm token is emitted;
- real write rejects before any setter;
- `executed_operations=[]`;
- Phase 3E Text Basics have since been expanded locally; see
  `023_text_cue_safe_editing.md`.

## Phase 3F deferred properties

Still blocked in this Phase 3F bucket:

- `text/format/fontFamilyAndStyle`: installed-font pair identity and exact
  canonical readback need runtime proof.
- aggregate `text/format` and aggregate `shadowOffset`: multi-field/rich
  payloads are outside the single-property gate.
- substring/word variants, `/live`, increment/decrement, and independent
  bold/italic controls.

Moved out of this blocked bucket into local Text Basics expansion pending
runtime validation: `fixedWidth`, `text/format/fontName`,
`text/format/lineSpacing`, and the five RGBA routes.

No Video or Camera Text Style real write is enabled.

## Phase 4A — Video FX read model

`inspector_safe` keeps the existing lightweight `video_summary.video_fx` and
adds only:

- effect index/name/enabled when present;
- raw effect key names;
- scalar parameter key, value, semantic kind, readback stability, documented
  write-path availability, dry-run candidacy, and risk.

Complex parameter values are classified but not copied into the safe summary.
Technical/exhaustive profiles continue to expose the original `videoEffects`
payload unchanged.

QLab's dictionary guarantees that `videoEffects` returns a list, but does not
guarantee that the aggregate contains enabled state or parameter dictionaries.
Runtime on QLab 5.5.10 returned flat effect payloads such as
`{"inputPower": 1}` and `{"Choose_Effect": 0, "inputIntensity": 2.6,
"inputRadius": 10}`. Phase 4A now preserves raw payloads in technical profiles
and summarizes flat keys as parameter-like fields while explicitly reporting
missing identity, type, or enabled state.

## Phase 4B — Video FX dry-run planner

Default remains dry-run only; no token and no setter:

- `videoEffect/enabled`
- `videoEffectIndex/enabled`
- `videoEffect/parameter`
- `videoEffectIndex/parameter`

Requirements:

- one Video/Camera/Text cue and one operation;
- exact cue UUID and saved mode;
- healthy inactive cue;
- effect resolves by exact OSC name or zero-based index;
- duplicate names require index addressing;
- enabled baseline is boolean; or parameter exists in the fresh aggregate/flat
  payload and
  current/requested values share the same finite numeric, boolean, or string
  type.

Output uses the additive `updateq_plan.video_fx` summary with cue/effect,
expected setter/readback addresses, before/requested values, high risk,
`planned_only=true`, and `will_modify_qlab=false`.

Still blocked even for planning: add, insert, delete, move, aggregate parameter
JSON, unknown effects/parameters, and complex parameter values.

Phase 4C adds one local-only exception after this planner: `Video`
`videoEffectIndex/0/parameter/inputRadius` can become a
`confirm:videoFxScalar:v1:` candidate when the fresh flat payload baseline is a
finite number. All other Video FX real writes remain blocked.

## Local validation

Covered by reader/write tests:

- all five Text Style candidates reject without token or setter because
  baseline/readback is unavailable in QLab 5.5.10;
- malformed/batch/wrong-type Text Style requests reject before mutation;
- Video FX enabled and most scalar-parameter plans emit no token and execute
  nothing;
- Phase 4C flat `Video` `inputRadius` by index emits a token and can execute
  only with that fresh token;
- flat Video FX payloads are summarized and scalar flat parameters can produce
  planned-only dry-runs by index;
- unknown or complex FX parameters reject;
- inspector summaries stay lightweight while exhaustive raw data remains.

## Runtime validation after restart

Use only the test workspace. Do not use playback, GO, audition, `/live`, raw
OSC, Dashboard, Workspace Video writes, or save.

1. Recheck each Phase 3F property on one healthy Text cue. Expected current
   result: no token, no setter, baseline/readback unavailable reason.
2. If a future QLab version returns reliable baselines, redesign the gate before
   enabling real writes.
3. Probe fake/cross-property tokens, cue number, batch, multi-property,
   wrong type/profile, active/broken cue, and blocked style families.
4. Validate Phase 4A/4B read and dry-run output only. Confirm no Video FX setter,
   token, or baseline change.
