"""Streaming Stereo Spatializer — main entry point.

Usage:
    python run_spatializer.py                          # batch: input_audio/ → spatializer_outputs_clean/
    python run_spatializer.py my_song.wav              # single file
    python run_spatializer.py my_song.wav --preset-mode auto_acoustic --output-mode binaural
"""

import argparse
import json
from pathlib import Path

import numpy as np

# ---- project imports ----
import config_center as cfg
from audio_io import discover_audio_files, export_audio, load_audio
from auto_refine import refine_auto_acoustic_routing, summarize_refine_actions
from binaural_renderer import (
    apply_room_rir_to_binaural,
    make_small_dry_room_stereo_rir,
    render_4ch_binaural,
    render_binaural_to_ctc_4ch,
)
from diagnostics import generate_diagnostics, save_diagnostics
from dsp_utils import db, peak, rms
from energy_manager import match_energy
from layer_extractor import extract_layers
from layer_router import apply_preset as route_apply_preset
from limiter import apply_limiter
from presets import (
    apply_phase5a_rear_content_candidate,
    apply_phase5a_v31_candidate,
    available_presets,
    resolve_preset,
)
from renderer_4ch import render_4ch
from spatial_safety import (
    apply_spatial_safety,
    classify_quality_risks,
    compare_quality_metrics,
    compute_quality_metrics,
    detect_over_protection,
    load_quality_thresholds,
)
from spatial_quality_report import write_manifest_report
from streaming_analyzer import analyze_audio


# ---------------------------------------------------------------------------
def _safe_stem(path):
    """Return a safe filename stem without tricky characters."""
    stem = Path(path).stem
    return stem.replace(" ", "_").replace("(", "").replace(")", "")


def _crest_factor_db(audio):
    """Return sample peak/RMS crest factor for gain-staging diagnostics."""
    audio = np.asarray(audio, dtype=np.float32)
    return float(db(peak(audio) / (rms(audio) + 1e-9)))


# ---------------------------------------------------------------------------
def resolve_input_files(args):
    """Return list of Path objects to process based on CLI args + config."""
    if args.input_file:
        # explicit single file on command line
        path = Path(args.input_file).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")
        if path.is_dir():
            raise IsADirectoryError(f"Expected a file, got directory: {path}")
        return [path]

    # no CLI input → use config_center settings
    if cfg.PROCESS_MODE == "single":
        single = cfg.INPUT_AUDIO_DIR / cfg.SINGLE_INPUT_FILENAME
        if not single.exists():
            raise FileNotFoundError(
                f"PROCESS_MODE=single but file not found: {single}\n"
                f"  → Put '{cfg.SINGLE_INPUT_FILENAME}' into input_audio/ "
                f"or switch PROCESS_MODE to 'all'."
            )
        return [single]

    if cfg.PROCESS_MODE == "all":
        files = discover_audio_files(cfg.INPUT_AUDIO_DIR)
        if not files:
            raise FileNotFoundError(
                f"No supported audio files found in {cfg.INPUT_AUDIO_DIR}\n"
                f"  → Drop .wav / .flac / .mp3 / .m4a files into input_audio/"
            )
        return files

    raise ValueError(
        f"config_center.PROCESS_MODE = '{cfg.PROCESS_MODE}' is invalid. "
        f"Must be 'single' or 'all'."
    )


