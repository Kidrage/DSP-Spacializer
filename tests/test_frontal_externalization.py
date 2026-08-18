import json
from hashlib import sha256
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import sofar
import soundfile as sf

from spatial_core import SpatialCoreProfile
from spatial_core.frontal_evaluation import (
    frontal_probe_cases,
    load_frontal_corpus,
    render_fex0_baseline,
)


def _write_test_sofa(path):
    directions = [
        (0, 0),
        (45, 0),
        (90, 0),
        (135, 0),
        (180, 0),
        (-135, 0),
        (-90, 0),
        (-45, 0),
        (0, 45),
        (0, -45),
    ]
    sofa = sofar.Sofa("SimpleFreeFieldHRIR")
    sofa.SourcePosition = np.asarray([[az, el, 1] for az, el in directions], dtype=float)
    sofa.Data_IR = np.zeros((len(directions), 2, 32), dtype=float)
    sofa.Data_IR[:, :, 4] = 1.0
    sofa.Data_Delay = np.zeros((len(directions), 2), dtype=float)
    sofa.Data_SamplingRate = 48_000
    sofar.write_sofa(path, sofa)


def test_frontal_probe_matrix_covers_all_requested_angles_and_distances():
    cases = frontal_probe_cases()

    assert len(cases) == 28
    assert {case.azimuth_deg for case in cases} == {-20.0, -10.0, -5.0, 0.0, 5.0, 10.0, 20.0}
    assert {case.distance_m for case in cases} == {0.5, 1.0, 1.6, 2.5}
    assert len({case.case_id for case in cases}) == len(cases)


def test_pinned_corpus_uses_relative_paths_and_sequential_little_blue_sections():
    corpus = load_frontal_corpus(
        Path(__file__).parents[1] / "config" / "frontal_externalization_corpus.json"
    )

    assert len(corpus.tracks) == 3
    assert all(not Path(track.relative_path).is_absolute() for track in corpus.tracks)
    little_blue = next(track for track in corpus.tracks if track.id == "same_mix_sequence")
    assert little_blue.role == "same_mix_sequential_vocals"
    assert [(item.role, item.start_s, item.duration_s) for item in little_blue.excerpts] == [
        ("male_vocal", 30.0, 20.0),
        ("female_vocal", 160.0, 20.0),
    ]


def test_frontal_corpus_rejects_absolute_audio_paths(tmp_path):
    path = tmp_path / "corpus.json"
    path.write_text(
        json.dumps(
            {
                "format": "frontal_externalization_corpus",
                "version": "1.0",
                "tracks": [
                    {
                        "id": "male_reference",
                        "role": "independent_male_vocal_mix",
                        "relative_path": "/private/music/song.wav",
                        "sha256": "0" * 64,
                        "excerpts": [
                            {
                                "id": "male_center",
                                "role": "male_vocal",
                                "start_s": 0,
                                "duration_s": 20,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="root-relative"):
        load_frontal_corpus(path)


def test_fex0_baseline_bundle_is_complete_and_does_not_persist_absolute_paths(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    audio_path = library / "song.wav"
    time = np.arange(2_400, dtype=np.float64) / 48_000
    stereo = np.stack(
        [0.02 * np.sin(2 * np.pi * 220 * time), 0.02 * np.sin(2 * np.pi * 330 * time)],
        axis=1,
    ).astype(np.float32)
    sf.write(audio_path, stereo, 48_000, subtype="FLOAT")
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(
        json.dumps(
            {
                "format": "frontal_externalization_corpus",
                "version": "1.0",
                "tracks": [
                    {
                        "id": "male_reference",
                        "role": "independent_male_vocal_mix",
                        "relative_path": "song.wav",
                        "sha256": sha256(audio_path.read_bytes()).hexdigest(),
                        "excerpts": [
                            {
                                "id": "male_center",
                                "role": "male_vocal",
                                "start_s": 0.0,
                                "duration_s": 0.02,
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sofa_path = tmp_path / "listener.sofa"
    _write_test_sofa(sofa_path)

    with pytest.warns(RuntimeWarning, match="SOFA directional coverage is sparse"):
        manifest_path = render_fex0_baseline(
            corpus=load_frontal_corpus(corpus_path),
            library_root=library,
            sofa_path=sofa_path,
            output_dir=tmp_path / "baseline",
            profile=SpatialCoreProfile(),
            source_revision="test-revision",
            probe_duration_s=0.01,
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["format"] == "frontal_externalization_baseline"
    assert manifest["stage"] == "FEX-0"
    assert len(manifest["artifacts"]) == 57
    assert str(tmp_path.resolve()) not in serialized
    assert "library_root" not in serialized
    for artifact in manifest["artifacts"]:
        assert not Path(artifact["audio_file"]).is_absolute()
        assert (manifest_path.parent / artifact["audio_file"]).is_file()
        assert not Path(artifact["diagnostics_file"]).is_absolute()
        assert (manifest_path.parent / artifact["diagnostics_file"]).is_file()


def test_fex0_cli_exposes_runtime_roots_without_embedding_them_in_config():
    result = subprocess.run(
        [sys.executable, "run_frontal_externalization_eval.py", "--help"],
        cwd=Path(__file__).parents[1],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--library-root" in result.stdout
    assert "--sofa" in result.stdout
    assert "--output-dir" in result.stdout
    assert "--source-revision" in result.stdout


def test_fex0_manifest_rejects_path_like_source_revisions(tmp_path):
    with pytest.raises(ValueError, match="source_revision"):
        render_fex0_baseline(
            corpus=load_frontal_corpus(
                Path(__file__).parents[1]
                / "config"
                / "frontal_externalization_corpus.json"
            ),
            library_root=tmp_path,
            sofa_path=tmp_path / "missing.sofa",
            output_dir=tmp_path / "baseline",
            profile=SpatialCoreProfile(),
            source_revision="/private/repository/main",
        )


def test_fex0_condition_a_rejects_nonlegacy_profiles(tmp_path):
    with pytest.raises(ValueError, match="condition A requires legacy defaults"):
        render_fex0_baseline(
            corpus=load_frontal_corpus(
                Path(__file__).parents[1]
                / "config"
                / "frontal_externalization_corpus.json"
            ),
            library_root=tmp_path,
            sofa_path=tmp_path / "missing.sofa",
            output_dir=tmp_path / "baseline",
            profile=SpatialCoreProfile(hrtf_compensation_mode="off"),
            source_revision="test-revision",
        )
