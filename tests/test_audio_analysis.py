"""Audio analysis contracts and measured signal regressions."""
import importlib
import io
import os
import shutil
import sys
import threading
import time
import wave

import pytest
from pydantic import ValidationError


def models():
    return importlib.import_module("qlab_mcp.audio_analysis_models")


@pytest.mark.parametrize("args", [
    {"resolution_ms": True}, {"resolution_ms": "100"}, {"resolution_ms": 30},
    {"offset": "0"}, {"offset": -1}, {"max_frames": 5001},
    {"start_ms": 11}, {"start_ms": True}, {"end_ms": 9},
    {"start_ms": 100, "end_ms": 100}, {"path": "relative.wav"},
    {"path": "https://example.com/audio.wav"}, {"path": "/tmp/a\x00.wav"},
    {"unexpected": 1},
])
def test_request_rejects_invalid_inputs(args):
    request = models().AudioAnalysisRequest
    with pytest.raises(ValidationError):
        request.model_validate({"path": "/tmp/source.wav", **args})


def test_request_keeps_long_ranges_and_defaults():
    request = models().AudioAnalysisRequest(path="/tmp/source.wav", end_ms=1801000)
    assert request.resolution_ms == 100
    assert request.max_frames == 5000
    assert request.end_ms == 1801000


def test_json_response_rejects_nonfinite_values():
    result = models().AudioAnalysisResult
    with pytest.raises(ValidationError):
        result.model_validate({"ok": True, "status": "ok", "summary": {
            "scope": "analyzed_range", "start_s": 0, "end_s": 1,
            "rms_dbfs": float("nan"), "peak_dbfs": None,
        }})


@pytest.fixture
def backend(monkeypatch):
    module = importlib.import_module("qlab_mcp.audio_analysis")
    module._CACHE.clear()
    yield module
    module._CACHE.clear()


@pytest.fixture
def audio_backend(backend):
    pytest.importorskip("numpy")
    pytest.importorskip("librosa")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("Real audio integration requires FFmpeg and ffprobe in PATH")
    return backend


