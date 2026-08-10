import pytest

from presets import apply_phase5a_rear_content_candidate


BASE = {
    "side_rear": 1.0,
    "amb_rear": 0.55,
    "rear_air_gain": 0.25,
    "rear_highmid_gain": 0.50,
    "lowbody_rear": 0.35,
    "rear_floor_ratio": 0.12,
    "max_rear_makeup": 3.5,
}


def _info(telephone=False):
    return {
        "side_material": 0.8,
        "hall_score": 0.8,
        "dry_bass_score": 0.1,
        "vocal_risk": 0.1,
        "telephone_risk": telephone,
    }


def test_candidate_restores_rear_definition_without_center_send():
    candidate, report = apply_phase5a_rear_content_candidate(BASE, _info())

    assert candidate["amb_rear"] > BASE["amb_rear"]
    assert candidate["rear_air_gain"] > BASE["rear_air_gain"]
    assert candidate["rear_highmid_gain"] > BASE["rear_highmid_gain"]
    assert candidate["lowbody_rear"] < BASE["lowbody_rear"]
    assert candidate["rear_floor_ratio"] > 0.28
    assert candidate["max_rear_makeup"] > BASE["max_rear_makeup"]
    assert report["center_send_added"] is False
    assert report["amount"] == pytest.approx(0.94)


def test_telephone_candidate_is_reduced_to_35_percent():
    normal, normal_report = apply_phase5a_rear_content_candidate(BASE, _info())
    telephone, telephone_report = apply_phase5a_rear_content_candidate(BASE, _info(True))

    normal_delta = normal["rear_highmid_gain"] - BASE["rear_highmid_gain"]
    telephone_delta = telephone["rear_highmid_gain"] - BASE["rear_highmid_gain"]
    assert telephone_delta == pytest.approx(normal_delta * 0.35)
    assert telephone_report["telephone_limited"] is True
    assert normal_report["telephone_limited"] is False


def test_candidate_does_not_mutate_source_preset():
    source = dict(BASE)
    apply_phase5a_rear_content_candidate(source, _info())

    assert source == BASE
