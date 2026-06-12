import ast
import json
import shutil
from datetime import datetime
from pathlib import Path


NOTEBOOK = Path("streaming_stereo_spatializer_clean_workflow.ipynb")


NEW_TOP = '''# 可控导出当前 preset / 批量 preset 的 4.0 与 binaural A/B：
# 默认只导出“当前 preset 的纯 4ch”，避免一次运行生成大量文件。
#
# 输出文件：
# - *_4ch.wav: 原始 LF/RF/LB/RB 四声道
# - *_binaural_4p0.wav: direct/procedural 4.0 虚拟扬声器 binaural
# - *_binaural_front_pair.wav: direct/procedural，只保留 LF/RF 的 binaural
# - *_binaural_rear_pair.wav: direct/procedural，只保留 LB/RB 的 binaural
# - *_binaural_4p0_room_rir.wav: direct binaural 再经过小型偏干房间 stereo RIR/matrix convolution
# - *_binaural_front_pair_room_rir.wav: front pair + small/dry room RIR
# - *_binaural_rear_pair_room_rir.wav: rear pair + small/dry room RIR
#
# 说明：
# 1) direct/procedural HRTF preview 不等同于个性化 HRTF/SOFA/BRIR。
# 2) 这里的 room RIR 是 deterministic synthetic small/dry room RIR，不联网下载外部 IR；
#    它被加在 binaural 输出之后，用于测试“房间外化/反射”是否改善后方扬声器感。
# 3) 这仍不是严格 BRIR：真正 BRIR 应该是每个 speaker -> 双耳的一对实测/模拟 IR。
# 4) 后方/front pair 单独导出时会独立 peak normalize，方便听 localization，而不是听音量差。

BINAURAL_FRONT_AZIMUTH_DEG = 30.0
BINAURAL_REAR_AZIMUTH_DEG = 135.0
BINAURAL_FULL_REAR_GAIN_DB = 1.5

# =========================
# Export switches
# =========================
# 默认安全模式：只跑当前 preset，只导出纯 4ch。
# 需要耳机监听时，把 EXPORT_BINAURAL_DIRECT 或 EXPORT_BINAURAL_ROOM_RIR 改成 True。
BATCH_ALL_PRESETS = False
EXPORT_4CH = True
EXPORT_BINAURAL_DIRECT = False
EXPORT_BINAURAL_ROOM_RIR = False
EXPORT_ROOM_RIR_MATRIX = False  # True 时额外导出 LL/LR/RL/RR 四列 RIR wav 供检查
BINAURAL_VARIANTS = ("4p0", "front_pair", "rear_pair")  # 可改成 ("4p0",) 来进一步减少文件

# 小一点、干一点的房间 RIR 参数：近似 small control room / dry studio booth。
# RIR 以 2x2 stereo matrix 形式应用到已经生成的 binaural：
# out_L = in_L * LL + in_R * RL
# out_R = in_L * LR + in_R * RR
ROOM_RIR_ENABLED = True
ROOM_RIR_NAME = "synthetic_small_dry_room_stereo_matrix"
ROOM_RIR_RT60_SECONDS = 0.32
ROOM_RIR_LENGTH_SECONDS = 0.45
ROOM_RIR_LATE_START_SECONDS = 0.040
ROOM_RIR_RANDOM_SEED = 20260611
ROOM_RIR_KEEP_TAIL = True

'''


