"""Export pseudo-object layer audio material."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from audio_io import export_audio


def _mono_layer(layers: dict, key: str, n: int) -> np.ndarray:
    if key in layers:
        return np.asarray(layers[key], dtype=np.float32)
    return np.zeros(n, dtype=np.float32)


def build_object_audio_layers(layers: dict) -> dict:
    """Return object-id keyed audio arrays before final limiting/mastering."""
    n = len(next(iter(layers.values()))) if layers else 0
    front_l = _mono_layer(layers, "front_L", n)
    front_r = _mono_layer(layers, "front_R", n)
    return {
        "bass_anchor": _mono_layer(layers, "bass", n),
        "front_core": np.stack([front_l, front_r], axis=1).astype(np.float32),
        "side_width": _mono_layer(layers, "side_width", n),
        "rear_ambience": _mono_layer(layers, "rear_ambience", n),
        "high_air": _mono_layer(layers, "high_air", n),
        "low_body_support": _mono_layer(layers, "low_body", n),
    }


def export_object_audio(object_audio: dict, object_audio_dir: str | Path, sample_rate: int) -> dict:
    """Write object audio files and return object-id -> relative filename map."""
    out_dir = Path(object_audio_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for object_id, audio in object_audio.items():
        path = out_dir / f"{object_id}.wav"
        export_audio(path, audio, sample_rate)
        paths[object_id] = path.name
    return paths
