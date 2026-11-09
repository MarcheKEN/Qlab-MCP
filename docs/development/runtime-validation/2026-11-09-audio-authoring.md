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
- The fixture had no saved Trim field that could establish a supported
  encoding. Trim editing remains disabled; this does not affect cue
  `startTime` or `endTime`.
- The passive CoreAudio inventory returned no devices in this environment.
  Device assignment therefore remains blocked unless inventory is available.
  CoreAudio availability stays separate for input and output channel directions;
  Mic capacity checks continue to depend on input-channel observations.

These observations establish saved configuration round-trips for the listed
fixture operations only. No cue was run; playback, microphone capture, device
negotiation and physical audio output were not tested.

## Automated checks

Focused tests cover guarded archive operations, routing matrix bounds, device
inventory absence, Audio FX chain changes and public schemas. Repository test
results: **2,462 passed, 40 skipped, 61 subtests passed**. The first sandboxed
attempt could not bind local TCP/UDP sockets; the suite passed when run with
loopback access.
