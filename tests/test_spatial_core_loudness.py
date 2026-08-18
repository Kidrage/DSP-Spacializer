import numpy as np
import pytest

from spatial_core.loudness import (
    _k_weighting_coefficients,
    integrated_loudness_bs1770,
    level_match_group_bs1770,
)


def test_bs1770_48khz_k_weighting_matches_reference_coefficients():
    (shelf_b, shelf_a), (highpass_b, highpass_a) = _k_weighting_coefficients(48_000)

    assert shelf_b == pytest.approx(
        [1.53512485958697, -2.69169618940638, 1.19839281085285],
        abs=1e-12,
    )
    assert shelf_a == pytest.approx(
        [1.0, -1.69065929318241, 0.73248077421585],
        abs=1e-12,
    )
    assert highpass_b == pytest.approx([1.0, -2.0, 1.0], abs=1e-12)
    assert highpass_a == pytest.approx(
        [1.0, -1.99004745483398, 0.99007225036621],
        abs=1e-12,
    )


def test_bs1770_integrated_loudness_tracks_a_known_gain_change():
    sample_rate = 48_000
    time = np.arange(sample_rate * 2, dtype=np.float64) / sample_rate
    stereo = np.stack(
        [
            0.05 * np.sin(2.0 * np.pi * 440.0 * time),
            0.04 * np.sin(2.0 * np.pi * 660.0 * time),
        ],
        axis=1,
    ).astype(np.float32)

    baseline_lkfs = integrated_loudness_bs1770(stereo, sample_rate)
    raised_lkfs = integrated_loudness_bs1770(stereo * (10.0 ** (6.0 / 20.0)), sample_rate)

    assert raised_lkfs - baseline_lkfs == pytest.approx(6.0, abs=0.01)


def test_group_level_match_uses_a_shared_headroom_gain_without_loudness_bias():
    sample_rate = 48_000
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    reference = np.stack(
        [
            0.40 * np.sin(2.0 * np.pi * 220.0 * time),
            0.35 * np.sin(2.0 * np.pi * 330.0 * time),
        ],
        axis=1,
    ).astype(np.float32)
    signals = {
        "A": reference,
        "B": reference * 0.25,
        "C": reference * 1.8,
    }

    result = level_match_group_bs1770(
        signals,
        sample_rate,
        reference_key="A",
        peak_ceiling=0.30,
    )

    matched_loudness = [item.matched_loudness_lkfs for item in result.signals.values()]
    assert max(matched_loudness) - min(matched_loudness) < 0.01
    assert result.shared_headroom_gain_db < 0.0
    assert all(item.sample_peak <= 0.30 + 1e-6 for item in result.signals.values())
    assert result.final_target_loudness_lkfs == pytest.approx(
        result.reference_loudness_lkfs + result.shared_headroom_gain_db,
        abs=0.01,
    )
