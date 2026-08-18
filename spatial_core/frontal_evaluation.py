"""Reproducible, path-safe evaluation support for frontal binaural experiments."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from math import gcd
from pathlib import Path, PurePosixPath
import re

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

from .binaural import SofaBinauralRenderer
from .builder import build_scene
from .profile import SpatialCoreProfile
from .scene import SpatialObject, SpatialScene


FRONTAL_AZIMUTHS_DEG = (0.0, -5.0, 5.0, -10.0, 10.0, -20.0, 20.0)
FRONTAL_DISTANCES_M = (0.5, 1.0, 1.6, 2.5)
CORPUS_FORMAT = "frontal_externalization_corpus"
CORPUS_VERSION = "1.0"
TRACK_ROLES = {
    "independent_male_vocal_mix",
    "independent_female_vocal_mix",
    "same_mix_sequential_vocals",
}
EXCERPT_ROLES = {"male_vocal", "female_vocal"}
_IDENTIFIER_PATTERN = re.compile(r"[a-z][a-z0-9_]*\Z")
_SHA256_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
_SOURCE_REVISION_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")


@dataclass(frozen=True)
class FrontalProbeCase:
    case_id: str
    azimuth_deg: float
    distance_m: float


@dataclass(frozen=True)
class EvaluationExcerpt:
    id: str
    role: str
    start_s: float
    duration_s: float


@dataclass(frozen=True)
class EvaluationTrack:
    id: str
    role: str
    relative_path: str
    sha256: str
    excerpts: tuple[EvaluationExcerpt, ...]


@dataclass(frozen=True)
class FrontalCorpus:
    tracks: tuple[EvaluationTrack, ...]


def _number_token(value: float) -> str:
    sign = "m" if value < 0.0 else "p"
    magnitude = f"{abs(value):.1f}".replace(".", "p")
    return f"{sign}{magnitude}"


def frontal_probe_cases() -> tuple[FrontalProbeCase, ...]:
    """Return the fixed 7-angle by 4-distance FEX-0 probe matrix."""

    return tuple(
        FrontalProbeCase(
            case_id=f"az_{_number_token(azimuth)}_d_{str(distance).replace('.', 'p')}",
            azimuth_deg=azimuth,
            distance_m=distance,
        )
        for distance in FRONTAL_DISTANCES_M
        for azimuth in FRONTAL_AZIMUTHS_DEG
    )


def _strict_keys(payload: dict[str, object], expected: set[str], label: str) -> None:
    missing = sorted(expected - set(payload))
    unknown = sorted(set(payload) - expected)
    if missing:
        raise ValueError(f"{label} is missing field: {missing[0]}")
    if unknown:
        raise ValueError(f"{label} has unknown field: {unknown[0]}")


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase identifier")
    return value


def _number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be numeric")
    return float(value)


def load_frontal_corpus(path: str | Path) -> FrontalCorpus:
    """Load a strict corpus manifest whose audio paths remain root-relative."""

    manifest_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read frontal corpus: {manifest_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("frontal corpus must be a JSON object")
    _strict_keys(payload, {"format", "version", "tracks"}, "frontal corpus")
    if payload["format"] != CORPUS_FORMAT or payload["version"] != CORPUS_VERSION:
        raise ValueError("frontal corpus must use frontal_externalization_corpus version 1.0")
    raw_tracks = payload["tracks"]
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raise ValueError("frontal corpus tracks must be a non-empty array")

    tracks: list[EvaluationTrack] = []
    track_ids: set[str] = set()
    for index, raw_track in enumerate(raw_tracks):
        label = f"track[{index}]"
        if not isinstance(raw_track, dict):
            raise ValueError(f"{label} must be a JSON object")
        _strict_keys(
            raw_track,
            {"id", "role", "relative_path", "sha256", "excerpts"},
            label,
        )
        track_id = _identifier(raw_track["id"], f"{label}.id")
        if track_id in track_ids:
            raise ValueError(f"duplicate track id: {track_id}")
        track_ids.add(track_id)
        role = raw_track["role"]
        if not isinstance(role, str) or role not in TRACK_ROLES:
            raise ValueError(f"{label}.role is not supported")
        relative_path = raw_track["relative_path"]
        if not isinstance(relative_path, str) or not relative_path:
            raise ValueError(f"{label}.relative_path must be a non-empty string")
        relative = PurePosixPath(relative_path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in relative_path:
            raise ValueError(f"{label}.relative_path must remain root-relative")
        digest = raw_track["sha256"]
        if not isinstance(digest, str) or _SHA256_PATTERN.fullmatch(digest) is None:
            raise ValueError(f"{label}.sha256 must be a lowercase SHA-256 digest")
        raw_excerpts = raw_track["excerpts"]
        if not isinstance(raw_excerpts, list) or not raw_excerpts:
            raise ValueError(f"{label}.excerpts must be a non-empty array")
        excerpts: list[EvaluationExcerpt] = []
        excerpt_ids: set[str] = set()
        for excerpt_index, raw_excerpt in enumerate(raw_excerpts):
            excerpt_label = f"{label}.excerpts[{excerpt_index}]"
            if not isinstance(raw_excerpt, dict):
                raise ValueError(f"{excerpt_label} must be a JSON object")
            _strict_keys(
                raw_excerpt,
                {"id", "role", "start_s", "duration_s"},
                excerpt_label,
            )
            excerpt_id = _identifier(raw_excerpt["id"], f"{excerpt_label}.id")
            if excerpt_id in excerpt_ids:
                raise ValueError(f"duplicate excerpt id in {track_id}: {excerpt_id}")
            excerpt_ids.add(excerpt_id)
            excerpt_role = raw_excerpt["role"]
            if not isinstance(excerpt_role, str) or excerpt_role not in EXCERPT_ROLES:
                raise ValueError(f"{excerpt_label}.role is not supported")
            start_s = _number(raw_excerpt["start_s"], f"{excerpt_label}.start_s")
            duration_s = _number(
                raw_excerpt["duration_s"],
                f"{excerpt_label}.duration_s",
            )
            if start_s < 0.0:
                raise ValueError(f"{excerpt_label}.start_s must be non-negative")
            if not 0.0 < duration_s <= 120.0:
                raise ValueError(f"{excerpt_label}.duration_s must be within (0, 120]")
            excerpts.append(
                EvaluationExcerpt(excerpt_id, excerpt_role, start_s, duration_s)
            )
        tracks.append(
            EvaluationTrack(
                track_id,
                role,
                relative_path,
                digest,
                tuple(excerpts),
            )
        )
    return FrontalCorpus(tuple(tracks))


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(payload: object) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _write_json(path: Path, payload: object) -> str:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return _file_sha256(path)


def _resolve_track_path(root: Path, track: EvaluationTrack) -> Path:
    candidate = root / PurePosixPath(track.relative_path)
    if candidate.is_symlink():
        raise ValueError(f"corpus track must not be a symbolic link: {track.id}")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"corpus track is unavailable: {track.id}") from exc
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError(f"corpus track escapes the library root: {track.id}")
    actual_digest = _file_sha256(resolved)
    if actual_digest != track.sha256:
        raise ValueError(f"corpus track hash mismatch: {track.id}")
    return resolved


def _read_excerpt(
    path: Path,
    excerpt: EvaluationExcerpt,
    target_sample_rate: int,
) -> np.ndarray:
    with sf.SoundFile(path) as handle:
        if handle.channels != 2:
            raise ValueError(f"evaluation track must be stereo: {path.name}")
        source_rate = int(handle.samplerate)
        start_frame = int(round(excerpt.start_s * source_rate))
        frame_count = int(round(excerpt.duration_s * source_rate))
        if start_frame < 0 or start_frame + frame_count > len(handle):
            raise ValueError(f"excerpt exceeds track duration: {excerpt.id}")
        handle.seek(start_frame)
        audio = handle.read(frame_count, dtype="float32", always_2d=True)
    if source_rate != target_sample_rate:
        divisor = gcd(source_rate, target_sample_rate)
        audio = resample_poly(
            audio,
            target_sample_rate // divisor,
            source_rate // divisor,
            axis=0,
        )
    return np.asarray(audio, dtype=np.float32)


def _pink_noise(num_frames: int, seed: int = 20260818) -> np.ndarray:
    white = np.random.default_rng(seed).standard_normal(num_frames)
    spectrum = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(num_frames)
    weighting = np.zeros_like(frequencies)
    weighting[1:] = 1.0 / np.sqrt(frequencies[1:])
    signal = np.fft.irfft(spectrum * weighting, n=num_frames)
    rms = float(np.sqrt(np.mean(signal**2)))
    return np.asarray(signal * (0.03 / max(rms, 1e-12)), dtype=np.float32)


def _short_transient(num_frames: int, sample_rate: int) -> np.ndarray:
    time = np.arange(num_frames, dtype=np.float64) / sample_rate
    signal = np.exp(-time / 0.006) * np.sin(2.0 * np.pi * 1_800.0 * time)
    peak = float(np.max(np.abs(signal)))
    return np.asarray(signal * (0.08 / max(peak, 1e-12)), dtype=np.float32)


def _probe_scene(
    signal: np.ndarray,
    sample_rate: int,
    case: FrontalProbeCase,
    profile: SpatialCoreProfile,
) -> SpatialScene:
    role = "center" if case.azimuth_deg == 0.0 else "front"
    source_rms = float(np.sqrt(np.mean(signal.astype(np.float64) ** 2)))
    return SpatialScene(
        sample_rate,
        objects=[
            SpatialObject(
                "frontal_probe",
                role,
                signal,
                azimuth_deg=case.azimuth_deg,
                elevation_deg=0.0,
                distance_m=case.distance_m,
                size=0.0,
                direct_ratio=profile.direct_ratio,
            )
        ],
        metadata={
            "source": "frontal_probe",
            "mastered_reference_rms": source_rms,
        },
    )


def _json_safe(value: object) -> object:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _safe_diagnostics(
    diagnostics: dict[str, object],
    *,
    sofa_name: str,
    sofa_sha256: str,
    audio: np.ndarray,
) -> dict[str, object]:
    safe = dict(diagnostics)
    safe.pop("sofa", None)
    safe["sofa_file"] = sofa_name
    safe["sofa_sha256"] = sofa_sha256
    value = np.asarray(audio, dtype=np.float64)
    safe["output"] = {
        "frames": int(value.shape[0]),
        "peak": float(np.max(np.abs(value))),
        "rms_left": float(np.sqrt(np.mean(value[:, 0] ** 2))),
        "rms_right": float(np.sqrt(np.mean(value[:, 1] ** 2))),
    }
    return _json_safe(safe)  # type: ignore[return-value]


def render_fex0_baseline(
    *,
    corpus: FrontalCorpus,
    library_root: str | Path,
    sofa_path: str | Path,
    output_dir: str | Path,
    profile: SpatialCoreProfile,
    source_revision: str,
    probe_duration_s: float = 1.0,
    sample_rate: int = 48_000,
) -> Path:
    """Render the fixed FEX-0 baseline and return its path-safe manifest."""

    revision = source_revision.strip() if isinstance(source_revision, str) else ""
    if _SOURCE_REVISION_PATTERN.fullmatch(revision) is None:
        raise ValueError("source_revision must be a path-free revision identifier")
    if profile != SpatialCoreProfile():
        raise ValueError("FEX-0 condition A requires legacy defaults")
    if isinstance(probe_duration_s, bool) or not 0.01 <= probe_duration_s <= 10.0:
        raise ValueError("probe_duration_s must be within [0.01, 10.0]")
    if isinstance(sample_rate, bool) or sample_rate < 8_000:
        raise ValueError("sample_rate must be at least 8000")
    root = Path(library_root).expanduser().resolve(strict=True)
    if not root.is_dir():
        raise ValueError("library_root must be a directory")
    measured_sofa = Path(sofa_path).expanduser().resolve(strict=True)
    if not measured_sofa.is_file():
        raise ValueError("sofa_path must be a file")
    destination = Path(output_dir).expanduser().resolve()
    if destination.exists() and any(destination.iterdir()):
        raise ValueError("output_dir must be absent or empty")
    audio_dir = destination / "audio"
    diagnostics_dir = destination / "diagnostics"
    audio_dir.mkdir(parents=True, exist_ok=True)
    diagnostics_dir.mkdir(parents=True, exist_ok=True)

    sofa_digest = _file_sha256(measured_sofa)
    renderer = SofaBinauralRenderer(
        measured_sofa,
        room_profile="balanced-depth",
        profile=profile,
        block_size=8_192,
    )
    artifacts: list[dict[str, object]] = []

    def persist(
        artifact_id: str,
        scene: SpatialScene,
        source: dict[str, object],
    ) -> None:
        result = renderer.render(scene)
        audio_relative = Path("audio") / f"{artifact_id}.wav"
        diagnostics_relative = Path("diagnostics") / f"{artifact_id}.json"
        audio_path = destination / audio_relative
        diagnostics_path = destination / diagnostics_relative
        sf.write(audio_path, result.audio, result.sample_rate, subtype="FLOAT")
        diagnostics = _safe_diagnostics(
            result.diagnostics,
            sofa_name=measured_sofa.name,
            sofa_sha256=sofa_digest,
            audio=result.audio,
        )
        diagnostics_digest = _write_json(diagnostics_path, diagnostics)
        artifacts.append(
            {
                "id": artifact_id,
                "source": source,
                "audio_file": audio_relative.as_posix(),
                "audio_sha256": _file_sha256(audio_path),
                "diagnostics_file": diagnostics_relative.as_posix(),
                "diagnostics_sha256": diagnostics_digest,
            }
        )

    probe_frames = int(round(probe_duration_s * sample_rate))
    probes = {
        "pink_noise": _pink_noise(probe_frames),
        "short_transient": _short_transient(probe_frames, sample_rate),
    }
    for probe_name, signal in probes.items():
        for case in frontal_probe_cases():
            persist(
                f"probe_{probe_name}_{case.case_id}",
                _probe_scene(signal, sample_rate, case, profile),
                {
                    "kind": "synthetic_probe",
                    "probe": probe_name,
                    "case_id": case.case_id,
                    "azimuth_deg": case.azimuth_deg,
                    "distance_m": case.distance_m,
                },
            )

    for track in corpus.tracks:
        track_path = _resolve_track_path(root, track)
        for excerpt in track.excerpts:
            stereo = _read_excerpt(track_path, excerpt, sample_rate)
            persist(
                f"excerpt_{track.id}_{excerpt.id}",
                build_scene(stereo, profile=profile, sample_rate=sample_rate),
                {
                    "kind": "stereo_excerpt",
                    "track_id": track.id,
                    "track_role": track.role,
                    "relative_path": track.relative_path,
                    "source_sha256": track.sha256,
                    "excerpt_id": excerpt.id,
                    "excerpt_role": excerpt.role,
                    "start_s": excerpt.start_s,
                    "duration_s": excerpt.duration_s,
                },
            )

    parameters = {
        "condition": "A",
        "profile": asdict(profile),
        "room_profile": "balanced-depth",
        "sample_rate": sample_rate,
        "probe_duration_s": probe_duration_s,
    }
    manifest: dict[str, object] = {
        "format": "frontal_externalization_baseline",
        "version": "1.0",
        "stage": "FEX-0",
        "source_revision": revision,
        "parameters": parameters,
        "parameters_sha256": sha256(_canonical_bytes(parameters)).hexdigest(),
        "sofa": {"filename": measured_sofa.name, "sha256": sofa_digest},
        "probe_matrix": {
            "azimuths_deg": list(FRONTAL_AZIMUTHS_DEG),
            "distances_m": list(FRONTAL_DISTANCES_M),
        },
        "artifacts": artifacts,
    }
    manifest["content_sha256"] = sha256(_canonical_bytes(manifest)).hexdigest()
    manifest_path = destination / "manifest.json"
    _write_json(manifest_path, manifest)
    return manifest_path
