# Lighting, networking, MIDI, and timecode

The documentation groups `Light Cues`, `Light Dashboard`, `Light Patch Editor`, `Network cues`, `MIDI cues`, `MIDI File cues`, `Timecode cues`, `Using MIDI & MSC`, `Using Timecode`, and `Show control broadcast`.

## Fade cues

An **Absolute Fade** (the default) takes each active parameter to its final level regardless of the initial value. A **Relative Fade** adds/subtracts or multiplies/divides relative to the active value; therefore the starting point matters and repeating it can accumulate changes. In QLab 5, absolute fades supersede relative fades. Source: [Fading Video and Video Effects](https://reference.qlab.app/docs/v5/video/fading-video/) and [Fading Audio and Audio Effects](https://reference.qlab.app/docs/v5/audio/fading-audio/).

In `Workspace Settings`, the `Network`, `MIDI`, and `OSC` tabs configure the workspace. OSC permissions are managed in `Network → OSC Access`; the conceptual OSC page explains the flow, and the separate OSC skill contains the exact dictionary.

Official sources:

- [Lighting](https://reference.qlab.app/docs/v5/lighting/)
- [Using MIDI and MSC](https://reference.qlab.app/docs/v5/networking/using-midi-and-msc/)
- [Using Timecode](https://reference.qlab.app/docs/v5/networking/using-timecode/)
- [Workspace Settings](https://reference.qlab.app/docs/v5/fundamentals/workspace-settings/)
- [QLab 5 Manual](https://reference.qlab.app/docs/v5/)

Do not use this page to invent control commands. Playback, Audition, Stop/Panic, and show control require a specific source and separate validation.
