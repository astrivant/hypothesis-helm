"""
Exercise the remote-job scripts locally with real application shard reports.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_remote_jobs_aggregate_idle_shards(tmp_path: Path) -> None:
    """
    Run three VM-shaped jobs on a two-path chart and require every shard during aggregation.

    Args:
        tmp_path (Path): Local stand-in for independent VM artifact directories.

    Returns:
        None: Idle shards aggregate successfully while a missing report is rejected.
    """
    project = Path(__file__).resolve().parents[3]
    chart = tmp_path / "chart"
    shutil.copytree(project / "examples/configmap", chart)
    run = tmp_path / "run"
    run.mkdir()
    collected = tmp_path / "collected"
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "RUN_ROOT": str(run),
        "HH_RUN_ID": "remote-shard-test",
        "SHARD_TOTAL": "3",
        "JOBS": "1",
        "SEED": "2026",
        "HH_CHART": str(chart),
        "LOCAL_RESULTS": str(collected),
        "CI": "true",
    }
    for index in range(1, 4):
        results = collected / "shards" / f"vm-{index}" / "results"
        results.mkdir(parents=True)
        subprocess.run(
            ["bash", str(project / "ansible/jobs/chart-tests.sh")],
            env={**environment, "SHARD_INDEX": str(index), "RESULTS_DIR": str(results), "CACHE_DIR": str(tmp_path / f"cache-{index}")},
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )
    aggregate = subprocess.run(
        ["bash", str(project / "ansible/jobs/aggregate-tests.sh")],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert aggregate.returncode == 0, aggregate.stdout + aggregate.stderr
    final = json.loads((collected / "final/report.json").read_text())
    assert final["run_id"] == "remote-shard-test"
    assert len(final["shards"]) == 3
    reports = list(collected.glob("shards/*/results/artifacts/shards/*/report.json"))
    assert len(reports) == 3
    assert any(json.loads(path.read_text())["shard"]["selected"] == 0 for path in reports)
    reports[0].unlink()
    incomplete = subprocess.run(
        ["bash", str(project / "ansible/jobs/aggregate-tests.sh")],
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert incomplete.returncode != 0
