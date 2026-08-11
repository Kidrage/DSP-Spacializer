"""Renderer contracts shared by Spatial Core V2 output backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

import numpy as np

from limiter import apply_limiter

from .scene import SpatialScene


@dataclass
class RenderResult:
    audio: np.ndarray
    sample_rate: int
    diagnostics: dict[str, object] = field(default_factory=dict)


class SceneRenderer(Protocol):
    def render(self, scene: SpatialScene) -> RenderResult: ...


def linked_peak_limit(audio: np.ndarray, ceiling: float = 0.98) -> tuple[np.ndarray, float]:
    """Apply one linked output gain, preserving all inter-channel relationships."""

    value = np.asarray(audio, dtype=np.float32)
    peak = float(np.max(np.abs(value))) if value.size else 0.0
    gain = min(1.0, float(ceiling) / peak) if peak > 0 else 1.0
    return np.asarray(value * gain, dtype=np.float32), gain


def linked_peak_limiter(
    audio: np.ndarray,
    sample_rate: int,
    ceiling: float = 0.98,
) -> tuple[np.ndarray, dict[str, object]]:
    """Limit local overloads with one gain envelope shared by both ears."""

    limited, report = apply_limiter(
        audio,
        threshold=ceiling,
        sample_rate=int(sample_rate),
        return_report=True,
    )
    return np.asarray(limited, dtype=np.float32), report
