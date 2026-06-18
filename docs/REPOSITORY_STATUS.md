# Repository Status

## Role

This repository is the stable fixed-channel DSP spatializer mainline.

It keeps the non-AI stereo -> fixed 4.0 / binaural / diagnostics path clean and
does not contain pseudo-object implementation code on `main`.

## Split Notice

Pseudo-object scene/export/DBAP/VBAP/hybrid renderer work has been split into:

```text
https://github.com/Kidrage/Pseudo-Object-DSP-Spatializer
```

The source repository's historical `Pseudo-Object` branch is left untouched as
an archive unless it is explicitly removed later.

## Branch Policy

- `main`: stable fixed 4.0 / binaural / diagnostics DSP spatializer.
- `Pseudo-Object`: archival branch only after the repository split.
- Active pseudo-object development: `Kidrage/Pseudo-Object-DSP-Spatializer`.

## Validation Commands

```bash
python -m compileall .
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --out-dir /tmp/stable_source_verify
python -m pytest -q
```

## Current Limitations

- No pseudo-object scene export in this repository.
- No object-layer audio export in this repository.
- No DBAP, 2D VBAP, or hybrid pseudo-object renderer in this repository.
- No auto-refine yet.
- No listener preference learning yet.
