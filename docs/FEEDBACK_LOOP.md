# DSP Feedback Loop

This branch keeps `run_spatializer.py` as the stable baseline and adds
`run_feedback_spatializer.py` for review-driven iterations.

Pipeline:

```text
stereo input -> auto_acoustic render -> diagnostics -> human score -> evaluation record -> tuning profile -> next render
```

Baseline:

```bash
python run_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch
```

Feedback path:

```bash
python run_feedback_spatializer.py input_audio/test_input.wav --preset-mode auto_acoustic --output-mode 4ch --tuning-profile profiles/quad_4p0_feedback_example.json --subjective-score examples/subjective_score_example.json --write-evaluation-record
```

Implemented now:

- `tuning_profile.py`: external profile loader and parameter overlay.
- `subjective_feedback.py`: score validation and evaluation record writing.
- `run_feedback_spatializer.py`: wrapper entrypoint that preserves the old renderer path.
- `profiles/quad_4p0_feedback_example.json`: example profile.
- `examples/subjective_score_example.json`: example listening score.

Next stages:

- profile suggestion from many evaluation records.
- A/B/C candidate generation.
- accepted/rejected profile registry.
