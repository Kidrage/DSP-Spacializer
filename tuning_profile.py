"""Tuning profile support for feedback-driven auto_acoustic refinement."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ALLOWED_TUNING_KEYS = {
    "side_front",
    "side_rear",
    "amb_rear",
    "air_rear",
    "rear_master",
    "decorrelation",
    "rear_floor_ratio",
    "max_rear_makeup",
    "guard_scale",
    "bass_gain",
    "bass_quad",
    "lowbody_rear",
    "rear_air_gain",
    "rear_highmid_gain",
}

DEFAULT_PARAMETER_RANGES = {
    "side_front": (0.0, 1.5),
    "side_rear": (0.0, 1.8),
    "amb_rear": (0.0, 1.6),
    "air_rear": (0.0, 1.0),
    "rear_master": (0.0, 1.6),
    "decorrelation": (0.0, 1.0),
    "rear_floor_ratio": (0.0, 0.25),
    "max_rear_makeup": (1.0, 8.0),
    "guard_scale": (0.0, 2.0),
    "bass_gain": (0.0, 1.8),
    "bass_quad": (0.0, 0.35),
    "lowbody_rear": (0.0, 0.9),
    "rear_air_gain": (0.0, 1.0),
    "rear_highmid_gain": (0.0, 1.0),
}


class TuningProfileError(ValueError):
    """Raised when a tuning profile is malformed."""


def _clamp(value: float, key: str) -> float:
    lo, hi = DEFAULT_PARAMETER_RANGES.get(key, (-1.0e12, 1.0e12))
    return float(max(lo, min(hi, float(value))))


def load_tuning_profile(path: str | Path | None) -> dict | None:
    """Load and validate a tuning profile JSON file."""
    if path is None:
        return None
    profile_path = Path(path).expanduser()
    with open(profile_path, "r", encoding="utf-8") as f:
        profile = json.load(f)
    validate_tuning_profile(profile)
    profile["_profile_path"] = str(profile_path)
    return profile


def validate_tuning_profile(profile: dict) -> None:
    if not isinstance(profile, dict):
        raise TuningProfileError("tuning profile must be a JSON object")
    if not str(profile.get("profile_id", "")).strip():
        raise TuningProfileError("tuning profile requires a non-empty profile_id")

    sections = (
        ("parameter_offsets", profile.get("parameter_offsets", {})),
        ("parameter_multipliers", profile.get("parameter_multipliers", {})),
        ("parameter_values", profile.get("parameter_values", {})),
    )
    for section_name, section in sections:
        if not isinstance(section, dict):
            raise TuningProfileError(f"{section_name} must be an object")
        unknown = sorted(set(section) - ALLOWED_TUNING_KEYS)
        if unknown:
            raise TuningProfileError(f"{section_name} contains unknown keys: {unknown}")
        for key, value in section.items():
            try:
                float(value)
            except (TypeError, ValueError) as exc:
                raise TuningProfileError(f"{section_name}.{key} must be numeric") from exc


def apply_tuning_profile(preset_values: dict, profile: dict | None) -> tuple[dict, dict]:
    """Return ``(new_preset_values, report)`` after applying a profile."""
    values = deepcopy(preset_values or {})
    if profile is None:
        return values, {"enabled": False}

    before = {key: float(values[key]) for key in sorted(values) if key in ALLOWED_TUNING_KEYS}
    applied = {}

    for key, value in profile.get("parameter_values", {}).items():
        if key in values:
            values[key] = _clamp(float(value), key)
            applied[key] = {"mode": "absolute", "value": float(value)}

    for key, multiplier in profile.get("parameter_multipliers", {}).items():
        if key in values:
            values[key] = _clamp(float(values[key]) * float(multiplier), key)
            applied[key] = {"mode": "multiplier", "value": float(multiplier)}

    for key, offset in profile.get("parameter_offsets", {}).items():
        if key in values:
            values[key] = _clamp(float(values[key]) + float(offset), key)
            applied[key] = {"mode": "offset", "value": float(offset)}

    after = {key: float(values[key]) for key in sorted(values) if key in ALLOWED_TUNING_KEYS}
    delta = {key: after[key] - before.get(key, after[key]) for key in after}
    return values, {
        "enabled": True,
        "profile_id": profile.get("profile_id"),
        "profile_path": profile.get("_profile_path"),
        "base": profile.get("base", "auto_acoustic"),
        "applied": applied,
        "before": before,
        "after": after,
        "delta": delta,
        "reason": profile.get("reason", []),
    }
