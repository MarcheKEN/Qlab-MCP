# Camera input and Unicode formatting follow-up

Scope: QLab 5.5.10/build 5510. This record separates local Core Text
observations from QLab behavior and runtime validation.

## Camera and Mic input channels

The test workspace's saved `AudioInputPatch` has `deviceDescription`,
`useSystemDevice`, `uniqueID`, and `name`. Its descriptor contains
`deviceUID`, `deviceModelUID`, `inputChannels`, and other metadata. The tested
patch uses the system device; stored metadata does not establish the current
default device or its current input capacity. The OSC patch inventory exposes
only UUID and name. The writer now requires an exact saved patch UUID, a clean
local QLab 5.5.10 document, and a passive CoreAudio device/capacity match, which
it rechecks before each setter. On this Mac CoreAudio reports no devices and
default input ID 0, so actual channel edits remain blocked. NDI Camera audio
uses a separate source and remains unvalidated.

## Text formatting

On the local Mac, passive `CTFontCreateForString` calls for Helvetica Neue
returned Helvetica Neue for ASCII, PingFang SC for Han, Hiragino Sans for
hiragana, Apple SD Gothic Neo for Korean, and Apple Color Emoji for an emoji.
This illustrates font substitution on this machine; it does not prove QLab's
setter behavior or visual output.

Range selection checks Core Foundation composed-character boundaries and also
rejects a split CR/LF pair. CJK formatting now has a fail-closed Core Text gate:
every selected grapheme must resolve to the exact observed font both before and
after the planned edit. Emoji and other scripts stay blocked. Unit tests cover
the gate, but no CJK setter/readback has yet been validated in QLab, so runtime
acceptance remains pending. No cue was started and no capture device was opened.
