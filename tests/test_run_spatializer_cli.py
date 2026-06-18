import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_help_lists_stable_legacy_options_only():
    result = subprocess.run(
        [sys.executable, "run_spatializer.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "--preset-mode" in result.stdout
    assert "--output-mode" in result.stdout
    assert "--export-binaural-front-pair" in result.stdout
    assert "--export-binaural-rear-pair" in result.stdout
    assert "--export-binaural-ctc-4ch" in result.stdout
    assert "--diagnostics-only" in result.stdout
    assert "--write-quality-report" in result.stdout
    assert "--no-spatial-safety" in result.stdout
    assert "--export-pseudo-scene" not in result.stdout
    assert "--decode-pseudo-scene" not in result.stdout
    assert "--pseudo-scene-only" not in result.stdout
    assert "--pseudo-renderer" not in result.stdout
