# Remaining cue editors — bounded live validation

QLab 5.5.10, one open `redacted-workspace-6b31c91e.qlab5`, workspace UUID
`8E86FE91-668B-560C-B738-4D581B5A7498`. Computer Use confirmed the path
`<redacted-local-path-851cab375f>.qlab5`.

The source registry exposes 72 tools (44 reads, 28 gated writes). The installed
MCP process still exposes the previous surface and requires a restart. These
tests called the new public tools through `fastmcp.Client(mcp)` with the configured
OSC transport; they did not bypass their validation or executors.

## Live results

Audio, Mic, Light, Fade, Network, MIDI, MIDI File, Timecode and Script each passed:

- Fresh Get details, including Triggers and editing capabilities, without errors.
- Name dry-run with observed previous value and no executed operations.
- One name setter followed by matching fresh readback.
- Fresh restoration plan, one restoration setter and matching independent Get.
- Computer Use confirmation of temporary and restored names in the Main,
  Audio and Light lists. Empty saved names correctly revert to generated labels.

All nine saved names, the Main list and original `AUDIO_MISSING_FILE` selection
were restored. The container inventory remained at 19. A preexisting running Mic
was left untouched; a Triggers dry-run failed with
`Workspace has running or paused cues.` and `executed_operations=[]`.
No cues were executed and no signals were activated.

## Acceptance and limits

Full suite: **3566 passed, 61 subtests passed**. Source `Client(mcp).list_tools()`
confirmed the nine schemas, workspace UUID format and 1–50 update limits.
`git diff --check` passed.

Live mutation coverage is **name only**, across all nine families. It does not
prove every family-specific setter. Existing family gates remain authoritative;
Network/MIDI configuration and other unverified endpoints remain planned-only.
Boolean Fade & Stop readback does not prove its scope, which remains blocked.
Script source/compilation, Audio Maps, `/live` and execution remain excluded.
See the [scope inventory](../research/2026-10-02-remaining-cue-edit-tools.md) and
[sanitized evidence](2026-10-02-remaining-cue-tools.json).
