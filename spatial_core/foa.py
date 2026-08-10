"""First-order Ambisonics helpers using AmbiX ACN/SN3D W,Y,Z,X."""

from __future__ import annotations

import numpy as np


def foa_direction_vector(azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    """Return the real first-order SN3D basis in ACN channel order."""

    azimuth = np.deg2rad(float(azimuth_deg))
    elevation = np.deg2rad(float(elevation_deg))
    horizontal = np.cos(elevation)
    return np.asarray(
        [
            1.0,
            np.sin(azimuth) * horizontal,
            np.sin(elevation),
            np.cos(azimuth) * horizontal,
        ],
        dtype=np.float32,
    )


def encode_mono_foa(
    audio: np.ndarray,
    azimuth_deg: float,
    elevation_deg: float,
    gain: float = 1.0,
) -> np.ndarray:
    signal = np.asarray(audio, dtype=np.float32)
    if signal.ndim != 1:
        raise ValueError("FOA encoder input must be mono")
    return signal[:, None] * (float(gain) * foa_direction_vector(azimuth_deg, elevation_deg))


def decode_foa_projection(
    foa: np.ndarray,
    directions_deg: list[tuple[float, float]],
    regularization: float = 1e-5,
) -> np.ndarray:
    """Decode FOA to arbitrary directions with a regularized least-squares matrix."""

    field = np.asarray(foa, dtype=np.float32)
    if field.ndim != 2 or field.shape[1] != 4:
        raise ValueError("FOA input must be shaped [frames, 4]")
    basis = np.stack([foa_direction_vector(az, el) for az, el in directions_deg])
    gram = basis.T @ basis + float(regularization) * np.eye(4, dtype=np.float32)
    decoder = basis @ np.linalg.inv(gram)
    return np.asarray(field @ decoder.T, dtype=np.float32)
