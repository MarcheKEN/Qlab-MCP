# Stage editor read coverage audit

For subsequent stage authoring, see [October 25 acceptance](2026-10-25-video-authoring.md).
This record retains the dated reader/UI audit and its historical incident sequence.

## Result and evidence boundary

Latest verification (2026-10-24): all twelve stages pass source FastMCP/native
read checks without truncation or byte changes. Full automated regression:
2,220 passed, 35 skipped, 61 subtests passed. The Layout lock is editor-local;
the forward midpoint evaluator now handles known warp branches with explicit
native-validation limits. The user subsequently authorized mutations, and
deformed Bézier, Linear and Perspective samples matched native UI centers
(see the latest acceptance below). Historical
incidents and their subsequent resolutions are retained below.

`qlab_get_video_stage` does not yet reproduce every meaningful Stage Editor
value in its default structured response. It reads the principal saved model
and current OSC summaries, but several values remain raw, UI-only, or explicitly
unavailable. A successful call is not proof of UI equivalence.

Workspace: `mcp_prueba.qlab5`, UUID
`95F0A03D-140E-4673-974A-E76748EBB023`; QLab 5.5.10/build 5510.
Saved file SHA-256:
`7170baaf3db4401f977400568ceab433eb524ec7b544de3f0b94f689029c1139`.
The file hash matches the preceding native verification. No workspace Save,
Close, Open, setter, cue execution, mask assignment, grid export or physical
output test was performed during this audit.

All twelve stages were queried through the attached MCP using `technical`.
OSC succeeded for all twelve. Saved enrichment correctly degraded to
`unavailable: Multiple QLab instances are running.` after Computer Use opened
the second installation at `/Applications/QLab.app`. The workspace is in the
installation at `/Users/filarmonica/Desktop/QLab.app`. Closing the empty second
instance was pending at that point; it was subsequently closed and native
enrichment revalidated as recorded below. Direct decoding alone is not a
substitute for the tool's live document/freshness checks.

Direct read-only decoding of the saved file finds twelve stages, zero unknown
field diagnostics, and matching stage names, dimensions and region counts.
This establishes coverage of the known saved schema, not every UI value or
unsaved state. Settings lists all twelve stages. Detailed UI observations
cover `casa prueba`, `inferior centro`, and `Stage 12`.

## Control-by-control checklist

| UI control or value | Current coverage | Meaning and remaining work |
| --- | --- | --- |
| Stage name | Current OSC and saved header | Available. |
| Stage size / pixel dimensions | Current OSC and saved width/height | Available; distinguish current from last saved. |
| Layer, including `top` | Saved viewport layer | Numeric 1000 observed as `top`; source now adds the validated label. Unsaved changes are not covered by this source. |
| Keep rendering between cues | Saved header | Available as last saved. |
| Load/remove mask | Actions | Reader returns the saved alias/path/bookmark presence. It does not perform assignment/removal. |
| Mask contents and health | Limited | Saved alias is available; resolved image bytes, dimensions, current reload success and rendered masking are not verified. |
| Resize new pixel dimensions | Pending action | Dialog begins with current dimensions. Proposed dimensions are not saved stage properties until applied. |
| Resize Scale / Crop-Pad | Pending action | Both modes observed. Crop-Pad shows nine anchors. Cancelled without applying. |
| Preserve Stage Aspect Ratio / Preserve Region Aspect Ratios | Pending action | Resize options; do not conflate them with the Layout region lock. |
| Region A/B/C, order and identities | OSC summary and saved hierarchy | Available. UI letters/order and UUIDs must remain distinct. |
| Region Size / Lower left / Upper right | Live bounds and derived stage-centered coordinates | Available mathematically. UI rounding at odd dimensions needs explicit handling before claiming exact displayed text. |
| Layout aspect lock | Editor-local UI state | Native getter/setter trace distinguishes the editor byte from the model ratio. Classified as `ui_only`; OSC `lockedAspectRatio` does not identify the padlock. |
| Edge widths / Auto edge blends | Live summary and saved geometry | Available; per-region state. |
| Blend gamma / power / center luminance | Saved geometry, mostly live summary | Values available. Gamma is shown for the selected context, not proof all regions share a value. |
| Assigned Output Route | Live summary and saved route UUID | Source now retains full saved configurations for assigned routes, deduplicated by UUID; unrelated routes remain excluded. |
| Region without output | Saved nullable route reference | Representable; no new unassigned-region fixture was created in this audit. |
| New region with output / Draw Regions | Actions / editor interaction mode | Menu contains current routes; drawing creates geometry. These are not additional saved scalar properties. |
| Move Regions | Editor interaction mode | Changes how mouse input operates; persisted result is bounds. |
| Region grid enabled | Supplemental current OSC read | Available for up to sixteen root regions; follow explicit continuation requests. |
| Grid appearance Dark/Light | Saved `grid_is_dark` | Light observed in `casa prueba`. |
| Grid edge blends | Saved `grid_bypasses_edge_blends` | UI applies blends when this saved flag is false. |
| Show/hide all grids / Export grid image | Actions | Individual grid state is readable; export is not part of this reader. |
| Show alignment guides | Supplemental route read | Current `enableGuides`; route state is shared. |
| Warp type Perspective / Linear / Bézier | Raw codes and labels | Native popup tags verified as 3 / 1 / 2. Label alone does not specify internal interpolation branch. |
| Mesh splits | OSC summary and saved hierarchy | `inferior centro` UI 2×2 agrees with OSC mesh width/height 2. |
| Control points / shadow controls / links | Technical OSC and paged saved geometry | Available; preserve nested hierarchy and links. |
| Warping Center | Derived, sample-based native acceptance | Forward midpoint evaluation handles known Linear/Perspective/Bézier and nested meshes. Deformed samples of all three modes and a divided Perspective sample match native integer Center fields. This does not prove every possible geometry. |
| Selected point coordinates | Geometry available; selection UI-only | Point coordinates are present; the current selected handle is not returned. |
| Size on Stage / Size of Route | Reset actions | Reader exposes their input geometry; these buttons are operations, not saved flags. |
| Warping guidelines | Raw route mode and derived label | Full sixteen-value native tag table validated below; source now returns readable dimensions/label in saved routes. |
| Fit / zoom / selected tab | Editor presentation | Not stage geometry; current UI state is not exposed by this reader. |
| Region thumbnails / canvas / output pixels | Not returned | These are rendered images. Geometry and mask identity do not establish visual or physical output. |

