"""
Exercise application shard execution and complete aggregation through the public CLI.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from hypothesis_helm.tests import PROJECT_ROOT


@pytest.mark.integration
@pytest.mark.skipif(shutil.which("helm") is None, reason="requires Helm")
def test_application_jobs_aggregate_idle_shards(tmp_path: Path) -> None:
    """
    Run three independent jobs on a two-path chart and require every shard report.

    Args:
        tmp_path (Path): Local stand-in for independent Actions artifact directories.

    Returns:
        None: An idle shard aggregates successfully, while its missing report is rejected.
    """
    chart = tmp_path / "chart"
    shutil.copytree(PROJECT_ROOT / "examples/configmap", chart)
    suite = tmp_path / "suite"
    collected = tmp_path / "collected"
    environment = {
        **os.environ,
        "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ['PATH']}",
        "CI": "true",
    }
    subprocess.run(["helm", "dependency", "build", str(chart)], env=environment, check=True, capture_output=True, text=True, timeout=60)
    subprocess.run(
        ["hypothesis-helm", "generate", str(chart), "--max-examples", "10", "--output", str(suite)],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )

    # All jobs use one immutable suite and run identity, with disjoint path ownership.
    for index in range(1, 4):
        subprocess.run(
            [
                "hypothesis-helm",
                "run",
                str(suite),
                "--shard",
                f"{index}/3",
                "--jobs",
                "1",
                "--seed",
                "2026",
                "--run-id",
                "application-shard-test",
                "--rerun",
                "all",
                "--cache-dir",
                str(tmp_path / f"cache-{index}"),
                "--artifact-dir",
                str(collected / str(index)),
            ],
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=120,
        )

    def aggregate() -> subprocess.CompletedProcess[str]:
        """
        Aggregate the currently available transported reports without any VM wrapper.

        Returns:
            subprocess.CompletedProcess[str]: Public CLI outcome with bounded diagnostics.
        """
        reports = sorted(collected.glob("*/shards/*/report.json"))
        return subprocess.run(
            [
                "hypothesis-helm",
                "aggregate",
                "--shards",
                "3",
                "--run-id",
                "application-shard-test",
                "--output-dir",
                str(tmp_path / "final"),
                *(str(path) for path in reports),
            ],
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )

    complete = aggregate()
    assert complete.returncode == 0, complete.stdout + complete.stderr
    final = json.loads((tmp_path / "final/report.json").read_text())
    assert final["run_id"] == "application-shard-test"
    assert len(final["shards"]) == 3
    reports = sorted(collected.glob("*/shards/*/report.json"))
    assert len(reports) == 3
    idle = next(path for path in reports if json.loads(path.read_text())["shard"]["selected"] == 0)
    idle.unlink()
    incomplete = aggregate()
    assert incomplete.returncode != 0
