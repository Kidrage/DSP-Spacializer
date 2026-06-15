# DSP-Spacializer auto_acoustic 闭环改造阶段性报告

日期：2026-06-15

## 当前结论

当前 `auto_acoustic` 已经从固定 preset 选择，推进到“基于歌曲分析特征动态生成空间化参数”的阶段。它已经具备可用的非 AI stereo-to-4.0 空间化核心：

- stereo 输入分解为 bass、low body、front core、side width、rear ambience、high air 等空间功能层；
- `streaming_analyzer.py` 提取宽度、中心风险、低频集中度、高频扩散、瞬态、频段相干等特征；
- `presets.py` 根据特征动态生成 `auto_acoustic` routing；
- `renderer_4ch.py` 输出 4.0 spatial bed；
- binaural 模式支持 4.0 虚拟扬声器耳机监听；
- 新增 crosstalk cancellation，可以把 binaural 目标反解到 4.0 speaker feeds；
- 新增 room RIR 后再 CTC 的 4ch 输出，用于测试“binaural + RIR + 4.0 CTC”玩法。

但当前算法还不是完整的“全自动空间化”。它更准确地说是：

```text
人工听感经验 -> 写成规则 -> 自动套用到歌曲
```

它能够自动生成参数，但还不能自动发现“哪里不好听”、自动定位问题原因、再自动修正。因此下一阶段重点不应继续堆效果，而应建立闭环：

```text
analysis -> initial preset -> render -> quality metrics -> refine preset -> final render
```

## 已完成的核心改动

### 1. auto_acoustic 后方增强更大胆

此前后方参数偏保守，导致空间化听感不够明显。当前已提高以下参数的基础量和上限：

- `side_rear`
- `amb_rear`
- `air_rear`
- `rear_master`
- `rear_floor_ratio`
- `max_rear_makeup`

并新增 `adaptive_intensity`，根据 `side_material`、`diffuse_energy`、`narrow_score` 和 `vocal_risk` 连续控制空间化强度。

### 2. rear enhancement 从硬阈值改为连续衰减

旧逻辑：

```python
if rear_enhancement and vocal_risk < 0.70:
```

新逻辑：

```python
rear_enhancement_amount = (0.90 - min(vocal_risk, 0.90)) / 0.90
```

这让后方增强不再因为人声风险略高就完全关闭，而是根据风险连续减少。

### 3. 低频核心层补偿

新增 `bass_gain`，用于补偿 150Hz 以下量感不足的问题。当前策略是优先增强低频核心层，而不是盲目提高后方低频：

- `bass_gain` 提升 sub/低频主体感；
- `bass_quad` 小幅提高，增加低频包围但避免低频发散；
- `lowbody_rear` 保持作为后方厚度，而不是替代低频管理。

### 4. binaural CTC 输出

新增：

- `render_binaural_to_ctc_4ch(...)`
- `make_4ch_to_ear_ir(...)`

可以把 binaural 双耳目标反解到 4.0 扬声器输出：

```text
4ch spatializer -> binaural target -> CTC inverse -> 4ch speaker feeds
```

同时支持：

```text
4ch spatializer -> binaural target -> room RIR -> CTC inverse -> 4ch speaker feeds
```

对应输出：

- `*_binaural_4p0.wav`
- `*_binaural_ctc_4ch.wav`
- `*_binaural_4p0_room_rir.wav`
- `*_binaural_ctc_4ch_room_rir.wav`

## 当前不足

### 1. 还不是闭环自动化

系统目前只会根据输入特征生成参数，不会自动判断渲染结果是否达标。例如：

- 后方不够明显，需要用户听出来；
- 低频不足，需要用户指出；
- 人声后漏，需要用户反馈；
- 高频刺、低中频浑、瞬态散，也缺少自动指标。

也就是说，当前仍然依赖人工发现问题，再把问题写回规则。

### 2. 缺少质量指标

当前 diagnostics 主要记录分析特征、routing、rear/front RMS、peak 等基础信息。下一阶段需要增加面向听感问题的指标：

- `rear_presence_score`：后方存在感是否足够；
- `spatial_contrast_score`：空间化前后是否有足够差异；
- `bass_retention_score`：150Hz 以下是否被削弱；
- `vocal_leakage_score`：人声/中心内容是否泄漏到后方；
- `lowmid_mud_score`：120-500Hz 后方是否过浑；
- `harshness_score`：2-8kHz 后方是否过刺；
- `phase_risk_score`：相位/相关性风险；
- `transient_smear_score`：瞬态是否被拉散。

### 3. auto_acoustic 参数体系还偏经验公式

虽然已改成连续映射，但仍是人工权重组合。更完善的结构应该输出几个明确的控制维度：

- `spatial_intensity`
- `rear_presence`
- `front_stability`
- `bass_pressure`
- `air_space`
- `vocal_safety`
- `transient_safety`

