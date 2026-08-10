"""Tests for threshold_calibrator.py — Phase 5A."""

import json
import tempfile
from pathlib import Path

import pytest

import threshold_calibrator as tc
from spatial_safety import load_quality_thresholds


# ---------------------------------------------------------------------------
# collect_threshold_evidence
# ---------------------------------------------------------------------------

def test_collect_evidence_from_feedback_records():
    """Evidence extracted from structured subjective feedback."""
    fb = [
        {
            "track_id": "bright_pop_001",
            "candidate_id": "B",
            "metric_observation": {
                "harshness_score": 0.35,
            },
            "listener_tags": ["highs_too_harsh"],
            "listener_boundary_note": "Sharp at 0.35 already.",
            "suggested_threshold_adjustment": {
                "harshness_score.warning": 0.30,
            },
        },
    ]
    evidence = tc.collect_threshold_evidence([], fb)
    assert len(evidence) == 1
    e = evidence[0]
    assert e["tag"] == "highs_too_harsh"
    assert e["metric_name"] == "harshness_score"
    assert e["direction"] == "lower"
    assert e["observed_value"] == 0.35
    assert "Sharp" in e["boundary_note"]


def test_collect_evidence_from_evaluation_records():
    """Evidence extracted from auto-generated evaluation records."""
    recs = [
        {
            "input_file": "track_01.mp3",
            "listener_tags": ["lowmid_muddy", "vocal_leaks_to_rear"],
            "quality_metrics": {
                "low_mid_mud_score": 0.62,
                "rear_vocal_leakage_score": 0.34,
            },
        },
    ]
    evidence = tc.collect_threshold_evidence(recs, [])
    assert len(evidence) == 2
    tags = {e["tag"] for e in evidence}
    assert tags == {"lowmid_muddy", "vocal_leaks_to_rear"}


def test_collect_evidence_ignores_unknown_tags():
    """Unknown tags are silently skipped."""
    fb = [{"listener_tags": ["not_a_real_tag"], "metric_observation": {}}]
    evidence = tc.collect_threshold_evidence([], fb)
    assert len(evidence) == 0


# ---------------------------------------------------------------------------
# suggest_threshold_calibration
# ---------------------------------------------------------------------------

def test_suggest_harshness_calibration():
    """Multiple consistent harshness complaints → lower threshold suggestion."""
    evidence = [
        {
            "track_id": f"track_{i}",
            "tag": "highs_too_harsh",
            "metric_name": "harshness_score",
            "direction": "lower",
            "observed_value": 0.32 + i * 0.01,
            "boundary_note": "Harsh at this level.",
        }
        for i in range(5)
    ]
    thresholds = load_quality_thresholds()
    suggestions = tc.suggest_threshold_calibration(evidence, thresholds, min_evidence_count=3)
    assert "harshness_score" in suggestions
    s = suggestions["harshness_score"]
    assert "warning" in s
    assert "danger" in s
    assert s["danger"] < thresholds["global"]["high_harshness_score_max"]
    assert s["evidence_count"] == 5
    assert s["confidence_level"] == "low"  # 5 → low confidence


def test_suggest_medium_confidence():
    """6+ examples → medium confidence."""
    evidence = [
        {
            "track_id": f"track_{i}",
            "tag": "lowmid_muddy",
            "metric_name": "lowmid_mud_score",
            "direction": "lower",
            "observed_value": 0.40,
            "boundary_note": "",
        }
        for i in range(7)
    ]
    thresholds = load_quality_thresholds()
    suggestions = tc.suggest_threshold_calibration(evidence, thresholds, min_evidence_count=3)
    assert suggestions["lowmid_mud_score"]["confidence_level"] == "medium"


