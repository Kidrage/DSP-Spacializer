# Streaming Stereo Spatializer / DSP Spatializer 使用说明（Pseudo-Object 分支）

> **Branch notice / 分支说明 — `Pseudo-Object` experimental branch / 实验分支**
>
> **EN:** This README describes the `Pseudo-Object` branch, not the repository `main` branch. The `main` branch should be treated as the legacy fixed 4.0 channel-renderer line. This branch keeps the legacy path working, while adding pseudo-object scene metadata, pseudo-object layer audio export, and modular pseudo-object decoders for layout-driven experiments.
>
> **中文：** 本 README 描述的是 `Pseudo-Object` 分支，不是仓库的 `main` 分支。`main` 应视为 legacy fixed 4.0 channel renderer 主线。本分支在保留 legacy 路径可用的基础上，新增 pseudo-object scene metadata、pseudo-object layer audio 导出，以及面向 speaker layout 实验的模块化 pseudo-object decoder。
>
> **Important / 重要：** Pseudo objects are **spatial-function objects** derived from DSP layers. They are not clean stems, not source-separated instruments, and not claims of real object audio.
>
> **重要：** pseudo object 是由 DSP 空间功能层派生出的 **spatial-function object**。它不是 clean stem，不是 AI 分离得到的乐器/人声 stem，也不代表真正的 object audio。

## Main vs Pseudo-Object / `main` 与 `Pseudo-Object` 分支对照

| Area / 项目 | `main` branch / 主分支 | `Pseudo-Object` branch / 本分支 |
| --- | --- | --- |
| Primary path / 主链路 | Stereo → DSP layers → fixed `renderer_4ch.py` | Same legacy path, plus pseudo-object scene path / 保留 legacy 链路，并新增 pseudo-object scene 链路 |
| Metadata / 元数据 | Diagnostics-focused JSON / 以 diagnostics JSON 为主 | Adds `pseudo_object_spatial_v1` scene metadata / 新增 pseudo-object scene metadata |
| Object audio / 对象音频 | Not exported as object layers / 不导出 object layer audio | Exports DSP layer material under `*_objects/` / 在 `*_objects/` 下导出 DSP layer material，但不是 clean stem |
| Decoding / 解码 | Fixed 4.0 renderer / 固定四声道渲染 | DBAP fallback, 2D VBAP, hybrid spread-VBAP / 支持 DBAP fallback、2D VBAP、hybrid spread-VBAP |
| CLI additions / CLI 增量 | Legacy output options / legacy 输出参数 | Adds `--export-pseudo-scene`, `--decode-pseudo-scene`, `--pseudo-scene-only`, `--pseudo-renderer` |
| Intended use / 用途 | Stable 4.0 / binaural upmix / 稳定 fixed-channel 4.0 / binaural upmix | Experimental pseudo-object architecture and decoder research / pseudo-object 架构与 decoder 实验研究 |

**EN:** If you want the original stable fixed-channel behavior, use `main` or run this branch without pseudo-object flags. If you want pseudo-object scene export, layout-driven decoding, or VBAP renderer experiments, use the `Pseudo-Object` branch.

**中文：** 如果只需要原来的稳定 fixed-channel 4.0 / binaural 行为，请使用 `main`，或者在本分支不加 pseudo-object 相关参数运行。若需要导出 pseudo-object scene、尝试 layout-driven decoder，或进行 VBAP / hybrid renderer 实验，请使用 `Pseudo-Object` 分支。

## Quick Reference / 快速说明

**EN:** This branch does not split stereo audio into real instrument objects. Instead, it describes the existing DSP layers, such as `bass`, `front_core`, `side_width`, `rear_ambience`, `high_air`, and `low_body_support`, as interpretable spatial-function pseudo objects. The scene JSON can be consumed by different decoders. The current default layout is `default_quad_4p0`, and three pseudo renderers are provided.

