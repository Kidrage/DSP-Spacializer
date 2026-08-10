"""Listener threshold calibration for spatial quality metrics.

Phase 5A of the auto_acoustic closed-loop upgrade (see
HANDOFF_auto_acoustic_closed_loop_upgrade.md).

Converts structured listening feedback into calibrated metric thresholds,
separating perceptual boundary discovery (5A) from aesthetic preference (5B).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import yaml


# ---------------------------------------------------------------------------
# Tag → metric mapping: which listening tag calibrates which metric
# ---------------------------------------------------------------------------

TAG_METRIC_MAP = {
    "highs_too_harsh":       {"metric": "harshness_score",       "direction": "lower"},
    "lowmid_muddy":          {"metric": "lowmid_mud_score",      "direction": "lower"},
    "vocal_leaks_to_rear":   {"metric": "vocal_leakage_score",   "direction": "lower"},
    "phase_weird":           {"metric": "phase_risk_score",      "direction": "lower"},
    "transient_smeared":     {"metric": "transient_smear_score", "direction": "lower"},
    "rear_too_weak":         {"metric": "rear_presence_score",   "direction": "raise_min"},
    "rear_too_strong":       {"metric": "rear_presence_score",   "direction": "lower_max"},
    "bass_too_light":        {"metric": "bass_retention_score",  "direction": "raise_min"},
    "bass_too_boomy":        {"metric": "bass_retention_score",  "direction": "lower_max"},
    "space_not_wide_enough": {"metric": "spatial_excess_score",  "direction": "raise"},
    "rear_too_dark":         {"metric": "harshness_score",       "direction": "raise"},
}


# ---------------------------------------------------------------------------
# Confidence levels
# ---------------------------------------------------------------------------

def _confidence_level(evidence_count: int) -> tuple[str, float]:
    """Return (level, scalar) for the given evidence count."""
    if evidence_count >= 10:
        return "high", 0.85
    if evidence_count >= 6:
        return "medium", 0.62
    if evidence_count >= 3:
        return "low", 0.40
    return "candidate", 0.15


# ---------------------------------------------------------------------------
# collect_threshold_evidence
# ---------------------------------------------------------------------------

def collect_threshold_evidence(
    evaluation_records: list[dict],
    subjective_feedback: list[dict],
) -> list[dict]:
    """Extract threshold-relevant evidence from evaluation records and feedback.

    Parameters
    ----------
    evaluation_records : list[dict]
        Output from run_feedback_spatializer.py (contains quality_metrics,
        auto_acoustic_info, listener_tags, etc.).
    subjective_feedback : list[dict]
        Structured listening feedback with metric_observation, listener_tags,
        listener_boundary_note, suggested_threshold_adjustment.

    Returns
    -------
    evidence : list[dict]
        One entry per usable observation.
    """
    evidence = []

    # Process explicit feedback records first (richer structure)
    for fb in subjective_feedback:
        tags = fb.get("listener_tags", [])
        if not tags:
            continue
        metric_obs = fb.get("metric_observation", {})
        boundary_note = fb.get("listener_boundary_note", "")
        suggested = fb.get("suggested_threshold_adjustment", {})

        for tag in tags:
            mapping = TAG_METRIC_MAP.get(tag)
            if mapping is None:
                continue
            metric_name = mapping["metric"]
            direction = mapping["direction"]

            # Extract the observed metric value if available
            obs_value = metric_obs.get(metric_name)

            entry = {
                "track_id": fb.get("track_id", "unknown"),
                "candidate_id": fb.get("candidate_id", "unknown"),
                "tag": tag,
                "metric_name": metric_name,
                "direction": direction,
                "observed_value": obs_value,
                "boundary_note": boundary_note,
            }
            if suggested:
                entry["suggested_adjustment"] = suggested
            evidence.append(entry)

    # Process evaluation records (auto-generated from feedback_spatializer)
    for rec in evaluation_records:
        tags = rec.get("listener_tags", [])
        if not tags:
            continue
        qm = rec.get("quality_metrics", {})

        for tag in tags:
            mapping = TAG_METRIC_MAP.get(tag)
            if mapping is None:
                continue
            metric_name = mapping["metric"]
            direction = mapping["direction"]

            # Map quality_metrics keys to calibration metric names
            qm_key_map = {
                "harshness_score":       "high_harshness_score",
                "lowmid_mud_score":      "low_mid_mud_score",
                "vocal_leakage_score":   "rear_vocal_leakage_score",
                "phase_risk_score":      "phase_correlation_risk",
                "transient_smear_score": "transient_smear_score",
                "rear_presence_score":   "rear_front_db",
                "bass_retention_score":  "sub150_retention_score",
                "spatial_excess_score":  "spatial_excess_score",
            }
            qm_key = qm_key_map.get(metric_name, metric_name)
            obs_value = qm.get(qm_key)

            evidence.append({
                "track_id": rec.get("input_file", rec.get("track_id", "unknown")),
                "candidate_id": rec.get("candidate_id", "unknown"),
                "tag": tag,
                "metric_name": metric_name,
                "direction": direction,
                "observed_value": obs_value,
                "boundary_note": f"Auto-generated from evaluation record. "
                                 f"Observed {qm_key}={obs_value}.",
            })

    return evidence


# ---------------------------------------------------------------------------
# suggest_threshold_calibration
# ---------------------------------------------------------------------------

def suggest_threshold_calibration(
    evidence: list[dict],
    current_thresholds: dict,
    min_evidence_count: int = 3,
) -> dict:
    """Analyze evidence and suggest threshold calibration changes.

    Parameters
    ----------
    evidence : list[dict]
        Output from collect_threshold_evidence().
    current_thresholds : dict
        Current quality thresholds (from load_quality_thresholds()).
    min_evidence_count : int
        Minimum consistent examples before suggesting a change.

    Returns
    -------
    calibration : dict
        Suggested calibration entries, keyed by metric_name.
        Empty dict if no suggestions meet the evidence threshold.
    """
    # Group evidence by metric_name + direction
    groups: dict[tuple[str, str], list[dict]] = {}
    for e in evidence:
        key = (e["metric_name"], e["direction"])
        groups.setdefault(key, []).append(e)

    suggestions = {}

    for (metric_name, direction), items in groups.items():
        n = len(items)
        if n < min_evidence_count:
            continue

        level, confidence = _confidence_level(n)
        if level == "candidate":
            # Still below min_evidence_count for action, but note as candidate
            continue

        # Collect observed values for this metric
        obs_values = [it["observed_value"] for it in items if it["observed_value"] is not None]
        track_ids = [it["track_id"] for it in items]

        # Determine suggested threshold adjustment based on direction
        suggestion = _compute_suggestion(
            metric_name, direction, obs_values, current_thresholds, items
        )

        if suggestion:
            suggestion["confidence"] = confidence
            suggestion["evidence_count"] = n
            suggestion["confidence_level"] = level
            suggestion["source_tracks"] = track_ids
            suggestions[metric_name] = suggestion

    return suggestions


def _compute_suggestion(metric_name, direction, obs_values, current_thresholds, items):
    """Compute a specific threshold suggestion for one metric."""
    # Extract current threshold from the thresholds dict
    current = _get_current_threshold_for_metric(metric_name, current_thresholds)

    if direction in ("lower",):
        # Listener finds this offensive at LOWER values than current threshold
        # → lower the warning/danger threshold
        if obs_values:
            avg_obs = sum(obs_values) / len(obs_values)
            # Warning: slightly below the average observation where listener complained
            new_warning = round(max(0.05, avg_obs - 0.05), 2)
            new_danger = round(max(0.10, avg_obs + 0.08), 2)
        else:
            # No observed values — shift down conservatively
            new_warning = round(current.get("warning", 0.30) * 0.80, 2)
            new_danger = round(current.get("danger", 0.45) * 0.85, 2)

        boundary_notes = [it.get("boundary_note", "") for it in items if it.get("boundary_note")]
        return {
            "warning": new_warning,
            "danger": new_danger,
            "reason": f"Listener reports {metric_name} issues below current threshold. "
                      + (" ".join(boundary_notes[:2]) if boundary_notes
                         else f"Observed complaints at avg={avg_obs:.2f}." if obs_values
                         else "No specific observations recorded."),
        }

    if direction in ("raise_min",):
        # Listener finds this lacking even when metrics say "safe"
        # → raise the minimum acceptable threshold
        if obs_values:
            avg_obs = sum(obs_values) / len(obs_values)
            new_min = round(min(0.95, avg_obs + 0.10), 2)
        else:
            new_min = round(current.get("min", 0.50) + 0.08, 2)
        return {
            "min": new_min,
            "reason": (
                f"Listener reports {metric_name} too low even when metrics suggest 'safe'. "
                f"Raising minimum threshold."
            ),
        }

    if direction in ("lower_max",):
        # Listener finds this excessive even when metrics say "safe"
        # → lower the maximum acceptable threshold
        if obs_values:
            avg_obs = sum(obs_values) / len(obs_values)
            new_max = round(max(0.10, avg_obs - 0.10), 2)
        else:
            new_max = round(current.get("max", 0.80) - 0.10, 2)
        return {
            "max": new_max,
            "reason": (
                f"Listener reports {metric_name} too high even when metrics suggest 'safe'. "
                f"Lowering maximum threshold."
            ),
        }

    if direction == "raise":
        # Listener wants MORE of this (e.g., space_not_wide_enough)
        # → raise the max acceptable threshold
        new_max = round(min(0.95, current.get("max", 0.60) + 0.08), 2)
        return {
            "max": new_max,
            "reason": f"Listener prefers more {metric_name} than current threshold allows.",
        }

    return None


def _get_current_threshold_for_metric(metric_name, thresholds):
    """Extract the current threshold value(s) for a given metric name."""
    global_thresh = thresholds.get("global", {})

    metric_to_key = {
        "harshness_score":       "high_harshness_score_max",
        "lowmid_mud_score":      "low_mid_mud_score_max",
        "vocal_leakage_score":   "rear_vocal_leakage_score_max",
        "phase_risk_score":      "phase_correlation_risk_max",
        "transient_smear_score": "transient_smear_score_max",
        "rear_presence_score":   "rear_front_db_max",
        "bass_retention_score":  "sub150_retention_score_min",
        "spatial_excess_score":  "spatial_excess_score_max",
    }

    key = metric_to_key.get(metric_name)
    if key:
        val = global_thresh.get(key)
        if val is not None:
            return {"warning": float(val) * 0.75, "danger": float(val)}

    return {"warning": 0.30, "danger": 0.45}


# ---------------------------------------------------------------------------
# apply_threshold_calibration
# ---------------------------------------------------------------------------

def apply_threshold_calibration(
    base_thresholds: dict,
    calibration: dict,
    target_style: str | None = None,
    output_mode: str | None = None,
) -> dict:
    """Apply listener calibration on top of base thresholds.

    Parameters
    ----------
    base_thresholds : dict
        Output from load_quality_thresholds().
    calibration : dict
        Calibration entries keyed by metric_name (from suggest_threshold_calibration()
        or loaded from config/listener_threshold_calibration.yml).
    target_style : str or None
        If set, also apply target-style-specific overrides.
    output_mode : str or None
        If set, also apply output-mode-specific overrides.

    Returns
    -------
    resolved : dict
        New thresholds dict with calibration applied.
    """
    import copy
    resolved = copy.deepcopy(base_thresholds)

    # Metric → threshold key mapping (same as _apply_calibration_to_thresholds)
    _CAL_MAP = {
        "harshness_score":       "high_harshness_score_max",
        "vocal_leakage_score":   "rear_vocal_leakage_score_max",
        "lowmid_mud_score":      "low_mid_mud_score_max",
        "phase_risk_score":      "phase_correlation_risk_max",
        "transient_smear_score": "transient_smear_score_max",
        "rear_presence_score":   "rear_front_db_max",
        "bass_retention_score":  "sub150_retention_score_min",
        "spatial_excess_score":  "spatial_excess_score_max",
    }

    for metric_name, cal in calibration.items():
        if not isinstance(cal, dict):
            continue
        threshold_key = _CAL_MAP.get(metric_name)
        if threshold_key is None:
            continue

        # Apply danger threshold to global
        danger = cal.get("danger")
        if danger is not None:
            resolved.setdefault("global", {})[threshold_key] = float(danger)

        # Also apply to matching preset overrides
        for preset in resolved.get("presets", {}):
            if threshold_key in resolved["presets"][preset]:
                if danger is not None:
                    resolved["presets"][preset][threshold_key] = float(danger)

    return resolved


# ---------------------------------------------------------------------------
# explain_threshold_changes
# ---------------------------------------------------------------------------

def explain_threshold_changes(
    old_thresholds: dict,
    new_thresholds: dict,
    evidence: list[dict],
) -> list[dict]:
    """Generate human-readable explanations for every threshold change.

    Returns a list of action dicts suitable for diagnostics.
    """
    explanations = []
    old_global = old_thresholds.get("global", {})
    new_global = new_thresholds.get("global", {})

    # Reverse mapping for display names
    _KEY_LABELS = {
        "high_harshness_score_max":   "harshness_score",
        "low_mid_mud_score_max":      "lowmid_mud_score",
        "rear_vocal_leakage_score_max": "vocal_leakage_score",
        "phase_correlation_risk_max": "phase_risk_score",
        "transient_smear_score_max":  "transient_smear_score",
        "rear_front_db_max":          "rear_presence_score",
        "sub150_retention_score_min": "bass_retention_score",
        "spatial_excess_score_max":   "spatial_excess_score",
    }

    for key, label in _KEY_LABELS.items():
        old_val = old_global.get(key)
        new_val = new_global.get(key)
        if old_val is None or new_val is None:
            continue
        if abs(old_val - new_val) < 1e-6:
            continue

        # Find matching evidence
        related = [e for e in evidence if e.get("metric_name") == label]
        track_ids = list({e.get("track_id", "?") for e in related})
        n = len(related)

        explanations.append({
            "type": "threshold_calibration",
            "metric": label,
            "old_value": old_val,
            "new_value": new_val,
            "reason": (
                f"Listener calibration: {label} threshold changed from {old_val} to {new_val}. "
                f"Based on {n} evidence record(s)."
            ),
            "confidence": related[0].get("confidence", 0.0) if related else 0.0,
            "evidence_count": n,
            "source_tracks": track_ids,
        })

    return explanations


# ---------------------------------------------------------------------------
# Calibration history (JSONL)
# ---------------------------------------------------------------------------

_HISTORY_PATH = None


def _get_history_path():
    global _HISTORY_PATH
    if _HISTORY_PATH is None:
        _HISTORY_PATH = (
            Path(__file__).resolve().parent
            / "config"
            / "threshold_calibration_history.jsonl"
        )
    return _HISTORY_PATH


def write_calibration_history_entry(
    metric_name: str,
    old_value: float,
    new_value: float,
    confidence: float,
    evidence_count: int,
    source_tracks: list[str],
    reason: str,
):
    """Append one calibration change to the JSONL history file."""
    entry = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "threshold_name": metric_name,
        "old_value": old_value,
        "new_value": new_value,
        "confidence": confidence,
        "evidence_count": evidence_count,
        "source_tracks": source_tracks,
        "reason": reason,
    }
    path = _get_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_calibration_history() -> list[dict]:
    """Read all calibration history entries."""
    path = _get_history_path()
    if not path.exists():
        return []
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return entries


def save_calibration_file(calibration: dict):
    """Persist the calibration dict to config/listener_threshold_calibration.yml."""
    path = (
        Path(__file__).resolve().parent
        / "config"
        / "listener_threshold_calibration.yml"
    )
    data = {
        "version": 1,
        "listener_id": "default",
        "playback_context": "four_speaker_reference",
        "calibrated_thresholds": calibration,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