NEW_RIR_FUNC = '''def make_small_dry_room_stereo_rir(
    sr,
    rt60=ROOM_RIR_RT60_SECONDS,
    length_seconds=ROOM_RIR_LENGTH_SECONDS,
    late_start_seconds=ROOM_RIR_LATE_START_SECONDS,
    seed=ROOM_RIR_RANDOM_SEED,
):
    """
    Deterministic synthetic small/dry-room stereo matrix RIR.

    Shape: (samples, input_channel, output_ear)
      h[:, 0, 0] = input L -> output L (LL)
      h[:, 0, 1] = input L -> output R (LR)
      h[:, 1, 0] = input R -> output L (RL)
      h[:, 1, 1] = input R -> output R (RR)

    Compared with the previous medium-room version, this one is smaller/drier:
      - shorter RT60 and shorter exported tail
      - earlier but lower-level reflections
      - quieter late tail so it does not wash out HRTF localization cues
    """
    sr = int(sr)
    n = max(8, int(round(length_seconds * sr)))
    h = np.zeros((n, 2, 2), dtype=np.float32)

    # Direct binaural path: do not collapse/crossfeed direct localization.
    h[0, 0, 0] = 1.0
    h[0, 1, 1] = 1.0

    # Small/dry room early reflections. Lower level than the previous medium-room RIR.
    # Tuple: (delay_seconds, gain_db, lateral_bias)
    early_taps = [
        (0.0042, -22.0, -0.60),  # close side wall, dry
        (0.0067, -23.5, 0.52),
        (0.0108, -25.0, 0.08),   # floor/ceiling
        (0.0165, -27.0, -0.28),
        (0.0240, -29.0, 0.34),
        (0.0330, -31.0, -0.12),
    ]

    for delay_s, gain_db, lateral in early_taps:
        d = int(round(delay_s * sr))
        g = 10 ** (gain_db / 20.0)

        # Same-side reflections.
        _safe_add_tap(h, d, 0, 0, g * (1.00 - 0.05 * lateral))
        _safe_add_tap(h, d + int(round(0.00025 * sr)), 1, 1, g * (1.00 + 0.05 * lateral))

        # Cross-ear reflections are later/quieter to avoid excessive wetness and image blur.
        cross_delay = d + int(round((0.0019 + 0.0015 * abs(lateral)) * sr))
        cross_gain = g * (0.22 + 0.10 * abs(lateral))
        _safe_add_tap(h, cross_delay, 0, 1, cross_gain * (1.00 + 0.04 * lateral))
        _safe_add_tap(h, cross_delay + int(round(0.00035 * sr)), 1, 0, cross_gain * (1.00 - 0.04 * lateral))

    # Quiet, dark, decorrelated late tail.
    late_start = min(n - 1, max(1, int(round(late_start_seconds * sr))))
    tail_len = n - late_start
    if tail_len > 0:
        rng = np.random.default_rng(seed)
        t = np.arange(tail_len, dtype=np.float32) / float(sr)
        decay = (10.0 ** (-3.0 * t / max(float(rt60), 0.05))).astype(np.float32)

        for in_ch in range(2):
            for out_ch in range(2):
                noise = rng.standard_normal(tail_len).astype(np.float32)
                # Drier/darker tail: less top-end sheen, no rumble/DC.
                noise = lowpass(noise, sr, 5200, order=2)
                noise = highpass(noise, sr, 150, order=2)
                noise = noise / (rms(noise) + EPS)

                same_side = in_ch == out_ch
                late_gain = 0.012 if same_side else 0.0065
                h[late_start:, in_ch, out_ch] += (late_gain * decay * noise).astype(np.float32)

    return h.astype(np.float32)'''


NEW_WRITER = '''def write_binaural_ab_files(
    final4,
    sr,
    stem,
    preset_name,
    room_ir=None,
    write_direct=True,
    write_room_rir=False,
    variants=BINAURAL_VARIANTS,
):
    variants = tuple(variants)
    valid_variants = {"4p0", "front_pair", "rear_pair"}
    invalid = [v for v in variants if v not in valid_variants]
    if invalid:
        raise ValueError(f"Unknown binaural variant(s): {invalid}. Valid: {sorted(valid_variants)}")
    if (write_direct or write_room_rir) and not variants:
        raise ValueError("BINAURAL_VARIANTS is empty while binaural export is enabled")
    if write_room_rir and room_ir is None:
        raise ValueError("write_room_rir=True requires a room_ir")

    direct_path_templates = {
        "4p0": OUT_DIR / f"{stem}_{preset_name}_binaural_4p0.wav",
        "front_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_front_pair.wav",
        "rear_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_rear_pair.wav",
    }
    room_path_templates = {
        "4p0": OUT_DIR / f"{stem}_{preset_name}_binaural_4p0_room_rir.wav",
        "front_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_front_pair_room_rir.wav",
        "rear_pair": OUT_DIR / f"{stem}_{preset_name}_binaural_rear_pair_room_rir.wav",
    }
    render_specs = {
        "4p0": {
            "active_channels": ("LF", "RF", "LB", "RB"),
            "rear_gain_db": BINAURAL_FULL_REAR_GAIN_DB,
            "metric_prefix": "binaural_4p0",
        },
        "front_pair": {
            "active_channels": ("LF", "RF"),
            "rear_gain_db": 0.0,
            "metric_prefix": "front_pair",
        },
        "rear_pair": {
            "active_channels": ("LB", "RB"),
            "rear_gain_db": 0.0,
            "metric_prefix": "rear_pair",
        },
    }

    paths = {}
    metrics = {}

    for key in variants:
        spec = render_specs[key]
        direct = render_4ch_binaural(
            final4,
            sr,
            active_channels=spec["active_channels"],
            rear_gain_db=spec["rear_gain_db"],
        )
        if key == "4p0":
            direct = normalize_peak(direct, 0.98).astype(np.float32)
        else:
            direct = peak_normalize_exact(direct, 0.98)

        prefix = spec["metric_prefix"]
        metrics[f"{prefix}_peak"] = peak(direct)
        metrics[f"{prefix}_rms"] = rms(direct)

        if write_direct:
            paths[key] = direct_path_templates[key]
            write_wav(paths[key], direct, sr)

        if write_room_rir:
            room = apply_room_rir_to_binaural(direct, room_ir)
            if key == "4p0":
                room = normalize_peak(room, 0.98).astype(np.float32)
            else:
                room = peak_normalize_exact(room, 0.98)

            room_key = f"{key}_room_rir"
            paths[room_key] = room_path_templates[key]
            write_wav(paths[room_key], room, sr)
            metrics[f"{prefix}_room_rir_peak"] = peak(room)
            metrics[f"{prefix}_room_rir_rms"] = rms(room)

    if write_room_rir:
        metrics["room_rir_added_tail_seconds"] = float(ROOM_RIR_LENGTH_SECONDS if ROOM_RIR_KEEP_TAIL else 0.0)

    return paths, metrics'''


