import pytest

from pseudo_object_scene import build_pseudo_object_scene
from pseudo_object_schema import validate_pseudo_object_scene


def _scene():
    n = 1024
    layers = {
        "bass": [0.0] * n,
        "low_body": [0.0] * n,
        "front_L": [0.0] * n,
        "front_R": [0.0] * n,
        "side_width": [0.0] * n,
        "rear_ambience": [0.0] * n,
        "high_air": [0.0] * n,
    }
    analysis = {"stereo_width": 0.4, "high_diffuse_ratio": 0.2}
    routing = {"bass_gain": 1.0, "side_front": 0.4, "side_rear": 0.5, "amb_rear": 0.5, "air_rear": 0.3, "decorrelation": 0.25, "lowbody_rear": 0.2}
    return build_pseudo_object_scene("dummy.wav", [], [], layers, analysis, routing, "auto_acoustic", "auto_acoustic", 48000, 1.0, export_object_audio=False)


def test_default_scene_validates():
    validate_pseudo_object_scene(_scene())


def test_missing_object_id_fails():
    scene = _scene()
    del scene["objects"][0]["id"]
    with pytest.raises(ValueError):
        validate_pseudo_object_scene(scene)


def test_azimuth_out_of_range_fails():
    scene = _scene()
    scene["objects"][0]["position"]["azimuth"] = 181.0
    with pytest.raises(ValueError):
        validate_pseudo_object_scene(scene)


def test_spread_out_of_range_fails():
    scene = _scene()
    scene["objects"][0]["spread"] = 1.2
    with pytest.raises(ValueError):
        validate_pseudo_object_scene(scene)
