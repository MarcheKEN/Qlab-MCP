# Audio File Analysis Implementation Plan

> Historical evidence or dated plan. Use the [current tools](../../user/tools.md) and
> [roadmap](../../status/roadmap.md) for today’s contract. Counts, tokens, commands and observations
> below retain their original scope; this record does not authorize implementation
> or establish present runtime readiness. Original-language quotations and user
> data are preserved where they are part of the evidence.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Add one tool, `qlab_analyze_audio_file`, describing an audio file with numeric measurements every 100 ms, individually timed events and a file summary.

**Architecture:** The server analyzes local files in time blocks without opening OSC connections or changing QLab. A private module computes only blocks required by the requested page, retains a bounded cache and produces typed tables. The same tool supports roughly 30-minute recordings, interval queries and subsequent pages without decoding the whole file on every call.

**Tech Stack:** Existing Python >=3.11, FastMCP >=3.3,<4 and Pydantic >=2.11; optional `audio` extra with NumPy >=1.26,<3 and librosa >=0.11,<0.12; FFmpeg/ffprobe executables available in the MCP process PATH.

## Global Constraints

- One new public tool. Default resolution: 100 ms.
- Size and validate this phase for songs, effects and roughly 30-minute recordings. Thirty minutes is a usage target, not a boundary rejecting 30:01 files. Bound work and memory per call/block; do not add job infrastructure for sessions lasting hours.
- Preserve existing checkout changes; do not change the version or publish a release.
- Local reads only: no playback, OSC, setters, cue creation, original-file changes or normalization of saved audio.
- Honor existing conversational consent for file access; no access tokens, folder allowlist or repeated questions when permission is already granted.
- Accept only regular local files with absolute paths. Reject URLs, directories, FIFOs, devices and unrestricted FFmpeg arguments.
- Measure the original file; QLab effects, levels, trims and loops are outside analysis.
- Never replace unknown values with invented numbers; JSON must contain no NaN or infinity.
- Beats, onsets and energy changes are detections/estimates. Do not assign labels such as thunder, chorus or lightning without a validated classifier.
- Exclude lyrics, voice alignment, musical key, bars/downbeats, spectrograms and classification models from this first implementation.

## 1. Current state and files

`src/qlab_mcp/media.py` already performs bounded local searches. `qlab_search_media_files` is registered in `server.py` and supplies paths. `qlab_get_audio_cue_details` retrieves an existing cue's `fileTarget`. The project has no signal-measurement extraction; `pyproject.toml` declares only FastMCP and Pydantic as runtime dependencies.

This session found neither FFmpeg/ffprobe in the inspected interpreter's PATH nor librosa. That does not establish absence in other environments: check the exact MCP environment before installing the extra and performing live tests.

Planned files:

- Create `src/qlab_mcp/audio_analysis.py`: reads, FFmpeg processes, measurements, events, limits and private cache.
- Create `src/qlab_mcp/audio_analysis_models.py`: Pydantic contract without NumPy/librosa imports.
- Update `src/qlab_mcp/server.py`: one read tool and updated instructions/count.
- Update `pyproject.toml`: optional `audio` extra.
- Create `tests/test_audio_analysis.py`: synthetic signals, simulated processes and cache.
- Update `tests/test_server_tools.py`: FastMCP contract and catalogue.
- Update `README.md`, `docs/user/tools.md`, `docs/user/agent-workflows.md`, `SECURITY.md`, `CHANGELOG.md` and `docs/status/current-state.md`.
- Create `docs/development/runtime-validation/2026-10-07-audio-file-analysis.md`: live acceptance evidence.

## 2. Fixed public contract

```python
qlab_analyze_audio_file(
    path: StrictStr,
    start_ms: StrictInt = 0,
    end_ms: StrictInt | None = None,
    resolution_ms: Literal[10, 20, 50, 100, 250, 500, 1000] = 100,
    offset: StrictInt = 0,
    max_frames: StrictInt = 5000,
    expected_analysis_id: StrictStr | None = None,
) -> AudioAnalysisResult
```

