# Attached MCP Lighting and Video Settings audit — 2026-10-25

## Conclusion and scope

The attached MCP reads and edits the **supported** Lighting and Video Settings
model in QLab 5.5.10/build 5510. It does **not** reproduce every Settings UI
control or every backend. This audit checks that distinction, actual tool calls,
native UI agreement and public documentation; it does not certify physical output.

The target was the already-open `mcp_prueba.qlab5`, UUID
`95F0A03D-140E-4673-974A-E76748EBB023`, in Edit Mode with zero active cues.
Initial saved SHA-256: `dabf463e6fbd5817bc0732fdb1933cd454147be4333e9683d6a9bdbd9968ea5d`.
Initial configuration: 6 instruments, 4 explicit groups, 2 workspace definitions,
12 stages, 5 routes, 3 input patches and 1 configured virtual device.
The built-in `all` light group explains the extra group in the OSC inventory.

Unlike the earlier [source acceptance](2026-10-25-video-authoring.md), the writes
here used the MCP tools exposed directly to this chat after restart. Every
execution had a reviewed preview and fresh token. Computer Use only observed
settings and switched inspection tabs; it did not create settings or execute cues.

## Capability and evidence matrix

| Area | Reads and edits checked | Native agreement and limits |
| --- | --- | --- |
| Light instruments/groups | Complete saved patch + current OSC; create/update/rename/delete instruments and nested groups | Dimmer occupied 401–402; RGBW 410–414; Art-Net universe 15, Net/Sub-Net 0; notes and 2-member/3-instrument nested group matched UI. Renames updated internal group references. |
| Light Definitions | Workspace, bundled and personal catalogue; custom scalar 16-bit/RGBW creation and HSI import; corrected manufacturer import; unused deletion | UI confirmed intensity default, 16-bit on, percentage off, home 0, and RGBW virtual bindings. Bundled catalogue has 5,793 records; personal catalogue returned 4. Global/personal libraries were not written. |
| Video overview/stage | Current + saved overview; exact stage with 620 geometry entries; stage/region creation, layer, routes, Bézier mesh and point edit | UI confirmed 800×600, layer 75, keep-rendering off, two routes, left blend 15, gamma 1.3 and Bézier 2×1. Earlier acceptance supplies Scale/Crop-Pad, mask, other warp and reset evidence; it is not a new claim of every combination. |
| Output routes | Exact live/saved route, layout and usage; create two routes on one NDI device | Tool and stage UI agreed on Fit/Fill, 180°, rear and section 3 of 2×2. Earlier acceptance covers the remaining scaling/rotation values. |
| Output devices | Passive displays, route observations and saved virtual objects; NDI creation | UI confirmed Audit NDI, 1280×720, 25 fps, no audio. This is configured-device evidence, not signal or complete process-registry enumeration. |
| Input patches | Saved/current patches, exact passive source/format metadata; camera manual, OBS Auto and empty patch creation; update to recognized mode | UI confirmed camera 1280×720 at 30 fps, OBS Auto and no selected input. It exposed a 24-fps representation mismatch, fixed below. No capture was requested by the MCP. |
| Gates and paging | Consumed token, in-use route/definition deletion, DMX footprint overflow, no-op; Light/video/stage continuation calls | Unsafe requests returned blocked with no executed operations; no-op did not reopen. Second pages accepted their returned arguments, including stage SHA-256 binding. |

Definition/patch writers preserve cues with explicit partial-reference warnings.
Video dependency deletions are blocked until uses are removed. This audit did
not modify Light, Video or other cues, Dashboard MIDI or global libraries.

## Corrections found by this audit

### Native definition default index representation

786 bundled records store `defaultParameter` as a decimal string. The reader
compared it with integer parameter keys and incorrectly rejected valid entries.
Canonical strings are now normalized for catalogue validation and archive import;
source bytes/hashes remain unchanged. Ambiguous strings, booleans and missing
indices remain blocked. Of those 786 records, 765 pass the remaining structural
checks; 21 still fail separate validation. This count is **not** native acceptance
of 765 individual fixture models.

