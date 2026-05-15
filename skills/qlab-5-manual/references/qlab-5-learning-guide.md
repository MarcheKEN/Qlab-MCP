# QLab 5 Learning Guide

Use this reference to decide how to explain QLab 5 from the official manual.

## Start with the user's level

For beginners, explain QLab's object model:

1. Workspace: the QLab document.
2. Cue list: sequential show structure.
3. Cue cart: non-sequential trigger grid.
4. Cue: a programmed action or media event.
5. Inspector: the main place to edit selected cue settings.
6. Target: the file, cue, device, or object affected by a cue, depending on cue type.

For advanced users, skip definitions and focus on exact settings, section links, and edge cases.

## Common learning paths

Getting started:

- Read the manual root and Fundamentals.
- Use tutorials such as Zero to Audio, Zero to Video, and Zero to Network.
- Explain edit mode vs show mode early.

Programming cues:

- Start from the Cues and Inspector pages.
- Explain target, pre-wait, duration, post-wait, and continue mode.
- Explain cue sequences when auto-continue or auto-follow is involved.

Audio:

- Start with Introduction to Audio, Audio Cues, output patches, audio maps, fades, and effects.
- Check system recommendations and Mac preparation for performance-sensitive shows.

Video:

- Start with Introduction to Video, Video Cues, Camera Cues, Text Cues, Video Output, NDI, and video effects.
- Separate media file compatibility, output routing, surfaces, and cue timing.

Lighting:

- Start with Introduction to Lighting, Light Cues, Light Dashboard, Lighting Command Language, Light Patch Editor, and Light Library.
- Separate patching fixtures from writing light commands.

Networking and show control:

- Start with Collaboration, QLab Remote, Stream Deck, Using OSC, MIDI/MSC, show control broadcast, timecode, Network cues, MIDI cues, MIDI File cues, and Timecode cues.
- Use `qlab-osc-guide` for exact OSC dictionary addresses and OSC query syntax.

Scripting and automation:

- Start with Script Cues, AppleScript Dictionary, Parameter Reference, and examples.
- Use the OSC dictionary skill for exact OSC commands.

## Answer patterns

Concept question:

1. Define the concept.
2. Explain why it exists in QLab.
3. Give a short example.
4. Link to the relevant manual page.

Workflow question:

1. State prerequisites.
2. Give numbered steps.
3. Mention where in the UI the user acts.
4. Add a check or troubleshooting step.

Troubleshooting question:

1. Identify the cue type and target.
2. Check workspace settings and QLab preferences separately.
3. Check warnings/status windows when relevant.
4. Verify hardware/network/media assumptions.
5. Link to the relevant manual section.

Show-operation question:

1. Distinguish programming from running the show.
2. Mention show mode/edit mode if accidental edits matter.
3. Keep steps operational and concise.
