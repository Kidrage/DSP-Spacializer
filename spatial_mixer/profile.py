"""Strict, portable universal seven-zone mixer profile."""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields, replace
from hashlib import sha256
from math import isfinite, log10
from pathlib import Path
from typing import Mapping
import json


PROFILE_FORMAT = "spatial_mixer_profile"
PROFILE_VERSION = "1.0"
RENDERER_REVISION = "spatial-core-v2.1"
ZONE_NAMES = (
    "bass",
    "center_anchor",
    "front_L_residual",
    "front_R_residual",
    "side_width",
    "rear_ambience",
    "high_air",
)
OBJECT_ZONE_NAMES = ZONE_NAMES[:4]
FIELD_ZONE_NAMES = ZONE_NAMES[4:]
TOP_LEVEL_FIELDS = {"format", "version", "renderer_revision", "zones", "room", "extraction"}


def _number(name: str, value: object, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not isfinite(result) or not minimum <= result <= maximum:
        raise ValueError(f"{name} must be within [{minimum}, {maximum}]")
    return result


def _strict_dataclass_values(
    name: str,
    payload: object,
    model: type,
) -> dict[str, object]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{name} must be a JSON object")
    allowed = {item.name for item in fields(model)}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"unknown {name} field: {unknown[0]}")
    missing = sorted(allowed - set(payload))
    if missing:
        raise ValueError(f"missing {name} field: {missing[0]}")
    return dict(payload)


@dataclass(frozen=True)
class ObjectZone:
    gain_db: float = 0.0
    azimuth_deg: float = 0.0
    elevation_deg: float = 0.0
    distance_m: float = 1.60
    size: float = 0.05
    diffusion: float = 0.0
    direct_ratio: float = 0.78
    early_reflection_trim_db: float = 0.0
    late_reverb_trim_db: float = 0.0

    def __post_init__(self) -> None:
        _number("gain_db", self.gain_db, -24.0, 12.0)
        _number("azimuth_deg", self.azimuth_deg, -180.0, 180.0)
        _number("elevation_deg", self.elevation_deg, -90.0, 90.0)
        _number("distance_m", self.distance_m, 0.1, 10.0)
        _number("size", self.size, 0.0, 1.0)
        _number("diffusion", self.diffusion, 0.0, 1.0)
        _number("direct_ratio", self.direct_ratio, 0.0, 1.0)
        _number("early_reflection_trim_db", self.early_reflection_trim_db, -18.0, 12.0)
        _number("late_reverb_trim_db", self.late_reverb_trim_db, -18.0, 12.0)


@dataclass(frozen=True)
class FieldZone:
    gain_db: float
    azimuth_deg: float
    elevation_deg: float = 0.0

    def __post_init__(self) -> None:
        _number("gain_db", self.gain_db, -120.0, 6.0)
        _number("azimuth_deg", self.azimuth_deg, 0.0, 180.0)
        _number("elevation_deg", self.elevation_deg, -90.0, 90.0)

    @property
    def field_gain(self) -> float:
        return 10.0 ** (self.gain_db / 20.0)


@dataclass(frozen=True)
class RoomSettings:
    early_reflection_level_db: float = -21.0
    late_reverb_level_db: float = -27.0
    late_rt60_s: float = 0.35

    def __post_init__(self) -> None:
        _number("early_reflection_level_db", self.early_reflection_level_db, -40.0, -10.0)
        _number("late_reverb_level_db", self.late_reverb_level_db, -40.0, -12.0)
        _number("late_rt60_s", self.late_rt60_s, 0.15, 1.20)


