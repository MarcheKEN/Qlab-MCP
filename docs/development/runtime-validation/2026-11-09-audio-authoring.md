# Audio authoring — 2026-11-09

## Scope

This pass adds guarded authoring for saved audio patches and limited existing
Audio FX chains, plus reads for saved routing cells, device descriptions and
AudioUnit identity/parameters. It does not add cue execution, capture, Audio
Maps, Preview, Monitor, `/live` or physical-output validation.

## QLab 5.5.10 fixture observations

Validation used disposable copies of a temporary workspace fixture. The
original `mcp_prueba.qlab5` SHA-256 was unchanged.

- QLab reopened a copy with output patches duplicated, renamed and reordered;
  the cue-output name was also visible after reopening.
- QLab reopened a copy with the built-in `AUDynamicsProcessor` on an output
  bus and showed the effect bypassed. A separate cue Audio FX bypass was
  confirmed in the saved archive after reopening.
- In a separate disposable copy, a saved output patch with
  `useSystemDevice=false` was changed through the QLab 5.5.10 archive planner
  to `true`. Before/after archive SHA-256 values were
  `e3a8c0dd7b63988350403ead4aa5ad4dcb402ca8b1aaaf0a3360a1011c98289e` and
  `d04599f057dd419e0b4b4094ecec08b7a18c2e4ae4d1d318267944dbb5bdd40c`.
  After reopening that output file in QLab, Patch 2 displayed `System Output -
  Altavoces del MacBook Air`. This validates enabling system mode and retaining
  its device descriptor; it does not validate the gated MCP transaction or
  switching back to an explicit device.
- QLab saved and reopened a separate copy after adding one Audio Object directly
  to an Audio cue with an empty `audioMapID`. The archive ownership check found
  its UUID in that cue's `AudioObjectCollection`; objects with map, duplicate,
  shared-cue or embedded-track ownership are rejected. No object OSC setter was
  sent.
- The archive planner added a virtual NDI device to a disposable copy. After
  reopening it in QLab, the Output Devices row showed `30 fps, 2 channel,
  48000 Hz, 1024 audio buffer size`. The starting and resulting fixture hashes
  were `e3a8c0dd7b63988350403ead4aa5ad4dcb402ca8b1aaaf0a3360a1011c98289e` and
  `6467f5690a7b2f532099181a9f6ccd667a39b79c8a17fb399c93d9b26617e164`.
- Changing `AUDynamicsProcessor` attack and gain in its editor did not preserve
  those parameter values after QLab closed and reopened the fixture: the chain
  remained, while attack returned to `0.03` and gain to `0.0`. Parameter writes
  therefore remain blocked; the archive reader does not claim those fields as
  persisted parameters.
- The fixture had no saved Trim field that could establish a supported
  encoding. Trim editing remains disabled; this does not affect cue
  `startTime` or `endTime`.
- The passive CoreAudio inventory returned no devices in this environment.
  Assigning an explicit device, and switching from system mode to an explicit
  device, therefore remain blocked unless inventory is available. Enabling
  system-device mode is covered separately above.
  CoreAudio availability stays separate for input and output channel directions;
  Mic capacity checks continue to depend on input-channel observations.

These observations establish saved configuration round-trips for the listed
fixture operations only. NDI audio-channel and buffer-size contract tests also
cover boundary and Syphon-rejection cases. No cue was run; playback, microphone
capture, device negotiation and physical audio output were not tested.

## Automated checks

Focused tests cover guarded archive operations, routing matrix bounds, device
inventory absence, Audio FX chain changes and public schemas. Repository test
results: **2,496 passed, 40 skipped, 61 subtests passed**. The first sandboxed
attempt could not bind local TCP/UDP sockets; the suite passed when run with
loopback access. Ruff reports no findings on added lines; its existing-file
scan still reports pre-existing findings elsewhere in the files.
