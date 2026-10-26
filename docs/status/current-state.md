# Current Project State — 2026-10-26

## Light cue audit follow-up — PR #19

Light cue details now include bounded last-saved ascending/descending curves,
with file hash, version, dirty-state freshness and explicit partial coverage for
unknown variants. Linear curves accept replacement control points as well as
Custom curves. Compact command ranges retain exact-name precedence and bounded
expansion. Native cue helpers target the unique verified running QLab installation;
trigger, Load Time and Target confirmations bind its process and bundle identity.

Verification: **2,338 passed, 35 skipped, 61 subtests passed**; the public contract
remains **87 tools: 52 reads and 35 writes**. Source FastMCP calls accepted and
restored a Linear point edit in QLab; native UI corroborated the intermediate
point. See the [follow-up evidence and remaining gaps](../development/runtime-validation/2026-10-26-light-cue-gap-closure.md).
The restarted attached MCP also returned both restored curves, native triggers
and the verified Desktop installation without errors; the document stayed clean
and inactive and its hash did not change during the reads.

## Settings follow-up — PR #19

Definition details now expose all interpretable parameters independently of
import eligibility. Video batches support root stage/route ordering, empty
input names and five NDI audio sample rates. The native writer preserves the
floating-point archive encoding of refresh/sample rates. Input inventories
include a bounded public local Syphon directory observation after framework
signature verification, without capture or assignment support.

Automated verification: **2,303 passed, 35 skipped, 61 subtests passed**.
Native acceptance and remaining limits are recorded in the
[settings follow-up](../development/runtime-validation/2026-10-25-settings-extensions.md).

## Video Settings authoring — PR #19

Four editors now support local saved-archive batches: stage/region, route,
configured NDI/Syphon device and local/OBS input patch. Stage and route tools
retain their original single OSC operation form; region OSC edits remain.
The shared transaction binds the running installation, document, file and
external dependencies, retains recovery, and closes/reopens only the target.
Dirty documents require an explicit Save and new preview; dependent deletions
are blocked. Initial compatibility remains QLab 5.5.10/build 5510.