# ---------------------------------------------------------------------------
def process_file(input_path, output_dir, options):
    """Full pipeline: load → analyze → preset → route → render → energy → limiter → export."""
    # ---- load ----
    left, right, sample_rate = load_audio(input_path, target_sr=options["target_sr"])
    duration = len(left) / sample_rate

    # ---- analyze ----
    analysis = analyze_audio(left, right, sample_rate, options["analysis_seconds"])

    # ---- resolve preset ----
    preset_name, preset_mode_used, preset_values, auto_info = resolve_preset(
        options["preset_mode"],
        options["manual_preset"],
        analysis,
        rear_enhancement=options["auto_acoustic_rear_enhancement"],
    )
    rear_content_candidate = {"enabled": False}
    v31_candidate = {"enabled": False}
    if (
        options.get("phase5a_rear_content_candidate", False)
        and preset_mode_used == "auto_acoustic"
    ):
        preset_values, rear_content_candidate = apply_phase5a_rear_content_candidate(
            preset_values, auto_info,
        )
    elif (
        options.get("phase5a_v31_candidate", False)
        and preset_mode_used == "auto_acoustic"
    ):
        preset_values, v31_candidate = apply_phase5a_v31_candidate(
            preset_values, auto_info, analysis,
        )

    # ---- route layers ----
    routing = route_apply_preset(
        preset_values,
        analysis,
        preset_name=preset_name,
        apply_analysis_adaptation=(preset_mode_used != "auto_acoustic"),
    )

    # ---- extract layers & render 4ch (initial) ----
    layers = extract_layers(left, right, sample_rate)
    raw_4ch = render_4ch(left, right, layers, routing, sample_rate, preset_name)

    # ---- spatial safety: rear-only protection before mastering ----
    safety_4ch, safety_report = apply_spatial_safety(
        left,
        right,
        raw_4ch,
        sample_rate,
        analysis=analysis,
        enabled=options["spatial_safety_enabled"],
    )

    # ---- quality risk classification thresholds ----
    thresholds = options.get("quality_thresholds") or load_quality_thresholds(options.get("quality_thresholds_path"))

    # ---- quality metrics on pre-mastering audio (for refinement decision) ----
    pre_master_metrics = compute_quality_metrics(
        left, right, safety_4ch, sample_rate, analysis=analysis,
    )

    # ---- closed-loop refinement (auto_acoustic only) ----
    refine_actions = []
    refine_routing_initial = dict(routing)
    refine_metrics_initial = dict(pre_master_metrics)
    refine_passes_applied = 0

    if (options.get("auto_acoustic_refine")
        and preset_mode_used == "auto_acoustic"
        and options["auto_acoustic_refine_passes"] > 0):

        for _ in range(options["auto_acoustic_refine_passes"]):
            prev_metrics = dict(pre_master_metrics)
            prev_routing = dict(routing)
            prev_safety_4ch = safety_4ch.copy()
            prev_safety_report = safety_report

            refined_routing, pass_actions = refine_auto_acoustic_routing(
                routing, analysis, prev_metrics,
                max_step=options["auto_acoustic_refine_max_step"],
            )
            if not pass_actions:
                break

            # Re-render with refined routing (skip layer_router — routing is complete)
            raw_4ch = render_4ch(left, right, layers, refined_routing, sample_rate, preset_name)
            safety_4ch, safety_report = apply_spatial_safety(
                left, right, raw_4ch, sample_rate,
                analysis=analysis, enabled=options["spatial_safety_enabled"],
            )
            new_metrics = compute_quality_metrics(
                left, right, safety_4ch, sample_rate, analysis=analysis,
            )

            # ---- overshoot guard: if this pass caused severe regression, revert ----
            spatial_delta = new_metrics.get("spatial_excess_score", 0) - prev_metrics.get("spatial_excess_score", 0)
            harsh_delta = new_metrics.get("high_harshness_score", 0) - prev_metrics.get("high_harshness_score", 0)
            mud_delta = new_metrics.get("low_mid_mud_score", 0) - prev_metrics.get("low_mid_mud_score", 0)

            if spatial_delta > 0.20 or harsh_delta > 0.30 or mud_delta > 0.30:
                # Overshoot detected — revert to previous routing + audio
                routing = prev_routing
                safety_4ch = prev_safety_4ch
                safety_report = prev_safety_report
                pre_master_metrics = prev_metrics
                refine_actions.append({
                    "reason": "overshoot_guard_reverted",
                    "spatial_excess_delta": round(spatial_delta, 3),
                    "high_harshness_delta": round(harsh_delta, 3),
                    "low_mid_mud_delta": round(mud_delta, 3),
                    "reverted_actions": pass_actions,
                })
                break

            refine_actions.extend(pass_actions)
            refine_passes_applied += 1
            routing = refined_routing
            pre_master_metrics = new_metrics

    # ---- gain staging + linked dynamic limiter (Phase 5A v2) ----
    energy_matched, energy_match_report = match_energy(
        (left, right),
        safety_4ch,
        sample_rate,
        reference="front",
        return_report=True,
    )
    final_4ch, limiter_report = apply_limiter(
        energy_matched,
        sample_rate=sample_rate,
        return_report=True,
    )
    input_pair = np.column_stack((left, right)).astype(np.float32)
    final_front = final_4ch[:, :2]
    gain_staging_report = {
        "version": 2,
        "energy_match": energy_match_report,
        "limiter": limiter_report,
        "input_stereo_rms": float(rms(input_pair)),
        "output_front_rms": float(rms(final_front)),
        "front_rms_delta_db": float(db(rms(final_front) / (rms(input_pair) + 1e-9))),
        "input_stereo_crest_factor_db": _crest_factor_db(input_pair),
        "output_front_crest_factor_db": _crest_factor_db(final_front),
        "front_crest_factor_delta_db": float(
            _crest_factor_db(final_front) - _crest_factor_db(input_pair)
        ),
    }
    final_quality_metrics = compute_quality_metrics(
        left,
        right,
        final_4ch,
        sample_rate,
        analysis=analysis,
    )
    quality_risk_before = classify_quality_risks(
        safety_report["before"], thresholds, preset_name=preset_name
    )
    quality_risk_after = classify_quality_risks(
        final_quality_metrics, thresholds, preset_name=preset_name
    )
    quality_delta = compare_quality_metrics(safety_report["before"], final_quality_metrics)
    over_protection = detect_over_protection(safety_report["before"], safety_report["after"])

    # ---- export ----
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = _safe_stem(input_path)
    output_paths = {}

    if (
        (not options.get("diagnostics_only"))
        and options["output_mode"] in {"4ch", "both"}
    ):
        path_4ch = output_dir / f"{stem}_{preset_name}_4ch.wav"
        export_audio(path_4ch, final_4ch, sample_rate)
        output_paths["4ch"] = str(path_4ch)

    room_ir = options.get("room_ir")

    if (
        (not options.get("diagnostics_only"))
        and options["output_mode"] in {"binaural", "both"}
    ):
        # full 4-ch binaural (virtual speakers → headphones, procedural HRTF)
        binaural = render_4ch_binaural(
            final_4ch,
            sample_rate,
            active_channels=("LF", "RF", "LB", "RB"),
            front_azimuth_deg=options["binaural_front_azimuth_deg"],
            rear_azimuth_deg=options["binaural_rear_azimuth_deg"],
            rear_gain_db=options["binaural_full_rear_gain_db"],
        )

        path_bin = output_dir / f"{stem}_{preset_name}_binaural_4p0.wav"
        export_audio(path_bin, binaural, sample_rate)
        output_paths["binaural_4p0"] = str(path_bin)

        if options["export_binaural_ctc_4ch"]:
            ctc_4ch = render_binaural_to_ctc_4ch(
                binaural,
                sample_rate,
                front_azimuth_deg=options["binaural_front_azimuth_deg"],
                rear_azimuth_deg=options["binaural_rear_azimuth_deg"],
                rear_gain_db=options["binaural_full_rear_gain_db"],
                speaker_distance_front_m=options["speaker_distance_front_m"],
                speaker_distance_rear_m=options["speaker_distance_rear_m"],
                speaker_ref_distance_m=options["speaker_ref_distance_m"],
                air_absorption_db_per_m=options["air_absorption_db_per_m"],
                regularization=options["ctc_regularization"],
                ir_length_samples=options["ctc_ir_length_samples"],
                peak_target=options["ctc_peak_target"],
            )
            path_ctc = output_dir / f"{stem}_{preset_name}_binaural_ctc_4ch.wav"
            export_audio(path_ctc, ctc_4ch, sample_rate)
            output_paths["binaural_ctc_4ch"] = str(path_ctc)

        if options["export_binaural_room_rir"] and room_ir is not None:
            room = apply_room_rir_to_binaural(binaural, room_ir, keep_tail=cfg.ROOM_RIR_KEEP_TAIL)
            path_room = output_dir / f"{stem}_{preset_name}_binaural_4p0_room_rir.wav"
            export_audio(path_room, room, sample_rate)
            output_paths["binaural_4p0_room_rir"] = str(path_room)

            if options["export_binaural_ctc_4ch"]:
                room_ctc_4ch = render_binaural_to_ctc_4ch(
                    room,
                    sample_rate,
                    front_azimuth_deg=options["binaural_front_azimuth_deg"],
                    rear_azimuth_deg=options["binaural_rear_azimuth_deg"],
                    rear_gain_db=options["binaural_full_rear_gain_db"],
                    speaker_distance_front_m=options["speaker_distance_front_m"],
                    speaker_distance_rear_m=options["speaker_distance_rear_m"],
                    speaker_ref_distance_m=options["speaker_ref_distance_m"],
                    air_absorption_db_per_m=options["air_absorption_db_per_m"],
                    regularization=options["ctc_regularization"],
                    ir_length_samples=options["ctc_ir_length_samples"],
                    peak_target=options["ctc_peak_target"],
                )
                path_room_ctc = output_dir / f"{stem}_{preset_name}_binaural_ctc_4ch_room_rir.wav"
                export_audio(path_room_ctc, room_ctc_4ch, sample_rate)
                output_paths["binaural_ctc_4ch_room_rir"] = str(path_room_ctc)

        if options["export_binaural_front_pair"]:
            front = render_4ch_binaural(
                final_4ch,
                sample_rate,
                active_channels=("LF", "RF"),
                front_azimuth_deg=options["binaural_front_azimuth_deg"],
                rear_azimuth_deg=options["binaural_rear_azimuth_deg"],
                exact_pair_normalize=True,
                speaker_distance_front_m=options["speaker_distance_front_m"],
                speaker_distance_rear_m=options["speaker_distance_rear_m"],
                speaker_ref_distance_m=options["speaker_ref_distance_m"],
                air_absorption_db_per_m=options["air_absorption_db_per_m"],
            )
            path_fp = output_dir / f"{stem}_{preset_name}_binaural_front_pair.wav"
            export_audio(path_fp, front, sample_rate)
            output_paths["binaural_front_pair"] = str(path_fp)

            if options["export_binaural_room_rir"] and room_ir is not None:
                front_room = apply_room_rir_to_binaural(front, room_ir, keep_tail=cfg.ROOM_RIR_KEEP_TAIL)
                path_fr = output_dir / f"{stem}_{preset_name}_binaural_front_pair_room_rir.wav"
                export_audio(path_fr, front_room, sample_rate)
                output_paths["binaural_front_pair_room_rir"] = str(path_fr)

        if options["export_binaural_rear_pair"]:
            rear = render_4ch_binaural(
                final_4ch,
                sample_rate,
                active_channels=("LB", "RB"),
                front_azimuth_deg=options["binaural_front_azimuth_deg"],
                rear_azimuth_deg=options["binaural_rear_azimuth_deg"],
                exact_pair_normalize=True,
            )
            path_rp = output_dir / f"{stem}_{preset_name}_binaural_rear_pair.wav"
            export_audio(path_rp, rear, sample_rate)
            output_paths["binaural_rear_pair"] = str(path_rp)

            if options["export_binaural_room_rir"] and room_ir is not None:
                rear_room = apply_room_rir_to_binaural(rear, room_ir, keep_tail=cfg.ROOM_RIR_KEEP_TAIL)
                path_rr = output_dir / f"{stem}_{preset_name}_binaural_rear_pair_room_rir.wav"
                export_audio(path_rr, rear_room, sample_rate)
                output_paths["binaural_rear_pair_room_rir"] = str(path_rr)

    # ---- diagnostics ----
    rear_front_ratio = float(rms(final_4ch[:, 2:]) / (rms(final_4ch[:, :2]) + 1e-9))
    diagnostics = generate_diagnostics(
        input_file=str(input_path),
        sample_rate=sample_rate,
        duration=duration,
        analysis=analysis,
        preset=preset_name,
        output_audio=final_4ch,
        output_file=output_paths.get("4ch") or output_paths.get("binaural_4p0"),
    )
    diagnostics.update({
        "preset_mode_used": preset_mode_used,
        "auto_acoustic_info": auto_info,
        "routing": routing,
        "spatial_safety": safety_report,
        "quality_metrics": final_quality_metrics,
        "quality_risk": {
            "before": quality_risk_before,
            "after": quality_risk_after,
        },
        "quality_delta": quality_delta,
        "over_protection": over_protection,
        "gain_staging": gain_staging_report,
        "phase5a_rear_content_candidate": rear_content_candidate,
        "phase5a_v31_candidate": v31_candidate,
        "output_paths": output_paths,
        "rear_to_front_rms_ratio": rear_front_ratio,
        "rear_to_front_db": float(db(rear_front_ratio)),
        "peak": float(peak(final_4ch)),
        # ---- closed-loop refine diagnostics (Phase 4) ----
        "auto_acoustic_refine_enabled": options.get("auto_acoustic_refine", False),
        "auto_acoustic_refine_passes_applied": refine_passes_applied,
        "auto_acoustic_refine_routing_initial": refine_routing_initial,
        "auto_acoustic_refine_routing_final": dict(routing),
        "auto_acoustic_refine_metrics_initial": refine_metrics_initial,
        "auto_acoustic_refine_metrics_final": dict(pre_master_metrics),
        "auto_acoustic_refine_actions": refine_actions,
    })

    if options["export_diagnostics"]:
        diag_path = output_dir / f"{stem}_{preset_name}_diagnostics.json"
        output_paths["diagnostics"] = str(diag_path)
        diagnostics["output_paths"] = output_paths
        save_diagnostics(diagnostics, diag_path)

    # ---- console summary ----
    print(f"Processed: {input_path.name}")
    print(f"  preset: {preset_name} ({preset_mode_used})")
    print(
        f"  rear/front: {diagnostics['rear_to_front_rms_ratio']:.4f} "
        f"({diagnostics['rear_to_front_db']:.2f} dB)"
    )
    print(
        "  safety risks: "
        f"vocal={final_quality_metrics['rear_vocal_leakage_score']:.2f}, "
        f"mud={final_quality_metrics['low_mid_mud_score']:.2f}, "
        f"transient={final_quality_metrics['transient_smear_score']:.2f}, "
        f"harsh={final_quality_metrics['high_harshness_score']:.2f}, "
        f"monoΔ={final_quality_metrics['mono_fold_down_delta_db']:.2f} dB"
    )
    print(
        "  gain staging: "
        f"frontΔ={gain_staging_report['front_rms_delta_db']:.2f} dB, "
        f"match={energy_match_report['applied_gain_db']:.2f} dB, "
        f"limiter maxGR={limiter_report['max_gain_reduction_db']:.2f} dB, "
        f"p95GR={limiter_report['p95_gain_reduction_db']:.2f} dB"
    )
    if refine_actions:
        print(f"  refine: {refine_passes_applied} pass(es), {len(refine_actions)} action(s)")
        for line in summarize_refine_actions(refine_actions):
            print(f"    {line}")
    for key, path in output_paths.items():
        print(f"  {key}: {path}")

    return diagnostics


