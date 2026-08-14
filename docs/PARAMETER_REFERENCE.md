# DSP-Spacializer 可控参数参考

本表以当前代码校验范围为准。`生产` 表示参数写入 profile 并影响离线渲染；`监听`
表示只影响校准台预听；`兼容` 表示仅属于冻结 legacy 链路。

## 1. 七区概览

|区|运行时类型|默认位置/电平|主要听感职责|
|---|---|---|---|
|`bass`|object|0°, 0 dB|低频中心稳定、重量|
|`center_anchor`|object|0°, 0 dB|人声与中心主体|
|`front_L_residual`|object|+35°, 0 dB|左前剩余内容|
|`front_R_residual`|object|-35°, 0 dB|右前剩余内容|
|`side_width`|mirrored field|±75°, -12.0412 dB|宽度与侧向差分|
|`rear_ambience`|mirrored field|±135°, -14.8945 dB|后方 ambience|
|`high_air`|mirrored field|±110° / +35°, -18.4164 dB|上方空气感|

正方位角在本项目中表示左侧。

## 2. Object zone 参数

适用于 bass、center、front-L、front-R，属于生产参数。

|字段|默认|范围|作用与风险|
|---|---:|---:|---|
|`gain_db`|0 dB|-24…+12 dB|区电平；先用 level match 判断，避免把响度误认为清晰|
|`azimuth_deg`|见上表|-180…180°|左右/前后方向；前区不对称会偏移中心|
|`elevation_deg`|0°|-90…90°|高度；当前 quad 会投影到水平面|
|`distance_m`|1.60 m|0.1…10 m|同时改变距离增益和 6 kHz 以上空气吸收|
|`size`|0.05；center 为 0|0…1|方向 ray 展宽；过大时中心和辅音变散|
|`diffusion`|0|0…1|direct 与 diffuse FOA 的等功率分配|
|`direct_ratio`|0.78|0…1|DRR；降低可减贴脸，但会损伤瞬态和人声清晰|
|`early_reflection_trim_db`|0 dB|-18…+12 dB|对象相对全局 early level 的 trim|
|`late_reverb_trim_db`|0 dB|-18…+12 dB|对象相对全局 late level 的 trim|

center 不建议先用 gain 或 EQ 修清晰度。应先检查 `center_anchor`、distance、
`direct_ratio`、early trim 与 late trim。

## 3. FOA field zone 参数

适用于 side、rear、air，属于生产参数。

|字段|默认|范围|作用与风险|
|---|---:|---:|---|
|`gain_db`|见七区表|-120…+6 dB|场区 send；-120 dB 代表近似关闭|
|`azimuth_deg`|75° / 135° / 110°|0…180°|一侧参考方位，renderer 自动生成反向镜像|
|`elevation_deg`|0° / 0° / 35°|-90…90°|场区高度|

当前 field 不是普通复制：第二个镜像方向使用相反音频极性，以保留原 stereo side
信号的方向关系。三个 field 在运行时相加成 FOA bed。

## 4. Room 参数

|字段|默认|范围|作用|
|---|---:|---:|---|
|`early_reflection_level_db`|-21 dB|-40…-10 dB|`balanced-depth` 首次/一阶反射的全局参考电平|
|`late_reverb_level_db`|-27 dB|-40…-12 dB|late FOA field 电平|
|`late_rt60_s`|0.35 s|0.15…1.20 s|尾场衰减时间|

`room_profile` 不是 profile 数值字段，而是 renderer 模式：

- `off`：无 early/late room；
- `small-dry`：固定六 tap 与 0.30 s legacy-compatible tail；
- `balanced-depth`：几何一阶反射、对象 trim、可调 late level/RT60。

## 5. Extraction Lab 参数

这些生产参数改变 stereo 如何被互补拆成七区。改变后应重新 Solo 每区并确认 dry
reconstruction，而不是只听最终 binaural。

|字段|默认|范围|作用|
|---|---:|---:|---|
|`bass_low_hz`|80 Hz|30…250 Hz|bass mask 低端|
|`bass_high_hz`|160 Hz|60…400 Hz|bass mask 高端；必须高于 low|
|`center_anchor`|0.80|0…1|相干中心提取强度|
|`center_focus_low_hz`|900 Hz|200…3000 Hz|中心 focus 起点|
|`center_focus_high_hz`|2500 Hz|800…8000 Hz|中心 focus 终点；必须高于 low|
|`center_focus_floor`|0.25|0…1|高频中心提取保留量|
|`front_side_weight_low`|0.90|0…1|低/中频 S 留在 front residual 的比例上限|
|`front_side_weight_high`|0.75|0…1|高频 S 留在 front residual 的比例下限|
|`rear_strength`|0.55|0…1|field side 内 rear preference|
|`rear_low_hz`|1500 Hz|300…6000 Hz|rear preference 起点|
|`rear_high_hz`|3000 Hz|800…10000 Hz|rear preference 终点；必须高于 low|
|`air_low_hz`|5500 Hz|2000…12000 Hz|air preference 起点|
|`air_high_hz`|9000 Hz|4000…20000 Hz|air preference 终点；必须高于 low|

额外约束：`front_side_weight_low >= front_side_weight_high`。

## 6. Compact Spatial Core profile

