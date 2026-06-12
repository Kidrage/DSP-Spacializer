import numpy as np

from dsp_utils import EPS, band_split, rms


def coherence(x, y):
    x = np.asarray(x, dtype=np.float32)
    y = np.asarray(y, dtype=np.float32)
    e_xy = np.mean(x * y)
    e_xx = np.mean(x * x)
    e_yy = np.mean(y * y)
    return float(abs(e_xy) / np.sqrt(e_xx * e_yy + EPS))


def transient_density(x, sample_rate, hop=512):
    """Lightweight transient estimate used by the notebook workflow."""
    del sample_rate  # kept for signature clarity/future streaming variants
    x = np.asarray(x, dtype=np.float32)
    if len(x) < hop * 4:
        return 0.0
    frames = [np.sqrt(np.mean(x[i:i + hop] ** 2) + EPS) for i in range(0, len(x) - hop, hop)]
    frames = np.asarray(frames, dtype=np.float32)
    diff = np.maximum(0.0, np.diff(frames))
    if len(diff) == 0:
        return 0.0
    threshold = np.mean(diff) + 1.5 * np.std(diff)
    return float(np.mean(diff > threshold))


def _suggest_legacy_preset(analysis):
    """Backward-compatible coarse suggestion for old diagnostics/CLI output."""
    if analysis["center_dominance"] > 0.80:
        return "vocal_focus_wide"
    if analysis["stereo_width"] > 0.35:
        return "wide_smooth"
    return "general_pop_wide"


def analyze_audio(left, right, sample_rate, analysis_duration=2.0):
    """Analyze stereo audio to extract the acoustic features used by presets.

    This follows notebook Cell 9 and adds band-level coherence/side-ratio so
    ``auto_select`` and ``auto_acoustic`` have enough information to make
    stable routing decisions.
    """
    n = min(len(left), int(sample_rate * analysis_duration))
    left_part = np.asarray(left[:n], dtype=np.float32)
    right_part = np.asarray(right[:n], dtype=np.float32)

    mid = 0.70710678 * (left_part + right_part)
    side = 0.70710678 * (left_part - right_part)

    stereo_width = rms(side) / (rms(mid) + rms(side) + EPS)
    center_dominance = rms(mid) / (rms(mid) + rms(side) + EPS)

    left_bands = band_split(left_part, sample_rate)
    right_bands = band_split(right_part, sample_rate)

    band_coherence = {}
    band_side_ratio = {}
    for name in left_bands.keys():
        band_mid = 0.70710678 * (left_bands[name] + right_bands[name])
        band_side = 0.70710678 * (left_bands[name] - right_bands[name])
        band_coherence[name] = coherence(left_bands[name], right_bands[name])
        band_side_ratio[name] = rms(band_side) / (rms(band_mid) + rms(band_side) + EPS)

    high_diffuse_ratio = float(
        0.55 * (1.0 - band_coherence["high_mid"]) * band_side_ratio["high_mid"]
        + 0.45 * (1.0 - band_coherence["air"]) * band_side_ratio["air"]
    )

    analysis = {
        "duration_analyzed_sec": float(n / sample_rate),
        "stereo_width": float(stereo_width),
        "center_dominance": float(center_dominance),
        "bass_mono_ratio": float(band_coherence["bass"]),
        "high_diffuse_ratio": float(high_diffuse_ratio),
        "transient_density": float(transient_density(mid, sample_rate)),
        "band_coherence": band_coherence,
        "band_side_ratio": band_side_ratio,
    }
    analysis["suggested_preset"] = _suggest_legacy_preset(analysis)
    return analysis