# Handoff: auto_acoustic Closed-Loop Upgrade

Date: 2026-06-15

## Context

This repository contains a non-AI stereo-to-spatial DSP pipeline. The current `auto_acoustic` feature already analyzes stereo music and generates per-song spatial routing parameters, but it is still mainly rule-based:

```text
human listening preference -> handwritten rules -> automatic preset generation
```

The next upgrade should make it more like a closed-loop adaptive spatializer:

```text
analysis -> initial preset -> render -> quality metrics -> refine routing -> final render
```

Calibration, physical speaker geometry rendering, and full room correction are out of scope for this handoff. The owner of this work is responsible only for improving the stereo-to-spatial core.

## Current State

Important files:

- `streaming_analyzer.py`
  - Extracts stereo width, center dominance, bass mono ratio, high diffuse ratio, transient density, band coherence, and band side ratios.
- `presets.py`
  - Contains `generate_auto_acoustic_preset(...)`.
  - Recently updated with `adaptive_intensity`, continuous `rear_enhancement_amount`, stronger rear defaults, and `bass_gain`.
- `renderer_4ch.py`
  - Renders the spatial layers to LF/RF/LB/RB.
  - Uses `bass_gain` to reinforce low-frequency core.
- `layer_router.py`
  - Clips routing parameters and keeps compatibility with manual presets.
- `binaural_renderer.py`
  - Renders 4ch to procedural binaural.
  - Also supports CTC inverse rendering from binaural target back to 4ch speaker feeds.
- `run_spatializer.py`
  - Main pipeline entry.
  - Exports 4ch, binaural, binaural room RIR, binaural CTC 4ch, and binaural CTC 4ch after room RIR.
- `diagnostics.py`
  - Current diagnostics are still basic and should be extended.
- `DSP-Spacializer_auto_acoustic_闭环改造阶段性报告.md`
  - Stage report with rationale and detailed upgrade direction.

Recent commits:

- `e8e5964 Enhance auto acoustic spatialization`
- `bfff596 Document auto acoustic refinement plan`

## Problem Statement

`auto_acoustic` can generate parameters automatically, but it cannot yet detect or correct bad outcomes by itself. If a user does not report that bass is weak, rear presence is too subtle, vocals leak to the rear, or highs are harsh, the system has no way to identify and repair that issue.

The missing capability is not another preset. The missing capability is a measurable feedback loop.

## Upgrade Goal

Build a deterministic, explainable, non-AI adaptive system that can:

1. Render an initial `auto_acoustic` result.
2. Measure spatial quality and failure modes.
3. Adjust routing parameters once or twice.
4. Render the final result.
5. Save before/after metrics, routing changes, and reasons into diagnostics.

This should remain transparent and reversible. Avoid black-box behavior.

## Proposed Architecture

### Phase 1: `quality_metrics.py`

Create a new module:

```text
quality_metrics.py
```

Suggested API:

```python
def evaluate_spatial_quality(
    input_left,
    input_right,
    output_4ch,
    sample_rate,
    analysis,
    routing,
):
    ...
    return metrics
```

Suggested metrics:

- `rear_front_ratio`
- `rear_presence_score`
- `spatial_contrast_score`
- `bass_retention_score`
- `vocal_leakage_score`
- `lowmid_mud_score`
- `harshness_score`
- `phase_risk_score`
- `transient_smear_score`

Initial metric definitions can be approximate. The important thing is consistency across songs and useful failure detection.

Recommended first implementation:

- `rear_presence_score`
  - Based on rear/front RMS plus rear energy above a minimum threshold.
- `bass_retention_score`
  - Compare input stereo `<150Hz` level against output front/full `<150Hz` level, normalized against 150-500Hz or 500-2000Hz.
- `vocal_leakage_score`
  - Estimate center-correlated mid/high-mid content leaking into rear channels.
- `lowmid_mud_score`
  - Rear 120-500Hz energy relative to rear mid/high content and front core.
- `harshness_score`
  - Rear 2-8kHz energy relative to rear broadband and input high-mid.
- `phase_risk_score`
  - Correlation / anti-correlation checks between LF/RF, LB/RB, and front/rear summed signals.
- `spatial_contrast_score`
  - Difference between input stereo spatial features and output 4ch rear/side features.

### Phase 2: `auto_refine.py`

Create a new module:

```text
auto_refine.py
```

Suggested API:

```python
def refine_auto_acoustic_routing(routing, analysis, metrics, max_step=1.0):
    ...
    return refined_routing, actions
```

`actions` should be a list of structured explanations:

```python
[
    {
        "reason": "rear_presence_low",
        "metric": 0.42,
        "changes": {
            "side_rear": 0.06,
            "rear_floor_ratio": 0.012,
            "rear_master": 0.03,
        },
    }
]
```

Initial refinement rules:

- If rear presence is too low and vocal leakage is safe:
  - Increase `rear_floor_ratio`.
  - Increase `side_rear`.
  - Increase `rear_master`.
- If bass retention is too low:
  - Increase `bass_gain`.
  - Optionally add a small `bass_quad` bump if phase risk is safe.
