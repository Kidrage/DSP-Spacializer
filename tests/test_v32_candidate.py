import pytest

from presets import apply_phase5a_v32_candidate, classify_phase5a_v32_profile


BASE = {
    "side_rear": 1.0,
    "amb_rear": 0.55,
    "rear_air_gain": 0.25,
    "rear_highmid_gain": 0.50,
    "lowbody_rear": 0.35,
    "rear_floor_ratio": 0.12,
    "max_rear_makeup": 3.5,
    "bass_gain": 1.08,
    "guard_scale": 0.90,
}


def _info(
    hall=0.75,
    side=0.72,
    vocal=0.12,
    narrow=0.04,
):
    return {
        "hall_score": hall,
        "side_material": side,
        "vocal_risk": vocal,
        "narrow_score": narrow,
    }


def _analysis(center=0.65, diffuse=0.36, transient=0.03):
    return {
        "center_dominance": center,
        "high_diffuse_ratio": diffuse,
        "transient_density": transient,
    }


@pytest.mark.parametrize(
    ("info", "analysis", "expected"),
    [
        (_info(1.0, 1.0), _analysis(), "abstain_low_separability"),
        (
            _info(0.23, 0.03, vocal=0.37, narrow=0.46),
            _analysis(center=0.95, diffuse=0.17),
            "narrow_spatial_source_lift",
        ),
        (
            _info(0.38, 0.18, vocal=0.60, narrow=0.50),
            _analysis(center=0.95, diffuse=0.26, transient=0.09),
            "strong_center_room_guard",
        ),
        (_info(0.38, 0.50), _analysis(center=0.65, diffuse=0.15), "abstain_clean_vocal"),
        (
            _info(0.38, 0.40, vocal=0.34, narrow=0.45),
            _analysis(center=0.84, diffuse=0.25),
            "vocal_anchor_guard",
        ),
        (
            _info(0.88, 0.96),
            _analysis(center=0.60, diffuse=0.39, transient=0.09),
            "hall_body_guard",
        ),
        (_info(0.83, 0.86), _analysis(diffuse=0.49), "hall_envelopment_only"),
        (
            _info(0.95, 0.98),
            _analysis(center=0.59, diffuse=0.45, transient=0.06),
            "low_separability_lift",
        ),
        (
            _info(0.74, 0.70),
            _analysis(center=0.66, diffuse=0.36, transient=0.09),
            "wet_vocal_guard",
        ),
        (_info(), _analysis(), "spatial_ready_body_safe"),
    ],
)
def test_v32_profile_classification(info, analysis, expected):
    profile, _ = classify_phase5a_v32_profile(info, analysis)
    assert profile == expected


def test_v32_abstention_is_exact_base_preset():
    candidate, report = apply_phase5a_v32_candidate(
        BASE, _info(1.0, 1.0), _analysis(),
    )

    assert candidate == BASE
    assert report["abstained"] is True


def test_v32_vocal_anchor_guard_protects_body_and_anchor():
    candidate, report = apply_phase5a_v32_candidate(
        BASE,
        _info(0.38, 0.40, vocal=0.34, narrow=0.45),
        _analysis(center=0.84, diffuse=0.25),
    )

    assert report["profile"] == "vocal_anchor_guard"
    assert candidate["rear_highmid_gain"] < BASE["rear_highmid_gain"] + 0.04
    assert candidate["rear_air_gain"] < BASE["rear_air_gain"] + 0.03
    assert candidate["lowbody_rear"] > BASE["lowbody_rear"]
    assert candidate["bass_gain"] > BASE["bass_gain"]
    assert candidate["guard_scale"] > BASE["guard_scale"]


def test_v32_narrow_spatial_source_gets_clarity_lift_without_body_cut():
    candidate, report = apply_phase5a_v32_candidate(
        BASE,
        _info(0.23, 0.03, vocal=0.37, narrow=0.46),
        _analysis(center=0.95, diffuse=0.17),
    )

    assert report["profile"] == "narrow_spatial_source_lift"
    assert candidate["rear_highmid_gain"] > BASE["rear_highmid_gain"]
    assert candidate["rear_air_gain"] > BASE["rear_air_gain"]
    assert candidate["lowbody_rear"] >= BASE["lowbody_rear"]


def test_v32_hall_body_guard_reduces_floor_pressure_vs_v31_target():
    candidate, report = apply_phase5a_v32_candidate(
        BASE,
        _info(0.88, 0.96),
        _analysis(center=0.60, diffuse=0.39, transient=0.09),
    )

    assert report["profile"] == "hall_body_guard"
    assert candidate["rear_floor_ratio"] < 0.20
    assert candidate["lowbody_rear"] > BASE["lowbody_rear"]
    assert candidate["rear_highmid_gain"] == BASE["rear_highmid_gain"]


def test_v32_wet_vocal_guard_no_longer_strips_lowbody():
    candidate, report = apply_phase5a_v32_candidate(
        BASE,
        _info(0.74, 0.70),
        _analysis(center=0.66, diffuse=0.36, transient=0.09),
    )

    assert report["profile"] == "wet_vocal_guard"
    assert candidate["lowbody_rear"] >= BASE["lowbody_rear"]
    assert candidate["rear_highmid_gain"] == BASE["rear_highmid_gain"]


def test_v32_does_not_mutate_source_preset():
    source = dict(BASE)
    apply_phase5a_v32_candidate(source, _info(), _analysis())

    assert source == BASE
