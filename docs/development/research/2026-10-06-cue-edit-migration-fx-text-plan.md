# Research to complete editors and remove the generic tool

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Update 2026-10-09: the following analysis retains its original date.
The generic tool and obsolete Python methods have now been removed. Text
UTF-16/percentage/ASCII-word selectors and partial fonts with observed tuples
were verified. Named FX getters can demonstrate the identity of a unique
instance; Gamma/Exposure have defaults and structural changes verified in
5.5.10. Matching keys does not enable writes.
Ambiguous cases, unobserved fonts, non-Latin fallback and partial shadows
remain blocked. [Implementation and evidence](../runtime-validation/2026-10-09-osc-text-fonts-video-fx.md).

Date: 2026-10-06. Research and proposal; **no implementation, API removal or QLab writes**.

## Decision

**The reasonable goal is to remove `qlab_edit_cues` from the public registry after completing migration. It cannot currently be claimed to be redundant.** There are functional and confirmation differences. Nor should its entire catalog be copied into new tools: it contains operations without reliable support or explicitly outside scope.

Removing a public tool does not imply deleting `reader.edit_cues` or the internal engine: `qlab_edit_group_cues` still delegates to that engine (`write/group.py:101–111`). Migrate and verify internal callers first. Removal will be a documented, authorized API change in an implementation phase.

Sources: current checkout, FastMCP registry, local dictionaries, installed SDEF, official manual and Parameter Reference, QClass. Checks in this research: code inspection and local probes with simulated transport/models. **They do not confirm OSC acceptance or effects in QLab 5.5.10.**

## 1. What completing the specific tools means

It does not mean promising every inspector control. It means each permitted operation has:

1. A documented native setter and applicability checked by type.
2. Reliable reading of the previous value and all affected dependencies/effects.
3. Typed input, without free-form paths, ambiguous indices or arbitrary JSON.
4. Batches of 1–50 per family; Control accepts its ten types. Multiple indexed operations require `operations`, not repeated JSON keys.
5. Signed five-minute confirmations, single use, full batch reservation and binding to tool/workspace/cue/operation/baseline/dependencies.
6. Full preflight, one setter per operation, fresh readback, stopping on uncertainty and explicit partial results without rollback or resends.

Schema availability must distinguish permitted, blocked by readback/dependency, awaiting trial and unavailable through the API.

### Verified differences before removing the generic tool

- **Video FX:** the generic tool retains a real gate limited to index 0 and `inputRadius`/`inputIntensity`, one Video cue and one property. Specialized visual editors only have enabled. Migrate/extend parameters before removing this legitimate capability (`operations.py:372–386,4540–4565`). Do not interpret this gate as authorization for any effect with those keys.
- **Group:** Triggers exist through `common`, but are missing in typed Get/Edit Group. The current Group editor also uses the legacy engine/confirmations and limits mode/Playlist to one cue and one property per call.
- **Mixed batch:** the generic tool accepts Basics from different families; specialized family editors do not reproduce a single call of that kind. Splitting by family can solve it; this will be sequential, not a joint transaction. If this convenience is to be retained, implement only a typed Basics facade, not another free-profile tool.
- **`tempDuration`:** it exists in the generic tool and has its own Fade gate, but is a temporary duration that reverts on reset or close/reopen (OSC dictionary:3055–3060). It is not a duration alias or pending persistent editing. Leave it outside this persistent migration and document the loss; a future overrides API would be a separate decision.
- **Aliases and old operations:** review by semantics, not string parity. Modern equivalents do not justify keeping two interfaces.

| Family | Parity comparison result |
|---|---|
| Audio/Mic | Specific editors cover the main legitimate operations and multiple indexed targets; remaining differences include aliases, excluded Audio Maps and weaker validation in the generic tool. |
| Video/Camera/Text | Migrate the Video FX gate; add repeated operations for Levels/slices/FX. Current visual editors accept only one indexed property of each class per cue/call. |
| Group | Get lacks Triggers and the editor lacks Triggers; mode/Playlist are already in the specific editor through an internal wrapper. |
| Control/Devamp/Target | UUID targets and Triggers covered by signed wrappers; do not retain tempTargets/ambiguous fallback numbers as necessary equivalence. |
| Fade | Legitimate Phase1 fields covered; tempDuration is temporary. Captures and FX parameters have no proven executable gap that should be blindly migrated. |
| Light/Network/MIDI/MIDI File/Timecode/Script | Main legitimate operations in specific editors; respect Device Definitions/MSC metadata, LTC capability and the Script source prohibition. |
| Cue Lists/Carts | Timecode settings have `qlab_edit_cue_lists`; its wrapper still uses the generic internal engine. It will not disappear by removing only the public registry entry. |

