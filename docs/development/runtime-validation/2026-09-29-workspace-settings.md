# Workspace Settings OSC edits — QLab 5.5.10

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Validation used `/private/tmp/mcp_workspace_settings_disposable.qlab5`, copied byte-for-byte from `redacted-workspace-6b31c91e.qlab5` (SHA-256 `927f302b28401563b54b5faae941ef1e0633824160e8e4075cd7d60e66e70396`). Computer Use confirmed that QLab had closed the original, opened this exact copy, and showed no active cues. OSC reported one workspace, UUID `8E86FE91-668B-560C-B738-4D581B5A7498`, in Edit mode with edit access.

Each published operation was tried as a dry run followed by one setter, a fresh read of the same property, and a separate gated restoration in the copy. No cues were executed. The tested operations were:

- General: `minGoTime`, `selectionIsPlayhead`.
- Audio output patch `42852B2A-3A48-525D-BB84-51A6B299D49C`: `name`, `cueOutputChannels`, numeric `level`, literal `-inf`, `mute`, `solo`, `muteClear`, `soloClear`.
- Video output route `233D1E49-6FA7-5B1C-B0F8-9FD7B1E7A865`: `enableGuides`.
- Video stage `A41F907E-3E01-570E-A4BC-0B86C6A1922E`: `name`.
- Video region `8BBA6421-9F0E-5B2B-95F9-A99A99059A71`: `bounds`, `origin`, `size`, `x`, `y`, `width`, `height`, indexed `controlPoint`, `enableGrid`, `enableGuide`. The exact region Get returned OSC bounds and the selected control point.

All setter replies timed out, but fresh readback confirmed every change and restoration. No timed-out setter was resent. QLab quantized the requested `-3.0 dB` to `-2.999948263168335 dB`; the level comparator now allows this measured difference. Setting `-inf` returned the configured minimum volume (`-60 dB`) on OSC readback. The response retains that raw number and warns that OSC cannot distinguish these two internal states. Routing dropped output 1 while its sole tested crosspoint was at `-inf`; routing membership cannot validate whether a device output exists. The exact crosspoint read is used instead.

The control point `(145, 725)` lay outside the region bounds `(0, 0, 960, 110)` and inside the associated route's `naturalSize` `(1920, 1080)`. Point edits therefore validate against the OSC output area after checking the route identity. All coordinates in the tools are OSC coordinates.

The audio patch-name setter has no clear permission cell in the OSC dictionary. On this copy it accepted a change, read back the new name, and restored the original. The patch detail Get now exposes `/name` as `name_property`; its displayed `name` includes device information and is not the exact setter baseline.

`reset`, `routing/reset`, and `resetControlPoints` remain unpublished. Their documented effects span multiple or incompletely enumerable values, so this test could not establish a complete before/after and restoration contract. Undo/redo, Audio Maps, and `/live` remain excluded.

Final fresh OSC reads matched all 13 recorded starting properties, and the original file's SHA-256 was unchanged. The installed MCP server was not restarted; the new public surface was inspected in-process with `Client(mcp).list_tools()`.

The disposable copy was closed without saving its test changes. Computer Use then reopened the original at `<redacted-local-path-851cab375f>.qlab5`.

## Follow-up during implementation resume — 2026-09-29

After the original was reopened, two additional reversible setter checks were
made there: Output 5 `enableGuides` false→true→false and the `Cuadro Superior`
stage name temporary rename→original. Every setter reply timed out; fresh
readback confirmed the requested state and the restoration. No setter was
resent and no cue was executed. Computer Use showed the original stage name and
region geometry after reopening the editor. The original file SHA-256 still
matches the baseline above.

The connected MCP exposes the 56-tool surface, but its running reader is older
than the final local fixes: an input-patch Get still advertises output-patch
edit operations, and Network reports `passcode_present=false` when OSC omits
the field. Local source and tests now report those states as unknown/unsupported;
reload the MCP process before relying on the fixes.

## Read-only recheck after implementation resume

Computer Use confirmed the input-patch row exposes only Name and Device. In
Network settings the UI showed a configured destination and a populated
passcode field; the credential value was not copied. Fresh reads from the
connected MCP still returned output-only edit operations for the input patch
and `passcode_present=false`. A fresh read from the local source against the
same workspace returned no input-patch edit operations and `passcode_present=null`.
The destination was omitted from OSC, so both readers should report its
presence as unknown (`null`) despite the UI showing a configured destination.
The local Network read also returned `passcode_present=null` as designed.

No setting was changed in this recheck. The QLab Settings window was returned
to Video → Output Routing, where Output 5 remained off.

## Multi-workspace recheck after MCP reload — 2026-09-29

Three open workspaces were resolved by UUID and read explicitly: `redacted-workspace-6b31c91e.qlab5` (`8E86FE91-668B-560C-B738-4D581B5A7498`), `redacted-workspace-7cd29b97.qlab5` (`9D9FDE61-4388-5E9D-B5E2-D28840C882DD`), and `redacted-workspace-ba83c794.qlab5` (`A7721349-A90B-54D4-8F52-EAAFDCE538E0`). All are QLab 5.5.10, readable, in Edit mode, and reported zero active cues in their visible QLab windows.

