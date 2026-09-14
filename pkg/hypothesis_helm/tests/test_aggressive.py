"""
Verify fresh per-chart calibration, protected regions and explicit sampling fallback.
"""

import json
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.cli import argument_parser, main
from hypothesis_helm.compiler.passes.sampling import profile
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.execution.aggressive import CALIBRATION_VERSION, descriptor, select
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import mapping
from hypothesis_helm.schemas.model import ValuesModel


def calibrated(tmp_path: Path) -> tuple[Chart, Path]:
    """
    Construct a small supported chart and an explicit policy fixture for selector tests.

    Args:
        tmp_path (Path): Fixture directory separate from execution artifacts.

    Returns:
        tuple[Chart, Path]: Loaded chart and matching test-only calibration.
    """
    root = tmp_path / "chart"
    generate(root, input_complexity=8, output_bins=2)
    chart = Chart.load(root)
    plan = plan_interactions(ValuesModel.from_schema(chart.schema), 2, max_cases=4096, max_candidates=4096, exhaustive_threshold=10000)
    values = [value for value in plan.values if value != chart.defaults]
    _, topology = trim_topology(chart.path, chart.defaults, values, values, 2, 0)
    document = {
        "version": CALIBRATION_VERSION,
        "status": "complete",
        "id": "selector-test-only",
        "profiles": [
            {
                "descriptor": descriptor(profile(chart), topology, {"strength": 2, "trim": 0, "trim_topology": 2}),
                "minimum_cases": 2,
                "minimum_fields": 8,
            }
        ],
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(document))
    return chart, path


def test_calibrated_selection_runs_real_helm(tmp_path: Path) -> None:
    """
    Execute the real CLI with a matched policy and verify actual retained-case accounting.

    Args:
        tmp_path (Path): Native chart, test-only calibration and report location.

    Returns:
        None: The preset enables expansion, preserves regions and drops only additional eligible cases.
    """
    chart, calibration = calibrated(tmp_path)
    output = tmp_path / "reports"
    assert (
        main(
            [
                "test",
                str(chart.path),
                "--filter-adaptive",
                "--sampling-calibration",
                str(calibration),
                "--artifact-dir",
                str(output),
                "--time-limit",
                "10s",
            ]
        )
        == 0
    )
    report = json.loads((output / "report.json").read_text())
    sampling = report["sampling"]
    assert sampling["aggressive"]["fallback"] is None
    assert sampling["percent"] == 70
    assert 0 < sampling["omitted"] < sampling["eligible"]
    assert sampling["protected"] == 2
    assert sampling["selected_fields"] == 8
    assert report["expand_failures"] is True
    assert report["attempts"] == sampling["retained"] + 1


@pytest.mark.parametrize("cause", ["missing", "unmatched", "unknown", "incomplete"])
def test_uncalibrated_cases_are_retained(tmp_path: Path, cause: str) -> None:
    """
    Retain the ordinary filtered plan whenever calibrated selection is unsupported.

    Args:
        tmp_path (Path): Finite chart and editable calibration fixture.
        cause (str): Missing evidence, changed topology, opaque code or incomplete study.

    Returns:
        None: Additional sampling is disabled and its reason is visible.
    """
    chart, calibration = calibrated(tmp_path)
    if cause == "missing":
        calibration = tmp_path / "absent.json"
    elif cause == "unmatched":
        document = json.loads(calibration.read_text())
        document["profiles"][0]["descriptor"]["features"]["maximum_score"] += 1
        calibration.write_text(json.dumps(document))
    elif cause == "unknown":
        (chart.path / "templates/opaque.yaml").write_text('{{ include "unknown" . }}')
    else:
        document = json.loads(calibration.read_text())
        document["status"] = "time-limit"
        calibration.write_text(json.dumps(document))
    report = check_chart(
        chart,
        permutations=2,
        trim_topology=2,
        expand_failures=True,
        sampling=Sampling(aggressive=True, calibration=str(calibration)),
        dry_run=True,
    )
    sampling = mapping(report["sampling"])
    assert sampling["omitted"] == 0
    assert sampling["retained"] == sampling["eligible"]
    assert mapping(sampling["aggressive"])["fallback"]


