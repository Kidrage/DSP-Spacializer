# Speaker-to-Binaural Mixing / Transaural Spatial Upmix 方案 Handoff

> 目标：将「2D/4.0/4.2 扬声器阵列 + HRTF + CTC」设计成一个面向单人听感优化的极致空间化模式。该方案不是传统 stereo→4ch 上混，而是将 stereo 或对象化内容先解释成 binaural 空间场景，再通过扬声器阵列和串音消除，让用户在不戴耳机的情况下获得接近 binaural/headphone spatial audio 的听感。

---

## 0. 项目定位

### 0.1 名称建议

工程名：`TransauralSpatialUpmix`

产品名可选：

- **Personal Immersive Mode**
- **Speaker Binaural Mode**
- **Air Headphone Mode**
- **Transaural Binaural Mode**
- **单人沉浸皇帝位模式**

### 0.2 一句话定义

**用真实扬声器阵列复现目标 binaural ear signals，使单个听众在不戴耳机的情况下获得强烈的 binaural 空间化体验。**

### 0.3 它不是普通上混

普通上混：

```text
Stereo L/R
  ↓
M/S、decorrelation、reverb、matrix
  ↓
LF/RF/LB/RB 扬声器声道
```

本方案：

```text
Stereo / Object / Stem
  ↓
非 AI 声场解释：center / side / ambience / transient / bass
  ↓
虚拟 2D/3D 空间场景
  ↓
HRTF binaural rendering
  ↓
目标双耳信号 binaural_L / binaural_R
  ↓
多扬声器 CTC inverse filtering
  ↓
4.0 / 4.2 扬声器输出
  ↓
用户双耳收到接近目标 binaural 的信号
```

核心区别：

- 普通 4.0 上混追求的是「房间里四个扬声器形成稳定空间感」。
- 本方案追求的是「用户左右耳膜收到正确的 binaural signal」。
- 它更像“空气中的耳机”，不是“真实重建完整三维声场”。

---

## 1. 使用场景与边界

### 1.1 最适合场景

- 单人坐在校准点听音乐。
- 桌面近场或小客厅主位。
- 产品演示模式。
- 游戏、VR、沉浸式音乐体验。
- 空间音频内容预览。
- 普通 stereo 音乐的强空间化增强。

### 1.2 不适合默认使用的场景

- 多人同时在不同位置听。
- 用户在房间里自由走动。
- 没有测距/测向/麦克风校准。
- 强混响、强反射、扬声器距离过远的客厅。
- 专业混音判断场景，除非系统经过严格校准和 AB 证明。

### 1.3 产品定位建议

该模式应作为高级模式，而不是默认音乐播放模式。

推荐产品结构：

```text
Default Mode：普通 4.0/4.2 空间增强，甜区较宽
Immersive Mode：混合式 HRTF + CTC，空间感明显增强
Transaural Mode：单人极致模式，强依赖校准和听音点
```

---

## 2. 核心技术概念

### 2.1 HRTF / Binaural Rendering

HRTF/HRIR 用于描述某个方向、距离的声音到达左右耳时发生的滤波变化。

输入：

```text
mono signal + virtual source position
```

输出：

```text
left ear target signal + right ear target signal
```

例如：

```text
vocal → azimuth 0°, elevation 0°, distance 1.5m
ambience → azimuth ±120°, elevation 0°, distance 3m
sparkle → azimuth ±70°, elevation 30°, distance 2m
```

经过 HRTF 后，每个虚拟音源都会生成一对 binaural 信号。

### 2.2 CTC / Crosstalk Cancellation

扬声器播放 binaural 时会出现串音：

```text
左扬声器 → 左耳：目标路径
左扬声器 → 右耳：串音路径
右扬声器 → 右耳：目标路径
右扬声器 → 左耳：串音路径
```

CTC 的目标：

```text
让左耳尽量收到 binaural_L
让右耳尽量收到 binaural_R
抵消对侧串音
```

矩阵形式：

```text
p = H · s
```

其中：

```text
p = [p_L, p_R]^T                     # 双耳目标声压
s = [s_1, s_2, ..., s_N]^T           # N 个扬声器驱动信号
H = 2 × N speakers-to-ears transfer  # 扬声器到左右耳传输矩阵
```

