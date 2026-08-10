import json

import pytest

from subjective_feedback import SubjectiveFeedbackError, load_subjective_score


def test_load_subjective_score_validates_range(tmp_path):
    path = tmp_path / "score.json"
    path.write_text(json.dumps({
        "scores": {"overall_preference": 3},
        "tags": [],
    }), encoding="utf-8")
    loaded = load_subjective_score(path)
    assert loaded["scores"]["overall_preference"] == 3


def test_load_subjective_score_rejects_bad_score(tmp_path):
    path = tmp_path / "score.json"
    path.write_text(json.dumps({
        "scores": {"overall_preference": 6},
        "tags": [],
    }), encoding="utf-8")
    with pytest.raises(SubjectiveFeedbackError):
        load_subjective_score(path)


def test_load_subjective_score_accepts_optional_spatial_v2_dimensions(tmp_path):
    path = tmp_path / "score.json"
    path.write_text(json.dumps({
        "scores": {
            "overall_preference": 4,
            "externalization": 4,
            "distance_naturalness": 3,
            "front_back_accuracy": 4,
            "head_motion_stability": 5,
        },
        "tags": ["spatial-v2"],
    }), encoding="utf-8")

    loaded = load_subjective_score(path)

    assert loaded["scores"]["externalization"] == 4
