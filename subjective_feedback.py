"""Subjective listening feedback records for spatialization evaluation."""

from __future__ import annotations

import json
from pathlib import Path


SCORE_KEYS = {
    "envelopment",
    "front_focus",
    "vocal_clarity",
    "bass_weight",
    "bass_tightness",
    "rear_naturalness",
    "harshness",
    "mud",
    "depth",
    "width",
    "mono_safety",
    "overall_preference",
}

REQUIRED_SCORE_KEYS = {"overall_preference"}


class SubjectiveFeedbackError(ValueError):
    """Raised when a subjective feedback record is malformed."""


def load_subjective_score(path: str | Path | None) -> dict | None:
    """Load and validate a subjective score JSON file."""
    if path is None:
        return None
    score_path = Path(path).expanduser()
    with open(score_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    validate_subjective_score(payload)
    payload["_score_path"] = str(score_path)
    return payload


def find_subjective_score(subjective_dir: str | Path | None, input_path: str | Path) -> Path | None:
    """Find a per-song score file by stem."""
    if subjective_dir is None:
        return None
    directory = Path(subjective_dir).expanduser()
    stem = Path(input_path).stem
    for name in (f"{stem}_subjective_score.json", f"{stem}.json"):
        candidate = directory / name
        if candidate.exists():
            return candidate
    return None


def validate_subjective_score(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise SubjectiveFeedbackError("subjective score must be a JSON object")
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise SubjectiveFeedbackError("subjective score requires a scores object")
    missing = sorted(REQUIRED_SCORE_KEYS - set(scores))
    if missing:
        raise SubjectiveFeedbackError(f"missing required score keys: {missing}")
    unknown = sorted(set(scores) - SCORE_KEYS)
    if unknown:
        raise SubjectiveFeedbackError(f"unknown score keys: {unknown}")
    for key, value in scores.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise SubjectiveFeedbackError(f"score {key} must be numeric") from exc
        if numeric < 1.0 or numeric > 5.0:
            raise SubjectiveFeedbackError(f"score {key} outside 1..5")
    tags = payload.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise SubjectiveFeedbackError("tags must be a list of strings")


def summarize_subjective_score(payload: dict | None) -> dict:
    if payload is None:
        return {"enabled": False}
    scores = payload.get("scores", {})
    average = sum(float(value) for value in scores.values()) / max(len(scores), 1)
    return {
        "enabled": True,
        "score_path": payload.get("_score_path"),
        "song_id": payload.get("song_id"),
        "render_id": payload.get("render_id"),
        "overall_preference": float(scores.get("overall_preference", 0.0)),
        "mean_score": float(average),
        "scores": dict(scores),
        "tags": list(payload.get("tags", [])),
        "notes": payload.get("notes", ""),
    }


def build_evaluation_record(diagnostics: dict, subjective_score: dict | None) -> dict:
    """Combine objective diagnostics and human listening feedback."""
    return {
        "record_format": "dsp_spatial_feedback_v1",
        "input_file": diagnostics.get("input_file"),
        "preset": diagnostics.get("preset"),
        "preset_mode_used": diagnostics.get("preset_mode_used"),
        "output_paths": diagnostics.get("output_paths", {}),
        "objective": {
            "quality_metrics": diagnostics.get("quality_metrics", {}),
            "quality_risk": diagnostics.get("quality_risk", {}),
            "quality_delta": diagnostics.get("quality_delta", {}),
            "over_protection": diagnostics.get("over_protection", {}),
            "rear_to_front_db": diagnostics.get("rear_to_front_db"),
            "peak": diagnostics.get("peak"),
        },
        "subjective": summarize_subjective_score(subjective_score),
        "tuning_profile": diagnostics.get("tuning_profile", {"enabled": False}),
    }


def write_evaluation_record(record: dict, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