## Native observations that constrain future changes

### Functional center

Static arm64 disassembly of the installed 5.5.10 executable establishes:

- `VideoRegionWarpCanvasView.centroidOfRegionAtIndex:` at `0x10044b9f0`
  obtains the region bounds, computes `(x + width/2, y + height/2)`, and calls
  `warpCanvas:warpedPointForStagePoint:onRegionAtIndex:`.
- `VideoStageEditor.refreshSelectedControlPointInfo` at `0x10061feac`
  subtracts half the current route's `naturalSize` and rounds with `frinta`
  before populating the Center fields.

Thus a bounding-box center is not a general functional-center algorithm.
Evaluating the region's warp at UV `(0.5, 0.5)` is the required forward path,
including mesh selection, projective/Bézier branches and shadow controls.
No generalized evaluator or renderer result was validated in this audit.

`inferior centro` currently shows Center `(-379, -241)` and mesh splits 2×2.
The existing helper intentionally reports such split geometry as unavailable.

### Layout aspect lock

`Stage 12` region A shows an open padlock and accessibility description
`Not preserving aspect ratio when changing scale`. In the same inspection,
OSC technical returns `lockedAspectRatio = 0.8883248730964467` (350/394).
The archive has no `lockedAspectRatio` field. A positive OSC ratio therefore
must not be interpreted as a verified boolean UI lock state. Additional
native editor-state tracing is required.

### Guidelines and native tags

REA decoded a temporary bundle containing an unchanged copy of
`VideoStageEditor.nib`: 401 objects, 121 connections, complete hierarchy.
Evidence ID:
`ev_9072151e97529934d0636b6f00bf2ed27a7c5a4b5fcfc33618c68f0327343b02`.
NIB SHA-256:
`b92538918547735cc39a1784bfabb4bd30014fbea3119e3848bd89ef6e4e2a8e`.

The sixteen menu titles and tags are row-major: modes 0–3 are 1×1 through
4×1; 4–7 are 1×2 through 4×2; 8–11 are 1×3 through 4×3; 12–15 are 1×4
through 4×4. Equivalently `width = mode % 4 + 1`, `height = mode // 4 + 1`
for integer modes 0–15 only. `changeWarpGuidelines:` reads `selectedTag` and
writes that value to the current route. Current UI 4×4 and OSC mode 15 agree.
Unknown integers must remain explicitly unknown.

The same NIB confirms Perspective=3, Linear=1, Bézier=2, Scale=0 and
Crop/Pad=1. Static tags establish an enum mapping; they do not validate every
operation or output path.

## Sources and remaining acceptance