- `start_ms` and `end_ms` bound the file interval in multiples of 10 ms; `end_ms=None` reaches the true end, including the final partial window.
- Require `start_ms >= 0`, `end_ms > start_ms` and in-file bounds; never silently clip invalid requests.
- Require `offset >= 0`, `1 <= max_frames <= 5000`; offset counts rows within the requested interval.
- Reject booleans/strings as numbers and reject unknown fields.
- Every call returns file metadata and a summary of the actually analyzed range, with explicit `scope` and bounds. A partial summary must not claim to describe the entire file. The first call for a long file analyzes its first page; continuation analyzes only the next required blocks.
- `expected_analysis_id` preserves identity across pages. If the file changes, return `source_changed` without mixing pages.
- No `workspace_id`, open QLab or Edit permission is required. The agent obtains the path using existing tools.

Example input:

```json
{
  "path": "/example/audio/source.mp3",
  "resolution_ms": 100,
  "max_frames": 5000
}
```

Response:

- `ok`, `status` (`ok`, `partial`, `error`), `error_code`, `warnings` and `unavailable_fields`.
- `analysis_id`, `time_reference="source_file"`, algorithm and backend versions.
- `source`: resolved path, stat identity, format, codec, channels, known layout, original sample rate, bit depth when available and reported duration. Full-file decoded PCM duration is supplied only when actually measured; otherwise null.
- `summary`: RMS/peak of the covered range, silence, onset/beat counts and rhythm estimates with context. Audio start/end refer to that range, not the entire file's first/last signal unless full coverage is demonstrated.
- `loudness_regions`: integrated LUFS, LU range and true peak dBTP for each actually measured block, with start/end and `scope`. Measure the complete file when it fits in one block. Do not average block LUFS/LRA into invented global loudness; global measurement is outside this version when it requires traversing the entire long file.
- `analysis_parameters`: bands, thresholds, channel aggregation, analysis sample rate, FFT window, hop and effective time precision.
- `timeline`: columns, units, rows, actual page range, total rows, `complete`, `next_offset` and response limits.
- `events`: onsets/beats within the page's covered time range, in source-file seconds. Events count toward the response budget; when reached, reduce the page range and continue through `next_offset` without lost/duplicated events.

Compact table with one typed tuple per row:

```python
COLUMNS = (
    "start_s", "end_s", "rms_dbfs", "peak_dbfs",
    "low_ratio", "mid_ratio", "high_ratio", "centroid_hz",
    "onset_strength", "delta_rms_db", "silent",
)
FrameRow = tuple[
    float, float, float | None, float | None,
    float | None, float | None, float | None, float | None,
    float, float | None, bool,
]
```

Columns always accompany rows in fixed order. A five-minute file produces 3,000 rows at 100 ms; attempt to return all in the first response. Limit each page to 5,000 rows and 512 KiB JSON: reaching either limit returns `complete=false` with explicit continuation through the same tool.

A 30-minute file produces 18,000 rows at 100 ms, traversed through multiple calls. Do not return all 18,000 rows in one message or finish the entire analysis before responding with the first page. `next_offset` and `expected_analysis_id` support continuation; if the cache is lost, recompute only blocks needed for that page.

`complete` describes coverage of the requested interval; it does not guarantee every algorithm succeeded. For example, `status=partial` identifies loudness failure with a valid table. Do not include a confidence score unless the algorithm supplies a calibrated one.

## 3. Measurement definitions

