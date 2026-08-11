import numpy as np
import pytest

from spatial_core import SpatialObject, balanced_depth_reflections


def test_balanced_depth_uses_first_order_image_sources_after_8_ms():
    source = SpatialObject(
        "lead",
        "front",
        np.zeros(16, dtype=np.float32),
        azimuth_deg=0.0,
        elevation_deg=0.0,
        distance_m=1.6,
    )

    reflections = balanced_depth_reflections(source)

    assert {item.wall for item in reflections} == {"front", "back", "left", "right"}
    assert all(item.delay_ms >= 8.0 for item in reflections)
    assert [item.delay_ms for item in reflections] == sorted(
        item.delay_ms for item in reflections
    )
    assert reflections[0].delay_ms == pytest.approx(8.16, abs=0.05)
