"""File-oriented workflow for the opt-in Spatial Core V2 CLI."""

from __future__ import annotations

from math import gcd
from pathlib import Path
import json

import numpy as np
from scipy.signal import resample_poly
import soundfile as sf

from .adapters import CtcOutputAdapter
from .binaural import SofaBinauralRenderer
from .builder import build_scene
from .motion import ListenerTrajectory
from .profile import SpatialCoreProfile, load_spatial_profile
from .scene import load_scene, save_scene
from .speaker import DEFAULT_QUAD_LAYOUT, QuadSpeakerRenderer, Speaker
from spatial_mixer import load_mixer_profile
from spatial_mixer.rendering import build_mixer_scene


def _read_stereo(path: str | Path, target_rate: int) -> tuple[np.ndarray, int]:
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"input audio file does not exist: {source}")
    audio, source_rate = sf.read(source, always_2d=True, dtype="float32")
    if audio.shape[1] != 2:
        raise ValueError("Spatial Core V2 DSP bus builder requires stereo input")
    if int(source_rate) != int(target_rate):
        divisor = gcd(int(source_rate), int(target_rate))
        audio = resample_poly(audio, target_rate // divisor, int(source_rate) // divisor, axis=0)
    return np.asarray(audio, dtype=np.float32), int(target_rate)


def load_speaker_layout(path: str | Path | None) -> tuple[Speaker, ...]:
    if path is None:
        return DEFAULT_QUAD_LAYOUT
    layout_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(layout_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read speaker layout: {layout_path}") from exc
    if payload.get("format") != "spatial_core_speaker_layout" or payload.get("version") != "1.0":
        raise ValueError("speaker layout must use spatial_core_speaker_layout version 1.0")
    speakers = tuple(
        Speaker(str(item.get("name", "")), float(item["azimuth"]))
        for item in payload.get("speakers", [])
    )
    if len(speakers) != 4 or len({item.name for item in speakers}) != 4:
        raise ValueError("speaker layout must contain four uniquely named speakers")
    return speakers


def _write_audio(path: Path, audio: np.ndarray, sample_rate: int) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, np.asarray(audio, dtype=np.float32), sample_rate, subtype="FLOAT")
    return str(path)


def render_spatial_v2(
    *,
    input_path: str | Path | None,
    scene_manifest: str | Path | None,
    output_dir: str | Path,
    output_mode: str,
    target_sample_rate: int,
    sofa_path: str | Path | None,
    export_scene_path: str | Path | None = None,
    listener_trajectory_path: str | Path | None = None,
    micro_motion: bool = False,
    motion_seed: int = 0,
    room_profile: str = "small-dry",
    spatial_profile_path: str | Path | None = None,
    mixer_profile_path: str | Path | None = None,
    speaker_layout_path: str | Path | None = None,
    export_ctc: bool = False,
    ctc_options: dict[str, object] | None = None,
) -> dict[str, object]:
    """Render one stereo file or public scene manifest with V2 backends."""

    if (input_path is None) == (scene_manifest is None):
        raise ValueError("provide exactly one stereo input or --scene-manifest")
    if output_mode not in {"4ch", "binaural", "both"}:
        raise ValueError("output_mode must be '4ch', 'binaural', or 'both'")
    needs_binaural = output_mode in {"binaural", "both"} or export_ctc
    if needs_binaural and sofa_path is None:
        raise ValueError("Spatial Core V2 binaural and CTC output require --sofa")
    if room_profile not in {"small-dry", "balanced-depth", "off"}:
        raise ValueError("room_profile must be 'small-dry', 'balanced-depth', or 'off'")
    if spatial_profile_path is not None and mixer_profile_path is not None:
        raise ValueError("--spatial-profile and --mixer-profile are mutually exclusive")
    if scene_manifest is not None and mixer_profile_path is not None:
        raise ValueError("--mixer-profile can only be used with stereo input")
    profile = (
        load_spatial_profile(spatial_profile_path)
        if spatial_profile_path is not None
        else SpatialCoreProfile()
    )
    mixer_profile = (
        load_mixer_profile(mixer_profile_path)
        if mixer_profile_path is not None
        else None
    )
    renderer_profile = profile
    if mixer_profile is not None:
        renderer_profile = SpatialCoreProfile(
            early_reflection_level_db=mixer_profile.room.early_reflection_level_db,
            late_reverb_level_db=mixer_profile.room.late_reverb_level_db,
            late_rt60_s=mixer_profile.room.late_rt60_s,
        )

    if scene_manifest is not None:
        scene = load_scene(scene_manifest)
        stem = Path(scene_manifest).stem
        source_description = str(Path(scene_manifest).expanduser().resolve())
    else:
        stereo, sample_rate = _read_stereo(input_path, int(target_sample_rate))
        scene = (
            build_mixer_scene(stereo, mixer_profile, sample_rate=sample_rate)
            if mixer_profile is not None
            else build_scene(stereo, profile=profile, sample_rate=sample_rate)
        )
        stem = Path(input_path).stem
        source_description = str(Path(input_path).expanduser().resolve())
    out_dir = Path(output_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    if export_scene_path is not None:
        save_scene(scene, export_scene_path)

    outputs: dict[str, str] = {}
    diagnostics: dict[str, object] = {}
    binaural_renderer = None
    if needs_binaural:
        trajectory = (
            ListenerTrajectory.load(listener_trajectory_path)
            if listener_trajectory_path is not None
            else None
        )
        binaural_renderer = SofaBinauralRenderer(
            sofa_path,
            listener_trajectory=trajectory,
            micro_motion=micro_motion,
            motion_seed=motion_seed,
            room_enabled=room_profile != "off",
            room_profile=room_profile,
            profile=renderer_profile,
            block_size=512 if trajectory is not None or micro_motion else 8_192,
        )
    if output_mode in {"binaural", "both"}:
        result = binaural_renderer.render(scene)
        outputs["binaural"] = _write_audio(
            out_dir / f"{stem}_spatial_v2_binaural.wav", result.audio, result.sample_rate
        )
        diagnostics["binaural"] = result.diagnostics
    if output_mode in {"4ch", "both"}:
        result = QuadSpeakerRenderer(load_speaker_layout(speaker_layout_path)).render(scene)
        outputs["quad"] = _write_audio(
            out_dir / f"{stem}_spatial_v2_quad.wav", result.audio, result.sample_rate
        )
        diagnostics["quad"] = result.diagnostics
    if export_ctc:
        result = CtcOutputAdapter(binaural_renderer, **(ctc_options or {})).render(scene)
        outputs["ctc_4ch"] = _write_audio(
            out_dir / f"{stem}_spatial_v2_ctc_4ch.wav", result.audio, result.sample_rate
        )
        diagnostics["ctc_4ch"] = result.diagnostics
    return {
        "engine": "spatial-v2",
        "input": source_description,
        "scene_format": "spatial_core_scene/2.0",
        "profile_format": (
            "spatial_mixer_profile/1.0"
            if mixer_profile is not None
            else "spatial_core_profile/1.0"
        ),
        "sample_rate": scene.sample_rate,
        "frames": scene.num_frames,
        "outputs": outputs,
        "diagnostics": diagnostics,
    }
