# Video Settings authoring: research and recommendation

Date: 2026-10-24. Research only; proposed capabilities below are not implemented.
Initial native-format target: QLab 5.5.10/build 5510.

## Conclusion

Use four authoring domains: stages and their regions, output routes, virtual
output devices, and video input patches. Expand the existing stage and route
editors, add device and input editors, and retain the existing region editor
for its focused OSC operations. There is no current `qlab_edit_video_settings`
tool to remove.

OSC supports a small subset of the required edits. The saved archive and REA
research make a version-gated file editor plausible, but do not yet establish
that QLab accepts externally created video objects. Validate each encoding and
operation through QLab reopen/readback before advertising it.

## Current implementation, checked against source and attached MCP

| Tool | Implemented operation | Important omissions |
| --- | --- | --- |
| `qlab_edit_video_stage` | Rename one stage. | Create/delete, dimensions, resize, layer, keep rendering, masks and region lifecycle. |
| `qlab_edit_video_output_route` | Set `enableGuides`. | Create/delete, name, device assignment, raster, rotation, rear projection, scaling and partial layouts. |
| `qlab_edit_video_region` | Bounds/origin/size and components, indexed control point, grid and guide flags. | Create/delete, route assignment, warp mode, mesh topology, linked controls and blending. |
| Output devices | Read tools only. | No device writer. |
| Video input patches | Read tools only. | No patch writer. |

Public registrations: `src/qlab_mcp/server.py:2858-2895`.
Typed operations: `src/qlab_mcp/models.py:174-267`.
OSC preparation and confirmation: `src/qlab_mcp/settings/object_writes.py`.
Existing editors perform one operation per call, with UUIDs, readiness,
baseline-bound confirmation and fresh readback. Setter timeouts are reconciled
without resending. Native acceptance of these basic operations is recorded in
`../runtime-validation/2026-09-29-workspace-settings.md`.

`qlab_edit_video_cues` assigns an existing stage to a cue. It does not create
or edit the stage itself. Camera cue input selection likewise differs from
configuring the input patch.

## Official API boundary

The OSC dictionary documents stage-name edits and route guides, plus region
geometry, indexed points, grid/guide flags and control-point reset. The current
MCP has not exposed the documented reset operation. It does not document CRUD
for stages, routes, regions, devices or patches, nor the remaining settings
listed above. AppleScript cue stage/input properties do not provide those
Workspace Settings operations.

The manual describes the full GUI model. Physical displays are selected from
detected hardware; NDI and Syphon are virtual devices QLab can create. Blackmagic
outputs have hardware-specific editable settings and require separate evidence.

Sources:

