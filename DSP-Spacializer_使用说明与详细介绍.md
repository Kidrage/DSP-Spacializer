# DSP-Spacializer 使用说明与详细介绍

> 日期：2026-06-12  
> 仓库：`Kidrage/DSP-Spacializer`  
> 定位：非 AI 的 streaming stereo → 4.0 DSP 空间化原型

---

## 1. 项目定位

`DSP-Spacializer` 是一个面向 **4.0 扬声器系统** 的非 AI 流式立体声空间化处理器。它的目标是把普通 stereo L/R 音频转换为四声道逻辑输出：

```text
LF = Left Front   左前
RF = Right Front  右前
LB = Left Back    左后
RB = Right Back   右后
```

该项目不是 AI stem separation，不试图把歌曲分离成“人声、鼓、贝斯、吉他”等干净音轨；它做的是 **spatial-function buses**：从 stereo 中提取对空间渲染有意义的频段、差分、氛围、空气感和低频体积，再通过 preset 路由到 4.0。

典型链路：

```text
Stereo L/R
↓
频段拆分 + Mid/Side 分析
↓
空间功能层提取
↓
preset 参数路由
↓
4.0 Renderer
↓
Energy Manager / Limiter
↓
LF / RF / LB / RB
```

---

## 2. 核心空间层

| 层 | 含义 | 主要用途 |
|---|---|---|
| Bass Layer | 低频主体、低频能量 | 保持 bass 稳定，必要时少量四点共享 |
| Front Core | 中心相关内容，人声、主旋律、鼓/bass body | 维持前方主声像与歌曲主体 |
| Side Width | L/R 差分、左右宽度信息 | 增强侧向与后方包围 |
| Rear Ambience | 低相干、diffuse、混响尾巴 | 送到后方形成空间空气 |
| High Air | 高频空气感、镲片、泛音、reverb brightness | 控制空间边缘和外化亮度 |
| Low Body | 约 120–500 Hz 的身体感与厚度 | 让后方不只靠高频，有中低频包围 |

这些层不是干净 stem，而是空间渲染素材。这个设计使它适合 streaming stereo：只要求输入已经解码成 stereo PCM，不依赖平台协议、DRM 或云端 AI 分离。

---

## 3. 仓库结构

```text
DSP-Spacializer/
│
├── run_spatializer.py        # 主入口：批量/单曲处理
├── config_center.py          # 全局配置中心
├── audio_io.py               # 音频加载与导出
├── streaming_analyzer.py     # stereo 声学结构分析
├── layer_extractor.py        # 空间功能层提取
├── presets.py                # preset 参数库与选择逻辑
├── layer_router.py           # 将 preset 转换为最终 routing 参数
├── decorrelator.py           # 后方去相关处理
├── renderer_4ch.py           # 4.0 渲染器
├── energy_manager.py         # 能量匹配，防止输出响度失控
├── limiter.py                # 峰值限制，防 clipping
├── diagnostics.py            # 输出诊断 JSON
├── binaural_renderer.py      # binaural/headphone preview
├── generate_test_audio.py    # 测试音频生成
├── input_audio/              # 默认批量输入目录
└── streaming_stereo_spatializer_clean_workflow.ipynb
```

---

## 4. 环境安装

建议 Python 3.10+。

```bash
git clone https://github.com/Kidrage/DSP-Spacializer.git
cd DSP-Spacializer

python -m venv .venv
source .venv/bin/activate

pip install numpy scipy soundfile librosa
```

如果要读取 MP3，建议安装 ffmpeg：

```bash
brew install ffmpeg
```

---

## 5. 快速开始

### 5.1 单曲渲染为 4.0 WAV

```bash
python run_spatializer.py "input_audio/song.wav" \
  --preset-mode manual \
  --preset general_pop_wide \
  --output-mode 4ch
```

输出通常会写入：

```text
spatializer_outputs_clean/
```

常见输出：

```text
<song>_<preset>_4ch.wav
<song>_<preset>_diagnostics.json
```

### 5.2 批量处理 input_audio 目录

把音频文件放入：

