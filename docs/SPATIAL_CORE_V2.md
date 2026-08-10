# Spatial Core V2 S1

Spatial Core V2 is the opt-in object/soundfield architecture. The legacy V3.2
fixed-channel renderer remains the default and the listening baseline.

```text
stereo or scene manifest
        |
DSP bus objects + AmbiX FOA bed
        |
        +-- measured-SOFA binaural renderer -- optional legacy CTC adapter
        |
        +-- FOA + 2D VBAP quad renderer
```

## Scope and invariants

- V2.0 objects are static, mono, omnidirectional sources.
- The bed is first-order Ambisonics in AmbiX ACN/SN3D order `W,Y,Z,X`.
- DSP buses are used as scene material; there is no AI source separation.
- Binaural rendering requires a real `SimpleFreeFieldHRIR` SOFA file. Missing,
  malformed, two-receiver-incompatible, or badly uncovered data fails loudly.
- No HRTF data is bundled and there is no procedural HRTF fallback.
- Distance is bounded to 0.1–10 m. Both backends apply gain and air absorption;
  the binaural backend additionally applies DRR, early reflections, and the
  late field.
- Object size spreads an L2-normalized ray set. Diffusion uses an equal-power
  positional/diffuse split.
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
(±3°). It is disabled by default. `--room-profile off` disables the fixed
small/dry early and late field. `--speaker-layout` accepts the public layout
format shown in `examples/quad_layout_example.json`.

## Scene interchange

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

Trajectory files use `spatial_core_listener_trajectory` 1.0 with strictly increasing
time keyframes. Yaw/pitch/roll are interpolated with SLERP and endpoints hold.

## Promotion gate

Legacy remains default until at least three uniquely identified paired tracks
meet all criteria:

- mean externalization improvement ≥ 0.5;
- mean depth improvement ≥ 0.5;
- no tracked timbre utility regresses by more than 0.5.

The optional feedback dimensions are `externalization`,
`distance_naturalness`, `front_back_accuracy`, and `head_motion_stability`.
Existing V1 feedback records remain valid.
