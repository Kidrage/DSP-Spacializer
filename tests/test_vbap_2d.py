import numpy as np

from renderers.vbap_2d import vbap_gains_for_layout
from speaker_layout import default_quad_4p0_layout


def _active_ids(gains):
    ids = ["LF", "RF", "LB", "RB"]
    return {sid for sid, gain in zip(ids, gains) if gain > 1e-5}


def _assert_equal_power(gains):
    assert np.isclose(np.sqrt(np.sum(gains * gains)), 1.0, atol=1e-5)


def test_front_active_pair_is_lf_rf():
    gains = vbap_gains_for_layout(0.0, default_quad_4p0_layout())
    assert _active_ids(gains) == {"LF", "RF"}
    _assert_equal_power(gains)


def test_rear_active_pair_wraparound_is_lb_rb():
    for azimuth in (180.0, -180.0):
        gains = vbap_gains_for_layout(azimuth, default_quad_4p0_layout())
        assert _active_ids(gains) == {"LB", "RB"}
        _assert_equal_power(gains)


def test_right_side_active_pair_is_rf_rb():
    gains = vbap_gains_for_layout(90.0, default_quad_4p0_layout())
    assert _active_ids(gains) == {"RF", "RB"}
    _assert_equal_power(gains)


def test_left_side_active_pair_is_lb_lf():
    gains = vbap_gains_for_layout(-90.0, default_quad_4p0_layout())
    assert _active_ids(gains) == {"LB", "LF"}
    _assert_equal_power(gains)


def test_exact_speaker_azimuths_are_single_speaker():
    cases = [(45.0, "RF"), (-45.0, "LF"), (135.0, "RB"), (-135.0, "LB")]
    ids = ["LF", "RF", "LB", "RB"]
    for azimuth, speaker_id in cases:
        gains = vbap_gains_for_layout(azimuth, default_quad_4p0_layout())
        assert ids[int(np.argmax(gains))] == speaker_id
        assert np.max(gains) == 1.0
        assert _active_ids(gains) == {speaker_id}
        _assert_equal_power(gains)