```text
input_audio/
```

然后运行：

```bash
python run_spatializer.py
```

程序会批量处理目录中的音频，并生成 batch manifest。

### 5.3 同时导出 4.0 与 binaural 预览

```bash
python run_spatializer.py "input_audio/song.wav" \
  --preset-mode manual \
  --preset wide_smooth \
  --output-mode both
```

binaural preview 适合耳机快速检查空间趋势，但不应替代实体 4.0 音箱实听。

---

## 6. Preset 工作流

现阶段正式调试建议以 **manual preset** 为主：

```bash
python run_spatializer.py "input_audio/song.wav" \
  --preset-mode manual \
  --preset vocal_focus_wide \
  --output-mode 4ch
```

可用 preset：

```text
general_pop_wide
wide_smooth
vocal_focus_wide
vocal_room_body_clear
bass_dry_wide
epic_orchestral_depth
vintage_jazz_room
bypass
ms_baseline
```

兼容旧名：

```text
natural     -> general_pop_wide
wide        -> wide_smooth
vocal_safe  -> vocal_focus_wide
live        -> epic_orchestral_depth
club        -> bass_dry_wide
```

---

## 7. Preset 详细说明

### 7.1 `bypass`

原始前方 stereo 对照。LB/RB 基本无输出，适合做 A/B 基准。

### 7.2 `ms_baseline`

传统 Mid/Side 后方映射对照。后方轮廓直接，但不够音乐化，主要用于确认 4ch 输出链路是否工作。

### 7.3 `general_pop_wide`

通用流行歌宽声场模式。目标是比普通 stereo 更宽，后方有存在感，但不明显破坏人声中心。适合作为安全默认项。

### 7.4 `wide_smooth`

最明显的空间感与包围感 A/B preset。

调试过程：早期 rear boost / wide 版本能明显扩大声场，但容易带来高频刺、齿音放大、reverb 被过度增强、人声变远等问题。随后通过降低后方过激 air，同时保留 side/rear/lowbody 的空间骨架，形成了 `wide_smooth`。

听感结果：空间感明显，后方音响最容易被感知，适合展示“算法确实把 stereo 推成了 4.0”；但在人声特别清晰、中心特别强、3–7 kHz presence 很突出的歌曲中，可能带来塑料感、电话感或人声距离变远。

### 7.5 `vocal_focus_wide`

人声清晰、伴奏较少时的主力 preset。它从 `wide_smooth` 中保留空间感，但降低 rear high-mid/air 与过强后方扩散，避免人声被后方拖走。

听感结果：在 folk / singer-songwriter / acoustic pop 中表现较好，人声更稳，空间仍存在；但对强 bass 电子/说唱、大混响交响、早期小声场 jazz 不够适配。

### 7.6 `vocal_room_body_clear`

强人声保护 preset。用于高相干、近 mono、强中心人声曲目，目标是消除电话感、塑料感和齿音风险。

听感结果：人声最稳、最不刺，但后方偏柔和、偏暗，空间感不强。它是“救人声”的安全模式，不是展示空间的模式。

### 7.7 `bass_dry_wide`

电子、说唱、强低频、干燥合成器音乐 preset。

调试逻辑：电子/说唱不能主要靠 reverb 做空间，而要靠 `lowbody_rear`、`side_rear`、少量 `bass_quad` 和 `rear_floor_ratio` 做 bass pressure 与干声扩展。

目标：bass 与 low-body 更有包围，synth/hi-hat 有侧后方扩展，vocal/rap 保持中心。

### 7.8 `epic_orchestral_depth`

交响、cinematic、epic、大混响音乐 preset。

调试逻辑：这类音乐本来就有 hall，继续增加 ambience 会糊。该 preset 控制 `amb_rear` 与 `decorrelation`，用适度 side 和 lowbody 保持纵深与低弦体积。

目标：减少 hall 糊，保留大厅宽度，让木管、长笛、低弦更清楚。

### 7.9 `vintage_jazz_room`

早期 jazz、小声场、窄 stereo 录音 preset。

