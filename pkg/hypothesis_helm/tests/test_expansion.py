"""
Verify failure-triggered scheduling, observed outcomes and budget accounting.
"""

import itertools
import json
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.benchmarking.charts.structures import configmap
from hypothesis_helm.benchmarking.studies.expansion import compare
from hypothesis_helm.benchmarking.studies.matrix import bundle_key
from hypothesis_helm.charts.runner import Chart, check_chart
from hypothesis_helm.compiler.passes.expansion import FailureExpansion
from hypothesis_helm.reporting.budget import TimeLimitReached
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence


@pytest.fixture
def expansion_chart(tmp_path: Path) -> Chart:
    """
    Create two output regions, each containing four valid input assignments.

    Args:
        tmp_path (Path): Fixture directory.

    Returns:
        Chart: Boolean a controls the failure; b and c are irrelevant within either region.
    """
    (tmp_path / "templates").mkdir()
    (tmp_path / "Chart.yaml").write_text(
        dedent(
            """
        apiVersion: v2
        name: expansion
        version: 0.1.0
        """
        ).removeprefix("\n")
    )
    (tmp_path / "values.yaml").write_text(
        dedent(
            """
        a: false
        b: false
        c: false
        """
        ).removeprefix("\n")
    )
    (tmp_path / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "required": ["a", "b", "c"],
                "additionalProperties": False,
                "properties": {key: {"type": "boolean"} for key in ("a", "b", "c")},
            }
        )
    )
    (tmp_path / "templates/error.yaml").write_text(
        dedent(
            """
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: benchmark-error
        data:
          status: "{{ if .Values.a }}incorrect{{ else }}expected{{ end }}"
        """
        ).removeprefix("\n")
    )
    return Chart.load(tmp_path)


def error_output(values: dict[str, object]) -> list[dict[str, object]]:
    """
    Compute the independent output oracle for the fixture.

    Args:
        values (dict[str, object]): Effective or partial input assignment.

    Returns:
        list[dict[str, object]]: Exact error-status manifest bundle.
    """
    return [configmap("benchmark-error", {"status": "incorrect" if values.get("a") else "expected"})]


def reject_error(resources: list[dict[str, object]]) -> None:
    """
    Reject the synthetic error status using only rendered output.

    Args:
        resources (list[dict[str, object]]): Observed manifest bundle.

    Returns:
        None: The assertion succeeds only for the expected status.
    """
    assert mapping(resources[0]["data"])["status"] == "expected"


