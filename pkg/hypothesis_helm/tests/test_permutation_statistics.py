"""
Verify measured permutation progress, historical comparisons and interrupted reports.
"""

import json
import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

from hypothesis_helm.charts.runner import Chart, check_chart
from hypothesis_helm.reporting.permutations import PermutationStatistics
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import mapping


def test_previous_counts_timing_and_remaining_work(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """
    Compare pairwise and exhaustive-strength workloads using a measured fake clock.

    Args:
        monkeypatch (pytest.MonkeyPatch): Replaces clocks and the Helm renderer.
        tmp_path (Path): Persistent run artifacts.
        caplog (pytest.LogCaptureFixture): Captures plan and progress messages.

    Returns:
        None: Counts, deltas, estimates and persisted reports match completed work.
    """
    clock = [100.0]
    timer = SimpleNamespace(perf_counter=lambda: clock[0])
    monkeypatch.setattr("hypothesis_helm.charts.runner.time", timer)
    monkeypatch.setattr("hypothesis_helm.reporting.permutations.time", timer)

    def render(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Simulate a successful two-second rendering iteration.

        Args:
            *args (object): Renderer positional arguments.
            **kwargs (object): Renderer execution options.

        Returns:
            list[dict[str, object]]: A resource accepted by the mocked boundary.
        """
        clock[0] += 2
        return [{}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    caplog.set_level(logging.INFO, logger="hypothesis_helm")
    first = check_chart("examples/workload", permutations=2, artifact_dir=tmp_path, exhaustive_threshold=0)
    assert first["planned_iterations"] == 19
    assert first["completed_iterations"] == first["attempted_iterations"] == 19
    assert first["remaining_iterations"] == first["unattempted_iterations"] == 0
    assert first["previous_planned_iterations"] is None
    assert first["iteration_delta"] is None
    assert first["elapsed_seconds"] == first["estimated_total_seconds"] == 38
    assert first["seconds_per_iteration"] == 2
    forecast = check_chart(
        "examples/workload",
        permutations=2,
        dry_run=True,
        artifact_dir=tmp_path,
        exhaustive_threshold=0,
    )
    progression = mapping(forecast["progressive_estimate"])
    assert mapping(progression["configured_run"])["estimated_seconds"] == 38
    assert progression["timing_source"] == "compatible_history"
    limited = check_chart(
        "examples/workload",
        permutations=2,
        dry_run=True,
        artifact_dir=tmp_path,
        exhaustive_threshold=0,
        time_limit=40,
    )
    budget = mapping(mapping(limited["progressive_estimate"])["execution_budget"])
    assert budget["recommended_strength"] == 2
    assert budget["estimated_seconds"] == 38
    assert budget["status"] == "estimated-fit"

    assert json.loads((tmp_path / "report.json").read_text()) == first
    assert "19 remaining (0 attempted)" in caplog.text
    assert "ETA unknown (unknown)" in caplog.text
    assert json.loads((tmp_path / "report.json").read_text()) == first
    assert ET.parse(tmp_path / "junit.xml").getroot().get("failures") == "0"

    caplog.clear()
    second = check_chart("examples/workload", permutations=3, artifact_dir=tmp_path, exhaustive_threshold=0)
    assert second["planned_iterations"] == 24
    assert second["previous_planned_iterations"] == 19
    assert second["iteration_delta"] == second["additional_iterations"] == 5
    assert second["elapsed_seconds"] == 48
    assert second["estimated_remaining_seconds"] == 0
    assert "19 -> 24 iterations (+5 versus previous)" in caplog.text
    assert "ETA 48.00s (previous_run)" in caplog.text
    assert "24/24 completed, 0 remaining" in caplog.text

    reduced = check_chart("examples/workload", permutations=2, artifact_dir=tmp_path, exhaustive_threshold=0)
    assert reduced["iteration_delta"] == -5
    assert reduced["additional_iterations"] == 0


@pytest.mark.parametrize("interrupted", [False, True])
def test_failure_retains_incomplete_iterations(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, interrupted: bool) -> None:
    """
    Keep the failed iteration in remaining work and preserve interruption statistics.

    Args:
        monkeypatch (pytest.MonkeyPatch): Installs a failing renderer.
        tmp_path (Path): Persistent run artifacts.
        interrupted (bool): Whether to interrupt instead of raising a rendering failure.

    Returns:
        None: Failed and interrupted reports retain accurate unfinished counts.
    """
    calls = [0]

    def render(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Pass the defaults check, then fail or interrupt the first permutation.

        Args:
            *args (object): Renderer positional arguments.
            **kwargs (object): Renderer execution options.

        Returns:
            list[dict[str, object]]: Successful defaults resources before the failure.
        """
        calls[0] += 1
        if calls[0] == 2:
            if interrupted:
                raise KeyboardInterrupt
            raise ValueError("broken permutation")
        return [{}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    if interrupted:
        with pytest.raises(KeyboardInterrupt):
            check_chart("examples/workload", permutations=2, artifact_dir=tmp_path, exhaustive_threshold=0)
    else:
        check_chart("examples/workload", permutations=2, artifact_dir=tmp_path, exhaustive_threshold=0)
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["status"] == ("interrupted" if interrupted else "failed")
    assert report["attempts"] == report["attempted_iterations"] == 2
    assert report["completed_iterations"] == 1
    assert report["remaining_iterations"] == 18
    assert report["unattempted_iterations"] == 17
    assert report["coverage_complete"] is False
    assert json.loads((tmp_path / "values.json").read_text())["replicas"] == 0
    history = json.loads(next((tmp_path / "permutation-history").glob("*.json")).read_text())
    assert history["status"] == report["status"]
    assert history["completed_iterations"] == 1
    junit = ET.parse(tmp_path / "junit.xml").getroot()
    assert junit.find("testcase/error" if interrupted else "testcase/failure") is not None


def test_history_is_scoped_and_bad_timing_is_ignored(tmp_path: Path) -> None:
    """
    Reuse counts across settings while excluding mismatched or invalid timing samples.

    Args:
        tmp_path (Path): Persistent run artifacts.

    Returns:
        None: Chart isolation, compatibility and corrupted-history handling hold.
    """
    chart = Chart.load("examples/workload")
    plan = plan_interactions(chart.schema, 2, exhaustive_threshold=0)
    first = PermutationStatistics(chart.path, plan, tmp_path, 0.2, {"helm": "one"})
    first.advance(True, 2)
    first.finish("failed")
    changed = PermutationStatistics(chart.path, plan, tmp_path, 0.3, {"helm": "two"})
    assert changed.snapshot()["previous_planned_iterations"] == 20
    assert changed.snapshot()["estimate_source"] == "unknown"
    other = PermutationStatistics(tmp_path / "other-chart", plan, tmp_path, 0, {"helm": "one"})
    assert other.snapshot()["previous_planned_iterations"] is None
    destination = first.history_path()
    assert destination is not None
    history = json.loads(destination.read_text())
    history["seconds_per_iteration"] = "not a duration"
    destination.write_text(json.dumps(history))
    invalid = PermutationStatistics(chart.path, plan, tmp_path, 0, {"helm": "one"})
    assert invalid.snapshot()["estimate_source"] == "unknown"
    destination.write_text("{")
    corrupt = PermutationStatistics(chart.path, plan, tmp_path, 0, {"helm": "one"})
    assert corrupt.snapshot()["previous_planned_iterations"] is None
