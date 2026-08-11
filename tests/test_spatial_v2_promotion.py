import pytest
import numpy as np

from spatial_core import (
    evaluate_clarity_gate,
    evaluate_promotion_gate,
    measure_clarity_metrics,
)


def _record(
    track_id,
    externalization_delta=0.5,
    depth_delta=0.5,
    clarity_delta=0.0,
    objective_clarity_pass=True,
):
    return {
        "track_id": track_id,
        "legacy": {"externalization": 3, "depth": 3, "vocal_clarity": 4},
        "spatial_v2": {
            "externalization": 3 + externalization_delta,
            "depth": 3 + depth_delta,
            "vocal_clarity": 4 + clarity_delta,
        },
        "objective_clarity_pass": objective_clarity_pass,
    }


def test_promotion_gate_requires_three_tracks_and_half_point_gains():
    assert evaluate_promotion_gate([_record("a"), _record("b")])["promote"] is False
    with pytest.raises(ValueError, match="unique track"):
        evaluate_promotion_gate([_record("a"), _record("a"), _record("b")])
    result = evaluate_promotion_gate([_record("a"), _record("b"), _record("c")])
    assert result["promote"] is True


def test_promotion_gate_blocks_large_timbre_regression():
    result = evaluate_promotion_gate(
        [_record("a", clarity_delta=-0.6), _record("b", clarity_delta=-0.6), _record("c", clarity_delta=-0.6)]
    )
    assert result["promote"] is False
    assert result["worst_timbre_regression"] == pytest.approx(0.6)


def test_promotion_gate_requires_objective_clarity_pass_for_every_track():
    result = evaluate_promotion_gate(
        [_record("a"), _record("b", objective_clarity_pass=False), _record("c")]
    )

    assert result["promote"] is False
    assert result["objective_clarity_pass"] is False


def test_clarity_gate_checks_width_transients_and_four_bands():
    passing = evaluate_clarity_gate(
        {
            "mid_side_balance_delta_db": 0.8,
            "crest_delta_db": -0.9,
            "fast_change_delta_db": -0.4,
            "band_delta_db": {
                "sub": -1.9,
                "bass": 1.0,
                "low_mid": 1.8,
                "presence": -1.7,
            },
        }
    )
    failing = evaluate_clarity_gate(
        {
            "mid_side_balance_delta_db": 1.2,
            "crest_delta_db": -1.1,
            "fast_change_delta_db": -0.6,
            "band_delta_db": {
                "sub": -2.1,
                "bass": 0.0,
                "low_mid": 2.2,
                "presence": 2.5,
            },
        }
    )

    assert passing["pass"] is True
    assert passing["failures"] == []
    assert failing["pass"] is False
    assert set(failing["failures"]) == {
        "mid_side_balance_delta_db",
        "crest_delta_db",
        "fast_change_delta_db",
        "band_delta_db.sub",
        "band_delta_db.low_mid",
        "band_delta_db.presence",
    }


def test_clarity_gate_rejects_non_finite_metrics():
    metrics = {
        "mid_side_balance_delta_db": float("nan"),
        "crest_delta_db": 0.0,
        "fast_change_delta_db": 0.0,
        "band_delta_db": {band: 0.0 for band in ("sub", "bass", "low_mid", "presence")},
    }

    with pytest.raises(ValueError, match="must be finite"):
        evaluate_clarity_gate(metrics)


def test_clarity_measurement_rejects_silent_excerpts():
    silence = np.zeros((4_096, 2), dtype=np.float32)

    with pytest.raises(ValueError, match="non-silent"):
        measure_clarity_metrics(silence, silence, 48_000)
