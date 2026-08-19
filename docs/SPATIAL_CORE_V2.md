# Spatial Core V2.1: clarity and depth

Spatial Core V2 is the opt-in object/soundfield architecture. The legacy V3.2
fixed-channel renderer remains the default and the listening baseline.

```text
stereo or scene manifest
        |
lossless M/S seven-zone scene + AmbiX FOA bed
        |
        +-- measured-SOFA binaural renderer -- optional legacy CTC adapter
        |
        +-- FOA + 2D VBAP quad renderer
```

## Scope and invariants

- V2.1 objects are static, mono, omnidirectional sources.
- Stereo input uses a 2048-sample Hann STFT with a 512-sample hop. A
  coherence mask extracts the center anchor; bass and low-body support remain
  centered, while panned content stays out of the anchor.
- The seven zones are `bass`, `center_anchor`, `front_L_residual`,
  `front_R_residual`, `side_width`, `rear_ambience`, and `high_air`. Their dry
  representation reconstructs the input below -80 dB error. Side, rear, and
  air use complementary masks instead of overlapping filtered copies.
- The bed is first-order Ambisonics in AmbiX ACN/SN3D order `W,Y,Z,X`.
- DSP buses are used as scene material; there is no AI source separation.
- Binaural rendering requires a real `SimpleFreeFieldHRIR` SOFA file. Missing,
  malformed, two-receiver-incompatible, or badly uncovered data fails loudly.
- No HRTF data is bundled and there is no procedural HRTF fallback.
- Distance is bounded to 0.1–10 m. Both backends apply gain and air absorption;
  the binaural backend additionally applies DRR, early reflections, and the
  late field.
- Stereo-built scenes retain the input program RMS as scene metadata. In the
  binaural backend, one bounded global gain approaches that mastered reference
  after object and bed summation, stopping at available 0.98 peak headroom to
  preserve dynamics. It may therefore remain below source RMS. No per-object
  or FOA-bed distance makeup is used, so their intended balance is preserved
  while distance remains audible through DRR, reflection timing, direction,
  and air absorption. The quad backend does not apply this headphone-only gain.
- Object size spreads amplitude-normalized coherent rays, so changing size does
  not raise the source level. Diffusion uses an equal-power positional/diffuse
  split.
- The binaural output removes the broad frontal common-field coloration of the
  measured HRIR with one bounded, smoothed minimum-phase filter shared by both ears. This
  preserves directional interaural differences while preventing the listener
  dataset from imposing its raw bass roll-off or pinna peak on the mix.
- A linked attack/release limiter handles local overloads without scaling the
  entire track from its single largest sample.
- Speaker elevation is projected to the horizontal 4.0 layout and reported.

## CLI

Install all dependencies:

```bash
python -m pip install -r requirements.txt
```

Render headphones directly from stereo DSP buses:

```bash
python run_spatializer.py input_audio/test_input.wav \
  --engine spatial-v2 \
  --sofa /absolute/path/listener.sofa \
  --output-mode binaural
```

Render the clarity/depth candidate with the compact profile and geometry room:

```bash
python run_spatializer.py input_audio/test_input.wav \
  --engine spatial-v2 \
  --sofa /absolute/path/listener.sofa \
  --spatial-profile profiles/spatial_core_balanced_depth.json \
  --room-profile balanced-depth \
  --output-mode binaural
```

Export the portable scene and render both backends:

```bash
python run_spatializer.py input_audio/test_input.wav \
  --engine spatial-v2 \
  --sofa /absolute/path/listener.sofa \
  --output-mode both \
  --export-scene outputs/test_scene.json
```

Render an existing scene, apply listener motion, and also export centered CTC:

```bash
python run_spatializer.py \
  --engine spatial-v2 \
  --scene-manifest outputs/test_scene.json \
  --sofa /absolute/path/listener.sofa \
  --listener-trajectory examples/listener_trajectory_example.json \
  --export-binaural-ctc-4ch
```

`--micro-motion --motion-seed 7` adds bounded simulated yaw (±5°) and pitch
(±3°). It is disabled by default. `--room-profile small-dry` preserves the S1
room; `off` disables room rendering. `balanced-depth` uses first-order image
sources in a fixed 6 x 5 x 3 m room, rejects reflections earlier than 8 ms,
starts the late field 10 ms after the last early reflection, and limits the
late field to 180 Hz–8 kHz. Center-anchor room send is 3 dB below other front
objects. `direct_ratio` scales both early and late wet sends around the default
0.78 reference. Sources outside the modeled room fail validation.
The individual compact-profile ranges are not a guarantee that every distance,
azimuth, and elevation combination fits this fixed room; incompatible
combinations fail before HRIR convolution.
`--speaker-layout` accepts the public layout format shown in
`examples/quad_layout_example.json`.

## Compact spatial profile

`spatial_core_profile` version 1.0 exposes only the parameters needed for the
static clarity/depth candidate:

