# Specialized visual cue validation — QLab 5.5.10

Workspace: `8E86FE91-668B-560C-B738-4D581B5A7498`,
`<redacted-local-path-851cab375f>.qlab5`.
User authorized edits in this test workspace while other workspaces stayed open.
Only this exact workspace was targeted. UI was consulted through Computer Use;
cues were never executed. Actual tool calls used source-loaded `Client(mcp)`
and authenticated OSC TCP; the installed MCP needs restart to load new tools.

| Tool / phase | Status | Setter count | Properties |
| --- | --- | ---: | --- |
| qlab_edit_video_cues / plan | dry_run | 0 | opacity, translation |
| qlab_edit_video_cues / execute | updated | 2 | opacity, translation |
| qlab_edit_video_cues / restore_plan | dry_run | 0 | opacity, translation |
| qlab_edit_video_cues / restore | updated | 2 | opacity, translation |
| qlab_edit_camera_cues / plan | dry_run | 0 | preWait, opacity |
| qlab_edit_camera_cues / execute | updated | 2 | preWait, opacity |
| qlab_edit_camera_cues / restore_plan | dry_run | 0 | preWait, opacity |
| qlab_edit_camera_cues / restore | updated | 2 | preWait, opacity |
| qlab_edit_text_cues / plan | dry_run | 0 | fixedWidth, text/format/fontSize |
| qlab_edit_text_cues / execute | updated | 2 | fixedWidth, text/format/fontSize |
| qlab_edit_text_cues / restore_plan | dry_run | 0 | fixedWidth, text/format/fontSize |
| qlab_edit_text_cues / restore | updated | 2 | fixedWidth, text/format/fontSize |
| qlab_edit_video_cues / plan | preflight_failed | 0 |  |
| qlab_edit_video_cues / plan | dry_run | 0 | rate |
| qlab_edit_video_cues / execute | updated | 1 | rate |
| qlab_edit_video_cues / restore_plan | dry_run | 0 | rate |
| qlab_edit_video_cues / restore | updated | 1 | rate |
| qlab_edit_video_cues / plan | preflight_failed | 0 |  |
| qlab_edit_video_cues / plan | dry_run | 0 | level |
| qlab_edit_video_cues / execute | updated | 1 | level |
| qlab_edit_video_cues / restore_plan | dry_run | 0 | level |
| qlab_edit_video_cues / restore | updated | 1 | level |
| qlab_edit_text_cues / plan | dry_run | 0 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / execute | updated | 2 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / restore_plan | dry_run | 0 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / restore | updated | 2 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / plan | dry_run | 0 | text |
| qlab_edit_text_cues / execute | updated | 1 | text |
| qlab_edit_text_cues / restore_plan | dry_run | 0 | text |
| qlab_edit_text_cues / restore | updated | 1 | text |
| qlab_edit_video_cues / plan | dry_run | 0 | level |
| qlab_edit_video_cues / execute | updated | 1 | level |
| qlab_edit_video_cues / restore_plan | dry_run | 0 | level |
| qlab_edit_video_cues / restore | updated | 1 | level |
| qlab_edit_text_cues / plan | dry_run | 0 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / execute | updated | 2 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / restore_plan | dry_run | 0 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / restore | updated | 2 | duckTime, secondTriggerAction |
| qlab_edit_text_cues / plan | dry_run | 0 | text |
| qlab_edit_text_cues / execute | partial_failed | 1 | text |
| qlab_edit_text_cues / restore_after_readback_failure | updated | 1 | text |
| qlab_edit_text_cues / plan | dry_run | 0 | text |
| qlab_edit_text_cues / execute | updated | 1 | text |
| qlab_edit_text_cues / restore_plan | dry_run | 0 | text |
| qlab_edit_text_cues / restore | updated | 1 | text |

All successful writes had fresh readback and were restored with a new dry run.
The intentional unhealthy Video fixture and initially unavailable audio bounds
failed preflight with zero setters. The audio bound implementation was corrected
from a nonexistent field to the observed `cueOutputChannels` and revalidated.
Text verification failed once after a content setter due to a duplicate format
query. Fresh Get confirmed the changed text; a distinct restoration operation
restored the original without retrying the failed change. The corrected content
write and restoration subsequently passed.

Final baseline values: Video2 opacity approximately 0.600000024 and original
OSC translation; Camera16 opacity 1 and preWait 0; Text1 original content
`Mcp video text`, fontSize 72 and fixedWidth 0; Video4 rate 1 and level(1,1)=0;
Text1 duckTime 1 and secondTriggerAction 0.