**中文：** 本分支不是把 stereo 分成真实乐器对象，而是把现有 DSP layer，例如 `bass`、`front_core`、`side_width`、`rear_ambience`、`high_air`、`low_body_support`，描述成可解释的 spatial-function pseudo objects。scene JSON 可以交给不同 decoder 使用；当前默认支持 `default_quad_4p0`，并提供三种 pseudo renderer。

- `dbap_quad_v1`
  - **EN:** Distance-based DBAP-like fallback. It produces a smoother and more forgiving sound distribution.
  - **中文：** 距离型 DBAP-like fallback，声音分布更平滑、更宽容。
- `vbap_2d_v1`
  - **EN:** Horizontal 2D VBAP. It gives sharper positioning and is better suited for point-like pseudo objects.
  - **中文：** 水平 2D VBAP，定位更 sharp，更适合 point-like pseudo objects。
- `hybrid_vbap_v1`
  - **EN:** Recommended mode. It chooses VBAP, spread VBAP, or stereo-bed special handling according to object type, spread, and diffuseness.
  - **中文：** 推荐模式，会根据 object type / spread / diffuseness 选择 VBAP、spread VBAP 或 stereo bed 特判。

Common commands / 常用命令：

```bash
python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --export-pseudo-scene

python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode both \
  --export-pseudo-scene \
  --decode-pseudo-scene \
  --pseudo-renderer hybrid_vbap_v1

python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --pseudo-scene-only
```

Typical pseudo-object outputs / 典型 pseudo-object 输出：

```text
outputs/<song>_auto_acoustic_pseudo_scene.json
outputs/<song>_auto_acoustic_objects/bass_anchor.wav
outputs/<song>_auto_acoustic_objects/front_core.wav
outputs/<song>_auto_acoustic_objects/side_width.wav
outputs/<song>_auto_acoustic_objects/rear_ambience.wav
outputs/<song>_auto_acoustic_objects/high_air.wav
outputs/<song>_auto_acoustic_objects/low_body_support.wav
outputs/<song>_auto_acoustic_pseudo_quad_hybrid_4ch.wav
```

## Overview / 概览

**EN:** This project is a non-AI, rule-based / signal-processing-driven stereo → 4.0 / pseudo-object spatializer. The legacy path still outputs fixed `[LF, RF, LB, RB]` 4-channel audio. The `Pseudo-Object` branch additionally exports scene metadata and object layer material, so that later work can decode the same layer content through different speaker-layout decoders.

**中文：** 本项目是一个非 AI、规则 / 信号处理驱动的 stereo → 4.0 / pseudo-object spatializer。legacy 路径仍然输出固定 `[LF, RF, LB, RB]` 四声道；`Pseudo-Object` 分支额外导出 scene metadata 和 object layer material，以便后续使用不同 speaker layout decoder 进行解码。

**EN:** The project implements a non-AI streaming stereo spatializer for a 4.0 speaker system. It converts stereo L/R audio into DSP spatial-function layers, then renders those layers to logical 4.0 output: left front, right front, left back, and right back.

**中文：** 这个项目实现了一个面向 4.0 扬声器系统的非 AI streaming stereo spatializer。它会将 stereo L/R 音频转换成 DSP spatial-function layers，再渲染到逻辑 4.0 输出：左前、右前、左后、右后。

**EN:** This is not AI-based source separation. The spatial layers are not clean stems; they are spatial-function buses used for rendering.

**中文：** 这不是基于 AI 的音源分离。这里的 spatial layers 不是 clean stems，而是用于空间渲染的 spatial-function buses。

## Key Features / 主要特性

- **EN:** Converts stereo L/R audio to 4.0 spatial output.
  - **中文：** 将 stereo L/R 音频转换为 4.0 空间音频输出。