| Parameter | Default | Range |
|---|---:|---:|
| `center_anchor` | 0.80 | 0–1 |
| `front_distance_m` | 1.60 | 0.5–4.0 |
| `front_width_deg` | 35 | 15–75 |
| `bed_width_gain` | 0.25 | 0–1 |
| `bed_rear_gain` | 0.18 | 0–1 |
| `bed_air_gain` | 0.12 | 0–1 |
| `direct_ratio` | 0.78 | 0.30–0.95 |
| `early_reflection_level_db` | -21 | -40 to -10 |
| `late_reverb_level_db` | -27 | -40 to -12 |
| `late_rt60_s` | 0.35 | 0.15–1.20 |
| `hrtf_compensation_mode` | `legacy_front_common` | `legacy_front_common`, `off` |
| `hrtf_compensation_strength` | 1.0 | 0–1 |
| `mastered_loudness_mode` | `legacy_input_rms` | `legacy_input_rms`, `fixed_scene_gain`, `level_matched_eval` |
| `center_room_send_db` | -3 | -12 to +6 |
| `reflection_normalization_mode` | `legacy_per_object` | `legacy_per_object`, `physical_path_gain` |
| `direct_ratio_mode` | `manual` | `manual`, `distance_curve` |

Unknown top-level or parameter keys, invalid mode names, non-numeric continuous
values, and out-of-range values fail before rendering. These optional 1.0 fields
are a backward-compatible extension: old profile files load and serialize as
before. The legacy values above preserve the previous Spatial Core V2/V2.1
output. The non-legacy controls are opt-in FEX experiments;
`level_matched_eval` is reserved for the FEX-1 evaluation exporter and
`distance_curve` is reserved for frozen FEX-2, so both fail at renderer
construction in FEX-0. Examples are
`profiles/spatial_core_balanced_depth.json` and
`profiles/spatial_core_frontal_externalization_fex0.json`.

## Scene interchange

`spatial_core_scene/2.0` is the current runtime render scene. It stores four
objects plus an already-combined FOA bed, so it is intentionally distinct from
the renderer-neutral seven-zone master defined by
[`spatial_scene_package/0.1`](SPATIAL_SCENE_PACKAGE_V0_1.md). The latter retains
side, rear, and air as independent audio assets and derives FOA at render time.

The `spatial_core_scene` 2.0 JSON manifest points to external WAV assets using
paths relative to the manifest. Object WAVs must be mono. The optional bed WAV
must contain exactly four `W,Y,Z,X` channels. Assets are resampled to the
declared scene rate, shorter assets are zero-padded, and missing/invalid assets
fail validation.

```json
{
  "format": "spatial_core_scene",
  "version": "2.0",
  "sample_rate": 48000,
  "foa_convention": "AmbiX ACN/SN3D (W,Y,Z,X)",
  "objects": [{
    "id": "lead",
    "role": "front",
    "audio": "scene_audio/lead.wav",
    "position": {"azimuth": 0, "elevation": 0, "distance": 1.2},
    "gain_db": 0,
    "size": 0.1,
    "diffusion": 0.05,
    "direct_ratio": null,
    "directivity": "omni"
  }],
  "foa_bed": {
    "audio": "scene_audio/foa_bed.wav",
    "channel_order": "W,Y,Z,X",
    "normalization": "SN3D"
  }
}
```

## SOFA and head motion

The loader consumes `Data.IR`, `Data.Delay`, source coordinates, and sampling
rate. It resamples to the scene rate. Exact direction hits preserve measured
HRIRs; other directions use inverse-angular three-neighbor interpolation after
onset and delay alignment. A nearest-direction error above 15° emits a
diagnostic warning; above 45° fails. The FOA bed is decoded to each ear by a
regularized first-order spherical-harmonic projection over the measured set.
After object and bed summation, the same minimum-phase frontal common-field
compensation is applied to both ears; its boost/cut limits and phase type are
included in render diagnostics. FEX-1 may opt into a fractional compensation
strength; the default 1.0 uses the legacy FIR unchanged, while intermediate
values scale the correction in decibels before minimum-phase FIR generation.

Trajectory files use `spatial_core_listener_trajectory` 1.0 with strictly increasing
time keyframes. Yaw/pitch/roll are interpolated with SLERP and endpoints hold.

## Promotion gate

Legacy remains default until at least three uniquely identified paired tracks
meet all criteria:

- every track passes its objective clarity gate;
- mean externalization improvement ≥ 0.5;
- mean depth improvement ≥ 0.5;
- no tracked timbre utility regresses by more than 0.5.

The optional feedback dimensions are `externalization`,
`distance_naturalness`, `front_back_accuracy`, and `head_motion_stability`.
Existing V1 feedback records remain valid.

Before subjective promotion, each candidate also runs the objective clarity
gate: absolute M/S-balance delta ≤ 1 dB, crest delta ≥ -1 dB, fast-change delta
≥ -0.5 dB, and absolute sub/bass/low-mid/presence deltas ≤ 2 dB. A failed
objective gate remains a listening candidate and is not promoted.
`evaluate_promotion_gate()` requires `objective_clarity_pass: true` on every
paired record; a missing or false value blocks promotion.
