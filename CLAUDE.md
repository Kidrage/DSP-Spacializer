# CLAUDE.md — DSP-Spacializer

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 独立 DSP 项目。与 AgentLab 无关。确定性（非 AI）stereo → 4.0 声道 / binaural DSP 空间化器。

## Git 状态

- 分支：`feat/dsp-feedback-loop-s1`
- 有未提交修改：`config_center.py`、`.gitignore`
- 备份分支：`backup/main-before-feedback-loop-20260618`

## 核心链路

```
MP3/WAV 加载 → 48kHz 重采样 → streaming_analyzer(2s窗) → preset 生成/选择
→ layer_extractor(6层) → layer_router(参数适配) → renderer_4ch
→ spatial_safety → energy_manager → limiter → WAV + diagnostics JSON 导出
```

## 常用命令

```bash
# 批量处理（使用 config_center.py 中的路径和模式）
python run_spatializer.py

# 单曲渲染
python run_spatializer.py 曲库/xxx.mp3 --preset-mode auto_acoustic --output-mode 4ch
python run_spatializer.py 曲库/xxx.mp3 --preset-mode manual --preset wide_smooth --output-mode 4ch

# binaural 耳机预览
python run_spatializer.py 曲库/xxx.mp3 --preset-mode auto_acoustic --output-mode binaural

# 同时输出 4ch + binaural
python run_spatializer.py 曲库/xxx.mp3 --preset-mode auto_acoustic --output-mode both

# 只分析不导出（调试用）
python run_spatializer.py 曲库/xxx.mp3 --diagnostics-only

# 质量报告
python run_spatializer.py 曲库/xxx.mp3 --write-quality-report

# 反馈闭环
python run_feedback_spatializer.py 曲库/xxx.mp3 --preset-mode auto_acoustic --output-mode 4ch \
  --tuning-profile profiles/xxx.json --subjective-score my_score.json --write-evaluation-record
python suggest_tuning_profile.py Output-DSP/ --profile-id round_001 --out profiles/round_001.json

# 批量诊断
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
```

## 测试

```bash
# 全部测试
python -m pytest -q

# 重点测试套件
python -m pytest -q tests/test_run_spatializer_cli.py tests/test_spatial_safety.py \
  tests/test_batch_spatial_diagnostics.py tests/test_tuning_profile.py \
  tests/test_subjective_feedback.py tests/test_feedback_profile_suggester.py

# 单文件
python -m pytest tests/test_spatial_safety.py -v
```

## 架构基础：5 频段分割

`dsp_utils.py:band_split()` 定义了 legacy renderer、router 与 diagnostics
共用的频段划分：

| 频段 | 范围 | 用途 |
|------|------|------|
| `bass` | <120 Hz | 低频核心 |
| `low_mid` | 120-500 Hz | 体积感/温暖度 |
| `mid` | 500-2000 Hz | 人声/主体基频 |
| `high_mid` | 2-6 kHz | 临场感/清晰度/齿音风险 |
| `air` | >6 kHz | 空气感/嘶声风险 |

这些 legacy/runtime 滤波都是 causal（`sosfilt`，非 `filtfilt`），更接近流式行为。
Spatial Core V2.1 是明确的离线候选例外：`spatial_core/zones.py` 使用
2048/512 Hann STFT 做互补、可重建的七区 M/S 分解；`balanced-depth` 的
180 Hz–8 kHz late-field bandpass 仅用于房间响应塑形，不替代 legacy
五频段定义，也不进入实时主链。

## 核心文件

### 渲染主线

| 文件 | 角色 |
|------|------|
| `run_spatializer.py` | 主入口，单曲/批量 CLI |
| `config_center.py` | 输入/输出路径、模式开关、binaural/CTC/speaker 距离参数 |
| `streaming_analyzer.py` | 2 秒窗口立体声分析：width、center dominance、分频段 coherence、side ratio、transient density |
| `presets.py` | **调参主战场** — 9 个手动 preset + `generate_auto_acoustic_preset()` + `auto_select_preset()` |
| `layer_extractor.py` | 6 层空间功能层提取（bass、low_body、front_L/R、side_width、rear_ambience、high_air） |
| `layer_router.py` | preset → routing 参数适配。**关键**：`auto_acoustic` 模式下 `apply_analysis_adaptation=False`，因为 auto_acoustic 已将分析特征融入参数公式 |
| `renderer_4ch.py` | 固定 `[LF, RF, LB, RB]` 渲染，含后方去相关、tone shaping、rear floor 保护 |
| `spatial_safety.py` | 后方安全保护 + 9 项质量指标计算 + 风险分类（pass/warn/fail） |
| `energy_manager.py` | 能量匹配 |
| `limiter.py` | 峰值限幅 |
| `audio_io.py` | MP3/WAV/FLAC 加载与导出（macOS 上 MP3 走 librosa + CoreAudio，无需 ffmpeg） |
| `diagnostics.py` | 诊断 JSON 生成 |

