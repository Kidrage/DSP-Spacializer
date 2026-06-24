# Phase 5A Calibration Evidence — Standard Recording Format

Each listening session produces one evidence block per evaluated track.
All blocks are appended to this file in chronological order.

---

## Evidence Block Format

```
### <track_name> | <date>

**System flags** (from 听评证据表): <comma-separated>

**T/F Grid**: `<flag1_flag2_...>` = `<T/F sequence>`

| Flag (system) | T/F | Listener interpretation |
|---------------|-----|------------------------|
| ...           | T/F | ...                    |

**Additional observations** (tags NOT in system flags):
- `<tag>`: `<description>`
- ...

**Engineering notes** (Claude fills this):
- <root cause analysis>
- <metric gap / safety over-attenuation / threshold miscue>
- ...

**Phase 5A action items**:
- [ ] <action> → <target module>
```

---

## Evidence Records

### Starboy | 2026-06-22

**System flags**: `highs_too_harsh`, `lowmid_muddy`, `phase_weird`, `bass_too_light`

**T/F Grid**: `harsh_mud_phase_bass` = `FFTT`

| Flag (system) | T/F | Listener interpretation |
|---------------|-----|------------------------|
| `highs_too_harsh` | **F** | 不是刺耳——开头pad高频被cutoff了，高频是**缺失**而非过量。spatial_safety 的 rear_air_gain 衰减过度 |
| `lowmid_muddy` | **F** | 不是浑浊——中低频**不均匀/缺失**，方向与系统判断相反 |
| `phase_weird` | **T** | 确认有相位问题，说不出的难受 |
| `bass_too_light` | **T** | 底鼓attack没了，确认低频不足 |

**Additional observations** (not in system flags):
- `transient_smeared` (system=0.00, safe): 底鼓attack丢失，**指标漏报**。transient 测量公式可能遗漏 80-150Hz 频段
- `vocal_presence_degraded`: 人声presence感觉变差，疑似 rear_highmid_gain / guard_scale 副作用影响前方清晰度
- ✅ positive: 带混响的配器和人声空间感明显，amb_rear 路由方向正确

**Engineering notes**:
1. **safety 衰减过度**：harshness=0.56 触发 spatial_safety → rear_air_gain=0.95, rear_highmid_gain=0.95。问题不在阈值（0.56 确实偏高），而在衰减系数——对 pad-heavy 流行曲应该更温和。`spatial_safety.py:404-407` 的 gain 公式需要检查
2. **transient 指标漏报**：`transient_smear_score=0.00` 但底鼓 attack 丢失。`compute_quality_metrics()` 的 transient 测量用 `transient_density(rear, sr)`，该函数在 `streaming_analyzer.py:15-27` 用 full-band RMS 帧差检测——底鼓的 50-100Hz 能量峰可能被全频段 RMS 平均化了。需要增加分频段 transient 测量
3. **mud 指标方向错误**：系统报 mud=0.72（高），但实际是中低频**不足**。说明 `low_mid_mud_score` 的测量（rear 120-500Hz / front 120-500Hz）对 pad-heavy 编曲不可靠——pad 本身占据 120-500Hz 频段，后方映射后比值高不等于「浑浊」
4. **phase_weird 确认**：phase_risk=0.55，系统阈值 0.42。对 Starboy 这类立体声宽度较大的素材，decorrelation 偏高会导致真实相位问题。阈值 0.42 对这类素材是合理的

**Phase 5A action items**:
- [ ] 检查 `spatial_safety.py:404-407` harshness gain 公式 —— 考虑改为渐进衰减而非一次性到达最低值
- [ ] 增加分频段 transient 测量（至少 bass + mid 分别测） —— `spatial_safety.py:compute_quality_metrics()`
- [ ] Starboy 的 mud 假阳性 —— 记入 `lowmid_mud_score` 已知盲区，后续收集更多 pad-heavy 素材再决定是否改公式
