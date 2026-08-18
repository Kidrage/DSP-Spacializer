"""Validated compact tuning profile for Spatial Core scene and room rendering."""

from __future__ import annotations

from dataclasses import dataclass, fields
from math import isfinite
from pathlib import Path
import json


PROFILE_FORMAT = "spatial_core_profile"
PROFILE_VERSION = "1.0"
PROFILE_FIELDS = {"format", "version", "parameters"}

LEGACY_PARAMETER_NAMES = (
    "center_anchor",
    "front_distance_m",
    "front_width_deg",
    "bed_width_gain",
    "bed_rear_gain",
    "bed_air_gain",
    "direct_ratio",
    "early_reflection_level_db",
    "late_reverb_level_db",
    "late_rt60_s",
)

FRONTAL_EXPERIMENT_NAMES = (
    "hrtf_compensation_mode",
    "mastered_loudness_mode",
    "center_room_send_db",
    "reflection_normalization_mode",
    "direct_ratio_mode",
)

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
    "center_room_send_db": (-12.0, 6.0),
}

MODE_VALUES = {
    "hrtf_compensation_mode": {"legacy_front_common", "off"},
    "mastered_loudness_mode": {
        "legacy_input_rms",
        "fixed_scene_gain",
        "level_matched_eval",
    },
    "reflection_normalization_mode": {"legacy_per_object", "physical_path_gain"},
    "direct_ratio_mode": {"manual", "distance_curve"},
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
    hrtf_compensation_mode: str = "legacy_front_common"
    mastered_loudness_mode: str = "legacy_input_rms"
    center_room_send_db: float = -3.0
    reflection_normalization_mode: str = "legacy_per_object"
    direct_ratio_mode: str = "manual"

    def __post_init__(self) -> None:
        for name, (minimum, maximum) in PARAMETER_RANGES.items():
            raw_value = getattr(self, name)
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            value = float(raw_value)
            if not isfinite(value) or not minimum <= value <= maximum:
                raise ValueError(f"{name} must be within [{minimum}, {maximum}]")
        for name, allowed in MODE_VALUES.items():
            value = getattr(self, name)
            if not isinstance(value, str) or value not in allowed:
                choices = ", ".join(sorted(allowed))
                raise ValueError(f"{name} must be one of: {choices}")


def profile_scene_parameters(profile: SpatialCoreProfile) -> dict[str, object]:
    """Serialize legacy fields identically and include only active experiments."""

    values = {name: getattr(profile, name) for name in LEGACY_PARAMETER_NAMES}
    defaults = SpatialCoreProfile()
    if any(
        getattr(profile, name) != getattr(defaults, name)
        for name in FRONTAL_EXPERIMENT_NAMES
    ):
        values.update(
            {name: getattr(profile, name) for name in FRONTAL_EXPERIMENT_NAMES}
        )
    return values


def load_spatial_profile(path: str | Path) -> SpatialCoreProfile:
    profile_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read spatial profile: {profile_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("spatial profile must be a JSON object")
    unknown_fields = sorted(set(payload) - PROFILE_FIELDS)
    if unknown_fields:
        raise ValueError(f"unknown spatial profile field: {unknown_fields[0]}")
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
    values: dict[str, object] = {}
    for item in fields(SpatialCoreProfile):
        raw_value = parameters.get(item.name, getattr(defaults, item.name))
        if item.name in PARAMETER_RANGES:
            if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                raise ValueError(f"{item.name} must be numeric")
            values[item.name] = float(raw_value)
        else:
            values[item.name] = raw_value
    return SpatialCoreProfile(**values)