- [OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
- [AppleScript Dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/)
- [Video Output](https://qlab.app/docs/v5/video/video-output/)
- [Workspace Settings](https://qlab.app/docs/v5/fundamentals/workspace-settings/)
- [Using NDI](https://qlab.app/docs/v5/video/using-ndi/)

## REA evidence and gaps

Source collection:
`/Users/filarmonica/Documents/ChatGPT/Qlab-REA/qlab-research/`.

| Evidence | What it establishes | What remains unproved |
| --- | --- | --- |
| `video/ARCHIVE_SCHEMA.md`, `QLAB-VIDEO-072/073` | Archived stages, viewports, regions/meshes, controls, routes, destinations and camera patches. | Creation and external-write round trips. |
| `QLAB-VIDEO-019/020/021` | Native UI Scale and Crop/Pad resize samples, including region changes. | General resize semantics for every nested/deformed mesh. |
| `QLAB-VIDEO-022/023` | Mask is a viewport `F53Alias` with bookmark/path and renderer integration. | Correctly constructing/replacing all alias variants externally. |
| `QLAB-VIDEO-027/052` | Warp tags and model/canvas normalization are distinct. | A scalar warp-code change alone preserving valid mesh/control topology. |
| `QLAB-VIDEO-054/056/061` | Native saved/reopened partial layout, Fit and 90-degree rotation examples. | An external editor producing equivalent accepted results. |
| `QLAB-VIDEO-025/026/064/065` | Shared destination registry, ownership scope, route references and cleanup. | Full live registry membership and safe generic device CRUD. |
| Main `FINDINGS.md`, `QLAB-VIDEO-080/081` | Private camera-patch name/descriptor/mode setters and saved `settings.Camera.cameraPatches`. | Public setters, manual-mode encoding acceptance, creation/deletion and capture. |
| `reports/qlab-document-routing-static-2026-10-23.md` | `.qlabsettings` JSON envelope containing Base64 keyed archives per pane. | Safe field-level merge, Apply wiring and an accepted external import. |

The earlier video integration handoff predates subsequent MCP region-write and
warped-center acceptance. Its claims about untested MCP writes must be read in
that historical scope; current repository runtime records supersede them.

## Identity prerequisite found in this investigation

The current saved-destination reader uses `virtualID` to construct its `id` and
`saved-virtual:` reference. REA shows that the workspace assigns its
`virtualOutputID` to each virtual destination for registry scoping. This is not
a demonstrated per-device unique identifier.

Read-only decoding of the current native archive confirmed:

- Workspace `virtualOutputID`: `E97A517F-E171-46F3-B076-FE23ACDF36DA`.
- Its NDI destination has the same `virtualID` (archive object slot 1228).
- The NDI route stores `videoOutputKeyPath=ndi.NDI` in `destinationInfo`, rather
  than a direct destination UUID reference.

The current single-device fixture does not expose a multi-device collision.
Before authoring, capture native multiple-NDI/Syphon and duplicate-name cases,
then provide an unambiguous per-object reference bound to the source snapshot.
Never accept `virtualID`, a name match, an array position, or an old display ID
alone as write identity. Preserve the workspace registry scope separately.
Screen IDs can be recycled; native display vendor/model/serial checks already
used by the reader must remain part of current-hardware resolution.

## Recommended public shape

| Domain tool | Intended validated scope |
| --- | --- |
| Expand `qlab_edit_video_stage` | Stage create/update/delete; layer, dimensions/explicit resize policy, keep rendering and mask; region create/update/delete/reorder/route assignment; geometry, blends, validated warping/mesh/link operations. |
| Expand `qlab_edit_video_output_route` | Route create/update/delete; name, dimensions, exact destination, rotation, rear projection, scaling and full/partial layout. |
| Add `qlab_edit_video_output_devices` | NDI/Syphon create/update/delete; validated pixel size/rate/format and NDI audio configuration. Physical displays remain selected hardware; Blackmagic editing is a later validated backend. |
| Add `qlab_edit_video_input_patches` | Patch create/update/delete/reorder, exact source assignment/unassignment and validated Auto/manual modes. Begin with local AVFoundation/OBS sources; network/Blackmagic variants need their own fixtures. |

Keep `qlab_edit_video_region` compatible for focused existing OSC calls. Its
planner/validation should share code with stage-region editing where possible.
Do not silently replace old argument contracts or require archive close/reopen
for a legacy single OSC edit that already works.

New authoring paths should accept typed operation batches. One preview and one
confirmed execution apply a complete batch within a domain. Local client labels
may connect newly created objects within that batch; existing targets use exact
references. Omitted fields are preserved and deletion is explicit. Separate
domain calls are not one atomic whole-workspace transaction.

A new virtual-output setup normally proceeds device -> route -> stage/regions.
Inputs are independent until a Camera cue selects their patch. Cue assignment
continues through the existing cue editors.

## Shared implementation and dependency policy

Prefer documented OSC for existing supported edits. For unsupported persisted
operations, validate a graph-preserving planner on a closed file and use the
existing same-path close/replace/reopen recovery mechanism.

The Light Patch transaction already accepts planners and postconditions, but
its baseline and final `_live()` verification are hard-coded to lighting.
It cannot be reused unchanged. Extract only the shared document transaction
steps and supply domain-specific identity, baseline and native/readback checks.
Do not duplicate the transaction four times.

Before closing: require exact local document/build/UUID, Edit Mode, acceptable
activity, clean saved state, stable file, operation/dependency-bound token and
successful final-state planning. Dirty documents return `needs_save`; no-op
batches do not close or rewrite. Preserve unknown graph fields and references,
other documents, cues and unrelated settings. Reopen the same path, verify the
native result, and retain recovery on failure without blind retries.

Preview all stages/regions affected by a shared route/device. Recommended
default: reject deletion of an in-use target until explicit reassignment/removal
has resolved its dependents. Report cue references and never silently repair
them. This policy needs approval before implementation.

Native metadata formats are candidates, not QLab input-mode encodings. Capture
QLab-produced Auto and explicit-mode samples before generating descriptors.
Mask paths require validated aliases/bookmarks. Resize must transform geometry
according to explicit Scale or Crop/Pad semantics, not just change width/height.

`.qlabsettings` is not the recommended initial writer: documented pane import
replaces settings and the research has not established a narrow merge. GUI
automation is useful for fixture creation/acceptance but should not become the
normal MCP authoring backend. No private selector invocation or code injection
is needed for this recommendation.

## Acceptance order

1. Verify exact document lifecycle support for the running QLab installation;
   current mutation guards require `/Applications/QLab.app`, whereas this fixture
   is open in `/Users/filarmonica/Desktop/QLab.app`. Do not bypass that guard.
2. Capture native device identities and minimal creation/deletion fixtures.
3. Prove a narrow offline route edit with reopen, OSC/UI comparison and semantic
   graph conservation; then basic route/stage/region creation.
4. Add virtual-device and local-input authoring with backend-specific fixtures.
5. Add resize, mask and advanced mesh/warp/link/blend operations independently.
6. Check shared references, deletions in use, dirty/concurrent files, expired or
   reused tokens, close/write/reopen failures, and preservation of other domains.

Zero active cues alone does not prove no video output: keep-rendering, grids,
monitors and persistent virtual outputs need explicit attention. Native virtual
device registration can affect process state. Acceptance must distinguish
stored configuration, QLab acceptance, capture/rendering and physical signal.

## Observation performed for this research

The attached MCP returned saved video `ready` with `document_modified=true`.
The existing unsaved changes were preserved. Computer Use inspected Output 5's
editor, the NDI editor, Video Inputs and Stage 12 Layout/Warping. Route/NDI
dialogs were cancelled; the stage editor and Settings were closed normally.
No field was changed, no Save/Close/Open of the document was requested, and no
Monitor, Show, cue or output was activated. The UI ended with zero active cues.

Automatic approval review rejected opening `New Video Stage` because it could
create an object. Creation options were taken from the official manual and
recorded REA UI evidence instead; no alternative mutation was attempted.

The workspace SHA-256 before and after observation remained
`6f7119078af8523287b1068a950abbb47ad1b29f0b8c44057f4512160051b19b`.
No implementation tests were run: this pass changed only this research note.

## Implementation follow-up

The recommendation is implemented in the current PR working tree. See the
[October 25 acceptance](../runtime-validation/2026-10-25-video-authoring.md) for
native evidence and remaining process-registry/physical-output limits. Historical
proposals above describe the investigation state, not the current public scope.