- **EN:** Extracts DSP spatial-function layers:
  - Bass Layer: low-frequency body
  - Low Body Support: warmth/body support
  - Front Core: center-correlated content
  - Side Width: stereo difference
  - Rear Ambience: diffuse, low-coherence content
  - High Air: high-frequency content
- **中文：** 提取 DSP 空间功能层：
  - Bass Layer：低频主体 / 低频厚度
  - Low Body Support：温暖感 / 中低频支撑
  - Front Core：中置相关内容
  - Side Width：立体声差异信息
  - Rear Ambience：扩散、低相干的环境层
  - High Air：高频空气感内容
- **EN:** Provides multiple presets for different spatialization styles.
  - **中文：** 提供多个 preset，用于不同风格的空间化处理。
- **EN:** Uses energy matching to maintain consistent loudness.
  - **中文：** 使用 energy matching 保持响度一致性。
- **EN:** Includes a limiter to prevent clipping.
  - **中文：** 内置 limiter，避免 clipping。
- **EN:** Exports diagnostic output for analysis.
  - **中文：** 输出 diagnostics，便于分析渲染结果。
- **EN:** Optionally exports pseudo-object scenes and decodes them with the default quad 4.0 decoder.
  - **中文：** 可选导出 pseudo-object scene，并使用默认 quad 4.0 decoder 解码。

## Batch Spatial Diagnostics Sync / 批量空间诊断同步

**EN:** This `Pseudo-Object` branch also includes the Gitea-side batch diagnostics work merged from `feat: add batch spatial diagnostics`. These tools are compatible with both the legacy 4.0 path and pseudo-object experiments.

**中文：** `Pseudo-Object` 分支也包含从 `feat: add batch spatial diagnostics` 合并来的 Gitea 侧批量诊断工具。这些工具同时兼容 legacy 4.0 路径和 pseudo-object 实验。

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
python run_spatializer.py my_song.wav --out-dir outputs --diagnostics-only
python run_spatializer.py my_song.wav --out-dir outputs --write-quality-report
```

Related files / 相关文件：

- `batch_spatial_diagnostics.py`
  - **EN:** Generates batch metrics, summaries, and reports.
  - **中文：** 生成批量 metrics、summary 和 report。
- `spatial_quality_report.py`
  - **EN:** Writes Markdown quality reports.
  - **中文：** 生成 Markdown 格式的质量报告。
- `spatial_quality_thresholds.json`
  - **EN:** Stores global and preset-specific quality thresholds.
  - **中文：** 存储全局和 preset-specific 的质量阈值。

**EN:** These diagnostics describe spatial safety and render quality. They do not change the definition of pseudo objects. Pseudo objects remain DSP-derived spatial-function objects, not clean source-separated stems.

**中文：** 这些 diagnostics 描述的是 spatial safety 和 render quality，并不改变 pseudo object 的定义。pseudo object 仍然是由 DSP 派生的 spatial-function object，不是 clean source-separated stem。

## Pseudo-Object Upmix Mode / Pseudo-Object Upmix 模式

**EN:** DSP-Spacializer now has two compatible rendering paths.

**中文：** DSP-Spacializer 现在有两条兼容的渲染路径。

1. **Legacy fixed 4.0 mode / Legacy 固定 4.0 模式**
   - **EN:** This is the original deterministic channel renderer in `renderer_4ch.py`. It directly maps DSP spatial-function layers to `[LF, RF, LB, RB]` and remains the default behavior for `4ch`, `binaural`, and `both` output modes.
   - **中文：** 这是 `renderer_4ch.py` 中原有的 deterministic channel renderer。它会直接把 DSP spatial-function layers 映射到 `[LF, RF, LB, RB]`，并且仍然是 `4ch`、`binaural`、`both` 输出模式的默认行为。
2. **Pseudo-object scene mode / Pseudo-object scene 模式**
   - **EN:** This is an additional metadata path that turns the same DSP layers into a `pseudo_object_spatial_v1` scene. These pseudo objects are spatial-function objects, not real instrument objects and not source-separated clean stems. Object audio files are layer material for a decoder, not final speaker feeds.
   - **中文：** 这是一条额外的 metadata 路径，会把同一组 DSP layers 转换成 `pseudo_object_spatial_v1` scene。这些 pseudo objects 是 spatial-function objects，不是真实乐器对象，也不是 source-separated clean stems。object audio files 是给 decoder 使用的 layer material，不是最终 speaker feeds。

**EN:** The first pseudo-object version emits six objects.

**中文：** 第一版 pseudo-object 会导出六个 objects。

- `bass_anchor`
- `front_core`
- `side_width`
- `rear_ambience`
- `high_air`
- `low_body_support`

**EN:** The scene stores coordinates, spread/depth/diffuseness, gain, constraints, and decoder hints. Current renderers target `default_quad_4p0`; future decoders can reuse the same metadata for other horizontal speaker layouts.

**中文：** scene 会存储坐标、spread / depth / diffuseness、gain、constraints 和 decoder hints。当前 renderer 目标是 `default_quad_4p0`；未来 decoder 可以复用同一套 metadata，适配其他水平扬声器布局。

Example output when pseudo-object export is enabled / 启用 pseudo-object export 后的示例输出：

```text
spatializer_outputs_clean/
  Song_auto_acoustic_4ch.wav
  Song_auto_acoustic_binaural_4p0.wav
  Song_auto_acoustic_pseudo_scene.json
  Song_auto_acoustic_pseudo_quad_hybrid_4ch.wav
  Song_auto_acoustic_objects/
    bass_anchor.wav
    front_core.wav
    side_width.wav
    rear_ambience.wav
    high_air.wav
    low_body_support.wav
  Song_auto_acoustic_diagnostics.json
  batch_manifest.json