- **RMS dBFS:** `20 * log10(sqrt(mean(sample ** 2)))`, using original samples and mean power across channels.
- **Peak dBFS:** maximum absolute original sample across channels. Distinguish sample peak from true peak.
- **Silence:** RMS <= -60 dBFS; regions lasting at least 300 ms computed over 10 ms base blocks. Publish threshold and resolution; silence means signal below that threshold, not proven absence of sound.
- **Delta RMS:** dB difference from the immediately preceding row at the same resolution/interval. The first row is `null`; later pages preserve the previous reference even when not returning it.
- **Bands:** [20,250), [250,2000), [2000,Nyquist] Hz; power relative to the total within those bands. Publish effective bounds for low-sample-rate files. With zero energy, ratios and centroid are `null`; never divide by zero.
- **Centroid:** frequency average weighted by spectral magnitude, using mean magnitude across channels.
- **Onset strength:** positive spectral change from librosa, without normalization to file/page maximum; return a nonnegative measurement with documented scale and parameters. Aggregate by maximum per row. Do not interpret it as probability or publish a 0–1 scale changing as the file advances.
- **Onsets/beats:** algorithm timestamps at internal resolution; never round to 100 ms boundaries.
- **Loudness:** measure each original block with FFmpeg `loudnorm`, extracting only `input_i`, `input_lra`, `input_tp` with explicit scope. Discard filter output; retain the original file. Loudness-block boundaries do not depend on page bounds.
- **Nonfinite values:** digital silence yields dB `null` with `silent=true`; reject corrupt/nonfinite PCM. Emit no `NaN` strings or invented numbers.

Preserve channels during measurement. Do not sum L/R before computing energy: phase-inverted stereo must not appear silent.

Spectral analysis: sample rate `min(original_sample_rate, 22050)`, 1024-sample Hann window and hop 256. Use canonical blocks up to 300 s anchored at file start, with up to 15 s context on either side for spectrum/onsets/rhythm. Context is outside the loudness block. Each event belongs exclusively to the block whose central range contains its timestamp. BPM estimates are block-local and publish their context; do not claim global tempo. Return effective window/hop in ms. A 10 ms output step does not imply 10 ms detection accuracy: window and hop set the real limit. Verify centering/padding compensation with synthetic impulses.

## 4. Resources, identity and access

- No arbitrary minute or total-file-size limit. Support 1–8 channels and 8–192 kHz sample rates; streaming and interval access avoid loading entire files. Unknown metadata or unverifiable range bounds yield explicit errors, not invented durations.
- Accept WAV, AIFF, MP3, M4A, FLAC and OGG after probing actual format/stream. One audio track; multiple streams or video are outside this version.
- ffprobe timeout 10 s; computation budget 260 s per call; public FastMCP timeout 300 s. All call processes share remaining budget. Stop before another block when budget runs out: return completed blocks, a partial page and continuation. With no completed block, return `analysis_timeout` without implying the whole file exceeds a supported duration.
- Incremental decoding; PCM, FFT and working buffers bounded to 256 MiB. Stop on actual output excess even when metadata is false.
- Invoke executables with argument lists, `shell=False`, `-nostdin`, local files and a local-protocol whitelist. Prevent containers from opening URLs/external resources. Reject playlist formats.
- One new computation at a time. Concurrent calls needing computation return `analysis_busy`; valid cache reads may continue.
- In-memory cache: up to 4 analyzed blocks, 128 MiB total arrays, 10-minute TTL. Store block measurements/events, not full PCM. Simple LRU eviction with `OrderedDict`.
- File identity: resolved path, `st_dev`, `st_ino`, size, `mtime_ns`, `ctime_ns`, algorithm version and analysis parameters. `analysis_id` derives from this identity; it is not a content hash. Cache keys add the canonical block index without changing `analysis_id` between pages.
- Check identity before/after every process and before serving a page. On replacement/modification, discard result/cache and return `source_changed`.
- Lazy NumPy/librosa imports: MCP and other tools must start without the extra.
- Timeout/cancellation: check cancellation between blocks/phases; terminate FFmpeg/ffprobe, wait for exit and release buffers/temporary files. Leave no computation running after the public timeout.
- Stable errors: `invalid_request`, `file_not_found`, `file_unreadable`, `unsupported_media`, `dependency_missing`, `resource_limit`, `analysis_busy`, `analysis_timeout`, `source_changed`, `decode_failed`. A primary error must not return an apparently valid complete table.

