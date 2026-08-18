# Frontal Externalization FEX-0/FEX-1 Decision Map

## Scope lock

- Base branch: latest `main` at `ae192c54587ced71e02c5d9582d53290e7509852`.
- Work branch: `feat/frontal-externalization-v1`.
- Only the Spatial Core V2/V2.1 measured-SOFA binaural path is in scope.
- FEX-2 physical DRR, FEX-3 structured frontal reflections, and FEX-4 BRIR
  residual work are frozen until FEX-1 reaches research maturity.
- Legacy V3.2, seven-zone extraction, FOA, speaker rendering, and default listening
  behavior remain frozen.

## Code facts verified on the base revision

- The binaural renderer applies a minimum-phase inverse derived from the nearest
  frontal HRIR to the complete output.
- Render output is matched toward `mastered_reference_rms`, with gain limits and
  peak headroom protection.
- The default builder assigns `direct_ratio = 0.78` to all front objects.
- `balanced-depth` applies an additional `-3 dB` wet send to `center` objects.
- Balanced early reflections are divided by each object's reflection-vector norm.
- First-order balanced-depth taps occupy roughly 8–18 ms in the pinned distance
  range; there is no structured 20–80 ms layer.
- `micro_motion` is deterministic seeded random motion, not world-locked tracking.

These facts identify causal A/B controls. They do not prove that any control
improves externalization.

## Perceptual hypotheses requiring listening

- Front-common-field compensation may remove useful frontal pinna cues.
- Input-RMS restoration may weaken a useful loudness-distance cue.
- A `0 dB` center room-send trim may improve distance without blurring the anchor.
- Physical path gain without per-object reflection normalization may improve depth.
- A combination may outperform each single factor without harming clarity or
  producing a double image.

No objective metric alone can promote any of these hypotheses.

## Pinned stereo corpus

The repository stores only roles, relative filenames, hashes, and excerpt times.
The runtime root is injected with `--library-root`; generated diagnostics must not
persist that root or any other absolute source path.

| Track | Role | Screening excerpt(s) |
|---|---|---|
| `孤勇者.mp3` | independent male vocal mix | 90–110 s |
| `Chan Chan (Live Session).mp3` | independent female vocal mix | 145–165 s |
| `Little Blue.mp3` | same-mix sequential vocal comparison | male 30–50 s; female 160–180 s |

All inputs remain complete stereo MP3/WAV files. There is no stem creation,
source separation, or assumption that the two `Little Blue` voices overlap.

## Evaluation conditions

| ID | Single change from A |
|---|---|
| A | current Spatial Core V2.1 baseline |
| B | front-common-field compensation off |
| C | render-time input-RMS restoration off |
| D | center room-send trim from `-3 dB` to `0 dB` |
| E | per-object early-reflection normalization off |
| F | B + C + D + E interaction check |

F is an interaction diagnostic, not an automatic candidate. A condition that
fails a single-factor safety gate cannot be rescued merely because F sounds wider.

## Loudness rule

Every condition has two exports:

1. Natural-Level Render, preserving the condition's configured gain staging.
2. Level-Matched Evaluation Render, matched to condition A with BS.1770 integrated
   loudness in the evaluation exporter only.

The manifest records pre/post loudness, applied gain, peak, and headroom limiting.
The existing RMS stage remains unchanged in legacy mode and is itself factor C.

## Stage tickets

### FEX0-01 — Experimental profile contract

- Add strict defaults and allowed values for the five requested controls.
- Preserve old profile loading and old V2 audio/diagnostics in default mode.
- Reserve `direct_ratio_mode = distance_curve` behind the frozen FEX-2 gate.

### FEX0-02 — Reproducible baseline harness

- Validate the pinned corpus without storing its absolute root.
- Generate 28 frontal probe cases: `0°, ±5°, ±10°, ±20°` crossed with
  `0.5, 1.0, 1.6, 2.5 m`.
- Render deterministic pink-noise and short-transient probes plus the four pinned
  screening excerpts.
