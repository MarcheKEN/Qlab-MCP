# Devamp and Network OSC safe editing research

Status: 2026-07-10 — implementation evidence, runtime validation pending.

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

## Network OSC Message

- `customString` is the documented read/write route for the cue message.
  QLab uses it for both `OSC Message` and `Plain Text`; it has no effect in
  other patch modes.
- `networkPatchID` identifies a workspace patch, but does not report its mode.
- `/settings/network/patchList` documents patch identity/name only. Neither the
  local nor official OSC dictionary provides a documented patch-mode/type
  readback that proves `OSC Message`.
- `message` and `messageError` are read-only and cannot prove that a cue uses an
  OSC Message patch. Device-description parameters, fade entries, 1D/2D paths,
  and parameter values have mode-dependent semantics and stay planned-only.

Decision: keep `customString`, `networkPatchID`, Network fades, and
device-description parameters planned-only. Do not infer OSC Message mode from
a patch name, `message`, `messageError`, or an undocumented fixture field.

## Runtime

No QLab runtime write was performed for this phase. Any later validation must
use a test workspace and the baseline → dry-run → token → write → fresh
readback → rollback → final readback sequence without firing a cue.
