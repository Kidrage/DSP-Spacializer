from dataclasses import replace

import numpy as np
import soundfile as sf

from spatial_core.builder import build_scene
from spatial_core.scene import load_scene, save_scene
from spatial_core.workflow import render_spatial_v2
from spatial_mixer import MixerProfile
from spatial_mixer import save_mixer_profile
from spatial_mixer.rendering import build_mixer_scene, extract_mixer_zones


def test_default_mixer_scene_is_equivalent_to_v21_builder():
    rng = np.random.default_rng(20260811)
    stereo = rng.normal(0.0, 0.08, (4096, 2)).astype(np.float32)

    baseline = build_scene(stereo)
    candidate = build_mixer_scene(stereo, MixerProfile.default())

    assert [item.object_id for item in candidate.objects] == [
        item.object_id for item in baseline.objects
    ]
    for actual, expected in zip(candidate.objects, baseline.objects):
        np.testing.assert_allclose(actual.audio, expected.audio, atol=1e-7)
        assert actual.azimuth_deg == expected.azimuth_deg
        assert actual.elevation_deg == expected.elevation_deg
        assert actual.distance_m == expected.distance_m
        assert actual.gain_db == expected.gain_db
        assert actual.size == expected.size
        assert actual.diffusion == expected.diffusion
        assert actual.direct_ratio == expected.direct_ratio
    np.testing.assert_allclose(candidate.bed.audio, baseline.bed.audio, atol=1e-7)


def test_extraction_lab_controls_change_masks_without_breaking_reconstruction():
    sample_rate = 48_000
    t = np.arange(8192, dtype=np.float64) / sample_rate
    stereo = np.stack(
        [
            0.20 * np.sin(2.0 * np.pi * 100.0 * t) + 0.05 * np.sin(2.0 * np.pi * 6_000.0 * t),
            0.20 * np.sin(2.0 * np.pi * 100.0 * t) - 0.05 * np.sin(2.0 * np.pi * 6_000.0 * t),
        ],
        axis=1,
    ).astype(np.float32)
    default = MixerProfile.default()
    narrow_bass = replace(
        default,
        extraction=replace(default.extraction, bass_low_hz=30.0, bass_high_hz=60.0),
    )

    default_zones = extract_mixer_zones(stereo, default, sample_rate=sample_rate)
    candidate_zones = extract_mixer_zones(stereo, narrow_bass, sample_rate=sample_rate)

    assert np.linalg.norm(candidate_zones.bass) < 0.25 * np.linalg.norm(default_zones.bass)
    error = stereo - candidate_zones.reconstruct_stereo()
    error_db = 20.0 * np.log10(
        max(float(np.sqrt(np.mean(error.astype(np.float64) ** 2))), 1e-12)
        / float(np.sqrt(np.mean(stereo.astype(np.float64) ** 2)))
    )
    assert error_db < -80.0


def test_object_room_trims_survive_scene_interchange(tmp_path):
    default = MixerProfile.default()
    zones = dict(default.zones)
    zones["bass"] = replace(
        zones["bass"],
        early_reflection_trim_db=3.0,
        late_reverb_trim_db=-4.0,
    )
    profile = replace(default, zones=zones)
    scene = build_mixer_scene(np.zeros((2048, 2), dtype=np.float32), profile)

    manifest = tmp_path / "scene.json"
    save_scene(scene, manifest)
    loaded = load_scene(manifest)

    assert loaded.objects[0].early_reflection_trim_db == 3.0
    assert loaded.objects[0].late_reverb_trim_db == -4.0


def test_file_workflow_accepts_new_mixer_profile_without_legacy_profile(tmp_path):
    sample_rate = 48_000
    t = np.arange(4096, dtype=np.float64) / sample_rate
    stereo = np.stack(
        [np.sin(2.0 * np.pi * 440.0 * t), np.sin(2.0 * np.pi * 660.0 * t)],
        axis=1,
    ).astype(np.float32) * 0.05
    input_path = tmp_path / "input.wav"
    sf.write(input_path, stereo, sample_rate, subtype="FLOAT")
    profile_path = save_mixer_profile(MixerProfile.default(), tmp_path / "profile.json")

    result = render_spatial_v2(
        input_path=input_path,
        scene_manifest=None,
        output_dir=tmp_path / "output",
        output_mode="4ch",
        target_sample_rate=sample_rate,
        sofa_path=None,
        room_profile="balanced-depth",
        mixer_profile_path=profile_path,
    )

    assert result["profile_format"] == "spatial_mixer_profile/1.0"
    assert (tmp_path / "output" / "input_spatial_v2_quad.wav").is_file()
