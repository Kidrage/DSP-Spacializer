# DSP Spatializer 使用说明

这是一个**非 AI、规则/信号处理驱动**的 stereo → 4.0 spatial bed 工程。主入口是 `run_spatializer.py`，默认读取 `input_audio/` 里的音频，生成 4ch 空间化 WAV 与 diagnostics JSON 到 `outputs/`。

当前主线是 **stereo → 4.0 spatial bed**。`binaural` / `CTC` 只作为实验监听与后续硬件 handoff，不作为主线交付。本项目不包含真实扬声器测距/测向、真实 HRTF/BRIR/SOFA 测量，也不包含 AI source separation / Demucs。

## 1. 快速运行

```bash
cd "/Users/saintpeter/Desktop/Coding/spatializer_outputs/DSP空间化codec"
python run_spatializer.py
```

默认配置来自 `config_center.py`：

```python
PROCESS_MODE = "all"        # 扫描 input_audio/ 全部音频
OUTPUT_MODE = "4ch"         # 默认输出 4.0 WAV
PRESET_MODE = "auto_acoustic"
TARGET_SR = 48000
EXPORT_DIAGNOSTICS = True
```

也可以指定单个文件：

```bash
python run_spatializer.py "input_audio/Chan Chan (Live Session).mp3" --out-dir outputs --preset-mode auto_acoustic --output-mode 4ch
```

指定输出模式：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --output-mode 4ch
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --output-mode both --export-binaural-ctc-4ch
python run_spatializer.py my_song.wav --out-dir outputs --no-spatial-safety
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
```

## 2. 输入与输出目录

### 输入

默认输入目录：

```text
input_audio/
```

支持常见音频格式，主要由 `audio_io.py` 处理，包括：

```text
.wav .flac .mp3 .m4a .ogg .aiff .aif
```

如果不传 CLI 参数，脚本会根据 `config_center.PROCESS_MODE` 决定处理范围：

| 配置 | 行为 |
|---|---|
| `PROCESS_MODE = "all"` | 扫描 `input_audio/` 中所有支持音频 |
| `PROCESS_MODE = "single"` | 只处理 `SINGLE_INPUT_FILENAME` 指定的文件 |

### 输出

默认输出目录：

```text
outputs/
```

每首歌的输出文件名格式：

```text
<安全化后的歌曲名>_<preset名>_<产物类型>.wav/json
```

例如：

```text
outputs/Chan_Chan_Live_Session_auto_acoustic_4ch.wav
outputs/Chan_Chan_Live_Session_auto_acoustic_diagnostics.json
outputs/batch_manifest.json
```

## 3. 产物生成逻辑

`run_spatializer.py` 的输出由 `OUTPUT_MODE` 与若干 export 开关共同决定。CLI 使用 `--out-dir` 指定目录；当前不使用 `--out`、`--export-preview` 或 `--export-diagnostics`。diagnostics 默认由 `config_center.EXPORT_DIAGNOSTICS` 控制，`--diagnostics-only` 会强制写 diagnostics 且不导出 WAV。

### `OUTPUT_MODE = "4ch"`

生成：

```text
*_4ch.wav
*_diagnostics.json
batch_manifest.json
```

`*_4ch.wav` 是 4 声道 WAV，声道顺序为：

```text
LF, RF, LB, RB
左前, 右前, 左后, 右后
```

这是主产物，适合 4.0 扬声器系统、DAW 或支持多声道播放的软件。

### `OUTPUT_MODE = "binaural"`

生成耳机监听版本：

```text
*_binaural_4p0.wav
*_diagnostics.json
batch_manifest.json
```

`*_binaural_4p0.wav` 是把 4.0 虚拟扬声器通过程序化 HRTF/ITD/ILD 渲染到双耳立体声，适合耳机试听空间效果。

如果 `EXPORT_BINAURAL_ROOM_RIR = True` 且输出模式包含 binaural，还会额外生成：

```text
*_binaural_4p0_room_rir.wav
```

这是在 binaural 后叠加一个合成小房间 RIR，用于增强耳机外化感。

### `OUTPUT_MODE = "both"`

同时生成 4ch 与 binaural：

```text
*_4ch.wav
*_binaural_4p0.wav
*_binaural_4p0_room_rir.wav   # 如果 room RIR 开启
*_diagnostics.json
batch_manifest.json
```

### 可选产物

以下开关在 `config_center.py` 或 CLI 中控制：

| 开关 | 产物 | 用途 |
|---|---|---|
| `EXPORT_BINAURAL_FRONT_PAIR` | `*_binaural_front_pair.wav` | 只监听前场虚拟扬声器 |
| `EXPORT_BINAURAL_REAR_PAIR` | `*_binaural_rear_pair.wav` | 只监听后场虚拟扬声器 |
| `EXPORT_BINAURAL_CROSSTALK_CANCELLED_4CH` | `*_binaural_ctc_4ch.wav` | 将 binaural 目标反解到 4ch 扬声器阵列 |
| `EXPORT_DIAGNOSTICS` | `*_diagnostics.json` | 每首歌的分析、路由、安全、质量指标 |
| `--diagnostics-only` | `*_diagnostics.json` | 只跑分析与 diagnostics，不导出 WAV |
| `--write-quality-report` | `quality_report.md` | 为当前 manifest 写简易质量报告 |

## 4. 主处理流水线

每首歌会经过以下闭环流程：

```text
load_audio
  → analyze_audio
  → resolve_preset
  → extract_layers
  → route_apply_preset
  → render_4ch
  → apply_spatial_safety
  → classify_quality_risks / compare_quality_metrics
  → match_energy
  → apply_limiter
  → export_audio
  → save_diagnostics
