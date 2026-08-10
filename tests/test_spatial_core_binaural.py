import json

import numpy as np
import pytest
import sofar

from spatial_core import (
    FoaBed,
    ListenerTrajectory,
    MicroMotion,
    SofaBinauralRenderer,
    SofaHrirDatabase,
    SpatialObject,
    SpatialScene,
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


def test_seeded_micro_motion_is_bounded_and_repeatable():
    first = MicroMotion(seed=7)
    second = MicroMotion(seed=7)

    first_angles = np.asarray([first.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])
    second_angles = np.asarray([second.rotation_at(t).as_euler("zyx", degrees=True) for t in np.arange(0, 8, 0.2)])

    assert np.allclose(first_angles, second_angles)
    assert np.max(np.abs(first_angles[:, 0])) <= 5.0
    assert np.max(np.abs(first_angles[:, 1])) <= 3.0
