import json

import numpy as np
import pytest
import sofar
from scipy.signal import firwin2

from spatial_core import (
    FoaBed,
    ListenerTrajectory,
    MicroMotion,
    SofaBinauralRenderer,
    SofaHrirDatabase,
    SpatialCoreProfile,
    SpatialObject,
    SpatialScene,
    build_scene,
    evaluate_clarity_gate,
    measure_clarity_metrics,
)
from spatial_core.binaural import _late_reverb_foa, _match_mastered_loudness


def _write_test_sofa(path, directions=None):
    directions = directions or [
        (0, 0),
        (45, 0),
        (90, 0),
        (135, 0),
        (180, 0),
        (-135, 0),
        (-90, 0),
        (-45, 0),
        (0, 45),
        (0, -45),
    ]
    sofa = sofar.Sofa("SimpleFreeFieldHRIR")
    sofa.SourcePosition = np.asarray([[az, el, 1] for az, el in directions], dtype=float)
    sofa.Data_IR = np.zeros((len(directions), 2, 48), dtype=float)
    for index, (azimuth, _elevation) in enumerate(directions):
        lateral = np.sin(np.deg2rad(azimuth))
        left_delay = 5 + int(round(max(0.0, -lateral) * 3))
        right_delay = 5 + int(round(max(0.0, lateral) * 3))
        sofa.Data_IR[index, 0, left_delay] = 1.0 - max(0.0, -lateral) * 0.25
        sofa.Data_IR[index, 1, right_delay] = 1.0 - max(0.0, lateral) * 0.25
    sofa.Data_Delay = np.zeros((len(directions), 2), dtype=float)
    sofa.Data_SamplingRate = 48_000
    sofar.write_sofa(path, sofa)
    return sofa


def _write_colored_test_sofa(path):
    directions = [
        (0, 0),
        (45, 0),
        (90, 0),
        (135, 0),
        (180, 0),
        (-135, 0),
        (-90, 0),
        (-45, 0),
        (0, 45),
        (0, -45),
    ]
    sofa = sofar.Sofa("SimpleFreeFieldHRIR")
    sofa.SourcePosition = np.asarray([[az, el, 1] for az, el in directions], dtype=float)
    common_response = firwin2(
        513,
        np.asarray([0, 50, 100, 250, 1_000, 3_000, 8_000, 24_000]) / 24_000,
        [0.05, 0.05, 0.15, 0.4, 1.0, 5.0, 0.7, 0.5],
    )
    sofa.Data_IR = np.zeros((len(directions), 2, common_response.size + 8), dtype=float)
    for index, (azimuth, _elevation) in enumerate(directions):
        lateral = np.sin(np.deg2rad(azimuth))
        left_delay = 5 + int(round(max(0.0, -lateral) * 3))
        right_delay = 5 + int(round(max(0.0, lateral) * 3))
        left_gain = 1.0 - max(0.0, -lateral) * 0.25
        right_gain = 1.0 - max(0.0, lateral) * 0.25
        sofa.Data_IR[index, 0, left_delay : left_delay + common_response.size] = (
            left_gain * common_response
        )
        sofa.Data_IR[index, 1, right_delay : right_delay + common_response.size] = (
            right_gain * common_response
        )
    sofa.Data_Delay = np.zeros((len(directions), 2), dtype=float)
    sofa.Data_SamplingRate = 48_000
    sofar.write_sofa(path, sofa)


def test_sofa_exact_match_preserves_measured_hrir(tmp_path):
    source = _write_test_sofa(tmp_path / "test.sofa")
    database = SofaHrirDatabase(tmp_path / "test.sofa", 48_000)

    result = database.interpolate(90, 0)

    assert np.array_equal(result.ir, source.Data_IR[2])
    assert np.array_equal(result.delay_samples, [0, 0])
    assert result.nearest_error_deg == pytest.approx(0.0)
    assert database.front_reference_gain == pytest.approx(1.0)


def test_sofa_rejects_directions_outside_coverage(tmp_path):
    _write_test_sofa(tmp_path / "front-only.sofa", [(0, 0), (10, 0), (-10, 0), (0, 10)])
    database = SofaHrirDatabase(tmp_path / "front-only.sofa", 48_000)

    with pytest.raises(ValueError, match="outside SOFA coverage"):
        database.interpolate(180, 0)


