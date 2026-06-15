"""Preset center for the DSP spatializer.

本文件是调音时最常改的地方，数值来自
``streaming_stereo_spatializer_clean_workflow.ipynb`` 的 Cell 15/17。

参数对空间化的影响：
- ``side_front``：把 Side 差分声放进前方 L/R 的比例。越大，前方越宽；过大时人声/主旋律会发散。
- ``side_rear``：把 Side 差分声送到后方的比例。越大，后方包围感越明显；过大可能后方抢主声像。
- ``amb_rear``：把 diffuse/reverb 氛围送到后方的比例。越大，厅堂感/后方空气越强；过大可能糊。
- ``air_rear``：把 6kHz 以上空气感送到后方的比例。越大，空间边缘更亮；过大容易“高频呲/嘶”。
- ``rear_master``：后方总增益。整体增强/削弱后方声像，不改变前方。
- ``decorrelation``：后方去相关强度。越大，后方越散/越包围；过大可能梳状滤波、回声感或定位虚。
- ``rear_floor_ratio``：后方 RMS 相对前方 RMS 的最低比例。解决“后方太不明显/不够空间化”。
- ``max_rear_makeup``：rear floor 最多可补多少倍。越大越敢补后方；过大可能把噪声/齿音抬起来。
- ``guard_scale``：人声/瞬态保护强度。越大，越保护中心与 punch；过大可能声场不够打开。
- ``bass_gain``：低频核心层的相对增益。越大，150Hz 以下更有重量；过大可能触发 limiter 或显得轰。
- ``bass_quad``：低频少量分到四声道。越大，bass 更包围；过大低频定位会散、低频变宽/变糊。
- ``lowbody_rear``：120-500Hz 体积感送后方。越大，后方更厚；过大可能人声低中频变浑。
- ``rear_air_gain``：后方 air 频段 tone shaping。越低越不刺；太低后方轮廓会消失。
- ``rear_highmid_gain``：后方 2-6kHz presence。越高后方更清晰；过高会人声齿音/高频刺激。

常见问题调参指南：
- 不够空间化/后方不显著：优先小幅提高 ``rear_floor_ratio``、``side_rear``、``rear_master``；如果后方仍空，再提高 ``lowbody_rear``。
- 高频呲/齿音刺：降低 ``air_rear``、``rear_air_gain``、``rear_highmid_gain``，必要时提高 ``guard_scale``。
- 人声不清晰/中心散：降低 ``side_front``、``side_rear``、``amb_rear``，提高 ``guard_scale``，不要提高 ``decorrelation``。
- bass 量感不足：优先小幅提高 ``bass_gain``；bass 太窄再提高 ``bass_quad`` 或 ``lowbody_rear``。如果低频糊，先退回 ``bass_quad``。
- 声场太窄：提高 ``side_front`` 与 ``side_rear``，再小幅提高 ``amb_rear``。
- 音量不均：检查 diagnostics 的 rear/front dB；调低 ``max_rear_makeup`` 或 ``rear_master``，必要时降低输出模式的后方监听增益。

auto_acoustic 如何自动空间化：
1. Analyzer 先计算 center vocal risk、telephone/plastic risk、dry bass score、hall score、narrow score、useful side material。
2. ``generate_auto_acoustic_preset`` 不选固定风格，而是按这些分数动态生成一组 routing 参数。
3. 人声风险高时收紧后方高频和中高频；素材窄/后方少时提高 rear floor、lowbody 和 side-to-rear；低频干时补一点低频包围。

如果觉得 auto_acoustic 后方音响不够显著，预备方案在
``AUTO_ACOUSTIC_REAR_ENHANCEMENT_PLAN``：建议优先提高 rear_floor/side_rear/rear_master 的系数和下限，而不是直接猛加 air，避免高频呲和人声泄漏。
"""

from copy import deepcopy

from dsp_utils import EPS


