"""Feedback-aware rendering entrypoint.

This keeps the original run_spatializer.py path stable while adding optional
human score records and external tuning profiles for reviewable iterations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

import config_center as cfg
import run_spatializer as base
from presets import resolve_preset as default_resolve_preset
from subjective_feedback import (
    build_evaluation_record,
    find_subjective_score,
    load_subjective_score,
    write_evaluation_record,
)
from tuning_profile import apply_tuning_profile, load_tuning_profile


def _base_args(args):
    return SimpleNamespace(
        input_file=args.input_file,
        out_dir=args.out_dir,
        preset=args.preset,
        preset_mode=args.preset_mode,
        output_mode=args.output_mode,
        analysis_seconds=args.analysis_seconds,
        target_sr=args.target_sr,
        auto_acoustic_rear_enhancement=args.auto_acoustic_rear_enhancement,
        export_binaural_front_pair=args.export_binaural_front_pair,
        export_binaural_rear_pair=args.export_binaural_rear_pair,
        export_binaural_ctc_4ch=args.export_binaural_ctc_4ch,
        ctc_regularization=args.ctc_regularization,
        ctc_ir_length_samples=args.ctc_ir_length_samples,
        no_diagnostics=args.no_diagnostics,
        quality_thresholds=args.quality_thresholds,
        diagnostics_only=args.diagnostics_only,
        write_quality_report=args.write_quality_report,
        no_spatial_safety=args.no_spatial_safety,
    )


def _patch_resolve_preset(profile, holder):
    def patched_resolve_preset(preset_mode, manual_preset, analysis, rear_enhancement=False):
        preset_name, preset_mode_used, preset_values, auto_info = default_resolve_preset(
            preset_mode,
            manual_preset,
            analysis,
            rear_enhancement=rear_enhancement,
        )
        tuned_values, report = apply_tuning_profile(preset_values, profile)
        holder["last_report"] = report
        auto_info = dict(auto_info or {})
        auto_info["tuning_profile"] = report
        return preset_name, preset_mode_used, tuned_values, auto_info

    base.resolve_preset = patched_resolve_preset


def _prepare_room_ir(options):
    if options["export_binaural_room_rir"] and options["output_mode"] in {"binaural", "both"}:
        sample_rate = options["target_sr"]
        options["room_ir"] = base.make_small_dry_room_stereo_rir(
            sample_rate,
            rt60=cfg.ROOM_RIR_RT60_SECONDS,
            length_seconds=cfg.ROOM_RIR_LENGTH_SECONDS,
            late_start_seconds=cfg.ROOM_RIR_LATE_START_SECONDS,
            seed=cfg.ROOM_RIR_RANDOM_SEED,
        )
    else:
        options["room_ir"] = None


def _write_feedback_outputs(diag, input_path, out_dir, subjective_score, profile_report, write_record):
    diag["tuning_profile"] = profile_report or {"enabled": False}
    if not write_record:
        return diag
    record = build_evaluation_record(diag, subjective_score)
    stem = base._safe_stem(input_path)
    preset = diag.get("preset", "preset")
    record_path = Path(out_dir) / f"{stem}_{preset}_evaluation_record.json"
    write_evaluation_record(record, record_path)
    diag.setdefault("output_paths", {})["evaluation_record"] = str(record_path)
    if diag.get("output_paths", {}).get("diagnostics"):
        base.save_diagnostics(diag, diag["output_paths"]["diagnostics"])
    return diag


def main():
    parser = argparse.ArgumentParser(description="Feedback-aware DSP spatializer")
    parser.add_argument("input_file", nargs="?", help="Optional single input file")
    parser.add_argument("--out-dir", default=str(cfg.OUTPUT_DIR))
    parser.add_argument("--preset", default=None, choices=base.available_presets())
    parser.add_argument("--preset-mode", default=None, choices=["manual", "auto_select", "auto_acoustic"])
    parser.add_argument("--output-mode", default=None, choices=["4ch", "binaural", "both"])
    parser.add_argument("--analysis-seconds", type=float, default=None)
    parser.add_argument("--target-sr", type=int, default=None)
    parser.add_argument("--auto-acoustic-rear-enhancement", action="store_true")
    parser.add_argument("--export-binaural-front-pair", action="store_true")
    parser.add_argument("--export-binaural-rear-pair", action="store_true")
    parser.add_argument("--export-binaural-ctc-4ch", action="store_true")
    parser.add_argument("--ctc-regularization", type=float, default=None)
    parser.add_argument("--ctc-ir-length-samples", type=int, default=None)
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--quality-thresholds", default=None)
    parser.add_argument("--diagnostics-only", action="store_true")
    parser.add_argument("--write-quality-report", action="store_true")
    parser.add_argument("--no-spatial-safety", action="store_true")
    parser.add_argument("--tuning-profile", default=None, help="External tuning profile JSON")
    parser.add_argument("--subjective-score", default=None, help="Single subjective score JSON")
    parser.add_argument("--subjective-score-dir", default=None, help="Directory of per-song subjective score JSON files")
    parser.add_argument("--write-evaluation-record", action="store_true")
    args = parser.parse_args()

    profile = load_tuning_profile(args.tuning_profile)
    holder = {"last_report": {"enabled": False}}
    _patch_resolve_preset(profile, holder)

    base_args = _base_args(args)
    files = base.resolve_input_files(base_args)
    options = base.build_options(base_args)
    _prepare_room_ir(options)

    out_dir = Path(args.out_dir).expanduser()
    manifest = []
    for file_path in files:
        diag = base.process_file(file_path, out_dir, options)
        score_path = args.subjective_score or find_subjective_score(args.subjective_score_dir, file_path)
        subjective_score = load_subjective_score(score_path)
        diag = _write_feedback_outputs(
            diag,
            file_path,
            out_dir,
            subjective_score,
            holder.get("last_report", {"enabled": False}),
            args.write_evaluation_record or subjective_score is not None,
        )
        manifest.append(diag)

    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "batch_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Batch manifest: {manifest_path}")

    if options.get("write_quality_report"):
        report_path = out_dir / "quality_report.md"
        base.write_manifest_report(manifest, report_path)
        print(f"Quality report: {report_path}")


if __name__ == "__main__":
    main()
