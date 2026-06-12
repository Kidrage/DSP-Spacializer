"""Energy matching for the spatializer."""

import numpy as np

from dsp_utils import EPS


def match_energy(input_audio, output_audio, sample_rate=None, max_boost_db=1.0, max_cut_db=-3.0):
    """Match 4ch output energy to the stereo input with safe gain limits.

    Notebook 对应：Cell 25 ``match_energy_to_input``。
    使用 L/R 总能量对齐 LF/RF/LB/RB 总能量，避免空间化后整体音量忽大忽小。
    """
    del sample_rate
    left, right = input_audio
    output_audio = np.asarray(output_audio, dtype=np.float32)
    input_energy = np.mean(left**2 + right**2) + EPS
    output_energy = np.mean(np.sum(output_audio**2, axis=1)) + EPS
    target_gain = np.sqrt(input_energy / output_energy)

    min_gain = 10 ** (max_cut_db / 20.0)
    max_gain = 10 ** (max_boost_db / 20.0)
    gain = float(np.clip(target_gain, min_gain, max_gain))
    return (output_audio * gain).astype(np.float32)


def soft_clip(audio, threshold=0.95, knee_width=0.05):
    """Compatibility helper kept for older imports; limiter now handles peaks."""
    del knee_width
    audio = np.asarray(audio, dtype=np.float32)
    return (np.tanh(audio / max(threshold, EPS)) * threshold).astype(np.float32)