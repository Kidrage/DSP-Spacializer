"""Create a V2 scene from the existing deterministic DSP analysis buses."""

from __future__ import annotations

from collections.abc import Mapping

import numpy as np

from layer_extractor import extract_layers

from .foa import encode_mono_foa
from .scene import FoaBed, SpatialObject, SpatialScene


def _profile_value(profile: Mapping[str, object], key: str, default: float) -> float:
    value = profile.get(key, default)
    return float(value) if isinstance(value, (int, float)) else default


def build_scene(
    stereo: np.ndarray,
    analysis: Mapping[str, object] | None = None,
    profile: Mapping[str, object] | None = None,
    *,
    sample_rate: int = 48_000,
) -> SpatialScene:
    """Build the default static Spatial Core V2 scene from stereo DSP buses.

    ``analysis`` is preserved in metadata for later source-aware builders; V2.0
    intentionally performs no AI source separation.
    """

    audio = np.asarray(stereo, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("stereo input must be shaped [frames, 2]")
    settings: Mapping[str, object] = profile or {}
    buses = extract_layers(audio[:, 0], audio[:, 1], int(sample_rate))
    objects = [
        SpatialObject("bass", "bass", buses["bass"], 0.0, 0.0, 1.0, size=0.25),
        SpatialObject("low_body", "front", buses["low_body"], 0.0, 0.0, 1.0, size=0.35),
        SpatialObject("front_L", "front", buses["front_L"], 30.0, 0.0, 1.2, size=0.15),
        SpatialObject("front_R", "front", buses["front_R"], -30.0, 0.0, 1.2, size=0.15),
    ]
    width_gain = _profile_value(settings, "bed_width_gain", 0.45)
    rear_gain = _profile_value(settings, "bed_rear_gain", 0.35)
    air_gain = _profile_value(settings, "bed_air_gain", 0.22)
    bed = np.zeros((audio.shape[0], 4), dtype=np.float32)
    bed += encode_mono_foa(buses["side_width"], 75.0, 0.0, width_gain)
    bed += encode_mono_foa(-buses["side_width"], -75.0, 0.0, width_gain)
    bed += encode_mono_foa(buses["rear_ambience"], 135.0, 0.0, rear_gain)
    bed += encode_mono_foa(-buses["rear_ambience"], -135.0, 0.0, rear_gain)
    bed += encode_mono_foa(buses["high_air"], 110.0, 35.0, air_gain)
    bed += encode_mono_foa(-buses["high_air"], -110.0, 35.0, air_gain)
    metadata: dict[str, object] = {
        "source": "dsp_bus_builder",
        "objects_static": True,
        "directivity": "omni",
    }
    if analysis:
        metadata["analysis"] = dict(analysis)
    return SpatialScene(int(sample_rate), objects=objects, bed=FoaBed(bed), metadata=metadata)
