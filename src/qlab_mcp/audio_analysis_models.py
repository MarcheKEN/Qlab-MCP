"""Audio analysis schemas; importing these does not load audio dependencies."""
from __future__ import annotations

import os
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, StrictInt, StrictStr, field_validator, model_validator


COLUMNS = (
    "start_s", "end_s", "rms_dbfs", "peak_dbfs", "low_ratio", "mid_ratio",
    "high_ratio", "centroid_hz", "onset_strength", "delta_rms_db", "silent",
)
FrameRow = tuple[
    float, float, float | None, float | None, float | None, float | None,
    float | None, float | None, float, float | None, bool,
]
Resolution = Literal[10, 20, 50, 100, 250, 500, 1000]


class AudioModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class AudioAnalysisRequest(AudioModel):
    path: Annotated[StrictStr, Field(min_length=1)]
    start_ms: Annotated[StrictInt, Field(ge=0)] = 0
    end_ms: Annotated[StrictInt, Field(gt=0)] | None = None
    resolution_ms: Resolution = 100
    offset: Annotated[StrictInt, Field(ge=0)] = 0
    max_frames: Annotated[StrictInt, Field(ge=1, le=5000)] = 5000
    expected_analysis_id: Annotated[StrictStr, Field(min_length=1)] | None = None

    @field_validator("path")
    @classmethod
    def absolute_local_path(cls, value: str) -> str:
        if "\x00" in value or not os.path.isabs(value):
            raise ValueError("path must be an absolute local file path without NUL bytes")
        return value

    @field_validator("resolution_ms", mode="before")
    @classmethod
    def strict_resolution(cls, value: object) -> object:
        if type(value) is not int:
            raise ValueError("resolution_ms must be an integer")
        return value

    @model_validator(mode="after")
    def valid_interval(self) -> AudioAnalysisRequest:
        if self.start_ms % 10 or (self.end_ms is not None and self.end_ms % 10):
            raise ValueError("start_ms and end_ms must be multiples of 10")
        if self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ValueError("end_ms must be greater than start_ms")
        return self


class AudioSource(AudioModel):
    path: str
    fingerprint: dict[str, int | str]
    format: str
    codec: str
    channels: int
    channel_layout: str | None = None
    sample_rate: int
    bit_depth: int | None = None
    duration_reported_s: float
    duration_decoded_s: float | None = None


class TimeRegion(AudioModel):
    start_s: float
    end_s: float


class RhythmEstimate(TimeRegion):
    scope: Literal["analysis_context"] = "analysis_context"
    bpm: float | None = None
    confidence: float | None = None


class AudioSummary(TimeRegion):
    scope: Literal["analyzed_range"] = "analyzed_range"
    rms_dbfs: float | None
    peak_dbfs: float | None
    first_significant_audio_s: float | None = None
    last_significant_audio_s: float | None = None
    silence_regions: list[TimeRegion] = Field(default_factory=list)
    onset_count: int = 0
    beat_count: int = 0
    rhythm: list[RhythmEstimate] = Field(default_factory=list)


class LoudnessRegion(TimeRegion):
    scope: Literal["source_block", "source_file"]
    integrated_lufs: float | None = None
    loudness_range_lu: float | None = None
    true_peak_dbtp: float | None = None
    error: str | None = None


class AudioTimeline(AudioModel):
    columns: tuple[str, ...] = COLUMNS
    units: dict[str, str] = Field(default_factory=lambda: {
        "start_s": "seconds", "end_s": "seconds", "rms_dbfs": "dBFS",
        "peak_dbfs": "dBFS", "low_ratio": "fraction", "mid_ratio": "fraction",
        "high_ratio": "fraction", "centroid_hz": "Hz",
        "onset_strength": "maximum positive mel-band dB change per analysis hop",
        "delta_rms_db": "dB", "silent": "boolean",
    })
    rows: list[FrameRow] = Field(default_factory=list)
    resolution_ms: int
    total_frames: int
    offset: int
    complete: bool
    next_offset: int | None = None
    covered_start_s: float
    covered_end_s: float
    max_response_bytes: int = 512 * 1024


class OnsetEvent(AudioModel):
    time_s: float
    strength: float


class AudioEvents(AudioModel):
    onsets: list[OnsetEvent] = Field(default_factory=list)
    beats: list[float] = Field(default_factory=list)


class AudioAnalysisResult(AudioModel):
    ok: bool
    status: Literal["ok", "partial", "error"]
    error_code: str | None = None
    message: str | None = None
    analysis_id: str | None = None
    time_reference: Literal["source_file"] = "source_file"
    source: AudioSource | None = None
    summary: AudioSummary | None = None
    loudness_regions: list[LoudnessRegion] = Field(default_factory=list)
    timeline: AudioTimeline | None = None
    events: AudioEvents = Field(default_factory=AudioEvents)
    analysis_parameters: dict[str, JsonValue] = Field(default_factory=dict)
    versions: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    unavailable_fields: list[str] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)
