"""Lossless seven-zone M/S analysis for stereo scene construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

import numpy as np
from scipy.signal import istft, stft

from .profile import SpatialCoreProfile


ZONE_NAMES = (
    "bass",
    "center_anchor",
    "front_L_residual",
    "front_R_residual",
    "side_width",
    "rear_ambience",
    "high_air",
)


@dataclass(frozen=True)
class SpatialZones:
    bass: np.ndarray
    center_anchor: np.ndarray
    front_L_residual: np.ndarray
    front_R_residual: np.ndarray
    side_width: np.ndarray
    rear_ambience: np.ndarray
    high_air: np.ndarray

    @property
    def names(self) -> tuple[str, ...]:
        return ZONE_NAMES

    def as_dict(self) -> dict[str, np.ndarray]:
        return {name: getattr(self, name) for name in self.names}

    def reconstruct_stereo(self) -> np.ndarray:
        common = self.bass + self.center_anchor
        bed_side = self.side_width + self.rear_ambience + self.high_air
        return np.stack(
            [common + self.front_L_residual + bed_side,
             common + self.front_R_residual - bed_side],
            axis=1,
        ).astype(np.float32)


def _cosine_ramp(frequencies: np.ndarray, start: float, stop: float) -> np.ndarray:
    position = np.clip((frequencies - start) / (stop - start), 0.0, 1.0)
    return 0.5 - 0.5 * np.cos(np.pi * position)


def _inverse_spectrum(spectrum: np.ndarray, frames: int) -> np.ndarray:
    _, audio = istft(
        spectrum,
        window="hann",
        nperseg=2048,
        noverlap=1536,
        nfft=2048,
        input_onesided=True,
        boundary=True,
    )
    return np.asarray(audio[:frames], dtype=np.float32)


def extract_spatial_zones(
    stereo: np.ndarray,
    *,
    sample_rate: int = 48_000,
    profile: SpatialCoreProfile | None = None,
    extraction: Mapping[str, float] | None = None,
) -> SpatialZones:
    """Split stereo into seven non-overlapping zones with exact dry reconstruction."""

    audio = np.asarray(stereo, dtype=np.float64)
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("stereo input must be shaped [frames, 2]")
    if not np.all(np.isfinite(audio)):
        raise ValueError("stereo input contains non-finite samples")
    settings = profile or SpatialCoreProfile()
    extraction_values = {
        "bass_low_hz": 80.0,
        "bass_high_hz": 160.0,
        "center_anchor": float(settings.center_anchor),
        "center_focus_low_hz": 900.0,
        "center_focus_high_hz": 2_500.0,
        "center_focus_floor": 0.25,
        "front_side_weight_low": 0.90,
        "front_side_weight_high": 0.75,
        "rear_strength": 0.55,
        "rear_low_hz": 1_500.0,
        "rear_high_hz": 3_000.0,
        "air_low_hz": 5_500.0,
        "air_high_hz": 9_000.0,
    }
    if extraction is not None:
        unknown = sorted(set(extraction) - set(extraction_values))
        if unknown:
            raise ValueError(f"unknown extraction parameter: {unknown[0]}")
        extraction_values.update({name: float(value) for name, value in extraction.items()})
    frames = audio.shape[0]
    if frames == 0:
        empty = np.zeros(0, dtype=np.float32)
        return SpatialZones(*(empty.copy() for _ in ZONE_NAMES))

    padded = np.pad(audio, ((0, max(0, 2048 - frames)), (0, 0)))
    frequencies, _, left = stft(
        padded[:, 0],
        fs=int(sample_rate),
        window="hann",
        nperseg=2048,
        noverlap=1536,
        nfft=2048,
        boundary="zeros",
        padded=True,
    )
    _, _, right = stft(
        padded[:, 1],
        fs=int(sample_rate),
        window="hann",
        nperseg=2048,
        noverlap=1536,
        nfft=2048,
        boundary="zeros",
        padded=True,
    )
    mid = 0.5 * (left + right)
    side = 0.5 * (left - right)

    frequency_column = frequencies[:, None]
    bass_mask = 1.0 - _cosine_ramp(
        frequency_column,
        extraction_values["bass_low_hz"],
        extraction_values["bass_high_hz"],
    )
    magnitude_left = np.abs(left)
    magnitude_right = np.abs(right)
    denominator = magnitude_left * magnitude_right + 1e-12
    phase_coherence = np.clip(
        np.real(left * np.conj(right)) / denominator,
        0.0,
        1.0,
    )
    balance = 2.0 * np.minimum(magnitude_left, magnitude_right) / (
        magnitude_left + magnitude_right + 1e-12
    )
    anchor_focus = 1.0 - (1.0 - extraction_values["center_focus_floor"]) * _cosine_ramp(
        frequency_column,
        extraction_values["center_focus_low_hz"],
        extraction_values["center_focus_high_hz"],
    )
    center_mask = (
        extraction_values["center_anchor"]
        * phase_coherence
        * balance
        * anchor_focus
        * (1.0 - bass_mask)
    )
    bass_spectrum = bass_mask * mid
    center_spectrum = center_mask * mid
    residual_mid = mid - bass_spectrum - center_spectrum

    front_weight_range = (
        extraction_values["front_side_weight_low"]
        - extraction_values["front_side_weight_high"]
    )
    front_side_weight = extraction_values["front_side_weight_low"]
    front_side_weight -= (2.0 / 3.0) * front_weight_range * _cosine_ramp(
        frequency_column, 500.0, 6_000.0
    )
    front_side_weight -= (1.0 / 3.0) * front_weight_range * _cosine_ramp(
        frequency_column, 6_000.0, 10_000.0
    )
    front_side_weight = np.clip(
        front_side_weight,
        extraction_values["front_side_weight_high"],
        extraction_values["front_side_weight_low"],
    )
    bed_weight = 1.0 - front_side_weight
    air_preference = _cosine_ramp(
        frequency_column,
        extraction_values["air_low_hz"],
        extraction_values["air_high_hz"],
    )
    rear_preference = extraction_values["rear_strength"] * _cosine_ramp(
        frequency_column,
        extraction_values["rear_low_hz"],
        extraction_values["rear_high_hz"],
    )
    rear_preference *= 1.0 - 0.65 * _cosine_ramp(frequency_column, 6_000.0, 10_000.0)
    width_preference = np.ones_like(frequency_column)
    preference_sum = width_preference + rear_preference + air_preference
    side_width_mask = bed_weight * width_preference / preference_sum
    rear_mask = bed_weight * rear_preference / preference_sum
    air_mask = bed_weight * air_preference / preference_sum

    front_side = front_side_weight * side
    spectra = (
        bass_spectrum,
        center_spectrum,
        residual_mid + front_side,
        residual_mid - front_side,
        side_width_mask * side,
        rear_mask * side,
        air_mask * side,
    )
    return SpatialZones(*(_inverse_spectrum(item, frames) for item in spectra))
