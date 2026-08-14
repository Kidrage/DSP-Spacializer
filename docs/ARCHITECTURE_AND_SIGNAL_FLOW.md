# DSP-Spacializer 生产链路与信号流

本文按当前 `main` 实际代码解释生产链路。仓库中并存两套架构：冻结的 legacy
固定 4.0 链路，以及 opt-in 的 Spatial Core V2 对象/声场链路。它们不是同一条
链路的两个配置档。

## 1. 总体结论

```text
legacy（兼容默认）
stereo -> DSP buses -> 固定 4.0 -> 可选虚拟扬声器 binaural

Spatial Core V2（推荐演进方向）
stereo/scene -> 七区 -> objects + FOA field -> binaural 或 speaker renderer
```

- Legacy 的核心产品是 `[LF, RF, LB, RB]` 四声道信号；binaural 是它的后级。
- V2 的核心产品是 `SpatialScene`；binaural 与扬声器输出是并列 renderer。
- 当前 `SpatialScene` 是运行时渲染格式，不是完整母版：三类扩散区已经合并进
  一条 FOA bed，无法再分别调节。
- 新的 `spatial_scene_package/0.1` 位于七区提取与 `SpatialScene` 之间，保留七区
  音频和作者参数；FOA 改为渲染时派生表示。

## 2. 入口与控制面

|入口|用途|主要输出|
|---|---|---|
|`run_spatializer.py` 默认模式|冻结 legacy 生产链|4.0、legacy binaural、诊断|
|`run_spatializer.py --engine spatial-v2`|V2 文件渲染|SOFA binaural、quad、scene manifest|
|`run_spatial_mixer.py`|本地七区校准台|A/B preview、mixer profile、证据包|
|`spatial_core.workflow.render_spatial_v2`|V2 Python 工作流|统一渲染结果和 diagnostics|
|`SpatialScene` + `SceneRenderer`|运行时 seam|任意 renderer 的输入|

V2 接受且只接受以下两种输入之一：

1. stereo 文件，由 compact profile 或完整 mixer profile 生成场景；
2. `spatial_core_scene/2.0` manifest，直接恢复当前运行时场景。

## 3. Legacy：stereo 到固定 4.0

### 3.1 生产顺序

```text
读取/重采样
  -> 声学分析
  -> manual / auto_select / auto_acoustic preset
  -> legacy 七 bus 提取
  -> routing + 固定 4.0 渲染
  -> rear safety
  -> 可选闭环 refine
  -> front-anchor 能量匹配
  -> linked limiter
  -> WAV + diagnostics
  -> 可选 4.0 虚拟扬声器 binaural / room RIR / CTC
```

`layer_extractor.extract_layers` 生成 `bass`、`low_body`、`front_L`、`front_R`、
`side_width`、`rear_ambience`、`high_air`。它们是带通与 M/S 加权得到的 DSP bus，
不是干净 stem，也不具备 V2 七区的严格互补重建性质。

### 3.2 固定声道合成

忽略安全和最终增益时，核心关系为：

```text
LF = bass_front * bass + front_L + side_front * side
RF = bass_front * bass + front_R - side_front * side

rear_base = side_rear * side + amb_rear * ambience + air_rear * air
LB/RB = decorrelate(rear_base)
        * rear_master
        + bass_rear * bass
        + lowbody_rear * low_body
```

后区再经过 tone softening、rear floor、空间安全、能量匹配和 linked limiter。
Legacy 的方位由四个声道名称隐式决定，音频本身没有对象身份、距离或动态位置元数据。

### 3.3 Legacy binaural

`binaural_renderer.render_4ch_binaural` 把四个声道视为位于前方 ±30°、后方
±135° 的虚拟扬声器，再合成为耳机 stereo。可选距离、高频空气衰减、rear gain、
小房间 RIR 都在 4.0 之后工作。因此它仍然是：

```text
stereo -> fake 4.0 speakers -> binaural
```

此链路适合保持旧作品和测试基线，不应作为新母版格式的抽象。

## 4. V2：stereo 到七区

### 4.1 STFT 与 M/S

`extract_spatial_zones` 使用 2048 点 Hann STFT、512 hop，并定义：

```text
M = 0.5 * (L + R)
S = 0.5 * (L - R)
L = M + S
R = M - S
```

低频 cosine mask 从 M 提取 bass。中心 anchor 同时依据左右相位一致性、幅度平衡、
人声频段 focus 和 `center_anchor` 强度，从非 bass 的 M 中提取。剩余 M 不复制：

```text
residual_mid = M - bass - center
```

S 被互补分成 front side 与三类 field side：

```text
front_side_weight + bed_weight = 1
side_width_mask + rear_mask + air_mask = bed_weight
```

七区因此为：

```text
bass
center_anchor
front_L_residual = residual_mid + front_side
front_R_residual = residual_mid - front_side
side_width
rear_ambience
high_air
```

按左声道对后三个 field 相加、右声道反相相加，可恢复原始 L/R；测试要求 dry
reconstruction 误差低于 -80 dB。这里仍然不是源分离：区内可能同时包含多种乐器。

### 4.2 七区到运行时场景

`build_mixer_scene` 当前执行：

