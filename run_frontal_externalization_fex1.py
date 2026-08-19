#!/usr/bin/env python3
"""Render a locked FEX-1 frontal binaural screening bundle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from spatial_core.frontal_evaluation import load_frontal_corpus, render_fex1_screening


REPOSITORY_ROOT = Path(__file__).resolve().parent
DEFAULT_CORPUS = REPOSITORY_ROOT / "config" / "frontal_externalization_corpus.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Render a fixed FEX-1 screening set as Natural-Level and "
            "BS.1770 Level-Matched Evaluation files."
        )
    )
    parser.add_argument(
        "--library-root",
        required=True,
        help="Runtime audio-library root; never persisted in the output manifest.",
    )
    parser.add_argument("--sofa", required=True, help="Measured SimpleFreeFieldHRIR SOFA file.")
    parser.add_argument("--output-dir", required=True, help="New or empty screening directory.")
    parser.add_argument(
        "--source-revision",
        required=True,
        help="Git revision recorded in the reproducibility manifest.",
    )
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--peak-ceiling", type=float, default=0.98)
    parser.add_argument(
        "--condition-set",
        choices=("initial", "bd_refinement"),
        default="initial",
        help="Locked causal matrix to render (default: initial).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        manifest_path = render_fex1_screening(
            corpus=load_frontal_corpus(args.corpus),
            library_root=args.library_root,
            sofa_path=args.sofa,
            output_dir=args.output_dir,
            source_revision=args.source_revision,
            peak_ceiling=args.peak_ceiling,
            condition_set=args.condition_set,
        )
    except ValueError as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(json.dumps({"manifest": str(manifest_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
