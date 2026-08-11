import json

import pytest

from spatial_core.profile import SpatialCoreProfile
from spatial_mixer import (
    ExtractionSettings,
    MixerProfile,
    load_mixer_profile,
    mixer_profile_from_spatial_core,
    save_mixer_profile,
)


def test_default_mixer_profile_preserves_the_v21_seven_zone_baseline():
    profile = MixerProfile.default()

    assert tuple(profile.zones) == (
        "bass",
        "center_anchor",
        "front_L_residual",
        "front_R_residual",
        "side_width",
        "rear_ambience",
        "high_air",
    )
    assert profile.zones["bass"].distance_m == pytest.approx(1.60)
    assert profile.zones["center_anchor"].direct_ratio == pytest.approx(0.78)
    assert profile.zones["front_L_residual"].azimuth_deg == pytest.approx(35.0)
    assert profile.zones["front_R_residual"].azimuth_deg == pytest.approx(-35.0)
    assert profile.zones["side_width"].field_gain == pytest.approx(0.25)
    assert profile.zones["rear_ambience"].field_gain == pytest.approx(0.18)
    assert profile.zones["high_air"].field_gain == pytest.approx(0.12)
    assert profile.room.early_reflection_level_db == pytest.approx(-21.0)
    assert profile.room.late_reverb_level_db == pytest.approx(-27.0)
    assert profile.room.late_rt60_s == pytest.approx(0.35)


def test_mixer_profile_round_trip_is_strict_and_hash_stable(tmp_path):
    path = tmp_path / "universal-profile.json"
    original = MixerProfile.default()

    save_mixer_profile(original, path)
    loaded = load_mixer_profile(path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["format"] == "spatial_mixer_profile"
    assert payload["version"] == "1.0"
    assert loaded.profile_hash == original.profile_hash

    payload["unexpected"] = True
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown mixer profile field"):
        load_mixer_profile(path)


def test_compact_spatial_profile_converts_to_the_strict_seven_zone_format():
    compact = SpatialCoreProfile(
        center_anchor=0.70,
        front_distance_m=2.0,
        front_width_deg=42.0,
        bed_width_gain=0.30,
        bed_rear_gain=0.20,
        bed_air_gain=0.10,
        direct_ratio=0.74,
        early_reflection_level_db=-19.0,
        late_reverb_level_db=-29.0,
        late_rt60_s=0.42,
    )

    mixer = mixer_profile_from_spatial_core(compact)

    assert mixer.extraction.center_anchor == 0.70
    assert mixer.zones["front_L_residual"].azimuth_deg == 42.0
    assert mixer.zones["front_R_residual"].azimuth_deg == -42.0
    assert mixer.zones["center_anchor"].distance_m == 2.0
    assert mixer.zones["side_width"].field_gain == pytest.approx(0.30)
    assert mixer.room.late_rt60_s == 0.42


def test_profile_loader_accepts_reordered_json_zone_keys_and_canonicalizes_them(tmp_path):
    profile = MixerProfile.default()
    payload = profile.to_payload()
    payload["zones"] = dict(reversed(list(payload["zones"].items())))
    path = tmp_path / "reordered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_mixer_profile(path)

    assert tuple(loaded.zones) == tuple(profile.zones)
    assert loaded.profile_hash == profile.profile_hash


def test_extraction_front_weight_curve_must_not_rise_toward_high_frequencies():
    with pytest.raises(ValueError, match="front_side_weight_low"):
        ExtractionSettings(front_side_weight_low=0.6, front_side_weight_high=0.8)
