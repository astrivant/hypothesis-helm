"""
Verify dry-run work estimates agree with cache-aware execution.
"""

import json
from pathlib import Path

import pytest

from hypothesis_helm.cli import main
from hypothesis_helm.execution.estimate import estimate_suite
from hypothesis_helm.execution.suite import run_suite
from hypothesis_helm.integrations.sharding import Shard


def test_saved_suite_cache_policy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Count failures, successes, CI defaults, and explicit cache overrides without execution.

    Args:
        tmp_path (Path): Saved suite and result cache.
        monkeypatch (pytest.MonkeyPatch): Control CI defaults.

    Returns:
        None: Plans match the prospective selection and leave artifacts unchanged.
    """
    monkeypatch.setenv("CI", "false")
    (tmp_path / "test_chart_values.py").write_text(
        "from pathlib import Path\ndef test_pass(): Path('executed').touch()\ndef test_fail(): assert False\n"
    )
    assert run_suite(tmp_path, jobs=1) == 1
    before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    estimate = estimate_suite(tmp_path)
    assert estimate["selected_properties"] == 2
    assert estimate["scheduled_properties"] == 1
    assert estimate["reused_properties"] == 1
    assert estimate["successful_example_budget"] is None
    assert estimate_suite(tmp_path, cache=False)["scheduled_properties"] == 2
    assert estimate_suite(tmp_path, schema_state={"status": "unavailable"})["scheduled_properties"] == 2
    assert estimate_suite(tmp_path, rerun="all")["scheduled_properties"] == 2
    monkeypatch.setenv("CI", "true")
    assert estimate_suite(tmp_path)["scheduled_properties"] == 2
    assert estimate_suite(tmp_path, rerun="failed")["scheduled_properties"] == 1
    after = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    assert before == after


def test_chart_dry_run_cache_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Stage generated sources without altering reports or breaking compatible cache keys.

    Args:
        tmp_path (Path): Prospective report location.
        monkeypatch (pytest.MonkeyPatch): Control local rerun policy.
        capsys (pytest.CaptureFixture[str]): Capture the JSON estimate.

    Returns:
        None: Cold, warm, and changed-budget plans report the appropriate work.
    """
    monkeypatch.setenv("CI", "false")
    target = tmp_path / "reports"
    args = [
        "test",
        "examples/workload",
        "--paths",
        "--artifact-dir",
        str(target),
        "--max-examples",
        "1",
        "--jobs",
        "1",
    ]
    assert main([*args, "--dry-run", "-o", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scheduled_properties"] == 4
    assert report["successful_example_budget"] == 4
    assert not target.exists()
    assert main(args) == 0
    capsys.readouterr()
    before = {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}
    assert main([*args, "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["cache_hit"]
    assert report["scheduled_properties"] == 0
    assert report["reused_properties"] == 4
    assert report["successful_example_budget"] == 0
    assert main([*args, "--dry-run", "--max-examples", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["successful_example_budget"] == 8
    assert before == {p: p.read_bytes() for p in target.rglob("*") if p.is_file()}


def test_plan_shards_and_missing_schemas(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """
    Respect shard partitioning and report uncached schemas without downloading them.

    Args:
        tmp_path (Path): Suite and missing schema cache locations.
        capsys (pytest.CaptureFixture[str]): Capture the CLI estimate.

    Returns:
        None: Every property is assigned once and schema preparation stays deferred.
    """
    (tmp_path / "test_chart_values.py").write_text("def test_one(): assert False\ndef test_two(): assert False\n")
    assert sum(int(str(estimate_suite(tmp_path, shard=Shard(i, 2))["selected_properties"])) for i in (1, 2)) == 2
    cache = tmp_path / "missing"
    assert main(["run", str(tmp_path), "--dry-run", "--kubeconform", "--schema-cache-dir", str(cache)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_cache"]["status"] == "unavailable"
    assert report["scheduled_properties"] == 2
    assert not cache.exists()
