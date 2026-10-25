# Changelog

## 0.4.0 (Unreleased)

- Extended stage and route editors with typed 1–50-operation archive batches,
  retaining their original single-property OSC forms.
- Added guarded NDI/Syphon output-device and local/OBS input-patch editors.
- Added stage masks, explicit resize, regions, edge blends and validated
  warp/mesh/point operations with dependency-aware deletion.
- Bound virtual device refs to their archive object/snapshot; callers must refresh
  saved virtual references after document changes. `virtualID` remains registry
  scope and is not a device identifier.
- Verified the exact running QLab installation and reused the archive transaction
  for video, preserving the lighting compatibility adapter.

- Restricted explicit input FPS to QLab 5.5.10 selectable range endpoints.
  Interior AVFoundation rates could be saved but displayed as Auto in QLab.

- Fixed import of native Light Definitions with canonical numeric-string default
  parameter indices; catalogue and archive imports now agree without changing the
  source payload/hash. Invalid or missing indices remain blocked.
- Aligned video update schemas with explicit-null rules: omission preserves values;
  only removable assignments advertise null. Current surface: **87 tools —
  52 read-only and 35 gated writes**.

- Enrich passive video inventories with camera connected/suspended/in-use state,
  unverified AVFoundation observed format, macOS display active/asleep/mirrored
  flags, field-specific unknown reasons and timestamp-independent content hashes.

- Add passive `qlab_get_video_output_devices` and `qlab_get_video_input_patches`: separate OSC, saved configuration and bounded CoreGraphics/AVFoundation metadata without capture, permission requests or network discovery. Add route scaling labels, partial layout and saved stage/region references.

- Expand exact Video stage inspection with source freshness, explicit coverage,
  readable warp labels, stage-centered coordinates, and bounded live grid/guide
  reads with continuation requests and shared-route deduplication.

- Exact Video stage/route reads now include saved configuration; stage geometry supports bounded pages with hash-checked continuation and explicit-save guidance.

- Enrich `qlab_get_workspace_video_settings` with read-only `saved_video`
  configuration from local QLab 5.5.10/build 5510 documents: stages, viewports,
  masks, nested region geometry, routes, input patches and configured virtual
  destinations. Keep live OSC and saved provenance distinct; bound section pages
  to 1,000 records and 2 MiB with explicit continuation and coverage limits.

- Add `qlab_edit_light_cue_curves`: separate bounded ascending/descending curve
  batches with same-path close/edit/reopen, recovery and saved-archive verification
  on QLab 5.5.10/build 5510. Preserve omitted fields and reject mirrored/unknown
  structures; no documented OSC curve readback or physical-output claim.
- Extend bounded Light command analysis with reserved `all = home`, instrument
  lists, matching-prefix ranges, bracket selectors and dynamic cue pulls with
  proportional factors. Bind source hashes and number uniqueness, reject cycles
  and conflicting batches, and preserve textual references. No playback.
- Extend definition creation/import to CMY, HSI, Pan/Tilt, acyclic One-to-Many
  controls and RGB lime, preserving native channels, bindings and metadata.
  Virtual controls consume no physical DMX channels. Historical checkpoint before
  the video editors: **85 tools, 52 reads and 33 gated writes**.

- Add `qlab_get_light_definitions`: source-aware paged catalogue of bundled, personal
  and last-saved workspace definitions, with exact channel/control detail.
- Add `qlab_edit_light_definitions`: dedicated workspace-only import and definition
  CRUD using source-bound confirmations and the existing document transaction.
  Preserve native channel positions and extended RGB bindings; unknown variants
  remain readable and blocked for import. No global library writes.
- **Breaking:** remove definition operations from `qlab_edit_light_patch`; use the
  definition editor first, then create/reassign instruments. Public surface is
  83 tools: 50 read-only and 33 gated writes.