求解：

```text
s = H⁺ · p_target
```

工程上使用正则化伪逆：

```text
s = H^H · (H · H^H + λI)^(-1) · p_target
```

其中 λ 用于控制稳定性、扬声器能量、动态范围损失和高频爆增。

---

## 3. 推荐总体链路

### 3.1 Hybrid 架构，而不是全频全量 CTC

最稳产品方案不是把整首 stereo 全频全量送进 HRTF+CTC，而是混合架构：

```text
主声像 / center / bass / transient：保守播放，保证音乐稳定
side / ambience / reverb / air / selected objects：HRTF + CTC，制造强空间化
```

理由：

- 人声、kick、snare、bass 如果被强 CTC 或错误 HRTF 处理，听感容易塌。
- 空间层、混响层、侧向层更适合做强 binaural 外部化。
- 产品听感应优先“不翻车”，再追求“惊艳”。

### 3.2 完整处理链

```text
Input Stereo / Stems / Objects
  ↓
Pre Analysis
  - loudness
  - stereo correlation
  - M/S energy ratio
  - spectral centroid
  - transient density
  - bass energy
  - ambience probability
  ↓
Layer Decomposition
  1. Front Core
  2. Center Anchor
  3. Side Width
  4. Rear / Surround Ambience
  5. Air / Sparkle
  6. Bass / LFE
  ↓
Virtual Scene Builder
  - assign azimuth / distance / width
  - optional elevation for advanced mode
  - generate virtual objects / beds
  ↓
Binaural Renderer
  - HRTF convolution
  - distance model
  - early reflection / late reverb optional
  ↓
CTC Processor
  - speaker-to-ear transfer matrix
  - regularized inverse filtering
  - band-limited CTC
  - head-position dependent update
  ↓
Speaker Output Renderer
  - 4.0 main output
  - 4.2 bass management
  - limiter / protection
  ↓
Playback
```

---

## 4. 模块拆分

## Module A：Calibration / Layout Capture

### 目标

获取扬声器到听音点/双耳的几何和声学传输信息。

### 输入

- 扬声器数量：4.0 或 4.2。
- 扬声器相对位置：角度、距离、高度。
- 听音点位置。
- 可选：用户头部朝向。
- 可选：麦克风测得的 IR。

### 输出

```json
{
  "listener_position": [0.0, 0.0, 1.2],
  "head_yaw_deg": 0.0,
  "speakers": [
    {"id": "spk1", "azimuth_deg": -35, "distance_m": 1.8, "gain_db": -1.2, "delay_ms": 5.2},
    {"id": "spk2", "azimuth_deg":  32, "distance_m": 1.9, "gain_db": -1.0, "delay_ms": 5.5},
    {"id": "spk3", "azimuth_deg": -130, "distance_m": 2.2, "gain_db": -2.0, "delay_ms": 6.4},
    {"id": "spk4", "azimuth_deg":  128, "distance_m": 2.1, "gain_db": -1.8, "delay_ms": 6.1}
  ],
  "subs": [
    {"id": "sub1", "distance_m": 2.0, "delay_ms": 5.8, "polarity": 1},
    {"id": "sub2", "distance_m": 2.4, "delay_ms": 7.0, "polarity": 1}
  ]
}
```

### 实现建议

分两级实现：

#### Level 1：几何近似版

用 UWB / App 引导 / 手动输入得到扬声器坐标。

估算 H 矩阵：

- 根据扬声器到左右耳的距离计算 delay。
- 根据距离和角度估算 gain。
- 用简化 head shadow 模型估算 ILD。

优点：快，适合 prototype。

缺点：高频 CTC 不准。

#### Level 2：实测 IR 版

用麦克风或 binaural dummy / 用户耳边麦克风采集每个扬声器到左右耳的 IR。

得到：

```text
h_speaker_i_to_left_ear[n]
h_speaker_i_to_right_ear[n]
```

优点：CTC 准确度高。

缺点：校准流程复杂。

### 验收标准