# 手动 preset 库。每一种都附了简短听感评价，便于 A/B。
PRESETS = {
    "bypass": {
        # 听感：只保留前方 L/R，适合作为原始/非空间化对照。
        "side_front": 0.0, "side_rear": 0.0, "amb_rear": 0.0, "air_rear": 0.0,
        "rear_master": 0.0, "decorrelation": 0.0, "rear_floor_ratio": 0.0,
        "max_rear_makeup": 1.0, "guard_scale": 1.0, "bass_quad": 0.0,
        "lowbody_rear": 0.0, "rear_air_gain": 1.0, "rear_highmid_gain": 1.0,
    },
    "ms_baseline": {
        # 听感：传统 M/S 后方映射，后方轮廓直接但较“技术对照感”，不如完整 preset 自然。
        "side_front": 0.0, "side_rear": 0.75, "amb_rear": 0.0, "air_rear": 0.0,
        "rear_master": 0.90, "decorrelation": 0.55, "rear_floor_ratio": 0.055,
        "max_rear_makeup": 2.5, "guard_scale": 1.0, "bass_quad": 0.0,
        "lowbody_rear": 0.0, "rear_air_gain": 0.50, "rear_highmid_gain": 0.85,
    },
    "general_pop_wide": {
        # 听感：流行歌安全宽声场，后方有存在感但不抢人声，默认推荐。
        "side_front": 0.48, "side_rear": 0.92, "amb_rear": 0.78, "air_rear": 0.28,
        "rear_master": 0.96, "decorrelation": 0.38, "rear_floor_ratio": 0.095,
        "max_rear_makeup": 3.2, "guard_scale": 0.88, "bass_quad": 0.08,
        "lowbody_rear": 0.34, "rear_air_gain": 0.28, "rear_highmid_gain": 0.66,
    },
    "wide_smooth": {
        # 听感：最明显的宽阔/包围感，适合想听“空间化效果”的 A/B；高频多的歌需留意刺感。
        "side_front": 0.44, "side_rear": 1.05, "amb_rear": 1.18, "air_rear": 0.48,
        "rear_master": 1.06, "decorrelation": 0.60, "rear_floor_ratio": 0.125,
        "max_rear_makeup": 4.5, "guard_scale": 0.58, "bass_quad": 0.11,
        "lowbody_rear": 0.36, "rear_air_gain": 0.42, "rear_highmid_gain": 0.98,
    },
    "vocal_focus_wide": {
        # 听感：保持人声居中清晰，同时有中等后方包围；适合 vocal/pop。
        "side_front": 0.50, "side_rear": 0.80, "amb_rear": 0.90, "air_rear": 0.18,
        "rear_master": 1.10, "decorrelation": 0.46, "rear_floor_ratio": 0.105,
        "max_rear_makeup": 3.6, "guard_scale": 0.82, "bass_quad": 0.08,
        "lowbody_rear": 0.42, "rear_air_gain": 0.36, "rear_highmid_gain": 0.80,
    },
    "vocal_room_body_clear": {
        # 听感：人声最稳、最不刺，后方偏柔和偏暗；适合清唱/窄混音/齿音风险高的歌。
        "side_front": 0.52, "side_rear": 0.68, "amb_rear": 0.42, "air_rear": 0.12,
        "rear_master": 0.95, "decorrelation": 0.22, "rear_floor_ratio": 0.070,
        "max_rear_makeup": 2.0, "guard_scale": 1.35, "bass_quad": 0.05,
        "lowbody_rear": 0.44, "rear_air_gain": 0.12, "rear_highmid_gain": 0.24,
    },
    "bass_dry_wide": {
        # 听感：低频和节奏更有包围，后方干净不拖尾；适合 EDM/rap/电子。
        "side_front": 0.56, "side_rear": 1.18, "amb_rear": 0.62, "air_rear": 0.32,
        "rear_master": 1.12, "decorrelation": 0.34, "rear_floor_ratio": 0.125,
        "max_rear_makeup": 4.0, "guard_scale": 0.90, "bass_quad": 0.13,
        "lowbody_rear": 0.52, "rear_air_gain": 0.34, "rear_highmid_gain": 0.76,
    },
    "epic_orchestral_depth": {
        # 听感：前后深度自然，后方不硬推；适合 orchestral/cinematic/live hall。
        "side_front": 0.48, "side_rear": 0.92, "amb_rear": 0.58, "air_rear": 0.26,
        "rear_master": 0.96, "decorrelation": 0.30, "rear_floor_ratio": 0.095,
        "max_rear_makeup": 3.0, "guard_scale": 0.76, "bass_quad": 0.07,
        "lowbody_rear": 0.34, "rear_air_gain": 0.26, "rear_highmid_gain": 0.58,
    },
    "vintage_jazz_room": {
        # 听感：小房间/爵士录音更有后方体积，温暖但不很亮。
        "side_front": 0.42, "side_rear": 1.12, "amb_rear": 0.72, "air_rear": 0.18,
        "rear_master": 1.08, "decorrelation": 0.44, "rear_floor_ratio": 0.145,
        "max_rear_makeup": 4.8, "guard_scale": 0.62, "bass_quad": 0.06,
        "lowbody_rear": 0.46, "rear_air_gain": 0.18, "rear_highmid_gain": 0.66,
    },
}

