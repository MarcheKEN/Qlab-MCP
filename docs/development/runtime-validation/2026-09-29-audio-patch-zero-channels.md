# Audio patch: channel 0 investigation

## Read-only evidence

2026-09-29, QLab 5.5.10. Original `redacted-workspace-6b31c91e.qlab5` remained open.
Workspace UUID `8E86FE91-668B-560C-B738-4D581B5A7498`; output patch UUID
`42852B2A-3A48-525D-BB84-51A6B299D49C`. Its exact `/uniqueID` matched
before the channel reads. MCP output-patch detail reported 12 cue outputs,
`routing=[1,2]`, no mutes/solos, and crosspoint 1→1 at 0 dB.

The repository's `QLabOscClient.request_tcp` issued only no-argument reads,
fully qualified by workspace and patch UUID. No setter, `/live`, or cue command
was sent. Sandbox network access initially failed with `Operation not permitted`;
the same read-only calls succeeded with approved local network access.

Base: `/workspace/{workspace_UUID}/settings/audio/patchID/{patch_UUID}`.

| Suffix | Result |
|---|---|
| `/level/0/0` | 0 dB |
| `/level/1/0` | 0 dB |
| `/level/0/1` | 0 dB |
| `/level/0/2` | 0 dB |
| `/level/1/1` | 0 dB |
| `/level/13/1` | QLab reply status `error` |
| `/level/1/3` | QLab reply status `error` |
| `/level/0/3` | QLab reply status `error` |
| `/level/13/0` | QLab reply status `error` |

The existing UI inspection showed Main at (0,0), input gains in column 0,
output gains in row 0, and positive-index crosspoints. The successful reads
are consistent with that layout. Identical initial values do not independently
prove each address's write semantics. Out-of-range errors support reliable
channel validation for this patch and runtime; do not extrapolate to all devices.

## Required next validation

1. Close originals with their pending changes explicitly resolved; open only a
   disposable copy. Confirm file path, workspace/patch identity, Edit permission,
   and zero active cues before every mutation sequence.
2. For (0,0), (1,0), and (0,1), read the prior value, prepare one bounded change
   to −3 dB, send one setter, read freshly, inspect the affected UI control and
   neighboring values, then restore with a separate single setter and readback.
   A timed-out setter must never be resent automatically.
3. Validate numeric and `-inf` behavior using the configured minimum-volume
   normalization. Keep mute/solo channel selectors strictly positive.
4. Only after write semantics are proven, allow zero in the existing Audio
   Output Patch level operation and matching Get selectors. Preserve strict
   integers, the 128 cue-output ceiling, exact identity, baseline tokens,
   known-channel validation, and existing positive crosspoint behavior.
5. Tests should cover Main, input/output gains, invalid indices, stale baseline,
   and no duplicate setter after timeout. Update tool schema descriptions to
   distinguish these matrix locations.

## Workspace preservation

Three workspaces were open at the start: `redacted-workspace-7cd29b97.qlab5`,
`redacted-workspace-6b31c91e.qlab5`, and `redacted-workspace-ba83c794.qlab5`. Attempting to close
`redacted-test-workspace` produced a Save / Don't Save / Cancel prompt for existing unsaved
changes. Cancel was selected. User input is required to resolve those changes;
none were saved or discarded. No write validation has occurred yet.

Update: the user subsequently authorized discarding `redacted-test-workspace` changes.
Computer Use selected Don't Save on that workspace's close prompt, and then
closed `redacted-workspace-ba83c794` without a save prompt. A byte-identical disposable
copy was created at `/private/tmp/mcp_settings_expansion_20260929.qlab5`, SHA-256
`927f302b28401563b54b5faae941ef1e0633824160e8e4075cd7d60e66e70396`.
Automatic approval review rejected closing `redacted-workspace-7cd29b97` because discard
authorization covered only `redacted-test-workspace` and other unsaved changes might exist.
No workaround was attempted. Authorization to close redacted-show-workspace, cancelling if
it asks to save, was requested and remains pending. The disposable copy has
not been opened and no setter has been sent.

## Numeric write validation completed

The user authorized closing redacted-show-workspace with cancellation if it asked to save.
It closed without a save prompt. Computer Use then opened the exact disposable
path above; OSC confirmed one workspace with the expected UUID and copy name,
Edit readiness, and zero running/paused cues before every setter. Patch UUID
and exact baseline were re-read immediately before each write.

| Coordinate | Change and fresh readback | UI verification | Restoration |
|---|---|---|---|
| (0,0) | 0 → −3 requested; −2.999948263168335 read | Main slider changed; output sliders stayed at unity | 0 read back |
| (1,0) | 0 → −3 requested; −2.999948263168335 read | Screenshot showed input 1 at −3, Main/outputs/crosspoint 1→1 at 0 | 0 read back |
| (0,1) | 0 → −3 requested; −2.999948263168335 read | Output 1 slider changed; Main/output 2 stayed at unity | 0 read back |

Each of the six calls sent exactly one setter. Every setter reply timed out;
none was resent. Fresh reads confirmed changes and restorations. After every
call, five bounded reads checked (0,0), (1,0), (0,1), (0,2), and (1,1): only
the intended location changed. At the end all five read 0 dB. This is bounded
evidence, not a scan of the complete matrix. No cues were executed or saved.

The research probe reused QLabReader, its write-readiness check, activity
snapshot, transport, and fresh reads. It did not bypass the production MCP
schema to advertise untested operations: public Get/Edit still reject zero
until their explicit implementation is updated. The successful tests establish
numeric Main/input/output gain semantics for this patch on QLab 5.5.10.
`-inf` at these three locations still requires separate validation.

Subsequent `-inf` tests completed for all three locations: one setter read back
−60 (configured minimum), then a separate restoration setter read back 0.
Each of these six setters timed out and was not resent. The same five bounded
locations showed only the requested location changed; all ended at 0.
The local implementation now admits zero in Audio level request/result schemas
and Get selectors. Input count checks still reject nonexistent positive rows;
mute/solo stay positive. Focused Workspace Settings tests: 76 passed.

Final checks: full suite 3221 passed, 59 subtests passed (37.01 seconds);
`Client(mcp).list_tools()` returned 56 tools with zero-based Audio level
selectors. The contract snapshot was updated only for the two affected tools.
After discarding the copy's test changes, Computer Use reopened the original
`redacted-test-workspace` path. The updated local reader accepted all three zero-index Get
selectors and generated three valid Edit dry runs with zero executed setters.
No package version or release changed. An already-running MCP process must
reload the local implementation before these new selectors become available.
