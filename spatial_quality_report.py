"""Markdown reporting utilities for batch spatial diagnostics."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

SAFETY_ACTION_KEYS = [
    "rear_low_mid_gain",
    "rear_mid_gain",
    "rear_high_mid_gain",
    "rear_air_gain",
    "rear_master_gain",
]


def _to_float(value, default=0.0):
    try:
        if value in (None, ""):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def load_batch_metrics(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _count_status(rows):
    counts = Counter((row.get("overall_status_after") or "unknown") for row in rows)
    return counts.get("pass", 0), counts.get("warn", 0), counts.get("fail", 0)


def _common_risks(rows):
    counter = Counter()
    for row in rows:
        raw = row.get("risk_items_after", "")
        for item in raw.split(";"):
            item = item.strip()
            if item:
                counter[item] += 1
    return counter


def _action_summary(rows):
    counter = Counter()
    for row in rows:
        raw = row.get("safety_actions", "")
        for part in raw.split(";"):
            if "=" not in part:
                continue
            key, value = part.split("=", 1)
            key = key.strip()
            if key in SAFETY_ACTION_KEYS and _to_float(value, 1.0) < 0.995:
                counter[key] += 1
    return counter


def _recommendations(rows, common_risks, action_counts):
    total = max(len(rows), 1)
    recs = []
    if common_risks.get("rear_vocal_leakage_score", 0) / total >= 0.30:
        recs.append("后方人声泄漏普遍偏高：建议优先检查 rear mid/high-mid 路由和 center-like material 抑制。")
    if common_risks.get("low_mid_mud_score", 0) / total >= 0.30:
        recs.append("低中频后方浑浊普遍偏高：建议收紧 rear low-mid bus 或调低对应 safety 阈值。")
    if common_risks.get("high_harshness_score", 0) / total >= 0.30:
        recs.append("高频后方刺耳普遍偏高：建议检查 rear air/high-mid 的增益与滤波。")
    over_count = sum(1 for row in rows if str(row.get("over_protection_warning", "")).lower() == "true")
    if over_count / total >= 0.20:
        recs.append("safety 可能过度压缩空间感：建议放宽 master/rear band 衰减或复核过保护阈值。")
    if action_counts.get("rear_master_gain", 0) / total >= 0.30:
        recs.append("rear_master_gain 经常触发：说明整体后场能量偏高，建议从 routing 侧降低而不是只靠 safety。")
    if not recs:
        recs.append("未发现明显批量性风险；建议抽听 Top Risk Tracks 并按风格微调 preset-specific thresholds。")
    return recs


def build_markdown_report(rows, title="Batch Spatial Diagnostics Report"):
    total = len(rows)
    pass_count, warn_count, fail_count = _count_status(rows)
    avg_before = sum(_to_float(r.get("overall_risk_before")) for r in rows) / max(total, 1)
    avg_after = sum(_to_float(r.get("overall_risk_after")) for r in rows) / max(total, 1)
    avg_reduction = avg_before - avg_after
    top = sorted(rows, key=lambda r: _to_float(r.get("overall_risk_after")), reverse=True)[:10]
    common = _common_risks(rows)
    actions = _action_summary(rows)
    over = [r for r in rows if str(r.get("over_protection_warning", "")).lower() == "true"]
    recs = _recommendations(rows, common, actions)

    lines = [f"# {title}", "", "## Overall Summary"]
    lines += [
        f"- total tracks: {total}",
        f"- pass / warn / fail count: {pass_count} / {warn_count} / {fail_count}",
        f"- average risk before: {avg_before:.3f}",
        f"- average risk after: {avg_after:.3f}",
        f"- average risk reduction: {avg_reduction:.3f}",
        "",
        "## Top Risk Tracks",
        "",
        "| # | filename | preset | status | risk after | risk before |",
        "|---:|---|---|---|---:|---:|",
    ]
    for i, row in enumerate(top, 1):
        lines.append(
            f"| {i} | {row.get('filename','')} | {row.get('preset','')} | "
            f"{row.get('overall_status_after','')} | {_to_float(row.get('overall_risk_after')):.3f} | "
            f"{_to_float(row.get('overall_risk_before')):.3f} |"
        )

    lines += ["", "## Common Risks", ""]
    if common:
        for name, count in common.most_common():
            lines.append(f"- {name}: {count}")
    else:
        lines.append("- none")

    lines += ["", "## Safety Action Summary", ""]
    if actions:
        for name in SAFETY_ACTION_KEYS:
            lines.append(f"- {name}: {actions.get(name, 0)}")
    else:
        lines.append("- no attenuating safety actions recorded")

    lines += ["", "## Over Protection Warnings", ""]
    if over:
        for row in over:
            lines.append(f"- {row.get('filename','')}: {row.get('over_protection_reasons','')}")
    else:
        lines.append("- none")

    lines += ["", "## Recommendations", ""]
    lines += [f"- {rec}" for rec in recs]
    lines.append("")
    return "\n".join(lines)


def write_markdown_report(metrics_csv, output_md):
    rows = load_batch_metrics(metrics_csv)
    text = build_markdown_report(rows)
    output_md = Path(output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(text, encoding="utf-8")
    return output_md


def write_manifest_report(manifest, output_md):
    rows = []
    for diag in manifest:
        before = diag.get("quality_risk", {}).get("before", {})
        after = diag.get("quality_risk", {}).get("after", {})
        safety_actions = diag.get("spatial_safety", {}).get("actions", {})
        rows.append({
            "filename": Path(diag.get("input_file", "")).name,
            "preset": diag.get("preset", ""),
            "overall_risk_before": before.get("overall_risk_score", 0.0),
            "overall_risk_after": after.get("overall_risk_score", 0.0),
            "overall_status_after": after.get("overall_status", ""),
            "risk_items_after": ";".join(after.get("risks", {}).keys()),
            "safety_actions": ";".join(f"{k}={v}" for k, v in safety_actions.items()),
            "over_protection_warning": diag.get("over_protection", {}).get("over_protection_warning", False),
            "over_protection_reasons": ";".join(diag.get("over_protection", {}).get("reasons", [])),
        })
    output_md = Path(output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(build_markdown_report(rows), encoding="utf-8")
    return output_md


def main():
    parser = argparse.ArgumentParser(description="Generate batch spatial diagnostics Markdown report")
    parser.add_argument("metrics_csv", help="Path to batch_metrics.csv")
    parser.add_argument("--output", "-o", default=None, help="Output Markdown path")
    args = parser.parse_args()
    out = args.output or str(Path(args.metrics_csv).with_name("batch_report.md"))
    path = write_markdown_report(args.metrics_csv, out)
    print(f"Wrote report: {path}")


if __name__ == "__main__":
    main()
