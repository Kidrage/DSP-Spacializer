"""Spatial Core V2 scene model and portable JSON/WAV interchange."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import gcd
from pathlib import Path
import json
import re

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf


SCENE_FORMAT = "bds_spatial_scene"
SCENE_VERSION = "2.0"
FOA_CONVENTION = "AmbiX ACN/SN3D (W,Y,Z,X)"


def _mono(audio: np.ndarray, name: str) -> np.ndarray:
    value = np.asarray(audio, dtype=np.float32)
    if value.ndim != 1:
        raise ValueError(f"{name} must be mono")
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{name} contains non-finite samples")
    return value


@dataclass
class SpatialObject:
    object_id: str
    role: str
    audio: np.ndarray
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    distance_m: float = 1.0
    gain_db: float = 0.0
    size: float = 0.0
    diffusion: float = 0.0
    direct_ratio: float | None = None
    directivity: str = "omni"

    def __post_init__(self) -> None:
        if not self.object_id or not re.fullmatch(r"[A-Za-z0-9_.-]+", self.object_id):
            raise ValueError("object_id must contain only letters, digits, '.', '_' or '-'")
        self.audio = _mono(self.audio, f"object {self.object_id}")
        if not -180.0 <= float(self.azimuth_deg) <= 180.0:
            raise ValueError("azimuth must be within [-180, 180] degrees")
        if not -90.0 <= float(self.elevation_deg) <= 90.0:
            raise ValueError("elevation must be within [-90, 90] degrees")
        if not 0.1 <= float(self.distance_m) <= 10.0:
            raise ValueError("distance must be within [0.1, 10] metres")
        if not 0.0 <= float(self.size) <= 1.0:
            raise ValueError("size must be within [0, 1]")
        if not 0.0 <= float(self.diffusion) <= 1.0:
            raise ValueError("diffusion must be within [0, 1]")
        if self.direct_ratio is not None and not 0.0 <= float(self.direct_ratio) <= 1.0:
            raise ValueError("direct_ratio must be within [0, 1]")
        if self.directivity != "omni":
            raise ValueError("Spatial Core V2 supports omni directivity only")


@dataclass
class FoaBed:
    audio: np.ndarray

    def __post_init__(self) -> None:
        self.audio = np.asarray(self.audio, dtype=np.float32)
        if self.audio.ndim != 2 or self.audio.shape[1] != 4:
            raise ValueError("FOA bed must have four AmbiX channels ordered W,Y,Z,X")
        if not np.all(np.isfinite(self.audio)):
            raise ValueError("FOA bed contains non-finite samples")


@dataclass
class SpatialScene:
    sample_rate: int
    objects: list[SpatialObject] = field(default_factory=list)
    bed: FoaBed | None = None
    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sample_rate = int(self.sample_rate)
        if self.sample_rate < 8_000 or self.sample_rate > 384_000:
            raise ValueError("sample_rate must be within [8000, 384000]")
        ids = [item.object_id for item in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("object ids must be unique")
        if not self.objects and self.bed is None:
            raise ValueError("scene must contain at least one object or an FOA bed")
        self._pad_to_common_length()

    @property
    def num_frames(self) -> int:
        lengths = [item.audio.shape[0] for item in self.objects]
        if self.bed is not None:
            lengths.append(self.bed.audio.shape[0])
        return max(lengths, default=0)

    def _pad_to_common_length(self) -> None:
        length = self.num_frames
        for item in self.objects:
            if item.audio.shape[0] < length:
                item.audio = np.pad(item.audio, (0, length - item.audio.shape[0]))
        if self.bed is not None and self.bed.audio.shape[0] < length:
            self.bed.audio = np.pad(
                self.bed.audio,
                ((0, length - self.bed.audio.shape[0]), (0, 0)),
            )


def _resample(audio: np.ndarray, source_rate: int, target_rate: int) -> np.ndarray:
    if source_rate == target_rate:
        return np.asarray(audio, dtype=np.float32)
    divisor = gcd(int(source_rate), int(target_rate))
    result = resample_poly(audio, target_rate // divisor, source_rate // divisor, axis=0)
    return np.asarray(result, dtype=np.float32)


def _read_audio(path: Path, sample_rate: int, channels: int) -> np.ndarray:
    if not path.is_file():
        raise ValueError(f"audio file does not exist: {path}")
    audio, source_rate = sf.read(path, always_2d=True, dtype="float32")
    if audio.shape[1] != channels:
        label = "mono" if channels == 1 else "four-channel FOA"
        raise ValueError(f"{path} must be {label} audio")
    audio = _resample(audio, int(source_rate), sample_rate)
    return audio[:, 0] if channels == 1 else audio


def _resolve_audio_path(base: Path, value: object) -> Path:
    relative = Path(str(value))
    if not str(value) or relative.is_absolute():
        raise ValueError("scene audio paths must be non-empty and relative to the manifest")
    resolved = (base / relative).resolve()
    try:
        resolved.relative_to(base)
    except ValueError as exc:
        raise ValueError("scene audio path escapes the manifest directory") from exc
    return resolved


def load_scene(manifest_path: str | Path) -> SpatialScene:
    """Load and strictly validate a BDS Spatial Scene V2 manifest."""

    path = Path(manifest_path).expanduser().resolve()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read scene manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("scene manifest must be a JSON object")
    if payload.get("format") != SCENE_FORMAT or payload.get("version") != SCENE_VERSION:
        raise ValueError("scene manifest must use bds_spatial_scene version 2.0")
    sample_rate = int(payload.get("sample_rate", 0))
    if sample_rate < 8_000 or sample_rate > 384_000:
        raise ValueError("scene sample_rate must be within [8000, 384000]")
    base = path.parent
    objects: list[SpatialObject] = []
    object_specs = payload.get("objects", [])
    if not isinstance(object_specs, list):
        raise ValueError("scene objects must be a list")
    for spec in object_specs:
        if not isinstance(spec, dict):
            raise ValueError("each scene object must be a JSON object")
        position = spec.get("position", {})
        if not isinstance(position, dict):
            raise ValueError("object position must be a JSON object")
        objects.append(
            SpatialObject(
                object_id=str(spec.get("id", "")),
                role=str(spec.get("role", "object")),
                audio=_read_audio(_resolve_audio_path(base, spec.get("audio", "")), sample_rate, 1),
                azimuth_deg=float(position.get("azimuth", 0.0)),
                elevation_deg=float(position.get("elevation", 0.0)),
                distance_m=float(position.get("distance", 1.0)),
                gain_db=float(spec.get("gain_db", 0.0)),
                size=float(spec.get("size", 0.0)),
                diffusion=float(spec.get("diffusion", 0.0)),
                direct_ratio=(
                    None if spec.get("direct_ratio") is None else float(spec["direct_ratio"])
                ),
                directivity=str(spec.get("directivity", "omni")),
            )
        )
    bed_spec = payload.get("foa_bed")
    bed = None
    if bed_spec is not None:
        if not isinstance(bed_spec, dict):
            raise ValueError("foa_bed must be a JSON object")
        bed = FoaBed(
            _read_audio(_resolve_audio_path(base, bed_spec.get("audio", "")), sample_rate, 4)
        )
    return SpatialScene(
        sample_rate=sample_rate,
        objects=objects,
        bed=bed,
        metadata=dict(payload.get("metadata", {})),
    )


def save_scene(scene: SpatialScene, manifest_path: str | Path) -> Path:
    """Write a portable scene manifest and external WAV assets."""

    path = Path(manifest_path).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    asset_dir = path.parent / f"{path.stem}_audio"
    asset_dir.mkdir(parents=True, exist_ok=True)
    objects: list[dict[str, object]] = []
    for item in scene.objects:
        audio_path = asset_dir / f"{item.object_id}.wav"
        sf.write(audio_path, item.audio, scene.sample_rate, subtype="FLOAT")
        objects.append(
            {
                "id": item.object_id,
                "role": item.role,
                "audio": str(audio_path.relative_to(path.parent)),
                "position": {
                    "azimuth": item.azimuth_deg,
                    "elevation": item.elevation_deg,
                    "distance": item.distance_m,
                },
                "gain_db": item.gain_db,
                "size": item.size,
                "diffusion": item.diffusion,
                "direct_ratio": item.direct_ratio,
                "directivity": item.directivity,
            }
        )
    payload: dict[str, object] = {
        "format": SCENE_FORMAT,
        "version": SCENE_VERSION,
        "sample_rate": scene.sample_rate,
        "foa_convention": FOA_CONVENTION,
        "objects": objects,
        "metadata": scene.metadata,
    }
    if scene.bed is not None:
        bed_path = asset_dir / "foa_bed.wav"
        sf.write(bed_path, scene.bed.audio, scene.sample_rate, subtype="FLOAT")
        payload["foa_bed"] = {
            "audio": str(bed_path.relative_to(path.parent)),
            "channel_order": "W,Y,Z,X",
            "normalization": "SN3D",
        }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
