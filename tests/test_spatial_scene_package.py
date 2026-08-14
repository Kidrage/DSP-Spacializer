import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np
import pytest
import soundfile as sf

from examples.build_spatial_scene_package_example import build_example, write_zip
from spatial_core import ScenePackageError, validate_scene_package
from spatial_mixer.profile import ZONE_NAMES as MIXER_ZONE_NAMES


ZONE_NAMES = (
    "bass",
    "center_anchor",
    "front_L_residual",
    "front_R_residual",
    "side_width",
    "rear_ambience",
    "high_air",
)


def _object_keyframe(*, azimuth_deg: float = 0.0, size: float = 0.05) -> dict[str, object]:
    return {
        "sample_offset": 0,
        "interpolation": "hold",
        "gain_db": 0.0,
        "azimuth_deg": azimuth_deg,
        "elevation_deg": 0.0,
        "distance_m": 1.6,
        "size": size,
        "diffusion": 0.0,
        "direct_ratio": 0.78,
        "early_reflection_trim_db": 0.0,
        "late_reverb_trim_db": 0.0,
    }


def _field_keyframe(*, gain_db: float, azimuth_deg: float, elevation_deg: float = 0.0):
    return {
        "sample_offset": 0,
        "interpolation": "hold",
        "gain_db": gain_db,
        "azimuth_deg": azimuth_deg,
        "elevation_deg": elevation_deg,
    }


def _write_package(root: Path, *, frames: int = 64) -> Path:
    audio_dir = root / "audio"
    audio_dir.mkdir(parents=True)
    audio_refs: dict[str, dict[str, str]] = {}
    for index, name in enumerate(ZONE_NAMES, start=1):
        path = audio_dir / f"{name}.wav"
        signal = np.zeros(frames, dtype=np.float32)
        signal[0] = index / 100.0
        sf.write(path, signal, 48_000, subtype="FLOAT")
        audio_refs[name] = {
            "path": f"audio/{name}.wav",
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
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
            "extractor_revision": "1.0",
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
                "keyframes": [_object_keyframe()],
            },
            "center_anchor": {
                "kind": "object",
                "role": "center",
                "audio": audio_refs["center_anchor"],
                "keyframes": [_object_keyframe(size=0.0)],
            },
            "front_L_residual": {
                "kind": "object",
                "role": "front",
                "audio": audio_refs["front_L_residual"],
                "keyframes": [_object_keyframe(azimuth_deg=35.0)],
            },
            "front_R_residual": {
                "kind": "object",
                "role": "front",
                "audio": audio_refs["front_R_residual"],
                "keyframes": [_object_keyframe(azimuth_deg=-35.0)],
            },
            "side_width": {
                "kind": "mirrored_field",
                "role": "width",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["side_width"],
                "keyframes": [_field_keyframe(gain_db=-12.0412, azimuth_deg=75.0)],
            },
            "rear_ambience": {
                "kind": "mirrored_field",
                "role": "ambience",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["rear_ambience"],
                "keyframes": [_field_keyframe(gain_db=-14.89455, azimuth_deg=135.0)],
            },
            "high_air": {
                "kind": "mirrored_field",
                "role": "air",
                "field_mode": "mirrored_opposite_polarity",
                "audio": audio_refs["high_air"],
                "keyframes": [
                    _field_keyframe(gain_db=-18.41638, azimuth_deg=110.0, elevation_deg=35.0)
                ],
            },
        },
        "extensions": {},
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def _load_manifest(package: Path) -> dict[str, object]:
    return json.loads((package / "manifest.json").read_text(encoding="utf-8"))


def _save_manifest(package: Path, manifest: dict[str, object]) -> None:
    (package / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )


def _replace_bass_audio(package: Path, signal: np.ndarray, sample_rate: int, subtype: str) -> None:
    path = package / "audio" / "bass.wav"
    sf.write(path, signal, sample_rate, subtype=subtype)
    manifest = _load_manifest(package)
    manifest["zones"]["bass"]["audio"]["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    _save_manifest(package, manifest)


def test_valid_directory_package_passes_end_to_end_validation(tmp_path):
    package = _write_package(tmp_path / "example.spatialpkg")

    result = validate_scene_package(package)

    assert result.package_id == "urn:uuid:11111111-2222-4333-8444-555555555555"
    assert result.container == "directory"
    assert result.frame_count == 64
    assert result.zone_names == ZONE_NAMES
    assert result.zone_names == MIXER_ZONE_NAMES


def test_valid_zip_package_uses_the_same_public_validator(tmp_path):
    package = _write_package(tmp_path / "unpacked")
    archive = tmp_path / "example.spatialpkg"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(package).as_posix())

    result = validate_scene_package(archive)

    assert result.container == "zip"
    assert result.frame_count == 64
    assert result.zone_names == ZONE_NAMES


