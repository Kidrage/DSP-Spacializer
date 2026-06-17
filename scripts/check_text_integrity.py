#!/usr/bin/env python3
"""Check text newline and basic line integrity for repository text files."""

from __future__ import annotations

import sys
from pathlib import Path


TEXT_EXTENSIONS = {".py", ".md", ".json", ".yml", ".yaml", ".txt", ".sh"}
SKIP_DIRS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "outputs",
    "input_audio",
    ".ipynb_checkpoints",
}
MAX_LINE_LENGTH = 300


def _looks_like_url_line(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith(("http://", "https://")) or "http://" in stripped or "https://" in stripped


def iter_text_files(root: Path):
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() in TEXT_EXTENSIONS:
            yield path


def check_file(path: Path, root: Path) -> list[str]:
    rel = path.relative_to(root)
    data = path.read_bytes()
    issues: list[str] = []
    if b"\r" in data:
        issues.append(f"{rel}: contains CR byte; expected LF-only newlines")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        issues.append(f"{rel}: not valid UTF-8 text ({exc})")
        return issues

    lines = text.split("\n")
    if lines and lines[-1] == "":
        logical_lines = lines[:-1]
    else:
        logical_lines = lines

    for index, line in enumerate(logical_lines, start=1):
        if len(line) > MAX_LINE_LENGTH and not _looks_like_url_line(line):
            issues.append(
                f"{rel}:{index}: line length {len(line)} exceeds {MAX_LINE_LENGTH} characters"
            )

    if path.suffix.lower() == ".py" and len(logical_lines) <= 1 and len(text.strip()) > 80:
        issues.append(f"{rel}: Python module appears compressed into {len(logical_lines)} line(s)")
    return issues


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    all_issues: list[str] = []
    checked = 0
    for path in iter_text_files(root):
        checked += 1
        all_issues.extend(check_file(path, root))

    if all_issues:
        print("Text integrity check failed:")
        for issue in all_issues:
            print(f"  - {issue}")
        return 1

    print(f"Text integrity check passed: {checked} files checked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