Full JSON evidence is in `2026-10-01-visual-cues.json`; confirmation tokens were
removed. This validates the listed operations, not every advanced OSC endpoint.

Final automated verification: `pytest -q` passed with 3368 tests and 61 subtests
in 43.63 seconds. Source-loaded `Client(mcp).list_tools()` exposes 62 tools,
including the three specialized editors with batch limits 1–50.
`git diff --check` passed. Advanced effects, Audio FX, ranged Text formatting
and Camera input-channel bounds remain pending as documented in the research.

## Post-restart installed MCP check

After the user's MCP restart, the live registry exposed
`qlab_edit_video_cues`, `qlab_edit_camera_cues`, and `qlab_edit_text_cues`.
All three available workspaces resolved by exact UUID and passed read access;
QLab reported 5.5.10 and Edit Mode. Only `redacted-test-workspace` has Video, Camera and
Text fixtures. On that workspace, each public tool completed one opacity or
font-size write with one setter, fresh readback, then a distinct token-gated
restoration and readback: Video2 60% → 55% → 60%, Camera 16 100% → 90% → 100%,
Text1 font size 72 → 73 → 72. Computer Use showed the matching temporary and
restored inspector values; Text preview returned to 507×152. No cues were run.
The other workspaces were read only: redacted-workspace-ba83c794 has Video cues and
passed a no-setter Video dry run; a second redacted workspace has no Video, Camera or
Text cues. The selected UI workspace ended on Video2 / Video FX as before.

## 2026-10-01 deeper Video validation

After another MCP restart, only `redacted-test-workspace` was edited. Target: Video cue 4,
`VIDEO_VALID`, UUID `4CC5ADC7-D124-58A3-B8CE-95A42CEADC50`. MCP reads reported
QLab 5.5.10, Edit Mode, no active cues, and an initially healthy/inactive cue.
Computer Use only selected inspector pages and read values; it did not edit the
workspace. No cue was run.

| Area | Change and readback | UI comparison / restoration |
| --- | --- | --- |
| Basics and Triggers | 15 properties changed and read back; timecode text was not sent because preflight timed out reading the parent list's `timecodeSMPTEFormat`. | Basics and Triggers matched the changed values. The 15 properties were restored and freshly read. |
| Geometry | 13 setters covered layer, opacity, fill style, smoothing, aspect ratio, blend mode, anchor, translation, scale and all four crop edges. Aggregate `crop` failed preflight because its readback was a list where the writer expected a `Crop` object; scalar crop setters worked. | UI matched Fill Stage, Stretch, layer 990, opacity 73% and Smooth off. Restore stopped before scale when QLab changed scale as a side effect of re-enabling Preserve Aspect Ratio. Scale and crop were then restored in fresh operations. MCP and UI confirmed baseline geometry. |
| Time, loops and audio | 11 setters changed start/end, rate, play count, hold-at-end, clock type, integrated fade, lock-to-cue, main level, one crosspoint and one mute. `preservePitch` was excluded: preflight rejected QLab's integer `0` against its strict boolean model. | UI matched 00:02–01:15, play count 2, rate 1.25, hold/fade on, main level −4 dB and the mute warning. The matrix showed input 1 (L) → output 2 at −12 dB; a one-setter check later confirmed the same cell visually. Mute was cleared with a separately token-gated `qlab_edit_cues` operation because `qlab_edit_video_cues` blocks all writes while `isWarning=true`. No warning remained after clear. |
| Slice marker | Dry run failed reading `/sliceMarkers` with QLab status `error`; no setter was sent. | Generic inspector-safe read reported an empty marker list; no marker was changed. |

During restoration, QLab returned an error for `/endTime` even though its fresh
readback matched the original end time. That setter was not retried. The
remaining timing properties were restored with a new dry run. Final MCP
readback confirmed original name, colors, waits, trigger values, geometry,
start/end, rate, loop count, audio levels, empty mute/solo lists, and
`isWarning=false`, `isBroken=false`, `isRunning=false`, `isPaused=false`.
The UI showed the original duration, time and level values, Clear Mutes disabled,
the restored matrix cell at its `−60 dB` floor (visually empty), and 0 Active Cues.

This deeper pass found preflight/readback edge cases in aggregate crop,
`preservePitch`, warning-state recovery, slice-marker reads, timecode format
preflight and `endTime` acknowledgements. It validates the tested setters on
this workspace; it does not establish that every Video property is reliable.
