# Streaming Stereo Spatializer

DSP-Spacializer is a stable, non-AI stereo to fixed 4.0 / binaural DSP
spatializer. It converts stereo L/R audio into deterministic spatial-function
layers and renders them to logical 4.0 output:

```text
[LF, RF, LB, RB]
```

The main branch is the clean fixed-channel line. It is not a source separation
system, not a pseudo-object scene renderer, not a DBAP/VBAP/hybrid object
decoder, and not a built-in listener model. Feedback-loop work is kept in
separate reviewable tooling so the stable renderer can be rolled back or used
unchanged.

## What It Does

- Loads stereo, mono, or multi-channel audio and normalizes it for processing.
- Analyzes stereo width, center dominance, spectral bands, coherence, and
  transient behavior.
- Extracts DSP spatial-function layers such as bass body, low-body support,
  front core, side width, rear ambience, and high air.
- Routes those layers through fixed-channel presets.
- Renders fixed 4.0 output with `renderer_4ch.py`.
- Applies rear-channel spatial safety, energy matching, limiting, diagnostics,
  and optional quality reports.
- Optionally renders binaural headphone previews and binaural-to-4ch CTC output.
- Optionally records subjective listening feedback and suggests external tuning
  profiles without modifying the stable renderer path.

## What It Does Not Do

- No AI source separation.
- No clean stem extraction.
- No pseudo-object scene JSON export.
- No object-layer audio export.
- No speaker-layout object decoding.
- No DBAP, VBAP, or hybrid pseudo-object renderer.
- No automatic modification of core preset code from listener feedback.

Pseudo-object scene/export/DBAP/VBAP/hybrid renderer work has been split into:
`https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer`.
See [docs/BRANCH_STRATEGY.md](docs/BRANCH_STRATEGY.md).

## Install

```bash
python -m pip install numpy librosa soundfile scipy
```

## Quick Start

```bash
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

`generate_test_audio.py` writes `input_audio/test_input.wav`, so the command
above runs without moving files by hand.

## Common Commands

Render a 4.0 WAV:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

Render a binaural headphone preview:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode binaural
```

Render both 4.0 and binaural outputs:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode both
```

Analyze only and write diagnostics:

```bash
python run_spatializer.py input_audio/test_input.wav --diagnostics-only
```

Write a quality report for the run manifest:

```bash
python run_spatializer.py input_audio/test_input.wav --write-quality-report
```

Run batch spatial diagnostics:

```bash
python batch_spatial_diagnostics.py --input-dir input_audio --output-dir outputs/batch_eval --preset-mode auto_acoustic
```

## Feedback Loop Commands

Render through the feedback wrapper, apply an external tuning profile, and write
an evaluation record from a subjective listening score:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_example.json \
  --subjective-score examples/subjective_score_example.json \
  --write-evaluation-record
```

Suggest the next reviewable tuning profile from one or more evaluation records:

```bash
python suggest_tuning_profile.py outputs \
  --profile-id quad_4p0_feedback_round_001 \
  --out profiles/quad_4p0_feedback_round_001.json
```

Use the suggested profile for the next render:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_round_001.json
```

The feedback path writes external JSON artifacts only. It does not rewrite
`presets.py` or replace the stable `run_spatializer.py` entrypoint.

## CLI

Primary arguments:

- `input_file`: optional input audio file. If omitted, the folder mode in
  `config_center.py` is used.
- `--out-dir`: output directory.
- `--preset-mode`: `manual`, `auto_select`, or `auto_acoustic`.
- `--preset`: manual preset name when `--preset-mode manual` is used.
- `--output-mode`: `4ch`, `binaural`, or `both`.
- `--analysis-seconds`: duration used for analysis.
- `--target-sr`: processing sample rate.
- `--auto-acoustic-rear-enhancement`: enable the safe rear enhancement plan.
- `--export-binaural-front-pair`: export a front-pair binaural preview.
- `--export-binaural-rear-pair`: export a rear-pair binaural preview.
- `--export-binaural-ctc-4ch`: export crosstalk-cancelled 4ch speaker feeds
  from the binaural target.
- `--diagnostics-only`: write diagnostics without exporting WAV files.
- `--write-quality-report`: write `quality_report.md` for the current manifest.
- `--no-spatial-safety`: disable rear-channel safety guards while still
  reporting quality metrics.

Feedback wrapper arguments:

- `--tuning-profile`: external JSON profile applied after preset resolution.
- `--subjective-score`: one subjective score JSON for the current render.
- `--subjective-score-dir`: directory of per-song score JSON files.
- `--write-evaluation-record`: force evaluation record output.

## Main Files

- `run_spatializer.py`: main single-file and folder-processing entrypoint.
- `run_feedback_spatializer.py`: feedback-aware wrapper around the stable path.
- `suggest_tuning_profile.py`: CLI for suggesting the next tuning profile.
- `tuning_profile.py`: external tuning profile validation and application.
- `subjective_feedback.py`: subjective score validation and evaluation records.
- `feedback_profile_suggester.py`: deterministic feedback-to-profile rules.
- `batch_spatial_diagnostics.py`: batch quality diagnostics and reports.
- `config_center.py`: folder mode, output mode, preset, binaural, CTC, and
  safety defaults.
- `audio_io.py`: input discovery, loading, and audio export helpers.
- `streaming_analyzer.py`: stereo and spectral analysis.
- `layer_extractor.py`: DSP spatial-function layer extraction.
- `layer_router.py`: preset routing application.
- `renderer_4ch.py`: fixed `[LF, RF, LB, RB]` renderer.
- `binaural_renderer.py`: 4.0 virtual-speaker binaural and CTC utilities.
- `spatial_safety.py`: rear-channel safety and quality metrics.
- `spatial_quality_report.py`: Markdown quality report generation.

## Tests

Run the focused suite:

```bash
python -m pytest -q tests/test_run_spatializer_cli.py tests/test_spatial_safety.py tests/test_batch_spatial_diagnostics.py tests/test_tuning_profile.py tests/test_subjective_feedback.py tests/test_feedback_profile_suggester.py
```

Run all tracked tests:

```bash
python -m pytest -q
```
