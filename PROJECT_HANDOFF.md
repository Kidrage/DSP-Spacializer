# Project Handoff

> Deterministically generated repository/project memory for cross-agent handoff.
> Update after every material project change and before final reporting.

## Repository Identity

- Repository ID: `dsp-spatializer-b2190f40dadb`
- Working root: `.`
- Repository name: `dsp-spatializer`
- Git repository: `true`
- Generated at: `2026-08-14T03:55:53.329324+00:00`

## Current State

- Branch: `feat/spatial-scene-package-v01`
- HEAD: `5b8ef3f`
- Indexed paths: 128
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
| `.` | 46 |
| `tests` | 27 |
| `spatial_core` | 16 |
| `docs` | 8 |
| `web_ui` | 5 |
| `.codex` | 4 |
| `config` | 4 |
| `examples` | 4 |
| `scripts` | 4 |
| `spatial_mixer` | 4 |
| `profiles` | 3 |
| `web_ui/static` | 3 |
| `.github` | 1 |
| `.github/workflows` | 1 |
| `input_audio` | 1 |
| `schemas` | 1 |

## Data and File Structure

### Categories

- code: 83 files, 552636 bytes
- literature: 28 files, 214683 bytes
- other: 5 files, 99136 bytes
- structured_data: 12 files, 16192 bytes

### Common Extensions

- `.py`: 82
- `.md`: 25
- `.json`: 8
- `.yml`: 4
- `.txt`: 3
- `[no extension]`: 2
- `.ipynb`: 1
- `.js`: 1
- `.html`: 1
- `.css`: 1

### Schema / Model / Interface Candidates

- `schemas/spatial_scene_package-0.1.schema.json`

## Key Entrypoints and Guides

- `AGENTS.md`
- `CLAUDE.md`
- `README.md`
- `input_audio/README.md`
- `requirements.txt`

## Change History

- `5b8ef3f 2026-08-14 feat: define spatial scene package v0.1`
- `c9e5070 2026-08-11 Merge pull request #9 from Kidrage/feat/seven-zone-calibration-mixer`
- `82bdbb7 2026-08-11 docs: refresh seven-zone mixer handoff`
- `73af3f4 2026-08-11 fix: harden blind calibration workflow`
- `83ba9ee 2026-08-11 feat: add seven-zone calibration mixer`
- `d87b54a 2026-08-11 Merge pull request #8 from Kidrage/fix/clarity-gate-nonfinite`
- `d5b016a 2026-08-11 docs: refresh clarity-gate handoff`
- `5fe5c77 2026-08-11 fix: fail closed on invalid clarity metrics`
- `1c5b8f6 2026-08-11 Merge pull request #7 from Kidrage/feat/spatial-core-v2p1-depth-clarity`
- `5e54902 2026-08-11 docs: refresh promotion-contract handoff`
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

## Current Changes

- `## feat/spatial-scene-package-v01`

## Related Repositories

### Remotes

- `origin github.com:Kidrage/DSP-Spacializer.git (fetch)`
- `origin github.com:Kidrage/DSP-Spacializer.git (push)`

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
- `docs/ARCHITECTURE_AND_SIGNAL_FLOW.md`
- `docs/BRANCH_STRATEGY.md`
- `docs/FEEDBACK_LOOP.md`

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
- `profiles/spatial_mixer_universal_default.json`
- `schemas/spatial_scene_package-0.1.schema.json`
- `spatial_quality_thresholds.json`

## Validation and Risks

- This inventory records paths and metadata, not semantic correctness.
- Binary/media payloads and secrets were not read.
- Validate current branch, tests, and interfaces before modifying files.

## Agent Notes

<!-- AGENT_NOTES_START -->
- 2026-08-14: branch `feat/spatial-scene-package-v01` documents the complete
  legacy/V2 production chain and parameter surface, then adds the strict
  `spatial_scene_package/0.1` JSON Schema, synthetic example generator, and a
  public directory/ZIP conformance validator. The package preserves seven
  independent 48 kHz float WAV zones; FOA remains a derived runtime bed.
- This milestone does not change DSP rendering, import packages into
  `SpatialScene`, or implement the six registered fixed-layout renderers.
  ADM/IAB conversion and consumer distribution coding remain later adapters.
- Validation for this milestone: 156 pytest tests, targeted Ruff, naming
  integrity, and `git diff --check` passed. No audio assets are committed.
- The generated HEAD field intentionally records the last material code commit;
  the canonical handoff is committed immediately afterward in a docs-only
  commit, avoiding a recursive self-hash requirement.
- 2026-08-11: commits `83ba9ee` and `73af3f4` add the opt-in seven-zone
  calibration mixer, strict `spatial_mixer_profile/1.0`, local web console, and
  offline `--mixer-profile` render path. Legacy rendering remains unchanged.
- The universal campaign pins nine tracks across six content classes. Blind
  versions share one Web Audio clock; server manifests bind track, excerpt,
  accepted/draft hashes, monitor, audition state, objective gate, and resolved
  choice. The client cannot submit objective evidence.
- Promotion requires all nine pinned comparisons. A red objective gate remains
  visible and requires a written reason retained in immutable evidence. This
  explicit, auditable override supersedes the earlier experimental all-pass
  requirement; it does not silently turn a failed metric into a pass.
- The console includes waveform display, four direct-object strips, three FOA
  field strips, room controls, monitor-only EQ, and an Extraction Lab with
  seven-zone Solo, RMS, 36-band spectra, and complementary reconstruction check.
- Real-library validation found 37 tracks and pinned the intended nine. A real
  measured-SOFA three-second preview completed in about 2.1 seconds; REF,
  version 1, version 2, static assets, and Extraction Lab endpoints returned 200.
- Generated campaign state and preview audio remain external at
  `/Users/saintpeter/Desktop/Coding/spatializer_outputs/spatial_mixer_calibration/`.
  The local console is available at `http://127.0.0.1:8765` while the launcher
  process remains running.
- Validation: 143 pytest tests, focused Ruff, JavaScript syntax,
  text-integrity, `git diff --check`, HTTP endpoint checks, and a 1440 x 1100
  Chrome screenshot passed. Whole-repository Ruff still reports nine unrelated
  pre-existing findings in legacy files and the old notebook schema.
<!-- AGENT_NOTES_END -->

## Mandatory Update Rule

Refresh canonical PROJECT_HANDOFF.md after branch, commit, file, directory, schema, interface,
related-repository, or material project-state changes, and before final handoff.
