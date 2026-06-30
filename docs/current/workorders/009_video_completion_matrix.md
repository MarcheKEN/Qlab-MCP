# Video Phase 5 - Completion Matrix and Closure Audit

Status: planned docs/audit phase; no new setters.

Goal: finish the Video domain by removing ambiguity, not by making every OSC
route writable. Each Video-family route or family must be classified as one of:

- runtime-validated real write
- safe dry-run/planned-only
- read-only
- blocked with explicit reason

Hard boundary:

- no runtime QLab tools
- no raw OSC
- no new real writes
- no token changes
- no write-scope expansion
- no commit

## Completion matrix

| Family | Examples | Current state | Phase 5 action |
|---|---|---|---|
| Video/Camera/Text opacity | `opacity` | runtime-validated real write, saved mode | keep closed |
| Video/Camera/Text translation | `translation/x`, `translation/y` | runtime-validated real write, saved mode | keep closed |
| Video/Camera/Text visual scalars | `scale/*`, `anchor/*`, `crop*` | runtime-validated real write, saved mode | keep closed |
| Video/Camera/Text appearance | `blendMode`, `preserveAspectRatio` | runtime-validated real write, saved mode | keep closed |
| Text basics | `text`, `text/format/fontSize`, `text/format/alignment` | runtime-validated real write, Text only | keep closed |
| Text style | shadow, underline, strikethrough, font/color families | blocked; QLab 5.5.10 did not provide reliable fresh baseline/readback | keep blocked |
| Video FX read model | `videoEffects` aggregate | read-only/summary plus technical raw payload | keep read-only |
| Video FX dry-run | enabled and scalar parameter previews by name/index | planned-only; no token, no setter | keep dry-run only |
| Video FX scalar 4C | `Video` `videoEffectIndex/0/parameter/inputRadius` | runtime-validated real write, exact UUID, saved, finite numeric | keep closed |
| Video FX scalar v2 | `Video` `videoEffectIndex/0/parameter/inputIntensity` | local candidate only; runtime validation not run | validate in separate runtime pass |
| Video FX enabled | `videoEffectIndex/enabled` | dry-run only when boolean baseline exists; real write blocked | keep blocked |
| Video FX name targeting | `videoEffect/{name}/parameter/*` | dry-run only; ambiguous names blocked | keep real write blocked |
| Video FX structural mutation | add/insert/delete/move/reorder | blocked | keep blocked |
| Video FX aggregate parameters | `videoEffect*/parameters` JSON | blocked | keep blocked |
| Camera/Text FX | inherited Video FX paths on Camera/Text cues | dry-run/read exploration only; no runtime real-write proof | keep real write blocked |
| FX color/structured/string/enum params | color arrays, dict/list values, enums/strings | blocked for real writes | keep blocked |
| `/live` variants | cue visual live paths, FX live paths, text live paths | blocked for MCP writes | keep blocked |
| Stage/region/surface | `stage/*`, region bounds, moveBy, control points | planned-only/read-only; visual topology risk | keep blocked |
| Workspace Video settings | input patches, routes, stages, undo/redo | read-only for inventory; mutations blocked | keep blocked |
| Video/camera patch refs | `videoInputPatch*`, `cameraPatch`, `stage*`, `videoOutputPatch*` | read-only or planned-only; target resolution risk | keep blocked |
| File target | `fileTarget` | blocked; file/path safety policy needed | keep blocked |
| Rotation/shutters/fade-only | quaternion, resetRotation, shutter, Fade `doOpacity` | blocked or outside current Video-family write gates | keep blocked |
| Batch/multi-property Video-family writes | multiple cue updates or multiple operations | blocked for gated Video-family real writes | keep blocked |

## Phase 5 deliverables

1. Keep this matrix current with docs, registry, and tests.
2. Clean documented contradictions before any new Video FX write.
3. Make the coverage snapshot explain generated registry counts versus
   specialized runtime-validated exceptions.
4. Keep Phase 6 as a separate implementation/runtime-validation track.

## Phase 6 candidate decision

Do not expand Video FX beyond the single Phase 6 candidate.

Phase 6 uses a new token family/version:

```text
confirm:videoFxScalar:v2:
```

Candidate boundary:

1. `inputIntensity` only, because it appears in the same flat payload shape as
   the validated `inputRadius` cue.
2. `inputPower` only after a separate cue/effect proof.
3. Never `Choose_Effect`; it behaves like selector/enum state, not a safe scalar.

Required Phase 6 proof per parameter:

- fresh dry-run token
- one saved setter
- matching fresh readback
- fresh-token rollback
- final baseline restored
- rejection probes before mutation with `executed_operations=[]`
- no `/live`, no raw OSC, no playback, no save