See [workflow](../user/agent-workflows.md#author-video-settings). Native acceptance
and limitations are recorded in the [October 25 report](../development/runtime-validation/2026-10-25-video-authoring.md), separately from physical output.
Source verification: **2,281 passed, 35 skipped, 61 subtests passed**; FastMCP
exposes 87 tools. The [attached audit](../development/runtime-validation/2026-10-25-light-video-audit.md)
now records real restarted-MCP calls and native UI agreement, including fixes for
string default indices and camera modes not selectable by QLab. This is supported
settings coverage, not full UI parity. Approved temporary objects were removed;
final reads confirm the original Light/video inventories and a clean inactive
workspace. The interrupted operation’s recovery remains retained separately.
The PR remains in draft for review.

## Passive video inventories — PR #19

Two new read-only tools inspect output devices and input patches, alongside the
extended exact route reader. Local CoreGraphics screens and AVFoundation
source/format metadata remain distinct from OSC observations and saved virtual
devices. No capture session, permission request, device activation or network
finder is created. Coverage is partial for the QLab process registry and network
sources. Saved configuration remains version-gated to 5.5.10/build 5510.

## Lighting authoring implementation — PR #19

Current source exposes **87 tools: 52 reads and 35 gated writes**.
`qlab_edit_light_cue_curves` adds separate saved-file ascending/descending curve
edits with source-bound confirmations, recovery and saved-archive postconditions.
Custom, S-Curve, Parametric and Linear were accepted on two new disarmed cues in
QLab 5.5.10/build 5510, including adding/removing points, no-op and consumed-token
rejection. OSC cannot read curve values; native visual checks are separately recorded.

The Light command analyzer models `all = home`, lists, matching-prefix ranges,
bracket selectors and dynamic cue pulls with proportional factors. Source hashes,
number resolution, cycles and same-batch conflicts are checked before setters;
the resulting dynamic look is not calculated. Native text/readback acceptance
confirmed a proportional pull with `pass`, with no cue errors or warnings.

Definition creation/import now covers CMY, HSI, Pan/Tilt, acyclic One-to-Many
and RGB lime alongside scalar 8/16-bit parameters. A native batch imported four
manufacturer examples, created combined/nested controls and assigned them to
five unpatched test instruments. Both file and OSC-visible verification passed;
QLab's native editor confirmed the virtual bindings. Global/personal libraries
and Dashboard MIDI are unchanged. No physical-output claim follows.

Verification: **2,183 passed, 61 subtests passed, 35 skipped**; FastMCP reports
83 tools. Test additions were removed and the original patch snapshot restored.

See [October 22 acceptance](../development/runtime-validation/2026-10-22-light-authoring-completion.md).
Earlier counts, blocked capabilities and test totals below retain their dated scope.

## October 21 lighting authoring research — PR #19

The [2026-10-21 research](../development/research/2026-10-21-light-authoring-expansion.md)
records native LCL acceptance, definition variant coverage and an accepted
same-path Light cue Custom control-point file edit in QLab 5.5.10. The shared
analyzer now models reserved `all = home` correctly and ignores only known
group-member parameter mismatches. Instrument lists, matching-prefix numeric
ranges and ad-hoc selectors are supported with bounded expansion. This is not complete LCL or curve authoring:
the proposed curve tool is not registered, and unvalidated definition variants
remain blocked. No playback or physical output was tested.

## October 21 separate Light Definition tools — PR #19

At the October 21 validation, source exposed **82 tools: 50 reads and 32 gated writes**.
`qlab_get_light_definitions` lists bundled/personal and last-saved workspace
sources with exact detail, source-bound IDs, filters and pagination.
`qlab_edit_light_definitions` imports native definitions or performs workspace
CRUD using the existing guarded document transaction and a dedicated token.
Public `qlab_edit_light_patch` now accepts instrument/group actions only;
definition actions moved to the dedicated tool (breaking change).
Initial import encodings cover scalar 8/16-bit and RGB with extended outputs;
other native variants remain readable with explicit import blocks.
No global library or Dashboard writes. [Native acceptance](../development/runtime-validation/2026-10-21-light-definitions.md)
confirmed extended RGB import, manufacturer import, 16-bit creation, edits,
rename/reference updates and in-use deletion blocking on temporary test copies.
The original workspace was reopened with unchanged bytes; no physical output
was tested. The transaction now resets the authenticated OSC session after
reopen, before readback. Verification: **2,120 passed, 61 subtests passed,
35 skipped**; FastMCP inspection reports 82 tools (50 reads, 32 writes).

## Combined Light Patch inspection — PR #19

`qlab_get_workspace_light_settings` now returns current OSC data together with
typed `saved_patch` configuration: addresses, outputs, direct group membership
and all stored workspace definitions. The saved source supports local QLab
5.5.10/build 5510. Dirty documents are labelled potentially stale and never
saved. Unavailable sources and unknown fields retain explicit coverage gaps.
Default requests cover up to 1,000 records per section, with a 2 MiB response
budget and exact continuation requests. Internal OSC readers and write guards
are unchanged. See the [inspection validation record](../development/runtime-validation/2026-10-21-light-patch-inspection.md)
for live and retained-file evidence and remaining limits.

## Light Patch authoring — PR #19

At the original patch-authoring validation, source exposed **80 tools: 49 reads and 31 gated writes**.
`qlab_edit_light_patch` adds signed batches of 1–100 typed operations for
instruments, groups and workspace definitions, including rename/delete. It
edits the original local document through clean-close, verified file replacement
with bounded recovery, reopen and OSC-visible readback on QLab 5.5.10/build 5510.
Preview has no native/file side effects; dirty documents require the existing
Save flow and a fresh preview.

Light cues, Dashboard MIDI and the global Library are preserved. Cue references
may need later repair and are reported with partial-analysis warnings. Art-Net
and unpatched assignments plus explicit USB-DMX identities are enabled as saved
configuration. USB discovery, compatible-device availability and output remain
unvalidated. New definition parameters are scalar/RGB only;
existing other parameter data is preserved where recognized.

File verification covers saved routing and definitions. Current OSC-visible
verification checks instrument names, notes, used definition parameters/defaults,
patched state and group names/memberships; routing and unused definitions remain
archive-only checks. USB patched state is not required for an absent device. No hardware-output claim follows from a verified result.
The [native acceptance record](../development/runtime-validation/2026-10-20-light-patch-authoring.md)
covers original-path batches, all twelve actions and preserving another open
document. Hardware output and additional parameter encodings remain unvalidated.
Earlier registry counts and test totals below retain their dated scope.

## Version 0.4.0 — October 17 release preparation

The package, MCP initialization version and current user guidance now identify
this development branch as **0.4.0**. PR #18 prepared that version. Earlier 0.3.0 reports and validation counts
below retain their original version: the version bump does not rerun or rename
historical runtime evidence.

## Earlier validation — 2026-10-17

At that validation point, the branch exposed **79 tools: 49 reads and 30 gated writes**.
The documentation reconciliation and code cleanup are included in PR #18.
At `9a346bc`, the local suite passed **1,942 tests and 61 subtests**, with
35 skips; GitHub CI, lockfile verification and artifact builds passed.

The subsequent [installed-MCP acceptance pass](../development/runtime-validation/2026-10-17-installed-mcp-acceptance.md)
invoked all 79 tools on QLab 5.5.10 and exercised real writes through 26 of
the 30 write tools. It covered representative operations, all 29 Query filters,
eight generic detail profiles, native fields, audio analysis and pagination.
The four remaining writers received preview or blocking checks only.
This is tool-level coverage, not acceptance of every argument combination.

All 24 temporary cues were removed. The final 493-row structural index and root
order matched the baseline; edited pre-existing properties were restored.
No cues were active. Selection became empty; the already-dirty document was
not saved or closed. Four configured Video routes reported disconnected, and
one Script preview encountered a transient permission failure before a fresh
readiness check and successful execution. No playback or hardware proof is claimed.

Current instructions are in the [tool catalogue](../user/tools.md) and
[workflows](../user/agent-workflows.md). The dated sections below retain their
original evidence and counts; their restart/pending notices are not global
current restrictions.

## Documentation reconciliation — 2026-10-17

At that review, source exposed 79 tools (49 reads, 30 gated writes). The [roadmap](roadmap.md)
now separates implemented contracts from remaining runtime cases; [architecture](../development/architecture.md)
reflects native document/Trigger operations and actual UDP/TCP behavior.
Existing-workspace writes require OSC readiness. Native Open instead uses its
empty-inventory, write-enable, fingerprint and document-token preflight.

Clock/fade/mute already have bounded October 1–2 proof. Solo/solo-clear, healthy
Video slice inventories and remaining marker operations still need their own
acceptance. Native document Get has evidence; Open/Save/Close events remain
unvalidated in the existing reports. Text shadow, fallback and FX identity/
reconstruction gates remain. Historical pending/restart statements below must
be read against the latest record, not treated as current global restrictions.

No new live QLab writes, playback or hardware validation were performed for
this documentation review. See the [documentation audit](../development/reviews/2026-10-17-documentation-audit.md).

## Dated evidence

The sections below retain the counts, fixtures and observations of each date;
they do not assert current installed-process freshness or live workspace state.

## Precommit preparation — 2026-10-15

Local CI, tool inspection and packaging checks are recorded in the
[precommit validation record](../development/reviews/2026-10-15-precommit-validation.md).
The registry remains 79 tools (49 reads, 30 writes). No new live QLab writes
were performed for this preparation; dated runtime reports below retain their
original evidence limits. Published capture identifiers and local paths are
redacted and must not be used as live targets.

## Editor and workspace follow-up — 2026-10-14

The source includes a paginated 60-effect/262-parameter Video FX catalogue,
indexed FX reads, typed FX operations, Text fragment editing, Group Triggers,
and local workspace document tools. Unsupported FX creation, unreadable Text
attributes, and other documented capability gates remain closed.

QLab 5.5.10 live tests ran in `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`. Readiness confirmed write mode, `/connect`
edit permission and Edit Mode; QLab showed 0 active cues. Group Second Trigger
was changed 0→1→0 and matched the Triggers inspector. Existing LinearKey
`inputContrast` changed 4.7→4.8→4.7; DropShadow `Distance` changed 0→2→0.
Text1 font size changed 72→73→72; MCP readback and QLab preview dimensions
matched the change and restoration. All tested values were restored.

Text2 was not changed. Its disabled inspector field initially displayed a stale
1.6; after focusing the text editor, QLab refreshed the field to 1.0, matching
the MCP read. The workspace remains `modified=true`; no Save was issued. No cue
was executed. The source registry has
79 tools (49 reads, 30 writes), with no public `qlab_edit_cues`. Full suite:
1,881 passed, 35 skipped, 61 subtests (Python 3.14.5, loopback allowed for local
fake servers). See the
[runtime record](../development/runtime-validation/2026-10-14-editor-completion.md).

## Text selections — 2026-10-11

Source Text formatting now supports bounded Latin word selectors with verified
whitespace, guillemet/curly-quote/em-dash delimiters. Color-only edits additionally
support those punctuation characters and NBSP while preserving every observed
format attribute. Native and source-MCP tests were contrasted with the inspector
and restored. Emoji still triggered fallback even for color; shadows remain
blocked without readable metadata. The restarted connector passed bounded Text
acceptance: six setters, UI contrast and exact full-text/state restoration.
Verification: 150 focused tests and 1805 full-suite tests passed (35 skipped);
74 public tools retain their existing schemas.
See the [Text follow-up](../development/runtime-validation/2026-10-11-text-selections.md).

## Fixed local cue AppleScript fields — 2026-10-10

Source Control/Target editors and the Control detail Get now include Load Time
and assigned number. Family editors also support fixed native Triggers: incoming
MIDI configuration, Wall Clock time, safe enable/disable and Timecode display.
Hotkey enabling/assignment and Wall Clock weekdays remain blocked. Detail Gets
opt in with `include_native_triggers=true`; ordinary OSC reads remain unchanged.
They reuse signed tokens, whole-batch preflight and full native snapshots. The source MCP was
used for reversible QLab 5.5.10 tests and UI contrast. The restarted installed
MCP verified the native Trigger changes; no new tools, dependencies, version or release.
See the [runtime report](../development/runtime-validation/2026-10-10-control-applescript.md).
See also [native Trigger evidence and limits](../development/runtime-validation/2026-10-10-native-triggers.md).
Closeout on 2026-10-11 corrected a redundant identity-only visual read that
blocked Text before its setter. Control, Group, Mic and Text values are restored;
fresh workspace status reports 0 running/paused. Full suite: **1788 passed,
35 skipped, 61 subtests passed** at that closeout. The restarted installed MCP
then verified the Text read correction and reversible Control/Text native edits.

At the 2026-10-11 closeout, the source and restarted MCP exposed **74 tools: 47
read-only and 27 gated writes**, including `qlab_get_fonts`. The 2026-10-14
source follow-up adds five tools; the installed MCP was not rechecked. Public
`qlab_edit_cues` is retired; use family editors. Package version remains 0.3.0;
no release was published.

## LinearKey/DropShadow diagnosis — 2026-10-09

The user added both effects manually to the disarmed Video fixtures #246/#291.
Native named getters proved their documented identities. Installed MCP tools
changed/restored LinearKey cutoff and DropShadow distance; QLab's inspector
confirmed both. The updated source MCP additionally changed/restored the native
DropShadow `Color` RGBA key with full-stack checks and UI contrast. Capabilities
publish its correspondence to documentary `inputColor`; requests keep their
exact OSC key. Add/insert remain blocked: their documented names are correct,
but previous acknowledged requests created no instance. No documented alternative
creation route or proven internal QLab cause was found. Existing effects can be
edited; deletion still needs reconstruction proof. No cues ran.
This color correction needs an installed MCP restart. Focused checks: **180
passed**; full suite: **1691 passed, 35 skipped, 61 subtests passed**; source
schema still has 74 tools. See the
[diagnosis report](../development/runtime-validation/2026-10-09-linear-key-drop-shadow.md).

## Video FX creation follow-up — 2026-10-09

Updated source MCP calls recorded native creation defaults for **58 effects**,
verified all 58 enabled flags, seven representative parameters and 55
delete/insert restorations. A nonempty Gamma/ColorControls stack passed add,
move and delete. LinearKey/DropShadow add/insert acknowledged without creating
an effect and remain blocked; three native key variants prevent safe deletion.
Final reads confirm all 58 fixtures disarmed and restored, 0 running/paused.
The test list remains for inspection. This source update needs an installed
MCP restart; no new UI or rendering verification is claimed.
Full suite: **1688 passed, 35 skipped, 61 subtests passed**; source schema has
74 tools; `git diff --check` passed. See the
[creation report](../development/runtime-validation/2026-10-09-fx-empty-stack-creation.md).
The sections below preserve earlier checks and their narrower evidence.

## OSC Text/fonts and Video FX — 2026-10-09

Source MCP calls in QLab 5.5.10 verified font inventories (529 PostScript names,
181 families), UTF-16 Latin ranges, native nearest-rounded percentages, simple
ASCII words and partial font changes between mappings observed in one cue.
Native named FX getters now prove unique indexed identity independently of keys.
EdgeWork radius edits and Gamma/Exposure add/insert/move/delete passed with
complete fresh stack verification. Computer Use contrasted modified/restored
Text and FX. All fixture changes were restored; no cue execution occurred.
Partial shadows, unobserved font mappings, non-Latin fallback, complex word
selection, repeated/ambiguous FX and unvalidated new-effect defaults remain
blocked. See the [runtime evidence](../development/runtime-validation/2026-10-09-osc-text-fonts-video-fx.md).

## Post-restart Text and Video FX checks — 2026-10-09

The restarted MCP confirmed all 74 tools and passed live reversible Text and
Video FX probes in QLab 5.5.10. Percentage and word selectors, EdgeWork
parameter editing, and Gamma/Exposure add, insert, move and delete were checked
with fresh readback and Computer Use UI comparison. Text and FX fixtures were
restored; QLab showed 0 Active Cues. Alignment in JSON formatting and full color
formatting over the em dash were safely blocked at dry run. Details:
[post-restart evidence](../development/runtime-validation/2026-10-09-osc-text-fonts-video-fx.md).

## Python compatibility and documentation checks

The obsolete `QLabReader.edit_cues()` and `QLabReader.update_cue()` methods are
removed with user approval. Public family editors retain the shared signed
executor. Full automated suite: 1625 passed, 35 skipped and 61 subtests passed;
source catalogues and local documentation links were checked. This validation
uses simulated transports and makes no new live QLab write claim. See the
[removal and verification record](../development/reviews/2026-10-08-python-editor-removal.md).

## Measured read performance

Cue readers reuse compiled validators; unescaped TCP frames avoid copying and
Python byte loops. A user restart confirmed lower live read medians. Additional
source changes cache only the static tool catalogue and skip unnecessary
read-cache expiry scans. After another user restart, 205 timed installed-MCP
read calls confirmed stable response medians: 16–109.5 ms across fourteen
representative tools, and 42 ms for a 50-cue health batch. No transport errors
or QLab writes occurred. Catalogue discovery improvements remain local
`Client(mcp)` measurements; existing image/overview partial reads remain visible.
Full regression suite: 1632 passed, 35 skipped and 61 subtests passed. See the
[performance report](../development/runtime-validation/2026-10-08-mcp-performance.md)
for whole-MCP versus reader timings and the remaining schema-validation cost.

## Workspace authoring audit — 2026-10-08

A new disarmed nine-cue Audio/image/Light scene was built through installed MCP
tools and contrasted with Computer Use. All nine cues are healthy and inactive;
the 417 original index rows are preserved. A quaternion write was applied but
incorrectly reported unverified because its requested vector collapsed to a
scalar; resetRotation restored identity successfully. Both findings were fixed
on 2026-10-09: quaternion planning preserves the vector, and native integer 0/1
infiniteLoop reads become booleans without weakening write inputs. The updated
source MCP verified/restored Video rotation against Computer Use and read both
image and movie details without partial errors. After the MCP restart on
2026-10-09, the public MCP repeated the reversible rotation and UI contrast;
the image read remains complete with `infiniteLoop=true`. Camera/Text share
automated quaternion regressions; their rotation was not revalidated live.
Full suite: 1654 passed, 35 skipped, 61 subtests passed. See the
[authoring audit](../development/runtime-validation/2026-10-08-workspace-authoring-audit.md)
for dependency ordering, negative cases, tests and UI evidence.

## Audio file analysis

Adds read-only `qlab_analyze_audio_file`: 100 ms numeric tuples, individual
estimated onsets/beats, explicit pages, block loudness/rhythm and source identity.
Canonical blocks and bounded cache support approximately 30-minute files without
whole-file PCM arrays. Local numerical tests, actual media MCP calls, a complete
30-minute MP3 traversal and QLab inspector contrasts are recorded in the
[audio runtime report](../development/runtime-validation/2026-10-07-audio-file-analysis.md).
Optional audio extra and FFmpeg/ffprobe are installed in this project's
environment; QLab MCP PATH was extended. No playback, source/media edits,
package version change or release.

## Cue editor migration

At the 2026-10-11 editor-migration closeout the source registry had 74 tools
(47 read-only, 27 gated writes), without public
`qlab_edit_cues`. Group Triggers and Cue List configuration use the signed common
writer. Video/Camera/Text share typed FX contracts, bounded reads and native type
proof. Text exposes typed range/word/percentage formatting with complete-run
verification. The 2026-10-09 evidence and limits above supersede the original
FX identity block; earlier reports retain their dated findings and counts.

# Historical validation records

The following sections preserve dated implementation and runtime observations.
Older counts, pending-restart notices and references to retired tools describe
their original point in time; the current public contract is above and in the
[tool catalogue](../user/tools.md).

## Create hardening — installed 100-cue recheck passed

`qlab_create_cues` now accepts 1–100 ordered template-backed cues. It retains
24 types, the existing destinations, and `confirm:createCues:v2` (five minutes,
one use). At that validation point the registry had 49 tools. Public timeout: 300 seconds; internal
execution budget: 270 seconds. Pending/uncertain indices and final batch
verification are explicit. Empty-list selection and empty-Group movement
accept documented status-only acknowledgements, with fresh readback; `/new`
and read replies remain strict. No AppleScript or initial setters were added.
The first installed 100-cue run created and independently verified all items,
but the final batch verifier reported a false mismatch because it compared
uppercase result UUIDs with lowercase snapshot UUIDs. That comparison is fixed
and verified after another user-confirmed MCP restart: the same mixed
100-cue batch completed in 15.274 seconds with `batch_verified=true`, all
100 results confirmed and no pending/uncertain indices. Independent MCP
readback and Computer Use matched the requested order. Cleanup restored
the complete baseline structure, 241 cues, original current Cue List and
output overrides, with no active cues. See the
[successful recheck](../development/runtime-validation/2026-09-27-create-installed-100-recheck.json), the historical
[runtime record](../development/runtime-validation/2026-09-27-create-installed-100.json)
and [Create runtime checklist](../development/runtime-validation/create-cues.md).

## Earlier project snapshots

## Workspace Settings Edit — implemented and validated locally

The source exposes **73 tools: 46 read-only and 27 gated writes**. The former
generic Workspace Settings Edit is replaced by five object-specific Edit tools;
`qlab_get_video_region` reads one exact region and optionally one indexed control
point. Supported edits are General, Audio output patch, Video output route,
Video stage name, and Video region. Audio Maps, `/live`, Light, Network, MIDI,
and UI-only fields have no Edit tool.

QLab 5.5.10 validation on the disposable copy exercised every published
operation, with fresh readback and restoration; setter replies timed out but
readback confirmed the changes, so no timed-out setter was resent. No cues ran.
The original workspace SHA-256 still matches the recorded baseline. The local
source fixes Network presence to unknown when OSC omits it and keeps output-only
edit operations off Audio input patches. The connected MCP process has not
loaded those final fixes yet: it still reports `passcode_present=false` when
OSC omits that field and advertises output operations on an input patch. Reload
the MCP process to use the corrected reader. The package version remains 0.3.0;
no release was made. See the [Workspace Settings runtime record](../development/runtime-validation/2026-09-29-workspace-settings.md).

## Remaining cue family editors — implemented; bounded live validation

The nine Audio/Mic/Light/Fade/Network/MIDI/MIDI File/Timecode/Script tools share
signed five-minute, single-use Control confirmations for every saved setter.
They accept 1–50 distinct cue UUIDs, typed indexed operations, and compatible
Basics/Triggers/family combinations. The full batch validates before mutation;
selectors and uncertain dependencies retain specific gates. Generic editing is
retained. Device Definition/MSC metadata, unknown object/input capacity and
unsupported source/FX/maps/live actions remain blocked or unavailable.

QLab 5.5.10 validated reversible family-specific edits in eight families,
with Computer Use contrasts and independent restoration reads. MIDI File timing
and other missing-fixture setters remain pending live validation. No cues or
external signals were executed. See the [current live report](../development/runtime-validation/2026-10-05-remaining-cue-completion.md)
for exact coverage and acceptance. Restart an existing installed MCP to load the
updated schemas and executor.

## Group cue editing — validated in QLab 5.5.10

`qlab_edit_group_cues` reuses the existing guarded Group writer for typed Basics
and single-property mode/Playlist edits. Group details expose mode-dependent
capabilities. Automated tests cover strict mode values, schema and capabilities;
live MCP tests verified Flagged, Timeline→Playlist→Timeline and Playlist Loop
off→on against Computer Use. All values and the original list/selection were
restored; no cue was executed.

## Root Cue List/Cart Create and Edit — installed recheck complete

`qlab_create_cue_lists` creates 1–50 empty root Cue Lists/Carts sequentially
through documented OSC `/new`, with a five-minute structure-bound token and
fresh UUID, type, order, and empty-content verification. `qlab_edit_cue_lists`
restricts the existing Edit executor to exact root UUIDs and typed common plus
incoming-timecode fields. Playhead, mode conversion, Cart grid resizing and
AppleScript-only sync settings remain excluded. At that validation point the
installed MCP exposed **51 tools: 43 reads and 8 gated writes**. After restart, a mixed creation batch
made one Cue List and one Cart; both UUIDs, types, root positions and empty
contents verified. Edit renamed both fixtures in one batch. QLab returned
`type: Cart` for the Cart, and both setter replies were `ok`; fresh reads and
Computer Use showed both new names. A stress run made 64 setter calls across 16
batches, alternating names and armed state on both fixtures. Every setter
returned `ok`, every batch was `updated`, and no timeout was confirmed. Whole
tool-call durations were 2.386–3.849 seconds, including preflight and readback;
this did not reproduce the earlier per-setter timeout, so the delayed-timeout
branch remains unforced. A fresh Move token passed directly from dry-run
to execution and verified the Cart's existing last position without sending a
move. The manually copied token failure remains a transcription error before
OSC. The two fixtures are left in the test workspace as requested:
`67D3BD54-4FBB-5144-B37A-BDFB82FE0AC7` and
`BA9DB096-A4F0-52C6-AA04-2A385374DB72`.

## Root Move and deferred root Delete — installed token spot check

`qlab_move_cue_lists` reorders 1–50 root Cue Lists and Cue Carts in the same
workspace, using the shared Move simulator and executor. A dedicated
`confirm:moveCueLists:v1` token expires after five minutes and binds the root
inventory and moved contents. Every step and the final audit verify the mixed
root order and container contents; no-op placements retain verification.
At that validation point the local MCP registry exposed 49 tools: 43 reads and 6 gated writes.
Local verification: **3140 tests and 47 subtests passed**; FastMCP inspection
confirmed that historical 49-tool surface and `git diff --check` passed.
After restart, the installed tool accepted the exact token passed from its
dry-run and verified an already-last Cart with `skipped_no_op`; no real reorder
was exercised in this spot check. Computer Use showed the same root order.
The broader placement matrix remains unverified on the installed process.

Delete QList is deferred: raw OSC and direct AppleScript both opened QLab's
modal confirmation for empty root Lists and Carts. An unattended implementation
would need a macOS Accessibility adapter and host permissions, which are outside
this change. See the [root OSC/AppleScript report](../development/runtime-validation/2026-09-27-raw-osc-root-list-cart.md).

## Move/Delete hardening — local verification, restart pending

Move now checks complete affected parent and moved-Group structures before,
after and at the end of the batch. Move/Delete preserve partial progress on
read failures and expose pending/uncertain UUIDs. Delete adds opt-in
`delete_container=true` for recursive Group removal, with the Group last.
The public registry remains 48 tools. Local verification: **3106 tests and
47 subtests passed**. Installed MCP and Computer Use acceptance await the
user restart; earlier live evidence below predates this update. See the
[hardening report and capture instructions](../development/runtime-validation/2026-09-27-move-delete-hardening.md).

## Move and Delete matrix — 2026-09-27

Move and explicit leaf Delete accept 1–50 UUID targets. Move reads fresh health
instead of inferring false values from shallow structure; broken/warning health
is informational for structural editing. Verified unchanged placements skip OSC
but retain fresh readback, and uppercase before/after anchors normalize correctly.
The full suite passes **3067 tests and 47 subtests**. Three-workspace live tests
and a fresh public FastMCP Client verified 50-cue moves/deletes, nested Groups,
cross-list placements, stale/invalid requests, and fixture cleanup. The public
surface remains 48 tools. See the [complete runtime report](../development/runtime-validation/2026-09-27-move-delete-cues.md)
for the matrix, exact limitations, and root List experiment/recommendation.
The installed MCP process must restart to load these source changes.

## Delete fix and runtime validation — 2026-09-26

The cue-editing branch fixes status-only Delete acknowledgements and stale cached
child-structure reads. The final full suite passes: **3057 tests, 47 subtests**.
A fresh in-process FastMCP instance using the corrected checkout deleted 55
temporary cues in `redacted-workspace-6b31c91e.qlab5` on QLab 5.5.10, including all 24 creatable
types, batches of ten, and 29 nested descendants with the root preserved.
Independent final readback confirmed the original workspace structure and
removal of all temporary fixtures. After restarting the installed MCP, a second
live matrix verified individual/batch/recursive deletion, token rejection and
fresh readback; the original 17-cue list remained byte-for-byte identical in
UUID and order. A further live test deleted one temporary child recursively
from a nonempty Cue List, restored its original Memo, and confirmed the safety
Group empty and the Cue List playhead restored to baseline. Anchored Create in
a nonempty Cue List passed. Empty Cue List Create still fails before `/new`:
the `currentCueListID` setter acknowledgement lacks `data`. This separate issue
is documented, not changed in the Delete fix. Existing Cart contents were
preserved.
See the [runtime report](../development/runtime-validation/2026-09-26-delete-cues.md).
The Move shallow-health issue remained outside that Delete fix; it is addressed
in the 2026-09-27 update above. The audit below records
the earlier Delete blocker as historical evidence.

## Documentation closeout snapshot — 2026-09-26

The local development surface is **48 public tools: 43 reads and 5 gated
writes**. Specialized Workspace Settings, List/Cart, and cue-family reads are
implemented. Generic Query and Cue Details remain for cross-type discovery and
health/target/editable diagnostics, not as the preferred family-detail workflow.
Fresh automated verification: **3054 passed, 39 subtests passed** using
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -m pytest -q -p no:cacheprovider`
with local fixture socket access. The restricted-sandbox attempt was interrupted
after socket fixtures failed; the unrestricted fixture run passed. No live QLab
mutation was performed for this audit.
Final documentation checks: README/catalogue inventories match all 48 tools
returned by the in-process FastMCP client; all 123 tracked Markdown files have
existing local link targets, and active documentation anchors resolve. `uv lock
--check`, unstaged/staged `git diff --check`, and the full suite pass. A temporary
reference-only checkout without local skills/agents passed its applicable tests
(3 passed, 5 optional-local tests skipped) and canonical extraction check.
Coverage remains bounded by documented OSC, profiles, and explicit exclusions:
Audio Maps/Objects, `/live`, patch/stage detail duplication, and unsupported
settings panels are not promised. Implemented reads do not imply that every
variant has been validated in a real workspace.

At this audit, [PR #17](https://github.com/MarcheKEN/Qlab-MCP/pull/17) is open.
Its published head is `9767ec5766618e8a46bb5a8d8ec39491d8833491`; its successful
pytest check covers that head, **not the subsequent uncommitted family readers
and Create consolidation**. The Create changes are a write-surface change beyond
the original read-tools scope; publication should explicitly include or separate
that work rather than silently discard it. No merge or physical file deletion
was performed. Subsequently, `.superpowers/` and `skills/` were removed from Git
tracking and ignored, while all local copies were preserved. Canonical reference
documents remain distributed; portable skill copies and local-agent tests are optional.

Known write issues from the preceding runtime session remain outside this
documentation closeout: Delete was blocked before mutation by `/alwaysReply`
acknowledgement validation requiring `data`; Move health checks can treat missing
`isBroken`/`isWarning` fields in shallow structure as false. Successful reversible
Audio movements do not establish safety for broken cues. These are pending fixes,
not read-tool coverage gaps, and were not retested during this documentation audit.

The dated records below are historical evidence, not the current inventory or
current CI result. Keep them and their research assets until an explicit cleanup
review identifies files that are genuinely redundant.

## Historical development snapshots

Development update (2026-09-24): the public singular Create tool was removed.
`qlab_create_cues` accepts one to 50 ordered cues with an exact Cue List, Group,
or empty Cue Cart destination and a v2 confirmation token. Source exposes 48
tools (43 read-only, 5 gated writes). The verification figures below predate
this change; automated verification is recorded with the implementation.

Development update (2026-09-23): ten Fade, Network, MIDI/MIDI File, Timecode,
and Script read tools are implemented. Source exposes 49 tools (43 read-only,
6 gated writes). Final local verification: 3044 tests and 39 subtests passed;
`git diff --check` passed. In the installed MCP, read-only validation on
`redacted-workspace-76f33afa.qlab5` (`F54ABACA-BB62-5B95-87E5-B43CFBD14B2B`) found two Fade
and 80 Network cues; two exact details of each returned `ok`. The three
Cue Lists had no MIDI, MIDI File, Timecode, or Script examples. The final
Network message-error profile change was made after those installed calls,
so it still needs a restarted MCP for live confirmation. Older counts and
runtime observations below are dated snapshots.

Development update (2026-09-22): 39 tools (33 read-only, 6 gated writes).
Control/organization inventory and details cover twelve cue types using the
shared family executor. Load load-time and Target assigned-number remain
documented OSC coverage limitations; Audio Maps stay excluded.

Control-family runtime validation (2026-09-22): both tools invoked through
FastMCP against QLab 5.5.10 in `redacted-workspace-6b31c91e.qlab5`
(`8E86FE91-668B-560C-B738-4D581B5A7498`). Seventeen Cue Lists read; examples
of all twelve types returned status=ok in safe and technical (24 details).
The local validation process received denied for the other three workspaces;
their content is not claimed validated by this process. No cues executed or
edited. Installed MCP still needs restart to load the new public tools.
Observed `fadeAndStopOthers` returned boolean in both direct and aggregate
reads; the typed result preserves it rather than inferring a numeric scope.
Control-family verification: 3000 tests and 39 subtests passed; diff check clean.
Both new tools also completed real FastMCP CLI calls over stdio (filtered Wait
inventory and exact Devamp detail). Existing installed session requires restart.

Light/Group inventory and detail are implemented and validated through the
restarted MCP. Earlier 33-tool runtime evidence below describes the preceding
surface.
Local verification: 2946 tests and 39 subtests passed; full suite required local
socket permission for its UDP/TCP fixtures. `git diff --check` passed. The installed
tool registry now exposes all four Light/Group tools.
Video, Text and Camera now each have Cue List-scoped inventory and UUID-only
details. All five cue families share the same reader executor; Audio and Mic
retain their public schemas. Text includes full content and formatting in safe
mode. Stage/patch expansion, Audio Maps, Objects and live/indexed effects remain
outside these cue tools. Older counts below are dated development snapshots.

Visual-family validation (2026-09-22): 2912 tests and 39 subtests passed;
`git diff --check` passed. An in-process FastMCP Client exercised the new
source against four open workspaces with writes disabled. Selected lists in
redacted-show-workspace and Practica each returned four Video cues and empty Text/Camera
inventories; the selected Memoria list returned empty inventories. In
redacted-test-workspace's Main Cue List, inventories returned two Video, one Text and one
Camera. Video and Camera details passed both profiles and main-level reads.
Text retained its content and format fragments with partial errors for eight
individual optional formatting getters (backgroundColor, shadowColor,
shadowBlurRadius, shadowOffset, strikethroughColor, underlineColor,
strikethroughStyle and underlineStyle). These are observed QLab errors, not
a claim that the documented getters are universally unsupported.
Computer Use confirmed VIDEO_VALID's Fill Stage/Fit, layer 1000 and 100%
opacity; Camera 1.6's video Patch 1, Stage 9 and one audio input starting at
channel 1; Text 1.7's content, centered alignment and 142x87 output size.
GUI inspection changed selection/playhead only: no playback, property edits
or saving. After the MCP restart, the installed registry exposed exactly 33
tools; direct read-only calls to all six new tools succeeded against the live
workspaces. This validates the installed server and those visible fields, not
every returned field.

Light/Group validation (2026-09-22): after restart, all four tools were visible
in the installed registry. Read-only inventories succeeded in all four QLab
5.5.10 workspaces. Representative counts included redacted-show-workspace Full show 30 Light
and 21 Group, redacted-show-workspace LX 140 Light and 41 Group, Memoria Master 36 Light and
19 Group, Memoria Lluces 54 Light, redacted-test-workspace Main 1 Light and 7 Group,
redacted-test-workspace Light/Group fixtures 8 and 10, and Practica Main 38 Light and 16
Group. Exact Light details returned command text, alwaysCollate and subcontroller
in safe mode; technical mode added notes and state/timing. Exact Group details
covered modes 1, 2, 3, 4 and 6; Playlist properties were queried only for mode
6. Depth, pagination, wrong-type UUIDs and nonexistent UUIDs behaved as errors or
bounded results. Computer Use matched Memoria's `kabuki on` Light (five seconds)
and a `trueno` Timeline Group (two children, 3.5 seconds). No playback, GO,
lighting command, edit or save was performed.

Development update (2026-09-21): 27 tools (21 read-only, 6 gated writes).
Audio cue inventory requires a Cue List UUID; exact Audio details reuse the
existing reader infrastructure. Audio Maps and Audio Objects remain excluded.
Mic now follows the same inventory/detail split, with a required Cue List UUID
for inventory and input/output patch references plus channels/offset in detail.
Audio and Mic share traversal, validation and detail execution internally.

Mic validation (2026-09-21): full suite passed with 2869 tests and 39 subtests.
An in-process FastMCP Client validated read-only inventories across four open
workspaces. `MCP_AUDIO_WRITE_FIXTURE` contained seven Mic cues; two returned
cues each passed safe and technical details with a selected main level.
Observed input/output patch references included both patched and unpatched
states; channels, offset, mute/solo and levels returned without errors.
Other scanned lists correctly returned empty Mic inventories. Writes were
disabled throughout. This validates current source against live OSC, not a
restarted installed MCP or a fresh GUI comparison.

Audio validation (2026-09-21): full suite passed with 2854 tests and 39 subtests.
An in-process FastMCP Client exercised the new tools against four open QLab
workspaces, with writes disabled: inventories matched 9, 25, 2 and 44 Audio cues
in their selected lists (two returned per page). One exact cue per workspace
passed safe and technical detail reads, including main-level selection.
`preservePitch` returned integer 0 and is normalized to false; missing fields
remain explicitly unavailable. This validates the updated source against live
OSC, not a restarted installed MCP or a fresh GUI comparison.
The combined Cue List / Cue Cart inventory feeds two UUID-only detail tools.
Cart details expose dimensions and occupied cell coordinates; both detail tools
share validation, timecode and state reads. Older runtime observations below
describe the contracts tested on their stated dates.

Provisional preparation snapshot: **2026-08-13 Europe/Madrid**.

This document describes the QLab MCP 0.3.0 preparation branch. The definitive
canonical snapshot will be updated through a docs-only PR after the merge into
`main`, before the `v0.3.0` tag.

> Branch update (2026-09-16): PR #16 supersedes the preparation counts below
> with 14 public tools, including the bounded
> `qlab_edit_workspace_settings` write for `general.minGoTime`. That scope is
> complete for the PR; other Workspace Settings operations are deferred and do
> not block review or merge. The dated 13-tool text below is retained as the
> historical preparation snapshot.

Development update (2026-09-20): the current checkout exposes 22 tools
(16 read-only, 6 gated writes) after adding the Cue List inventory and exact
detail readers. Generic Cue Details returns a structured redirect for Cue Lists
and retains Cue Cart support. Cue List details reuse bounded traversal and
expose explicit OSC coverage, including unknown timecode sync activation/source
settings.

Cue List read-only STDIO validation (2026-09-20, QLab 5.5.10): inventory returned
17 lists and 1 excluded Cart in `redacted-workspace-6b31c91e.qlab5`, 5 lists in
`redacted-workspace-1ebcea13.qlab5`, and 8 lists in `redacted-workspace-7cd29b97.qlab5`.
Safe and technical detail passed for `Main Cue List`
(`70A6B610-7094-5939-A9FC-D7AAD7C3379C`, 25 direct / 27 returned descendants),
`Master` (`8A01493C-BAD2-56D6-89DF-92C89A79BDEC`, 151 / 215), and `Full show`
(`8836BE62-7BEC-5499-9DF0-11F0620F00C4`, 22 / 128). Depth-2 truncation was
explicit for Main and Full show. Current timecode was unavailable in these
samples; MTC configuration was readable. Generic details retained the payload
and returned the deprecation notice in each workspace. These observations used
fresh temporary STDIO processes, the configured MCP credentials where needed,
and disabled write mode; no cue execution, setters or save occurred.
The desktop MCP process still needs a restart to load the added tools.

Historical development update (2026-09-18): the checkout exposed 20 tools
(14 read-only and 6 gated writes), including six Workspace Settings domains
and separate UUID-only Video Stage and Output Route readers. The preparation
snapshot below remains historical; see the current [tool catalog](../user/tools.md).

Video split verification: `PYTHONPATH=src .venv/bin/python -m pytest -q
-p no:cacheprovider` passed with **2681 tests and 41 subtests**. FastMCP
inspection reported 20 tools. Read-only STDIO calls against QLab 5.5.10,
workspace `redacted-workspace-6b31c91e.qlab5` (`8E86FE91-668B-560C-B738-4D581B5A7498`), returned
3 input patches, 5 routes, and 9 stages. Exact Stage
`A41F907E-3E01-570E-A4BC-0B86C6A1922E` and Route
`3B9E921B-BB0E-509A-A0A5-CE5C76DB3567` passed both safe and technical reads.
A nonexistent Stage UUID returned `video_stage_not_found` after a same-domain
inventory check. No QLab setters, playback, or save commands were used.
This validates the local checkout; a running MCP process must reload source
changes before it serves the latest error-handling behavior.

Contract-hardening verification (2026-09-19): the full synthetic suite passed
with **2745 tests and 41 subtests**. Audio Maps are no longer public; exact
Output Patch reads cover routing, cue outputs, mute/solo, and one optional
matrix crosspoint. Bounds are schema-enforced, and malformed OSC/settings
payloads are rejected rather than summarized as empty success.

## Preparation Git State

```text
branch: codex/docs
HEAD: local preparation; run `git rev-parse HEAD` to query it
base: origin/main verified before starting; the branch contains local preparation commits
worktree: local 0.3.0 preparation commit; snapshot still provisional
```

The remote reference was verified with `git fetch origin` and
`git ls-remote origin refs/heads/main` before starting.

## Preparation Objective

- contractual version `0.3.0`;
- exactly 13 public FastMCP tools;
- `qlab_edit_cues` as the only public edit tool;
- reproducible CI in a clean checkout;
- current documentation and audited workorders;
- architectural audit without speculative refactoring.

## Verification State

The temporary environments `pip install -e ".[dev]"` and
`uv sync --locked --no-editable --python 3.11 --extra dev` installed
successfully during the initial comparison. The final local preflight passed the
full suite with `2595 passed, 41 subtests passed` outside the managed sandbox.
Linux CI verification remains pending.

FastMCP inspection reported 13 tools, and `uv build` generated the `0.3.0`
wheel and sdist. The wheel was installed in a temporary Python 3.11
environment independent of the checkout; the STDIO entry point initialized with
version `0.3.0`, exactly 13 tools, and no `qlab_update_cues`. The final
post-merge snapshot remains pending.

A clean checkout generated with `git archive` passed the reproducible flow with
`2580 passed, 4 skipped, 41 subtests passed`; the skips correspond to missing
local `.codex/agents/` fixtures. This local result does not replace GitHub CI.

## Active Workorders — historical preparation snapshot

Workorders 017, 019, 021, and 022 are classified as local implementation with
runtime validation pending. Workorder 029 remains active runtime-validation
work. The only new runtime mutation in this iteration was bounded Delete
validation on two disposable empty Groups; it is documented in
[`empty-group-delete-2026-08-13.md`](../development/runtime-validation/empty-group-delete-2026-08-13.md).

The bounded architectural audit is documented in
[`architecture-audit-0.3.0.md`](architecture-audit-0.3.0.md) and concludes
`no extraction for 0.3.0`.

The agent-facing and Edit cleanup research is documented in
[`2026-08-13-mcp-agent-ux-and-edit-cleanup.md`](../development/research/2026-08-13-mcp-agent-ux-and-edit-cleanup.md).

## Evidence Boundary

```text
local implementation
≠
runtime validated
≠
show ready for GO
```

No setters, Create, Edit, Move, playback, GO, `/live`, or raw OSC were run.
The bounded Delete of two empty Groups used only the MCP
dry-run/token/one-execution/readback flow and left the temporary prefix with no
results; it does not turn other workorders into runtime evidence.
Historical references and prior runtime evidence remain under
`docs/archive/` and are not reused as new evidence for this release.

## Reproducible Verification

```bash
cd <repo-root>
uv sync --locked --no-editable --python 3.11 --extra dev
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q -p no:cacheprovider
uv lock --check
uv run fastmcp inspect fastmcp.json
uv build --out-dir /tmp/qlab-mcp-build
git diff --check
git status --short --branch
```

The final snapshot will replace this provisional state after the main PR, the
merge into `main`, the final docs-only PR, and verification of the commit that
will receive `v0.3.0`.