After restart, attached catalogue calls recognized string-default BAC503 records.
The 5-channel definition was imported and QLab's UI confirmed default `intensity`.
Tests cover numeric/string defaults, virtual/no-default indices, malformed values,
source preservation and archived integer encoding.

### QLab-selectable camera modes versus AVFoundation ranges

A 1280×720/24-fps descriptor was saved, while QLab displayed Auto. Its mode menu
listed only 15 and 30 fps for the available format. Being inside AVFoundation's
15–30 interval therefore did not establish a selectable QLab mode.

The writer now requires the exact reported minimum or maximum endpoint for this
validated encoding. The temporary input was changed to 30 fps and the UI agreed.
After another MCP restart, a 24-fps preview returned `blocked`, with empty
executed operations and no reopen. Configured mode, observed macOS format and
actual capture remain separate concepts.

### Schema and documentation

Video update schemas no longer advertise null for preserve-by-omission fields;
removable assignments remain nullable. Pixel-format documentation directs agents
to the exact selected-source code rather than a guessed label. OSC detail
`editable_operations` lists legacy setters only, not all archive operations.

README, changelog, roadmap, workflows, setup, security and architecture now
separate dynamically targeted document/archive bridges from the stricter
cue-native installation path. Historical tool counts are labelled checkpoints.
Public schemas, docstrings, inventory and local links are checked by tests and
read-only review. PR #19 had no conversation comments, reviews or inline threads
to reconcile; its eight pre-existing commits were inspected without rewriting history.

## Recovery and cleanup

An MCP restart interrupted acknowledgement of the instrument/group rename batch.
The journal reached `replaced`. The operation was **not retried**: its exact output
bytes were reproduced from retained original bytes/operations, matched to the
journal hash, and checked against fresh native patch, UUID/path, one clean
inactive document and QLab build. The original recovery directory was retained
separately with its unrevised journal, rather than overwritten by later tests.

All temporary Light instruments, groups and definitions were subsequently removed
through the MCP. Final Light inventory returned the original 6 instruments,
4 groups and 2 definitions. Automatic action review initially rejected deletion
of the temporary stage and required a new approval even after ownership/use
checks. The user explicitly approved removal of the seven named temporary video
objects; only then were the stage, two routes, device and three input patches
removed through their public editors. Each cleanup returned `verified`.

Final attached reads: **6 instruments, 4 groups, 2 definitions; 12 stages,
5 routes, 3 inputs, 1 configured virtual device**. Both settings reads reported
matching observable fields, no diagnostics, and the same saved SHA-256:
`3308ce218979aea167fd341fc3092d3a45314756050541652c65243a82250c9b`.
The document was clean, in Edit Mode, with no active cues. This is logical
configuration preservation, not a claim of byte-identical archives after edits.

## Verification and remaining coverage

Full source suite: **2,281 passed, 35 skipped, 61 subtests passed**. Contract
snapshots cover the schema corrections. `git diff --check` passed. Native
acceptance is representative and version-bound, not every possible combination.

Known exclusions from full UI parity:

- Light Dashboard/live control and global/personal library writes; USB discovery
  and physical USB/Art-Net delivery are not verified.
- Unknown Light Definition variants or metadata that cannot be preserved safely.
- Complete QLab process device registry, network discovery/new network input
  assignment and Blackmagic configuration/capture/output.
- The unlicensed “Video output for all cues” selector; standalone ordering of
  root stages/routes is not an operation in these editors (region and input
  order are supported). The selectable NDI audio-rate set remains the validated
  subset, not every rate offered by the native UI.
- UI presentation controls, actual capture, rendered output and physical signal.

Sources for UI scope: [Light Patch Editor](https://qlab.app/docs/v5/lighting/light-patch-editor/)
and [Video Output](https://qlab.app/docs/v5/video/video-output/), alongside the
observed 5.5.10 interface and current typed operation schemas. QLab's shared
registry can retain stale virtual rows separately from the saved configuration;
see the earlier acceptance report. None of these limits should be described as
complete support for every Lighting/Video Settings control.
