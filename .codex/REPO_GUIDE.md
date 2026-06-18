# DSP-Spacializer Repo Guide

## Purpose

Stable non-AI stereo to fixed 4.0 / binaural DSP spatializer. The main branch
renders deterministic DSP spatial-function layers to `[LF, RF, LB, RB]`.

## Branches And Remotes

- Current cleanup branch: `main-cleanup-legacy-4ch-r0b`
- Main remote: `origin` -> `https://github.com/Kidrage/DSP-Spacializer.git`
- Local mirror remote: `gitea` -> `http://10.0.1.2:3000/Ao/DSP-Spatializer.git`
- `main`: stable fixed-channel line
- `Pseudo-Object`: experimental scene/object/layout-decoder line

## Main Entrypoints

- `run_spatializer.py`: single-file/folder processing entrypoint.
- `batch_spatial_diagnostics.py`: batch metrics, summary, and reports.
- `generate_test_audio.py`: creates `input_audio/test_input.wav`.
- `config_center.py`: default processing, output, preset, binaural, CTC, and
  safety settings.

## Core Source

- `audio_io.py`: input discovery/load/export.
- `streaming_analyzer.py`: stereo/spectral analysis.
- `layer_extractor.py`: DSP spatial-function layer extraction.
- `layer_router.py`: preset routing.
- `renderer_4ch.py`: fixed 4.0 renderer.
- `binaural_renderer.py`: binaural and CTC rendering.
- `spatial_safety.py`: quality metrics and rear-channel safety.
- `spatial_quality_report.py`: Markdown reports.

## Tests

- `tests/test_run_spatializer_cli.py`
- `tests/test_spatial_safety.py`
- `tests/test_batch_spatial_diagnostics.py`
- `tests/test_text_integrity.py`

## Avoid

- Generated outputs: `outputs/`, `spatializer_outputs_clean/`
- Python caches and virtualenvs
- Generated audio unless explicitly requested
- Reintroducing pseudo-object modules or CLI flags on `main`

## Before Modifying Code

1. Check `git status --short`, current branch, and remotes.
2. Read `README.md`, `docs/BRANCH_STRATEGY.md`, and the target source file.
3. Search before editing: `rg "<symbol-or-flag>"`.
4. Run focused tests first; broaden only when shared behavior changes.

## Push Checklist

1. Review `git diff`.
2. Confirm no generated audio, caches, or secrets.
3. Run focused verification and preferably `python -m pytest -q`.
4. Push the intended branch and check CI if configured.