def test_sofa_rejects_directions_that_cannot_decode_foa(tmp_path):
    _write_test_sofa(tmp_path / "horizontal.sofa", [(0, 0), (90, 0), (180, 0), (-90, 0)])

    with pytest.raises(ValueError, match="rank-4"):
        SofaHrirDatabase(tmp_path / "horizontal.sofa", 48_000)


def test_binaural_renderer_renders_objects_foa_and_head_motion(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    impulse = np.zeros(2048, dtype=np.float32)
    impulse[64] = 0.3
    bed = np.zeros((2048, 4), dtype=np.float32)
    bed[128, 0] = 0.05
    scene = SpatialScene(
        48_000,
        [SpatialObject("lead", "front", impulse, 45, 0, 1.2, size=0.2, diffusion=0.1)],
        FoaBed(bed),
    )
    trajectory_path = tmp_path / "trajectory.json"
    trajectory_path.write_text(
        json.dumps(
            {
                "format": "spatial_core_listener_trajectory",
                "version": "1.0",
                "keyframes": [
                    {"time": 0.0, "yaw": 0, "pitch": 0, "roll": 0},
                    {"time": 0.05, "yaw": 30, "pitch": 0, "roll": 0},
                ],
            }
        ),
        encoding="utf-8",
    )
    renderer = SofaBinauralRenderer(
        tmp_path / "test.sofa",
        listener_trajectory=ListenerTrajectory.load(trajectory_path),
        room_enabled=False,
        block_size=256,
    )

    with pytest.warns(RuntimeWarning, match="SOFA directional coverage is sparse"):
        result = renderer.render(scene)

    assert result.audio.shape[0] > 2048
    assert result.audio.shape[1] == 2
    assert np.all(np.isfinite(result.audio))
    assert np.max(np.abs(result.audio)) > 0
    assert result.diagnostics["engine"] == "spatial-v2-sofa"
    assert result.diagnostics["head_motion"] is True


def test_binaural_renderer_removes_common_hrtf_timbre_coloration(tmp_path):
    _write_colored_test_sofa(tmp_path / "colored.sofa")
    sample_rate = 48_000
    frequencies = np.asarray([30, 50, 100, 250, 1_000, 3_000, 8_000], dtype=float)
    time = np.arange(sample_rate, dtype=float) / sample_rate
    signal = np.sum(np.sin(2.0 * np.pi * frequencies[:, None] * time), axis=0)
    signal = np.asarray(0.02 * signal, dtype=np.float32)
    scene = SpatialScene(sample_rate, [SpatialObject("reference", "front", signal)])

    result = SofaBinauralRenderer(tmp_path / "colored.sofa", room_enabled=False).render(scene)

    mono = np.mean(result.audio[6_000:42_000], axis=1)
    analysis_time = np.arange(mono.size, dtype=float) / sample_rate
    amplitudes = []
    for frequency in frequencies:
        phase = 2.0 * np.pi * frequency * analysis_time
        amplitudes.append(
            2.0
            / mono.size
            * np.hypot(np.dot(mono, np.sin(phase)), np.dot(mono, np.cos(phase)))
        )
    relative_db = 20.0 * np.log10(np.maximum(amplitudes, 1e-12) / amplitudes[4])

    assert np.max(np.abs(relative_db)) < 3.0
    assert result.diagnostics["hrtf_timbre_compensation"] == "front-common-field"


def test_binaural_renderer_can_disable_front_common_field_compensation(tmp_path):
    _write_colored_test_sofa(tmp_path / "colored.sofa")
    signal = np.zeros(4_096, dtype=np.float32)
    signal[512] = 0.05
    scene = SpatialScene(48_000, [SpatialObject("reference", "front", signal)])

    legacy = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
    ).render(scene)
    uncompensated = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
        profile=SpatialCoreProfile(hrtf_compensation_mode="off"),
    ).render(scene)

    assert uncompensated.audio.shape == legacy.audio.shape
    assert not np.allclose(uncompensated.audio, legacy.audio)
    assert uncompensated.diagnostics["hrtf_timbre_compensation"] == "off"
    assert uncompensated.diagnostics["hrtf_compensation_phase"] == "disabled"


