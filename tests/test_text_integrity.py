import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_text_integrity_script_passes():
    subprocess.run(
        [sys.executable, "scripts/check_text_integrity.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
