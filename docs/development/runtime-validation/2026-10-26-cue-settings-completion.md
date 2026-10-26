# Light and Video cue settings — 2026-10-26

## Scope

QLab 5.5.10/build 5510, local `mcp_prueba.qlab5`, exact workspace UUID
`95F0A03D-140E-4673-974A-E76748EBB023`. No cues were started. Configuration
acceptance does not establish trigger execution, rendering, NDI audio or DMX output.

The source FastMCP server adds `qlab_edit_saved_cue_settings` (88 tools: 52 reads,
36 gated writes). Light/Video detail tools expose last-saved Hotkey and weekday
settings; Video also exposes selected audio track, bounded channel-name overrides,
sparse gang members, integrated audio envelope and FX identity. Dirty-state
freshness remains explicit. Reads do not save, close or reopen documents.

## Native evidence

| Capability | Observed result |
|---|---|
| Hotkey assignment | A disabled Control-Option-H assignment appeared in the Light cue's Triggers tab after the new tool reopened the document. Light and Video assignments were applied in one batch. |
| Hotkey activation | Separate enable/disable transactions succeeded on the assigned, disarmed Light cue. No key was pressed and no cue executed. |
| Wall Clock weekdays | Light Monday/Friday and Video Tuesday/Thursday were written; the Light UI displayed Monday, Friday. Trigger activation stayed disabled. |
| Integrated Video audio fade | Native Custom/Linear samples identified the embedded AudioCue's `downShape`. The tool replaced normalized points and preserved fade activation/lock flags; reopen and saved readback succeeded. |
| Audio track | A temporary MOV had one video and two audio tracks. Native selection produced track 3; the tool selected track 2, with OSC returning text `"2"`. Automatic selection is saved as -1. |
| Channel labels/gangs/slices | The existing Video editor wrote input 1's name, gang membership at row 1/column 1, Fade & Stop scope 2 and a marker at 1 second with play count 2. Readback and saved decoding agreed. |
| Compound Light values | Explicit RGB, CMY, HSI and Pan/Tilt commands were accepted through the Light editor. Native sliders/widgets corroborated their interpretation. Controls sharing physical channels can overwrite one another; analysis preserves command order. |
| NDI audio assignment | A temporary stage referenced an existing configured two-channel NDI route. The Video editor accepted `ndi-output`, binding the saved route/device and current destination metadata. No output was started or measured. |
| LinearKey/DropShadow | Native UI samples supplied complete NSKeyedArchiver subgraphs. The new editor inserted both effects and reopened QLab; the Video FX UI displayed all four native/sample instances. |

Native artifacts were retained outside Git under
`/private/tmp/qlab-cue-gap-implementation-20261026/`, including source MCP requests,
previews, results and saved snapshots. The original snapshot SHA-256 was
`b1147b6052a3e10b982ebd6c15a3106b5d24a4144b2a9c3dd5e97e6af96989d4`.
These local artifacts are not distributed fixture files and are not a guarantee
for another QLab version.

## Failure and recovery exercised

An early FX prototype placed an integer directly in a keyed dictionary's
`NS.objects`, rather than an object UID. QLab rejected that output. The original
was restored only after checking the empty document inventory and exact source,
output and recovery hashes; the rejected output and recovery were retained.
A regression now requires dictionary values to remain UIDs. A fresh confirmed
transaction using the corrected writer reopened successfully. No failed native
write was automatically retried.

A cleanup token was rejected before closing when another Untitled Workspace
appeared after preview. The target file hash and identity remained unchanged.
A fresh preview bound both documents and preserved the other document.

## Cleanup outcome

The Light command, shared trigger settings, Video target, output routing,
track, envelope, slice markers, gang, channel label and FX stack were restored.
The temporary Light instrument and definition were removed; the four temporary
FX instances were removed in the QLab interface. The channel label is restored
semantically to `L` as an explicit saved override, whereas its original value
was inherited.

The temporary stage `Audit NDI Audio` remains. Deletion correctly blocked on
references from two existing Video cues, `Sin slices` and `Con slices`, plus one
archived object. Both active cues now report the temporary stage. The original
saved archive had viewport references for those cues which do not match any
active stage in that archive; the cause of the subsequent reassignment was not
established. The cues were not redirected to an arbitrary replacement. The other
open Untitled Workspace was preserved. Do not treat this workspace as identical
to its pre-test state.

After MCP restart, attached tool calls read the restored Video settings and Light
saved settings, and a weekday dry run returned a plan with no executed operations.

## Verification limits

Archive postconditions verify saved properties. Native readback verifies cue
UUID/type, explicit audio-track selection, fade flags and FX count. An explicit
native FX type is compared when available; opaque OSC parameter dictionaries do
not prove a class identity. UI observation corroborated the accepted FX samples.
The editor does not claim every saved field has a public native getter.

Compound formatters require matching live parameter type and a native home-value
prototype, including component count. Unknown formatters remain unresolved.
Cue pulls without an explicit parameter retain all known parameters and their
dynamic reference; the analyzer does not calculate the referenced cue's look.

Objects, Audio Maps, Audio FX and Video Settings additions are outside this
increment. Existing FX OSC creation restrictions and repeated-type identity
restrictions remain; file insertion of the two validated templates is separate.

## Trim feasibility (research only)

The saved structure is `VideoCue.audioCue -> AudioCue.levels ->
AudioLevelMatrix.entries -> AudioLevelKnobs.trimLevel`. Occupied knobs also retain
row, column, initial level and gang references. In the inspected native archive,
entry indices matched `row * columns + column`; matrix capacity is not an actual
channel count. Video samples used unity trim. This establishes readable storage,
not a validated writer or audio behavior. No Trim operation is exposed.

The [official Trim documentation](https://qlab.app/docs/v5/audio/audio-cues/#the-trim-tab)
explains its distinction from ordinary automated levels. The
[Lighting Command Language](https://qlab.app/docs/v5/lighting/lighting-command-language/)
confirms multiparameter cue pulls and command ordering. Private archive evidence
is limited to the named version/build and native samples above.
