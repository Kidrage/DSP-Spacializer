"""Translate one mixer profile into a Spatial Core scene."""

from __future__ import annotations

from dataclasses import asdict
from typing import Iterable

import numpy as np

from spatial_core.foa import encode_mono_foa
from spatial_core.profile import SpatialCoreProfile
from spatial_core.scene import FoaBed, SpatialObject, SpatialScene
from spatial_core.zones import extract_spatial_zones

from .profile import FieldZone, MixerProfile, ObjectZone


def extract_mixer_zones(
    stereo: np.ndarray,
    profile: MixerProfile,
    *,
    sample_rate: int = 48_000,
):
    """Extract the seven editable zones using the profile's Lab settings."""

    return extract_spatial_zones(
        stereo,
        sample_rate=int(sample_rate),
        profile=SpatialCoreProfile(center_anchor=profile.extraction.center_anchor),
        extraction=asdict(profile.extraction),
    )


def _object(
    zone_id: str,
    role: str,
    audio: np.ndarray,
    settings: ObjectZone,
) -> SpatialObject:
    return SpatialObject(
        zone_id,
        role,
        audio,
        settings.azimuth_deg,
        settings.elevation_deg,
        settings.distance_m,
        gain_db=settings.gain_db,
        size=settings.size,
        diffusion=settings.diffusion,
        direct_ratio=settings.direct_ratio,
        early_reflection_trim_db=settings.early_reflection_trim_db,
        late_reverb_trim_db=settings.late_reverb_trim_db,
    )


def _add_mirrored_field(
    bed: np.ndarray,
    audio: np.ndarray,
    settings: FieldZone,
) -> None:
    bed += encode_mono_foa(
        audio,
        settings.azimuth_deg,
        settings.elevation_deg,
        settings.field_gain,
    )
    bed += encode_mono_foa(
        -audio,
        -settings.azimuth_deg,
        settings.elevation_deg,
        settings.field_gain,
    )


def build_mixer_scene(
    stereo: np.ndarray,
    profile: MixerProfile,
    *,
    sample_rate: int = 48_000,
    muted: Iterable[str] = (),
    soloed: Iterable[str] = (),
) -> SpatialScene:
    """Build one renderable scene from the strict seven-zone profile."""

    audio = np.asarray(stereo, dtype=np.float32)
    if audio.ndim != 2 or audio.shape[1] != 2:
        raise ValueError("stereo input must be shaped [frames, 2]")
    zones = extract_mixer_zones(audio, profile, sample_rate=int(sample_rate))
    muted_names = set(muted)
    soloed_names = set(soloed)
    unknown = sorted((muted_names | soloed_names) - set(profile.zones))
    if unknown:
        raise ValueError(f"unknown audition zone: {unknown[0]}")

    def audition_audio(name: str, value: np.ndarray) -> np.ndarray:
        audible = name not in muted_names and (not soloed_names or name in soloed_names)
        return value if audible else np.zeros_like(value)
    bass = profile.zones["bass"]
    center = profile.zones["center_anchor"]
    front_l = profile.zones["front_L_residual"]
    front_r = profile.zones["front_R_residual"]
    side = profile.zones["side_width"]
    rear = profile.zones["rear_ambience"]
    air = profile.zones["high_air"]
    assert isinstance(bass, ObjectZone)
    assert isinstance(center, ObjectZone)
    assert isinstance(front_l, ObjectZone)
    assert isinstance(front_r, ObjectZone)
    assert isinstance(side, FieldZone)
    assert isinstance(rear, FieldZone)
    assert isinstance(air, FieldZone)
    objects = [
        _object("bass", "bass", audition_audio("bass", zones.bass), bass),
        _object(
            "center_anchor",
            "center",
            audition_audio("center_anchor", zones.center_anchor),
            center,
        ),
        _object(
            "front_L_residual",
            "front",
            audition_audio("front_L_residual", zones.front_L_residual),
            front_l,
        ),
        _object(
            "front_R_residual",
            "front",
            audition_audio("front_R_residual", zones.front_R_residual),
            front_r,
        ),
    ]
    bed = np.zeros((audio.shape[0], 4), dtype=np.float32)
    _add_mirrored_field(bed, audition_audio("side_width", zones.side_width), side)
    _add_mirrored_field(bed, audition_audio("rear_ambience", zones.rear_ambience), rear)
    _add_mirrored_field(bed, audition_audio("high_air", zones.high_air), air)
    metadata: dict[str, object] = {
        "source": "seven_zone_mixer",
        "builder_version": "1.0",
        "zones": list(zones.names),
        "mixer_profile_hash": profile.profile_hash,
        "mixer_profile": profile.to_payload(),
        "mastered_reference_rms": float(np.sqrt(np.mean(audio.astype(np.float64) ** 2))),
        "objects_static": True,
        "directivity": "omni",
        "extraction": asdict(profile.extraction),
    }
    return SpatialScene(int(sample_rate), objects=objects, bed=FoaBed(bed), metadata=metadata)
