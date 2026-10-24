# Passive video inventory acceptance — 2026-10-24

## Scope

QLab 5.5.10/build 5510, local `mcp_prueba.qlab5`, workspace UUID
`95F0A03D-140E-4673-974A-E76748EBB023`. The document already had unsaved
user changes; no Save, Close, Open, setter, Monitor or cue execution occurred.

## Native and MCP evidence

The source server was called through a real in-process FastMCP Client against
the open QLab. CoreGraphics/AVFoundation getters ran in the isolated native
helper. The initial restricted shell could not observe the GUI/hardware context;
the authorized native repeat was used for acceptance.

- Output devices: two online macOS displays, integrated Retina 2940×1912 at
  60 Hz and `PhilipsTV (5)` 1360×768 at 60 Hz. This agrees with the observed
  QLab Output Devices table. Five separate OSC route-destination observations
  and one saved NDI virtual configuration are also returned. These are eight
  source records, not eight unique devices.
- NDI saved configuration agrees with the native editor: 1920×1080, 30 fps,
  BGRA, two audio channels, 48 kHz and 512-sample buffer. The editor was cancelled
  without applying changes. Syphon remains a route assignment observation;
  no existing saved Syphon virtual device was inferred from the matching name.
- Inputs: three patches, including an unassigned patch. Native AVFoundation
  metadata identified the built-in camera and OBS Virtual Camera, with seven
  and one supported formats respectively. QLab's patch table showed both
  assigned cameras in Auto mode. Authorization remained not determined (0)
  when querying metadata; no permission request or capture session was made.
  These are supported macOS formats, not proof of QLab accepting every format
  or of the effective capture format in use.
- Output 5 route: 1920×1080, 0° rotation, rear projection off, code 2 / Fill,
  full 1×1 layout, and a configured but disconnected display destination.
  The saved route references eight stage regions. Source and freshness are
  explicit; references are not asserted to be current while the document is dirty.
- Technical profiles, exact returned device refs and exact patch UUID filters
  succeeded through FastMCP. Limit-1 continuation returned offset 1 and the
  same content snapshot ID. Every response preserved its typed fields.

Initial observed durations: output devices 2.93 s, input patches 2.43 s,
route detail 1.10 s. These are fixture observations, not latency guarantees.
All reads preserved the exact workspace bytes and SHA-256:
`2b3271b8edc9b4c35a35365a6966e8236a380d9975c20d039b0017f8ae14be82`.
The unsaved document state remained explicit; it was not cleared by a reader.

## Automated checks

Full suite: **2,239 passed, 35 skipped, 61 subtests passed**. FastMCP inspection
succeeded with **85 tools: 52 read-only and 33 gated writes**. Contracts cover
new tool metadata, strict bounded inputs, output-model field preservation and
the additive route schema. Tests cover independent source failures, remote
host exclusion, dirty/concurrent saved snapshots, duplicate-name separation,
exact identity associations, orphan formats, count/byte pagination, invalid
native output and timeout without retries. Native getter allowlists prohibit
capture/session/setter calls in the tested metadata path. Route references are
capped at 1,000 with explicit count/truncation and a stage-inventory continuation.

## Boundaries and remaining deployment check

These tools do not reproduce QLab's complete process registry. Network discovery,
Blackmagic backend enumeration, capture, effective capture format and rendered
or physical output remain outside coverage. Native enumeration has independent
caps; continuation only pages records actually observed within those caps.
Metadata getters do not make the aggregate sources an atomic snapshot.

