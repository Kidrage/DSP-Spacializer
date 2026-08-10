"""Strict SOFA HRIR loading and time-aligned directional interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from math import gcd
from pathlib import Path
import warnings

import numpy as np
from scipy.signal import resample_poly

from .foa import foa_direction_vector


@dataclass(frozen=True)
class InterpolatedHrir:
    ir: np.ndarray
    delay_samples: np.ndarray
    nearest_error_deg: float


def _unit_vectors(azimuth_deg: np.ndarray, elevation_deg: np.ndarray) -> np.ndarray:
    azimuth = np.deg2rad(azimuth_deg)
    elevation = np.deg2rad(elevation_deg)
    horizontal = np.cos(elevation)
    return np.stack(
        [horizontal * np.cos(azimuth), horizontal * np.sin(azimuth), np.sin(elevation)], axis=-1
    )


def _source_directions(sofa: object) -> np.ndarray:
    positions = np.asarray(sofa.SourcePosition, dtype=float)
    if positions.ndim != 2 or positions.shape[1] < 3:
        raise ValueError("SOFA SourcePosition must be shaped [M, 3]")
    kind = str(getattr(sofa, "SourcePosition_Type", "spherical")).lower()
    if kind == "spherical":
        return positions[:, :2]
    if kind == "cartesian":
        x, y, z = positions[:, 0], positions[:, 1], positions[:, 2]
        azimuth = np.rad2deg(np.arctan2(y, x))
        elevation = np.rad2deg(np.arctan2(z, np.hypot(x, y)))
        return np.stack([azimuth, elevation], axis=1)
    raise ValueError(f"unsupported SOFA SourcePosition_Type: {kind}")


def _expand_delays(sofa: object, measurements: int, receivers: int, sample_rate: int) -> np.ndarray:
    delays = np.asarray(getattr(sofa, "Data_Delay", 0.0), dtype=float)
    if delays.ndim == 0:
        delays = np.full((measurements, receivers), float(delays))
    elif delays.ndim == 1:
        delays = np.broadcast_to(delays[None, :], (measurements, receivers))
    elif delays.shape[0] == 1:
        delays = np.broadcast_to(delays, (measurements, receivers))
    if delays.shape != (measurements, receivers):
        raise ValueError("SOFA Data.Delay must be scalar, [R], [1,R], or [M,R]")
    units = str(getattr(sofa, "Data_Delay_Units", "second")).lower()
    return delays * sample_rate if "second" in units else delays


class SofaHrirDatabase:
    """A validated SimpleFreeFieldHRIR database at one renderer sample rate."""

    def __init__(self, path: str | Path, sample_rate: int):
        try:
            import sofar
        except ImportError as exc:
            raise RuntimeError("Spatial Core V2 requires the 'sofar' package") from exc
        sofa_path = Path(path).expanduser().resolve()
        if not sofa_path.is_file():
            raise ValueError(f"SOFA file does not exist: {sofa_path}")
        try:
            sofa = sofar.read_sofa(sofa_path)
        except Exception as exc:
            raise ValueError(f"unable to read SOFA file: {sofa_path}") from exc
        if str(getattr(sofa, "GLOBAL_SOFAConventions", "")) != "SimpleFreeFieldHRIR":
            raise ValueError("SOFA file must use the SimpleFreeFieldHRIR convention")
        ir = np.asarray(sofa.Data_IR, dtype=np.float32)
        if ir.ndim != 3 or ir.shape[1] != 2:
            raise ValueError("SOFA Data.IR must contain two receivers and FIR data [M,2,N]")
        directions = _source_directions(sofa)
        rounded = np.round(directions, decimals=6)
        if np.unique(rounded, axis=0).shape[0] < 3:
            raise ValueError("SOFA file must contain at least three unique source directions")
        basis = np.stack(
            [foa_direction_vector(azimuth, elevation) for azimuth, elevation in directions]
        )
        if np.linalg.matrix_rank(basis) < 4:
            raise ValueError("SOFA source directions must span the rank-4 first-order basis")
        source_rate = int(np.asarray(sofa.Data_SamplingRate).reshape(-1)[0])
        delays = _expand_delays(sofa, ir.shape[0], 2, source_rate)
        target_rate = int(sample_rate)
        if source_rate != target_rate:
            divisor = gcd(source_rate, target_rate)
            ir = resample_poly(ir, target_rate // divisor, source_rate // divisor, axis=-1)
            delays = delays * target_rate / source_rate
        self.path = sofa_path
        self.sample_rate = target_rate
        self.ir = np.asarray(ir, dtype=np.float32)
        self.delays = np.asarray(delays, dtype=np.float32)
        self.directions = directions
        self.vectors = _unit_vectors(directions[:, 0], directions[:, 1])
        front_index = int(np.argmin(self.angular_errors(0.0, 0.0)))
        front_energy = float(np.sqrt(np.mean(np.sum(self.ir[front_index] ** 2, axis=-1))))
        if not np.isfinite(front_energy) or front_energy <= 1e-9:
            raise ValueError("SOFA front-reference HRIR has no usable energy")
        self.front_reference_gain = 1.0 / front_energy

    def angular_errors(self, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
        target = _unit_vectors(np.asarray([azimuth_deg]), np.asarray([elevation_deg]))[0]
        return np.rad2deg(np.arccos(np.clip(self.vectors @ target, -1.0, 1.0)))

    def interpolate(self, azimuth_deg: float, elevation_deg: float) -> InterpolatedHrir:
        errors = self.angular_errors(azimuth_deg, elevation_deg)
        order = np.argsort(errors)
        nearest_error = float(errors[order[0]])
        if nearest_error > 45.0:
            raise ValueError(
                f"requested direction is outside SOFA coverage ({nearest_error:.1f} degree nearest error)"
            )
        if nearest_error > 15.0:
            warnings.warn(
                f"SOFA directional coverage is sparse ({nearest_error:.1f} degree nearest error)",
                RuntimeWarning,
                stacklevel=2,
            )
        if nearest_error < 1e-7:
            index = int(order[0])
            return InterpolatedHrir(self.ir[index].copy(), self.delays[index].copy(), nearest_error)
        indices = order[:3]
        weights = 1.0 / np.maximum(errors[indices], 1e-6)
        weights /= np.sum(weights)
        aligned = np.zeros_like(self.ir[indices[0]], dtype=np.float64)
        effective_delays = np.zeros(2, dtype=np.float64)
        for weight, index in zip(weights, indices):
            for ear in range(2):
                response = self.ir[index, ear]
                threshold = 0.1 * float(np.max(np.abs(response)))
                onset_candidates = np.flatnonzero(np.abs(response) >= threshold)
                onset = int(onset_candidates[0]) if onset_candidates.size else 0
                shifted = np.zeros_like(response)
                shifted[: response.size - onset] = response[onset:]
                aligned[ear] += weight * shifted
                effective_delays[ear] += weight * (float(self.delays[index, ear]) + onset)
        return InterpolatedHrir(
            np.asarray(aligned, dtype=np.float32),
            np.asarray(effective_delays, dtype=np.float32),
            nearest_error,
        )

    def foa_to_ear_filters(self, regularization: float = 1e-4) -> np.ndarray:
        """Project all measured HRIRs onto four first-order SH filters."""

        max_delay = int(np.ceil(float(np.max(self.delays))))
        length = self.ir.shape[-1] + max_delay + 1
        measured = np.zeros((self.ir.shape[0], 2, length), dtype=np.float64)
        for measurement in range(self.ir.shape[0]):
            for ear in range(2):
                delay = float(self.delays[measurement, ear])
                base = int(np.floor(delay))
                fraction = delay - base
                response = self.ir[measurement, ear]
                measured[measurement, ear, base : base + response.size] += (1.0 - fraction) * response
                measured[measurement, ear, base + 1 : base + response.size + 1] += fraction * response
        basis = np.stack(
            [foa_direction_vector(azimuth, elevation) for azimuth, elevation in self.directions]
        ).astype(np.float64)
        inverse = np.linalg.solve(
            basis.T @ basis + float(regularization) * np.eye(4),
            basis.T,
        )
        return np.asarray(np.einsum("cm,mer->cer", inverse, measured), dtype=np.float32)