def write_wave(path, samples, rate=48000):
    import numpy as np
    samples = np.asarray(samples)
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    pcm = (np.clip(samples, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels)
        output.setsampwidth(2)
        output.setframerate(rate)
        output.writeframes(pcm.tobytes())
    return path


def analyze(backend, path, **args):
    request = models().AudioAnalysisRequest(path=str(path), **args)
    result = backend.analyze_audio_file(request)
    assert result.ok, result.model_dump()
    return result


@pytest.fixture
def tones(tmp_path):
    import numpy as np
    rate = 48000
    t = np.arange(rate) / rate
    samples = np.concatenate([np.zeros(rate),
        0.5 * np.sin(2 * np.pi * 100 * t),
        0.5 * np.sin(2 * np.pi * 1000 * t),
        0.5 * np.sin(2 * np.pi * 4000 * t), np.zeros(rate)])
    return write_wave(tmp_path / "tones.wav", samples)


def test_original_levels_bands_and_silences(audio_backend, tones):
    result = analyze(audio_backend, tones)
    assert result.source.duration_decoded_s == pytest.approx(5, abs=1e-5)
    assert result.source.sample_rate == 48000
    assert result.source.bit_depth == 16
    assert len(result.timeline.rows) == 50
    for index, band in [(15, 4), (25, 5), (35, 6)]:
        row = result.timeline.rows[index]
        assert row[2] == pytest.approx(-9.0309, abs=0.1)
        assert row[3] == pytest.approx(-6.0206, abs=0.1)
        assert row[band] > 0.95
    assert result.timeline.rows[0][2] is None
    assert result.timeline.rows[0][10] is True
    assert [(r.start_s, r.end_s) for r in result.summary.silence_regions] == [(0, 1), (4, 5)]
    assert result.loudness_regions[0].scope == "source_file"
    assert result.loudness_regions[0].integrated_lufs is not None


def test_stereo_antiphase_does_not_cancel_energy(audio_backend, tmp_path):
    import numpy as np
    t = np.arange(48000) / 48000
    signal = 0.5 * np.sin(2 * np.pi * 1000 * t)
    path = write_wave(tmp_path / "antiphase.wav", np.column_stack([signal, -signal]))
    result = analyze(audio_backend, path)
    assert result.summary.rms_dbfs == pytest.approx(-9.0309, abs=0.1)
    assert result.timeline.rows[5][5] > 0.95
    assert result.summary.silence_regions == []


def test_last_fractional_frame_and_digital_silence(audio_backend, tmp_path):
    import numpy as np
    path = write_wave(tmp_path / "silent.wav", np.zeros(11280))
    result = analyze(audio_backend, path)
    assert len(result.timeline.rows) == 3
    assert result.timeline.rows[-1][0:2] == pytest.approx((0.2, 0.235))
    assert result.summary.rms_dbfs is None
    assert result.events.onsets == [] and result.events.beats == []
    assert result.summary.rhythm[0].bpm is None
    assert all(row[4:8] == (None, None, None, None) for row in result.timeline.rows)
    result.model_dump_json()  # JSON, including silence, has no non-finite numbers.


def test_attacks_keep_subwindow_times(audio_backend, tmp_path):
    import numpy as np
    signal = np.zeros(3 * 48000)
    signal[round(1.037 * 48000):round(1.037 * 48000) + 100] = 0.9
    signal[round(2.087 * 48000):round(2.087 * 48000) + 100] = 0.9
    result = analyze(audio_backend, write_wave(tmp_path / "hits.wav", signal))
    detected = [event.time_s for event in result.events.onsets]
    for expected in [1.037, 2.087]:
        nearest = min(detected, key=lambda t: abs(t - expected))
        assert abs(nearest - expected) < 0.05
        assert nearest != round(nearest, 1)


def test_beats_have_local_context_and_half_second_spacing(audio_backend, tmp_path):
    import numpy as np
    signal = np.zeros(12 * 48000)
    for instant in np.arange(0.5, 11.6, 0.5):
        signal[int(instant * 48000):int(instant * 48000) + 300] = 0.8
    result = analyze(audio_backend, write_wave(tmp_path / "clicks.wav", signal))
    assert len(result.events.beats) > 10
    assert np.median(np.diff(result.events.beats)) == pytest.approx(0.5, abs=0.05)
    assert result.summary.rhythm[0].confidence is None
    assert result.summary.rhythm[0].scope == "analysis_context"


def test_paging_preserves_values_events_and_previous_delta(audio_backend, tones):
    full = analyze(audio_backend, tones)
    offset = 0
    rows, onsets, beats = [], [], []
    while True:
        page = analyze(audio_backend, tones, offset=offset, max_frames=7,
                       expected_analysis_id=full.analysis_id)
        rows.extend(page.timeline.rows)
        onsets.extend(page.events.onsets)
        beats.extend(page.events.beats)
        if page.timeline.complete:
            break
        assert page.timeline.next_offset > offset
        offset = page.timeline.next_offset
    assert rows == full.timeline.rows
    assert onsets == full.events.onsets and beats == full.events.beats
    empty = analyze(audio_backend, tones, offset=50)
    assert empty.timeline.rows == [] and empty.timeline.complete


def test_byte_budget_paginates_the_complete_result(audio_backend, tones, monkeypatch):
    monkeypatch.setattr(audio_backend, "MAX_RESPONSE_BYTES", 5000)
    page = analyze(audio_backend, tones)
    assert not page.timeline.complete
    assert page.timeline.next_offset is not None
    assert len(page.model_dump_json().encode()) <= 5000


def test_cache_hit_and_source_change(audio_backend, tones, monkeypatch):
    first = analyze(audio_backend, tones)
    original = audio_backend._compute_block
    monkeypatch.setattr(audio_backend, "_compute_block", lambda *args: pytest.fail("cache hit decoded again"))
    second = analyze(audio_backend, tones, start_ms=1000, end_ms=2000, resolution_ms=50)
    assert second.analysis_id == first.analysis_id
    assert second.timeline.rows[2][2] == pytest.approx(-9.0309, abs=0.1)
    stat = tones.stat()
    os.utime(tones, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    changed = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(
        path=str(tones), expected_analysis_id=first.analysis_id))
    assert not changed.ok and changed.error_code == "source_changed"
    monkeypatch.setattr(audio_backend, "_compute_block", original)


def test_dependency_missing_without_process(audio_backend, tones, monkeypatch):
    monkeypatch.setenv("PATH", "")
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(tones)))
    assert not result.ok and result.error_code == "dependency_missing"


