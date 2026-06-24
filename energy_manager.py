"""Gain staging for the spatializer.

The original implementation matched the sum of all four output channels to
the stereo input. That is energy-conserving, but it turns the front pair down
as soon as material is sent to the rears. For an upmixer the front pair is the
stable perceptual anchor, so the default mode now matches LF/RF to input L/R.
"""

import numpy as np

from dsp_utils import EPS, db


def match_energy(
    input_audio,
    output_audio,
    sample_rate=None,
    max_boost_db=3.0,
    max_cut_db=-3.0,
    reference="front",
    return_report=False,
):
    """Match output gain to the stereo input with safe gain limits.

    ``reference="front"`` aligns LF/RF energy with input L/R so routing
    content to LB/RB does not silently reduce the front anchor.
    ``reference="all"`` retains the legacy total-four-channel behaviour.

    When ``return_report`` is true, return ``(audio, report)``. The default
    return type remains the processed array for compatibility.
    """
    del sample_rate
    left, right = input_audio
    output_audio = np.asarray(output_audio, dtype=np.float32)
    input_energy = np.mean(left**2 + right**2) + EPS
    if output_audio.ndim != 2 or output_audio.shape[1] < 2:
        raise ValueError("output_audio must have shape [samples, channels>=2]")
    if reference == "front":
        reference_audio = output_audio[:, :2]
    elif reference == "all":
        reference_audio = output_audio
    else:
        raise ValueError("reference must be 'front' or 'all'")

    reference_energy = np.mean(np.sum(reference_audio**2, axis=1)) + EPS
    target_gain = np.sqrt(input_energy / reference_energy)

    min_gain = 10 ** (max_cut_db / 20.0)
    max_gain = 10 ** (max_boost_db / 20.0)
    gain = float(np.clip(target_gain, min_gain, max_gain))
    matched = (output_audio * gain).astype(np.float32)
    report = {
        "version": 2,
        "reference": reference,
        "input_stereo_energy": float(input_energy),
        "output_reference_energy_before": float(reference_energy),
        "target_gain_db": float(db(target_gain)),
        "applied_gain_db": float(db(gain)),
        "gain_limited": bool(abs(gain - target_gain) > 1e-7),
        "max_boost_db": float(max_boost_db),
        "max_cut_db": float(max_cut_db),
    }
    if return_report:
        return matched, report
    return matched


def soft_clip(audio, threshold=0.95, knee_width=0.05):
    """Compatibility helper kept for older imports; limiter now handles peaks."""
    del knee_width
    audio = np.asarray(audio, dtype=np.float32)
    return (np.tanh(audio / max(threshold, EPS)) * threshold).astype(np.float32)
