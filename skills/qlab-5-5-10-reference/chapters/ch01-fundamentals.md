# Fundamentals

## Workspace and structure

A **Workspace** contains cue lists, cue carts, cues, patches, and configuration. `Workspace Settings` belongs to the frontmost workspace; its changes do not affect other workspaces and travel with it. Source: [Workspace Settings](https://reference.qlab.app/docs/v5/fundamentals/workspace-settings/).

`Cue Lists` are for sequences; `Cue Carts` are for non-sequential triggering. The `Inspector` exposes common tabs (`Basics`, `Triggers`) and cue-specific tabs.

## Group cues

A **Group cue** contains child cues, including other Groups. The parent mode determines the flow:

- `Timeline`: children start simultaneously.
- `Playlist`: children run sequentially, with optional crossfading, looping, and shuffling.
- `Start First And Enter`: the playhead enters the first child.
- `Start First`: starts the first child and the playhead continues after the Group.
- `Start Random`: chooses an armed, inactive child; it maintains round-robin memory until the workspace is reopened.

Source: [Group Cues](https://reference.qlab.app/docs/v5/fundamentals/group-cues/). Do not extrapolate playback side effects to an MCP edit without a specific test.

## Targets and read safety

Distinguish cue number, unique cue ID, selected cue, playhead cue, and workspace-qualified target. An ambiguous query must not become a write. For exact names and OSC paths, use the separate OSC skill.
