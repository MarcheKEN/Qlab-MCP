# 025 — Devamp and Network OSC safe editing

Status: runtime validation complete; Network patch reassignment demoted

## Scope

- Add narrow, token-gated saved configuration edits for `Devamp` cues.
- Enable only Network OSC Message edits after exact complete-name prefix
  classification from `settings/network/patchList`.

## Devamp gate

- Exact source cue UUID, one cue, one saved property, no `/live`.
- Properties: `cueTargetID`, `devampType`,
  `startNextCueWhenSliceEnds`, `stopTargetWhenSliceEnds`.
- Source and target must be healthy/inactive; target must be exact existing
  `Audio` or `Video`, never self.
- Token binds workspace, source/type/profile/property, baseline, requested
  value, target UUID/type, and dependent Start next/Stop target state.
- A real write requires a fresh dry-run token and fresh readback. Rollback is a
  separate baseline dry-run with a new token.

## Network patch classifier

Observed exact prefixes: `OSC Message`, `Plain Text`, `Hex Codes`, `QLab 5`,
`Go Button 3`, and `d&b DS100`, each followed by ` - ` and a non-empty suffix.
Classification is case-sensitive and fail-closed for unknown, malformed, or
nested/ambiguous prefixes.

## Network OSC Message gate

- Token: `confirm:networkOscMessage:v1:`.
- Promoted property: `customString` only.
- Fresh patch-list read must resolve the current patch UUID and classify it
  exactly as `OSC Message`.
- Token binds workspace, cue, property, baseline/requested value, patch UUID,
  complete name, and classification.
- Patch-name classification proves patch type, not operational validity or
  complete configuration.

## Broken Network repair gate

- Token: `confirm:networkRepair:v1:`.
- Exact workspace UUID, exact Network cue UUID, one inactive broken cue, one
  saved property, and no `/live`.
- `customString` requires a current `OSC Message` patch and a concrete valid
  OSC address/message.
- `networkPatchID` requires a fresh patch-list match classified as
  `OSC Message` immediately before writing.
- Fresh readback includes the changed value, `isBroken`, `isWarning`, `message`,
  and `messageError`.
- If patch reassignment leaves the cue broken, restore only the original
  `networkPatchID` baseline signed into the repair token.
- The normal broken-cue gate remains unchanged for every other property and
  cue type.

## Explicitly blocked

- Healthy-cue `networkPatchID`, Network patch definitions,
  destination/protocol/passcode/device descriptions.
- Network fades and parameter values remain planned-only.
- MIDI, MIDI File, Timecode, Script, raw OSC, `/live`, playback, and save.

## Runtime result

`customString` completed baseline → dry-run → token → write → fresh readback →
rollback → final readback. A `networkPatchID` change between two patches
classified as `OSC Message` read back successfully but made the cue broken.
The health gate correctly refused the rollback, and the cue was restored
manually. Keep `networkPatchID` planned-only; do not weaken the broken-cue gate.