## Task 1: Contract and optional extra

**Files:** `audio_analysis_models.py`, `pyproject.toml`, `tests/test_audio_analysis.py`.

**Interfaces:** Models `AudioAnalysisRequest`, `AudioAnalysisResult`, `AudioTimeline`, `AudioEvents`, `AudioSource`, `AudioSummary`; `FrameRow` table in the order defined above. Requests use `ConfigDict(extra="forbid")` and strict types. Typed results allow missing optional measurements.

- [x] First add contract regressions: 100 ms default; invalid intervals; booleans/strings; offset/max_frames; expected_analysis_id and unknown fields.

```python
@pytest.mark.parametrize("args", [
    {"resolution_ms": True}, {"offset": "0"}, {"max_frames": 5001},
    {"start_ms": 11}, {"start_ms": 100, "end_ms": 100},
    {"path": "relative.wav"}, {"unexpected": 1},
])
def test_request_rejects_invalid_inputs(args):
    payload = {"path": "/tmp/source.wav", **args}
    with pytest.raises(ValidationError):
        AudioAnalysisRequest.model_validate(payload)
```

- [x] Run `uv run --extra dev pytest tests/test_audio_analysis.py -q`; verify failure from the missing contract.
- [x] Implement specified models/validators. Document units, time reference and null meaning in the schema.
- [x] Declare `[project.optional-dependencies].audio = ["numpy>=1.26,<3", "librosa>=0.11,<0.12"]`. Never install dependencies at startup or bundle FFmpeg.
- [x] Rerun the contract test; it must pass without NumPy/librosa imports.

## Task 2: Reads and signal measurements

**Files:** `audio_analysis.py`, `tests/test_audio_analysis.py`.

**Interfaces:** `analyze_audio_file(request: AudioAnalysisRequest) -> AudioAnalysisResult`. Private functions for probing, PCM streaming, measurement extraction and page construction; no service/factory classes.

- [x] Create synthetic WAV with `wave`: silence, amplitude-0.5 sine at 100 Hz, another at 1 kHz, another at 4 kHz and ending silence. Expect sine RMS ≈ -9.03 dBFS and peak ≈ -6.02 dBFS (0.1 dB tolerance), with dominant energy in the corresponding band.

```python
def test_dbfs_reference():
    samples = 0.5 * np.sin(2 * np.pi * 100 * np.arange(48000) / 48000)
    rms = 20 * np.log10(np.sqrt(np.mean(samples * samples)))
    peak = 20 * np.log10(np.max(np.abs(samples)))
    assert rms == pytest.approx(-9.0309, abs=0.1)
    assert peak == pytest.approx(-6.0206, abs=0.1)
```

- [x] Implement ffprobe and FFmpeg streaming with internally constructed arguments. Check metadata/streams and determine required page blocks; measure original signal in 10 ms base blocks and obtain a separate spectral stream at the analysis sample rate. Construct decoder seek/duration internally for those blocks. Capture errors without exposing unnecessary private commands/payloads.

```python
probe_args = ["ffprobe", "-v", "error", "-protocol_whitelist", "file,pipe",
              "-show_format", "-show_streams", "-of", "json", str(path)]
decode_args = ["ffmpeg", "-nostdin", "-v", "error",
               "-protocol_whitelist", "file,pipe",
               "-ss", f"{decode_start_s:.6f}", "-i", str(path),
               "-t", f"{decode_duration_s:.6f}",
               "-map", "0:a:0", "-vn", "-sn", "-dn",
               "-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"]
```

`decode_start_s` and `decode_duration_s` derive from the canonical block/context and are checked against file duration. Preserve absolute source-file timestamps when converting interval PCM/FFT indices.