The remaining nine accept up to 50 typed indexed operations per cue; Visual/Control do not have that additional list. Group/List wrappers still use the legacy engine for some properties; specific signed gates do not automatically convert all their Basics to common signed confirmation.

### Contract finding in the generic tool

`real_write_permission_errors` allows some operations marked gated if the deterministic token matches and a value has been read (`registry.py:1969–1984,2155–2170`). The planned/no-OSC reason does not always prohibit sending.

With the existing `BatchFakeWriteClient`, the researcher obtained a sent setter for `scriptSource`, `audioMapID`, aggregate `sliceMarkers`, `qList` and `playheadID`, as well as Duck. This **proves exposure of the simulated executor**, not that QLab supports those writes. Script source without an OSC setter, excluded Audio Maps and out-of-scope playhead are not capabilities to preserve.

The next implementation must close the shared gate: exclusion reasons and operations without an authorized verifier cannot be enabled by a generic token. Do not globally enable exclusive internal profiles. Retain legitimate setters not yet migrated, with an exact list and rejection tests.

## 2. Video FX: contract and design

### Native coverage

The OSC dictionary documents these saved operations, without `/live`, for Video; Camera and Text explicitly inherit Video FX:

| Operation | Suffix relative to cue UUID | Value/arguments |
|---|---|---|
| Inventory | `videoEffects` | Read the stack used by that cue. |
| Add | `videoEffects/add` | Effect OSC name. |
| Insert | `videoEffects/insert` | OSC name + index. |
| Delete | `videoEffectIndex/{index}/delete` | No arguments. |
| Enable/disable | `videoEffectIndex/{index}/enabled` | Boolean; query without arguments. |
| Reorder | `videoEffectIndex/{index}/move` | New index. |
| Parameter | `videoEffectIndex/{index}/parameter/{key}` | Valid value; query without arguments. |
| Effect parameters | `videoEffectIndex/{index}/parameters` | JSON object string; query returns current names and values. |

Named variants also exist. Avoid them for writes when effects repeat: they address the first match. Indices start at zero. The `/videoEffect/0/parameters` example contradicts the index signature; use `videoEffectIndex/0/parameters`, do not copy that typo. Source: [local OSC dictionary](../../references/qlab_osc_dictionary.md), lines 5183–5274.