调试逻辑：老录音 side/diffuse 很少，后方没有足够可提取素材。该 preset 提高 rear floor、lowbody 和小房间感，让录音温和打开。

局限：如果原曲几乎 mono，仍需要后续 rear perceptual fill / mono room fill，单靠 side/diffuse 提取不够。

---

## 8. 输出诊断 JSON

常见字段：

| 字段 | 含义 |
|---|---|
| `stereo_width` | 原曲 stereo 宽度 |
| `center_dominance` | 中心主体/人声强度 |
| `bass_mono_ratio` | bass 是否集中 |
| `high_diffuse_ratio` | 是否存在可用于后方的 diffuse ambience |
| `band_coherence` | 各频段 L/R 相干度 |
| `band_side_ratio` | 各频段 side 信息占比 |
| `rear_to_front_db` | 后方相对前方 RMS dB |
| `channel_rms` | LF/RF/LB/RB 各通道 RMS |
| `channel_peak` | 各通道峰值 |

注意：`rear_to_front_db` 不能单独代表空间感。有些曲目后方 RMS 不低，但如果 LB/RB 主要是暗的 lowbody 或没有中高频轮廓，主观上仍会像 stereo。

---

## 9. 推荐测试方法

每首歌建议先导出：

```bash
python run_spatializer.py song.wav --preset-mode manual --preset bypass --output-mode 4ch
python run_spatializer.py song.wav --preset-mode manual --preset ms_baseline --output-mode 4ch
python run_spatializer.py song.wav --preset-mode manual --preset general_pop_wide --output-mode 4ch
python run_spatializer.py song.wav --preset-mode manual --preset wide_smooth --output-mode 4ch
```

然后按曲风补测：

```bash
# vocal / folk
python run_spatializer.py song.wav --preset-mode manual --preset vocal_focus_wide --output-mode 4ch

# EDM / rap
python run_spatializer.py song.wav --preset-mode manual --preset bass_dry_wide --output-mode 4ch

# orchestral / cinematic
python run_spatializer.py song.wav --preset-mode manual --preset epic_orchestral_depth --output-mode 4ch

# vintage jazz
python run_spatializer.py song.wav --preset-mode manual --preset vintage_jazz_room --output-mode 4ch
```

建议记录：空间感、后方存在感、人声清晰度、高频刺、低频宽度、reverb 是否过大、是否仍像 stereo。

---

## 10. 调参原则

### 空间感不够

优先调：

```text
side_rear
rear_floor_ratio
rear_master
lowbody_rear
```

不要第一时间大幅增加：

```text
air_rear
rear_highmid_gain
decorrelation
```

### 人声塑料/电话感

优先降低：

```text
rear_highmid_gain
air_rear
rear_air_gain
decorrelation
```

必要时提高：

```text
guard_scale
```

### 中低频不够宽

优先提高：

```text
lowbody_rear
```

小幅提高：

```text
bass_quad
```

### 大混响音乐变糊

优先降低：

```text
amb_rear
decorrelation
rear_highmid_gain
```

---

## 11. Binaural Preview 使用注意

binaural preview 只用于耳机快速检查趋势，不等价于实体 4.0 音箱。

原因：

- 通用 HRTF 会显著改变 EQ；
- headphone preview 的后方外化与个人耳朵、耳机有关；
- 如果实体音箱和 binaural preview 冲突，优先相信实体 4.0 音箱。

适合用它检查：

```text
LB/RB 是否有内容
不同 preset 的空间趋势
是否有明显 clipping / imbalance
```

不要用它作为最终音质判断。

---

## 12. 当前推荐工作方式

```text
1. 用 manual preset 批量渲染测试曲库
2. 每首歌输出 diagnostics JSON
3. 在真实 4.0 扬声器上 A/B
4. 按曲风与声学结构记录听感
5. 回写 presets.py 参数
6. 逐步形成稳定 preset library
```

现阶段正式调试优先围绕：

```text
general_pop_wide
wide_smooth
vocal_focus_wide
vocal_room_body_clear
bass_dry_wide
epic_orchestral_depth
vintage_jazz_room
```

