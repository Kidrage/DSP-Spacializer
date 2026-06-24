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

### Phase 5: Listener Calibration and Preference Memory

The original preference-memory stage should be split into two layers:

```text
Phase 5A: listener threshold calibration
Phase 5B: listener preference bias
```

Threshold calibration must come before preference bias.

The system should not assume that the default metric thresholds are objectively correct for the listener, speaker system, room, or production taste. A metric such as `harshness_score = 0.35` may be numerically safe under the default threshold,
but the listener may already perceive it as harsh on the actual playback system.

The goal of Phase 5 is therefore not only:

```text
"I prefer more spatial intensity."
```

but also:

```text
"My perceptual boundary for harshness, mud, vocal leakage, phase instability, and rear weakness differs from the default threshold."
```

---

#### Phase 5A: Listener Threshold Calibration

Add a new calibration layer above the default quality-threshold system.

Suggested file:

```text
config/listener_threshold_calibration.yml
```

Example:

```yaml
version: 1
listener_id: default
playback_context: four_speaker_reference

calibrated_thresholds:
  harshness_score:
    warning: 0.30
    danger: 0.45
    reason: "Listener reports harshness earlier than default on the reference speaker setup."
    confidence: 0.62
    evidence_count: 6

  vocal_leakage_score:
    warning: 0.22
    danger: 0.36
    reason: "Rear vocal image becomes distracting earlier than default."
    confidence: 0.70
    evidence_count: 8

  lowmid_mud_score:
    warning: 0.38
    danger: 0.55
    reason: "Rear low-mid buildup is noticeable on the current speaker setup."
    confidence: 0.58
    evidence_count: 5

  rear_presence_score:
    too_low: 0.42
    ideal_min: 0.50
    ideal_max: 0.72
    too_high: 0.85
    reason: "Listener prefers clearly audible rear image, but not rear-dominant presentation."
    confidence: 0.65
    evidence_count: 7
```

This file should not replace the base safety thresholds destructively. It should override or offset them at runtime.

Recommended threshold resolution order:

```text
base default thresholds
-> output-mode thresholds
-> target-style thresholds
-> listener threshold calibration
-> optional preference bias
```

Example:

```python
resolved_thresholds = resolve_quality_thresholds(
    base_thresholds=default_thresholds,
    output_mode="4ch",
    target_style="vocal_safe",
    listener_calibration=listener_threshold_calibration,
    preference_bias=listener_preference,
)
```

Threshold calibration should be based on structured listening evidence.

Example feedback record:

```json
{
  "track_id": "bright_pop_001",
  "candidate_id": "B",
  "metric_observation": {
    "harshness_score": 0.35,
    "rear_presence_score": 0.61,
    "vocal_leakage_score": 0.18
  },
  "listener_tags": [
    "highs_too_harsh"
  ],
  "listener_boundary_note": "Although harshness_score is only 0.35, the rear high-mid already feels sharp on the physical speakers.",
  "suggested_threshold_adjustment": {
    "harshness_score.warning": 0.30,
    "harshness_score.danger": 0.45
  }
}
```

The system should collect multiple examples before strongly changing thresholds.

Suggested confidence logic:

```text
1-2 examples: write candidate threshold suggestion only
3-5 examples: allow low-confidence calibration
6+ consistent examples: allow medium-confidence calibration
10+ consistent examples: allow high-confidence calibration
```

Conflicting evidence should reduce confidence.

---

#### New Module: `threshold_calibrator.py`

Create:

```text
threshold_calibrator.py
```

Suggested API:

```python
def collect_threshold_evidence(
    evaluation_records: list[dict],
    subjective_feedback: list[dict],
) -> list[dict]:
    ...

def suggest_threshold_calibration(
    evidence: list[dict],
    current_thresholds: dict,
    min_evidence_count: int = 3,
) -> dict:
    ...

def apply_threshold_calibration(
    base_thresholds: dict,
    calibration: dict,
    target_style: str | None = None,
    output_mode: str | None = None,
) -> dict:
    ...

def explain_threshold_changes(
    old_thresholds: dict,
    new_thresholds: dict,
    evidence: list[dict],
) -> list[dict]:
    ...
```

The calibrator should only adjust threshold values. It should not directly modify routing parameters.

---

#### Threshold Calibration Rules

Use listening tags to calibrate metric boundaries:

```text
highs_too_harsh
-> lower harshness_score warning/danger threshold

lowmid_muddy
-> lower lowmid_mud_score warning/danger threshold

vocal_leaks_to_rear
-> lower vocal_leakage_score warning/danger threshold

phase_weird
-> lower phase_risk_score warning/danger threshold

rear_too_weak while rear_presence_score is "safe"
-> raise rear_presence_score ideal_min or too_low threshold

rear_too_strong while rear/front ratio is "safe"
-> lower rear_presence_score ideal_max or rear/front upper bound

bass_too_light while bass_retention_score is "safe"
-> raise bass_retention_score minimum acceptable threshold

bass_too_boomy while bass metrics are "safe"
-> lower bass pressure / low-frequency rear tolerance
```

