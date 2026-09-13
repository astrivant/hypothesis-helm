"""
Verify duration input validation and bounded execution reporting.
"""

import argparse
import json
import signal
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import mapping, sequence


@pytest.mark.parametrize(("value", "seconds"), [("180", 180), ("3m", 180), ("0.5h", 1800), ("0.01s", 0.01)])
def test_duration_units(value: str, seconds: float) -> None:
    """
    Accept explicit duration units and fractional positive seconds.

    Args:
        value (str): User-provided duration.
        seconds (float): Expected budget in seconds.

    Returns:
        None: Valid durations normalize to seconds.
    """
    assert parse_time_limit(value) == seconds


@pytest.mark.parametrize("value", ["0", "-1", "nan", "inf", "3ms", "", "1e3", "9" * 400])
def test_invalid_duration(value: str) -> None:
    """
    Reject durations that cannot define a finite positive execution budget.

    Args:
        value (str): Invalid user input.

    Returns:
        None: Invalid limits fail before starting work.
    """
    with pytest.raises(argparse.ArgumentTypeError):
        parse_time_limit(value)


def test_default_budget_retains_completed_statistics(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """
    Stop before a fourth one-minute iteration and preserve history and incomplete JUnit.

    Args:
        monkeypatch (pytest.MonkeyPatch): Supplies a deterministic execution clock.
        tmp_path (Path): Artifact destination.

    Returns:
        None: The default three-minute budget stops cleanly without a counterexample.
    """
    clock = [0.0]
    timer = SimpleNamespace(perf_counter=lambda: clock[0])
    monkeypatch.setattr("hypothesis_helm.charts.runner.time", timer)
    monkeypatch.setattr("hypothesis_helm.reporting.permutations.time", timer)

    def render(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Consume one minute of the execution budget.

        Args:
            *args (object): Chart and input arguments.
            **kwargs (object): Renderer options.

        Returns:
            list[dict[str, object]]: A successful manifest.
        """
        clock[0] += 60
        return [{}]

    renderer = Mock(side_effect=render)
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", renderer)
    report = check_chart("examples/workload", permutations=2, artifact_dir=tmp_path)
    assert report["status"] == "time-limit"
    assert report["exit_code"] == 124
    assert report["time_limit_seconds"] == report["execution_seconds"] == 180
    assert report["attempted_iterations"] == report["completed_iterations"] == 3
    assert report["remaining_iterations"] == report["unattempted_iterations"] == 21
    assert report["coverage_complete"] is False
    assert report["elapsed_seconds"] == 180
    assert renderer.call_count == 3
    assert mapping(renderer.call_args.kwargs)["timeout"] == 30
    assert not (tmp_path / "values.json").exists()
    assert json.loads((tmp_path / "report.json").read_text()) == report
    history = json.loads(next((tmp_path / "permutation-history").glob("*")).read_text())
    assert history["completed_iterations"] == 3
    assert history["seconds_per_iteration"] == 60
    junit = ET.parse(tmp_path / "junit.xml").getroot()
    assert junit.get("failures") == "0"
    assert junit.get("errors") == "1"
    assert junit.find("testcase/error") is not None


def test_active_assertion_is_stopped_and_alarm_restored(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Interrupt an active callback on the CLI thread and restore its signal state.

    Args:
        monkeypatch (pytest.MonkeyPatch): Replaces Helm with a successful renderer.

    Returns:
        None: Partial work stays incomplete and the temporary timer is removed.
    """
    monkeypatch.setattr("hypothesis_helm.charts.runner.render", Mock(return_value=[{}]))
    previous = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()
    report = check_chart(
        "examples/workload",
        permutations=2,
        time_limit=0.05,
        properties=(lambda resources: time.sleep(2),),
    )
    assert time.monotonic() - started < 1.5
    assert report["status"] == "time-limit"
    assert report["attempted_iterations"] == 1
    assert report["completed_iterations"] == 0
    assert report["remaining_iterations"] == 24
    assert signal.getsignal(signal.SIGALRM) == previous
    assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)


def test_cli_stops_slow_helm(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """
    Stop an in-flight renderer and expose a distinct incomplete-run exit status.

    Args:
        tmp_path (Path): Slow executable and artifact location.
        capsys (pytest.CaptureFixture[str]): Captures structured CLI output.

    Returns:
        None: Deadline expiry produces a report instead of a rendering counterexample.
    """
    helm = tmp_path / "helm"
    helm.write_text(f"#!{sys.executable}\nimport time\ntime.sleep(10)\n")
    helm.chmod(0o755)
    started = time.monotonic()
    status = main(
        [
            "test",
            "examples/workload",
            "--permutations",
            "2",
            "--helm",
            str(helm),
            "--time-limit",
            "0.1s",
            "--artifact-dir",
            str(tmp_path / "artifacts"),
        ]
    )
    assert status == 124
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "time-limit"
    assert report["attempted_iterations"] == 1
    assert report["completed_iterations"] == 0
    assert report["remaining_iterations"] == 24
    assert time.monotonic() - started < 2
    assert "failure_type" not in report


def test_execution_limit_does_not_limit_dry_run() -> None:
    """
    Complete planning with a tiny execution budget while retaining an unknown recommendation.

    Returns:
        None: Dry-run calculation is not stopped by the test execution limit.
    """
    report = check_chart(
        "examples/workload",
        permutations=2,
        dry_run=True,
        time_limit=0.000001,
    )
    forecast = mapping(report["progressive_estimate"])
    assert report["status"] == "dry-run"
    assert len(sequence(forecast["stages"])) == 3
    budget = mapping(forecast["execution_budget"])
    assert budget["status"] == "unknown"
    assert budget["recommended_strength"] is None