```

对应模块：

| 阶段 | 文件 | 说明 |
|---|---|---|
| 音频读取/导出 | `audio_io.py` | 读取音频、重采样、导出 WAV |
| 分析 | `streaming_analyzer.py` | 计算中心占比、瞬态密度、频带能量等 |
| 预设解析 | `presets.py` | manual / auto_select / auto_acoustic |
| 分层 | `layer_extractor.py` | 从 stereo 构造空间功能层 |
| 路由 | `layer_router.py` | 根据 preset 和 analysis 决定各层到前后声道的权重 |
| 4ch 渲染 | `renderer_4ch.py` | 生成 LF/RF/LB/RB 四声道 |
| 空间安全 | `spatial_safety.py` | 后声道人声泄漏、浑浊、刺耳、反相风险保护 |
| 质量阈值 | `spatial_quality_thresholds.json` | global 与 preset-specific 风险阈值 |
| 批量诊断 | `batch_spatial_diagnostics.py` | 批量生成 metrics CSV、summary JSON、Markdown report |
| 质量报告 | `spatial_quality_report.py` | 从 batch metrics/manifest 生成 Markdown 报告 |
| 能量匹配 | `energy_manager.py` | 控制输出响度不要异常偏离输入 |
| 限幅 | `limiter.py` | 防止 clipping |
| 双耳渲染 | `binaural_renderer.py` | 4.0 虚拟扬声器 → 耳机 binaural |
| 诊断 | `diagnostics.py` | 输出 JSON 报告 |

## 5. 算法机制说明

### 5.1 不是 AI 分轨

本项目不做 AI source separation。所谓 layer 不是干净的人声/鼓/贝斯 stem，而是**空间功能 bus**：

- `bass`：低频主体，保护低频稳定性
- `front_core`：中置/中心相关内容，通常更靠前
- `side_width`：左右差异内容，用于宽度与侧向感
- `rear_ambience`：低相关/扩散成分，送到后方形成包围感
- `high_air`：高频空气感，用于空间亮度

### 5.2 Stereo → M/S 与频带拆分

核心思想是从 stereo 中提取：

```text
Mid  = L + R
Side = L - R
```

再结合 `band_split()` 做多频段拆分，例如 bass / low_mid / mid / high_mid / air。不同频段承担不同空间职责：低频更稳，中高频更容易制造宽度和空气感。

### 5.3 auto_acoustic 预设

默认 `PRESET_MODE = "auto_acoustic"`。它会根据 `analyze_audio()` 的结果为当前歌曲动态生成空间参数，而不是固定套一个 preset。

典型分析维度包括：

- 中置主导程度
- stereo 宽度/side 能量
- 频带能量分布
- 瞬态密度
- 可能的人声/中心内容风险

如果 `AUTO_ACOUSTIC_REAR_ENHANCEMENT = True`，会在安全范围内增强后方空间显著性。

### 5.4 4.0 渲染

`renderer_4ch.py` 将各层按 routing 权重合成为：

```text
LF = left front
RF = right front
LB = left back
RB = right back
```

前方优先保证主体、低频和中心稳定；后方主要承载 ambience、side width、air 等非主体成分。

### 5.5 Spatial Safety 安全网

`spatial_safety.py` 位于 4ch 渲染之后、最终 mastering 之前。它只对后声道做保守衰减，不提升、不改前声道。

检测指标包括：

- `rear_vocal_leakage_score`：后声道人声/中置泄漏风险
- `low_mid_mud_score`：后方低中频浑浊
- `transient_smear_score`：后方瞬态涂抹
- `high_harshness_score`：后方高频刺耳
- `phase_correlation_risk`：反相/mono fold-down 风险
- `spatial_excess_score`：整体空间过量风险

如果风险过高，会衰减后声道对应频段：

```text
rear low_mid / mid / high_mid / air
```

这样能避免人声飘到后方、低频糊、高频刺、mono 下混异常等问题。

### 5.6 Energy Match 与 Limiter

空间化后可能改变响度和峰值，因此最后会：

1. `match_energy()`：让输出能量与输入保持合理一致；
2. `apply_limiter()`：限制峰值，防止导出的 WAV 爆音。

### 5.7 Binaural / Room RIR / CTC

当输出 binaural 时，`binaural_renderer.py` 会模拟虚拟 4.0 扬声器到双耳的传输：

- ITD：左右耳时间差
- ILD：左右耳响度差
- 简化频率响应/HRTF
- 前后扬声器角度：`BINAURAL_FRONT_AZIMUTH_DEG` / `BINAURAL_REAR_AZIMUTH_DEG`

如果开启 room RIR，会在 binaural 后卷积一个小房间响应，使耳机声音更外化。

CTC 输出则是把 binaural 目标反解成 4ch 扬声器播放信号，仅适合实验监听与后续硬件 handoff。它不是本轮主线，也不代表真实扬声器测距、测向或真实 BRIR/HRTF 校准。

## 6. 诊断文件怎么看

每首歌的 `*_diagnostics.json` 包含：

- `analysis`：输入音频分析结果
- `preset_mode_used`：实际使用的 preset 模式
- `auto_acoustic_info`：自动声学参数生成信息
- `routing`：各层到各声道的路由权重
- `spatial_safety.before` / `after`：安全模块修正前后指标
- `spatial_safety.actions`：实际做了哪些后声道 gain 衰减
- `quality_metrics`：最终 4ch 质量指标
- `quality_risk.before` / `quality_risk.after`：阈值分类结果，包含 `overall_status`、`overall_risk_score` 和逐项 `risks`
- `quality_delta`：各指标 after - before 的 delta
- `over_protection`：检测 safety 是否过度压缩后方空间感
- `output_paths`：本首歌生成了哪些文件
- `rear_to_front_rms_ratio` / `rear_to_front_db`：后场相对前场能量
- `peak`：最终峰值

## 7. 常用命令

批量处理 `input_audio/`：

```bash
python run_spatializer.py
```

单文件 4ch：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --output-mode 4ch
```

