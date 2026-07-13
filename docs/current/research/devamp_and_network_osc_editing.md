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

Runtime evidence for Devamp cue `755C11D0-5605-4B8C-B9C1-F4E21F13A138`:

- `cueTargetID`: PASS (Audio → Video → Audio; baseline restored).
- `devampType`: PASS (`1 → 2 → 1`).
- `startNextCueWhenSliceEnds`: PASS (`false → true → false`).
- `stopTargetWhenSliceEnds`: PASS using the valid prerequisite sequence
  (`Start next=true`, then `Stop target=true`, then rollback in reverse order).
- Final booleans are both `false`; `devampType` is `1`; target baseline restored.

## Network patch-list evidence

Read-only QLab workspace `mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`)
returned these complete patch-list names:

| Patch UUID | Complete name | Detected prefix | Type |
|---|---|---|---|
| `64507A1E-9A74-472F-9FB7-FB9FA186C8CC` | `OSC Message - Patch 1` | `OSC Message` | OSC Message |
| `EF908F47-4B52-40A6-BBA1-FBDCAF3E0135` | `OSC Message - Patch 2` | `OSC Message` | OSC Message |
| `7EE87A0B-8C70-4C0C-9100-C406556B241A` | `Plain Text - Patch 3` | `Plain Text` | Plain Text |
| `891EF2EA-1D5E-40DF-8E09-5DA6EDA29294` | `Hex Codes - Patch 4` | `Hex Codes` | Hex Codes |
| `81193623-7334-4FD1-8372-70C6344DCC3C` | `QLab 5 - Patch 5` | `QLab 5` | QLab 5 |
| `DBD55C8B-F13D-4F5C-9E26-1F42BE0C5E1B` | `Go Button 3 - Patch 6` | `Go Button 3` | Go Button 3 |
| `7B635DA0-41C8-44AF-84C5-133D8734C082` | `d&b DS100 - Patch 7` | `d&b DS100` | d&b DS100 |

Every observed name has exactly one stable ` - ` separator and a non-empty
user suffix. The prefix is case-sensitive. Unknown, malformed, or nested
known-prefix names are unclassified. A suffix that imitates another complete
prefix is treated as ambiguous and fails closed.

Network cue mapping (all eight cues were inactive; only cue `13` was healthy):

| Cue UUID | Number/name | Patch UUID | Patch type | Confidence |
|---|---|---|---|---|
| `BA42C1B4-5DDE-44EC-9C49-3A3B295D697D` | `13 / NETWORK_VALID` | `64507A1E-9A74-472F-9FB7-FB9FA186C8CC` | OSC Message | high |
| `8348785F-450A-44B4-9387-85AFAF495AEE` | `33 / (unnamed)` | `7EE87A0B-8C70-4C0C-9100-C406556B241A` | Plain Text | high |
| `9528E894-CACC-4FC3-843D-5A27BE937EC4` | `34 / (unnamed)` | `EF908F47-4B52-40A6-BBA1-FBDCAF3E0135` | OSC Message | high |
| `C0F08400-0778-4872-97F2-25189EE66087` | `35 / (unnamed)` | `64507A1E-9A74-472F-9FB7-FB9FA186C8CC` | OSC Message | high |
| `3BABC765-77DB-4BA8-A087-D5FAAD2F23B9` | `37 / (unnamed)` | `81193623-7334-4FD1-8372-70C6344DCC3C` | QLab 5 | high |
| `4EF0501E-8085-4BD0-9B3D-ABF739B3E119` | `38 / (unnamed)` | `DBD55C8B-F13D-4F5C-9E26-1F42BE0C5E1B` | Go Button 3 | high |
| `DDEFB09D-EAE2-465D-9AC7-85CDC1328B96` | `39 / (unnamed)` | `64507A1E-9A74-472F-9FB7-FB9FA186C8CC` | OSC Message | high |
| `7CC523D5-FF0E-4913-B615-8BF115558691` | `40 / (unnamed)` | `7B635DA0-41C8-44AF-84C5-133D8734C082` | d&b DS100 | high |

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