- [x] Add per-block loudnorm measurement to null output; parse JSON with key, value and time-scope validation. Isolated failure yields `status=partial`, null block loudness, visible error and an available table. Do not remeasure an entire 30-minute file per page.
- [x] Verify phase-inverted stereo, total silence, very short files, final partial blocks, clipping, mono/multichannel and metadata lacking bit depth.
- [x] Simulate missing binaries, unreadable files, corrupt audio, ambiguous streams, indirect URLs, excessive decoder output, timeout and cancellation; verify process closure.

## Task 3: Spectrum, events, pages and cache

**Files:** `audio_analysis.py`, `tests/test_audio_analysis.py`.

**Interfaces:** The same `analyze_audio_file`; internal parameters/versions in the response. All resolutions use shared canonical blocks; measurements/context do not change with page boundaries.

- [x] Add impulses at 1.037 s and 2.087 s: detections within one effective window; verify output sampling does not turn them into 1.0/2.0 s.
- [x] Implement FFT blocks with halo, band power, centroid and onset envelope; run `librosa.onset.onset_detect(..., units="time")` and `librosa.beat.beat_track(..., units="time")` over the cross-channel aggregate envelope. Publish estimated times without invented confidence.
- [x] Test 120 BPM clicks: roughly 0.5 s beat spacing within 50 ms; do not require every initial click. Silence returns null BPM and empty events.
- [x] Aggregate to requested resolution. For RMS sum powers/counts; never average dB or lose peaks by selecting only one sample per interval.
- [x] Build pages respecting row limits and JSON <=512 KiB; include events only in the covered time range. On excess, shorten coverage and return continuation recovering every event. Apply the limit to full-response JSON, not rows alone.
- [x] Ensure concatenated pages equal canonical-block traversal without duplicates/gaps. An `offset` at interval end returns an empty complete page, not an invented row. Test events/silence across block boundaries, preserving continuity without padding artifacts.
- [x] Add bounded `OrderedDict` cache and before/after stat fingerprints. Test cache hits without decoding, TTL, LRU, file changes, stale expected_analysis_id and concurrency.
- [x] Measure resources/time with 3–5 minutes of stereo; inspect actual response size and enforce limits. Performance is observed, not a promise of exact per-song timing.
- [x] Add tests for 5-, 15-, 30-minute and 30:01 files: first page, queries near minute 25, continuation and cache eviction. Assert decoded volume is bounded by required blocks/context rather than total duration. Validate a real roughly 30-minute recording without adding it to the repository.
- [x] Compare full-decoded short-MP3 PCM/timestamps with seek queries, and check a late section of a long compressed file. Codec gapless/delay and seeking must not shift events; report observed limits if the format prevents verifying correspondence.

## Task 4: FastMCP integration

**Files:** `server.py`, `tests/test_server_tools.py`, `tests/test_audio_analysis.py`.

**Interfaces:** One public `qlab_analyze_audio_file` tool, `readOnlyHint=True`, `destructiveHint=False`, timeout 300 s, tags `qlab`, `media`, `audio`, `safe-read`. Invoke without `_run_tool` or `QLabReader`.

- [x] First write `Client(mcp).list_tools()` regression and simulated-backend call. Verify types/columns/schemas, input limits and typed output.

```python
async with Client(mcp) as client:
    listed = await client.list_tools()
    tool = next(t for t in listed if t.name == "qlab_analyze_audio_file")
    assert tool.annotations.readOnlyHint is True
    assert "workspace_id" not in tool.inputSchema["properties"]
    assert tool.inputSchema["properties"]["resolution_ms"]["default"] == 100
```

- [x] Register wrapper with defined strict parameters. Analyze outside the event loop with cooperative cancellation closing processes. The wrapper prepares `AudioAnalysisRequest`, lazily imports the backend and returns `AudioAnalysisResult`.
- [x] Update actual snapshots/count and instructions from `Client(mcp).list_tools()`. Preserve existing tools/contracts.
- [x] Test with QLab closed and real backend, and without the extra: `dependency_missing` while other MCP tools remain usable.
- [x] Verify `QLabReader` is never instantiated and OSC never sent: patch `_reader` to raise `AssertionError("No OSC from audio analysis")` and call the tool.

