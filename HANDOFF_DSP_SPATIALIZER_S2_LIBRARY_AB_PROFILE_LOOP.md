# Handoff: DSP-Spacializer S2 Library-Level A/B Feedback and Profile Solidification Loop

Date: 2026-06-22
Target repository: `Kidrage/DSP-Spacializer`
Target line: DSP-Spacializer mainline only
Not target line: Pseudo-Object / object metadata / DBAP / VBAP / hybrid pseudo-object renderer

---

## 0. Context

This handoff assumes the previous DSP-Spacializer feedback-loop work is already complete and validated.

The previous stage should already provide:

1. Stable `auto_acoustic` rendering.
2. Objective quality metrics.
3. Optional automatic routing refinement.
4. Subjective listening feedback JSON.
5. Evaluation record generation.
6. Tuning profile suggestion.
7. Re-rendering with an external tuning profile.
8. Diagnostics showing before/after metrics and applied profile effects.
9. Clean Python formatting, real physical line breaks, `compileall` pass, pytest pass, and no raw-file one-line corruption.

This next stage does **not** repeat S1.
This stage upgrades the project from:

```text
single render -> human feedback -> suggested profile -> next render
```

to:

```text
library batch render
-> multiple candidate mixes per track
-> blind or semi-blind A/B/C listening
-> subjective score + objective safety merge
-> winner selection
-> profile solidification
-> library-level profile evolution
-> regression validation on reference songs
```

The goal is to make DSP-Spacializer evolve like a practical spatial mixing system, where the human spatial mixing engineer gives structured judgments and the system turns them into durable, explainable tuning profiles.

---

## 1. Main Goal

Build a deterministic, explainable, non-AI, library-level feedback loop for the DSP-Spacializer mainline.

The system should be able to:

1. Generate several safe candidate mixes for each song.
2. Render all candidates in batch.
3. Produce a listening session package.
4. Accept human subjective scores, tags, and A/B preferences.
5. Merge subjective feedback with objective diagnostics.
6. Select a winning candidate per song.
7. Update or create a stable tuning profile.
8. Validate that the new profile improves the library without breaking known reference tracks.
9. Preserve rollback history for every profile update.

The core philosophy remains:

```text
human listening preference
-> structured score/tag data
-> deterministic profile update
-> explainable next render
-> repeatable library-level improvement
```

This must not become a black-box model training system yet.

---

## 2. Non-Goals

Do not implement the following in this stage:

1. Do not merge Pseudo-Object logic into this repository.
2. Do not add pseudo-object scene JSON.
3. Do not add object-layer audio export.
4. Do not add DBAP/VBAP/hybrid pseudo-object renderer logic.
5. Do not replace the current DSP pipeline with a neural model.
6. Do not perform physical room correction or speaker calibration.
7. Do not assume arbitrary loudspeaker layouts.
8. Do not hand-tune only one song and call it a general improvement.
9. Do not modify stable manual presets destructively.
10. Do not silently overwrite existing tuning profiles without history.

The DSP-Spacializer mainline remains a stereo-to-4.0 / binaural / CTC-oriented deterministic spatialization pipeline.

---

## 3. Current Expected Baseline

Before starting this handoff, verify that the current branch already has the S1 components:

Expected modules or equivalent functionality:

```text
spatial_safety.py
subjective_feedback.py
tuning_profile.py
feedback_profile_suggester.py
suggest_tuning_profile.py
run_feedback_spatializer.py
quality metrics / safety diagnostics
evaluation record generation
```

Expected successful checks:

```bash
python -m compileall .
python -m pytest -q
git diff --check
```

If these fail, stop and fix S1 first.

---

## 4. New Architecture Overview

Target S2 architecture:

```text
reference_library.yml
        |
        v
candidate_profile_generator.py
        |
        v
batch_candidate_render.py
        |
        v
candidate output folders + diagnostics
        |
        v
listening_session_builder.py
        |
        v
subjective A/B/C feedback JSON
        |
        v
ab_selection.py
        |
        v
profile_solidifier.py
        |
        v
profile_registry.json
        |
        v
library_iteration_report.py
        |
        v
next round candidate generation
```

