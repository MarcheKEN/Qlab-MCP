# QLab's AppleScript Dictionary

The list of commands, functions, properties, and so on that AppleScript can use to interact with an application is called that application's dictionary. You can find QLab's AppleScript dictionary here, or view it within the Script Editor application, which is found in /Applications/Utilities.

In Script Editor, choose *Open Dictionary...* from the **File** menu, and choose QLab from the list of applications.

AppleScript dictionaries are grouped by "suite"; all applications that use AppleScript must include the *Standard Suite*, and then any application-specific commands or properties are generally grouped together into another suite named after the application.

This documentation only describes the commands, classes, enumerations, and records from the *QLab Suite*. Items from the *Standard Suite* can also be used in QLab, such as the **save** command, which saves a specified workspace.

Readers are enthusiastically encouraged to use the navigation sidebar on this page, as AppleScript dictionaries are exceedingly verbose. Readers of the PDF version of this manual are encouraged to brace themselves accordingly.

# Commands

---

<a id="audition-go"></a>
## audition go

*(verb):* make a workspace Audition GO.

#### Syntax

```applescript
audition go {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace to GO. |

#### Classes

The following classes respond to the **audition go** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  audition go
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  audition go workspace "hamlet.qlab5"
end tell
```

---

<a id="audition-preview"></a>
## audition preview

*(verb):* Audition preview one or more cues. Previewing a cue starts the action of that cue, skipping pre-waits and ignoring auto-follows and auto-continues.

#### Syntax

```applescript
  preview {cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue(s) to preview. |

#### Classes

The following classes respond to the **audition preview** command:

- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  audition preview cue "1"
end tell
```

---

<a id="capture-timecode"></a>
## capture timecode

*(verb):* Set the cue's timecode trigger to the current incoming timecode received by its parent cue list.

#### Syntax

```applescript
  capture timecode {cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue whose timecode trigger is to be captured. |

#### Classes

The following classes respond to the **capture timecode** command:

- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  capture timecode cue "1"
end tell
```

---

<a id="clear"></a>
## clear

*(verb):* clear the levels in the Light Dashboard.

#### Syntax

```applescript
clear {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard you want to clear. |

#### Classes

The following classes respond to the **clear** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  tell theDashboard to clear
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  clear theDashboard
end tell
```

---

<a id="collapse"></a>
## collapse

*(verb):* collapse a Group cue or cue list.

#### Syntax

```applescript
collapse {group cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | group cue | The Group cue that will collapse. |

#### Classes

The following classes respond to the **collapse** command:

- [group cue](#group-cue)
- [cue list](#cue-list)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  collapse cue "1"
end tell
```

---

<a id="collateandstart"></a>
## collateAndStart

*(verb):* collate and start a Light cue.

#### Syntax

```applescript
collateAndStart {light cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light cue | The Light cue that you want to collate and start. |

#### Classes

The following classes respond to the **collateAndStart** command:

- [light cue](#light-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  collateAndStart cue "1"
end tell
```

---

<a id="compile"></a>
## compile

*(verb):* verify and prepare the script for use.

#### Syntax

```applescript
compile {script cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | script cue | The Script cue whose source you want to (re)compile. |

#### Classes

The following classes respond to the **compile** command:

- [script cue](#script-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  compile cue "1"
end tell
```

---

<a id="delete"></a>
## delete

*(verb):* delete a cue or list of cues.

#### Syntax

```applescript
delete {cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue or list | The cue or cues to delete. |

#### Classes

The following classes respond to the **delete** command:

- [cue](#cue)

#### Examples

```applescript
-- the cue whose cue number is "1"
delete cue "1" 

-- one or several selected cues
delete selected
```

```applescript
-- a list of cues based on position in the cue list
set listOfCues to cues 3 thru -1 of myCueList
delete listOfCues

