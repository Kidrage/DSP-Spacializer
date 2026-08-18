import numpy as np
import pytest

from spatial_core import SpatialCoreProfile, build_scene, encode_mono_foa, foa_direction_vector


def test_foa_uses_ambix_acn_sn3d_channel_order():
    signal = np.ones(8, dtype=np.float32)

    front = encode_mono_foa(signal, azimuth_deg=0, elevation_deg=0)
    left = encode_mono_foa(signal, azimuth_deg=90, elevation_deg=0)
    above = encode_mono_foa(signal, azimuth_deg=0, elevation_deg=90)

    assert np.allclose(front[0], [1, 0, 0, 1], atol=1e-6)
    assert np.allclose(left[0], [1, 1, 0, 0], atol=1e-6)
    assert np.allclose(above[0], [1, 0, 1, 0], atol=1e-6)
    assert np.allclose(foa_direction_vector(-90, 0), [1, -1, 0, 0], atol=1e-6)


def test_default_builder_creates_direct_objects_and_foa_bed():
    frames = 256
    stereo = np.zeros((frames, 2), dtype=np.float32)
    stereo[:, 0] = np.linspace(-0.2, 0.2, frames)
    stereo[:, 1] = np.linspace(0.2, -0.2, frames)

    scene = build_scene(stereo, sample_rate=48_000)

    positions = {item.object_id: item.azimuth_deg for item in scene.objects}
    assert positions == {
        "bass": 0.0,
        "center_anchor": 0.0,
        "front_L_residual": 35.0,
        "front_R_residual": -35.0,
    }
    assert scene.bed is not None
    assert scene.bed.audio.shape == (frames, 4)
    assert scene.metadata["source"] == "dsp_bus_builder"
    assert scene.metadata["zones"] == [
        "bass",
        "center_anchor",
        "front_L_residual",
        "front_R_residual",
        "side_width",
        "rear_ambience",
        "high_air",
    ]
    assert scene.metadata["profile"] == {
        "center_anchor": 0.8,
        "front_distance_m": 1.6,
        "front_width_deg": 35.0,
        "bed_width_gain": 0.25,
        "bed_rear_gain": 0.18,
        "bed_air_gain": 0.12,
        "direct_ratio": 0.78,
        "early_reflection_level_db": -21.0,
        "late_reverb_level_db": -27.0,
        "late_rt60_s": 0.35,
    }


def test_builder_applies_compact_front_spatial_parameters():
    stereo = np.zeros((2048, 2), dtype=np.float32)
    profile = SpatialCoreProfile(
        front_distance_m=2.2,
        front_width_deg=48.0,
        direct_ratio=0.7,
    )

    scene = build_scene(stereo, profile=profile, sample_rate=48_000)
    objects = {item.object_id: item for item in scene.objects}

    assert objects["bass"].distance_m == 2.2
    assert objects["center_anchor"].distance_m == 2.2
    assert objects["front_L_residual"].azimuth_deg == 48.0
    assert objects["front_R_residual"].azimuth_deg == -48.0
    assert all(item.direct_ratio == 0.7 for item in scene.objects)
    assert all(item.gain_db == 0.0 for item in scene.objects)
    assert scene.metadata["mastered_reference_rms"] == pytest.approx(0.0)


def test_builder_serializes_active_frontal_experiment_controls():
    stereo = np.zeros((2_048, 2), dtype=np.float32)
    profile = SpatialCoreProfile(
        hrtf_compensation_mode="off",
        mastered_loudness_mode="fixed_scene_gain",
        center_room_send_db=0.0,
        reflection_normalization_mode="physical_path_gain",
    )

    scene = build_scene(stereo, profile=profile, sample_rate=48_000)

    assert scene.metadata["profile"] == {
        "center_anchor": 0.8,
        "front_distance_m": 1.6,
        "front_width_deg": 35.0,
        "bed_width_gain": 0.25,
        "bed_rear_gain": 0.18,
        "bed_air_gain": 0.12,
        "direct_ratio": 0.78,
        "early_reflection_level_db": -21.0,
        "late_reverb_level_db": -27.0,
        "late_rt60_s": 0.35,
        "hrtf_compensation_mode": "off",
        "mastered_loudness_mode": "fixed_scene_gain",
        "center_room_send_db": 0.0,
        "reflection_normalization_mode": "physical_path_gain",
        "direct_ratio_mode": "manual",
    }


def test_builder_rejects_unknown_mapping_profile_parameters():
    stereo = np.zeros((2048, 2), dtype=np.float32)

    with pytest.raises(ValueError, match="unknown spatial profile parameter"):
        build_scene(stereo, profile={"front_distance_m": 1.6, "notes": 1.0})
