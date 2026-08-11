import numpy as np
import pytest
import soundfile as sf

from spatial_mixer import MixerProfile
from spatial_mixer.campaign import MixerService


class FakeRenderer:
    def __init__(self):
        self.calls = 0

    def render(self, stereo, sample_rate, profile, audition):
        self.calls += 1
        gain = 10.0 ** (profile.zones["bass"].gain_db / 20.0)
        return stereo * gain, {"fake": True}


class RedClarityRenderer(FakeRenderer):
    def render(self, stereo, sample_rate, profile, audition):
        self.calls += 1
        return np.stack([stereo[:, 0], -stereo[:, 1]], axis=1), {"fake": True}


def _write_track(path, frequency=440.0):
    sample_rate = 48_000
    t = np.arange(sample_rate, dtype=np.float64) / sample_rate
    mono = 0.1 * np.sin(2.0 * np.pi * frequency * t)
    sf.write(path, np.stack([mono, mono], axis=1), sample_rate, subtype="FLOAT")


def test_campaign_keeps_a_immutable_and_caches_profile_hashed_previews(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    _write_track(library / "reference.wav")
    renderer = FakeRenderer()
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=renderer,
    )

    initial = service.open_campaign()
    accepted_hash = initial["accepted"]["profile_hash"]
    revised = service.patch_draft({"zones": {"bass": {"gain_db": 1.0}}})

    assert revised["accepted"]["profile_hash"] == accepted_hash
    assert revised["draft"]["profile_hash"] != accepted_hash
    assert (tmp_path / "workspace" / "revisions" / f"{revised['draft']['profile_hash']}.json").is_file()

    track_id = revised["tracks"][0]["track_id"]
    first = service.request_preview(track_id=track_id, start_s=0.0, duration_s=1.0)
    second = service.request_preview(track_id=track_id, start_s=0.0, duration_s=1.0)

    assert first["preview_id"] == second["preview_id"]
    assert first["cached"] is False
    assert second["cached"] is True
    assert renderer.calls == 2
    assert set(first["audio"]) == {"reference", "1", "2"}
    assert len(first["waveform"]) == 240
    assert "blind_order" not in first
    assert "diagnostics" not in first
    assert all(path.startswith("/api/audio/") for path in first["audio"].values())
    assert all(
        (tmp_path / "workspace" / "previews" / first["preview_id"] / f"{variant}.wav").is_file()
        for variant in ("reference", "a", "b")
    )

    draft_hash = revised["draft"]["profile_hash"]
    monitored = service.patch_monitor({"output_gain_db": -2.0})
    assert monitored["draft"]["profile_hash"] == draft_hash
    assert "monitor" not in MixerProfile.default().to_payload()

    lab = service.analyze_extraction(track_id=track_id, start_s=0.0, duration_s=1.0)
    assert set(lab["zones"]) == set(MixerProfile.default().zones)
    assert all(len(zone["spectrum"]) == 36 for zone in lab["zones"].values())
    assert lab["reconstruction_error_db"] < -80.0
    assert lab["stft"] == {"size": 2048, "hop": 512, "editable": False}

    reopened = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=FakeRenderer(),
    ).open_campaign()
    assert reopened["draft"]["profile_hash"] == draft_hash
    assert reopened["monitor"]["output_gain_db"] == -2.0


def test_promotion_requires_nine_tracks_six_classes_and_audits_red_override(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    for index in range(9):
        _write_track(library / f"track-{index}.wav", 220.0 + index * 30.0)
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=RedClarityRenderer(),
    )
    service.patch_draft({"zones": {"bass": {"gain_db": 0.5}}})
    state = service.open_campaign()
    categories = ["pop", "ballad", "cinematic", "world", "jazz", "electronic"]
    for index, track in enumerate(state["tracks"]):
        preview = service.request_preview(
            track_id=track["track_id"], start_s=0.0, duration_s=1.0
        )
        assert preview["objective_gate"]["pass"] is False
        service.record_comparison(
            track_id=track["track_id"],
            category=categories[index % len(categories)],
            choice="2",
            scores={"clarity": 8, "bass": 8, "depth": 8, "externalization": 8},
            preview_id=preview["preview_id"],
            notes="calibration excerpt",
        )

    with pytest.raises(ValueError, match="override reason"):
        service.promote_profile()

    result = service.promote_profile(override_reason="Listening result is preferred across all six classes.")

    assert result["promoted"] is True
    assert result["objective_override"] is True
    assert result["track_count"] == 9
    assert result["category_count"] == 6
    assert all((tmp_path / "workspace" / path).is_file() for path in result["exports"].values())
    assert service.open_campaign()["accepted"]["profile_hash"] == state["draft"]["profile_hash"]


def test_campaign_discovers_mp3_calibration_tracks(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    audio = np.zeros((4800, 2), dtype=np.float32)
    sf.write(library / "孤勇者.mp3", audio, 48_000, format="WAV", subtype="FLOAT")

    state = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=FakeRenderer(),
    ).open_campaign()

    assert state["tracks"][0]["name"] == "孤勇者"
    assert state["tracks"][0]["suggested_category"] == "pop"


def test_preview_renders_once_when_a_and_b_are_identical(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    _write_track(library / "reference.wav")
    renderer = FakeRenderer()
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=renderer,
    )
    track_id = service.open_campaign()["tracks"][0]["track_id"]

    service.request_preview(track_id=track_id, start_s=0.0, duration_s=1.0)

    assert renderer.calls == 1


def test_comparison_must_bind_to_a_server_preview_for_the_current_profile(tmp_path):
    library = tmp_path / "library"
    library.mkdir()
    _write_track(library / "reference.wav")
    service = MixerService(
        library_dir=library,
        workspace_dir=tmp_path / "workspace",
        renderer=FakeRenderer(),
    )
    track_id = service.open_campaign()["tracks"][0]["track_id"]

    with pytest.raises(ValueError, match="preview"):
        service.record_comparison(
            track_id=track_id,
            category="pop",
            choice="2",
            scores={"clarity": 8, "bass": 8, "depth": 8, "externalization": 8},
            preview_id="not-a-preview",
        )

    preview = service.request_preview(track_id=track_id, start_s=0.0, duration_s=1.0)
    service.patch_draft({"zones": {"bass": {"gain_db": 1.0}}})
    with pytest.raises(ValueError, match="current draft"):
        service.record_comparison(
            track_id=track_id,
            category="pop",
            choice="2",
            scores={"clarity": 8, "bass": 8, "depth": 8, "externalization": 8},
            preview_id=preview["preview_id"],
        )
