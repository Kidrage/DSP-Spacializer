import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf


def _write_wav(path, freq, sr=16000, seconds=0.35):
    t = np.arange(int(sr * seconds)) / sr
    left = 0.15 * np.sin(2 * np.pi * freq * t)
    right = 0.12 * np.sin(2 * np.pi * (freq * 1.01) * t + 0.2)
    audio = np.stack([left, right], axis=1).astype(np.float32)
    sf.write(path, audio, sr)


def test_batch_script_generates_metrics_summary_report_and_diagnostics(tmp_path):
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "out"
    input_dir.mkdir()
    for i, freq in enumerate([220, 330, 440], 1):
        _write_wav(input_dir / f"test_{i}.wav", freq)

    cmd = [
        sys.executable,
        "batch_spatial_diagnostics.py",
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(output_dir),
        "--preset-mode",
        "auto_acoustic",
        "--output-mode",
        "4ch",
        "--target-sr",
        "16000",
        "--analysis-seconds",
        "0.2",
    ]
    subprocess.run(cmd, check=True)

    assert (output_dir / "batch_metrics.csv").exists()
    assert (output_dir / "batch_summary.json").exists()
    assert (output_dir / "batch_report.md").exists()

    summary = json.loads((output_dir / "batch_summary.json").read_text())
    assert summary["total_tracks"] == 3

    diagnostics = sorted(output_dir.glob("*_diagnostics.json"))
    assert len(diagnostics) == 3
    for path in diagnostics:
        payload = json.loads(path.read_text())
        assert "quality_risk" in payload
        assert "quality_delta" in payload
        assert "over_protection" in payload
