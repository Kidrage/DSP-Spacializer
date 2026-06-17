import numpy as np

from layer_extractor import extract_layers
from object_decoder import decode_scene_to_layout
from pseudo_object_scene import build_object_audio_for_scene, build_pseudo_object_scene
from speaker_layout import default_quad_4p0_layout
from spatial_safety import compute_quality_metrics


def test_short_dummy_pipeline_and_quality_metrics():
    sr = 24000
    n = sr // 2
    t = np.linspace(0, 0.5, n, endpoint=False)
    left = (0.4 * np.sin(2 * np.pi * 220 * t) + 0.1 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)
    right = (0.4 * np.sin(2 * np.pi * 330 * t) - 0.1 * np.sin(2 * np.pi * 1200 * t)).astype(np.float32)
    layers = extract_layers(left, right, sr)
    analysis = {"stereo_width": 0.5, "high_diffuse_ratio": 0.3, "center_dominance": 0.4, "transient_density": 0.1}
    routing = {"bass_gain": 1.0, "side_front": 0.35, "side_rear": 0.55, "amb_rear": 0.45, "air_rear": 0.3, "decorrelation": 0.2, "lowbody_rear": 0.2}
    scene = build_pseudo_object_scene("dummy.wav", left, right, layers, analysis, routing, "auto_acoustic", "auto_acoustic", sr, n / sr, export_object_audio=False)
    assert len(scene["objects"]) >= 6
    pseudo_4ch = decode_scene_to_layout(scene, build_object_audio_for_scene(layers), default_quad_4p0_layout(), sr)
    metrics = compute_quality_metrics(left, right, pseudo_4ch, sr, analysis=analysis)
    assert pseudo_4ch.shape == (n, 4)
    assert "mono_fold_down_delta_db_avg4_legacy" in metrics
    assert np.isfinite(metrics["mono_fold_down_delta_db_front_norm"])