`spatial_core_profile/1.0` 是完整 mixer profile 的简化入口。

|字段|默认|范围|映射|
|---|---:|---:|---|
|`center_anchor`|0.80|0…1|中心提取|
|`front_distance_m`|1.60 m|0.5…4 m|四个 object 的统一 distance|
|`front_width_deg`|35°|15…75°|左右 front residual 方位|
|`bed_width_gain`|0.25|0…1|side field 线性增益|
|`bed_rear_gain`|0.18|0…1|rear field 线性增益|
|`bed_air_gain`|0.12|0…1|air field 线性增益|
|`direct_ratio`|0.78|0.30…0.95|四个 object 的统一 DRR|
|`early_reflection_level_db`|-21 dB|-40…-10 dB|全局 early|
|`late_reverb_level_db`|-27 dB|-40…-12 dB|全局 late|
|`late_rt60_s`|0.35 s|0.15…1.20 s|late RT60|

`--spatial-profile` 与 `--mixer-profile` 互斥。需要个人精调时使用完整 mixer profile。

## 7. Monitor 与 audition

以下参数只影响校准台 preview，不进入导出的 mixer profile 或母版。

|监听字段|默认|范围|
|---|---:|---:|
|`output_gain_db`|0 dB|-24…+12 dB|
|`balance_db`|0 dB|-6…+6 dB|
|`low_db`|0 dB|-12…+12 dB|
|`low_mid_db`|0 dB|-12…+12 dB|
|`mid_db`|0 dB|-12…+12 dB|
|`presence_db`|0 dB|-12…+12 dB|
|`air_db`|0 dB|-12…+12 dB|

EQ 锚点约为 20、120、500、1800、5000、12000 Hz 和 Nyquist。试听状态包括：

- `muted`：被静音区名集合；
- `soloed`：Solo 区名集合；
- `level_match`：A/B 响度匹配，默认开启。

## 8. V2 工作流开关

|入口|取值/默认|说明|
|---|---|---|
|`--engine`|`legacy` / `spatial-v2`；默认 legacy|选择架构|
|`--output-mode`|`4ch` / `binaural` / `both`|V2 默认 binaural|
|`--sofa`|路径|V2 binaural/CTC 强制 measured SOFA|
|`--scene-manifest`|路径|读取 `spatial_core_scene/2.0`|
|`--export-scene`|路径|写当前运行时 scene 与外部 WAV|
|`--listener-trajectory`|路径|真实/预制 listener pose 时间轴|
|`--micro-motion`|关闭|模拟 yaw ±5°、pitch ±3°|
|`--motion-seed`|0|微头动可重复 seed|
|`--room-profile`|见 Room|mixer profile 默认 balanced-depth|
|`--spatial-profile`|路径|compact profile|
|`--mixer-profile`|路径|完整七区 profile|
|`--speaker-layout`|路径|当前只接受四个唯一扬声器|
|`--export-binaural-ctc-4ch`|关闭|binaural target 后接 CTC adapter|

## 9. Legacy routing 参数

Legacy 没有统一的严格 JSON schema。下表范围是当前 auto/candidate 代码中 clamp 的并集，
不是对外长期格式保证。

|字段|当前代码范围|作用|
|---|---:|---|
|`side_front`|0.38…0.62|side bus 注入前区|
|`side_rear`|0.56…1.40|side bus 注入后区|
|`amb_rear`|0.32…1.08|ambience 注入后区|
|`air_rear`|0.09…0.46|air 注入后区|
|`rear_master`|0.84…1.24|后区总量|
|`decorrelation`|0.16…0.46|后区 delay/all-pass 强度|
|`rear_floor_ratio`|0.075…0.30|后区能量下限|
|`max_rear_makeup`|1.0…8.0|rear floor 最大补偿|
|`guard_scale`|0.55…1.55|空间安全保护强度|
|`bass_gain`|1.02…1.24|bass bus 增益|
|`bass_quad`|0.055…0.18|bass 向后区分配量|
|`lowbody_rear`|0.12…0.60|low-body 向后区分配量|
|`rear_air_gain`|0.08…0.58|后区高频 tone shaping|
|`rear_highmid_gain`|0.18…0.88|后区高中频 tone shaping|

Legacy binaural/config 的当前默认值：

|字段|默认|
|---|---:|
|front/rear virtual azimuth|30° / 135°|
|full rear gain|+1.5 dB|
|front/rear/reference distance|1.2 / 0.95 / 1.0 m|
|air absorption|0.5 dB/m|
|room RT60 / length / late start|0.30 / 0.50 / 0.03 s|
|CTC regularization / IR length / peak|0.08 / 4096 / 0.98|

## 10. 安全调优顺序

1. 关闭 monitor EQ，开启 level match；
2. Solo `center_anchor`，调中心提取，不先加 presence；
3. Solo bass 与两个 front residual，确认没有空洞或重复；
4. Solo side/rear/air，调 extraction 后再调它们的 field gain；
5. 调 object distance/azimuth/size；
6. 只在上述稳定后降低 `direct_ratio`；
7. 逐步加入 early reflection，再加入 late reverb；
8. 更换 SOFA/头动验证外化是否稳定；
9. 最后恢复个人 monitor EQ，盲听多个曲目并保存 profile hash。
