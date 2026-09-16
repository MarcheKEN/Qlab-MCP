# Audio

## Audio cues

An **Audio cue** needs a `file target` and an `audio output patch`. The patch connects the cue to hardware or a network output and defines routing and channels. QLab recommends AIFF, WAV, and CAF; MP3 can introduce a variable delay on start and is not recommended when exact timing matters.

Source: [Audio Cues](https://reference.qlab.app/docs/v5/audio/audio-cues/) and [Audio Output Patch Editor](https://reference.qlab.app/docs/v5/audio/audio-output-patch-editor/).

## Mic cues

A **Mic cue** passes live audio from an `audio input patch` to an `audio output patch`, using the same cueing, routing, and effects system as Audio cues. It requires macOS microphone permission and normally runs indefinitely until stopped or given a finite duration.

Source: [Mic Cues](https://reference.qlab.app/docs/v5/audio/mic-cues/).

## Practical configuration

To configure an `Audio Output Patch`, open `Workspace Settings → Audio → Audio Outputs`, create the patch, set the device and routing, and select it in the cue's `I/O` tab. Do not confuse the patch with the target file or an `Audio Input Patch`.