- If vocal leakage is high:
  - Reduce `side_rear`.
  - Reduce `amb_rear`.
  - Reduce `rear_highmid_gain`.
  - Increase `guard_scale`.
- If low-mid mud is high:
  - Reduce `lowbody_rear`.
  - Avoid increasing `bass_quad`.
- If harshness is high:
  - Reduce `air_rear`.
  - Reduce `rear_air_gain`.
  - Reduce `rear_highmid_gain`.
- If phase risk is high:
  - Reduce `decorrelation`.
  - Reduce aggressive side-to-rear sends.

All changes should be small, clipped, and logged.

### Phase 3: Pipeline Integration

Modify `run_spatializer.py` to optionally run refinement:

```text
analysis
-> resolve_preset
-> route
-> render initial
-> match/limit initial if needed
-> quality metrics
-> refine routing
-> render final
-> match/limit final
-> export
-> diagnostics
```

Suggested config flags in `config_center.py`:

```python
AUTO_ACOUSTIC_ENABLE_CLOSED_LOOP = True
AUTO_ACOUSTIC_REFINE_PASSES = 1
AUTO_ACOUSTIC_REFINE_MAX_STEP = 1.0
```

Suggested CLI flags:

```text
--auto-acoustic-refine
--auto-acoustic-refine-passes 1
--no-auto-acoustic-refine
```

Keep the default conservative until validated.

### Phase 4: Diagnostics Expansion

Diagnostics should include:

```json
{
  "auto_acoustic_initial_routing": {},
  "auto_acoustic_final_routing": {},
  "auto_acoustic_quality_metrics_initial": {},
  "auto_acoustic_quality_metrics_final": {},
  "auto_acoustic_refine_actions": []
}
```

This is critical. The user needs to understand why the algorithm changed something.

### Phase 5: Preference Memory

After the closed-loop works, add optional preference memory. Do not implement this before metrics/refinement exist.

Suggested file:

```text
config/listener_preference.yml
```

Example:

```yaml
spatial_intensity_bias: 0.10
rear_presence_bias: 0.08
bass_pressure_bias: 0.06
vocal_safety_bias: 0.00
air_brightness_bias: -0.04
```

Suggested feedback tags:

```text
rear_too_weak
rear_too_strong
bass_too_light
bass_too_boomy
vocal_leaks_to_rear
vocal_not_clear
highs_too_harsh
rear_too_dark
lowmid_muddy
space_not_wide_enough
phase_weird
transient_smeared
```

## Human Responsibilities

The human should not be asked to manually tune raw parameters first. The human should provide structured listening feedback.

Required human tasks:

1. Maintain a reference song set.
   - Vocal pop
   - Rap / bass-heavy
   - EDM
   - Narrow old recording
   - Live / hall
   - Orchestral / cinematic
   - Acoustic
   - Bright/high-frequency-heavy track
   - Low-frequency-heavy track
   - Known failure cases

2. Label listening problems using fixed tags.
   - Example: `bass_too_light`, `rear_too_weak`, `vocal_leaks_to_rear`.

3. Choose target style per test song.
   - `vocal_safe`
   - `more_spatial`
   - `bass_pressure`
   - `cinematic_depth`
   - `club_wide`
   - `natural_room`

4. Confirm final subjective quality.
   - Metrics can catch obvious failures.
   - Human listening remains the final judge for music preference.

## Implementation Rules

- Do not replace `auto_acoustic` with a black-box model.
- Keep all automatic changes explainable.
- Keep parameter changes small and clipped.
- Preserve current manual presets.
- Preserve current 4ch/binaural/CTC export behavior.
- Avoid changing physical speaker calibration or external renderer assumptions.
- Do not hand-tune for only one song.
- Validate on at least two tracks before committing.

## Validation Plan

Minimum validation after implementation:

1. Syntax check:

```bash
/Users/saintpeter/anaconda3/bin/python3 -c "from pathlib import Path; root=Path('/Users/saintpeter/Desktop/Coding/spatializer_outputs/DSP空间化codec'); [compile((root/f).read_text(encoding='utf-8'), str(root/f), 'exec') for f in ['quality_metrics.py','auto_refine.py','run_spatializer.py']]"
```

2. Run at least two songs:

```bash
/Users/saintpeter/anaconda3/bin/python3 -B run_spatializer.py 曲库/一生所爱.mp3 --out-dir /private/tmp/spatializer_refine_check --preset-mode auto_acoustic --output-mode 4ch
/Users/saintpeter/anaconda3/bin/python3 -B run_spatializer.py 曲库/Drake.mp3 --out-dir /private/tmp/spatializer_refine_check --preset-mode auto_acoustic --output-mode binaural
```

3. Inspect diagnostics:

- initial/final routing exists;
- metrics exist;
- refine actions are explainable;
- peak remains safe;
- output files are generated.

4. Run `git diff --check`.

## Expected Outcome

After this upgrade, the system should be able to say:

```text
This track had low rear presence and safe vocal leakage, so I increased rear floor, side rear, and rear master.
This track had weak sub-150Hz retention, so I increased bass_gain.
This track had high rear high-mid leakage, so I reduced rear_highmid_gain and side_rear.
```

That is the key step from subjective rule automation toward explainable mechanical learning.
