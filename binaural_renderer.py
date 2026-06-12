"""Binaural downmix — virtual 4.0 speakers to stereo headphones.

Implements the notebook's procedural HRTF pipeline:
1) Per-speaker virtual rendering with proper ITD, frequency-dependent ILD,
   rear pinna notch / presence / body reflection, plus 1/r distance attenuation
   and high-frequency air absorption.
2) Optional post-binaural stereo-matrix room RIR convolution for externalisation.

The SOFA file ``KEMAR_HRTFs_lfcorr.sofa`` is NOT loaded by this renderer;
the notebook uses deterministic synthetic cues that are faster and do not
require pysofaconventions.
"""

import numpy as np
from scipy import signal

from dsp_utils import (
    EPS, bandpass, delay_samples, highpass, lowpass, normalize_peak,
    peak, peak_normalize_exact, rms,
)


# ---------------------------------------------------------------------------
# Procedural HRTF helpers (from notebook Cell 32)
# ---------------------------------------------------------------------------

def rear_pinna_cue(x, sr):
    """Lightweight rear-position cue for headphones.

    A generic HRTF has strong front/back confusion, so the rear pair gets:
      - mild 5.6-9.2 kHz pinna notch
      - mild 1.8-4.2 kHz presence boost
      - tiny early body reflection (~12 ms delay)
    """
    notch = bandpass(x, sr, 5600, 9200, order=2)
    air = highpass(x, sr, 9000, order=2)
    presence = bandpass(x, sr, 1800, 4200, order=2)
    early_body = delay_samples(lowpass(x, sr, 2600, order=2), int(0.012 * sr))

    y = x - 0.30 * notch - 0.06 * air + 0.035 * presence + 0.055 * early_body
    return y.astype(np.float32)


def far_ear_shadow(x, sr, side_amount):
    """Frequency-dependent ILD for far-ear side.

    Splits at 1.5 kHz:
      - low  (<1.5 kHz): mild attenuation  (-0.7 dB  * side_amount)
      - high (>1.5 kHz): strong attenuation (-7.5 dB * side_amount)
    """
    low = lowpass(x, sr, 1500, order=2)
    high = (x - low).astype(np.float32)

    low_gain = 10 ** ((-0.7 * side_amount) / 20.0)
    high_gain = 10 ** ((-7.5 * side_amount) / 20.0)
    return (low_gain * low + high_gain * high).astype(np.float32)


def _air_absorption_gain_db(distance_m, ref_distance_m, air_absorption_db_per_m):
    """Additional high-frequency loss from air absorption over distance.

    Formula: extra_loss_dB = air_absorption_db_per_m * max(0, distance - ref)
    """
    extra_m = max(0.0, float(distance_m) - float(ref_distance_m))
    return float(air_absorption_db_per_m) * extra_m


def render_virtual_speaker_binaural(
    x, sr, azimuth_deg, is_rear=False,
    distance_m=None,
    ref_distance_m=1.0,
    air_absorption_db_per_m=0.0,
):
    """Render ONE virtual speaker at azimuth into headphone L/R.

    azimuth convention: negative -> left, positive -> right.

    Uses:
      - rear pinna cue when is_rear
      - ITD ~ 0.68 ms * sin(azimuth)
      - frequency-dependent far-ear shadow
      - 1/r distance attenuation (relative to ref_distance_m)
      - high-frequency air absorption for distances > ref_distance_m
    """
    x = np.asarray(x, dtype=np.float32)
    if is_rear:
        x = rear_pinna_cue(x, sr)

    # ---- distance attenuation ----
    if distance_m is not None and distance_m > EPS:
        # 1/r energy fall-off (gain = ref_distance / distance)
        dist_gain = float(ref_distance_m) / max(float(distance_m), 0.01)
        x = x * dist_gain

        # high-frequency air absorption (applies to >6kHz)
        extra_loss_db = _air_absorption_gain_db(
            distance_m, ref_distance_m, air_absorption_db_per_m,
        )
        if extra_loss_db > 0.01:
            air_band = highpass(x, sr, 6000, order=2)
            rest = x - air_band
            air_gain = 10.0 ** (-extra_loss_db / 20.0)
            x = rest + air_band * air_gain

    # ---- ITD + ILD ----
    side = float(np.sin(np.deg2rad(azimuth_deg)))
    side_amount = abs(side)
    itd_samples = int(round(sr * 0.00068 * side_amount))

    near = x
    far = delay_samples(far_ear_shadow(x, sr, side_amount), itd_samples)

    if side < 0:
        left, right = near, far
    elif side > 0:
        left, right = far, near
    else:
        left, right = near, near

    return np.stack([left, right], axis=1).astype(np.float32)


# ---------------------------------------------------------------------------
# 4ch -> binaural (main entry, from notebook Cell 32)
# ---------------------------------------------------------------------------

