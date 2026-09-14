"""
Verify one-chart benchmark ownership, recipe replay, and the independent stress oracle.
"""

import itertools
import json
from pathlib import Path

import pytest
from attrs import asdict

from hypothesis_helm.benchmarking.analysis.pca import inject_errors
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, case_path, chart_path, read_spec
from hypothesis_helm.benchmarking.charts.generator import generate, reproduce
from hypothesis_helm.benchmarking.charts.stress import FAMILIES, SIGNALS, Stress, progression
from hypothesis_helm.benchmarking.charts.structures import STRUCTURES, expected_manifests
from hypothesis_helm.benchmarking.charts.workload import source_digest
from hypothesis_helm.benchmarking.cli import main
from hypothesis_helm.benchmarking.studies.matrix import bundle_key, reference_space
from hypothesis_helm.charts import yamlio
from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.schemas.contracts import mapping


@pytest.mark.parametrize("structure", STRUCTURES)
def test_shared_chart_recipe_replays_exactly(tmp_path: Path, structure: str) -> None:
    """
    Retain parameters for each case while using and cleaning one physical chart.

    Args:
        tmp_path (Path): Case records and explicitly replayed chart location.
        structure (str): Existing benchmark topology category.

    Returns:
        None: Recipes recreate identical bytes, and named inputs match the Helm oracle.
    """
    logical = tmp_path / "charts" / structure
    with FixtureWorkspace() as workspace:
        spec = generate(logical, input_complexity=6, output_bins=4, structure=structure, workspace=workspace)
        chart = Chart.load(chart_path(logical, workspace=workspace))
        assert chart.path == workspace.chart
        assert not logical.exists()
        assert not any(name.startswith("input") for name in chart.defaults)
        assert bundle_key(render(chart, chart.defaults, release="matrix")) == bundle_key(expected_manifests(chart.defaults, spec))
        digest = source_digest(chart.path)
        assert read_spec(logical) == spec
        generate(tmp_path / "charts" / "next", input_complexity=6, output_bins=4, workspace=workspace)
        assert list(workspace.chart.parent.rglob("Chart.yaml")) == [workspace.chart / "Chart.yaml"]
        with pytest.raises(ValueError, match="no longer active"):
            chart_path(logical, workspace=workspace)
    assert not workspace.chart.exists()
    assert case_path(logical).is_file()
    replayed = tmp_path / "exported"
    reproduce(case_path(logical), replayed)
    assert source_digest(replayed) == digest


def test_fault_recipe_replays_exactly(tmp_path: Path) -> None:
    """
    Retain post-generation PCA fault parameters without storing another chart snapshot.

    Args:
        tmp_path (Path): Case records and exported replay.

    Returns:
        None: The fault decision tree and all chart bytes replay identically.
    """
    from hypothesis_helm.schemas.combinations import plan_interactions
    from hypothesis_helm.schemas.contracts import configuration_key
    from hypothesis_helm.schemas.model import ValuesModel

    logical = tmp_path / "charts" / "faulty"
    with FixtureWorkspace() as workspace:
        generate(logical, input_complexity=6, output_bins=4, structure="interactions", workspace=workspace)
        chart = Chart.load(chart_path(logical, workspace=workspace))
        plan = plan_interactions(ValuesModel.from_schema(chart.schema), 6, max_cases=8192, max_candidates=8192)
        values = [chart.defaults, *(value for value in plan.values if configuration_key(value) != configuration_key(chart.defaults))]
        inject_errors(logical, values, 5, 1729, workspace=workspace)
        digest = source_digest(chart.path)
    reproduce(case_path(logical), tmp_path / "replay")
    assert source_digest(tmp_path / "replay") == digest


def test_fixed_progression_changes_one_control() -> None:
    """
    Keep defect triggers and the input inventory fixed while reducing one topology control.

    Returns:
        None: The progression has stable order, unit changes, and a minimal final profile.
    """
    steps = progression(Stress())
    assert len(steps) == 22
    assert steps == progression(Stress())
    for (_, before), (_, after) in itertools.pairwise(steps):
        differences = [name for name, value in asdict(before).items() if asdict(after)[name] != value]
        assert len(differences) == 1
        assert getattr(before, differences[0]) - getattr(after, differences[0]) == 1
        assert after.faults_enabled


@pytest.mark.parametrize("settings", [Stress(), Stress(coupled_pairs=0), progression(Stress())[-1][1]])
def test_stress_helm_oracle_and_filtering(tmp_path: Path, settings: Stress) -> None:
    """
    Match actual Helm outputs at gates, boundaries, and all six known defect triggers.

    Args:
        tmp_path (Path): Isolated combined chart.
        settings (Stress): Worst, supported, or minimally redundant topology profile.

    Returns:
        None: Oracle and Helm agree; supported profiles use real topology grouping.
    """
    spec = generate(tmp_path, stress=settings)
    chart = Chart.load(tmp_path)
    assert list(chart.defaults) == list(SIGNALS)
    choices: list[dict[str, object]] = [chart.defaults, dict.fromkeys(chart.defaults, True)]
    choices.extend({**dict.fromkeys(chart.defaults, True), key: False} for key in SIGNALS[4:])
    for values in choices:
        actual = render(chart, values, release="matrix")
        assert bundle_key(actual) == bundle_key(expected_manifests(values, spec))
    all_enabled = render(chart, dict.fromkeys(chart.defaults, True), release="matrix")
    assert {
        mapping(resource["metadata"])["name"] for resource in all_enabled if mapping(resource.get("data", {})).get("status") == "incorrect"
    } == {"defect-" + family for family in FAMILIES}
    reference = reference_space(chart, spec, 4096)
    candidates = [mapping(json.loads(value)) for value in sorted(reference[0])]
    retained, evidence = trim_topology(chart.path, chart.defaults, candidates, candidates, 2, 2026)
    if settings.coupled_pairs:
        assert evidence["fallback"] and len(retained) == len(candidates)
    else:
        assert evidence["fallback"] is None and evidence["region_count"]
        if settings.equivalent_inputs:
            assert len(retained) < len(candidates)