```

CLI examples / CLI 示例：

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --export-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode both --export-pseudo-scene --decode-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --pseudo-scene-only
```

## Pseudo-Object Rendering Algorithms / Pseudo-Object 渲染算法

**EN:** Pseudo-object decoding is routed through modular renderers under `renderers/`. These renderers consume scene metadata and speaker layout data. They do not treat pseudo objects as clean stems or real isolated instruments.

**中文：** pseudo-object decoding 现在通过 `renderers/` 下的模块化 renderer 调度。这些 renderer 会读取 scene metadata 和 speaker layout data；它们不会把 pseudo objects 当作 clean stems 或真实隔离乐器来处理。

- `dbap_quad_v1`
  - **EN:** The first pseudo-object decoder, kept as a fallback. It uses distance-based amplitude panning, so it is smooth and forgiving for diffuse layer material.
  - **中文：** 第一版 pseudo-object decoder，保留为 fallback。它使用 distance-based amplitude panning，因此对 diffuse layer material 更平滑、更宽容。
- `vbap_2d_v1`
  - **EN:** Horizontal 2D VBAP. It chooses the adjacent speaker pair that encloses the object azimuth and applies equal-power normalization to the active pair. It is sharper and more layout-driven, so it is better for point-like pseudo objects.
  - **中文：** 水平 2D VBAP。它会选择包围 object azimuth 的相邻扬声器对，并对 active pair 做 equal-power normalization。它定位更 sharp，也更依赖 layout，因此更适合 point-like pseudo objects。
- `hybrid_vbap_v1`
  - **EN:** Recommended V2 mode. It keeps `front_core` as a stereo bed, uses VBAP for sharper objects such as `bass_anchor`, and uses spread VBAP for diffuse or lateral beds such as `side_width`, `rear_ambience`, and `high_air`.
  - **中文：** 推荐的 V2 模式。它将 `front_core` 保持为 stereo bed，对 `bass_anchor` 这类更 sharp 的 object 使用 VBAP，对 `side_width`、`rear_ambience`、`high_air` 这类 diffuse / lateral bed 使用 spread VBAP。