- Enrich `qlab_get_workspace_light_settings` with typed saved-file instruments,
  addresses, Art-Net/USB configuration, groups and workspace definitions alongside
  current OSC data. Dirty documents remain unsaved and sources retain explicit
  freshness/coverage. Add bounded section pagination and a 2 MiB response budget;
  archive inspection initially supports QLab 5.5.10/build 5510. Internal cue-editor
  dependency reads and all write gates remain unchanged.
- Add `qlab_edit_light_patch`: typed batches of 1–100 create/edit/rename/delete
  operations for instruments and groups. Workspace definitions use the dedicated editor. On local
  QLab 5.5.10/build 5510 it previews a source-bound plan, then closes the clean
  document, replaces the same path with bounded recovery and reopens for
  archive/OSC-visible readback. Cues, Dashboard MIDI and the global Light
  Library remain untouched; cue-reference warnings are partial. Art-Net and
  unpatched output and explicit USB-DMX identities are supported as saved
  configuration; compatible-device availability and output remain unvalidated. Definition parameters use the separately validated encodings above. Percentage
  home values use 0–100 display units; raw DMX homes use the 8/16-bit range.
  The original patch-editor addition exposed 80 tools; the separate definition tools originally brought the surface to 82, before the curve tool.
- Reuse existing reader normalization and inherited cue model fields, and
  simplify equivalent settings/creation branches without changing MCP contracts.
- Evidence capture now redacts confirmation tokens embedded in JSON-quoted
  strings as well as structured responses.
- Workspace document operations now require an explicit native send acknowledgement
  before readback can report success. A confirmed no-send response blocks without
  counting a mutation; a missing acknowledgement remains uncertain even if the
  document already matches the requested state.
- QLab 5.5.10 copy validation changed and restored Group Second Trigger,
  existing LinearKey contrast, DropShadow distance, and Text1 font size through
  their typed editors. Text2's inspector initially showed a stale 1.6 while its
  field was disabled; focusing its text editor refreshed the field to 1.0,
  matching OSC. Text2 was not edited. All tested values were restored, with 0
  active cues; the workspace was not saved.
- Add a paginated Video FX documentation catalogue with parameter types, enums,
  bands and per-effect keys. Extend selected FX reads with native enabled state
  and parameter metadata. Indexed Gets may discover the native type when omitted;
  ambiguous identity remains blocked. Documentation metadata does not bypass
  baseline, duplicate-instance or structural-write gates.
- Add workspace document inventory, open, save and clean-close tools through a
  fixed local AppleScript bridge. Open requires an empty workspace inventory;
  save is bound to the existing path and saves all changes; close refuses dirty
  documents. All operations use single-use confirmations and fresh readback.
- Fix the native workspace inventory's AppleScript variable collision and
  verify its read-only Get against the open QLab workspace.
- Record remaining Text selector and shadow limits, and extend regression
  coverage for signed cue-owned Audio/Mic object edits and unsupported metadata
  cases. No new cue writes are inferred from missing OSC readback.

- Extend typed Text word selectors to Latin letters and verified whitespace,
  guillemet/curly-quote/em-dash delimiters. Color-only fragment edits also accept
  verified NBSP/guillemet/curly-quote/em-dash characters, with complete format verification retained.
  Emoji and non-Latin selections remain blocked: a live color-only experiment
  also triggered font fallback. Shadows still require readable attributes;
  no defaults or new tools are added.

- Avoid redundant identity-only visual editor reads that QLab 5.5.10 can
  suppress, blocking native Trigger edits before their setter. Fresh identity
  validation and final checks after property reads remain in place.

- Added optional fixed local AppleScript Trigger reads (`include_native_triggers`)
  and signed edits in the existing cue-family tools: MIDI command/channel/bytes,
  comparator strings, Wall Clock time, Timecode activation/display and trigger
  disable state. A full native/safety snapshot guards every setter and detects
  neighboring changes. Configuration requires disabled triggers; activation is
  separate and requires disarmed, no continuation and no skip-if-disarmed.
  Hotkey activation remains blocked without readable key/modifier identity;
  key assignment, Wall Clock weekdays and capture remain unavailable. No new
  tools, dependencies, playback or global input override changes.

