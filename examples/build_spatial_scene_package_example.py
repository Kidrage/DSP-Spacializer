"""Generate a tiny, synthetic Spatial Scene Package without committing audio."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import zipfile

import numpy as np
import soundfile as sf

from spatial_core import validate_scene_package


ZONE_NAMES = (
    "bass",
    "center_anchor",
    "front_L_residual",
    "front_R_residual",
    "side_width",
    "rear_ambience",
    "high_air",
)


def _object_keyframe(azimuth: float, size: float) -> dict[str, object]:
    return {
        "sample_offset": 0,
        "interpolation": "hold",
        "gain_db": 0.0,
        "azimuth_deg": azimuth,
        "elevation_deg": 0.0,
        "distance_m": 1.6,
        "size": size,
        "diffusion": 0.0,
        "direct_ratio": 0.78,
        "early_reflection_trim_db": 0.0,
        "late_reverb_trim_db": 0.0,
    }


def _field_keyframe(gain: float, azimuth: float, elevation: float = 0.0):
    return {
        "sample_offset": 0,
        "interpolation": "hold",
        "gain_db": gain,
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
    }


def build_example(root: str | Path) -> Path:
    """Create one 10 ms conformance example in a new directory."""

    package = Path(root).expanduser().resolve()
    if package.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {package}")
    audio_dir = package / "audio"
    audio_dir.mkdir(parents=True)
    frames = 480
    audio_refs: dict[str, dict[str, str]] = {}
    for index, name in enumerate(ZONE_NAMES, start=1):
        path = audio_dir / f"{name}.wav"
        signal = np.zeros(frames, dtype=np.float32)
        signal[index] = index / 100.0
        sf.write(path, signal, 48_000, subtype="FLOAT")
        audio_refs[name] = {
            "path": f"audio/{name}.wav",
            "sha256": sha256(path.read_bytes()).hexdigest(),
        }

    manifest = {
        "format": "spatial_scene_package",
        "version": "0.1",
        "package_id": "urn:uuid:11111111-2222-4333-8444-555555555555",
        "timebase": {"sample_rate": 48_000, "frame_count": frames},
        "coordinate_system": {
            "reference": "listener",
            "azimuth_zero": "front",
            "positive_azimuth": "left",
            "positive_elevation": "up",
            "distance_unit": "metre",
        },
        "source": {
            "kind": "stereo_seven_zone",
            "extractor_revision": "example-1.0",
            "source_sha256": "0" * 64,
            "profile_sha256": "1" * 64,
        },
        "room": {
            "early_reflection_level_db": -21.0,
            "late_reverb_level_db": -27.0,
            "late_rt60_s": 0.35,
        },
        "zones": {
            "bass": {
                "kind": "object",
                "role": "bass",
                "audio": audio_refs["bass"],
                "keyframes": [_object_keyframe(0.0, 0.05)],
            },
            "center_anchor": {
                "kind": "object",
                "role": "center",
                "audio": audio_refs["center_anchor"],
                "keyframes": [_object_keyframe(0.0, 0.0)],
            },
            "front_L_residual": {
                "kind": "object",
                "role": "front",
                "audio": audio_refs["front_L_residual"],
                "keyframes": [_object_keyframe(35.0, 0.05)],
            },
            "front_R_residual": {
                "kind": "object",
                "role": "front",
                "audio": audio_refs["front_R_residual"],
                "keyframes": [_object_keyframe(-35.0, 0.05)],
            },
            "side_width": {
                "kind": "mirrored_field",
                "role": "width",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["side_width"],
                "keyframes": [_field_keyframe(-12.0412, 75.0)],
            },
            "rear_ambience": {
                "kind": "mirrored_field",
                "role": "ambience",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["rear_ambience"],
                "keyframes": [_field_keyframe(-14.89455, 135.0)],
            },
            "high_air": {
                "kind": "mirrored_field",
                "role": "air",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["high_air"],
                "keyframes": [_field_keyframe(-18.41638, 110.0, 35.0)],
            },
        },
        "extensions": {},
    }
    (package / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    validate_scene_package(package)
    return package


def write_zip(package: str | Path, archive: str | Path) -> Path:
    """Write a standard ZIP container without changing the source directory."""

    root = Path(package).expanduser().resolve()
    output = Path(archive).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {output}")
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                target.write(path, path.relative_to(root).as_posix())
    validate_scene_package(output)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", help="New directory to create")
    parser.add_argument("--zip", action="store_true", help="Also create OUTPUT.spatialpkg")
    args = parser.parse_args()
    package = build_example(args.output)
    print(package)
    if args.zip:
        archive = write_zip(package, package.with_suffix(".spatialpkg"))
        print(archive)


if __name__ == "__main__":
    main()
