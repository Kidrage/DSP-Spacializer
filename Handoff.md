# Repository Handoff

## Purpose and current objective

This repository implements deterministic stereo-to-4.0 spatialization with
fixed channel order `[LF, RF, LB, RB]`. The current objective is to preserve
Phase 5A V3.2 as the stable baseline after the prototype-speaker A/B pass.

## Structure and entry points

- `run_spatializer.py`: CLI and render pipeline.
- `config_center.py`: repository-relative input/output paths and feature flags.
- `presets.py`: manual, automatic and experimental candidate routing profiles.
- `spatial_safety.py`, `energy_manager.py`, `limiter.py`: safety, gain staging
  and linked multichannel limiting.
- `auto_refine.py`: deterministic closed-loop metric refinement.
- `threshold_calibrator.py`: listener-evidence threshold suggestions.
- `config/`: quality, refinement and listener calibration configuration.
- `tests/`: DSP safety, gain staging, calibration and candidate regressions.

## Current pipeline and conventions

Stereo input is loaded and resampled, analysed, routed to four channels,
measured and optionally refined, then front-anchor gain matching and linked
envelope limiting are applied before WAV and diagnostics export. Input and
output default to workspace-level `曲库/` and `Output-DSP/`, with environment
variable overrides available.

Experimental Phase 5A rear-content, V3.1 and V3.2 paths are disabled by default.
V3.2 is the frozen Phase 5A stable baseline for future A/B, but it is not yet
delivery-final or a full-library default. Human listening remains authoritative.

## Repository state

- Branch: `feat/dsp-feedback-loop-s1`.
- Baseline before this work: `65d65d5`.
- The current change set adds closed-loop refinement, Phase 5A calibration,
  gain-staging v2, linked limiting, rear-content/V3.1/V3.2 candidates,
  diagnostics, migration/rebuild tools, tests and supporting documentation.

## Decisions and risks

- Do not merge pseudo-object rendering into this fixed-channel mainline.
- Do not globally relax thresholds without at least three consistent listening
  records from the same playback context.
- V3 and V3.1 remain evaluation candidates; neither is promoted globally.
- V3.2 is accepted as the Phase 5A stable baseline based on 2026-06-29
  prototype-speaker listening, with caveats: `Little Blue` preferred A,
  `You Belong With Me` had slight bass resonance, and rear presence is still
  weak on low-side/narrow material.
- V3.3 work must branch from V3.2 as separate rear-audibility or front-width
  candidates. Do not mutate V3.2 in place and do not add raw center send to rear.
- Current v2 gain staging is transitional and is not yet BS.1770/true-peak
  delivery-final.

## Validation and next step

Validation on 2026-06-29: 63 tests passed with
`PYTHONPYCACHEPREFIX=/private/tmp/spatializer_pycache .venv/bin/python -m pytest -q`;
`git diff --check` passed.

Next, keep V3.2 frozen. Any further tuning should start as a V3.3 focused A/B
for rear audibility, front matrix width and bass-resonance protection rather
than changing V3.2 directly.
