"""Common renderer interface and audio application helpers."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from renderer_4ch import decorrelate_rear
from renderers.layout_utils import speaker_ids


EPS = 1e-9


@dataclass
class RenderResult:
    feeds: np.ndarray
    gains_by_object: dict
    renderer_name: str
    diagnostics: dict


class SceneRenderer:
    name: str = "base"

    def render(
        self,
        scene: dict,
        object_audio: dict,
        speaker_layout: dict,
        sample_rate: int,
    ) -> RenderResult:
        raise NotImplementedError


def ensure_2d_audio(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        return audio[:, None]
    return audio


def max_num_samples(object_audio: dict) -> int:
    max_n = 0
    for audio in object_audio.values():
        max_n = max(max_n, ensure_2d_audio(audio).shape[0])
    return max_n


def equal_power_normalize(gains: np.ndarray) -> np.ndarray:
    gains = np.asarray(gains, dtype=np.float32)
    norm = float(np.sqrt(np.sum(gains * gains)) + EPS)
    return (gains / norm).astype(np.float32)


def gains_to_dict(gains: np.ndarray, layout: dict) -> dict:
    return {sid: float(gain) for sid, gain in zip(speaker_ids(layout), gains)}


def apply_front_core_bed(feeds: np.ndarray, audio: np.ndarray, obj: dict) -> np.ndarray:
    stereo = ensure_2d_audio(audio)
    if stereo.shape[1] < 2:
        stereo = np.repeat(stereo[:, :1], 2, axis=1)
    n = min(stereo.shape[0], feeds.shape[0])
    if n == 0:
        return np.array([0.0, 0.0, 0.0, 0.0], dtype=np.float32)

    gain = float(obj.get("gain", 1.0))
    spread = float(np.clip(obj.get("spread", 0.35), 0.0, 1.0))
    rear_cross = 0.04 + 0.10 * spread
    if obj.get("constraints", {}).get("keep_front"):
        rear_cross = min(rear_cross, 0.08)

    feeds[:n, 0] += stereo[:n, 0] * gain
    feeds[:n, 1] += stereo[:n, 1] * gain
    feeds[:n, 2] += stereo[:n, 0] * gain * rear_cross
    feeds[:n, 3] += stereo[:n, 1] * gain * rear_cross
    return np.array([gain, gain, gain * rear_cross, gain * rear_cross], dtype=np.float32)


def add_mono_object_to_feeds(
    feeds: np.ndarray,
    audio: np.ndarray,
    gains: np.ndarray,
    obj: dict,
    sample_rate: int,
) -> None:
    x = np.asarray(audio, dtype=np.float32).reshape(-1)
    n = min(len(x), feeds.shape[0])
    if n == 0:
        return
    if obj.get("diffuseness", 0.0) >= 0.6 and obj.get("decorrelation", 0.0) > 0.0:
        lb, rb = decorrelate_rear(x[:n], sample_rate, obj.get("decorrelation", 0.0))
        feeds[:n, 0] += x[:n] * gains[0]
        feeds[:n, 1] += x[:n] * gains[1]
        feeds[:n, 2] += lb[:n] * gains[2]
        feeds[:n, 3] += rb[:n] * gains[3]
        return
    for index in range(feeds.shape[1]):
        feeds[:n, index] += x[:n] * gains[index]