No complete catalog endpoint, defaults or type/range metadata was found. `videoEffects` lists instances already in use; `parameters` returns current values, not a schema. The static catalog must come from [Parameter Reference](https://qlab.app/docs/v5/scripting/parameter-reference/), tied to version/evidence.

The complete documented inventory contains **60 OSC names and 262 targets**: 229 numeric, 21 enums, 11 vectors of four floats and one boolean. [Catalog with keys and ranges by effect](2026-10-06-video-fx-parameter-inventory.md). Two effects offer no scriptable parameters; that does not prevent adding or enabling them as instances. The 262 targets were not tested at runtime.

### Do not create one tool per effect

Extend `qlab_edit_video_cues`, `qlab_edit_camera_cues` and `qlab_edit_text_cues` with the same typed FX operations. Keep their names and `properties`; add compatible `operations` for multiple targets. Extend their Gets with optional bounded effect/parameter selectors.

Metadata model: human name, exact OSC name, exact key, type, enum if present, published range, source and validation state. **Select the validator by effect + key.** `inputRadius` does not have the same range in every effect. Reject booleans as numbers and NaN/infinity; distinguish float, integer enum, boolean and vector of four floats. Colors are RGBA; Window/inputRectangle is a rectangle, not a color.

Published ranges are not always absolute limits: QLab documents that some values can exceed them. If MCP chooses to restrict itself to the suggested range, describe this as conservative policy, not a QLab rule. Undocumented defaults and units must remain unknown.

The current specialized `VideoEffect` reader preserves index/name/type/enabled/keys, not a value dictionary; `technical_payload` preserves raw data. The generic summary recognizes scalars and marks arrays as unstable (`cues/visual.py:30–43`, `cues/profiles.py:473–590`, `cues/family.py:318`). Completing reads is part of this implementation.

### Identity, structure and side effects

- An index is not a stable identity after add/insert/delete/move. Token and preflight must include the complete stack, order, type, enabled and affected parameters. Do not invent an effect UUID if readback does not offer one.
- In a first phase, edit parameters/activation of existing effects. Then add structure. For a structural operation, read the complete collection before/after and check exactly the requested change.
- Until every index can be predicted and revalidated, separate add/delete/reorder from index-dependent edits in another dry run. This preserves scope, preventing a plan from executing against the wrong element.
- JSON is transport, not public passthrough: validate every key and value, reject aliases/repeated targets and verify that unrequested parameters remain equal. For compound values, verify the wire format; do not assume a Python list is an equivalent OSC argument.
- Before deleting/reordering, investigate Fade dependencies targeting that cue. A possible change in indexed association is a design hypothesis requiring a trial, not a runtime effect demonstrated here.
- Add/insert require confirmation of resulting type/defaults in fixtures. Delete requires restorable reconstruction of the effect and its parameters for tests; if it cannot be checked, leave that endpoint pending.

### Fade is not completed through inheritance

The manual confirms fading target FX parameters and per-parameter activation checkboxes. No precise OSC path was found for all those checkboxes or for “Set Video FX from Target”. Do not extend add/delete/move to Fade by analogy or declare a functional Fade by writing values alone. [Fading Video & Video Effects](https://qlab.app/docs/v5/video/fading-video/).

QClass Day 2, 4:48:47–4:49:38 explains that order changes the image; 5:08:31–5:12:36 distinguishes final crop from fadeable Shutter/Window. Custom Quartz Composer belongs to the legacy QLab 4 workflow; it is not a plugin extension to implement for QLab 5 Metal (Day 2, 4:46:38–4:48:06).

## 3. Text: full coverage without losing formatting

### Properties and scope

| Group | Contract |
|---|---|
| Content | `/text`: changes the text; new text inherits formatting from the previous first character. It does not preserve mixed text by itself. |
| Size | `fixedWidth` ≥0; zero is automatic. `text/outputSize` is a read; no direct height setter was found. |
| Alignment | left/center/right/justify; all text shares alignment according to the manual. Do not promise different alignment by fragment. |
| Font | `fontName` or a `fontFamilyAndStyle` pair; separate fontFamily and fontStyle are reads. |
| Styles | Size, lineSpacing, text/background/shadow/underline/strikethrough RGBA; shadow blur/offset; none/single/double underline/strikethrough style. |
| Partial formatting | `/text/format` JSON with optional `range`; attribute setters support range or word variants where documented. |
| Shared visual properties | Stage, Geometry and FX remain in the Text editor; formatting does not replace these sections. |

Source: local OSC dictionary:5314–5525; [Text Cues](https://qlab.app/docs/v5/video/text-cues/). For shadows, the partial variant only works when indexing the first character/word of a line, counting returns as well. Do not treat it as arbitrary styling of an interior letter.

### Current state and pending work

Get returns fragments and summarizes eight optional attributes only if every run includes them and they match. Missing/mixed is `null`, not a default. The global writer requires a uniform baseline; therefore it rejects a cue with two sizes when asked for a global fontSize change (`write/visual.py:301–320`). This is a writer limit, not an absent range setter.

Add typed formatting operations to `qlab_edit_text_cues`, with an explicit selector: entire text, range or word. The operation set must cover documented variants; percentages and `length=-1` require deterministic resolution against the baseline, not interpretation with shifting positions.

Preservation requirements:

1. Complete snapshot of text and runs before authorization; preserve all attributes, including unknown ones in reads, without offering them as free-form setters.
2. Consider `raw_attributes` in Get or a model with read extras: a local probe confirms that current `TextRun` **discards unknown attributes** when serializing. Technical raw data does preserve them. Do not reconstruct a snapshot from modeled properties alone.
3. Verify the requested range and unrelated regions. QLab can merge/split equivalent runs: compare effective formatting by intervals, without requiring an identical run count/partition.
4. Do not assume the Unicode unit: `A😀B` has 3 Python characters and 4 UTF-16 units. The OSC dictionary says “characters”, without resolving that unit. Test emoji, combining characters, CR/LF and line breaks; publish OSC coordinates, not invented Python offsets.
5. OSC starts at 0; AppleScript `rangeOffset` and `wordIndex` start at 1. Never share offsets directly.
6. A missing attribute cannot be restored by pretending it had its default. Find deletion/normalization semantics or block that write when no reliable baseline/restoration exists.
7. Font by name versus pair, repeated/overlapping ranges and text + formatting requests must have explicit rules. First separate content replacement and formatting with a new dry run; enable combination when the state after `/text` can be predicted.
8. Global alignment and per-line shadows must state that scope and verify the entire affected set.

The documentation permits mixed styles; QClass does not specify indices or run preservation. QClass Day 3, 5:54:54–5:55:43 even distinguishes Text batch UI: individual programmatic editing by cue is not a literal reproduction of that UI multiselection.

## 4. Group Triggers, explained

These are **settings in a Group cue's Triggers tab**, not a new cue class or firing its children. For example: how much it ducks other cues, Fade & Stop scope, the action configured for a second trigger or saved Timecode time.

Today `qlab_edit_group_cues` models Basics, mode and four Playlist settings. It does not have these Triggers; `GroupCueDetailsResult` has no `triggers` section either (`write/group.py:13–38`, `cues/light_group.py:72–87`). The generic tool does offer a common path. Migrate it rather than discovering setters from scratch.

Proposed implementation:

- Add Trigger reads and capabilities to Get Group.
- Reuse current common properties and signed engine; common Second Trigger 0–5 and 6–7 only when mode=6 Playlist is confirmed.
- Configuring saved Play Next/Previous does not execute the command; do not add a playback navigation tool.
- Validate Timecode against the containing list and frame/drop-frame. Having a time does not mean activating the trigger.
- Fade & Stop requires an exact integer 0–3; a boolean does not authorize a scope change.
- Avoid mode + dependent Trigger in the same batch until the full transition is verified. Moving from Playlist to another mode with an exclusive action requires explicit resolution.
- QClass Day 1, 2:55:38–2:57:10 notes that Timeline/Playlist can remove continue/follow from children. Read children/dependencies when changing mode or moving them; do not treat mode as a scalar without side effects.

## 5. AppleScript, explained

It is a second native interface for properties OSC does not expose, managed by the server. **It does not mean creating or executing a Script cue.** A fixed external script that reads or sets `load time` is infrastructure; writing a cue's `script source` recompiles and remains out of scope.

| Phase | Extension | Precondition |
|---|---|---|
| Reading | Load Time, Target assigned number, Trigger fields and document path/modified. | Exact QLab/TCC available, UUID identity checked and typed getters. |
| Bounded editing | Load Time; Target Cue Number; MIDI/Wall Clock/Timecode configuration without signal activation. | Reliable baseline, resolved dependency and token with backend. |
| Separate activation | MIDI/Wall Clock/Timecode/Hotkey checkbox and Fade & Stop scope. | Isolated trial: activation permits future execution through an external signal, even if MCP does not send GO. |
| Lifecycle | Open/save/close existing documents. | Exact path, modified state and policy for saving/preserving changes. No implicit discard. |

Details:

- Target `assigned number` does not change Basics number: it indicates which cue will become the receiving cue's new target. Resolve the number to exactly one UUID in the same workspace and bind the token to both target levels; duplicate numbers cannot serve as an unambiguous destination.
- No native assignment of Hotkey keys/modifiers, Wall Clock weekdays or MIDI `greater/less/any` grammar was found. Display strings do not prove that syntax can be written.
- MIDI byte one/byte two are integer in the installed SDEF; the documentation import disagrees on byte one. Validate against the installed version. MIDI Trigger does not include pitch_bend; channel 0 means workspace default and -1 any channel.
- Triggers inherit from cue, but not all types accept every property. A failed getter blocks; do not infer from inheritance.
- Standard Suite `open/save/close` does not provide documented creation of a new workspace. Do not confuse make cue with make workspace.

Minimum backend: fixed AppleScript templates with an allowlist of properties and values passed as arguments, without free-form scripts or shell interpolation; exact app path; UUID selection, not front workspace; structured results. Reuse engine and codec, add backend binding. No OSC→AS fallback after a setter or retry of an Apple Event timeout.

Sources: local AppleScript dictionary, Load:2732; Target:3149; cue:2253–2325; text format:3216,3776–3784,3905. Installed SDEF at `/Applications/QLab.app/Contents/Resources/QLab.sdef`. [Official AppleScript dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/).

## 6. Implementation order and acceptance

1. **Generic contract:** close out-of-scope paths; produce a real parity matrix. Do not remove it yet.
2. **Group:** Get/Edit Triggers, full migration of the legacy wrapper to signed confirmation and mode/child change tests.
3. **Existing FX:** parameter reads and catalog by type; multiple typed operations in Video/Camera/Text; migrate the historical parameter gate.
4. **Text:** ranges and complete snapshot, Unicode and global/line scope; extend to documented words/percentages after resolving their semantics.
5. **FX structure:** add/insert/delete/move, defaults and Fade dependencies; keep non-restorable/unverifiable operations pending.
6. **Public removal:** when legitimate functions have migrated and the mixed-batch loss is decided; remove public registry/export, update guide/CHANGELOG and absence regression. Keep private engine if callers remain.
7. **AppleScript:** reads first; then specific properties; activations and lifecycle in explicit phases.

One tool per effect or UI gesture is unnecessary. Nor is there a need to add renumbering/relative-copy tools if composing Get + Edit already solves the case.

### Tests required for implementation

- Registry `Client(mcp).list_tools()`: types, limits, operations and absence of passthrough; removal only when appropriate.
- Generic gate: a token does not authorize Script source, Audio Maps, `/live`, navigation or unverified setters.
- FX: enum/bool/float/RGBA, nonexistent parameters and the same name with different ranges; duplicate stack; changed index; add/delete/reorder and neighbor preservation; timeout without resend.
- Text: mixed/missing baseline, unknown attributes preserved, merged runs, Unicode/CR/LF, invalid word/range, per-line shadows, missing fonts and dependent content+formatting.
- Group: Second Trigger 6–7 in Playlist and rejection in other modes, mode/dependency change, child continue/follow, boolean Fade & Stop readback, Timecode list.
- Tokens: expiry, consumption, signature, tool/backend change, baseline/dependencies and full reservation; preflight error without setter; intermediate failure with pending operations.
- AS: text/quotes/newlines through argv without injection, missing TCC/app, invalid return, wrong UUID/type, timeout with readback; no mutating fallback.
- In QLab 5.5.10: authorized fixtures, verified path/UUID/Edit Mode/inactivity; baseline → dry run → single setter → fresh readback → UI cross-check → restoration with a new token. No GO/Preview/Send or external signals.

This phase did not execute the implementation suite or new runtime writes. Those tests are gates for the proposed work, not results already obtained.

### Automated research evidence

The source researcher ran, without a QLab connection:

```sh
PYTHONPATH=src .venv/bin/python -m pytest -q tests/test_write_mode.py -k 'video_fx_phase4c_real_write_updates_single_flat_input_radius or fade_phase1_all_shared_basics_emit_only_fade_basic_token or edit_cues_batch_dry_run_allows_mixed_profiles or group_mode_reviewed_token_writes_and_reads_back'
```

Result: **18 passed, 2264 deselected in 0.26s**, exit 0. These are existing focused simulated-transport regressions, not tests of every property or a live trial. The `.venv/bin/pytest` binary retains a shebang from the old checkout; using the current interpreter with `-m pytest` avoids that obsolete path without modifying the environment.

The parent locally verified that TextRun removes unknown extras when serializing, that `A😀B` differs in Python/UTF-16 length, and that the inventory has 60 unique names/262 unique targets by effect, with the published type counts. Local links, whitespace in both reports and `git diff --check` were checked. These checks do not replace the proposed runtime gates.

## Implementation outcome and runtime check

- Explicit authorization before legacy gates; tokens do not enable exclusions.
- Group Triggers and Cue Lists migrated to the signed engine; revalidation of
  mode, children, Second Trigger and aggregate Timecode between each setter.
- Generic API removed; private engine retained. UUID replaces number;
  mixed families are split. TempDuration never becomes duration.
- FX catalog and operations/selectors integrated. Real OSC inventory in the
  fixtures contains parameters only, without type: identity and structure blocked.
- Text preserves extras and compares intervals. ASCII/range/to-end checked.
  Unicode uses UTF-16 in the observation, but the emoji triggers unpredictable
  font fallback; verification fails closed and restoration was checked.
  Unicode/percentages/words/fonts/partial shadows remain pending.
- Evidence: [runtime](../runtime-validation/2026-10-06-editor-migration.md).
