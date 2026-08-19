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
    fex1_bd_refinement_conditions,
    fex1_conditions,
    frontal_probe_cases,
    load_frontal_corpus,
    render_fex0_baseline,
    render_fex1_screening,
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


def test_fex1_conditions_are_exact_single_factor_changes_plus_required_interaction():
    conditions = {condition.id: condition for condition in fex1_conditions()}

    assert tuple(conditions) == ("A", "B", "C", "D", "E", "F")
    assert conditions["A"].changed_controls == ()
    assert conditions["B"].changed_controls == ("hrtf_compensation_mode",)
    assert conditions["C"].changed_controls == ("mastered_loudness_mode",)
    assert conditions["D"].changed_controls == ("center_room_send_db",)
    assert conditions["E"].changed_controls == ("reflection_normalization_mode",)
    assert conditions["F"].changed_controls == (
        "hrtf_compensation_mode",
        "mastered_loudness_mode",
        "center_room_send_db",
        "reflection_normalization_mode",
    )
    assert conditions["B"].profile.hrtf_compensation_mode == "off"
    assert conditions["C"].profile.mastered_loudness_mode == "fixed_scene_gain"
    assert conditions["D"].profile.center_room_send_db == 0.0
    assert conditions["E"].profile.reflection_normalization_mode == "physical_path_gain"
    assert conditions["F"].profile == SpatialCoreProfile(
        hrtf_compensation_mode="off",
        mastered_loudness_mode="fixed_scene_gain",
        center_room_send_db=0.0,
        reflection_normalization_mode="physical_path_gain",
    )


def test_fex1_bd_refinement_conditions_dose_only_confirmed_b_and_d_dimensions():
    conditions = {condition.id: condition for condition in fex1_bd_refinement_conditions()}

    assert tuple(conditions) == ("R0", "R1", "R2", "R3", "R4", "R5")
    assert conditions["R0"].changed_controls == ()
    assert conditions["R1"].changed_controls == ("hrtf_compensation_strength",)
    assert conditions["R1"].profile.hrtf_compensation_strength == 0.75
    assert conditions["R2"].profile.hrtf_compensation_strength == 0.5
    assert conditions["R3"].changed_controls == ("center_room_send_db",)
    assert conditions["R3"].profile.center_room_send_db == -1.5
    assert conditions["R4"].profile.center_room_send_db == 0.0
    assert conditions["R5"].changed_controls == (
        "hrtf_compensation_strength",
        "center_room_send_db",
    )
    assert conditions["R5"].profile == SpatialCoreProfile(
        hrtf_compensation_strength=0.75,
        center_room_send_db=-1.5,
    )


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
    assert "hrtf_compensation_strength" not in manifest["parameters"]["profile"]
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


