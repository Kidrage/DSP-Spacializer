"""Object/FOA-to-headphone renderer backed exclusively by measured SOFA HRIRs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt
from scipy.spatial.transform import Rotation

from .foa import encode_mono_foa
from .hrtf import InterpolatedHrir, SofaHrirDatabase
from .motion import ListenerTrajectory, MicroMotion, relative_direction
from .profile import SpatialCoreProfile
from .rendering import RenderResult, linked_peak_limiter
from .room import ROOM_DIMENSIONS_M, balanced_depth_reflections
from .scene import SpatialObject, SpatialScene


EARLY_DELAYS_MS = np.asarray([4.2, 6.7, 10.8, 16.5, 24.0, 33.0], dtype=float)
EARLY_LEVELS_DB = np.asarray([-22.0, -23.5, -25.0, -27.0, -29.0, -31.0], dtype=float)
EARLY_AZIMUTH_OFFSETS = np.asarray([-38.0, 42.0, 96.0, -112.0, 154.0, -166.0])
EARLY_ELEVATION_OFFSETS = np.asarray([0.0, 8.0, -6.0, 12.0, -10.0, 5.0])
BALANCED_REFERENCE_DIRECT_RATIO = 0.78


def distance_gain_db(distance_m: float) -> float:
    return float(np.clip(20.0 * np.log10(1.0 / float(distance_m)), -18.0, 6.0))


def default_direct_ratio(distance_m: float) -> float:
    return float(1.0 / (1.0 + (float(distance_m) / 2.0) ** 2))


def apply_air_absorption(audio: np.ndarray, sample_rate: int, distance_m: float) -> np.ndarray:
    attenuation_db = -0.5 * max(0.0, float(distance_m) - 1.0)
    if attenuation_db == 0.0 or audio.size == 0:
        return np.asarray(audio, dtype=np.float32)
    spectrum = np.fft.rfft(np.asarray(audio, dtype=np.float64))
    frequencies = np.fft.rfftfreq(audio.size, 1.0 / sample_rate)
    high_gain = 10.0 ** (attenuation_db / 20.0)
    spectrum[frequencies >= 6_000.0] *= high_gain
    return np.asarray(np.fft.irfft(spectrum, n=audio.size), dtype=np.float32)


def _apply_hrir(signal: np.ndarray, hrir: InterpolatedHrir) -> np.ndarray:
    output_length = signal.size + hrir.ir.shape[-1] + int(np.ceil(np.max(hrir.delay_samples))) + 1
    output = np.zeros((output_length, 2), dtype=np.float64)
    for ear in range(2):
        convolved = fftconvolve(signal, hrir.ir[ear], mode="full")
        delay = float(hrir.delay_samples[ear])
        base = int(np.floor(delay))
        fraction = delay - base
        output[base : base + convolved.size, ear] += (1.0 - fraction) * convolved
        output[base + 1 : base + convolved.size + 1, ear] += fraction * convolved
    return np.asarray(output, dtype=np.float32)


def _apply_common_field_compensation(
    audio: np.ndarray,
    correction_ir: np.ndarray,
) -> np.ndarray:
    value = np.asarray(audio, dtype=np.float32)
    output = np.zeros((value.shape[0] + correction_ir.size - 1, 2), dtype=np.float32)
    for ear in range(2):
        output[:, ear] = fftconvolve(value[:, ear], correction_ir, mode="full").astype(np.float32)
    return output


def _size_rays(item: SpatialObject) -> list[tuple[float, float, float]]:
    if item.size <= 1e-6:
        return [(item.azimuth_deg, item.elevation_deg, 1.0)]
    azimuth_spread = 30.0 * item.size
    elevation_spread = 15.0 * item.size
    directions = [
        (item.azimuth_deg, item.elevation_deg),
        (item.azimuth_deg - azimuth_spread, item.elevation_deg),
        (item.azimuth_deg + azimuth_spread, item.elevation_deg),
        (item.azimuth_deg, item.elevation_deg - elevation_spread),
        (item.azimuth_deg, item.elevation_deg + elevation_spread),
    ]
    # Every ray carries the same source signal and nearby HRIRs remain highly
    # correlated. Amplitude-normalize the copies instead of treating them as
    # independent energy sources.
    weight = 1.0 / len(directions)
    return [(azimuth, elevation, weight) for azimuth, elevation in directions]


def _rotate_foa_to_listener(foa: np.ndarray, rotation: Rotation) -> np.ndarray:
    result = np.asarray(foa, dtype=np.float32).copy()
    xyz = np.stack([result[:, 3], result[:, 1], result[:, 2]], axis=1)
    relative = rotation.inv().apply(xyz)
    result[:, 3] = relative[:, 0]
    result[:, 1] = relative[:, 1]
    result[:, 2] = relative[:, 2]
    return result


def _late_reverb_foa(
    audio: np.ndarray,
    sample_rate: int,
    *,
    rt60_s: float = 0.30,
    length_s: float = 0.50,
    start_s: float = 0.03,
    level_db: float | None = None,
    band_limits_hz: tuple[float, float] | None = None,
    decay_from_start: bool = False,
) -> np.ndarray:
    """Create a deterministic shaped late FOA field."""

    length = max(1, int(round(float(length_s) * sample_rate)))
    start = int(round(float(start_s) * sample_rate))
    time = np.arange(length, dtype=np.float64) / sample_rate
    decay_time = np.maximum(0.0, time - float(start_s)) if decay_from_start else time
    envelope = 10.0 ** (-3.0 * decay_time / float(rt60_s))
    rng = np.random.default_rng(32)
    output = np.zeros((audio.size + length - 1, 4), dtype=np.float32)
    target_norm = 0.08 if level_db is None else 10.0 ** (float(level_db) / 20.0)
    for channel in range(4):
        kernel = rng.standard_normal(length) * envelope
        kernel[: min(start, length)] = 0.0
        if band_limits_hz is not None:
            low, high = band_limits_hz
            sos = butter(2, [float(low), float(high)], btype="bandpass", fs=sample_rate, output="sos")
            kernel = sosfilt(sos, kernel)
        norm = np.linalg.norm(kernel)
        if norm > 0:
            kernel *= target_norm / norm
        output[:, channel] = fftconvolve(audio, kernel, mode="full")
    return output


def _balanced_wet_gain(direct_ratio: float) -> float:
    reference_wet = np.sqrt(1.0 - BALANCED_REFERENCE_DIRECT_RATIO)
    return float(np.sqrt(max(0.0, 1.0 - direct_ratio)) / reference_wet)


def _match_mastered_loudness(
    output: np.ndarray,
    scene: SpatialScene,
) -> tuple[np.ndarray, float, bool]:
    target_rms = scene.metadata.get("mastered_reference_rms")
    if isinstance(target_rms, bool) or not isinstance(target_rms, (int, float)):
        return output, 0.0, False
    target_rms = float(target_rms)
    active = output[: scene.num_frames]
    current_rms = float(np.sqrt(np.mean(active.astype(np.float64) ** 2)))
    if not np.isfinite(target_rms) or target_rms <= 0.0 or current_rms <= 0.0:
        return output, 0.0, False
    requested_gain = float(
        np.clip(
            target_rms / current_rms,
            10.0 ** (-6.0 / 20.0),
            10.0 ** (8.0 / 20.0),
        )
    )
    peak = float(np.max(np.abs(output)))
    headroom_gain = 0.98 / peak if peak > 0.0 else requested_gain
    gain = min(requested_gain, headroom_gain)
    peak_limited = gain < requested_gain - 1e-9
    return (
        np.asarray(output * gain, dtype=np.float32),
        float(20.0 * np.log10(gain)),
        peak_limited,
    )


class SofaBinauralRenderer:
    """Render SpatialScene objects and its FOA bed directly to headphones."""

    def __init__(
        self,
        sofa_path: str | Path,
        *,
        listener_trajectory: ListenerTrajectory | None = None,
        micro_motion: bool = False,
        motion_seed: int = 0,
        room_enabled: bool = True,
        room_profile: str = "small-dry",
        profile: SpatialCoreProfile | None = None,
        block_size: int = 512,
    ):
        if room_profile not in {"small-dry", "balanced-depth", "off"}:
            raise ValueError("room_profile must be 'small-dry', 'balanced-depth', or 'off'")
        self.sofa_path = Path(sofa_path)
        self.listener_trajectory = listener_trajectory
        self.micro_motion = MicroMotion(motion_seed) if micro_motion else None
        self.room_profile = room_profile if room_enabled else "off"
        self.room_enabled = self.room_profile != "off"
        self.profile = profile or SpatialCoreProfile()
        if self.profile.direct_ratio_mode != "manual":
            raise ValueError(
                "direct_ratio_mode=distance_curve is reserved for frozen FEX-2"
            )
        if self.profile.mastered_loudness_mode == "level_matched_eval":
            raise ValueError(
                "mastered_loudness_mode=level_matched_eval requires the FEX-1 "
                "evaluation exporter"
            )
        self.block_size = max(64, int(block_size))
        self._databases: dict[int, SofaHrirDatabase] = {}

    def _database(self, sample_rate: int) -> SofaHrirDatabase:
        if sample_rate not in self._databases:
            self._databases[sample_rate] = SofaHrirDatabase(self.sofa_path, sample_rate)
        return self._databases[sample_rate]

    def _rotation_at(self, time_s: float) -> Rotation:
        rotation = (
            self.listener_trajectory.rotation_at(time_s)
            if self.listener_trajectory is not None
            else Rotation.identity()
        )
        if self.micro_motion is not None:
            rotation = rotation * self.micro_motion.rotation_at(time_s)
        return rotation

    @staticmethod
    def _add(output: np.ndarray, rendered: np.ndarray, start: int, gain: float = 1.0) -> None:
        stop = min(output.shape[0], start + rendered.shape[0])
        if stop > start:
            output[start:stop] += float(gain) * rendered[: stop - start]

    def _render_directional_block(
        self,
        database: SofaHrirDatabase,
        signal: np.ndarray,
        azimuth_deg: float,
        elevation_deg: float,
        rotation: Rotation,
    ) -> tuple[np.ndarray, float]:
        azimuth, elevation = relative_direction(azimuth_deg, elevation_deg, rotation)
        hrir = database.interpolate(azimuth, elevation)
        return database.front_reference_gain * _apply_hrir(signal, hrir), hrir.nearest_error_deg

    def _render_foa(
        self,
        database: SofaHrirDatabase,
        foa: np.ndarray,
        output: np.ndarray,
        sample_rate: int,
    ) -> None:
        filters = database.front_reference_gain * database.foa_to_ear_filters()
        for start in range(0, foa.shape[0], self.block_size):
            block = foa[start : start + self.block_size]
            time_s = (start + 0.5 * block.shape[0]) / sample_rate
            relative = _rotate_foa_to_listener(block, self._rotation_at(time_s))
            rendered = np.zeros((block.shape[0] + filters.shape[-1] - 1, 2), dtype=np.float32)
            for channel in range(4):
                for ear in range(2):
                    rendered[:, ear] += fftconvolve(
                        relative[:, channel], filters[channel, ear], mode="full"
                    ).astype(np.float32)
            self._add(output, rendered, start)

    def render(self, scene: SpatialScene) -> RenderResult:
        database = self._database(scene.sample_rate)
        hrir_tail = database.ir.shape[-1] + int(np.ceil(np.max(database.delays))) + 1
        room_tail = int(round(0.50 * scene.sample_rate)) if self.room_enabled else 0
        output = np.zeros((scene.num_frames + hrir_tail + room_tail, 2), dtype=np.float32)
        diffuse_foa = np.zeros((scene.num_frames, 4), dtype=np.float32)
        late_send = np.zeros(scene.num_frames, dtype=np.float32)
        max_coverage_error = 0.0
        balanced_early_taps = 0
        balanced_last_early_ms = 0.0
        late_start_s = 0.03
        for item in scene.objects:
            signal = apply_air_absorption(item.audio, scene.sample_rate, item.distance_m)
            signal *= 10.0 ** ((item.gain_db + distance_gain_db(item.distance_m)) / 20.0)
            direct_ratio = item.direct_ratio
            if direct_ratio is None:
                direct_ratio = default_direct_ratio(item.distance_m)
            direct_gain = np.sqrt(direct_ratio) if self.room_enabled else 1.0
            room_gain = np.sqrt(max(0.0, 1.0 - direct_ratio)) if self.room_enabled else 0.0
            balanced_reflections = ()
            balanced_room_send = 0.0
            if self.room_profile == "balanced-depth":
                balanced_reflections = balanced_depth_reflections(item)
                balanced_early_taps += len(balanced_reflections)
                if balanced_reflections:
                    balanced_last_early_ms = max(
                        balanced_last_early_ms,
                        balanced_reflections[-1].delay_ms,
                    )
                balanced_room_send = _balanced_wet_gain(direct_ratio)
                if item.role == "center":
                    balanced_room_send *= 10.0 ** (
                        self.profile.center_room_send_db / 20.0
                    )
                if self.profile.reflection_normalization_mode == "legacy_per_object":
                    reflection_norm = np.linalg.norm(
                        [reflection.relative_gain for reflection in balanced_reflections]
                    )
                else:
                    reflection_norm = 1.0
            else:
                reflection_norm = 1.0
            dry_gain = np.sqrt(max(0.0, 1.0 - item.diffusion))
            diffuse_gain = np.sqrt(item.diffusion)
            for start in range(0, scene.num_frames, self.block_size):
                block = signal[start : start + self.block_size]
                time_s = (start + 0.5 * block.size) / scene.sample_rate
                rotation = self._rotation_at(time_s)
                for azimuth, elevation, ray_gain in _size_rays(item):
                    rendered, error = self._render_directional_block(
                        database, block, azimuth, elevation, rotation
                    )
                    max_coverage_error = max(max_coverage_error, error)
                    self._add(output, rendered, start, direct_gain * dry_gain * ray_gain)
                if self.room_profile == "balanced-depth" and balanced_reflections:
                    for reflection in balanced_reflections:
                        reflected, error = self._render_directional_block(
                            database,
                            block,
                            reflection.azimuth_deg,
                            reflection.elevation_deg,
                            rotation,
                        )
                        max_coverage_error = max(max_coverage_error, error)
                        delay = int(round(reflection.delay_ms * scene.sample_rate / 1000.0))
                        gain = (
                            balanced_room_send
                            * 10.0 ** (self.profile.early_reflection_level_db / 20.0)
                            * 10.0 ** (item.early_reflection_trim_db / 20.0)
                            * reflection.relative_gain
                            / max(float(reflection_norm), 1e-9)
                        )
                        self._add(output, reflected, start + delay, gain)
                elif room_gain > 0.0:
                    for delay_ms, level_db, az_offset, el_offset in zip(
                        EARLY_DELAYS_MS,
                        EARLY_LEVELS_DB,
                        EARLY_AZIMUTH_OFFSETS,
                        EARLY_ELEVATION_OFFSETS,
                    ):
                        reflected, error = self._render_directional_block(
                            database,
                            block,
                            item.azimuth_deg + az_offset,
                            np.clip(item.elevation_deg + el_offset, -90.0, 90.0),
                            rotation,
                        )
                        max_coverage_error = max(max_coverage_error, error)
                        delay = int(round(float(delay_ms) * scene.sample_rate / 1000.0))
                        gain = (
                            room_gain
                            * 10.0 ** (float(level_db) / 20.0)
                            * 10.0 ** (item.early_reflection_trim_db / 20.0)
                        )
                        self._add(output, reflected, start + delay, gain)
            if diffuse_gain > 0.0:
                send = signal * diffuse_gain
                # Each SN3D direction has basis energy 2. Two decorrelated
                # sends at gain .5 retain unit total power.
                diffuse_foa += encode_mono_foa(send, item.azimuth_deg + 90.0, 20.0, 0.5)
                delayed = np.pad(send[:-17] if send.size > 17 else np.zeros(0), (17, 0))
                diffuse_foa += encode_mono_foa(delayed, item.azimuth_deg - 115.0, -12.0, 0.5)
            if self.room_profile == "balanced-depth":
                late_send += (
                    balanced_room_send
                    * 10.0 ** (item.late_reverb_trim_db / 20.0)
                    * signal
                )
            elif room_gain > 0.0:
                late_send += (
                    room_gain
                    * 10.0 ** (item.late_reverb_trim_db / 20.0)
                    * signal
                )
        if np.any(late_send):
            if self.room_profile == "balanced-depth":
                late_start_s = (balanced_last_early_ms + 10.0) / 1_000.0
                late_field = _late_reverb_foa(
                    late_send,
                    scene.sample_rate,
                    rt60_s=self.profile.late_rt60_s,
                    start_s=late_start_s,
                    level_db=self.profile.late_reverb_level_db,
                    band_limits_hz=(180.0, 8_000.0),
                    decay_from_start=True,
                )
            else:
                late_start_s = 0.03
                late_field = _late_reverb_foa(late_send, scene.sample_rate)
            diffuse_foa = np.pad(
                diffuse_foa,
                ((0, late_field.shape[0] - diffuse_foa.shape[0]), (0, 0)),
            )
            diffuse_foa += late_field
        if scene.bed is not None:
            diffuse_foa[: scene.num_frames] += scene.bed.audio
        if np.any(diffuse_foa):
            self._render_foa(database, diffuse_foa, output, scene.sample_rate)
        compensation_active = (
            self.profile.hrtf_compensation_mode == "legacy_front_common"
            and self.profile.hrtf_compensation_strength > 0.0
        )
        if compensation_active:
            output = _apply_common_field_compensation(
                output,
                database.timbre_compensation_for_strength(
                    self.profile.hrtf_compensation_strength
                ),
            )
        else:
            output = np.pad(
                output,
                ((0, database.timbre_compensation_ir.size - 1), (0, 0)),
            )
        if self.profile.mastered_loudness_mode == "legacy_input_rms":
            output, mastered_loudness_gain_db, mastered_loudness_peak_limited = (
                _match_mastered_loudness(output, scene)
            )
        else:
            mastered_loudness_gain_db = 0.0
            mastered_loudness_peak_limited = False
        limited, limiter_report = linked_peak_limiter(output, scene.sample_rate)
        limiter_gain = 10.0 ** (-float(limiter_report["max_gain_reduction_db"]) / 20.0)
        if self.room_profile == "balanced-depth":
            room_diagnostics: dict[str, object] | None = {
                "name": "balanced-depth",
                "dimensions_m": ROOM_DIMENSIONS_M.tolist(),
                "first_order_candidates_per_object": 6,
                "early_taps_rendered": balanced_early_taps,
                "minimum_early_delay_ms": 8.0,
                "early_reflection_level_db": self.profile.early_reflection_level_db,
                "late_reverb_level_db": self.profile.late_reverb_level_db,
                "late_rt60_s": self.profile.late_rt60_s,
                "late_length_s": 0.50,
                "late_start_s": late_start_s,
                "late_highpass_hz": 180.0,
                "late_lowpass_hz": 8_000.0,
                "center_room_send_db": self.profile.center_room_send_db,
                "reference_direct_ratio": BALANCED_REFERENCE_DIRECT_RATIO,
            }
        elif self.room_enabled:
            room_diagnostics = {
                "name": "small-dry",
                "early_taps": 6,
                "late_rt60_s": 0.30,
                "late_length_s": 0.50,
                "late_start_s": 0.03,
            }
        else:
            room_diagnostics = None
        if (
            room_diagnostics is not None
            and self.profile.reflection_normalization_mode != "legacy_per_object"
        ):
            room_diagnostics["reflection_normalization_mode"] = (
                self.profile.reflection_normalization_mode
            )
        diagnostics: dict[str, object] = {
            "engine": "spatial-v2-sofa",
            "sofa": str(database.path),
            "head_motion": self.listener_trajectory is not None or self.micro_motion is not None,
            "micro_motion": self.micro_motion is not None,
            "block_size": self.block_size,
            "room": self.room_enabled,
            "room_profile": room_diagnostics,
            "max_sofa_coverage_error_deg": max_coverage_error,
            "sofa_front_reference_gain": database.front_reference_gain,
            "hrtf_timbre_compensation": (
                "front-common-field"
                if compensation_active
                else "off"
            ),
            "hrtf_compensation_phase": (
                "minimum"
                if compensation_active
                else "disabled"
            ),
            "hrtf_compensation_max_boost_db": (
                database.timbre_compensation_max_boost_db
                * self.profile.hrtf_compensation_strength
            ),
            "hrtf_compensation_max_cut_db": (
                database.timbre_compensation_max_cut_db
                * self.profile.hrtf_compensation_strength
            ),
            "mastered_loudness_gain_db": mastered_loudness_gain_db,
            "mastered_loudness_peak_limited": mastered_loudness_peak_limited,
            "limiter_gain": limiter_gain,
            "limiter": limiter_report,
            "foa_convention": "AmbiX ACN/SN3D (W,Y,Z,X)",
        }
        if self.profile.mastered_loudness_mode != "legacy_input_rms":
            diagnostics["mastered_loudness_mode"] = self.profile.mastered_loudness_mode
        if self.profile.hrtf_compensation_strength != 1.0:
            diagnostics["hrtf_compensation_strength"] = (
                self.profile.hrtf_compensation_strength
            )
        return RenderResult(limited, scene.sample_rate, diagnostics)
