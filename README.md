# Streaming Stereo Spatializer / DSP Spatializer 使用说明（Pseudo-Object 分支）

> **Branch notice / 分支说明 — `Pseudo-Object` experimental branch**
>
> **EN:** This README describes the `Pseudo-Object` branch, not the repository
> `main` branch.  `main` is the legacy fixed 4.0 channel-renderer line.  This
> branch keeps that legacy path working, and adds pseudo-object scene metadata,
> pseudo-object layer audio export, and modular pseudo-object decoders for
> layout-driven experiments.
>
> **中文：** 本 README 描述的是 `Pseudo-Object` 分支，不是仓库的 `main` 分支。
> `main` 应视为 legacy fixed 4.0 channel renderer 主线；本分支在保留 legacy
> 4ch / binaural / both 输出能力的基础上，新增 pseudo-object scene metadata、
> pseudo-object layer audio 导出，以及面向 speaker layout 的模块化 decoder。
>
> **Important / 重要：** Pseudo objects are **spatial-function objects** derived
> from DSP layers.  They are not clean stems, not source-separated instruments,
> and not claims of real object audio.
>
> **重要：** pseudo object 是由 DSP 空间功能层派生的 **spatial-function object**。
> 它不是 clean stem，不是 AI 分离出来的乐器/人声 stem，也不代表真实物体音频。

## Main vs Pseudo-Object / `main` 与 `Pseudo-Object` 分支对照

| Area / 项目 | `main` branch / 主分支 | `Pseudo-Object` branch / 本分支 |
| --- | --- | --- |
| Primary path / 主链路 | Stereo → DSP layers → fixed `renderer_4ch.py` | Same legacy path, plus pseudo-object scene path / 保留 legacy 链路，并新增 pseudo-object scene 链路 |
| Metadata / 元数据 | Diagnostics-focused JSON / 以 diagnostics JSON 为主 | Adds `pseudo_object_spatial_v1` scene metadata / 新增 pseudo-object scene metadata |
| Object audio / 对象音频 | Not exported as object layers / 不导出 object layer audio | Exports DSP layer material under `*_objects/` / 导出 DSP layer material，不是 clean stem |
| Decoding / 解码 | Fixed 4.0 renderer / 固定四声道渲染 | DBAP fallback, 2D VBAP, hybrid spread-VBAP / 支持 DBAP、2D VBAP、hybrid renderer |
| CLI additions / CLI 增量 | Legacy output options / legacy 输出参数 | Adds `--export-pseudo-scene`, `--decode-pseudo-scene`, `--pseudo-scene-only`, `--pseudo-renderer` |
| Intended use / 用途 | Stable 4.0 / binaural upmix / 稳定固定通道 upmix | Experimental pseudo-object architecture and decoder research / pseudo-object 架构与 decoder 实验 |

**EN:** If you want the original stable fixed-channel behavior, use `main` or
run this branch without pseudo-object flags.  If you want pseudo-object scene
export, layout-driven decoding, or VBAP renderer experiments, use this
`Pseudo-Object` branch.

**中文：** 如果你只需要原来的稳定 fixed-channel 4.0 / binaural 行为，请使用 `main`，
或者在本分支不加 pseudo-object 相关参数运行。若需要导出 pseudo-object scene、
尝试 layout-driven decoder 或 VBAP / hybrid renderer，请使用 `Pseudo-Object` 分支。

## 中文快速说明 / Chinese Quick Reference

本分支不是把 stereo 分成真实乐器对象，而是把现有 DSP layer（例如 `bass`、
`front_core`、`side_width`、`rear_ambience`、`high_air`、`low_body_support`）描述
成可解释的 spatial-function pseudo objects。scene JSON 可以交给不同 decoder 使用；
当前默认支持 `default_quad_4p0`，并提供三种 pseudo renderer：

- `dbap_quad_v1`：距离型 DBAP-like fallback，声音分布较平滑。
- `vbap_2d_v1`：水平 2D VBAP，定位更 sharp，适合 point-like pseudo objects。
- `hybrid_vbap_v1`：推荐模式，根据 object type / spread / diffuseness 选择 VBAP、
  spread VBAP 或 stereo bed 特判。

常用命令：

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

典型 pseudo-object 输出：

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

本项目是一个非 AI、规则/信号处理驱动的 stereo → 4.0 / pseudo-object spatializer。
legacy 路径仍然输出固定 `[LF, RF, LB, RB]` 四声道；`Pseudo-Object` 分支额外导出
scene metadata 和 object layer material，以便后续使用不同 speaker layout decoder。

This project implements a **non-AI streaming stereo spatializer** for a 4.0 speaker system. It converts stereo L/R audio into DSP spatial-function layers that are rendered to logical 4.0 output (left front, right front, left back, right back).