def test_fex1_screening_exports_blind_natural_and_level_matched_conditions(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    audio_path = library / "song.wav"
    sample_rate = 48_000
    time = np.arange(int(0.8 * sample_rate), dtype=np.float64) / sample_rate
    stereo = np.stack(
        [
            0.025 * np.sin(2.0 * np.pi * 220.0 * time),
            0.020 * np.sin(2.0 * np.pi * 330.0 * time),
        ],
        axis=1,
    ).astype(np.float32)
    sf.write(audio_path, stereo, sample_rate, subtype="FLOAT")
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
                                "duration_s": 0.5,
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
        manifest_path = render_fex1_screening(
            corpus=load_frontal_corpus(corpus_path),
            library_root=library,
            sofa_path=sofa_path,
            output_dir=tmp_path / "screening",
            source_revision="test-revision",
        )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    serialized = json.dumps(manifest, ensure_ascii=False)
    assert manifest["format"] == "frontal_externalization_screening"
    assert manifest["stage"] == "FEX-1"
    assert "condition_set" not in manifest["parameters"]
    assert manifest["parameters"]["level_match_reference"] == "A"
    assert all(
        "hrtf_compensation_strength" not in item["profile"]
        for item in manifest["conditions"]
    )
    assert {
        item["id"]: item["parameters_sha256"] for item in manifest["conditions"]
    } == {
        "A": "4cf363a3c0b5eb47ef8e0f2605193c5e7b6bc3ae8c6354d3136c4ccf42e1c1cc",
        "B": "49d6b8af47210e052bdcd4e3b0183fd19513674b05c29aca60c1ae24738e7c19",
        "C": "c776eebc5f748f56a3ee5df7758316f1f2c58c9414f3865964850a43ec35ff3a",
        "D": "447ee5a00eb16a47eab5cb3c66f44e7b85518680cb7a94b4580f7a5058804aa6",
        "E": "d2b04dc39033ce4ce4b7453cd7f98de16b2dea0fa23caf16769a661e394c5220",
        "F": "611521c5b955f41fe2642238cea54e0715b352f992238c2ddfe7ca4c2b2bc50a",
    }
    assert "score_sheet_file" not in manifest
    assert "listening_guide_file" not in manifest
    assert [item["id"] for item in manifest["conditions"]] == list("ABCDEF")
    assert len(manifest["artifacts"]) == 6
    assert str(tmp_path.resolve()) not in serialized
    assert "library_root" not in serialized

    answer_key_path = manifest_path.parent / manifest["answer_key_file"]
    answer_key = json.loads(answer_key_path.read_text(encoding="utf-8"))
    assert set(answer_key["blind_to_condition"].values()) == set("ABCDEF")
    artifact_labels = [artifact["blind_label"] for artifact in manifest["artifacts"]]
    condition_order_labels = [
        next(
            blind
            for blind, condition in answer_key["blind_to_condition"].items()
            if condition == condition_id
        )
        for condition_id in "ABCDEF"
    ]
    assert artifact_labels == sorted(artifact_labels)
    assert artifact_labels != condition_order_labels
    listening_form_path = manifest_path.parent / manifest["listening_form_file"]
    listening_form = json.loads(listening_form_path.read_text(encoding="utf-8"))
    assert listening_form["dimensions"] == [
        "externalization",
        "perceived_distance",
        "center_stability",
        "vocal_clarity",
        "timbre_naturalness",
        "double_image",
        "overall_preference",
    ]
    assert len(listening_form["primary_level_matched_trials"]) == 6
    assert len(listening_form["natural_level_confound_trials"]) == 6
    matched_loudness = []
    for artifact in manifest["artifacts"]:
        for variant in ("natural_level", "level_matched"):
            audio_file = artifact[variant]["audio_file"]
            assert not Path(audio_file).is_absolute()
            rendered_path = manifest_path.parent / audio_file
            assert rendered_path.is_file()
            wav_bytes = rendered_path.read_bytes()
            peak_chunk = wav_bytes.find(b"PEAK")
            assert peak_chunk >= 0
            assert wav_bytes[peak_chunk + 12 : peak_chunk + 16] == b"\0\0\0\0"
        assert (manifest_path.parent / artifact["diagnostics_file"]).is_file()
        assert artifact["level_matched"]["sample_peak"] <= 0.98 + 1e-6
        matched_loudness.append(
            artifact["level_matched"]["integrated_loudness_lkfs"]
        )
    assert max(matched_loudness) - min(matched_loudness) < 0.05

    with pytest.warns(RuntimeWarning, match="SOFA directional coverage is sparse"):
        refinement_manifest_path = render_fex1_screening(
            corpus=load_frontal_corpus(corpus_path),
            library_root=library,
            sofa_path=sofa_path,
            output_dir=tmp_path / "bd-refinement",
            source_revision="test-revision",
            condition_set="bd_refinement",
        )

    refinement = json.loads(refinement_manifest_path.read_text(encoding="utf-8"))
    assert [item["id"] for item in refinement["conditions"]] == [
        "R0",
        "R1",
        "R2",
        "R3",
        "R4",
        "R5",
    ]
    assert refinement["parameters"]["condition_set"] == "bd_refinement"
    assert refinement["parameters"]["level_match_reference"] == "R0"
    refinement_form = json.loads(
        (refinement_manifest_path.parent / refinement["listening_form_file"]).read_text(
            encoding="utf-8"
        )
    )
    assert refinement_form["dimensions"][-2:] == [
        "forehead_elevation",
        "spectral_coloration",
    ]
    assert refinement_form["dimension_guidance"]["forehead_elevation"].startswith(
        "1 = none"
    )
    assert refinement_form["dimension_guidance"]["spectral_coloration"].startswith(
        "1 = none"
    )
    assert all(
        set(trial["ratings"]) == set(refinement_form["dimensions"])
        for trial in refinement_form["primary_level_matched_trials"]
    )
    score_sheet = refinement_manifest_path.parent / refinement["score_sheet_file"]
    score_lines = score_sheet.read_text(encoding="utf-8").splitlines()
    assert len(score_lines) == 7
    assert score_lines[0].split(",") == [
        "trial_id",
        "track_id",
        "excerpt_id",
        "blind_label",
        "audio_file",
        *refinement_form["dimensions"],
        "notes",
        "natural_level_judgment_changed",
        "natural_level_notes",
    ]
    guide = (
        refinement_manifest_path.parent / refinement["listening_guide_file"]
    ).read_text(encoding="utf-8")
    assert "Level-Matched" in guide
    assert "answer_key.json" in guide
    assert "Natural-Level" in guide


def test_fex1_screening_rejects_unknown_condition_sets(tmp_path):
    with pytest.raises(ValueError, match="condition_set"):
        render_fex1_screening(
            corpus=load_frontal_corpus(
                Path(__file__).parents[1]
                / "config"
                / "frontal_externalization_corpus.json"
            ),
            library_root=tmp_path,
            sofa_path=tmp_path / "missing.sofa",
            output_dir=tmp_path / "screening",
            source_revision="test-revision",
            condition_set="custom",
        )


def test_fex1_cli_exposes_only_runtime_paths_and_reproducibility_inputs():
    result = subprocess.run(
        [sys.executable, "run_frontal_externalization_fex1.py", "--help"],
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
    assert "--condition-set" in result.stdout
    assert "--profile" not in result.stdout
