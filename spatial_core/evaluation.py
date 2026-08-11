"""Subjective A/B promotion gate for replacing the frozen legacy renderer."""

from __future__ import annotations

from collections.abc import Mapping, Sequence


TIMBRE_UTILITY_DIRECTIONS = {
    "vocal_clarity": 1.0,
    "bass_weight": 1.0,
    "bass_tightness": 1.0,
    "harshness": -1.0,
    "mud": -1.0,
}

CLARITY_GATE_THRESHOLDS = {
    "maximum_mid_side_balance_delta_db": 1.0,
    "minimum_crest_delta_db": -1.0,
    "minimum_fast_change_delta_db": -0.5,
    "maximum_absolute_band_delta_db": 2.0,
}
CLARITY_GATE_BANDS = ("sub", "bass", "low_mid", "presence")


def evaluate_clarity_gate(metrics: Mapping[str, object]) -> dict[str, object]:
    """Classify objective timbre/clarity deltas for one rendered candidate."""

    band_deltas = metrics.get("band_delta_db")
    if not isinstance(band_deltas, Mapping):
        raise ValueError("clarity metrics require band_delta_db")
    failures: list[str] = []
    mid_side_delta = float(metrics["mid_side_balance_delta_db"])
    crest_delta = float(metrics["crest_delta_db"])
    fast_change_delta = float(metrics["fast_change_delta_db"])
    if abs(mid_side_delta) > CLARITY_GATE_THRESHOLDS["maximum_mid_side_balance_delta_db"]:
        failures.append("mid_side_balance_delta_db")
    if crest_delta < CLARITY_GATE_THRESHOLDS["minimum_crest_delta_db"]:
        failures.append("crest_delta_db")
    if fast_change_delta < CLARITY_GATE_THRESHOLDS["minimum_fast_change_delta_db"]:
        failures.append("fast_change_delta_db")
    for band in CLARITY_GATE_BANDS:
        if abs(float(band_deltas[band])) > CLARITY_GATE_THRESHOLDS["maximum_absolute_band_delta_db"]:
            failures.append(f"band_delta_db.{band}")
    return {
        "pass": not failures,
        "failures": failures,
        "thresholds": dict(CLARITY_GATE_THRESHOLDS),
    }


def evaluate_promotion_gate(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Evaluate the S1 listening gate across paired legacy/V2 score records."""

    track_ids: list[str] = []
    for record in records:
        identifier = record.get("track_id", record.get("song_id", record.get("input")))
        if identifier is None or not str(identifier).strip():
            raise ValueError("each promotion record requires track_id, song_id, or input")
        track_ids.append(str(identifier))
    unique_track_count = len(set(track_ids))
    if unique_track_count != len(track_ids):
        raise ValueError("promotion records must contain one paired record per unique track")
    if unique_track_count < 3:
        return {
            "promote": False,
            "track_count": unique_track_count,
            "record_count": len(records),
            "reason": "at least three unique paired tracks are required",
        }
    externalization_deltas: list[float] = []
    depth_deltas: list[float] = []
    worst_timbre_regression = 0.0
    for record in records:
        legacy = record.get("legacy")
        candidate = record.get("spatial_v2")
        if not isinstance(legacy, Mapping) or not isinstance(candidate, Mapping):
            raise ValueError("each promotion record requires legacy and spatial_v2 score objects")
        externalization_deltas.append(float(candidate["externalization"]) - float(legacy["externalization"]))
        depth_deltas.append(float(candidate["depth"]) - float(legacy["depth"]))
        for key, direction in TIMBRE_UTILITY_DIRECTIONS.items():
            if key in legacy and key in candidate:
                utility_delta = direction * (float(candidate[key]) - float(legacy[key]))
                worst_timbre_regression = max(worst_timbre_regression, -utility_delta)
    externalization_delta = sum(externalization_deltas) / len(externalization_deltas)
    depth_delta = sum(depth_deltas) / len(depth_deltas)
    promote = (
        externalization_delta >= 0.5
        and depth_delta >= 0.5
        and worst_timbre_regression <= 0.5
    )
    return {
        "promote": promote,
        "track_count": unique_track_count,
        "record_count": len(records),
        "mean_externalization_delta": externalization_delta,
        "mean_depth_delta": depth_delta,
        "worst_timbre_regression": worst_timbre_regression,
        "thresholds": {
            "minimum_tracks": 3,
            "minimum_externalization_delta": 0.5,
            "minimum_depth_delta": 0.5,
            "maximum_timbre_regression": 0.5,
        },
    }
