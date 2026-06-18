"""Diagnostics helpers for pseudo-object scenes."""

from __future__ import annotations

from collections import Counter

import numpy as np


def summarize_scene(scene: dict) -> dict:
    objects = list(scene.get("objects", []))
    roles = Counter(obj.get("role", "unknown") for obj in objects)
    spreads = [float(obj.get("spread", 0.0)) for obj in objects]
    diffuseness = [float(obj.get("diffuseness", 0.0)) for obj in objects]
    return {
        "object_count": len(objects),
        "roles": dict(roles),
        "mean_spread": float(np.mean(spreads)) if spreads else 0.0,
        "mean_diffuseness": float(np.mean(diffuseness)) if diffuseness else 0.0,
        "motion_object_count": int(sum(obj.get("motion", {}).get("type", "static") != "static" for obj in objects)),
        "front_locked_object_count": int(sum(bool(obj.get("constraints", {}).get("keep_front")) for obj in objects)),
        "rear_preferred_object_count": int(sum(bool(obj.get("constraints", {}).get("prefer_rear")) for obj in objects)),
        "mono_safe_object_count": int(sum(bool(obj.get("constraints", {}).get("mono_safe")) for obj in objects)),
    }
