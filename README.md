# Streaming Stereo Spatializer / 流媒体立体声空间化器

## English

DSP-Spacializer is a stable, non-AI stereo to fixed 4.0 / binaural DSP spatializer. It converts stereo L/R audio into deterministic spatial-function layers and renders them to logical 4.0 output:

```text
[LF, RF, LB, RB]
```

The main branch is the clean fixed-channel line. It is not a source-separation system, not a pseudo-object scene renderer, not a DBAP/VBAP/hybrid object decoder, and not a built-in listener model. Feedback-loop work is kept in separate reviewable tooling so the stable renderer can be rolled back or used unchanged.

## 中文

DSP-Spacializer 是一个稳定的、非 AI 分离的 stereo 到固定 4.0 / binaural DSP 空间化原型。它会把 stereo L/R 音频转换为确定性的空间功能层，并渲染到逻辑 4.0 输出：

```text
[LF, RF, LB, RB]
```

`main` 主线保持为干净的固定声道 DSP 路线。它不是源分离系统，不是 pseudo-object 场景渲染器，不是 DBAP/VBAP/hybrid 对象解码器，也不是内置听感学习模型。反馈闭环功能被放在独立、可审查的工具链中，这样稳定渲染器可以随时回滚或保持原样使用。

---

## What It Does / 功能范围

### English

- Loads stereo, mono, or multi-channel audio and normalizes it for processing.
- Analyzes stereo width, center dominance, spectral bands, coherence, and transient behavior.
- Extracts DSP spatial-function layers such as bass body, low-body support, front core, side width, rear ambience, and high air.
- Routes those layers through fixed-channel presets.
- Renders fixed 4.0 output with `renderer_4ch.py`.
- Applies rear-channel spatial safety, energy matching, limiting, diagnostics, and optional quality reports.
- Optionally renders binaural headphone previews and binaural-to-4ch CTC output.
- Optionally records subjective listening feedback and suggests external tuning profiles without modifying the stable renderer path.

### 中文

- 读取 stereo、mono 或多声道音频，并统一整理为可处理输入。
- 分析 stereo width、center dominance、频段特征、coherence 与 transient 行为。
- 提取 DSP 空间功能层，例如 bass body、low-body support、front core、side width、rear ambience、high air。
- 通过固定声道 preset 对这些功能层进行路由。
- 使用 `renderer_4ch.py` 渲染固定 4.0 输出。
- 应用后场安全保护、能量匹配、limiter、diagnostics 与可选 quality report。
- 可选输出 binaural headphone preview 与 binaural-to-4ch CTC。
- 可选记录主观听感反馈，并生成外部 tuning profile 建议，不直接修改稳定渲染路径。

---

## What It Does Not Do / 非目标

### English

- No AI source separation.
- No clean stem extraction.
- No pseudo-object scene JSON export.
- No object-layer audio export.
- No speaker-layout object decoding.
- No DBAP, VBAP, or hybrid pseudo-object renderer.
- No automatic modification of core preset code from listener feedback.

Pseudo-object scene/export/DBAP/VBAP/hybrid renderer work has been split into:
`https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer`.
See [docs/BRANCH_STRATEGY.md](docs/BRANCH_STRATEGY.md).

### 中文

- 不做 AI 源分离。
- 不做 clean stem 提取。
- 不导出 pseudo-object scene JSON。
- 不导出 object-layer audio。
- 不负责 speaker-layout object decoding。
- 不内置 DBAP、VBAP 或 hybrid pseudo-object renderer。
- 不允许根据听感反馈自动改写核心 preset 代码。

pseudo-object scene/export/DBAP/VBAP/hybrid renderer 工作已经拆分到：
`https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer`。
详见 [docs/BRANCH_STRATEGY.md](docs/BRANCH_STRATEGY.md)。

---

## Install / 安装

```bash
python -m pip install numpy librosa soundfile scipy
```

---

## Quick Start / 快速开始

### English

Generate test audio and render a fixed 4.0 output:

```bash
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

`generate_test_audio.py` writes `input_audio/test_input.wav`, so the command above runs without moving files by hand.

### 中文

生成测试音频并渲染固定 4.0 输出：

```bash
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

`generate_test_audio.py` 会写出 `input_audio/test_input.wav`，因此无需手动移动文件即可运行上面的命令。

---

## Common Commands / 常用命令

