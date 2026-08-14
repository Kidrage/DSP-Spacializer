# Spatial Scene Package 0.1

状态：项目内 v0.1 母版/交换规范。Schema 标识为
`urn:spatializer:schema:spatial_scene_package:0.1`。

## 1. 规范解决什么问题

当前 `spatial_core_scene/2.0` 已能把对象和 FOA bed 交给 binaural/quad renderer，
但三个 field zone 已被相加，无法再分别调 side、rear、air。本规范把 renderer-neutral
母版放到这一损失发生之前：

```text
7 zone audio + author metadata
  -> Spatial Scene Package master
  -> runtime adapter
  -> SpatialScene(objects + derived FOA)
  -> binaural / speaker renderer
```

FOA 是 scene-based 音频的有效载荷，但不是对象身份、时间轴、作者参数和音频资产的
完整容器，因此不是“中间格式”和“对象格式”的二选一。

## 2. 与沉浸式交付标准的分层关系

本项目采用三层而不是一种文件包打天下：

|层|本项目|行业对照|职责|
|---|---|---|---|
|作者/运行时 scene|`SpatialZones`、`SpatialScene`|DAW/renderer 内部 scene|编辑和实时渲染|
|无损母版/交换|`spatial_scene_package/0.1`|ADM BWF、DAMF|保存音频 essence 与作者元数据|
|分发码流|未来版本|IAB、DD+ JOC、AC-4 等|分帧、压缩、终端传输|