The system should support repeated rounds:

```text
Round 001 -> profile v1
Round 002 -> profile v2
Round 003 -> profile v3
```

Every round must be explainable and reversible.

---

## 5. Phase S2-A: Reference Library Manifest

### Goal

Create a structured manifest for the listening test library.

Suggested file:

```text
config/reference_library.yml
```

Example:

```yaml
library_name: default_spatial_reference_set
version: 1

tracks:
  - track_id: vocal_pop_001
    title: "Example Vocal Pop"
    path: "曲库/example_vocal_pop.wav"
    category: vocal_pop
    target_style: vocal_safe
    priority: high
    notes: "Lead vocal should remain clear and front-centered."

  - track_id: bass_rap_001
    title: "Example Rap Bass"
    path: "曲库/example_rap.wav"
    category: rap_bass
    target_style: bass_pressure
    priority: high
    notes: "Bass should feel powerful but not muddy."

  - track_id: narrow_old_001
    title: "Example Narrow Old Recording"
    path: "曲库/example_old.wav"
    category: narrow_old_recording
    target_style: natural_room
    priority: medium
    notes: "Avoid fake wide phasey sound."
```

Required categories:

```text
vocal_pop
rap_bass
edm
narrow_old_recording
live_hall
orchestral_cinematic
acoustic
bright_high_frequency
low_frequency_heavy
known_failure_case
```

### Implementation Requirements

Add module:

```text
reference_library.py
```

Suggested API:

```python
def load_reference_library(path: str) -> dict:
    ...

def validate_reference_library(manifest: dict) -> list[str]:
    ...

def iter_reference_tracks(manifest: dict):
    ...
```

Validation should check:

1. Required fields exist.
2. Track paths exist.
3. `track_id` values are unique.
4. `category` is known.
5. `target_style` is known.
6. No absolute local-only paths are committed into tracked config unless intentionally documented.

---

## 6. Phase S2-B: Candidate Profile Generation

### Goal

Generate multiple candidate tuning profiles per song.

This solves the missing step:

```text
one profile suggestion
```

to:

```text
several safe candidate mixes for A/B comparison
```

Add module:

```text
candidate_profile_generator.py
```

Suggested API:

```python
def generate_candidate_profiles(
    base_routing: dict,
    analysis: dict,
    quality_metrics: dict,
    target_style: str,
    max_candidates: int = 5,
) -> list[dict]:
    ...
```

Each candidate should include:

```json
{
  "candidate_id": "A",
  "candidate_name": "baseline_safe",
  "target_style": "vocal_safe",
  "profile_delta": {},
  "reason": "Baseline S1 auto_acoustic/refined result.",
  "risk_notes": [],
  "expected_effect": "Preserve current stable render."
}
```

Recommended default candidates:

### Candidate A: Baseline Safe

Purpose:

```text
Do not change the current refined auto_acoustic result.
```

Use this as the anchor.

### Candidate B: More Spatial

Increase:

```text
rear_floor_ratio
side_rear
amb_rear
rear_master
```

Only if:

```text
vocal_leakage_score is safe
phase_risk_score is safe
harshness_score is safe
```

### Candidate C: Vocal Safe

Reduce:

```text
side_rear
rear_highmid_gain
air_rear
amb_rear
```

Increase:

```text
guard_scale
front_core_stability
```

Use for vocal-heavy tracks.

### Candidate D: Bass Pressure

Increase:

```text
bass_gain
lowbody_front
optional very small bass_quad
```

Only if phase risk is safe.

Avoid excessive rear low-mid.

### Candidate E: Natural Room

Increase:

```text
amb_rear
decorrelation slightly
rear_floor_ratio slightly
```

Reduce:

```text
rear_highmid_gain
air_rear if harsh
```

Use for live, acoustic, orchestral, and old recordings.

### Candidate F: Club Wide

Increase:

