# Audio file analysis — 2026-10-07

## Verified source and runtime

One new public read-only tool, `qlab_analyze_audio_file`; registry: **73 tools,
46 reads / 27 gated writes**. Existing tools retained. Strict absolute paths,
intervals, resolution, offsets and output tuples are checked through FastMCP.
No OSC/QLabReader is involved in the analyzer. A fresh stdio server started with
the actual Codex MCP command/environment advertised all 73 tools and analyzed a
one-second WAV successfully. The previously running connector must restart to
load the added tool. Package version remains 0.3.0; no release or commit.

Detailed measurements: [runtime JSON](2026-10-07-audio-file-analysis.json).
Dependencies in the project environment: NumPy 2.4.6, librosa 0.11.0,
FFmpeg/ffprobe 7.0. The latter executables were installed into ignored `.venv/bin`;
only the QLab MCP environment PATH was extended, preserving other settings.
No production auto-installer/download path was added.

## Numerical and behavioral checks

Known WAV fixtures validate −9.03 dBFS RMS / −6.02 dBFS peak for amplitude-0.5
sines, dominant 100 Hz/1 kHz/4 kHz bands, silence, a fractional final frame,
antiphase stereo, six-channel power and maximum peak. Impulses retain times
inside the 100 ms output windows; clicks produce approximately half-second beat
spacing. One impulse straddling 300 s is now detected once on the global FFT
grid, including separate pages. No page/file normalization of returned strength.

WAV, AIFF, MP3, M4A, FLAC and OGG passed actual decoding. A compressed seek test
compares samples against the full native decode; a one-second preroll restores
MP3 decoder/bit-reservoir state. Genuine video/playlists are rejected before
analysis. Dimensions outside 1–8 channels / 8–192 kHz, malformed/non-finite PCM,
missing dependencies and invalid files/ranges return explicit errors.

Paging includes the entire result's JSON budget, no duplicated/lost rows or
individual events, and predecessor delta. Cache hit, stat changes, TTL/LRU,
busy calculation and concurrent cache reads are tested. Timeout/cancellation
reaps processes; partial completed blocks preserve a continuation. Base server
imports do not load NumPy/librosa, and missing optional packages leave the base
server usable. Subprocess stdout/log limits also apply to fast exits.

## Real media and 30-minute coverage

Authorized authorized audio fixture MP3: 44.1 kHz stereo, **2263 rows** at 100 ms, one page,
**466231 bytes**, **11.817 s** cold. Cached one-second detail at 10 ms: 100 rows,
0.124 s. FFmpeg measures −10.19 LUFS, 4.3 LU LRA and +2.22 dBTP over the complete
decoded source. Another authorized WAV (`<redacted-local-path-28c6cc97d1>.wav`) produced
1231 rows in 5.039 s. These labels identify fixtures, not classifier outputs.

The approximately 30-minute MP3 is a temporary fixture rendered by repeating
the authorized song. It is **not** presented as an original uninterrupted
30-minute recording. A separate full native decode gives **1800.824603 s**;
all **18009 rows** were retrieved in eight pages, with contiguous intervals and
6171 unique onset times / 2383 unique beat times. Maximum measured response:
524210 bytes, below 512 KiB. Initial page computed only block 0; a minute-25
query computed block 5, not the intervening file. Full traversal exercised LRU
eviction/recomputation; final cache: four blocks / **6138200 feature bytes**.
Cold block pages took about 12.5–13.2 s; cached pages about 0.6–1.1 s. Separate
5/15/30:01 WAV fixtures prove the final partial block and that 30 minutes is not
a hard cutoff. Spectral PCM is read in small batches, not mapped into resident
memory as a complete multichannel block.

Observed process peak RSS: **579584000 bytes**. This includes Python, FastMCP,
Pydantic, NumPy/librosa/Numba and their initialization; it is not a claim that
the whole process fits the 256 MiB working-buffer budget. The former default
per-frame tempogram caused roughly 1.42 GB peak RSS in the first song run;
using a bounded context autocorrelation removes that allocation. BPM is still
an estimate, with a disclosed 40–240 BPM search and 120 BPM log2 prior; no
calibrated confidence or promise of musical correctness.

## QLab / Computer Use contrast

QLab 5.5.10 workspace `8E86FE91-668B-560C-B738-4D581B5A7498`,
Audio cue `9B354ECC-3E85-5048-9985-2337DE975D41`. Existing MCP technical read and
the I/O inspector agree on the authorized audio fixture file, two channels and 44100 Hz.
Time & Loops shows 03:46.233; OSC gives **226.233469 s**. Independent FFmpeg
native decode and the analyzer both give **226.221474 s**, approximately 12 ms
shorter. Reported container duration is **226.246531 s**. These are distinct
observations; no invented equality or definitive QLab-bug attribution. Original
media stat identity stayed unchanged. No GO, Preview, Send or edits.
The display-name UI binding showed another QLab instance's port warning;
inspection was rebound to the existing Desktop QLab workspace instance.

A screenshot validates file/format/displayed timing, not numeric spectrum,
loudness or beats. Numerical fixtures and independent decoding supply that
evidence. QLab trims/rate/loops/effects and lyrics remain outside this tool;
no future lighting design is declared musically calibrated by these tests.

## Review and project gates

Fresh independent review identified two reproducible defects: an onset duplicated
at the canonical boundary and incorrect `source_block` labeling of complete
MP3 loudness. Both regressions failed before correction and passed afterwards.
The full-suite sandbox run exposed denied localhost socket binds; the complete
UDP/TCP suite was repeated with permission instead of skipping it. Six stale
FileTarget tests/inventory assumptions were reconciled with the already present
family implementation, without changing any setter authorization.

Final focused audio/media/registry suite: **202 passed** in102.22s.
Final full suite in the correct checkout interpreter: **3744 passed,
61 subtests passed**, no skips (129.60 s), using
`uv run --frozen --no-sync --extra audio --extra dev pytest -q -rs`.
The exact configured stdio startup advertises **73 tools**, with one new
read-only analyzer. `uv lock --check --offline` and local wheel/sdist build
passed; old locked versions and package version are preserved. `git diff
--check` passed. No claims of GO/playback validation are made.

QLab was left open for UI inspection; independence is covered by a reader
that raises if invoked, deferred-import tests and standalone MCP analysis.
The installed connector needs a restart to load the new registry.
