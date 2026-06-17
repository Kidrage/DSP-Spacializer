"""Speaker layout descriptors for pseudo-object decoding."""

from __future__ import annotations


def default_quad_4p0_layout() -> dict:
    return {
        "layout_format": "speaker_layout_v1",
        "layout_name": "quad_4p0_default",
        "speakers": [
            {"id": "LF", "role": "front_left", "azimuth": -45.0, "elevation": 0.0, "radius": 1.0, "gain_trim_db": 0.0, "delay_ms": 0.0},
            {"id": "RF", "role": "front_right", "azimuth": 45.0, "elevation": 0.0, "radius": 1.0, "gain_trim_db": 0.0, "delay_ms": 0.0},
            {"id": "LB", "role": "rear_left", "azimuth": -135.0, "elevation": 0.0, "radius": 1.0, "gain_trim_db": 0.0, "delay_ms": 0.0},
            {"id": "RB", "role": "rear_right", "azimuth": 135.0, "elevation": 0.0, "radius": 1.0, "gain_trim_db": 0.0, "delay_ms": 0.0},
        ],
    }


def validate_speaker_layout(layout: dict) -> None:
    if not isinstance(layout, dict):
        raise ValueError("layout must be a dict")
    if layout.get("layout_format") != "speaker_layout_v1":
        raise ValueError("layout_format must be speaker_layout_v1")
    speakers = layout.get("speakers")
    if not isinstance(speakers, list) or not speakers:
        raise ValueError("speakers must be a non-empty list")
    seen = set()
    for speaker in speakers:
        sid = speaker.get("id")
        if not sid:
            raise ValueError("speaker id is required")
        if sid in seen:
            raise ValueError(f"duplicate speaker id: {sid}")
        seen.add(sid)
        az = float(speaker.get("azimuth", 0.0))
        el = float(speaker.get("elevation", 0.0))
        radius = float(speaker.get("radius", 0.0))
        if not -180.0 <= az <= 180.0:
            raise ValueError(f"speaker {sid} azimuth out of range")
        if not -90.0 <= el <= 90.0:
            raise ValueError(f"speaker {sid} elevation out of range")
        if radius <= 0.0:
            raise ValueError(f"speaker {sid} radius must be > 0")
