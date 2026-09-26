# Current Project State

## Delete fix and runtime validation — 2026-09-26

The cue-editing branch fixes status-only Delete acknowledgements and stale cached
child-structure reads. The final full suite passes: **3057 tests, 47 subtests**.
A fresh in-process FastMCP instance using the corrected checkout deleted 55
temporary cues in `mcp_prueba.qlab5` on QLab 5.5.10, including all 24 creatable
types, batches of ten, and 29 nested descendants with the root preserved.
Independent final readback confirmed the original workspace structure and
removal of all temporary fixtures. After restarting the installed MCP, a second
live matrix verified individual/batch/recursive deletion, token rejection and
fresh readback; the original 17-cue list remained byte-for-byte identical in
UUID and order. Existing List/Cart contents were preserved.
See the [runtime report](../development/runtime-validation/2026-09-26-delete-cues.md).
The Move shallow-health issue remains outside this fix. The audit below records
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
`TRUBIA.qlab5` (`DF5AAFEF-EAE5-409A-902B-7315C748481B`) found two Fade
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
FastMCP against QLab 5.5.10 in `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`). Seventeen Cue Lists read; examples
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
MATADERO and Practica each returned four Video cues and empty Text/Camera
inventories; the selected Memoria list returned empty inventories. In
mcp_prueba's Main Cue List, inventories returned two Video, one Text and one
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
5.5.10 workspaces. Representative counts included MATADERO Full show 30 Light
and 21 Group, MATADERO LX 140 Light and 41 Group, Memoria Master 36 Light and
19 Group, Memoria Lluces 54 Light, mcp_prueba Main 1 Light and 7 Group,
mcp_prueba Light/Group fixtures 8 and 10, and Practica Main 38 Light and 16
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
17 lists and 1 excluded Cart in `mcp_prueba.qlab5`, 5 lists in
`Memoria de la nisal - Filarmónica.qlab5`, and 8 lists in `MATADERO - FILAR.qlab5`.
Safe and technical detail passed for `Main Cue List`
(`CC4DF6DC-175E-4346-92A1-43CCB6062390`, 25 direct / 27 returned descendants),
`Master` (`063BD7D0-7105-4FB9-8AE5-53615FBAD173`, 151 / 215), and `Full show`
(`D80B01AB-18D8-466D-9FB7-269FA5337FD1`, 22 / 128). Depth-2 truncation was
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
workspace `mcp_prueba.qlab5` (`95F0A03D-140E-4673-974A-E76748EBB023`), returned
3 input patches, 5 routes, and 9 stages. Exact Stage
`4ADC86C9-4975-40A2-A1E7-34E07D55C452` and Route
`A8DCBB7D-309D-479F-B60E-19F1D9B2EFEA` passed both safe and technical reads.
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

## Active Workorders

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
