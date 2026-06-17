# Streaming Stereo Spatializer

> **Branch notice — `Pseudo-Object` experimental branch**
>
> This README describes the `Pseudo-Object` branch, not the repository `main`
> branch.  `main` should be treated as the legacy fixed 4.0 channel-renderer
> line.  This branch keeps that legacy path working, but adds pseudo-object
> scene metadata export and modular pseudo-object decoders for layout-driven
> experiments.
>
> Pseudo objects here are **spatial-function objects** derived from DSP layers.
> They are not clean stems, not source-separated instruments, and not claims of
> real object audio.

## How This Branch Differs From `main`

| Area | `main` branch | `Pseudo-Object` branch |
| --- | --- | --- |
| Primary path | Stereo → DSP layers → fixed `renderer_4ch.py` | Same legacy path, plus pseudo-object scene path |
| Metadata | Diagnostics-focused JSON | Adds `pseudo_object_spatial_v1` scene metadata |
| Object audio | Not exported as object layers | Exports DSP layer material under `*_objects/` |
| Decoding | Fixed 4.0 renderer | DBAP fallback, 2D VBAP, and hybrid spread-VBAP renderers |
| CLI additions | Legacy output options | Adds `--export-pseudo-scene`, `--decode-pseudo-scene`, `--pseudo-scene-only`, `--pseudo-renderer` |
| Intended use | Stable 4.0 / binaural upmix | Experimental pseudo-object architecture and decoder research |

If you want the original stable fixed-channel behavior, use `main` or run this
branch without pseudo-object flags.  If you want pseudo-object scene export,
layout-driven decoding, or VBAP renderer experiments, use this `Pseudo-Object`
branch.

## Overview

This project implements a **non-AI streaming stereo spatializer** for a 4.0 speaker system. It converts stereo L/R audio into DSP spatial-function layers that are rendered to logical 4.0 output (left front, right front, left back, right back).

This is **not** AI-based source separation. The spatial layers are not clean stems but rather spatial-function buses used for rendering.

## Key Features

- Converts stereo L/R audio to 4.0 spatial output
- DSP spatial-function layers:
  - Bass Layer (low-frequency body)
  - Low Body Support (warmth/body support)
  - Front Core (center-correlated content)
  - Side Width (stereo difference)
  - Rear Ambience (diffuse, low-coherence)
  - High Air (high-frequency content)
- Multiple presets for different spatialization styles
- Energy matching to maintain consistent loudness
- Limiter to prevent clipping
- Diagnostic output for analysis
- Optional pseudo-object scene export and default quad 4.0 decoder


## Batch Spatial Diagnostics Sync

This `Pseudo-Object` branch also includes the Gitea-side batch diagnostics work merged from `feat: add batch spatial diagnostics`.  These tools are compatible with the legacy 4.0 path and with pseudo-object experiments:

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
python run_spatializer.py my_song.wav --out-dir outputs --diagnostics-only
python run_spatializer.py my_song.wav --out-dir outputs --write-quality-report
```

Related files:

- `batch_spatial_diagnostics.py`: batch metrics/summary/report generation.
- `spatial_quality_report.py`: Markdown quality report writer.
- `spatial_quality_thresholds.json`: global and preset-specific quality thresholds.

These diagnostics describe spatial safety and render quality; they do not change the definition of pseudo objects.  Pseudo objects remain DSP-derived spatial-function objects, not clean source-separated stems.

## Pseudo-Object Upmix Mode

DSP-Spacializer now has two compatible rendering paths:

1. **Legacy fixed 4.0 mode** — the original deterministic channel renderer in
   `renderer_4ch.py`.  It directly maps DSP spatial-function layers to
   `[LF, RF, LB, RB]` and remains the default behavior for `4ch`, `binaural`,
   and `both` output modes.
2. **Pseudo-object scene mode** — an additional metadata path that turns the
   same DSP layers into a `pseudo_object_spatial_v1` scene.  These pseudo
   objects are **spatial-function objects**, not real instrument objects and not
   source-separated clean stems.  Object audio files are layer material for a
   decoder, not final speaker feeds.

The first pseudo-object version emits six objects:

- `bass_anchor`
- `front_core`
- `side_width`
- `rear_ambience`
- `high_air`
- `low_body_support`

The scene stores coordinates, spread/depth/diffuseness, gain, constraints, and
decoder hints.  Current renderers target `default_quad_4p0`; future decoders can
reuse the same metadata for other horizontal speaker layouts.

Example output when pseudo-object export is enabled:

```text
spatializer_outputs_clean/
  Song_auto_acoustic_4ch.wav
  Song_auto_acoustic_binaural_4p0.wav
  Song_auto_acoustic_pseudo_scene.json
  Song_auto_acoustic_pseudo_quad_hybrid_4ch.wav
  Song_auto_acoustic_objects/
    bass_anchor.wav
    front_core.wav
    side_width.wav
    rear_ambience.wav
    high_air.wav
    low_body_support.wav
  Song_auto_acoustic_diagnostics.json
  batch_manifest.json
