# Audit fixes — QLab 5.5.10 validation

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

Date: 2026-09-30. Updated checkout tested through `Client(mcp)` using the existing
MCP configuration. The installed server may still need restarting to load these
changes. Version and published release were not changed.

## Target and authorization

Computer Use confirmed the test workspace window at
`<redacted-local-path-851cab375f>.qlab5`, Edit mode,
zero active cues. OSC confirmed UUID `8E86FE91-668B-560C-B738-4D581B5A7498`,
QLab 5.5.10, and Edit permission. The user expressly allowed testing directly
in this workspace, replacing the disposable-copy requirement. Memoria and
redacted-show-workspace remained open; writes were qualified exclusively to the test UUID.
Computer Use was used only for observation. No cues were executed or files saved.

## Reversible Settings checks

| Family | Operation | Setter reply | Restoration |
| --- | --- | --- | --- |
| General | minGoTime | ok | Verified |
| Audio output patch | name | ok | Verified |
| Video output route | enableGuides | ok | Verified |
| Video stage | name | ok | Verified |
| Video region | enableGrid | ok | Verified |

Each change and restoration had a separate dry run and fresh single-use token.
Every real call invoked one Settings setter with same-session `/alwaysReply`
preparation and explicit status-only acknowledgement acceptance. The fresh
readback matched the requested value; restored readbacks matched each initial
baseline. None of these ten setter calls timed out or was resent. This validates
these operations on this version, not every OSC setter or every hardware setup.

## Read regressions

- Text cue `3F11DC3A-7BC7-5A58-917F-78A6108E07FD`: status ok, no errors;
  absent optional styles remain null rather than causing eight failed queries.
- Timecode cue `FE1D267E-B24D-5511-AC94-AC4E4BEEAC2B`: status ok, no errors;
  LTC channel zero preserved. Broken-state diagnostics remain separate.
- redacted-show-workspace Cortina L, region A, point (subregion 0, point 0): read-only result
  ok, x=948.9149903942621, y=217.85067072331196. No writes to redacted-show-workspace.
- Styled and mixed Text fragments are covered by simulated tests. The internal
  QLab cause of absent scalar attribute errors has not been established.

## Automated checks

`PYTHONPATH=src .venv/bin/python -m pytest -q`: 3241 passed, 61 subtests passed.
Socket tests ran outside the filesystem/network sandbox because localhost binds
were denied inside it. `Client(mcp).list_tools()` confirmed 56 tools; only the
Timecode detail output schema changed (LTC channel minimum zero). The contract
snapshot was updated for that exact change. `git diff --check` passed.

Detailed baselines, requested values, setter records and restoration results:
[2026-09-30-audit-fixes.json](2026-09-30-audit-fixes.json). Confirmation tokens and
passcodes are omitted.

## Post-restart MCP and Computer Use check

After the MCP restart, the connected registry exposed all five specialized Edit
tools plus `qlab_get_video_region`; `qlab_edit_workspace_settings` was absent.
Write readiness was confirmed for the exact test workspace in Edit mode.

The five live edits were repeated through the connected MCP tools, each with its
own dry-run, execution token and separate restoration token. All five restored
to their initial baselines. General, Audio, Route and Stage setters returned
`updated` with setter reply `ok`. The Region `enableGrid` setter timed out, but
its fresh readback confirmed the requested value; restoration then returned
`updated` and read back the original `false`. No retry was sent.

Computer Use read-only comparison in Workspace Settings agreed with MCP:

- General: minimum GO interval `0`; Lock playhead to selection on.
- Audio: Patch 1 on System Output, maximum `+12 dB`, minimum `-60 dB`.
- Video Outputs: Stage 9 at `2940 × 1912`; its region editor showed Grid off.
- Output Routing: route 22B1W's Guides column off, matching
  `enableGuides=false` from the MCP route detail.

Fresh MCP reads after the restorations reported the original General values,
Audio patch name `Patch 1`, route guides false, Stage 9 name, and region grid
false. No cues were run; the main workspace view showed zero active cues.
