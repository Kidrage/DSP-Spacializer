#!/usr/bin/env python3
"""Rebuild a complete manifest from per-track diagnostics and repair stale paths."""

import argparse
import json
from pathlib import Path


WORKSPACE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_LIBRARY = WORKSPACE_DIR / "曲库"
DEFAULT_OUTPUT = WORKSPACE_DIR / "Output-DSP"
AUDIO_EXTENSIONS = {".wav", ".flac", ".aiff", ".aif", ".ogg", ".mp3", ".m4a"}


def safe_stem(path):
    return Path(path).stem.replace(" ", "_").replace("(", "").replace(")", "")


def repair_diagnostics_paths(diagnostics, input_path, diagnostics_path, output_dir):
    diagnostics["input_file"] = str(input_path.resolve())
    output_paths = diagnostics.get("output_paths", {})
    repaired = {}
    for name, old_path in output_paths.items():
        candidate = diagnostics_path if name == "diagnostics" else output_dir / Path(old_path).name
        if candidate.exists():
            repaired[name] = str(candidate.resolve())
    diagnostics["output_paths"] = repaired
    primary = repaired.get("4ch") or repaired.get("binaural_4p0")
    if primary:
        diagnostics["output_file"] = primary
    return diagnostics


def rebuild(library_dir, output_dir, preset, repair_paths):
    audio_files = sorted(
        path for path in library_dir.iterdir()
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )
    manifest = []
    missing = []
    for input_path in audio_files:
        diagnostics_path = output_dir / f"{safe_stem(input_path)}_{preset}_diagnostics.json"
        if not diagnostics_path.exists():
            missing.append(input_path)
            continue
        diagnostics = json.loads(diagnostics_path.read_text(encoding="utf-8"))
        diagnostics = repair_diagnostics_paths(
            diagnostics, input_path, diagnostics_path, output_dir
        )
        if repair_paths:
            diagnostics_path.write_text(
                json.dumps(diagnostics, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        manifest.append(diagnostics)
    return manifest, missing


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-dir", type=Path, default=DEFAULT_LIBRARY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--preset", default="auto_acoustic")
    parser.add_argument("--repair-paths", action="store_true")
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()
    manifest, missing = rebuild(
        args.library_dir.resolve(), args.output_dir.resolve(), args.preset, args.repair_paths
    )
    manifest_path = args.output_dir / "batch_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"Wrote {manifest_path}: {len(manifest)} tracks")
    if missing:
        print("Missing diagnostics:")
        for path in missing:
            print(f"  {path}")
        if not args.allow_missing:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