```text
side_rear
rear_master
air_rear slightly
decorrelation within safe cap
```

Use for EDM / electronic / rap when vocal leakage is low.

### Candidate Safety Rules

Never allow candidate generation to violate these constraints:

1. Rear channels should not dominate front channels unless explicitly allowed by style.
2. Vocal leakage must not increase aggressively on vocal tracks.
3. Harshness must not be worsened on already bright tracks.
4. Phase risk must block aggressive decorrelation and side-to-rear expansion.
5. Bass enhancement must not create low-mid mud.
6. All profile deltas must be clipped.
7. Every candidate must include a reason and expected effect.

---

## 7. Phase S2-C: Batch Candidate Rendering

### Goal

Render all candidates for a track or a whole reference library.

Add script:

```text
batch_candidate_render.py
```

Suggested CLI:

```bash
python batch_candidate_render.py \
  --library config/reference_library.yml \
  --out-dir /tmp/dsp_spatializer_candidates \
  --preset-mode auto_acoustic \
  --output-mode 4ch \
  --max-candidates 5
```

For one track:

```bash
python batch_candidate_render.py \
  --track 曲库/example.wav \
  --track-id example_001 \
  --target-style vocal_safe \
  --out-dir /tmp/dsp_spatializer_candidates \
  --output-mode 4ch
```

Output directory structure:

```text
candidate_runs/
  round_001/
    manifest.json
    tracks/
      vocal_pop_001/
        A_baseline_safe/
          output_4ch.wav
          diagnostics.json
          candidate_profile.json
          evaluation_record.json
        B_more_spatial/
          output_4ch.wav
          diagnostics.json
          candidate_profile.json
          evaluation_record.json
        C_vocal_safe/
          ...
    listening_session/
      listening_sheet.md
      listening_sheet.csv
      listening_feedback_template.json
```

### Requirements

1. Candidate render should call existing stable rendering functions/scripts instead of duplicating the DSP pipeline.
2. Each candidate must write its profile delta.
3. Each candidate must write diagnostics.
4. Each candidate must write an evaluation record.
5. Batch rendering should continue on per-track failure and summarize failures.
6. The output manifest must record command, timestamp, git commit if available, and profile version.

---

## 8. Phase S2-D: Listening Session Builder

### Goal

Create a structured listening test package for the human spatial mixing engineer.

Add module:

```text
listening_session_builder.py
```

Suggested outputs:

```text
listening_sheet.md
listening_sheet.csv
listening_feedback_template.json
blind_map.json
```

The human should not need to inspect raw parameters first.

A listening item should look like:

```json
{
  "round_id": "round_001",
  "track_id": "vocal_pop_001",
  "candidate_id": "B",
  "blind_label": "Take 2",
  "audio_path": "tracks/vocal_pop_001/B_more_spatial/output_4ch.wav",
  "target_style": "vocal_safe",
  "score_fields": {
    "overall": null,
    "front_clarity": null,
    "rear_presence": null,
    "bass_pressure": null,
    "vocal_stability": null,
    "spatial_width": null,
    "depth": null,
    "naturalness": null,
    "harshness": null,
    "phase_stability": null,
    "fatigue": null
  },
  "tags": [],
  "free_notes": ""
}
```

Recommended score range:

```text
1 = bad
2 = weak
3 = acceptable
4 = good
5 = excellent
```

Recommended tags:

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
front_collapsed
too_dry
too_wet
good_balance
best_candidate
reject
```

### Blind / Semi-Blind Mode

Support:

```bash
--blind
--semi-blind
--no-blind
```

* `--blind`: hide candidate names and profile intent.
* `--semi-blind`: show target style but hide profile details.
* `--no-blind`: show all candidate names and reasons.

Default should be `--semi-blind`.

---

## 9. Phase S2-E: A/B Selection Logic

### Goal

Merge subjective scores with objective diagnostics and choose winners.

Add module:

```text
ab_selection.py
```

Suggested API:

```python
def load_listening_feedback(path: str) -> dict:
    ...