def test_binaural_renderer_can_dose_front_common_field_compensation(tmp_path):
    _write_colored_test_sofa(tmp_path / "colored.sofa")
    signal = np.zeros(4_096, dtype=np.float32)
    signal[512] = 0.01
    scene = SpatialScene(48_000, [SpatialObject("reference", "front", signal)])

    common = {
        "mastered_loudness_mode": "fixed_scene_gain",
    }
    legacy = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
        profile=SpatialCoreProfile(**common),
    ).render(scene)
    uncompensated = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
        profile=SpatialCoreProfile(hrtf_compensation_mode="off", **common),
    ).render(scene)
    half = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
        profile=SpatialCoreProfile(hrtf_compensation_strength=0.5, **common),
    ).render(scene)

    nfft = 1 << int(np.ceil(np.log2(legacy.audio.shape[0])))
    legacy_magnitude = np.abs(np.fft.rfft(legacy.audio[:, 0], nfft))
    half_magnitude = np.abs(np.fft.rfft(half.audio[:, 0], nfft))
    dry_magnitude = np.abs(np.fft.rfft(uncompensated.audio[:, 0], nfft))
    frequencies = np.fft.rfftfreq(nfft, 1.0 / 48_000)
    legacy_db = 20.0 * np.log10(
        np.maximum(legacy_magnitude, 1e-12) / np.maximum(dry_magnitude, 1e-12)
    )
    half_db = 20.0 * np.log10(
        np.maximum(half_magnitude, 1e-12) / np.maximum(dry_magnitude, 1e-12)
    )
    informative = (
        (frequencies >= 50.0)
        & (frequencies <= 16_000.0)
        & (np.abs(legacy_db) >= 1.0)
    )

    assert (
        np.median(np.abs(half_db[informative] - 0.5 * legacy_db[informative]))
        < 0.35
    )
    zero = SofaBinauralRenderer(
        tmp_path / "colored.sofa",
        room_enabled=False,
        profile=SpatialCoreProfile(hrtf_compensation_strength=0.0, **common),
    ).render(scene)
    assert np.array_equal(zero.audio, uncompensated.audio)
    assert "hrtf_compensation_strength" not in legacy.diagnostics
    assert half.diagnostics["hrtf_compensation_strength"] == 0.5


def test_common_field_compensation_preserves_interaural_cues(tmp_path):
    _write_colored_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(4_096, dtype=np.float32)
    signal[512] = 0.1
    scene = SpatialScene(
        48_000,
        [SpatialObject("right", "front", signal, azimuth_deg=90.0)],
    )

    result = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False).render(scene)

    left_peak = int(np.argmax(np.abs(result.audio[:, 0])))
    right_peak = int(np.argmax(np.abs(result.audio[:, 1])))
    interaural_level_ratio = (
        np.max(np.abs(result.audio[:, 1])) / np.max(np.abs(result.audio[:, 0]))
    )
    assert right_peak - left_peak == 3
    assert interaural_level_ratio == pytest.approx(0.75, rel=0.01)
    assert max(left_peak, right_peak) < 1_200
    assert result.diagnostics["hrtf_compensation_phase"] == "minimum"


def test_binaural_object_size_does_not_increase_coherent_level(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(4_096, dtype=np.float32)
    signal[512] = 0.02
    renderer = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False)

    point = renderer.render(
        SpatialScene(48_000, [SpatialObject("point", "front", signal, size=0.0)])
    )
    broad = renderer.render(
        SpatialScene(48_000, [SpatialObject("broad", "front", signal, size=0.25)])
    )

    level_ratio = np.linalg.norm(broad.audio) / np.linalg.norm(point.audio)
    assert level_ratio <= 1.05


def test_binaural_limiter_does_not_turn_down_the_whole_track_for_one_peak(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.full(48_000, 0.1, dtype=np.float32)
    signal[24_000] = 2.0
    scene = SpatialScene(48_000, [SpatialObject("music", "front", signal)])

    result = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False).render(scene)

    unaffected_level = float(np.median(np.abs(result.audio[5_000:15_000])))
    assert unaffected_level > 0.09
    assert np.max(np.abs(result.audio)) <= 0.98 + 1e-6
    assert result.diagnostics["limiter"]["mode"] == "linked_frame_envelope"


