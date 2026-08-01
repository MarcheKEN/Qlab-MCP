# Utility cue editing research

Status: researched, implementation pending

## Sources

- QLab 5 documentation: [Transport Cues](https://qlab.app/docs/v5/other-cues/transport-cues/), [GoTo Cues](https://qlab.app/docs/v5/other-cues/goto-cues/), [Arm and Disarm Cues](https://qlab.app/docs/v5/other-cues/arm-and-disarm-cues/), [Wait Cues](https://qlab.app/docs/v5/other-cues/wait-cues/), [Memo Cues](https://qlab.app/docs/v5/other-cues/memo-cues/), and [QLab's OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/).
- Local OSC reference: `docs/references/qlab_osc_dictionary.md`.

## Matrix

| QLab readback type | Target | Documented saved target route | Other type-specific saved routes | Policy |
| --- | --- | --- | --- | --- |
| `Start` | cue | `cueTargetID` | none | UUID-only candidate |
| `Stop` | cue | `cueTargetID` | none | UUID-only candidate |
| `Pause` | cue | `cueTargetID` | none | UUID-only candidate |
| `Load` | cue | `cueTargetID` | none; `/load` and `/loadAt` are actions | UUID-only candidate |
| `Reset` | cue, patch, audio map | `cueTargetID`, `patchTargetID`, `audioMapTargetID` | `targetMode` | only cue UUID candidate; patch/map/mode planned-only |
| `Goto` | cue | `cueTargetID` | none | UUID-only candidate |
| `Arm` | cue | `cueTargetID` | none | UUID-only candidate |
| `Disarm` | cue | `cueTargetID` | none | UUID-only candidate |
| `Wait` | none | none | no type-specific OSC setter | Basics-only |
| `Memo` | none | none | no Memo text route; generic `notes` is documented | Basics-only |

For all cue targets, the OSC dictionary documents read/write
`/cue/{cue_number}/cueTargetID {string}`. This server must address it as
`/workspace/{workspace_id}/cue_id/{source_uuid}/cueTargetID`, never by name,
number, selection, playhead, or active cue.

## Safety decision

The saved `cueTargetID` candidate requires one healthy inactive source cue,
one property, saved mode, a fresh readable baseline, an existing non-self
target UUID, a fresh bound confirmation token, fresh readback, and a fresh-token
rollback. `cueTargetNumber`, `cueTargetName`, temporary targets, Reset patch/map
targets, and `targetMode` remain planned-only. No action routes, `/live`, raw
OSC, or playback are in scope.
