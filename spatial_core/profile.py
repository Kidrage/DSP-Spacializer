"""Validated compact tuning profile for Spatial Core scene and room rendering."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path
import json


PROFILE_FORMAT = "spatial_core_profile"
PROFILE_VERSION = "1.0"

PARAMETER_RANGES = {
    "center_anchor": (0.0, 1.0),
    "front_distance_m": (0.5, 4.0),
    "front_width_deg": (15.0, 75.0),
    "bed_width_gain": (0.0, 1.0),
    "bed_rear_gain": (0.0, 1.0),
    "bed_air_gain": (0.0, 1.0),
    "direct_ratio": (0.3, 0.95),
    "early_reflection_level_db": (-40.0, -10.0),
    "late_reverb_level_db": (-40.0, -12.0),
    "late_rt60_s": (0.15, 1.20),
}


@dataclass(frozen=True)
class SpatialCoreProfile:
    center_anchor: float = 0.80
    front_distance_m: float = 1.60
    front_width_deg: float = 35.0
    bed_width_gain: float = 0.25
    bed_rear_gain: float = 0.18
    bed_air_gain: float = 0.12
    direct_ratio: float = 0.78
    early_reflection_level_db: float = -21.0
    late_reverb_level_db: float = -27.0
    late_rt60_s: float = 0.35

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in PARAMETER_RANGES.items():
            value = float(getattr(self, name))
            if not isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be within [{minimum}, {maximum}]")


def load_spatial_profile(path: str | Path) -> SpatialCoreProfile:
    profile_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read spatial profile: {profile_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("spatial profile must be a JSON object")
    if payload.get("format") != PROFILE_FORMAT or payload.get("version") != PROFILE_VERSION:
        raise ValueError("spatial profile must use spatial_core_profile version 1.0")
    parameters = payload.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("spatial profile parameters must be a JSON object")
    names = {item.name for item in fields(SpatialCoreProfile)}
    unknown = sorted(set(parameters) - names)
    if unknown:
        raise ValueError(f"unknown spatial profile parameter: {unknown[0]}")
    defaults = SpatialCoreProfile()
    values = {
        item.name: float(parameters.get(item.name, getattr(defaults, item.name)))
        for item in fields(SpatialCoreProfile)
    }
    return SpatialCoreProfile(**values)