单文件耳机监听：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --output-mode binaural
```

同时输出 4ch 和 binaural：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --output-mode both --export-binaural-ctc-4ch
```

关闭空间安全保护，仅保留指标报告：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --no-spatial-safety
```

手动 preset：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode manual --preset wide_smooth
```


批量 diagnostics / 阈值评估：

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic --output-mode 4ch --quality-thresholds spatial_quality_thresholds.json
```

只写 diagnostics，不导出 WAV：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --preset-mode auto_acoustic --diagnostics-only
```

为当前 run_spatializer manifest 生成质量报告：

```bash
python run_spatializer.py my_song.wav --out-dir outputs --write-quality-report
```

`batch_spatial_diagnostics.py` 会输出：

```text
outputs/batch_eval/batch_metrics.csv
outputs/batch_eval/batch_summary.json
outputs/batch_eval/batch_report.md
outputs/batch_eval/*_diagnostics.json
```

## 8. 调参入口

| 目标 | 修改位置 |
|---|---|
| 改默认输入/输出目录 | `config_center.py` |
| 改默认输出类型 | `config_center.py -> OUTPUT_MODE` |
| 改自动/手动 preset | `config_center.py -> PRESET_MODE` |
| 调 preset 参数 | `presets.py` |
| 调层路由逻辑 | `layer_router.py` |
| 调 4ch 声像/延迟/频带 | `renderer_4ch.py` |
| 调质量阈值 | `spatial_quality_thresholds.json` |
| 调 safety 算法 | `spatial_safety.py` |
| 调 binaural 虚拟扬声器 | `binaural_renderer.py` / `config_center.py` |

## 9. 注意事项

- 4ch WAV 不是普通 stereo 文件；普通播放器可能只播放前两个声道或下混。
- binaural WAV 是普通 stereo，适合耳机试听。
- 该系统不等同 Dolby Atmos，也不生成对象音频 metadata。
- 该系统不做 AI 分离，因此后方声场是空间功能重分配，不是干净 stem。
- 该系统不做真实扬声器测距/测向，也不做真实 BRIR/HRTF 测量；binaural/CTC 是实验监听与 handoff。
- 如果 GitHub 推送失败且提示文件超过 100MB，通常是 notebook 或音频产物过大，应避免提交大音频/大 notebook，必要时使用 Git LFS。
