import json
import shutil
from datetime import datetime
from pathlib import Path


NOTEBOOK = Path("streaming_stereo_spatializer_clean_workflow.ipynb")


CELL_SOURCE = r'''# 批量导出多个 preset 的 4ch、direct binaural 与中等房间 RIR 卷积版 binaural A/B：
# - *_4ch.wav: 原始 LF/RF/LB/RB 四声道
# - *_binaural_4p0.wav: direct/procedural 4.0 虚拟扬声器 binaural
# - *_binaural_front_pair.wav: direct/procedural，只保留 LF/RF 的 binaural
# - *_binaural_rear_pair.wav: direct/procedural，只保留 LB/RB 的 binaural
# - *_binaural_4p0_room_rir.wav: direct binaural 再经过中等体积房间 stereo RIR/matrix convolution
# - *_binaural_front_pair_room_rir.wav: front pair + room RIR
# - *_binaural_rear_pair_room_rir.wav: rear pair + room RIR
#
# 说明：
# 1) direct/procedural HRTF preview 不等同于个性化 HRTF/SOFA/BRIR。
# 2) 这里的 room RIR 是 deterministic synthetic medium-room RIR，不联网下载外部 IR；
#    它被加在 binaural 输出之后，用于测试“房间外化/反射”是否改善后方扬声器感。
# 3) 这仍不是严格 BRIR：真正 BRIR 应该是每个 speaker -> 双耳的一对实测/模拟 IR。
# 4) 后方/front pair 单独导出时会独立 peak normalize，方便听 localization，而不是听音量差。

BINAURAL_FRONT_AZIMUTH_DEG = 30.0
BINAURAL_REAR_AZIMUTH_DEG = 135.0
BINAURAL_FULL_REAR_GAIN_DB = 1.5

# 中等体积房间 RIR 参数：大约 6.5 m x 4.8 m x 2.8 m / RT60 ~ 0.55 s。
# RIR 以 2x2 stereo matrix 形式应用到已经生成的 binaural：
# out_L = in_L * LL + in_R * RL
# out_R = in_L * LR + in_R * RR
ROOM_RIR_ENABLED = True
ROOM_RIR_NAME = "synthetic_medium_room_stereo_matrix"
ROOM_RIR_RT60_SECONDS = 0.55
ROOM_RIR_LENGTH_SECONDS = 0.80
ROOM_RIR_LATE_START_SECONDS = 0.055
ROOM_RIR_RANDOM_SEED = 20260611
ROOM_RIR_KEEP_TAIL = True

BINAURAL_LAYOUT = {
    "LF": {"channel": 0, "azimuth": -BINAURAL_FRONT_AZIMUTH_DEG, "is_rear": False},
    "RF": {"channel": 1, "azimuth": BINAURAL_FRONT_AZIMUTH_DEG, "is_rear": False},
    "LB": {"channel": 2, "azimuth": -BINAURAL_REAR_AZIMUTH_DEG, "is_rear": True},
    "RB": {"channel": 3, "azimuth": BINAURAL_REAR_AZIMUTH_DEG, "is_rear": True},
}


def peak_normalize_exact(audio, peak_target=0.98):
    p = peak(audio)
    if p <= EPS:
        return audio.astype(np.float32)
    return (audio * (peak_target / p)).astype(np.float32)


def rear_pinna_cue(x, sr):
    """
    Lightweight rear-position cue for headphones.
    Generic HRTF has strong front/back confusion, so the rear pair gets a
    mild 6-9 kHz pinna notch plus a tiny early body reflection.
    """
    notch = bandpass(x, sr, 5600, 9200, order=2)
    air = highpass(x, sr, 9000, order=2)
    presence = bandpass(x, sr, 1800, 4200, order=2)
    early_body = delay_samples(lowpass(x, sr, 2600, order=2), int(0.012 * sr))

    y = x - 0.30 * notch - 0.06 * air + 0.035 * presence + 0.055 * early_body
    return y.astype(np.float32)


def far_ear_shadow(x, sr, side_amount):
    """Frequency-dependent far-ear attenuation for a simple HRTF preview."""
    low = lowpass(x, sr, 1500, order=2)
    high = (x - low).astype(np.float32)

    low_gain = 10 ** ((-0.7 * side_amount) / 20.0)
    high_gain = 10 ** ((-7.5 * side_amount) / 20.0)
    return (low_gain * low + high_gain * high).astype(np.float32)


def render_virtual_speaker_binaural(x, sr, azimuth_deg, is_rear=False):
    """
    Render one virtual speaker into headphone L/R.
    azimuth convention: negative = left, positive = right.
    """
    x = np.asarray(x, dtype=np.float32)
    if is_rear:
        x = rear_pinna_cue(x, sr)

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


def render_4ch_binaural(out4, sr, active_channels=("LF", "RF", "LB", "RB"), rear_gain_db=0.0):
    out4 = np.asarray(out4, dtype=np.float32)
    y = np.zeros((out4.shape[0], 2), dtype=np.float32)
    rear_gain = 10 ** (rear_gain_db / 20.0)

    for name in active_channels:
        spec = BINAURAL_LAYOUT[name]
        mono = out4[:, spec["channel"]]
        if spec["is_rear"]:
            mono = mono * rear_gain

        y += render_virtual_speaker_binaural(
            mono,
            sr,
            spec["azimuth"],
            is_rear=spec["is_rear"],
        )

    return y.astype(np.float32)


def _safe_add_tap(h, sample_index, in_ch, out_ch, gain):
    if 0 <= sample_index < h.shape[0]:
        h[sample_index, in_ch, out_ch] += float(gain)


def make_medium_room_stereo_rir(
    sr,
    rt60=ROOM_RIR_RT60_SECONDS,
    length_seconds=ROOM_RIR_LENGTH_SECONDS,
    late_start_seconds=ROOM_RIR_LATE_START_SECONDS,
    seed=ROOM_RIR_RANDOM_SEED,
):
    """
    Deterministic synthetic medium-room stereo matrix RIR.

    Shape: (samples, input_channel, output_ear)
      h[:, 0, 0] = input L -> output L (LL)
      h[:, 0, 1] = input L -> output R (LR)
      h[:, 1, 0] = input R -> output L (RL)
      h[:, 1, 1] = input R -> output R (RR)

    It contains:
      - direct path at 0 ms for LL/RR, preserving original binaural localization
      - sparse early reflections roughly matching a medium listening room
      - dark, decorrelated late tail with RT60-style exponential decay
    """
    sr = int(sr)
    n = max(8, int(round(length_seconds * sr)))
    h = np.zeros((n, 2, 2), dtype=np.float32)

    # Direct binaural path: do not collapse/crossfeed direct localization.
    h[0, 0, 0] = 1.0
    h[0, 1, 1] = 1.0

    # Early reflections: delays/gains are intentionally modest to avoid washing out HRTF cues.
    # Tuple: (delay_seconds, gain_db, lateral_bias)
    early_taps = [
        (0.0068, -17.0, -0.65),  # near side wall
        (0.0096, -18.5, 0.55),   # opposite side wall
        (0.0145, -19.5, 0.10),   # floor/ceiling
        (0.0215, -22.0, -0.30),
        (0.0290, -23.5, 0.38),
        (0.0380, -25.5, -0.12),
        (0.0470, -27.0, 0.26),
    ]

    for delay_s, gain_db, lateral in early_taps:
        d = int(round(delay_s * sr))
        g = 10 ** (gain_db / 20.0)

        # Same-side reflections.
        _safe_add_tap(h, d, 0, 0, g * (1.00 - 0.06 * lateral))
        _safe_add_tap(h, d + int(round(0.00035 * sr)), 1, 1, g * (1.00 + 0.06 * lateral))

        # Cross-ear room reflections arrive slightly later and quieter.
        cross_delay = d + int(round((0.0028 + 0.0022 * abs(lateral)) * sr))
        cross_gain = g * (0.32 + 0.16 * abs(lateral))
        _safe_add_tap(h, cross_delay, 0, 1, cross_gain * (1.00 + 0.05 * lateral))
        _safe_add_tap(h, cross_delay + int(round(0.00055 * sr)), 1, 0, cross_gain * (1.00 - 0.05 * lateral))

    # Decorrelated late tail.
    late_start = min(n - 1, max(1, int(round(late_start_seconds * sr))))
    tail_len = n - late_start
    if tail_len > 0:
        rng = np.random.default_rng(seed)
        t = np.arange(tail_len, dtype=np.float32) / float(sr)
        decay = (10.0 ** (-3.0 * t / max(float(rt60), 0.05))).astype(np.float32)

        for in_ch in range(2):
            for out_ch in range(2):
                noise = rng.standard_normal(tail_len).astype(np.float32)
                # Darken the room tail and remove rumble/DC.
                noise = lowpass(noise, sr, 6400, order=2)
                noise = highpass(noise, sr, 120, order=2)
                noise = noise / (rms(noise) + EPS)

                same_side = in_ch == out_ch
                late_gain = 0.028 if same_side else 0.017
                h[late_start:, in_ch, out_ch] += (late_gain * decay * noise).astype(np.float32)

    return h.astype(np.float32)


def room_rir_matrix_to_4ch(room_ir):
    """Export helper: columns are LL, LR, RL, RR."""
    return np.stack(
        [
            room_ir[:, 0, 0],
            room_ir[:, 0, 1],
            room_ir[:, 1, 0],
            room_ir[:, 1, 1],
        ],
        axis=1,
    ).astype(np.float32)


def convolve_1d_full(x, h):
    x = np.asarray(x, dtype=np.float32)
    h = np.asarray(h, dtype=np.float32)
    if hasattr(signal, "oaconvolve"):
        y = signal.oaconvolve(x, h, mode="full")
    else:
        y = signal.fftconvolve(x, h, mode="full")
    return y.astype(np.float32)


def apply_room_rir_to_binaural(binaural, room_ir, keep_tail=ROOM_RIR_KEEP_TAIL):
    """
    Apply stereo matrix RIR to a 2-channel binaural signal.

    This is intentionally post-binaural room convolution. It can improve externalization,
    but it is not equivalent to per-speaker BRIR convolution.
    """
    binaural = np.asarray(binaural, dtype=np.float32)
    if binaural.ndim != 2 or binaural.shape[1] != 2:
        raise ValueError(f"Expected binaural shape (n, 2), got {binaural.shape}")

    y_l = (
        convolve_1d_full(binaural[:, 0], room_ir[:, 0, 0])
        + convolve_1d_full(binaural[:, 1], room_ir[:, 1, 0])
    )
    y_r = (
        convolve_1d_full(binaural[:, 0], room_ir[:, 0, 1])
        + convolve_1d_full(binaural[:, 1], room_ir[:, 1, 1])
    )

    out_len = len(y_l) if keep_tail else binaural.shape[0]
    return np.stack([y_l[:out_len], y_r[:out_len]], axis=1).astype(np.float32)


def write_binaural_ab_files(final4, sr, stem, preset_name, room_ir=None):
    paths = {
        "4p0": OUT_DIR / f"{stem}_{preset_name}_binaural_4p0.wav",
        "front_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_front_pair.wav",
        "rear_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_rear_pair.wav",
    }
    if room_ir is not None:
        paths.update(
            {
                "4p0_room_rir": OUT_DIR / f"{stem}_{preset_name}_binaural_4p0_room_rir.wav",
                "front_pair_room_rir": OUT_DIR / f"{stem}_{preset_name}_binaural_front_pair_room_rir.wav",
                "rear_pair_room_rir": OUT_DIR / f"{stem}_{preset_name}_binaural_rear_pair_room_rir.wav",
            }
        )

    binaural_4p0 = render_4ch_binaural(
        final4,
        sr,
        active_channels=("LF", "RF", "LB", "RB"),
        rear_gain_db=BINAURAL_FULL_REAR_GAIN_DB,
    )
    binaural_4p0 = normalize_peak(binaural_4p0, 0.98).astype(np.float32)

    front_pair = render_4ch_binaural(
        final4,
        sr,
        active_channels=("LF", "RF"),
        rear_gain_db=0.0,
    )
    front_pair = peak_normalize_exact(front_pair, 0.98)

    rear_pair = render_4ch_binaural(
        final4,
        sr,
        active_channels=("LB", "RB"),
        rear_gain_db=0.0,
    )
    rear_pair = peak_normalize_exact(rear_pair, 0.98)

    write_wav(paths["4p0"], binaural_4p0, sr)
    write_wav(paths["front_pair"], front_pair, sr)
    write_wav(paths["rear_pair"], rear_pair, sr)

    metrics = {
        "binaural_4p0_peak": peak(binaural_4p0),
        "front_pair_peak": peak(front_pair),
        "rear_pair_peak": peak(rear_pair),
        "front_pair_rms": rms(front_pair),
        "rear_pair_rms": rms(rear_pair),
    }

    if room_ir is not None:
        binaural_4p0_room = apply_room_rir_to_binaural(binaural_4p0, room_ir)
        binaural_4p0_room = normalize_peak(binaural_4p0_room, 0.98).astype(np.float32)

        front_pair_room = apply_room_rir_to_binaural(front_pair, room_ir)
        front_pair_room = peak_normalize_exact(front_pair_room, 0.98)

        rear_pair_room = apply_room_rir_to_binaural(rear_pair, room_ir)
        rear_pair_room = peak_normalize_exact(rear_pair_room, 0.98)

        write_wav(paths["4p0_room_rir"], binaural_4p0_room, sr)
        write_wav(paths["front_pair_room_rir"], front_pair_room, sr)
        write_wav(paths["rear_pair_room_rir"], rear_pair_room, sr)

        metrics.update(
            {
                "binaural_4p0_room_rir_peak": peak(binaural_4p0_room),
                "front_pair_room_rir_peak": peak(front_pair_room),
                "rear_pair_room_rir_peak": peak(rear_pair_room),
                "front_pair_room_rir_rms": rms(front_pair_room),
                "rear_pair_room_rir_rms": rms(rear_pair_room),
                "room_rir_added_tail_seconds": float(ROOM_RIR_LENGTH_SECONDS if ROOM_RIR_KEEP_TAIL else 0.0),
            }
        )

    return paths, metrics


TEST_PRESETS = [
    "bypass",
    "ms_baseline",
    "general_pop_wide",
    "wide_smooth",
    "vocal_focus_wide",
    "vocal_room_body_clear",
    "bass_dry_wide",
    "epic_orchestral_depth",
    "vintage_jazz_room",
]

# 如果当前 preset 是 auto_acoustic 或自定义 preset，也放到第一项一起导出。
TEST_PRESETS = list(dict.fromkeys([preset_name] + TEST_PRESETS))

room_ir = None
room_rir_path = None
room_rir_config = None
if ROOM_RIR_ENABLED:
    room_ir = make_medium_room_stereo_rir(sr)
    room_rir_path = OUT_DIR / f"{stem}_{ROOM_RIR_NAME}_rir_matrix_LL_LR_RL_RR.wav"
    write_wav(room_rir_path, room_rir_matrix_to_4ch(room_ir), sr)
    room_rir_config = {
        "name": ROOM_RIR_NAME,
        "path": str(room_rir_path),
        "matrix_channel_order": "LL, LR, RL, RR",
        "rt60_seconds": float(ROOM_RIR_RT60_SECONDS),
        "length_seconds": float(ROOM_RIR_LENGTH_SECONDS),
        "late_start_seconds": float(ROOM_RIR_LATE_START_SECONDS),
        "keep_tail": bool(ROOM_RIR_KEEP_TAIL),
        "seed": int(ROOM_RIR_RANDOM_SEED),
        "note": "Synthetic post-binaural stereo matrix RIR; useful for externalization A/B, not a measured per-speaker BRIR.",
    }

print("Binaural layout azimuths:", {k: v["azimuth"] for k, v in BINAURAL_LAYOUT.items()})
print("Full 4.0 binaural rear monitor gain:", f"{BINAURAL_FULL_REAR_GAIN_DB:.1f} dB")
if room_rir_config is not None:
    print(
        "Room RIR:",
        ROOM_RIR_NAME,
        f"RT60={ROOM_RIR_RT60_SECONDS:.2f}s",
        f"length={ROOM_RIR_LENGTH_SECONDS:.2f}s",
        "matrix:",
        room_rir_path,
    )

batch_manifest = []

for p_name in TEST_PRESETS:
    route = route_layers(analysis, p_name, apply_analysis_adaptation=(p_name != "auto_acoustic"))
    raw = render_4ch(L, R, layers, route, sr, p_name)
    matched, eg = match_energy_to_input(L, R, raw)
    final, lg = safety_limiter(matched)

    out_path = OUT_DIR / f"{stem}_{p_name}_4ch.wav"
    write_wav(out_path, final, sr)

    binaural_paths, binaural_metrics = write_binaural_ab_files(final, sr, stem, p_name, room_ir=room_ir)

    front_r = rms(final[:, :2])
    rear_r = rms(final[:, 2:])
    rear_front_ratio = rear_r / (front_r + EPS)

    batch_manifest.append({
        "preset": p_name,
        "four_channel_path": str(out_path),
        "binaural_paths": {k: str(v) for k, v in binaural_paths.items()},
        "room_rir": room_rir_config,
        "rear_to_front_rms_ratio": float(rear_front_ratio),
        "rear_to_front_db": float(db(rear_front_ratio)),
        "energy_gain": float(eg),
        "limiter_gain": float(lg),
        "binaural_metrics": binaural_metrics,
    })

    print(f"\n{p_name}")
    print("  4ch:", out_path)
    print("  binaural 4.0 direct:", binaural_paths["4p0"])
    print("  binaural front pair direct:", binaural_paths["front_pair"])
    print("  binaural rear pair direct:", binaural_paths["rear_pair"])
    if room_ir is not None:
        print("  binaural 4.0 room RIR:", binaural_paths["4p0_room_rir"])
        print("  binaural front pair room RIR:", binaural_paths["front_pair_room_rir"])
        print("  binaural rear pair room RIR:", binaural_paths["rear_pair_room_rir"])
    print(
        "  peak=", f"{peak(final):.3f}",
        "rear/front=", f"{rear_front_ratio:.4f}",
        f"({db(rear_front_ratio):.2f} dB)",
        "energy_gain=", f"{eg:.3f}",
        "limiter_gain=", f"{lg:.3f}",
    )

manifest_path = OUT_DIR / f"{stem}_batch_binaural_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(batch_manifest, f, indent=2, ensure_ascii=False)

print("\nBatch binaural manifest:", manifest_path)
'''


def main() -> None:
    if not NOTEBOOK.exists():
        raise FileNotFoundError(NOTEBOOK)

    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    if len(nb.get("cells", [])) <= 32:
        raise RuntimeError("Expected notebook to have at least 33 cells; batch cell index 32 not found")
    if nb["cells"][32].get("cell_type") != "code":
        raise RuntimeError("Expected cell 32 to be the batch export code cell")

    backup = NOTEBOOK.with_suffix(NOTEBOOK.suffix + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(NOTEBOOK, backup)

    nb["cells"][32]["source"] = CELL_SOURCE.splitlines(True)
    nb["cells"][32]["outputs"] = []
    nb["cells"][32]["execution_count"] = None
    NOTEBOOK.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Backup: {backup}")
    print(f"Updated: {NOTEBOOK.resolve()}")
    print(f"New cell 32 lines: {len(CELL_SOURCE.splitlines())}")


if __name__ == "__main__":
    main()