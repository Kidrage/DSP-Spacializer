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