NEW_TAIL = '''BATCH_TEST_PRESETS = [
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

if BATCH_ALL_PRESETS:
    # 如果当前 preset 是 auto_acoustic 或自定义 preset，也放到第一项一起导出。
    TEST_PRESETS = list(dict.fromkeys([preset_name] + BATCH_TEST_PRESETS))
else:
    TEST_PRESETS = [preset_name]

if not (EXPORT_4CH or EXPORT_BINAURAL_DIRECT or EXPORT_BINAURAL_ROOM_RIR):
    raise ValueError("At least one export flag must be True: EXPORT_4CH / EXPORT_BINAURAL_DIRECT / EXPORT_BINAURAL_ROOM_RIR")

room_ir = None
room_rir_path = None
room_rir_config = None
if EXPORT_BINAURAL_ROOM_RIR:
    if not ROOM_RIR_ENABLED:
        raise ValueError("EXPORT_BINAURAL_ROOM_RIR=True requires ROOM_RIR_ENABLED=True")
    room_ir = make_small_dry_room_stereo_rir(sr)
    if EXPORT_ROOM_RIR_MATRIX:
        room_rir_path = OUT_DIR / f"{stem}_{ROOM_RIR_NAME}_rir_matrix_LL_LR_RL_RR.wav"
        write_wav(room_rir_path, room_rir_matrix_to_4ch(room_ir), sr)
    room_rir_config = {
        "name": ROOM_RIR_NAME,
        "path": str(room_rir_path) if room_rir_path is not None else None,
        "matrix_channel_order": "LL, LR, RL, RR",
        "rt60_seconds": float(ROOM_RIR_RT60_SECONDS),
        "length_seconds": float(ROOM_RIR_LENGTH_SECONDS),
        "late_start_seconds": float(ROOM_RIR_LATE_START_SECONDS),
        "keep_tail": bool(ROOM_RIR_KEEP_TAIL),
        "seed": int(ROOM_RIR_RANDOM_SEED),
        "note": "Synthetic post-binaural small/dry stereo matrix RIR; useful for externalization A/B, not a measured per-speaker BRIR.",
    }

print("Selected presets:", TEST_PRESETS)
print("Export 4ch:", EXPORT_4CH)
print("Export binaural direct:", EXPORT_BINAURAL_DIRECT, "variants:", BINAURAL_VARIANTS)
print("Export binaural room RIR:", EXPORT_BINAURAL_ROOM_RIR)
print("Binaural layout azimuths:", {k: v["azimuth"] for k, v in BINAURAL_LAYOUT.items()})
print("Full 4.0 binaural rear monitor gain:", f"{BINAURAL_FULL_REAR_GAIN_DB:.1f} dB")
if room_rir_config is not None:
    print(
        "Room RIR:",
        ROOM_RIR_NAME,
        f"RT60={ROOM_RIR_RT60_SECONDS:.2f}s",
        f"length={ROOM_RIR_LENGTH_SECONDS:.2f}s",
        "matrix:",
        room_rir_path if room_rir_path is not None else "not exported",
    )

batch_manifest = []

for p_name in TEST_PRESETS:
    route = route_layers(analysis, p_name, apply_analysis_adaptation=(p_name != "auto_acoustic"))
    raw = render_4ch(L, R, layers, route, sr, p_name)
    matched, eg = match_energy_to_input(L, R, raw)
    final, lg = safety_limiter(matched)

    out_path = None
    if EXPORT_4CH:
        out_path = OUT_DIR / f"{stem}_{p_name}_4ch.wav"
        write_wav(out_path, final, sr)

    binaural_paths = {}
    binaural_metrics = {}
    if EXPORT_BINAURAL_DIRECT or EXPORT_BINAURAL_ROOM_RIR:
        binaural_paths, binaural_metrics = write_binaural_ab_files(
            final,
            sr,
            stem,
            p_name,
            room_ir=room_ir,
            write_direct=EXPORT_BINAURAL_DIRECT,
            write_room_rir=EXPORT_BINAURAL_ROOM_RIR,
            variants=BINAURAL_VARIANTS,
        )

    front_r = rms(final[:, :2])
    rear_r = rms(final[:, 2:])
    rear_front_ratio = rear_r / (front_r + EPS)

    batch_manifest.append({
        "preset": p_name,
        "four_channel_path": str(out_path) if out_path is not None else None,
        "binaural_paths": {k: str(v) for k, v in binaural_paths.items()},
        "room_rir": room_rir_config,
        "rear_to_front_rms_ratio": float(rear_front_ratio),
        "rear_to_front_db": float(db(rear_front_ratio)),
        "energy_gain": float(eg),
        "limiter_gain": float(lg),
        "binaural_metrics": binaural_metrics,
    })

    print(f"\\n{p_name}")
    if out_path is not None:
        print("  4ch:", out_path)
    else:
        print("  4ch: skipped")

    if binaural_paths:
        for key, path in binaural_paths.items():
            print(f"  binaural {key}:", path)
    else:
        print("  binaural: skipped")

    print(
        "  peak=", f"{peak(final):.3f}",
        "rear/front=", f"{rear_front_ratio:.4f}",
        f"({db(rear_front_ratio):.2f} dB)",
        "energy_gain=", f"{eg:.3f}",
        "limiter_gain=", f"{lg:.3f}",
    )

manifest_path = OUT_DIR / f"{stem}_batch_export_manifest.json"
with open(manifest_path, "w", encoding="utf-8") as f:
    json.dump(batch_manifest, f, indent=2, ensure_ascii=False)

print("\\nBatch export manifest:", manifest_path)
'''