@dataclass(frozen=True)
class ExtractionSettings:
    bass_low_hz: float = 80.0
    bass_high_hz: float = 160.0
    center_anchor: float = 0.80
    center_focus_low_hz: float = 900.0
    center_focus_high_hz: float = 2_500.0
    center_focus_floor: float = 0.25
    front_side_weight_low: float = 0.90
    front_side_weight_high: float = 0.75
    rear_strength: float = 0.55
    rear_low_hz: float = 1_500.0
    rear_high_hz: float = 3_000.0
    air_low_hz: float = 5_500.0
    air_high_hz: float = 9_000.0

    def __post_init__(self) -> None:
        _number("bass_low_hz", self.bass_low_hz, 30.0, 250.0)
        _number("bass_high_hz", self.bass_high_hz, 60.0, 400.0)
        _number("center_anchor", self.center_anchor, 0.0, 1.0)
        _number("center_focus_low_hz", self.center_focus_low_hz, 200.0, 3_000.0)
        _number("center_focus_high_hz", self.center_focus_high_hz, 800.0, 8_000.0)
        _number("center_focus_floor", self.center_focus_floor, 0.0, 1.0)
        _number("front_side_weight_low", self.front_side_weight_low, 0.0, 1.0)
        _number("front_side_weight_high", self.front_side_weight_high, 0.0, 1.0)
        _number("rear_strength", self.rear_strength, 0.0, 1.0)
        _number("rear_low_hz", self.rear_low_hz, 300.0, 6_000.0)
        _number("rear_high_hz", self.rear_high_hz, 800.0, 10_000.0)
        _number("air_low_hz", self.air_low_hz, 2_000.0, 12_000.0)
        _number("air_high_hz", self.air_high_hz, 4_000.0, 20_000.0)
        if self.bass_low_hz >= self.bass_high_hz:
            raise ValueError("bass_low_hz must be below bass_high_hz")
        if self.center_focus_low_hz >= self.center_focus_high_hz:
            raise ValueError("center_focus_low_hz must be below center_focus_high_hz")
        if self.rear_low_hz >= self.rear_high_hz:
            raise ValueError("rear_low_hz must be below rear_high_hz")
        if self.air_low_hz >= self.air_high_hz:
            raise ValueError("air_low_hz must be below air_high_hz")
        if self.front_side_weight_low < self.front_side_weight_high:
            raise ValueError("front_side_weight_low must be at least front_side_weight_high")


