"""Batch diagnostics runner for stereo -> 4.0 spatial quality evaluation."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

import config_center as cfg
from audio_io import discover_audio_files
from run_spatializer import process_file
from spatial_quality_report import write_markdown_report
from spatial_safety import load_quality_thresholds

CSV_FIELDS = [
    "filename",
    "duration_sec",
    "preset",
    "preset_mode_used",
    "safety_enabled",
    "rear_front_db_before",
    "rear_front_db_after",
    "rear_vocal_leakage_before",
    "rear_vocal_leakage_after",
    "sub150_retention_before",
    "sub150_retention_after",
    "low_mid_mud_before",
    "low_mid_mud_after",
    "transient_smear_before",
    "transient_smear_after",
    "high_harshness_before",
    "high_harshness_after",
    "phase_risk_before",
    "phase_risk_after",
    "mono_delta_db_before",
    "mono_delta_db_after",
    "spatial_excess_before",
    "spatial_excess_after",
    "overall_risk_before",
    "overall_risk_after",
    "overall_status_after",
    "over_protection_warning",
    "safety_actions",
    "risk_items_after",
    "over_protection_reasons",
    "diagnostics_path",
]


def _metric(metrics, key):
    return float((metrics or {}).get(key, 0.0))


def _actions_string(actions):
    return ";".join(f"{k}={float(v):.4f}" for k, v in sorted((actions or {}).items()))


def diagnostics_to_row(diag):
    safety = diag.get("spatial_safety", {})
    before = safety.get("before", {})
    after = diag.get("quality_metrics", safety.get("after", {}))
    risk_before = diag.get("quality_risk", {}).get("before", {})
    risk_after = diag.get("quality_risk", {}).get("after", {})
    over = diag.get("over_protection", {})
    output_paths = diag.get("output_paths", {})
    return {
        "filename": Path(diag.get("input_file", "")).name,
        "duration_sec": float(diag.get("duration_seconds", 0.0)),
        "preset": diag.get("preset", ""),
        "preset_mode_used": diag.get("preset_mode_used", ""),
        "safety_enabled": bool(safety.get("enabled", False)),
        "rear_front_db_before": _metric(before, "rear_front_db"),
        "rear_front_db_after": _metric(after, "rear_front_db"),
        "rear_vocal_leakage_before": _metric(before, "rear_vocal_leakage_score"),
        "rear_vocal_leakage_after": _metric(after, "rear_vocal_leakage_score"),
        "sub150_retention_before": _metric(before, "sub150_retention_score"),
        "sub150_retention_after": _metric(after, "sub150_retention_score"),
        "low_mid_mud_before": _metric(before, "low_mid_mud_score"),
        "low_mid_mud_after": _metric(after, "low_mid_mud_score"),
        "transient_smear_before": _metric(before, "transient_smear_score"),
        "transient_smear_after": _metric(after, "transient_smear_score"),
        "high_harshness_before": _metric(before, "high_harshness_score"),
        "high_harshness_after": _metric(after, "high_harshness_score"),
        "phase_risk_before": _metric(before, "phase_correlation_risk"),
        "phase_risk_after": _metric(after, "phase_correlation_risk"),
        "mono_delta_db_before": _metric(before, "mono_fold_down_delta_db"),
        "mono_delta_db_after": _metric(after, "mono_fold_down_delta_db"),
        "spatial_excess_before": _metric(before, "spatial_excess_score"),
        "spatial_excess_after": _metric(after, "spatial_excess_score"),
        "overall_risk_before": float(risk_before.get("overall_risk_score", 0.0)),
        "overall_risk_after": float(risk_after.get("overall_risk_score", 0.0)),
        "overall_status_after": risk_after.get("overall_status", "pass"),
        "over_protection_warning": bool(over.get("over_protection_warning", False)),
        "safety_actions": _actions_string(safety.get("actions", {})),
        "risk_items_after": ";".join((risk_after.get("risks", {}) or {}).keys()),
        "over_protection_reasons": ";".join(over.get("reasons", [])),
        "diagnostics_path": output_paths.get("diagnostics", ""),
    }


def write_csv(rows, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_summary(rows, path):
    status_counts = Counter(row.get("overall_status_after", "unknown") for row in rows)
    total = len(rows)
    avg_before = sum(float(r["overall_risk_before"]) for r in rows) / max(total, 1)
    avg_after = sum(float(r["overall_risk_after"]) for r in rows) / max(total, 1)
    payload = {
        "total_tracks": total,
        "status_counts_after": dict(status_counts),
        "average_risk_before": avg_before,
        "average_risk_after": avg_after,
        "average_risk_reduction": avg_before - avg_after,
        "over_protection_warnings": sum(1 for r in rows if r.get("over_protection_warning") is True),
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def build_options(args):
    return {
        "target_sr": args.target_sr or cfg.TARGET_SR,
        "analysis_seconds": args.analysis_seconds or cfg.ANALYSIS_SECONDS,
        "preset_mode": args.preset_mode,
        "manual_preset": args.preset or cfg.MANUAL_PRESET,
        "output_mode": args.output_mode,
        "auto_acoustic_rear_enhancement": args.auto_acoustic_rear_enhancement,
        "export_binaural_front_pair": False,
        "export_binaural_rear_pair": False,
        "export_binaural_ctc_4ch": False,
        "binaural_front_azimuth_deg": cfg.BINAURAL_FRONT_AZIMUTH_DEG,
        "binaural_rear_azimuth_deg": cfg.BINAURAL_REAR_AZIMUTH_DEG,
        "binaural_full_rear_gain_db": cfg.BINAURAL_FULL_REAR_GAIN_DB,
        "ctc_regularization": cfg.CTC_REGULARIZATION,
        "ctc_ir_length_samples": cfg.CTC_IR_LENGTH_SAMPLES,
        "ctc_peak_target": cfg.CTC_PEAK_TARGET,
        "export_binaural_room_rir": False,
        "export_diagnostics": True,
        "spatial_safety_enabled": not args.no_spatial_safety,
        "quality_thresholds_path": args.quality_thresholds,
        "quality_thresholds": load_quality_thresholds(args.quality_thresholds),
        "diagnostics_only": args.diagnostics_only,
        "write_quality_report": False,
        "speaker_distance_front_m": cfg.SPEAKER_DISTANCE_FRONT_M,
        "speaker_distance_rear_m": cfg.SPEAKER_DISTANCE_REAR_M,
        "speaker_ref_distance_m": cfg.SPEAKER_DISTANCE_REFERENCE_M,
        "air_absorption_db_per_m": cfg.SPEAKER_AIR_ABSORPTION_DB_PER_M,
        "room_ir": None,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch spatial quality diagnostics")
    parser.add_argument("--input-dir", default=str(cfg.INPUT_AUDIO_DIR))
    parser.add_argument("--output-dir", default="outputs/batch_eval")
    parser.add_argument("--preset-mode", default="auto_acoustic", choices=["manual", "auto_select", "auto_acoustic"])
    parser.add_argument("--preset", default=None)
    parser.add_argument("--output-mode", default="4ch", choices=["4ch", "binaural", "both"])
    parser.add_argument("--quality-thresholds", default=None)
    parser.add_argument("--analysis-seconds", type=float, default=None)
    parser.add_argument("--target-sr", type=int, default=None)
    parser.add_argument("--no-spatial-safety", action="store_true")
    parser.add_argument("--diagnostics-only", action="store_true")
    parser.add_argument("--auto-acoustic-rear-enhancement", action="store_true")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    files = discover_audio_files(input_dir)
    if not files:
        raise FileNotFoundError(f"No supported audio files found in {input_dir}")

    options = build_options(args)
    manifest = []
    rows = []
    for path in files:
        diag = process_file(path, output_dir, options)
        manifest.append(diag)
        rows.append(diagnostics_to_row(diag))

    metrics_csv = output_dir / "batch_metrics.csv"
    summary_json = output_dir / "batch_summary.json"
    report_md = output_dir / "batch_report.md"
    manifest_json = output_dir / "batch_manifest.json"

    write_csv(rows, metrics_csv)
    summary = write_summary(rows, summary_json)
    manifest_json.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    write_markdown_report(metrics_csv, report_md)

    print(f"Batch metrics: {metrics_csv}")
    print(f"Batch summary: {summary_json}")
    print(f"Batch report: {report_md}")
    print(f"Tracks: {summary['total_tracks']}")


if __name__ == "__main__":
    main()
