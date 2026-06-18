import json

import pytest

from tuning_profile import TuningProfileError, apply_tuning_profile, load_tuning_profile


def test_apply_tuning_profile_offsets_and_clamps():
    preset = {
        "side_rear": 0.5,
        "rear_floor_ratio": 0.1,
        "air_rear": 0.2,
    }
    profile = {
        "profile_id": "test_profile",
        "parameter_offsets": {
            "side_rear": 0.25,
            "rear_floor_ratio": 1.0,
            "air_rear": -0.05,
        },
    }
    out, report = apply_tuning_profile(preset, profile)
    assert out["side_rear"] == 0.75
    assert out["rear_floor_ratio"] == 0.25
    assert out["air_rear"] == 0.15000000000000002
    assert report["enabled"] is True
    assert report["profile_id"] == "test_profile"


def test_apply_tuning_profile_none_is_noop():
    preset = {"side_rear": 0.5}
    out, report = apply_tuning_profile(preset, None)
    assert out == preset
    assert report == {"enabled": False}


def test_load_tuning_profile_rejects_unknown_key(tmp_path):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps({
        "profile_id": "bad",
        "parameter_offsets": {"unknown": 1.0},
    }), encoding="utf-8")
    with pytest.raises(TuningProfileError):
        load_tuning_profile(path)