Threshold calibration should be conservative:

1. Never change thresholds from a single example.
2. Never update hard safety thresholds without evidence.
3. Keep a history file for every calibration update.
4. Distinguish global thresholds from target-style thresholds.
5. Distinguish 4ch speaker playback from binaural preview and CTC output.
6. Prefer warning-threshold changes before danger-threshold changes.
7. All changes must be explainable.

---

#### Calibration History

Add:

```text
config/threshold_calibration_history.jsonl
```

Each update should record:

```json
{
  "timestamp": "2026-06-22T00:00:00Z",
  "threshold_name": "harshness_score.warning",
  "old_value": 0.42,
  "new_value": 0.30,
  "confidence": 0.62,
  "evidence_count": 6,
  "source_tracks": [
    "bright_pop_001",
    "edm_003",
    "female_vocal_002"
  ],
  "reason": "Listener repeatedly reported harshness below the previous warning threshold."
}
```

---

#### Phase 5B: Listener Preference Bias

After threshold calibration exists, keep the original preference-memory idea as a second layer.

Suggested file:

```text
config/listener_preference.yml
```

Example:

```yaml
version: 1
listener_id: default

preference_bias:
  spatial_intensity_bias: 0.10
  rear_presence_bias: 0.08
  bass_pressure_bias: 0.06
  vocal_safety_bias: 0.00
  air_brightness_bias: -0.04
  natural_room_bias: 0.05
```

Preference bias answers:

```text
Given that the safety thresholds are calibrated, what does the listener prefer aesthetically?
```

It should not redefine safety boundaries.

For example:

```text
listener_threshold_calibration:
  "harshness begins around 0.30 for this playback setup."

listener_preference:
  "even below the harshness threshold, I prefer slightly darker rear air."
```

---

#### Correct Phase 5 Pipeline

The final Phase 5 pipeline should be:

```text
render output
-> compute objective metrics
-> compare metrics against calibrated listener thresholds
-> classify risk/failure
-> collect subjective feedback
-> update threshold calibration if listener perception disagrees with metrics
-> update preference bias if listener consistently prefers a direction
-> use both in the next routing/profile suggestion
```

Expanded loop:

```text
objective metric says safe
+ listener says bad
= threshold calibration candidate

objective metric says safe
+ listener says acceptable but wants more/less stylistically
= preference bias candidate

objective metric says unsafe
+ listener also says bad
= threshold confirmed

objective metric says unsafe
+ listener says acceptable
= threshold may be too strict, but require repeated evidence
```

---

#### Diagnostics Additions

Diagnostics should include:

```json
{
  "quality_thresholds_base": {},
  "quality_thresholds_calibrated": {},
  "listener_threshold_calibration_applied": {},
  "threshold_calibration_actions": [],
  "listener_preference_bias_applied": {},
  "preference_bias_actions": []
}
```

Each action should explain:

```json
{
  "type": "threshold_calibration",
  "metric": "harshness_score",
  "old_warning": 0.42,
  "new_warning": 0.30,
  "reason": "Listener repeatedly tagged highs_too_harsh below old threshold.",
  "confidence": 0.62,
  "evidence_count": 6
}
```

---

#### Acceptance Criteria for Modified Phase 5

Phase 5 is complete only when:

1. The system can load default thresholds.
2. The system can load listener threshold calibration.
3. The system can resolve final thresholds by output mode and target style.
4. Subjective feedback can generate threshold calibration suggestions.
5. Threshold calibration suggestions require multiple evidence records.
6. Threshold calibration history is written.
7. Preference bias remains separate from threshold calibration.
8. Diagnostics show base thresholds, calibrated thresholds, and applied preference bias.
9. Tests cover harshness, vocal leakage, rear weakness, bass weakness, and phase-risk calibration.
10. Existing S1/S2 rendering behavior remains compatible.
11. No threshold update directly modifies routing without going through the existing refinement/profile system.

---

#### Implementation Order

Recommended order:

```text
5A-1: extract current quality thresholds into explicit config
5A-2: add threshold resolver
5A-3: add listener_threshold_calibration.yml
5A-4: add threshold_calibrator.py
5A-5: add calibration history JSONL
5A-6: add diagnostics fields
5A-7: add tests
5B-1: add listener_preference.yml
5B-2: apply preference bias after calibrated thresholds
5B-3: connect preference bias to profile suggestion, not raw safety
```

Do not start preference bias until threshold calibration is working.

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
PYTHONPYCACHEPREFIX=/private/tmp/spatializer_pycache .venv/bin/python -m compileall -q .
```

2. Run at least two songs:

From the repository root:

```bash
.venv/bin/python -B run_spatializer.py ../曲库/一生所爱.mp3 --out-dir /private/tmp/spatializer_refine_check --preset-mode auto_acoustic --output-mode 4ch
.venv/bin/python -B run_spatializer.py ../曲库/Drake.mp3 --out-dir /private/tmp/spatializer_refine_check --preset-mode auto_acoustic --output-mode binaural
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