def test_repeated_visits_recompute_complexity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Recompute even when the same chart and policy object are used on a later visit.

    Args:
        tmp_path (Path): Revisited chart and calibration fixture.
        monkeypatch (pytest.MonkeyPatch): Record actual profile calls.

    Returns:
        None: Each invocation measures current bytes; later changes cannot reuse the previous score.
    """
    chart, calibration = calibrated(tmp_path)
    calls = []

    def measured(source: Chart) -> dict[str, object]:
        """
        Record a real fresh compiler analysis.

        Args:
            source (Chart): Current chart.

        Returns:
            dict[str, object]: New topology measurements.
        """
        result = profile(source)
        calls.append(result)
        return result

    monkeypatch.setattr("hypothesis_helm.charts.planning.sampling_profile", measured)
    sampling = Sampling(aggressive=True, calibration=str(calibration))
    for _ in range(2):
        check_chart(chart, permutations=2, trim_topology=2, sampling=sampling, dry_run=True)
    assert len(calls) == 2
    assert calls[0] is not calls[1]
    assert calls[0]["fingerprint"] == calls[1]["fingerprint"]


def test_stale_snapshot_disables_selection(tmp_path: Path) -> None:
    """
    Refuse a stale profile even when a previous calibration would have matched.

    Args:
        tmp_path (Path): Mutable source chart.

    Returns:
        None: The profile is recomputed and the original eligible cases remain selected.
    """
    chart, calibration = calibrated(tmp_path)
    analysis = profile(chart)
    (chart.path / "changed.txt").write_text("new snapshot")
    selected, report = select(
        chart,
        Sampling(aggressive=True, calibration=str(calibration)),
        [{}, chart.defaults],
        0,
        protected=set(),
        analysis=analysis,
        topology={},
        context={},
    )
    assert len(selected) == 2
    details = mapping(report["aggressive"])
    assert "changed" in str(details["fallback"])
    assert mapping(details["analysis"])["fingerprint"] != analysis["fingerprint"]


def test_field_floor_adds_cases_in_seeded_order() -> None:
    """
    Reach a rare path even when the percentage quota already has enough configurations.

    Returns:
        None: The field floor expands the selected subset without losing protected cases.
    """
    values = [str(index) for index in range(100)]
    small, _ = Sampling(1, 1).select(values, str, 0)
    rare = next(value for value in values if value not in small)
    selected, report = Sampling(1, 1).select(values, str, 0, fields=lambda value: {"rare" if value == rare else "common"}, minimum_fields=2)
    assert rare in selected and set(small) <= set(selected)
    assert report["selected_fields"] == 2
    assert Sampling(1, 1).select(values, str, 0, fields=lambda value: {"only"}, minimum_fields=2)[0] == values


@pytest.mark.parametrize("command", ["test", "scan"])
@pytest.mark.parametrize("options", [["--filter", "--filter-adaptive"], ["--filter-adaptive", "--filter"]])
def test_presets_are_exclusive(command: str, options: list[str]) -> None:
    """
    Reject conflicting presets regardless of argument order or discovery source.

    Args:
        command (str): Local testing or remote scanning.
        options (list[str]): Mutually exclusive presets.

    Returns:
        None: Argument parsing rejects both forms.
    """
    with pytest.raises(SystemExit):
        argument_parser().parse_args([command, ".", *options])


@pytest.mark.parametrize("command", ["test", "scan"])
def test_adaptive_flag_replaces_old_name(command: str) -> None:
    """
    Accept the renamed preset and reject the removed flag without an alias.

    Args:
        command (str): Local testing or remote scanning.

    Returns:
        None: Parser assertions verify the breaking rename.
    """
    parser = argument_parser()
    args = parser.parse_args([command, ".", "--filter-adaptive"])
    assert args.filter_adaptive is True
    with pytest.raises(SystemExit) as error:
        parser.parse_args([command, ".", "--filter-aggressive"])
    assert error.value.code == 2


def test_nearby_selection_uses_maximum_neighbor_floors(tmp_path: Path) -> None:
    """
    Apply the most demanding case and field floors separately across nearby evidence.

    Args:
        tmp_path (Path): Supported chart and two surrounding test-only profiles.

    Returns:
        None: The real planner reports nearby matching and uses both conservative floors.
    """
    chart, calibration = calibrated(tmp_path)
    document = json.loads(calibration.read_text())
    original = document["profiles"][0]
    profiles = []
    for delta, cases, fields in [(-1, 3, 7), (1, 2, 8)]:
        neighbor = json.loads(json.dumps(original))
        neighbor["descriptor"]["features"]["maximum_score"] += delta
        neighbor.update(minimum_cases=cases, minimum_fields=fields)
        profiles.append(neighbor)
    document.update(
        profiles=profiles,
        approximation={"enabled": True, "metric": "maximum-relative-coordinate-change-v1", "radius": 0.2},
    )
    calibration.write_text(json.dumps(document))
    report = check_chart(
        chart, permutations=2, trim_topology=2, sampling=Sampling(aggressive=True, calibration=str(calibration)), dry_run=True
    )
    selection = mapping(report["sampling"])
    assert mapping(selection["aggressive"])["match"] == "nearby"
    assert mapping(selection["aggressive"])["fallback"] is None
    assert selection["minimum"] == 3 and selection["minimum_fields"] == 8
    assert selection["selected_fields"] == 8


def test_empty_population_remains_empty() -> None:
    """
    Handle an empty eligible population without inventing work to meet a floor.

    Returns:
        None: Empty plans retain zero cases and honestly report an unmet field floor.
    """
    values: list[str] = []
    selected, report = Sampling(70, 128).select(values, str, 0, protected={"absent"}, fields=lambda _: {"field"}, minimum_fields=1)
    assert selected == []
    assert report["retained"] == report["omitted"] == report["protected"] == 0
    assert report["field_floor_met"] is False


@pytest.mark.parametrize("options", [["--sampling-calibration", "custom.json"], ["--filter-adaptive", "--sample-random", "50"]])
def test_invalid_calibration_options_are_cli_errors(options: list[str]) -> None:
    """
    Explain conflicting calibration options without an implementation traceback.

    Args:
        options (list[str]): Invalid option combination.

    Returns:
        None: Parsing stops with the conventional usage-error exit status.
    """
    with pytest.raises(SystemExit) as error:
        main(["test", ".", *options])
    assert error.value.code == 2


def test_archived_benchmark_labels_preserve_measurements() -> None:
    """
    Relabel historical display data without modifying its recorded source.

    Returns:
        None: Assertions verify nested labels, unchanged measurements and immutable source data.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    original = {"methods": ["filter-aggressive"], "strategies": {"filter-aggressive": {"seconds": 2.5}}}
    assert current_labels(original) == {"methods": ["filter-adaptive"], "strategies": {"filter-adaptive": {"seconds": 2.5}}}
    assert original == {"methods": ["filter-aggressive"], "strategies": {"filter-aggressive": {"seconds": 2.5}}}
