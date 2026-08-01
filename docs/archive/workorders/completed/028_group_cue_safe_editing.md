# Group Cue Safe Editing

Archive note: this document preserves the completed implementation and runtime
evidence. Remaining safe edge validation lives in
[`030_group_edge_runtime_validation.md`](../../../status/workorders/active/030_group_edge_runtime_validation.md).

Status: runtime-validated QLab 5.5 subset; edge validation remains.

## Scope

The existing `qlab_edit_cues` tool and `group_basic` profile now gate:

- Group `mode`: `1` Start first and enter, `2` Start first, `3` Timeline,
  `4` Start random, `6` Playlist
- Playlist scalars: `playlist/doLoop`, `playlist/doShuffle`,
  `playlist/doCrossfade`, `playlist/crossfade/duration`

Modes `0` List and `5` Cart remain read-only. No new public tool or input model
was added; `qlab_update_cues` remains the compatibility alias.

## Gates

- `confirm:groupMode:v1:` and `confirm:groupPlaylist:v1:`
- one cue, one canonical saved property
- exact workspace and Group cue UUIDs
- fresh Group type/mode, health, activity, loaded/overridden, and child-audition
  state
- ordered direct-child UUID/type/continue/timing/armed/health/duration snapshot
- process-bound HMAC token with nonce and 300-second expiry
- fresh token validation followed by atomic single-use consumption immediately
  before exactly one setter send
- consumed-token state retained after timeout, QLab error, or failed verification
- no automatic mutating retry; timeout recovery uses fresh readback only
- fresh scalar and child readback after the setter
- explicit child/Group side-effect reporting and no implicit restoration
- rollback only after a new dry-run and fresh token

Playlist properties fail closed unless fresh mode is exactly `6`. Loop enable
requires a readable non-zero child duration. Crossfade enable, or duration
change while enabled, fails when a child is shorter than the effective
crossfade. Shuffle option writes compare child order before and after.

## Blocked

- Playlist `currentCue`, `currentCueID`, `next`, and `previous` writes
- `/shuffle`, playhead/control routes, GO, playback, audition, and raw OSC
- deprecated Playlist aliases for new writes
- Timeline inspector gestures and invented Group Timeline scalar routes
- fade-in/fade-out crossfade curve shapes: UI behavior is documented, but the
  local OSC dictionary provides no deterministic setter/readback

## Evidence

Primary OSC source:
`docs/references/qlab_osc_dictionary.md`. QLab behavior was cross-checked with
the official Group Cues manual, local QClass 5.5 transcripts, and the supplied
screenshots. Timeline and Playlist transitions can change child
continue/post-wait state, so tokens bind the full ordered child snapshot and
post-write differences are reported.

Local tests cover token families/expiry, immediate replay, replay after
rollback, concurrent consumption, consumption after timeout/error/failure,
exact UUIDs, stale child
fingerprints, one-send behavior, normalized timeout states, mode verification,
duration constraints, scalar readback, Shuffle order effects, transition child
effects, and Group `continueMode 0 -> 1 -> 0` with rollback.

QLab 5.5 runtime passes validated modes `1`, `2`, `3`, `4`, and `6`; canonical
Playlist `doLoop`, `doShuffle`, `doCrossfade`, and crossfade duration; and
common Basics `notes`, `flagged`, `preWait`, `postWait`, and `continueMode`
(`0 -> 1 -> 0`). Each deterministic change used exact UUIDs, dry-run, a fresh
token, fresh Group/child readback, and fresh-token rollback. Timeline/Playlist
transitions and Shuffle produced documented child order, `continueMode`, and
`postWait` changes; these were reported rather than treated as unexplained
mutation. Setter timeouts with matching readback returned
`updated_with_confirmed_timeouts`, with one setter and no mutating retry.

In the latest runtime pass, immediate replay was blocked with zero setters but
returned the less useful no-op-baseline error; replay after rollback returned
`confirmation_already_consumed` before a setter. The validation order is now
fixed and regression-tested locally, but has not been rerun against QLab since
that code change because a fresh MCP restart was not confirmed. A token manually
copied incorrectly failed signature validation with zero setters; that was
caller input error, not an accepted replay or MCP mutation. Final confirmed
runtime activity was running/paused/auditioning `0/0/0`.

Still not runtime-validated: around 200 direct children, Loop with a
zero-duration child, crossfade longer than the shortest child, minimum
crossfade duration, playback, active/auditioning Groups,
warning-but-not-broken Groups, and token expiry in a live MCP process.

## Runtime validation contract

Use a disposable workspace, explicit workspace/cue UUIDs, inactive cues,
dry-run first, fresh tokens, reversible changes, fresh readback, rollback with
a new dry-run/token, and final running/paused/auditioning counts `0/0/0`. Do
not use GO, playback, raw OSC, panic, container/cascade deletion, or unrelated
mutations.