-- an indivdual cue by position
delete last cue of myGroupCue
```

---

<a id="expand"></a>
## expand

*(verb):* expand a Group cue or cue list.

#### Syntax

```applescript
expand {group cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | group cue | The Group cue that will expand. |

#### Classes

The following classes respond to the **expand** command:

- [group cue](#group-cue)
- [cue list](#cue-list)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  expand cue "1"
end tell
```

---

<a id="getgang"></a>
## getGang

*(verb):* get the gang for a specified location in the cue's matrix.

#### Syntax

```applescript
set theResult to getGang {cue} row {row_number} column {column_number}
```

#### Result

*text:* the value of the gang at the specified location in the cue's matrix.

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to get the gang. |
| column | ✓ | integer | The column of the level matrix. Column 0 is the main and input levels column. |
| row | ✓ | integer | The row of the level matrix. Row 0 is the main and output levels row. |

#### Classes

The following classes respond to the **getGang** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [fade cue](#fade-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theGang to getGang 1 row 0 column 1
  display dialog "The gang for row 0, column 1 is: " & theGang
end tell
```

---

<a id="getinputchannelname"></a>
## getInputChannelName

*(verb):* get the input name for a specified input channel.

#### Syntax

```applescript
set theResult to getInputChannelName {cue} row {row_number}
```

#### Result

*text:* the name for the input channel.

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to get the audio input name. |
| row | ✓ | integer | The row of the level matrix. Starts at 1. |

#### Classes

The following classes respond to the **getGang** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theName to getInputChannelName 1 row 2
  display dialog "The input name for input 2 of cue 1 is: " & theName
end tell
```

---

<a id="getlevel"></a>
## getLevel

*(verb):* get the level for a specified location in the cue's matrix.

#### Syntax

```applescript
set theResult to getLevel {cue} row {row_number} column {column_number}
```

#### Result

*real number:* the level in decibels of the specified location in the cue's matrix.

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to get the level. |
| column | ✓ | integer | The column of the level matrix. Column 0 is the main and input levels column. |
| row | ✓ | integer | The row of the level matrix. Row 0 is the main and output levels row. |

#### Classes

The following classes respond to the **getLevel** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [fade cue](#fade-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theLevel to getLevel 1 row 0 column 1
  display dialog "The level for row 0, column 1 of cue 1 is: " & theLevel
end tell
```

---

<a id="getmute"></a>
## getMute

*(verb):* get the status of the mute button for a specified output of the cue.

#### Syntax

```applescript
set theResult to getMute {cue} output {output_number}
```

#### Result

*boolean:* the state of the specified mute control.

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to get the mute state. |
| output | ✓ | integer | The output of the level matrix. Output 0 is the main level. |

#### Classes

The following classes respond to the **getMute** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theMute to cue "6" getMute output 1
  display dialog "The mute state of output 1 is: " & theMute
end tell
```

---

<a id="getsolo"></a>
## getSolo

*(verb):* get the status of the solo button for a specified output of the cue.

#### Syntax

```applescript
set theResult to getSolo {cue} output {output_number}
```

#### Result

*boolean:* the state of the specified solo control.

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to get the solo state. |
| output | ✓ | integer | The output of the level matrix. Output 0 is the main level. |

#### Classes

The following classes respond to the **getMute** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theSolo to cue "6" getMute output 1
  display dialog "The solo state of output 1 is: " & theMute
end tell
```

---

<a id="go"></a>
## go

*(verb):* make a workspace GO.

#### Syntax

```applescript
go {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace to GO. |

#### Classes

The following classes respond to the **go** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5"
  go front workspace
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  go workspace "hamlet.qlab5"
end tell
```

---

<a id="hardstop"></a>
## hardStop

*(verb):* hardStop one or more cues or workspaces.

#### Syntax

```applescript
hardStop {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The cue(s) or workspace(s) to hardStop. |

#### Classes

The following classes respond to the **hardStop** command:

- [workspace](#workspace)
- [cue list](#cue-list)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5"
  hardStop cue "1"
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  hardStop front workspace
end tell
```

---

<a id="load"></a>
## load

*(verb):* load one or more cues or workspaces to a given time. A negative value loads that many seconds back from the end of the cue.

#### Syntax

```applescript
load {reference} time {real number}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The cue(s) or workspace(s) to load. |
| time |  | real number | Load time. |

**Note:** Because "load" is both a noun and a verb in QLab (load vs. Load cue), you need to place the reference within parentheses; see examples below.

#### Classes

The following classes respond to the **load** command:

- [workspace](#workspace)
- [cue list](#cue-list)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5"
  -- load the cue whose cue number is "1"
  load (cue "1")
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  -- load the cue whose cue number is "2" to 15 seconds
  load (cue "2") time 15
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  -- load the cue whose cue number is "3" to 20 seconds before the end of the cue
  load (cue "3") time -20
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  -- load the cue whose cue id is 4
  load (cue 4)
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  -- this does not work!
  -- AppleScript thinks you're talking about a Load cue whose cue number is "5"
  load cue "5"
end tell
```

---

<a id="make"></a>
## make

*(verb):* make a new cue in a workspace. The cue will be created below the currently selected cue.

#### Syntax

```applescript
make {workspace} type {text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace in which the cue will be made. |
| type | ✓ | text | The name of the kind of cue you want to create (audio, video, camera, etc.) To create a new cue list, use "cue list". To create a new cue cart, use "cue cart". |

#### Classes

The following classes respond to the **make** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5"
  make front workspace type "audio"
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  make front workspace type "cue list"
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  make workspace "hamlet.qlab5" type "midi"
end tell
```

---

<a id="move"></a>
## move

*(verb):* move a cue or list of cues to a new location.

#### Syntax

```applescript
move {reference to cue or list} to {location specifier}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference to cue or list of cues | The cue or list of cues to move. |
| to | ✓ | location specifier | The new location for the cue or cues. |

#### Examples

```applescript
-- moving a cue
set theCue to cue "FROMCUE"
set theDestination to cue "DESTCUE"
move theCue to {after|before|beginning of|end of} theDestination
```

```applescript
-- moving a list of cues
set theCues to {list_of_cues}
set theDestination to cue "DESTCUE"
move theCues to {after|before|beginning of|end of} theDestination
```

```applescript
-- by position within a group or list
set theGroupCue to cue "MYGROUP"
set theDestination to cue "DESTCUE"
move last cue of theGroupCue to {after|before|beginning of|end of} theDestination
```

---

<a id="moveplayheaddown"></a>
## movePlayheadDown

*(verb):* move the playhead to the next cue.

#### Syntax

```applescript
movePlayheadDown {specifier}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace or cue number | The workspace or cue list whose playhead will change. |

#### Classes

The following classes respond to the **movePlayheadDown** command:

- [workspace](#workspace)
- [cue list](#cue-list)

#### Examples

```applescript
-- move the playhead to the next cue in the active cue list of the front workspace
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadDown
end tell
```

```applescript
-- move the playhead to the next cue in the active cue list of a specific workspace
tell application id "com.figure53.QLab.5"
  movePlayheadDown workspace "hamlet.qlab5"
end tell
```

```applescript
-- move the playhead to the next cue in a cue list numbered "101" in the front workspace
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadDown cue "101"
end tell
```

```applescript
-- move the playhead to the next cue in a cue list numbered "101" in a specific workspace
tell application id "com.figure53.QLab.5" to tell cue "101" of workspace "ophelia"
  movePlayheadDown
end tell
```

---

<a id="moveplayheaddownasequence"></a>
## movePlayheadDownASequence

*(verb):* move the playhead to the top of the next cue sequence.

#### Syntax

```applescript
movePlayheadDownASequence {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace whose playhead will change. |

#### Classes

The following classes respond to the **movePlayheadDownASequence** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadDownASequence
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  movePlayheadDownASequence workspace "hamlet.qlab5"
end tell
```

---

<a id="moveplayheadup"></a>
## movePlayheadUp

*(verb):* move the playhead to the previous cue.

#### Syntax

```applescript
movePlayheadUp {specifier}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace or cue number | The workspace or cue list whose playhead will change. |

#### Classes

The following classes respond to the **movePlayheadUp** command:

- [workspace](#workspace)

#### Examples

```applescript
-- move the playhead to the next cue in the active cue list of the front workspace
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadUp
end tell
```

```applescript
-- move the playhead to the next cue in the active cue list of a specific workspace
tell application id "com.figure53.QLab.5"
  movePlayheadUp workspace "hamlet.qlab5"
end tell
```

```applescript
-- move the playhead to the next cue in a cue list numbered "101" in the front workspace
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadUp cue "101"
end tell
```

```applescript
-- move the playhead to the next cue in a cue list numbered "101" in a specific workspace
tell application id "com.figure53.QLab.5" to tell cue "101" of workspace "ophelia"
  movePlayheadUp
end tell
```

---

<a id="moveplayheadupasequence"></a>
## movePlayheadUpASequence

*(verb):* move the playhead to the top of the previous cue sequence.

#### Syntax

```applescript
movePlayheadUpASequence {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace whose playhead will change. |

#### Classes

The following classes respond to the **movePlayheadUpASequence** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  movePlayheadUpASequence
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  movePlayheadUpASequence workspace "hamlet.qlab5"
end tell
```

---

<a id="moveselectiondown"></a>
## moveSelectionDown

*(verb):* select the next cue.

#### Syntax

```applescript
moveSelectionDown {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace whose selection will change. |

#### Classes

The following classes respond to the **moveSelectionDown** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  moveSelectionDown
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  moveSelectionDown workspace "hamlet.qlab5"
end tell
```

---

<a id="moveselectionup"></a>
## moveSelectionUp

*(verb):* select the previous cue.

#### Syntax

```applescript
moveSelectionUp {workspace}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | workspace | The workspace whose selection will change. |

#### Classes

The following classes respond to the **moveSelectionUp** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  moveSelectionUp
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  moveSelectionUp workspace "hamlet.qlab5"
end tell
```

---

<a id="newcuewithall"></a>
## newCueWithAll

*(verb):* create a new Light cue containing levels for all parameters of all instruments.

#### Syntax

```applescript
newCueWithAll {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to create a new Light cue. |

#### Classes

The following classes respond to the **newCueWithAll** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  newCueWithAll theDashboard
end tell
```

---

<a id="newcuewithchanges"></a>
## newCueWithChanges

*(verb):* create a new Light cue containing levels for all manually adjusted parameters in the Light Dashboard.

#### Syntax

```applescript
newCueWithChanges {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to create a new Light cue. |

#### Classes

The following classes respond to the **newCueWithChanges** command:

- [workspace](#workspace)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  newCueWithChanges theDashboard
end tell
```

---

<a id="panic"></a>
## panic

*(verb):* panic one or more cues or workspaces.

#### Syntax

```applescript
  panic {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The cue(s) or workspace(s) to panic. |

#### Classes

The following classes respond to the **panic** command:

- [workspace](#workspace)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  panic
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  panic front workspace
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  panic cue "1"
end tell
```

---

<a id="pause"></a>
## pause

*(verb):* pause one or more cues or workspaces.

#### Syntax

```applescript
  pause {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The cue(s) or workspace(s) to pause. |

#### Classes

The following classes respond to the **pause** command:

- [workspace](#workspace)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  pause
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  pause front workspace
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  pause cue "1"
end tell
```

---

<a id="preview"></a>
## preview

*(verb):* preview one or more cues. Previewing a cue starts the action of that cue, skipping pre-waits and ignoring auto-follows and auto-continues.

#### Syntax

```applescript
  preview {cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue(s) to preview. |

#### Classes

The following classes respond to the **preview** command:

- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  preview cue "1"
end tell
```

---

<a id="prune"></a>
## prune

*(verb):* remove light commands that have no effect from a Light cue.

#### Syntax

```applescript
  prune {light cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light cue | The Light cue(s) whose command text you want to prune. |

#### Classes

The following classes respond to the **prune** command:

- [light cue](#light-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  prune cue "1"
end tell
```

---

<a id="recordalltolatest"></a>
## recordAllToLatest

*(verb):* record all levels for all parameters of all instruments into the latest run Light cue.

#### Syntax

```applescript
  recordAllToLatest {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to record all to the latest cue. |

#### Classes

The following classes respond to the **recordAllToLatest** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  recordAllToLatest theDashboard
end tell
```

---

<a id="recordalltoselected"></a>
## recordAllToSelected

*(verb):* record all levels for all parameters of all instruments into the selected Light cue(s).

#### Syntax

```applescript
  recordAllToSelected {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to record all to the selected cue(s). |

#### Classes

The following classes respond to the **recordAllToSelected** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  recordAllToSelected theDashboard
end tell
```

---

<a id="redo"></a>
## redo

*(verb):* redo the last undone action.

#### Syntax

```applescript
  redo {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The workspace or Light Dashboard in which you want to redo the last undone action. |

#### Classes

The following classes respond to the **redo** command:

- [workspace](#workspace)
- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  redo
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  redo theDashboard
end tell
```

---

<a id="removelightcommandsmatching"></a>
## removeLightCommandsMatching

*(verb):* remove existing light commands in the specified cue matching the command provided.

#### Syntax

```applescript
  removeLightCommandsMatching {cue} command {text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue from which you want to remove light commands. |
| command | ✓ | text | The full text of the light command you want to remove. |

#### Classes

The following classes respond to the **removeLightCommandsMatching** command:

- [light cue](#light-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  removeLightCommandsMatching cue "1" command "myLight.intensity = 100"
end tell
```

---

<a id="replacelightcommand"></a>
## replaceLightCommand

*(verb):* replace a specified light command in the specified cue with a new light command.

#### Syntax

```applescript
  replaceLightCommand {cue} oldCommandText {text} newCommandText {text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue in which you want to replace light commands. |
| newCommandText | ✓ | text | The full text of the light command that will replaced the old. |
| oldCommandText | ✓ | text | The full text of the light command that will be replaced. |

#### Classes

The following classes respond to the **replaceLightCommand** command:

- [light cue](#light-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  replaceLightCommand cue "1" oldCommandText "myLight.intensity = 100" newCommandText "myLight.intensity = 80"
end tell
```

---

<a id="reset"></a>
## reset

*(verb):* reset one or more cues or workspaces.

#### Syntax

```applescript
  reset {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The cue(s) or workspace(s) to reset. |

#### Classes

The following classes respond to the **reset** command:

- [workspace](#workspace)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  reset cue "1"
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  reset
end tell
```

```applescript
tell application id "com.figure53.QLab.5"
  reset workspace "hamlet.qlab5"
end tell
```

---

<a id="revert"></a>
## revert

*(verb):* revert changes in the specified Light Dashboard.

#### Syntax

```applescript
  revert {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard in which you want to revert changes. |

#### Classes

The following classes respond to the **revert** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  revert theDashboard
end tell
```

---

<a id="save"></a>
## save

*(verb):* save the last undone action.

#### Syntax

```applescript
  save {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The workspace or Light Dashboard in which you want to save the last undone action. |

#### Classes

The following classes respond to the **save** command:

- [workspace](#workspace)
- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  save
end tell
```

---

<a id="setgang"></a>
## setGang

*(verb):* set the gang for a specified location in the cue's matrix.

#### Syntax

```applescript
setGang {cue} row {row_number} column {column_number} gang {text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue for which you want to set the gang. |
| column | ✓ | integer | The column of the level matrix. Column 0 is the main and input levels column. |
| gang | ✓ | text | The gang to set. |
| row | ✓ | integer | The row of the level matrix. Row 0 is the main and output levels row. |

#### Classes

The following classes respond to the **setGang** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [fade cue](#fade-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set cue "1" row 0 column 1 gang "a"
end tell
```

---

<a id="setinputchannelname"></a>
## setInputChannelName

*(verb):* set the input name for a specified row of a cue.

#### Syntax

```applescript
setInputChannelName {cue} row {row_number} name {text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue for which you want to set the audio input name. |
| name | ✓ | text | The name for the input channel. |
| row | ✓ | integer | The row of the level matrix. Starts at 1. |

#### Classes

The following classes respond to the **setInputChannelName** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  setInputChannelName cue "1" row 0 input "vocals"
end tell
```

---

<a id="setlevel"></a>
## setLevel

*(verb):* set the level in decibels for a specified location in the cue's matrix.

#### Syntax

```applescript
setLevel {cue} row {row_number} column {column_number} db {real number}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue for which you want to set the level. |
| column | ✓ | integer | The column of the level matrix. Column 0 is the main and input levels column. |
| db | ✓ | real number | The level in decibels to set. |
| row | ✓ | integer | The row of the level matrix. Row 0 is the main and output levels row. |

#### Classes

The following classes respond to the **setLevel** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [fade cue](#fade-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  setLevel cue "1" row 0 column 1 db "-6"
end tell
```

---

<a id="setlight"></a>
## setLight

*(verb):* add a light command to the specified cue or to the Light Dashboard.

#### Syntax

```applescript
setLight {reference} selector {text} value {real number or text}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | reference | The Light cue or Light Dashboard for which you want to add a light command. |
| selector | ✓ | text | The instrument or group name for the command you want to add. Using a parameter name as well is optional. |
| value |  | real number or text | Optional parameter value to set. |

#### Classes

The following classes respond to the **setLight** command:

- [light dashboard](#light-dashboard)
- [light cue](#light-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  setLight cue "1" selector "myLight"
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  setLight theDashboard selector "myLight.red" value "50"
end tell
```

---

<a id="setmute"></a>
## setMute

*(verb):* set the status of the mute button for a specified output of the cue.

#### Syntax

```applescript
setMute {cue} output {output_number} mute {boolean}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue for which you want to set the mute. |
| output | ✓ | integer | The output number. Output 0 is the main level. |
| mute | ✓ | boolean | True = mute. False = unmute. |

#### Classes

The following classes respond to the **setMute** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  setMute cue "1" output 0 mute true
end tell
```

---

<a id="setsolo"></a>
## setSolo

*(verb):* set the status of the solo button for a specified output of the cue.

#### Syntax

```applescript
setSolo {cue} output {output_number} solo {boolean}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue for which you want to set the mute. |
| output | ✓ | integer | The output number. Output 0 is the main level. |
| solo | ✓ | boolean | True = solo. False = unsolo. |

#### Classes

The following classes respond to the **setSolo** command:

- [audio cue](#audio-cue)
- [mic cue](#mic-cue)
- [video cue](#video-cue)
- [camera cue](#camera-cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  setSolo cue "1" output 0 mute true
end tell
```

---

<a id="shuffle"></a>
## shuffle

*(verb):* shuffle the order of child cues in a Group cue.

#### Syntax

```applescript
shuffle {group cue}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | group cue | The Group cue(s) whose child cues you want to shuffle. |

#### Classes

The following classes respond to the **start** command:

- [group cue](#group-cue)
- [cue list](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  start
end tell
```

---

<a id="start"></a>
## start

*(verb):* start one or more cues or workspaces.

#### Syntax

```applescript
start {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue(s) or workspace(s) to start. Starting a workspace unpauses all paused cues; it does not start cues which are not paused. |

#### Classes

The following classes respond to the **start** command:

- [workspace](#workspace)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  start
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  start cue "1"
end tell
```

---

<a id="stop"></a>
## stop

*(verb):* stop one or more cues or workspaces.

#### Syntax

```applescript
stop {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The cue(s) or workspace(s) to stop. |

#### Classes

The following classes respond to the **stop** command:

- [workspace](#workspace)
- any type of [cue](#cue)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  stop
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  stop cue "1"
end tell
```

---

<a id="undo"></a>
## undo

*(verb):* undo the last action.

#### Syntax

```applescript
undo {reference}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | cue | The workspace or Light Dashboard in which you want to undo the last action. |

#### Classes

The following classes respond to the **undo** command:

- [workspace](#workspace)
- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  undo
end tell
```

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  undo theDashboard
end tell
```

---

<a id="updatelatestcue"></a>
## updateLatestCue

*(verb):* copy all manually adjusted levels into the latest run Light cue.

#### Syntax

```applescript
  updateLatestCue {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to update the latest cue. |

#### Classes

The following classes respond to the **updateLatestCue** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  updateLatestCue theDashboard
end tell
```

---

<a id="updateoriginatingcues"></a>
## updateOriginatingCues

*(verb):* copy all manually adjusted levels into their originating Light cue(s).

#### Syntax

```applescript
  updateOriginatingCues {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to update the originating cue(s). |

#### Classes

The following classes respond to the **updateOriginatingCues** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  updateOriginatingCues theDashboard
end tell
```

---

<a id="updateselectedcues"></a>
## updateSelectedCues

*(verb):* copy all manually adjusted levels into the selected Light cue(s).

#### Syntax

```applescript
  updateSelectedCues {light dashboard}
```

#### Parameters

| Parameter | Required? | Type | Description |
| --- | --- | --- | --- |
| direct parameter | ✓ | light dashboard | The Light Dashboard from which you want to update the selected cue(s). |

#### Classes

The following classes respond to the **updateSelectedCues** command:

- [light dashboard](#light-dashboard)

#### Examples

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set theDashboard to current light dashboard
  updateSelectedCues theDashboard
end tell
```

---

# Classes

---

<a id="application"></a>
## application

*(noun): the top-level scripting object of QLab.*

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| frontmost | get | boolean | Is this the frontmost (active) application? |
| name | get | text | The name of the application. |
| overrides | get | override controller | Application-wide communication overrides. |
| preferences | get | preferences controller | Application-wide preferences and settings. |
| version | get | text | The version of the application. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| document | get | by name, by index, by range, relative to others, by whose/where, by unique ID |  |
| window | get | by name, by index, by range, relative to others, by whose/where, by unique ID |  |
| workspace | get | by name, by index, by range, relative to others, by whose/where, by unique ID |  |

#### Commands

The **application** class responds to the following commands:

| Command | Description |
| --- | --- |
| open | Open QLab. |
| print | This command has no effect in QLab. |
| quit | Quit QLab. |

---

<a id="audio-cue"></a>
## audio cue

*(noun), pl. **audio cues** *

#### Properties

In addition to the properties listed here, **audio cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| audio input channels | get | integer | The number of audio input channels for this cue (i.e. the number of distinct channels in the target audio file.) |
| audio output patch name | get/set | text | The name of this cue's audio output patch. `none` means "unpatched." |
| audio output patch number | get/set | integer | The 1-indexed number of this cue's audio output patch. `0` means "unpatched." |
| audio output patch id | get/set | text | The unique ID of this cue's audio output patch. Empty string or `none` means "unpatched." |
| end time | get/set | real number | Time in the target file where playback ends. |
| infinite loop | get/set | boolean | Does this cue loop infinitely? |
| integrated fade | get/set | enabled or disabled | State of the integrated fade checkbox. |
| last slice infinite loop | get/set | boolean | Does the last slice of this cue loop infinitely? |
| last slice play count | get/set | integer | Number of times the last slice of this cue plays. Always >= `1`. |
| lock fade to cue | get/set | enabled or disabled | State of the lock fade to start/end checkbox. |
| patch | get/set | integer | The 1-indexed number of this cue's audio output patch. *Deprecated in QLab 5.0 - use `audio output patch number` instead.* |
| play count | get/set | boolean | Number of times this cue plays. Always >= `1`. |
| preserve pitch | get/set | enabled disabled | State of the preserve pitch checkbox. |
| rate | get/set | real number | Playback rate of this cue. |
| slice markers | get/set | list of [slice marker record](#slice-marker-record) | List of slice markers in this cue. |
| start time | get/set | real number | Time in the target file where playback begins. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **audio cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [getGang](#getgang) | Get the gang for a specified location in the cue's matrix. |
| [getInputChannelName](#getinputchannelname) | Get the input name for a specified row in the cue's matrix. |
| [getLevel](#getlevel) | Get the level for a specified location in the cue's matrix. |
| [getMute](#getmute) | Get the status of the mute button of a specified output. |
| [getSolo](#getsolo) | Get the status of the solo button of a specified output. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setGang](#setgang) | Set the gang for a specified location in the cue's matrix. |
| [setInputChannelName](#setinputchannelname) | Set the intput name for a specified row in the cue's matrix. |
| [setLevel](#setlevel) | Set the level for a specified location in the cue's matrix. |
| [setMute](#setmute) | Set the status of the mute button of a specified output. |
| [setSolo](#setsolo) | Set the status of the solo button of a specified output. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **audio cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="camera-cue"></a>
## camera cue

*(noun), pl. **camera cues** *

#### Properties

In addition to the properties listed here, **camera cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| anchor x | get/set | real number | Anchor along the x axis. |
| anchor y | get/set | real number | Anchor along the y axis. |
| audio input channels | get | integer | The number of audio input channels for this cue (i.e. the number of distinct channels in the target audio file.) |
| audio input patch name | get/set | text | The name of this cue's audio input patch. `none` means "unpatched." |
| audio input patch number | get/set | integer | The 1-indexed number of this cue's audio input patch. `0` equals "unpatched." |
| audio input patch id | get/set | text | The unique ID of this cue's audio input patch. Empty string or `none` equals "unpatched." |
| audio output patch name | get/set | text | The name of this cue's audio output patch. `none` means "unpatched." |
| audio output patch number | get/set | integer | The 1-indexed number of this cue's audio output patch. `0` means "unpatched." |
| audio output patch id | get/set | text | The unique ID of this cue's audio output patch. Empty string or `none` means "unpatched." |
| blend mode | get/set | text | Display name of the video blend mode. |
| camera patch | get/set | integer | The 1-indexed number of this cue's camera patch. *Deprecated in QLab 5.0 - use `video input patch number` instead.* |
| fill stage | get/set | boolean | Is the cue displaying in fill stage mode? |
| fill style | get/set | [fill styles](#fill-styles) | How does the cue fill the stage? |
| full screen | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| full surface | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| layer | get/set | integer | The display layer of this cue. `0` is the bottom layer; `1000` is the top layer. |
| opacity | get/set | real number | The opacity of this cue. `0` = 0%; `0.5` = 50%; `1` = 100% |
| scale x | get/set | real number | The X-axis scale of this cue. |
| scale y | get/set | real number | The Y-axis scale of this cue. |
| smooth | get/set | boolean | Should the cue be scaled using smoothing interpolation? |
| stage name | get/set | text | Video output stage name. Empty string or `none` means "unpatched." |
| stage number | get/set | integer | Video output stage number. `0` means "unpatched." |
| stage id | get/set | text | Video output stage unique ID. Empty string or `none` means "unpatched." |
| translation x | get/set | real number | The X-axis translation (position) of this cue. |
| translation y | get/set | real number | The Y-axis translation (position) of this cue. |
| video input patch name | get/set | text | The name of this cue's video input patch. `none` means "unpatched." |
| video input patch number | get/set | integer | The 1-indexed number of this cue's video input patch. `0` means "unpatched." |
| video input patch id | get/set | text | The unique ID of this cue's video input patch. Empty string or `none` means "unpatched." |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **camera cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [getGang](#getgang) | Get the gang for a specified location in the cue's matrix. |
| [getInputChannelName](#getinputchannelname) | Get the input name for a specified row in the cue's matrix. |
| [getLevel](#getlevel) | Get the level for a specified location in the cue's matrix. |
| [getMute](#getmute) | Get the status of the mute button of a specified output. |
| [getSolo](#getsolo) | Get the status of the solo button of a specified output. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setGang](#setgang) | Set the gang for a specified location in the cue's matrix. |
| [setInputChannelName](#setinputchannelname) | Set the intput name for a specified row in the cue's matrix. |
| [setLevel](#setlevel) | Set the level for a specified location in the cue's matrix. |
| [setMute](#setmute) | Set the status of the mute button of a specified output. |
| [setSolo](#setsolo) | Set the status of the solo button of a specified output. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **camera cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="cue"></a>
## cue

*(noun), pl. **cues** *

#### Properties

All cues have properties from this list, but not every type of cue has every property. For example, only cue type which accept a file target (Audio, Video, and MIDI file) have the *file target* property.

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| action elapsed | get | real number | The time in seconds that have elapsed in the action of this cue. |
| armed | get/set | boolean | Is this cue armed? |
| autoload | get/set | boolean | Does this cue auto-load? |
| broken | get | boolean | Is this cue broken? |
| cart position | get | row column record | The row and column numbers for the position of this cue within a cart. A cue that is not contained within a cart will return row and column `0`. |
| continue mode | get/set | [contine modes](#continue-modes) | The continue mode of this cue. |
| cue target | get/set | [cue](#cue) | The cue this cue targets, if any. |
| current duration | get | real number | The current duration of this cue's action in seconds. This property reflects the temporary duration, if it has been set. Otherwise, it returns this cue's duration. |
| duck level | get/set | real number | The "duck or boost others" audio level. Accepts a range of `-120` to `12`. |
| duck others | get/set | enabled or disabled | The "duck or boost others" setting of this cue. |
| duck time | get/set | real number | The "duck or boost others" fade time. |
| duration | get | real number | The duration of this cue's action in seconds. Not editable for all cue types. |
| fade and stop others | get/set | integer | The "fade and stop others" setting of the cue: 0 = disabled 1 = peers 2 = list 3 = all |
| fade and stop others time | get/set | real number | The "fade and stop others" time in seconds. |
| file target | get/set | file | The file this cue targets, if any. |
| flagged | get/set | boolean | Is this cue flagged? |
| hotkey trigger | get/set | enabled or disabled | State of the hotkey trigger checkbox. |
| loaded | get | boolean | Is this cue loaded? |
| midi byte one | get/set | string | Byte 1 of this cue's MIDI trigger, if any. |
| midi byte one string | get/set | string | Display string of byte 1 of this cue's MIDI trigger, if any. |
| midi byte two | get/set | integer | Byte 2 of this cue's MIDI trigger, if any. |
| midi byte two string | get/set | string | Display string of byte 2 of this cue's MIDI trigger, if any. |
| midi command | get/set | [midi commands](#midi-command) | Type of MIDI command used for this cue's MIDI trigger, if any. NOTE: pitch bend messages cannot be used for MIDI triggers. |
| midi trigger | get/set | enabled or disabled | State of the MIDI trigger checkbox. |
| midi trigger channel | get/set | integer | MIDI channel used for the MIDI trigger of the cue. `0` is the workspace channel, `-1` is "any channel". |
| notes | get/set | text | The notes for this cue. |
| parent | get | group cue | The parent cue of this cue. |
| parent list | get | cue | The cue list or cue cart that contains this cue. |
| paused | get | boolean | Is this cue paused? |
| percent action elapsed | get | real number | The percentage of this cue's action that has elapsed. |
| percent post wait elapsed | get | real number | The percentage of this cue's post-wait that has elapsed. |
| percent pre wait elapsed | get | real number | The percentage of this cue's pre-wait that has elapsed. |
| post wait | get/set | real number | The time in seconds before this cue auto-continues, if this cue is set to auto-continue. |
| post wait elapsed | get | real number | The time in seconds of this cue's post-wait that has elapsed. |
| pre wait | get/set | real number | The time in seconds that this cue's action will delay after being started. |
| pre wait elapsed | get | real number | The time in seconds of this cue's pre-wait that has elapsed. |
| q color | get/set | text | The name of this cue's color, or "none" if no color is set. |
| q color 2 | get/set | text | The name of this cue's second color, or "none" if no color is set. |
| q default name | get | text | The name that QLab would give to this cue by default. |
| q display name | get | text | The name of this cue as displayed in the standby view. Never empty. |
| q list name | get | text | The name of this cue as displayed in the cue list or cart. Might be a default name. |
| q name | get/set | text | The name of this cue. |
| q number | get/set | text | The number of this cue. Unique if present. May be empty. |
| q type | get | text | The name of this type of cue (i.e. "Audio", "Video", etc.) |
| running | get | boolean | Is this cue running? |
| second trigger action | get/set | integer | The second trigger action of the cue: `0 = do nothing` `1 = panic` `2 = stop` `3 = hard stop` `4 = hard stop and restart` `5 = devamp` `6 = (playlist only) play next` `7 = (playlist only) play previous` |
| second trigger on release | get/set | enabled or disabled | State of the "second trigger on release" checkbox. |
| skip if disarmed | get/set | boolean | Skip this cue if it is not armed? |
| temp duration | get/set | real number | The temporary duration of this cue's action in seconds. Not all cues support temporary durations. Setting the temporary duration does not mark the document as edited. Reset the cue to restore its original, saved duration. |
| timecode bits | get/set | integer | The bits field of the timecode trigger of this cue. |
| timecode frames | get/set | integer | The frames field of the timecode trigger of this cue. |
| timecode hours | get/set | integer | The hours field of the timecode trigger of this cue. |
| timecode minutes | get/set | integer | The minutes field of the timecode trigger of this cue. |
| timecode seconds | get/set | integer | The seconds field of the timecode trigger of this cue. |
| timecode show as timecode | get/set | boolean | True if the timecode trigger is shown as timecode; false if shown as real time. |
| timecode text | get/set | text | Text representation of the timecode trigger. |
| timecode trigger | get/set | enabled or disabled | State of the timecode trigger checkbox. |
| uniqueID | get | text | The unique ID of this cue. |
| use q color 2 | get/set | boolean | Whether this cue will use the second cue color after it starts. |
| wall clock hours | get/set | integer | The hours field of the wall clock trigger of this cue. |
| wall clock minutes | get/set | integer | The minutes field of the wall clock trigger of this cue. |
| wall clock seconds | get/set | integer | The seconds field of the wall clock trigger of this cue. |
| wall clock trigger | get/set | enabled or disabled | State of the wall clock trigger checkbox. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID | Cues contained by this cue, if any. |

#### Commands

The **cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Subclasses

All cue classes inherit the elements and properties of the **cue** class.

#### Where Used

The **cue** class is used in the following ways:

- element of [workspace](#workspace) class.
- direct parameter to the [getLevel](#getlevel) command.
- direct parameter to the [setLevel](#setlevel) command.
- direct parameter to the [getGang](#getgang) command.
- direct parameter to the [setGang](#setgang) command.
- direct parameter to the [getInputChannelName](#getinputchannelname) command.
- direct parameter to the [setInputChannelName](#setinputchannelname) command.
- direct parameter to the [getMute](#getmute) command.
- direct parameter to the [setMute](#setmute) command.
- direct parameter to the [getSolo](#getsolo) command.
- direct parameter to the [setSolo](#setsolo) command.
- direct parameter to the [replaceLightCommand](#replacelightcommand) command.
- direct parameter to the [removeLightCommandsMatching](#removelightcommandsmatching) command.
- **active cues** property of the [workspace](#workspace) class.
- **cue target** property of the [cue](#cue) class.
- **parent** property of the [cue](#cue) class.
- **parent list** property of the [cue](#cue) class.
- **playback position** property of the [cue list](#cue-list) class.
- **playhead** property of the [cue list](#cue-list) class.
- **selected** property of the [workspace](#workspace) class.

---

<a id="cue-list"></a>
## cue list

*(noun), pl. **cue lists** *

#### Properties

In addition to the properties listed here, **cue list** inherits properties from [**cue**](#cue) and from [**group cue**](#group-cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| current timecode text | get | text | The timecode currently being received. |
| ltc sync channel | get/set | integer | Audio channel supplying an LTC sync signal. |
| mtc sync source name | get/set | text | Name of the MIDI device supplying an MTC sync signal. |
| playback position | get/set | [cue](#cue) | The playback position of a cue list is the cue which is standing by and which will start at the next GO. |
| playhead | get/set | [cue](#cue) | Synonym for **playback position**. |
| smpte format | get/set | [timecode smpte format](#timecode-smpte-format) | The SMPTE format of the incoming timecode. |
| sync mode | get/set | [sync mode](#mtc-ltc) | Which type of incoming timecode this cue list listens for. |
| sync to timecode | get/set | enabled or disabled | State of the sync to timecode checkbox. |
| timecode start behavior | get/set | [timecode start](#timecode-start) | How cues in this list will behave when timecode starts. |
| timecode stop behavior | get/set | [timecode stop](#timecode-stop) | How cues in this list will behave when timecode stops. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID | Cues contained by this cue list, if any. |

#### Commands

The **cue list** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [collapse](#collapse) | Collapse the cue list in the sidebar. |
| [expand](#expand) | Expand the cue list in the sidebar. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [movePlayheadDown](#moveplayheaddown) | Move the playhead in the active cue list to the next cue. |
| [movePlayheadDownASequence](#moveplayheaddownasequence) | Move the playhead in the active cue list to top of the next cue sequence. |
| [movePlayheadUp](#moveplayheadup) | Move the playhead in the active cue list to the previous cue. |
| [movePlayheadUpASequnce](#moveplayheadupasequence) | Move the playhead in the active cue list to top of the previous cue sequence. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **cue list** class inherits elements and properties from the [**group cue**](#group-cue) class.

#### Where Used

The **cue list** class is used in the following ways:

- element of the [workspace](#workspace) class.
- **current cue list** property of the [workspace](#workspace) class.

---

<a id="devamp-cue"></a>
## devamp cue

*(noun), pl. **devamp cues** *

#### Properties

In addition to the properties listed here, **devamp cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| start next cue when slice ends | get/set | boolean | Start the next cue at the moment the target slice ends? |
| stop target when slice ends | get/set | boolean | Stop the target at the moment the target slice ends? |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **devamp cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **devamp cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="fade-cue"></a>
## fade cue

*(noun), pl. **fade cues** *

#### Properties

In addition to the properties listed here, **fade cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| audio fade mode | get/set | absolute or relative | Set absolute or relative mode for fading audio levels. |
| audio map target id | get/set | text | The unique ID of the audio map this cue targets, if any. |
| do opacity | get/set | boolean | Does this cue animate opacity? |
| do rotation | get/set | boolean | Does this cue animate rotation? |
| do scale | get/set | boolean | Does this cue animate scale? |
| do translation | get/set | boolean | Does this cue animate translation? |
| fade mode | get/set | absolute or relative | *Deprecated in QLab 5.0 - use `audio fade mode` instead.* |
| fade type | get/set | integer | 1 = 1D Fade 2 = 2D Fade |
| opacity | get/set | real number | Video opacity to fade to. `0` = 0%; `0.5` = 50%; `1` = 100% |
| patch target id | get/set | text | The patch this cue targets, if any. |
| path height | get/set | real | The maximum Y value for the grid displayed in the inspector for a 2D fade. Must not be a negative number. |
| path loop | get/set | boolean | Does the path loop? |
| path smooth | get/set | boolean | Is the path smoothed? |
| path width | get/set | real | The maximum X value for the grid displayed in the inspector for a 2D fade. Must not be a negative number. |
| preserve aspect ratio | get/set | boolean | Does this cue preserve aspect ratio? |
| rotation | get/set | real number | Rotation in degrees when this cue's *rotation type* is set to a single-axis mode (modes 1, 2, or 3). When *rotation type* is 3D orientation (mode 0), this cannot be used to set and returns 0.0 when used to get. |
| rotation type | get/set | integer | 0 = 3D orientation 1 = X axis 2 = Y axis 3 = Z axis |
| scale x | get/set | real number | X-axis scale to fade to. |
| scale y | get/set | real number | Y-axis scale to fade to. |
| stop target when done | get/set | boolean | Stop the target cue when this cue completes? |
| target mode | get/set | target modes | The target mode of this cue. |
| translation y | get/set | real | Translation along the Y axis. |
| translation x | get/set | real | Translation along the X axis. |
| video fade mode | get/set | absolute or relative | Set absolute or relative mode for fading video geometry. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **fade cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [getGang](#getgang) | Get the gang for a specified location in the cue's matrix. |
| [getLevel](#getlevel) | Get the level for a specified location in the cue's matrix. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setGang](#setgang) | Set the gang for a specified location in the cue's matrix. |
| [setLevel](#setlevel) | Set the level for a specified location in the cue's matrix. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **fade cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="group-cue"></a>
## group cue

*(noun), pl. **group cues** *

#### Properties

In addition to the properties listed here, **group cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| mode | get/set | [group modes](#group-modes) | The playback behavior of this group. |
| playlist crossfade | get/set | boolean | Does this playlist group crossfade between its child cues? |
| playlist crossfade duration | get/set | real number | The duration of the cue's playlist crossfade in seconds. |
| playlist loop | get/set | boolean | Does this playlist group loop? |
| playlist shuffle | get/set | boolean | Does this playlist group shuffle the order of its child cues? |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID | Cues contained by this cue, if any. |

#### Commands

The **group cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [collapse](#collapse) | Collapse the cue list in the cue list. |
| [expand](#expand) | Expand the cue list in the cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [shuffle](#shuffle) | Shuffle the order of child cues in a group cue. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **group cue** class inherits elements and properties from the [**cue**](#cue) class.

#### Subclasses

The [**cue list**](#cue-list) class inherits elements and properties from the **group cue** class.

#### Where Used

The **group cue** class is used in the following ways:

- direct parameter to the [collapse](#collapse) command.
- direct parameter to the [expand](#expand) command.

---

<a id="light-cue"></a>
## light cue

*(noun), pl. **light cues** *

#### Properties

In addition to the properties listed here, **light cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| always collate | get/set | boolean | Flag for whether this cue should always collate the effects of previous light cues in the same list when it runs. |
| command text | get/set | text | The light command text of this cue. |
| subcontroller | get/set | boolean | Is this cue used as a subcontroller in the Light Dashboard? |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **light cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [collateAndsStart](#collapse) | Collate and start the light cue. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [prune](#prune) | Remove light commands that have no effect from a light cue. |
| [removeLightCommandsMatching](#removelightcommandsmatching) | Remove existing light commands in the specified cue matching the command provided. |
| [replaceLightCommand](#replacelightcommand) | Replace a specified light command in the specified cue with a new light command. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setLight](#setlight) | Add a light command to the specified cue. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **light cue** class inherits elements and properties from the [**cue**](#cue) class.

#### Where Used

The **light cue** class is used in the following ways:

- direct parameter to the [prune](#prune) command.
- direct parameter to the [collateAndStart](#collateandstart) command.

---

<a id="light-dashboard"></a>
## light dashboard

*(noun)*

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| dashboard fade time | get/set | real number | The duration in seconds over which the next light command entered will fade from current to new level(s). Resets to 0.0 after each use. |
| dashboard mode | get/set | [light dashboard view mode](#light-dashboard-view-mode) | The view mode of the Light Dashboard. |
| dashboard visibility | get/set | boolean | Is the Light Dashboard currently visible? |
| properties | get/set | record | All of the Light Dashboard's properties. |

#### Commands

The **light dashboard** class responds to the following commands:

| Command | Description |
| --- | --- |
| [clear](#clear) | Clear the levels in the light dashboard |
| [newCueWithAll](#newcuewithall) | Create a new Light cue containing levels for all parameters of all instruments. |
| [newCueWithChanges](#newcuewithchanges) | Create a new Light cue containing levels for all manually adjusted parameters in the light dashboard. |
| [recordAllToLatest](#recordalltolatest) | Record all levels for all parameters of all instruments into the latest run Light cue. |
| [recordAllToSelected](#recordalltoselected) | Record all levels for all parameters of all instruments into the selected Light cue(s). |
| [redo](#redo) | Redo the last undone action. |
| [revert](#revert) | Revert changes in the light dashboard. |
| [setLight](#setlight) | add a light command to the light dashboard. |
| [undo](#undo) | Undo the last action. |
| [updateLatestCue](#updatelatestcue) | Copy all manually adjusted levels into the latest run Light cue. |
| [updateOriginatingCues](#updateoriginatingcues) | Copy all manually adjusted levels into their originating Light cue(s). |
| [updateSelectedCues](#updateselectedcues) | Copy all manually adjusted levels into the selected Light cue(s). |

#### Where Used

The **light dashboard** class is used in the following ways:

- direct parameter to the [clear](#clear) command.
- direct parameter to the [updateLatestCue](#updatelatestcue) command.
- direct parameter to the [updateOriginatingCues](#updateoriginatingcues) command.
- direct parameter to the [updateSelectedCues](#updateselectedcues) command.
- direct parameter to the [newCueWithAll](#newcuewithall) command.
- direct parameter to the [newCueWithChanges](#newcuewithchanges) command.
- direct parameter to the [recordAllToLatest](#recordalltolatest) command.
- direct parameter to the [recordAllToSelected](#recordalltoselected) command.
- direct parameter to the [revert](#revert) command.
- **current light dashboard** property of the [workspace](#workspace) class.

---

<a id="load-cue"></a>
## load cue

*(noun), pl. **load cues** *

#### Properties

In addition to the properties listed here, **load cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| load time | get/set | real number | Load target cue to this time. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **load cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **load cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="mic-cue"></a>
## mic cue

*(noun), pl. **mic cues** *

#### Properties

In addition to the properties listed here, **mic cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| audio input channels | get | integer | The number of audio input channels for this cue. |
| audio input patch name | get/set | text | The name of this cue's audio input patch. `none` means "unpatched." |
| audio input patch number | get/set | integer | The 1-indexed number of this cue's audio input patch. `0` equals "unpatched." |
| audio input patch id | get/set | text | The unique ID of this cue's audio input patch. Empty string or `none` equals "unpatched." |
| audio output patch name | get/set | text | The name of this cue's audio output patch. `none` means "unpatched." |
| audio output patch number | get/set | integer | The 1-indexed number of this cue's audio output patch. `0` means "unpatched." |
| audio output patch id | get/set | text | The unique ID of this cue's audio output patch. Empty string or `none` equals "unpatched." |
| patch | get/set | integer | The 1-indexed number of this cue's audio output patch. *Deprecated in QLab 5.0 - use `audio input patch number` or `audio output patch number` instead.* |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **mic cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [getGang](#getgang) | Get the gang for a specified location in the cue's matrix. |
| [getInputChannelName](#getinputchannelname) | Get the input name for a specified row in the cue's matrix. |
| [getLevel](#getlevel) | Get the level for a specified location in the cue's matrix. |
| [getMute](#getmute) | Get the status of the mute button of a specified output. |
| [getSolo](#getsolo) | Get the status of the solo button of a specified output. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setGang](#setgang) | Set the gang for a specified location in the cue's matrix. |
| [setInputChannelName](#setinputchannelname) | Set the intput name for a specified row in the cue's matrix. |
| [setLevel](#setlevel) | Set the level for a specified location in the cue's matrix. |
| [setMute](#setmute) | Set the status of the mute button of a specified output. |
| [setSolo](#setsolo) | Set the status of the solo button of a specified output. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **mic cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="midi-cue"></a>
## midi cue

*(noun), pl. **midi cues** *

#### Properties

In addition to the properties listed here, **midi cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| byte combo | get/set | integer | (MIDI voice message type) Value when first and second bytes of the MIDI message are interpreted as parts of one number. Used for pitch bend messages. |
| byte one | get/set | integer | (MIDI voice message type) First byte of the MIDI message. |
| byte two | get/set | integer | (MIDI voice message type) Second byte of the MIDI message. |
| channel | get/set | integer | (MIDI voice message type) MIDI channel number. |
| command | get/set | [midi command](#midi-command) | (MIDI voice message type) MIDI command. |
| command format | get/set | integer | (MSC message type) MSC command format. |
| command number | get/set | integer | (MSC message type) MSC command. |
| control number | get/set | integer | (MSC message type) MSC control number. |
| control value | get/set | integer | (MSC message type) MSC control value. |
| deviceID | get/set | integer | (MSC message type) MSC device ID number. |
| end value | get/set | integer | (MIDI voice message type) The end value for a faded MIDI message. |
| fade | get/set | boolean | (MIDI voice message type) Does the MIDI message fade? |
| macro | get/set | integer | (MSC message type) MSC macro parameter. |
| message type | get/set | [midi type](#midi-type) | The type of MIDI message for this cue (msd, sysex, or voice.) |
| midi patch id | get/set | text | The unique ID of this cue's MIDI patch. Empty string or `none` means "unpatched." |
| midi patch name | get/set | text | The name of this cue's MIDI patch. `none` means "unpatched." |
| midi patch number | get/set | integer | The 1-indexed number of this cue's MIDI patch. `0` means "unpatched." |
| msc frames | get/set | integer | (MSC message type) MSC frames parameter. |
| msc hours | get/set | integer | (MSC message type) MSC hours parameter. |
| msc minutes | get/set | integer | (MSC message type) MSC minutes parameter. |
| msc seconds | get/set | integer | (MSC message type) MSC seconds parameter. |
| msc subframes | get/set | integer | (MSC message type) MSC subframes parameter. |
| patch | get/set | integer | The 1-indexed number of this cue's MIDI patch. *Deprecated in QLab 5.0 - use `midi patch number` instead.* |
| q_list | get/set | text | (MSC message type) Q List message parameter. |
| q_number | get/set | text | (MSC message type) Q Number message parameter. |
| q_path | get/set | text | (MSC message type) Q Path message parameter. |
| send time with set | get/set | boolean | (MSC message type) Send the timecode parameters with the SET command? |
| smpte format | get/set | [smpte format](#smpte-format) | (MSC message type) SMPTE format of the timecode parameters. |
| start value | get/set | integer | (MIDI voice message type) The start value for a faded MIDI message. |
| sysex message | get/set | text | (SysEx message type) The raw SysEx message. Use only hexadecimal characters and whitespace. Omit the starting `F0` and the ending `F7`. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **midi cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **midi cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="midi-file-cue"></a>
## midi file cue

*(noun), pl. **midi file cues** *

#### Properties

In addition to the properties listed here, **midi file cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| midi patch name | get/set | text | The name of this cue's MIDI patch. `none` means "unpatched." |
| midi patch number | get/set | integer | The 1-indexed number of this cue's MIDI patch. `0` means "unpatched." |
| midi patch id | get/set | text | The unique ID of this cue's MIDI patch. Empty string or `none` means "unpatched." |
| patch | get/set | integer | The 1-indexed number of this cue's MIDI patch. *Deprecated in QLab 5.0 - use `midi patch number` instead.* |
| rate | get/set | real number | Playback rate of the MIDI file. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **midi file cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **midi file cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="network-cue"></a>
## network cue

*(noun), pl. **network cues** *

#### Properties

In addition to the properties listed here, **network cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| custom message | get/set | text | The custom OSC message, for custom type messages. *Deprecated in QLab 5.0 - use `parameter values` instead.*) |
| fade entries | get/set | list of text | The list of {x,y} coordinates representing entries which define the shape (1D) or path (2D) of the current fade. |
| fade fps | get/set | integer | The rate in frames per second in which fade values are sent. Must be a positive integer between `1` and `120`. |
| fade from | get/set | real number | The starting value for a 1D fade. |
| fade number type | get/set | integer | Whether the fade sends integer (0) or float (1) values. |
| fade path height | get/set | real number | The maximum Y value for the grid displayed in the inspector for a 2D fade. Must not be a negative number. |
| fade path loop | get/set | boolean | Does the fade path loop? |
| fade path smooth | get/set | boolean | Is the fade path smoothed? |
| fade path width | get/set | real number | The maximum X value for the grid displayed in the inspector for a 2D fade. Must not be a negative number. |
| fade to | get/set | real number | The ending value for a 1D fade. |
| fade type | get/set | integer | 0 = no fade/resend 1 = 1D fade 2 = 2D fade Writeable only for `string` type parameters. |
| network patch id | get/set | text | The unique ID of this cue's Network patch. Empty string or `none` means "unpatched." |
| network patch name | get/set | text | The name of this cue's Network patch. `none` means "unpatched." |
| network patch number | get/set | integer | The 1-indexed number of this cue's Network patch. `0` means "unpatched." |
| parameter fades enabled | get/set | list of boolean | The list of boolean values that represent the fade-enabled states of all fade-able parameters in this Network cue. |
| parameter values | get/set | list of text, boolean, or number | The list of parameter values used to configure the current command. |
| patch | get/set | integer | The 1-indexed number of this cue's Network patch. *Deprecated in QLab 5.0 - use `network patch number` instead.* |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **network cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **network cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="override-controller"></a>
## override controller

*(noun)*

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| dmx output enabled | get/set | boolean | Allow DMX output (default is TRUE.) |
| midi input enabled | get/set | boolean | Allow MIDI Voice input (default is TRUE.) |
| midi output enabled | get/set | boolean | Allow MIDI Voice output (default is TRUE.) |
| msc input enabled | get/set | boolean | Allow MSC input (default is TRUE.) |
| msc output enabled | get/set | boolean | Allow MSC output (default is TRUE.) |
| network external input enabled | get/set | boolean | Allow external network input (default is TRUE.) |
| network external output enabled | get/set | boolean | Allow external network output (default is TRUE.) |
| network local input enabled | get/set | boolean | Allow local network input (default is TRUE.) |
| network local output enabled | get/set | boolean | Allow local network output (default is TRUE.) |
| osc input enabled | get/set | boolean | Allow OSC input (default is TRUE.) |
| osc output enabled | get/set | boolean | Allow OSC output (default is TRUE.) |
| overrides visibility | get/set | boolean | Is the Overrides Controls window visible? |
| sysex input enabled | get/set | boolean | Allow SysEx (other than MSC and MTC) input (default is TRUE.) |
| sysex output enabled | get/set | boolean | Allow SysEx (other than MSC and MTC) output (default is TRUE.) |
| timecode input enabled | get/set | boolean | Allow timecode input (default is TRUE.) |
| timecode output enabled | get/set | boolean | Allow timecode output (default is TRUE.) |

#### Where Used

The *override controller* class is used in the following ways:

- *overrides* property of the application class.

#### Examples

```applescript
-- override MIDI output (i.e. "don't output any MIDI")
tell application id "com.figure53.QLab.5"
  tell overrides to set midi output enabled to false
end tell
```

```applescript
-- open the override controls window
tell application "QLab" to tell overrides to set overrides visibility to true
```

---

<a id="reset-cue"></a>
## reset cue

*(noun), pl. **reset cues** *

#### Properties

In addition to the properties listed here, **reset cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| patch target id | get/set | text | The patch this cue targets, if any. |
| target mode | get/set | target modes | The target mode of this cue. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **devamp cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [compile](#compile) | Verify and prepare the script for use. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **devamp cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="script-cue"></a>
## script cue

*(noun), pl. **script cues** *

#### Properties

In addition to the properties listed here, **script cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| script source | get/set | text | AppleScript source for the cue. The script will be recompiled when set. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **script cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [compile](#compile) | Verify and prepare the script for use. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **script cue** class inherits elements and properties from the [**cue**](#cue) class.

#### Where Used

The **script cue** class is used in the following ways:

- direct parameter to the [compile](#compile) command.

---

<a id="target-cue"></a>
## target cue

*(noun), pl. **target cues** *

#### Properties

In addition to the properties listed here, **target cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| assigned number | get/set | text | The cue number of the cue to assign. The cue with this number will be assigned as the new target of the cue which this cue targets. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **target cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **target cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="text-cue"></a>
## text cue

*(noun), pl. **text cues** *

#### Properties

In addition to the properties listed here, **text cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| anchor x | get/set | real number | Anchor along the x axis. |
| anchor y | get/set | real number | Anchor along the y axis. |
| blend mode | get/set | text | Display name of the video blend mode. |
| fill stage | get/set | boolean | Is the cue displaying in fill stage mode? |
| fill style | get/set | [fill styles](#fill-styles) | How does the cue fill the stage? |
| full screen | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| full surface | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| fixed width | get/set | number | Fixed width of the text cue. Setting this to `0` specifies "auto" width. |
| layer | get/set | integer | The display layer of this cue. `0` is the bottom layer; `1000` is the top layer. |
| live text | get/set | text | Live text of this cue. Setting this does not mark the workspace as edited. |
| live text alignment | get/set | text | Text alignment of the live text of this cue. Possible values are "left", "center", "right", and "justify". Setting this does not mark the workspace as edited. |
| live text format | get/set | list of [text format record](#text-format-record) | The list of text formats in the live text of this cue. Setting this does not mark the workspace as edited. |
| live text output size | get | list of number | A 2-item list representing the width and height of the live text of this cue. |
| opacity | get/set | real number | The opacity of this cue. `0` = 0%; `0.5` = 50%; `1` = 100% |
| preserve aspect ratio | get/set | boolean | Does this cue preserve aspect ratio? |
| scale x | get/set | real number | The X-axis scale of this cue. |
| scale y | get/set | real number | The Y-axis scale of this cue. |
| smooth | get/set | Should the cue be scaled using smoothing interpolation? |  |
| stage name | get/set | text | Video output stage name. Empty string or `none` means "unpatched." |
| stage number | get/set | integer | Video output stage number. `0` means "unpatched." |
| stage id | get/set | text | Video output stage unique ID. Empty string or `none` means "unpatched." |
| text | get/set | text | Text of this cue. |
| text alignment | get/set | text | Text alignment of this cue. Possible values are "left", "center", "right", and "justify". |
| text format | get/set | list of [text format record](#text-format-record) | The list of text formats in the text of this cue. |
| text output size | get | list of number | A 2-item list representing the width and height of the text of this cue. |
| translation x | get/set | real number | The X-axis translation (position) of this cue. |
| translation y | get/set | real number | The Y-axis translation (position) of this cue. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **text cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **text cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="timecode-cue"></a>
## timecode cue

*(noun), pl. **timecode cues** *

#### Properties

In addition to the properties listed here, **timecode cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| audio output patch name | get/set | text | (For cues in LTC mode.) The name of this cue's audio output patch. `none` means "unpatched." |
| audio output patch number | get/set | integer | (For cues in LTC mode.) The 1-indexed number of this cue's audio output patch. `0` means "unpatched." |
| audio output patch id | get/set | text | (For cues in LTC mode.) The unique ID of this cue's audio output patch. Empty string or `none` means "unpatched." |
| midi patch name | get/set | text | (For cues in MTC mode.) The name of this cue's MIDI patch. `none` means "unpatched." |
| midi patch number | get/set | integer | (For cues in MTC mode.) The 1-indexed number of this cue's MIDI patch. `0` means "unpatched." |
| midi patch id | get/set | text | (For cues in MTC mode.) The unique ID of this cue's MIDI patch. Empty string or `none` means "unpatched." |
| patch | get/set | integer | (For cues in LTC mode.) The 1-indexed number of this cue's audio output patch. *Deprecated in QLab 5.0 - use `audio output patch number` instead.* |
| patch | get/set | integer | (For cues in MTC mode.) The 1-indexed number of this cue's MIDI patch. *Deprecated in QLab 5.0 - use `midi patch number` instead.* |
| smpte format | get/set | [smpte format](#smpte-format) | SMPTE format of the outgoing timecode. |
| start time offset | get/set | real number | Time in seconds where the timecode clock begins counting. |
| timecode end time | get/set | text | The timecode clock end time. |
| timecode start time | get/set | text | The timecode clock start time. |
| type | get/set | mtc or ltc | The type of timecode used by this cue. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **timecode cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **timecode cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="video-cue"></a>
## video cue

*(noun), pl. **video cues** *

#### Properties

In addition to the properties listed here, **video cue** inherits properties from [**cue**](#cue).

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| anchor x | get/set | real number | Anchor along the x axis. |
| anchor y | get/set | real number | Anchor along the y axis. |
| audio input channels | get | integer | The number of audio input channels for this cue (i.e. the number of distinct channels in the target audio file.) |
| audio output patch name | get/set | text | The name of this cue's audio output patch. `none` means "unpatched." |
| audio output patch number | get/set | integer | The 1-indexed number of this cue's audio output patch. `0` means "unpatched." |
| audio output patch id | get/set | text | The unique ID of this cue's audio output patch. Empty string or `none` means "unpatched." |
| blend mode | get/set | text | Display name of the video blend mode. |
| clock type | get/set | audio or video | The clock type of the cue. |
| end time | get/set | real number | Time in the target file where playback ends. |
| fill stage | get/set | boolean | Is the cue displaying in fill stage mode? |
| fill style | get/set | [fill styles](#fill-styles) | How does the cue fill the stage? |
| full screen | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| full surface | get/set | boolean | Is the cue displaying in full-stage mode? *Deprecated in QLab 5.0 - use 'fill stage' instead.* |
| hold at end | get/set | boolean | Should the final frame of the video be left visible when playback reaches the end of the file? |
| infinite loop | get/set | boolean | Does this cue loop infinitely? |
| integrated fade | get/set | enabled or disabled | State of the integrated fade checkbox. |
| last slice infinite loop | get/set | boolean | Does the last slice of this cue loop infinitely? |
| last slice play count | get/set | integer | Number of times the last slice of this cue plays. Always >= `1`. |
| layer | get/set | integer | The display layer of this cue. `0` is the bottom layer; `1000` is the top layer. |
| lock fade to cue | get/set | enabled or disabled | State of the lock fade to start/end checkbox. |
| opacity | get/set | real number | The opacity of this cue. `0` = 0%; `0.5` = 50%; `1` = 100% |
| patch | get/set | integer | The 1-indexed number of this cue's audio output patch. *Deprecated in QLab 5.0 - use `audio output patch number` instead.* |
| play count | get/set | boolean | Number of times this cue plays. Always >= `1`. |
| preserve aspect ratio | get/set | boolean | Does this cue preserve aspect ratio? |
| preserve pitch | get/set | enabled or disabled | State of the preserve pitch checkbox. |
| rate | get/set | real number | Playback rate of this cue. |
| scale x | get/set | real number | The X-axis scale of this cue. |
| scale y | get/set | real number | The Y-axis scale of this cue. |
| slice markers | get/set | list of [slice marker record](#slice-marker-record) | List of slice markers in this cue. |
| smooth | get/set | Should the cue be scaled using smoothing interpolation? |  |
| stage name | get/set | text | Video output stage name. Empty string or `none` means "unpatched." |
| stage number | get/set | integer | Video output stage number. `0` means "unpatched." |
| stage id | get/set | text | Video output stage unique ID. Empty string or `none` means "unpatched." |
| start time | get/set | real number | Time in the target file where playback begins. |
| translation x | get/set | real number | The X-axis translation (position) of this cue. |
| translation y | get/set | real number | The Y-axis translation (position) of this cue. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get/make/delete | by name, by index, by uniqueID |  |

#### Commands

The **video cue** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition preview](#audition-preview) | Audition preview one or more cues. Previewing starts only the action of the cue, skipping any prewait and not continuing to other cues. |
| [capture timecode](#capture-timecode) | Set the cue's timecode trigger to the current incoming timecode received by its parent cue list. |
| [getGang](#getgang) | Get the gang for a specified location in the cue's matrix. |
| [getInputChannelName](#getinputchannelname) | Get the input name for a specified row in the cue's matrix. |
| [getLevel](#getlevel) | Get the level for a specified location in the cue's matrix. |
| [getMute](#getmute) | Get the status of the mute button of a specified output. |
| [getSolo](#getsolo) | Get the status of the solo button of a specified output. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [preview](#preview) | Preview one or more cues. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [setGang](#setgang) | Set the gang for a specified location in the cue's matrix. |
| [setInputChannelName](#setinputchannelname) | Set the intput name for a specified row in the cue's matrix. |
| [setLevel](#setlevel) | Set the level for a specified location in the cue's matrix. |
| [setMute](#setmute) | Set the status of the mute button of a specified output. |
| [setSolo](#setsolo) | Set the status of the solo button of a specified output. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |

#### Superclass

The **video cue** class inherits elements and properties from the [**cue**](#cue) class.

---

<a id="workspace"></a>
## workspace

*(noun), pl. **workspaces** *

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| active cues | get | list of [cue](#cue) | The list of active cues (running or paused) in this workspace. |
| always audition | get/set | boolean | Is the workspace currently set to always audition? |
| current cue list | get/set | [cue list](#cue-list) | The cue list that's currently visible in the main window of the workspace. |
| current light dashboard | get | [light dashboard](#light-dashboard) | The current Light Dashboard for the workspace. |
| edit mode | get/set | boolean | Is the workspace currently in edit mode? |
| inspector visibility | get/set | boolean | Is the inspector visible? |
| live fade preview | get/set | boolean | Is live fade preview currently enabled for this workspace? |
| selected | get/set | list of [cue](#cue) | The currently selected cue(s) in the current cue list. |
| show mode | get/set | boolean | Is the workspace currently in show mode? |
| unique id | get | text | The unique ID of the workspace. |

#### Elements

| Element | Access | Key Forms | Description |
| --- | --- | --- | --- |
| cue | get | by name, by unique id | The complete list of cues in this workspace. |
| cue list | get/make/delete | by name, by index, by unique id | The list of cue lists in the workspace. |

#### Commands

The **workspace** class responds to the following commands:

| Command | Description |
| --- | --- |
| [audition go](#audition-go) | Make a workspace Audition GO. |
| [go](#go) | Make a workspace GO. |
| [hardStop](#hardstop) | hardStop one or more cues or workspaces. |
| [load](#getgang) | Load one or more cues or workspaces to a given time. |
| [make](#make) | Create a new cue. |
| [movePlayheadDown](#moveplayheaddown) | Move the playhead in the active cue list to the next cue. |
| [movePlayheadDownASequence](#moveplayheaddownasequence) | Move the playhead in the active cue list to top of the next cue sequence. |
| [movePlayheadUp](#moveplayheadup) | Move the playhead in the active cue list to the previous cue. |
| [movePlayheadUpASequnce](#moveplayheadupasequence) | Move the playhead in the active cue list to top of the previous cue sequence. |
| [moveSelectionDown](#moveselectiondown) | Select the next cue. |
| [moveSelectionUp](#moveselectionup) | Select the previous cue. |
| [panic](#panic) | Panic one or more cues or workspaces. |
| [pause](#pause) | Pause one or more cues or workspaces. |
| [redo](#redo) | Redo the last undone action. |
| [reset](#reset) | Reset one or more cues or workspaces. |
| [start](#start) | Start one or more cues or workspaces. |
| [stop](#stop) | Stop one or more cues or workspaces. |
| [undo](#undo) | Undo the last action. |

#### Where Used

The workspace class is used in the following ways:

- element of application class.
- direct parameter to the [make](#make) command.

---

<a id="enumerations"></a>
# Enumerations

---

<a id="absolute-relative"></a>
## absolute relative

#### Constants

| Constant | Description |
| --- | --- |
| absolute |  |
| relative |  |

#### Where Used

The **absolute relative** enumeration is used in the following ways:

- **audio fade mode** property of the [fade cue](#fade-cue) class.
- **fade mode** property of the [fade cue](#fade-cue) class.
- **video fade mode** property of the [fade cue](#fade-cue) class.

---

<a id="clock-types"></a>
## clock types

#### Constants

| Constant | Description |
| --- | --- |
| audio |  |
| video |  |

#### Where Used

The **clock types** enumeration is used in the following ways:

- **clock type** property of the [video cue](#video-cue) class.

---

<a id="continue-modes"></a>
## continue modes

#### Constants

| Constant | Description |
| --- | --- |
| auto_continue | Automatically continue to the next cue after completing the post-wait. |
| auto_follow | Automatically continue to the next cue after completing the action of the cue. |
| do_not_continue | Do not automatically continue to the next cue. |

#### Where Used

The **continue modes** enumeration is used in the following ways:

- **continue mode** property of the [cue](#cue) class.

---

<a id="enabled-disabled"></a>
## enabled disabled

#### Constants

| Constant | Description |
| --- | --- |
| disabled |  |
| enabled |  |

#### Where Used

The **enabled disabled** enumeration is used in the following ways:

- **duck others** property of the [cue](#cue) class.
- **fade** property of the [midi cue](#midi-cue) class.
- **hotkey trigger** property of the [cue](#cue) class.
- **integrated fade** property of the [audio cue](#audio-cue) class.
- **integrated fade** property of the [video cue](#video-cue) class.
- **lock fade to cue** property of the [audio cue](#audio-cue) class.
- **lock fade to cue** property of the [video cue](#video-cue) class.
- **midi trigger** property of the [cue](#cue) class.
- **preserve pitch** property of the [audio cue](#audio-cue) class.
- **preserve pitch** property of the [video cue](#video-cue) class.
- **second trigger on release** property of the [cue](#cue) class.
- **sync to timecode** property of the [cue list](#cue-list) class.
- **timecode trigger** property of the [cue](#cue) class.
- **wall clock trigger** property of the [cue](#cue) class.

---

<a id="fill-styles"></a>
## fill styles

#### Constants

| Constant | Description |
| --- | --- |
| fill | Fill the entire stage with the cue, preserving aspect ratio. Some portion of the cue may be cut off. |
| fit | Fit the cue inside the stage, preserving aspect ratio. Some empty space may be left to the sides or top and bottom of the cue. |
| stretch | Fill the stage by stretching the cue height and width to match the stage. |

#### Where Used

The **fill styles** enumeration is used in the following ways:

- **fill style** property of the [video cue](#video-cue) class.
- **fill style** property of the [text cue](#text-cue) class.
- **fill style** property of the [camera cue](#camera-cue) class.

---

<a id="group-modes"></a>
## group modes

#### Constants

| Constant | Description |
| --- | --- |
| cue_list | The group is a cue list. |
| playlist | Playlist - one cue at a time. |
| start_first | Start first child and go to next cue. |
| start_first_and_enter | Start first child and enter into group. |
| start_random | Start a random child and then go to the next cue. |
| timeline | Timeline - start all children simultaneously. |

#### Where Used

The **group modes** enumeration is used in the following ways:

- **mode** property of the [group cue](#group-cue) class.

---

<a id="light-dashboard-view-mode"></a>
## light dashboard view mode

#### Constants

| Constant | Description |
| --- | --- |
| sliders |  |
| tiles |  |

#### Where Used

The **light dashboard view mode** enumeration is used in the following ways:

- **dashboard mode** property of the [light dashboard](#light-dashboard) class.

---

<a id="midi-command"></a>
## midi command

#### Constants

| Constant | Description |
| --- | --- |
| channel_pressure |  |
| control_change |  |
| key_pressure | a.k.a. aftertouch |
| note_off |  |
| note_on |  |
| pitch_bend | a.k.a. pitch wheel |
| program_change |  |

#### Where Used

The **midi command** enumeration is used in the following ways:

- **command** property of the [midi cue](#midi-cue) class.
- **midi command** property of the [cue](#cue) class.

---

<a id="midi-type"></a>
## midi type

#### Constants

| Constant | Description |
| --- | --- |
| msc | MIDI Show Control message. |
| sysex | MIDI System Exclusive message. |
| voice | MIDI Voice message. |

#### Where Used

The **midi type** enumeration is used in the following ways:

- **message type** property of the [midi cue](#cue) class.

---

<a id="mtc-ltc"></a>
## mtc ltc

#### Constants

| Constant | Description |
| --- | --- |
| ltc | Linear/Longitudinal Timecode. |
| mtc | MIDI Timecode. |

#### Where Used

The **mtc ltc** enumeration is used in the following ways:

- **sync mode** property of the [cue list](#cue-list) class.

---

<a id="smpte-format"></a>
## smpte format

#### Constants

| Constant | Description |
| --- | --- |
| fps_24 | 24 frames per second. |
| fps_25 | 25 frames per second. |
| fps_30_drop | 30 frames per second, drop frame. |
| fps_30_non_drop | 30 frames per second, non-drop frame. |

#### Where Used

The **smpte format** enumeration is used in the following ways:

- **smpte format** property of the [midi cue](#midi-cue) class.
- **smpte format** property of the [timecode cue](#timecode-cue) class.

---

<a id="target-modes"></a>
## target modes

#### Constants

| Constant | Description |
| --- | --- |
| target mode cue |  |
| target mode patch |  |

#### Where Used

The **target modes** enumeration is used in the following ways:

- **target mode** property of the [fade cue](#fade-cue) class.
- **target mode** property of the [reset cue](#reset-cue) class.

---

<a id="timecode-smpte-format"></a>
## timecode smpte format

#### Constants

| Constant | Description |
| --- | --- |
| fps_23_976 | 23.976 frames per second. |
| fps_24 | 24 frames per second. |
| fps_24_975 | 24.975 frames per second. |
| fps_25 | 25 frames per second. |
| fps_29_97 | 29.97 frames per second, drop frame. |
| fps_29_97_non_drop | 29.97 frames per second, non-drop frame. |
| fps_30_drop | 30 frames per second, drop frame. |
| fps_30_non_drop | 30 frames per second, non-drop frame. |

#### Where Used

The **timecode smpte format** enumeration is used in the following ways:

- **smpte format** property of the [cue list](#cue-list) class.

---

<a id="timecode-start"></a>
## timecode start

#### Constants

| Constant | Description |
| --- | --- |
| lookback time | start cues whose timecode triggers precede the incoming timecode by the lookback window. |
| recent hour | start cues whose timecode triggers fall within the most recent hour of incoming timecode. |
| recent minute | start cues whose timecode triggers fall within the most recent minute of incoming timecode. |
| skip | do not start cues whose timecode triggers precede the incoming timecode. |
| start all | start all cues whose timecode triggers precede the incoming timecode. |

#### Where Used

The **timecode start** enumeration is used in the following ways:

- **timecode start behavior** property of the [cue list](#cue-list) class.

---

<a id="timecode-stop"></a>
## timecode stop

#### Constants

| Constant | Description |
| --- | --- |
| hard pause | hard pause timecode triggered cues when incoming timecode stops. |
| hard stop | hard stop timecode triggered cues when incoming timecode stops. |
| none | do nothing when incoming timecode stops. |

#### Where Used

The **timecode stop** enumeration is used in the following ways:

- **timecode stop behavior** property of the [cue list](#cue-list) class.

---

<a id="records"></a>
# Records

---

<a id="range-record"></a>
## range record

A 2-item record representing the offset and length of a substring.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| rangeLength | get/set | integer or text | The length of the substring range. |
| rangeOffset | get/set | integer or text | The 1-indexed location of the starting character of a substring range. |

#### Where Used

The **range record** is used in the following ways:

- **range** property of the [text format record](#text-format-record).

---

<a id="rgba-color-record"></a>
## rgba color record

A 4-item record representing red, green, blue, and alpha percentage values of a color.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| red | get/set | real number |  |
| green | get/set | real number |  |
| blue | get/set | real number |  |
| alpha | get/set | real number |  |

#### Where Used

The rgba color record record is used in the following ways:

- **backgroundRgbaColor** property of the [text format record](#text-format-record).
- **rgbaColor** property of the [text format record](#text-format-record).
- **shadowRgbaColor** property of the [text format record](#text-format-record).
- **strikethroughRgbaColor** property of the [text format record](#text-format-record).
- **underlineRgbaColor** property of the [text format record](#text-format-record).

#### Examples

This script will set the color of all the text in cue `2` to a nice purple-y color:

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set aNiceColor to {rgbaColor:{red:0.5, green:0.2, blue:0.6, alpha:1}}
  set text format of cue "2" to aNiceColor
end tell
```

This script will set the color of the underline of all the text in cue `2` to primary blue:

```applescript
tell application id "com.figure53.QLab.5" to tell front workspace
  set aNiceColor to {underlineRgbaColor:{red:0, green:0, blue:1, alpha:1}}
  set text format of cue "2" to aNiceColor
end tell
```

---

<a id="row-column-record"></a>
## row column record

A 2-item record representing a position defined by a numeric row and column value.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| column | get/set | integer |  |
| row | get/set | integer |  |

#### Where Used

The **row column record** is used in the following ways:

- **cart position** property of the [cue](#cue) class.

---

<a id="size-record"></a>
## size record

A 2-item record representing width and height values.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| height | get/set | real number |  |
| width | get/set | real number |  |

#### Where Used

The slice marker record record is used in the following ways:

- **shadowOffset** property of the [text format record](#text-format-record).

---

<a id="slice-marker-record"></a>
## slice marker record

A 2-item record representing the play count and end time of a slice.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| playCount | get/set | integer | The number of times a slice will play. Play count -1 = infinite loop. |
| time | get/set | real number | The end time of a slice. |

#### Where Used

The slice marker record record is used in the following ways:

- **slice markers** property of the [audio cue](#audio-cue) class.
- **slice markers** property of the [video cue](#video-cue) class.

---

<a id="text-format-record"></a>
## text format record

A record representing the formatting aspects of a text string.

#### Properties

| Property | Access | Type | Description |
| --- | --- | --- | --- |
| backgroundRgbaColor | get/set | rgba color record | An RGBA color record representing the percentage values for the red, green, blue, and alpha components of the background color of this format. |
| fontFamily | get/set | text | The font family for this format. (e.g. "Helvetica", "Courier New") |
| fontName | get/set | text | The font name for this format. (e.g. "CourierNewPS-BoldItalicMT") |
| fontSize | get/set | real | The font size for this format. |
| fontStyle | get/set | text | The font style (face) for this format. (e.g. "Regular", "Light Oblique") |
| lineSpacing | get/set | real number | The line spacing for this format. |
| range | get/set | range record | A range record representing the index and length for the substring that has this format. |
| rgbaColor | get/set | rgba color record | An RGBA color record representing the percentage values for the red, green, blue, and alpha components of the text color of this format. |
| shadowBlurRadius | get/set | real number | The shadow blur radius for this format. |
| shadowOffset | get/set | size record | A size record representing the width and height components of the shadow offset of this format. |
| shadowRgbaColor | get/set | rgba color record | An RGBA color record representing the percentage values for the red, green, blue, and alpha components of the shadow color of this format. |
| strikethroughRgbaColor | get/set | rgba color record | An RGBA color record representing the percentage values for the red, green, blue, and alpha components of the strikethrough color of this format. |
| strikethroughStyle | get/set | text | The strikethrough style of this format. Possible values are "none", "single", and "double". |
| underlineRgbaColor | get/set | rgba color record | An RGBA color record representing the percentage values for the red, green, blue, and alpha components of the underline color of this format. |
| underlineStyle | get/set | text | The underline style of this format. Possible values are "none", "single", and "double". |
| wordIndex | get/set | integer | An optional 1-indexed word number to which this format should be applied. When used, the "range" property will be ignored. (setting only) |

#### Where Used

The text format record record is used in the following ways:

- **live text format** property of the [text cue](#text-cue) class.
- **text format** property of the [text cue](#text-cue) class.