[ITU-R BS.2076](https://www.itu.int/rec/R-REC-BS.2076/) 的 ADM 可以描述
channel、object 与 HOA 等元素；[ITU-R BS.2127](https://www.itu.int/rec/R-REC-BS.2127-1-202311-I/en)
定义面向目标环境的 ADM renderer。Dolby 的官方母版说明同样把
[ADM BWF、DAMF 和 IMF IAB](https://professionalsupport.dolby.com/s/article/Overview-of-Dolby-Atmos-Master-File-Formats)
列为不同母版容器，而 [SMPTE ST 2098-2](https://pub.smpte.org/latest/st2098-2/st2098-2-2022.pdf)
定义的是 IAB bitstream。

因此 v0.1 不尝试实现消费码流，也不宣称兼容 Dolby 编解码器。

## 3. 物理封装

规范包可以是目录，也可以是内容完全相同的标准 ZIP。ZIP 建议使用
`.spatialpkg` 扩展名。

```text
example.spatialpkg/
├── manifest.json
└── audio/
    ├── bass.wav
    ├── center_anchor.wav
    ├── front_L_residual.wav
    ├── front_R_residual.wav
    ├── side_width.wav
    ├── rear_ambience.wav
    └── high_air.wav
```

v0.1 不允许未引用成员、软链接、绝对路径、反斜杠路径或 `..` 路径。ZIP 只是容器，
不会把 manifest 或 audio 额外转码。

## 4. 音频 essence

七个 zone WAV 必须全部满足：

- RIFF/WAVE；
- 48,000 Hz；
- mono；
- IEEE 32-bit float；
- 与 `timebase.frame_count` 等长；
- 每区独立文件且路径唯一；
- 文件字节的 SHA-256 与 manifest 一致。

32-bit float 是为了与当前内部 float32 DSP 无量化往返。v0.1 不允许 44.1/96 kHz、
PCM 24-bit 或不同区不等长；需要这些能力时提升规范版本。

## 5. Manifest 顶层

完整约束以
[`schemas/spatial_scene_package-0.1.schema.json`](../schemas/spatial_scene_package-0.1.schema.json)
为准。

|字段|含义|
|---|---|
|`format`|固定 `spatial_scene_package`|
|`version`|固定 `0.1`|
|`package_id`|小写 `urn:uuid:` 标识|
|`timebase`|固定采样率和全包 frame count|
|`coordinate_system`|固定 listener-relative 极坐标约定|
|`source`|七区提取来源、revision 和源/profile hash|
|`room`|全局 early、late、RT60 作者参数|
|`zones`|严格七个 canonical zone|
|`extensions`|带命名空间的未来扩展对象|

扩展 key 必须是小写、多段命名空间，例如 `org.example.feature`。未知扩展不得改变
核心字段语义；不理解扩展的 renderer 可以忽略它。

## 6. 坐标系

v0.1 只支持以下约定：

```text
reference           = listener
azimuth 0°          = front
positive azimuth    = left
positive elevation  = up
distance unit       = metre
```

不存储 Cartesian 坐标、房间绝对世界坐标或设备坐标。listener/head pose 是 renderer
输入，不烘焙到母版对象位置。

## 7. 七区语义

### 7.1 四个 object

|zone|role|状态字段|
|---|---|---|
|`bass`|`bass`|完整 object keyframe|
|`center_anchor`|`center`|完整 object keyframe|
|`front_L_residual`|`front`|完整 object keyframe|
|`front_R_residual`|`front`|完整 object keyframe|

Object keyframe 必须完整记录：

```text
sample_offset, interpolation,
gain_db, azimuth_deg, elevation_deg, distance_m,
size, diffusion, direct_ratio,
early_reflection_trim_db, late_reverb_trim_db
```

### 7.2 三个 mirrored field

|zone|role|编码规则|
|---|---|---|
|`side_width`|`width`|`mirrored_opposite_polarity`|
|`rear_ambience`|`ambience`|`mirrored_opposite_polarity`|
|`high_air`|`air`|`mirrored_opposite_polarity`|

Field keyframe 记录 `gain_db`、正侧 `azimuth_deg` 和 `elevation_deg`。运行时生成：

```text
ray A = +audio at (+azimuth, elevation)
ray B = -audio at (-azimuth, elevation)
```

两条 ray 可被编码成 FOA/HOA，也可直接交给扬声器 panner；FOA 不作为 v0.1
authoritative asset，避免 side/rear/air 合并后失去可编辑性。

## 8. 关键帧

每个 zone 至少一个关键帧，规则为：

1. 第一帧 `sample_offset == 0`；
2. offset 严格递增且小于 `frame_count`；
3. 每个关键帧保存完整状态，不使用继承或 partial patch；
4. `hold` 保持当前状态到下一关键帧；
5. `linear` 对所有数值状态按 sample 线性插值；
6. 最后一个关键帧的 interpolation 不影响包尾。

当前七区引擎只产生一个 `hold` 静态关键帧。时间轴在 v0.1 中先冻结接口，避免未来
加入自动化时破坏母版结构；当前 renderer 尚未消费多关键帧。

## 9. Room 与 endpoint 参数

Manifest 保存作者意图：全局 early level、late level、RT60，以及 object 的 DRR 和
room trim。以下内容属于 endpoint，不进入包：

- SOFA/HRTF 文件和个人耳形选择；
- head tracking 或 micro-motion seed；
- 耳机频响补偿和 monitor EQ；
- 具体扬声器校准、delay、bass management；
- CTC inverse filter；
- limiter 的运行时 diagnostics。

这保证更换耳机、扬声器或 HRTF 时不需要重做母版。

## 10. 固定输出布局注册表

v0.1 冻结目标 ID 和参考几何，不表示当前代码已实现所有 renderer。方位和高度取
[ITU-R BS.2051](https://www.itu.int/rec/R-REC-BS.2051/en) 允许范围内的中心参考值；
正角为左侧。

|目标 ID|参考声道与位置|
|---|---|
|`binaural`|两耳 endpoint；位置由 SOFA renderer 计算|
|`stereo_2_0`|L +30°，R -30°|
|`quad_4_0_legacy`|FL +30°，FR -30°，RL +135°，RR -135°|
|`surround_5_1`|L/R ±30°，C 0°，Ls/Rs ±110°，LFE|
|`surround_7_1`|L/R ±30°，C 0°，Lss/Rss ±90°，Lrs/Rrs ±135°，LFE|
|`height_5_1_4`|5.1 + top-front ±30°/+45° + top-rear ±110°/+45°|
|`height_7_1_4`|7.1 + top-front ±45°/+45° + top-rear ±135°/+45°|

七区没有独立 LFE essence。所有 bass zone 内容保持 full-range object；`.1` 布局的
LFE 默认静音，endpoint bass management 不属于 scene renderer。不得自动把 bass
低通复制到 LFE，否则可能与播放设备的 bass management 重复。

## 11. Renderer contract

读取 v0.1 包的 renderer/adapter 应按以下顺序工作：

1. 验证 Schema、路径、成员、hash 和 WAV 属性；
2. 恢复七个独立 mono zone；
3. 采样或插值每区关键帧；
4. 四个 object 生成直接对象；
5. 三个 field 生成镜像反相 ray；
6. binaural 路径可把 field ray 编码为 FOA 后逐耳解码；
7. speaker 路径可把 object/field ray 映射到目标固定布局；
8. endpoint 才应用 SOFA、speaker calibration、limiter 和交付编码。

当前运行时代码的适配关系是：

```text
package objects -> SpatialObject
package fields  -> encode_mono_foa twice per field -> FoaBed
objects + bed   -> SpatialScene
```

## 12. 验证接口

```python
from spatial_core import validate_scene_package

info = validate_scene_package("mix.spatialpkg")
print(info.package_id, info.container, info.frame_count, info.zone_names)
```

该接口接受目录或标准 ZIP，只做 conformance validation，不导入、渲染或修改包。
失败时抛出 `ScenePackageError`。

生成一个不进入 Git 的合成示例目录和 ZIP：

```bash
python examples/build_spatial_scene_package_example.py /tmp/spatial-example --zip
```

## 13. 外部格式 adapter seam

v0.1 只保留转换 seam，不添加空实现：

```text
external master <-> interchange adapter <-> spatial_scene_package/0.1
```

未来首个真实 adapter 出现时再定义代码 interface。转换必须报告：可无损映射字段、
降级字段、忽略扩展和目标格式 profile；本版本不实现 ADM BWF、DAMF 或 IAB。

## 14. 演进顺序

1. v0.1：规范、Schema、validator 和生成式示例；
2. v0.2：从七区/mixer profile 导出包，并导入当前 `SpatialScene`；
3. renderer milestone：实现注册表中的固定 2D/3D 布局；
4. v0.3：原生 stems/objects、独立 LFE、HOA bed 和实际关键帧消费；
5. interchange milestone：在真实需求下实现 ADM adapter；
6. distribution milestone：另行定义分帧、压缩、错误恢复和终端能力协商。

母版版本和消费码流版本必须独立演进。