**EN:** VBAP is layout-driven decoding. It calculates speaker gains from object azimuths and speaker azimuths instead of hard-coding fixed 4-channel routing amounts. V2 supports horizontal 2D layouts and the default quad 4.0 layout. Future versions can extend the same renderer interface to other planar arrays.

**中文：** VBAP 是 layout-driven decoding。它根据 object azimuth 和 speaker azimuth 计算 speaker gains，而不是 hard-code 固定的 4-channel routing amount。V2 支持水平 2D layout 和默认 quad 4.0 layout；未来版本可以沿用同一个 renderer interface 扩展到其他平面扬声器阵列。

Renderer selection example / renderer 选择示例：

```bash
python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --export-pseudo-scene \
  --decode-pseudo-scene \
  --pseudo-renderer hybrid_vbap_v1
```

Decoded file names include the renderer family / 解码后的文件名会包含 renderer family：

```text
*_pseudo_quad_dbap_4ch.wav
*_pseudo_quad_vbap_4ch.wav
*_pseudo_quad_hybrid_4ch.wav
```

**EN:** Diagnostics include `pseudo_object_scene` when scene export is enabled and `pseudo_decode` when the scene is decoded. The legacy field `mono_fold_down_delta_db` is preserved, but it refers to the legacy average-4 fold down `(LF+RF+LB+RB)/4`. New fields clarify the basis.

**中文：** 当启用 scene export 时，diagnostics 会包含 `pseudo_object_scene`；当 scene 被 decode 时，diagnostics 会包含 `pseudo_decode`。legacy 字段 `mono_fold_down_delta_db` 被保留，但它指的是 legacy average-4 fold down `(LF+RF+LB+RB)/4`。新增字段用于明确计算基准。

- `mono_fold_down_delta_db_avg4_legacy`
- `mono_fold_down_delta_db_front_norm`
- `mono_front_only_delta_db`

## Installation / 安装

1. **EN:** Clone this repository.
   - **中文：** 克隆本仓库。
2. **EN:** Install dependencies.
   - **中文：** 安装依赖。

```bash
pip install numpy librosa soundfile scipy
```

## Usage / 使用方法

**EN:** To run with the generated test audio:

**中文：** 使用生成的测试音频运行：

