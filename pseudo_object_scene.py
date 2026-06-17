"""Pseudo-object scene builder for DSP-Spacializer."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from object_audio_export import build_object_audio_layers, export_object_audio
from pseudo_object_schema import make_pseudo_object, make_scene_base, validate_pseudo_object_scene


def _clamp(value, lo, hi):
    return float(np.clip(float(value), lo, hi))


def build_pseudo_object_scene(
    input_file: str,
    left,
    right,
    layers: dict,
    analysis: dict,
    routing: dict,
    preset_name: str,
    preset_mode_used: str,
    sample_rate: int,
    duration_seconds: float,
    object_audio_dir: str | Path | None = None,
    export_object_audio: bool = True,
) -> dict:
    """Build and optionally export a pseudo-object scene.

    The object audio is layer material, not final speaker feed and not clean
    instrument stems.  When ``export_object_audio`` is true, ``object_audio_dir``
    receives one WAV per pseudo object.
    """
    scene = make_scene_base(
        input_file=input_file,
        sample_rate=sample_rate,
        duration_seconds=duration_seconds,
        channels=2,
        analysis=analysis,
        routing=routing,
        preset_name=preset_name,
        preset_mode_used=preset_mode_used,
    )
    object_audio = build_object_audio_layers(layers)
    if object_audio_dir is not None and export_object_audio:
        export_object_audio_fn = globals()["export_object_audio"]
        export_object_audio_fn(object_audio, object_audio_dir, sample_rate)

    stereo_width = _clamp(analysis.get("stereo_width", analysis.get("width", 0.35)), 0.0, 1.0)
    front_spread = _clamp(0.35 + 0.20 * stereo_width, 0.35, 0.55)
    rear_spread = _clamp(0.85 + 0.10 * analysis.get("high_diffuse_ratio", analysis.get("high_diffuse", 0.2)), 0.85, 0.95)
    side_gain = _clamp(0.5 * (routing.get("side_front", 0.4) + routing.get("side_rear", 0.4)), 0.25, 0.85)
    decorrelation = _clamp(routing.get("decorrelation", 0.25), 0.0, 1.0)

    objects = [
        make_pseudo_object(
            "bass_anchor", "Bass Anchor", "bass_anchor", "mono_anchor", "bass",
            "objects/bass_anchor.wav", "mono",
            {"azimuth": 0.0, "elevation": 0.0, "radius": 0.20},
            0.10, 0.10, 0.05, float(routing.get("bass_gain", 1.0)), 0.0,
            {"keep_front": True, "allow_rear": False, "mono_safe": True, "allow_motion": False},
            {"preferred_region": "front", "allowed_speaker_roles": ["LF", "RF", "C"], "forbidden_speaker_roles": [], "downmix_weight": 1.0},
            ["bass"],
        ),
        make_pseudo_object(
            "front_core", "Front Core", "main_image", "stereo_bed", "front_stereo",
            "objects/front_core.wav", "stereo",
            {"azimuth": 0.0, "elevation": 0.0, "radius": 0.45},
            front_spread, 0.35, 0.15, 1.0, 0.0,
            {"keep_front": True, "protect_vocal": True, "avoid_rear": True, "mono_safe": True, "allow_motion": False},
            {"preferred_region": "front", "allowed_speaker_roles": ["LF", "RF"], "forbidden_speaker_roles": [], "downmix_weight": 1.0},
            ["front_L", "front_R"],
        ),
        make_pseudo_object(
            "side_width", "Side Width", "lateral_width", "lateral_bed", "side_width",
            "objects/side_width.wav", "mono",
            {"azimuth": 90.0, "elevation": 0.0, "radius": 0.75},
            0.65, 0.50, 0.45, side_gain, _clamp(decorrelation * 0.5, 0.0, 1.0),
            {"avoid_center": True, "protect_vocal": True, "mono_safe": True, "allow_motion": True},
            {"preferred_region": "side", "allowed_speaker_roles": [], "forbidden_speaker_roles": [], "downmix_weight": 0.5},
            ["side_width"],
            motion={"type": "breathe", "rate_hz": 0.03, "depth": 0.06},
        ),
        make_pseudo_object(
            "rear_ambience", "Rear Ambience", "envelopment", "diffuse_bed", "rear_ambience",
            "objects/rear_ambience.wav", "mono",
            {"azimuth": 180.0, "elevation": 0.0, "radius": 0.90},
            rear_spread, 0.75, 0.85, float(routing.get("amb_rear", 0.5)), decorrelation,
            {"keep_front": False, "prefer_rear": True, "avoid_center": True, "protect_vocal": True, "mono_safe": True, "allow_motion": False},
            {"preferred_region": "rear", "allowed_speaker_roles": ["LB", "RB"], "forbidden_speaker_roles": [], "downmix_weight": 0.25},
            ["side_width", "rear_ambience", "high_air"],
        ),
        make_pseudo_object(
            "high_air", "High Air", "air_envelopment", "high_air_bed", "high_air",
            "objects/high_air.wav", "mono",
            {"azimuth": 180.0, "elevation": 0.0, "radius": 0.88},
            0.80, 0.65, 0.75, float(routing.get("air_rear", 0.35)), _clamp(decorrelation * 0.5, 0.0, 1.0),
            {"avoid_center": True, "avoid_harshness": True, "mono_safe": True, "allow_motion": False},
            {"preferred_region": "rear", "allowed_speaker_roles": [], "forbidden_speaker_roles": [], "downmix_weight": 0.25},
            ["high_air"],
        ),
        make_pseudo_object(
            "low_body_support", "Low Body Support", "warm_support", "warm_support", "low_body",
            "objects/low_body_support.wav", "mono",
            {"azimuth": 0.0, "elevation": 0.0, "radius": 0.50},
            0.35, 0.30, 0.20, float(routing.get("lowbody_rear", 0.0)) * 0.5, 0.0,
            {"keep_front": True, "limited_rear": True, "mono_safe": True, "allow_motion": False},
            {"preferred_region": "front", "allowed_speaker_roles": [], "forbidden_speaker_roles": [], "downmix_weight": 0.5},
            ["low_body"],
        ),
    ]
    scene["objects"] = objects
    validate_pseudo_object_scene(scene)
    return scene


def build_object_audio_for_scene(layers: dict) -> dict:
    """Public convenience wrapper used by CLI/tests before decoding."""
    return build_object_audio_layers(layers)