@dataclass(frozen=True)
class MixerProfile:
    zones: dict[str, ObjectZone | FieldZone]
    room: RoomSettings = RoomSettings()
    extraction: ExtractionSettings = ExtractionSettings()
    renderer_revision: str = RENDERER_REVISION

    def __post_init__(self) -> None:
        if len(self.zones) != len(ZONE_NAMES) or set(self.zones) != set(ZONE_NAMES):
            raise ValueError("mixer profile zones must contain the canonical seven zones")
        object.__setattr__(self, "zones", {name: self.zones[name] for name in ZONE_NAMES})
        for name in OBJECT_ZONE_NAMES:
            if not isinstance(self.zones[name], ObjectZone):
                raise ValueError(f"{name} must be an object zone")
        for name in FIELD_ZONE_NAMES:
            if not isinstance(self.zones[name], FieldZone):
                raise ValueError(f"{name} must be an FOA field zone")
        if self.renderer_revision != RENDERER_REVISION:
            raise ValueError(f"renderer_revision must be {RENDERER_REVISION}")

    @classmethod
    def default(cls) -> "MixerProfile":
        return cls(
            zones={
                "bass": ObjectZone(size=0.05),
                "center_anchor": ObjectZone(size=0.0),
                "front_L_residual": ObjectZone(azimuth_deg=35.0, size=0.05),
                "front_R_residual": ObjectZone(azimuth_deg=-35.0, size=0.05),
                "side_width": FieldZone(gain_db=-12.041199826559248, azimuth_deg=75.0),
                "rear_ambience": FieldZone(gain_db=-14.89454989793388, azimuth_deg=135.0),
                "high_air": FieldZone(
                    gain_db=-18.416375079047505,
                    azimuth_deg=110.0,
                    elevation_deg=35.0,
                ),
            }
        )

    def to_payload(self) -> dict[str, object]:
        zones: dict[str, object] = {}
        for name, zone in self.zones.items():
            zones[name] = {
                "kind": "object" if isinstance(zone, ObjectZone) else "foa_field",
                **asdict(zone),
            }
        return {
            "format": PROFILE_FORMAT,
            "version": PROFILE_VERSION,
            "renderer_revision": self.renderer_revision,
            "zones": zones,
            "room": asdict(self.room),
            "extraction": asdict(self.extraction),
        }

    @property
    def profile_hash(self) -> str:
        canonical = json.dumps(
            self.to_payload(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        return sha256(canonical.encode("utf-8")).hexdigest()


def profile_from_payload(payload: object) -> MixerProfile:
    if not isinstance(payload, Mapping):
        raise ValueError("mixer profile must be a JSON object")
    unknown = sorted(set(payload) - TOP_LEVEL_FIELDS)
    if unknown:
        raise ValueError(f"unknown mixer profile field: {unknown[0]}")
    missing = sorted(TOP_LEVEL_FIELDS - set(payload))
    if missing:
        raise ValueError(f"missing mixer profile field: {missing[0]}")
    if payload.get("format") != PROFILE_FORMAT or payload.get("version") != PROFILE_VERSION:
        raise ValueError("mixer profile must use spatial_mixer_profile version 1.0")
    if payload.get("renderer_revision") != RENDERER_REVISION:
        raise ValueError(f"renderer_revision must be {RENDERER_REVISION}")
    raw_zones = payload.get("zones")
    if (
        not isinstance(raw_zones, Mapping)
        or len(raw_zones) != len(ZONE_NAMES)
        or set(raw_zones) != set(ZONE_NAMES)
    ):
        raise ValueError("mixer profile zones must contain the canonical seven zones")
    zones: dict[str, ObjectZone | FieldZone] = {}
    for name in ZONE_NAMES:
        raw_zone = raw_zones[name]
        if not isinstance(raw_zone, Mapping):
            raise ValueError(f"zone {name} must be a JSON object")
        kind = raw_zone.get("kind")
        values = {key: value for key, value in raw_zone.items() if key != "kind"}
        if name in OBJECT_ZONE_NAMES:
            if kind != "object":
                raise ValueError(f"{name} must use kind object")
            zones[name] = ObjectZone(**_strict_dataclass_values(name, values, ObjectZone))
        else:
            if kind != "foa_field":
                raise ValueError(f"{name} must use kind foa_field")
            zones[name] = FieldZone(**_strict_dataclass_values(name, values, FieldZone))
    room = RoomSettings(**_strict_dataclass_values("room", payload["room"], RoomSettings))
    extraction = ExtractionSettings(
        **_strict_dataclass_values("extraction", payload["extraction"], ExtractionSettings)
    )
    return MixerProfile(
        zones=zones,
        room=room,
        extraction=extraction,
        renderer_revision=str(payload["renderer_revision"]),
    )


def load_mixer_profile(path: str | Path) -> MixerProfile:
    profile_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(profile_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read mixer profile: {profile_path}") from exc
    return profile_from_payload(payload)


def save_mixer_profile(profile: MixerProfile, path: str | Path) -> Path:
    profile_path = Path(path).expanduser().resolve()
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile_path.write_text(
        json.dumps(profile.to_payload(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return profile_path


def mixer_profile_from_spatial_core(compact_profile) -> MixerProfile:
    """Convert the legacy compact V2.1 controls into the strict seven-zone schema."""

    from spatial_core.profile import SpatialCoreProfile

    if not isinstance(compact_profile, SpatialCoreProfile):
        raise TypeError("compact_profile must be a SpatialCoreProfile")
    profile = MixerProfile.default()
    zones = dict(profile.zones)
    for name in OBJECT_ZONE_NAMES:
        zone = zones[name]
        assert isinstance(zone, ObjectZone)
        zones[name] = replace(
            zone,
            distance_m=compact_profile.front_distance_m,
            direct_ratio=compact_profile.direct_ratio,
        )
    zones["front_L_residual"] = replace(
        zones["front_L_residual"], azimuth_deg=compact_profile.front_width_deg
    )
    zones["front_R_residual"] = replace(
        zones["front_R_residual"], azimuth_deg=-compact_profile.front_width_deg
    )

    def gain_db(value: float) -> float:
        return -120.0 if value <= 0.0 else 20.0 * log10(value)

    zones["side_width"] = replace(
        zones["side_width"], gain_db=gain_db(compact_profile.bed_width_gain)
    )
    zones["rear_ambience"] = replace(
        zones["rear_ambience"], gain_db=gain_db(compact_profile.bed_rear_gain)
    )
    zones["high_air"] = replace(
        zones["high_air"], gain_db=gain_db(compact_profile.bed_air_gain)
    )
    return MixerProfile(
        zones=zones,
        room=RoomSettings(
            early_reflection_level_db=compact_profile.early_reflection_level_db,
            late_reverb_level_db=compact_profile.late_reverb_level_db,
            late_rt60_s=compact_profile.late_rt60_s,
        ),
        extraction=replace(profile.extraction, center_anchor=compact_profile.center_anchor),
    )