def test_invalid_files_and_intervals(audio_backend, tmp_path, tones):
    for path, code in [(tmp_path / "missing.wav", "file_not_found"),
                       (tmp_path, "unsupported_media")]:
        result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(path)))
        assert not result.ok and result.error_code == code
    bad = tmp_path / "broken.wav"
    bad.write_bytes(b"not audio")
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(bad)))
    assert not result.ok and result.error_code == "unsupported_media"
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(tones), end_ms=6000))
    assert not result.ok and result.error_code == "invalid_request"


def test_cancelled_analysis_and_native_nonfinite_rejected(audio_backend, tones):
    import numpy as np
    cancelled = threading.Event()
    cancelled.set()
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(tones)), cancelled)
    assert not result.ok and result.error_code == "analysis_timeout"
    with pytest.raises(audio_backend.AnalysisError, match="non-finite"):
        audio_backend._signal_bins(io.BytesIO(np.array([float("nan")], dtype="<f4").tobytes()),
                                   48000, 1, 0.01, audio_backend._Budget())


def test_process_timeout_and_cancel_cleanup(backend):
    for cancel in [False, True]:
        event = threading.Event()
        budget = backend._Budget(event, seconds=0.2 if not cancel else 10)
        if cancel:
            timer = threading.Timer(0.2, event.set)
            timer.start()
        started = time.monotonic()
        with pytest.raises(backend.AnalysisError) as error:
            with backend._process([sys.executable, "-c", "import time; time.sleep(30)"], budget) as process:
                process.stdout.read()
        assert error.value.code == "analysis_timeout"
        assert process.poll() is not None
        assert time.monotonic() - started < 3


def test_busy_does_not_start_another_calculation(audio_backend, tones):
    with audio_backend._CALC_LOCK:
        result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(tones)))
    assert not result.ok and result.error_code == "analysis_busy"


def test_mcp_schema_and_call_without_osc(monkeypatch):
    import asyncio
    from fastmcp import Client
    import qlab_mcp.server as server
    import qlab_mcp.audio_analysis as module
    monkeypatch.setattr(server, "_reader", lambda: pytest.fail("No OSC from audio analysis"))
    observed = []
    def fake(request, cancelled=None):
        observed.append(request)
        return models().AudioAnalysisResult(ok=False, status="error", error_code="file_not_found", message="fixture")
    monkeypatch.setattr(module, "analyze_audio_file", fake)
    async def run():
        async with Client(server.mcp) as client:
            tools = {tool.name: tool for tool in await client.list_tools()}
            tool = tools["qlab_analyze_audio_file"]
            assert tool.annotations.readOnlyHint and not tool.annotations.destructiveHint
            assert "workspace_id" not in tool.inputSchema["properties"]
            assert tool.inputSchema["properties"]["resolution_ms"]["default"] == 100
            assert (await server.mcp.get_tool(tool.name)).timeout == 300
            result = await client.call_tool(tool.name, {"path": "/tmp/test.wav"})
            assert result.structured_content["error_code"] == "file_not_found"
            for args in [{"start_ms": True}, {"resolution_ms": "100"}, {"unexpected": 1}]:
                with pytest.raises(Exception):
                    await client.call_tool(tool.name, {"path": "/tmp/test.wav", **args})
    asyncio.run(run())
    assert len(observed) == 1


