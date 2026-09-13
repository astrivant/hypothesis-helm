"""
Check structural truth, strategy comparisons and censored matrix measurements.
"""

import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.benchmark_matrix import STRATEGIES, measure, reference_space
from hypothesis_helm.benchmarking.generate_benchmark_chart import generate
from hypothesis_helm.benchmarking.structures import STRUCTURES, expected_manifests
from hypothesis_helm.charts.runner import Chart, RenderFailure


@pytest.mark.parametrize("structure", STRUCTURES)
def test_matrix_strategy_contracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, structure: str) -> None:
    """
    Preserve oracle outcomes or explicit fallback without silently changing the valid domain.

    Args:
        tmp_path (Path): Independent generated fixture.
        monkeypatch (pytest.MonkeyPatch): Replace Helm with deterministic oracle output.
        structure (str): Structural case under comparison.

    Returns:
        None: Coverage, strategy counts, fallback and deadline reporting remain consistent.
    """
    spec = generate(tmp_path, input_complexity=6, output_bins=4, structure=structure)
    chart = Chart.load(tmp_path)
    truth = reference_space(chart, spec, 128)
    assert len(truth[0]) == (32 if structure == "constraints" else 96 if structure == "boundaries" else 64)
    monkeypatch.setattr(
        "hypothesis_helm.benchmarking.benchmark_matrix.render",
        lambda chart, values, **kwargs: expected_manifests(values, spec),
    )
    reports = {
        strategy: measure(
            chart,
            spec,
            strategy,
            level=2,
            seed=2026,
            limit=128,
            seconds=30,
            helm="helm",
            reference=truth,
        )
        for strategy in STRATEGIES
    }
    assert all(report["status"] == "passed" for report in reports.values())
    for strategy in ("default", "exact-equivalence", "topology", "combined"):
        assert reports[strategy]["observed_outcomes"] == reports[strategy]["possible_outcomes"]
    assert reports["default"]["completed"] == len(truth[0])
    assert int(str(reports["random"]["selected"])) < len(truth[0])
    if structure in {"constraints", "control-flow", "boundaries"}:
        assert reports["topology"]["omitted"] == reports["combined"]["omitted"] == 0
    stopped = measure(
        chart,
        spec,
        "default",
        level=2,
        seed=2026,
        limit=128,
        seconds=1e-9,
        helm="helm",
        reference=truth,
    )
    assert stopped["status"] == "time-limit"
    assert stopped["remaining"] == stopped["selected"]
    assert stopped["distribution"] is None
    monkeypatch.setattr("hypothesis_helm.benchmarking.benchmark_matrix.render", lambda *args, **kwargs: [])
    failed = measure(
        chart,
        spec,
        "default",
        level=2,
        seed=2026,
        limit=128,
        seconds=30,
        helm="helm",
        reference=truth,
    )
    assert failed["status"] == "failed"
    assert failed["completed"] == 0


def test_numeric_boundary_helm(tmp_path: Path) -> None:
    """
    Check integer threshold behavior through Helm's JSON numeric conversion.

    Args:
        tmp_path (Path): Generated fixture destination.

    Returns:
        None: Every numeric boundary state agrees with the independent oracle.
    """
    import shutil

    from hypothesis_helm.benchmarking.benchmark_matrix import bundle_key
    from hypothesis_helm.charts.runner import render

    if not shutil.which("helm"):
        pytest.skip("Helm required")
    spec = generate(tmp_path, input_complexity=6, output_bins=4, structure="boundaries")
    chart = Chart.load(tmp_path)
    for value in (0, 1, 2):
        values = {**chart.defaults, "input002": value}
        actual = render(chart, values, release="matrix")
        assert bundle_key(actual) == bundle_key(expected_manifests(values, spec))


@pytest.mark.parametrize("seconds,status", [(1, "time-limit"), (60, "failed")])
def test_matrix_distinguishes_deadline_from_render_timeout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seconds: int, status: str
) -> None:
    """
    Report an exhausted study budget separately from a stalled Helm invocation.

    Args:
        tmp_path (Path): Generated matrix chart.
        monkeypatch (pytest.MonkeyPatch): Deterministic clock and Helm timeout.
        seconds (int): Study execution budget.
        status (str): Expected deadline or failure classification.

    Returns:
        None: Deadline censorship preserves counts without hiding an independent timeout.
    """
    spec = generate(tmp_path, input_complexity=6, output_bins=4, structure="dependencies")
    chart = Chart.load(tmp_path)
    reference = reference_space(chart, spec, 128)
    clock = [0.0]
    monkeypatch.setattr("hypothesis_helm.benchmarking.benchmark_matrix.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr("hypothesis_helm.benchmarking.benchmark_matrix.execution_timer", lambda seconds: nullcontext())

    def timeout(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Advance to a simulated subprocess timeout and preserve its exception cause.

        Args:
            *args (object): Chart and input values.
            **kwargs (object): Render execution settings.

        Returns:
            list[dict[str, object]]: No manifest is returned by the timed-out process.
        """
        clock[0] = min(30, seconds)
        raise RenderFailure("Helm timed out") from subprocess.TimeoutExpired("helm", clock[0])

    monkeypatch.setattr("hypothesis_helm.benchmarking.benchmark_matrix.render", timeout)
    result = measure(chart, spec, "default", level=2, seed=2026, limit=128, seconds=seconds, helm="helm", reference=reference)
    assert result["status"] == status
    assert result["completed"] == 0
    assert result["remaining"] == result["selected"]
    assert (result["error"] is None) == (status == "time-limit")