- bass、center、front-L、front-R -> 四个静态 mono `SpatialObject`；
- side、rear、air -> 每区以 `+azimuth/+audio` 和 `-azimuth/-audio` 镜像编码；
- 三组镜像结果相加为一条 AmbiX ACN/SN3D `[W,Y,Z,X]` FOA bed；
- profile、提取设置、参考 RMS 和版本信息写入 scene metadata。

这一步适合渲染，却会抹平三个 field 的独立身份。因此 FOA 是运行时 bed，不是七区
母版的唯一载荷。

## 5. V2 binaural renderer

### 5.1 对象直接声

每个对象依次经过：

1. 距离高频吸收：1 m 以后，6 kHz 以上每米衰减 0.5 dB；
2. 距离增益：`clip(20*log10(1/distance), -18 dB, +6 dB)`；
3. 作者 `gain_db`；
4. `size` 产生能量归一的多条方向 ray；
5. `diffusion` 用等功率方式分配 direct 与 diffuse FOA send；
6. measured SOFA HRIR 的延迟对齐三邻点插值；
7. 可选 listener trajectory 或有 seed 的微头动旋转。

SOFA 是 V2 binaural 的强制依赖。仓库不会回退到 procedural HRTF，也不会把个人
SOFA 文件写入母版包。

### 5.2 DRR、早反射和尾混响

开启房间时，`direct_ratio` 决定直接声与 room send。一般而言：

- 值更高：人声更近、更清楚，但可能重新贴脸；
- 值更低：距离和包围感增加，但辅音、瞬态和中心稳定性更容易下降。

`small-dry` 使用固定六个 early tap，并生成约 0.5 秒的确定性 late FOA field。
`balanced-depth` 使用 6 x 5 x 3 m 几何房间的一阶 image sources：

- 每对象最多六个一阶反射候选；
- 首反射不早于 8 ms；
- 中心对象 room send 额外降低 3 dB；
- late field 在最后一个 early tap 之后 10 ms 开始；
- late field 限制在约 180 Hz–8 kHz，RT60 和电平由 profile 控制。

全局 room level 与对象的 early/late trim 相加。它们是真正影响距离感的生产参数，
不是后置试听 EQ。

### 5.3 FOA、母版响度与输出保护

对象 diffusion、late reverb 和 scene FOA bed 汇合后，通过测得 HRIR 的一阶球谐
投影逐耳解码。最终再执行：

1. front common-field minimum-phase HRTF 音色补偿；
2. 受 peak headroom 限制的 mastered RMS 匹配；
3. 双耳 linked peak limiter。

人声清晰度下降不应只归因于 HRTF。首先要分离检查中心提取、distance、DRR、
early/late send 和 diffusion，再检查 SOFA 个体匹配与 common-field compensation。

## 6. 扬声器 renderer

当前 `QuadSpeakerRenderer` 只实现四个水平扬声器：

- 对象：distance/air -> size rays -> 2D VBAP -> diffusion；
- FOA bed：投影到四个扬声器方向；
- elevation：被投影到水平面并写入 diagnostics；
- 输出：linked limiter 后的四声道 WAV。

当前 speaker layout manifest 强制恰好四个唯一扬声器。2.0、5.1、7.1、5.1.4、
7.1.4 只在新母版规范中冻结目标 ID 和参考几何，尚未由生产 renderer 实现。

CTC 不是 scene renderer。它先取得 binaural target，再反演到四个扬声器，是一个
后级 adapter。

## 7. 推荐的中间层

```text
Stereo
  -> Seven-zone extraction
  -> Spatial Scene Package master
       - 7 independent mono zone assets
       - keyframed author intent
       - room metadata
  -> Render-scene adapter
       - 4 direct objects
       - derived FOA bed from 3 field zones
  -> Binaural renderer | fixed-layout speaker renderer
```

这使一个母版可以重复生成不同 HRTF 的 binaural，也可以映射到不同扬声器布局，
同时保留重新调整 side/rear/air 的能力。完整规范见
[`SPATIAL_SCENE_PACKAGE_V0_1.md`](SPATIAL_SCENE_PACKAGE_V0_1.md)。

## 8. 调优入口与建议顺序

入口分为四级：

1. `run_spatial_mixer.py` 本地混音台：完整七区、room、Extraction Lab 和盲听 A/B；
2. `spatial_mixer_profile/1.0`：完整、可导出、可离线重现的生产参数；
3. `spatial_core_profile/1.0`：十项 compact 参数；
4. CLI/config：renderer、SOFA、room mode、motion、layout 和 legacy compatibility。

一次只改一层，推荐顺序：

1. 固定音量并开启 level match；
2. Solo 七区，先修 center/bass/side 的提取归属；
3. 调前区方位、distance、size；
4. 调 `direct_ratio`，确认人声清晰与距离的平衡；
5. 调 side/rear/air 的 field gain 和角度；
6. 最后调 early level、late level、RT60 与对象 room trim；
7. 换 SOFA 或测试头动；
8. monitor EQ 只用于耳机补偿，不用它掩盖生产 profile 问题。

所有字段、范围和默认值见 [`PARAMETER_REFERENCE.md`](PARAMETER_REFERENCE.md)。
