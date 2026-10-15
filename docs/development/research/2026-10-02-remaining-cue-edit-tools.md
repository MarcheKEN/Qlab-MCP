> Historical adapter inventory. The completed shared executor and current limits
> are described in [2026-10-05 completion](2026-10-05-remaining-cue-completion.md).
> The separate-executor and single-property descriptions below are superseded.

# Remaining typed cue editors

This migration splits the existing profile executor into nine UUID-only public
tools. It does not promote an unverified endpoint solely because it has a
documented setter. The repository [OSC snapshot](../../references/qlab_osc_dictionary.md),
`write/registry.py` and the existing per-family preflight/readback implementations
define the scope. The schema exposes saved requests; the explicit dry-run is
authoritative for whether a gated operation can execute.

| Tool family | Typed saved settings | Existing limits |
| --- | --- | --- |
| Audio | Media, output patch UUID, timing/loops, Levels, slices, indexed Audio Object settings | Bounds, media health, file roots and specialized gates; spatial routes remain planned-only |
| Mic | Input/output patch UUID, Levels and channel format | Format capacity remains unverified |
| Light | Command text, Always Collate, Subcontroller | Existing command analysis and behavior tokens; mutation actions excluded |
| Fade | Exact cue/patch targets, completion, modes, geometry and Levels | Existing target-bound one-property gates; unverified patch/object/curve/path routes remain planned-only |
| Network | Patch UUID, message, parameter and fade settings | Network patch message type cannot be proven; configuration stays planned-only |
| MIDI | Patch UUID, Voice/MSC/SysEx, timecode and fade fields | Configuration stays planned-only; byte/channel ranges remain strict |
| MIDI File | Media/patch UUID, playback timing, rate, count | Existing supported metadata writes; unverified file/routing remain gated or planned-only |
| Timecode | MTC/LTC, frame rate, start/end, patch UUIDs, LTC output | LTC writes require positive channels; read zero remains an observed unpatched state |
| Script | Basics and common OSC Triggers | `scriptSource` is documented read-only; `compileSource` is not a parameter edit |

Each call accepts 1–50 unique exact cue UUIDs with typed properties and
`confirm_gates`. Family-specific requests reuse the generic executor and its
existing single-property limits and tokens. Requests containing common OSC
Triggers route to the signed five-minute single-use Control executor. They may
include common Basics; mixing family-specific fields or items is rejected before
OSC because the two executors have different confirmation/dependency policies.

Details expose current Triggers and capabilities. Unknown scalar scope readback
blocks Fade & Stop; Timecode trigger edits use the containing list's format and
never infer activation. Public models reject null edits, boolean-as-number,
non-finite numbers, unknown fields and deprecated aliases. Indexed operation
arguments remain typed. Alias collisions targeting the same OSC path are
rejected before calling the executor.

Audio Maps, /live, cue execution, workspace setters and source compilation are
excluded. Get details retain bounded, configuration-only reads; they do not
scan every channel, object, parameter or slice. No dependencies, release or
version changes are included. The generic editor remains available for existing
clients and catalog-only research.

Acceptance uses focused adapter/transport regressions, real FastMCP calls with
simulated QLab, full suite, public schema inspection and `git diff --check`.
Live evidence, when collected, is recorded separately and never inferred from
these simulated calls.
