# DSP-Spacializer 阶段性开发报告

> 日期：2026-06-12  
> 阶段：Streaming Stereo → 4.0 DSP Spatializer 原型与 preset 调音阶段

---

## 1. 阶段结论

当前 `DSP-Spacializer` 已经完成从 notebook 原型到模块化仓库的初步整理，形成了一个可运行的 **非 AI stereo-to-4.0 DSP 空间化处理链路**。

当前系统已经具备：

```text
stereo audio input
↓
声学结构分析
↓
空间功能层提取
↓
preset-based routing
↓
4.0 rendering
↓
energy matching / limiter
↓
4ch WAV + preview + diagnostics
```

本阶段最重要的成果是：

> 已经证明普通 stereo 音频可以通过 DSP 层拆分、频段路由、后方去相关、能量管理和 preset 调参，形成可听见的 4.0 空间化效果；同时也明确了不同曲风无法用单一 wide preset 解决，必须进入曲风/声学结构驱动的 preset 精调阶段。

---

## 2. 当前开发目标

本阶段目标是为 4.0 无线扬声器产品建立一个 **streaming stereo 场景下的空间化 DSP 原型**。

目标链路：

```text
流媒体 / 本地 stereo 音频
↓
主机端解码为 PCM L/R
↓
DSP spatializer
↓
LF / RF / LB / RB 四声道输出
```

该链路区别于 AI stem separation。AI 分轨适合离线、内容制作或高算力场景；当前系统面向的是更轻量、更实时、更接近产品播放链路的 streaming stereo upmix。

---

## 3. 系统架构现状

当前仓库已经按模块拆分：

| 模块 | 功能 |
|---|---|
| `audio_io.py` | 音频加载、格式处理、导出 |
| `streaming_analyzer.py` | 分析 stereo width、center dominance、band coherence 等 |
| `layer_extractor.py` | 提取 Bass、Front Core、Side Width、Rear Ambience、High Air、Low Body |
| `presets.py` | 管理当前主要调音 preset |
| `layer_router.py` | 将 preset 转成最终 routing 参数 |
| `decorrelator.py` | 后方去相关与空间扩散 |
| `renderer_4ch.py` | 输出 LF/RF/LB/RB |
| `energy_manager.py` | 输入输出能量匹配 |
| `limiter.py` | 防止 clipping |
| `diagnostics.py` | 输出诊断指标 |
| `binaural_renderer.py` | 耳机虚拟预览 |
| `run_spatializer.py` | CLI 主入口 |

工程上，项目已经从单一 notebook 实验向 Python 模块化仓库过渡，便于批量测试和后续集成。

---

## 4. 核心算法阶段说明

当前输入假设为：

```text
decoded stereo PCM L/R
```

系统不处理：

- DRM；
- Spotify/Apple Music 等平台协议；
- AI stem separation；
- Atmos metadata；
- 硬件校准；
- 网络传输。

这一边界让算法可以专注于：

```text
stereo signal analysis + DSP spatial rendering
```

当前主要空间功能层包括：

1. **Bass Layer**：低频主体，负责稳定 bass 与 punch。  
2. **Front Core**：中心相关内容，包括人声、主旋律、鼓、bass body，主要保持在前方。  
3. **Side Width**：stereo L/R 差分信息，是横向宽度和后方包围的重要来源。  
4. **Rear Ambience**：原曲里的 diffuse/reverb/low-coherence 信息，送往后方形成空间感。  
5. **High Air**：高频空气感和空间边缘线索，决定后方是否有亮度和外化感。  
6. **Low Body**：约 120–500 Hz 的中低频体积，用于改善“后方只有高频/空间感太薄”的问题。

---

## 5. Preset 开发与调试总结

### 5.1 从 basic wide 到 `wide_smooth`

最早的 wide 思路是增强：

```text
side_rear
amb_rear
air_rear
decorrelation
rear_floor_ratio
```

测试结果表明：空间感确实增强，后方存在感明显；但高频容易呲，人声可能变远、变塑料，原曲 reverb 会被放大，部分曲目 3–7 kHz presence 变得刺耳。

因此进入 `wide_smooth` 阶段。

`wide_smooth` 的目标是：

```text
保留宽阔和包围感
减少早期 rear_boost 的高频刺激
维持后方音箱明显存在
```

阶段听感结论：

- 它是最能展示空间化效果的 preset；
- 适合 A/B 演示；
- 但不适合所有曲风；
- 在强中心人声或高相干录音中，仍可能产生人声塑料感。

---

### 5.2 人声保护：`vocal_focus_wide`

在测试 vocal-heavy 歌曲时，发现 `wide_smooth` 会把人声 presence 的一部分送到后方，叠加后方 delay/decorrelation 后，容易出现：