def score_candidate(subjective: dict, objective: dict, target_style: str) -> dict:
    ...

def select_winner(candidates: list[dict], target_style: str) -> dict:
    ...

def summarize_ab_result(track_id: str, candidates: list[dict]) -> dict:
    ...
```

### Scoring Philosophy

Human preference is primary, but objective safety can veto dangerous candidates.

Recommended weighting:

```text
subjective_overall: primary
target_style_relevant_scores: high weight
objective_safety: veto / penalty
diagnostic improvement: secondary
```

Example target-style score emphasis:

```yaml
vocal_safe:
  front_clarity: high
  vocal_stability: high
  phase_stability: high
  rear_presence: medium
  bass_pressure: low

more_spatial:
  rear_presence: high
  spatial_width: high
  depth: high
  phase_stability: high
  front_clarity: medium

bass_pressure:
  bass_pressure: high
  lowmid_mud: negative high
  phase_stability: high
  front_clarity: medium

cinematic_depth:
  depth: high
  naturalness: high
  rear_presence: high
  harshness: negative high

club_wide:
  spatial_width: high
  bass_pressure: high
  rear_presence: high
  vocal_stability: medium
```

### Hard Veto Rules

A candidate should not win if:

1. It has `reject` tag.
2. `phase_weird` is tagged and objective phase risk is high.
3. `vocal_leaks_to_rear` is tagged on a vocal-safe track.
4. Harshness is rated very bad and objective harshness is high.
5. Rear is subjectively too strong and rear/front ratio is objectively excessive.
6. Output clipped or peak safety failed.

### Output

Write:

```text
ab_result.json
```

Example:

```json
{
  "round_id": "round_001",
  "track_id": "vocal_pop_001",
  "winner_candidate_id": "C",
  "winner_name": "vocal_safe",
  "selection_reason": [
    "Highest vocal stability score.",
    "No rear vocal leakage tag.",
    "Objective harshness improved versus baseline.",
    "Rear presence remained acceptable."
  ],
  "rejected_candidates": [
    {
      "candidate_id": "B",
      "reason": "More spatial but vocal leakage was tagged."
    }
  ],
  "score_table": []
}
```

---

## 10. Phase S2-F: Profile Solidification

### Goal

Convert repeated A/B winners into durable tuning profiles.

Add module:

```text
profile_solidifier.py
```

Suggested files:

```text
profiles/
  registry.json
  history/
    profile_update_round_001.json
  styles/
    vocal_safe.json
    more_spatial.json
    bass_pressure.json
    cinematic_depth.json
    club_wide.json
    natural_room.json
```

A profile should not be overwritten directly.
Every update should create a history record.

Profile entry example:

```json
{
  "profile_id": "vocal_safe_v003",
  "base_style": "vocal_safe",
  "version": 3,
  "confidence": 0.72,
  "sample_count": 18,
  "last_updated_round": "round_004",
  "parameter_bias": {
    "side_rear": -0.04,
    "rear_highmid_gain": -0.06,
    "guard_scale": 0.05,
    "rear_floor_ratio": 0.02
  },
  "known_strengths": [
    "Improves vocal stability",
    "Reduces rear high-mid leakage"
  ],
  "known_risks": [
    "May reduce spatial excitement on EDM"
  ],
  "source_tracks": [
    "vocal_pop_001",
    "vocal_pop_002"
  ]
}
```

### Update Rules

1. Use small updates.
2. Blend winner deltas into existing profile.
3. Increase confidence only when multiple tracks support the same direction.
4. Decrease confidence when feedback conflicts.
5. Track category-specific effects.
6. Never let one song dominate the global profile.
7. Always write rollback history.

Pseudo-logic:

```python
new_bias = old_bias * 0.85 + winner_delta * 0.15
```

For high-confidence repeated agreement:

```python
new_bias = old_bias * 0.75 + winner_delta * 0.25
```

For conflict:

```python
new_bias = old_bias * 0.95 + winner_delta * 0.05
confidence -= 0.05
```

All final biases must be clipped.

---

## 11. Phase S2-G: Library Iteration Database

### Goal

Create a persistent record of tracks, candidates, metrics, feedback, winners, and profile updates.

Keep this lightweight. Start with JSONL or SQLite.
Prefer JSONL first unless the repository already has a database convention.

Suggested file:

```text
spatial_mix_history.jsonl
```

Each line:

```json
{
  "event_type": "candidate_evaluated",
  "timestamp": "2026-06-22T00:00:00Z",
  "round_id": "round_001",
  "track_id": "vocal_pop_001",
  "candidate_id": "C",
  "target_style": "vocal_safe",
  "profile_delta": {},
  "objective_metrics": {},
  "subjective_scores": {},
  "tags": [],
  "selected_as_winner": true
}
```

Add module:

```text
spatial_mix_db.py
```

Suggested API:

```python
def append_event(db_path: str, event: dict) -> None:
    ...