def test_import_does_not_load_optional_audio_dependencies():
    import subprocess
    result = subprocess.run([sys.executable, "-c", "import sys; import qlab_mcp.server; "
                             "assert 'numpy' not in sys.modules; assert 'librosa' not in sys.modules"],
                            env={**os.environ, "PYTHONPATH": "src"}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_process_decoder_failure_is_not_silent(backend):
    with pytest.raises(backend.AnalysisError) as error:
        with backend._process([sys.executable, "-c", "raise SystemExit(3)"], backend._Budget()) as process:
            process.stdout.read()
    assert error.value.code == "decode_failed"


def test_native_read_timeout_keeps_timeout_code(backend):
    pytest.importorskip("numpy")
    with pytest.raises(backend.AnalysisError) as error:
        with backend._process([sys.executable, "-c", "import time; time.sleep(30)"],
                              backend._Budget(seconds=0.1)) as process:
            backend._signal_bins(process.stdout, 48000, 1, 1, backend._Budget())
    assert error.value.code == "analysis_timeout"


def test_cache_ttl_and_lru(backend, monkeypatch):
    from types import SimpleNamespace
    block = SimpleNamespace(nbytes=10)
    now = [100.0]
    monkeypatch.setattr(backend.time, "monotonic", lambda: now[0])
    for i in range(4):
        backend._store(("a", i), block)
    assert backend._cached(("a", 0)) is block
    backend._store(("a", 4), block)
    assert backend._cached(("a", 1)) is None
    now[0] += 601
    assert backend._cached(("a", 0)) is None
    assert not backend._CACHE


def test_loudness_failure_is_visible_partial(audio_backend, tones, monkeypatch):
    def failed(source, start, end, *args):
        return models().LoudnessRegion(start_s=start, end_s=end, scope="source_file", error="fixture error")
    monkeypatch.setattr(audio_backend, "_loudness", failed)
    result = analyze(audio_backend, tones)
    assert result.status == "partial" and result.timeline.complete
    assert result.errors == {"loudness:0": "fixture error"}
    assert result.loudness_regions[0].integrated_lufs is None


def test_source_change_during_compute_discards_result(audio_backend, tones, monkeypatch):
    original = audio_backend._compute_block
    def changed(*args):
        result = original(*args)
        info = tones.stat()
        os.utime(tones, ns=(info.st_atime_ns, info.st_mtime_ns + 1000000))
        return result
    monkeypatch.setattr(audio_backend, "_compute_block", changed)
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(tones)))
    assert result.error_code == "source_changed"
    assert result.timeline is None


def test_mcp_cancellation_waits_for_worker_cleanup(monkeypatch):
    import asyncio
    import qlab_mcp.server as server
    import qlab_mcp.audio_analysis as module
    started, finished = threading.Event(), threading.Event()
    def work(request, cancelled):
        started.set()
        assert cancelled.wait(2)
        time.sleep(0.05)
        finished.set()
        return models().AudioAnalysisResult(ok=False, status="error", error_code="analysis_timeout")
    monkeypatch.setattr(module, "analyze_audio_file", work)
    async def run():
        task = asyncio.create_task(server.qlab_analyze_audio_file(path="/tmp/test.wav"))
        await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert finished.is_set()
    asyncio.run(run())


