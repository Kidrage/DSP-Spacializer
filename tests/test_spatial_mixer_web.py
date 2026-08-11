import numpy as np
from pathlib import Path
import soundfile as sf
import subprocess
import sys
from fastapi.testclient import TestClient

from spatial_mixer.campaign import MixerService
from web_ui.server import create_app


ROOT = Path(__file__).resolve().parents[1]


class PassthroughRenderer:
    def render(self, stereo, sample_rate, profile, audition):
        return stereo, {"renderer": "test"}


class MissingDependencyRenderer:
    def render(self, stereo, sample_rate, profile, audition):
        raise RuntimeError("measured-SOFA reader is unavailable")


def test_local_web_interface_exposes_state_preview_and_allowlisted_audio(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    audio = np.zeros((48_000, 2), dtype=np.float32)
    audio[:, 0] = 0.05
    audio[:, 1] = 0.05
    sf.write(library / "track.wav", audio, 48_000, subtype="FLOAT")
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=PassthroughRenderer(),
    )
    client = TestClient(create_app(service))

    page = client.get("/")
    assert page.status_code == 200
    assert "七区" in page.text

    state = client.get("/api/state").json()
    response = client.patch("/api/draft", json={"zones": {"bass": {"gain_db": 0.5}}})
    assert response.status_code == 200
    preview = client.post(
        "/api/preview",
        json={"track_id": state["tracks"][0]["track_id"], "start_s": 0, "duration_s": 1},
    ).json()
    audio_response = client.get(f"/api/audio/{preview['preview_id']}/reference")
    assert audio_response.status_code == 200
    assert audio_response.headers["content-type"].startswith("audio/")
    assert client.get("/api/audio/not-a-cache/reference").status_code == 404


def test_local_mixer_launcher_documents_required_roots():
    result = subprocess.run(
        [sys.executable, "run_spatial_mixer.py", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "--library-dir" in result.stdout
    assert "--sofa" in result.stdout
    assert "127.0.0.1" in result.stdout


def test_preview_runtime_dependency_error_is_shown_as_actionable_response(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    sf.write(library / "track.wav", np.ones((4800, 2), dtype=np.float32) * 0.01, 48_000)
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=MissingDependencyRenderer(),
    )
    client = TestClient(create_app(service))
    track_id = client.get("/api/state").json()["tracks"][0]["track_id"]

    response = client.post(
        "/api/preview",
        json={"track_id": track_id, "start_s": 0, "duration_s": 1},
    )

    assert response.status_code == 422
    assert response.json()["detail"] == "measured-SOFA reader is unavailable"
