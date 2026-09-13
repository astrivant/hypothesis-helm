"""
Verify reproducible finite-plan thinning without false coverage claims.
"""

from pathlib import Path

import pytest

from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.schemas.combinations import trim_values
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_nested_trim() -> None:
    """
    Keep deterministic nested subsets and preserve execution order and zero defaults.

    Returns:
        None: Levels reduce counts without replacement and reject negative depths.
    """
    values: list[dict[str, object]] = [{"value": index} for index in range(64)]
    stages = [trim_values(values, level, 2026) for level in range(5)]
    assert [len(stage) for stage in stages] == [64, 16, 4, 1, 1]
    assert stages[0] is values
    for previous, current in zip(stages, stages[1:], strict=False):
        assert all(item in previous for item in current)
        assert [item["value"] for item in current] == sorted(int(str(item["value"])) for item in current)
    assert stages[1] == trim_values(values, 1, 2026)
    assert stages[1] != trim_values(values, 1, 2027)
    assert trim_values([], 100, 0) == []
    with pytest.raises(ValueError, match="nonnegative"):
        trim_values(values, -1, 0)


def test_trim_reports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Align execution, dry-run forecasts, history deltas and coverage after thinning.

    Args:
        tmp_path (Path): Isolated report history.
        monkeypatch (pytest.MonkeyPatch): Replace rendering while retaining real planning.

    Returns:
        None: Defaults run first, omitted cases remain explicit, and coverage is incomplete.
    """
    rendered: list[dict[str, object]] = []

    def render(chart: object, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record planned cases without invoking Helm.

        Args:
            chart (object): Loaded chart.
            values (dict[str, object]): Override configuration.
            **kwargs (object): Rendering options.

        Returns:
            list[dict[str, object]]: Accepted synthetic resource.
        """
        rendered.append(values)
        return [{}]

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    baseline = check_chart("examples/workload", permutations=2, artifact_dir=tmp_path)
    assert baseline["coverage_complete"] is True
    rendered.clear()
    forecast = check_chart("examples/workload", permutations=2, trim=1, dry_run=True)
    assert not rendered
    result = check_chart("examples/workload", permutations=2, trim=1, artifact_dir=tmp_path)
    assert rendered[0] == {}
    assert result["status"] == "passed"
    assert result["coverage_complete"] is False
    assert result["coverage_strategy"] == "trimmed"
    assert result["coverage_guaranteed_by_plan"] is False
    assert result["untrimmed_iterations"] == baseline["planned_iterations"]
    assert result["trimmed_iterations"] == -int(str(result["iteration_delta"]))
    assert result["completed_iterations"] == result["planned_iterations"] == len(rendered)
    assert result["remaining_iterations"] == 0
    assert forecast["planned_iterations"] == len(rendered)
    progressive = mapping(forecast["progressive_estimate"])
    assert mapping(progressive["configured_run"])["candidate_inputs"] == len(rendered)
    assert progressive["trim"] == 1


@pytest.mark.parametrize("arguments", [["--trim", "-1"], ["--trim", "1", "--paths"]])
def test_invalid_trim_cli(arguments: list[str]) -> None:
    """
    Reject invalid depths and incompatible testing modes before execution.

    Args:
        arguments (list[str]): Invalid test options.

    Returns:
        None: The CLI fails rather than silently ignoring requested thinning.
    """
    assert main(["test", "examples/workload", *arguments]) == 2


def test_topology_sampling(tmp_path: Path) -> None:
    """
    Preserve projected regions under combined thinning and retain unsupported inputs.

    Args:
        tmp_path (Path): Isolated generated chart.

    Returns:
        None: Region floors, nesting, unknown fallback and CLI composition hold.
    """
    from hypothesis_helm.benchmarking.generate_benchmark_chart import generate
    from hypothesis_helm.charts.runner import Chart
    from hypothesis_helm.cli import argument_parser
    from hypothesis_helm.compiler.topology import trim_topology
    from hypothesis_helm.schemas.finite import enumerate_values

    generate(tmp_path, input_complexity=10, output_bins=4, topology=True)
    chart = Chart.load(tmp_path)
    values = enumerate_values(chart.schema, 2000)
    first, first_report = trim_topology(tmp_path, chart.defaults, values, values, 1, 2026)
    combined, report = trim_topology(tmp_path, chart.defaults, values, values, 1, 2026, random_steps=1)
    assert 0 < len(combined) < len(first) < len(values)
    assert all(item in first for item in combined)
    assert report["region_count"] == first_report["region_count"]
    assert report["unknown_cases_retained"] == 0
    assert all(int(str(mapping(region)["retained"])) >= 1 for region in sequence(report["regions"]))
    assert report["coverage_guarantee"] is False
    args = argument_parser().parse_args(["test", "--trim-random", "1", "--trim-topology", "2"])
    assert args.trim == 1 and args.trim_topology == 2
    assert argument_parser().parse_args(["test", "--trim", "1"]).trim == 1
    generate(tmp_path, input_complexity=10, output_bins=4, topology_opaque=True, force=True)
    kept, unknown = trim_topology(tmp_path, chart.defaults, values, values, 3, 2026, random_steps=3)
    assert kept == values
    assert unknown["unknown_cases_retained"] == len(values)


def test_topology_generator_oracle(tmp_path: Path) -> None:
    """
    Exercise every topology assignment through Helm and the independent projection oracle.

    Args:
        tmp_path (Path): Generated topology fixture.

    Returns:
        None: Conditional resources, shared ports, replicas and rare regions match the oracle.
    """
    import shutil

    from hypothesis_helm.benchmarking.generate_benchmark_chart import generate
    from hypothesis_helm.benchmarking.topology import validate_topology
    from hypothesis_helm.charts.runner import Chart, render

    if not shutil.which("helm"):
        pytest.skip("Helm required")
    spec = generate(tmp_path, input_complexity=10, output_bins=4, topology=True)
    chart = Chart.load(tmp_path)
    for assignment in range(64):
        values = {
            **chart.defaults,
            **{f"input{index + 2:03d}": bool(assignment & (1 << index)) for index in range(6)},
        }
        resources = render(chart, values)
        validate_topology(resources, values, spec)
    resources[-1]["metadata"] = {"name": "topology-unexpected"}
    with pytest.raises((AssertionError, KeyError)):
        validate_topology(resources, values, spec)
