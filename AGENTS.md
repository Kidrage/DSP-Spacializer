# Repository Rules

- Read `PROJECT_HANDOFF.md`, `.codex/REPO_GUIDE.md`, and `.codex/source_index.txt` before broad exploration.
- Preserve the deterministic fixed-channel `[LF, RF, LB, RB]` renderer; pseudo-object work belongs in the separate Pseudo-Object repository.
- Treat Phase 5A V3.2 as a frozen listening baseline. New tuning must use a separate candidate path instead of mutating V3.2 in place.
- Keep experimental rear-content, V3.1, and V3.2 paths disabled by default unless the task explicitly changes promotion status.
- Do not scan or commit audio, generated output, virtual environments, caches, or local workspace data.
- Make the smallest focused change and run the relevant pytest file(s); use `python -m pytest -q` for broad DSP changes.
- Check `git status -sb` before editing and preserve unrelated local changes.
