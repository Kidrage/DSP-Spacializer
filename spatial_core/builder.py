"""Create a V2 scene from the existing deterministic DSP analysis buses."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, fields

import numpy as np

from .foa import encode_mono_foa
from .profile import SpatialCoreProfile
from .scene import FoaBed, SpatialObject, SpatialScene
from .zones import extract_spatial_zones


def _resolve_profile(
    profile: SpatialCoreProfile | Mapping[str, object] | None,
) -> SpatialCoreProfile:
    if isinstance(profile, SpatialCoreProfile):
        return profile
    if profile is None:
        return SpatialCoreProfile()
    names = {item.name for item in fields(SpatialCoreProfile)}
    unknown = sorted(set(profile) - names)
    if unknown:
        raise ValueError(f"unknown spatial profile parameter: {unknown[0]}")
    defaults = SpatialCoreProfile()
    values = {
        item.name: profile.get(item.name, getattr(defaults, item.name))
        for item in fields(SpatialCoreProfile)
    }
    return SpatialCoreProfile(**values)


def build_scene(
    stereo: np.ndarray,
    analysis: Mapping[str, object] | None = None,
    profile: SpatialCoreProfile | Mapping[str, object] | None = None,
    *,
    sample_rate: int = 48_000,
) -> SpatialScene:
    """Build the default static Spatial Core scene from seven lossless M/S zones.

    ``analysis`` is preserved in metadata for later source-aware builders. The
    center anchor is coherence-derived; no source-separation model is used.
    """

    audio = np.asarray(stereo, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("stereo input must be shaped [frames, 2]")
    settings = _resolve_profile(profile)
    zones = extract_spatial_zones(audio, sample_rate=int(sample_rate), profile=settings)
    objects = [
        SpatialObject(
            "bass", "bass", zones.bass, 0.0, 0.0, settings.front_distance_m,
            size=0.05, direct_ratio=settings.direct_ratio,
        ),
        SpatialObject(
            "center_anchor", "center", zones.center_anchor, 0.0, 0.0,
            settings.front_distance_m, size=0.0, direct_ratio=settings.direct_ratio,
        ),
        SpatialObject(
            "front_L_residual", "front", zones.front_L_residual,
            settings.front_width_deg, 0.0, settings.front_distance_m,
            size=0.05, direct_ratio=settings.direct_ratio,
        ),
        SpatialObject(
            "front_R_residual", "front", zones.front_R_residual,
            -settings.front_width_deg, 0.0, settings.front_distance_m,
            size=0.05, direct_ratio=settings.direct_ratio,
        ),
    ]
    bed = np.zeros((audio.shape[0], 4), dtype=np.float32)
    bed += encode_mono_foa(zones.side_width, 75.0, 0.0, settings.bed_width_gain)
    bed += encode_mono_foa(-zones.side_width, -75.0, 0.0, settings.bed_width_gain)
    bed += encode_mono_foa(zones.rear_ambience, 135.0, 0.0, settings.bed_rear_gain)
    bed += encode_mono_foa(-zones.rear_ambience, -135.0, 0.0, settings.bed_rear_gain)
    bed += encode_mono_foa(zones.high_air, 110.0, 35.0, settings.bed_air_gain)
    bed += encode_mono_foa(-zones.high_air, -110.0, 35.0, settings.bed_air_gain)
    metadata: dict[str, object] = {
        "source": "dsp_bus_builder",
        "builder_version": "2.1",
        "zones": list(zones.names),
        "profile": asdict(settings),
        "mastered_reference_rms": float(
            np.sqrt(np.mean(audio.astype(np.float64) ** 2))
        ),
        "objects_static": True,
        "directivity": "omni",
    }
    if analysis:
        metadata["analysis"] = dict(analysis)
    return SpatialScene(int(sample_rate), objects=objects, bed=FoaBed(bed), metadata=metadata)