### Binaural 模块

| 文件 | 角色 |
|------|------|
| `binaural_renderer.py` | 程序化 HRTF 虚拟扬声器渲染（**不加载 SOFA 文件**，使用确定性合成线索：ITD、频段相关 ILD、pinna notch、body reflection）+ CTC 逆滤波 + Room RIR |

Binaural 渲染链条：
```
4ch final → render_4ch_binaural(procedural HRTF, ITD+ILD+pinna) → 立体声耳机
  ├─ 可选：apply_room_rir_to_binaural（合成小房间 RIR，增强外化感）
  └─ 可选：render_binaural_to_ctc_4ch（binaural 目标反解到 4ch 扬声器馈送）
```

### 反馈闭环工具链

| 文件 | 角色 |
|------|------|
| `run_feedback_spatializer.py` | 闭环渲染 wrapper（不修改稳定渲染路径） |
| `subjective_feedback.py` | 主观评分校验（`overall_preference` 必填，1-5 分） |
| `tuning_profile.py` | 外部 tuning profile 校验与应用 |
| `feedback_profile_suggester.py` | **确定性规则引擎**：评分 → 调参建议（不做 AI/ML） |
| `suggest_tuning_profile.py` | CLI 生成下一轮 tuning profile |

反馈数据流：`批量渲染 → 主观打分 → evaluation record → suggested tuning profile → 下一轮渲染`。只写外部 JSON 产物，不修改 `presets.py`。

## auto_acoustic 调参架构

```
6 原始特征 → 5 中间得分 → 14 参数公式 → 3 覆写安全网 → rear_enhancement 叠加
```

**5 个中间得分**：
- `vocal_risk`（中心人声风险，越高越收紧后方）
- `telephone_risk`（电话声/窄频风险，bool 触发覆写）
- `dry_bass_score`（低频干/紧程度）
- `hall_score`（厅堂/扩散程度，过高会压制 amb_rear）
- `narrow_score`（声场窄程度，越高越积极推后方）
- 辅助：`side_material`（有效侧向素材量）+ `adaptive_intensity`（整体自适应强度系数）

**3 个覆写安全网**（按优先级）：
1. `telephone_risk` → 大幅收紧后方高频 + 提高 guard_scale
2. `hall_score > 0.65` → 限制 amb_rear、decorrelation、rear_highmid_gain
3. `dry_bass_score > 0.65`（非 telephone） → 补低频包围

**调参层次**：
- **轻量**：`AUTO_ACOUSTIC_REAR_ENHANCEMENT_PLAN`（`presets.py:121-131`）— 只改 4 个系数
- **中度**：14 个参数公式的基准值、系数、上下限（`presets.py:218-231`）
- **深度**：5 个中间得分公式 + 3 个覆写阈值（`presets.py:202-213,238-262`）

## 14 参数 Preset 模型

`presets.py` 顶部注释有完整的参数 → 听感影响映射和常见问题调参指南。以下是关键约束：

- `guard_scale` 是人声/瞬态保护的**全局乘数**，影响 `layer_router.py` 中 center guard、transient guard 的衰减力度
- `rear_floor_ratio` + `max_rear_makeup` 是后方保底机制（在 `renderer_4ch.py:apply_rear_floor()` 中执行）
- `bass_quad` 控制低频四声道分配，过大导致低频定位散
- `decorrelation` 只作用于后方，过大会导致梳状滤波

## 质量阈值系统

`spatial_quality_thresholds.json` + `spatial_safety.py:DEFAULT_QUALITY_THRESHOLDS` 定义了 9 项质量指标阈值。支持 **全局阈值 + preset 级别覆盖**（`load_quality_thresholds()` 会 deep-merge 外部 JSON 到内置默认值）。

`classify_quality_risks()` 返回 `pass/warn/fail` 三级分类，`detect_over_protection()` 检测安全保护是否过度压制了后方空间感。

## 当前配置

- 输入：`~/Desktop/Coding/spatializer_outputs/曲库/`（25 首 MP3）
- 输出：`~/Desktop/Coding/spatializer_outputs/Output-DSP/`
- 模式：`auto_acoustic`，4ch 输出，48kHz，rear enhancement 开启
- Room RIR：开启（RT60=0.30s，dry room）
- 扬声器距离：前 1.2m，后 0.95m（含空气吸收 0.5 dB/m @8kHz）

## 环境

```bash
pip install numpy scipy soundfile librosa
```
