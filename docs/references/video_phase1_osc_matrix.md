# Video Phase 1 OSC Matrix

QLab 5 reference classification for Video, Camera, Text, and Workspace Video.
Canonical route source: `docs/references/qlab_osc_dictionary.md`.
Runtime coverage remains generated from the dictionary; this matrix records Phase 1 safety decisions.

| Area | Property | OSC path | Read | Write | Live | +/- | Deprecated | MCP status | Risk |
|---|---|---|---|---|---|---|---|---|---|
| Video/Camera/Text | opacity | `/cue/{cue_number}/opacity` | yes | yes | yes | yes | no | Phase 2 dry-run; Phase 3A gated real write | high |
| Video/Camera/Text | translation axis | `/cue/{cue_number}/translation/x`, `/translation/y` | yes | yes | yes | yes | no | dry-run only | high |
| Video/Camera/Text | scale axis | `/cue/{cue_number}/scale/x`, `/scale/y` | yes | yes | yes | yes | no | dry-run only | high |
| Video/Camera/Text | anchor axis | `/cue/{cue_number}/anchor/x`, `/anchor/y` | yes | yes | yes | yes | no | dry-run only | high |
| Video/Camera/Text | crop edges | `/cue/{cue_number}/cropTop`, `/cropBottom`, `/cropLeft`, `/cropRight` | yes | yes | yes | yes | no | dry-run only | high |
| Video/Camera/Text | blend mode | `/cue/{cue_number}/blendMode` | yes | yes | no | no | no | dry-run only | high |
| Video/Camera/Text | clock type | `/cue/{cue_number}/clockType` | yes | yes | no | no | no | dry-run only | high |
| Video/Camera | rotation quaternion | `/cue/{cue_number}/quaternion`, `/resetRotation` | yes/action | yes/action | no | no | no | blocked | critical |
| Video/Camera | scalar rotation | `/cue/{cue_number}/rotation` | no | no | no | no | no | blocked; removed from Video/Camera registry | critical |
| Video | file target | `/cue/{cue_number}/fileTarget` | yes | yes | no | no | no | blocked | critical |
| Camera | legacy camera patch | `/cue/{cue_number}/cameraPatch` | yes | yes | no | no | yes | blocked | critical |
| Camera | input patch | `/cue/{cue_number}/videoInputPatchName`, `/videoInputPatchNumber`, `/videoInputPatchID` | yes | yes | no | no | no | read-only; writes blocked | critical |
| Video | effects aggregate | `/cue/{cue_number}/videoEffects` | yes | no | yes | no | no | read-only | critical |
| Video | effects mutation | `/cue/{cue_number}/videoEffects/add`, `/insert`, `/delete`, `/move`, `/enabled`, `/parameters` | no | action | no | no | no | blocked | critical |
| Text | text and simple format | `/cue/{cue_number}/text`, `/fixedWidth`, `/text/format/alignment`, `/fontName`, `/fontSize` | yes | yes | mixed | mixed | no | dry-run only | high |
| Text | full rich format | `/cue/{cue_number}/text/format` and color/shadow/decorations | yes | yes | mixed | mixed | no | blocked | critical |
| Workspace Video | input patches, routes, stages | `/settings/video/inputPatchList`, `/routes`, `/stages` | yes | mixed | no | no | no | read-only; mutations blocked | critical |
| Workspace Video | history actions | `/settings/video/undo`, `/redo` | no | action | no | no | no | blocked | critical |

## Phase 1 invariants

- `/live`, playback, GO, Dashboard, and raw OSC mutation remain blocked.
- Workspace Video mutations, stage regions/bounds/warping/control points, output devices, and routes remain blocked.
- `fileTarget`, camera patch writes, and Video FX mutations fail before planning.
- Technical/exhaustive reads may retain raw topology; inspector-safe output exposes summaries only.
