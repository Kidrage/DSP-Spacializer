import pytest

from spatial_core import evaluate_promotion_gate


def _record(track_id, externalization_delta=0.5, depth_delta=0.5, clarity_delta=0.0):
    return {
        "track_id": track_id,
        "legacy": {"externalization": 3, "depth": 3, "vocal_clarity": 4},
        "spatial_v2": {
            "externalization": 3 + externalization_delta,
            "depth": 3 + depth_delta,
            "vocal_clarity": 4 + clarity_delta,
        },
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