PRESET_ALIASES = {
    # 兼容旧 CLI 名称
    "auto": "auto_select",
    "natural": "general_pop_wide",
    "wide": "wide_smooth",
    "vocal_safe": "vocal_focus_wide",
    "live": "epic_orchestral_depth",
    "club": "bass_dry_wide",
}

AUTO_ACOUSTIC_REAR_ENHANCEMENT_PLAN = {
    "when": "auto_acoustic 听起来整体后方音响偏不显著时启用；会按 vocal_risk 连续衰减，不再只在低风险歌曲生效。",
    "safe_first_step": {
        "rear_floor_ratio_add": 0.020,
        "rear_master_add": 0.05,
        "side_rear_add": 0.10,
        "max_rear_makeup_add": 0.7,
    },
    "why": "优先增加后方保底、side 后送和后方总增益，比直接增加 air_rear 更不容易带来齿音和高频呲。",
    "do_not_start_with": ["大幅提高 air_rear", "大幅提高 rear_highmid_gain", "decorrelation 超过 0.55"],
}


def _clamp(x, lo, hi):
    return float(max(lo, min(hi, x)))


def _norm(x, lo, hi):
    return _clamp((float(x) - lo) / (hi - lo + EPS), 0.0, 1.0)


def _get(d, key, default=0.0):
    return float(d.get(key, default))


def normalize_preset_name(name):
    return PRESET_ALIASES.get(str(name).strip(), str(name).strip())


def available_presets():
    return sorted(PRESETS.keys())


def get_preset(preset_name):
    preset_name = normalize_preset_name(preset_name)
    if preset_name not in PRESETS:
        raise KeyError(f"Preset not found: {preset_name}. Available: {available_presets()}")
    return deepcopy(PRESETS[preset_name])


def auto_select_preset(analysis):
    """Rule-based selection of an existing preset."""
    width = analysis["stereo_width"]
    center = analysis["center_dominance"]
    bass_mono = analysis["bass_mono_ratio"]
    diffuse = analysis["high_diffuse_ratio"]
    transient = analysis["transient_density"]
    coh = analysis.get("band_coherence", {})
    mid_coh = _get(coh, "mid")
    highmid_coh = _get(coh, "high_mid")

    if center > 0.68 and mid_coh > 0.90 and highmid_coh > 0.88 and diffuse < 0.06:
        return "vocal_room_body_clear"
    if bass_mono > 0.85 and transient > 0.08 and diffuse < 0.12:
        return "bass_dry_wide"
    if diffuse > 0.22 and width > 0.22 and transient < 0.20:
        return "epic_orchestral_depth"
    if width < 0.22 and diffuse < 0.08 and mid_coh > 0.75:
        return "vintage_jazz_room"
    if center > 0.65 and mid_coh > 0.70:
        return "vocal_focus_wide"
    return "general_pop_wide"