def test_suggest_insufficient_evidence():
    """Below min_evidence_count → no suggestion."""
    evidence = [
        {
            "track_id": "track_1",
            "tag": "phase_weird",
            "metric_name": "phase_risk_score",
            "direction": "lower",
            "observed_value": 0.48,
            "boundary_note": "",
        }
    ]
    thresholds = load_quality_thresholds()
    suggestions = tc.suggest_threshold_calibration(evidence, thresholds, min_evidence_count=3)
    assert len(suggestions) == 0


def test_suggest_rear_too_weak_raises_min():
    """rear_too_weak → raise minimum threshold."""
    evidence = [
        {
            "track_id": f"track_{i}",
            "tag": "rear_too_weak",
            "metric_name": "rear_presence_score",
            "direction": "raise_min",
            "observed_value": -8.0 + i * 0.5,
            "boundary_note": "Rear too quiet.",
        }
        for i in range(4)
    ]
    thresholds = load_quality_thresholds()
    suggestions = tc.suggest_threshold_calibration(evidence, thresholds, min_evidence_count=3)
    assert "rear_presence_score" in suggestions
    assert "min" in suggestions["rear_presence_score"]


# ---------------------------------------------------------------------------
# apply_threshold_calibration
# ---------------------------------------------------------------------------

def test_apply_calibration_reduces_threshold():
    """Calibration lowers a danger threshold in the resolved output."""
    base = load_quality_thresholds()
    cal = {
        "harshness_score": {
            "danger": 0.30,
        },
    }
    resolved = tc.apply_threshold_calibration(base, cal)
    assert resolved["global"]["high_harshness_score_max"] == 0.30
    # auto_acoustic preset overrides rear_vocal_leakage → calibrate that instead
    cal2 = {"vocal_leakage_score": {"danger": 0.20}}
    resolved2 = tc.apply_threshold_calibration(base, cal2)
    assert resolved2["presets"]["auto_acoustic"]["rear_vocal_leakage_score_max"] == 0.20


def test_apply_calibration_preserves_unrelated():
    """Calibration only affects the specified metric."""
    base = load_quality_thresholds()
    original_phase = base["global"]["phase_correlation_risk_max"]
    cal = {"harshness_score": {"danger": 0.30}}
    resolved = tc.apply_threshold_calibration(base, cal)
    assert resolved["global"]["phase_correlation_risk_max"] == original_phase


# ---------------------------------------------------------------------------
# explain_threshold_changes
# ---------------------------------------------------------------------------

def test_explain_threshold_changes():
    """Produces structured explanations for each changed threshold."""
    old = load_quality_thresholds()
    new = load_quality_thresholds()
    new["global"]["high_harshness_score_max"] = 0.30
    evidence = [
        {
            "track_id": "test_track",
            "tag": "highs_too_harsh",
            "metric_name": "harshness_score",
            "direction": "lower",
            "observed_value": 0.35,
            "confidence": 0.62,
        }
    ]
    explanations = tc.explain_threshold_changes(old, new, evidence)
    assert len(explanations) == 1
    assert explanations[0]["metric"] == "harshness_score"
    assert explanations[0]["old_value"] == 0.45
    assert explanations[0]["new_value"] == 0.30


# ---------------------------------------------------------------------------
# calibration history
# ---------------------------------------------------------------------------

def test_write_and_read_calibration_history():
    """JSONL history round-trips correctly."""
    import threshold_calibrator as tc2
    # Point history to a temp file
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".jsonl") as f:
        tmp_path = Path(f.name)
    try:
        # Override the module's history path
        tc2._HISTORY_PATH = tmp_path
        tc2.write_calibration_history_entry(
            metric_name="harshness_score.warning",
            old_value=0.42,
            new_value=0.30,
            confidence=0.62,
            evidence_count=6,
            source_tracks=["t1", "t2"],
            reason="test",
        )
        entries = tc2.read_calibration_history()
        assert len(entries) == 1
        assert entries[0]["threshold_name"] == "harshness_score.warning"
        assert entries[0]["new_value"] == 0.30
    finally:
        tmp_path.unlink(missing_ok=True)