@pytest.mark.parametrize("sampled", [False, True])
def test_fail_fast_preserves_first_failure(expansion_chart: Chart, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, sampled: bool) -> None:
    """
    Stop after one faulty render in both sampled and failure-expansion execution.

    Args:
        expansion_chart (Chart): Two-region chart fixture.
        monkeypatch (pytest.MonkeyPatch): Replace Helm with the independent output oracle.
        tmp_path (Path): Failure artifact destination.
        sampled (bool): Use Hypothesis sampling instead of finite expansion.

    Returns:
        None: No confirmation, shrinking, or expansion renders follow the first failure.
    """
    from hypothesis import strategies as st

    calls: list[dict[str, object]] = []

    def render(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record renders and produce the fixture's independent expected output.

        Args:
            chart (Chart): Chart under test.
            values (dict[str, object]): Generated overrides.
            **kwargs (object): Renderer options.

        Returns:
            list[dict[str, object]]: Oracle manifests.
        """
        calls.append(values)
        return error_output(values)

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    report = check_chart(
        expansion_chart,
        permutations=None if sampled else 2,
        trim_topology=0 if sampled else 2,
        expand_failures=not sampled,
        fail_fast=True,
        input_strategy=st.just({"a": True, "b": False, "c": False}) if sampled else None,
        properties=(reject_error,),
        infer_exhaustive_groups=False,
        artifact_dir=tmp_path / "reports",
    )
    assert report["status"] == "failed"
    assert sum(bool(values.get("a")) for values in calls) == 1
    assert calls[-1]["a"] is True
    assert report["attempts"] == len(calls)
    assert json.loads((tmp_path / "reports/values.json").read_text()) == calls[-1]
    if not sampled:
        assert report["failed_iterations"] == 1
        assert mapping(report["failure_expansion"])["additional_scheduled"] == 0


@pytest.mark.parametrize("limited", [False, True])
@pytest.mark.parametrize("pruning", [False, True])
def test_expansion_execution(
    expansion_chart: Chart,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    limited: bool,
    pruning: bool,
) -> None:
    """
    Execute each failed-region member once and preserve failures when the budget interrupts work.

    Args:
        expansion_chart (Chart): Finite two-region fixture.
        monkeypatch (pytest.MonkeyPatch): Replace the Helm boundary with an independent oracle.
        tmp_path (Path): Artifact destination.
        limited (bool): Stop when the second faulty input reaches the renderer.
        pruning (bool): Enable successful-output reuse while forcing added inputs to render.

    Returns:
        None: Actual execution counts, additional scheduling and failure records agree.
    """
    calls: list[dict[str, object]] = []

    def render(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Simulate Helm output or a deadline during an added render.

        Args:
            chart (Chart): Fixture being rendered.
            values (dict[str, object]): Current overrides.
            **kwargs (object): Remaining renderer settings.

        Returns:
            list[dict[str, object]]: Independent manifest output when time remains.
        """
        calls.append(values)
        if limited and sum(bool(value.get("a")) for value in calls) == 2:
            raise TimeLimitReached()
        return error_output(values)

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    report = check_chart(
        expansion_chart,
        permutations=2,
        trim_topology=2,
        expand_failures=True,
        prune_equivalent=pruning,
        properties=(reject_error,),
        max_cases=8,
        infer_exhaustive_groups=False,
        artifact_dir=tmp_path / "reports",
    )
    details = mapping(report["failure_expansion"])
    assert details["additional_scheduled"] == 3
    assert details["inferred_failures"] == 0
    if pruning:
        assert mapping(report["pruning"])["rendered_candidates"] == len(calls)
    assert len({configuration_key(value) for value in calls}) == len(calls)
    if limited:
        assert report["status"] == "time-limit"
        assert report["failed_iterations"] == 1
        assert details["additional_executed"] == 0
        assert details["additional_remaining"] == report["remaining_iterations"] == 3
    else:
        assert report["status"] == "failed"
        assert report["failed_iterations"] == 4
        assert details["additional_executed"] == 3
        assert report["remaining_iterations"] == 0
        assert report["completed_iterations"] == report["attempts"]
    assert json.loads((tmp_path / "reports/report.json").read_text()) == json.loads(json.dumps(report))


def test_expansion_scheduler_and_benchmark(expansion_chart: Chart, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Expand only observed failures and preserve exact output coverage while increasing input recall.

    Args:
        expansion_chart (Chart): Shared symbolic region fixture.
        monkeypatch (pytest.MonkeyPatch): Capture additional physical renders.

    Returns:
        None: Duplicate triggers do not reschedule inputs and no oracle labels guide selection.
    """
    values: list[dict[str, object]] = [dict(zip(("a", "b", "c"), bits, strict=True)) for bits in itertools.product((False, True), repeat=3)]
    scheduler = FailureExpansion.build(expansion_chart.path, expansion_chart.defaults, values, values, [0, 4])
    assert scheduler.failed(4) == [5, 6, 7]
    assert scheduler.failed(5) == []
    assert FailureExpansion({}, {}, {0}).failed(0) == []
    calls: list[dict[str, object]] = []

    def render(chart: Chart, value: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record a real expansion request and return independently computed manifests.

        Args:
            chart (Chart): Chart passed through the benchmark.
            value (dict[str, object]): Scheduled added input.
            **kwargs (object): Remaining Helm arguments.

        Returns:
            list[dict[str, object]]: Output for the explicitly requested input.
        """
        calls.append(value)
        return error_output(value)

    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.expansion.render", render)
    reference: dict[str, object] = {
        "structure": "fixture",
        "values": values,
        "outcomes": [json.loads(bundle_key(error_output(value))) for value in (values[0], values[4])],
        "outcome_indices": [0] * 4 + [1] * 4,
        "selected_indices": {"topology": [0, 4]},
        "faulty_indices": [],  # Intentionally wrong: scheduling must read observed outputs.
    }
    before, after = compare(expansion_chart, reference, "helm", 30)
    assert before["erroneous_inputs_found"] == 1
    assert after["erroneous_inputs_found"] == 4
    assert before["erroneous_output_coverage"] == after["erroneous_output_coverage"] == 1
    assert after["additional_indices"] == [5, 6, 7]
    assert calls == values[5:]
    assert after["additional_executed"] == 3
    restricted = {**reference, "candidate_indices": [0, 4, 5]}
    _, limited = compare(expansion_chart, restricted, "helm", 30)
    assert limited["additional_indices"] == [5]
    assert limited["erroneous_inputs_found"] == 2
    assert limited["erroneous_inputs_total"] == 4


@pytest.mark.parametrize(
    "options",
    [
        ["--expand-failures", "--trim-topology", "2"],
        ["--filter"],
        ["--filter", "--trim", "1"],
        ["--trim-random", "1", "--filter"],
    ],
)
def test_expansion_cli_dry_run(expansion_chart: Chart, capsys: pytest.CaptureFixture[str], options: list[str]) -> None:
    """
    Expose the opt-in flag and bound failure-dependent work without executing chart tests.

    Args:
        expansion_chart (Chart): Finite chart for planning.
        capsys (pytest.CaptureFixture[str]): Captured CLI report.
        options (list[str]): Individual controls or the combined preset.

    Returns:
        None: The dry run declares expansion without claiming observed failures.
    """
    from hypothesis_helm.cli import main

    assert (
        main(
            [
                "test",
                str(expansion_chart.path),
                *options,
                "--dry-run",
                "--artifact-dir",
                str(expansion_chart.path / "reports"),
            ]
        )
        == 0
    )
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "dry-run"
    assert report["failure_expansion"]["enabled"] is True
    assert report["failure_expansion"]["maximum_additional_iterations"] > 0
    if "--filter" in options:
        assert report["trim_topology"] == 2
        assert report["trim_random"] == (0 if options == ["--filter"] else 1)
    assert main(["test", str(expansion_chart.path), "--expand-failures", "--whole-chart"]) == 2


@pytest.mark.parametrize("traversal", ["random", "linear"])
def test_filter_cli_expands_observed_failures(
    expansion_chart: Chart, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], traversal: str
) -> None:
    """
    Enable actual failure expansion through the preset before either traversal order.

    Args:
        expansion_chart (Chart): Finite chart with four members per output region.
        monkeypatch (pytest.MonkeyPatch): Substitute a renderer rejecting the faulty region.
        capsys (pytest.CaptureFixture[str]): Capture the CLI execution report.
        traversal (str): Requested order of the initially filtered configurations.

    Returns:
        None: The preset executes all omitted faulty members without duplicate renders.
    """
    from hypothesis_helm.cli import main

    calls: list[dict[str, object]] = []

    def render(chart: Chart, values: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record execution and fail each member of the fixture's faulty output region.

        Args:
            chart (Chart): Chart under test.
            values (dict[str, object]): Selected overrides.
            **kwargs (object): Renderer settings.

        Returns:
            list[dict[str, object]]: Successful baseline or nonfaulty manifest output.
        """
        calls.append(values)
        if values.get("a"):
            raise ValueError("faulty output region")
        return error_output(values)

    monkeypatch.setattr("hypothesis_helm.charts.runner.render", render)
    assert (
        main(
            [
                "test",
                str(expansion_chart.path),
                "--filter",
                "--no-infer-groups",
                "--traversal-strategy",
                traversal,
                "--artifact-dir",
                str(expansion_chart.path / "reports"),
            ]
        )
        == 1
    )
    report = json.loads(capsys.readouterr().out)
    assert report["failure_expansion"]["enabled"] is True
    assert report["failure_expansion"]["additional_executed"] == 3
    assert report["failed_iterations"] == 4
    assert len({configuration_key(value) for value in calls}) == len(calls)


@pytest.mark.parametrize(
    "individual",
    [["--trim-topology", "0"], ["--expand-failures"]],
)
@pytest.mark.parametrize("preset_first", [False, True])
def test_filter_exclusivity(individual: list[str], preset_first: bool) -> None:
    """
    Reject preset mixing in either order while retaining individual composition.

    Args:
        individual (list[str]): Individual method, including an explicit zero level.
        preset_first (bool): Whether the preset appears before the individual option.

    Returns:
        None: Parser errors occur before command execution.
    """
    from hypothesis_helm.cli import argument_parser

    parser = argument_parser()
    options = ["--filter", *individual] if preset_first else [*individual, "--filter"]
    with pytest.raises(SystemExit) as error:
        parser.parse_args(["test", *options])
    assert error.value.code == 2
    parsed = parser.parse_args(["test", "--trim-random", "1", "--trim-topology", "2", "--expand-failures"])
    assert (parsed.trim, parsed.trim_topology, parsed.expand_failures) == (1, 2, True)


def test_structure_depth_sweep(expansion_chart: Chart, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep depth comparisons matched and preserve pending expansion when the budget expires.

    Args:
        expansion_chart (Chart): Two-region fixture with a known failing region.
        monkeypatch (pytest.MonkeyPatch): Substitute deterministic physical render observations.

    Returns:
        None: Coverage is observed, depths are isolated and censored work is explicit.
    """
    from itertools import product

    from hypothesis_helm.benchmarking.studies.structure_depth import sweep

    values: list[dict[str, object]] = [dict(zip(("a", "b", "c"), items, strict=True)) for items in product((False, True), repeat=3)]
    reference: dict[str, object] = {
        "structure": "fixture",
        "values": values,
        "outcomes": [json.loads(bundle_key(error_output(value))) for value in (values[0], values[4])],
        "outcome_indices": [0] * 4 + [1] * 4,
    }
    calls: list[dict[str, object]] = []

    def observed(chart: Chart, value: dict[str, object], **kwargs: object) -> list[dict[str, object]]:
        """
        Record every physical expansion execution and return independent oracle resources.

        Args:
            chart (Chart): Fixed chart.
            value (dict[str, object]): Executed input.
            **kwargs (object): Fixed render context.

        Returns:
            list[dict[str, object]]: Observed manifest bundle.
        """
        calls.append(value)
        return error_output(value)

    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.expansion.render", observed)
    rows = sweep(expansion_chart, reference, [0, 1, 2, 3], 2026, "helm", 30)
    assert rows[0]["initial_checks"] == 8
    assert all(row["erroneous_inputs_found"] == 4 for row in rows)
    assert all(row["trim_random"] == 0 and row["expand_failures"] for row in rows)
    assert sum(int(str(row["additional_executed"])) for row in rows) == len(calls)
    assert all(len(sequence(row["checked_indices"])) == len(set(sequence(row["checked_indices"]))) for row in rows)
    stopped = sweep(expansion_chart, reference, [1, 2], 2026, "helm", 0)
    assert len(stopped) == 1
    assert stopped[0]["status"] == "time-limit"
    assert stopped[0]["remaining"] == 3


def test_pca_presets_expand_only_observed_failures(expansion_chart: Chart) -> None:
    """
    Include default preset expansion in PCA without consulting injected fault identities.

    Args:
        expansion_chart (Chart): Two-region chart with one independently observed failing output.

    Returns:
        None: Correct observations do not expand; observed failures add each region member once.
    """
    from itertools import product

    from hypothesis_helm.benchmarking.analysis.selection import PRESETS
    from hypothesis_helm.benchmarking.studies.pca import expand_selections

    values: list[dict[str, object]] = [dict(zip(("a", "b", "c"), items, strict=True)) for items in product((False, True), repeat=3)]
    selected = {strategy: [0, 4] for strategy in PRESETS}
    added = expand_selections(expansion_chart, values, selected, [error_output(values[0])] * len(values))
    assert all(count == 0 for count in added.values())
    assert all(indices == [0, 4] for indices in selected.values())
    added = expand_selections(expansion_chart, values, selected, [error_output(value) for value in values])
    assert all(count == 3 for count in added.values())
    assert all(set(indices) == {0, 4, 5, 6, 7} and len(indices) == 5 for indices in selected.values())
