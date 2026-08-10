# Repository Rules

- Read `PROJECT_HANDOFF.md`, `.codex/REPO_GUIDE.md`, and `.codex/source_index.txt` before broad exploration.
- Preserve the deterministic legacy `[LF, RF, LB, RB]` renderer as the default. Spatial Core V2 is the unified opt-in object/FOA core; the separate Pseudo-Object repository is reference material only.
- Treat Phase 5A V3.2 as a frozen listening baseline. New tuning must use a separate candidate path instead of mutating V3.2 in place.
- Keep experimental rear-content, V3.1, and V3.2 paths disabled by default unless the task explicitly changes promotion status.
- Keep measured SOFA mandatory for V2 binaural; never add a procedural HRTF fallback or bundled listener dataset.
- Do not reintroduce retired-company identifiers, prefixes, or compatibility aliases. The text-integrity check enforces the blocked naming across content and paths.
- Do not scan or commit audio, generated output, virtual environments, caches, or local workspace data.
- Make the smallest focused change and run the relevant pytest file(s); use `python -m pytest -q` for broad DSP changes.
- Check `git status -sb` before editing and preserve unrelated local changes.