## Task 5: Documentation and acceptance

**Files:** Documentation listed in section 1, tests and runtime evidence.

- [x] Document `uv sync --extra audio --extra dev`, FFmpeg/ffprobe in PATH and checks within the actual MCP environment. Do not install components during planning.
- [x] Document workflow: get `fileTarget`/search path → analyze → select times → edit cues through existing confirmation protocol → compare UI.
- [x] Explain time conversion: source-file events; for simple playback without loops/slices, action position `(event - startTime) / rate`. Add pre-wait when referencing GO. Only events within trim apply. Loops/slices require choosing an occurrence and reading configuration; avoid a misleading universal conversion.
- [x] Add guidance for columns, units, local estimates, blocks, pages/errors and an Unreleased entry without version change. Explain that interval summaries/LUFS do not describe an entire long file, and resolution changes reduce row count without changing supported duration.
- [x] Run `uv run --extra audio --extra dev pytest tests/test_audio_analysis.py tests/test_media_files.py tests/test_server_tools.py -q`; then `uv run --extra audio --extra dev pytest -q` and `git diff --check`. Tests without external executables remain distinct from live acceptance; a skip is not validation.
- [x] Inspect `Client(mcp).list_tools()`; verify exactly one new tool and preserved arguments for existing tools.
- [x] Analyze the authorized authorized audio fixture MP3 and another available effect through MCP. Record file/fingerprint, duration, sample rate, timings, tables and limits. Check the complete song at 100 ms and a selected event at 10 ms.
- [x] Compare metadata/duration against ffprobe and reference measurements against known signals. Computer Use checks the QLab inspector's file/duration without playback or changes. QLab's graph does not validate frequencies, LUFS or beats: those require their own numerical checks.
- [x] Record time, memory, actual response size and cache hits. Correct tables do not prove future lighting is musically calibrated.

## Verified sources

- [ffprobe: metadata and machine-readable output](https://ffmpeg.org/ffprobe.html).
- [FFmpeg loudnorm: input measurements and JSON output](https://ffmpeg.org/ffmpeg-filters.html#loudnorm).
- [librosa RMS](https://librosa.org/doc/0.11.0/generated/librosa.feature.rms.html).
- [librosa onset detection: estimated times](https://librosa.org/doc/0.11.0/generated/librosa.onset.onset_detect.html).
- [librosa beat tracking: estimated tempo and positions](https://librosa.org/doc/0.11.0/generated/librosa.beat.beat_track.html).
- [librosa spectral centroid](https://librosa.org/doc/0.11.0/generated/librosa.feature.spectral_centroid.html).

## Closure criteria

The tool is implemented and verified when it meets the contract, returns correct known-signal measurements, preserves subwindow attacks, supports lossless pagination, invalidates cache on file changes, respects budgets/cancellation and works through MCP on real files. Lyrics interpretation, semantic event recognition and QLab execution remain explicitly excluded.

## Implementation closure — 2026-10-07

Contract, backend, cache, integration, documentation and acceptance completed.
Final suite in the checkout interpreter: **3744 passed, 61 subtests passed**,
without skips. `uv.lock` includes the extra and retains all previously
pinned versions; local wheel/sdist built without publication or version changes.

Acceptance equivalents: commands use `uv run --frozen --no-sync`
in the prepared, verified environment, avoiding resynchronization of preexisting
dependencies. QLab was not closed for the independence check: the wrapper
with a failing `_reader` and analysis/stdio calls without a reader or OSC
demonstrate that QLab is uninvolved; Computer Use was inspection-only.
The roughly 30-minute compressed fixture repeats an authorized song; it is not
presented as an original continuous recording. Duration differences
and estimation limits are recorded in the runtime report.
