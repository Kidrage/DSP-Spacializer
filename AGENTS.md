# DSP-Spacializer Agent Notes

## Scope

This repository's `main` branch is the stable fixed-channel DSP spatializer:
stereo input -> DSP layers -> fixed 4.0 renderer -> optional binaural / CTC
outputs. Keep pseudo-object scene, object audio, DBAP, VBAP, hybrid renderer,
and speaker-layout decoder work on the `Pseudo-Object` branch.

## Read First

- `README.md`
- `docs/BRANCH_STRATEGY.md`
- `run_spatializer.py`
- `config_center.py`
- `.codex/REPO_GUIDE.md`

## Editing Rules

- Preserve the clean fixed-channel contract on `main`.
- Keep changes small and targeted.
- Do not reintroduce pseudo-object imports, CLI flags, modules, or tests on
  `main`.
- Do not commit generated audio, output folders, caches, or local reports.

## Verification

Preferred focused checks:

```bash
python -m pytest -q tests/test_run_spatializer_cli.py tests/test_spatial_safety.py tests/test_batch_spatial_diagnostics.py
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --out-dir /tmp/dsp_spacializer_verify
```

Run `python -m pytest -q` before pushing broader changes.
