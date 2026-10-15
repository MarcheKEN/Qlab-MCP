# Audio and video Workspace Settings: OSC, AppleScript and UI

Date: 2026-09-29. Capability research; no implementation.

Subsequent update: [Audio validation](../runtime-validation/2026-09-29-audio-patch-zero-channels.md)
confirmed Main `(0,0)` and gains `(input,0)` / `(0,output)`, with numbers and
`-inf`; the local Get/Edit implementation now supports those selectors. The
positive-channel restrictions below describe the initial state of this
investigation. The [moveBy test](../runtime-validation/2026-09-29-video-region-moveby.md)
demonstrated warping-point translation and incomplete restoration; that public
operation is not added. Claims of absent documentation remain limited to the
dictionaries examined.

## Conclusion

The dictionaries examined do not provide creation of stages, regions, routes or audio/video patches. AppleScript does not fill that gap: its model exposes workspaces and cues, but not these shared Settings objects. Editing an entire stage is also impossible through these native APIs.

OSC does support editing specific properties of existing objects: stage name, region geometry and control points, guides, and certain audio output patch parameters. Reading a property inside a JSON object does not establish that its setter exists.

| Object | OSC read | Documented OSC write | Native AppleScript Settings API |
|---|---|---|---|
| Audio Output Patch | Inventory, detail, channels, routing and specific values | Name, cue output count, levels, mute/solo and clearing; resets of previously faded parameters | No |
| Audio Input Patch | Name and UUID | None found | No |
| Video Stage | Detail, size and regions | Name | No |
| Video Region | Geometry, mesh and details; individual point | Bounds/origin/size, components, control point, grid and guide; point reset | No |
| Video Output Route | Detail and destination | `enableGuides` | No |
| Video Output Device | Metadata inside a route destination; no independent inventory | None found | No |
| Video Input Patch | Name and UUID | None found | No |

None of these objects has a documented creation operation in the sources examined. Audio Maps is outside this study.

## Method and evidence boundaries

The Settings sections and related paths through cues in the [local OSC dictionary](../../references/qlab_osc_dictionary.md), the classes and commands of the [local AppleScript dictionary](../../references/qlab_applescript_dictionary.md), its [original HTML](../../sources/qlab-5-applescript/applescript_dictionary_v5.local.html) and the [installed SDEF](/Applications/QLab.app/Contents/Resources/QLab.sdef) were reviewed. The installed application is QLab **5.5.10, build 5510**, according to its `Info.plist`.

The web snapshots describe QLab 5, exact patch unknown. The OSC download date is unknown; the AppleScript HTML records 2026-08-02. See [provenance and limitations](../../references/README.md) and [manifest](../../references/manifest.json). The project's two OSC copies match byte for byte. The web was not consulted and imported sources were not modified.

Computer Use inspected Audio Outputs, Audio Inputs, Video Outputs, Output Routing, Output Devices, Video Inputs and the edit dialogs of a patch, a route, an NDI device and stage `Cuadro Superior`. Warping, resize and grid menus were opened to identify options. Dialogs were canceled; no fields were changed, objects created, saves performed, AppleScript executed or OSC setters sent. No cues were executed or monitors enabled. Settings and the editor were closed afterward, returning to the workspace with 0 active cues.

Observed workspace: `redacted-workspace-6b31c91e.qlab5`, path `<redacted-local-path-851cab375f>.qlab5`, UUID `8E86FE91-668B-560C-B738-4D581B5A7498`. Video MCP reads confirmed the inventory and one region with an individual point. This investigation establishes reads and control presence; **it does not validate new writes**. Previously tested writes belong to the [earlier record](../runtime-validation/2026-09-29-workspace-settings.md).

## Audio: UI versus APIs

### Audio Outputs and patch

The UI presents patch creation, name and device selection. The editor contains Cue Outputs, Device Outputs and Patch Routing. The inspected patch had 12 cue outputs and 2 physical outputs.

