"""Hybrid pseudo-object renderer combining VBAP and spread VBAP."""

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
from renderers.layout_utils import apply_gain_trim_and_delay, speaker_ids
from renderers.vbap_2d import apply_object_constraints, spread_vbap_gains, vbap_gains_for_layout
from speaker_layout import validate_speaker_layout


SPREAD_OBJECT_TYPES = {"diffuse_bed", "high_air_bed", "lateral_bed"}


def hybrid_gains_for_object(obj: dict, layout: dict) -> tuple[np.ndarray, str]:
    oid = obj.get("id")
    object_type = obj.get("object_type")
    azimuth = float(obj.get("position", {}).get("azimuth", 0.0))
    spread = float(np.clip(obj.get("spread", 0.0), 0.0, 1.0))
    diffuseness = float(np.clip(obj.get("diffuseness", 0.0), 0.0, 1.0))

    if oid == "side_width":
        gains = spread_vbap_gains(azimuth, max(spread, 0.65), layout)
        renderer = "spread_vbap"
    elif diffuseness >= 0.65 or object_type in SPREAD_OBJECT_TYPES:
        gains = spread_vbap_gains(azimuth, spread, layout)
        renderer = "spread_vbap"
    else:
        gains = vbap_gains_for_layout(azimuth, layout)
        renderer = "vbap"

    gains = apply_object_constraints(gains, obj, layout)
    if obj.get("constraints", {}).get("avoid_harshness"):
        gains *= 0.85
    gains = equal_power_normalize(gains) * float(obj.get("gain", 1.0))
    return gains, renderer


class HybridPseudoObjectRenderer(SceneRenderer):
    name = "hybrid_vbap_v1"

    def render(self, scene: dict, object_audio: dict, speaker_layout: dict, sample_rate: int) -> RenderResult:
        validate_speaker_layout(speaker_layout)
        if speaker_ids(speaker_layout) != ["LF", "RF", "LB", "RB"]:
            raise ValueError("V1 hybrid renderer currently supports default quad order [LF, RF, LB, RB]")

        feeds = np.zeros((max_num_samples(object_audio), 4), dtype=np.float32)
        gains_by_object: dict = {}
        renderer_counts: dict[str, int] = {}
        for obj in scene.get("objects", []):
            oid = obj.get("id")
            if oid not in object_audio:
                continue
            if oid == "front_core" or obj.get("channel_format") == "stereo":
                gains = apply_front_core_bed(feeds, object_audio[oid], obj)
                renderer = "stereo_bed"
                gains_by_object[oid] = {"renderer": renderer, "gains": gains_to_dict(gains, speaker_layout)}
                renderer_counts[renderer] = renderer_counts.get(renderer, 0) + 1
                continue

            gains, renderer = hybrid_gains_for_object(obj, speaker_layout)
            add_mono_object_to_feeds(feeds, object_audio[oid], gains, obj, sample_rate)
            gains_by_object[oid] = {"renderer": renderer, "gains": gains_to_dict(gains, speaker_layout)}
            renderer_counts[renderer] = renderer_counts.get(renderer, 0) + 1

        feeds = apply_gain_trim_and_delay(feeds, speaker_layout, sample_rate)
        return RenderResult(
            feeds=np.nan_to_num(feeds, copy=False).astype(np.float32),
            gains_by_object=gains_by_object,
            renderer_name=self.name,
            diagnostics={"object_count": len(gains_by_object), "renderer_counts": renderer_counts},
        )
