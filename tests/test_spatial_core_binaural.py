import json

import numpy as np
import pytest
import sofar
from scipy.signal import butter, firwin2, sosfiltfilt

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
)


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


def test_seeded_micro_motion_is_bounded_and_repeatable():
    first = MicroMotion(seed=7)
    second = MicroMotion(seed=7)

    first_angles = np.asarray([first.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])
    second_angles = np.asarray([second.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])

    assert np.allclose(first_angles, second_angles)
    assert np.max(np.abs(first_angles[:, 0])) <= 5.0
    assert np.max(np.abs(first_angles[:, 1])) <= 3.0


def test_default_scene_preserves_static_clarity_metrics(tmp_path):
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

    def clarity_metrics(audio):
        filtered = sosfiltfilt(
            butter(4, [250.0, 5_000.0], btype="bandpass", fs=sample_rate, output="sos"),
            audio,
            axis=0,
        )
        def rms(value):
            return np.sqrt(np.mean(np.asarray(value, dtype=float) ** 2)) + 1e-12
        return np.asarray(
            [
                20.0 * np.log10(np.max(np.abs(filtered)) / rms(filtered)),
                20.0 * np.log10(rms(np.diff(filtered, axis=0)) / rms(filtered)),
            ]
        )

    delta = clarity_metrics(output) - clarity_metrics(stereo)
    assert delta[0] >= -1.0
    assert delta[1] >= -0.5
