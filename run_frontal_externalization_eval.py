#!/usr/bin/env python3
"""Render the opt-in FEX-0 frontal binaural baseline bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spatial_core.frontal_evaluation import load_frontal_corpus, render_fex0_baseline
from spatial_core.profile import load_spatial_profile


REPOSITORY_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = REPOSITORY_ROOT / "config" / "frontal_externalization_corpus.json"
DEFAULT_PROFILE = (
    REPOSITORY_ROOT / "profiles" / "spatial_core_frontal_externalization_fex0.json"
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Render the path-safe Spatial Core FEX-0 baseline bundle."
    )
    parser.add_argument(
        "--library-root",
        required=True,
        help="Runtime audio-library root; never persisted in the output manifest.",
    )
    parser.add_argument("--sofa", required=True, help="Measured SimpleFreeFieldHRIR SOFA file.")
    parser.add_argument("--output-dir", required=True, help="New or empty baseline output directory.")
    parser.add_argument(
        "--source-revision",
        required=True,
        help="Git revision recorded in the reproducibility manifest.",
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--profile", default=str(DEFAULT_PROFILE))
    parser.add_argument("--probe-duration-s", type=float, default=1.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest_path = render_fex0_baseline(
            corpus=load_frontal_corpus(args.corpus),
            library_root=args.library_root,
            sofa_path=args.sofa,
            output_dir=args.output_dir,
            profile=load_spatial_profile(args.profile),
            source_revision=args.source_revision,
            probe_duration_s=args.probe_duration_s,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(json.dumps({"manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