def generate_auto_acoustic_preset(analysis, rear_enhancement=False):
    """Generate a dynamic preset from the current song's acoustic features."""
    width = _get(analysis, "stereo_width")
    center = _get(analysis, "center_dominance")
    bass_mono = _get(analysis, "bass_mono_ratio")
    diffuse = _get(analysis, "high_diffuse_ratio")
    transient = _get(analysis, "transient_density")
    coh = analysis.get("band_coherence", {})
    side = analysis.get("band_side_ratio", {})

    mid_coh = _get(coh, "mid")
    highmid_coh = _get(coh, "high_mid")
    lowmid_side = _get(side, "low_mid")
    mid_side = _get(side, "mid")
    highmid_side = _get(side, "high_mid")
    air_side = _get(side, "air")

    vocal_risk = _clamp(
        0.34 * _norm(center, 0.58, 0.82)
        + 0.26 * _norm(mid_coh, 0.72, 0.98)
        + 0.26 * _norm(highmid_coh, 0.70, 0.98)
        + 0.14 * (1.0 - _norm(diffuse, 0.03, 0.22)),
        0.0, 1.0,
    )
    telephone_risk = center > 0.66 and mid_coh > 0.88 and highmid_coh > 0.88 and diffuse < 0.08
    dry_bass_score = _clamp(0.40 * _norm(bass_mono, 0.78, 0.98) + 0.35 * _norm(transient, 0.06, 0.22) + 0.25 * (1.0 - _norm(diffuse, 0.04, 0.20)), 0.0, 1.0)
    hall_score = _clamp(0.50 * _norm(diffuse, 0.16, 0.42) + 0.30 * _norm(width, 0.20, 0.45) + 0.20 * (1.0 - _norm(transient, 0.08, 0.28)), 0.0, 1.0)
    narrow_score = _clamp(0.45 * (1.0 - _norm(width, 0.18, 0.36)) + 0.35 * (1.0 - _norm(diffuse, 0.04, 0.18)) + 0.20 * _norm((mid_coh + highmid_coh) * 0.5, 0.72, 0.98), 0.0, 1.0)
    side_material = _clamp(0.35 * _norm(width, 0.18, 0.42) + 0.25 * _norm(mid_side, 0.16, 0.38) + 0.25 * _norm(highmid_side, 0.18, 0.46) + 0.15 * _norm(air_side, 0.18, 0.48), 0.0, 1.0)

    diffuse_energy = _norm(diffuse, 0.05, 0.30)
    adaptive_intensity = _clamp(0.88 + 0.24 * side_material + 0.10 * diffuse_energy + 0.06 * narrow_score - 0.06 * vocal_risk, 0.82, 1.22)

    side_front = _clamp(0.44 + 0.14 * side_material - 0.04 * vocal_risk, 0.38, 0.62)
    side_rear = _clamp(0.78 + 0.40 * side_material + 0.20 * dry_bass_score + 0.16 * narrow_score - 0.18 * vocal_risk, 0.56, 1.28)
    amb_rear = _clamp(0.50 + 0.30 * diffuse_energy + 0.14 * narrow_score - 0.16 * hall_score - 0.15 * vocal_risk, 0.32, 0.96)
    air_rear = _clamp(0.18 + 0.18 * _norm(air_side, 0.18, 0.48) + 0.11 * _norm(diffuse, 0.08, 0.30) - 0.15 * vocal_risk, 0.09, 0.44)
    rear_master = _clamp(0.92 + 0.18 * side_material + 0.10 * dry_bass_score + 0.10 * narrow_score - 0.05 * vocal_risk, 0.84, 1.18)
    decorrelation = _clamp(0.28 + 0.12 * side_material + 0.08 * narrow_score - 0.12 * vocal_risk - 0.10 * hall_score - 0.08 * _norm(transient, 0.08, 0.25), 0.16, 0.46)
    rear_floor_ratio = _clamp(0.095 + 0.046 * narrow_score + 0.022 * dry_bass_score + 0.010 * side_material - 0.018 * vocal_risk, 0.075, 0.165)
    max_rear_makeup = _clamp(2.8 + 1.7 * narrow_score + 0.9 * dry_bass_score - 0.6 * vocal_risk, 2.0, 5.4)
    guard_scale = _clamp(0.72 + 0.62 * vocal_risk - 0.16 * side_material, 0.55, 1.45)
    bass_gain = _clamp(1.06 + 0.12 * dry_bass_score + 0.06 * narrow_score + 0.04 * side_material - 0.04 * hall_score, 1.02, 1.22)
    bass_quad = _clamp(0.08 + 0.075 * dry_bass_score + 0.025 * narrow_score - 0.020 * vocal_risk - 0.015 * hall_score, 0.055, 0.18)
    lowbody_rear = _clamp(0.28 + 0.18 * dry_bass_score + 0.16 * narrow_score + 0.08 * (1.0 - _norm(lowmid_side, 0.22, 0.42)) - 0.04 * vocal_risk, 0.18, 0.58)
    rear_air_gain = _clamp(0.18 + 0.16 * _norm(diffuse, 0.08, 0.32) + 0.08 * _norm(air_side, 0.18, 0.48) - 0.20 * vocal_risk, 0.08, 0.40)
    rear_highmid_gain = _clamp(0.46 + 0.18 * side_material + 0.08 * _norm(highmid_side, 0.18, 0.46) - 0.34 * vocal_risk - 0.10 * hall_score, 0.18, 0.78)

    side_rear = _clamp(side_rear * adaptive_intensity, 0.56, 1.32)
    amb_rear = _clamp(amb_rear * adaptive_intensity, 0.32, 1.00)
    air_rear = _clamp(air_rear * (0.92 + 0.12 * adaptive_intensity), 0.09, 0.46)
    rear_master = _clamp(rear_master * (0.92 + 0.10 * adaptive_intensity), 0.84, 1.22)

    if telephone_risk:
        side_rear = min(side_rear, 0.92)
        amb_rear = min(amb_rear, 0.52)
        air_rear = min(max(air_rear, 0.14), 0.24)
        decorrelation = min(max(decorrelation, 0.24), 0.32)
        rear_floor_ratio = min(max(rear_floor_ratio, 0.095), 0.125)
        max_rear_makeup = min(max(max_rear_makeup, 3.0), 4.2)
        rear_air_gain = min(max(rear_air_gain, 0.20), 0.34)
        rear_highmid_gain = min(max(rear_highmid_gain, 0.34), 0.48)
        guard_scale = max(guard_scale, 1.10)
        bass_gain = min(max(bass_gain, 1.06), 1.16)
        lowbody_rear = max(lowbody_rear, 0.46)

    if hall_score > 0.65:
        amb_rear = min(amb_rear, 0.58)
        decorrelation = min(decorrelation, 0.30)
        rear_highmid_gain = min(rear_highmid_gain, 0.58)
        rear_air_gain = min(rear_air_gain, 0.30)

    if dry_bass_score > 0.65 and not telephone_risk:
        lowbody_rear = max(lowbody_rear, 0.48)
        bass_gain = max(bass_gain, 1.14)
        bass_quad = max(bass_quad, 0.10)
        amb_rear = min(amb_rear, 0.62)
        decorrelation = min(decorrelation, 0.34)

    rear_enhancement_amount = 0.0
    if rear_enhancement:
        plan = AUTO_ACOUSTIC_REAR_ENHANCEMENT_PLAN["safe_first_step"]
        rear_enhancement_amount = _clamp((0.90 - min(vocal_risk, 0.90)) / 0.90, 0.0, 1.0)
        rear_floor_ratio = _clamp(rear_floor_ratio + plan["rear_floor_ratio_add"] * rear_enhancement_amount, 0.075, 0.180)
        rear_master = _clamp(rear_master + plan["rear_master_add"] * rear_enhancement_amount, 0.84, 1.24)
        side_rear = _clamp(side_rear + plan["side_rear_add"] * rear_enhancement_amount, 0.56, 1.36)
        max_rear_makeup = _clamp(max_rear_makeup + plan["max_rear_makeup_add"] * rear_enhancement_amount, 2.0, 5.8)

    auto_preset = {
        "side_front": side_front, "side_rear": side_rear, "amb_rear": amb_rear,
        "air_rear": air_rear, "rear_master": rear_master, "decorrelation": decorrelation,
        "rear_floor_ratio": rear_floor_ratio, "max_rear_makeup": max_rear_makeup,
        "guard_scale": guard_scale, "bass_gain": bass_gain, "bass_quad": bass_quad, "lowbody_rear": lowbody_rear,
        "rear_air_gain": rear_air_gain, "rear_highmid_gain": rear_highmid_gain,
    }
    auto_info = {
        "vocal_risk": vocal_risk,
        "telephone_risk": bool(telephone_risk),
        "dry_bass_score": dry_bass_score,
        "hall_score": hall_score,
        "narrow_score": narrow_score,
        "side_material": side_material,
        "adaptive_intensity": adaptive_intensity,
        "rear_enhancement_amount": rear_enhancement_amount,
        "rear_enhancement_applied": bool(rear_enhancement and rear_enhancement_amount > 0.0),
        "rear_enhancement_plan": AUTO_ACOUSTIC_REAR_ENHANCEMENT_PLAN,
    }
    return auto_preset, auto_info


def resolve_preset(preset_mode, manual_preset, analysis, rear_enhancement=False):
    """Resolve manual / auto_select / auto_acoustic into final preset values."""
    mode = normalize_preset_name(preset_mode)
    if mode == "auto_select":
        selected = auto_select_preset(analysis)
        return selected, "auto_select", get_preset(selected), {}
    if mode == "auto_acoustic":
        preset, info = generate_auto_acoustic_preset(analysis, rear_enhancement=rear_enhancement)
        return "auto_acoustic", "auto_acoustic", preset, info
    selected = normalize_preset_name(manual_preset if mode == "manual" else mode)
    return selected, "manual", get_preset(selected), {}
