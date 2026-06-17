import numpy as np
import pytest

from object_decoder import decode_scene_to_layout, decode_scene_to_layout_with_diagnostics
from pseudo_object_scene import build_object_audio_for_scene, build_pseudo_object_scene
from renderers.base import RenderResult
from speaker_layout import default_quad_4p0_layout


def _dummy_scene_and_audio(sr=48000):
    n = sr
    t = np.linspace(0, 1.0, n, endpoint=False)
    layers = {
        "bass": np.sin(2 * np.pi * 80 * t).astype(np.float32),
        "low_body": np.sin(2 * np.pi * 180 * t).astype(np.float32),
        "front_L": np.sin(2 * np.pi * 440 * t).astype(np.float32),
        "front_R": np.sin(2 * np.pi * 550 * t).astype(np.float32),
        "side_width": np.sin(2 * np.pi * 700 * t).astype(np.float32),
        "rear_ambience": np.sin(2 * np.pi * 900 * t).astype(np.float32),
        "high_air": np.sin(2 * np.pi * 4000 * t).astype(np.float32) * 0.2,
    }
    analysis = {"stereo_width": 0.4, "high_diffuse_ratio": 0.5}
    routing = {
        "bass_gain": 1.0,
        "side_front": 0.4,
        "side_rear": 0.6,
        "amb_rear": 0.7,
        "air_rear": 0.4,
        "decorrelation": 0.2,
        "lowbody_rear": 0.2,
    }
    scene = build_pseudo_object_scene(
        "dummy.wav",
        layers["front_L"],
        layers["front_R"],
        layers,
        analysis,
        routing,
        "auto_acoustic",
        "auto_acoustic",
        sr,
        1.0,
        export_object_audio=False,
    )
    return scene, build_object_audio_for_scene(layers)


@pytest.mark.parametrize("mode", ["dbap_quad_v1", "vbap_2d_v1", "hybrid_vbap_v1"])
def test_decode_modes_return_array(mode):
    scene, object_audio = _dummy_scene_and_audio()
    out = decode_scene_to_layout(scene, object_audio, default_quad_4p0_layout(), 48000, mode)
    assert out.shape == (48000, 4)
    assert np.isfinite(out).all()


def test_invalid_decoder_mode_fails():
    scene, object_audio = _dummy_scene_and_audio()
    with pytest.raises(ValueError):
        decode_scene_to_layout(scene, object_audio, default_quad_4p0_layout(), 48000, "bad_mode")


def test_decode_with_diagnostics_returns_render_result():
    scene, object_audio = _dummy_scene_and_audio()
    result = decode_scene_to_layout_with_diagnostics(
        scene,
        object_audio,
        default_quad_4p0_layout(),
        48000,
        "hybrid_vbap_v1",
    )
    assert isinstance(result, RenderResult)
    assert result.feeds.shape == (48000, 4)
    assert result.renderer_name == "hybrid_vbap_v1"
    assert "bass_anchor" in result.gains_by_object


def test_bass_anchor_prefers_front_when_isolated():
    scene, object_audio = _dummy_scene_and_audio()
    scene["objects"] = [obj for obj in scene["objects"] if obj["id"] == "bass_anchor"]
    object_audio = {"bass_anchor": object_audio["bass_anchor"]}
    out = decode_scene_to_layout(scene, object_audio, default_quad_4p0_layout(), 48000)
    front = np.mean(out[:, :2] ** 2)
    rear = np.mean(out[:, 2:] ** 2)
    assert front > rear * 5.0


def test_rear_ambience_prefers_rear_when_isolated():
    scene, object_audio = _dummy_scene_and_audio()
    scene["objects"] = [obj for obj in scene["objects"] if obj["id"] == "rear_ambience"]
    object_audio = {"rear_ambience": object_audio["rear_ambience"]}
    out = decode_scene_to_layout(scene, object_audio, default_quad_4p0_layout(), 48000)
    front = np.mean(out[:, :2] ** 2)
    rear = np.mean(out[:, 2:] ** 2)
    assert rear > front * 5.0
