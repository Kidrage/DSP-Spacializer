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
- `spatial_core/`: V2 scene interchange, lossless seven-zone M/S builder, compact profile, geometry room, SOFA binaural, listener motion, quad VBAP, and CTC adapter.
- `run_frontal_externalization_eval.py` and `run_frontal_externalization_fex1.py`:
  path-safe FEX-0 baseline and fixed A–F FEX-1 screening exporters. FEX-1 uses
  evaluation-only BS.1770 matching and never writes its gain back to the renderer.
- `docs/SPATIAL_CORE_V2.md`: V2 contracts, formats, CLI, and promotion gate.
- `spatial_mixer/`: strict universal seven-zone profile, preview renderer, pinned
  calibration campaign, blind comparison evidence, and promotion export.
- `run_spatial_mixer.py` + `web_ui/`: local-only calibration console. The server
  owns all campaign mutations; the browser is not an evidence authority.
- `docs/SEVEN_ZONE_MIXER.md`: mixing theory, safe listening order, profile and
  campaign contracts, and launch instructions.
- `docs/ARCHITECTURE_AND_SIGNAL_FLOW.md` and `docs/PARAMETER_REFERENCE.md`:
  complete legacy/V2 production-chain and tuning-entry reference.
- `docs/SPATIAL_SCENE_PACKAGE_V0_1.md`, `schemas/`, and `spatial_core/package.py`:
  renderer-neutral seven-zone master contract and directory/ZIP validator.

## Commands

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m pytest -q tests/test_v32_candidate.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
python run_spatial_mixer.py --library-dir /absolute/audio/library --sofa /absolute/listener.sofa
python run_frontal_externalization_fex1.py --library-root /absolute/audio/library --sofa /absolute/listener.sofa --output-dir /absolute/new-output --source-revision <commit>
```

## Constraints

- Human listening remains authoritative; diagnostics are advisory.
- V3.2 is frozen and experimental candidates are disabled by default.
- Do not add raw center send to legacy rear channels. New scene-renderer work belongs in the unified `spatial_core` package and must remain opt-in until promoted.
- V2 binaural requires measured `SimpleFreeFieldHRIR` SOFA data; no procedural fallback or bundled dataset.
- V2.1 stereo scenes use `spatial_core_profile` 1.0 and can opt into the
  `balanced-depth` room. Keep `small-dry` and `off` compatible.
- The opt-in `spatial_mixer_profile` 1.0 expands V2.1 into four direct-object
  strips, three FOA field strips, room controls, and extraction controls. JSON
  object key order is irrelevant; loading canonicalizes the seven zones.
- Calibration promotion requires the pinned nine-track/six-class set and
  server-bound preview evidence. Objective red warnings require a written,
  exported override; they are not silently converted to a pass.
- Avoid `input_audio/` payloads, `outputs/`, workspace-level `曲库/` and `Output-DSP/`, `.venv/`, caches, notebooks, and binary/audio assets unless explicitly required.
- Spatial Scene Package v0.1 is fixed at seven mono 48 kHz float WAV assets;
  FOA is derived at render time and is not the authoritative package payload.
- Keep generated listener data and suggested tuning profiles external to the stable renderer path.

## Git and Verification

- Remote: `origin` -> `Kidrage/DSP-Spacializer`.
- Spatial Core S1 branch: `feat/spatial-core-v2-s1`, based on the feedback-loop merge in `main`.
- Run targeted tests for localized changes and the full suite for routing, safety, gain-staging, or pipeline changes.
- Run `git diff --check` before handoff. Deliver through a feature-branch PR; do not push directly to `main`.
