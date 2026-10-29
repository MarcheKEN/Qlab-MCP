# Video follow-up — 2026-10-27

QLab 5.5.10/build 5510, workspace `mcp_prueba.qlab5`
(`95F0A03D-140E-4673-974A-E76748EBB023`). All writes used MCP previews,
fresh confirmations and readback. No cue was run or camera capture started.

- A temporary Video cue with `negro.mp4` and a connected stage was healthy.
  Added two slice markers, changed time and play count, deleted them individually,
  then added and cleared two markers; `lastSlicePlayCount` 1 → 2 → 1 succeeded.
- End time 8 → 9.922 seconds succeeded; QLab returned approximately
  `9.92199993133545`. This sample does not establish behavior for other files.
- Video output channel 1 solo was enabled and cleared; readback returned an
  empty solo list. Exposure and ColorControls effects were added; parameter,
  enabled state, order and removal operations succeeded with fresh readback.
- A temporary Camera cue switched from the built-in camera patch to OBS and
  back. Assigning a microphone patch failed before writing because the editor
  queried `settings/audio/inputPatchList`; the supported inventory is
  `settings/mic/patchList`. A fresh FastMCP client loaded from the corrected
  source assigned the existing microphone patch to a temporary Camera cue;
  native readback returned the exact UUID and `isBroken=false`. The reloaded
  Codex MCP then independently created a temporary Camera cue, assigned the
  same input patch, and confirmed the UUID and healthy cue by fresh readback.
  A second temporary Camera cue assigned, cleared and reassigned the input
  patch, then cleared and restored its original audio output patch. Each write
  returned matching readback; the final cue was healthy.
  A channels=2 preview with the microphone assigned was blocked before writing
  because Camera input channel bounds had no validated OSC inventory. The
  follow-up implementation now resolves the saved patch to the current CoreAudio
  device, but this Mac reports no audio devices and default input ID 0, so the
  channel edit remains correctly blocked here.
- A Text cue retained `Prueba Ñ á 漢字 🎭` and a 48-point Latin fragment.
  Formatting the Chinese characters was blocked before writing. ArialMT was
  accepted; a nonexistent font passed preview but QLab kept ArialMT and the
  writer reported `verification_inconclusive` without retry.
- Nine temporary stages expanded from 100×100 to 120×140 using Crop/Pad and
  each anchor. After reopen, OSC reported the requested size and the expected
  region offsets for all nine. This is configuration readback, not comparison
  against independently authored UI resize samples.
- Passive inventory observed the built-in camera and OBS as connected, and the
  built-in Retina display as active and not asleep or mirrored. These macOS
  observations do not prove QLab capture or physical output.

All temporary cues and stages were deleted and read back as absent. The workspace
was saved and reported clean and inactive. Focused visual/contract tests: 300
passed, including the new input-patch regression. CJK formatting, unavailable
font variants, host-specific absence of an audio input, physical output and
rendered content retain their stated limits.

Source follow-up: Camera and Mic channel preflight now requires a clean local
archive and an exact passive CoreAudio identity/capacity match. This machine
currently reports no CoreAudio input devices, so a successful channel write
cannot be demonstrated here. Text CJK preflight now permits only graphemes that
Core Text resolves to the exact observed font; unit tests cover this condition.
The earlier QLab CJK block predates this code. The updated MCP still needs a
fresh dry-run and, for an eligible font, one setter/readback plus UI inspection.

## Scalar font fallback follow-up — 2026-10-29

With QLab 5.5.10/build 5510 and the same workspace, a temporary Text cue
contained `漢字かなé🙂`. The updated source blocked scalar `fontName` and
`fontFamilyAndStyle` previews before either setter was sent. A typed UTF-16
range changed the color of the complete `é` cluster and fresh readback retained
the other text and formatting. The reloaded Codex MCP repeated these checks.
In a second temporary cue, a scalar font change on `hello` returned `updated`
and read back `HiraginoSans-W3`. Both temporary cues were deleted and verified
absent. After reloading Codex, another temporary cue containing `漢字かな`
accepted `HiraginoSans-W3`; a typed color change on the first two characters
returned `updated` and fresh readback preserved the other characters. That cue
was also deleted and verified absent. The workspace was already modified before
testing and was left unsaved;
no cues were run. These checks do not validate emoji rendering or every font.
