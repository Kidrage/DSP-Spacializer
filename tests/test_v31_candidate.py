import pytest

from presets import apply_phase5a_v31_candidate, classify_phase5a_v31_profile


BASE = {
    "side_rear": 1.0,
    "amb_rear": 0.55,
    "rear_air_gain": 0.25,
    "rear_highmid_gain": 0.50,
    "lowbody_rear": 0.35,
    "rear_floor_ratio": 0.12,
    "max_rear_makeup": 3.5,
}


def _info(hall=0.75, side=0.72):
    return {"hall_score": hall, "side_material": side}


def _analysis(center=0.65, diffuse=0.36, transient=0.03):
    return {
        "center_dominance": center,
        "high_diffuse_ratio": diffuse,
        "transient_density": transient,
    }


@pytest.mark.parametrize(
    ("info", "analysis", "expected"),
    [
        (_info(0.96, 0.97), _analysis(), "abstain_low_separability"),
        (_info(0.38, 0.50), _analysis(diffuse=0.15), "abstain_clean_vocal"),
        (_info(0.84, 0.86), _analysis(diffuse=0.49, transient=0.10), "hall_envelopment_only"),
        (_info(0.74, 0.70), _analysis(diffuse=0.36, transient=0.09), "wet_vocal_guard"),
        (_info(), _analysis(), "spatial_ready"),
    ],
)
def test_v31_profile_classification(info, analysis, expected):
    profile, _ = classify_phase5a_v31_profile(info, analysis)
    assert profile == expected


def test_v31_abstention_is_exact_v2_preset():
    candidate, report = apply_phase5a_v31_candidate(
        BASE, _info(0.96, 0.97), _analysis(),
    )

    assert candidate == BASE
    assert report["abstained"] is True


def test_v31_hall_profile_adds_wrap_without_tone_change():
    candidate, report = apply_phase5a_v31_candidate(
        BASE, _info(0.84, 0.86), _analysis(diffuse=0.49, transient=0.10),
    )

    assert candidate["amb_rear"] > BASE["amb_rear"]
    assert candidate["rear_floor_ratio"] > BASE["rear_floor_ratio"]
    assert candidate["rear_air_gain"] == BASE["rear_air_gain"]
    assert candidate["rear_highmid_gain"] == BASE["rear_highmid_gain"]
    assert candidate["lowbody_rear"] == BASE["lowbody_rear"]
    assert report["amounts"]["rear_envelopment"] == pytest.approx(0.85)


def test_v31_wet_vocal_guard_blocks_highmid_definition():
    candidate, report = apply_phase5a_v31_candidate(
        BASE, _info(0.74, 0.70), _analysis(diffuse=0.36, transient=0.09),
    )

    assert candidate["amb_rear"] > BASE["amb_rear"]
    assert candidate["rear_highmid_gain"] == BASE["rear_highmid_gain"]
    assert candidate["rear_air_gain"] > BASE["rear_air_gain"]
    assert candidate["lowbody_rear"] < BASE["lowbody_rear"]
    assert report["profile"] == "wet_vocal_guard"


def test_v31_spatial_ready_retains_full_v3_direction():
    candidate, report = apply_phase5a_v31_candidate(BASE, _info(), _analysis())

    assert candidate["amb_rear"] == pytest.approx(BASE["amb_rear"] + 0.12)
    assert candidate["rear_highmid_gain"] == pytest.approx(BASE["rear_highmid_gain"] + 0.16)
    assert candidate["rear_air_gain"] == pytest.approx(BASE["rear_air_gain"] + 0.14)
    assert candidate["lowbody_rear"] == pytest.approx(BASE["lowbody_rear"] - 0.10)
    assert report["profile"] == "spatial_ready"
    assert report["center_send_added"] is False


def test_v31_does_not_mutate_source_preset():
    source = dict(BASE)
    apply_phase5a_v31_candidate(source, _info(), _analysis())
    assert source == BASE
