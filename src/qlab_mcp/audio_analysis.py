"""Bounded local-file analysis. No OSC, playback, or changes to the source."""
from __future__ import annotations

from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import signal
import stat
import subprocess
import tempfile
import threading
import time

from .audio_analysis_models import (
    AudioAnalysisRequest, AudioAnalysisResult, AudioEvents, AudioSource,
    AudioSummary, AudioTimeline, LoudnessRegion, OnsetEvent, RhythmEstimate,
    TimeRegion,
)

ALGORITHM_VERSION = "1"
BLOCK_SECONDS = 300
CONTEXT_SECONDS = 15
MAX_RESPONSE_BYTES = 512 * 1024
WORK_BYTES = 256 * 1024 * 1024
CACHE_BYTES = 128 * 1024 * 1024
CACHE_TTL = 600
_CACHE: OrderedDict = OrderedDict()
_CACHE_LOCK = threading.Lock()
# ponytail: one calculation at a time bounds memory; cached reads remain concurrent.
_CALC_LOCK = threading.Lock()
_FORMATS = "wav,aiff,mp3,mov,flac,ogg"


class AnalysisError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class _Budget:
    def __init__(self, cancelled=None, seconds=260):
        self.cancelled = cancelled or threading.Event()
        self.deadline = time.monotonic() + seconds

    def check(self):
        if self.cancelled.is_set() or time.monotonic() >= self.deadline:
            raise AnalysisError("analysis_timeout", "Analysis cancelled or time budget exhausted")

    @property
    def remaining(self):
        self.check()
        return self.deadline - time.monotonic()


@contextmanager
def _process(args, budget, *, seconds=None, output=None, output_limit=WORK_BYTES):
    """A watchdog unblocks pipe reads and always reaps the child on cancellation."""
    budget.check()
    deadline = min(budget.deadline, time.monotonic() + seconds) if seconds else budget.deadline
    done = threading.Event()
    failure = []
    with tempfile.TemporaryFile() as errors:
        try:
            process = subprocess.Popen(args, stdin=subprocess.DEVNULL,
                                       stdout=output if output is not None else subprocess.PIPE,
                                       stderr=errors, start_new_session=True, shell=False)
        except OSError as exc:
            raise AnalysisError("dependency_missing", "Cannot start the required audio executable") from exc

        def kill():
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except PermissionError:
                    # Some macOS sandboxes permit child termination but deny group signals.
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass
                except ProcessLookupError:
                    pass

        def watch():
            while not done.wait(0.02):
                if budget.cancelled.is_set() or time.monotonic() >= deadline:
                    failure.append(AnalysisError("analysis_timeout", "Audio process cancelled or timed out"))
                    kill()
                    return
                if os.fstat(errors.fileno()).st_size > 1024 * 1024 or (
                    hasattr(output, "fileno") and os.fstat(output.fileno()).st_size > output_limit
                ):
                    failure.append(AnalysisError("resource_limit", "Audio process exceeded its output budget"))
                    kill()
                    return

        watcher = threading.Thread(target=watch, daemon=True)
        watcher.start()
        # Expose the bounded log for loudnorm parsing while the context is open.
        process.stderr = errors
        try:
            yield process
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
            if failure:
                raise failure[0]
            budget.check()
            if os.fstat(errors.fileno()).st_size > 1024 * 1024 or (
                hasattr(output, "fileno") and os.fstat(output.fileno()).st_size > output_limit
            ):
                raise AnalysisError("resource_limit", "Audio process exceeded its output budget")
            if process.returncode:
                raise AnalysisError("decode_failed", "Audio executable rejected the file or decoding failed")
        except subprocess.TimeoutExpired as exc:
            raise AnalysisError("analysis_timeout", "Audio process timed out") from exc
        except BaseException:
            if failure:
                raise failure[0]
            budget.check()
            raise
        finally:
            kill()
            process.wait()
            done.set()
            watcher.join()
            if process.stdout is not None:
                process.stdout.close()