def replace_between(text: str, start_marker: str, end_marker: str, replacement: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[:start] + replacement + text[end:]


def main() -> None:
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    cell = "".join(nb["cells"][32].get("source", []))

    # Replace top config block up to BINAURAL_LAYOUT.
    layout_start = cell.index("BINAURAL_LAYOUT = {")
    cell = NEW_TOP + cell[layout_start:]

    # Replace RIR generator function.
    if "def make_medium_room_stereo_rir(" in cell:
        cell = replace_between(cell, "def make_medium_room_stereo_rir(", "\n\ndef room_rir_matrix_to_4ch", NEW_RIR_FUNC)
    elif "def make_small_dry_room_stereo_rir(" in cell:
        cell = replace_between(cell, "def make_small_dry_room_stereo_rir(", "\n\ndef room_rir_matrix_to_4ch", NEW_RIR_FUNC)
    else:
        raise RuntimeError("RIR function block not found")

    # Replace binaural writer.
    writer_start = cell.index("def write_binaural_ab_files(")
    tail_marker_positions = [
        pos for marker in ("\n\nTEST_PRESETS =", "\n\nBATCH_TEST_PRESETS =")
        if (pos := cell.find(marker, writer_start)) != -1
    ]
    if not tail_marker_positions:
        raise RuntimeError("Could not find end of write_binaural_ab_files block")
    writer_end = min(tail_marker_positions)
    cell = cell[:writer_start] + NEW_WRITER + cell[writer_end:]

    # Replace tail/export loop.
    tail_candidates = [
        pos for marker in ("BATCH_TEST_PRESETS =", "TEST_PRESETS =")
        if (pos := cell.find(marker)) != -1
    ]
    if not tail_candidates:
        raise RuntimeError("Preset/tail block start not found")
    tail_start = min(tail_candidates)
    cell = cell[:tail_start] + NEW_TAIL

    ast.parse(cell, filename=f"{NOTEBOOK.name}:cell_32")

    backup = NOTEBOOK.with_suffix(NOTEBOOK.suffix + f".bak_switches_dryrir_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(NOTEBOOK, backup)

    nb["cells"][32]["source"] = cell.splitlines(True)
    nb["cells"][32]["outputs"] = []
    nb["cells"][32]["execution_count"] = None
    NOTEBOOK.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"Backup: {backup}")
    print(f"Updated: {NOTEBOOK.resolve()}")
    print(f"Cell 32 lines: {len(cell.splitlines())}")
    print("Defaults: BATCH_ALL_PRESETS=False, EXPORT_4CH=True, EXPORT_BINAURAL_DIRECT=False, EXPORT_BINAURAL_ROOM_RIR=False")


if __name__ == "__main__":
    main()