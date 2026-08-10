#!/usr/bin/env python3
"""Generate the complete Phase 5A listener evidence table from a manifest."""

import argparse
import json
from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = WORKSPACE_DIR / "Output-DSP" / "batch_manifest.json"
DEFAULT_OUTPUT = WORKSPACE_DIR / "Output-DSP" / "听评证据表_Phase5A.md"

TAGS = [
    "good_balance",
    "highs_too_harsh",
    "lowmid_muddy",
    "vocal_leaks_to_rear",
    "phase_weird",
    "transient_smeared",
    "rear_too_weak",
    "rear_too_strong",
    "bass_too_light",
    "bass_too_boomy",
    "space_not_wide_enough",
    "space_too_wide",
    "rear_too_dark",
]


def load_manifest(path):
    with Path(path).open(encoding="utf-8") as stream:
        manifest = json.load(stream)
    if not isinstance(manifest, list):
        raise ValueError("batch manifest must contain a JSON list")
    return manifest


def guess_flags(qm):
    """Suggest listening tags from objective metrics; these are not verdicts."""
    flags = []
    if qm.get("high_harshness_score", 0) > 0.45:
        flags.append("highs_too_harsh")
    if qm.get("low_mid_mud_score", 0) > 0.45:
        flags.append("lowmid_muddy")
    if qm.get("rear_vocal_leakage_score", 0) > 0.28:
        flags.append("vocal_leaks_to_rear")
    if qm.get("phase_correlation_risk", 0) > 0.42:
        flags.append("phase_weird")
    if qm.get("transient_smear_score", 0) > 0.30:
        flags.append("transient_smeared")
    if qm.get("rear_front_db", 0) < -9.0:
        flags.append("rear_too_weak")
    if qm.get("rear_front_db", 0) > -3.0:
        flags.append("rear_too_strong")
    if qm.get("sub150_retention_score", 0) < 0.50:
        flags.append("bass_too_light")
    if qm.get("spatial_excess_score", 0) > 0.55:
        flags.append("space_too_wide")
    return flags


def render_table(manifest):
    lines = [
        "# 听评证据表 — Phase 5A Threshold Calibration",
        "",
        f"> 覆盖范围：当前完整曲库，共 **{len(manifest)} 首**。系统标记只是听评提示，不代表主观结论。",
        "> 监听环境（填）：`4.0 speakers` / `binaural headphones` / `CTC 4ch`；设备/房间备注：__________",
        "> **用法**：逐首听，在对应行的 **听感标签** 列填你真实感知到的标签名。",
        "> 若指标数值看似安全但听感已有问题，请在 **感知边界备注** 中写明数值与感受。",
        "",
        "> **可用标签**：",
    ]
    lines.extend(f"> - `{tag}`" for tag in TAGS)
    lines.extend([
        "",
        "| # | 曲目 | 后/前 dB | harsh | mud | vocal | phase | trans | bass_ret | sp_exc | 系统标记 | 你的标签（填） | 感知边界备注（填） |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|",
    ])

    def high(value, threshold, suffix=""):
        return f"**{value:.2f}{suffix}**" if value >= threshold else f"{value:.2f}"

    def low(value, threshold, suffix=""):
        return f"**{value:.2f}{suffix}**" if value <= threshold else f"{value:.2f}"

    for index, item in enumerate(manifest, 1):
        track = Path(item.get("input_file", "?")).stem.replace("|", "\\|")
        qm = item.get("quality_metrics", {})
        rear_front_db = qm.get("rear_front_db", item.get("rear_to_front_db", 0))
        metrics = {
            "harsh": qm.get("high_harshness_score", 0),
            "mud": qm.get("low_mid_mud_score", 0),
            "vocal": qm.get("rear_vocal_leakage_score", 0),
            "phase": qm.get("phase_correlation_risk", 0),
            "trans": qm.get("transient_smear_score", 0),
            "bass": qm.get("sub150_retention_score", 0),
            "excess": qm.get("spatial_excess_score", 0),
        }
        flags = guess_flags({**qm, "rear_front_db": rear_front_db})
        system_flags = " ".join(f"`{flag}`" for flag in flags) or "—"
        if item.get("auto_acoustic_info", {}).get("telephone_risk"):
            system_flags = f"📞 {system_flags}"
        rear_text = f"**{rear_front_db:.1f}**" if rear_front_db > -3 or rear_front_db < -9 else f"{rear_front_db:.1f}"
        lines.append(
            f"| {index} | {track} | {rear_text} | "
            f"{high(metrics['harsh'], 0.45, '🔥' if metrics['harsh'] >= 0.80 else '')} | "
            f"{high(metrics['mud'], 0.45)} | {high(metrics['vocal'], 0.28)} | "
            f"{high(metrics['phase'], 0.42)} | {high(metrics['trans'], 0.30)} | "
            f"{low(metrics['bass'], 0.50, '⬇')} | {high(metrics['excess'], 0.55)} | "
            f"{system_flags} |  |  |"
        )

    lines.extend([
        "",
        "---",
        "",
        "### 填写说明",
        "",
        "1. 只记录真实听感；系统标记用于提醒重点监听位置。",
        "2. 没有问题可填 `good_balance`，或留空。",
        "3. 同一问题积累至少 3 条一致证据后，才进入低置信度阈值校准。",
        "4. 请同时注明监听方式（4.0 音箱、耳机 binaural 或 CTC），不同模式不混用阈值。",
        "",
    ])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    table = render_table(load_manifest(args.manifest))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(table, encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
