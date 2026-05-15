---
name: qlab-osc-guide
description: Help users learn, search, and apply QLab OSC commands and OSC queries using the bundled QLab OSC Dictionary and OSC Queries references. Use when the user asks about QLab, Q-L-A-B, OSC, Open Sound Control messages, cue commands, Network cues, OSC queries in #...#, workspace/cue addressing, or wants examples for controlling QLab or sending live QLab values to another device.
---

# QLab OSC Guide

## Overview

Use this skill to explain and build QLab OSC messages from the bundled references. Favor practical examples and plain-language explanations over dumping reference text.

## References

- `references/qlab-osc-dictionary.txt`: full QLab OSC dictionary. Search this first for exact command syntax, arguments, reply behavior, workspace addressing, cue messages, and port/transport details.
- `references/osc-queries.txt`: short guide to OSC queries in QLab Network cues. Read this when the user asks how to insert live QLab values into outgoing OSC messages with `#...#`.
- `references/reference-index.md`: quick map of useful sections and common lookup patterns.

## Workflow

1. Identify the user goal: controlling QLab, reading state from QLab, sending QLab data to another device, or learning the concepts.
2. Search the dictionary for exact OSC address patterns before giving command syntax. Prefer exact matches over memory.
3. If the user mentions a dynamic value in a QLab Network cue, read `osc-queries.txt` and explain the `#<OSC address>#` query form.
4. Provide the smallest working example first, then add variants such as selected cue, cue number, cue ID, or workspace-prefixed addressing.
5. State what each placeholder means, such as `{cue_number}`, `{workspace_id}`, `{cue_id}`, `{number}`, `{boolean}`, or `{string}`.
6. Mention transport and ports only when relevant: QLab listens for OSC on UDP/TCP port `53000` by default, replies on UDP `53001` by default, and can interpret plain text OSC on UDP `53535`.
7. If the reference does not clearly support the requested command, say what is known, what needs to be checked in QLab, and offer a nearby tested pattern.

## Answer Style

Explain in Spanish when the user writes in Spanish. Keep the OSC addresses exact and in code formatting.

For learning questions:
- Start with the concept in one or two sentences.
- Show a concrete message.
- Explain each part of the address and argument.
- Add one realistic QLab use case.

For build questions:
- Give the final OSC message or Network cue message.
- Explain whether it is a command, a query, or a continuously updating query.
- Include any required QLab setup, such as Network cue duration for continuous query updates.

## Common Patterns

Selected cue:

```text
/cue/selected/start
/cue/selected/number
```

Specific cue by cue number:

```text
/cue/{cue_number}/start
/cue/{cue_number}/name
```

OSC query inside a QLab Network cue:

```text
/device/standby #/cue/selected/number#
```

Continuously updating query:

Use the same `#...#` query inside a Network cue and give that Network cue a duration. QLab updates the query value while the Network cue is running.

Workspace-specific addressing:

```text
/workspace/{id}/cue/{cue_number}/start
```

Use workspace prefixes when multiple workspaces may be open or listening on the same port.

## Searching Tips

Use focused searches against `qlab-osc-dictionary.txt`, for example:

- Search `/cue/selected` for selected-cue addressing.
- Search `/cue/{cue_number}/` plus the property name for cue commands.
- Search `Workspace messages` for workspace-level commands.
- Search `Show Control Broadcast messages` for broadcast/update behavior.
- Search a cue type name, such as `Network`, `Audio`, `Group`, or `Video`, when the question is cue-type-specific.

Do not paste long excerpts from the references. Summarize and cite the relevant file name when helpful.