@pytest.mark.parametrize("minutes", [5, 15, 30])
def test_long_files_decode_only_requested_canonical_blocks(audio_backend, tmp_path, monkeypatch, minutes):
    # Streaming fixture: no full-file PCM array, including the 30:01 boundary.
    path = tmp_path / f"{minutes}min.wav"
    duration = minutes * 60 + (1 if minutes == 30 else 0)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        second = b"\0" * 16000
        for _ in range(duration):
            output.writeframesraw(second)
    computed = []
    original = audio_backend._compute_block
    def tracked(source, index, *args):
        computed.append(index)
        return original(source, index, *args)
    monkeypatch.setattr(audio_backend, "_compute_block", tracked)
    first = analyze(audio_backend, path, max_frames=3)
    assert computed == [0]
    assert first.timeline.total_frames == duration * 10
    assert first.timeline.next_offset == 3
    if minutes > 5:
        at = min(1500000, (minutes * 60 - 10) * 1000)
        late = analyze(audio_backend, path, start_ms=at, end_ms=at + 1000)
        assert computed == [0, at // 300000]
        assert late.timeline.rows[0][0] == at / 1000
        assert late.timeline.complete and len(late.timeline.rows) == 10
    if minutes == 30:
        end = analyze(audio_backend, path, start_ms=1800000)
        assert end.timeline.total_frames == 10 and len(end.timeline.rows) == 10
        assert end.source.duration_decoded_s == 1801


def test_byte_limit_prevents_decoding_unreturned_blocks(audio_backend, tmp_path, monkeypatch):
    import numpy as np
    path = write_wave(tmp_path / "long.wav", np.zeros(301 * 8000), rate=8000)
    monkeypatch.setattr(audio_backend, "MAX_RESPONSE_BYTES", 6000)
    seen = []
    original = audio_backend._compute_block
    def tracked(source, index, *args):
        seen.append(index)
        return original(source, index, *args)
    monkeypatch.setattr(audio_backend, "_compute_block", tracked)
    result = analyze(audio_backend, path)
    assert seen == [0]
    assert not result.timeline.complete and result.timeline.next_offset < 3000
    assert len(result.model_dump_json().encode()) <= 6000


def test_rhythm_avoids_full_context_tempogram(audio_backend, tmp_path, monkeypatch):
    import numpy as np
    import librosa.beat
    monkeypatch.setattr(librosa.beat, "_tempo", lambda *a, **k: pytest.fail("unbounded context tempogram"))
    signal = np.zeros(4 * 48000)
    for instant in [0.5, 1, 1.5, 2, 2.5, 3]:
        signal[int(instant * 48000):int(instant * 48000) + 200] = 0.8
    result = analyze(audio_backend, write_wave(tmp_path / "rhythm.wav", signal))
    assert result.summary.rhythm[0].bpm is not None


def test_mp3_zero_seek_preserves_gapless_sample_count(audio_backend, tmp_path):
    import numpy as np
    import subprocess
    path = write_wave(tmp_path / "source.wav", 0.5 * np.sin(2 * np.pi * 440 * np.arange(48000) / 48000))
    compressed = tmp_path / "source.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(path),
                    "-c:a", "libmp3lame", str(compressed)], check=True)
    baseline = subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(compressed),
                               "-f", "f32le", "-c:a", "pcm_f32le", "pipe:1"], capture_output=True, check=True).stdout
    result = analyze(audio_backend, compressed)
    assert result.source.duration_decoded_s == len(baseline) / 4 / 48000


def test_zero_start_does_not_request_input_seek(backend):
    assert "-ss" not in backend._decode_args("ffmpeg", "/tmp/file.mp3", 0, 5)


@pytest.mark.parametrize("extension,codec", [("aiff", "pcm_s16be"), ("flac", "flac"),
                                              ("m4a", "aac"), ("ogg", "libvorbis")])
def test_supported_containers(audio_backend, tmp_path, extension, codec):
    import subprocess
    import numpy as np
    source = write_wave(tmp_path / "input.wav", 0.5 * np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000))
    target = tmp_path / f"output.{extension}"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(source),
                    "-c:a", codec, str(target)], check=True)
    result = analyze(audio_backend, target)
    assert result.source.channels == 1
    assert result.timeline.rows[5][5] > 0.95


def test_real_video_and_playlists_rejected(audio_backend, tmp_path):
    import subprocess
    movie = tmp_path / "movie.mp4"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-f", "lavfi", "-i",
                    "color=c=black:s=32x32:d=1", "-c:v", "mpeg4", str(movie)], check=True)
    playlist = tmp_path / "indirect.m3u8"
    playlist.write_text("#EXTM3U\n#EXTINF:1\nhttp://127.0.0.1:9/never.wav\n")
    for path in [movie, playlist]:
        result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(path)))
        assert result.error_code == "unsupported_media" and result.timeline is None


