"""Horizontal 2D VBAP pseudo-object renderer."""

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
from renderers.layout_utils import (
    apply_gain_trim_and_delay,
    azimuth_to_unit_xy,
    normalize_azimuth_360,
    sorted_speakers_by_azimuth,
    speaker_ids,
)
from speaker_layout import validate_speaker_layout


def find_vbap_pair(azimuth_deg: float, speakers: list[dict]) -> tuple[int, int]:
    """Find adjacent speaker indices enclosing an azimuth, including wrap-around."""
    if not speakers:
        raise ValueError("speakers must not be empty")
    indexed = []
    for index, speaker in enumerate(speakers):
        azimuth = normalize_azimuth_360(speaker.get("azimuth", 0.0))
        indexed.append((azimuth, index))
    indexed.sort(key=lambda item: item[0])
    target = normalize_azimuth_360(azimuth_deg)

    for azimuth, index in indexed:
        if abs(target - azimuth) <= 1e-6:
            return index, index

    count = len(indexed)
    for offset in range(count):
        az_a, index_a = indexed[offset]
        az_b, index_b = indexed[(offset + 1) % count]
        if offset == count - 1:
            az_b += 360.0
        target_adjusted = target
        if target_adjusted < az_a:
            target_adjusted += 360.0
        if az_a <= target_adjusted <= az_b:
            return index_a, index_b
    return indexed[-1][1], indexed[0][1]


def vbap_pair_gains(
    source_azimuth_deg: float,
    speaker_a_azimuth_deg: float,
    speaker_b_azimuth_deg: float,
) -> tuple[float, float]:
    """Solve equal-power normalized 2D VBAP gains for a speaker pair."""
    if abs(normalize_azimuth_360(source_azimuth_deg) - normalize_azimuth_360(speaker_a_azimuth_deg)) <= 1e-6:
        return 1.0, 0.0
    if abs(normalize_azimuth_360(source_azimuth_deg) - normalize_azimuth_360(speaker_b_azimuth_deg)) <= 1e-6:
        return 0.0, 1.0

    source = azimuth_to_unit_xy(source_azimuth_deg)
    matrix = np.stack(
        [azimuth_to_unit_xy(speaker_a_azimuth_deg), azimuth_to_unit_xy(speaker_b_azimuth_deg)],
        axis=1,
    )
    gains = np.linalg.solve(matrix, source).astype(np.float32)
    gains = np.maximum(gains, 0.0)
    gains = equal_power_normalize(gains)
    return float(gains[0]), float(gains[1])


def vbap_gains_for_layout(azimuth_deg: float, layout: dict) -> np.ndarray:
    """Return equal-power VBAP gains in layout speaker order."""
    speakers = layout.get("speakers", [])
    a, b = find_vbap_pair(azimuth_deg, speakers)
    gains = np.zeros(len(speakers), dtype=np.float32)
    if a == b:
        gains[a] = 1.0
        return gains
    gain_a, gain_b = vbap_pair_gains(
        azimuth_deg,
        speakers[a].get("azimuth", 0.0),
        speakers[b].get("azimuth", 0.0),
    )
    gains[a] = gain_a
    gains[b] = gain_b
    return equal_power_normalize(gains)


def spread_vbap_gains(
    center_azimuth: float,
    spread: float,
    layout: dict,
    num_rays: int = 5,
) -> np.ndarray:
    """Average VBAP over virtual rays around the center azimuth."""
    spread = float(np.clip(spread, 0.0, 1.0))
    if spread <= 1e-6:
        return vbap_gains_for_layout(center_azimuth, layout)
    width = 15.0 + 75.0 * spread
    rays = np.linspace(center_azimuth - width / 2.0, center_azimuth + width / 2.0, num_rays)
    gains = np.zeros(len(layout.get("speakers", [])), dtype=np.float32)
    for ray in rays:
        gains += vbap_gains_for_layout(float(ray), layout)
    return equal_power_normalize(gains)


def apply_object_constraints(gains: np.ndarray, obj: dict, layout: dict) -> np.ndarray:
    """Apply first-version object constraints after raw VBAP gain calculation."""
    gains = np.asarray(gains, dtype=np.float32).copy()
    ids = speaker_ids(layout)
    constraints = obj.get("constraints", {})

    if constraints.get("keep_front"):
        has_rear = any(sid in {"LB", "RB"} and gains[i] > 1e-6 for i, sid in enumerate(ids))
        if has_rear:
            gains = vbap_gains_for_layout(0.0, layout)
        for i, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[i] = min(gains[i], 0.08)

    if constraints.get("prefer_rear"):
        for i, sid in enumerate(ids):
            if sid in {"LF", "RF"}:
                gains[i] *= 0.18

    if constraints.get("limited_rear"):
        for i, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[i] *= 0.35

    allowed = set(obj.get("decoder_hint", {}).get("allowed_speaker_roles") or [])
    allowed = allowed.intersection(set(ids))
    if allowed:
        for i, sid in enumerate(ids):
            if sid not in allowed:
                gains[i] *= 0.08

    forbidden = set(obj.get("decoder_hint", {}).get("forbidden_speaker_roles") or [])
    for i, sid in enumerate(ids):
        if sid in forbidden:
            gains[i] = 0.0
    return equal_power_normalize(gains)


class Vbap2DRenderer(SceneRenderer):
    name = "vbap_2d_v1"

    def render(self, scene: dict, object_audio: dict, speaker_layout: dict, sample_rate: int) -> RenderResult:
        validate_speaker_layout(speaker_layout)
        if speaker_ids(speaker_layout) != ["LF", "RF", "LB", "RB"]:
            raise ValueError("V1 VBAP renderer currently supports default quad order [LF, RF, LB, RB]")

        _ = sorted_speakers_by_azimuth(speaker_layout)
        feeds = np.zeros((max_num_samples(object_audio), 4), dtype=np.float32)
        gains_by_object: dict = {}
        for obj in scene.get("objects", []):
            oid = obj.get("id")
            if oid not in object_audio:
                continue
            if oid == "front_core" or obj.get("channel_format") == "stereo":
                gains = apply_front_core_bed(feeds, object_audio[oid], obj)
                gains_by_object[oid] = {"renderer": "stereo_bed", "gains": gains_to_dict(gains, speaker_layout)}
                continue

            azimuth = float(obj.get("position", {}).get("azimuth", 0.0))
            gains = vbap_gains_for_layout(azimuth, speaker_layout)
            gains = apply_object_constraints(gains, obj, speaker_layout)
            gains = gains * float(obj.get("gain", 1.0))
            add_mono_object_to_feeds(feeds, object_audio[oid], gains, obj, sample_rate)
            gains_by_object[oid] = {"renderer": "vbap", "gains": gains_to_dict(gains, speaker_layout)}

        feeds = apply_gain_trim_and_delay(feeds, speaker_layout, sample_rate)
        return RenderResult(
            feeds=np.nan_to_num(feeds, copy=False).astype(np.float32),
            gains_by_object=gains_by_object,
            renderer_name=self.name,
            diagnostics={"object_count": len(gains_by_object)},
        )