def test_distance_model_reduces_far_direct_sound(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(512, dtype=np.float32)
    signal[32] = 0.1
    renderer = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False)
    near = renderer.render(
        SpatialScene(48_000, [SpatialObject("near", "front", signal, distance_m=0.5)])
    )
    far = renderer.render(
        SpatialScene(48_000, [SpatialObject("far", "front", signal, distance_m=5.0)])
    )

    assert np.linalg.norm(far.audio) < np.linalg.norm(near.audio) * 0.4


def test_distance_curve_direct_ratio_remains_frozen_after_fex0(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")

    with pytest.raises(ValueError, match="reserved for frozen FEX-2"):
        SofaBinauralRenderer(
            tmp_path / "test.sofa",
            profile=SpatialCoreProfile(direct_ratio_mode="distance_curve"),
        )


def test_level_matched_eval_remains_owned_by_the_fex1_exporter(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")

    with pytest.raises(ValueError, match="requires the FEX-1 evaluation exporter"):
        SofaBinauralRenderer(
            tmp_path / "test.sofa",
            profile=SpatialCoreProfile(mastered_loudness_mode="level_matched_eval"),
        )


def test_room_renderer_preserves_late_tail(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(256, dtype=np.float32)
    signal[-1] = 0.1
    scene = SpatialScene(48_000, [SpatialObject("ending", "front", signal, 0, 0, 2)])

    with pytest.warns(RuntimeWarning, match="SOFA directional coverage is sparse"):
        result = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=True).render(scene)

    assert result.audio.shape[0] >= 256 + int(0.5 * 48_000)
    assert np.max(np.abs(result.audio[256:])) > 0


def test_balanced_depth_reports_geometry_and_delays_late_field(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(512, dtype=np.float32)
    signal[64] = 0.02
    scene = SpatialScene(
        48_000,
        [SpatialObject("lead", "front", signal, 0, 0, 1.6, direct_ratio=0.78)],
    )

    with pytest.warns(RuntimeWarning, match="SOFA directional coverage is sparse"):
        result = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=SpatialCoreProfile(),
        ).render(scene)

    room = result.diagnostics["room_profile"]
    assert room["name"] == "balanced-depth"
    assert room["dimensions_m"] == [6.0, 5.0, 3.0]
    assert room["minimum_early_delay_ms"] == 8.0
    assert room["late_start_s"] >= 0.027
    assert room["late_highpass_hz"] == 180.0
    assert room["late_lowpass_hz"] == 8_000.0


def test_balanced_depth_reduces_center_room_send_by_three_db(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(1024, dtype=np.float32)
    signal[128] = 0.005
    profile = SpatialCoreProfile()

    def room_residual(role):
        scene = SpatialScene(
            48_000,
            [SpatialObject("lead", role, signal, 0, 0, 1.6, direct_ratio=profile.direct_ratio)],
        )
        wet = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=profile,
        ).render(scene).audio
        direct_gain_db = 20.0 * np.log10(np.sqrt(profile.direct_ratio))
        dry_scene = SpatialScene(
            48_000,
            [SpatialObject("lead", role, signal, 0, 0, 1.6, gain_db=direct_gain_db)],
        )
        dry = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False).render(
            dry_scene
        ).audio
        dry = np.pad(dry, ((0, wet.shape[0] - dry.shape[0]), (0, 0)))
        return wet - dry

    with pytest.warns(RuntimeWarning):
        center_room = room_residual("center")
    with pytest.warns(RuntimeWarning):
        front_room = room_residual("front")

    assert np.linalg.norm(center_room) / np.linalg.norm(front_room) == pytest.approx(
        10.0 ** (-3.0 / 20.0), rel=0.02
    )


def test_balanced_depth_center_room_send_trim_is_configurable(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(1_024, dtype=np.float32)
    signal[128] = 0.005
    profile = SpatialCoreProfile(center_room_send_db=0.0)

    def room_residual(role):
        scene = SpatialScene(
            48_000,
            [SpatialObject("lead", role, signal, 0, 0, 1.6, direct_ratio=profile.direct_ratio)],
        )
        wet = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=profile,
        ).render(scene).audio
        direct_gain_db = 20.0 * np.log10(np.sqrt(profile.direct_ratio))
        dry_scene = SpatialScene(
            48_000,
            [SpatialObject("lead", role, signal, 0, 0, 1.6, gain_db=direct_gain_db)],
        )
        dry = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False).render(
            dry_scene
        ).audio
        dry = np.pad(dry, ((0, wet.shape[0] - dry.shape[0]), (0, 0)))
        return wet - dry

    with pytest.warns(RuntimeWarning):
        center_room = room_residual("center")
    with pytest.warns(RuntimeWarning):
        front_room = room_residual("front")

    assert np.linalg.norm(center_room) / np.linalg.norm(front_room) == pytest.approx(
        1.0, rel=0.02
    )


