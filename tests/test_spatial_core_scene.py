import json

import numpy as np
import pytest
import soundfile as sf

from spatial_core import FoaBed, SpatialObject, SpatialScene, load_scene, save_scene


def test_scene_manifest_round_trip_resamples_and_pads_audio(tmp_path):
    scene = SpatialScene(
        sample_rate=48_000,
        objects=[
            SpatialObject(
                object_id="lead",
                role="front",
                audio=np.ones(240, dtype=np.float32),
                azimuth_deg=15.0,
                elevation_deg=5.0,
                distance_m=1.5,
            )
        ],
        bed=FoaBed(np.ones((480, 4), dtype=np.float32) * 0.1),
    )

    manifest = save_scene(scene, tmp_path / "scene.json")
    loaded = load_scene(manifest)

    assert loaded.sample_rate == 48_000
    assert loaded.num_frames == 480
    assert loaded.objects[0].audio.shape == (480,)
    assert np.allclose(loaded.objects[0].audio[:240], 1.0, atol=2e-4)
    assert np.allclose(loaded.objects[0].audio[240:], 0.0, atol=2e-4)
    assert loaded.bed is not None
    assert loaded.bed.audio.shape == (480, 4)

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["format"] == "bds_spatial_scene"
    assert payload["version"] == "2.0"
    assert payload["foa_convention"] == "AmbiX ACN/SN3D (W,Y,Z,X)"


def test_scene_manifest_rejects_missing_audio(tmp_path):
    manifest = tmp_path / "scene.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "bds_spatial_scene",
                "version": "2.0",
                "sample_rate": 48_000,
                "objects": [
                    {
                        "id": "missing",
                        "role": "front",
                        "audio": "missing.wav",
                        "position": {"azimuth": 0, "elevation": 0, "distance": 1},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="audio file does not exist"):
        load_scene(manifest)


def test_scene_manifest_resamples_to_declared_sample_rate(tmp_path):
    sf.write(tmp_path / "object.wav", np.ones(240, dtype=np.float32), 24_000)
    manifest = tmp_path / "scene.json"
    manifest.write_text(
        json.dumps(
            {
                "format": "bds_spatial_scene",
                "version": "2.0",
                "sample_rate": 48_000,
                "objects": [
                    {
                        "id": "lead",
                        "role": "front",
                        "audio": "object.wav",
                        "position": {"azimuth": 0, "elevation": 0, "distance": 1},
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    scene = load_scene(manifest)

    assert scene.objects[0].audio.shape == (480,)
    assert np.mean(scene.objects[0].audio) == pytest.approx(1.0, abs=0.02)
