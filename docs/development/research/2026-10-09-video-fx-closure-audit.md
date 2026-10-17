# Blend Mode and Video FX closure audit

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-10-09. Result: complete documentary inventory; runtime closure of all
operations remains pending.

## Later update: creation tests

The [later MCP write series](../runtime-validation/2026-10-09-fx-empty-stack-creation.md)
resolves the Gamma/Exposure default limitation: 58 effects have recorded native
defaults, tested enabled state and verified reads/restoration. 55 passed
delete/insert; three retain blocks for attributes without setters.
LinearKey/DropShadow could not be created through add or insert in 5.5.10 and
remain blocked. This update does not turn the read-only audit below into proof
of every parameter or playback result.

## Scope and evidence

Research covered current source, the local OSC dictionary, current official
reference, QClass Day 2 and inspector comparison through Computer Use. Installed
tools performed only reads and dry runs; no cue setters, execution or QLab
configuration changes.

QLab 5.5.10; single workspace `redacted-workspace-6b31c91e.qlab5`, UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`. The QLab window confirmed path
`<redacted-local-path-851cab375f>.qlab5`, Edit Mode and zero Active Cues.

Structured evidence is in
[2026-10-09-video-fx-closure-audit.json](2026-10-09-video-fx-closure-audit.json).
Earlier Gamma/Exposure and EdgeWork writes are historical evidence identified in
[previous validation](../runtime-validation/2026-10-09-osc-text-fonts-video-fx.md);
they were not repeated as writes during this review.

## Sources and comparison

- [Official Parameter Reference](https://qlab.app/docs/v5/scripting/parameter-reference/):
  all published effects, keys, types, bands and options were compared against
  `src/qlab_mcp/write/video_fx_catalogue.json`. Result: **60 effects, 262
  parameters, zero differences**: 229 numbers, 21 enums, 11 four-component vectors
  and 1 boolean.
- Local OSC dictionary `docs/references/qlab_osc_dictionary.md`, line 4744 and
  lines 5183–5273: blendMode and effect-route contracts.
- [Video Cues, Video FX](https://qlab.app/docs/v5/video/video-cues/#the-video-fx-tab):
  layered composition, cue effects and stack order.
- Local QClass `docs/qclass/September 2025 QClass 5.5 at the Voxel - Day 2.md`:
  4:44:45–4:48:41 and 5:00:50 onward. It provides design/use context, not evidence
  of OSC capability or setter acceptance.
- The local MANIFEST notes that the reference PDF was created on 2025-11-25,
  before 5.5.10. That PDF is not presented as verification of the live version.

## Blend Mode

There are **24 modes**; UI menu names, reference and `VALID_BLEND_MODES` agree.
Blend Mode selects a compositing method; it is distinct from parameterized
video effects.

OSC documents reading/writing `/cue/{cue_number}/blendMode` with a full name.
MCP uses UUIDs and Video/Camera/Text wrappers. An installed dry run on v11
proposed `Screen` from `Color Burn`, with one planned setter and
`executed_operations=[]`. Reads and UI retained `Color Burn`.

The inventory has no missing names. This review does not test all 24 setters
or their visual playback results.

## Video FX: inventory and contract

QLab's Add video effect menu showed **60 names**, identical to the reference
labels. The list does not require a separate tool for each effect.

Documented routes support:

- Inventorying existing effects.
- Reading/changing enabled by index.
- Reading/changing a parameter by index and key.
- Reading/changing several parameters through internal JSON.
- Adding, inserting, moving and deleting effects.

MCP already models these operations in Video, Camera and Text. Internally
generated JSON and indexed writes avoid free-form addresses and ambiguous name
selection when effects repeat.

Documentation permits some out-of-band values. Current MCP policy limits new
writes to published bands and preserves external observations without normalizing
them.

## Current MCP/UI comparison

Fixture: v11, UUID `CC889BBC-471F-5039-854E-5F61184B73D6`.
Get with selector `EdgeWork/index=0` confirmed:

- Blend Mode `Color Burn`, matching UI.
- `inputRadius=10`, UI 10,000.
- `inputIntensity=2.6191787719726562`, UI 2,619.
- `Choose_Effect=0`; UI Edge Work/Edges menu matches the documented enum.

Installed dry runs:

1. Change radius to 8: accepted, no setters.
2. Add ColorControls: blocked, result defaults/identity unvalidated.
3. Delete EdgeWork: blocked, reconstruction through insert unvalidated.

## Work required for closure

### 1. Sufficient Get information

`read_selected()` returns index, type, parameters and raw_attributes. It does
not return type/band/enum metadata or selector enabled state. EdgeWork summary
returned enabled=null, while UI shows it enabled. The OSC enabled route is
documented and the writer already reads it.

Extend existing Gets with enabled and metadata for requested parameters,
preserving errors/unknown values without automatically traversing every instance.
Provide catalogue discovery through a bounded documentary selector or specific
catalogue read; the 60/262 count alone cannot discover every key and option.
Decide the API shape before implementation.

### 2. Defaults and structural operations

Source validates creation/reconstruction of **Gamma and Exposure** on 5.5.10.
Verified defaults are missing for **58 effects**. Their add/insert remains
blocked; delete requires verifiable reconstruction. Move requires a complete
stack, identities and Fade dependency checks.

Obtain each baseline in isolated fixtures; test add/insert and restoration with
readable values. Record additional runtime parameters and enabled state rather
than inferring defaults from documented bands.

### 3. Parameter and submode coverage

A complete catalogue does not prove all 262 setters. Test numbers, enums,
booleans and vectors; compare direct and aggregate values, every neighboring
parameter and neighboring effects.

For Choose_Effect, Choose_Blur and Shape, check which parameters hide, change or
normalize. The current verifier rejects unexpected changes after a setter;
that does not replace understanding and planning those effects before writing.
Window/inputRectangle needs its relationship to its components checked.

### 4. Identity and repeated effects

On 5.5.10 the inventory can be a list of parameter dictionaries without instance
type/UUID. Source uses a native name-based read that must match one unique
indexed payload. It does not infer type from keys.

Ambiguous/repeated stacks block writes; add rejects a type already present.
Investigate documented identity proof for those cases and retain the block when
OSC cannot distinguish them. An indexed setter alone does not establish universal
coverage.

### 5. Dependencies and real limits

Retain preflight, signed tokens, one send and fresh readback. Order changes with
dependent Fade cues stay blocked until parameter/flag correspondence can be
verified.

FX parameter Fade remains pending; do not enable flags by analogy. The UI Set
Default Parameters button has no specific documented route in the inspected
Video FX section. A reset implemented through values must describe restoring
verified defaults without claiming equivalence to the button. /live and playback
remain outside the agreed scope.

## Proposed closure sequence

1. Complete metadata, enabled and documentary discovery in Gets.
2. Validate defaults of the remaining 58 effects, starting with ColorControls,
   WhitePoint, Shutter, Window and NinePartTiled to cover types and dependencies.
3. Validate each effect's parameters/submodes with baseline → dry run → single
   setter → fresh readback → UI comparison → restoration with a new token.
4. Extend add/insert/delete/move only for effects with complete evidence.
5. Resolve repeated identities/dependencies if OSC supplies sufficient evidence;
   publish remaining limits explicitly.

Closure requires an effect/operation matrix: verified, blocked by an OSC
limitation, or pending a test. Do not remove blocks merely because a command is
present in the dictionary.

## Checks

`.venv/bin/pytest -q tests/test_visual_cue_writes.py tests/test_video_fx_operations.py`:
**105 passed**. The earlier FX/blend test selection passed 31 tests. The full
suite was not rerun because this audit changed no source.
