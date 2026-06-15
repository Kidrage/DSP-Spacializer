"""Preset-to-routing adapter.

The notebook uses a flat routing dictionary. This module applies
analysis-based adaptations (center guard, width boost, diffuse boost,
transient guard) on top of a preset to produce the final routing parameters
used by renderer_4ch.
"""

import numpy as np


def apply_preset(preset_dict, analysis, preset_name="manual", apply_analysis_adaptation=True):
    """Apply a flat preset dictionary, optionally adapting to analysis features.

    Parameters
    ----------
    preset_dict : dict
        Flat preset values (side_rear, amb_rear, air_rear, decorrelation,
        bass_gain, bass_quad, lowbody_rear, rear_floor_ratio, max_rear_makeup,
        rear_air_gain, rear_highmid_gain, guard_scale, rear_master, side_front).
    analysis : dict
        Audio analysis features from streaming_analyzer.
        Expected keys: center_guard, transient, width, high_diffuse.
    preset_name : str
        Label for the preset (stored in routing for diagnostics).
    apply_analysis_adaptation : bool
        If True, adjust routing based on center guard, width, diffuse, transient.
        Set False for auto_acoustic which already baked these in.

    Returns
    -------
    routing : dict
        Final routing parameters, clipped to safe ranges.
    """
    routing = dict(preset_dict)  # shallow copy

    # extract analysis features with safe defaults
    center_coherence = float(analysis.get("center_coherence", 0.5))
    transient = float(analysis.get("transient", 0.03))
    width = float(analysis.get("width", 0.25))
    high_diffuse = float(analysis.get("high_diffuse", 0.15))
    guard_scale = float(routing.get("guard_scale", 1.0))

    # ---- analysis adaptation (skipped for auto_acoustic) ----
    center_guard = np.clip((center_coherence - 0.3) / 0.7, 0.0, 1.0)
    transient_guard = np.clip(transient / 0.05, 0.0, 1.0)
    width_boost = 1.0
    diffuse_boost = 1.0

    if apply_analysis_adaptation:
        routing["side_rear"] *= (1.0 - 0.10 * guard_scale * center_guard)
        routing["amb_rear"] *= (1.0 - 0.08 * guard_scale * center_guard)
        routing["air_rear"] *= (1.0 - 0.14 * guard_scale * center_guard)
        width_boost = np.clip(0.85 + width / 0.40, 0.85, 1.45)
        routing["side_rear"] *= width_boost
        diffuse_boost = np.clip(1.0 + 1.4 * high_diffuse, 1.0, 1.35)
        routing["amb_rear"] *= diffuse_boost
        routing["air_rear"] *= np.clip(1.0 + 0.7 * high_diffuse, 1.0, 1.20)
        routing["decorrelation"] *= (1.0 - 0.14 * guard_scale * transient_guard)
        routing["amb_rear"] *= (1.0 - 0.05 * guard_scale * transient_guard)
        routing["air_rear"] *= (1.0 - 0.08 * guard_scale * transient_guard)
        routing["lowbody_rear"] *= (1.0 - 0.12 * guard_scale * center_guard)
        routing["lowbody_rear"] *= (1.0 - 0.10 * guard_scale * transient_guard)
        routing["bass_quad"] *= (1.0 - 0.18 * guard_scale * transient_guard)

    # ---- clip all routing values to safe ranges ----
    for key in ["side_front", "side_rear", "amb_rear", "air_rear",
                "rear_master", "decorrelation", "bass_quad", "lowbody_rear"]:
        routing[key] = float(np.clip(routing.get(key, 0.0), 0.0, 1.8))
    routing["rear_floor_ratio"] = float(np.clip(routing.get("rear_floor_ratio", 0.0), 0.0, 0.30))
    routing["max_rear_makeup"] = float(np.clip(routing.get("max_rear_makeup", 1.0), 1.0, 8.0))
    routing["rear_air_gain"] = float(np.clip(routing.get("rear_air_gain", 1.0), 0.08, 1.0))
    routing["rear_highmid_gain"] = float(np.clip(routing.get("rear_highmid_gain", 1.0), 0.18, 1.10))
    routing["bass_gain"] = float(np.clip(routing.get("bass_gain", 1.0), 0.85, 1.30))
    routing["bass_quad"] = float(np.clip(routing.get("bass_quad", 0.0), 0.0, 0.25))
    routing["lowbody_rear"] = float(np.clip(routing.get("lowbody_rear", 0.0), 0.0, 0.60))

    # attach metadata for diagnostics
    routing.update({
        "preset_name": preset_name,
        "center_guard": float(center_guard),
        "transient_guard": float(transient_guard),
        "width_boost": float(width_boost),
        "diffuse_boost": float(diffuse_boost),
    })
    return routing


# Compatibility wrapper for old code that called route_layers().
def route_layers(layers, routing_params, sample_rate):
    from renderer_4ch import render_4ch
    zeros = next(iter(layers.values())) * 0.0
    return render_4ch(zeros, zeros, layers, routing_params, sample_rate,
                      routing_params.get("preset_name", "manual"))
