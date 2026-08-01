# Fade cue safe editing research

Status: 2026-07-14 — exact Audio-targeting-Mic runtime subset validated; remaining routes stay gated.

## Sources checked

- QLab 5 Reference Manual: [Fade cue audio](https://qlab.app/docs/v5/audio/fading-audio/),
  [Fade cue video](https://qlab.app/docs/v5/video/fading-video/), Cue inspector,
  Cues, Workspace, and Cue Lists.
- [QLab 5 OSC Dictionary](https://qlab.app/docs/v5/scripting/osc-dictionary-v5/)
  plus the local dictionary snapshot.
- Local `docs/references/qlab_osc_dictionary.md` Fade, target, audio-level,
  and geometry routes.
- Local QClass September 2025 transcripts for Curve and auto-continue behavior.
- `src/qlab_mcp/write/registry.py`, `src/qlab_mcp/write/operations.py`,
  `tests/test_write_mode.py`, and the FastMCP `qlab_edit_cues` contract.

## Confirmed saved OSC routes

- target and mode: `cueTargetID`, `targetMode`, `fadeType`, `levelsMode`,
  `geoMode`
- behavior: `stopTargetWhenDone`
- audio matrix: `doLevel/{row}/{column}`, `level/{inChannel}/{outChannel}`;
  readback through `doLevel` and `levels`
- geometry activation: `doOpacity`, `doRate`, `doRotation`, `doScale`,
  `doTranslation`
- inherited values: `opacity`, `rate`, `translation/x`, `translation/y`,
  `scale/x`, `scale/y`, `rotation`, `rotationType`, `quaternion`

`fadeType` means `1 = 1D Curve` and `2 = 2D Path`. `geoMode` and
`levelsMode` mean `0 = absolute` and `1 = relative`. Deprecated `mode` aliases
`levelsMode`, not `geoMode`. The exact QLab write sentinel is `-inf`; QLab
reads that saved value back as the workspace Audio `minVolume`, so silence
tokens and verification bind both values.

Cue targets documented for Fade include `Group`, `Audio`, `Mic`, `Video`,
`Camera`, `Text`, and Cue Lists. This implementation resolves cue UUIDs only.
New target assignment is promoted only for direct scalar targets whose
compatibility can be proven from one fresh target fingerprint: `Audio`, `Mic`,
`Video`, `Camera`, and `Text`. Existing Group targets may be edited or changed
away from, but assigning Group or Cue List fanout remains planned-only because
one target read cannot validate every affected child/running cue. Patch,
audio-map, temporary, name, and number targets are not promoted.

## Absolute and relative behavior

- Levels, translation, and rotation are additive in relative mode.
- Opacity and scale are multiplicative in relative mode.
- Absolute 3D rotation uses the documented four-component `quaternion` route
  when `rotationType=0`. Relative 3D rotation is not deterministic enough for
  this gate.
- The dictionary does not define a relative operator for `rate`, so rate-value
  writes require absolute geometry mode.
- `-inf` is permitted only for an absolute Levels destination. Relative Levels
  accept finite deltas only.

Audio writes bind the token to fresh source and target matrices, the exact
crosspoint, target audio evidence, and the activation matrix. Unsupported or
ambiguous matrix coordinates receive no token.

## Curve-tab finding

The UI exposes rising and falling curves, lock/mirror behavior, S-Curve,
Custom Curve, Parametric Curve with intensity, and Linear Curve. Its value
domains are Slider, Decibel, and Linear; no separate Auto domain was confirmed.
No documented deterministic Fade-cue OSC routes expose these selections or
their control points with exact readback. `fadeEntries` belongs to Network cues
and must not be reused. All Curve-tab internals remain planned-only.

## Safety model

Every promoted write requires one exact workspace UUID, one exact inactive
Fade UUID, one property/operation, saved mode, a dry-run token, fresh source
and target readback, one setter, and exact post-write readback. The target must
be healthy, inactive, non-self, and compatible with the property. The source
must already have `targetMode=0` and `fadeType=1`.

Generic tokens cannot authorize any `fade_basic` setter. Token families are:

- shared Basics: `confirm:fadeBasic:v1:`
- exact cue target: `confirm:fadeTarget:v1:`
- geometry: `confirm:fadeGeometry:v1:`
- Levels/audio matrix: `confirm:fadeAudio:v1:`
- completion behavior: `confirm:fadeBehavior:v1:`
- narrow broken-cue setup: `confirm:fadeSetup:v1:`
- exact setup recovery: `confirm:fadeRecovery:v1:`

## Property matrix

Table records local gates; closure section below records current runtime status.

| UI control / property | OSC route | Type / valid values | Prerequisites | Target types | Token family | Readback | Runtime result | Status | Reason |
|---|---|---|---|---|---|---|---|---|---|
| shared Basics | same saved route | existing validators | healthy inactive Fade/target; cue mode; 1D | Group, Audio, Mic, Video, Camera, Text | `fadeBasic:v1` | same property plus health | not run | supported locally | saved metadata with Fade-specific gate |
| Target cue | `cueTargetID` | exact UUID | same workspace; healthy inactive non-self direct cue | direct cue types above | `fadeTarget:v1` | UUID plus target fingerprint | not run | supported locally | deterministic cue resolution |
| Stop target when done | `stopTargetWhenDone` | boolean | valid direct target | direct cue types | `fadeBehavior:v1` | property plus health | passed | runtime-validated | live timeout; independent fresh readback confirmed requested value |
| Levels mode | `levelsMode` | `0` absolute, `1` relative | fresh matrices and proven target audio | Audio, Mic, Video/Camera with audio | `fadeAudio:v1` | mode and matrix fingerprints | validated for Audio-targeting-Mic | runtime-validated subset | deterministic scalar |
| Active crosspoint | `doLevel/{row}/{column}` | integer indexes; boolean | cell exists in source/target; cannot disable last parameter | audio-capable direct cues | `fadeAudio:v1`, setup/recovery | exact `doLevel` cell | validated for Audio-targeting-Mic | runtime-validated subset | documented activation matrix |
| Level crosspoint | `level/{input}/{output}` | finite dB; exact `-inf` only absolute | matching `doLevel=true`; existing cell; fresh Audio `minVolume` for silence | audio-capable direct cues | `fadeAudio:v1` | exact `levels` cell; `-inf` maps to `minVolume` | validated for Audio-targeting-Mic | runtime-validated subset | live QLab returned `-60` for `-inf`, matching current workspace minimum |
| Output slider | `sliderLevel/{channel}` | finite dB; exact `-inf` only absolute | matching row-0 `doLevel=true`; existing output | audio-capable direct cues | `fadeAudio:v1` | exact `sliderLevels` element | validated for Audio-targeting-Mic | runtime-validated subset | documented row-0 alias |
| Input channel label | `inputChannelName/{number}` | input `1..N`; safe string 1–64 chars | input exists in source/target | audio-capable direct cues | `fadeAudio:v1` | exact dynamic route | not run | supported locally | deterministic Levels metadata |
| Crosspoint gang | `gang/{input}/{output}` | non-Main input; existing output; safe string 0–64 chars | cell exists in source/target | audio-capable direct cues | `fadeAudio:v1` | exact dynamic route | not run | supported locally | one gang cell per call |
| Geometry mode | `geoMode` | `0` absolute, `1` relative | active geometry parameter | Video, Camera, Text | `fadeGeometry:v1` | same property | not run | supported locally | deterministic scalar |
| Opacity | `doOpacity`, `opacity` | boolean; `0..1` | value requires active flag | Video, Camera, Text | `fadeGeometry:v1`, setup/recovery | same properties/health | not run | supported locally | absolute value or relative multiplier |
| Rate activation/value | `doRate`, `rate` | boolean; finite positive rate | value requires active flag; value write requires `geoMode=0` | Audio, Video | `fadeGeometry:v1`, setup/recovery | same properties/health | not run | supported locally in absolute mode | relative operator is undocumented |
| Translation X/Y | `doTranslation`, `translation/x`, `translation/y` | boolean; finite numbers | value requires active flag | Video, Camera, Text | `fadeGeometry:v1`, setup/recovery | same properties/health | not run | supported locally | absolute value or relative delta |
| Scale X/Y | `doScale`, `scale/x`, `scale/y` | boolean; finite numbers | value requires active flag | Video, Camera, Text | `fadeGeometry:v1`, setup/recovery | same properties/health | not run | supported locally | absolute value or relative multiplier |
| X/Y/Z rotation | `doRotation`, `rotationType`, `rotation` | boolean; type `1/2/3`; finite degrees | active single-axis rotation | Video, Camera, Text | `fadeGeometry:v1`, setup/recovery | type/angle and health | not run | supported locally | deterministic single-axis readback |
| Target mode | `targetMode` | `0` cues, `1` patches | must already be `0` | mixed | none | same route | not run | planned-only | never switch silently to patch target |
| Fade type | `fadeType` | `1` Curve, `2` Path | must already be `1` | mixed | none | same route | not run | planned-only | switch can invalidate coupled state |
| 3D rotation | `quaternion`, `rotationType=0` | four finite components | active rotation; `geoMode=0` | Video, Camera, Text | `fadeGeometry:v1`, setup/recovery | exact four-component quaternion | not run | supported locally in absolute mode | relative 3D semantics remain unsafe |
| Z translation/scale | no documented Fade route | unavailable | unavailable | visual | none | unavailable | not run | planned-only | route is not exposed |
| 2D Path | QLab 5.5: `pathWidth`, `pathHeight`; no points/merge routes | positive scalars | `fadeType=2` | visual | none | incomplete | not run | planned-only | no deterministic full path model; 5.6 additions are outside the 5.5 contract |
| Curve controls | no deterministic documented Fade route | unavailable | unavailable | all | none | unavailable | not run | planned-only | UI is not an OSC contract |
| Set From Target actions | `setLevelsFromTarget`, `setGeometryFromTarget` | action | multi-property side effect | mixed | none | no atomic inverse | not run | planned-only | violates one-property rollback |
| Objects / Audio FX / Video FX | target-dependent | mixed | unresolved coupling | mixed | none | incomplete | not run | planned-only | explicitly out of scope |
| patch/map/temp/name/number targets | target-specific | mixed | violates exact cue UUID model | mixed | none | rejected | not run | planned-only | no silent target-mode change |

## Fade versus other curve systems

- **Fade Curve:** its inspector controls have no deterministic documented OSC
  configuration routes, so they remain planned-only.
- **Light Curve:** a different Light-cue system; its routes and tokens are not
  reused.
- **Network fades:** `fadeEntries`, `fadeFrom`, and `fadeTo` belong to Network
  cues and are never accepted as Fade Curve routes.

## Broken Fade setup and recovery

The normal broken-cue gate remains unchanged except for four exact shapes:

1. empty `cueTargetID` → assign one exact compatible direct cue target;
2. a saved `cueTargetID` proven unresolved or incompatible → replace it with
   one exact compatible direct cue target; a valid target is never replaced
   merely because another missing parameter leaves the Fade broken;
3. valid compatible target and no active parameter → enable exactly one of
   `doOpacity`, `doRate`, `doTranslation`, `doScale`, `doRotation`, or one
   exact `doLevel` matrix cell;
4. one active `doLevel` cell exists in the Fade matrix but not in the fresh
   target matrix → disable that exact invalid cell.

No Basics, mode, destination value, or behavior property can use this bypass.
Setup records the exact path, setup kind, baseline, request, target UUID/type,
matrix/audio fingerprints, and dependencies. If the result is unhealthy or
unexpected, only the inverse baseline operation against that same target and
fingerprint can receive `confirm:fadeRecovery:v1:`.

## Runtime fixtures required

- healthy absolute and relative visual Fades
- healthy absolute and relative audio Fades with readable matrices
- broken Fade without a target
- broken Fade with a compatible target and no active parameter
- compatible Audio, Mic, Video-with-audio, Camera, Video, Camera, Text, and
  Group target cues

Runtime proof remains dry-run → fresh token → one write → fresh readback →
fresh rollback token → rollback → final readback. No cue execution or save.

### Runtime evidence — `<TEST_WORKSPACE_NAME>`

The live `stopTargetWhenDone: true → false` dry-run on Fade
`<TEST_FADE_CUE_UUID>` returned
`confirm:fadeBehavior:v1:` with no executed operations. The authorized retry
timed out, but both the tool's fresh after-read and an independent MCP read
confirmed `false`; the cue remained healthy and inactive.

The Fade Audio setup then assigned the exact Video target and enabled
`doLevel/0/0`, making the broken Fade healthy. A subsequent `level/0/0 =
"-inf"` timed out and `/levels` remained `-60`. The current workspace Audio
minimum is `-60`, so this was already the semantic silence baseline. Local
preflight and verification now read and bind `/settings/audio/minVolume`,
reject a silence no-op, and compare `-inf` writes against the numeric minimum.
Runtime validation later completed for exact Mic targeting, absolute/relative
Levels, `doLevel`, `level`, `sliderLevel`, semantic `-inf`/workspace minimum,
`stopTargetWhenDone`, fresh readback, and `0.001 dB` tolerance. Final activity
was `0/0/0`. No claim extends to `inputChannelName`, gangs, visual Geometry,
setup/recovery, special resets, Curve internals, Path, Objects, FX, or fanout.
