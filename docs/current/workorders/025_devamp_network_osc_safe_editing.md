# 025 — Devamp and Network OSC safe editing

Status: active

## Scope

- Add narrow, token-gated saved configuration edits for `Devamp` cues.
- Keep Network OSC Message editing planned-only until a documented patch-mode
  readback exists.

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

## Explicitly blocked

- Network patch definitions, destination/protocol/passcode/device descriptions.
- `customString`, `networkPatchID`, Network fades and parameter values until
  OSC Message mode can be verified from documented readback.
- MIDI, MIDI File, Timecode, Script, raw OSC, `/live`, playback, and save.

## Runtime plan

Do not execute a cue. If a connected test workspace is explicitly approved,
validate one saved property at a time with baseline → dry-run → token → write
→ fresh readback → rollback → final readback.