# ---------------------------------------------------------------------------
def _resolve_refine_flag(args, cfg):
    """Resolve --auto-acoustic-refine / --no-auto-acoustic-refine vs config default."""
    if args.auto_acoustic_refine:
        return True
    if args.no_auto_acoustic_refine:
        return False
    return cfg.AUTO_ACOUSTIC_ENABLE_CLOSED_LOOP


# ---------------------------------------------------------------------------
def build_options(args):
    """Merge CLI args with config_center defaults into a single options dict."""
    output_mode = args.output_mode or cfg.OUTPUT_MODE
    if output_mode not in {"4ch", "binaural", "both"}:
        raise ValueError("OUTPUT_MODE must be '4ch', 'binaural', or 'both'")

    return {
        "target_sr": args.target_sr or cfg.TARGET_SR,
        "analysis_seconds": args.analysis_seconds or cfg.ANALYSIS_SECONDS,
        "preset_mode": args.preset_mode or cfg.PRESET_MODE,
        "manual_preset": args.preset or cfg.MANUAL_PRESET,
        "output_mode": output_mode,
        "auto_acoustic_rear_enhancement": (
            args.auto_acoustic_rear_enhancement or cfg.AUTO_ACOUSTIC_REAR_ENHANCEMENT
        ),
        "phase5a_rear_content_candidate": args.phase5a_rear_content_candidate,
        "phase5a_v31_candidate": args.phase5a_v31_candidate,
        "export_binaural_front_pair": (
            args.export_binaural_front_pair or cfg.EXPORT_BINAURAL_FRONT_PAIR
        ),
        "export_binaural_rear_pair": (
            args.export_binaural_rear_pair or cfg.EXPORT_BINAURAL_REAR_PAIR
        ),
        "export_binaural_ctc_4ch": (
            args.export_binaural_ctc_4ch or cfg.EXPORT_BINAURAL_CROSSTALK_CANCELLED_4CH
        ),
        "binaural_front_azimuth_deg": cfg.BINAURAL_FRONT_AZIMUTH_DEG,
        "binaural_rear_azimuth_deg": cfg.BINAURAL_REAR_AZIMUTH_DEG,
        "binaural_full_rear_gain_db": cfg.BINAURAL_FULL_REAR_GAIN_DB,
        "ctc_regularization": args.ctc_regularization or cfg.CTC_REGULARIZATION,
        "ctc_ir_length_samples": args.ctc_ir_length_samples or cfg.CTC_IR_LENGTH_SAMPLES,
        "ctc_peak_target": cfg.CTC_PEAK_TARGET,
        "export_binaural_room_rir": (
            getattr(args, "export_binaural_room_rir", False) or cfg.EXPORT_BINAURAL_ROOM_RIR
        ),
        "export_diagnostics": ((not args.no_diagnostics) and cfg.EXPORT_DIAGNOSTICS) or args.diagnostics_only,
        "spatial_safety_enabled": not args.no_spatial_safety,
        "quality_thresholds_path": args.quality_thresholds,
        "quality_thresholds": load_quality_thresholds(args.quality_thresholds),
        "diagnostics_only": args.diagnostics_only,
        "write_quality_report": args.write_quality_report,
        "speaker_distance_front_m": cfg.SPEAKER_DISTANCE_FRONT_M,
        "speaker_distance_rear_m": cfg.SPEAKER_DISTANCE_REAR_M,
        "speaker_ref_distance_m": cfg.SPEAKER_DISTANCE_REFERENCE_M,
        "air_absorption_db_per_m": cfg.SPEAKER_AIR_ABSORPTION_DB_PER_M,
        # ---- closed-loop refine ----
        "auto_acoustic_refine": _resolve_refine_flag(args, cfg),
        "auto_acoustic_refine_passes": (
            args.auto_acoustic_refine_passes
            if args.auto_acoustic_refine_passes is not None
            else cfg.AUTO_ACOUSTIC_REFINE_PASSES
        ),
        "auto_acoustic_refine_max_step": (
            args.auto_acoustic_refine_max_step
            if args.auto_acoustic_refine_max_step is not None
            else cfg.AUTO_ACOUSTIC_REFINE_MAX_STEP
        ),
    }


# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Streaming Stereo Spatializer — stereo → 4ch / binaural"
    )
    parser.add_argument(
        "input_file", nargs="?",
        help="Optional single input file. If omitted, use config_center.py settings.",
    )
    parser.add_argument("--out-dir", default=str(cfg.OUTPUT_DIR), help="Output directory")
    parser.add_argument(
        "--preset", default=None,
        choices=available_presets(),
        help="Manual preset name (for preset_mode=manual)",
    )
    parser.add_argument(
        "--preset-mode", default=None,
        choices=["manual", "auto_select", "auto_acoustic"],
        help="Preset workflow",
    )
    parser.add_argument(
        "--output-mode", default=None,
        choices=["4ch", "binaural", "both"],
        help="Output format",
    )
    parser.add_argument("--analysis-seconds", type=float, default=None)
    parser.add_argument("--target-sr", type=int, default=None)
    parser.add_argument(
        "--auto-acoustic-rear-enhancement", action="store_true",
        help="Apply safe rear enhancement plan when using auto_acoustic",
    )
    parser.add_argument(
        "--phase5a-rear-content-candidate", action="store_true",
        help="Enable isolated Phase 5A.2 rear-content A/B candidate.",
    )
    parser.add_argument(
        "--phase5a-v31-candidate", action="store_true",
        help="Enable profiled Phase 5A V3.1 golden candidate.",
    )
    parser.add_argument("--export-binaural-front-pair", action="store_true")
    parser.add_argument("--export-binaural-rear-pair", action="store_true")
    parser.add_argument("--export-binaural-ctc-4ch", action="store_true")
    parser.add_argument("--ctc-regularization", type=float, default=None)
    parser.add_argument("--ctc-ir-length-samples", type=int, default=None)
    parser.add_argument("--no-diagnostics", action="store_true")
    parser.add_argument("--quality-thresholds", default=None, help="Quality thresholds JSON path")
    parser.add_argument("--diagnostics-only", action="store_true", help="Analyze and write diagnostics without exporting WAV files")
    parser.add_argument("--write-quality-report", action="store_true", help="Write a Markdown quality report for the current manifest")
    parser.add_argument(
        "--no-spatial-safety",
        action="store_true",
        help="Disable rear-channel safety guards while still reporting quality metrics.",
    )
    parser.add_argument(
        "--auto-acoustic-refine", action="store_true", default=None,
        help="Enable closed-loop auto_acoustic refinement.",
    )
    parser.add_argument(
        "--no-auto-acoustic-refine", action="store_true", default=None,
        help="Disable closed-loop auto_acoustic refinement.",
    )
    parser.add_argument(
        "--auto-acoustic-refine-passes", type=int, default=None,
        help="Number of refine passes (default from config_center).",
    )
    parser.add_argument(
        "--auto-acoustic-refine-max-step", type=float, default=None,
        help="Refine step size 0.0-1.0 (default from config_center).",
    )
    args = parser.parse_args()
    if args.phase5a_rear_content_candidate and args.phase5a_v31_candidate:
        parser.error("V3 and V3.1 candidate switches are mutually exclusive")

    # ---- resolve files to process ----
    files = resolve_input_files(args)
    if not files:
        print(f"No supported audio files found in {cfg.INPUT_AUDIO_DIR}")
        print("Put audio files into input_audio/ or pass a file path as CLI argument.")
        return

    options = build_options(args)

    # Generate room RIR once for all files (if enabled)
    if options["export_binaural_room_rir"] and options["output_mode"] in {"binaural", "both"}:
        sample_rate = options["target_sr"]
        room_ir = make_small_dry_room_stereo_rir(
            sample_rate,
            rt60=cfg.ROOM_RIR_RT60_SECONDS,
            length_seconds=cfg.ROOM_RIR_LENGTH_SECONDS,
            late_start_seconds=cfg.ROOM_RIR_LATE_START_SECONDS,
            seed=cfg.ROOM_RIR_RANDOM_SEED,
        )
        options["room_ir"] = room_ir
        print(f"Room RIR: small/dry RT60={cfg.ROOM_RIR_RT60_SECONDS:.2f}s "
              f"len={cfg.ROOM_RIR_LENGTH_SECONDS:.2f}s seed={cfg.ROOM_RIR_RANDOM_SEED}")
    else:
        options["room_ir"] = None

    manifest = []
    out_dir = Path(args.out_dir).expanduser()

    for file_path in files:
        manifest.append(process_file(file_path, out_dir, options))

    manifest_path = out_dir / "batch_manifest.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"\nBatch manifest: {manifest_path}")

    if options.get("write_quality_report"):
        report_path = out_dir / "quality_report.md"
        write_manifest_report(manifest, report_path)
        print(f"Quality report: {report_path}")


if __name__ == "__main__":
    main()
