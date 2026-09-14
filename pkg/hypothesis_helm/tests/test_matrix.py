"""
Check structural truth, strategy comparisons and censored matrix measurements.
"""

import subprocess
from contextlib import nullcontext
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES, expected_manifests
from hypothesis_helm.benchmarking.studies.matrix import STRATEGIES, measure, reference_space
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
        "hypothesis_helm.benchmarking.studies.matrix.render",
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
    for strategy in ("default", "exact-equivalence", "topology", "combined", "filter", "filter-adaptive"):
        assert reports[strategy]["observed_outcomes"] == reports[strategy]["possible_outcomes"]
    assert reports["default"]["completed"] == len(truth[0])
    assert int(str(reports["random"]["selected"])) < len(truth[0])
    assert reports["filter-adaptive"]["sampling_fallback"]
    assert reports["filter-adaptive"]["selected_sha256"] == reports["filter"]["selected_sha256"]
    assert reports["filter-adaptive"]["expand_failures"] is True
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
    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.matrix.render", lambda *args, **kwargs: [])
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

    from hypothesis_helm.benchmarking.studies.matrix import bundle_key
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
    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.matrix.time.perf_counter", lambda: clock[0])
    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.matrix.execution_timer", lambda seconds: nullcontext())

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

    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.matrix.render", timeout)
    result = measure(chart, spec, "default", level=2, seed=2026, limit=128, seconds=seconds, helm="helm", reference=reference)
    assert result["status"] == status
    assert result["completed"] == 0
    assert result["remaining"] == result["selected"]
    assert (result["error"] is None) == (status == "time-limit")


def test_benchmark_preset_matches_native_calibrated_selection(tmp_path: Path) -> None:
    """
    Exercise a measured profile through the benchmark and actual chart-testing engine.

    Args:
        tmp_path (Path): Independently generated fixture matching a packaged calibration cell.

    Returns:
        None: Both paths apply the same nontrivial sample floor and exact calibration descriptor.
    """
    from hypothesis_helm.benchmarking.analysis.selection import select
    from hypothesis_helm.benchmarking.charts.faults import Fault, write_faults
    from hypothesis_helm.charts.runner import check_chart
    from hypothesis_helm.execution.sampling import Sampling
    from hypothesis_helm.schemas.combinations import plan_interactions
    from hypothesis_helm.schemas.contracts import mapping, sequence
    from hypothesis_helm.schemas.model import ValuesModel

    spec = generate(tmp_path, input_complexity=7, output_bins=2, readable_inputs=True)
    names = [str(name) for name in sequence(spec["input_names"])]
    write_faults(
        tmp_path, [Fault("bug0", {names[0]: True}), Fault("bug1", {names[3]: True}), Fault("bug2", {names[0]: True})], symbolic=True
    )
    chart = Chart.load(tmp_path)
    plan = plan_interactions(ValuesModel.from_schema(chart.schema), 2)
    values = [value for value in plan.values if value != chart.defaults]
    selected, evidence = select(chart, values, "filter-adaptive", 2026)
    native = check_chart(chart, permutations=2, trim_topology=2, expand_failures=True, sampling=Sampling(aggressive=True), random_seed=2026)
    sampling = mapping(evidence["sampling"])
    assert native["status"] == "passed"
    assert native["completed_iterations"] == len(selected) + 1
    assert int(str(sampling["omitted"])) > 0
    assert mapping(sampling["aggressive"])["match"] == "exact"
    assert mapping(sampling["aggressive"])["fallback"] is None
    assert mapping(sampling["aggressive"])["descriptor"] == mapping(mapping(native["sampling"])["aggressive"])["descriptor"]
    assert sampling["minimum_fields"] == mapping(native["sampling"])["minimum_fields"]
