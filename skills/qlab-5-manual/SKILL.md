---
name: qlab-5-manual
description: Help users learn and apply QLab 5 using the official QLab 5 manual. Use when the user asks how QLab 5 works, how to use workspaces, cue lists, cue carts, cues, the inspector, workflow tools, audio, video, lighting, network/MIDI/show control, scripting, other cue types, tutorials, licenses, preferences, system setup, or needs guidance finding the right QLab 5 documentation page.
---

# QLab 5 Manual

## Overview

Use this skill to answer QLab 5 usage questions by navigating the official QLab 5 manual. This skill complements `qlab-osc-guide`: use this skill for general QLab behavior and workflows, and use `qlab-osc-guide` for exact OSC command syntax.

The official manual changes over time. When exact current behavior matters, consult the linked documentation in `references/official-docs-map.md` before giving a final answer.

## References

- `references/official-docs-map.md`: map of the official QLab 5 documentation sections and useful links.
- `references/qlab-5-learning-guide.md`: local summary of QLab 5 concepts, navigation strategy, and answer patterns.

## Workflow

1. Identify the user's domain: fundamentals, workflow tools, audio, video, lighting, networking/MIDI/show control, scripting/automation, other cues, tutorials, licensing/preferences, or system setup.
2. Open `official-docs-map.md` and choose the most relevant official QLab page.
3. For general concepts, explain the QLab mental model first: workspaces contain cue lists/carts, which contain cues; cues are configured mainly in the inspector.
4. For procedural questions, give a concrete step-by-step workflow and mention the relevant QLab UI area: workspace window, cue list, toolbar, inspector, workspace settings, tools menu, or preferences.
5. For cue-specific questions, explain:
   - what the cue type does,
   - whether it needs a target,
   - which inspector tabs/settings matter,
   - how it behaves in cue sequences,
   - what license or hardware dependencies may apply if relevant.
6. For show-control, automation, OSC, or AppleScript questions, decide whether to stay in this skill or switch/reference `qlab-osc-guide` for OSC dictionary details.
7. Avoid pretending to know exact menu names, defaults, or version-specific details if not checked. Verify from the official docs when precision matters.

## Answer Style

Answer in Spanish when the user writes in Spanish.

For beginners:

- Start with a short conceptual explanation.
- Use a realistic example.
- Define QLab terms such as workspace, cue list, cue cart, cue, target, inspector, pre-wait, post-wait, duration, and continue mode.
- Avoid overwhelming the user with every advanced option.

For experienced users:

- Lead with the direct workflow or setting.
- Mention edge cases, compatibility, show mode/edit mode, licenses, and performance considerations when relevant.
- Point to the exact manual section or URL.

For troubleshooting:

- Ask what the user sees in QLab only when the answer depends on runtime state.
- Separate workspace setup, cue settings, target media/hardware, and external control systems.
- Recommend checking QLab's warnings/status windows when relevant.

## Core QLab 5 Mental Model

- A QLab document is a workspace.
- A workspace contains cue lists and cue carts.
- Cue lists are sequential structures; cue carts are non-sequential trigger surfaces.
- Cues are the basic show-control objects: audio, video, light, network, MIDI, timecode, group, script, memo, transport cues, and others.
- The inspector is where selected cue parameters are viewed and edited.
- Targets matter for many cues: file targets for media cues, cue targets for fade/transport-style cues, and no targets for some control or utility cues.
- Timing is often built from pre-wait, duration, post-wait, auto-continue, auto-follow, and group/cue sequence behavior.
- Show mode helps prevent accidental edits during operation; edit mode is for programming.

## Common Routing Decisions

Use the official manual:

- "How do I create a cue list?"
- "What is a cue cart?"
- "How do fade cues target other cues?"
- "How do I configure video outputs?"
- "How does show mode differ from edit mode?"
- "How do I use Light cues or the Lighting Command Language?"
- "What are Network cues?"

Use `qlab-osc-guide`:

- "What OSC command starts the selected cue?"
- "How do I query selected cue number with OSC?"
- "What is the exact `/cue/...` OSC address?"

Use both:

- "How do Network cues send OSC?"
- "How do I control QLab from another device?"
- "How do I build a show-control workflow using QLab and OSC?"

## Citation And Source Handling

When using web documentation, cite the official QLab page URL. Do not paste long manual excerpts. Summarize, then give a short link to the relevant section.