General, Audio overview/output/input, Video overview/stage/route/region, Light, Network, MIDI, connection, and write-readiness Gets returned successfully for all three. The restarted MCP now omits output-only edit operations from Audio Input details and returns `null` for omitted Network destination/passcode fields. Credentials were not inspected or copied.

Computer Use matched General (`minGoTime=0`, playhead locked to selection) in all three. Audio matched for `redacted-test-workspace` (12 cue outputs, channels 1→1 and 1→2 at unity) and `redacted-workspace-ba83c794` (6 cue outputs, the same two unity crosspoints); both Get details returned routing `[1, 2]` and crosspoint 1→1 at `0 dB`. In `redacted-test-workspace`, the Audio Input row exposed only Name and Device, matching its Get without edit operations. Matadero's patch is disconnected: its UI matrix still displays the two unity crosspoints, but OSC returned `routing=[]`, `routing_present=false`, and `routing_count=0` while device presence was unknown. The exact 1→1 level query returned `0 dB`. This conflicts with the matrix shown by QLab; do not interpret the empty OSC list as confirmed absence of saved routing.

Video route names and connected/offline states matched the UI in all three. Exact route Gets returned `enableGuides=false`, matching the UI's Show-off state. Stage names/sizes and region Gets also matched: UI lower-left origins were `(-480,-55)` for `Cuadro Superior`, `(-1512,-982)` for `TELON`, and `(-960,-600)` for `EPSON PJ`; OSC region bounds used `(0,0)` with the same respective sizes. Region grid and guide toggles were off in both views.

All 36 edit dry-runs were made with explicit workspace and object UUIDs: ten operations per workspace returned `dry_run`, while `muteClear` and `soloClear` returned `unchanged` because both lists were empty. No setters were sent to Matadero or `redacted-workspace-ba83c794`.

On the named test workspace only, `selectionIsPlayhead` was changed true→false→true using separate fresh dry-run tokens. Both setter replies timed out; each fresh MCP Get confirmed the requested value, and Computer Use showed the checkbox off then restored on. Neither request was resent. No cues were executed.

The disconnected-audio comparison exposed an unknown-versus-empty issue. The local summarizer now reports `routing`, `routing_present`, and `routing_count` as `null` when routing is empty and the device is not confirmed present. A local FastMCP Client read against Matadero returned these unknown values; its dry-run could not be checked locally because that process lacked configured write credentials. The already-running MCP process was started before this final local correction and must be reloaded to expose it. The full test suite then passed: `3204 passed, 59 subtests passed` with loopback UDP access.

## Final live setter check — 2026-09-29

On `redacted-workspace-6b31c91e.qlab5`, Video Stage `Cuadro Superior` was changed to a temporary name and restored; the fresh Get and refreshed QLab stage list both showed `Cuadro Superior`. Region `A` (`8BBA6421-9F0E-5B2B-95F9-A99A99059A71`) then changed `enableGrid` false→true→false using separate dry-run tokens. Each setter reply timed out, but fresh Gets verified true and then false. The editor showed Grid on after reopening, and off after the restoration and another reopen. OSC bounds remained `(0,0,960,110)`; QLab displayed lower-left `(-480,-55)`.

The QLab file SHA-256 remains `927f302b28401563b54b5faae941ef1e0633824160e8e4075cd7d60e66e70396`. No cues were executed. No setter was sent to Matadero or `redacted-workspace-ba83c794`.

At the time of this check, the connected MCP process still reported Matadero's empty audio routing list as `[]` / `false` although device presence was unknown. This was superseded by the post-restart recheck below.

## Recheck after the reported MCP restart — 2026-09-29

The connected MCP resolved all three UUIDs as QLab 5.5.10 workspaces in Edit mode. General, Audio, Video, Network, and MIDI overview Gets succeeded in all three. General remained `minGoTime=0` and `selectionIsPlayhead=true`; Audio reported 12 cue outputs for `redacted-test-workspace` and Matadero, and 6 for `redacted-workspace-ba83c794`; Video listed 9, 6, and 4 stages respectively. Omitted Network destination/passcode fields returned `null` in all three.

Computer Use matched General, the Audio patch names/devices and channel levels, and Video stage names/sizes in the three current Settings windows. In Matadero, QLab showed the External Headphones patch disconnected and both device-output crosspoint sliders at `1`. After the reported restart, the connected MCP's patch overview and exact output-patch Get both returned `routing=null`, `routing_present=null`, `routing_count=null`, and unknown device presence. The exact 1→1 read returned `0 dB`, matching the UI's unity slider. This confirms the connected MCP now uses the corrected unknown-routing semantics. Network destination/passcode fields omitted by OSC returned `null` in all three workspaces.

After that restart, the connected MCP's five Edit tools each returned a one-operation dry run on `redacted-test-workspace` for General `selectionIsPlayhead`, Audio crosspoint level, Video Output `enableGuides`, Video Stage name, and Video Region `enableGrid`. Every response reported zero executed operations. No setter was sent during this recheck.

No settings were changed in this recheck; no setters were sent to Matadero or `redacted-workspace-ba83c794`, and no cues were executed.
