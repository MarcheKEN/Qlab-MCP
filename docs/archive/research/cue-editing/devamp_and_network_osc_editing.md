# Devamp and Network OSC safe editing research

Status: 2026-07-13 — runtime evidence recorded; Network `customString` gate enabled.

## Sources checked

- QLab 5 [Devamp Cues](https://qlab.app/docs/v5/other-cues/devamp-cues/)
- QLab 5 [Network Cues](https://qlab.app/docs/v5/networking/network-cues/)
- QLab 5 [OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
- Local `docs/references/qlab_osc_dictionary.md`

## Devamp

- Readback type is `Devamp`; its saved routes are `cueTargetID`, `devampType`,
  `startNextCueWhenSliceEnds`, and `stopTargetWhenSliceEnds`.
- `devampType` accepts only `1` (currently looping slice) or `2` (looping cue).
- A Devamp target must be an existing `Audio` or `Video` cue. It must be
  re-read by exact UUID before a real setter.
- QLab enables `stopTargetWhenSliceEnds` only when
  `startNextCueWhenSliceEnds` is enabled. A one-property gate must therefore
  reject a stop-target edit when Start next is false, and reject turning Start
  next off while Stop target is true.

Safe implementation candidate: one exact-UUID, saved-mode property per call;
healthy inactive source and target; fresh baseline; `confirm:devamp:v1` token;
fresh readback; rollback only through a new dry-run/token to the baseline.

Runtime evidence for Devamp cue `<TEST_DEVAMP_CUE_UUID>`:

- `cueTargetID`: PASS (Audio → Video → Audio; baseline restored).
- `devampType`: PASS (`1 → 2 → 1`).
- `startNextCueWhenSliceEnds`: PASS (`false → true → false`).
- `stopTargetWhenSliceEnds`: PASS using the valid prerequisite sequence
  (`Start next=true`, then `Stop target=true`, then rollback in reverse order).
- Final booleans are both `false`; `devampType` is `1`; target baseline restored.

## Network patch-list evidence

Read-only QLab workspace `<TEST_WORKSPACE_NAME>` (`<TEST_WORKSPACE_UUID>`)
returned these complete patch-list names:

| Patch UUID | Complete name | Detected prefix | Type |
|---|---|---|---|
| `<TEST_PATCH_UUID_1>` | `OSC Message - <TEST_PATCH_SUFFIX_1>` | `OSC Message` | OSC Message |
| `<TEST_PATCH_UUID_2>` | `OSC Message - <TEST_PATCH_SUFFIX_2>` | `OSC Message` | OSC Message |
| `<TEST_PATCH_UUID_3>` | `Plain Text - <TEST_PATCH_SUFFIX_3>` | `Plain Text` | Plain Text |
| `<TEST_PATCH_UUID_4>` | `Hex Codes - <TEST_PATCH_SUFFIX_4>` | `Hex Codes` | Hex Codes |
| `<TEST_PATCH_UUID_5>` | `QLab 5 - <TEST_PATCH_SUFFIX_5>` | `QLab 5` | QLab 5 |
| `<TEST_PATCH_UUID_6>` | `Go Button 3 - <TEST_PATCH_SUFFIX_6>` | `Go Button 3` | Go Button 3 |
| `<TEST_PATCH_UUID_7>` | `d&b DS100 - <TEST_PATCH_SUFFIX_7>` | `d&b DS100` | d&b DS100 |

Every observed name has exactly one stable ` - ` separator and a non-empty
user suffix. The prefix is case-sensitive. Unknown, malformed, or nested
known-prefix names are unclassified. A suffix that imitates another complete
prefix is treated as ambiguous and fails closed.

Network cue mapping (all eight cues were inactive; only cue `13` was healthy):

| Cue UUID | Number/name | Patch UUID | Patch type | Confidence |
|---|---|---|---|---|
| `<TEST_NETWORK_CUE_UUID_1>` | `<TEST_NETWORK_CUE_1>` | `<TEST_PATCH_UUID_1>` | OSC Message | high |
| `<TEST_NETWORK_CUE_UUID_2>` | `<TEST_NETWORK_CUE_2>` | `<TEST_PATCH_UUID_3>` | Plain Text | high |
| `<TEST_NETWORK_CUE_UUID_3>` | `<TEST_NETWORK_CUE_3>` | `<TEST_PATCH_UUID_2>` | OSC Message | high |
| `<TEST_NETWORK_CUE_UUID_4>` | `<TEST_NETWORK_CUE_4>` | `<TEST_PATCH_UUID_1>` | OSC Message | high |
| `<TEST_NETWORK_CUE_UUID_5>` | `<TEST_NETWORK_CUE_5>` | `<TEST_PATCH_UUID_5>` | QLab 5 | high |
| `<TEST_NETWORK_CUE_UUID_6>` | `<TEST_NETWORK_CUE_6>` | `<TEST_PATCH_UUID_6>` | Go Button 3 | high |
| `<TEST_NETWORK_CUE_UUID_7>` | `<TEST_NETWORK_CUE_7>` | `<TEST_PATCH_UUID_1>` | OSC Message | high |
| `<TEST_NETWORK_CUE_UUID_8>` | `<TEST_NETWORK_CUE_8>` | `<TEST_PATCH_UUID_7>` | d&b DS100 | high |

The complete patch-list name is different from the cue-level
`networkPatchName` (which is only `Patch 1`, `Patch 2`, etc.).

## Network OSC Message

- `customString` is the documented read/write route for the cue message.
  QLab uses it for both `OSC Message` and `Plain Text`; it has no effect in
  other patch modes.
- `networkPatchID` identifies a workspace patch, but does not report its mode.
- `/settings/network/patchList` provides complete names whose observed prefixes
  classify the current fixture deterministically.
- Patch-name classification proves the Network patch type only. It does not
  prove that the patch is operationally valid or fully configured.
- `message` and `messageError` are read-only and cannot prove that a cue uses an
  OSC Message patch. Device-description parameters, fade entries, 1D/2D paths,
  and parameter values have mode-dependent semantics and stay planned-only.

Decision: promote only `customString` for cues whose fresh patch-list
classification is exactly `OSC Message`. The token family is
`confirm:networkOscMessage:v1:` and binds the cue, baseline/requested value,
resolved patch UUID, complete name, and classification. `networkPatchID`,
Network fades, parameter values, device-description parameters, patch
definitions, and all non-OSC patch families remain planned-only.

Broken inactive Network cues have a narrower repair-only exception. A single
saved `customString` or `networkPatchID` change requires exact workspace/cue
UUIDs and `confirm:networkRepair:v1:`. `customString` must contain a concrete
OSC address and the current patch must classify as `OSC Message`.
`networkPatchID` must resolve to an existing patch classified as `OSC Message`;
if fresh health readback remains broken, the same call restores only the
original patch UUID bound into the repair token. No other property or cue type
can bypass the normal health gate.

## Runtime

Runtime Network validation used healthy inactive cue `13 / NETWORK_VALID`
without firing a cue. `customString` passed dry-run, token, write, fresh
readback, rollback, and final baseline readback. `networkPatchID` changed from
one patch classified as `OSC Message` to another and read back successfully,
but QLab then marked the cue broken. The existing health gate correctly blocked
the rollback; the cue was later restored manually. This proves classification
does not establish operational patch validity, so `networkPatchID` is
planned-only.
