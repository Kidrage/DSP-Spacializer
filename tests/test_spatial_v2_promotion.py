import pytest

from spatial_core import evaluate_promotion_gate


def _record(externalization_delta=0.5, depth_delta=0.5, clarity_delta=0.0):
    return {
        "legacy": {"externalization": 3, "depth": 3, "vocal_clarity": 4},
        "spatial_v2": {
            "externalization": 3 + externalization_delta,
            "depth": 3 + depth_delta,
            "vocal_clarity": 4 + clarity_delta,
        },
    }


def test_promotion_gate_requires_three_tracks_and_half_point_gains():
    assert evaluate_promotion_gate([_record(), _record()])["promote"] is False
    result = evaluate_promotion_gate([_record(), _record(), _record()])
    assert result["promote"] is True


def test_promotion_gate_blocks_large_timbre_regression():
    result = evaluate_promotion_gate(
        [_record(clarity_delta=-0.6), _record(clarity_delta=-0.6), _record(clarity_delta=-0.6)]
    )
    assert result["promote"] is False
    assert result["worst_timbre_regression"] == pytest.approx(0.6)
