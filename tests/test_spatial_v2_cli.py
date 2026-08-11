import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import sofar
import soundfile as sf


ROOT = Path(__file__).resolve().parents[1]


def _write_dense_test_sofa(path):
    directions = [(azimuth, 0) for azimuth in range(-180, 180, 30)]
    directions += [(azimuth, elevation) for elevation in (-45, 45) for azimuth in range(-180, 180, 60)]
    sofa = sofar.Sofa("SimpleFreeFieldHRIR")
    sofa.SourcePosition = np.asarray([[azimuth, elevation, 1] for azimuth, elevation in directions])
    sofa.Data_IR = np.zeros((len(directions), 2, 32), dtype=float)
    sofa.Data_IR[:, 0, 4] = 1.0
    sofa.Data_IR[:, 1, 5] = 1.0
    sofa.Data_Delay = np.zeros((len(directions), 2), dtype=float)
    sofa.Data_SamplingRate = 48_000
    sofar.write_sofa(path, sofa)


def test_spatial_v2_cli_renders_distinct_outputs_and_exports_scene(tmp_path):
    frames = 1024
    phase = np.arange(frames) / 48_000
    stereo = np.stack(
        [0.05 * np.sin(2 * np.pi * 440 * phase), 0.05 * np.sin(2 * np.pi * 550 * phase)],
        axis=1,
    ).astype(np.float32)
    input_path = tmp_path / "input.wav"
    sofa_path = tmp_path / "listener.sofa"
    output_dir = tmp_path / "outputs"
    scene_path = tmp_path / "exported_scene.json"
    sf.write(input_path, stereo, 48_000)
    _write_dense_test_sofa(sofa_path)

    result = subprocess.run(
        [
            sys.executable,
            "run_spatializer.py",
            str(input_path),
            "--engine",
            "spatial-v2",
            "--sofa",
            str(sofa_path),
            "--output-mode",
            "both",
            "--room-profile",
            "off",
            "--export-scene",
            str(scene_path),
            "--out-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert (output_dir / "input_spatial_v2_binaural.wav").is_file()
    assert (output_dir / "input_spatial_v2_quad.wav").is_file()
    assert scene_path.is_file()
    manifest = json.loads((output_dir / "spatial_v2_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["engine"] == "spatial-v2"
    assert set(manifest[0]["outputs"]) == {"binaural", "quad"}


def test_spatial_v2_cli_applies_profile_to_scene_and_balanced_room(tmp_path):
    frames = 2048
    time = np.arange(frames) / 48_000
    stereo = np.stack(
        [0.03 * np.sin(2 * np.pi * 330 * time), 0.03 * np.sin(2 * np.pi * 330 * time)],
        axis=1,
    ).astype(np.float32)
    input_path = tmp_path / "input.wav"
    sofa_path = tmp_path / "listener.sofa"
    profile_path = tmp_path / "profile.json"
    output_dir = tmp_path / "outputs"
    scene_path = tmp_path / "scene.json"
    sf.write(input_path, stereo, 48_000)
    _write_dense_test_sofa(sofa_path)
    profile_path.write_text(
        json.dumps(
            {
                "format": "spatial_core_profile",
                "version": "1.0",
                "parameters": {"front_distance_m": 2.0, "front_width_deg": 48.0},
            }
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "run_spatializer.py",
            str(input_path),
            "--engine",
            "spatial-v2",
            "--sofa",
            str(sofa_path),
            "--spatial-profile",
            str(profile_path),
            "--room-profile",
            "balanced-depth",
            "--export-scene",
            str(scene_path),
            "--out-dir",
            str(output_dir),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    manifest = json.loads((output_dir / "spatial_v2_manifest.json").read_text(encoding="utf-8"))
    assert manifest[0]["diagnostics"]["binaural"]["room_profile"]["name"] == "balanced-depth"
    assert manifest[0]["diagnostics"]["binaural"]["block_size"] == 8_192
    scene = json.loads(scene_path.read_text(encoding="utf-8"))
    assert scene["metadata"]["profile"]["front_distance_m"] == 2.0
    assert scene["metadata"]["profile"]["front_width_deg"] == 48.0