```text
人声变远
塑料感
电话感
3–7 kHz harsh
前后音箱之间的叠影
```

因此产生 `vocal_focus_wide`。

该 preset 的策略：

```text
降低后方 high-mid/air
降低一部分 side-to-rear aggressive routing
保留 lowbody_rear
保留一定 rear ambience
增强人声中心保护
```

听感结果：

- 对人声清晰、伴奏稀疏的 folk / acoustic pop 表现很好；
- 人声主体比 `wide_smooth` 稳；
- 空间感仍存在；
- 但在强 bass 电子/说唱、大混响交响、早期小声场 jazz 中表现不佳。

阶段判断：

> `vocal_focus_wide` 不应作为通用 preset，而应定位为 folk / singer-songwriter / vocal pop 的专用人声保护型宽声场 preset。

---

### 5.3 强人声保护：`vocal_room_body_clear`

进一步测试高相干、近 mono、强中心人声曲目时，发现只要后方 2–6 kHz 人声副本存在，就容易产生电话声和塑料感。

`vocal_room_body_clear` 因此采取更强保护：

```text
显著降低 rear_highmid_gain
显著降低 rear_air_gain
降低 decorrelation
降低 amb_rear
提高 guard_scale
```

听感结果：人声稳定、刺耳和电话感降低，但后方更柔和，空间感明显弱。它是“救人声”的安全模式，而不是“展示空间”的模式。

---

### 5.4 电子/说唱方向：`bass_dry_wide`

电子和说唱类音乐通常具有：

```text
强 bass
干燥 synth
中心 vocal/rap
自然 ambience 少
中低频内容丰富
```

如果仍用 vocal 或 wide 类 preset，空间感往往不明显，bass 也不够包围。

`bass_dry_wide` 的策略是：

```text
增加 lowbody_rear
增加 side_rear
少量 bass_quad
控制 amb_rear
控制 decorrelation
```

阶段判断：

> 该方向需要后续重点批量调试，因为电子/说唱对 bass punch 和空间宽度的要求与 vocal/folk 完全不同。

---

### 5.5 交响/epic 方向：`epic_orchestral_depth`

大混响交响与 cinematic 音乐的问题是：原曲本来就有 hall，再增强 `amb_rear` 容易糊；1–2 kHz 中频乐器容易突出；2 kHz 以上木管/长笛可能被混响盖掉；cello / low strings 需要 body，但不能变浑。

`epic_orchestral_depth` 的策略：

```text
降低 amb_rear
降低 decorrelation
控制 rear_highmid_gain
保留适度 side_rear
用 lowbody_rear 保留低弦体积
```

阶段判断：

> 交响类不应该追求“更大混响”，而应该追求“可控纵深和层次”。

---

### 5.6 早期 jazz / 小声场方向：`vintage_jazz_room`

早期 jazz 和小声场录音常见问题：

```text
stereo width 很窄
side 信息很少
diffuse ambience 少
全频高相干
后方没有可直接提取的内容
```

`vintage_jazz_room` 的策略：

```text
增加 rear_floor_ratio
增加 lowbody_rear
适度提高 side_rear
提供温和小房间感
避免过亮 air
```

阶段判断：

> 该方向后续需要更明确的 rear room fill / perceptual fill，否则单靠 side/diffuse 提取不够。

---

## 6. 当前主要听感问题

### 6.1 单一 preset 无法跨曲风泛化

`wide_smooth` 可以展示空间感，但在人声上风险高。`vocal_focus_wide` 适合 folk，但对电子/交响/jazz 不适配。`vocal_room_body_clear` 安全但空间弱。不同曲风需要不同空间策略。

### 6.2 后方 RMS 与主观空间感不完全一致

部分测试中，LB/RB RMS 并不低，但主观仍像 stereo。原因是后方内容可能缺少中高频轮廓、attack、空气感和可辨识空间线索。

### 6.3 高频亮度与人声保护存在矛盾

为了避免人声塑料感，系统会降低 rear high-mid 和 air。但如果压得太狠，可能导致人声高频明亮感被吞、后方外化线索不足、原本 stereo 的层次感没有转化为 4.0 增益。

### 6.4 极窄声场素材需要额外空间生成机制

对于早期 jazz、安静歌曲、频段单一且集中、高频内容不丰富的音乐，原始 stereo 中可提取的 side/diffuse 很少。单纯提高 `side_rear` 或 `amb_rear` 作用有限。

---

## 7. 当前成果

### 7.1 算法成果

已形成完整 DSP pipeline：

```text
Analyzer
Layer Extractor
Preset Router
4.0 Renderer
Energy Manager
Limiter
Diagnostics
```

