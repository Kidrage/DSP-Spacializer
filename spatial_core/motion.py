"""Listener trajectory parsing, SLERP interpolation, and seeded micro-motion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json

import numpy as np
from scipy.spatial.transform import Rotation, Slerp


@dataclass(frozen=True)
class ListenerPose:
    yaw_deg: float = 0.0
    pitch_deg: float = 0.0
    roll_deg: float = 0.0


class ListenerTrajectory:
    def __init__(self, times: np.ndarray, rotations: Rotation):
        values = np.asarray(times, dtype=float)
        if values.ndim != 1 or values.size == 0 or np.any(np.diff(values) <= 0):
            raise ValueError("listener trajectory times must be strictly increasing")
        if len(rotations) != values.size:
            raise ValueError("listener trajectory pose count does not match times")
        self.times = values
        self.rotations = rotations
        self._slerp = Slerp(values, rotations) if values.size > 1 else None

    @classmethod
    def load(cls, path: str | Path) -> "ListenerTrajectory":
        manifest = Path(path).expanduser().resolve()
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to read listener trajectory: {manifest}") from exc
        if payload.get("format") != "bds_listener_trajectory" or payload.get("version") != "1.0":
            raise ValueError("listener trajectory must use bds_listener_trajectory version 1.0")
        keyframes = payload.get("keyframes", [])
        times = np.asarray([float(item["time"]) for item in keyframes], dtype=float)
        euler = np.asarray(
            [
                [float(item.get("yaw", 0)), float(item.get("pitch", 0)), float(item.get("roll", 0))]
                for item in keyframes
            ],
            dtype=float,
        )
        return cls(times, Rotation.from_euler("zyx", euler, degrees=True))

    def rotation_at(self, time_s: float) -> Rotation:
        time = float(np.clip(time_s, self.times[0], self.times[-1]))
        if self._slerp is None:
            return self.rotations[0]
        return self._slerp([time])[0]


class MicroMotion:
    def __init__(self, seed: int = 0):
        rng = np.random.default_rng(int(seed))
        self.phases = rng.uniform(0.0, 2.0 * np.pi, size=4)
        self.rates = rng.uniform(0.07, 0.21, size=4)

    def rotation_at(self, time_s: float) -> Rotation:
        time = float(time_s)
        yaw = 2.5 * np.sin(2 * np.pi * self.rates[0] * time + self.phases[0])
        yaw += 2.5 * np.sin(2 * np.pi * self.rates[1] * time + self.phases[1])
        pitch = 1.5 * np.sin(2 * np.pi * self.rates[2] * time + self.phases[2])
        pitch += 1.5 * np.sin(2 * np.pi * self.rates[3] * time + self.phases[3])
        return Rotation.from_euler("zyx", [yaw, pitch, 0.0], degrees=True)


def relative_direction(
    azimuth_deg: float,
    elevation_deg: float,
    listener_rotation: Rotation,
) -> tuple[float, float]:
    azimuth = np.deg2rad(float(azimuth_deg))
    elevation = np.deg2rad(float(elevation_deg))
    vector = np.asarray(
        [np.cos(elevation) * np.cos(azimuth), np.cos(elevation) * np.sin(azimuth), np.sin(elevation)]
    )
    relative = listener_rotation.inv().apply(vector)
    azimuth_out = np.rad2deg(np.arctan2(relative[1], relative[0]))
    elevation_out = np.rad2deg(np.arctan2(relative[2], np.hypot(relative[0], relative[1])))
    return float(azimuth_out), float(elevation_out)
