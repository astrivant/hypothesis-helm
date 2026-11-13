"""
Check retained work graph artifact freshness without private runtime dependencies.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
from pathlib import Path


def test_receipt_detects_stale_work_graph(tmp_path: Path) -> None:
    """
    Reject a changed source or generated graph before pre-commit and CI succeed.

    Args:
        tmp_path (Path): Isolated project with a synthetic reviewed graph.

    Returns:
        None: Matching hashes pass, while an altered input fails with a diagnostic.
    """
    project = Path(__file__).resolve().parents[2]
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy2(project / "scripts/check-work-graphs.sh", scripts)
    directory = tmp_path / ".github/review-evidence/example"
    directory.mkdir(parents=True)
    paths = [directory / name for name in ("work.json", "work.md", "work.mmd")]
    for path in paths:
        path.write_text(f"synthetic {path.name}\n")
    receipt = "".join(f"{hashlib.sha256(path.read_bytes()).hexdigest()}  {path.relative_to(tmp_path)}\n" for path in paths)
    (directory / "work.sha256").write_text(receipt)
    command = ["bash", str(scripts / "check-work-graphs.sh"), "--debug"]
    success = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert success.returncode == 0, success.stderr
    assert "INFO: Checking 1 work graph receipts" in success.stderr
    assert "DEBUG: Checking" in success.stderr
    paths[0].write_text("changed input\n")
    failure = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert failure.returncode != 0
    assert "stale or incomplete" in failure.stderr