BINAURAL_LAYOUT = {
    "LF": {"channel": 0, "azimuth": -30.0, "is_rear": False},
    "RF": {"channel": 1, "azimuth": 30.0, "is_rear": False},
    "LB": {"channel": 2, "azimuth": -135.0, "is_rear": True},
    "RB": {"channel": 3, "azimuth": 135.0, "is_rear": True},
}


def render_4ch_binaural(
    four_ch,
    sr,
    active_channels=None,
    front_azimuth_deg=30.0,
    rear_azimuth_deg=135.0,
    rear_gain_db=0.0,
    exact_pair_normalize=False,
    speaker_distance_front_m=None,
    speaker_distance_rear_m=None,
    speaker_ref_distance_m=1.0,
    air_absorption_db_per_m=0.0,
):
    """Render selected channels of a 4ch array to procedural binaural stereo.

    Parameters
    ----------
    four_ch : ndarray (N, 4)
        4-channel audio: columns = LF, RF, LB, RB.
    sr : int
    active_channels : tuple of str, optional
        Default ("LF", "RF", "LB", "RB").
    front_azimuth_deg / rear_azimuth_deg : float
    rear_gain_db : float
        Extra gain for rear channels before rendering.
    exact_pair_normalize : bool
        If True and exactly 2 channels active, normalise output to the RMS
        of those channels.
    speaker_distance_front_m / speaker_distance_rear_m : float or None
        Virtual speaker distance in metres. ``None`` disables distance
        attenuation for that pair.
    speaker_ref_distance_m : float
        Reference distance where gain=1.0.
    air_absorption_db_per_m : float
        High-frequency air absorption coefficient (dB/m @ 8 kHz approx).

    Returns
    -------
    stereo : ndarray (N, 2)
    """
    out4 = np.atleast_2d(four_ch)
    if out4.shape[1] < 4:
        raise ValueError(f"Expected 4-channel input, got shape {out4.shape}")

    if active_channels is None:
        active_channels = ("LF", "RF", "LB", "RB")

    # Build layout from keyword arguments (so callers can override azimuths)
    layout = {
        "LF": {"channel": 0, "azimuth": -front_azimuth_deg, "is_rear": False,
               "distance_m": speaker_distance_front_m},
        "RF": {"channel": 1, "azimuth":  front_azimuth_deg, "is_rear": False,
               "distance_m": speaker_distance_front_m},
        "LB": {"channel": 2, "azimuth": -rear_azimuth_deg, "is_rear": True,
               "distance_m": speaker_distance_rear_m},
        "RB": {"channel": 3, "azimuth":  rear_azimuth_deg, "is_rear": True,
               "distance_m": speaker_distance_rear_m},
    }

    y = np.zeros((out4.shape[0], 2), dtype=np.float32)
    rear_linear = 10.0 ** (rear_gain_db / 20.0)

    ch_set = set(active_channels)

    # reference RMS for pair normalisation
    ref_rms = 0.0
    if exact_pair_normalize and len(ch_set) == 2:
        for name in ch_set:
            spec = layout[name]
            mono = out4[:, spec["channel"]]
            if spec["is_rear"]:
                mono = mono * rear_linear
            ref_rms = max(ref_rms, float(np.sqrt(np.mean(mono ** 2))) + EPS)

    for name in ch_set:
        spec = layout[name]
        mono = out4[:, spec["channel"]]
        if spec["is_rear"]:
            mono = mono * rear_linear

        y += render_virtual_speaker_binaural(
            mono, sr, spec["azimuth"], is_rear=spec["is_rear"],
            distance_m=spec["distance_m"],
            ref_distance_m=speaker_ref_distance_m,
            air_absorption_db_per_m=air_absorption_db_per_m,
        )

    if exact_pair_normalize and len(ch_set) == 2:
        out_rms = float(np.sqrt(np.mean(y ** 2))) + EPS
        if out_rms > 0 and ref_rms > 0:
            y *= ref_rms / out_rms

    return y.astype(np.float32)


# ---------------------------------------------------------------------------
# Room RIR (stereo matrix, post-binaural convolution)  from notebook Cell 32
# ---------------------------------------------------------------------------

def _safe_add_tap(h, sample_index, in_ch, out_ch, gain):
    if 0 <= sample_index < h.shape[0]:
        h[sample_index, in_ch, out_ch] += float(gain)


def _convolve_1d_full(x, h):
    x = np.asarray(x, dtype=np.float32)
    h = np.asarray(h, dtype=np.float32)
    if hasattr(signal, "oaconvolve"):
        y = signal.oaconvolve(x, h, mode="full")
    else:
        y = signal.fftconvolve(x, h, mode="full")
    return y.astype(np.float32)