def _identity(path):
    try:
        resolved = Path(path).resolve(strict=True)
        info = resolved.stat()
    except FileNotFoundError as exc:
        raise AnalysisError("file_not_found", "Audio file does not exist") from exc
    except (OSError, RuntimeError) as exc:
        raise AnalysisError("file_unreadable", "Cannot access the audio file") from exc
    if not stat.S_ISREG(info.st_mode):
        raise AnalysisError("unsupported_media", "Only regular local audio files are supported")
    if not os.access(resolved, os.R_OK):
        raise AnalysisError("file_unreadable", "Audio file is not readable")
    return dict(path=str(resolved), device=info.st_dev, inode=info.st_ino,
                size=info.st_size, mtime_ns=info.st_mtime_ns, ctime_ns=info.st_ctime_ns)


def _unchanged(identity):
    try:
        current = _identity(identity["path"])
    except AnalysisError as exc:
        raise AnalysisError("source_changed", "Source disappeared or became inaccessible during analysis") from exc
    if current != identity:
        raise AnalysisError("source_changed", "Source changed; request a new analysis")


def _dependencies():
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise AnalysisError("dependency_missing", "FFmpeg and ffprobe must be available in the MCP process PATH")
    try:
        import numpy as np
        import librosa
    except ImportError as exc:
        raise AnalysisError("dependency_missing", "Install the optional audio extra in the MCP environment") from exc
    return np, librosa, ffmpeg, ffprobe