def test_mp3_seek_matches_full_decode_samples(audio_backend, tmp_path):
    import subprocess
    import numpy as np
    rate = 44100
    t = np.arange(20 * rate) / rate
    # Varying envelope makes an incorrect seek audible/numerically observable.
    signal = (0.25 + 0.2 * np.sin(2 * np.pi * 0.3 * t)) * np.sin(2 * np.pi * 997 * t)
    source = write_wave(tmp_path / "source.wav", signal, rate=rate)
    compressed = tmp_path / "seek.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(source),
                    "-c:a", "libmp3lame", "-q:a", "2", str(compressed)], check=True)
    full = subprocess.run(audio_backend._decode_args(shutil.which("ffmpeg"), str(compressed), 0, 20),
                          capture_output=True, check=True).stdout
    seek = subprocess.run(audio_backend._decode_args(shutil.which("ffmpeg"), str(compressed), 7, 2),
                          capture_output=True, check=True).stdout
    baseline = np.frombuffer(full, dtype="<f4")[7 * rate:9 * rate]
    observed = np.frombuffer(seek, dtype="<f4")
    assert len(observed) == len(baseline)
    # MP3's bit reservoir can differ at the seek boundary; the settled samples match.
    assert np.max(np.abs(observed[rate // 10:] - baseline[rate // 10:])) < 0.001


def test_multichannel_clipping_preserves_maximum_and_power(audio_backend, tmp_path):
    import numpy as np
    source = np.zeros((48000, 6))
    source[:, 0] = 1
    source[:, 5] = -1
    result = analyze(audio_backend, write_wave(tmp_path / "six.wav", source))
    assert result.source.channels == 6
    assert result.summary.peak_dbfs == pytest.approx(0, abs=0.001)
    assert result.summary.rms_dbfs == pytest.approx(10 * np.log10(2 / 6), abs=0.001)


def test_process_output_limit_is_checked_even_after_fast_exit(backend):
    import tempfile
    with tempfile.TemporaryFile() as output:
        with pytest.raises(backend.AnalysisError) as error:
            with backend._process([sys.executable, "-c", "import sys; sys.stdout.write('x'*10000)"],
                                  backend._Budget(), output=output, output_limit=100):
                pass
    assert error.value.code == "resource_limit"


def test_spectral_pcm_is_read_in_small_batches(audio_backend, tones, monkeypatch):
    import numpy as np
    monkeypatch.setattr(np, "memmap", lambda *a, **k: pytest.fail("full block mapping retains excessive resident PCM"))
    result = analyze(audio_backend, tones)
    assert result.timeline.complete


def test_one_attack_crossing_canonical_boundary_is_not_duplicated(audio_backend, tmp_path):
    import numpy as np
    rate = 22050
    samples = np.zeros(301 * rate)
    instant = round(300.012 * rate)
    samples[instant:instant + 100] = 0.9
    path = write_wave(tmp_path / "boundary.wav", samples, rate=rate)
    result = analyze(audio_backend, path, start_ms=299900, end_ms=300100)
    assert len(result.events.onsets) == 1, result.events.onsets
    assert abs(result.events.onsets[0].time_s - 300.012) < 0.05
    first = analyze(audio_backend, path, start_ms=299900, end_ms=300100, max_frames=1)
    second = analyze(audio_backend, path, start_ms=299900, end_ms=300100, offset=first.timeline.next_offset)
    assert first.events.onsets + second.events.onsets == result.events.onsets


def test_complete_mp3_loudness_scope_uses_real_coverage(audio_backend, tmp_path):
    import numpy as np
    import subprocess
    source = write_wave(tmp_path / "second.wav", 0.5 * np.sin(2 * np.pi * 1000 * np.arange(48000) / 48000))
    compressed = tmp_path / "second.mp3"
    subprocess.run([shutil.which("ffmpeg"), "-nostdin", "-v", "error", "-i", str(source),
                    "-c:a", "libmp3lame", str(compressed)], check=True)
    result = analyze(audio_backend, compressed)
    assert result.source.duration_reported_s > result.source.duration_decoded_s
    assert result.loudness_regions[0].scope == "source_file"
    assert result.loudness_regions[0].end_s == result.source.duration_decoded_s


def test_cached_reads_continue_while_calculation_lock_is_held(audio_backend, tones):
    first = analyze(audio_backend, tones)
    with audio_backend._CALC_LOCK:
        result = analyze(audio_backend, tones, max_frames=1, expected_analysis_id=first.analysis_id)
    assert len(result.timeline.rows) == 1


def test_unreadable_file_has_stable_error(backend, tmp_path, monkeypatch):
    path = tmp_path / "private.wav"
    path.write_bytes(b"not inspected")
    monkeypatch.setattr(backend.os, "access", lambda *args: False)
    result = backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(path)))
    assert result.error_code == "file_unreadable" and result.timeline is None


def test_base_environment_reports_missing_extra_without_loading_osc(tmp_path):
    import subprocess
    script = '''
import builtins
from qlab_mcp.audio_analysis import analyze_audio_file
from qlab_mcp.audio_analysis_models import AudioAnalysisRequest
original = builtins.__import__
def blocked(name, *args, **kwargs):
    if name.split('.')[0] in {'numpy', 'librosa'}: raise ImportError('optional extra absent')
    return original(name, *args, **kwargs)
builtins.__import__ = blocked
result = analyze_audio_file(AudioAnalysisRequest(path=__import__('sys').argv[1]))
assert result.error_code == 'dependency_missing', result
import qlab_mcp.server
assert qlab_mcp.server.mcp is not None
'''
    path = tmp_path / "source.wav"
    path.write_bytes(b"not decoded")
    result = subprocess.run([sys.executable, "-c", script, str(path)],
                            env={**os.environ, "PYTHONPATH": "src"}, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_shared_budget_returns_completed_block_with_continuation(audio_backend, tmp_path, monkeypatch):
    path = tmp_path / "budget.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1); output.setsampwidth(2); output.setframerate(8000)
        for _ in range(601):
            output.writeframesraw(b"\0" * 16000)
    original = audio_backend._compute_block
    def exhausted(source, index, *args):
        if index == 1:
            raise audio_backend.AnalysisError("analysis_timeout", "fixture exhausted shared budget")
        return original(source, index, *args)
    monkeypatch.setattr(audio_backend, "_compute_block", exhausted)
    result = analyze(audio_backend, path)
    assert result.status == "partial" and "time_budget" in result.errors
    assert result.timeline.next_offset == 3000
    assert result.timeline.covered_end_s == 300


@pytest.mark.parametrize("channels,rate", [(9, 48000), (1, 7999), (1, 192001)])
def test_probe_rejects_out_of_range_dimensions(audio_backend, tmp_path, channels, rate):
    path = tmp_path / "unsupported.wav"
    with wave.open(str(path), "wb") as output:
        output.setnchannels(channels); output.setsampwidth(2); output.setframerate(rate)
        output.writeframes(b"\0" * rate * channels * 2)
    result = audio_backend.analyze_audio_file(models().AudioAnalysisRequest(path=str(path)))
    assert result.error_code == "unsupported_media" and result.timeline is None


def test_audio_extra_is_locked_with_base_versions_preserved():
    import tomllib
    from pathlib import Path
    project = tomllib.loads(Path("pyproject.toml").read_text())
    lock = tomllib.loads(Path("uv.lock").read_text())
    package = next(item for item in lock["package"] if item["name"] == "qlab-mcp")
    assert set(item["name"] for item in package["optional-dependencies"]["audio"]) == {"numpy", "librosa"}
    assert package["version"] == project["project"]["version"] == "0.4.0"
    assert next(item for item in lock["package"] if item["name"] == "fastmcp")["version"] == "3.3.1"