| Observed control | OSC | AppleScript |
|---|---|---|
| New Output Patch, delete/reorder | No operation found | No patch class or constructor |
| Patch name | `name` setter | Cue fields select an existing patch |
| Audio device | Read metadata available; no setter found | No patch device selector |
| Cue output count | `cueOutputChannels`, 1–128 | No Settings property |
| Cue output/device output names | Custom-name reads; no patch setter found | `setInputChannelName` acts on the cue |
| Matrix crosspoints | `level/{in}/{out}` | `setLevel` acts on the cue matrix |
| Main 0 and marginal input/output gains | Index 0 semantics undefined in the patch OSC entry | Index 0 is documented for cues, not patches |
| Physical output Mute/Solo and Clear | Explicit setters and clearing | Cue commands, not patch commands |
| Add Audio Effect on cue outputs and device outputs | No effect-configuration setters found | No patch effect objects/properties |
| Patch channel ganging | No setter found | `setGang` belongs to cues |
| Set From another patch/defaults | No documented equivalent found | No patch API |
| Audio Settings Min/max Volume | Read-only | No equivalent Settings property |

The visual editor shows `(0,0)` Main, each input's gain in column 0, each output's gain in row 0 and positive crosspoints. This justifies future bounded research of index 0; **it does not justify implementation** by analogy with the cue matrix. The current tool limits crosspoints to positive channels.

The UI states that any level at or below Min Volume is `-INF` (observed minimum: −60 dB). Therefore a numeric floor response does not establish an audible state different from `-inf`. The earlier fix requiring an explicit `-inf` request when the previous read is numeric establishes a conservative write policy; it does not establish a sonic difference. Readback may normalize the result to the floor.

### Audio Inputs

The UI offers New Input Patch, name and device; no matrix editor equivalent to the output editor was observed. OSC only documents `/settings/mic/patchList`, with UUID and name (the device name may be used as fallback). No creation, name or device setters were found. Mic/Camera input selectors assign an existing patch **to the cue**.

## Audio: exact OSC addresses

Prefix with `/workspace/{workspace_UUID}`. Use `A = /settings/audio/patchID/{patch_UUID}`. Without arguments, the following RW properties support reads except for the `name` caveat.

| Address | Operation/type | Evidence: OSC dictionary lines |
|---|---|---|
| `/settings/audio/patchList` | Inventory of name, UUID and routing | 1953–1978 |
| `A`, `A/uniqueID` | Read object and identity | 1818–1835; 1945–1950 |
| `/settings/audio/cueOutputChannelCounts` | Read counts by UUID | 1217–1233 |
| `A/cueOutputChannels` | Read/write integer 1–128 | 1838–1845 |
| `A/level/{inChannel}/{outChannel}` | Read/write dB; number or string | 1848–1857 |
| `A/mute/{output}`, `A/solo/{output}` | Read/write physical output boolean; also a form with channel as an argument | 1860–1869; 1917–1926 |
| `A/mute/clear`, `A/solo/clear` | Action on all physical outputs | 1872–1877; 1929–1934 |
| `A/muteChannels`, `A/soloChannels` | Read lists; check they are empty after clearing | 1880–1885; 1937–1942 |
| `A/name` | Write string; the local entry does not document a no-argument read | 1888–1892 |
| `A/routing` | Read physical outputs with at least one connected cue output; does not return the complete matrix | 1902–1907 |
| `/settings/audio/outputChannelNames` | Read custom names; an empty list does not mean zero channels | 1790–1815 |
| `/settings/audio/minVolume`, `/settings/audio/maxVolume` | Read dB | 1782–1787 |
| `/settings/mic/patchList` | Input inventory, name and UUID | 2159–2176 |

The dictionary accepts any string in `level` as minus infinity. Retaining the MCP restriction to the literal `-inf` prevents accepting typos as valid levels. The patch entry does not establish index bounds or 0 semantics: resolve these through reads and channel validation before extending the schema.

`A/reset` restores faded patch parameters (output effects, routing and device effects) to the saved state; `A/routing/reset` restores faded levels. **These are not factory-reset commands** or equivalents of Set From Defaults (1895–1914). Do not publish them until all affected state can be observed and the result verified.

Permission columns for some actions/name are incomplete or shifted in the local extraction. This limits the snapshot's permission evidence; it does not independently invalidate earlier name and clearing validation. Do not infer Control permission from an incomplete row. `/live`, undo and redo are outside single-property saved editing scope.

## Video: UI versus APIs