- 能保存并加载 layout JSON。
- 能对任意 4 个主扬声器生成 2×4 transfer matrix。
- 能对 4.2 生成独立 bass management 参数。
- delay/gain compensation 后，四个扬声器在听音点 RMS 偏差小于 ±1.5 dB。

---

## Module B：Stereo Analysis & Layer Decomposition

### 目标

从普通 stereo 中提取适合空间化的层，避免人声、低频、主瞬态被错误送入强 CTC。

### 输入

```text
L[n], R[n]
```

### 基础分解

```text
M = (L + R) / 2
S = (L - R) / 2
```

### 层定义

#### 1. Front Core

保留原始 stereo 舞台。

```text
front_L = L * a + M * b
front_R = R * a + M * b
```

建议：

```text
a = 0.75 ~ 0.9
b = 0.05 ~ 0.2
```

#### 2. Center Anchor

高相关中心信息：

```text
center = bandpass(M, 120Hz, 6000Hz)
```

用于稳定人声、鼓、主旋律。

#### 3. Side Width

```text
side = highpass(S, 150Hz ~ 250Hz)
```

用于左右扩展和轻度 binaural 空间化。

#### 4. Rear Ambience

```text
rear_seed = decorrelate(highpass(S, 180Hz)) + late_reverb(M) * small_gain
```

用于后方/侧后方外部化。

#### 5. Air Layer

```text
air = highpass(S or L/R residual, 6000Hz ~ 8000Hz)
```

只轻微增强，避免高频尖锐和 CTC 高频失稳。

#### 6. Bass / LFE

```text
bass = lowpass(M, 80Hz ~ 120Hz)
```

只进入 main bass 或 dual sub，不进入强 HRTF/CTC 空间层。

### 动态规则

根据短时 correlation 调节强度：

```text
corr = correlation(L_frame, R_frame)
```

规则：

```text
corr > 0.6       → 中心材料多，降低 CTC spatial intensity
0.2 < corr < 0.6 → 正常空间增强
corr < 0.2       → side/ambience 可增强
```

根据 transient density 调节：

```text
transient strong → 减少后方和 CTC
sustained pad/reverb → 增强后方和 CTC
```

### 验收标准

- 人声类音乐中，center vocal 不明显跑后或偏侧。
- 低频不会因 side/CTC 处理产生明显相位塌陷。
- 开启空间化后，mono compatibility 可接受。
- 与原 stereo A/B，对主旋律清晰度损伤可控。

---

## Module C：Virtual Scene Builder

### 目标

把分解出的音频层映射为虚拟空间对象或空间床。

### 默认 2D 虚拟布局

```json
{
  "center_anchor": {"azimuth": 0, "distance": 1.5, "width": 0.1},
  "front_left":    {"azimuth": -30, "distance": 1.8, "width": 0.2},
  "front_right":   {"azimuth":  30, "distance": 1.8, "width": 0.2},
  "side_left":     {"azimuth": -70, "distance": 2.2, "width": 0.5},
  "side_right":    {"azimuth":  70, "distance": 2.2, "width": 0.5},
  "rear_left":     {"azimuth": -125, "distance": 2.8, "width": 0.8},
  "rear_right":    {"azimuth":  125, "distance": 2.8, "width": 0.8},
  "air":           {"azimuth": 0, "distance": 3.0, "width": 1.0}
}
```

### 场景策略

#### Safe Scene

```text
center: front only
side: ±60°
rear ambience: weak, ±110°
CTC bandwidth: limited
```

#### Immersive Scene

```text
center: front stable
side: ±80°
rear ambience: ±130°
air: wide diffuse
CTC bandwidth: medium
```

#### Extreme Transaural Scene

```text
center: binaural front
side/rear: strong HRTF
selected transient objects: can orbit or move
CTC bandwidth: aggressive but protected
```

### 验收标准

- 场景配置可由 preset JSON 控制。
- 可以实时切换 Safe / Immersive / Extreme。
- 切换时无爆音、无明显响度跳变。
- 所有虚拟对象均可 bypass，用于调试。

---

## Module D：HRTF Binaural Renderer

### 目标

将虚拟对象/空间床渲染成目标 binaural L/R。

### 输入