def test_package_requires_the_canonical_seven_zones(tmp_path):
    package = _write_package(tmp_path / "missing-zone")
    manifest = _load_manifest(package)
    del manifest["zones"]["high_air"]
    _save_manifest(package, manifest)

    with pytest.raises(ScenePackageError, match="high_air"):
        validate_scene_package(package)


def test_keyframes_start_at_zero_and_are_strictly_increasing(tmp_path):
    package = _write_package(tmp_path / "bad-keyframes")
    manifest = _load_manifest(package)
    first = manifest["zones"]["bass"]["keyframes"][0]
    later = dict(first, sample_offset=32)
    earlier = dict(first, sample_offset=16)
    manifest["zones"]["bass"]["keyframes"] = [first, later, earlier]
    _save_manifest(package, manifest)

    with pytest.raises(ScenePackageError, match="strictly increasing"):
        validate_scene_package(package)


def test_package_rejects_audio_checksum_mismatch(tmp_path):
    package = _write_package(tmp_path / "bad-checksum")
    manifest = _load_manifest(package)
    manifest["zones"]["bass"]["audio"]["sha256"] = "f" * 64
    _save_manifest(package, manifest)

    with pytest.raises(ScenePackageError, match="checksum mismatch"):
        validate_scene_package(package)


@pytest.mark.parametrize(
    ("signal", "sample_rate", "subtype", "message"),
    [
        (np.zeros(64, dtype=np.float32), 44_100, "FLOAT", "48000 Hz"),
        (np.zeros((64, 2), dtype=np.float32), 48_000, "FLOAT", "mono"),
        (np.zeros(64, dtype=np.float32), 48_000, "PCM_24", "32-bit float WAV"),
        (np.zeros(63, dtype=np.float32), 48_000, "FLOAT", "frame count mismatch"),
    ],
)
def test_package_rejects_noncanonical_audio_assets(
    tmp_path, signal, sample_rate, subtype, message
):
    package = _write_package(tmp_path / "bad-audio")
    _replace_bass_audio(package, signal, sample_rate, subtype)

    with pytest.raises(ScenePackageError, match=message):
        validate_scene_package(package)


def test_package_rejects_unreferenced_members(tmp_path):
    package = _write_package(tmp_path / "extra-member")
    (package / "notes.txt").write_text("not part of the v0.1 package\n", encoding="utf-8")

    with pytest.raises(ScenePackageError, match="package members"):
        validate_scene_package(package)


def test_directory_package_rejects_symlinked_audio(tmp_path):
    package = _write_package(tmp_path / "symlinked-audio")
    bass = package / "audio" / "bass.wav"
    target = package / "audio" / "center_anchor.wav"
    bass.unlink()
    bass.symlink_to(target.name)
    manifest = _load_manifest(package)
    manifest["zones"]["bass"]["audio"]["sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    _save_manifest(package, manifest)

    with pytest.raises(ScenePackageError, match="regular file"):
        validate_scene_package(package)


def test_directory_package_rejects_symlinked_manifest(tmp_path):
    package = _write_package(tmp_path / "symlinked-manifest")
    manifest = package / "manifest.json"
    target = tmp_path / "external-manifest.json"
    manifest.rename(target)
    manifest.symlink_to(target)

    with pytest.raises(ScenePackageError, match="manifest.json must be a regular file"):
        validate_scene_package(package)


def test_zip_package_rejects_path_traversal_members(tmp_path):
    package = _write_package(tmp_path / "unpacked-unsafe")
    archive = tmp_path / "unsafe.spatialpkg"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                output.write(path, path.relative_to(package).as_posix())
        output.writestr("../escape.wav", b"unsafe")

    with pytest.raises(ScenePackageError, match="unsafe ZIP member"):
        validate_scene_package(archive)


def test_documented_example_generator_creates_valid_directory_and_zip(tmp_path):
    package = build_example(tmp_path / "example")
    archive = write_zip(package, tmp_path / "example.spatialpkg")

    assert validate_scene_package(package).frame_count == 480
    assert validate_scene_package(archive).container == "zip"
