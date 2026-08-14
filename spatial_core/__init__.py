"""Object/soundfield based Spatial Core V2 public API."""

from .adapters import CtcOutputAdapter
from .builder import build_scene
from .binaural import SofaBinauralRenderer, default_direct_ratio, distance_gain_db
from .evaluation import evaluate_clarity_gate, evaluate_promotion_gate, measure_clarity_metrics
from .foa import decode_foa_projection, encode_mono_foa, foa_direction_vector
from .hrtf import InterpolatedHrir, SofaHrirDatabase
from .motion import ListenerPose, ListenerTrajectory, MicroMotion
from .package import ScenePackageError, ScenePackageInfo, validate_scene_package
from .profile import SpatialCoreProfile, load_spatial_profile
from .rendering import RenderResult, SceneRenderer
from .room import EarlyReflection, balanced_depth_reflections
from .speaker import DEFAULT_QUAD_LAYOUT, QuadSpeakerRenderer, Speaker, vbap_gains
from .scene import FoaBed, SpatialObject, SpatialScene, load_scene, save_scene
from .zones import SpatialZones, extract_spatial_zones

__all__ = [
    "CtcOutputAdapter",
    "DEFAULT_QUAD_LAYOUT",
    "EarlyReflection",
    "FoaBed",
    "InterpolatedHrir",
    "ListenerPose",
    "ListenerTrajectory",
    "MicroMotion",
    "QuadSpeakerRenderer",
    "RenderResult",
    "SceneRenderer",
    "ScenePackageError",
    "ScenePackageInfo",
    "SofaBinauralRenderer",
    "SofaHrirDatabase",
    "Speaker",
    "SpatialObject",
    "SpatialCoreProfile",
    "SpatialScene",
    "SpatialZones",
    "build_scene",
    "balanced_depth_reflections",
    "decode_foa_projection",
    "default_direct_ratio",
    "distance_gain_db",
    "encode_mono_foa",
    "evaluate_clarity_gate",
    "evaluate_promotion_gate",
    "extract_spatial_zones",
    "foa_direction_vector",
    "load_scene",
    "load_spatial_profile",
    "measure_clarity_metrics",
    "save_scene",
    "validate_scene_package",
    "vbap_gains",
]
