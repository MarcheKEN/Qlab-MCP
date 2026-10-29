# Lighting authoring completion — 2026-10-22

## Scope

Authorized native fixture: `mcp_prueba.qlab5`, UUID
`95F0A03D-140E-4673-974A-E76748EBB023`, QLab 5.5.10/build 5510.
Only newly created test definitions and two newly created, disarmed Light cues
were used. Existing fixture cues were not repaired or executed. Pending edits
were saved using the reviewed MCP Save flow. No playback or hardware output test.

## Light cue curves

The new public FastMCP tool was invoked through an in-process MCP client using
the current source and existing server environment. The already connected MCP
process does not reload source or schemas automatically.

Test cue UUIDs:

- `F32918E6-5163-4634-A170-F6036B4D25A4`
- `97B57008-64B3-4F1D-B06B-AF2CDEDBC4BF`

First preview/execution batch: ascending Custom with an interior point
`t=0.4,v=0.8`, descending Parametric 2.5, ascending S-Curve 2.5 and descending
Linear. Execution returned `verified`, `document_reopened=true` and
`saved_curve_verified=true`. QLab's native Curve inspector displayed all four
shapes, including the new Custom control point.

Second batch: remove the ascending interior point, create a descending Custom
point `t=0.6,v=0.2`, switch the second cue to ascending Parametric and descending
S-Curve. Execution again verified after reopening. Repeating the request as a
preview returned `no_op`, without replacement/reopen. Reusing its consumed token
returned `blocked` before any native/file action.

Native archives use `UID(0)` at the ends of `FadeShapeEntry.previous/next`.
The writer emits that native nil encoding and validates both native nil and
legacy synthetic fixture nulls. Comparing the second result with its recovery
baseline showed all existing outer archive objects unchanged. Existing inner
objects differed only in the two requested Light cues' `fade` pointers; new
curve branches were appended. Patch, definitions, other cues and MIDI data
remained preserved in that comparison.

These are saved-file and visual observations. OSC does not expose Light curve
values. Parametric 2.5 was tested; this does not validate every positive parameter
or unknown/mirrored shape. No physical lighting behavior is established.

## Native definition encoding capture

Created one unused 12-channel scalar definition through the existing MCP tool,
then added native controls through QLab's definition editor. Saved samples
confirmed these exact classes and output encodings:

| Type | Archive class suffix | Outputs |
| --- | --- | --- |
| `cmycolor` | `CMYColor` | map: cyan, magenta, yellow |
| `hsicolor` | `HSIColor` | map: hue, saturation, intensity |
| `pantilt` | `PanTilt` | map: pan, tilt |
| `muxer` | `Muxer` | ordered list referencing a CMY virtual control and a scalar |
| `rgbcolor` | `RGBColor` | map: red, green, blue, lime |

All class names begin `LightCueInstrumentDefinitionParameter`. Virtual controls
coexisted at negative channel keys and added no physical channels. The RGB native
selector explicitly offered `lime`, which was linked to the scalar named `lime`.
The writer acceptance below separately tests import and typed creation.

## Definition writer acceptance

One reviewed `qlab_edit_light_definitions` execution imported native CMY, HSI,
Pan/Tilt and One-to-Many manufacturer records and created a 12-physical-channel
custom definition containing all five virtual types, RGB lime and a nested
One-to-Many reference. The same-path transaction returned `verified` and reopened
the clean document. A second patch-editor execution assigned all five definitions
to five new instruments with `backend=none`; OSC-visible patch verification passed.
Fresh `qlab_get_workspace_light_settings` returned saved-patch coverage `complete`,
no diagnostics, all five instruments, all six parameter types and footprint 12
for the custom definition. Its default remained scalar index 5.

QLab's native Light Definitions editor displayed CMY, HSI, Pan/Tilt, RGB/lime,
`master → cmy,intensity` and `nested → master,rgb` exactly as created. The patch
editor displayed all five instruments with “No output selected”. Library imports
came from the unchanged bundled source fingerprint used by the preview.
The vendor records tested were AO Lighting Sky Falcon Arc colour 1200W (6),
Chauvet COLORado Batten 72 HSV (3), Chroma-Q Moving Mirror 8 bit and Chauvet
Strike Array 2 (2). This is representative acceptance, not certification of every
manufacturer definition or physical fixture.

## Definition update and command references

A native definition batch replaced the custom parameter list to change a home
value and `nested → master,hsi`, then renamed the definition. The existing test
instrument reference followed the rename, nested outputs survived, and the
physical footprint remained 12. Deleting that in-use definition was blocked.
One earlier execution was blocked with `needs_save` before Close when the
native document became dirty after preview; a fresh saved-state plan succeeded.

A separate reviewed OSC Light edit saved this text on the second disarmed test cue:

```text
Frontales Prueba = cue 288 * .5
Frontal Derecho = pass
```

The source test cue contained `Frontales Prueba = 25`. The editor returned
`updated`; fresh Light details preserved the exact dynamic text and reported
`isBroken=false`, `isWarning=false`, `armed=false`. No resulting output level was
computed or observed. Dependency/cycle/concurrency rejection uses automated
fixtures; this native check did not execute either cue.

## Final verification and cleanup

Full suite: **2,183 passed, 61 subtests passed, 35 skipped**. Localhost sockets
were enabled for simulated OSC transport tests; sandbox-denied socket failures
are not QLab runtime failures. FastMCP inspection reports **83 tools: 50 reads
and 33 gated writes**. Contracts include the separate typed curve editor.

The five new unpatched instruments and all six new test definitions were removed
through reviewed MCP editor batches. The resulting Light Patch snapshot matched
the saved pre-test baseline exactly. The two new disarmed Light cues were removed
through `qlab_delete_cues`. Final live inspection confirmed a clean, inactive Edit
Mode document, 50 original instruments, the three original definitions and no
remaining `MCP Virtual Fixture` instruments. No playback or physical DMX test.
