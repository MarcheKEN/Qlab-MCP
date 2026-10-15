---
name: qlab-workspace-authoring
description: Review and organize QLab workspaces with the existing MCP tools, including dependency checks, staged cue edits, renumbering, selected-property copies and relative adjustments. Use for workspace authoring and reviews, without playback.
---

# QLab workspace authoring

Read the [canonical workflow](../../../docs/user/workspace-authoring.md) before
reviewing or organizing a workspace. It contains tool selection, dependency
order, three request examples and the final report format.

- Review is read-only unless the user has authorized the actual changes.
  Existing authorization remains valid for its stated scope; do not ask again.
- Resolve workspace and cue UUIDs. Bound reads to the requested scope; consult
  family details and edit capabilities only for relevant cues/dependencies.
- Separate confirmed problems, proposed improvements and unknown/unreviewed
  state. A complete structural index does not prove complete health coverage.
- Stage edits: files/destinations, targets/modes, activation/dependencies, final
  values, fresh verification. Do not combine changes that reset dependencies.
- Use the existing writer's readiness, dry run and exact fresh tokens. Stop on
  uncertainty; no setter retry or automatic rollback. Split edits by family.
- Renumber into free numbers; copy only requested compatible properties;
  calculate relative requests from fresh finite baselines, without clamping.
- Preserve unknown values, real capability blocks and manual timing boundaries.
  Historical notes do not override current reads. Computer Use only inspects.
- Report scope, confirmed evidence, proposed/applied changes and pending checks.
  Saved configuration is not proof of playback or physical output.

Do not add raw OSC, AppleScript, `/live`, Audio Maps, Script compilation, output
signals or cue execution to this workflow. If MCP tools are unavailable, report
the limitation; the skill is guidance, not a substitute transport.