This is **not** AI-based source separation. The spatial layers are not clean stems but rather spatial-function buses used for rendering.

## Key Features / 主要特性

- Converts stereo L/R audio to 4.0 spatial output
- DSP spatial-function layers:
  - Bass Layer (low-frequency body)
  - Low Body Support (warmth/body support)
  - Front Core (center-correlated content)
  - Side Width (stereo difference)
  - Rear Ambience (diffuse, low-coherence)
  - High Air (high-frequency content)
- Multiple presets for different spatialization styles
- Energy matching to maintain consistent loudness
- Limiter to prevent clipping
- Diagnostic output for analysis
- Optional pseudo-object scene export and default quad 4.0 decoder


## Batch Spatial Diagnostics Sync / 批量空间诊断同步

This `Pseudo-Object` branch also includes the Gitea-side batch diagnostics work merged from `feat: add batch spatial diagnostics`.  These tools are compatible with the legacy 4.0 path and with pseudo-object experiments:

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
python run_spatializer.py my_song.wav --out-dir outputs --diagnostics-only
python run_spatializer.py my_song.wav --out-dir outputs --write-quality-report
```

Related files:

- `batch_spatial_diagnostics.py`: batch metrics/summary/report generation.
- `spatial_quality_report.py`: Markdown quality report writer.
- `spatial_quality_thresholds.json`: global and preset-specific quality thresholds.

These diagnostics describe spatial safety and render quality; they do not change the definition of pseudo objects.  Pseudo objects remain DSP-derived spatial-function objects, not clean source-separated stems.

## Pseudo-Object Upmix Mode / Pseudo-Object Upmix 模式

DSP-Spacializer now has two compatible rendering paths:

1. **Legacy fixed 4.0 mode** — the original deterministic channel renderer in
   `renderer_4ch.py`.  It directly maps DSP spatial-function layers to
   `[LF, RF, LB, RB]` and remains the default behavior for `4ch`, `binaural`,
   and `both` output modes.
2. **Pseudo-object scene mode** — an additional metadata path that turns the
   same DSP layers into a `pseudo_object_spatial_v1` scene.  These pseudo
   objects are **spatial-function objects**, not real instrument objects and not
   source-separated clean stems.  Object audio files are layer material for a
   decoder, not final speaker feeds.

The first pseudo-object version emits six objects:

- `bass_anchor`
- `front_core`
- `side_width`
- `rear_ambience`
- `high_air`
- `low_body_support`

The scene stores coordinates, spread/depth/diffuseness, gain, constraints, and
decoder hints.  Current renderers target `default_quad_4p0`; future decoders can
reuse the same metadata for other horizontal speaker layouts.

Example output when pseudo-object export is enabled:

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

CLI examples:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --export-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode both --export-pseudo-scene --decode-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --pseudo-scene-only
```

## Pseudo-Object Rendering Algorithms / 渲染算法

Pseudo-object decoding is now routed through modular renderers under
`renderers/`.  These renderers consume scene metadata and speaker layout data;
they do not treat pseudo objects as clean stems or real isolated instruments.

- `dbap_quad_v1`: the first pseudo-object decoder, kept as a fallback.  It uses
  distance-based amplitude panning, so it is smooth and forgiving for diffuse
  layer material.
- `vbap_2d_v1`: horizontal 2D VBAP.  It chooses the adjacent speaker pair that
  encloses the object azimuth and equal-power normalizes the active pair.  This
  is sharper and more layout-driven, so it is better for point-like pseudo
  objects.
- `hybrid_vbap_v1`: recommended V2 mode.  It keeps `front_core` as a stereo bed,
  uses VBAP for sharper objects such as `bass_anchor`, and uses spread VBAP for
  diffuse/lateral beds such as `side_width`, `rear_ambience`, and `high_air`.

VBAP is layout-driven decoding: it calculates speaker gains from object
azimuths and speaker azimuths instead of hard-coding fixed 4-channel routing
amounts.  V2 supports horizontal 2D layouts and the default quad 4.0 layout;
future versions can extend the same renderer interface to other planar arrays.

Renderer selection example:

```bash
python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --export-pseudo-scene \
  --decode-pseudo-scene \
  --pseudo-renderer hybrid_vbap_v1
```

Decoded file names include the renderer family, for example:

```text
*_pseudo_quad_dbap_4ch.wav
*_pseudo_quad_vbap_4ch.wav
*_pseudo_quad_hybrid_4ch.wav
```

Diagnostics include `pseudo_object_scene` when scene export is enabled and
`pseudo_decode` when the scene is decoded.  The legacy field
`mono_fold_down_delta_db` is preserved, but it means the legacy average-4 fold
down `(LF+RF+LB+RB)/4`.  New fields clarify the basis:

