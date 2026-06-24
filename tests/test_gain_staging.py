import numpy as np

from energy_manager import match_energy
from limiter import apply_limiter
from auto_refine import summarize_refine_actions


def _pair_energy(audio):
    return float(np.mean(np.sum(audio * audio, axis=1)))


def test_match_energy_anchors_front_pair_not_all_channels():
    samples = 4800
    t = np.arange(samples, dtype=np.float32) / 48000.0
    left = 0.2 * np.sin(2.0 * np.pi * 440.0 * t)
    right = 0.2 * np.sin(2.0 * np.pi * 660.0 * t)
    output = np.column_stack((left * 0.5, right * 0.5, left, right)).astype(np.float32)

    matched, report = match_energy(
        (left, right), output, max_boost_db=9.0,
        reference="front", return_report=True,
    )

    assert np.isclose(_pair_energy(matched[:, :2]), _pair_energy(np.column_stack((left, right))), rtol=1e-5)
    assert report["reference"] == "front"
    assert np.isclose(report["applied_gain_db"], 6.0206, atol=0.01)


def test_match_energy_legacy_all_mode_remains_available():
    source = np.full(1000, 0.1, dtype=np.float32)
    output = np.column_stack((source, source, source, source))
    matched = match_energy(
        (source, source), output, max_cut_db=-6.0, reference="all",
    )

    assert np.isclose(_pair_energy(matched), _pair_energy(np.column_stack((source, source))), rtol=1e-5)


def test_limiter_only_attenuates_region_around_peak():
    sample_rate = 48000
    audio = np.full((sample_rate, 4), 0.1, dtype=np.float32)
    audio[sample_rate // 2, :] = 2.0

    limited, report = apply_limiter(audio, sample_rate=sample_rate, return_report=True)

    assert float(np.max(np.abs(limited))) <= 0.980001
    assert np.allclose(limited[: sample_rate // 4], audio[: sample_rate // 4])
    assert limited[-1, 0] > 0.0995
    assert report["max_gain_reduction_db"] > 6.0
    assert report["active_frame_fraction"] < 0.75


def test_limiter_uses_one_gain_envelope_for_all_channels():
    audio = np.zeros((4800, 4), dtype=np.float32)
    audio[:, 0] = 0.2
    audio[:, 1] = 0.4
    audio[:, 2] = 0.6
    audio[:, 3] = 0.8
    audio[2400, 3] = 1.6

    limited = apply_limiter(audio)
    index = 2400
    gains = limited[index, :3] / audio[index, :3]

    assert np.allclose(gains, gains[0], atol=1e-6)
    assert float(np.max(np.abs(limited))) <= 0.980001


def test_refine_summary_handles_overshoot_guard_record():
    lines = summarize_refine_actions([{
        "reason": "overshoot_guard_reverted",
        "spatial_excess_delta": 0.21,
        "high_harshness_delta": 0.0,
        "low_mid_mud_delta": 0.31,
        "reverted_actions": [{"reason": "rear_presence_low"}],
    }])

    assert "reverted 1 action(s)" in lines[0]