可以稳定输出：

```text
4ch WAV
binaural preview
diagnostics JSON
batch manifest
```

### 7.2 Preset 成果

当前已经形成一组可测试 preset：

```text
general_pop_wide
wide_smooth
vocal_focus_wide
vocal_room_body_clear
bass_dry_wide
epic_orchestral_depth
vintage_jazz_room
```

它们覆盖了通用流行、强空间演示、人声 folk、强人声保护、电子/说唱、交响/epic、早期 jazz / 小声场等方向。

### 7.3 工程成果

项目已从 notebook 实验向 Python 模块化仓库过渡。CLI 支持单曲和批量处理，输出目录、preset、output mode 等参数可以通过命令行和配置文件控制。

---

## 8. 下一阶段目标

下一阶段核心是进入 **preset 批量人工精调阶段**。

### 8.1 建立标准测试曲库

建议建立 20–50 首测试集，覆盖：

```text
vocal folk
general pop
EDM
rap / trap
cinematic / epic
orchestral
old jazz
small room jazz
rock
ambient
```

每类至少 3–5 首。

### 8.2 为每首歌批量导出多个 preset

建议每首歌至少导出：

```text
bypass
ms_baseline
general_pop_wide
wide_smooth
vocal_focus_wide
vocal_room_body_clear
bass_dry_wide
epic_orchestral_depth
vintage_jazz_room
```

并记录：空间感、后方存在感、人声清晰度、高频刺耳程度、低频包围、reverb 是否过大、是否仍像 stereo。

### 8.3 建立 preset 评分表

| 曲名 | 曲风 | Preset | 空间感 | 人声 | 高频 | 低频 | 后方 | 备注 |
|---|---|---:|---:|---:|---:|---:|---:|---|

评分建议 1–5 分。这个表会成为下一阶段调参的核心资产。

### 8.4 精调方向

`wide_smooth`：保留强空间感，减少高频刺与人声塑料，优化 reverb 放大程度。  
`vocal_focus_wide`：保持 folk / vocal 优势，提高一点空间存在感，避免回到 wide_smooth 的塑料感。  
`bass_dry_wide`：增强 bass pressure，拓宽 dry synth，保持 rap/vocal 居中。  
`epic_orchestral_depth`：减少 hall 糊，保留纵深，让木管/长笛/低弦更清楚。  
`vintage_jazz_room`：让小声场更自然打开，避免假大厅，提高后方存在感。

---

## 9. Auto preset 的预见性开发思路

下一阶段在人工 preset 精调稳定后，可以基于 analyzer 的声学结构指标，逐步建立自动 preset 推荐与参数自适应框架。

预期思路：

```text
输入歌曲
↓
分析 stereo_width / center_dominance / bass_mono_ratio / high_diffuse_ratio / band_coherence
↓
判断声学结构
↓
选择最接近的 preset family
↓
根据指标微调 rear_floor / side_rear / lowbody / highmid / air
↓
输出 4.0
```

自动化不应先追求完全替代听评，而应先做到：

```text
避免明显错误
自动给出合理初始 preset
辅助批量测试
减少人工试错时间
```

更合理的发展顺序是：

```text
人工听评数据积累
↓
preset 稳定
↓
规则化推荐
↓
参数自适应
↓
小规模产品化自动模式
```

当前阶段建议仍把 manual preset tuning 作为主线，把自动化作为下一阶段预研方向，而不是当前正式功能卖点。

---

## 10. 风险与限制

1. 如果输入音频极窄、近 mono、缺少 high diffuse 和 side material，DSP 只能有限打开空间。  
2. 电子、说唱、交响、folk、old jazz 的空间目标不同，不能依赖一个 universal preset。  
3. 通用 HRTF 的 binaural preview 容易改变 EQ，不能代表真实四音箱播放。  
4. 当前只输出逻辑 4ch 文件，还未与真实硬件校准、UWB 定位、主机 DSP、无线同步等链路联调。

---

## 11. 阶段性结论

当前 `DSP-Spacializer` 已经进入 **可运行、可批量测试、可人工调音** 的原型阶段。

最重要的阶段成果是：

```text
1. 证明 stereo → 4.0 的 DSP pipeline 可行；
2. 建立了空间功能层，而非 stem separation 的工程思路；
3. 明确了不同曲风需要不同 preset；
4. 形成了初步 preset library；
5. 建立了 diagnostics + 听评联合调参路径；
6. 为后续自动化推荐与产品端部署奠定结构基础。
```

下一阶段应集中资源做：

```text
批量人工听评
preset 精调
曲风适配
后方 perceptual fill 预研
真实 4.0 音箱验证
```