- `mono_fold_down_delta_db_avg4_legacy`
- `mono_fold_down_delta_db_front_norm`
- `mono_front_only_delta_db`

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install numpy librosa soundfile scipy
```

## Usage

To run with the generated test audio:
```bash
python generate_test_audio.py  # Creates input_audio/test_input.wav
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

For your own audio files:
```bash
python run_spatializer.py input.wav --preset-mode auto_acoustic --output-mode both
```

### Arguments
- `input.wav`: Path to input stereo WAV file
- `--out-dir`: Output directory
- `--preset-mode`: `manual`, `auto_select`, or `auto_acoustic`
- `--output-mode`: `4ch`, `binaural`, or `both`
- `--preset`: Manual preset name when `--preset-mode manual` is used
- `--analysis-seconds`: Duration of analysis (default: 2.0)
- `--export-pseudo-scene`: Export pseudo-object JSON and object layer audio
- `--decode-pseudo-scene`: Decode pseudo-object scene to renderer-tagged quad WAV
- `--pseudo-renderer`: Select `dbap_quad_v1`, `vbap_2d_v1`, or `hybrid_vbap_v1`
- `--pseudo-scene-only`: Export only pseudo-object scene/audio, skipping legacy file exports
- `--no-diagnostics`: Disable JSON diagnostics export

## Presets

- **natural**: Balanced default mode
- **wide**: More obvious spatial effect
- **vocal_safe**: For vocal-heavy music
- **live**: For live/acoustic recordings
- **club**: For electronic/bass-heavy music
- **bypass**: No spatialization
- **ms_baseline**: Simple M/S baseline for comparison

## Listening to 4-Channel Audio

Most consumer audio equipment is stereo. To listen to the 4-channel output:

1. Use a surround sound system with 4 speakers
2. Use headphones with a virtual surround sound processor
3. Use audio software that supports 4-channel playback

## Tuning Presets

To tune presets:
1. Modify the routing parameters in `presets.py`
2. Adjust the layer routing logic in `layer_router.py`
3. Experiment with different decorrelation settings in `decorrelator.py`
4. Use the diagnostic output to understand the impact of changes

## File Structure

```
streaming_stereo_spatializer/
│
├── run_spatializer.py        # Main script
├── audio_io.py               # Audio loading and export
├── streaming_analyzer.py     # Audio analysis
├── layer_extractor.py        # Layer extraction
├── layer_router.py           # Layer routing
├── decorrelator.py           # Rear ambience decorrelation
├── renderer_4ch.py           # 4-channel rendering
├── energy_manager.py         # Loudness matching
├── limiter.py                # Clipping prevention
├── diagnostics.py            # Diagnostic output
├── batch_spatial_diagnostics.py
│                              # Batch spatial metrics and summaries
├── spatial_quality_report.py   # Markdown quality report writer
├── spatial_quality_thresholds.json
│                              # Quality risk thresholds
├── pseudo_object_schema.py    # Pseudo-object metadata schema validation
├── pseudo_object_scene.py     # Pseudo-object scene builder
├── object_audio_export.py     # Object layer audio export helpers
├── speaker_layout.py          # Speaker layout descriptors
├── object_decoder.py          # Pseudo-object renderer dispatch layer
├── renderers/                 # DBAP, 2D VBAP and hybrid renderer modules
├── scripts/check_text_integrity.py
│                              # LF newline and line integrity check
├── scene_diagnostics.py       # Scene summary diagnostics
├── presets.py                # Spatialization presets
├── generate_test_audio.py    # Test tone generation
├── tests/                    # Pytest regression tests
├── README.md                 # This file
```

## Implementation Notes

- The system is designed to resemble a streaming PCM processor
- It uses a rule-based approach rather than AI
- The architecture prioritizes stable front image and bass protection
- Rear ambience is designed to feel wide without obvious echoes
- Energy management prevents output from becoming louder than input

## Limitations

- This is a simulation, not real hardware
- It doesn't handle physical speaker calibration
- The presets need to be tuned based on listening experience
- It doesn't implement advanced features like Dolby Atmos metadata
- It's not designed for network streaming or hardware distribution

## Why Not AI?

This project is explicitly not AI-based. It uses simple signal processing techniques to extract spatial characteristics from stereo audio. The spatial layers are not clean stems but rather spatial-function buses used for rendering to a 4.0 speaker system.

## Next Steps

To evaluate the system:

1. Compare original stereo vs bypass vs ms_baseline vs natural vs wide
2. Test with different music genres
3. Adjust presets based on listening experience
4. Add visualization of spatial characteristics
5. Implement more advanced decorrelation techniques