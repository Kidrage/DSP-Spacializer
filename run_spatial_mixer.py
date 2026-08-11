#!/usr/bin/env python3
"""Launch the local-only seven-zone calibration mixer."""

from __future__ import annotations

from pathlib import Path
import argparse

import uvicorn

from spatial_mixer.campaign import MixerService
from web_ui.server import create_app


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the seven-zone calibration mixer on http://127.0.0.1 only."
    )
    parser.add_argument(
        "--library-dir",
        required=True,
        help="Allowlisted directory containing calibration music",
    )
    parser.add_argument(
        "--sofa",
        required=True,
        help="Measured SimpleFreeFieldHRIR SOFA file",
    )
    parser.add_argument(
        "--workspace-dir",
        default=str(Path.home() / ".spatializer" / "calibration"),
        help="Directory for campaign state, previews, and immutable exports",
    )
    parser.add_argument("--port", type=int, default=8765, help="Local TCP port (default: 8765)")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not 1 <= args.port <= 65_535:
        raise SystemExit("--port must be within [1, 65535]")
    service = MixerService(
        library_dir=args.library_dir,
        workspace_dir=args.workspace_dir,
        sofa_path=args.sofa,
    )
    print(f"Seven-zone calibration mixer: http://127.0.0.1:{args.port}")
    uvicorn.run(create_app(service), host="127.0.0.1", port=args.port, log_level="info")


if __name__ == "__main__":
    main()