- [Official Video Output manual](https://qlab.app/docs/v5/video/video-output/):
  basic stage attributes, Resize, Masks, Layout and Warping sections.
- Local QClass Day 2: 6:09:08–6:12:22 masks/layers; 6:12:36 Layout;
  6:16:21 route raster and Warping; 6:19:06 mesh splits;
  6:20:01 Bézier; 6:20:22 Linear.
- Existing REA `video/FINDINGS.md`, especially forward warp and canvas/model
  distinctions; current static center trace above adds the UI calculation.

The working tree now adds layer/guideline labels, assigned saved routes and
explicit action/unverified-state coverage. Focused video, tool-contract and
workspace-settings tests: 226 passed. These source additions still require
native enriched acceptance after restoring single-instance operation and
restarting the MCP; the attached process has not loaded these additions yet.

The second instance was subsequently closed. Source validation then exposed
the original bridge's `/Applications/QLab.app` restriction: the only running
5.5.10 bundle is on the Desktop. Saved video inspection now opts into a
separate `read_inventory` action that addresses the exact single running bundle.
The mutation/default-inventory path retains the existing installation-path gate.
Real Automation validation returned the exact UUID, `modified=false`, twelve
saved stages, and the unchanged SHA-256 above. Focused tests including document
lifecycle regressions: 263 passed. The attached MCP still needs a restart to
load this source correction. A fresh in-process FastMCP Client then called the
real source tool against QLab: `ok=true`, `status=ok`, saved status `ready`,
`modified=false`, `layer_label=top`, one deduplicated Output 1 with grid label
`4×4`, and the unchanged hash. This proves the new source contract/native read
integration, but is not a test of the still-running attached MCP process.

Remaining: restart the MCP and repeat native enriched calls;
validate unsaved changes independently;
resolve the editor lock state; validate a general center against native
Perspective/Linear/Bézier and divided meshes; retain explicit action/UI-only
coverage. Full Stage Editor equivalence remains unproven.

## Attached MCP recheck and editor lock trace (2026-10-24)

The attached MCP now returns `ok`, saved status `ready`, clean document,
`top`, the mask alias, and the assigned Output 1 with a `4×4` guideline grid.
Its SHA-256 remains `7170baaf3db4401f977400568ceab433eb524ec7b544de3f0b94f689029c1139`.
This supersedes the pending restart acceptance above.

The native arm64 `VideoStageEditor lockRegionAspectRatio` getter at
`0x10062c538` reads one byte from the editor instance. Its setter at
`0x100622680` writes that same byte; enabling additionally calls
`setLockedAspectRatioForSelectedRegion`, while disabling returns without
clearing the model ratio. `refreshRegionInfo` selects the padlock image using
this editor getter. This explains the observed open padlock with a positive
OSC `lockedAspectRatio`: they represent distinct states. Coverage now classifies
the padlock as `ui_only`, rather than an unverified archive property. No UI state
or workspace was changed for this trace. General warped centers remain pending.

### Divided-region center cross-check

For saved `inferior centro`, the 2×2 mesh has four children. Applying the native
forward-warp cell-selection rule to UV (0.5,0.5) selects child 3 at local UV
(0,0). Its first control point is (581.2533946038212,298.5591293837278).
Subtracting half the saved Output 5 natural raster (1920,1080) gives
(-378.7466053961788,-241.4408706162722); native integer rounding gives
(-379,-241), matching the previously observed Stage Editor Center fields.
This validates this mesh-node case, not arbitrary projective or Bézier centers;
no generalized center evaluator has been enabled from this single sample.

The connected MCP subsequently still returned the earlier padlock coverage
classification. Codex configuration explicitly supplies this checkout's `src`
via `PYTHONPATH`; a fresh interpreter with that environment imports the correct
source. A different installed package was therefore not established as the
cause. The currently attached process's reload state remains unverified.

### Forward midpoint implementation

The reader now evaluates the native forward-warp branch structure for a region
midpoint: recursive row-major mesh selection, bilinear Linear interpolation,
four-corner projective Perspective, and tensor-product cubic Bézier (including
16-point Perspective shadows). Unknown types, malformed meshes/points, excessive
nesting, singular projective maps and non-finite results remain unavailable.
Synthetic tests distinguish projective from bilinear results, Bézier weights,
shadow selection, mesh boundary selection and rejection paths. The divided
Perspective sample reproduces the native Center above; rectangular casa prueba
centers are unchanged. `native_validation` explicitly limits native acceptance
to rectangles and the divided Perspective sample. General Bézier/deformed
native acceptance remains open; computed values are not proof of UI equivalence.

A fresh Computer Use observation after this implementation opened Settings,
then `Edit inferior centro`, then Warping. The live UI again shows Center
(-379,-241), Perspective, 2×2 divisions and 4×4 guidelines, matching the saved
midpoint calculation. Only panel/tab navigation occurred; no field was edited,
no reset/mask/resize action applied and no cue executed.

A real FastMCP Client call against the updated source and running QLab returned
`ok=true`, saved `ready`, `document_modified=false`, unchanged SHA-256, midpoint
(-378.7466053961788,-241.44087061627226), and the explicit native-validation
limit. The serialized stage response retained the new midpoint fields and
`layout_aspect_lock_state` under `ui_only`. The restricted shell initially
could not access OSC/Automation; the approved read-only unsandboxed verification
succeeded. This is source-to-native integration, separate from the attached
Codex MCP process's reload state.

### All-stage source integration sweep

A fresh real FastMCP Client queried all twelve saved stages against the running
QLab. Every response was `ok`, saved `ready`, clean, below 2 MiB and without
geometry truncation. Assigned route counts were one for each nonempty stage,
zero for empty Stage 11. The full workspace bytes were identical before and
after all twelve calls. This validates transport/model preservation and current
fixture coverage, not arbitrary geometry or physical output.

The user explicitly chose to keep the workspace intact instead of authorizing
a temporary native Bézier sample. Do not change warp types or create test
regions in this workspace. General Bézier native UI acceptance remains pending
an existing sample; synthetic interpolation tests are not a substitute.

## Authorized native warp acceptance (latest)

The user superseded the keep-intact constraint with explicit permission to
modify this workspace. Stage 12 was used; no cue was executed or grid/output
activated. The native warp-type selector affected all three regions of this
stage. A Bézier control-point edit used MCP readiness, dry-run, fresh token,
one execution and successful exact readback. The native File > Save action
saved the sample. Current and saved reads remained separate while dirty:
OSC reported type 2 and 16 controls; saved geometry remained the previous
baseline, with `document_modified=true`, `possibly_stale` and `needs_save`.

| Sample | Native UI Center | Saved forward midpoint | Evidence |
| --- | --- | --- | --- |
| Bézier, inner control 5 changed to (500,180) | (-940,-752) | (-940.3117617187501,-752.15541890625) | 16 controls; native saved SHA-256 `627ef2df05a00a63afbedd6d4dde5f59b7f980c985af56ff46b0679e36c42da4` |
| Linear, child corner 3 changed to (740,440) | (-935,-748) | (-935,-747.5) | Four controls; exact MCP setter readback |
| Perspective, same deformed child corner | (-945,-759) | (-945.1933953065072,-758.7822921406748) | Saved SHA-256 `d7c63e91ae8bbe481d08ca8bde353978916b4496aa2f577a5cdbc7ca19cb675b` |

All match QLab's integer rounding. The last sample retains different parent
and child control coordinates; evaluating the nested child is essential.
Numeric regression fixtures cover these actual measured samples. Focused
video/document/contract/settings/patch transaction tests: 302 passed.

The test workspace is left saved with Stage 12 in Perspective and its child
corner deformation. Temporary evidence copies are in `/private/tmp` with
prefix `qlab-stage12-` (Bézier, Linear and Perspective); these are evidence,
not production recovery files. Native acceptance is sample-based, not proof
for every pathological or unknown warp structure. UI-only controls and
rendered/physical output exclusions remain unchanged.

## Final attached MCP acceptance after restart

The user reopened the workspace and restarted the MCP. `qlab_check_connection`
confirmed the exact workspace UUID and QLab 5.5.10. The attached Codex MCP now
returns `forward_warp_at_region_midpoint`, the native sample-validation field,
and the Layout lock under `ui_only`; the stale-process blocker is resolved.
The reopened saved baseline SHA-256 is
`2b3271b8edc9b4c35a35365a6966e8236a380d9975c20d039b0017f8ae14be82`.
All twelve attached stage calls succeeded with saved status `ready`, clean
document, identical hashes, no geometry truncation and matching region counts.
Stage 12 Center is (-945.1933953065072,-758.7822921406748).

A limit-10 Stage 12 request explicitly reported 441 geometry entries and
truncation; its exact next request used offset 10 and the baseline hash. That
continuation returned ten entries with the same hash and `ready` status.
These final checks were read-only and made no workspace changes.

Audit conclusion: every requested Stage Editor control is mapped in the
checklist to current/saved data, derived geometry, editor-only state, an action,
or an explicit unavailable rendering/device capability. This is a completed
coverage investigation, not a claim of complete UI reproduction, universal
geometry equivalence, or physical-video validation. The typed reader is ready
within those declared boundaries; adding editor UI-state capture or performing
Resize/mask/region operations would require separate capability work.
