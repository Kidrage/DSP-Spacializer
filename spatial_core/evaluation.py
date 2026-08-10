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


def evaluate_promotion_gate(records: Sequence[Mapping[str, object]]) -> dict[str, object]:
    """Evaluate the S1 listening gate across paired legacy/V2 score records."""

    if len(records) < 3:
        return {
            "promote": False,
            "track_count": len(records),
            "reason": "at least three paired tracks are required",
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
        "track_count": len(records),
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
