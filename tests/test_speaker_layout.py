import pytest

from speaker_layout import default_quad_4p0_layout, validate_speaker_layout


def test_default_quad_has_four_speakers_in_order():
    layout = default_quad_4p0_layout()
    assert len(layout["speakers"]) == 4
    assert [s["id"] for s in layout["speakers"]] == ["LF", "RF", "LB", "RB"]
    validate_speaker_layout(layout)


def test_default_quad_ids_are_unique():
    layout = default_quad_4p0_layout()
    ids = [s["id"] for s in layout["speakers"]]
    assert len(ids) == len(set(ids))


def test_invalid_radius_fails():
    layout = default_quad_4p0_layout()
    layout["speakers"][0]["radius"] = 0.0
    with pytest.raises(ValueError):
        validate_speaker_layout(layout)
