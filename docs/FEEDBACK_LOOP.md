# DSP Feedback Loop

This branch keeps `run_spatializer.py` as the stable baseline and adds a
review-driven path around it. The stable renderer remains the source of truth;
feedback tooling only writes external records and tuning profiles.

## Closed Loop Shape

```text
stereo input
-> auto_acoustic render
-> diagnostics
-> human score
-> evaluation record
-> suggested tuning profile
-> next feedback render
```

The loop is intentionally reviewable. A suggested profile is a JSON artifact;
it is not automatically committed into `presets.py` and does not rewrite the
core DSP algorithm.

## Baseline Render

```bash
python run_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch
```

## Feedback Render With Existing Profile

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_example.json \
  --subjective-score examples/subjective_score_example.json \
  --write-evaluation-record
```

This writes the normal render outputs plus an evaluation record such as:

```text
outputs/test_input_auto_acoustic_evaluation_record.json
```

## Suggest Next Profile From Records

```bash
python suggest_tuning_profile.py outputs \
  --profile-id quad_4p0_feedback_round_001 \
  --out profiles/quad_4p0_feedback_round_001.json
```

Then render again with the suggested profile:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --tuning-profile profiles/quad_4p0_feedback_round_001.json
```

## Implemented Now

- `tuning_profile.py`: external profile loader and parameter overlay.
- `subjective_feedback.py`: score validation and evaluation record writing.
- `feedback_profile_suggester.py`: deterministic rules for suggested profiles.
- `run_feedback_spatializer.py`: wrapper entrypoint preserving the old renderer path.
- `suggest_tuning_profile.py`: CLI for profile suggestion from evaluation records.
- `profiles/quad_4p0_feedback_example.json`: example profile.
- `examples/subjective_score_example.json`: example listening score.

## Current Scope

This is a first closed-loop scaffold. It supports human scoring, evaluation
record creation, suggested tuning profile generation, and rerendering with that
profile. It does not yet implement randomized A/B/C candidate packs,
automated winner selection, or accepted/rejected profile registries.
