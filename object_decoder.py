"""Pseudo-object scene decoder dispatch layer."""

from __future__ import annotations

import numpy as np

from renderers.base import RenderResult
from renderers.dbap_renderer import DbapRenderer
from renderers.hybrid_renderer import HybridPseudoObjectRenderer
from renderers.vbap_2d import Vbap2DRenderer


RENDERER_MODES = ("dbap_quad_v1", "vbap_2d_v1", "hybrid_vbap_v1")


def get_renderer(decoder_mode: str):
    if decoder_mode == "dbap_quad_v1":
        return DbapRenderer()
    if decoder_mode == "vbap_2d_v1":
        return Vbap2DRenderer()
    if decoder_mode == "hybrid_vbap_v1":
        return HybridPseudoObjectRenderer()
    raise ValueError(f"Unsupported decoder_mode: {decoder_mode}")


def decode_scene_to_layout_with_diagnostics(
    scene: dict,
    object_audio: dict,
    speaker_layout: dict,
    sample_rate: int,
    decoder_mode: str = "hybrid_vbap_v1",
) -> RenderResult:
    """Decode scene and return speaker feeds plus renderer diagnostics."""
    renderer = get_renderer(decoder_mode)
    return renderer.render(scene, object_audio, speaker_layout, sample_rate)


def decode_scene_to_layout(
    scene: dict,
    object_audio: dict,
    speaker_layout: dict,
    sample_rate: int,
    decoder_mode: str = "hybrid_vbap_v1",
) -> np.ndarray:
    """Backward-compatible helper returning only decoded speaker feeds."""
    result = decode_scene_to_layout_with_diagnostics(
        scene,
        object_audio,
        speaker_layout,
        sample_rate,
        decoder_mode=decoder_mode,
    )
    return result.feeds