```text
virtual_sources = [
  {signal, azimuth, elevation, distance, width, gain}
]
```

### 输出

```text
binaural_L[n], binaural_R[n]
```

### 实现建议

#### Prototype

- 使用公开 HRIR 数据集。
- 先只实现 2D azimuth。
- elevation 固定 0°。
- distance 用 gain、direct/reverb ratio、HF damping 简化模拟。

#### Advanced

- 支持 elevation。
- 支持个性化 HRTF profile 选择。
- 支持插值。
- 支持 minimum-phase + ITD 分离。
- 支持动态头部朝向修正。

### Width 处理

宽对象不要只用单个 HRTF 点。

建议：

```text
wide source = multiple virtual points + decorrelation
```

例如 rear ambience：

```text
rear_bed = sum of 4~8 virtual points around ±100°~±160°
```

### 验收标准

- 单个 mono click/voice 能稳定定位到指定方向。
- side/rear layer 有明确外部化，不明显 inside-head。
- 高频不过度尖锐。
- HRTF bypass 后可回到普通 stereo/upmix。

---

## Module E：CTC Processor

### 目标

将目标 binaural L/R 转换为 N 个扬声器驱动信号，使左右耳尽量收到目标 binaural 信号。

### 输入

```text
binaural_L, binaural_R
H_matrix or measured IRs
regularization settings
band limits
```

### 输出

```text
speaker_1, speaker_2, speaker_3, speaker_4
optional sub_1, sub_2
```

### 设计原则

#### 1. Band-limited CTC

不要全频无脑 CTC。

建议频段：

```text
低频 < 150Hz：不做 CTC，走 bass management
中频 150Hz~6kHz：主要 CTC 工作区
高频 > 6kHz：谨慎、弱化或只做轻度处理
```

原因：

- 低频串音消除需要大量能量，且定位收益低。
- 高频对头动和位置误差极敏感。
- 中频是空间外部化和前后侧向感的主要可控区。

#### 2. Regularized inverse

频域逐 bin 求解：

```text
S(f) = H(f)^H · (H(f) · H(f)^H + λ(f)I)^(-1) · P_target(f)
```

其中：

```text
S(f): N 个扬声器频域信号
H(f): 2×N 传输矩阵
P_target(f): 2×1 双耳目标
λ(f): 频率相关正则项
```

#### 3. Energy constraint

限制扬声器驱动能量：

```text
if speaker_gain_boost > threshold:
    increase regularization
    reduce CTC depth
```

建议阈值：

```text
max boost: +6dB prototype
absolute max boost: +12dB debug only
```

#### 4. CTC Depth

不要只有 on/off。做成连续参数：

```text
ctc_depth = 0.0 ~ 1.0
```

混合方式：

```text
output = dry_speaker_render * (1 - ctc_depth) + ctc_output * ctc_depth
```

#### 5. Head-position adaptive CTC

如果有 head tracking：

```text
head pose update → update H approximation or select nearest CTC filter
```

低成本做法：

- 每 10° yaw 一个 filter set。
- 每 5~10 cm 位置变化一个 filter set。
- 运行时 crossfade。

### 验收标准

- 生成 4ch 输出无明显爆音。
- CTC on/off 有明显空间差异。
- 坐在主位时，binaural 外部化明显强于普通 4.0 upmix。
- 头部平移 10~20 cm 内仍可接受，但允许效果下降。
- 离开主位时不应产生刺耳、过载或严重 comb-filter。

---

## Module F：4.2 Bass Management

### 目标

将低频从 CTC 链路中分离，交给 sub 或主扬声器低频系统处理。

### 推荐策略

```text
<80Hz: mono bass → sub1/sub2
80~120Hz: crossover blend
120~180Hz: main speakers with caution
>180Hz: spatial layers
```

### 双 Sub 处理

```text
sub_signal = lowpass(M, crossover_freq)
sub1 = delay_gain_eq(sub_signal, sub1_calib)
sub2 = delay_gain_eq(sub_signal, sub2_calib)
```

### 验收标准

- sub/main crossover 处无明显低频空洞。
- sub polarity 切换测试能找到更优状态。
- 低频不因 CTC 开关发生巨大变化。
- 极致模式下低频仍稳定、居中、有重量。