- Added fixed local AppleScript reads and signed edits for Load `loadTime` and
  Target `assignedNumber` through the existing Control tools. No new tool or
  dependency. Plans identify the transport; whole-batch preflight, five-minute
  single-use tokens, identity/dependency guards and fresh readback remain required.
  Negative Load times and clearing assigned numbers are supported. Automation
  errors preserve OSC read data and block the native property. Remote OSC,
  arbitrary scripts and cue execution remain excluded.

- Added a canonical workspace review/authoring guide and a project-local
  `qlab-workspace-authoring` skill. They reuse existing MCP tools for bounded
  reviews, staged dependency changes, free-number renumbering, selected-property
  copies and relative adjustments. No tool API or runtime writer changed.

- Video FX deletion reconstruction now tolerates native, undocumented attributes
  only when they match the recorded QLab 5.5.10 creation default. It sends setters
  only for documented parameters; mismatching attributes still block deletion.
  Automated regressions pass; live structural verification remains pending.

- Accepts the QLab 5.5.10 native DropShadow color key `Color` in typed FX reads
  and edits, using the documented `inputColor` RGBA bounds. Exact wire keys and
  native attributes are preserved; conflicting aliases are rejected. User-created
  LinearKey/DropShadow instances passed reversible OSC edits with UI contrast.
  Their acknowledged-but-ineffective OSC creation routes remain blocked.
  The shared writer now labels an explicit QLab `status=error` plus unchanged
  fresh readback as `verification_failed`, not inconclusive, and never retries.

- Records the QLab 5.5.10 add/insert diagnostic for LinearKey and DropShadow:
  the QLab log reports `unrecognized video effect name` despite the UI tooltip
  and OSC dictionary specifying the same names. MCP creation remains blocked;
  existing instances remain readable and editable.

- Removes the two-effect Video FX creation ceiling: isolated MCP probes record
  QLab 5.5.10 creation defaults for 58 effects. Native named getters verify
  runtime key differences without guessing aliases or filling missing values.
  Unknown defaults remain blocked;
  LinearKey/DropShadow creation is blocked after add/insert returned empty stacks.
  Vector/boolean parameters use internally generated JSON setters and native
  aggregate reads, avoiding unreliable scalar routes. Live checks cover all
  58 enabled flags, 55 delete/insert restorations and seven parameter samples.
  Existing confirmation, full-stack checks and reconstruction gates remain.

- Adds `qlab_get_fonts` (application-wide names/families over TCP), bringing the
  source catalogue to 74 tools. Extends typed Text formatting with UTF-16 Latin
  ranges, nearest percentages, simple ASCII words and observed font mappings.
  Native named FX getters prove unique indexed identity; complete stack checks
  enable verified Gamma/Exposure structure in QLab 5.5.10. Ambiguous identities,
  unvalidated defaults, non-Latin fallback and partial shadows remain blocked.
  Live source MCP tests were contrasted with QLab UI and restored.


- Fixes shared Video/Camera/Text quaternion planning, confirmation binding and
  verification to preserve all four components. Accepts native OSC integer 0/1
  for `infiniteLoop` reads and visual write verification while keeping write
  inputs strictly boolean. QLab 5.5.10 image/movie reads and reversible Video
  rotation were verified through the updated source MCP and contrasted with UI.

- Caches the static tool catalogue with FastMCP's existing middleware, while
  explicitly excluding tool execution, resource and prompt results. Read-cache
  expiry sweeps run only when an entry can expire; TTL, invalidation and fresh
  writer reads are preserved. Post-restart live timings and comparative
  discovery/cache measurements are recorded in the performance report.

- Reuses bounded compiled field validators across cue-family and Cue List
  reads, preserving fresh OSC observations and strict validation. TCP reply
  decoding avoids a Python byte loop and copy for unescaped SLIP frames.
  Focused before/after measurements and unchanged request traces are recorded
  in the 2026-10-08 MCP performance report; no public API changes.

- Aligns current architecture, tool catalogue, user workflows, security and
  status documentation with the 73-tool registry, optional indexed reads,
  current FileTarget access policy and retired generic cue editor. Dated
  validation reports remain historical.

