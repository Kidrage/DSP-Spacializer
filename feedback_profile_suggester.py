"""Suggest reviewable tuning profiles from evaluation records.

This module intentionally does not modify presets.py or any renderer code.  It
reads objective diagnostics plus human listening feedback and emits a small
external tuning profile that can be passed back into run_feedback_spatializer.py.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from tuning_profile import validate_tuning_profile


DEFAULT_PROFILE_ID = "feedback_suggested_quad_4p0_v1"

# Conservative per-iteration bounds.  These are offsets, not absolute values.
OFFSET_LIMITS = {
    "side_front": 0.08,
    "side_rear": 0.16,
    "amb_rear": 0.14,
    "air_rear": 0.08,
    "rear_master": 0.10,
    "decorrelation": 0.08,
    "rear_floor_ratio": 0.035,
    "max_rear_makeup": 0.9,
    "guard_scale": 0.16,
    "bass_gain": 0.08,
    "bass_quad": 0.03,
    "lowbody_rear": 0.12,
    "rear_air_gain": 0.10,
    "rear_highmid_gain": 0.10,
}


class FeedbackSuggestionError(ValueError):
    """Raised when feedback records cannot produce a safe suggestion."""


def _clamp_offset(key: str, value: float) -> float:
    limit = OFFSET_LIMITS.get(key, 0.0)
    return float(max(-limit, min(limit, float(value))))


def _add(offsets: dict[str, float], key: str, amount: float) -> None:
    offsets[key] += float(amount)


def _scores(record: dict) -> dict:
    subjective = record.get("subjective", {}) or {}
    return subjective.get("scores", {}) or {}


def _tags(record: dict) -> list[str]:
    subjective = record.get("subjective", {}) or {}
    return list(subjective.get("tags", []) or [])


def _quality_metrics(record: dict) -> dict:
    objective = record.get("objective", {}) or {}
    return objective.get("quality_metrics", {}) or {}


def _as_float(value, default=0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _collect_json_files(paths: Iterable[str | Path]) -> list[Path]:
    files: list[Path] = []
    for item in paths:
        path = Path(item).expanduser()
        if path.is_dir():
            files.extend(sorted(path.glob("*_evaluation_record.json")))
            files.extend(sorted(p for p in path.glob("*.json") if p.name not in {f.name for f in files}))
        elif path.exists():
            files.append(path)
        else:
            raise FileNotFoundError(f"Feedback input not found: {path}")
    unique: list[Path] = []
    seen = set()
    for path in files:
        resolved = str(path.resolve())
        if resolved not in seen:
            unique.append(path)
            seen.add(resolved)
    return unique


def load_evaluation_records(paths: Iterable[str | Path]) -> list[dict]:
    """Load evaluation records from files and/or directories."""
    records = []
    for path in _collect_json_files(paths):
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        if payload.get("record_format") != "dsp_spatial_feedback_v1":
            continue
        payload["_record_path"] = str(path)
        records.append(payload)
    return records


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(sum(values) / len(values))


def _rounded_offsets(offsets: dict[str, float], record_count: int) -> dict[str, float]:
    if record_count <= 0:
        return {}
    rounded = {}
    for key, value in sorted(offsets.items()):
        averaged = float(value) / float(record_count)
        averaged = _clamp_offset(key, averaged)
        if abs(averaged) >= 1.0e-6:
            rounded[key] = round(averaged, 6)
    return rounded


def suggest_tuning_profile(
    records: list[dict],
    profile_id: str = DEFAULT_PROFILE_ID,
    base: str = "auto_acoustic",
) -> dict:
    """Suggest a conservative profile from human/objective feedback records."""
    if not records:
        raise FeedbackSuggestionError("at least one evaluation record is required")

    offsets: dict[str, float] = defaultdict(float)
    tag_counts: Counter[str] = Counter()
    score_values: dict[str, list[float]] = defaultdict(list)
    metric_values: dict[str, list[float]] = defaultdict(list)
    rules_fired: Counter[str] = Counter()

    for record in records:
        tags = _tags(record)
        tag_counts.update(tags)
        scores = _scores(record)
        metrics = _quality_metrics(record)

        for key, value in scores.items():
            score_values[key].append(_as_float(value))
        for key, value in metrics.items():
            metric_values[key].append(_as_float(value))

        envelopment = _as_float(scores.get("envelopment"), 3.0)
        vocal_clarity = _as_float(scores.get("vocal_clarity"), 3.0)
        bass_weight = _as_float(scores.get("bass_weight"), 3.0)
        bass_tightness = _as_float(scores.get("bass_tightness"), 3.0)
        harshness = _as_float(scores.get("harshness"), 3.0)
        mud = _as_float(scores.get("mud"), 3.0)
        rear_naturalness = _as_float(scores.get("rear_naturalness"), 3.0)

        if "rear_too_weak" in tags or envelopment <= 2.5:
            _add(offsets, "rear_floor_ratio", 0.014)
            _add(offsets, "side_rear", 0.070)
            _add(offsets, "amb_rear", 0.030)
            _add(offsets, "rear_master", 0.030)
            rules_fired["increase_rear_presence"] += 1

        if "rear_too_loud" in tags or (envelopment >= 4.6 and rear_naturalness <= 2.8):
            _add(offsets, "side_rear", -0.060)
            _add(offsets, "amb_rear", -0.040)
            _add(offsets, "rear_master", -0.040)
            rules_fired["reduce_rear_dominance"] += 1

        if "vocal_blurry" in tags or "vocal_too_far" in tags or vocal_clarity <= 2.5:
            _add(offsets, "guard_scale", 0.070)
            _add(offsets, "side_front", -0.025)
            _add(offsets, "side_rear", -0.040)
            _add(offsets, "amb_rear", -0.030)
            _add(offsets, "rear_highmid_gain", -0.035)
            rules_fired["protect_front_vocal"] += 1

        if "harsh_rear" in tags or harshness >= 4.0:
            _add(offsets, "air_rear", -0.040)
            _add(offsets, "rear_air_gain", -0.055)
            _add(offsets, "rear_highmid_gain", -0.045)
            _add(offsets, "guard_scale", 0.030)
            rules_fired["soften_rear_highs"] += 1

        if "muddy_low_mid" in tags or mud >= 4.0:
            _add(offsets, "lowbody_rear", -0.055)
            _add(offsets, "amb_rear", -0.030)
            _add(offsets, "bass_quad", -0.008)
            rules_fired["reduce_low_mid_mud"] += 1

        if "bass_weak" in tags or bass_weight <= 2.5:
            _add(offsets, "bass_gain", 0.040)
            _add(offsets, "bass_quad", 0.010)
            rules_fired["increase_bass_weight"] += 1

        if "bass_boomy" in tags or bass_tightness <= 2.5:
            _add(offsets, "bass_quad", -0.012)
            _add(offsets, "lowbody_rear", -0.030)
            rules_fired["tighten_bass"] += 1

        rear_front_db = _as_float(metrics.get("rear_front_db"), -9.0)
        if rear_front_db < -12.0 and envelopment < 4.0:
            _add(offsets, "rear_floor_ratio", 0.008)
            _add(offsets, "rear_master", 0.020)
            rules_fired["objective_rear_under_target"] += 1

        if _as_float(metrics.get("rear_vocal_leakage_score"), 0.0) > 0.32:
            _add(offsets, "guard_scale", 0.050)
            _add(offsets, "rear_highmid_gain", -0.030)
            _add(offsets, "side_rear", -0.020)
            rules_fired["objective_vocal_leakage"] += 1

        if _as_float(metrics.get("high_harshness_score"), 0.0) > 0.45:
            _add(offsets, "air_rear", -0.030)
            _add(offsets, "rear_air_gain", -0.040)
            rules_fired["objective_high_harshness"] += 1

        if _as_float(metrics.get("low_mid_mud_score"), 0.0) > 0.45:
            _add(offsets, "lowbody_rear", -0.040)
            _add(offsets, "amb_rear", -0.020)
            rules_fired["objective_low_mid_mud"] += 1

        over = (record.get("objective", {}) or {}).get("over_protection", {}) or {}
        if over.get("over_protection_warning") is True:
            _add(offsets, "rear_master", 0.020)
            _add(offsets, "max_rear_makeup", 0.250)
            rules_fired["objective_over_protection"] += 1

    parameter_offsets = _rounded_offsets(offsets, len(records))
    if not parameter_offsets:
        parameter_offsets = {"rear_master": 0.0}
        rules_fired["no_change_suggested"] += 1

    mean_scores = {key: round(_mean(values), 4) for key, values in sorted(score_values.items()) if _mean(values) is not None}
    objective_means = {key: round(_mean(values), 6) for key, values in sorted(metric_values.items()) if _mean(values) is not None}

    reason = [
        f"records={len(records)}",
        f"top_tags={dict(tag_counts.most_common(8))}",
        f"rules_fired={dict(rules_fired)}",
    ]
    profile = {
        "profile_id": str(profile_id),
        "base": str(base),
        "created_by": "feedback_profile_suggester_v1",
        "record_count": len(records),
        "parameter_offsets": parameter_offsets,
        "evidence": {
            "tag_counts": dict(sorted(tag_counts.items())),
            "mean_scores": mean_scores,
            "objective_means": objective_means,
            "rules_fired": dict(sorted(rules_fired.items())),
            "record_paths": [record.get("_record_path") for record in records if record.get("_record_path")],
        },
        "reason": reason,
    }
    validate_tuning_profile(profile)
    return profile


def write_suggested_profile(profile: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")
