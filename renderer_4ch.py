import numpy as np
from scipy import signal

from dsp_utils import EPS, band_split, delay_samples, rms


def allpass_delay(x, delay, g):
    delay = int(max(1, delay))
    b = np.zeros(delay + 1, dtype=np.float64)
    a = np.zeros(delay + 1, dtype=np.float64)
    b[0] = -g
    b[delay] = 1.0
    a[0] = 1.0
    a[delay] = -g
    return signal.lfilter(b, a, x).astype(np.float32)


def soften_rear_tone(x, sample_rate, air_gain=0.50, highmid_gain=0.95):
    """Rear-only tone shaping: control hiss/harshness without dulling front."""
    bands = band_split(x, sample_rate)
    y = (
        bands["bass"] + bands["low_mid"] + bands["mid"]
        + highmid_gain * bands["high_mid"] + air_gain * bands["air"]
    )
    return y.astype(np.float32)


def decorrelate_rear(x, sample_rate, amount=0.6):
    """Notebook-style short delay/all-pass rear decorrelation."""
    amount = float(np.clip(amount, 0.0, 1.0))
    d_l = int(sample_rate * (0.0055 + 0.0030 * amount))
    d_r = int(sample_rate * (0.0085 + 0.0040 * amount))
    xl = delay_samples(x, d_l)
    xr = delay_samples(-x, d_r)
    g1 = 0.28 + 0.24 * amount
    g2 = 0.20 + 0.20 * amount
    yl = allpass_delay(xl, int(sample_rate * 0.0037), g1)
    yl = allpass_delay(yl, int(sample_rate * 0.0089), g2)
    yr = allpass_delay(xr, int(sample_rate * 0.0049), g1 * 0.92)
    yr = allpass_delay(yr, int(sample_rate * 0.0113), g2 * 0.88)
    return yl.astype(np.float32), yr.astype(np.float32)


def apply_rear_floor(out4, routing, preset_name):
    """Avoid almost-silent rear channels without over-amplifying hiss."""
    if preset_name == "bypass":
        return out4.astype(np.float32)
    front_rms = rms(out4[:, :2])
    rear_rms = rms(out4[:, 2:])
    floor = float(routing.get("rear_floor_ratio", 0.0))
    max_makeup = float(routing.get("max_rear_makeup", 1.0))
    target = front_rms * floor
    if floor > 0 and rear_rms < target:
        gain = float(np.clip(target / (rear_rms + EPS), 1.0, max_makeup))
        out4 = out4.copy()
        out4[:, 2:] *= gain
    return out4.astype(np.float32)


def render_4ch(left, right, layers, routing, sample_rate, preset_name="manual"):
    """Render spatial layers to 4-channel output [LF, RF, LB, RB]."""
    if preset_name == "bypass":
        return np.stack([left, right, np.zeros_like(left), np.zeros_like(right)], axis=1).astype(np.float32)

    if preset_name == "ms_baseline":
        side = 0.70710678 * (left - right)
        lb, rb = decorrelate_rear(side, sample_rate, routing["decorrelation"])
        lb *= routing["rear_master"] * routing["side_rear"]
        rb *= routing["rear_master"] * routing["side_rear"]
        lb = soften_rear_tone(lb, sample_rate, routing.get("rear_air_gain", 0.65), routing.get("rear_highmid_gain", 0.95))
        rb = soften_rear_tone(rb, sample_rate, routing.get("rear_air_gain", 0.65), routing.get("rear_highmid_gain", 0.95))
        return apply_rear_floor(np.stack([left, right, lb, rb], axis=1), routing, preset_name)

    bass_gain = float(routing.get("bass_gain", 1.0))
    bass = layers["bass"] * bass_gain
    low_body = layers.get("low_body", np.zeros_like(bass))
    side = layers["side_width"]
    amb = layers["rear_ambience"]
    air = layers["high_air"]
    bass_quad = float(routing.get("bass_quad", 0.0))
    bass_front_gain = (1.0 - bass_quad) * 0.7071 + bass_quad * 0.5
    bass_rear_gain = bass_quad * 0.5

    lf = bass_front_gain * bass + layers["front_L"] + routing["side_front"] * side
    rf = bass_front_gain * bass + layers["front_R"] - routing["side_front"] * side
    rear_base = routing["side_rear"] * side + routing["amb_rear"] * amb + routing["air_rear"] * air
    lb, rb = decorrelate_rear(rear_base, sample_rate, routing["decorrelation"])
    lb = lb * routing["rear_master"] + bass_rear_gain * bass + routing.get("lowbody_rear", 0.0) * low_body
    rb = rb * routing["rear_master"] + bass_rear_gain * bass + routing.get("lowbody_rear", 0.0) * low_body
    lb = soften_rear_tone(lb, sample_rate, routing.get("rear_air_gain", 0.50), routing.get("rear_highmid_gain", 0.95))
    rb = soften_rear_tone(rb, sample_rate, routing.get("rear_air_gain", 0.50), routing.get("rear_highmid_gain", 0.95))
    return apply_rear_floor(np.stack([lf, rf, lb, rb], axis=1), routing, preset_name)
