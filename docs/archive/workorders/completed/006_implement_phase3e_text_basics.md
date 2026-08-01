# Video Phase 3E — Text Basics

Status: runtime validated + closed.

## Support matrix

| Property | Cue type/profile | Validation | Readback |
|---|---|---|---|
| `text` | Text / `text_basic` | plain string | exact |
| `text/format/fontSize` | Text / `text_basic` | finite number, `0 < value <= 1000` | numeric tolerance `abs=1e-5`, `rel=1e-6` |
| `text/format/alignment` | Text / `text_basic` | `left`, `center`, `right`, or `justify` | exact normalized value |

Token family: `confirm:textBasic:v1:`.

Video and Camera cues are not eligible.

## Gate

- one cue and one property
- UUID cue reference
- exact `text_basic` profile and `Text` cue type
- saved mode only
- healthy, inactive cue
- fresh deterministic baseline
- exact workspace, cue, type, profile, property, path, value, mode, operation,
  risk, and baseline-hash token binding
- exactly one setter
- fresh readback verification
- new dry-run/token for rollback
- no mutating retry after uncertainty

Setter timeout plus matching fresh readback is confirmed success with warning
`setter_timeout_but_readback_matched`.

## Runtime validation

Independently validated in QLab 5.5.10:

- workspace: `<TEST_WORKSPACE_NAME>`
- workspace UUID: `<TEST_WORKSPACE_UUID>`
- cue: `<TEST_TEXT_CUE_NAME>`
- cue UUID: `<TEST_TEXT_CUE_UUID>`
- initial and final baseline:
  - `text`: `"Mcp video text"`
  - `text/format/fontSize`: `72`
  - `text/format/alignment`: `"center"`
- 3/3 real writes passed
- 3/3 rollbacks passed with a fresh dry-run and token
- 12/12 rejection probes passed before mutation
- every rejection returned `executed_operations=[]`
- final baseline was restored exactly
- cue remained healthy and inactive
- global running/paused/auditioning counts were 0/0/0
- no GO, playback, audition, `/live`, raw OSC, save, or unrelated mutation
  occurred

All six setters timed out. Fresh readback matched each requested value, so each
result correctly returned `status="updated"` with warning
`setter_timeout_but_readback_matched`. No setter was retried.

## Rejection probes

Confirmed rejection before mutation for malformed token, stale token,
wrong-property token, cue number instead of UUID, Video cue, Camera cue, batch,
multi-property update, live mode, `fontName`, rich color formatting, and a
broken Text cue.

## Risk note

Changing plain `text` may inherit formatting from the existing first
character. Phase 3E verifies exact plain-text readback only; rich formatting
was not modified or validated.

## Still blocked

Video/Camera text writes, `fontName`, text/background/shadow colors, underline,
strikethrough, full `text/format`, rich text objects, `/live`, batch and
multi-property writes, playback, raw OSC, Workspace Video, Video FX,
`fileTarget`, patches, stage/route/surface, rotation, shutters, and
`doOpacity`.

## Next candidate phase

Phase 3F — Text Style is optional and future-only: `fontName`, text and
background colors, shadow, underline, and strikethrough. Do not implement any
property until the OSC dictionary route and exact deterministic readback are
clear.
