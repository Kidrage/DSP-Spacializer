# Project Handoff

> Deterministically generated repository/project memory for cross-agent handoff.
> Update after every material project change and before final reporting.

## Repository Identity

- Repository ID: `dsp-spatializer-32f0bd60890c`
- Working root: `.`
- Repository name: `dsp-spatializer`
- Git repository: `true`
- Generated at: `2026-08-11T04:52:32.816395+00:00`

## Current State

- Branch: `feat/spatial-core-v2p1-depth-clarity`
- HEAD: `b094a4b`
- Indexed paths: 105
- Inventory truncated: `false`
- Inaccessible paths: 0
- Scan mode: complete path/metadata inventory; no bulk content read; no symlink traversal.

## Project Progress Dashboard

- Current progress: derive from branch, HEAD, current changes, and manual Agent Notes below.
- Work already changed: see Change History and Current Changes.
- Active work: any dirty Git status entries listed under Current Changes.
- Remaining work / ETA: maintain in Agent Notes when it cannot be inferred deterministically.
- Pending decisions: maintain in Agent Notes and refresh before final reporting.
- Pending files / plans / acceptance artifacts: maintain in Agent Notes and task run ledgers.
- Fast reporting source: this canonical root file; use the shared mirror only when explicitly written.

## Active Work and Pending Items

- In progress: inspect Current Changes and Agent Notes.
- Pending decisions: record durable choices in Agent Notes before handoff.
- Pending files to modify: record intended paths in Agent Notes before dispatch.
- Pending plans to confirm: link task/run plans in Agent Notes.
- Pending acceptance artifacts: link deliverables and validation evidence in Agent Notes.
- Next safe entry point: run `./agentlab.sh repository-handoff --repo <path>` before deep work.

## Directory Routes

| Route | Files |
|---|---:|
| `.` | 45 |
| `tests` | 22 |
| `spatial_core` | 15 |
| `.codex` | 4 |
| `config` | 4 |
| `docs` | 4 |
| `scripts` | 4 |
| `examples` | 3 |
| `profiles` | 2 |
| `.github` | 1 |
| `.github/workflows` | 1 |
| `input_audio` | 1 |

## Data and File Structure

### Categories

- code: 68 files, 415504 bytes
- literature: 24 files, 174394 bytes
- other: 3 files, 81607 bytes
- structured_data: 10 files, 7076 bytes

### Common Extensions

- `.py`: 68
- `.md`: 21
- `.json`: 6
- `.yml`: 4
- `.txt`: 3
- `[no extension]`: 2
- `.ipynb`: 1

### Schema / Model / Interface Candidates

- None detected.

## Key Entrypoints and Guides

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `input_audio/README.md`
- `requirements.txt`

## Change History

- `b094a4b 2026-08-11 fix: enforce Spatial Core promotion contracts`
- `3b1d086 2026-08-11 docs: refresh Spatial Core V2.1 handoff`
- `d03efea 2026-08-11 fix: address Spatial Core V2.1 review findings`
- `8566d3f 2026-08-11 feat: add Spatial Core V2.1 clarity and depth`
- `8e4041f 2026-08-11 Merge pull request #6 from Kidrage/fix/binaural-timbre-preservation`
- `1831844 2026-08-11 docs: refresh binaural fix handoff`
- `98d462b 2026-08-11 test: preserve binaural interaural cues`
- `823d5bb 2026-08-11 fix: preserve binaural timbre and gain staging`
- `f57595b 2026-08-10 Merge pull request #5 from Kidrage/chore/remove-retired-branding`
- `bb467fa 2026-08-10 docs: refresh naming-isolation handoff`
- `d844183 2026-08-10 test: block retired identifiers in every file type`
- `8fb191c 2026-08-10 refactor: remove retired company identifiers`
- `4cf12cc 2026-08-10 Merge pull request #4 from Kidrage/feat/spatial-core-v2-s1`
- `954ffa0 2026-08-10 docs: refresh Spatial Core handoff`
- `77dec30 2026-08-10 fix: tighten Spatial Core V2 rendering contracts`
- `8a95fc0 2026-08-10 feat: expose opt-in Spatial Core V2 workflow`
- `dc11cff 2026-08-10 feat: add SOFA binaural and quad speaker renderers`
- `0aca659 2026-08-10 feat: add Spatial Core V2 scene format and FOA builder`
- `0701a0a 2026-08-10 Merge pull request #3 from Kidrage/feat/dsp-feedback-loop-s1`
- `071435b 2026-08-10 chore: add repository onboarding and CI`

