"""Subjective A/B promotion gate for replacing the frozen legacy renderer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
from scipy.signal import butter, sosfiltfilt


TIMBRE_UTILITY_DIRECTIONS = {
    "vocal_clarity": 1.0,
    "bass_weight": 1.0,
    "bass_tightness": 1.0,
    "harshness": -1.0,
    "mud": -1.0,
}

CLARITY_GATE_THRESHOLDS = {
    "maximum_mid_side_balance_delta_db": 1.0,
    "minimum_crest_delta_db": -1.0,
    "minimum_fast_change_delta_db": -0.5,
    "maximum_absolute_band_delta_db": 2.0,
}
CLARITY_GATE_BANDS = ("sub", "bass", "low_mid", "presence")
CLARITY_BAND_LIMITS_HZ = {
    "sub": (25.0, 70.0),
    "bass": (70.0, 250.0),
    "low_mid": (250.0, 700.0),
    "presence": (2_000.0, 6_000.0),
}


def _rms(audio: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(audio, dtype=np.float64) ** 2)) + 1e-12)


def _bandpass(
    audio: np.ndarray,
    sample_rate: int,
    low_hz: float,
    high_hz: float,
) -> np.ndarray:
    sos = butter(4, [low_hz, high_hz], btype="bandpass", fs=sample_rate, output="sos")
    return sosfiltfilt(sos, audio, axis=0)


def _clarity_snapshot(audio: np.ndarray, sample_rate: int) -> dict[str, object]:
    value = np.asarray(audio, dtype=np.float64)
    if value.ndim != 2 or value.shape[1] != 2:
        raise ValueError("clarity audio must be shaped [frames, 2]")
    focus = _bandpass(value, sample_rate, 250.0, 5_000.0)
    mid = (focus[:, 0] + focus[:, 1]) / np.sqrt(2.0)
    side = (focus[:, 0] - focus[:, 1]) / np.sqrt(2.0)
    focus_rms = _rms(focus)
    return {
        "mid_side_balance_db": 20.0 * np.log10(_rms(mid) / _rms(side)),
        "crest_db": 20.0 * np.log10(float(np.max(np.abs(focus))) / focus_rms),
        "fast_change_db": 20.0 * np.log10(_rms(np.diff(focus, axis=0)) / focus_rms),
        "band_db": {
            name: 20.0 * np.log10(_rms(_bandpass(value, sample_rate, *limits)) / _rms(value))
            for name, limits in CLARITY_BAND_LIMITS_HZ.items()
        },
    }


def measure_clarity_metrics(
    source: np.ndarray,
    output: np.ndarray,
    sample_rate: int,
) -> dict[str, object]:
    """Measure objective clarity deltas between paired stereo excerpts."""

    source_snapshot = _clarity_snapshot(source, int(sample_rate))
    output_snapshot = _clarity_snapshot(output, int(sample_rate))
    source_bands = source_snapshot["band_db"]
    output_bands = output_snapshot["band_db"]
    return {
        "mid_side_balance_delta_db": float(output_snapshot["mid_side_balance_db"])
        - float(source_snapshot["mid_side_balance_db"]),
        "crest_delta_db": float(output_snapshot["crest_db"])
        - float(source_snapshot["crest_db"]),
        "fast_change_delta_db": float(output_snapshot["fast_change_db"])
        - float(source_snapshot["fast_change_db"]),
        "band_delta_db": {
            band: float(output_bands[band]) - float(source_bands[band])
            for band in CLARITY_GATE_BANDS
        },
    }


def evaluate_clarity_gate(metrics: Mapping[str, object]) -> dict[str, object]:
    """Classify objective timbre/clarity deltas for one rendered candidate."""

    band_deltas = metrics.get("band_delta_db")
    if not isinstance(band_deltas, Mapping):
        raise ValueError("clarity metrics require band_delta_db")
    failures: list[str] = []
    mid_side_delta = float(metrics["mid_side_balance_delta_db"])
    crest_delta = float(metrics["crest_delta_db"])
    fast_change_delta = float(metrics["fast_change_delta_db"])
    if abs(mid_side_delta) > CLARITY_GATE_THRESHOLDS["maximum_mid_side_balance_delta_db"]:
        failures.append("mid_side_balance_delta_db")
    if crest_delta < CLARITY_GATE_THRESHOLDS["minimum_crest_delta_db"]:
        failures.append("crest_delta_db")
    if fast_change_delta < CLARITY_GATE_THRESHOLDS["minimum_fast_change_delta_db"]:
        failures.append("fast_change_delta_db")
    for band in CLARITY_GATE_BANDS:
        if abs(float(band_deltas[band])) > CLARITY_GATE_THRESHOLDS["maximum_absolute_band_delta_db"]:
            failures.append(f"band_delta_db.{band}")
    return {
        "pass": not failures,
        "failures": failures,
        "thresholds": dict(CLARITY_GATE_THRESHOLDS),
    }


def evaluate_promotion_gate(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Evaluate the S1 listening gate across paired legacy/V2 score records."""

    track_ids: list[str] = []
    for record in records:
        identifier = record.get("track_id", record.get("song_id", record.get("input")))
        if identifier is None or not str(identifier).strip():
            raise ValueError("each promotion record requires track_id, song_id, or input")
        track_ids.append(str(identifier))
    unique_track_count = len(set(track_ids))
    if unique_track_count != len(track_ids):
        raise ValueError("promotion records must contain one paired record per unique track")
    if unique_track_count < 3:
        return {
            "promote": False,
            "track_count": unique_track_count,
            "record_count": len(records),
            "reason": "at least three unique paired tracks are required",
        }
    externalization_deltas: list[float] = []
    depth_deltas: list[float] = []
    worst_timbre_regression = 0.0
    objective_clarity_pass = True
    for record in records:
        legacy = record.get("legacy")
        candidate = record.get("spatial_v2")
        if not isinstance(legacy, Mapping) or not isinstance(candidate, Mapping):
            raise ValueError("each promotion record requires legacy and spatial_v2 score objects")
        externalization_deltas.append(float(candidate["externalization"]) - float(legacy["externalization"]))
        depth_deltas.append(float(candidate["depth"]) - float(legacy["depth"]))
        objective_clarity_pass = objective_clarity_pass and (
            record.get("objective_clarity_pass") is True
        )
        for key, direction in TIMBRE_UTILITY_DIRECTIONS.items():
            if key in legacy and key in candidate:
                utility_delta = direction * (float(candidate[key]) - float(legacy[key]))
                worst_timbre_regression = max(worst_timbre_regression, -utility_delta)
    externalization_delta = sum(externalization_deltas) / len(externalization_deltas)
    depth_delta = sum(depth_deltas) / len(depth_deltas)
    promote = (
        externalization_delta >= 0.5
        and depth_delta >= 0.5
        and worst_timbre_regression <= 0.5
        and objective_clarity_pass
    )
    return {
        "promote": promote,
        "track_count": unique_track_count,
        "record_count": len(records),
        "mean_externalization_delta": externalization_delta,
        "mean_depth_delta": depth_delta,
        "worst_timbre_regression": worst_timbre_regression,
        "objective_clarity_pass": objective_clarity_pass,
        "thresholds": {
            "minimum_tracks": 3,
            "minimum_externalization_delta": 0.5,
            "minimum_depth_delta": 0.5,
            "maximum_timbre_regression": 0.5,
        },
    }