def test_balanced_depth_direct_ratio_controls_wet_send(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(1024, dtype=np.float32)
    signal[128] = 0.005

    def room_residual(direct_ratio):
        wet_scene = SpatialScene(
            48_000,
            [SpatialObject("lead", "front", signal, 0, 0, 1.6, direct_ratio=direct_ratio)],
        )
        wet = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=SpatialCoreProfile(),
        ).render(wet_scene).audio
        dry_gain_db = 20.0 * np.log10(np.sqrt(direct_ratio))
        dry_scene = SpatialScene(
            48_000,
            [SpatialObject("lead", "front", signal, 0, 0, 1.6, gain_db=dry_gain_db)],
        )
        dry = SofaBinauralRenderer(tmp_path / "test.sofa", room_enabled=False).render(
            dry_scene
        ).audio
        dry = np.pad(dry, ((0, wet.shape[0] - dry.shape[0]), (0, 0)))
        return wet - dry

    with pytest.warns(RuntimeWarning):
        wetter = room_residual(0.5)
    with pytest.warns(RuntimeWarning):
        drier = room_residual(0.9)

    assert np.linalg.norm(wetter) / np.linalg.norm(drier) == pytest.approx(
        np.sqrt((1.0 - 0.5) / (1.0 - 0.9)), rel=0.03
    )


def test_balanced_depth_can_preserve_physical_reflection_path_gain(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    signal = np.zeros(1_024, dtype=np.float32)
    signal[128] = 0.005
    scene = SpatialScene(
        48_000,
        [SpatialObject("lead", "front", signal, 0, 0, 1.6, direct_ratio=0.78)],
    )

    with pytest.warns(RuntimeWarning):
        legacy = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=SpatialCoreProfile(),
        ).render(scene)
    with pytest.warns(RuntimeWarning):
        physical = SofaBinauralRenderer(
            tmp_path / "test.sofa",
            room_profile="balanced-depth",
            profile=SpatialCoreProfile(
                reflection_normalization_mode="physical_path_gain"
            ),
        ).render(scene)

    assert not np.allclose(physical.audio, legacy.audio)
    assert (
        physical.diagnostics["room_profile"]["reflection_normalization_mode"]
        == "physical_path_gain"
    )


def test_small_dry_late_reverb_keeps_legacy_decay_origin():
    sample_rate = 1_000
    impulse = np.asarray([1.0], dtype=np.float32)

    result = _late_reverb_foa(
        impulse,
        sample_rate,
        rt60_s=0.30,
        length_s=0.10,
        start_s=0.03,
    )

    time = np.arange(100, dtype=np.float64) / sample_rate
    envelope = 10.0 ** (-3.0 * time / 0.30)
    kernel = np.random.default_rng(32).standard_normal(100) * envelope
    kernel[:30] = 0.0
    kernel *= 0.08 / np.linalg.norm(kernel)
    assert result[:, 0] == pytest.approx(kernel, abs=1e-7)