Render a 4.0 WAV / 渲染 4.0 WAV：

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

Render a binaural headphone preview / 渲染 binaural 耳机预览：

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode binaural
```

Render both 4.0 and binaural outputs / 同时渲染 4.0 与 binaural：

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode both
```

Analyze only and write diagnostics / 只分析并写出 diagnostics：

```bash
python run_spatializer.py input_audio/test_input.wav --diagnostics-only
```

Write a quality report for the run manifest / 为当前 manifest 写出 quality report：

```bash
python run_spatializer.py input_audio/test_input.wav --write-quality-report
```

Run batch spatial diagnostics / 批量空间化诊断：

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
```

---

## Feedback Loop Commands / 反馈闭环命令

### English

The feedback path is designed for a spatial mixing workflow:

```text
batch render -> subjective score -> evaluation record -> suggested tuning profile -> next render
```

It writes external JSON artifacts only. It does not rewrite `presets.py` or replace the stable `run_spatializer.py` entrypoint.

Render through the feedback wrapper, apply an external tuning profile, and write an evaluation record from a subjective listening score:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_example.json \
  --subjective-score examples/subjective_score_example.json \
  --write-evaluation-record
```

Suggest the next reviewable tuning profile from one or more evaluation records:

```bash
python suggest_tuning_profile.py outputs \
  --profile-id quad_4p0_feedback_round_001 \
  --out profiles/quad_4p0_feedback_round_001.json
```

Use the suggested profile for the next render:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_round_001.json
```

### 中文

反馈闭环路径面向空间混音师工作流：

```text
批量渲染 -> 主观打分 -> evaluation record -> suggested tuning profile -> 下一轮渲染
```

该路径只写出外部 JSON 产物。它不会改写 `presets.py`，也不会替换稳定入口 `run_spatializer.py`。

通过 feedback wrapper 渲染，应用外部 tuning profile，并根据主观听感评分写出 evaluation record：

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_example.json \
  --subjective-score examples/subjective_score_example.json \
  --write-evaluation-record
```

从一个或多个 evaluation records 生成下一轮可审查 tuning profile 建议：

```bash
python suggest_tuning_profile.py outputs \
  --profile-id quad_4p0_feedback_round_001 \
  --out profiles/quad_4p0_feedback_round_001.json
```

