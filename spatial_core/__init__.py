"""Object/soundfield based Spatial Core V2 public API."""

from .adapters import CtcOutputAdapter
from .builder import build_scene
from .binaural import SofaBinauralRenderer, default_direct_ratio, distance_gain_db
from .foa import decode_foa_projection, encode_mono_foa, foa_direction_vector
from .hrtf import InterpolatedHrir, SofaHrirDatabase
from .motion import ListenerPose, ListenerTrajectory, MicroMotion
from .rendering import RenderResult, SceneRenderer
from .speaker import DEFAULT_QUAD_LAYOUT, QuadSpeakerRenderer, Speaker, vbap_gains
from .scene import FoaBed, SpatialObject, SpatialScene, load_scene, save_scene

__all__ = [
    "CtcOutputAdapter",
    "DEFAULT_QUAD_LAYOUT",
    "FoaBed",
    "InterpolatedHrir",
    "ListenerPose",
    "ListenerTrajectory",
    "MicroMotion",
    "QuadSpeakerRenderer",
    "RenderResult",
    "SceneRenderer",
    "SofaBinauralRenderer",
    "SofaHrirDatabase",
    "Speaker",
    "SpatialObject",
    "SpatialScene",
    "build_scene",
    "decode_foa_projection",
    "default_direct_ratio",
    "distance_gain_db",
    "encode_mono_foa",
    "foa_direction_vector",
    "load_scene",
    "save_scene",
    "vbap_gains",
]
