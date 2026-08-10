# DSP-Spacializer Repository Guide

## Purpose

Deterministic, non-AI stereo-to-fixed-4.0/binaural DSP spatializer. The logical channel order is `[LF, RF, LB, RB]`. The current feature branch freezes Phase 5A V3.2 as a human-listening baseline; it is not the default full-library delivery path.

## First Reads

- `PROJECT_HANDOFF.md`: generated repository state and current risks.
- `Handoff.md`: Phase 5A/V3.2 decisions and listening conclusions.
- `README.md`: supported workflows and CLI examples.
- `.codex/source_index.txt`: filtered source, test, config, and documentation map.
- `CLAUDE.md`: detailed DSP conventions and file roles; verify its status notes against Git because they can age.

## Main Routes

- `run_spatializer.py`: primary CLI and render pipeline.
- `presets.py`: manual, automatic, and Phase 5A candidate routing.
- `layer_extractor.py` -> `layer_router.py` -> `renderer_4ch.py`: spatial-function render chain.
- `spatial_safety.py`, `energy_manager.py`, `limiter.py`: safety, gain staging, and linked limiting.
- `run_feedback_spatializer.py`, `subjective_feedback.py`, `tuning_profile.py`: external listener-feedback loop.
- `auto_refine.py`, `threshold_calibrator.py`, `config/`: deterministic refinement and calibration.
- `tests/test_v32_candidate.py`: focused V3.2 regression contract.

## Commands

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m pytest -q tests/test_v32_candidate.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

## Constraints

- Human listening remains authoritative; diagnostics are advisory.
- V3.2 is frozen and experimental candidates are disabled by default.
- Do not add raw center send to rear channels or fold pseudo-object rendering into this repository.
- Avoid `input_audio/` payloads, `outputs/`, workspace-level `曲库/` and `Output-DSP/`, `.venv/`, caches, notebooks, and binary/audio assets unless explicitly required.
- Keep generated listener data and suggested tuning profiles external to the stable renderer path.

## Git and Verification

- Remote: `origin` -> `Kidrage/DSP-Spacializer`.
- Working branch at onboarding: `feat/dsp-feedback-loop-s1`.
- Run targeted tests for localized changes and the full suite for routing, safety, gain-staging, or pipeline changes.
- Run `git diff --check` before handoff. Do not push this feature branch without explicit user direction.