def _probe(identity, ffprobe, budget):
    args = [ffprobe, "-v", "error", "-protocol_whitelist", "file,pipe",
            "-format_whitelist", _FORMATS, "-show_format", "-show_streams",
            "-show_program_version", "-of", "json", identity["path"]]
    try:
        with tempfile.TemporaryFile() as output:
            with _process(args, budget, seconds=10, output=output, output_limit=1024 * 1024):
                pass
            output.seek(0)
            payload = json.load(output)
    except (ValueError, AnalysisError) as exc:
        if isinstance(exc, AnalysisError) and exc.code != "decode_failed":
            raise
        raise AnalysisError("unsupported_media", "Cannot read supported audio metadata") from exc
    streams = payload.get("streams", [])
    audio = [s for s in streams if s.get("codec_type") == "audio"]
    other = [s for s in streams if s.get("codec_type") != "audio"
             and not (s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") == 1)]
    if len(audio) != 1 or other:
        raise AnalysisError("unsupported_media", "Exactly one audio stream and no video are required")
    stream = audio[0]
    try:
        rate, channels = int(stream["sample_rate"]), int(stream["channels"])
        duration = float(stream.get("duration") or payload["format"]["duration"])
        depth = int(stream.get("bits_per_raw_sample") or stream.get("bits_per_sample") or 0) or None
        format_name = payload["format"]["format_name"]
        if not math.isfinite(duration) or duration <= 0 or not 8000 <= rate <= 192000 or not 1 <= channels <= 8:
            raise ValueError("unsupported dimensions")
        if not set(format_name.split(",")) & set(_FORMATS.split(",")):
            raise ValueError("unsupported format")
    except (KeyError, ValueError, TypeError) as exc:
        raise AnalysisError("unsupported_media", "Audio duration, format, channels or sample rate cannot be verified") from exc
    return AudioSource(path=identity["path"], fingerprint=identity, format=format_name,
                       codec=stream.get("codec_name", "unknown"), channels=channels,
                       channel_layout=stream.get("channel_layout"), sample_rate=rate,
                       bit_depth=depth, duration_reported_s=duration), payload.get("program_version", {}).get("version", "unknown")


def _executable_version(binary, budget):
    with tempfile.TemporaryFile() as output:
        with _process([binary, "-version"], budget, seconds=10, output=output, output_limit=16384):
            pass
        output.seek(0)
        first = output.readline().decode("utf-8", errors="replace").split()
    return first[2] if len(first) >= 3 and first[1] == "version" else "unknown"


def _decode_args(binary, path, start, duration, rate=None):
    args = [binary, "-nostdin", "-v", "error", "-protocol_whitelist", "file,pipe",
            "-format_whitelist", _FORMATS]
    # Explicit input seek at zero changes gapless MP3 handling in FFmpeg.
    seek = max(0, start - 1)
    if seek > 0:
        args += ["-ss", f"{seek:.9f}"]
    args += ["-i", path]
    if start > 0:
        # Decode one second of preroll to restore compressed-frame/bit-reservoir state.
        args += ["-ss", f"{start - seek:.9f}"]
    args += ["-t", f"{duration:.9f}", "-map", "0:a:0", "-vn", "-sn", "-dn"]
    if rate is not None:
        args += ["-ar", str(rate)]
    return args + ["-c:a", "pcm_f32le", "-f", "f32le", "pipe:1"]


def _signal_bins(stream, rate, channels, duration, budget):
    import numpy as np
    limit = math.ceil(duration * rate) + rate  # tolerate one decoder frame, never unbounded output
    bins = math.ceil((duration + 1) * 100)
    energy = np.zeros(bins, dtype=np.float64)
    counts = np.zeros(bins, dtype=np.int64)
    peaks = np.zeros(bins, dtype=np.float64)
    carry = b""
    position = 0
    while True:
        budget.check()
        data = stream.read(rate * channels * 4)
        if not data:
            break
        data = carry + data
        usable = len(data) // (channels * 4) * (channels * 4)
        carry = data[usable:]
        samples = np.frombuffer(data[:usable], dtype="<f4").reshape(-1, channels)
        if not np.isfinite(samples).all():
            raise AnalysisError("decode_failed", "Decoded PCM contains non-finite samples")
        if position + len(samples) > limit:
            raise AnalysisError("resource_limit", "Decoder exceeded the requested signal range")
        consumed = 0
        while consumed < len(samples):
            index = position * 100 // rate
            boundary = math.ceil((index + 1) * rate / 100)
            take = min(boundary - position, len(samples) - consumed)
            part = samples[consumed:consumed + take].astype(np.float64)
            energy[index] += np.sum(part * part)
            counts[index] += part.size
            peaks[index] = max(peaks[index], float(np.max(np.abs(part))))
            position += take
            consumed += take
    if carry:
        raise AnalysisError("decode_failed", "Incomplete PCM sample frame")
    if position == 0:
        raise AnalysisError("decode_failed", "Decoder returned no audio")
    length = math.ceil(position * 100 / rate)
    return energy[:length], counts[:length], peaks[:length], position / rate


def _spectrum(output, rate, channels, start, duration, budget, np, librosa):
    size = os.fstat(output.fileno()).st_size
    if size > WORK_BYTES or size % (channels * 4):
        raise AnalysisError("resource_limit", "Spectral PCM exceeded its bounded buffer")
    samples = size // (channels * 4)
    if samples == 0:
        raise AnalysisError("decode_failed", "No spectral samples")
    hop, window = 256, 1024
    # Keep every context on the same source-file FFT grid, including block seams.
    first_center = (-round(start * rate)) % hop
    centers = np.arange(first_center, samples, hop)
    n = len(centers)
    bands = np.zeros((n, 3), dtype=np.float64)
    centroid = np.zeros(n, dtype=np.float64)
    mel = np.zeros((128, n), dtype=np.float32)
    frequencies = np.fft.rfftfreq(window, 1 / rate)
    filters = librosa.filters.mel(sr=rate, n_fft=window, n_mels=128)
    hann = np.hanning(window + 1)[:-1]
    masks = [(frequencies >= low) & (frequencies < high if i < 2 else frequencies <= high)
             for i, (low, high) in enumerate([(20, 250), (250, 2000), (2000, rate / 2)])]
    for offset in range(0, n, 64):
        budget.check()
        at = centers[offset:offset + 64]
        indices = at[:, None] + np.arange(window)[None, :] - window // 2
        valid = (indices >= 0) & (indices < samples)
        first = max(0, int(indices.min()))
        last = min(samples, int(indices.max()) + 1)
        output.seek(first * channels * 4)
        raw = output.read((last - first) * channels * 4)
        pcm = np.frombuffer(raw, dtype="<f4").reshape(-1, channels)
        frames = np.array(pcm[np.clip(indices - first, 0, len(pcm) - 1)], dtype=np.float64)
        if not np.isfinite(frames).all():
            raise AnalysisError("decode_failed", "Decoded PCM contains non-finite samples")
        frames *= valid[:, :, None]
        magnitude = np.abs(np.fft.rfft(frames * hann[None, :, None], axis=1))
        power = np.mean(magnitude * magnitude, axis=2)
        average_magnitude = np.mean(magnitude, axis=2)
        total = average_magnitude.sum(axis=1)
        centroid[offset:offset + len(at)] = np.divide(average_magnitude @ frequencies, total,
                                                    out=np.zeros(len(at)), where=total > 0)
        for i, mask in enumerate(masks):
            bands[offset:offset + len(at), i] = power[:, mask].sum(axis=1)
        mel[:, offset:offset + len(at)] = filters @ power.T
    del pcm
    if not np.isfinite(mel).all():
        raise AnalysisError("decode_failed", "Spectral measurements overflowed")
    # Fixed reference/absolute floor, rather than a file/page-dependent max.
    logmel = 10 * np.log10(np.maximum(mel, 1e-10))
    flux = librosa.onset.onset_strength(S=logmel, sr=rate, hop_length=hop, center=False,
                                       lag=1, max_size=1)
    times = start + centers / rate
    budget.check()
    onset_frames = np.array([], dtype=int)
    beat_times = np.array([], dtype=float)
    bpm = None
    if np.any(flux > 0):
        onset_frames = librosa.onset.onset_detect(onset_envelope=flux, sr=rate, hop_length=hop,
                                                units="frames", normalize=True)
        budget.check()
        if len(onset_frames) >= 2:
            # A single context autocorrelation avoids the large per-frame tempogram.
            lags = np.arange(max(1, math.ceil(60 * rate / hop / 240)),
                             min(len(flux), math.floor(60 * rate / hop / 40) + 1))
            if len(lags):
                autocorrelation = librosa.autocorrelate(np.maximum(flux - flux.mean(), 0),
                                                       max_size=int(lags[-1]) + 1)
                candidates = 60 * rate / hop / lags
                prior = np.exp(-0.5 * np.log2(candidates / 120) ** 2)
                estimated = float(candidates[np.argmax(autocorrelation[lags] * prior)])
                tempo, relative = librosa.beat.beat_track(onset_envelope=flux, sr=rate,
                                                        hop_length=hop, bpm=estimated, units="time")
                if len(relative):
                    bpm = float(np.asarray(tempo).ravel()[0])
                    beat_times = start + first_center / rate + relative
    budget.check()
    onsets = [OnsetEvent(time_s=float(times[i]), strength=float(flux[i])) for i in onset_frames]
    return times, bands, centroid, flux, onsets, beat_times.tolist(), bpm


def _loudness(source, core_start, core_end, binary, budget):
    scope = "source_file" if core_start == 0 and source.duration_reported_s <= BLOCK_SECONDS else "source_block"
    result = LoudnessRegion(start_s=core_start, end_s=core_end, scope=scope)
    args = _decode_args(binary, source.path, core_start, core_end - core_start)
    args[-5:] = ["-af", "loudnorm=print_format=json", "-f", "null", "-"]
    args[3] = "info"
    # The input measurements are retained; filtered output is discarded.
    try:
        with _process(args, budget, output=subprocess.DEVNULL) as process:
            process.wait(timeout=budget.remaining)
            process.stderr.seek(0)
            log = process.stderr.read(1024 * 1024).decode("utf-8", errors="replace")
        raw, _ = json.JSONDecoder().raw_decode(log[log.rfind("{"):])
        for key, field in [("input_i", "integrated_lufs"), ("input_lra", "loudness_range_lu"), ("input_tp", "true_peak_dbtp")]:
            value = float(raw[key])
            if math.isnan(value) or value == math.inf:
                raise ValueError("Invalid loudness measurement")
            setattr(result, field, value if math.isfinite(value) else None)
    except (AnalysisError, KeyError, ValueError, subprocess.TimeoutExpired) as exc:
        if isinstance(exc, AnalysisError) and exc.code in {"analysis_timeout", "resource_limit"}:
            raise
        result.error = "Loudness measurement failed; no value was substituted"
    return result


@dataclass
class _Block:
    start: float
    end: float
    context_start: float
    context_end: float
    energy: object
    counts: object
    peaks: object
    times: object
    bands: object
    centroid: object
    flux: object
    onsets: list
    beats: list
    rhythm: RhythmEstimate
    loudness: LoudnessRegion
    decoded_end: float | None

    @property
    def nbytes(self):
        return sum(value.nbytes for value in (self.energy, self.counts, self.peaks,
                                              self.times, self.bands, self.centroid, self.flux))


def _compute_block(source, index, identity, binary, budget, np, librosa):
    core_start = index * BLOCK_SECONDS
    core_end = min(core_start + BLOCK_SECONDS, source.duration_reported_s)
    context_start = max(0, core_start - CONTEXT_SECONDS)
    context_end = min(source.duration_reported_s, core_end + CONTEXT_SECONDS)
    _unchanged(identity)
    with _process(_decode_args(binary, source.path, context_start, context_end - context_start), budget) as process:
        energy, counts, peaks, decoded = _signal_bins(process.stdout, source.sample_rate,
                                                     source.channels, context_end - context_start, budget)
    _unchanged(identity)
    actual_end = context_start + decoded
    core_end = min(core_end, actual_end)
    with tempfile.TemporaryFile() as output:
        with _process(_decode_args(binary, source.path, context_start, context_end - context_start,
                                   min(22050, source.sample_rate)), budget, output=output):
            pass
        _unchanged(identity)
        times, bands, centroid, flux, onsets, beats, bpm = _spectrum(
            output, min(22050, source.sample_rate), source.channels, context_start, decoded,
            budget, np, librosa)
    _unchanged(identity)
    loudness = _loudness(source, core_start, core_end, binary, budget)
    _unchanged(identity)
    return _Block(core_start, core_end, context_start, actual_end, energy, counts, peaks,
                  times, bands, centroid, flux,
                  [event for event in onsets if core_start <= event.time_s < core_end],
                  [instant for instant in beats if core_start <= instant < core_end],
                  RhythmEstimate(start_s=context_start, end_s=actual_end, bpm=bpm), loudness,
                  actual_end if context_end == source.duration_reported_s else None)


def _cached(key):
    with _CACHE_LOCK:
        now = time.monotonic()
        for old in list(_CACHE):
            if now - _CACHE[old][0] >= CACHE_TTL:
                del _CACHE[old]
        if key in _CACHE:
            entry = _CACHE.pop(key)
            _CACHE[key] = entry
            return entry[1]
    return None


def _store(key, block):
    with _CACHE_LOCK:
        _CACHE[key] = (time.monotonic(), block)
        while len(_CACHE) > 4 or sum(entry[1].nbytes for entry in _CACHE.values()) > CACHE_BYTES:
            _CACHE.popitem(last=False)


def _db(value, power=False):
    return (10 if power else 20) * math.log10(value) if value > 0 else None


def _native(block, start, end, rate):
    # Requests align to the 10 ms base grid, except the actual end of file.
    first = max(0, round((start - block.context_start) * 100))
    last = min(len(block.counts), math.ceil((end - block.context_start) * 100 - 1e-8))
    return float(block.energy[first:last].sum()), int(block.counts[first:last].sum()), float(block.peaks[first:last].max(initial=0))


def _row(start, end, blocks, rate, previous):
    import numpy as np
    energy, counts, peak = 0.0, 0, 0.0
    spectral = []
    for block in blocks:
        lo, hi = max(start, block.start), min(end, block.end)
        if hi <= lo:
            continue
        power, count, maximum = _native(block, lo, hi, rate)
        energy += power
        counts += count
        peak = max(peak, maximum)
        mask = (block.times >= lo - 1e-9) & (block.times < hi - 1e-9)
        indices = np.flatnonzero(mask)
        if len(indices) == 0:
            indices = np.array([np.argmin(np.abs(block.times - (lo + hi) / 2))])
        spectral.append((block, indices))
    rms = _db(energy / counts, power=True) if counts else None
    all_bands = np.concatenate([block.bands[indices] for block, indices in spectral]) if spectral else np.zeros((1, 3))
    band = all_bands.mean(axis=0)
    total = float(band.sum())
    ratios = [float(value / total) for value in band] if total > 0 else [None] * 3
    center = float(np.concatenate([block.centroid[indices] for block, indices in spectral]).mean()) if total > 0 else None
    flux = max((float(block.flux[indices].max()) for block, indices in spectral), default=0.0)
    delta = rms - previous if rms is not None and previous is not None else None
    row = (start, end, rms, _db(peak), *ratios, center, flux, delta, rms is None or rms <= -60)
    return row, energy, counts, peak


def _regions(blocks, start, end):
    """Use the context to qualify a silence before clipping it to the page."""
    intervals = []
    significant = []
    for block in blocks:
        run = None
        for i, (energy, count) in enumerate(zip(block.energy, block.counts)):
            a = block.context_start + i / 100
            b = min(a + 0.01, block.context_end)
            quiet = count == 0 or energy / count <= 1e-6
            if quiet and run is None:
                run = a
            if not quiet:
                if run is not None and a - run >= 0.3 - 1e-8:
                    intervals.append((run, a))
                run = None
                if a < end and b > start:
                    significant.append((max(a, start), min(b, end)))
        if run is not None and block.context_end - run >= 0.3 - 1e-8:
            intervals.append((run, block.context_end))
    clipped = sorted((max(a, start), min(b, end)) for a, b in intervals if a < end and b > start)
    merged = []
    for a, b in clipped:
        if merged and a <= merged[-1][1] + 1e-8:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return [TimeRegion(start_s=round(a, 9), end_s=round(b, 9)) for a, b in merged], (
        min(a for a, _ in significant) if significant else None), (
        max(b for _, b in significant) if significant else None)


def _result(request, source, analysis_id, values, blocks, end, versions):
    start = values[0][0][0] if values else min(end, request.start_ms / 1000 + request.offset * request.resolution_ms / 1000)
    covered_end = values[-1][0][1] if values else start
    relevant = [b for b in blocks if b.start < covered_end and b.end > start]
    onsets = [event for b in relevant for event in b.onsets if start <= event.time_s < covered_end]
    beats = [instant for b in relevant for instant in b.beats if start <= instant < covered_end]
    silence, first, last = _regions(relevant, start, covered_end)
    energy = sum(v[1] for v in values)
    count = sum(v[2] for v in values)
    peak = max((v[3] for v in values), default=0)
    total = max(0, math.ceil((end - request.start_ms / 1000) * 1000 / request.resolution_ms - 1e-8))
    complete = request.offset + len(values) >= total
    errors = {f"loudness:{b.start:g}": b.loudness.error for b in relevant if b.loudness.error}
    sr = min(22050, source.sample_rate)
    return AudioAnalysisResult(
        ok=True, status="partial" if errors else "ok", analysis_id=analysis_id, source=source,
        summary=AudioSummary(start_s=start, end_s=covered_end, rms_dbfs=_db(energy / count, True) if count else None,
                             peak_dbfs=_db(peak), silence_regions=silence,
                             first_significant_audio_s=first, last_significant_audio_s=last,
                             onset_count=len(onsets), beat_count=len(beats), rhythm=[b.rhythm for b in relevant]),
        loudness_regions=[b.loudness for b in relevant],
        timeline=AudioTimeline(rows=[v[0] for v in values], resolution_ms=request.resolution_ms,
                               total_frames=total, offset=request.offset, complete=complete,
                               next_offset=None if complete else request.offset + len(values),
                               covered_start_s=start, covered_end_s=covered_end, max_response_bytes=MAX_RESPONSE_BYTES),
        events=AudioEvents(onsets=onsets, beats=beats), versions=versions, errors=errors,
        unavailable_fields=["rhythm.confidence"],
        warnings=["Onsets and beats are estimates; output resolution does not set detection accuracy.",
                  "Source-file times exclude QLab trims, rate, loops, effects and pre-wait."],
        analysis_parameters=dict(algorithm_version=ALGORITHM_VERSION, analysis_sample_rate=sr,
                                 fft_window_samples=1024, fft_hop_samples=256,
                                 fft_window_ms=1024000 / sr, fft_hop_ms=256000 / sr,
                                 fft_window="periodic Hann; centered, zero padding at file edges",
                                 base_resolution_ms=10, silence_threshold_dbfs=-60,
                                 silence_min_duration_ms=300, channel_energy="mean power; peak maximum across channels",
                                 bands_hz=[[20, 250], [250, 2000], [2000, sr / 2]],
                                 onset_strength="maximum positive mel-band dB change per output row; fixed reference, no page normalization",
                                 tempo_estimator="context onset autocorrelation, 40–240 BPM, log2 prior centered on 120 BPM",
                                 block_seconds=BLOCK_SECONDS, context_seconds=CONTEXT_SECONDS,
                                 identity="stat fingerprint plus algorithm version; not a content digest"))


def analyze_audio_file(request: AudioAnalysisRequest, cancelled=None) -> AudioAnalysisResult:
    budget = _Budget(cancelled)
    locked = False
    try:
        budget.check()
        identity = _identity(request.path)
        np, librosa, binary, probe = _dependencies()
        analysis_id = hashlib.sha256(json.dumps([identity, ALGORITHM_VERSION], sort_keys=True).encode()).hexdigest()
        if request.expected_analysis_id is not None and request.expected_analysis_id != analysis_id:
            raise AnalysisError("source_changed", "Analysis identity changed; request a new first page")
        source, ffversion = _probe(identity, probe, budget)
        decoder_version = _executable_version(binary, budget)
        _unchanged(identity)
        end = source.duration_reported_s if request.end_ms is None else request.end_ms / 1000
        if request.start_ms / 1000 >= source.duration_reported_s or end > source.duration_reported_s + 1e-6:
            raise AnalysisError("invalid_request", "Requested interval is outside the audio duration")
        blocks = {}

        def get(index):
            nonlocal locked, end
            if index in blocks:
                return blocks[index]
            budget.check()
            block = _cached((analysis_id, index))
            if block is None:
                if not locked:
                    locked = _CALC_LOCK.acquire(blocking=False)
                    if not locked:
                        raise AnalysisError("analysis_busy", "Another audio calculation is in progress; try again later")
                _unchanged(identity)
                block = _compute_block(source, index, identity, binary, budget, np, librosa)
                _store((analysis_id, index), block)
            blocks[index] = block
            if block.decoded_end is not None:
                source.duration_decoded_s = block.decoded_end
                end = min(end, block.decoded_end)
            return block

        step = request.resolution_ms / 1000
        origin = request.start_ms / 1000
        values = []
        previous = None
        stopped_for_budget = False
        first_index = request.offset
        # A continuation computes its predecessor at this same resolution.
        begin = max(0, first_index - 1) if first_index else 0
        for i in range(begin, first_index + request.max_frames):
            a = origin + i * step
            if a >= end - 1e-9:
                break
            b = min(origin + (i + 1) * step, end)
            indices = range(math.floor(a / BLOCK_SECONDS), math.floor((b - 1e-9) / BLOCK_SECONDS) + 1)
            try:
                if values and budget.remaining < 1 and any(index not in blocks for index in indices):
                    stopped_for_budget = True
                    break
                needed = [get(index) for index in indices]
            except AnalysisError as exc:
                if exc.code == "analysis_timeout" and values:
                    stopped_for_budget = True
                    break
                raise
            b = min(b, end)
            if b <= a:
                break
            value = _row(a, b, needed, source.sample_rate, previous)
            previous = value[0][2]
            if i >= first_index:
                values.append(value)
                # Stop before decoding another block when this page already fills its budget.
                if len(values) % 128 == 0:
                    preview = _result(request, source, analysis_id, values, list(blocks.values()), end, {})
                    if len(preview.model_dump_json().encode()) >= MAX_RESPONSE_BYTES - 512:
                        break
        versions = dict(algorithm=ALGORITHM_VERSION, numpy=np.__version__, librosa=librosa.__version__, ffprobe=ffversion, ffmpeg=decoder_version)
        result = _result(request, source, analysis_id, values, list(blocks.values()), end, versions)
        if len(result.model_dump_json().encode()) > MAX_RESPONSE_BYTES:
            low, high = 0, len(values)
            while low < high:
                midpoint = (low + high + 1) // 2
                candidate = _result(request, source, analysis_id, values[:midpoint], list(blocks.values()), end, versions)
                if len(candidate.model_dump_json().encode()) <= MAX_RESPONSE_BYTES:
                    low = midpoint
                else:
                    high = midpoint - 1
            if low == 0:
                raise AnalysisError("resource_limit", "Response metadata or a single frame exceeds the byte budget")
            result = _result(request, source, analysis_id, values[:low], list(blocks.values()), end, versions)
        if stopped_for_budget:
            result.status = "partial"
            result.errors["time_budget"] = "Stopped after completed work; continue with next_offset"
            if len(result.model_dump_json().encode()) > MAX_RESPONSE_BYTES:
                raise AnalysisError("resource_limit", "Response exceeded the byte budget")
        _unchanged(identity)
        return result
    except ImportError:
        return AudioAnalysisResult(ok=False, status="error", error_code="dependency_missing",
                                   message="Install the optional audio extra in the MCP environment")
    except AnalysisError as exc:
        return AudioAnalysisResult(ok=False, status="error", error_code=exc.code, message=str(exc))
    except (OSError, ValueError, OverflowError) as exc:
        return AudioAnalysisResult(ok=False, status="error", error_code="decode_failed", message=f"Audio analysis failed: {type(exc).__name__}")
    finally:
        if locked:
            _CALC_LOCK.release()
