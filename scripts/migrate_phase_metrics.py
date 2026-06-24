#!/usr/bin/env python3
"""Repair legacy phase/spatial metrics without re-rendering audio."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np


REPOSITORY_DIR = Path(__file__).resolve().parents[1]
WORKSPACE_DIR = REPOSITORY_DIR.parent
DEFAULT_OUTPUT = WORKSPACE_DIR / "Output-DSP"
sys.path.insert(0, str(REPOSITORY_DIR))

from spatial_safety import (  # noqa: E402
    classify_quality_risks,
    compare_quality_metrics,
    detect_over_protection,
    load_quality_thresholds,
)


def _clip01(value):
    return float(np.clip(float(value), 0.0, 1.0))


def migrate_metric_set(metrics):
    required = {
        "rear_lr_correlation",
        "mono_fold_down_delta_db_front_norm",
        "mono_fold_down_correlation",
        "rear_front_rms_ratio",
        "rear_vocal_leakage_score",
        "low_mid_mud_score",
        "transient_smear_score",
        "high_harshness_score",
    }
    if not isinstance(metrics, dict) or not required.issubset(metrics):
        return False

    rear_corr = metrics["rear_lr_correlation"]
    mono_delta = metrics["mono_fold_down_delta_db_front_norm"]
    mono_corr = metrics["mono_fold_down_correlation"]
    metrics["phase_correlation_risk"] = _clip01(
        0.45 * np.clip((-rear_corr - 0.10) / 0.80, 0.0, 1.0)
        + 0.35 * np.clip((abs(mono_delta) - 1.5) / 5.0, 0.0, 1.0)
        + 0.20 * np.clip((0.82 - mono_corr) / 0.60, 0.0, 1.0)
    )
    metrics["spatial_excess_score"] = _clip01(
        0.24 * np.clip((metrics["rear_front_rms_ratio"] - 0.22) / 0.38, 0.0, 1.0)
        + 0.22 * metrics["rear_vocal_leakage_score"]
        + 0.18 * metrics["low_mid_mud_score"]
        + 0.16 * metrics["transient_smear_score"]
        + 0.12 * metrics["high_harshness_score"]
        + 0.08 * metrics["phase_correlation_risk"]
    )
    return True


def migrate_diagnostics(diagnostics, thresholds):
    migrated = 0
    metric_sets = [diagnostics.get("quality_metrics")]
    safety = diagnostics.get("spatial_safety", {})
    metric_sets.extend([safety.get("before"), safety.get("after")])
    metric_sets.extend([
        diagnostics.get("auto_acoustic_refine_metrics_initial"),
        diagnostics.get("auto_acoustic_refine_metrics_final"),
    ])
    for metrics in metric_sets:
        migrated += int(migrate_metric_set(metrics))

    final_metrics = diagnostics.get("quality_metrics", {})
    before_metrics = safety.get("before", {})
    preset = diagnostics.get("preset")
    if final_metrics and before_metrics:
        diagnostics["quality_risk"] = {
            "before": classify_quality_risks(before_metrics, thresholds, preset_name=preset),
            "after": classify_quality_risks(final_metrics, thresholds, preset_name=preset),
        }
        diagnostics["quality_delta"] = compare_quality_metrics(before_metrics, final_metrics)
    if safety.get("before") and safety.get("after"):
        diagnostics["over_protection"] = detect_over_protection(
            safety["before"], safety["after"]
        )
    diagnostics["phase_metric_version"] = 2
    return migrated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    thresholds = load_quality_thresholds()
    files = sorted(args.output_dir.glob("*_diagnostics.json"))
    migrated_sets = 0
    for path in files:
        diagnostics = json.loads(path.read_text(encoding="utf-8"))
        migrated_sets += migrate_diagnostics(diagnostics, thresholds)
        path.write_text(
            json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(f"Migrated {len(files)} diagnostics files ({migrated_sets} metric sets)")


if __name__ == "__main__":
    main()
