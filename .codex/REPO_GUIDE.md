# DSP-Spacializer Repository Guide

## Purpose

Deterministic, non-AI spatializer with a frozen legacy stereo-to-fixed-4.0/binaural baseline and an opt-in Spatial Core V2 object/FOA architecture. Legacy logical order is `[LF, RF, LB, RB]`; V2 FOA order is AmbiX ACN/SN3D `[W,Y,Z,X]`.

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
- `spatial_core/`: V2 scene interchange, DSP-bus builder, SOFA binaural, listener motion, quad VBAP, and CTC adapter.
- `docs/SPATIAL_CORE_V2.md`: V2 contracts, formats, CLI, and promotion gate.

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
- Do not add raw center send to legacy rear channels. New scene-renderer work belongs in the unified `spatial_core` package and must remain opt-in until promoted.
- V2 binaural requires measured `SimpleFreeFieldHRIR` SOFA data; no procedural fallback or bundled dataset.
- Avoid `input_audio/` payloads, `outputs/`, workspace-level `曲库/` and `Output-DSP/`, `.venv/`, caches, notebooks, and binary/audio assets unless explicitly required.
- Keep generated listener data and suggested tuning profiles external to the stable renderer path.

## Git and Verification

- Remote: `origin` -> `Kidrage/DSP-Spacializer`.
- Spatial Core S1 branch: `feat/spatial-core-v2-s1`, based on the feedback-loop merge in `main`.
- Run targeted tests for localized changes and the full suite for routing, safety, gain-staging, or pipeline changes.
- Run `git diff --check` before handoff. Deliver through a feature-branch PR; do not push directly to `main`.
