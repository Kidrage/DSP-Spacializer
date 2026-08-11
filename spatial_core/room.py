"""Deterministic first-order room geometry for the balanced-depth renderer."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .scene import SpatialObject


ROOM_DIMENSIONS_M = np.asarray([6.0, 5.0, 3.0], dtype=np.float64)
LISTENER_POSITION_M = np.asarray([3.0, 2.5, 1.2], dtype=np.float64)
SPEED_OF_SOUND_M_S = 343.0


@dataclass(frozen=True)
class EarlyReflection:
    wall: str
    delay_ms: float
    azimuth_deg: float
    elevation_deg: float
    relative_gain: float


def _source_vector(item: SpatialObject) -> np.ndarray:
    azimuth = np.deg2rad(float(item.azimuth_deg))
    elevation = np.deg2rad(float(item.elevation_deg))
    horizontal = float(item.distance_m) * np.cos(elevation)
    return np.asarray(
        [
            horizontal * np.cos(azimuth),
            horizontal * np.sin(azimuth),
            float(item.distance_m) * np.sin(elevation),
        ],
        dtype=np.float64,
    )


def balanced_depth_reflections(
    item: SpatialObject,
    *,
    minimum_delay_ms: float = 8.0,
) -> tuple[EarlyReflection, ...]:
    """Return audible first-order image sources in a fixed 6 x 5 x 3 m room."""

    source = LISTENER_POSITION_M + _source_vector(item)
    walls = (
        ("back", 0, 0.0, 0.72),
        ("front", 0, ROOM_DIMENSIONS_M[0], 0.72),
        ("right", 1, 0.0, 0.78),
        ("left", 1, ROOM_DIMENSIONS_M[1], 0.78),
        ("floor", 2, 0.0, 0.55),
        ("ceiling", 2, ROOM_DIMENSIONS_M[2], 0.65),
    )
    direct_distance = float(item.distance_m)
    reflections: list[EarlyReflection] = []
    for wall, axis, plane, wall_gain in walls:
        image = source.copy()
        image[axis] = 2.0 * plane - source[axis]
        vector = image - LISTENER_POSITION_M
        path_length = float(np.linalg.norm(vector))
        delay_ms = 1_000.0 * (path_length - direct_distance) / SPEED_OF_SOUND_M_S
        if delay_ms < float(minimum_delay_ms):
            continue
        azimuth = float(np.rad2deg(np.arctan2(vector[1], vector[0])))
        elevation = float(np.rad2deg(np.arctan2(vector[2], np.hypot(vector[0], vector[1]))))
        reflections.append(
            EarlyReflection(
                wall=wall,
                delay_ms=delay_ms,
                azimuth_deg=azimuth,
                elevation_deg=elevation,
                relative_gain=float(wall_gain * direct_distance / max(path_length, 1e-9)),
            )
        )
    return tuple(sorted(reflections, key=lambda reflection: reflection.delay_ms))
