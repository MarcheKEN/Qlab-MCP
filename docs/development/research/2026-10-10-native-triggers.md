# Native cue Triggers — 2026-10-10

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Evidence and scope

The QLab 5.5.10 installed dictionary at
`/Applications/QLab.app/Contents/Resources/QLab.sdef` defines saved cue properties
for trigger enable state, incoming MIDI message configuration, Wall Clock time
and Timecode display mode. See the official
[AppleScript dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/)
and [inspector documentation](https://qlab.app/docs/v5/fundamentals/inspector/).
The installed SDEF identifies numeric `midi byte one` as an integer; the web
table's string annotation does not justify changing that runtime type.

Existing OSC Triggers remain OSC. The additions reuse the fixed local JSON-to-
AppleScript bridge; callers cannot provide scripts, property names or commands.
Reads are opt-in with `include_native_triggers=true` on family detail Gets.
No new MCP tool is registered. Root lists/carts are outside this cue-only change.

## Property contract

| MCP properties | Dictionary properties / accepted requests |
| --- | --- |
| `hotkeyTriggerEnabled` | `hotkey trigger`; disabling only |
| `midiTriggerEnabled` | `midi trigger`; boolean |
| `midiTriggerCommand` | `midi command`; 0–5: Note Off, Note On, Key Pressure, Control Change, Program Change, Channel Pressure |
| `midiTriggerChannel` | `midi trigger channel`; -1 = any, 0 = workspace channel, 1–16 = explicit channel |
| `midiTriggerByte1`, `midiTriggerByte2` | `midi byte one/two`; integer 0–127 in requests |
| `midiTriggerByte1String`, `midiTriggerByte2String` | `midi byte one/two string`; decimal 0–127, `any`, `<n`, `>n` |
| `wallClockTriggerEnabled` | `wall clock trigger`; boolean |
| `wallClockHours`, `wallClockMinutes`, `wallClockSeconds` | corresponding Wall Clock properties; 0–23 / 0–59 / 0–59 |
| `timecodeTriggerEnabled` | `timecode trigger`; boolean |
| `timecodeShowAsTimecode` | `timecode show as timecode`; boolean |

Observed numeric MIDI bytes may encode predicates and are preserved rather than
normalized to request bounds. Numeric and display-string aliases cannot both be
written in one request. The second byte is blocked for one-byte commands.
QLab 5.5.10 numeric writes preserve the current comparison operator; setting
`midiTriggerByte2=0` from `<70` produces numeric zero and display `<0`.
Use the display-string setter `"0"` to replace the predicate with exact matching.
MIDI trigger fields describe incoming triggers, not outgoing MIDI cue messages.

## Safety rulings

- Configure only a disabled trigger. Change command, activation, safety controls
  and OSC Timecode time in separate calls, with fresh reads and tokens.
- Enabling requires a disarmed cue, `continueMode=0`, and `skipIfDisarmed=false`.
  Disarming alone does not stop auto-continue/auto-follow behavior.
- Hotkey assignment/key/modifiers and Wall Clock weekdays have no located
  dictionary read/write property. Hotkey enabling is blocked without that
  identity; disabling remains possible.
- Timecode activation/display uses the existing containing-list format checks.
- Bind the complete native snapshot, including safety and Timecode components,
  to signed confirmations. Recheck it inside the fixed AppleScript immediately
  before the single setter, then inspect neighbors in a fresh snapshot.
- Keep global input overrides untouched. No capture, external signal, playback
  or permission modification is part of validation.
- Local macOS, a loopback OSC host and exactly one already-running
  `/Applications/QLab.app` are required. Native read errors preserve OSC results
  as partial and block properties without evidence.

Documented availability, automated coverage and observed QLab behavior remain
separate. See the [runtime report](../runtime-validation/2026-10-10-native-triggers.md).