- Record canonical parameters, content/output hashes, measured SOFA hash, renderer
  diagnostics, and revision identity.

### FEX0-03 — Baseline gate

- Run targeted and complete tests.
- Verify no legacy V3.2 source file changed and its regression tests pass.
- Produce the external baseline bundle and reproducible command.
- Stop for stage acceptance before FEX-1.

Accepted on 2026-08-18: all four stereo excerpts were suitable, the frontal
voice remained reproducibly close/under-spatialized, and no click, dropout,
channel reversal, clipping, or abnormal level was reported. This is confirmation
of the baseline problem, not evidence of an externalization improvement.

Reproduce the FEX-0 bundle without placing local roots in its manifest:

```bash
python run_frontal_externalization_eval.py \
  --library-root /path/to/audio-library \
  --sofa /path/to/measured-listener.sofa \
  --output-dir /path/to/new-or-empty/fex0-baseline \
  --source-revision <git-commit>
```

The result contains 56 engineering probes and four complete-stereo screening
excerpts. This is condition A only; FEX-0 intentionally does not render or judge
the B–F perceptual conditions.

### FEX1-01 — Single-factor screening

- Render A–E as Natural-Level and Level-Matched copies on all four excerpts.
- Blind-rate externalization, perceived distance, center stability, vocal clarity,
  timbre naturalness, double-image, and overall preference.
- Reject conditions with meaningful utility regressions.

Implemented as the fixed `render_fex1_screening` interface and the standalone
`run_frontal_externalization_fex1.py` adapter. The condition profiles are owned
by the exporter and cannot be replaced by a caller-provided profile. This keeps
A–E causal and prevents accidental tuning drift.

### FEX1-02 — Interaction screening

- Render required F and an accepted-factor-only combination if those differ.
- Treat louder, darker, or wider-only changes as confounds, not success.

F is exported together with A–E but remains an interaction diagnostic. It is not
eligible for maturity merely because it differs more strongly from A.

### FEX1-03 — Research maturity

- Render only surviving conditions on all three complete stereo tracks.
- Require at least two blind-listening rounds with a stable cross-track conclusion.
- Keep all production defaults unchanged. Promotion is a separate later decision
  and does not automatically unfreeze FEX-2/FEX-3/FEX-4.

## Open decisions after FEX-0

- Which single factors survive blind excerpt screening.
- Whether F or an accepted-only combination is worth full-track validation.
- Whether FEX-1 reaches research maturity.

No FEX-2/FEX-3/FEX-4 design decision is open during this workstream.

## Reproduce FEX-1 excerpt screening

```bash
python run_frontal_externalization_fex1.py \
  --library-root /path/to/audio-library \
  --sofa /path/to/measured-listener.sofa \
  --output-dir /path/to/new-or-empty/fex1-screening \
  --source-revision <git-commit>
```

The bundle contains 24 blind condition/excerpt pairs and 48 float WAV files:
one Natural-Level Render and one Level-Matched Evaluation Render per pair.
`manifest.json` records parameters, hashes, natural/matched BS.1770 loudness,
applied gain, sample peak, and any shared headroom attenuation. `answer_key.json`
must stay closed until ratings are complete. `listening_form.json` contains the
seven required rating dimensions; level-matched trials are primary and natural-
level trials are only a loudness-confound check. Do not inspect `diagnostics/`
before rating because renderer fields can reveal the hidden condition.

FEX-1 is not mature at export time. Maturity still requires two blind listening
rounds with a stable cross-track conclusion and no important center-stability,
clarity, timbre, double-image, or mono regression. Full-track rendering is not
performed until excerpt screening selects survivors.

The first screening bundle was generated from source revision `f0dc2884` with
content hash `2749d3179db81e910a20be2d0c388cdc1dc9b4692bfad1c5ef1167f224e80247`.
Its 24 level-matched trials differ by at most `0.00000001 LU` within each
excerpt. This confirms evaluation-level equality only; it is not perceptual
evidence for any condition.
