"""
Verify the shared local and CI pull-request test environment.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def test_runner_isolates_provider_context(tmp_path: Path) -> None:
    """
    Run a real child test with a synthetic event and no inherited provider tokens.

    Args:
        tmp_path (Path): Temporary pytest source outside the repository.

    Returns:
        None: The child receives the committed event and bounded diagnostics.
    """
    project = Path(__file__).resolve().parents[2]
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    (frozen / "frozen_marker.py").write_text("value = 'frozen'\n")
    case = tmp_path / "test_event.py"
    case.write_text(
        "import json, os, frozen_marker\n"
        "from pathlib import Path\n"
        "from scripts.release.attest import fingerprint\n"
        "def test_event():\n"
        "    event = json.loads(Path(os.environ['GITHUB_EVENT_PATH']).read_text())\n"
        "    assert os.environ['GITHUB_EVENT_NAME'] == 'pull_request'\n"
        "    assert os.environ['GITHUB_REPOSITORY'] == 'example/example'\n"
        "    assert event['pull_request']['base']['ref'] == 'main'\n"
        "    assert 'CIRCLECI' not in os.environ\n"
        "    assert 'GITHUB_TOKEN' not in os.environ and 'GH_TOKEN' not in os.environ\n"
        "    assert callable(fingerprint)\n"
        "    assert frozen_marker.value == 'frozen'\n"
    )
    environment = {
        **os.environ,
        "CIRCLECI": "true",
        "GITHUB_TOKEN": "synthetic-token",
        "GH_TOKEN": "synthetic-token",
        "PYTHONPATH": str(frozen),
    }
    result = subprocess.run(
        ["bash", "scripts/run-pr-tests.sh", "--debug", "-q", str(case)],
        cwd=project,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "INFO: Running pytest" in result.stderr
    assert "DEBUG: Provider coordinates" in result.stderr
    assert "synthetic-token" not in result.stdout + result.stderr
