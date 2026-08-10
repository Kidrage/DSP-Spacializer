import subprocess
import sys
from pathlib import Path

from scripts.check_text_integrity import check_retired_identifiers


ROOT = Path(__file__).resolve().parents[1]


def test_text_integrity_script_passes():
    subprocess.run(
        [sys.executable, "scripts/check_text_integrity.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )


def test_retired_identifier_guard_checks_any_content_type_and_case(tmp_path):
    token = "B" + "DS"
    config = tmp_path / "settings.toml"
    config.write_text(f'owner = "{token}"\n', encoding="utf-8")

    issues = check_retired_identifiers(config, tmp_path)

    assert any("contains a retired-company identifier" in issue for issue in issues)


def test_retired_identifier_guard_checks_file_names(tmp_path):
    token = "b" + "ds"
    artifact = tmp_path / f"legacy_{token}.bin"
    artifact.write_bytes(b"clean")

    issues = check_retired_identifiers(artifact, tmp_path)

    assert any("path contains a retired-company identifier" in issue for issue in issues)
