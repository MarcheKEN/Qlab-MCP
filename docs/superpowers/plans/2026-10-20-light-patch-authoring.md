# Light Patch Authoring Implementation Record

Date: 2026-10-20. PR #19, branch `codex/light-patch-authoring`.

**Design:** [Light Patch authoring](../specs/2026-10-20-light-patch-authoring-design.md).
**Evidence:** [Native acceptance](../../development/runtime-validation/2026-10-20-light-patch-authoring.md).

## Completed implementation

- [x] Bounded nested keyed-archive reader/writer; active-root inventory and
  clone-on-write exterior branch preserve shared carriers and unrelated objects.
- [x] Strict batches of 1–100 typed operations for create/update/rename/delete
  of instruments, groups and workspace definitions.
- [x] Final-state references, group cycles, definition consumers, physical channel
  footprints and output-namespace conflicts are validated before writes.
- [x] Art-Net and explicit USB identity configuration; scalar 8/16-bit and RGB
  definition parameters. Other recognized existing variants are preserved.
- [x] Patch-only edits. Rename/delete report partial cue-reference warnings;
  cues, MIDI Dashboard and global Library are not modified.
- [x] Dry-run, needs_save, source/native-state-bound five-minute single-use tokens,
  no-op behavior, clean close, same-path replacement and one bounded recovery.
- [x] Private reopen preserves other documents without changing public Open.
- [x] A lost Open acknowledgement can be confirmed by fresh state without retry.
  Post-open dirty state is reported and never implicitly saved.
- [x] Public tool, schemas, inventory and user/security/architecture documentation
  reconciled: 80 tools, 49 read-only and 31 gated writes.
- [x] Automated tests and native MCP acceptance cover the implemented operations.

## Evidence limits retained

- No compatible USB-DMX device was detected. USB validation covers the saved
  schema and a deliberately synthetic identity accepted on reopen, not hardware.
- CMY/HSI/Pan-Tilt/Muxer creation is not exposed. Existing recognized data is
  preserved; adding public encodings requires separate native acceptance.
- Routing and unused definitions are verified from the file. OSC-visible used
  definitions and patch membership are checked independently after reopening.
- Unit tests exercise failure phases and recovery; the native run also exposed
  and retained an uncertain Open timeout. Not every crash point was tested by
  killing QLab or the operating system.
- The historical generic-writer failures were not reproduced or assigned a
  universal cause. Current writer source and its accepted native results are
  retained instead of assuming those historical failures apply to every method.
