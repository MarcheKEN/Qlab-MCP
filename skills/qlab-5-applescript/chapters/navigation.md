# Navigation

The complete dictionary is in
[`../references/qlab_applescript_dictionary.md`](../references/qlab_applescript_dictionary.md).
Use exact names; do not infer a missing entry.

## Sections

| Section | Entries | Lookup |
|---|---:|---|
| Commands | 52 | `rg -n '^## <command>$' references/qlab_applescript_dictionary.md` |
| Classes | 23 | `rg -n '^## <class>$' references/qlab_applescript_dictionary.md` |
| Enumerations | 15 | `rg -n '^## <enumeration>$' references/qlab_applescript_dictionary.md` |
| Records | 6 | `rg -n '^## <record>$' references/qlab_applescript_dictionary.md` |

## Commands

`audition go`, `audition preview`, `capture timecode`, `clear`, `collapse`,
`collateAndStart`, `compile`, `delete`, `expand`, `getGang`,
`getInputChannelName`, `getLevel`, `getMute`, `getSolo`, `go`, `hardStop`,
`load`, `make`, `move`, `movePlayheadDown`, `movePlayheadDownASequence`,
`movePlayheadUp`, `movePlayheadUpASequence`, `moveSelectionDown`,
`moveSelectionUp`, `newCueWithAll`, `newCueWithChanges`, `panic`, `pause`,
`preview`, `prune`, `recordAllToLatest`, `recordAllToSelected`, `redo`,
`removeLightCommandsMatching`, `replaceLightCommand`, `reset`, `revert`,
`save`, `setGang`, `setInputChannelName`, `setLevel`, `setLight`, `setMute`,
`setSolo`, `shuffle`, `start`, `stop`, `undo`, `updateLatestCue`,
`updateOriginatingCues`, `updateSelectedCues`.

## Classes

`application`, `audio cue`, `camera cue`, `cue`, `cue list`, `devamp cue`,
`fade cue`, `group cue`, `light cue`, `light dashboard`, `load cue`, `mic cue`,
`midi cue`, `midi file cue`, `network cue`, `override controller`, `reset cue`,
`script cue`, `target cue`, `text cue`, `timecode cue`, `video cue`, `workspace`.

## Enumerations and records

Enumerations: `absolute relative`, `clock types`, `continue modes`,
`enabled disabled`, `fill styles`, `group modes`, `light dashboard view mode`,
`midi command`, `midi type`, `mtc ltc`, `smpte format`, `target modes`,
`timecode smpte format`, `timecode start`, `timecode stop`.

Records: `range record`, `rgba color record`, `row column record`, `size record`,
`slice marker record`, `text format record`.

## Examples and properties

- Examples: `rg -n '^```applescript$|com\.figure53\.QLab\.5' references/qlab_applescript_dictionary.md`.
- Properties: search the exact property name, then read the enclosing `##` class
  and its access/type/description table.
- Inherited properties: check the class's `Superclass` entry before claiming a
  property belongs directly to a cue subtype.