def load_events(db_path: str) -> list[dict]:
    ...

def summarize_by_track(events: list[dict]) -> dict:
    ...

def summarize_by_style(events: list[dict]) -> dict:
    ...

def summarize_parameter_trends(events: list[dict]) -> dict:
    ...
```

### Required Summaries

1. Best candidate by track.
2. Average score by target style.
3. Common failure tags.
4. Parameter deltas most often associated with wins.
5. Parameter deltas most often associated with rejection.
6. Tracks that remain unresolved.
7. Profiles with low confidence.
8. Profiles with regression risk.

---

## 12. Phase S2-H: Library Iteration Report

### Goal

Generate a human-readable report after each iteration round.

Add script:

```text
generate_library_iteration_report.py
```

Suggested CLI:

```bash
python generate_library_iteration_report.py \
  --round-dir candidate_runs/round_001 \
  --db spatial_mix_history.jsonl \
  --out reports/round_001_iteration_report.md
```

Report sections:

```text
1. Round Summary
2. Track Coverage
3. Winners by Track
4. Rejected Candidates and Reasons
5. Most Common Listening Problems
6. Objective Metric Trends
7. Profile Updates Proposed
8. Profile Updates Applied
9. Regression Risks
10. Next Round Recommendations
```

Example language:

```text
For vocal_pop tracks, candidates with reduced rear_highmid_gain and slightly increased guard_scale won 4/5 comparisons. The system updated vocal_safe profile from v002 to v003 with low-risk deltas.

For EDM tracks, more_spatial candidates improved width but caused harshness on 2/3 tracks. The system did not update club_wide globally and recommends a high-frequency safety variant next round.
```

---

## 13. Phase S2-I: Regression and Golden Set Validation

### Goal

Prevent profile updates from improving one subset while breaking known good references.

Create:

```text
config/golden_regression_set.yml
```

This can initially point to a subset of the reference library.

Add script:

```text
validate_profile_regression.py
```

Suggested CLI:

```bash
python validate_profile_regression.py \
  --profile profiles/styles/vocal_safe.json \
  --golden-set config/golden_regression_set.yml \
  --out reports/vocal_safe_v003_regression.md
```

Regression checks:

1. Output peak safety.
2. Rear/front ratio within acceptable range.
3. Vocal leakage does not worsen beyond threshold.
4. Harshness does not worsen beyond threshold.
5. Phase risk does not worsen beyond threshold.
6. Bass retention does not collapse.
7. Subjective known-good tracks remain acceptable if previous feedback exists.

Profile update should be blocked or marked risky if regression fails.

---

## 14. Phase S2-J: CLI Integration

Add one top-level workflow script if useful:

```text
run_library_feedback_loop.py
```

Suggested commands:

### Generate candidate renders

```bash
python run_library_feedback_loop.py generate \
  --library config/reference_library.yml \
  --round-id round_001 \
  --out-dir candidate_runs
```

### Build listening session

```bash
python run_library_feedback_loop.py listening-sheet \
  --round-dir candidate_runs/round_001 \
  --blind semi
