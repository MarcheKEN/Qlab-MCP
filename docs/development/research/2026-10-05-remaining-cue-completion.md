# Completion of the nine saved cue editors

## Sources and implementation

The repository [QLab 5 OSC dictionary](../../references/qlab_osc_dictionary.md),
current property registry, family readers and common Control executor define the
contract. QClass explanations guide test workflows; they do not establish setter
permission or readback reliability. The previous adapter inventory is historical.
Live evidence below uses QLab 5.5.10, not an assumption from documentation.

`write/remaining.py` derives typed indexed operation/read selectors from existing
property contracts and routes all nine families through the common Control
executor. `remaining_context.py` reuses existing media policy, slice prediction,
Light command analysis and Fade validators. No dependency or public profile is
added. `qlab_edit_cues` remains available.

All family setters now require signed five-minute one-use confirmations binding
tool, workspace, cue/type, canonical indexed destination, old/new values and
family dependencies. Whole-batch preflight and reservation precede mutation;
identity, baseline, permissions/mode and inactivity are checked again per setter.
Exact patch payload fingerprints, file stat/realpath, cue contexts, ownership,
selector snapshots and cumulative slice inventories prevent stale authorization.
Selectors are separated from dependent settings when resets cannot be predicted. File assignment also reads channel/Levels effects and cannot verify success while the newly assigned media remains broken.
Results expose observed effects; batches remain sequential and non-atomic.

The generic writer now uses `ensure_always_reply=True` in each known setter
request. `/alwaysReply 1` and setter share UDP socket/TCP session. Preparation
failure records no setter. Only setters permit missing acknowledgement data.
Fresh verification remains mandatory; timeout never triggers another setter.

## Corrections confirmed during implementation

- Slice play-count batches require the complete expected cumulative inventory;
  scalar equality cannot hide movement of another marker.
- Fade geometry/rate/Levels must fit a resolved inactive target. Target-mode
  changes validate dormant cue/patch UUIDs. Relative Levels cannot request silence,
  and activation edits cannot remove the last active parameter.
- Timecode frame-rate aliases are removed from immutable dependencies when changed.
  QLab preserves duration and start label and normalizes end time on format change;
  verification uses fractional rates and checks that resulting span, within one frame.
- Every scalar identity/query uses its own prepared connection. This removed the
  live intermittent pre-setter identity-read failures seen while selecting MIDI modes.
- Complete Levels snapshots can include QLab's reserved output columns beyond
  visible patch outputs. Individual edits still obey actual cue/patch bounds.

## Gates retained

- Audio/Mic `doLevel` and `doObjectIDLevel` belong to Fade; blocked.
- Mic input count/offset: input capacity is absent from the documented payload.
  UI capacity is evidence for inspection, not authorization to bypass this gate.
- Objects: UUID must exist in cue inventory and absence of an Audio Map must be
  independently readable. Ownership unknown or map-backed objects are blocked.
- Network Device Definition parameters: type/range/fade metadata unavailable;
  pending validation and blocked. `customString` is opaque saved text, independent
  of a protocol guessed from a patch name.
- MSC command-dependent parameters: OSC does not prove activation metadata;
  blocked. Supported mode/command/format/device and Voice/SysEx configuration
  retain strict mode/range validation.
- Default Levels: expected template state unavailable; blocked. Bulk clears
  require affected inventories; object clears additionally require ownership.
- Script source, Trim, Audio FX and undocumented curves lack an applicable OSC
  saved setter. Captures from target lack a complete expected snapshot.
- Fade & Stop scope readback is boolean in the fixture, so scope changes remain
  blocked. Setting Timecode trigger time does not imply enabling that trigger.

## Validation limits

The [runtime report](../runtime-validation/2026-10-05-remaining-cue-completion.md)
separates actual properties tested from missing fixtures. In particular MIDI File
has no healthy file fixture, SysEx payload starts empty, no cue-owned Object fixture
was available, and LTC output zero cannot be restored through positive-only
writes. Those cases are pending live validation; simulated coverage is not called
hardware/runtime coverage. Audio timing cannot extend past observed media end
without independently verified media length. No GO, Preview, Send, signal capture,
Audio Map edit or script compilation was performed.
