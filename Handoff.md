# Repository Handoff

## Purpose and current objective

This repository implements deterministic stereo-to-4.0 spatialization with
fixed channel order `[LF, RF, LB, RB]`. The current objective is controlled
listening of the Phase 5A V3.1 profiled candidate before wider library testing.

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

Experimental Phase 5A rear-content and V3.1 paths are disabled by default and
must not be treated as production defaults. Human listening remains authoritative.

## Repository state

- Branch: `feat/dsp-feedback-loop-s1`.
- Baseline before this work: `65d65d5`.
- The current change set adds closed-loop refinement, Phase 5A calibration,
  gain-staging v2, linked limiting, rear-content/V3.1 candidates, diagnostics,
  migration/rebuild tools, tests and supporting documentation.

## Decisions and risks

- Do not merge pseudo-object rendering into this fixed-channel mainline.
- Do not globally relax thresholds without at least three consistent listening
  records from the same playback context.
- V3 and V3.1 remain evaluation candidates; neither is promoted globally.
- Current v2 gain staging is transitional and is not yet BS.1770/true-peak
  delivery-final.

## Validation and next step

Validation on 2026-06-24: 47 tests passed; text integrity passed on 65 files;
`git diff --check` passed.

Next, complete focused V3.1 listening, then expand to a 12-track genre/risk set
only if the golden-set evidence supports it.
