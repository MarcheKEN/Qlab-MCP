# Workorder 023 - Text Cue Safe Editing

Status: runtime validation closed for safe subset.

Source: `docs/references/qlab_osc_dictionary.md`, Text cue messages.

## Scope

This phase is Text cues only through `qlab_edit_cues` / `text_basic`.

Token family: `confirm:textBasic:v1:`.

Runtime safety boundary:

- exact cue UUID only
- one cue, one property/operation
- saved mode only
- healthy inactive `Text` cue only
- readable baseline
- fresh dry-run token
- real write with exact token
- fresh exact readback
- rollback with fresh dry-run token
- no `/live`, batch, multi-property, raw OSC, playback, save, or cue create/delete

## Runtime-Confirmed Routes

| Property | OSC route | Value rule | Readback |
|---|---|---|---|
| `text` | `/cue/{cue_number}/text {string}` | string, max 20000 chars, newlines allowed | exact string |
| `fixedWidth` | `/cue/{cue_number}/fixedWidth {number}` | finite non-boolean number `>= 0`; `0` means automatic | numeric |
| `text/format/alignment` | `/cue/{cue_number}/text/format/alignment {alignment}` | exact `left`, `center`, `right`, or `justify` | exact string |
| `text/format/fontName` | `/cue/{cue_number}/text/format/fontName {name}` | non-empty string, max 128 chars, no control chars | exact string |
| `text/format/fontSize` | `/cue/{cue_number}/text/format/fontSize {number}` | finite non-boolean number, `0 < value <= 1000` | numeric |
| `text/format/lineSpacing` | `/cue/{cue_number}/text/format/lineSpacing {number}` | finite non-boolean number `>= 0` | numeric |
| `text/format/color` | `/cue/{cue_number}/text/format/color {red} {green} {blue} {alpha}` | four finite non-boolean numbers `0..1` | four-number array |

## Planned-Only / Runtime-Blocked

These routes remain dry-run/planned-only and do not emit `confirm:textBasic:v1:` tokens:

- `text/format/backgroundColor`
- `text/format/shadowColor`
- `text/format/strikethroughColor`
- `text/format/underlineColor`

Reason: QLab runtime did not expose reliable readable baseline/readback on
`Text1 / v1`, so real writes are not safely reversible.

## Read-Only / Detail Exposure

The safe Text profile reads these keys when available:

- `text`
- `text/fragments`
- `text/outputSize`
- `text/outputSize/width`
- `text/outputSize/height`
- `text/format/alignment`
- `text/format/fontFamily`
- `text/format/fontStyle`
- `text/format/fontFamilyAndStyle`
- `text/format/fontName`
- `text/format/fontSize`
- `text/format/lineSpacing`
- the RGBA routes above, when QLab exposes them

Missing keys remain missing; they are not normalized to fake empty values.

## Blocked

- `/live` variants
- full `text/format {json_string}` and `text/format/live`
- substring/range/word formatting
- `text/format/fontFamily` and `text/format/fontStyle` writes; documented as read-only
- `text/format/fontFamilyAndStyle`; blocked pending installed-font pair proof and exact readback
- `text/outputSize*` writes; read-only output-size routes
- Phase 3F shadow blur/offset and underline/strikethrough style routes; QLab 5.5.10 did not provide reliable fresh baseline/readback in prior runtime validation
- background, shadow, strikethrough, and underline color routes; QLab runtime did not expose reliable readable baseline/readback on the safe Text cue
- Video/Camera/Audio/Fade/Network promotion
- Stage Editor, surfaces, regions, warping, Video FX, Fade cue editing, Network fade editing

## Local Test Status

`tests/test_write_mode.py` covers:

- dry-run token emission
- real write path and rollback for scalar routes and `text/format/color`
- planned-only rejection for runtime-blocked color routes
- invalid value rejection without token
- wrong type/profile/ref, batch, multi-property, `/live`, fake/wrong/stale token, and active/unhealthy cue rejection
- exact OSC setter paths and no `/live`

Runtime validation closed on `mcp_prueba.qlab5` using `Text1 / v1`.