| Observed control | OSC read | Settings OSC / AppleScript write |
|---|---|---|
| Create/delete/reorder stage | Existing stage inventory | No command found |
| Stage name | Yes | OSC `name` |
| Stage layer | No specific property found in these paths | No setter found; cue layer is another object |
| Stage resize: size, Scale/Crop-Pad, preserve aspect | Stage size | Size **explicitly RO**; no resize documented |
| Load Mask / Keep rendering between cues | No specific property found in these paths | No setter found |
| Create/delete region, name and Output Route assignment | Region and associated route | No setter found |
| Region: size, Lower Left, components | Yes | OSC bounds/origin/size/x/y/width/height |
| Preserve aspect when scaling | No specific property found | No setter found |
| Auto Edge Blends, four edges, gamma | Present in region detail | No setters found |
| Warping: Perspective/Linear/Bézier, mesh divisions | `warpType`, meshWidth/Height and point structure | No type or subdivision setters found |
| Move existing control point | Individual read | OSC, both components together |
| Reset Size: Size On Stage / Size Of Route | No equivalent operation found | No setter found |
| Reset Control Points | Readable structure/points | Documented OSC action; complete validation/restoration still pending |
| Link/Unlink all control points | No equivalent operation found | No setter found |
| Region grid and guide | Yes, exact properties | OSC `enableGrid` / `enableGuide` |
| Grid Options: appearance, lines, edge blends, export image | No equivalent API found | No setter found |
| Route Show guides | Exact property | OSC `enableGuides` |
| Route name/device/resolution/rotation/rear/scaling/crop | Route detail, fields depending on payload | Only `enableGuides` has a setter found |
| Create route or virtual device | Route inventory; destination inside route | No command found |
| NDI device: name, resolution, fps, pixels, audio, sample rate, buffer | Part of destination metadata when present | No setters found |
| Video Input: create, name, device, Mode | Inventory limited to name/UUID | No setters found |

Local display controls (Fit, Move/Draw Regions) and monitors do not automatically become Settings parameters editable through an API. Monitor buttons were not activated during testing.

## Video: exact OSC addresses

Prefix with the workspace UUID. `S = /settings/video/stageID/{stage_UUID}`; `R = S/regionID/{region_UUID}`.

| Address | Operation/type | OSC lines |
|---|---|---|
| `/settings/video/inputPatchList` | Input inventory, name/UUID | 2233–2249 |
| `/settings/video/routes` | Inventory and destinations | 2251–2282 |
| `/settings/video/routeID/{route_UUID}` | Read route | 2284–2291 |
| `/settings/video/routeID/{route_UUID}/enableGuides` | Read/write boolean | 2293–2300 |
| `/settings/video/routeID/{route_UUID}/uniqueID` | Read identity | 2302–2307 |
| `/settings/video/stages`, `S`, `S/regions` | Read stages, detail and regions | 2309–2344; 2354–2358 |
| `S/name` | Read/write string | 2346–2352 |
| `S/size`, `S/size/width`, `S/size/height` | Read-only | 2360–2376 |
| `S/uniqueID`, `R` | Identity and detail | 2378–2392 |
| `R/bounds` | Read/write integer x,y,width,height (string form also documented) | 2394–2410 |
| `R/bounds/origin` | Read/write integer x,y | 2412–2428 |
| `R/bounds/origin/x`, `R/bounds/origin/y` | Read/write integer | 2430–2452 |
| `R/bounds/size` | Read/write integer width,height | 2454–2470 |
| `R/bounds/size/width`, `R/bounds/size/height` | Read/write integer | 2472–2494 |
| `R/subregionIndex/{i}/controlPointIndex/{j}` | Read/write integer x,y together, within the specified area | 2496–2506 |
| `R/enableGrid`, `R/enableGuide` | Read/write boolean | 2508–2530 |
| `R/resetControlPoints` | Reset all points to initial positions | 2532–2539 |

Geometry setters require valid stage/area bounds. The dictionary specifies `routeIndex` starting at 0, but does not explicitly establish the base for all region/subregion/point indices. Do not generalize from an index-0 example without checking the structure.

### Live coordinate comparison

Stage `Cuadro Superior`, UUID `A41F907E-3E01-570E-A4BC-0B86C6A1922E`, size 960×110. Region A, UUID `8BBA6421-9F0E-5B2B-95F9-A99A99059A71`:

- Layout UI: Lower Left **(−480,−55)**, Upper Right **(480,55)**.
- Exact MCP/OSC read: bounds **(0,0,960,110)**; grid and guide false.
- OSC detail: mesh 1×1, 4 points, 1 subregion, numeric warpType 3, autoEdgeBlends true, gamma ≈0.8.
- Subregion 0/point 0 read: **(145,725)**. Successful reading does not validate writing or establish that points must be restricted to the Layout rectangle 960×110.

