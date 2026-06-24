# Session Changelog — 2026-06-22/23

> 从 `65d65d5` (feat/dsp-feedback-loop-s1) 出发，实现 auto_acoustic 闭环精炼 + Phase 5A 阈值校准系统。

---

## 新增文件

| 文件 | 阶段 | 作用 |
|------|------|------|
| `auto_refine.py` | Phase 2 | 闭环精炼引擎。8 条确定性规则，从 `config/refine_thresholds.yml` 加载阈值，生成结构化 `actions` 记录 |
| `threshold_calibrator.py` | Phase 5A | 阈值校准器。4 个 API：`collect_threshold_evidence` / `suggest_threshold_calibration` / `apply_threshold_calibration` / `explain_threshold_changes`。含 JSONL 历史记录 + YAML 持久化 |
| `config/quality_thresholds.yml` | 5A-1 | 安全质量阈值配置（从 `spatial_safety.py` 的 `DEFAULT_QUALITY_THRESHOLDS` 提取为显式 YAML） |
| `config/refine_thresholds.yml` | 5A-1 | 精炼触发阈值配置（从 `auto_refine.py` 硬编码提取） |
| `config/listener_threshold_calibration.yml` | 5A-3 | 监听者阈值校准文件（空模板，待耳朵填充） |
| `config/calibration_evidence.md` | 5A | Phase 5A 证据记录标准格式 + Starboy 首条记录 |
| `scripts/make_evidence_table.py` | 5A | 从 `batch_manifest.json` 自动生成听评证据表 |
| `tests/test_threshold_calibrator.py` | 5A-7 | 10 个校准器测试（harshness/vocal/phase/rear/bass/泥感） |

## 修改文件

| 文件 | 变更 |
|------|------|
| `run_spatializer.py` | +`auto_refine` 导入；+闭环精炼回路（2 轮 + 过冲保护）；+4 个 CLI 标志（`--auto-acoustic-refine` / `--no-auto-acoustic-refine` / `--auto-acoustic-refine-passes` / `--auto-acoustic-refine-max-step`）；+诊断字段（initial/final routing + metrics + actions） |
| `spatial_safety.py` | +`yaml` 导入；+`_load_yaml_or_json()` 通用加载器；重构 `load_quality_thresholds()` 为 4 层合并（built-in → YAML config → path override → listener calibration）；+`_merge_threshold_dicts()`；+`_apply_calibration_to_thresholds()` |
| `auto_refine.py` | 阈值从硬编码改为 `_load_refine_thresholds()` 从 `config/refine_thresholds.yml` 加载 |
| `config_center.py` | +3 个闭环开关：`AUTO_ACOUSTIC_ENABLE_CLOSED_LOOP=True`、`AUTO_ACOUSTIC_REFINE_PASSES=2`、`AUTO_ACOUSTIC_REFINE_MAX_STEP=1.0` |
| `HANDOFF_auto_acoustic_closed_loop_upgrade.md` | Phase 5 完全改写为 5A+5B 两层设计（原 preference memory → listener calibration + preference bias） |
| `README.md` | 修 316 字符长行 |

## 当前管线（完成状态）

```
MP3加载 → 48kHz → 分析(2s) → auto_acoustic生成preset → layer_router
→ 渲染4ch → spatial_safety → 质量测量(pre-master)
        ↓
   ┌─ 闭环精炼（2轮，仅auto_acoustic）─────────────────┐
   │  检测8项指标 → 小幅调参 → 重新渲染+safety+测量      │
   │  过冲保护：spatial_excess涨>0.2 或 harsh涨>0.3     │
   │            或 mud涨>0.3 → revert + 记录             │
   └──────────────────────────────────────────────────┘
        ↓
→ energy_match → limiter → WAV导出 + diagnostics JSON
   (含 initial/final routing + metrics + refine_actions)
```

## 8 条精炼规则速查

| 规则 | 检测指标 | 触发条件 | 动作 |
|------|---------|---------|------|
| `rear_presence_low` | rear_front_db | < -7.5 dB | +rear_floor_ratio, +side_rear, +rear_master |
| `bass_retention_low` | sub150_retention | < 0.55 | +bass_gain, +bass_quad(if phase safe) |
| `vocal_leakage_high` | vocal_leakage | > 0.26 | -side_rear, -amb_rear, -rear_highmid_gain, +guard_scale |
| `lowmid_mud_high` | low_mid_mud | > 0.42 | -lowbody_rear |
| `harshness_high` | harshness | > 0.42 | -air_rear, -rear_air_gain, -rear_highmid_gain |
| `phase_risk_high` | phase_risk | > 0.42 | -decorrelation, -side_rear |
| `transient_smear_high` | transient_smear | > 0.28 | -decorrelation, +guard_scale |
| `spatial_excess_high` | spatial_excess | > 0.50 | -side_rear, -amb_rear, -rear_master |

## Phase 5A 阈值校准流程

```
听评反馈(标签+边界备注) → collect_threshold_evidence()
→ suggest_threshold_calibration() → 检查证据数≥3
→ apply_threshold_calibration() → 合并到运行时阈值
→ explain_threshold_changes() → 可解释的变更记录
→ write_calibration_history_entry() → JSONL 历史
→ save_calibration_file() → listener_threshold_calibration.yml
```

## 曲库变更 (2026-06-23)

当前曲库共 37 首音频。原缺失的 11 首已于 2026-06-23 在当前工作区完成闭环精炼渲染（2 轮）：
All I Need, Architects, Defiledmp3, Foretaste, Heat, High Hopes, Kanye West, Led Zeppelin, MerryChristmas, Sleep Token - The Summoning, Them Changes

## 测试

29 passed, 0 failed（含阈值校准与四声道 fold-down 相位风险回归测试）

完整产物：37 个 48 kHz/4ch/float WAV、37 个 diagnostics JSON、完整 `batch_manifest.json`。

相位指标已升级到 v2：风险计算和阈值分类改用电平归一化的四声道 fold-down，避免把 legacy 1/4 平均固有的约 -6 dB 当作相位失败。历史 diagnostics 已由 `scripts/migrate_phase_metrics.py` 迁移。

## 待完成

- Phase 5B: listener_preference.yml + preference bias 应用到 profile suggestion
- Starboy 证据中发现的 transient 指标漏报（需增加分频段测量）
- spatial_safety harshness gain 公式审查（对 pad-heavy 流行曲衰减过度）
