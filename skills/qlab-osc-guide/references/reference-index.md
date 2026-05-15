# QLab OSC Reference Index

Use this index to choose which bundled reference to inspect.

## Core files

- `qlab-osc-dictionary.txt`: complete QLab OSC implementation reference.
- `osc-queries.txt`: explanation of QLab Network cue OSC queries written as `#<OSC address>#`.

## Useful dictionary locations

- Getting started and ports: near the beginning of `qlab-osc-dictionary.txt`.
- How to read command syntax: search `How To Read This Dictionary`.
- Workspace messages: search `Workspace messages`.
- Cue messages: search `Cue messages`.
- Selected cue addressing: search `/cue/selected`.
- Show control broadcast: search `Show Control Broadcast messages`.
- Examples: search `Examples`.

## Lookup patterns

When the user asks for a QLab OSC command:

1. Search the dictionary for the object or action name.
2. Prefer exact address patterns from the dictionary.
3. Preserve argument placeholders exactly, then explain them.
4. Give a concrete filled-in example when the user has supplied cue numbers, IDs, values, or target device details.

When the user asks for a QLab OSC query:

1. Read `osc-queries.txt`.
2. Build the normal QLab OSC address first.
3. Wrap the address in hash marks when it is used as a query inside a QLab Network cue, for example `#/cue/selected/number#`.
4. If the value should keep updating, tell the user to give the Network cue a duration.
