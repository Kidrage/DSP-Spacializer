import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_help_lists_pseudo_renderer():
    result = subprocess.run(
        [sys.executable, "run_spatializer.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "--pseudo-renderer" in result.stdout
    assert "hybrid_vbap_v1" in result.stdout
