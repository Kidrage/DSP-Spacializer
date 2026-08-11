import numpy as np

from spatial_core import extract_spatial_zones


def test_seven_spatial_zones_reconstruct_stereo_below_minus_80_db():
    sample_rate = 48_000
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    center = 0.12 * np.sin(2 * np.pi * 220 * time) + 0.05 * np.sin(
        2 * np.pi * 1_100 * time
    )
    side = 0.04 * np.sin(2 * np.pi * 3_300 * time) + 0.02 * np.sin(
        2 * np.pi * 8_000 * time
    )
    stereo = np.stack([center + side, center - side], axis=1).astype(np.float32)

    zones = extract_spatial_zones(stereo, sample_rate=sample_rate)
    reconstructed = zones.reconstruct_stereo()

    assert zones.names == (
        "bass",
        "center_anchor",
        "front_L_residual",
        "front_R_residual",
        "side_width",
        "rear_ambience",
        "high_air",
    )
    error_rms = np.sqrt(np.mean((reconstructed - stereo) ** 2))
    source_rms = np.sqrt(np.mean(stereo**2))
    error_db = 20.0 * np.log10(max(error_rms / source_rms, 1e-12))
    assert error_db < -80.0


def test_hard_panned_content_does_not_leak_into_center_anchor():
    sample_rate = 48_000
    time = np.arange(sample_rate // 2, dtype=np.float64) / sample_rate
    left = 0.1 * np.sin(2 * np.pi * 1_000 * time)
    stereo = np.stack([left, np.zeros_like(left)], axis=1).astype(np.float32)

    zones = extract_spatial_zones(stereo, sample_rate=sample_rate)

    center_rms = np.sqrt(np.mean(zones.center_anchor**2))
    source_rms = np.sqrt(np.mean(left**2))
    leakage_db = 20.0 * np.log10(max(center_rms / source_rms, 1e-12))
    assert leakage_db < -80.0


def test_center_anchor_keeps_low_body_but_leaves_presence_in_front_residuals():
    sample_rate = 48_000
    time = np.arange(sample_rate, dtype=np.float64) / sample_rate
    coherent = 0.05 * np.sin(2 * np.pi * 400 * time) + 0.05 * np.sin(
        2 * np.pi * 4_000 * time
    )
    stereo = np.stack([coherent, coherent], axis=1).astype(np.float32)

    zones = extract_spatial_zones(stereo, sample_rate=sample_rate)
    spectrum = np.abs(np.fft.rfft(zones.center_anchor))
    frequencies = np.fft.rfftfreq(zones.center_anchor.size, 1.0 / sample_rate)
    low_body = spectrum[np.argmin(np.abs(frequencies - 400.0))]
    presence = spectrum[np.argmin(np.abs(frequencies - 4_000.0))]

    assert presence < 0.3 * low_body
