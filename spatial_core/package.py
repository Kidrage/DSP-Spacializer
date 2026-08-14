"""Validation for the renderer-neutral Spatial Scene Package master."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO
import zipfile

from jsonschema import Draft202012Validator
import soundfile as sf


PACKAGE_FORMAT = "spatial_scene_package"
PACKAGE_VERSION = "0.1"
ZONE_NAMES = (
    "bass",
    "center_anchor",
    "front_L_residual",
    "front_R_residual",
    "side_width",
    "rear_ambience",
    "high_air",
)
SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "spatial_scene_package-0.1.schema.json"


class ScenePackageError(ValueError):
    """Raised when a Spatial Scene Package violates its public contract."""


@dataclass(frozen=True)
class ScenePackageInfo:
    package_id: str
    container: str
    frame_count: int
    zone_names: tuple[str, ...]


def _load_schema() -> dict[str, Any]:
    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScenePackageError(f"unable to read package schema: {SCHEMA_PATH}") from exc
    Draft202012Validator.check_schema(schema)
    return schema


def _validate_manifest(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ScenePackageError("manifest must be a JSON object")
    validator = Draft202012Validator(_load_schema())
    errors = sorted(
        validator.iter_errors(payload),
        key=lambda error: tuple(str(item) for item in error.absolute_path),
    )
    if errors:
        error = errors[0]
        location = ".".join(str(item) for item in error.absolute_path) or "manifest"
        raise ScenePackageError(f"invalid manifest at {location}: {error.message}")
    return payload


def _safe_audio_path(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts or "\\" in relative:
        raise ScenePackageError(f"unsafe audio path: {relative}")
    candidate = root / Path(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.is_symlink():
            raise ScenePackageError(
                f"audio asset does not exist or is not a regular file: {relative}"
            )
    path = candidate.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise ScenePackageError(f"audio path escapes package: {relative}") from exc
    if path.is_symlink() or not path.is_file():
        raise ScenePackageError(f"audio asset does not exist or is not a regular file: {relative}")
    return path


def _stream_sha256(stream: BinaryIO) -> str:
    digest = sha256()
    while chunk := stream.read(1024 * 1024):
        digest.update(chunk)
    return digest.hexdigest()


def _validate_audio_info(info: Any, relative: str, frame_count: int) -> None:
    if info.format != "WAV" or info.subtype != "FLOAT":
        raise ScenePackageError(f"audio asset must be a 32-bit float WAV: {relative}")
    if info.channels != 1:
        raise ScenePackageError(f"audio asset must be mono: {relative}")
    if info.samplerate != 48_000:
        raise ScenePackageError(f"audio asset must use 48000 Hz: {relative}")
    if info.frames != frame_count:
        raise ScenePackageError(f"audio frame count mismatch: {relative}")


def _audio_references(payload: dict[str, Any]) -> list[tuple[str, str]]:
    references = [
        (
            str(payload["zones"][name]["audio"]["path"]),
            str(payload["zones"][name]["audio"]["sha256"]),
        )
        for name in ZONE_NAMES
    ]
    paths = [path for path, _ in references]
    if len(paths) != len(set(paths)):
        raise ScenePackageError("each zone must reference a unique audio asset")
    return references


def _validate_keyframes(payload: dict[str, Any], frame_count: int) -> None:
    for name in ZONE_NAMES:
        offsets = [int(item["sample_offset"]) for item in payload["zones"][name]["keyframes"]]
        if offsets[0] != 0:
            raise ScenePackageError(f"zone {name} must start at sample_offset 0")
        if offsets != sorted(set(offsets)):
            raise ScenePackageError(f"zone {name} keyframes must be strictly increasing")
        if offsets[-1] >= frame_count:
            raise ScenePackageError(f"zone {name} keyframe exceeds frame_count")


def _validate_directory_assets(root: Path, payload: dict[str, Any]) -> None:
    frame_count = int(payload["timebase"]["frame_count"])
    references = _audio_references(payload)
    expected = {"manifest.json", *(relative for relative, _ in references)}
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() or path.is_symlink()
    }
    if actual != expected:
        raise ScenePackageError("package members must be manifest.json and the seven referenced WAV files")
    for relative, expected_sha256 in references:
        path = _safe_audio_path(root, relative)
        with path.open("rb") as stream:
            actual_sha256 = _stream_sha256(stream)
        if actual_sha256 != expected_sha256:
            raise ScenePackageError(f"audio checksum mismatch: {relative}")
        info = sf.info(path)
        _validate_audio_info(info, relative, frame_count)


def _safe_zip_members(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    members = archive.infolist()
    names = [item.filename for item in members if not item.is_dir()]
    if len(names) != len(set(names)):
        raise ScenePackageError("ZIP contains duplicate members")
    result: dict[str, zipfile.ZipInfo] = {}
    for item in members:
        if item.is_dir():
            continue
        path = PurePosixPath(item.filename)
        unix_mode = item.external_attr >> 16
        if (
            path.is_absolute()
            or ".." in path.parts
            or "\\" in item.filename
            or not path.parts
            or unix_mode & 0o170000 == 0o120000
        ):
            raise ScenePackageError(f"unsafe ZIP member: {item.filename}")
        result[item.filename] = item
    return result


def _validate_zip_package(path: Path) -> tuple[dict[str, Any], int]:
    try:
        archive = zipfile.ZipFile(path, "r")
    except (OSError, zipfile.BadZipFile) as exc:
        raise ScenePackageError(f"unable to read package ZIP: {path}") from exc
    with archive:
        members = _safe_zip_members(archive)
        manifest_info = members.get("manifest.json")
        if manifest_info is None:
            raise ScenePackageError("ZIP package is missing manifest.json")
        if manifest_info.file_size > 1024 * 1024:
            raise ScenePackageError("manifest.json exceeds the 1 MiB limit")
        try:
            payload = json.loads(archive.read(manifest_info).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ScenePackageError("unable to decode ZIP package manifest") from exc
        manifest = _validate_manifest(payload)
        frame_count = int(manifest["timebase"]["frame_count"])
        _validate_keyframes(manifest, frame_count)
        references = _audio_references(manifest)
        expected = {"manifest.json", *(relative for relative, _ in references)}
        if set(members) != expected:
            raise ScenePackageError(
                "package members must be manifest.json and the seven referenced WAV files"
            )
        for relative, expected_sha256 in references:
            with archive.open(members[relative], "r") as stream:
                actual_sha256 = _stream_sha256(stream)
            if actual_sha256 != expected_sha256:
                raise ScenePackageError(f"audio checksum mismatch: {relative}")
            with archive.open(members[relative], "r") as stream:
                info = sf.info(stream)
            _validate_audio_info(info, relative, frame_count)
    return manifest, frame_count


def validate_scene_package(source: str | Path) -> ScenePackageInfo:
    """Validate one directory or ZIP v0.1 master package and return its identity."""

    path = Path(source).expanduser().resolve()
    if path.is_dir():
        manifest_path = path / "manifest.json"
        if manifest_path.is_symlink() or not manifest_path.is_file():
            raise ScenePackageError("manifest.json must be a regular file")
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ScenePackageError(f"unable to read package manifest: {manifest_path}") from exc
        manifest = _validate_manifest(payload)
        frame_count = int(manifest["timebase"]["frame_count"])
        _validate_keyframes(manifest, frame_count)
        _validate_directory_assets(path, manifest)
        container = "directory"
    elif path.is_file() and zipfile.is_zipfile(path):
        manifest, frame_count = _validate_zip_package(path)
        container = "zip"
    else:
        raise ScenePackageError("package source must be a directory or ZIP file")
    return ScenePackageInfo(
        package_id=str(manifest["package_id"]),
        container=container,
        frame_count=frame_count,
        zone_names=ZONE_NAMES,
    )
