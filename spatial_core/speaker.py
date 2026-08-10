"""FOA and 2D VBAP renderer for configurable four-speaker layouts."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .binaural import apply_air_absorption, distance_gain_db
from .foa import decode_foa_projection
from .rendering import RenderResult, linked_peak_limit
from .scene import SpatialScene


@dataclass(frozen=True)
class Speaker:
    name: str
    azimuth_deg: float


DEFAULT_QUAD_LAYOUT = (
    Speaker("front_left", 30.0),
    Speaker("front_right", -30.0),
    Speaker("rear_left", 135.0),
    Speaker("rear_right", -135.0),
)


def _speaker_vector(azimuth_deg: float) -> np.ndarray:
    azimuth = np.deg2rad(float(azimuth_deg))
    return np.asarray([np.cos(azimuth), np.sin(azimuth)], dtype=np.float64)


def vbap_gains(azimuth_deg: float, layout: tuple[Speaker, ...]) -> np.ndarray:
    """Return L2-normalized gains for the enclosing adjacent 2D speaker pair."""

    if len(layout) < 2:
        raise ValueError("VBAP layout requires at least two speakers")
    ordered = sorted(enumerate(layout), key=lambda item: item[1].azimuth_deg)
    target = _speaker_vector(azimuth_deg)
    candidates: list[tuple[float, int, int, np.ndarray]] = []
    for pair_index in range(len(ordered)):
        first_index, first = ordered[pair_index]
        second_index, second = ordered[(pair_index + 1) % len(ordered)]
        matrix = np.stack([_speaker_vector(first.azimuth_deg), _speaker_vector(second.azimuth_deg)], axis=1)
        if abs(np.linalg.det(matrix)) < 1e-8:
            continue
        pair_gains = np.linalg.solve(matrix, target)
        penalty = float(np.sum(np.maximum(0.0, -pair_gains)))
        candidates.append((penalty, first_index, second_index, pair_gains))
    if not candidates:
        raise ValueError("VBAP layout has no invertible adjacent speaker pair")
    _penalty, first_index, second_index, pair_gains = min(candidates, key=lambda item: item[0])
    pair_gains = np.maximum(pair_gains, 0.0)
    norm = float(np.linalg.norm(pair_gains))
    if norm < 1e-8:
        nearest = int(np.argmin([abs(((azimuth_deg - item.azimuth_deg + 180) % 360) - 180) for item in layout]))
        result = np.zeros(len(layout), dtype=np.float32)
        result[nearest] = 1.0
        return result
    result = np.zeros(len(layout), dtype=np.float32)
    result[first_index] = pair_gains[0] / norm
    result[second_index] = pair_gains[1] / norm
    return result


class QuadSpeakerRenderer:
    def __init__(self, layout: tuple[Speaker, ...] = DEFAULT_QUAD_LAYOUT):
        if len(layout) != 4:
            raise ValueError("QuadSpeakerRenderer requires exactly four speakers")
        self.layout = tuple(layout)

    def render(self, scene: SpatialScene) -> RenderResult:
        output = np.zeros((scene.num_frames, 4), dtype=np.float32)
        elevation_projected: list[str] = []
        for item in scene.objects:
            if abs(item.elevation_deg) > 1e-6:
                elevation_projected.append(item.object_id)
            gain = 10.0 ** ((item.gain_db + distance_gain_db(item.distance_m)) / 20.0)
            azimuths = [item.azimuth_deg]
            if item.size > 1e-6:
                spread = 30.0 * item.size
                azimuths.extend([item.azimuth_deg - spread, item.azimuth_deg + spread])
            ray_gain = 1.0 / np.sqrt(len(azimuths))
            positional = np.zeros(4, dtype=np.float32)
            for azimuth in azimuths:
                positional += ray_gain * vbap_gains(azimuth, self.layout)
            direct_gain = np.sqrt(max(0.0, 1.0 - item.diffusion))
            diffuse_gain = np.sqrt(item.diffusion) / 2.0
            gains = direct_gain * positional + diffuse_gain * np.ones(4, dtype=np.float32)
            filtered = apply_air_absorption(item.audio, scene.sample_rate, item.distance_m)
            output += filtered[:, None] * (gain * gains)[None, :]
        if scene.bed is not None:
            directions = [(item.azimuth_deg, 0.0) for item in self.layout]
            output += decode_foa_projection(scene.bed.audio, directions)
        limited, limiter_gain = linked_peak_limit(output)
        return RenderResult(
            limited,
            scene.sample_rate,
            {
                "engine": "spatial-v2-quad",
                "layout": [{"name": item.name, "azimuth": item.azimuth_deg} for item in self.layout],
                "elevation_projected_objects": elevation_projected,
                "limiter_gain": limiter_gain,
                "foa_convention": "AmbiX ACN/SN3D (W,Y,Z,X)",
            },
        )
