"""Deterministic closed-loop refinement for auto_acoustic routing.

Phase 2 of the auto_acoustic closed-loop upgrade (see
HANDOFF_auto_acoustic_closed_loop_upgrade.md).

This module does NOT replace auto_acoustic with a black-box model.  It applies
small, explainable, clipped parameter adjustments based on measurable quality
shortfalls, and records every change with a reason.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml

# ---------------------------------------------------------------------------
# Thresholds — loaded from config/refine_thresholds.yml with fallback.
# ---------------------------------------------------------------------------


def _load_refine_thresholds():
    """Load refine trigger thresholds from YAML, falling back to built-in defaults."""
    defaults = {
        "rear_presence_low_db": -7.5,
        "rear_presence_safe_vocal": 0.26,
        "bass_retention_low": 0.55,
        "bass_phase_safe": 0.38,
        "vocal_leakage_high": 0.26,
        "lowmid_mud_high": 0.42,
        "harshness_high": 0.42,
        "phase_risk_high": 0.42,
        "transient_smear_high": 0.28,
        "spatial_excess_high": 0.50,
    }
    config_path = Path(__file__).resolve().parent / "config" / "refine_thresholds.yml"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        if isinstance(data, dict) and isinstance(data.get("thresholds"), dict):
            defaults.update({k: float(v) for k, v in data["thresholds"].items()})
    except (FileNotFoundError, yaml.YAMLError, OSError, ValueError):
        pass
    return defaults


_THRESHOLDS = _load_refine_thresholds()

# Per-adjustment step sizes (at max_step=1.0).  These are deliberately small
# so a single refine pass never overshoots.
_STEP = {
    "side_rear": 0.05,
    "rear_floor_ratio": 0.010,
    "rear_master": 0.025,
    "bass_gain": 0.030,
    "bass_quad": 0.008,
    "amb_rear": 0.04,
    "air_rear": 0.03,
    "rear_air_gain": 0.035,
    "rear_highmid_gain": 0.040,
    "guard_scale": 0.050,
    "lowbody_rear": 0.030,
    "decorrelation": 0.030,
    "side_front": 0.02,
}

# Clip ranges (same as layer_router.py).  Refinement must not escape these.
_CLIP = {
    "side_front": (0.0, 1.8),
    "side_rear": (0.0, 1.8),
    "amb_rear": (0.0, 1.8),
    "air_rear": (0.0, 1.8),
    "rear_master": (0.0, 1.8),
    "decorrelation": (0.0, 1.8),
    "bass_quad": (0.0, 0.25),
    "lowbody_rear": (0.0, 0.60),
    "rear_floor_ratio": (0.0, 0.30),
    "max_rear_makeup": (1.0, 8.0),
    "rear_air_gain": (0.08, 1.0),
    "rear_highmid_gain": (0.18, 1.10),
    "bass_gain": (0.85, 1.30),
    "guard_scale": (0.55, 1.45),
}


def _clamp_param(name, value):
    lo, hi = _CLIP.get(name, (0.0, 1.8))
    return float(np.clip(value, lo, hi))


def _apply_delta(routing, key, delta, actions_log):
    """Apply a clamped delta and record the change if meaningful."""
    if abs(delta) < 1e-6:
        return
    old = float(routing.get(key, 0.0))
    new = _clamp_param(key, old + delta)
    actual = new - old
    if abs(actual) < 1e-6:
        return
    routing[key] = new
    actions_log.setdefault(key, 0.0)
    actions_log[key] += actual


def refine_auto_acoustic_routing(routing, analysis, metrics, max_step=1.0):
    """Apply one pass of deterministic closed-loop refinement.

    Parameters
    ----------
    routing : dict
        Current routing parameters (from auto_acoustic preset + layer_router).
    analysis : dict
        Audio analysis features (from streaming_analyzer).
    metrics : dict
        Quality metrics (from spatial_safety.compute_quality_metrics).
    max_step : float
        Aggressiveness clamp (0.0 = no change, 1.0 = full step).

    Returns
    -------
    refined_routing : dict
        New routing dictionary (shallow copy of input).
    actions : list of dict
        Structured explanations, one per refinement category applied.
    """
    step = float(np.clip(max_step, 0.0, 1.0))
    refined = dict(routing)  # shallow copy — we mutate values below
    actions = []

    # ---- read current metric values ----
    rear_front_db = float(metrics.get("rear_front_db", -6.0))
    vocal_leakage = float(metrics.get("rear_vocal_leakage_score", 0.25))
    sub150_retention = float(metrics.get("sub150_retention_score", 0.7))
    low_mid_mud = float(metrics.get("low_mid_mud_score", 0.40))
    harshness = float(metrics.get("high_harshness_score", 0.35))
    phase_risk = float(metrics.get("phase_correlation_risk", 0.35))
    transient_smear = float(metrics.get("transient_smear_score", 0.20))
    spatial_excess = float(metrics.get("spatial_excess_score", 0.40))

    # ---- Rule 1: rear presence too low (only if vocal is safe) ----
    if rear_front_db < _THRESHOLDS["rear_presence_low_db"] and vocal_leakage < _THRESHOLDS["rear_presence_safe_vocal"]:
        changes = {}
        _apply_delta(refined, "rear_floor_ratio",  _STEP["rear_floor_ratio"] * step, changes)
        _apply_delta(refined, "side_rear",          _STEP["side_rear"] * step, changes)
        _apply_delta(refined, "rear_master",        _STEP["rear_master"] * step, changes)
        if changes:
            actions.append({
                "reason": "rear_presence_low",
                "metric": round(rear_front_db, 2),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 2: bass retention too low ----
    if sub150_retention < _THRESHOLDS["bass_retention_low"]:
        changes = {}
        _apply_delta(refined, "bass_gain", _STEP["bass_gain"] * step, changes)
        # Only add bass_quad spread if phase is safe
        if phase_risk < _THRESHOLDS["bass_phase_safe"]:
            _apply_delta(refined, "bass_quad", _STEP["bass_quad"] * step, changes)
        if changes:
            actions.append({
                "reason": "bass_retention_low",
                "metric": round(sub150_retention, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 3: vocal leakage too high (counteract aggressive rear sends) ----
    if vocal_leakage > _THRESHOLDS["vocal_leakage_high"]:
        changes = {}
        _apply_delta(refined, "side_rear",          -_STEP["side_rear"] * step, changes)
        _apply_delta(refined, "amb_rear",           -_STEP["amb_rear"] * step, changes)
        _apply_delta(refined, "rear_highmid_gain",  -_STEP["rear_highmid_gain"] * step, changes)
        _apply_delta(refined, "guard_scale",         _STEP["guard_scale"] * step, changes)
        if changes:
            actions.append({
                "reason": "vocal_leakage_high",
                "metric": round(vocal_leakage, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 4: low-mid mud too high ----
    if low_mid_mud > _THRESHOLDS["lowmid_mud_high"]:
        changes = {}
        _apply_delta(refined, "lowbody_rear", -_STEP["lowbody_rear"] * step, changes)
        if changes:
            actions.append({
                "reason": "lowmid_mud_high",
                "metric": round(low_mid_mud, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 5: high-frequency harshness ----
    if harshness > _THRESHOLDS["harshness_high"]:
        changes = {}
        _apply_delta(refined, "air_rear",          -_STEP["air_rear"] * step, changes)
        _apply_delta(refined, "rear_air_gain",     -_STEP["rear_air_gain"] * step, changes)
        _apply_delta(refined, "rear_highmid_gain", -_STEP["rear_highmid_gain"] * step, changes)
        if changes:
            actions.append({
                "reason": "harshness_high",
                "metric": round(harshness, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 6: phase correlation risk ----
    if phase_risk > _THRESHOLDS["phase_risk_high"]:
        changes = {}
        _apply_delta(refined, "decorrelation", -_STEP["decorrelation"] * step, changes)
        _apply_delta(refined, "side_rear",     -_STEP["side_rear"] * 0.6 * step, changes)
        if changes:
            actions.append({
                "reason": "phase_risk_high",
                "metric": round(phase_risk, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 7: transient smear ----
    if transient_smear > _THRESHOLDS["transient_smear_high"]:
        changes = {}
        _apply_delta(refined, "decorrelation", -_STEP["decorrelation"] * step, changes)
        _apply_delta(refined, "guard_scale",    _STEP["guard_scale"] * 0.7 * step, changes)
        if changes:
            actions.append({
                "reason": "transient_smear_high",
                "metric": round(transient_smear, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    # ---- Rule 8: spatial excess (over-spatialized) ----
    if spatial_excess > _THRESHOLDS["spatial_excess_high"]:
        changes = {}
        _apply_delta(refined, "side_rear",   -_STEP["side_rear"] * 0.7 * step, changes)
        _apply_delta(refined, "amb_rear",    -_STEP["amb_rear"] * 0.6 * step, changes)
        _apply_delta(refined, "rear_master", -_STEP["rear_master"] * 0.6 * step, changes)
        if changes:
            actions.append({
                "reason": "spatial_excess_high",
                "metric": round(spatial_excess, 3),
                "changes": {k: round(v, 4) for k, v in changes.items()},
            })

    return refined, actions


def summarize_refine_actions(actions):
    """Return a human-readable one-liner per action for console / diagnostics."""
    lines = []
    for a in actions:
        reason = a.get("reason", "unknown")
        changes = a.get("changes")
        if changes is not None:
            metric = a.get("metric", "n/a")
            change_strs = [f"{k} {'+' if v > 0 else ''}{v:.3f}" for k, v in changes.items()]
            lines.append(f"[{reason}] metric={metric} → {', '.join(change_strs)}")
            continue
        if reason == "overshoot_guard_reverted":
            reverted = len(a.get("reverted_actions", []))
            lines.append(
                f"[{reason}] reverted {reverted} action(s); "
                f"spatialΔ={a.get('spatial_excess_delta', 0):.3f}, "
                f"harshΔ={a.get('high_harshness_delta', 0):.3f}, "
                f"mudΔ={a.get('low_mid_mud_delta', 0):.3f}"
            )
            continue
        lines.append(f"[{reason}]")
    return lines
