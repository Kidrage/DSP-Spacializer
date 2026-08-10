import numpy as np

from spatial_core import build_scene, encode_mono_foa, foa_direction_vector


def test_foa_uses_ambix_acn_sn3d_channel_order():
    signal = np.ones(8, dtype=np.float32)

    front = encode_mono_foa(signal, azimuth_deg=0, elevation_deg=0)
    left = encode_mono_foa(signal, azimuth_deg=90, elevation_deg=0)
    above = encode_mono_foa(signal, azimuth_deg=0, elevation_deg=90)

    assert np.allclose(front[0], [1, 0, 0, 1], atol=1e-6)
    assert np.allclose(left[0], [1, 1, 0, 0], atol=1e-6)
    assert np.allclose(above[0], [1, 0, 1, 0], atol=1e-6)
    assert np.allclose(foa_direction_vector(-90, 0), [1, -1, 0, 0], atol=1e-6)


def test_default_builder_creates_direct_objects_and_foa_bed():
    frames = 256
    stereo = np.zeros((frames, 2), dtype=np.float32)
    stereo[:, 0] = np.linspace(-0.2, 0.2, frames)
    stereo[:, 1] = np.linspace(0.2, -0.2, frames)

    scene = build_scene(stereo, sample_rate=48_000)

    positions = {item.object_id: item.azimuth_deg for item in scene.objects}
    assert positions == {"bass": 0.0, "front_L": 30.0, "front_R": -30.0}
    assert scene.bed is not None
    assert scene.bed.audio.shape == (frames, 4)
    assert scene.metadata["source"] == "dsp_bus_builder"
