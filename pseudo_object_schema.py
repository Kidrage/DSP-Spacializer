"""Pseudo-object scene metadata schema helpers.

The pseudo-object scene format describes spatial-function objects derived from
DSP layers.  These objects are intentionally *not* clean source-separated stems;
they are explainable routing/material descriptors for downstream decoders.
"""

from __future__ import annotations

import math

SCENE_FORMAT = "pseudo_object_spatial_v1"
SCHEMA_VERSION = 1
REQUIRED_OBJECT_IDS = (
    "bass_anchor",
    "front_core",
    "side_width",
    "rear_ambience",
    "high_air",
    "low_body_support",
)
MOTION_TYPES = {"static", "orbit", "breathe", "drift"}


def gain_to_db(gain: float) -> float:
    gain = float(gain)
    if gain <= 0.0:
        return -120.0
    return float(20.0 * math.log10(gain))


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _require_keys(data: dict, keys, where: str) -> None:
    for key in keys:
        _require(key in data, f"Missing required key '{key}' in {where}")


def _require_range(value, lo: float, hi: float, where: str) -> None:
    value = float(value)
    _require(lo <= value <= hi, f"{where}={value} out of range [{lo}, {hi}]")


def make_scene_base(
    input_file: str,
    sample_rate: int,
    duration_seconds: float,
    channels: int,
    analysis: dict,
    routing: dict,
    preset_name: str,
    preset_mode_used: str,
) -> dict:
    """Build the top-level pseudo-object scene envelope without objects."""
    return {
        "scene_format": SCENE_FORMAT,
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "name": "DSP-Spacializer",
            "mode": "pseudo_object_upmix",
            "legacy_renderer_compatible": True,
        },
        "source": {
            "input_file": str(input_file),
            "sample_rate": int(sample_rate),
            "duration_seconds": float(duration_seconds),
            "channels": int(channels),
        },
        "analysis": dict(analysis or {}),
        "preset": {
            "preset_name": str(preset_name),
            "preset_mode_used": str(preset_mode_used),
            "routing": dict(routing or {}),
        },
        "coordinate_system": {
            "azimuth_degrees": "0=front, +right, -left, 180=rear",
            "elevation_degrees": "0=ear level, +up, -down",
            "radius": "0=center/listener, 1=nominal speaker ring",
        },
        "objects": [],
        "speaker_layout_hint": "quad_4p0_default",
        "decoder_policy": {
            "default_decoder": "dbap_quad_v1",
            "energy_normalization": "equal_power_per_object",
            "mono_safety": True,
        },
    }


def make_pseudo_object(
    object_id: str,
    label: str,
    role: str,
    object_type: str,
    audio_layer: str,
    audio_file: str,
    channel_format: str,
    position: dict,
    spread: float,
    depth: float,
    diffuseness: float,
    gain: float,
    decorrelation: float,
    constraints: dict,
    decoder_hint: dict,
    derived_from,
    motion: dict | None = None,
) -> dict:
    """Create one schema-shaped pseudo object and validate it."""
    obj = {
        "id": str(object_id),
        "label": str(label),
        "role": str(role),
        "object_type": str(object_type),
        "audio_layer": str(audio_layer),
        "audio_file": str(audio_file),
        "channel_format": str(channel_format),
        "position": {
            "azimuth": float(position.get("azimuth", 0.0)),
            "elevation": float(position.get("elevation", 0.0)),
            "radius": float(position.get("radius", 1.0)),
        },
        "spread": float(spread),
        "depth": float(depth),
        "diffuseness": float(diffuseness),
        "gain": float(gain),
        "gain_db": gain_to_db(float(gain)),
        "decorrelation": float(decorrelation),
        "motion": dict(motion or {"type": "static"}),
        "constraints": dict(constraints or {}),
        "decoder_hint": dict(decoder_hint or {}),
        "provenance": {
            "derived_from": list(derived_from),
            "is_clean_stem": False,
            "description": (
                "Pseudo object generated from DSP spatial-function layer, "
                "not a separated instrument stem."
            ),
        },
    }
    validate_pseudo_object(obj)
    return obj


def validate_pseudo_object(obj: dict) -> None:
    """Validate a single pseudo-object dictionary."""
    _require(isinstance(obj, dict), "Object must be a dict")
    _require_keys(
        obj,
        (
            "id", "label", "role", "object_type", "audio_layer", "audio_file",
            "channel_format", "position", "spread", "depth", "diffuseness",
            "gain", "gain_db", "decorrelation", "motion", "constraints",
            "decoder_hint", "provenance",
        ),
        "object",
    )
    _require(str(obj["id"]).strip() != "", "Object id must be non-empty")
    _require(obj["channel_format"] in {"mono", "stereo"}, "channel_format must be mono or stereo")
    pos = obj["position"]
    _require_keys(pos, ("azimuth", "elevation", "radius"), f"object {obj['id']}.position")
    _require_range(pos["azimuth"], -180.0, 180.0, f"object {obj['id']}.position.azimuth")
    _require_range(pos["elevation"], -90.0, 90.0, f"object {obj['id']}.position.elevation")
    _require_range(pos["radius"], 0.0, 1.5, f"object {obj['id']}.position.radius")
    _require_range(obj["spread"], 0.0, 1.0, f"object {obj['id']}.spread")
    _require_range(obj["depth"], 0.0, 1.0, f"object {obj['id']}.depth")
    _require_range(obj["diffuseness"], 0.0, 1.0, f"object {obj['id']}.diffuseness")
    _require(float(obj["gain"]) >= 0.0, f"object {obj['id']}.gain must be >= 0")
    _require_range(obj["decorrelation"], 0.0, 1.0, f"object {obj['id']}.decorrelation")
    motion_type = obj.get("motion", {}).get("type")
    _require(motion_type in MOTION_TYPES, f"object {obj['id']}.motion.type invalid: {motion_type}")
    provenance = obj["provenance"]
    _require(provenance.get("is_clean_stem") is False, "Pseudo objects must not claim clean-stem provenance")


def validate_pseudo_object_scene(scene: dict) -> None:
    """Validate top-level pseudo-object scene metadata."""
    _require(isinstance(scene, dict), "Scene must be a dict")
    _require_keys(
        scene,
        (
            "scene_format", "schema_version", "generator", "source", "analysis",
            "preset", "coordinate_system", "objects", "speaker_layout_hint",
            "decoder_policy",
        ),
        "scene",
    )
    _require(scene["scene_format"] == SCENE_FORMAT, "Unsupported scene_format")
    _require(int(scene["schema_version"]) == SCHEMA_VERSION, "Unsupported schema_version")
    _require(scene["generator"].get("legacy_renderer_compatible") is True, "Scene must preserve legacy compatibility")
    source = scene["source"]
    _require_keys(source, ("input_file", "sample_rate", "duration_seconds", "channels"), "scene.source")
    _require(int(source["sample_rate"]) > 0, "source.sample_rate must be positive")
    _require(float(source["duration_seconds"]) >= 0.0, "source.duration_seconds must be >= 0")
    _require(int(source["channels"]) == 2, "source.channels must be 2 for stereo input")
    objects = scene["objects"]
    _require(isinstance(objects, list), "scene.objects must be a list")
    seen = set()
    for obj in objects:
        validate_pseudo_object(obj)
        _require(obj["id"] not in seen, f"Duplicate object id: {obj['id']}")
        seen.add(obj["id"])
    missing = [oid for oid in REQUIRED_OBJECT_IDS if oid not in seen]
    _require(not missing, f"Missing required pseudo objects: {missing}")
