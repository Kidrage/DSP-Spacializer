"""Layout math helpers shared by pseudo-object renderers."""

from __future__ import annotations

import math

import numpy as np


def normalize_azimuth_360(azimuth_deg: float) -> float:
    return float((float(azimuth_deg) + 360.0) % 360.0)


def azimuth_to_unit_xy(azimuth_deg: float) -> np.ndarray:
    """
    Coordinate convention:
    0 degrees = front (+y)
    +90 = right (+x)
    -90 = left (-x)
    180/-180 = rear (-y)
    """
    theta = math.radians(float(azimuth_deg))
    return np.array([math.sin(theta), math.cos(theta)], dtype=np.float32)


def azimuth_radius_to_xy(azimuth_deg: float, radius: float) -> np.ndarray:
    return azimuth_to_unit_xy(azimuth_deg) * float(radius)


def sorted_speakers_by_azimuth(layout: dict) -> list[dict]:
    indexed = []
    for index, speaker in enumerate(layout.get("speakers", [])):
        item = dict(speaker)
        item["_layout_index"] = index
        item["_azimuth_360"] = normalize_azimuth_360(item.get("azimuth", 0.0))
        indexed.append(item)
    return sorted(indexed, key=lambda speaker: speaker["_azimuth_360"])


def speaker_ids(layout: dict) -> list[str]:
    return [speaker["id"] for speaker in layout.get("speakers", [])]


def apply_gain_trim_and_delay(
    feeds: np.ndarray,
    layout: dict,
    sample_rate: int,
) -> np.ndarray:
    """
    Apply per-speaker gain trims.  ``delay_ms`` is intentionally preserved in
    the layout contract for future calibration; V1 does not delay samples yet.
    """
    del sample_rate
    out = np.asarray(feeds, dtype=np.float32).copy()
    for index, speaker in enumerate(layout.get("speakers", [])):
        trim_db = float(speaker.get("gain_trim_db", 0.0))
        out[:, index] *= float(10.0 ** (trim_db / 20.0))
    return out.astype(np.float32)
