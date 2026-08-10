# Project Handoff

> Deterministically generated repository/project memory for cross-agent handoff.
> Update after every material project change and before final reporting.

## Repository Identity

- Repository ID: `dsp-spatializer-32f0bd60890c`
- Working root: `.`
- Repository name: `dsp-spatializer`
- Git repository: `true`
- Generated at: `2026-08-10T06:33:02.943802+00:00`

## Current State

- Branch: `feat/dsp-feedback-loop-s1`
- HEAD: `647e724`
- Indexed paths: 76
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
| `tests` | 13 |
| `config` | 4 |
| `scripts` | 4 |
| `.codex` | 3 |
| `docs` | 3 |
| `.github` | 1 |
| `.github/workflows` | 1 |
| `examples` | 1 |
| `input_audio` | 1 |
| `profiles` | 1 |

## Data and File Structure

### Categories

- code: 44 files, 286601 bytes
- literature: 22 files, 159841 bytes
- other: 3 files, 81607 bytes
- structured_data: 7 files, 6164 bytes

### Common Extensions

- `.py`: 44
- `.md`: 19
- `.yml`: 4
- `.txt`: 3
- `.json`: 3
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

- `647e724 2026-06-29 Freeze Phase 5A V3.2 stable baseline`
- `1fd9d4c 2026-06-24 implement Phase 5A listening candidates and calibration`
- `65d65d5 2026-06-18 docs: update README with bilingual feedback loop guide`
- `b4a3ad1 2026-06-18 docs(feedback): add feedback loop commands to README`
- `a7036a0 2026-06-18 docs(feedback): describe suggestion loop closure`
- `084cc8c 2026-06-18 test(feedback): cover profile suggestion rules`
- `3be4a85 2026-06-18 feat(feedback): add tuning profile suggestion CLI`
- `dc16e88 2026-06-18 feat(feedback): suggest tuning profiles from evaluation records`
- `d76b53f 2026-06-18 docs(feedback): document DSP feedback loop`
- `13b9f28 2026-06-18 test(feedback): cover subjective evaluation records`
- `c57ca15 2026-06-18 test(feedback): cover tuning profile overlay`
- `8eda176 2026-06-18 feat(feedback): add feedback render entrypoint`
- `839c8a1 2026-06-18 docs(feedback): add subjective score example`
- `9e8ffb0 2026-06-18 docs(feedback): add example tuning profile`
- `b7448ee 2026-06-18 feat(feedback): add subjective score records`
- `906c946 2026-06-18 feat(feedback): add tuning profile overlay`
- `a59fcf1 2026-06-18 chore: remove local agent metadata`
- `699098b 2026-06-18 docs: document pseudo-object repository split`
- `89a31c6 2026-06-18 Merge pull request #2 from Kidrage/main-cleanup-legacy-4ch-r0b`
- `f33465e 2026-06-18 Clean main legacy spatializer path`

## Current Changes

- `## feat/dsp-feedback-loop-s1...origin/feat/dsp-feedback-loop-s1`
- `?? .codex/`
- `?? .github/`
- `?? AGENTS.md`
- `?? PROJECT_HANDOFF.md`

## Related Repositories

### Remotes

- `origin https://github.com/Kidrage/DSP-Spacializer.git (fetch)`
- `origin https://github.com/Kidrage/DSP-Spacializer.git (push)`

### Submodules

- None detected.

## Media and Literature Routes

### literature

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
- `input_audio/README.md`

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
- `examples/subjective_score_example.json`
- `profiles/quad_4p0_feedback_example.json`
- `spatial_quality_thresholds.json`

## Validation and Risks

- This inventory records paths and metadata, not semantic correctness.
- Binary/media payloads and secrets were not read.
- Validate current branch, tests, and interfaces before modifying files.

## Agent Notes

<!-- AGENT_NOTES_START -->
- Add durable decisions, constraints, or cross-agent context here.
<!-- AGENT_NOTES_END -->

## Mandatory Update Rule

Refresh canonical PROJECT_HANDOFF.md after branch, commit, file, directory, schema, interface,
related-repository, or material project-state changes, and before final handoff.
