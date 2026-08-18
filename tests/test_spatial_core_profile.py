import json

import pytest

from spatial_core import SpatialCoreProfile, load_spatial_profile


def test_spatial_profile_defaults_preserve_legacy_frontal_modes():
    profile = SpatialCoreProfile()

    assert profile.hrtf_compensation_mode == "legacy_front_common"
    assert profile.mastered_loudness_mode == "legacy_input_rms"
    assert profile.center_room_send_db == -3.0
    assert profile.reflection_normalization_mode == "legacy_per_object"
    assert profile.direct_ratio_mode == "manual"


def test_spatial_profile_loads_compact_parameters(tmp_path):
    path = tmp_path / "balanced.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {
                    "center_anchor": 0.72,
                    "front_distance_m": 1.8,
                    "front_width_deg": 42,
                    "bed_width_gain": 0.2,
                    "bed_rear_gain": 0.15,
                    "bed_air_gain": 0.1,
                    "direct_ratio": 0.8,
                    "early_reflection_level_db": -22,
                    "late_reverb_level_db": -29,
                    "late_rt60_s": 0.4,
                },
            }
        ),
        encoding="utf-8",
    )

    profile = load_spatial_profile(path)

    assert profile.center_anchor == 0.72
    assert profile.front_distance_m == 1.8
    assert profile.front_width_deg == 42
    assert profile.late_rt60_s == 0.4


def test_spatial_profile_loads_frontal_experiment_controls(tmp_path):
    path = tmp_path / "frontal.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {
                    "hrtf_compensation_mode": "off",
                    "mastered_loudness_mode": "fixed_scene_gain",
                    "center_room_send_db": 0.0,
                    "reflection_normalization_mode": "physical_path_gain",
                    "direct_ratio_mode": "distance_curve",
                },
            }
        ),
        encoding="utf-8",
    )

    profile = load_spatial_profile(path)

    assert profile.hrtf_compensation_mode == "off"
    assert profile.mastered_loudness_mode == "fixed_scene_gain"
    assert profile.center_room_send_db == 0.0
    assert profile.reflection_normalization_mode == "physical_path_gain"
    assert profile.direct_ratio_mode == "distance_curve"


def test_spatial_profile_rejects_unknown_parameters(tmp_path):
    path = tmp_path / "unknown.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {"stereo_width": 2.0},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown spatial profile parameter"):
        load_spatial_profile(path)


def test_spatial_profile_rejects_unknown_top_level_keys(tmp_path):
    path = tmp_path / "unknown-top-level.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {},
                "notes": "not part of the strict schema",
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="unknown spatial profile field"):
        load_spatial_profile(path)


def test_spatial_profile_rejects_boolean_parameter_values(tmp_path):
    path = tmp_path / "boolean.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {"center_anchor": True},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="center_anchor must be numeric"):
        load_spatial_profile(path)


def test_spatial_profile_constructor_rejects_boolean_values():
    with pytest.raises(ValueError, match="center_anchor must be numeric"):
        SpatialCoreProfile(center_anchor=True)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("hrtf_compensation_mode", "minimum_phase"),
        ("mastered_loudness_mode", "louder"),
        ("reflection_normalization_mode", "unit_energy"),
        ("direct_ratio_mode", "automatic"),
    ],
)
def test_spatial_profile_rejects_unknown_frontal_modes(name, value):
    with pytest.raises(ValueError, match=name):
        SpatialCoreProfile(**{name: value})


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("center_anchor", 1.1),
        ("front_distance_m", 0.4),
        ("front_width_deg", 80),
        ("bed_width_gain", -0.1),
        ("bed_rear_gain", 1.1),
        ("bed_air_gain", 1.1),
        ("direct_ratio", 0.2),
        ("early_reflection_level_db", -9),
        ("late_reverb_level_db", -41),
        ("late_rt60_s", 1.3),
        ("center_room_send_db", 6.1),
    ],
)
def test_spatial_profile_rejects_out_of_range_parameters(tmp_path, name, value):
    path = tmp_path / "invalid.json"
    path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {name: value},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=name):
        load_spatial_profile(path)
