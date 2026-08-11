"""Object/FOA-to-headphone renderer backed exclusively by measured SOFA HRIRs."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve
from scipy.spatial.transform import Rotation

from .foa import encode_mono_foa
from .hrtf import InterpolatedHrir, SofaHrirDatabase
from .motion import ListenerTrajectory, MicroMotion, relative_direction
from .rendering import RenderResult, linked_peak_limiter
from .scene import SpatialObject, SpatialScene


EARLY_DELAYS_MS = np.asarray([4.2, 6.7, 10.8, 16.5, 24.0, 33.0], dtype=float)
EARLY_LEVELS_DB = np.asarray([-22.0, -23.5, -25.0, -27.0, -29.0, -31.0], dtype=float)
EARLY_AZIMUTH_OFFSETS = np.asarray([-38.0, 42.0, 96.0, -112.0, 154.0, -166.0])
EARLY_ELEVATION_OFFSETS = np.asarray([0.0, 8.0, -6.0, 12.0, -10.0, 5.0])


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


def _apply_common_field_compensation(audio: np.ndarray, correction_ir: np.ndarray) -> np.ndarray:
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


def _late_reverb_foa(audio: np.ndarray, sample_rate: int) -> np.ndarray:
    """Create a deterministic small/dry late field (RT60 .30 s, 0.50 s)."""

    length = max(1, int(round(0.50 * sample_rate)))
    start = int(round(0.03 * sample_rate))
    time = np.arange(length, dtype=np.float64) / sample_rate
    envelope = 10.0 ** (-3.0 * time / 0.30)
    rng = np.random.default_rng(32)
    output = np.zeros((audio.size + length - 1, 4), dtype=np.float32)
    for channel in range(4):
        kernel = rng.standard_normal(length) * envelope
        kernel[: min(start, length)] = 0.0
        norm = np.linalg.norm(kernel)
        if norm > 0:
            kernel *= 0.08 / norm
        output[:, channel] = fftconvolve(audio, kernel, mode="full")
    return output


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
        block_size: int = 512,
    ):
        self.sofa_path = Path(sofa_path)
        self.listener_trajectory = listener_trajectory
        self.micro_motion = MicroMotion(motion_seed) if micro_motion else None
        self.room_enabled = bool(room_enabled)
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
        for item in scene.objects:
            signal = apply_air_absorption(item.audio, scene.sample_rate, item.distance_m)
            signal *= 10.0 ** ((item.gain_db + distance_gain_db(item.distance_m)) / 20.0)
            direct_ratio = item.direct_ratio
            if direct_ratio is None:
                direct_ratio = default_direct_ratio(item.distance_m)
            direct_gain = np.sqrt(direct_ratio) if self.room_enabled else 1.0
            room_gain = np.sqrt(max(0.0, 1.0 - direct_ratio)) if self.room_enabled else 0.0
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
                if room_gain > 0.0:
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
                        gain = room_gain * 10.0 ** (float(level_db) / 20.0)
                        self._add(output, reflected, start + delay, gain)
            if diffuse_gain > 0.0:
                send = signal * diffuse_gain
                # Each SN3D direction has basis energy 2. Two decorrelated
                # sends at gain .5 retain unit total power.
                diffuse_foa += encode_mono_foa(send, item.azimuth_deg + 90.0, 20.0, 0.5)
                delayed = np.pad(send[:-17] if send.size > 17 else np.zeros(0), (17, 0))
                diffuse_foa += encode_mono_foa(delayed, item.azimuth_deg - 115.0, -12.0, 0.5)
            if room_gain > 0.0:
                late_send += room_gain * signal
        if np.any(late_send):
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
        output = _apply_common_field_compensation(output, database.timbre_compensation_ir)
        limited, limiter_report = linked_peak_limiter(output, scene.sample_rate)
        limiter_gain = 10.0 ** (-float(limiter_report["max_gain_reduction_db"]) / 20.0)
        diagnostics: dict[str, object] = {
            "engine": "spatial-v2-sofa",
            "sofa": str(database.path),
            "head_motion": self.listener_trajectory is not None or self.micro_motion is not None,
            "micro_motion": self.micro_motion is not None,
            "room": self.room_enabled,
            "room_profile": (
                {"early_taps": 6, "late_rt60_s": 0.30, "late_length_s": 0.50, "late_start_s": 0.03}
                if self.room_enabled
                else None
            ),
            "max_sofa_coverage_error_deg": max_coverage_error,
            "sofa_front_reference_gain": database.front_reference_gain,
            "hrtf_timbre_compensation": "front-common-field",
            "hrtf_compensation_max_boost_db": database.timbre_compensation_max_boost_db,
            "hrtf_compensation_max_cut_db": database.timbre_compensation_max_cut_db,
            "limiter_gain": limiter_gain,
            "limiter": limiter_report,
            "foa_convention": "AmbiX ACN/SN3D (W,Y,Z,X)",
        }
        return RenderResult(limited, scene.sample_rate, diagnostics)
