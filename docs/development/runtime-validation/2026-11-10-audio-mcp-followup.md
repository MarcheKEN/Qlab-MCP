# Audio MCP round-trip follow-up — 2026-11-10

## Runtime evidence

The target was a disposable copy opened in QLab 5.5.10/build 5510. The exact
workspace ID was supplied to readiness and write calls because two workspaces
were open. No write targeted the original `mcp_prueba.qlab5`.

At closeout, QLab's document inventory reported the original path as clean
(`modified=false`). Its current SHA-256 was
`0aaec1a2706cb7276a74af0c626eb8af96f38ad399d057f84dc5260a31231122`, which
differs from the earlier PR snapshot `a884bf20ed09667b6862e99a5960a0668b5d653b8307fca315be252f7aaf4d76`.
No operation here selected the original UUID; this inspection cannot establish
when the two snapshots diverged.

- `qlab_edit_audio_output_patch` changed a Patch 2 routing cell's level, mute
  and solo through confirmed OSC setters. Fresh reads matched the QLab Audio
  settings UI. The cell was restored to its original level with mute and solo
  off, then read back.
- `qlab_edit_saved_audio_patches` renamed Patch 2 in a dry-run/write transaction.
  The writer closed and reopened the copy, and saved-patch readback confirmed the
  name. A second fresh transaction restored the original name; readback confirmed
  the baseline patch names and IDs.
- `qlab_edit_saved_cue_settings` bypassed the saved SnapTune effect on an Audio
  cue, reopened and read back `enabled=false`, then re-enabled it with a fresh
  confirmation and reopened/read back `enabled=true`. QLab's Audio FX inspector
  showed the effect off during the bypass test and on after restoration.
- `set_system_device` switched Patch 2 to system-device mode and back in two
  separate confirmed MCP transactions. Both transactions reported a successful
  reopen and native patch verification. The second readback showed the explicit
  BuiltInSpeakerDevice again, but its saved manufacturer changed from `Apple
  Inc.` to `Unknown`: CoreAudio did not report manufacturer metadata. The local
  writer now preserves manufacturer/model from the existing descriptor when the
  UID is unchanged and the observation omits those fields. Unit tests cover the
  same-UID and new-UID cases; the connected MCP still runs the pre-fix code, so
  this preservation fix has not yet passed a live QLab round-trip.
- Saved-state FX edits now require exact identities from QLab 5.5.10 fixtures:
  SnapTune on cue audio and Apple's AUDynamicsProcessor on output-patch buses.
  Other identities and unknown archived classes remain visible as read-only
  entries. `installed_plugins` remains unknown; identity does not prove runtime
  availability.

These checks establish saved configuration and UI agreement for the named
operations. They do not establish plugin availability for other AudioUnits,
playback, audible processing, or physical output.

## Fail-closed shared-chain guard

Two synthetic archive cases reproduced a shared-effects-array hazard: separate
cue or bus owners referenced the same `effects` array UID. A bypass edit mutates
the referenced effect state in place, so a graph walk that skips repeated UIDs
could count only one reference and alter both owners. Cue and output-bus bypass
now count effect-array owners and reject a shared chain. Existing per-effect
reference checks still reject shared effect objects across distinct arrays.
Output-bus removal and reordering copy the array before editing so other owners
retain their original chain. A VideoCue bypass also rejects an AudioCue object
that is simultaneously reachable as a separate active cue.

The cue and bus shared-array regressions, VideoCue-to-active-AudioCue shared
object case, bus remove/reorder preservation checks, unknown identities and
unknown archived classes first failed, then passed after the fixes. Focused
verification: **78 passed** across
`test_audio_archive.py` and `test_saved_cue_settings.py`.

## Remaining limits

The current writer does not create blank patches, change cue-output counts,
insert AudioUnits, edit AudioUnit parameters, write Audio Object properties,
edit Fade cue audio targets, or write default/silent levels. Explicit-device
assignment requires a current exact passive device identity. The system-device
MCP round-trip above did not validate the metadata-preservation fix; NDI fixture
round-trips are documented in the [November 9 fixture report](2026-11-09-audio-authoring.md).
Trim remains read-only because the build-5510 archive fixture did not establish
a saved encoding. Unknown AudioUnit availability is not inferred from saved
metadata. Audio Maps, GO/live, Preview/Monitor, capture and physical-output tests
remain out of scope.
