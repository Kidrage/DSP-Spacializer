import numpy as np

from dsp_utils import band_split


def extract_layers(left, right, sample_rate):
    """Extract notebook-aligned spatial-function layers.

    These are not clean stems; they are DSP buses:
    ``bass``, ``low_body``, ``front_L``, ``front_R``, ``side_width``,
    ``rear_ambience`` and ``high_air``.
    """
    left_bands = band_split(left, sample_rate)
    right_bands = band_split(right, sample_rate)

    mid_bands = {name: 0.70710678 * (left_bands[name] + right_bands[name]) for name in left_bands}
    side_bands = {name: 0.70710678 * (left_bands[name] - right_bands[name]) for name in left_bands}

    bass = mid_bands["bass"]
    low_body = 0.95 * mid_bands["low_mid"] + 0.12 * mid_bands["mid"]

    front_l = (
        left_bands["low_mid"]
        + left_bands["mid"]
        + 0.96 * left_bands["high_mid"]
        + 0.62 * left_bands["air"]
    )
    front_r = (
        right_bands["low_mid"]
        + right_bands["mid"]
        + 0.96 * right_bands["high_mid"]
        + 0.62 * right_bands["air"]
    )

    side_width = (
        0.05 * side_bands["low_mid"]
        + 0.28 * side_bands["mid"]
        + 0.92 * side_bands["high_mid"]
        + 0.82 * side_bands["air"]
    )

    rear_ambience = (
        0.018 * side_bands["mid"]
        + 0.88 * side_bands["high_mid"]
        + 0.54 * side_bands["air"]
        + 0.014 * mid_bands["high_mid"]
        + 0.018 * mid_bands["air"]
    )

    high_air = 0.76 * side_bands["air"] + 0.08 * mid_bands["air"]

    return {
        "bass": bass.astype(np.float32),
        "low_body": low_body.astype(np.float32),
        "front_L": front_l.astype(np.float32),
        "front_R": front_r.astype(np.float32),
        "side_width": side_width.astype(np.float32),
        "rear_ambience": rear_ambience.astype(np.float32),
        "high_air": high_air.astype(np.float32),
    }