def test_stress_cli_keeps_only_parameter_records(tmp_path: Path) -> None:
    """
    Generate the complete progression through the installed benchmark command dispatcher.

    Args:
        tmp_path (Path): Retained benchmark output.

    Returns:
        None: Twenty-two scenarios produce recipes rather than twenty-two Helm charts.
    """
    assert main(["stress", "--generate-only", "--output", str(tmp_path)]) == 0
    assert len(list((tmp_path / "cases").glob("*.yaml"))) == 22
    assert not list(tmp_path.rglob("Chart.yaml"))


def test_forced_recipe_replaces_previous_named_faults(tmp_path: Path) -> None:
    """
    Replace an exported named chart without applying its old field mapping to new faults.

    Args:
        tmp_path (Path): Fresh and overwritten chart exports.

    Returns:
        None: Repeated exports and regenerated fault templates remain byte-identical.
    """
    first, second = tmp_path / "first", tmp_path / "second"
    generate(first, input_complexity=8, bug_percent=5, readable_inputs=True)
    generate(second, input_complexity=6, bug_percent=5, readable_inputs=True)
    generate(first, input_complexity=6, bug_percent=5, readable_inputs=True, force=True)
    assert source_digest(first) == source_digest(second)


@pytest.mark.parametrize("invalid", ["gate_depth: 1.5", "gate_depth: 6", 'faults_enabled: "false"'])
def test_recipe_rejects_invalid_stress_controls(tmp_path: Path, invalid: str) -> None:
    """
    Reject malformed controls instead of coercing them into a different experiment.

    Args:
        tmp_path (Path): Invalid recipe and destination.
        invalid (str): Out-of-range or incorrectly typed setting.

    Returns:
        None: Chart generation does not begin for an invalid recipe.
    """
    source = tmp_path / "parameters.yaml"
    source.write_text(f"parameters:\n  stress:\n    {invalid}\n")
    with pytest.raises(ExceptionGroup):
        reproduce(source, tmp_path / "chart")
    assert not (tmp_path / "chart").exists()


def test_cli_keeps_shard_recipes_separate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Store each shard's parameters with its results and clean up its isolated chart.

    Args:
        tmp_path (Path): Shared benchmark output root and generator recipe.
        monkeypatch (pytest.MonkeyPatch): Inspect worker inputs without repeating timing tests.

    Returns:
        None: Separate shard records survive after their distinct chart workspaces are removed.
    """
    from hypothesis_helm.benchmarking.studies import performance as benchmark_helm

    recipe = tmp_path / "parameters.yaml"
    recipe.write_text(yamlio.dump({"parameters": {"input_complexity": 6, "output_bins": 4}}))
    charts: list[Path] = []

    def inspect(argv: list[str], *, workspace: FixtureWorkspace | None = None) -> int:
        """
        Inspect the physical chart passed to a benchmark invocation.

        Args:
            argv (list[str]): Explicit arguments supplied by the dispatcher.
            workspace (FixtureWorkspace | None): Owner that remains alive during execution.

        Returns:
            int: Success after confirming the worker can load its generated chart.
        """
        args = benchmark_helm.parser().parse_args(argv)
        assert (args.chart / "Chart.yaml").is_file()
        charts.append(args.chart)
        return 0

    monkeypatch.setattr(benchmark_helm, "run", inspect)
    for shard in ("1/3", "2/3", "3/3"):
        assert main(["--parameters", str(recipe), "run", "--shard", shard, "--output", str(tmp_path)]) == 0
    assert len(set(charts)) == 3
    assert all(not chart.exists() for chart in charts)
    assert len(list(tmp_path.glob("shard-*/chart-parameters.yaml"))) == 3
    assert not (tmp_path / "chart-parameters.yaml").exists()


def test_explicit_workspaces_do_not_redirect_each_other(tmp_path: Path) -> None:
    """
    Keep interleaved invocations independent even when logical output locations match.

    Args:
        tmp_path (Path): Shared logical destination for two explicit owners.

    Returns:
        None: Each owner resolves and updates only its own physical chart.
    """
    logical = tmp_path / "charts" / "shared"
    with FixtureWorkspace() as first, FixtureWorkspace() as second:
        generate(logical, input_complexity=6, workspace=first)
        generate(logical, input_complexity=6, workspace=second)
        generate(tmp_path / "charts" / "next", input_complexity=8, workspace=first)
        assert first.chart != chart_path(logical, workspace=second)
        assert len(Chart.load(first.chart).defaults) == 8
        assert len(Chart.load(chart_path(logical, workspace=second)).defaults) == 6
        assert chart_path(logical) == logical
