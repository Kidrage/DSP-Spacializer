"""Evaluation-only ITU-R BS.1770 integrated loudness support."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import isfinite

import numpy as np
from scipy.signal import lfilter


_BLOCK_SECONDS = 0.400
_ABSOLUTE_GATE_LKFS = -70.0
_RELATIVE_GATE_LU = -10.0
_LOUDNESS_OFFSET_DB = -0.691


@dataclass(frozen=True)
class LevelMatchedSignal:
    audio: np.ndarray
    natural_loudness_lkfs: float
    matched_loudness_lkfs: float
    applied_gain_db: float
    sample_peak: float


@dataclass(frozen=True)
class LoudnessMatchedGroup:
    signals: dict[str, LevelMatchedSignal]
    reference_loudness_lkfs: float
    final_target_loudness_lkfs: float
    shared_headroom_gain_db: float


def _k_weighting_coefficients(sample_rate: int) -> tuple[tuple[np.ndarray, np.ndarray], ...]:
    # ITU-R BS.1770 K-weighting, using the reference pre-warped De Man
    # biquad parameters at the requested sampling rate.
    shelf_frequency = 1_681.974450955533
    shelf_gain_db = 3.999843853973347
    shelf_q = 0.7071752369554196
    k = np.tan(np.pi * shelf_frequency / sample_rate)
    vh = 10.0 ** (shelf_gain_db / 20.0)
    vb = vh**0.4996667741545416
    a0 = 1.0 + k / shelf_q + k * k
    shelf_b = np.asarray(
        [
            (vh + vb * k / shelf_q + k * k) / a0,
            2.0 * (k * k - vh) / a0,
            (vh - vb * k / shelf_q + k * k) / a0,
        ],
        dtype=np.float64,
    )
    shelf_a = np.asarray(
        [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / shelf_q + k * k) / a0],
        dtype=np.float64,
    )

    highpass_frequency = 38.13547087602444
    highpass_q = 0.5003270373238773
    k = np.tan(np.pi * highpass_frequency / sample_rate)
    a0 = 1.0 + k / highpass_q + k * k
    highpass_b = np.asarray([1.0, -2.0, 1.0], dtype=np.float64)
    highpass_a = np.asarray(
        [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / highpass_q + k * k) / a0],
        dtype=np.float64,
    )
    return (shelf_b, shelf_a), (highpass_b, highpass_a)


def integrated_loudness_bs1770(audio: np.ndarray, sample_rate: int) -> float:
    """Measure mono or stereo integrated loudness using BS.1770-4 gating."""

    if isinstance(sample_rate, bool) or not isinstance(sample_rate, int) or sample_rate < 8_000:
        raise ValueError("sample_rate must be an integer of at least 8000")
    signal = np.asarray(audio, dtype=np.float64)
    if signal.ndim == 1:
        signal = signal[:, None]
    if signal.ndim != 2 or signal.shape[1] not in {1, 2}:
        raise ValueError("audio must be mono or stereo")
    if not np.all(np.isfinite(signal)):
        raise ValueError("audio must contain only finite samples")
    block_frames = int(round(_BLOCK_SECONDS * sample_rate))
    if signal.shape[0] < block_frames:
        raise ValueError("audio must contain at least 400 ms")

    weighted = signal
    for numerator, denominator in _k_weighting_coefficients(sample_rate):
        weighted = lfilter(numerator, denominator, weighted, axis=0)

    hop_frames = block_frames // 4
    block_starts = range(0, signal.shape[0] - block_frames + 1, hop_frames)
    block_energy = np.asarray(
        [
            float(np.sum(np.mean(weighted[start : start + block_frames] ** 2, axis=0)))
            for start in block_starts
        ],
        dtype=np.float64,
    )
    block_loudness = np.full(block_energy.shape, -np.inf, dtype=np.float64)
    positive = block_energy > 0.0
    block_loudness[positive] = (
        _LOUDNESS_OFFSET_DB + 10.0 * np.log10(block_energy[positive])
    )
    absolute_mask = block_loudness >= _ABSOLUTE_GATE_LKFS
    if not np.any(absolute_mask):
        return float("-inf")
    absolute_energy = float(np.mean(block_energy[absolute_mask]))
    relative_gate = (
        _LOUDNESS_OFFSET_DB + 10.0 * np.log10(absolute_energy) + _RELATIVE_GATE_LU
    )
    gated_mask = absolute_mask & (block_loudness >= relative_gate)
    gated_energy = float(np.mean(block_energy[gated_mask]))
    return float(_LOUDNESS_OFFSET_DB + 10.0 * np.log10(gated_energy))


def level_match_group_bs1770(
    signals: Mapping[str, np.ndarray],
    sample_rate: int,
    *,
    reference_key: str,
    peak_ceiling: float = 0.98,
) -> LoudnessMatchedGroup:
    """Match a signal group to one reference while retaining shared headroom."""

    if not signals:
        raise ValueError("signals must not be empty")
    if reference_key not in signals:
        raise ValueError("reference_key must identify a signal")
    if (
        isinstance(peak_ceiling, bool)
        or not isinstance(peak_ceiling, (int, float))
        or not 0.0 < float(peak_ceiling) <= 1.0
    ):
        raise ValueError("peak_ceiling must be within (0, 1]")

    natural_loudness = {
        key: integrated_loudness_bs1770(audio, sample_rate)
        for key, audio in signals.items()
    }
    if any(not isfinite(value) for value in natural_loudness.values()):
        raise ValueError("signals must contain measurable non-silent audio")
    reference_loudness = natural_loudness[reference_key]
    individual_gain_db = {
        key: reference_loudness - loudness for key, loudness in natural_loudness.items()
    }
    individually_matched = {
        key: np.asarray(
            np.asarray(audio, dtype=np.float64) * (10.0 ** (individual_gain_db[key] / 20.0)),
            dtype=np.float32,
        )
        for key, audio in signals.items()
    }
    maximum_peak = max(
        float(np.max(np.abs(audio))) if audio.size else 0.0
        for audio in individually_matched.values()
    )
    shared_headroom_gain_db = (
        min(0.0, 20.0 * np.log10(float(peak_ceiling) / maximum_peak))
        if maximum_peak > 0.0
        else 0.0
    )
    matched: dict[str, LevelMatchedSignal] = {}
    for key, audio in individually_matched.items():
        total_gain_db = individual_gain_db[key] + shared_headroom_gain_db
        safe_audio = np.asarray(
            audio * (10.0 ** (shared_headroom_gain_db / 20.0)),
            dtype=np.float32,
        )
        matched[key] = LevelMatchedSignal(
            audio=safe_audio,
            natural_loudness_lkfs=natural_loudness[key],
            matched_loudness_lkfs=integrated_loudness_bs1770(safe_audio, sample_rate),
            applied_gain_db=float(total_gain_db),
            sample_peak=float(np.max(np.abs(safe_audio))) if safe_audio.size else 0.0,
        )
    return LoudnessMatchedGroup(
        signals=matched,
        reference_loudness_lkfs=float(reference_loudness),
        final_target_loudness_lkfs=float(reference_loudness + shared_headroom_gain_db),
        shared_headroom_gain_db=float(shared_headroom_gain_db),
    )
