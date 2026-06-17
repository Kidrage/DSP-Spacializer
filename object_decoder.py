"""Pseudo-object scene decoder.

V1 intentionally implements a simple DBAP-like decoder for default quad 4.0.
It prioritizes structural correctness, deterministic output, and readable
metadata over perfect imaging.
"""

from __future__ import annotations

import math

import numpy as np

from renderer_4ch import decorrelate_rear
from speaker_layout import validate_speaker_layout


EPS = 1e-9


def _az_radius_to_xy(azimuth_deg: float, radius: float) -> np.ndarray:
    theta = math.radians(float(azimuth_deg))
    # 0 degrees is front (+y), +right is +x.
    return np.array([math.sin(theta) * radius, math.cos(theta) * radius], dtype=np.float32)


def _speaker_ids(layout: dict) -> list[str]:
    return [speaker["id"] for speaker in layout["speakers"]]


def _dbap_gains(obj: dict, layout: dict) -> np.ndarray:
    pos = obj.get("position", {})
    obj_xy = _az_radius_to_xy(pos.get("azimuth", 0.0), pos.get("radius", 1.0))
    spread = float(np.clip(obj.get("spread", 0.5), 0.0, 1.0))
    effective_rolloff = 1.6 - 1.2 * spread
    gains = []
    for speaker in layout["speakers"]:
        sp_xy = _az_radius_to_xy(speaker.get("azimuth", 0.0), speaker.get("radius", 1.0))
        distance = float(np.linalg.norm(obj_xy - sp_xy))
        gain = 1.0 / ((distance + 0.25) ** effective_rolloff)
        gains.append(gain)
    gains = np.asarray(gains, dtype=np.float32)
    constraints = obj.get("constraints", {})
    ids = _speaker_ids(layout)
    if constraints.get("keep_front"):
        for i, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[i] *= 0.08 if constraints.get("allow_rear") is False else 0.25
    if constraints.get("prefer_rear"):
        for i, sid in enumerate(ids):
            if sid in {"LF", "RF"}:
                gains[i] *= 0.22
    if constraints.get("limited_rear"):
        for i, sid in enumerate(ids):
            if sid in {"LB", "RB"}:
                gains[i] *= 0.35
    allowed = set(obj.get("decoder_hint", {}).get("allowed_speaker_roles") or [])
    if allowed:
        for i, sid in enumerate(ids):
            if sid not in allowed:
                gains[i] *= 0.08
    forbidden = set(obj.get("decoder_hint", {}).get("forbidden_speaker_roles") or [])
    for i, sid in enumerate(ids):
        if sid in forbidden:
            gains[i] = 0.0
    norm = float(np.sqrt(np.sum(gains * gains)) + EPS)
    return gains / norm


def _ensure_2d_audio(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def _apply_mono_object(out: np.ndarray, audio: np.ndarray, gains: np.ndarray, obj: dict, sample_rate: int) -> None:
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    n = min(len(x), out.shape[0])
    if n == 0:
        return
    ids = ["LF", "RF", "LB", "RB"]
    rear_ids = {"LB", "RB"}
    if obj.get("diffuseness", 0.0) >= 0.6 and obj.get("decorrelation", 0.0) > 0.0:
        lb, rb = decorrelate_rear(x[:n], sample_rate, obj.get("decorrelation", 0.0))
        for i, sid in enumerate(ids):
            if sid == "LB":
                out[:n, i] += lb[:n] * gains[i]
            elif sid == "RB":
                out[:n, i] += rb[:n] * gains[i]
            else:
                out[:n, i] += x[:n] * gains[i]
        return
    for i in range(out.shape[1]):
        out[:n, i] += x[:n] * gains[i]


def _apply_front_core(out: np.ndarray, audio: np.ndarray, obj: dict) -> None:
    stereo = _ensure_2d_audio(audio)
    if stereo.shape[1] < 2:
        stereo = np.repeat(stereo[:, :1], 2, axis=1)
    n = min(stereo.shape[0], out.shape[0])
    if n == 0:
        return
    gain = float(obj.get("gain", 1.0))
    spread = float(np.clip(obj.get("spread", 0.35), 0.0, 1.0))
    rear_cross = 0.04 + 0.10 * spread
    out[:n, 0] += stereo[:n, 0] * gain
    out[:n, 1] += stereo[:n, 1] * gain
    out[:n, 2] += stereo[:n, 0] * gain * rear_cross
    out[:n, 3] += stereo[:n, 1] * gain * rear_cross


def decode_scene_to_layout(
    scene: dict,
    object_audio: dict,
    speaker_layout: dict,
    sample_rate: int,
    decoder_mode: str = "dbap_quad_v1",
) -> np.ndarray:
    """Decode pseudo-object audio to speaker feeds in layout speaker order."""
    if decoder_mode != "dbap_quad_v1":
        raise ValueError(f"Unsupported decoder_mode: {decoder_mode}")
    validate_speaker_layout(speaker_layout)
    ids = _speaker_ids(speaker_layout)
    if ids != ["LF", "RF", "LB", "RB"]:
        raise ValueError("V1 decoder currently supports default quad order [LF, RF, LB, RB]")
    max_n = 0
    for audio in object_audio.values():
        max_n = max(max_n, _ensure_2d_audio(audio).shape[0])
    out = np.zeros((max_n, len(ids)), dtype=np.float32)
    for obj in scene.get("objects", []):
        oid = obj.get("id")
        if oid not in object_audio:
            continue
        audio = object_audio[oid]
        if obj.get("channel_format") == "stereo" or oid == "front_core":
            _apply_front_core(out, audio, obj)
            continue
        gains = _dbap_gains(obj, speaker_layout) * float(obj.get("gain", 1.0))
        _apply_mono_object(out, audio, gains, obj, sample_rate)
    return np.nan_to_num(out, copy=False).astype(np.float32)
