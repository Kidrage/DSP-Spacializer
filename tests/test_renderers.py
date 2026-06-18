import numpy as np
import pytest

from pseudo_object_scene import build_object_audio_for_scene, build_pseudo_object_scene
from renderers.dbap_renderer import DbapRenderer
from renderers.hybrid_renderer import HybridPseudoObjectRenderer
from renderers.vbap_2d import Vbap2DRenderer
from speaker_layout import default_quad_4p0_layout


def _scene_and_audio(sr=24000):
    n = sr // 2
    t = np.linspace(0, 0.5, n, endpoint=False)
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
        n / sr,
        export_object_audio=False,
    )
    return scene, build_object_audio_for_scene(layers), sr, n


@pytest.mark.parametrize("renderer_cls", [DbapRenderer, Vbap2DRenderer, HybridPseudoObjectRenderer])
def test_renderer_shape_finiteness_and_gains(renderer_cls):
    scene, object_audio, sr, n = _scene_and_audio()
    result = renderer_cls().render(scene, object_audio, default_quad_4p0_layout(), sr)
    assert result.feeds.shape == (n, 4)
    assert np.isfinite(result.feeds).all()
    assert set(result.gains_by_object) == {obj["id"] for obj in scene["objects"]}


def test_hybrid_directional_energy_preferences():
    scene, object_audio, sr, _ = _scene_and_audio()
    renderer = HybridPseudoObjectRenderer()
    layout = default_quad_4p0_layout()

    bass_scene = dict(scene, objects=[obj for obj in scene["objects"] if obj["id"] == "bass_anchor"])
    bass = renderer.render(bass_scene, {"bass_anchor": object_audio["bass_anchor"]}, layout, sr).feeds
    assert np.mean(bass[:, :2] ** 2) > np.mean(bass[:, 2:] ** 2) * 5.0

    rear_scene = dict(scene, objects=[obj for obj in scene["objects"] if obj["id"] == "rear_ambience"])
    rear = renderer.render(rear_scene, {"rear_ambience": object_audio["rear_ambience"]}, layout, sr).feeds
    assert np.mean(rear[:, 2:] ** 2) > np.mean(rear[:, :2] ** 2) * 5.0

    side_scene = dict(scene, objects=[obj for obj in scene["objects"] if obj["id"] == "side_width"])
    side = renderer.render(side_scene, {"side_width": object_audio["side_width"]}, layout, sr).feeds
    right_side = np.mean(side[:, [1, 3]] ** 2)
    left_side = np.mean(side[:, [0, 2]] ** 2)
    assert right_side > left_side