---

## 5. 三档产品模式

### 5.1 Safe Spatial Mode

目标：稳，适合默认体验。

```text
front core: normal speaker rendering
side width: mild decorrelation
rear ambience: weak
HRTF: optional, weak
CTC: off or 0.1~0.2
bass: normal 4.2 management
```

听感：

- 比 stereo 宽。
- 后方有空气感。
- 不容易翻车。

### 5.2 Immersive Transaural Mode

目标：明显空间化，适合产品亮点。

```text
front core: preserved
center anchor: front stable
side/rear/air: HRTF binaural rendering
CTC: 0.4~0.7
bass: independent
```

听感：

- 明显外部化。
- 左右/后方空间增强。
- 音乐主体仍清楚。

### 5.3 Extreme Personal Binaural Mode

目标：单人皇帝位极致体验。

```text
full virtual scene → HRTF → CTC
front core 也可部分 binauralize
CTC: 0.7~1.0
requires calibration
prefer head tracking
```

听感：

- 最强烈。
- 可尝试绕头、耳边、后方、头顶幻觉。
- 甜点位要求最高。

---

## 6. 工程接口建议

### 6.1 C++ 类结构建议

```cpp
class LayoutCalibrator {
public:
    SpeakerLayout loadLayout(const std::string& path);
    TransferMatrix estimateTransferMatrix(const SpeakerLayout& layout,
                                          const ListenerPose& pose);
    MeasuredIRSet loadMeasuredIRs(const std::string& path);
};

class StereoLayerAnalyzer {
public:
    LayerFrame processBlock(const float* left,
                            const float* right,
                            int numSamples);
};

class VirtualSceneBuilder {
public:
    VirtualScene buildScene(const LayerFrame& layers,
                            const ScenePreset& preset);
};

class HRTFRenderer {
public:
    BinauralBlock render(const VirtualScene& scene,
                         int numSamples);
};

class CTCProcessor {
public:
    void prepare(const TransferMatrix& H,
                 const CTCSettings& settings);

    SpeakerBlock process(const BinauralBlock& target);
};

class BassManager42 {
public:
    BassOutput process(const float* midSignal,
                       int numSamples,
                       const BassSettings& settings);
};

class TransauralSpatialUpmixEngine {
public:
    void prepare(double sampleRate, int blockSize);
    void setLayout(const SpeakerLayout& layout);
    void setPreset(const TransauralPreset& preset);
    void processStereoTo42(const float* inL,
                           const float* inR,
                           float** outSpeakers,
                           int numSamples);
};
```

### 6.2 Python Prototype 结构建议

```text
transaural_spatial_upmix/
  calibration/
    layout.py
    transfer_matrix.py
    measured_ir.py
  analysis/
    ms_decompose.py
    transient.py
    ambience.py
  scene/
    scene_builder.py
    presets.py
  hrtf/
    hrtf_loader.py
    binaural_renderer.py
  ctc/
    inverse_filter.py
    regularization.py
    ctc_processor.py
  bass/
    bass_manager.py
  evaluation/
    metrics.py
    ab_render.py
  demos/
    render_stereo_to_4ch.py
    render_stereo_to_42.py
```

---

## 7. 最小可行 Demo

### 7.1 MVP 目标

输入一首 stereo wav，输出 4ch wav：

```text
input_stereo.wav
  ↓
TransauralSpatialUpmix prototype
  ↓
output_4ch_transaural.wav
```

### 7.2 MVP 限制

- 固定 4 扬声器布局。
- 固定听音点。
- 只做 2D azimuth HRTF。
- 不做 head tracking。
- 用估算 transfer matrix，不要求实测 IR。
- CTC 只做 200Hz~6000Hz。
- 低频直接保守分配到前方或 sub。

### 7.3 MVP 链路

```text
1. read stereo wav
2. loudness normalize
3. M/S decomposition
4. create layers:
   - front core
   - center anchor
   - side width
   - rear ambience
   - bass
5. assign virtual positions
6. HRTF render side/rear layers to binaural
7. CTC convert binaural to 4 speaker feeds
8. mix with dry front core
9. bass management
10. limiter
11. write 4ch wav
```

