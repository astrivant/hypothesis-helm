"""
Exercise the retained full-refresh recipes with isolated repositories and native workers.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
def test_refresh_repository_recipe(tmp_path: Path) -> None:
    """
    Verify fresh initialization, worker findings, aggregation, and missing-worker rejection.

    Args:
        tmp_path (Path): Isolated checkout, source repositories, and refresh outputs.

    Returns:
        None: Both repository reports retain findings and incomplete work cannot replace a report.
    """
    if shutil.which("helm") is None or shutil.which("parallel") is None:
        pytest.skip("Helm 4 and GNU Parallel are required")
    version = subprocess.check_output(["helm", "version", "--short"], text=True)
    if not version.startswith("v4."):
        pytest.skip("The full refresh requires Helm 4")
    project = Path(__file__).resolve().parents[3]
    (tmp_path / "pkg").symlink_to(project / "pkg", target_is_directory=True)
    for name in ("bitnami-charts", "prometheus-community-helm-charts"):
        source = tmp_path / "third_party" / name
        shutil.copytree(project / "examples/broken", source / "charts/broken")
        subprocess.run(["git", "init", str(source)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(source), "add", "."], check=True, capture_output=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.org",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "-m",
                "Fixture",
            ],
            check=True,
            capture_output=True,
        )
    environment = dict(os.environ, PYTHONPATH=str(project / "pkg"), PATH=f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}")
    run_root = Path(".cache/benchmark-refresh-1234")
    initialized = subprocess.run(
        [sys.executable, str(project / "docs/benchmarks/refresh/initialize.py"), str(run_root)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    assert (tmp_path / ".cache/latest-refresh.txt").read_text().strip() == str(run_root)
    snapshot = tmp_path / run_root / "frozen-source"
    for name, expected in json.loads((tmp_path / run_root / "measured-source-hashes.json").read_text()).items():
        assert hashlib.sha256((snapshot / name).read_bytes()).hexdigest() == expected
    environment["PYTHONPATH"] = str(snapshot / "pkg")
    for name in ("bitnami", "prometheus"):
        run = Path(f"docs/reports/{name}-runs/{name}-charts_1234")
        result = subprocess.run(["bash", str(run / "run.sh"), str(run)], cwd=tmp_path, env=environment, capture_output=True, check=False)
        assert result.returncode == 1, result.stdout + result.stderr
        finalized = subprocess.run(
            [sys.executable, str(run / "finalize.py"), str(run), name],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )
        assert finalized.returncode == 0, finalized.stdout + finalized.stderr
        report = tmp_path / "docs/reports" / f"{name}.pdf"
        assert report.read_bytes().startswith(b"%PDF")
        verified = json.loads((tmp_path / run / "verification.json").read_text())
        assert verified["completed_jobs"] == verified["expected_charts"] == 1
        assert verified["attempts"] > 0
        original_pdf = report.read_bytes()
        (tmp_path / run / "jobs/1.json").unlink()
        incomplete = subprocess.run(
            [sys.executable, str(run / "finalize.py"), str(run), name],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            check=False,
        )
        assert incomplete.returncode != 0
        assert report.read_bytes() == original_pdf