```

CLI examples:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --export-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode both --export-pseudo-scene --decode-pseudo-scene

python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --pseudo-scene-only
```

## Pseudo-Object Rendering Algorithms

Pseudo-object decoding is now routed through modular renderers under
`renderers/`.  These renderers consume scene metadata and speaker layout data;
they do not treat pseudo objects as clean stems or real isolated instruments.

- `dbap_quad_v1`: the first pseudo-object decoder, kept as a fallback.  It uses
  distance-based amplitude panning, so it is smooth and forgiving for diffuse
  layer material.
- `vbap_2d_v1`: horizontal 2D VBAP.  It chooses the adjacent speaker pair that
  encloses the object azimuth and equal-power normalizes the active pair.  This
  is sharper and more layout-driven, so it is better for point-like pseudo
  objects.
- `hybrid_vbap_v1`: recommended V2 mode.  It keeps `front_core` as a stereo bed,
  uses VBAP for sharper objects such as `bass_anchor`, and uses spread VBAP for
  diffuse/lateral beds such as `side_width`, `rear_ambience`, and `high_air`.

VBAP is layout-driven decoding: it calculates speaker gains from object
azimuths and speaker azimuths instead of hard-coding fixed 4-channel routing
amounts.  V2 supports horizontal 2D layouts and the default quad 4.0 layout;
future versions can extend the same renderer interface to other planar arrays.

Renderer selection example:

```bash
python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --export-pseudo-scene \
  --decode-pseudo-scene \
  --pseudo-renderer hybrid_vbap_v1
```

Decoded file names include the renderer family, for example:

```text
*_pseudo_quad_dbap_4ch.wav
*_pseudo_quad_vbap_4ch.wav
*_pseudo_quad_hybrid_4ch.wav
```

Diagnostics include `pseudo_object_scene` when scene export is enabled and
`pseudo_decode` when the scene is decoded.  The legacy field
`mono_fold_down_delta_db` is preserved, but it means the legacy average-4 fold
down `(LF+RF+LB+RB)/4`.  New fields clarify the basis:

- `mono_fold_down_delta_db_avg4_legacy`
- `mono_fold_down_delta_db_front_norm`
- `mono_front_only_delta_db`

## Installation

1. Clone this repository
2. Install dependencies:
```bash
pip install numpy librosa soundfile scipy
```

## Usage