### 7.4 MVP 验收

主观验收：

- A/B 比普通 stereo 更宽、更外部化。
- A/B 比普通 4.0 upmix 有更强“耳外/后方/环绕”感。
- 人声没有明显跑到后面。
- 低频没有塌。
- 没有明显刺耳或爆音。

客观验收：

- 输出峰值不超过 -1 dBFS。
- integrated loudness 与输入差异可控。
- 各扬声器 RMS 不出现异常偏大。
- CTC filter max boost 受限。
- mono downmix 不产生严重抵消。

---

## 8. 关键风险与规避

### 风险 1：CTC 甜点位太小

表现：用户头一动，空间感消失或音色变怪。

规避：

- 默认使用 Immersive Mode，不默认 Extreme。
- CTC depth 可调。
- 限制 CTC 高频。
- 加入 head tracking 或多位置 filter crossfade。
- 离开主位时自动退回 Safe Mode。

### 风险 2：HRTF 不匹配导致前后/上下混淆

表现：后方像前方，头顶不像头顶，声音进脑子。

规避：

- 先主打 2D 平面强空间感，不急着宣传头顶。
- 提供 HRTF profile 选择。
- 加入个性化测试：用户选择哪个版本外部化最好。
- 对高频 notch 不做过度夸张。

### 风险 3：房间反射破坏 CTC

表现：comb-filter、染色、定位不稳。

规避：

- 近场优先。
- 校准时估算 direct window。
- CTC inverse 只针对早期/direct path。
- late reflection 不强行反演。
- 正则化加强。

### 风险 4：音乐主体被空间化搞坏

表现：人声糊、鼓不集中、低频散。

规避：

- Center / bass / transient 默认保守处理。
- HRTF+CTC 主要用于 side/rear/ambience。
- 对高 correlation 内容降低空间化强度。
- preset 针对 vocal/folk/electronic/orchestral 分开。

### 风险 5：扬声器能量过大或滤波爆增

表现：某一路喇叭突然很大，失真或保护触发。

规避：

- max boost limiter。
- frequency-dependent λ。
- output limiter。
- per-speaker RMS watchdog。
- CTC fail-safe fallback。

---

## 9. 分阶段开发计划

### Phase 0：理论验证 / Offline Notebook

目标：证明 stereo→binaural scene→CTC→4ch 有明显听感收益。

任务：

- 固定 4 扬声器布局。
- 写 Python offline renderer。
- 用公开 HRTF。
- 实现 M/S layer。
- 实现简化 2×4 CTC inverse。
- 输出 4ch wav。

验收：

- 至少 5 首歌 A/B。
- 人声稳定性可接受。
- 空间感明显强于普通 stereo。

### Phase 1：Hybrid Product Prototype

目标：形成可调 preset 的产品原型。

任务：

- 三档模式 Safe / Immersive / Extreme。
- 增加 preset JSON。
- 增加 limiter 和能量保护。
- 支持 4.2 bass management。
- 支持布局 JSON。

验收：

- 4.0/4.2 均可输出。
- 不同布局可重算参数。
- 开关 CTC 差异明确。

### Phase 2：Calibration Integration

目标：接入真实测距/测向/扫频。

任务：

- 读取 UWB / 扬声器自带麦阵列结果。
- 生成真实 speaker layout。
- 可选采集 IR。
- 生成更准确 H matrix。
- 支持校准 profile 保存。

验收：

- 校准后空间感优于默认布局。
- 听音点偏差小于一定范围时仍可接受。

### Phase 3：Realtime Engine

目标：移植到 C++/App/主机实时播放链路。

任务：

- C++ block-based 处理。
- partitioned convolution。
- 低延迟 CTC FIR。
- preset realtime switch。
- CPU profiling。

验收：

- 48kHz realtime。
- latency 可控。
- CPU 占用满足主机端预算。
- 无爆音、无内存泄漏。

### Phase 4：Head Tracking / Personalization

目标：让 Extreme Mode 更稳。

任务：

- 接入 head pose。
- 多 filter set crossfade。
- HRTF profile selection。
- 用户听感测试流程。