```bash
python generate_test_audio.py  # Creates input_audio/test_input.wav / 创建 input_audio/test_input.wav
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

**EN:** To run with your own audio file:

**中文：** 使用自己的音频文件运行：

```bash
python run_spatializer.py input.wav --preset-mode auto_acoustic --output-mode both
```

### Arguments / 参数说明

- `input.wav`
  - **EN:** Path to the input stereo WAV file.
  - **中文：** 输入 stereo WAV 文件路径。
- `--out-dir`
  - **EN:** Output directory.
  - **中文：** 输出目录。
- `--preset-mode`
  - **EN:** Selects `manual`, `auto_select`, or `auto_acoustic`.
  - **中文：** 选择 `manual`、`auto_select` 或 `auto_acoustic`。
- `--output-mode`
  - **EN:** Selects `4ch`, `binaural`, or `both`.
  - **中文：** 选择 `4ch`、`binaural` 或 `both`。
- `--preset`
  - **EN:** Manual preset name when `--preset-mode manual` is used.
  - **中文：** 当使用 `--preset-mode manual` 时指定手动 preset 名称。
- `--analysis-seconds`
  - **EN:** Duration of analysis in seconds. Default: `2.0`.
  - **中文：** 分析时长，单位为秒。默认值：`2.0`。
- `--export-pseudo-scene`
  - **EN:** Exports pseudo-object JSON and object layer audio.
  - **中文：** 导出 pseudo-object JSON 和 object layer audio。
- `--decode-pseudo-scene`
  - **EN:** Decodes the pseudo-object scene to a renderer-tagged quad WAV file.
  - **中文：** 将 pseudo-object scene 解码为带 renderer 标记的 quad WAV 文件。
- `--pseudo-renderer`
  - **EN:** Selects `dbap_quad_v1`, `vbap_2d_v1`, or `hybrid_vbap_v1`.
  - **中文：** 选择 `dbap_quad_v1`、`vbap_2d_v1` 或 `hybrid_vbap_v1`。
- `--pseudo-scene-only`
  - **EN:** Exports only pseudo-object scene/audio and skips legacy file exports.
  - **中文：** 只导出 pseudo-object scene / audio，跳过 legacy 文件导出。
- `--no-diagnostics`
  - **EN:** Disables JSON diagnostics export.
  - **中文：** 禁用 JSON diagnostics 导出。

## Presets / 预设

- **natural**
  - **EN:** Balanced default mode.
  - **中文：** 平衡型默认模式。
- **wide**
  - **EN:** More obvious spatial effect.
  - **中文：** 空间感更明显的模式。
- **vocal_safe**
  - **EN:** For vocal-heavy music.
  - **中文：** 面向人声占比较高的音乐。
- **live**
  - **EN:** For live or acoustic recordings.
  - **中文：** 面向现场 / 原声录音。
- **club**
  - **EN:** For electronic or bass-heavy music.
  - **中文：** 面向电子音乐或低频较重的音乐。
- **bypass**
  - **EN:** No spatialization.
  - **中文：** 不进行空间化处理。
- **ms_baseline**
  - **EN:** Simple M/S baseline for comparison.
  - **中文：** 用于对比的简单 M/S baseline。

## Listening to 4-Channel Audio / 监听四声道音频

**EN:** Most consumer audio equipment is stereo. To listen to the 4-channel output, use one of the following approaches.

**中文：** 大多数消费级音频设备都是 stereo。若要监听 4-channel 输出，可以使用以下方式。

1. **EN:** Use a surround sound system with 4 speakers.
   - **中文：** 使用带 4 个扬声器的 surround sound system。
2. **EN:** Use headphones with a virtual surround sound processor.
   - **中文：** 使用带虚拟环绕处理器的耳机方案。
3. **EN:** Use audio software that supports 4-channel playback.
   - **中文：** 使用支持 4-channel playback 的音频软件。

## Tuning Presets / 调整预设

**EN:** To tune presets:

**中文：** 调整 preset 时：

1. **EN:** Modify the routing parameters in `presets.py`.
   - **中文：** 修改 `presets.py` 中的 routing parameters。
2. **EN:** Adjust the layer routing logic in `layer_router.py`.
   - **中文：** 调整 `layer_router.py` 中的 layer routing logic。
3. **EN:** Experiment with different decorrelation settings in `decorrelator.py`.
   - **中文：** 在 `decorrelator.py` 中尝试不同 decorrelation settings。
4. **EN:** Use the diagnostic output to understand the impact of changes.
   - **中文：** 使用 diagnostic output 分析修改带来的影响。

## File Structure / 文件结构

```text
streaming_stereo_spatializer/
│
├── run_spatializer.py          # Main script / 主脚本
├── audio_io.py                 # Audio loading and export / 音频读取与导出
├── streaming_analyzer.py       # Audio analysis / 音频分析
├── layer_extractor.py          # Layer extraction / 空间功能层提取
├── layer_router.py             # Layer routing / 层路由
├── decorrelator.py             # Rear ambience decorrelation / 后方环境层去相关
├── renderer_4ch.py             # 4-channel rendering / 四声道渲染
├── energy_manager.py           # Loudness matching / 响度匹配
├── limiter.py                  # Clipping prevention / 防止削波
├── diagnostics.py              # Diagnostic output / 诊断输出
├── batch_spatial_diagnostics.py
│                                # Batch spatial metrics and summaries / 批量空间指标与汇总
├── spatial_quality_report.py   # Markdown quality report writer / Markdown 质量报告生成器
├── spatial_quality_thresholds.json
│                                # Quality risk thresholds / 质量风险阈值
├── pseudo_object_schema.py      # Pseudo-object metadata schema validation / pseudo-object 元数据 schema 校验
├── pseudo_object_scene.py       # Pseudo-object scene builder / pseudo-object scene 构建器
├── object_audio_export.py       # Object layer audio export helpers / object layer audio 导出辅助函数
├── speaker_layout.py            # Speaker layout descriptors / 扬声器布局描述
├── object_decoder.py            # Pseudo-object renderer dispatch layer / pseudo-object renderer 调度层
├── renderers/                   # DBAP, 2D VBAP and hybrid renderer modules / DBAP、2D VBAP 与 hybrid renderer 模块
├── scripts/check_text_integrity.py
│                                # LF newline and line integrity check / LF 换行与行完整性检查
├── scene_diagnostics.py         # Scene summary diagnostics / scene 汇总诊断
├── presets.py                   # Spatialization presets / 空间化预设
├── generate_test_audio.py       # Test tone generation / 测试音频生成
├── tests/                       # Pytest regression tests / pytest 回归测试
├── README.md                    # This file / 本文件
```

## Implementation Notes / 实现说明

- **EN:** The system is designed to resemble a streaming PCM processor.
  - **中文：** 系统设计上接近一个 streaming PCM processor。
- **EN:** It uses a rule-based approach rather than AI.
  - **中文：** 它使用规则 / 信号处理方法，而不是 AI。
- **EN:** The architecture prioritizes stable front image and bass protection.
  - **中文：** 架构优先保证稳定前方声像和低频保护。
- **EN:** Rear ambience is designed to feel wide without obvious echoes.
  - **中文：** 后方 ambience 的设计目标是宽阔，但不要产生明显 echo。
- **EN:** Energy management prevents the output from becoming louder than the input.
  - **中文：** energy management 用于防止输出响度明显高于输入。

## Limitations / 局限性

- **EN:** This is a simulation, not real hardware.
  - **中文：** 这是一个模拟系统，不是真实硬件。
- **EN:** It does not handle physical speaker calibration.
  - **中文：** 它不处理物理扬声器校准。
- **EN:** The presets need to be tuned based on listening experience.
  - **中文：** preset 需要根据实际听感继续调试。
- **EN:** It does not implement advanced features like Dolby Atmos metadata.
  - **中文：** 它没有实现 Dolby Atmos metadata 等高级特性。
- **EN:** It is not designed for network streaming or hardware distribution.
  - **中文：** 它不是为网络串流或硬件分发而设计的。

## Why Not AI? / 为什么不是 AI？

**EN:** This project is explicitly not AI-based. It uses simple signal-processing techniques to extract spatial characteristics from stereo audio. The spatial layers are not clean stems; they are spatial-function buses used for rendering to a 4.0 speaker system.

**中文：** 本项目明确不是基于 AI 的方案。它使用简单的信号处理技术，从 stereo audio 中提取空间特征。这里的 spatial layers 不是 clean stems，而是用于渲染到 4.0 speaker system 的 spatial-function buses。

## Next Steps / 下一步

**EN:** To evaluate the system:

**中文：** 评估系统时可以：

1. **EN:** Compare original stereo, bypass, `ms_baseline`, `natural`, and `wide`.
   - **中文：** 对比 original stereo、bypass、`ms_baseline`、`natural` 和 `wide`。
2. **EN:** Test with different music genres.
   - **中文：** 用不同音乐风格进行测试。
3. **EN:** Adjust presets based on listening experience.
   - **中文：** 根据听感调整 presets。
4. **EN:** Add visualization of spatial characteristics.
   - **中文：** 添加空间特征可视化。
5. **EN:** Implement more advanced decorrelation techniques.
   - **中文：** 实现更高级的 decorrelation 技术。
