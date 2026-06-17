import numpy as np

from spatial_safety import (
    apply_spatial_safety,
    classify_quality_risks,
    compare_quality_metrics,
    compute_quality_metrics,
    detect_over_protection,
    load_quality_thresholds,
)


def _signals(kind="random", sr=48000, seconds=0.25):
    n = int(sr * seconds)
    if kind == "silence":
        left = np.zeros(n, dtype=np.float32)
        right = np.zeros(n, dtype=np.float32)
    elif kind == "mono":
        t = np.arange(n) / sr
        left = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
        right = left.copy()
    else:
        rng = np.random.default_rng(123)
        left = (0.05 * rng.standard_normal(n)).astype(np.float32)
        right = (0.05 * rng.standard_normal(n)).astype(np.float32)
    four = np.stack([left, right, 0.25 * left, -0.20 * right], axis=1).astype(np.float32)
    return left, right, four, sr


def test_compute_quality_metrics_fields_complete():
    left, right, four, sr = _signals("random")
    metrics = compute_quality_metrics(left, right, four, sr)
    expected = {
        "rear_front_rms_ratio",
        "rear_front_db",
        "rear_vocal_leakage_score",
        "sub150_retention_ratio",
        "sub150_retention_score",
        "low_mid_mud_score",
        "phase_correlation_risk",
        "transient_smear_score",
        "high_harshness_score",
        "mono_fold_down_delta_db",
        "mono_fold_down_correlation",
        "front_lr_correlation",
        "rear_lr_correlation",
        "rear_side_rms_ratio",
        "spatial_excess_score",
    }
    assert expected.issubset(metrics.keys())


def test_silence_mono_random_do_not_crash():
    for kind in ["silence", "mono", "random"]:
        left, right, four, sr = _signals(kind)
        metrics = compute_quality_metrics(left, right, four, sr)
        assert isinstance(metrics, dict)
        assert all(np.isfinite(v) for v in metrics.values())


def test_apply_spatial_safety_disabled_does_not_change_audio():
    left, right, four, sr = _signals("random")
    out, report = apply_spatial_safety(left, right, four, sr, enabled=False)
    assert np.allclose(out, four)
    assert report["enabled"] is False


def test_classify_quality_risks_detects_threshold_exceedance():
    thresholds = load_quality_thresholds()
    metrics = {
        "rear_front_db": 0.0,
        "rear_vocal_leakage_score": 0.9,
        "sub150_retention_score": 0.2,
        "low_mid_mud_score": 0.9,
        "phase_correlation_risk": 0.9,
        "transient_smear_score": 0.9,
        "high_harshness_score": 0.9,
        "mono_fold_down_delta_db": 4.0,
        "spatial_excess_score": 0.9,
    }
    risk = classify_quality_risks(metrics, thresholds, preset_name="auto_acoustic")
    assert risk["overall_status"] == "fail"
    assert "rear_vocal_leakage_score" in risk["risks"]


def test_compare_quality_metrics_outputs_delta():
    delta = compare_quality_metrics({"rear_front_db": -6.0, "low_mid_mud_score": 0.5}, {"rear_front_db": -7.4, "low_mid_mud_score": 0.38})
    assert delta["rear_front_db_delta"] == -1.4000000000000004
    assert delta["low_mid_mud_score_delta"] == -0.12


def test_detect_over_protection_flags_large_reduction():
    before = {
        "rear_front_db": -5.0,
        "spatial_excess_score": 0.8,
        "rear_front_rms_ratio": 0.5,
        "rear_lr_correlation": 0.4,
    }
    after = {
        "rear_front_db": -10.0,
        "spatial_excess_score": 0.3,
        "rear_front_rms_ratio": 0.2,
        "rear_lr_correlation": 0.95,
    }
    result = detect_over_protection(before, after)
    assert result["over_protection_warning"] is True
    assert result["reasons"]