Numeric route-scale and partial-layout interpretation follows native 5.5.10
research records QLAB-VIDEO-010 and QLAB-VIDEO-031, cross-checked against the
[official route editor](https://qlab.app/docs/v5/video/video-output/#the-output-route-editor).
[Apple's capture-device reference](https://developer.apple.com/documentation/avfoundation/avcapturedevice)
and [formats reference](https://developer.apple.com/documentation/avfoundation/avcapturedevice/formats)
distinguish metadata from capture/session configuration.

After restarting the attached Codex MCP, both new tools were advertised and
called through that process. `qlab_check_connection` confirmed QLab 5.5.10,
the exact workspace UUID, and read access to 27 cue lists. The device inventory
returned the two displays, five route observations, and saved NDI record; exact
display-reference filtering returned `PhilipsTV (5)` alone. The input inventory
returned three patches, two AVFoundation sources, and eight formats; exact
filtering returned the unassigned third patch with no inherited source or
format. Route detail returned Output 5 with Fill, full 1×1 layout, disconnected
status, and eight saved stage-region references. Limit-1 continuation returned
the requested next item with the same snapshot ID. All responses retained the
dirty-document warning. The archive SHA-256 before and after attached-process
reads was identical (`2b3271b8edc9b4c35a35365a6966e8236a380d9975c20d039b0017f8ae14be82`).
Attached-process acceptance is complete for this QLab 5.5.10 fixture.

## Extended read-tool acceptance

On 2026-10-24 the attached MCP was checked again against the same workspace.
All six Video configuration readers returned usable results: the workspace
inventory, exact stage, exact region, exact route, output-device inventory,
and input-patch inventory. The workspace overview reported 12 stages, five
routes and three input patches; saved data reported one configured virtual
destination, build 5510, complete coverage and no truncation at the default
limit. The document remained modified, with saved geometry marked possibly
stale.

Each of the five route-detail calls succeeded: one route was connected and four
were disconnected. Output 5 returned 1920×1080, 0° rotation, rear projection
off, Fill scaling, a full 1×1 layout and eight saved stage/region references.
In QLab's UI, Output 5 showed the same dimensions, rotation, rear-projection
state and Fill mode; its device was marked missing. The other configured
missing displays were reported disconnected by the MCP. This matches QLab's
manual description of a configured device that is currently unavailable.

The output-device inventory returned eight source records: two CoreGraphics
displays, five separate route observations, and one saved NDI destination.
QLab's Output Devices UI showed the same two displays and NDI output. Exact
`device_ref` filtering returned only the requested record. The input inventory
returned three patches, two AVCaptureDevice sources and eight supported camera
formats. The UI showed Patch 1 and Patch 2 in Auto mode and Patch 3 unassigned;
exact patch reads returned seven formats for Patch 1 and none for Patch 3.
No Monitor button, capture session, permission request, output or cue was
activated.

The `inferior centro` stage returned one region with four mesh subregions and
four control points. Its 805 saved geometry entries were collected in 17
50-entry pages (the last page contained five): all 805 paths were unique, offsets
were contiguous, and every page retained the same archive hash. An exact region
read returned its 2×2 mesh, Perspective warp, Output 5 assignment and one
requested control point.

The workspace file SHA-256 was unchanged before and after these calls. FastMCP
inspection reported 85 tools (52 read-only, 33 gated writes); the focused Video
suite passed **48 tests**. Computer Use read the Output Devices, Video Inputs,
Output Routing and Output 5 editor values. Its final Cancel/state capture timed
out, so closure of that read-only editor was not confirmed by Computer Use; no
field was changed and the workspace file remained byte-identical.

## Passive state and observed-format follow-up

The updated native helper was executed against the real macOS providers on
2026-10-24. The Retina and PhilipsTV displays both reported active=true,
asleep=false and mirrored=false. The built-in camera and OBS Virtual Camera
both reported connected=true, suspended=false and in_use_by_another_application=false.
Both returned an observed 1920×1080 format despite no reported use by another
application. Their pixel-format codes were respectively 875704438 and 1111970369.
These observations are explicitly not attributed to QLab or verified capture.
Camera authorization remained not determined (0); no permission request or
capture session was created.

Native observations now include observed_at. Missing optional getters produce
null fields with metadata_errors. Inventory content hashes exclude timestamps;
changes to device state still change the snapshot. Typed FastMCP records retain
these observations without populating effective_capture_format.

Focused inventory/video/contracts tests: 201 passed. Workspace settings/document
regressions: 86 passed. The workspace SHA-256 before/after both updated native
helper reads was identical:
`6f7119078af8523287b1068a950abbb47ad1b29f0b8c44057f4512160051b19b`.

The attached MCP still resolves the expected workspace over OSC. Current local
archive enrichment is blocked by the existing document guard: the running
workspace belongs to /Users/filarmonica/Desktop/QLab.app, while document operations
require /Applications/QLab.app. This guard was preserved. Computer Use's initial
name lookup opened the Applications installation's empty launcher with a port
warning; that instance was subsequently selected by exact path and closed.
A process-path check confirmed only the original Desktop instance remained.
Computer Use then observed the original workspace and zero active cues.
Full UI/device comparison and attached-process acceptance of the new fields
remain pending; source FastMCP contract tests and real native-helper checks are
separate evidence from a restarted deployed MCP.