- Adds read-only `qlab_analyze_audio_file`: strict local paths, source metadata,
  100 ms numeric tuples, channel-safe RMS/peaks, frequency bands, silence and
  estimated onsets/beats. Explicit paging preserves detail in 30-minute files;
  canonical blocks, scoped loudness/rhythm, stat identity, bounded cache and
  cancellation avoid whole-file arrays. No OSC, playback or media changes.
- Adds optional `audio` dependencies (NumPy/librosa); FFmpeg and ffprobe must
  be in the MCP process PATH. Base server imports remain independent of this
  extra. Package version and release are unchanged.


- Removes the `QLAB_ALLOWED_FILE_ROOTS` gate. The agent asks the person for file
  access in conversation; search then scans the MCP user's home folder. Enables
  signed Audio, Video and MIDI File `fileTarget` edits with existing-file checks
  and fresh QLab verification.
- Video file assignment now requires fresh `isBroken=false` as well as matching
  path before reporting a verified change.

- QLab 5.5.10 runtime checks verified/restored Group Triggers, signed Cue List
  Basics/Timecode and ASCII Text ranges/color/spacing against Computer Use.
  FX identity is absent in native inventory; emoji formatting additionally
  changes font companions, so those operations retain explicit blocks.
- API change: removes public `qlab_edit_cues`. Use exact UUIDs and the existing
  family editors; split mixed-family batches. Also removes the obsolete Python
  `QLabReader.edit_cues()` and `QLabReader.update_cue()` adapters and their
  phase-specific writer modules and result helper. Create, Move and Delete
  remain on the reader.
- Rejects excluded/unverified operations before legacy gates; tokens no longer
  bypass documented write authorization. Group Triggers and Cue List Basics/
  Timecode use signed five-minute single-use confirmations and fresh dependencies.
- Adds typed Video/Camera/Text FX selectors and operations, a 60-effect/262-key
  documentary catalogue, and typed Text fragment operations with complete saved
  snapshots and effective-interval verification. Runtime limits remain explicit;
  no inferred FX identity, invented Text defaults, execution or AppleScript.

- Completes the nine typed Audio, Mic, Light, Fade, Network, MIDI, MIDI File,
  Timecode and Script editors with one common signed five-minute, single-use
  confirmation flow, 1–50 cue batches and up to 50 typed indexed operations per
  cue. Basics/Triggers and verified family settings can share a batch; empty,
  ambiguous and conflicting requests fail before setters. Generic editor subsequently removed in this Unreleased entry.
- Fixes generic setters to prepare `/alwaysReply` on the same UDP/TCP connection;
  failed preparation sends no setter. Known setters accept empty acknowledgements,
  queries remain strict, and fresh readback/stop-on-uncertainty never retries writes.
- Adds bounded typed detail inspections, exact family dependency snapshots,
  cumulative slice verification and honest blocked/pending/OSC-unavailable
  capabilities. Enforces MIDI modes/ranges, MIDI Type 0/1 headers, Timecode/drop-frame,
  cue-owned objects and Fade target/activation requirements. Timecode frame-rate
  verification accounts for QLab preserving duration and normalizing end time.
- Records QLab 5.5.10 reversible family tests and Computer Use comparisons.
  Missing fixtures, boolean Fade & Stop scope, Mic input capacity, MSC/Device
  Definition metadata and low-level Fade quantization retain explicit limits.
  Script source remains read-only; Audio Maps, /live and execution are excluded.
  No dependency, package version or release change.

- Adds `qlab_edit_group_cues` for typed Basics on 1–50 Group, Cue List, Cue Cart
  or Cart UUIDs, plus one-at-a-time Group mode and canonical Playlist changes.
  It reuses the existing child-snapshot-bound, single-use Group confirmation
  flow. Group details now advertise mode-dependent edit capabilities.

