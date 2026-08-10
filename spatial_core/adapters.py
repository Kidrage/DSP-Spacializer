"""Output adapters that intentionally remain outside the Spatial Core renderer."""

from __future__ import annotations

from binaural_renderer import render_binaural_to_ctc_4ch

from .rendering import RenderResult, SceneRenderer
from .scene import SpatialScene


class CtcOutputAdapter:
    """Post-process a V2 binaural render with the existing centered-listener CTC."""

    def __init__(self, renderer: SceneRenderer, **ctc_options: object):
        self.renderer = renderer
        self.ctc_options = ctc_options

    def render(self, scene: SpatialScene) -> RenderResult:
        binaural = self.renderer.render(scene)
        speakers = render_binaural_to_ctc_4ch(
            binaural.audio,
            binaural.sample_rate,
            **self.ctc_options,
        )
        diagnostics = dict(binaural.diagnostics)
        diagnostics["adapter"] = "legacy-ctc-post"
        return RenderResult(speakers, binaural.sample_rate, diagnostics)