def make_small_dry_room_stereo_rir(
    sr,
    rt60=0.32,
    length_seconds=0.45,
    late_start_seconds=0.040,
    seed=20260611,
):
    """Deterministic synthetic small/dry-room stereo matrix RIR.

    Shape: (samples, input_channel, output_ear)
      h[:, 0, 0] = L -> L (LL)    h[:, 0, 1] = L -> R (LR)
      h[:, 1, 0] = R -> L (RL)    h[:, 1, 1] = R -> R (RR)

    - Direct path at sample 0 is unity for LL/RR, zero for cross-ear.
    - Sparse early reflections approximating a small control room.
    - Dark decorrelated late tail with RT60 decay.
    """
    sr = int(sr)
    n = max(8, int(round(length_seconds * sr)))
    h = np.zeros((n, 2, 2), dtype=np.float32)

    # Direct binaural path -- do not collapse / crossfeed localization
    h[0, 0, 0] = 1.0
    h[0, 1, 1] = 1.0

    # Small/dry room early reflections. Lower level than medium-room version.
    # Tuple: (delay_seconds, gain_db, lateral_bias)
    early_taps = [
        (0.0042, -22.0, -0.60),  # close side wall, dry
        (0.0067, -23.5,  0.52),
        (0.0108, -25.0,  0.08),  # floor/ceiling
        (0.0165, -27.0, -0.28),
        (0.0240, -29.0,  0.34),
        (0.0330, -31.0, -0.12),
    ]

    for delay_s, gain_db, lateral in early_taps:
        d = int(round(delay_s * sr))
        g = 10 ** (gain_db / 20.0)

        # Same-side reflections
        _safe_add_tap(h, d, 0, 0, g * (1.00 - 0.05 * lateral))
        _safe_add_tap(h, d + int(round(0.00025 * sr)), 1, 1, g * (1.00 + 0.05 * lateral))

        # Cross-ear reflections arrive later and quieter
        cross_delay = d + int(round((0.0019 + 0.0015 * abs(lateral)) * sr))
        cross_gain = g * (0.22 + 0.10 * abs(lateral))
        _safe_add_tap(h, cross_delay, 0, 1, cross_gain * (1.00 + 0.04 * lateral))
        _safe_add_tap(
            h, cross_delay + int(round(0.00035 * sr)),
            1, 0, cross_gain * (1.00 - 0.04 * lateral),
        )

    # Quiet dark decorrelated late tail
    late_start = min(n - 1, max(1, int(round(late_start_seconds * sr))))
    tail_len = n - late_start
    if tail_len > 0:
        rng = np.random.default_rng(seed)
        t = np.arange(tail_len, dtype=np.float32) / float(sr)
        decay = (10.0 ** (-3.0 * t / max(float(rt60), 0.05))).astype(np.float32)

        for in_ch in range(2):
            for out_ch in range(2):
                noise = rng.standard_normal(tail_len).astype(np.float32)
                noise = lowpass(noise, sr, 5200, order=2)
                noise = highpass(noise, sr, 150, order=2)
                noise = noise / (rms(noise) + EPS)

                same_side = in_ch == out_ch
                late_gain = 0.012 if same_side else 0.0065
                h[late_start:, in_ch, out_ch] += (late_gain * decay * noise).astype(
                    np.float32
                )

    return h.astype(np.float32)


def apply_room_rir_to_binaural(binaural, room_ir, keep_tail=True):
    """Apply stereo matrix RIR to a 2-channel binaural signal.

    This is intentionally post-binaural room convolution -- it can improve
    externalisation but is NOT equivalent to per-speaker BRIR convolution.
    """
    binaural = np.asarray(binaural, dtype=np.float32)
    if binaural.ndim != 2 or binaural.shape[1] != 2:
        raise ValueError(
            f"Expected binaural shape (n, 2), got {binaural.shape}"
        )

    y_l = _convolve_1d_full(binaural[:, 0], room_ir[:, 0, 0]) + _convolve_1d_full(
        binaural[:, 1], room_ir[:, 1, 0]
    )
    y_r = _convolve_1d_full(binaural[:, 0], room_ir[:, 0, 1]) + _convolve_1d_full(
        binaural[:, 1], room_ir[:, 1, 1]
    )

    out_len = len(y_l) if keep_tail else binaural.shape[0]
    return np.stack([y_l[:out_len], y_r[:out_len]], axis=1).astype(np.float32)


def room_rir_matrix_to_4ch(room_ir):
    """Export helper: columns are LL, LR, RL, RR (for inspection)."""
    return np.stack(
        [
            room_ir[:, 0, 0],
            room_ir[:, 0, 1],
            room_ir[:, 1, 0],
            room_ir[:, 1, 1],
        ],
        axis=1,
    ).astype(np.float32)