- Fixes visual editor readback normalization for OSC crop lists and integer
  preservePitch values without relaxing public input types. Timecode edits read
  the containing List/Cart format through identity-checked valuesForKeys and
  avoid duplicate immediate format queries. Warning recovery permits only
  removing confirmed mutes/solos from inactive, unbroken cues. Scale restoration
  precedes enabling Preserve Aspect Ratio; conflicting scale requests fail
  before writing. Unavailable slice inventories now block advertised edits.
  QLab 5.5.10 slice absence and media-end acknowledgement limits remain documented.

- Adds `qlab_edit_video_cues`, `qlab_edit_camera_cues` and `qlab_edit_text_cues`
  for 1–50 exact UUIDs with typed saved inspector properties, Basics and OSC
  Triggers. Reuses the shared sequential writer, signed five-minute single-use
  confirmations, same-connection acknowledgements and fresh verification.
- Adds Triggers and editing capabilities to visual detail reads. Missing or
  mixed Text style baselines, unknown channel bounds and boolean Fade & Stop
  scopes block writes. Generic cue editing subsequently removed in this Unreleased entry.

- Fixes Control Triggers detail mapping so `timecodeTriggerText` is returned,
  and validates the resulting Devamp Start Next/Stop Target combination before
  planning setters.
- Adds `qlab_edit_devamp_cues` and `qlab_edit_target_cues`, each for 1–50 exact
  cue UUIDs with typed Basics, OSC Triggers and targets. They share the Control
  writer and tool-bound signed five-minute confirmations. Devamp adds its three
  documented Settings; Target excludes the Cue Number tab unavailable via OSC.
  Control details advertise both tools. Generic editing remains compatible.

- Adds `qlab_edit_control_cues` for 1–50 mixed control cue UUIDs with typed
  Basics, OSC Triggers and cue/Reset patch targets. Signed five-minute single-use
  confirmations bind baseline and dependencies; batches stop on uncertain
  readback without retry or rollback. Generic cue editing remains available.
- Extends Control details with Triggers and per-type editing capabilities.
  Reads Fade & Stop scope from its scalar endpoint because QLab 5.5.10 bulk reads
  collapse it to boolean. Reset changes target mode before target assignment.
- Corrects shared Fade & Stop (0–3), Second Trigger Playlist (6–7), and Timecode
  syntax/component/SMPTE validation; rejects read-only aggregate Timecode writes.

- Preserves finite decimal Video control-point readings and unassigned LTC channel
  zero, while retaining strict setter inputs. Text optional style summaries now
  come from format fragments; absent or mixed attributes do not cause partial errors.
- Enables `/alwaysReply` on the same connection immediately before Workspace
  Settings setters and accepts their status-only acknowledgements. Preparation
  failure sends no setter; uncertain writes still require fresh readback without retry.

- Extends Audio Output Patch level Get/Edit selectors to include Main `(0,0)`,
  input gains `(input,0)`, and output gains `(0,output)`, validated on QLab 5.5.10.
  Mute/solo still require positive output channels.

- Fixes Audio `-inf` requests being skipped when OSC only reports the numeric
  volume floor. Rejects malformed OSC geometry in Video Region reads and edits.

- Replaces `qlab_edit_workspace_settings` with five object-specific Workspace
  Settings Edit tools for General, Audio output patches, Video routes, stages,
  and regions. Adds `qlab_get_video_region` and exact-property token-gated
  readback. Audio Maps and `/live` remain excluded. Network destination and
  passcode presence are unknown when OSC omits evidence; input patch reads do
  not advertise output-only edit operations. This is a breaking
  public tool name change; package version is unchanged.

- Fixes Delete preflight rejecting documented status-only `/alwaysReply` and
  `delete_id` acknowledgements on UDP/TCP. Read replies still require `data`.
  Child-structure reads bypass the shared cache so deletion verification and
  structural write preflight use current QLab state.

- Adds the MIT license for original project code and authored documentation,
  with third-party material excluded in NOTICE and license metadata in packages.

- Corrects contributor tool counts, Create security-token documentation, reference
  provenance, and write-registry versus read coverage; surfaces pending Move/Delete
  runtime findings in user workflows and distinguishes historical plans from current API.

