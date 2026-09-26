"""
Verify release tags and artifact versions without building or publishing distributions.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from hypothesis_helm.tests import PROJECT_ROOT


@pytest.mark.parametrize(
    ("package", "tag", "expected"),
    [
        ("1.3.0", "v1.3.0", "1.3.0"),
        ("1.3.0a0", "v1.3.0-alpha", "1.3.0a0"),
        ("1.3.0a1", "v1.3.0-alpha.1", "1.3.0a1"),
        ("1.3.0b2", "v1.3.0-beta.2", "1.3.0b2"),
        ("1.3.0rc0", "v1.3.0-rc", "1.3.0rc0"),
        ("1.3.0rc1", "v1.3.0-rc.1", "1.3.0rc1"),
        ("1.3.0rc1", "v1.3.0rc1", "1.3.0rc1"),
        ("1.3.0-alpha.1", "v1.3.0-alpha.1", "1.3.0a1"),
        ("1.3.0-alpha.1", None, "1.3.0a1"),
        ("1.3.0", "v1.3.0-rc.1", "1.3.0rc1"),
        ("1.3.0rc1", "v1.3.0", "1.3.0"),
        ("1.3.0a1", "v1.3.0-alpha.2", "1.3.0a2"),
        ("1.3.0", "v1.4.0", "1.4.0"),
        ("1.3.0", "v1.3.4", "1.3.4"),
        ("1.3.0", None, "1.3.0"),
        ("1.3.0", "1.3.0", None),
        ("1.3.0", "v1.3", None),
        ("1.3.0", "v1.3.0-invalid", None),
        ("1.3.0+local", "v1.3.0+local", None),
    ],
)
def test_release_version(tmp_path: Path, package: str, tag: str | None, expected: str | None) -> None:
    """
    Use release tags as authoritative versions and reject unsupported tag syntax.

    Args:
        tmp_path (Path): Isolated project metadata and GitHub output file.
        package (str): Declared Poetry version.
        tag (str | None): Release tag or ordinary branch build.
        expected (str | None): Canonical version, or None when validation must fail.

    Returns:
        None: Valid tags override checkout versions; branches retain their declared version.
    """
    project = PROJECT_ROOT
    (tmp_path / "pyproject.toml").write_text(f'[tool.poetry]\nversion = "{package}"\n')
    output = tmp_path / "github-output"
    command = [sys.executable, str(project / ".github/release-version.py"), "--output", str(output)]
    if tag is not None:
        command.extend(["--tag", tag])
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
    if expected is None:
        assert result.returncode != 0
        assert not output.exists()
    else:
        assert result.returncode == 0, result.stderr
        assert output.read_text() == f"version={expected}\n"
