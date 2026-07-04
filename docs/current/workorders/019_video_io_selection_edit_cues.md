# Video I/O Selection and Edit Cues

Status: local implementation complete; runtime validation pending after MCP restart.

## Scope

Phase 8A adds cue-level selection of existing I/O targets only. It does not edit
workspace-level stage, patch, route, region, surface, device, or media target
definitions.

Public tool naming now prefers `qlab_edit_cues`. `qlab_update_cues` remains as a
compatibility alias to avoid breaking existing prompts, tests, and clients.

## Sources

- Local QLab OSC dictionary, `docs/references/qlab_osc_dictionary.md`
- `/cue/{cue_number}/stageID {string}`: read/write cue video stage by stage ID;
  unknown strings have no effect.
- `/cue/{cue_number}/audioOutputPatchID {string}`: read/write cue audio output
  patch by patch ID; unknown strings have no effect.
- `/cue/{cue_number}/audioInputPatchID {string}`: read/write cue audio input
  patch by patch ID; unknown strings have no effect.
- `/cue/{cue_number}/videoInputPatchID {string}`: read/write Camera cue video
  input patch by patch ID; unknown strings have no effect.
- `/cue/{cue_number}/cameraPatch {number}` is deprecated in QLab 5 and remains
  blocked.

## Implemented Matrix

| Cue type | Profile | Property | OSC path | Value | Token |
|---|---|---|---|---|---|
| Video | `video_basic` | `stageID` | `/cue/{cue_number}/stageID` | non-empty string ID | `confirm:videoIO:v1:` |
| Video | `video_basic` | `audioOutputPatchID` | `/cue/{cue_number}/audioOutputPatchID` | non-empty string ID | `confirm:videoIO:v1:` |
| Camera | `camera_basic` | `stageID` | `/cue/{cue_number}/stageID` | non-empty string ID | `confirm:videoIO:v1:` |
| Camera | `camera_basic` | `audioOutputPatchID` | `/cue/{cue_number}/audioOutputPatchID` | non-empty string ID | `confirm:videoIO:v1:` |
| Camera | `camera_basic` | `videoInputPatchID` | `/cue/{cue_number}/videoInputPatchID` | non-empty string ID | `confirm:videoIO:v1:` |
| Camera | `camera_basic` | `audioInputPatchID` | `/cue/{cue_number}/audioInputPatchID` | non-empty string ID | `confirm:videoIO:v1:` |
| Text | `text_basic` | `stageID` | `/cue/{cue_number}/stageID` | non-empty string ID | `confirm:videoIO:v1:` |

## Safety Contract

- exact cue UUID only for real writes
- saved mode only
- one cue, one property
- healthy inactive cue
- fresh readable baseline
- fresh dry-run token
- fresh post-write readback must match requested ID
- setter timeout accepted only when readback matched
- rollback requires fresh dry-run token using the baseline ID
- no `/live`, raw OSC, playback/show-control, workspace save, batch, or
  multi-property real write

`stageID` may select an existing stage whose route/device is currently
disconnected. That is allowed because disconnected outputs are common during
prep and tech. When workspace settings expose that state, dry-run and real-write
results surface `stage_route_disconnected` warning metadata: the stage exists,
but QLab may mark the cue broken until the output is connected.

`confirm:videoIO:v1:` authorizes only the implemented I/O ID properties. It does
not authorize Geometry, Appearance, Video FX, Text Style, file targets, or
workspace/stage/patch definition edits. Existing Geometry, Appearance, Reset,
and Video FX tokens do not authorize I/O writes.

## Workspace Validation

QLab docs say unknown IDs have no effect. Phase 8A therefore requires fresh
readback after every real write and reports failure if QLab did not select the
requested ID.

Direct validation against workspace stage/patch ID lists remains future work
because the write path does not yet have a small deterministic resolver shared
with workspace settings reads. That resolver should be added before allowing
name/number convenience writes or unpatch operations.

If a `stageID` write leaves the cue broken, only a narrow recovery rollback is
allowed: same workspace, same cue UUID, same property, saved mode, one cue, one
property, requested value equal to the recorded pre-write baseline `stageID`,
and a fresh `confirm:videoIO:v1:` token. The exception does not permit arbitrary
edits on broken cues or changing a broken cue to a third stage.

## Blocked

- `stageName`, `stageNumber`
- `audioOutputPatchName`, `audioOutputPatchNumber`
- `videoInputPatchName`, `videoInputPatchNumber`
- `audioInputPatchName`, `audioInputPatchNumber`
- `cameraPatch`
- unpatch via `""`, `"none"`, or patch number `0`
- workspace stage/patch/route/region/surface/device definition edits
- file/media targets
- `/live`
- batch/multi-cue and multi-property real writes
- raw OSC/playback/show-control

## Runtime Validation Plan

After MCP restart, validate one healthy inactive `Video`, one `Camera`, and one
`Text` cue. For each implemented property:

1. Read baseline.
2. Dry-run one ID change and require `confirm:videoIO:v1:`.
3. Real write using the fresh token.
4. Fresh readback must match requested ID.
5. Roll back with a fresh token to the baseline ID.
6. Confirm final workspace running/paused/auditioning remains `0/0/0`.

Use exact cue UUIDs only. Do not save workspace.
