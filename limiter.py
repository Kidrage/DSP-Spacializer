"""Linked multichannel peak limiting."""

import numpy as np


def _frame_peak(audio, frame_samples):
    """Return one linked multichannel peak per fixed-size frame."""
    samples = audio.shape[0]
    frames = (samples + frame_samples - 1) // frame_samples
    padded = np.zeros((frames * frame_samples, audio.shape[1]), dtype=np.float32)
    padded[:samples] = audio
    framed = padded.reshape(frames, frame_samples, audio.shape[1])
    return np.max(np.abs(framed), axis=(1, 2))


def apply_limiter(
    audio,
    threshold=0.98,
    attack_time=0.005,
    release_time=0.1,
    sample_rate=48000,
    frame_time=0.001,
    return_report=False,
):
    """Apply a linked peak limiter with attack and release envelopes.

    The legacy implementation found the largest peak and scaled the entire
    song. This implementation attenuates only the region around an overload.
    A short reverse attack envelope moves gain before the peak, while the
    forward release envelope restores it smoothly. All channels share one
    envelope, preserving the 4.0 image.
    """
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim != 2:
        raise ValueError("audio must have shape [samples, channels]")
    if not 0.0 < threshold <= 1.0:
        raise ValueError("threshold must be in (0, 1]")
    if sample_rate <= 0 or attack_time <= 0 or release_time <= 0 or frame_time <= 0:
        raise ValueError("sample_rate and limiter time constants must be positive")

    input_peak = float(np.max(np.abs(audio), initial=0.0))
    frame_samples = max(1, int(round(sample_rate * frame_time)))
    peaks = _frame_peak(audio, frame_samples)
    required_gain = np.minimum(1.0, threshold / np.maximum(peaks, 1e-12))
    required_reduction = 1.0 - required_gain

    release_coeff = float(np.exp(-frame_samples / (release_time * sample_rate)))
    reduction = required_reduction.copy()
    for index in range(1, reduction.size):
        reduction[index] = max(reduction[index], reduction[index - 1] * release_coeff)

    attack_coeff = float(np.exp(-frame_samples / (attack_time * sample_rate)))
    for index in range(reduction.size - 2, -1, -1):
        reduction[index] = max(reduction[index], reduction[index + 1] * attack_coeff)

    frame_gain = 1.0 - reduction
    sample_gain = np.repeat(frame_gain, frame_samples)[: audio.shape[0]]
    limited = (audio * sample_gain[:, None]).astype(np.float32)
    output_peak = float(np.max(np.abs(limited), initial=0.0))

    gain_reduction_db = -20.0 * np.log10(np.maximum(frame_gain, 1e-12))
    report = {
        "version": 2,
        "mode": "linked_frame_envelope",
        "threshold": float(threshold),
        "attack_time_seconds": float(attack_time),
        "release_time_seconds": float(release_time),
        "frame_time_seconds": float(frame_time),
        "input_peak": input_peak,
        "output_peak": output_peak,
        "max_gain_reduction_db": float(np.max(gain_reduction_db, initial=0.0)),
        "p95_gain_reduction_db": float(np.percentile(gain_reduction_db, 95)),
        "active_frame_fraction": float(np.mean(gain_reduction_db > 0.01)),
    }
    if return_report:
        return limited, report
    return limited
