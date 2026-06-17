"""DBAP-like pseudo-object renderer kept as V1 fallback."""

from __future__ import annotations

import numpy as np

from renderers.base import (
    RenderResult,
    SceneRenderer,
    add_mono_object_to_feeds,
    apply_front_core_bed,
    equal_power_normalize,
    gains_to_dict,
    max_num_samples,
)
from renderers.layout_utils import apply_gain_trim_and_delay, azimuth_radius_to_xy, speaker_ids
from speaker_layout import validate_speaker_layout


def dbap_gains_for_object(obj: dict, layout: dict) -> np.ndarray:
    """Distance-based amplitude panning gains for one pseudo object."""
    pos = obj.get("position", {})
    obj_xy = azimuth_radius_to_xy(pos.get("azimuth", 0.0), pos.get("radius", 1.0))
    spread = float(np.clip(obj.get("spread", 0.5), 0.0, 1.0))
    effective_rolloff = 1.6 - 1.2 * spread
    gains = []
    for speaker in layout["speakers"]:
        sp_xy = azimuth_radius_to_xy(speaker.get("azimuth", 0.0), speaker.get("radius", 1.0))
        distance = float(np.linalg.norm(obj_xy - sp_xy))
        gains.append(1.0 / ((distance + 0.25) ** effective_rolloff))
    gains = np.asarray(gains, dtype=np.float32)

    constraints = obj.get("constraints", {})
    ids = speaker_ids(layout)
    if constraints.get("keep_front"):
        for index, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[index] *= 0.08 if constraints.get("allow_rear") is False else 0.25
    if constraints.get("prefer_rear"):
        for index, sid in enumerate(ids):
            if sid in {"LF", "RF"}:
                gains[index] *= 0.22
    if constraints.get("limited_rear"):
        for index, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[index] *= 0.35

    allowed = set(obj.get("decoder_hint", {}).get("allowed_speaker_roles") or [])
    allowed = allowed.intersection(set(ids))
    if allowed:
        for index, sid in enumerate(ids):
            if sid not in allowed:
                gains[index] *= 0.08
    forbidden = set(obj.get("decoder_hint", {}).get("forbidden_speaker_roles") or [])
    for index, sid in enumerate(ids):
        if sid in forbidden:
            gains[index] = 0.0
    return equal_power_normalize(gains)


class DbapRenderer(SceneRenderer):
    name = "dbap_quad_v1"

    def render(self, scene: dict, object_audio: dict, speaker_layout: dict, sample_rate: int) -> RenderResult:
        validate_speaker_layout(speaker_layout)
        if speaker_ids(speaker_layout) != ["LF", "RF", "LB", "RB"]:
            raise ValueError("V1 DBAP renderer currently supports default quad order [LF, RF, LB, RB]")

        feeds = np.zeros((max_num_samples(object_audio), 4), dtype=np.float32)
        gains_by_object: dict = {}
        for obj in scene.get("objects", []):
            oid = obj.get("id")
            if oid not in object_audio:
                continue
            if obj.get("channel_format") == "stereo" or oid == "front_core":
                gains = apply_front_core_bed(feeds, object_audio[oid], obj)
                gains_by_object[oid] = {"renderer": "stereo_bed", "gains": gains_to_dict(gains, speaker_layout)}
                continue
            gains = dbap_gains_for_object(obj, speaker_layout) * float(obj.get("gain", 1.0))
            add_mono_object_to_feeds(feeds, object_audio[oid], gains, obj, sample_rate)
            gains_by_object[oid] = {"renderer": "dbap", "gains": gains_to_dict(gains, speaker_layout)}

        feeds = apply_gain_trim_and_delay(feeds, speaker_layout, sample_rate)
        return RenderResult(
            feeds=np.nan_to_num(feeds, copy=False).astype(np.float32),
            gains_by_object=gains_by_object,
            renderer_name=self.name,
            diagnostics={"object_count": len(gains_by_object)},
        )
