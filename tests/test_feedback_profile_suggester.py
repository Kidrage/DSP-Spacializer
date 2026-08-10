from feedback_profile_suggester import suggest_tuning_profile
from tuning_profile import validate_tuning_profile


def _record(tags=None, scores=None, metrics=None):
    return {
        "record_format": "dsp_spatial_feedback_v1",
        "subjective": {
            "enabled": True,
            "scores": scores or {"overall_preference": 3},
            "tags": tags or [],
        },
        "objective": {
            "quality_metrics": metrics or {},
            "over_protection": {"over_protection_warning": False},
        },
    }


def test_rear_too_weak_suggests_rear_boost():
    profile = suggest_tuning_profile([
        _record(
            tags=["rear_too_weak"],
            scores={"overall_preference": 3, "envelopment": 2, "vocal_clarity": 4},
            metrics={"rear_front_db": -14.0},
        )
    ])
    validate_tuning_profile(profile)
    offsets = profile["parameter_offsets"]
    assert offsets["side_rear"] > 0
    assert offsets["rear_floor_ratio"] > 0
    assert offsets["rear_master"] > 0


def test_harsh_and_blurry_feedback_protects_vocal_and_highs():
    profile = suggest_tuning_profile([
        _record(
            tags=["harsh_rear", "vocal_blurry"],
            scores={
                "overall_preference": 2,
                "harshness": 5,
                "vocal_clarity": 2,
            },
            metrics={
                "rear_vocal_leakage_score": 0.5,
                "high_harshness_score": 0.6,
            },
        )
    ])
    offsets = profile["parameter_offsets"]
    assert offsets["guard_scale"] > 0
    assert offsets["rear_air_gain"] < 0
    assert offsets["rear_highmid_gain"] < 0


def test_multiple_records_average_safely():
    profile = suggest_tuning_profile([
        _record(tags=["rear_too_weak"], scores={"overall_preference": 3, "envelopment": 2}),
        _record(tags=["rear_too_weak"], scores={"overall_preference": 4, "envelopment": 3}),
        _record(tags=["rear_too_loud"], scores={"overall_preference": 2, "envelopment": 5, "rear_naturalness": 2}),
    ])
    validate_tuning_profile(profile)
    assert profile["record_count"] == 3
    assert "rules_fired" in profile["evidence"]