使用建议 profile 进行下一轮渲染：

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_round_001.json
```

---

## Feedback Data Model / 反馈数据模型

### English

A subjective score JSON should identify the render it evaluates and provide 1-5 listening scores. `overall_preference` is required.

Typical score dimensions include:

```text
envelopment, front_focus, vocal_clarity, bass_weight, bass_tightness,
rear_naturalness, harshness, mud, depth, width, mono_safety,
overall_preference
```

Useful issue tags include:

```text
rear_too_weak, rear_too_loud, vocal_blurry, vocal_too_far,
harsh_rear, muddy_low_mid, bass_weak, bass_boomy, too_narrow,
too_wide, good_balance
```

### 中文

主观评分 JSON 应该标明它评价的是哪一次 render，并提供 1-5 分的听感评分。其中 `overall_preference` 为必填字段。

典型评分维度包括：

```text
envelopment, front_focus, vocal_clarity, bass_weight, bass_tightness,
rear_naturalness, harshness, mud, depth, width, mono_safety,
overall_preference
```

常用问题标签包括：

```text
rear_too_weak, rear_too_loud, vocal_blurry, vocal_too_far,
harsh_rear, muddy_low_mid, bass_weak, bass_boomy, too_narrow,
too_wide, good_balance
```

---

## CLI / 命令行参数

### Stable renderer arguments / 稳定渲染入口参数

- `input_file`: optional input audio file. If omitted, the folder mode in `config_center.py` is used. / 可选输入音频文件；若省略，则使用 `config_center.py` 中的文件夹模式。
- `--out-dir`: output directory. / 输出目录。
- `--preset-mode`: `manual`, `auto_select`, or `auto_acoustic`. / preset 工作模式。
- `--preset`: manual preset name when `--preset-mode manual` is used. / 手动 preset 名称。
- `--output-mode`: `4ch`, `binaural`, or `both`. / 输出模式。
- `--analysis-seconds`: duration used for analysis. / 分析用时长。
- `--target-sr`: processing sample rate. / 处理采样率。
- `--auto-acoustic-rear-enhancement`: enable the safe rear enhancement plan. / 启用安全后场增强计划。
- `--export-binaural-front-pair`: export a front-pair binaural preview. / 导出前方声道对 binaural 预览。
- `--export-binaural-rear-pair`: export a rear-pair binaural preview. / 导出后方声道对 binaural 预览。
- `--export-binaural-ctc-4ch`: export crosstalk-cancelled 4ch speaker feeds from the binaural target. / 从 binaural 目标导出 CTC 4ch speaker feeds。
- `--diagnostics-only`: write diagnostics without exporting WAV files. / 只写 diagnostics，不导出 WAV。
- `--write-quality-report`: write `quality_report.md` for the current manifest. / 为当前 manifest 写出 `quality_report.md`。
- `--no-spatial-safety`: disable rear-channel safety guards while still reporting quality metrics. / 关闭后场安全保护，但仍报告 quality metrics。

### Feedback wrapper arguments / 反馈入口参数

- `--tuning-profile`: external JSON profile applied after preset resolution. / preset 解析后应用的外部 JSON tuning profile。
- `--subjective-score`: one subjective score JSON for the current render. / 当前 render 对应的一份主观评分 JSON。
- `--subjective-score-dir`: directory of per-song score JSON files. / 每首歌评分 JSON 所在目录。
- `--write-evaluation-record`: force evaluation record output. / 强制写出 evaluation record。

---

## Main Files / 主要文件

- `run_spatializer.py`: main single-file and folder-processing entrypoint. / 单文件与文件夹处理主入口。
- `run_feedback_spatializer.py`: feedback-aware wrapper around the stable path. / 稳定路径外层的反馈闭环 wrapper。
- `suggest_tuning_profile.py`: CLI for suggesting the next tuning profile. / 生成下一轮 tuning profile 建议的 CLI。
- `tuning_profile.py`: external tuning profile validation and application. / 外部 tuning profile 校验与应用。
- `subjective_feedback.py`: subjective score validation and evaluation records. / 主观评分校验与 evaluation record 生成。
- `feedback_profile_suggester.py`: deterministic feedback-to-profile rules. / 从反馈生成 profile 建议的确定性规则。
- `batch_spatial_diagnostics.py`: batch quality diagnostics and reports. / 批量质量诊断与报告。
- `config_center.py`: folder mode, output mode, preset, binaural, CTC, and safety defaults. / 文件夹模式、输出模式、preset、binaural、CTC 与 safety 默认配置。
- `audio_io.py`: input discovery, loading, and audio export helpers. / 输入发现、加载与音频导出工具。
- `streaming_analyzer.py`: stereo and spectral analysis. / stereo 与频谱分析。
- `layer_extractor.py`: DSP spatial-function layer extraction. / DSP 空间功能层提取。
- `layer_router.py`: preset routing application. / preset 路由应用。
- `renderer_4ch.py`: fixed `[LF, RF, LB, RB]` renderer. / 固定 `[LF, RF, LB, RB]` 渲染器。
- `binaural_renderer.py`: 4.0 virtual-speaker binaural and CTC utilities. / 4.0 virtual speaker binaural 与 CTC 工具。
- `spatial_safety.py`: rear-channel safety and quality metrics. / 后场安全保护与质量指标。
- `spatial_quality_report.py`: Markdown quality report generation. / Markdown 质量报告生成。

---

## Tests / 测试

Run the focused suite / 运行重点测试：

```bash
python -m pytest -q tests/test_run_spatializer_cli.py tests/test_spatial_safety.py tests/test_batch_spatial_diagnostics.py tests/test_tuning_profile.py tests/test_subjective_feedback.py tests/test_feedback_profile_suggester.py
```

Run all tracked tests / 运行全部已跟踪测试：

```bash
python -m pytest -q
```

---

## Rollback / 回档

### English

The feedback-loop branch was created without changing `main`. A pre-change backup branch was also created:

```text
backup/main-before-feedback-loop-20260618
```

Use that branch when you need to inspect or restore the repository state before feedback-loop work.

### 中文

反馈闭环功能分支没有直接修改 `main`。本轮改动前也已经创建备份分支：

```text
backup/main-before-feedback-loop-20260618
```

如需检查或恢复反馈闭环改造前的仓库状态，可以使用该分支。
