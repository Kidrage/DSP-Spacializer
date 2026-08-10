# Repository Status

## Role

This repository is the authoritative unified DSP spatializer mainline. It
contains the frozen/default non-AI legacy renderer and the opt-in Spatial Core
V2 object/FOA implementation.

## Reference repository

`Kidrage/Pseudo-Object-DSP-Spatializer` and the historical `Pseudo-Object`
branch are reference/archive material. Spatial Core has no runtime dependency
on them.

## Branch Policy

- `main`: stable legacy renderer plus reviewed, opt-in Spatial Core modules.
- `Pseudo-Object`: archival branch only after the repository split.
- New work: focused feature branch -> PR -> CI -> `main`.

## Validation Commands

```bash
python -m compileall .
python generate_test_audio.py
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --out-dir /tmp/stable_source_verify
python -m pytest -q
```

## Current Limitations

- V2 scene objects are DSP buses, not AI-separated clean stems.
- V2.0 has no moving objects, HOA, non-omni directivity, or live tracker.
- V2 S1 has 2D VBAP, not DBAP or hybrid decoding.
- No listener preference learning yet.
