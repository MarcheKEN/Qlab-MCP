---
name: qlab-5-applescript
description: "Exact lookup in the QLab 5 AppleScript Dictionary for commands, classes, properties, elements, enumerations, records, syntax, and examples."
---

# QLab 5 AppleScript Dictionary

Use this skill to answer questions about QLab 5 AppleScript names and
signatures. Preserve capitalization, spaces, identifiers, types, parameters,
and code literally.

## Source and authority

- Official source: [QLab AppleScript Dictionary](https://qlab.app/docs/v5/scripting/applescript-dictionary-v5/).
- Repository copy: [`docs/references/qlab_applescript_dictionary.md`](../../docs/references/qlab_applescript_dictionary.md).
- Portable copy: [`references/qlab_applescript_dictionary.md`](references/qlab_applescript_dictionary.md).
- Provenance and hashes: [`references/source-manifest.json`](references/source-manifest.json).

The official page remains authoritative. The local snapshot documents QLab 5,
but does not establish a specific patch release.

## Exact navigation

1. Read [`chapters/navigation.md`](chapters/navigation.md) to choose the section.
2. Search for the literal first in the complete copy:
   `rg -n '^## go$|^## workspace$|fontName|com.figure53.QLab.5' references/qlab_applescript_dictionary.md`.
3. For an entry, preserve its `Syntax`, `Result`, `Parameters`, `Classes`,
   `Properties`, `Elements`, `Where Used`, and `Examples` blocks.
4. Distinguish the **QLab Suite** from the **Standard Suite**. Do not attribute
   a standard command to QLab without saying so.

## Safety and accuracy rules

- Do not invent commands, properties, types, or examples by analogy.
- Do not confuse a class name with a cue number or a unique ID.
- Do not execute AppleScript or modify QLab from this skill.
- Separate what the dictionary confirms from any unverified runtime behavior.
- If the entry is absent, respond: `Not found in the supplied QLab AppleScript Dictionary.`