## Current Changes

- `## feat/spatial-core-v2p1-depth-clarity`

## Related Repositories

### Remotes

- `origin https://github.com/Kidrage/DSP-Spacializer.git (fetch)`
- `origin https://github.com/Kidrage/DSP-Spacializer.git (push)`

### Submodules

- None detected.

## Media and Literature Routes

### literature

- `.codex/MAINLINE.md`
- `.codex/REPO_GUIDE.md`
- `.codex/repo_files.txt`
- `.codex/source_index.txt`
- `AGENTS.md`
- `CLAUDE.md`
- `DSP-Spacializer_auto_acoustic_闭环改造阶段性报告.md`
- `DSP-Spacializer_使用说明与详细介绍.md`
- `DSP-Spacializer_阶段性开发报告.md`
- `DSP空间化迭代方案.md`
- `HANDOFF_2026-06-23_session_changelog.md`
- `HANDOFF_DSP_SPATIALIZER_S2_LIBRARY_AB_PROFILE_LOOP.md`
- `HANDOFF_auto_acoustic_closed_loop_upgrade.md`
- `Handoff.md`
- `PROJECT_HANDOFF.md`
- `README.md`
- `config/calibration_evidence.md`
- `docs/BRANCH_STRATEGY.md`
- `docs/FEEDBACK_LOOP.md`
- `docs/REPOSITORY_STATUS.md`

### image

- None detected.

### audio

- None detected.

### video

- None detected.

### structured_data

- `.github/workflows/test.yml`
- `config/listener_threshold_calibration.yml`
- `config/quality_thresholds.yml`
- `config/refine_thresholds.yml`
- `examples/listener_trajectory_example.json`
- `examples/quad_layout_example.json`
- `examples/subjective_score_example.json`
- `profiles/quad_4p0_feedback_example.json`
- `profiles/spatial_core_balanced_depth.json`
- `spatial_quality_thresholds.json`

## Validation and Risks

- This inventory records paths and metadata, not semantic correctness.
- Binary/media payloads and secrets were not read.
- Validate current branch, tests, and interfaces before modifying files.

## Agent Notes

<!-- AGENT_NOTES_START -->
- The generated HEAD field intentionally records the last material code commit;
  the canonical handoff is committed immediately afterward in a docs-only
  commit, avoiding a recursive self-hash requirement.
- 2026-08-11: Spatial Core V2 binaural now applies one bounded frontal
  common-field correction to both ears, amplitude-normalizes coherent size
  rays, and uses the linked local limiter. Legacy rendering remains unchanged.
- Fixed listening renders and their spectral/limiter evidence are external at
  `/Users/saintpeter/Desktop/Coding/spatializer_outputs/spatial_core_v2_candidates_fixed/`;
  audio remains untracked by repository policy.
- Validation at `98d462b`: 91 pytest tests and focused Ruff checks passed; the
  measured KEMAR equal-tone check is within 1.7 dB of 1 kHz from 50 Hz to 8 kHz.
- 2026-08-11: V2.1 adds lossless seven-zone M/S construction, a strict compact
  profile, the opt-in geometry-based `balanced-depth` room, minimum-phase
  common-field correction, and post-sum mastered-RMS matching constrained by
  peak headroom. Legacy, scene-manifest, `small-dry`, and `off` paths remain
  compatible.
- Reviewed three-track listening renders and evidence are external at
  `/Users/saintpeter/Desktop/Coding/spatializer_outputs/spatial_core_v2p1_candidates_reviewed/`;
  generated audio remains untracked. All files are 48 kHz stereo float WAV,
  and the limiter is inactive for all three after peak-aware gain matching.
- Validation: 123 pytest tests, focused Ruff, text-integrity, and
  `git diff --check` pass. The objective clarity gate remains RED: all three
  exceed the 1 dB M/S-balance delta; the wide orchestral candidate also fails
  crest, low-mid, and presence thresholds. These are audition candidates, not
  promoted defaults. The promotion evaluator now requires an explicit
  objective-clarity pass for every paired track.
<!-- AGENT_NOTES_END -->

## Mandatory Update Rule

Refresh canonical PROJECT_HANDOFF.md after branch, commit, file, directory, schema, interface,
related-repository, or material project-state changes, and before final handoff.
