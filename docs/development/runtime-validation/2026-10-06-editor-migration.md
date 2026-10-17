# Cue editor migration — QLab 5.5.10

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

## Environment and method

Workspace `redacted-workspace-6b31c91e.qlab5`, UUID `8E86FE91-668B-560C-B738-4D581B5A7498`,
path `<redacted-local-path-851cab375f>.qlab5`.
One workspace, Edit access/Mode, zero active cues. All writes used the source
FastMCP server via `Client(mcp).call_tool`, reviewed dry runs and fresh signed
confirmations. Computer Use only selected cues/tabs/text for inspection.
No GO, Preview, Send, signals, UI edits or automatic setter retries.
Installed MCP registration still needs restart; this validates the source tools.

Each successful setter was followed by fresh saved-state readback. Restoration
used new dry runs/tokens. Raw configuration comparisons confirm every tested
fixture's original settings, text and full format runs were restored exactly.

## Verified live

- Group Playlist UUID `FF2A2F6A-05AD-5ED9-B5DB-FE89D53DB510`: Duck Level
  `0 → -6 → 0`; Second Trigger `0 → 6 → 0`. UI shows `-6` and `plays next`,
  with Duck activation still off. Two sequential setters, fresh readings,
  two fresh-token restoration setters. [Evidence](2026-10-06-group-triggers.json).
- Root Cue List UUID `DCBE4AD4-E7F5-57F2-97B4-DA4388CD9F87`: flagged
  `false → true → false`; Freewheel `0.25 → 0.75 → 0.25`. Inspector showed
  `0,75`; list flag visible. Timecode sync remained off.
  [Evidence](2026-10-06-cue-list-signed.json).
- Text1 UUID `AF8C54B5-8FEC-5C90-B2E0-E558B2A6C917`: ASCII `[0,3]`
  font-size `72 → 48 → 72`; then two disjoint operations `[0,3]` and `[4,end]`
  with 48/60. QLab returned mixed fragments, unchanged neighbors preserved;
  inspector visually matched sizes. Restoration returned all runs to72.
  [Ranges](2026-10-06-text-ranges.json).
- Text JSON full color red→cyan→red and line spacing1.6→2→1.6 verified.
  Inspector text selection exposes spacing2 and then1,6; without selecting
  text the disabled spacing control shows1, which is not the saved value.
  [Attributes](2026-10-06-text-attributes.json).

ASCII/range proof probes used a process-local proposed range policy before
publishing `ranges_verified=True`. Integer to-end requests are converted to an
absolute range from the complete saved text snapshot. No percentage/word policy
was enabled by this experiment.

## Blocked / pending validation

- Existing FX raw inventory consists only of parameter dictionaries. Dorado
  UUID `CC889BBC-471F-5039-854E-5F61184B73D6` shows Edge Work in the UI, radius10,
  intensity2.619, matching OSC parameter observations. OSC supplies no type/name
  to bind instance identity. A selected EdgeWork read returns partial identity
  error while preserving inventory; parameter dry run fails with zero setters.
  No structural FX mutation attempted. Parameters/enabled/stack changes remain
  blocked until identity and structural/dependency proofs exist.
  [Evidence](2026-10-06-fx-identity-blocked.json).
- Unicode probe text `Á😀 é\nDos palabras`: native range length19 proves UTF-16
  units. A proposed `[1,2]` font-size setter changed the emoji to48, but also
  normalized fontName/family/style from Helvetica Neue Bold to Apple Color Emoji
  Regular. Verifier reported `verification_inconclusive`, one setter, no retry.
  Finally restored original content and full typography, confirmed exact.
  Non-ASCII formatting remains blocked; no acceptance of fallback normalization.
  [Probe](2026-10-06-text-unicode-probe.json).
- Words, percentages, font resolution, absent attributes and partial shadows
  remain unverified/blocked. Fade & Stop boolean cannot establish integer scope.
  FX Fade flags/defaults/dependent cues/duplicate-stack mutations remain pending.

## Automated acceptance

`PYTHONPATH=src .venv/bin/python -m pytest -q`: **3678 passed,61 subtests passed**.
UDP/TCP simulation requires localhost bind; sandbox-only execution failed with
`PermissionError: [Errno 1] Operation not permitted`, so the final suite ran with
permitted localhost access. Initial coverage assertions were corrected to reflect
explicitly excluded temporary duration; historical records remain labelled.

Fresh `Client(mcp).list_tools()`: **71 tools,44 reads,27 writes**,
no `qlab_edit_cues` registration/export. [Registry](2026-10-06-editor-schemas.json).
`git diff --check` passed. No dependency, version or release change.
