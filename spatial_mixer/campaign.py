"""Persistent calibration campaign behind the mixer's five-operation interface."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
from math import gcd, isfinite
from pathlib import Path
from typing import Mapping, Protocol
import json

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

from spatial_core.binaural import SofaBinauralRenderer
from spatial_core.evaluation import evaluate_clarity_gate, measure_clarity_metrics
from spatial_core.profile import SpatialCoreProfile

from .profile import MixerProfile, profile_from_payload, save_mixer_profile
from .rendering import build_mixer_scene, extract_mixer_zones


AUDIO_EXTENSIONS = {".wav", ".flac", ".aif", ".aiff", ".ogg", ".mp3"}
DEFAULT_CALIBRATION_SPECS = (
    ("孤勇者", "pop"),
    ("一路向北", "ballad"),
    ("Hans Zimmer - Time", "cinematic"),
    ("Test Drive", "cinematic"),
    ("Chan Chan (Live Session)", "world"),
    ("STAN GETZ - TANGERINE", "jazz"),
    ("Starboy", "electronic"),
    ("Sleep Token - The Summoning", "electronic"),
    ("Little Blue", "pop"),
)
PATCHABLE_PROFILE_FIELDS = {"zones", "room", "extraction"}
SCORE_FIELDS = {
    "clarity",
    "vocal_clarity",
    "bass",
    "depth",
    "width",
    "externalization",
    "distance",
    "timbre",
}


class PreviewRenderer(Protocol):
    def render(
        self,
        stereo: np.ndarray,
        sample_rate: int,
        profile: MixerProfile,
        audition: "AuditionState",
    ) -> tuple[np.ndarray, dict[str, object]]: ...


def _finite_number(name: str, value: object, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be within [{minimum}, {maximum}]")
    return result


@dataclass(frozen=True)
class MonitorProfile:
    output_gain_db: float = 0.0
    balance_db: float = 0.0
    low_db: float = 0.0
    low_mid_db: float = 0.0
    mid_db: float = 0.0
    presence_db: float = 0.0
    air_db: float = 0.0

    def __post_init__(self) -> None:
        _finite_number("output_gain_db", self.output_gain_db, -24.0, 12.0)
        _finite_number("balance_db", self.balance_db, -6.0, 6.0)
        for name in ("low_db", "low_mid_db", "mid_db", "presence_db", "air_db"):
            _finite_number(name, getattr(self, name), -12.0, 12.0)


@dataclass(frozen=True)
class AuditionState:
    muted: tuple[str, ...] = ()
    soloed: tuple[str, ...] = ()
    level_match: bool = True


class SpatialPreviewRenderer:
    """Measured-SOFA adapter used by the local campaign."""

    def __init__(self, sofa_path: str | Path):
        self.sofa_path = Path(sofa_path).expanduser().resolve()
        if not self.sofa_path.is_file():
            raise ValueError(f"SOFA file does not exist: {self.sofa_path}")

    def render(
        self,
        stereo: np.ndarray,
        sample_rate: int,
        profile: MixerProfile,
        audition: AuditionState,
    ) -> tuple[np.ndarray, dict[str, object]]:
        scene = build_mixer_scene(
            stereo,
            profile,
            sample_rate=sample_rate,
            muted=audition.muted,
            soloed=audition.soloed,
        )
        room = profile.room
        renderer_profile = SpatialCoreProfile(
            early_reflection_level_db=room.early_reflection_level_db,
            late_reverb_level_db=room.late_reverb_level_db,
            late_rt60_s=room.late_rt60_s,
        )
        result = SofaBinauralRenderer(
            self.sofa_path,
            room_profile="balanced-depth",
            profile=renderer_profile,
            block_size=8_192,
        ).render(scene)
        return result.audio, result.diagnostics


def _sha256_file(path: Path | None) -> str | None:
    if path is None:
        return None
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _deep_merge(base: dict[str, object], patch: Mapping[str, object]) -> dict[str, object]:
    result = json.loads(json.dumps(base))
    for key, value in patch.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _profile_state(profile: MixerProfile) -> dict[str, object]:
    return {"profile_hash": profile.profile_hash, "profile": profile.to_payload()}


def _profile_warnings(profile: MixerProfile) -> list[str]:
    warnings: list[str] = []
    left = profile.zones["front_L_residual"]
    right = profile.zones["front_R_residual"]
    if abs(abs(left.azimuth_deg) - abs(right.azimuth_deg)) > 5.0:
        warnings.append("front angle asymmetry exceeds 5 degrees")
    if abs(left.gain_db - right.gain_db) > 1.0:
        warnings.append("front gain asymmetry exceeds 1 dB")
    if profile.room.late_rt60_s > 0.70:
        warnings.append("late RT60 is outside the recommended dry-room range")
    return warnings


def _apply_monitor(audio: np.ndarray, sample_rate: int, monitor: MonitorProfile) -> np.ndarray:
    value = np.asarray(audio, dtype=np.float64)
    if value.size == 0:
        return value.astype(np.float32)
    bins = np.fft.rfftfreq(value.shape[0], 1.0 / sample_rate)
    anchors = np.array([20.0, 120.0, 500.0, 1_800.0, 5_000.0, 12_000.0, sample_rate / 2.0])
    gains = np.array(
        [
            monitor.low_db,
            monitor.low_db,
            monitor.low_mid_db,
            monitor.mid_db,
            monitor.presence_db,
            monitor.air_db,
            monitor.air_db,
        ]
    )
    curve_db = np.interp(bins, anchors, gains)
    spectrum = np.fft.rfft(value, axis=0)
    spectrum *= (10.0 ** (curve_db / 20.0))[:, None]
    filtered = np.fft.irfft(spectrum, n=value.shape[0], axis=0)
    left_gain = 10.0 ** ((monitor.output_gain_db - monitor.balance_db * 0.5) / 20.0)
    right_gain = 10.0 ** ((monitor.output_gain_db + monitor.balance_db * 0.5) / 20.0)
    filtered[:, 0] *= left_gain
    filtered[:, 1] *= right_gain
    return np.asarray(filtered, dtype=np.float32)


def _match_reference_level(reference: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    reference_rms = float(np.sqrt(np.mean(reference.astype(np.float64) ** 2)))
    candidate_rms = float(np.sqrt(np.mean(candidate.astype(np.float64) ** 2)))
    if reference_rms <= 1e-9 or candidate_rms <= 1e-9:
        return np.asarray(candidate, dtype=np.float32)
    gain = reference_rms / candidate_rms
    peak = float(np.max(np.abs(candidate)))
    if peak > 0.0:
        gain = min(gain, 0.98 / peak)
    return np.asarray(candidate * gain, dtype=np.float32)


class MixerService:
    """Deep module for campaign state, previews, comparisons, and promotion."""

    def __init__(
        self,
        *,
        library_dir: str | Path,
        workspace_dir: str | Path,
        sofa_path: str | Path | None = None,
        renderer: PreviewRenderer | None = None,
    ):
        self.library_dir = Path(library_dir).expanduser().resolve()
        self.workspace_dir = Path(workspace_dir).expanduser().resolve()
        if not self.library_dir.is_dir():
            raise ValueError(f"library directory does not exist: {self.library_dir}")
        if self.workspace_dir == self.library_dir or self.workspace_dir.is_relative_to(self.library_dir):
            raise ValueError("workspace directory must be outside the audio library")
        self.workspace_dir.mkdir(parents=True, exist_ok=True)
        self.sofa_path = None if sofa_path is None else Path(sofa_path).expanduser().resolve()
        self.sofa_sha256 = _sha256_file(self.sofa_path)
        self.renderer = renderer or SpatialPreviewRenderer(self.sofa_path)
        self._tracks = self._discover_tracks()
        campaign_path = self.workspace_dir / "campaign.json"
        if campaign_path.is_file():
            self._load_campaign(campaign_path)
        else:
            self.accepted = MixerProfile.default()
            self.draft = self.accepted
            self.monitor = MonitorProfile()
            self.audition = AuditionState()
            self.comparisons: list[dict[str, object]] = []
            self._write_revision(self.accepted)
            self._save_campaign()

    def _discover_tracks(self) -> list[dict[str, object]]:
        tracks: list[dict[str, object]] = []
        for path in sorted(self.library_dir.rglob("*")):
            if path.is_symlink() or not path.is_file() or path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            resolved = path.resolve()
            if not resolved.is_relative_to(self.library_dir):
                continue
            relative = resolved.relative_to(self.library_dir).as_posix()
            track_id = sha256(relative.encode("utf-8")).hexdigest()[:16]
            calibration_slot = None
            suggested_category = None
            lower_stem = path.stem.casefold()
            for index, (name_fragment, category) in enumerate(DEFAULT_CALIBRATION_SPECS):
                if name_fragment.casefold() in lower_stem:
                    calibration_slot = index
                    suggested_category = category
                    break
            tracks.append(
                {
                    "track_id": track_id,
                    "name": path.stem,
                    "relative_path": relative,
                    "calibration_slot": calibration_slot,
                    "suggested_category": suggested_category,
                }
            )
        tracks.sort(
            key=lambda item: (
                item["calibration_slot"] is None,
                item["calibration_slot"] if item["calibration_slot"] is not None else 999,
                str(item["name"]).casefold(),
            )
        )
        return tracks

    def _write_revision(self, profile: MixerProfile) -> None:
        save_mixer_profile(
            profile,
            self.workspace_dir / "revisions" / f"{profile.profile_hash}.json",
        )

    def _load_campaign(self, path: Path) -> None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to read calibration campaign: {path}") from exc
        if payload.get("format") != "spatial_mixer_campaign" or payload.get("version") != "1.0":
            raise ValueError("calibration campaign must use spatial_mixer_campaign version 1.0")
        stored_root = payload.get("library_root")
        if stored_root is not None and Path(str(stored_root)).resolve() != self.library_dir:
            raise ValueError("calibration campaign belongs to a different audio library")
        if payload.get("renderer_revision") != MixerProfile.default().renderer_revision:
            raise ValueError("calibration campaign renderer revision does not match this build")
        if payload.get("sofa_sha256") != self.sofa_sha256:
            raise ValueError("calibration campaign SOFA hash does not match the selected listener data")
        accepted = payload.get("accepted", {})
        draft = payload.get("draft", {})
        if not isinstance(accepted, Mapping) or not isinstance(draft, Mapping):
            raise ValueError("calibration campaign profiles are invalid")
        self.accepted = profile_from_payload(accepted.get("profile"))
        self.draft = profile_from_payload(draft.get("profile"))
        if accepted.get("profile_hash") != self.accepted.profile_hash:
            raise ValueError("accepted profile hash does not match campaign content")
        if draft.get("profile_hash") != self.draft.profile_hash:
            raise ValueError("draft profile hash does not match campaign content")
        monitor_values = payload.get("monitor", {})
        audition_values = payload.get("audition", {})
        if not isinstance(monitor_values, Mapping) or not isinstance(audition_values, Mapping):
            raise ValueError("calibration campaign monitor state is invalid")
        self.monitor = MonitorProfile(**dict(monitor_values))
        self.audition = AuditionState(
            muted=tuple(str(item) for item in audition_values.get("muted", [])),
            soloed=tuple(str(item) for item in audition_values.get("soloed", [])),
            level_match=bool(audition_values.get("level_match", True)),
        )
        comparisons = payload.get("comparisons", [])
        if not isinstance(comparisons, list) or not all(isinstance(item, dict) for item in comparisons):
            raise ValueError("calibration campaign comparisons must be a list")
        self.comparisons = list(comparisons)

    def _save_campaign(self) -> None:
        payload = {
            "format": "spatial_mixer_campaign",
            "version": "1.0",
            "renderer_revision": self.draft.renderer_revision,
            "library_root": str(self.library_dir),
            "sofa_sha256": self.sofa_sha256,
            "accepted": _profile_state(self.accepted),
            "draft": _profile_state(self.draft),
            "monitor": asdict(self.monitor),
            "audition": asdict(self.audition),
            "tracks": self._tracks,
            "comparisons": self.comparisons,
        }
        (self.workspace_dir / "campaign.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _state(self) -> dict[str, object]:
        comparisons = [
            {**item, "stale": item.get("profile_hash") != self.draft.profile_hash}
            for item in self.comparisons
        ]
        current = [item for item in comparisons if not item["stale"]]
        return {
            "accepted": _profile_state(self.accepted),
            "draft": _profile_state(self.draft),
            "monitor": asdict(self.monitor),
            "audition": asdict(self.audition),
            "tracks": list(self._tracks),
            "comparisons": comparisons,
            "validation": {
                "track_count": len({str(item["track_id"]) for item in current}),
                "category_count": len({str(item["category"]) for item in current}),
                "required_tracks": 9,
                "required_categories": 6,
            },
            "warnings": _profile_warnings(self.draft),
            "workspace": str(self.workspace_dir),
        }

    def open_campaign(self) -> dict[str, object]:
        return self._state()

    def patch_draft(self, patch: Mapping[str, object]) -> dict[str, object]:
        unknown = sorted(set(patch) - PATCHABLE_PROFILE_FIELDS)
        if unknown:
            raise ValueError(f"draft patch cannot change: {unknown[0]}")
        payload = _deep_merge(self.draft.to_payload(), patch)
        self.draft = profile_from_payload(payload)
        self._write_revision(self.draft)
        self._save_campaign()
        return self._state()

    def patch_monitor(self, patch: Mapping[str, object]) -> dict[str, object]:
        unknown = sorted(set(patch) - {item for item in asdict(self.monitor)})
        if unknown:
            raise ValueError(f"unknown monitor field: {unknown[0]}")
        self.monitor = replace(self.monitor, **dict(patch))
        self._save_campaign()
        return self._state()

    def patch_audition(self, patch: Mapping[str, object]) -> dict[str, object]:
        unknown = sorted(set(patch) - {"muted", "soloed", "level_match"})
        if unknown:
            raise ValueError(f"unknown audition field: {unknown[0]}")
        values = asdict(self.audition)
        values.update(patch)
        muted = tuple(str(item) for item in values["muted"])
        soloed = tuple(str(item) for item in values["soloed"])
        valid = set(self.draft.zones)
        if not set(muted).issubset(valid) or not set(soloed).issubset(valid):
            raise ValueError("audition mute/solo contains an unknown zone")
        self.audition = AuditionState(muted, soloed, bool(values["level_match"]))
        self._save_campaign()
        return self._state()

    def _track_path(self, track_id: str) -> Path:
        match = next((item for item in self._tracks if item["track_id"] == track_id), None)
        if match is None:
            raise ValueError("unknown track_id")
        path = (self.library_dir / str(match["relative_path"])).resolve()
        if not path.is_file() or not path.is_relative_to(self.library_dir):
            raise ValueError("track path is outside the allowed library")
        return path

    def _read_excerpt(
        self,
        path: Path,
        start_s: float,
        duration_s: float,
        target_rate: int = 48_000,
    ) -> tuple[np.ndarray, int]:
        if not 0.0 <= start_s:
            raise ValueError("start_s must be non-negative")
        if not 1.0 <= duration_s <= 30.0:
            raise ValueError("duration_s must be within [1, 30]")
        with sf.SoundFile(path) as handle:
            if handle.channels != 2:
                raise ValueError("calibration tracks must be stereo")
            handle.seek(min(int(round(start_s * handle.samplerate)), len(handle)))
            audio = handle.read(int(round(duration_s * handle.samplerate)), dtype="float32", always_2d=True)
            source_rate = int(handle.samplerate)
        if audio.shape[0] == 0:
            raise ValueError("excerpt starts after the end of the track")
        if source_rate != target_rate:
            divisor = gcd(source_rate, target_rate)
            audio = resample_poly(audio, target_rate // divisor, source_rate // divisor, axis=0)
        return np.asarray(audio, dtype=np.float32), target_rate

    def request_preview(
        self,
        *,
        track_id: str,
        start_s: float,
        duration_s: float,
    ) -> dict[str, object]:
        path = self._track_path(track_id)
        cache_payload = {
            "track_id": track_id,
            "track_size": path.stat().st_size,
            "track_mtime_ns": path.stat().st_mtime_ns,
            "start_s": float(start_s),
            "duration_s": float(duration_s),
            "accepted_hash": self.accepted.profile_hash,
            "draft_hash": self.draft.profile_hash,
            "audition": asdict(self.audition),
            "monitor": asdict(self.monitor),
            "sofa_sha256": self.sofa_sha256,
        }
        preview_id = sha256(
            json.dumps(cache_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:24]
        preview_dir = self.workspace_dir / "previews" / preview_id
        manifest_path = preview_dir / "preview.json"
        if manifest_path.is_file():
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            payload["cached"] = True
            return payload
        reference, sample_rate = self._read_excerpt(path, float(start_s), float(duration_s))
        try:
            a_audio, a_diagnostics = self.renderer.render(
                reference, sample_rate, self.accepted, self.audition
            )
            if self.accepted.profile_hash == self.draft.profile_hash:
                b_audio = np.asarray(a_audio, dtype=np.float32).copy()
                b_diagnostics = {**a_diagnostics, "reused_a_render": True}
            else:
                b_audio, b_diagnostics = self.renderer.render(
                    reference, sample_rate, self.draft, self.audition
                )
        except RuntimeError as exc:
            raise ValueError(str(exc)) from exc
        frames = max(reference.shape[0], a_audio.shape[0], b_audio.shape[0])

        def padded(value: np.ndarray) -> np.ndarray:
            return np.pad(value, ((0, frames - value.shape[0]), (0, 0)))

        reference = padded(reference)
        a_audio = padded(np.asarray(a_audio, dtype=np.float32))
        b_audio = padded(np.asarray(b_audio, dtype=np.float32))
        if self.audition.level_match:
            a_audio = _match_reference_level(reference, a_audio)
            b_audio = _match_reference_level(reference, b_audio)
        objective_metrics = measure_clarity_metrics(reference, b_audio, sample_rate)
        objective_gate = evaluate_clarity_gate(objective_metrics)
        rendered = {
            "reference": _apply_monitor(reference, sample_rate, self.monitor),
            "a": _apply_monitor(a_audio, sample_rate, self.monitor),
            "b": _apply_monitor(b_audio, sample_rate, self.monitor),
        }
        preview_dir.mkdir(parents=True, exist_ok=True)
        audio_paths: dict[str, str] = {}
        for name, audio in rendered.items():
            audio_path = preview_dir / f"{name}.wav"
            sf.write(audio_path, audio, sample_rate, subtype="FLOAT")
            audio_paths[name] = audio_path.relative_to(self.workspace_dir).as_posix()
        payload = {
            "preview_id": preview_id,
            "cached": False,
            "track_id": track_id,
            "sample_rate": sample_rate,
            "frames": frames,
            "audio": audio_paths,
            "profile_hash": self.draft.profile_hash,
            "objective_metrics": objective_metrics,
            "objective_gate": objective_gate,
            "diagnostics": {"a": a_diagnostics, "b": b_diagnostics},
        }
        manifest_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return payload

    def analyze_extraction(
        self,
        *,
        track_id: str,
        start_s: float,
        duration_s: float,
    ) -> dict[str, object]:
        """Return Lab diagnostics without changing the render profile or campaign scores."""

        reference, sample_rate = self._read_excerpt(
            self._track_path(track_id), float(start_s), float(duration_s)
        )
        zones = extract_mixer_zones(reference, self.draft, sample_rate=sample_rate)
        reconstruction = zones.reconstruct_stereo()
        error = reference - reconstruction
        reference_rms = float(np.sqrt(np.mean(reference.astype(np.float64) ** 2)))
        error_rms = float(np.sqrt(np.mean(error.astype(np.float64) ** 2)))
        if reference_rms <= 1e-12:
            raise ValueError("extraction analysis requires a non-silent excerpt")
        error_db = 20.0 * np.log10(max(error_rms / reference_rms, 1e-12))
        if not np.isfinite(error_db) or error_db >= -80.0:
            raise ValueError("extraction reconstruction error must remain below -80 dB")
        zone_metrics = {
            name: {
                "rms": float(np.sqrt(np.mean(value.astype(np.float64) ** 2))),
                "peak": float(np.max(np.abs(value))),
            }
            for name, value in zones.as_dict().items()
        }
        return {
            "track_id": track_id,
            "profile_hash": self.draft.profile_hash,
            "zones": zone_metrics,
            "reconstruction_error_db": float(error_db),
            "stft": {"size": 2048, "hop": 512, "editable": False},
        }

    def record_comparison(
        self,
        *,
        track_id: str,
        category: str,
        choice: str,
        scores: Mapping[str, object],
        objective_gate: Mapping[str, object],
        notes: str = "",
    ) -> dict[str, object]:
        """Record one listening decision against the current immutable draft hash."""

        self._track_path(track_id)
        category_name = str(category).strip()
        if not category_name:
            raise ValueError("comparison category is required")
        if choice not in {"a", "b", "equal"}:
            raise ValueError("comparison choice must be 'a', 'b', or 'equal'")
        required_scores = {"clarity", "bass", "depth", "externalization"}
        unknown_scores = sorted(set(scores) - SCORE_FIELDS)
        if unknown_scores:
            raise ValueError(f"unknown comparison score: {unknown_scores[0]}")
        missing_scores = sorted(required_scores - set(scores))
        if missing_scores:
            raise ValueError(f"missing comparison score: {missing_scores[0]}")
        validated_scores = {
            name: _finite_number(f"score {name}", value, 0.0, 10.0)
            for name, value in scores.items()
        }
        if objective_gate.get("pass") not in {True, False}:
            raise ValueError("objective_gate.pass must be boolean")
        failures = objective_gate.get("failures", [])
        if not isinstance(failures, list) or not all(isinstance(item, str) for item in failures):
            raise ValueError("objective_gate.failures must be a list of strings")
        record = {
            "track_id": track_id,
            "category": category_name,
            "choice": choice,
            "scores": validated_scores,
            "objective_gate": {"pass": objective_gate["pass"], "failures": list(failures)},
            "notes": str(notes),
            "profile_hash": self.draft.profile_hash,
            "accepted_hash": self.accepted.profile_hash,
        }
        self.comparisons = [
            item
            for item in self.comparisons
            if not (
                item.get("track_id") == track_id
                and item.get("profile_hash") == self.draft.profile_hash
            )
        ]
        self.comparisons.append(record)
        self._save_campaign()
        return self._state()

    def promote_profile(self, *, override_reason: str | None = None) -> dict[str, object]:
        """Promote one globally validated draft and retain all advisory warnings."""

        current = [
            item for item in self.comparisons if item.get("profile_hash") == self.draft.profile_hash
        ]
        track_count = len({str(item["track_id"]) for item in current})
        category_count = len({str(item["category"]) for item in current})
        if track_count < 9 or category_count < 6:
            raise ValueError("promotion requires nine tracks spanning at least six categories")
        objective_failures = [
            {
                "track_id": item["track_id"],
                "failures": item["objective_gate"].get("failures", []),
            }
            for item in current
            if item["objective_gate"].get("pass") is not True
        ]
        objective_override = bool(objective_failures)
        reason = "" if override_reason is None else str(override_reason).strip()
        if objective_override and not reason:
            raise ValueError("an override reason is required while objective warnings are red")
        export_dir = self.workspace_dir / "exports" / self.draft.profile_hash
        profile_path = save_mixer_profile(self.draft, export_dir / "universal-profile.json")
        evidence = {
            "format": "spatial_mixer_promotion_evidence",
            "version": "1.0",
            "profile_hash": self.draft.profile_hash,
            "renderer_revision": self.draft.renderer_revision,
            "sofa_sha256": self.sofa_sha256,
            "track_count": track_count,
            "category_count": category_count,
            "objective_override": objective_override,
            "override_reason": reason or None,
            "objective_failures": objective_failures,
            "comparisons": current,
            "monitor": asdict(self.monitor),
            "profile_warnings": _profile_warnings(self.draft),
        }
        evidence_path = export_dir / "evidence.json"
        evidence_path.write_text(
            json.dumps(evidence, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        report_path = export_dir / "report.md"
        warning_text = "none" if not objective_failures else ", ".join(
            f"{item['track_id']}: {', '.join(item['failures']) or 'unspecified'}"
            for item in objective_failures
        )
        report_path.write_text(
            "# Universal seven-zone calibration report\n\n"
            f"- Profile hash: `{self.draft.profile_hash}`\n"
            f"- Tracks: {track_count}\n"
            f"- Categories: {category_count}\n"
            f"- Objective override: {'yes' if objective_override else 'no'}\n"
            f"- Override reason: {reason or 'not required'}\n"
            f"- Objective warnings: {warning_text}\n\n"
            "This export is an immutable calibration artifact. It does not change the repository default.\n",
            encoding="utf-8",
        )
        self.accepted = self.draft
        self._save_campaign()
        exports = {
            "profile": profile_path.relative_to(self.workspace_dir).as_posix(),
            "evidence": evidence_path.relative_to(self.workspace_dir).as_posix(),
            "report": report_path.relative_to(self.workspace_dir).as_posix(),
        }
        return {
            "promoted": True,
            "profile_hash": self.accepted.profile_hash,
            "track_count": track_count,
            "category_count": category_count,
            "objective_override": objective_override,
            "exports": exports,
        }