- Removes `.superpowers/` and `skills/` from Git tracking while retaining local
  copies; ignores both directories. Reference extraction no longer requires a
  portable skill copy, and local skill tests are optional on clean checkouts.

- Aligns active read workflows and inventory links with 48 public tools; marks
  prior status/roadmap entries as dated evidence and separates published PR CI
  from uncommitted development and pending write-safety defects.

- Replaces the public single-cue Create tool with `qlab_create_cues` for one to
  50 ordered cues in an exact Cue List, Group, or empty Cue Cart. Adds explicit
  destination/position, typed compact per-cue results, and a fresh
  `confirm:createCues:v2` token. Public surface: 48 tools (43 reads, 5 gated writes).

- Adds five scoped inventory/detail pairs for Fade, Network, MIDI and MIDI File,
  Timecode, and Script. Conditional reads follow the cue mode. Script source
  and Network free-form content require technical profile. Public surface:
  49 tools (43 reads, 6 gated writes) before the Create consolidation.

- Adds `qlab_get_control_cues` and `qlab_get_control_cue_details` for Start,
  Stop, Pause, Load, Reset, Devamp, GoTo, Target, Arm, Disarm, Wait and Memo.
  One bounded Cue List inventory with optional type filter; exact UUID detail
  with typed common fields and conditional target/Reset/Devamp blocks.
  Memo content is included in safe. Shared readers, no action calls or fallback.
  Public surface: 39 tools (33 reads, 6 writes).

- Adds Light/Group inventories and UUID-only details: Light commands, collate,
  subcontroller; Group mode, conditional Playlist and bounded ordered children.
  Reuses shared readers and traversal. Public surface: 37 tools (31 reads, 6 writes).

- Adds scoped inventory and exact detail tools for Video, Text and Camera.
  Typed geometry, stage/input references, aggregate effects, Video timing/audio,
  Camera channel selection and Text content/format runs reuse the Audio/Mic
  executor extracted into cues/family.py. Audio/Mic schemas remain unchanged.
  Optional Text formatting OSC failures retain available data as partial results.

- Adds `qlab_get_audio_cues`, scoped to a required Cue List UUID (nested groups
  included), and `qlab_get_audio_cue_details` for an exact Audio cue UUID.
  Shared bounded traversal, workspace resolution, transport and validation;
  typed timing, patch reference, slices, mute/solo and aggregate levels, with
  optional crosspoint selection. Technical metadata is credential-redacted.
  Audio Maps, Audio Objects and live/indexed effect exploration remain excluded.
  Generic cue tools remain available.
- Adds `qlab_get_mic_cues` and `qlab_get_mic_cue_details`, sharing Audio's
  scoped traversal, exact targeting, validation and bounded levels reader.
  Mic details include input/output patch references, channels and channel offset;
  Maps, Objects, live metrics and indexed effects remain excluded.

- Adds `qlab_get_cue_lists` and UUID-only `qlab_get_cue_list_details`, with
  typed identity/state, playhead, incoming timecode and bounded ordered contents.
  Technical reads retain typed sections and add a redacted allowlisted payload.
  The inventory includes both lists and carts, with separate type counts.
  Adds UUID-only `qlab_get_cue_cart_details` for typed dimensions, occupied cell
  positions, state and timecode, sharing the container reader and validation.
  Both details include common basics; notes are read only in technical profile.
- Removes Cue List detail reads from `qlab_get_cue_details`. Single and batch
  calls return an actionable structured redirect to `qlab_get_cue_list_details`;
  Cue Cart reads remain supported by the generic tool.

- Extends exact Audio Output Patch reads with routing, cue-output count and
  names, mute/solo state, and an optional single matrix crosspoint selected by
  strict `input_channel` and `output_channel` arguments. The matrix is never
  scanned automatically.
- Replaces generic Workspace Settings detail payloads with typed Audio, Light,
  Network, MIDI, choice, and empty-inventory models while retaining redacted
  technical payloads where QLab's shape is variable.