```

### Import feedback

```bash
python run_library_feedback_loop.py import-feedback \
  --round-dir candidate_runs/round_001 \
  --feedback candidate_runs/round_001/listening_session/completed_feedback.json
```

### Select winners

```bash
python run_library_feedback_loop.py select \
  --round-dir candidate_runs/round_001
```

### Solidify profile

```bash
python run_library_feedback_loop.py solidify \
  --round-dir candidate_runs/round_001 \
  --profile-registry profiles/registry.json
```

### Generate report

```bash
python run_library_feedback_loop.py report \
  --round-dir candidate_runs/round_001 \
  --out reports/round_001_iteration_report.md
```

This top-level script should call smaller modules.
Avoid putting all logic into one large CLI file.

---

## 15. Diagnostics Requirements

Every candidate diagnostics file should include or link to:

```json
{
  "track_id": "",
  "round_id": "",
  "candidate_id": "",
  "candidate_name": "",
  "target_style": "",
  "base_preset": "auto_acoustic",
  "base_profile_id": "",
  "candidate_profile_delta": {},
  "analysis": {},
  "initial_routing": {},
  "final_routing": {},
  "quality_metrics": {},
  "spatial_safety": {},
  "subjective_feedback": {},
  "ab_selection": {},
  "profile_update": {}
}
```

Do not duplicate huge data unnecessarily.
It is acceptable to store paths to related JSON files.

---

## 16. Testing Requirements

Add tests for:

```text
tests/test_reference_library.py
tests/test_candidate_profile_generator.py
tests/test_batch_candidate_render.py
tests/test_listening_session_builder.py
tests/test_ab_selection.py
tests/test_profile_solidifier.py
tests/test_spatial_mix_db.py
tests/test_library_iteration_report.py
tests/test_profile_regression.py
```

Minimum unit test coverage:

1. Reference library manifest validates correct files.
2. Duplicate track IDs are rejected.
3. Candidate generation always includes baseline.
4. Candidate generation clips parameter deltas.
5. Candidate generation blocks risky expansions under high vocal leakage.
6. Listening session builder creates feedback template.
7. A/B selector respects hard veto tags.
8. A/B selector can choose a winner from valid scores.
9. Profile solidifier creates history instead of overwriting.
10. Conflicting feedback reduces confidence.
11. JSONL database append/load works.
12. Report generation works with minimal fake data.
13. Regression validator blocks unsafe profile update.

---

## 17. Text Integrity Requirements

This repository has had raw-file formatting risk before.
Every change must preserve real physical line breaks.

Run:

```bash
python -m compileall .
python -m pytest -q
git diff --check
```

If the repo has a text integrity checker, also run it.

If not, add a lightweight checker:

```text
scripts/check_text_integrity.py
```

It should detect:

1. Python files with suspiciously low physical line count.
2. Python files with extremely long lines.
3. Files where many imports appear on one physical line.
4. Literal escaped newline corruption.
5. CRLF or mixed newline problems if relevant.

Do not allow generated code to be committed as one-line Python.

---

## 18. Validation Plan

Minimum validation before marking this handoff complete:

### Step 1: Static checks

```bash
python -m compileall .
python -m pytest -q
git diff --check
```

### Step 2: Generate candidates for at least three tracks

Use at least:

```text
one vocal-heavy track
one bass-heavy track
one narrow/old/mono-ish track
```

Command example:

```bash
python run_library_feedback_loop.py generate \
  --library config/reference_library.yml \
  --round-id round_001 \
  --out-dir candidate_runs \
  --max-candidates 4
```

Expected:

```text
candidate_runs/round_001/
candidate profiles exist
audio files exist
diagnostics exist
evaluation records exist
manifest exists
```

### Step 3: Build listening session

```bash
python run_library_feedback_loop.py listening-sheet \
  --round-dir candidate_runs/round_001 \
  --blind semi