def test_builder_scene_matches_mastered_input_rms_before_limiter(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    sample_rate = 48_000
    time = np.arange(8_192, dtype=np.float64) / sample_rate
    stereo = np.stack(
        [
            0.015 * np.sin(2.0 * np.pi * 220.0 * time),
            0.012 * np.sin(2.0 * np.pi * 330.0 * time),
        ],
        axis=1,
    ).astype(np.float32)
    scene = build_scene(stereo, sample_rate=sample_rate)

    result = SofaBinauralRenderer(
        tmp_path / "test.sofa",
        room_profile="off",
        room_enabled=False,
        block_size=8_192,
    ).render(scene)

    source_rms = np.sqrt(np.mean(stereo.astype(np.float64) ** 2))
    output_rms = np.sqrt(
        np.mean(result.audio[: stereo.shape[0]].astype(np.float64) ** 2)
    )
    assert output_rms == pytest.approx(source_rms, rel=0.01)
    assert abs(result.diagnostics["mastered_loudness_gain_db"]) > 0.1


def test_fixed_scene_gain_skips_render_time_input_rms_restoration(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    sample_rate = 48_000
    time = np.arange(8_192, dtype=np.float64) / sample_rate
    stereo = np.stack(
        [
            0.015 * np.sin(2.0 * np.pi * 220.0 * time),
            0.012 * np.sin(2.0 * np.pi * 330.0 * time),
        ],
        axis=1,
    ).astype(np.float32)
    profile = SpatialCoreProfile(mastered_loudness_mode="fixed_scene_gain")
    scene = build_scene(stereo, profile=profile, sample_rate=sample_rate)

    result = SofaBinauralRenderer(
        tmp_path / "test.sofa",
        room_profile="off",
        room_enabled=False,
        profile=profile,
        block_size=8_192,
    ).render(scene)

    source_rms = np.sqrt(np.mean(stereo.astype(np.float64) ** 2))
    output_rms = np.sqrt(
        np.mean(result.audio[: stereo.shape[0]].astype(np.float64) ** 2)
    )
    assert output_rms != pytest.approx(source_rms, rel=0.01)
    assert result.diagnostics["mastered_loudness_gain_db"] == 0.0
    assert result.diagnostics["mastered_loudness_mode"] == "fixed_scene_gain"


def test_mastered_loudness_match_preserves_peak_headroom():
    output = np.zeros((100, 2), dtype=np.float32)
    output[50] = 1.0
    scene = SpatialScene(
        48_000,
        [SpatialObject("reference", "front", np.zeros(100, dtype=np.float32))],
        metadata={"mastered_reference_rms": 1.0},
    )

    matched, _gain_db, peak_limited = _match_mastered_loudness(output, scene)

    assert np.max(np.abs(matched)) == pytest.approx(0.98)
    assert peak_limited is True


def test_seeded_micro_motion_is_bounded_and_repeatable():
    first = MicroMotion(seed=7)
    second = MicroMotion(seed=7)

    first_angles = np.asarray([first.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])
    second_angles = np.asarray([second.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])

    assert np.allclose(first_angles, second_angles)
    assert np.max(np.abs(first_angles[:, 0])) <= 5.0
    assert np.max(np.abs(first_angles[:, 1])) <= 3.0


def test_default_scene_reports_end_to_end_clarity_gate(tmp_path):
    _write_test_sofa(tmp_path / "test.sofa")
    sample_rate = 48_000
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    center = 0.04 * np.sin(2 * np.pi * 300 * time) + 0.025 * np.sin(
        2 * np.pi * 3_000 * time
    )
    side = 0.012 * np.sin(2 * np.pi * 1_500 * time)
    transient_time = np.arange(240, dtype=np.float64) / sample_rate
    transient = 0.08 * np.exp(-transient_time / 0.0015) * np.sin(
        2 * np.pi * 2_500 * transient_time
    )
    for start in range(0, sample_rate - transient.size, 4_800):
        center[start : start + transient.size] += transient
    stereo = np.stack([center + side, center - side], axis=1).astype(np.float32)
    profile = SpatialCoreProfile()
    scene = build_scene(stereo, profile=profile, sample_rate=sample_rate)

    output = SofaBinauralRenderer(
        tmp_path / "test.sofa",
        room_profile="off",
        room_enabled=False,
        profile=profile,
        block_size=8_192,
    ).render(scene).audio[: stereo.shape[0]]

    metrics = measure_clarity_metrics(stereo, output, sample_rate)
    gate = evaluate_clarity_gate(metrics)

    assert gate["pass"] is False
    assert set(gate["failures"]) == {
        "mid_side_balance_delta_db",
        "band_delta_db.sub",
        "band_delta_db.presence",
    }