The Layout UI uses a centered origin in this example, whereas OSC bounds use another origin. Do not copy visible coordinates directly into an OSC setter or extend this conversion to every warping type. Do not assign a universal enum to `warpType=3` from one screen. The existing Get tool retrieves data and operations without traversing the entire mesh.

### Paths through cues

The dictionary also documents `/cue/.../stage/...` (4963–5112) and `/cue/.../audioOutputPatch/...` (4062–4149). These paths modify the **referenced shared object**, not a local copy of the stage/patch.

An additional capability exists: `/cue/.../stage/regionID/{id}/moveBy {x} {y}` accepts decimal offsets (5063–5067). No equivalent was found under `/settings/video/...`. Some cue geometry paths accept decimals (4982–5025), whereas Settings paths require integers. This discrepancy requires a bounded test before extending UUID tools; introducing an intermediary cue requires resolving its identity and checking that it still points to the correct stage.

The stageID/Name/Number and audio/video input/output patch selectors, and cue video effects, assign destinations or process **the cue**. They do not create objects, change hardware or replace Load Mask or stage warping.

## AppleScript: what it actually provides

The local `workspace` dictionary contains cues and cue lists (3390–3449). `make` creates cues (702–741), and `delete` operates on cues/lists (264–303). There are no stage, region, route, device or input/output patch Settings classes.

The installed SDEF confirms this absence. Workspace inherits from document, declares cue/cue list elements and no Settings collection (lines 628–727). The effective QLab `make` takes a workspace and cue type (1887–1892). Generic Standard Suite `make` and `duplicate` are commented out, so cannot be used as documented stage constructors. A generic `properties` property does not invent missing objects.

The web snapshot mentions `application.preferences`, but that property does not appear in the application class of the installed SDEF; `preferencescontroller` is commented out and contains no usable Settings API. Do not base implementation on that snapshot mention.

| AppleScript capability | Actual scope and local source |
|---|---|
| Audio output patch name/number/id | Selects an existing Audio cue patch, 2117–2120 |
| Audio input/output patch | Mic cue selection, 2774–2780; Camera, 2186–2192 |
| Video input patch and stage | Camera selection, 2204–2211 |
| Video output patch and stage | Video selection, 3315–3318 and 3343–3345; Text stage, 3209–3211 |
| Anchor/scale/translation/opacity/fill/layer | Video/Camera/Text cue transformation; not stage size/layer/mask |
| `getLevel` / `setLevel` | Audio/Mic/Video/Fade cue matrix, row/column and real dB; 427–468, 1653–1690 |
| `getGang` / `setGang` | Cue ganging, text and coordinates; 342–382, 1576–1612 |
| `getInputChannelName` / `setInputChannelName` | Cue input, row starting at 1; 385–423, 1615–1649 |
| `getMute` / `setMute`, `getSolo` / `setSolo` | Cue output, 0 main; 470–550, 1735–1806 |
| Fade/Reset patch target ID | Assigns Fade/Reset cue target, 2508–2520 and 3056; not a direct patch editor |

`setLevel` documents row 0 as main/output and column 0 as main/input in the **cue** matrix. Do not extrapolate to the shared patch. Do not execute a Fade/Reset cue to simulate a direct Settings editing API either.

Local examples contain errors: `setInputChannelName` uses arguments that do not match the signature; solo examples/headings mention mute. For schema design, prioritize signatures and SDEF, and verify in a disposable copy before asserting execution compatibility. No Apple Events were executed here.

## Project consequences

1. Keep editing tools scoped to existing objects and documented properties. Do not add OSC/AppleScript-based `create_video_stage` or `create_audio_patch`: the native operation is missing.
2. Do not promise complete stage or patch editing: masks, devices, effects, subdivisions and much routing require another mechanism.
3. Investigate patch Main/marginal gains and index 0 separately, as well as `moveBy` through a cue. Start with bounded reads; any setter requires a disposable copy, identity, a single send, readback and restoration.
4. Keep resets outside the public API until all their state is identified and verified. Exclude undo/redo because of shared history.
5. A future complete creation/configuration solution would need to evaluate UI automation or another officially available API. AppleScript with System Events would be UI automation, not a native QLab dictionary capability; it requires separate design and validation.

This report adds documentation. It does not extend server schemas or operations, change the package version or publish anything.
