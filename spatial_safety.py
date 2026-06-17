"""Safety guards and objective quality metrics for stereo -> 4.0 spatial beds.

This module sits between the creative spatial renderer and final mastering
stages.  It does not try to replace calibration, speaker-array rendering, or
AI source separation.  Instead it provides deterministic guardrails for the
prototype DSP spatializer:

- estimate whether rear channels contain too much center/vocal-like material;
- reduce rear transient smear and low-mid mud when risk is high;
- tame excessive rear high-frequency harshness;
- report mono fold-down and phase/correlation risk for A/B debugging.

All scores are normalized to roughly ``0.0 = safe`` and ``1.0 = risky``.
They are intentionally conservative heuristics so that batch runs can identify
problem songs before subjective listening.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from dsp_utils import EPS, band_split, db, rms
from streaming_analyzer import transient_density


DEFAULT_QUALITY_THRESHOLDS = {
    "global": {
        "rear_front_db_max": -5.0,
        "rear_vocal_leakage_score_max": 0.35,
        "sub150_retention_score_min": 0.75,
        "low_mid_mud_score_max": 0.45,
        "phase_correlation_risk_max": 0.40,
        "transient_smear_score_max": 0.35,
        "high_harshness_score_max": 0.45,
        "mono_fold_down_delta_db_abs_max": 1.5,
        "spatial_excess_score_max": 0.60,
    },
    "presets": {
        "auto_acoustic": {
            "rear_front_db_max": -5.5,
            "rear_vocal_leakage_score_max": 0.32,
            "spatial_excess_score_max": 0.58,
        },
        "folk_vocal": {
            "rear_front_db_max": -8.0,
            "rear_vocal_leakage_score_max": 0.25,
            "transient_smear_score_max": 0.25,
        },
        "epic_orchestral_depth": {
            "rear_front_db_max": -4.5,
            "low_mid_mud_score_max": 0.50,
            "spatial_excess_score_max": 0.70,
        },
        "bass_dry_wide": {
            "sub150_retention_score_min": 0.85,
            "phase_correlation_risk_max": 0.35,
        },
        "wide_smooth": {
            "spatial_excess_score_max": 0.55,
        },
    },
}

_THRESHOLD_RULES = {
    "rear_front_db_max": ("rear_front_db", "max"),
    "rear_vocal_leakage_score_max": ("rear_vocal_leakage_score", "max"),
    "sub150_retention_score_min": ("sub150_retention_score", "min"),
    "low_mid_mud_score_max": ("low_mid_mud_score", "max"),
    "phase_correlation_risk_max": ("phase_correlation_risk", "max"),
    "transient_smear_score_max": ("transient_smear_score", "max"),
    "high_harshness_score_max": ("high_harshness_score", "max"),
    "mono_fold_down_delta_db_abs_max": ("mono_fold_down_delta_db", "abs_max"),
    "spatial_excess_score_max": ("spatial_excess_score", "max"),
}


def _copy_default_thresholds():
    return json.loads(json.dumps(DEFAULT_QUALITY_THRESHOLDS))


def load_quality_thresholds(path=None):
    """Load quality thresholds, falling back to built-in defaults if needed."""
    if path is None:
        path = Path(__file__).with_name("spatial_quality_thresholds.json")
    else:
        path = Path(path).expanduser()

    defaults = _copy_default_thresholds()
    try:
        with open(path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return defaults

    if not isinstance(loaded, dict):
        return defaults

    merged = defaults
    if isinstance(loaded.get("global"), dict):
        merged["global"].update(loaded["global"])
    if isinstance(loaded.get("presets"), dict):
        for preset, preset_thresholds in loaded["presets"].items():
            if isinstance(preset_thresholds, dict):
                merged["presets"].setdefault(preset, {}).update(preset_thresholds)
    return merged


def get_thresholds_for_preset(thresholds, preset_name):
    """Return global thresholds overlaid with optional preset-specific values."""
    thresholds = thresholds or _copy_default_thresholds()
    selected = dict(thresholds.get("global", {}))
    if preset_name and isinstance(thresholds.get("presets"), dict):
        selected.update(thresholds["presets"].get(preset_name, {}))
    return selected


def _risk_status(value, threshold, mode):
    value = float(value)
    threshold = float(threshold)
    judged = abs(value) if mode == "abs_max" else value
    if mode == "min":
        warn_boundary = threshold * 1.08 if threshold >= 0 else threshold + abs(threshold) * 0.08
        if judged < threshold:
            severity = (threshold - judged) / (abs(threshold) + EPS)
            return "fail" if severity >= 0.15 else "warn", severity
        if judged <= warn_boundary:
            return "warn", max(0.0, (warn_boundary - judged) / (abs(threshold) + EPS)) * 0.5
        return "pass", 0.0

    warn_boundary = threshold * 0.90 if threshold >= 0 else threshold - abs(threshold) * 0.10
    if judged > threshold:
        severity = (judged - threshold) / (abs(threshold) + EPS)
        return "fail" if severity >= 0.15 else "warn", severity
    if judged >= warn_boundary:
        return "warn", max(0.0, (judged - warn_boundary) / (abs(threshold) + EPS)) * 0.5
    return "pass", 0.0


def classify_quality_risks(metrics, thresholds, preset_name=None):
    """Classify metric values against global/preset quality thresholds."""
    active = get_thresholds_for_preset(thresholds, preset_name)
    risks = {}
    weighted_scores = []

    for threshold_key, (metric_key, mode) in _THRESHOLD_RULES.items():
        if threshold_key not in active or metric_key not in metrics:
            continue
        value = float(metrics[metric_key])
        threshold = float(active[threshold_key])
        status, severity = _risk_status(value, threshold, mode)
        if status != "pass":
            risks[metric_key] = {
                "value": value,
                "threshold": threshold,
                "status": status,
            }
        weighted_scores.append(1.0 if status == "fail" else (0.45 if status == "warn" else 0.0))
        if severity > 0 and status != "pass":
            weighted_scores[-1] = min(1.0, weighted_scores[-1] + min(severity, 1.0) * 0.25)

    if any(item["status"] == "fail" for item in risks.values()):
        overall_status = "fail"
    elif any(item["status"] == "warn" for item in risks.values()):
        overall_status = "warn"
    else:
        overall_status = "pass"

    overall_risk_score = float(np.clip(np.mean(weighted_scores) if weighted_scores else 0.0, 0.0, 1.0))
    return {
        "overall_status": overall_status,
        "overall_risk_score": overall_risk_score,
        "risks": risks,
    }


def compare_quality_metrics(before, after):
    """Return per-metric deltas as ``after - before``."""
    before = before or {}
    after = after or {}
    keys = sorted(set(before.keys()) & set(after.keys()))
    deltas = {}
    for key in keys:
        try:
            deltas[f"{key}_delta"] = float(after[key]) - float(before[key])
        except (TypeError, ValueError):
            continue
    return deltas


def detect_over_protection(before, after):
    """Detect if safety reduced rear spatial energy too aggressively."""
    before = before or {}
    after = after or {}
    reasons = []

    if "rear_front_db" in before and "rear_front_db" in after:
        delta = float(after["rear_front_db"]) - float(before["rear_front_db"])
        if delta < -4.0:
            reasons.append(f"rear_front_db dropped {abs(delta):.2f} dB (> 4 dB)")

    if "spatial_excess_score" in before and "spatial_excess_score" in after:
        delta = float(after["spatial_excess_score"]) - float(before["spatial_excess_score"])
        if delta < -0.35:
            reasons.append(f"spatial_excess_score dropped {abs(delta):.2f} (> 0.35)")

    if "rear_front_rms_ratio" in before and "rear_front_rms_ratio" in after:
        b = float(before["rear_front_rms_ratio"])
        a = float(after["rear_front_rms_ratio"])
        if b > EPS and (b - a) / b > 0.45:
            reasons.append(f"rear_front_rms_ratio dropped {(b - a) / b:.0%} (> 45%)")

    if "rear_lr_correlation" in before and "rear_lr_correlation" in after:
        b = float(before["rear_lr_correlation"])
        a = float(after["rear_lr_correlation"])
        if a > 0.88 and (a - b) > 0.18:
            reasons.append("rear_lr_correlation became too high; rear diffusion may be over-compressed")

    return {
        "over_protection_warning": bool(reasons),
        "reasons": reasons,
    }


def _clip01(x):
    return float(np.clip(float(x), 0.0, 1.0))


def _safe_corr(x, y):
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    n = min(len(x), len(y))
    if n == 0:
        return 0.0
    x = x[:n] - float(np.mean(x[:n]))
    y = y[:n] - float(np.mean(y[:n]))
    return float(np.mean(x * y) / np.sqrt(np.mean(x * x) * np.mean(y * y) + EPS))


def _mono_fold_down(four_ch):
    four_ch = np.asarray(four_ch, dtype=np.float32)
    return np.mean(four_ch, axis=1).astype(np.float32)


def _mono_fold_down_front_norm(four_ch):
    four_ch = np.asarray(four_ch, dtype=np.float32)
    return (0.5 * np.sum(four_ch, axis=1)).astype(np.float32)


def _mono_front_only(four_ch):
    four_ch = np.asarray(four_ch, dtype=np.float32)
    return (0.5 * (four_ch[:, 0] + four_ch[:, 1])).astype(np.float32)


def _attenuate_rear_band(four_ch, sample_rate, band_name, gain):
    """Apply a rear-only band attenuation while preserving other bands."""
    gain = float(np.clip(gain, 0.0, 1.0))
    if gain >= 0.999:
        return four_ch
    out = np.asarray(four_ch, dtype=np.float32).copy()
    for ch in (2, 3):
        bands = band_split(out[:, ch], sample_rate)
        bands[band_name] *= gain
        out[:, ch] = sum(bands.values())
    return out.astype(np.float32)


def compute_quality_metrics(left, right, four_ch, sample_rate, analysis=None):
    """Return objective diagnostics for a rendered 4.0 spatial bed.

    Parameters
    ----------
    left, right : np.ndarray
        Original stereo input.
    four_ch : np.ndarray
        Rendered 4-channel audio in ``[LF, RF, LB, RB]`` order.
    sample_rate : int
        Sample rate in Hz.
    analysis : dict, optional
        Existing analyzer output; used only to enrich risk estimation.
    """
    analysis = analysis or {}
    left = np.asarray(left, dtype=np.float32)
    right = np.asarray(right, dtype=np.float32)
    four_ch = np.asarray(four_ch, dtype=np.float32)

    front = 0.5 * (four_ch[:, 0] + four_ch[:, 1])
    rear = 0.5 * (four_ch[:, 2] + four_ch[:, 3])
    rear_side = 0.5 * (four_ch[:, 2] - four_ch[:, 3])
    input_mid = 0.70710678 * (left + right)
    input_side = 0.70710678 * (left - right)
    input_mono = 0.5 * (left + right)
    output_mono = _mono_fold_down(four_ch)
    output_mono_front_norm = _mono_fold_down_front_norm(four_ch)
    output_front_only = _mono_front_only(four_ch)

    front_rms = rms(four_ch[:, :2])
    rear_rms = rms(four_ch[:, 2:])
    rear_front_ratio = rear_rms / (front_rms + EPS)

    in_bands = band_split(input_mid, sample_rate)
    side_bands = band_split(input_side, sample_rate)
    rear_bands = band_split(rear, sample_rate)

    # Center/vocal leakage: rear mid/high-mid correlated with input center and
    # not sufficiently explained by stereo side material.
    mid_corr = abs(_safe_corr(rear_bands["mid"], in_bands["mid"]))
    highmid_corr = abs(_safe_corr(rear_bands["high_mid"], in_bands["high_mid"]))
    mid_rear_ratio = rms(rear_bands["mid"]) / (rms(in_bands["mid"]) + EPS)
    highmid_rear_ratio = rms(rear_bands["high_mid"]) / (rms(in_bands["high_mid"]) + EPS)
    side_explanation = rms(side_bands["mid"]) / (rms(in_bands["mid"]) + rms(side_bands["mid"]) + EPS)
    vocal_hint = float(analysis.get("center_dominance", 0.0))
    rear_vocal_leakage_score = _clip01(
        0.34 * mid_corr
        + 0.28 * highmid_corr
        + 0.18 * np.clip(mid_rear_ratio / 0.34, 0.0, 1.0)
        + 0.12 * np.clip(highmid_rear_ratio / 0.30, 0.0, 1.0)
        + 0.08 * vocal_hint
        - 0.18 * side_explanation
    )

    sub150_in = rms(band_split(input_mono, sample_rate)["bass"])
    sub150_out = rms(band_split(_mono_fold_down(four_ch[:, :2]), sample_rate)["bass"])
    sub150_retention_ratio = float(sub150_out / (sub150_in + EPS))
    sub150_retention_score = _clip01(1.0 - abs(sub150_retention_ratio - 1.0) / 0.35)

    lowmid_rear_ratio = rms(rear_bands["low_mid"]) / (rms(band_split(front, sample_rate)["low_mid"]) + EPS)
    low_mid_mud_score = _clip01((lowmid_rear_ratio - 0.30) / 0.55)

    rear_transient = transient_density(rear, sample_rate)
    front_transient = transient_density(front, sample_rate)
    input_transient = float(analysis.get("transient_density", transient_density(input_mid, sample_rate)))
    transient_smear_score = _clip01(
        0.55 * np.clip((rear_transient - front_transient * 0.85) / 0.12, 0.0, 1.0)
        + 0.45 * np.clip((rear_transient - input_transient * 0.90) / 0.12, 0.0, 1.0)
    )

    rear_air_ratio = rms(rear_bands["air"]) / (rms(band_split(front, sample_rate)["air"]) + EPS)
    rear_highmid_ratio = rms(rear_bands["high_mid"]) / (rms(band_split(front, sample_rate)["high_mid"]) + EPS)
    high_harshness_score = _clip01(
        0.58 * np.clip((rear_air_ratio - 0.34) / 0.70, 0.0, 1.0)
        + 0.42 * np.clip((rear_highmid_ratio - 0.28) / 0.62, 0.0, 1.0)
    )

    lr_corr_front = _safe_corr(four_ch[:, 0], four_ch[:, 1])
    lr_corr_rear = _safe_corr(four_ch[:, 2], four_ch[:, 3])
    mono_corr = _safe_corr(input_mono, output_mono)
    mono_delta_db = db(rms(output_mono) / (rms(input_mono) + EPS))
    mono_delta_db_front_norm = db(rms(output_mono_front_norm) / (rms(input_mono) + EPS))
    mono_front_only_delta_db = db(rms(output_front_only) / (rms(input_mono) + EPS))
    phase_correlation_risk = _clip01(
        0.45 * np.clip((-lr_corr_rear - 0.10) / 0.80, 0.0, 1.0)
        + 0.35 * np.clip((abs(mono_delta_db) - 1.5) / 5.0, 0.0, 1.0)
        + 0.20 * np.clip((0.82 - mono_corr) / 0.60, 0.0, 1.0)
    )

    spatial_excess_score = _clip01(
        0.24 * np.clip((rear_front_ratio - 0.22) / 0.38, 0.0, 1.0)
        + 0.22 * rear_vocal_leakage_score
        + 0.18 * low_mid_mud_score
        + 0.16 * transient_smear_score
        + 0.12 * high_harshness_score
        + 0.08 * phase_correlation_risk
    )

    return {
        "rear_front_rms_ratio": float(rear_front_ratio),
        "rear_front_db": float(db(rear_front_ratio)),
        "rear_vocal_leakage_score": float(rear_vocal_leakage_score),
        "sub150_retention_ratio": float(sub150_retention_ratio),
        "sub150_retention_score": float(sub150_retention_score),
        "low_mid_mud_score": float(low_mid_mud_score),
        "phase_correlation_risk": float(phase_correlation_risk),
        "transient_smear_score": float(transient_smear_score),
        "high_harshness_score": float(high_harshness_score),
        "mono_fold_down_delta_db": float(mono_delta_db),
        "mono_fold_down_delta_db_avg4_legacy": float(mono_delta_db),
        "mono_fold_down_delta_db_front_norm": float(mono_delta_db_front_norm),
        "mono_front_only_delta_db": float(mono_front_only_delta_db),
        "mono_fold_down_correlation": float(mono_corr),
        "front_lr_correlation": float(lr_corr_front),
        "rear_lr_correlation": float(lr_corr_rear),
        "rear_side_rms_ratio": float(rms(rear_side) / (rear_rms + EPS)),
        "spatial_excess_score": float(spatial_excess_score),
    }


def apply_spatial_safety(left, right, four_ch, sample_rate, analysis=None, enabled=True):
    """Apply conservative rear-only protection and return ``(audio, report)``.

    The guard operates before final energy matching/limiting.  It only attenuates
    risky rear bands; it never boosts, and it leaves the front channels intact.
    """
    four_ch = np.asarray(four_ch, dtype=np.float32)
    before = compute_quality_metrics(left, right, four_ch, sample_rate, analysis)
    if not enabled:
        return four_ch, {"enabled": False, "before": before, "after": before, "actions": {}}

    out = four_ch.copy()
    actions = {}

    vocal_gain = 1.0 - 0.34 * np.clip((before["rear_vocal_leakage_score"] - 0.48) / 0.42, 0.0, 1.0)
    transient_gain = 1.0 - 0.22 * np.clip((before["transient_smear_score"] - 0.42) / 0.48, 0.0, 1.0)
    mud_gain = 1.0 - 0.30 * np.clip((before["low_mid_mud_score"] - 0.38) / 0.52, 0.0, 1.0)
    harsh_gain = 1.0 - 0.36 * np.clip((before["high_harshness_score"] - 0.40) / 0.50, 0.0, 1.0)
    phase_gain = 1.0 - 0.18 * np.clip((before["phase_correlation_risk"] - 0.52) / 0.38, 0.0, 1.0)

    mid_gain = float(np.clip(vocal_gain * transient_gain * phase_gain, 0.52, 1.0))
    highmid_gain = float(np.clip(vocal_gain * harsh_gain * phase_gain, 0.48, 1.0))
    lowmid_gain = float(np.clip(mud_gain * phase_gain, 0.58, 1.0))
    air_gain = float(np.clip(harsh_gain, 0.52, 1.0))

    for band_name, gain in (
        ("low_mid", lowmid_gain),
        ("mid", mid_gain),
        ("high_mid", highmid_gain),
        ("air", air_gain),
    ):
        if gain < 0.995:
            out = _attenuate_rear_band(out, sample_rate, band_name, gain)
        actions[f"rear_{band_name}_gain"] = gain

    rear_master_gain = 1.0 - 0.20 * np.clip((before["spatial_excess_score"] - 0.62) / 0.30, 0.0, 1.0)
    rear_master_gain = float(np.clip(rear_master_gain, 0.80, 1.0))
    if rear_master_gain < 0.995:
        out[:, 2:] *= rear_master_gain
    actions["rear_master_gain"] = rear_master_gain

    after = compute_quality_metrics(left, right, out, sample_rate, analysis)
    return out.astype(np.float32), {
        "enabled": True,
        "before": before,
        "after": after,
        "actions": actions,
    }