To run with the generated test audio:
```bash
python generate_test_audio.py  # Creates input_audio/test_input.wav
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

For your own audio files:
```bash
python run_spatializer.py input.wav --preset-mode auto_acoustic --output-mode both
```

### Arguments
- `input.wav`: Path to input stereo WAV file
- `--out-dir`: Output directory
- `--preset-mode`: `manual`, `auto_select`, or `auto_acoustic`
- `--output-mode`: `4ch`, `binaural`, or `both`
- `--preset`: Manual preset name when `--preset-mode manual` is used
- `--analysis-seconds`: Duration of analysis (default: 2.0)
- `--export-pseudo-scene`: Export pseudo-object JSON and object layer audio
- `--decode-pseudo-scene`: Decode pseudo-object scene to renderer-tagged quad WAV
- `--pseudo-renderer`: Select `dbap_quad_v1`, `vbap_2d_v1`, or `hybrid_vbap_v1`
- `--pseudo-scene-only`: Export only pseudo-object scene/audio, skipping legacy file exports
- `--no-diagnostics`: Disable JSON diagnostics export

## Presets

- **natural**: Balanced default mode
- **wide**: More obvious spatial effect
- **vocal_safe**: For vocal-heavy music
- **live**: For live/acoustic recordings
- **club**: For electronic/bass-heavy music
- **bypass**: No spatialization
- **ms_baseline**: Simple M/S baseline for comparison

## Listening to 4-Channel Audio

Most consumer audio equipment is stereo. To listen to the 4-channel output:

1. Use a surround sound system with 4 speakers
2. Use headphones with a virtual surround sound processor
3. Use audio software that supports 4-channel playback

## Tuning Presets

To tune presets:
1. Modify the routing parameters in `presets.py`
2. Adjust the layer routing logic in `layer_router.py`
3. Experiment with different decorrelation settings in `decorrelator.py`
4. Use the diagnostic output to understand the impact of changes

## File Structure

```
streaming_stereo_spatializer/
│
├── run_spatializer.py        # Main script
├── audio_io.py               # Audio loading and export
├── streaming_analyzer.py     # Audio analysis
├── layer_extractor.py        # Layer extraction
├── layer_router.py           # Layer routing
├── decorrelator.py           # Rear ambience decorrelation
├── renderer_4ch.py           # 4-channel rendering
├── energy_manager.py         # Loudness matching
├── limiter.py                # Clipping prevention
├── diagnostics.py            # Diagnostic output
├── batch_spatial_diagnostics.py
│                              # Batch spatial metrics and summaries
├── spatial_quality_report.py   # Markdown quality report writer
├── spatial_quality_thresholds.json
│                              # Quality risk thresholds
├── pseudo_object_schema.py    # Pseudo-object metadata schema validation
├── pseudo_object_scene.py     # Pseudo-object scene builder
├── object_audio_export.py     # Object layer audio export helpers
├── speaker_layout.py          # Speaker layout descriptors
├── object_decoder.py          # Pseudo-object renderer dispatch layer
├── renderers/                 # DBAP, 2D VBAP and hybrid renderer modules
├── scripts/check_text_integrity.py
│                              # LF newline and line integrity check
├── scene_diagnostics.py       # Scene summary diagnostics
├── presets.py                # Spatialization presets
├── generate_test_audio.py    # Test tone generation
├── tests/                    # Pytest regression tests
├── README.md                 # This file
```

## Implementation Notes

- The system is designed to resemble a streaming PCM processor
- It uses a rule-based approach rather than AI
- The architecture prioritizes stable front image and bass protection
- Rear ambience is designed to feel wide without obvious echoes
- Energy management prevents output from becoming louder than input

## Limitations

- This is a simulation, not real hardware
- It doesn't handle physical speaker calibration
- The presets need to be tuned based on listening experience
- It doesn't implement advanced features like Dolby Atmos metadata
- It's not designed for network streaming or hardware distribution

## Why Not AI?

This project is explicitly not AI-based. It uses simple signal processing techniques to extract spatial characteristics from stereo audio. The spatial layers are not clean stems but rather spatial-function buses used for rendering to a 4.0 speaker system.

## Next Steps

To evaluate the system:

1. Compare original stereo vs bypass vs ms_baseline vs natural vs wide
2. Test with different music genres
3. Adjust presets based on listening experience
4. Add visualization of spatial characteristics
5. Implement more advanced decorrelation techniques