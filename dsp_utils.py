"""Shared DSP helpers for the stereo -> 4.0 spatializer.

This module mirrors the utility layer in
``streaming_stereo_spatializer_clean_workflow.ipynb`` so that the script
pipeline and the notebook use the same assumptions: float32 processing,
48 kHz target sample-rate, causal filters, peak/rms helpers, and lightweight
delay utilities.
"""

import math

import numpy as np
from scipy import signal

EPS = 1e-9


def rms(x):
    x = np.asarray(x, dtype=np.float32)
    return float(np.sqrt(np.mean(x * x) + EPS))


def peak(x):
    return float(np.max(np.abs(x)) + EPS)


def db(x):
    return 20.0 * math.log10(max(float(x), EPS))


def normalize_peak(x, peak_target=0.98):
    p = peak(x)
    if p > peak_target:
        return (x * (peak_target / p)).astype(np.float32)
    return np.asarray(x, dtype=np.float32)


def peak_normalize_exact(x, peak_target=0.98):
    p = peak(x)
    if p <= EPS:
        return np.asarray(x, dtype=np.float32)
    return (x * (peak_target / p)).astype(np.float32)


def butter_sos(kind, sample_rate, cutoff, order=4):
    return signal.butter(order, cutoff, btype=kind, fs=sample_rate, output="sos")


def filt_sos(x, sos):
    # Causal filtering: closer to streaming behavior than zero-phase filtfilt.
    return signal.sosfilt(sos, np.asarray(x, dtype=np.float32)).astype(np.float32)


def lowpass(x, sample_rate, cutoff, order=4):
    return filt_sos(x, butter_sos("lowpass", sample_rate, cutoff, order))


def highpass(x, sample_rate, cutoff, order=4):
    return filt_sos(x, butter_sos("highpass", sample_rate, cutoff, order))


def bandpass(x, sample_rate, low, high, order=4):
    return filt_sos(x, butter_sos("bandpass", sample_rate, [low, high], order))


def band_split(x, sample_rate):
    """Split audio into the five notebook bands.

    - ``bass``: <120 Hz, low-frequency core.
    - ``low_mid``: 120-500 Hz, body/warmth.
    - ``mid``: 500-2000 Hz, vocal/body fundamentals.
    - ``high_mid``: 2-6 kHz, presence/clarity/harshness risk.
    - ``air``: >6 kHz, shimmer/air/hiss risk.
    """
    return {
        "bass": lowpass(x, sample_rate, 120),
        "low_mid": bandpass(x, sample_rate, 120, 500),
        "mid": bandpass(x, sample_rate, 500, 2000),
        "high_mid": bandpass(x, sample_rate, 2000, 6000),
        "air": highpass(x, sample_rate, 6000),
    }


def delay_samples(x, samples):
    samples = int(max(0, samples))
    x = np.asarray(x, dtype=np.float32)
    if samples == 0:
        return x.copy()
    if samples >= len(x):
        return np.zeros_like(x)
    return np.concatenate([np.zeros(samples, dtype=np.float32), x[:-samples]]).astype(np.float32)
