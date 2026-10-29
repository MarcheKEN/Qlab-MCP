# Settings follow-up — 2026-10-25

## Scope and method

QLab 5.5.10/build 5510, the already-open authorized `mcp_prueba` workspace.
Actual writes used public tools through a persistent FastMCP `Client(mcp)`
loaded from the current source. This retains the public models, preflights,
preview/token and transaction paths; it is distinct from the older attached
MCP process. Computer Use observed the native settings without running cues,
Show, Monitor or requesting capture. Reopening configured devices can initialize
QLab backends; zero active cues does not prove absence of output.

## Accepted behavior

- Root stage order: reversed all 12 stages, reopened, verified OSC order and
  inspected QLab; restored the original order through a second transaction.
  Root ordering does not change viewport layers.
- Root route order: reversed all five routes and restored them. Both executions
  returned `verified`, including native order checks.
- Empty input name: set the unassigned third patch name to the empty string.
  QLab displayed its Name placeholder with no assigned input. Restored `Patch 3`.
- NDI audio sample rates: executed 22050, 88200, 96000 and 44100 Hz, then restored
  48000 Hz. Every corrected execution reopened and returned `verified`; technical
  OSC route reads returned each selected rate. QLab's Output Devices table
  independently displayed 22050 Hz. Other combinations of channels, buffers,
  pixel format and frame rate were not exhaustively exercised.
- Definition details through the public tool: ARRI SkyPanel Mode 26 returned
  all 51 parameters, and Martin MAC Aura PXL 512 returned all 667. Both retained
  `parameters_complete=true` and `importable=false`. Reading every interpretable
  parameter does not enable an unvalidated import.
- Passive Syphon helper: verified the bundled `info.v002.Syphon` framework with
  Apple's code-signing verifier and Figure 53 team `7672N4CCJM`, then observed
  the public directory for one second. It returned `ready`, zero servers and
  retained two AVFoundation cameras. Empty bounded observation is not an
  exhaustive absence claim or acceptance of a live server/frame stream.

## Failure found and recovery

The first 22050-Hz execution wrote an integer `audioSampleRate`, while QLab's
native archive stores a floating-point value. QLab refused to load that file.
The tool returned `uncertain`, phase `replaced`, with the recovery retained.
It did not retry or silently roll back.

Recovery was deliberate: verified that the current file still matched the
failed output hash and the retained original matched the source hash, preserved
the rejected file, restored the exact original, and reopened it via the public
Open preview/confirmation flow. The resolved recovery was retained separately.
The shared device writer now preserves floating-point encoding for sample and
refresh rates. Type-sensitive create/update regressions fail on the previous
implementation; all five sample rates pass after the fix. Repeated native
22050-Hz acceptance then succeeded.

## Preservation and limits

Final semantic graph comparison against the pre-test archive found no differences
in Video, Light, Audio, General, Network, MIDI or the nested cue archive. The
original 12 stages, five routes, three inputs and one saved virtual destination
remain. Byte hashes change after archive transactions; semantic restoration is
not a claim of byte-identical rewrites.

The process-shared Output Devices table still contains pre-existing residual
rows independent of the one configured saved destination. No private registry
access, application restart, NDI discovery, Blackmagic backend or global library
write was introduced. USB/Art-Net delivery, camera frames and rendered video
remain unverified.

## Automated verification

Full regression suite: **2,303 passed, 35 skipped, 61 subtests passed**.
Tests cover complete definition reads despite import rejection, strict import
preservation, exact reorder permutations, temporary references, unchanged layers,
empty input-only names, floating-point sample rates, failed signatures, escaped
framework paths, isolated Syphon failures, budgets and retained FastMCP fields.
The public surface remains 87 tools; only existing schemas were extended.

After installation and MCP restart, attached-chat calls confirmed three input
patches, two cameras and `syphon_status=ready` with zero announced servers.
The attached definition reader returned all 51 SkyPanel Mode 26 parameters,
`parameters_complete=true` and `importable=false`. The overall input status
remains `partial` because the explicitly excluded process/network/capture
coverage is still unavailable; individual local source reads succeeded.

Private response captures and recovery archives were kept outside Git during
acceptance; temporary files may expire. No vendor library payloads, workspace
archives or credentials are committed.