验收：

- 用户轻微转头时空间感不立刻崩。
- 个性化 profile 明显提升外部化命中率。

---

## 10. 推荐优先级

### 必须先做

1. Stereo layer decomposition。
2. HRTF binaural renderer。
3. 简化 2×4 CTC inverse。
4. Hybrid dry/CTC mix。
5. Output limiter / energy guard。
6. 4.2 bass management。

### 第二优先级

1. 实测 IR。
2. 多布局适配。
3. 多 preset。
4. HRTF profile selection。
5. UI 校准引导。

### 暂缓

1. 完整 3D elevation 宣传。
2. 全频全量 CTC。
3. 多人 CTC。
4. 房间完整声场重建。
5. 完全自动对象分离。

---

## 11. 给工程 Agent / 同事的执行 Prompt

请基于当前仓库新增一个 `TransauralSpatialUpmix` 原型模块，目标是实现「stereo 输入 → 非 AI 分层 → HRTF binaural rendering → 4 扬声器 CTC → 4.0/4.2 输出」的离线 proof-of-concept。不要改动已有稳定 DSP 上混链路，新增模块应独立，可被后续 C++/App 链路复用。

### 具体任务

1. 新增模块目录：

```text
transaural_spatial_upmix/
  calibration/
  analysis/
  scene/
  hrtf/
  ctc/
  bass/
  evaluation/
  demos/
```

2. 实现 stereo 分层：

- M/S decomposition。
- front_core。
- center_anchor。
- side_width。
- rear_ambience。
- bass。
- 每一层可单独导出 wav debug。

3. 实现虚拟场景配置：

- 用 JSON 定义虚拟对象方向、距离、宽度、gain。
- 至少支持 Safe / Immersive / Extreme 三个 preset。

4. 实现 HRTF renderer：

- 可加载 HRIR wav/npz。
- 支持 azimuth 插值，至少先支持 2D。
- 输出 target binaural L/R。

5. 实现 CTC processor：

- 支持 2×4 transfer matrix。
- 支持 regularized pseudo-inverse。
- 支持 frequency-dependent regularization。
- 支持 ctc_depth 0~1。
- 支持 band-limited CTC。
- 支持 per-speaker energy guard。

6. 实现 4.2 bass management：

- lowpass M 作为 bass。
- 支持 sub1/sub2 delay/gain/polarity。
- 支持 crossover frequency 设置。

7. 实现 demo CLI：

```bash
python demos/render_stereo_to_transaural_4ch.py \
  --input input.wav \
  --layout configs/layout_4ch_default.json \
  --preset configs/preset_immersive.json \
  --output output_4ch.wav \
  --debug-dir debug_layers
```

8. 实现基础验收脚本：

- 输出峰值检查。
- 各声道 RMS 检查。
- filter boost 检查。
- mono downmix check。
- debug report JSON。

### 验收标准

- CLI 能成功输入 stereo wav，输出 4ch wav。
- Safe / Immersive / Extreme 三档均可运行。
- 每一层 debug wav 可导出。
- CTC 可开关，开关后听感差异明显。
- 人声类测试中，人声不得明显跑后。
- 输出不得 clipping。
- 任一扬声器声道 RMS 不得异常爆增。
- 代码不破坏现有 DSP-Spacializer 或 app framework 产物。
- 提供 README，说明算法链路、参数、运行命令和已知限制。

---

## 12. 最终产品判断

这条路线值得做，但应该以“单人极致沉浸模式”定位，而不是替代所有 4.0/4.2 上混。

最佳产品结构是：

```text
普通播放：4.0/4.2 非 AI 空间增强，上限稳，甜区宽
单人沉浸：HRTF + CTC transaural，上限高，甜点位窄
专业制作：保守监听模式，少处理，可 A/B
```

一句话结论：

**2D 扬声器阵列 + HRTF + CTC 可以成为一种非常硬核的 speaker-based binaural upmix。它可以制造强烈空间化，但必须承认它本质是单人听点优化，而不是多人共享的真实三维声场重建。产品上应以 hybrid 架构落地：主体保守，空间层激进，低频独立，CTC 可调。**