```

Expected:

```text
listening_sheet.md
listening_sheet.csv
listening_feedback_template.json
blind_map.json
```

### Step 4: Fill fake or real feedback

For automated tests, use a fixture feedback file.

For real acceptance, use actual human listening notes.

### Step 5: Select winners

```bash
python run_library_feedback_loop.py select \
  --round-dir candidate_runs/round_001
```

Expected:

```text
ab_result.json exists for each track
winner selected or unresolved reason written
unsafe candidates rejected with reasons
```

### Step 6: Solidify profile

```bash
python run_library_feedback_loop.py solidify \
  --round-dir candidate_runs/round_001 \
  --profile-registry profiles/registry.json
```

Expected:

```text
profile registry updated
history record written
confidence updated
no destructive overwrite
rollback possible
```

### Step 7: Generate report

```bash
python run_library_feedback_loop.py report \
  --round-dir candidate_runs/round_001 \
  --out reports/round_001_iteration_report.md
```

Expected report includes:

```text
winner table
failure tags
profile changes
regression risks
next round recommendations
```

---

## 19. Acceptance Criteria

This handoff is complete only when all of the following are true:

1. Candidate generation works for individual tracks.
2. Candidate generation works for a reference library.
3. Each track has at least baseline plus two meaningful candidate variants.
4. Candidate variants are clipped and safety-aware.
5. Listening session files are generated.
6. Subjective feedback can be imported.
7. A/B winner selection works.
8. Hard veto rules work.
9. Profile solidification creates versioned history.
10. Library iteration database records all important events.
11. Round report is generated.
12. Regression validation exists.
13. Existing `run_spatializer.py` behavior remains compatible.
14. Existing manual presets remain compatible.
15. Pseudo-Object logic is not introduced.
16. `python -m compileall .` passes.
17. `python -m pytest -q` passes.
18. `git diff --check` passes.
19. No suspicious one-line Python corruption exists.
20. At least one full round can be demonstrated end-to-end.

---

## 20. Expected Outcome

After this stage, the system should be able to say:

```text
For this vocal pop track, candidate C won because it preserved front vocal clarity, reduced rear high-mid leakage, and kept rear presence acceptable.

Across 8 vocal_safe tracks, reduced rear_highmid_gain and increased guard_scale repeatedly won. The vocal_safe profile was updated from v002 to v003 with confidence 0.72.

For EDM tracks, wider candidates improved subjective width but increased harshness. The system did not update the club_wide profile globally and recommends a safer high-frequency variant in the next round.

For narrow old recordings, natural_room candidates won more often than more_spatial candidates. The system recommends separate handling for mono-ish inputs.
```

That is the key step from per-song feedback toward a reusable spatial mixing profile system.

---

## 21. Recommended Commit Strategy

Use small commits:

```text
S2-A reference library manifest
S2-B candidate profile generator
S2-C batch candidate rendering
S2-D listening session builder
S2-E A/B selection
S2-F profile solidification
S2-G spatial mix history database
S2-H iteration report
S2-I regression validation
S2-J CLI integration and docs
```

Each commit should pass:

```bash
python -m compileall .
python -m pytest -q
git diff --check
```

Final commit should include an acceptance report:

```text
acceptance_runs/s2_library_ab_profile_loop/S2_LIBRARY_AB_PROFILE_LOOP_REPORT.md
```

The report should include:

```text
branch
commit hash
changed files
commands run
test results
sample round output path
known limitations
next-stage recommendations
```

---

## 22. Next Stage After This Handoff

After S2 is complete, the next likely stage is S3:

```text
S3: Mode-aware rendering validation and production dataset expansion
```

S3 should focus on:

1. Larger reference library.
2. Real 4.0 speaker listening validation.
3. Binaural and CTC mode-specific diagnostics.
4. Profile behavior across output modes.
5. Long-term preference memory.
6. Optional lightweight dashboard for comparing candidates.
7. Optional SQLite migration if JSONL becomes insufficient.
8. Preparing data for future ML-assisted recommendation, without replacing deterministic control yet.

Do not start S3 before S2 has a working end-to-end A/B profile loop.
