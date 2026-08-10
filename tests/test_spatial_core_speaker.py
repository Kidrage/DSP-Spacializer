import numpy as np

from spatial_core import CtcOutputAdapter, QuadSpeakerRenderer, RenderResult, SpatialObject, SpatialScene


def test_quad_vbap_routes_front_center_to_front_pair():
    signal = np.zeros(256, dtype=np.float32)
    signal[0] = 0.1
    scene = SpatialScene(48_000, [SpatialObject("center", "front", signal, 0, 0, 1)])

    result = QuadSpeakerRenderer().render(scene)

    assert result.audio.shape == (256, 4)
    assert result.audio[0, 0] > 0
    assert result.audio[0, 1] > 0
    assert np.allclose(result.audio[:, 2:], 0, atol=1e-7)


def test_quad_renderer_reports_elevation_projection():
    signal = np.ones(64, dtype=np.float32) * 0.01
    scene = SpatialScene(48_000, [SpatialObject("air", "air", signal, 90, 35, 1)])

    result = QuadSpeakerRenderer().render(scene)

    assert result.diagnostics["elevation_projected_objects"] == ["air"]


def test_ctc_adapter_uses_binaural_result_as_post_stage(monkeypatch):
    class StubRenderer:
        def render(self, scene):
            return RenderResult(np.ones((32, 2), dtype=np.float32) * 0.01, scene.sample_rate)

    called = {}

    def fake_ctc(audio, sample_rate, **kwargs):
        called["shape"] = audio.shape
        called["sample_rate"] = sample_rate
        return np.ones((32, 4), dtype=np.float32) * 0.02

    monkeypatch.setattr("spatial_core.adapters.render_binaural_to_ctc_4ch", fake_ctc)
    scene = SpatialScene(48_000, [SpatialObject("lead", "front", np.ones(32), 0, 0, 1)])

    result = CtcOutputAdapter(StubRenderer()).render(scene)

    assert called == {"shape": (32, 2), "sample_rate": 48_000}
    assert result.audio.shape == (32, 4)
    assert result.diagnostics["adapter"] == "legacy-ctc-post"