然后由这些中间控制量统一映射到 routing 参数，避免每个参数各自散落一套经验公式。

### 4. 缺少用户偏好记忆

空间化不是纯客观任务。用户可能偏好：

- 更明显的后方；
- 更稳的人声；
- 更厚的低频；
- 更暗、更柔和的后方；
- 更亮、更打开的空间。

当前系统没有保存这些偏好，也不会把多次反馈折算成长期权重。

## 下一阶段改造计划

### 阶段 1：质量指标层

新增 `quality_metrics.py`，输入原始 stereo、初始 4ch 输出、routing、analysis，输出质量指标。

建议先实现这些指标：

```text
rear_front_ratio
rear_presence_score
bass_retention_score
vocal_leakage_score
lowmid_mud_score
harshness_score
phase_risk_score
spatial_contrast_score
```

目标不是一次做到 psychoacoustic 完美，而是先让系统能发现明显问题。

### 阶段 2：自动微调层

新增 `auto_refine.py`，根据 `quality_metrics` 对 routing 做一轮或两轮微调。

初版规则：

- 后方不足：提高 `rear_floor_ratio`、`side_rear`、`rear_master`；
- 低频不足：提高 `bass_gain`，少量提高 `bass_quad`；
- 人声泄漏：降低 `side_rear`、`amb_rear`、`rear_highmid_gain`，提高 `guard_scale`；
- 低中频浑：降低 `lowbody_rear` 和后方 120-500Hz 送量；
- 高频刺：降低 `air_rear`、`rear_air_gain`、`rear_highmid_gain`；
- 相位风险高：降低 `decorrelation` 或侧向后送。

目标流程：

```text
analysis
-> generate_auto_acoustic_preset
-> render initial
-> quality_metrics
-> refine routing
-> render final
-> diagnostics 保存 before/after
```

### 阶段 3：偏好记忆层

新增一个本地偏好文件，例如：

```text
config/listener_preference.yml
```

记录用户长期倾向：

```yaml
spatial_intensity_bias: 0.10
rear_presence_bias: 0.08
bass_pressure_bias: 0.06
vocal_safety_bias: 0.00
air_brightness_bias: -0.04
```

人工听感反馈可以转成结构化事件：

```yaml
- song: Drake.mp3
  feedback:
    - rear_too_weak
    - bass_too_light
  accepted_adjustments:
    side_rear: 0.08
    bass_gain: 0.06
```

这不是神经网络 AI，而是可解释的机械学习/偏好学习。

### 阶段 4：批量 A/B 评估工具

新增批量评估脚本：

```text
run_spatializer.py --preset-mode auto_acoustic --auto-refine --output-mode both
```

并生成汇总表：

```text
song
rear_presence_score
bass_retention_score
vocal_leakage_score
phase_risk_score
refine_actions
rear_front_db
peak
```

这样可以快速筛出“不好听风险最高”的歌曲。

## 人工需要做的事

### 1. 提供听感标签

人工最重要的工作不是直接改参数，而是给系统标注问题类型。建议使用固定标签：

```text
rear_too_weak
rear_too_strong
bass_too_light
bass_too_boomy
vocal_leaks_to_rear
vocal_not_clear
highs_too_harsh
rear_too_dark
lowmid_muddy
space_not_wide_enough
phase_weird
transient_smeared
```

### 2. 给每首测试歌选优先级

不是每首歌都要同样空间化。人工需要判断歌曲目标：

```text
vocal_safe
more_spatial
bass_pressure
cinematic_depth
club_wide
natural_room
```

这决定系统修正时是更大胆还是更保守。

### 3. 维护参考曲库

建议维护 10-20 首固定 reference：

- 人声流行；
- rap / bass-heavy；
- EDM；
- 老歌窄声场；
- live / hall；
- orchestral / cinematic；
- acoustic；
- 高频很亮的歌；
- 低频很重的歌；
- 已知容易翻车的歌。

每次算法改动都跑这一组，避免只对单首歌变好。

### 4. 做最终听感确认

自动指标只能发现问题，不能完全替代听感。人工最终需要确认：

- 人声是否仍然稳；
- 后方是否有空间感但不抢；
- 低频是否够厚但不糊；
- 高频是否有空气感但不刺；
- binaural / CTC 是否只是玩法还是可交付输出。

## 建议的下一步

下一步不要继续手动调 `side_rear`、`rear_floor_ratio` 这类单点参数。建议先实现：

```text
quality_metrics.py
auto_refine.py
diagnostics before/after 输出
```

这会把系统从“主观规则自动化”推进到“可解释闭环自动化”。完成后，`auto_acoustic` 才能开始自己发现：

- 哪首歌后方不够；
- 哪首歌 bass 被吃；
- 哪首歌人声风险高；
- 哪首歌空间化过度。

这一步是从 demo 走向稳定产品的关键分水岭。