- Removes Audio Maps from the public Audio settings schema and overview reads.
  Audio patch device presence is now explicit when known and remains unknown
  when OSC omits device evidence.
- Hardens OSC and settings reads against malformed status/data/workspace
  identities, trailing bytes, invalid payload shapes, non-finite numbers, and
  unsafe credential fields. Workspace UUID matching is case-insensitive while
  preserving QLab's canonical UUID.
- Adds strict public scan limits, actionable settings-selection and Cue Details
  errors, and promotes detected Video routing problems into Workspace Status.
- Types the Workspace Status response and enriches its partial Warnings section
  with cue flags, explicit evidence provenance, and sampled known Video Settings
  problems without adding OSC reads or a new public tool.
- Splits Video reads into the compact `qlab_get_workspace_video_settings`
  overview and UUID-only `qlab_get_video_stage` and
  `qlab_get_video_output_route` tools. This intentionally removes the overview's
  `view`, `ref`, and `profile` inputs; exact reads offer `safe` and `technical`.
  This split brought the inventory to 20 tools before the Cue List additions.
  Video overview uses three bulk reads without per-stage region queries.
  Device metadata remains limited to assigned route destinations.
- Replaces the broad `qlab_get_workspace_settings` and
  `qlab_get_workspace_setting_details` public tools with six typed read tools
  for General, Audio, Video, Light, Network, and MIDI. This is an intentional
  breaking API change; the internal shared settings readers remain in use.
- Adds the documented Audio volume-limit reads (`maxVolume` and `minVolume`).
  Controls, Audition, Collaboration, and Templates remain unexposed because
  QLab provides no complete documented settings-read API for those panels.
- Adds the gated `qlab_edit_workspace_settings` tool for the single proven
  `general.minGoTime` saved-setting operation. The scope is intentionally
  complete for this PR; other Workspace Settings writes remain deferred until
  separately researched and approved.
- Defines the local threat model, security invariants, reportable findings, and
  accepted risks in `SECURITY.md`.
- Documents the PR-1 through PR-4 input limits, canonical script profile
  contract, UDP source-port limitation, and QLab 5.5.10 evidence boundary.
- Records delayed UDP reply correlation as a separate follow-up from source-port
  authenticity.

## 0.3.0

- Establishes the 13-tool public FastMCP contract for QLab inspection and gated
  Create, Edit, Move, and Delete workflows.
- Removes the breaking `qlab_update_cues` compatibility alias; use
  `qlab_edit_cues` for cue edits.
- Removes the duplicate `batch_update_cues` readiness capability key; use
  `edit_existing_cue` as the canonical Edit capability.
- Marks Edit and Move as conservatively destructive MCP metadata hints; runtime
  safety gates, confirmation tokens, execution, and QLab behavior are unchanged.
- Adds a direct Delete route for one exact inactive empty Group while preserving
  the existing leaf and root-preserving recursive routes. Lists and Carts remain
  recursive-only.
- Carries forward sequential Create, recursive Delete, hardened write/readback,
  and release CI/packaging checks. The new Group route has fixture-specific
  QLab 5.5.10 evidence; it is not a general show-readiness claim.
- Clarifies partial overview follow-up, missing settings/cue recovery guidance,
  and sequential Create count semantics without changing the 13-tool surface,
  status vocabulary, write gates, tokens, or runtime behavior.

## 0.2.0

- Exposes 13 public MCP tools for QLab inspection and gated cue creation,
  editing, movement, and leaf deletion.
- Keeps read operations safe by default and writes disabled, dry-run-first, and
  protected by readiness checks, exact targeting, confirmation gates, and
  fresh readback.
- Makes `qlab_edit_cues` the preferred edit tool while retaining
  `qlab_update_cues` as a compatible alias.
- Adds intentional Move and Delete tools with dedicated, process-bound
  confirmation tokens.
- Separates OSC transport, cache, tokens, result construction, timeouts, and
  several write families while preserving the public contract.

Earlier development plans and phase records are available in
[`docs/archive/`](docs/archive/README.md).
