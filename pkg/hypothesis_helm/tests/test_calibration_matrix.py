"""
Test matching boundaries, protected selection and evidence-matrix decisions.
"""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import given
from hypothesis import strategies as st

from hypothesis_helm.benchmarking.analysis.calibration_matrix import METRIC, evaluate
from hypothesis_helm.execution.aggressive import matching_profiles
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.schemas.contracts import mapping, sequence


def description(score: int) -> dict[str, object]:
    """
    Build a controlled descriptor with exactly one changing coordinate.

    Args:
        score (int): Maximum output score.

    Returns:
        dict[str, object]: A synthetic matching fixture, not empirical calibration.
    """
    return {
        "profile_version": "sampling-topology-v1",
        "features": {
            "maximum_score": score,
            "input_fields": 6,
            "domain_sizes": [2] * 6,
            "domain_kinds": ["bool"],
            "gate_depth": 2,
            "interaction_order": 3,
        },
        "region_sizes": [[63, 16]],
        "context": {"strength": 2, "trim": 0, "trim_topology": 2},
        "unit": "non-default configuration",
    }


def evidence() -> dict[str, object]:
    """
    Surround a target with two measured coordinates for bounded lookup tests.

    Returns:
        dict[str, object]: Nearby matching fixture with a 20% radius.
    """
    return {
        "profiles": [{"descriptor": description(score), "minimum_cases": 2, "minimum_fields": 1} for score in [90, 110]],
        "approximation": {"enabled": True, "metric": METRIC, "radius": 0.2},
    }


def test_nearby_lookup_is_bounded_and_exact_takes_precedence() -> None:
    """
    Prefer exact matches and prohibit extrapolation even when a point is close.

    Returns:
        None: Only interior compatible targets use neighboring evidence.
    """
    document = evidence()
    matches, method, distance = matching_profiles(document, description(100))
    assert len(matches) == 2 and method == "nearby"
    assert distance == pytest.approx(10 / 110)
    assert matching_profiles(document, description(90))[1:] == ("exact", 0.0)
    assert matching_profiles(document, description(111)) == ([], "outside measured range", None)


@pytest.mark.parametrize("change", ["context", "domain", "kinds", "version", "unit", "depth"])
def test_incompatible_profiles_keep_all_cases(change: str) -> None:
    """
    Refuse to transfer evidence across unmeasured structural or execution differences.

    Args:
        change (str): Coordinate or categorical contract changed on the target.

    Returns:
        None: No matching profile is returned.
    """
    target = json.loads(json.dumps(description(100)))
    if change == "context":
        target["context"]["strength"] = 3
    elif change == "domain":
        target["features"]["domain_sizes"] = [3] * 6
    elif change == "kinds":
        target["features"]["domain_kinds"] = ["str"]
    elif change == "depth":
        target["features"]["gate_depth"] = 3
    else:
        target["profile_version" if change == "version" else "unit"] = "different"
    assert matching_profiles(evidence(), target)[0] == []


@pytest.mark.parametrize("radius", [0, -1, 0.51, float("inf"), float("nan")])
def test_invalid_radius_disables_approximation(radius: float) -> None:
    """
    Reject nonfinite, nonpositive and overly broad approximation thresholds.

    Args:
        radius (float): Invalid configured radius.

    Returns:
        None: No nearby evidence can authorize sampling.
    """
    document = evidence()
    document["approximation"] = {"enabled": True, "metric": METRIC, "radius": radius}
    assert matching_profiles(document, description(100))[0] == []


@given(seed=st.integers(), percent=st.integers(1, 100), floor=st.integers(0, 12))
def test_sampling_preserves_protected_cases_and_order_independence(seed: int, percent: int, floor: int) -> None:
    """
    Check selector invariants over seeds, percentage quotas and field floors.

    Args:
        seed (int): Seed controlling identity ranking.
        percent (int): Retained percentage.
        floor (int): Requested number of distinct fields, sometimes unattainable.

    Returns:
        None: Protected cases survive; selection is unique, deterministic and independent of input ordering.
    """
    values = list(range(20))
    protected = {"19", "17"}
    sampling = Sampling(percent, 1)
    selected, report = sampling.select(values, str, seed, protected=protected, fields=lambda value: {str(value % 10)}, minimum_fields=floor)
    reversed_selection, _ = sampling.select(
        values[::-1], str, seed, protected=protected, fields=lambda value: {str(value % 10)}, minimum_fields=floor
    )
    assert {17, 19} <= set(selected)
    assert len(selected) == len(set(selected))
    assert set(selected) == set(reversed_selection)
    assert int(str(report["retained"])) + int(str(report["omitted"])) == len(values)
    assert int(str(report["selected_fields"])) >= min(floor, 10)
    if floor > 10:
        assert selected == values and not report["field_floor_met"]


def test_matrix_excludes_target_and_requires_useful_measured_reduction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise the complete decision matrix on a small fully specified population.

    Args:
        tmp_path (Path): Written evidence matrix.
        monkeypatch (pytest.MonkeyPatch): Skip plotting in this numerical regression test.

    Returns:
        None: Interior neighbors reduce work, endpoints fall back, and insufficient trials disable the policy.
    """
    profiles = []
    for score in [90, 100, 110]:
        profiles.append(
            {
                "case": f"score-{score}",
                "descriptor": description(score),
                "minimum_cases": 2,
                "minimum_fields": 1,
                "evidence": {"trials": 100, "seed_start": 0, "known_bugs": 1},
                "reference": {
                    "defaults": {"value": 0},
                    "baseline_bugs": [],
                    "cases": [{"values": {"value": index}, "bugs": ["bug"], "region": "one"} for index in range(1, 64)],
                },
            }
        )
    # A second interior target is required before a radius can be useful on two cases.
    fourth = deepcopy(profiles[1])
    fourth["case"] = "score-105"
    fourth["descriptor"] = description(105)
    profiles.append(fourth)
    document: dict[str, object] = {"profiles": profiles, "metadata": {"test_only": True}}
    monkeypatch.setattr("hypothesis_helm.benchmarking.analysis.calibration_matrix.plot", lambda *_: None)
    evaluate(tmp_path, document)
    matrix = json.loads((tmp_path / "matrix.json").read_text())
    assert matrix["policy"]["enabled"] is True
    assert matrix["policy"]["radius"] == 0.1
    target = [row for row in matrix["rows"] if row["case"] == "score-100" and row["strategy"] == "nearby-0.1"][0]
    assert target["match"] == "nearby" and target["mean_extra_omitted"] > 0
    assert target["target_successes"] == 100
    endpoint = [row for row in matrix["rows"] if row["case"] == "score-90" and row["strategy"] == "nearby-0.1"][0]
    assert endpoint["match"] == "outside measured range" and endpoint["mean_extra_omitted"] == 0
    for cell in profiles:
        mapping(cell["evidence"])["trials"] = 1
    evaluate(tmp_path, document)
    assert json.loads((tmp_path / "matrix.json").read_text())["policy"]["enabled"] is False
    for cell in profiles:
        mapping(cell["evidence"])["trials"] = 100
        for index, row in enumerate(sequence(mapping(cell["reference"])["cases"])):
            mapping(row)["bugs"] = ["bug"] if index == 0 else []
    evaluate(tmp_path, document)
    assert json.loads((tmp_path / "matrix.json").read_text())["policy"]["enabled"] is False


def test_calibration_command_writes_reproducible_matrix_and_plots(tmp_path: Path) -> None:
    """
    Render a complete tiny population and regenerate its plots from recorded evidence.

    Args:
        tmp_path (Path): Output directory for native Helm calibration artifacts.

    Returns:
        None: The command writes full reference data, numerical matrices, PNG/SVG plots and redrawable reports.
    """
    from hypothesis_helm.benchmarking.studies.calibration import main

    output = tmp_path / "study"
    assert (
        main(
            [
                "--output",
                str(output),
                "--inputs",
                "3",
                "--depths",
                "1",
                "--placements",
                "1",
                "--trials",
                "2",
                "--breadths",
                "1",
                "2",
                "--output-depths",
                "0",
                "1",
            ]
        )
        == 0
    )
    document = json.loads((output / "calibration.json").read_text())
    assert document["status"] == "complete"
    assert len(document["profiles"]) == 4
    assert all(cell["evidence"]["reference_renders"] == 8 for cell in document["profiles"])
    assert all(cell["faults"] == document["profiles"][0]["faults"] for cell in document["profiles"])
    dimensions = [cell["analysis"]["complexity"]["maximum_output"] for cell in document["profiles"]]
    assert len({cell["breadth"] for cell in dimensions}) == len({cell["depth"] for cell in dimensions}) == 2
    assert len({cell["score"] for cell in dimensions}) == 4
    assert document["approximation"]["enabled"] is False
    recorded = (output / "calibration.json").read_bytes()
    assert main(["--output", str(output), "--plot-only"]) == 0
    assert (output / "calibration.json").read_bytes() == recorded
    for name in ("calibration", "matching-matrix", "profile-variation", "complexity-sweep"):
        for extension in ("png", "svg"):
            assert (output / f"{name}.{extension}").stat().st_size > 1000
    assert len(json.loads((output / "matrix.json").read_text())["rows"]) == 24
    assert (output / "MATRIX.md").is_file() and (output / "matrix.csv").is_file()
    assert not list(output.rglob("Chart.yaml"))


def test_plot_export_preserves_all_heatmap_rows(tmp_path: Path) -> None:
    """
    Preserve image extents when the shared plot exporter handles an inverted Y axis.

    Args:
        tmp_path (Path): Heatmap output location.

    Returns:
        None: Export cannot crop a multi-row matrix down to its first row.
    """
    from matplotlib import pyplot as plt

    from hypothesis_helm.benchmarking.reporting.plots import finish

    figure, axis = plt.subplots()
    axis.imshow([[1, 2], [3, 4], [5, 6]])
    limits = axis.get_ylim()
    finish(figure, tmp_path, "heatmap", "Three rows must remain visible.", question="How do the three recorded cases compare?")
    assert axis.get_ylim() == limits


def test_shaped_fixture_replays_the_same_fault_outputs(tmp_path: Path) -> None:
    """
    Reproduce sibling copies and nested envelopes from the retained shared-chart recipe.

    Args:
        tmp_path (Path): Independent generated and replayed chart locations.

    Returns:
        None: Replay preserves exact manifests, all defect copies and the measured tree shape.
    """
    from hypothesis_helm.benchmarking.charts.faults import Fault, write_faults
    from hypothesis_helm.benchmarking.charts.generator import generate, reproduce
    from hypothesis_helm.benchmarking.charts.shape import fault_outputs, reshape_faults
    from hypothesis_helm.charts.model import Chart
    from hypothesis_helm.charts.rendering import render

    source, target = tmp_path / "source", tmp_path / "replayed"
    generate(source, input_complexity=3, output_bins=2)
    values = Chart.load(source).defaults
    fault = Fault("bug", {next(iter(values)): True})
    write_faults(source, [fault], symbolic=True)
    reshape_faults(source, 3, 2)
    values = {key: True for key in values}
    actual = render(Chart.load(source), values, stream=False)
    assert list(fault_outputs(actual)) == [{"bug": "incorrect"}] * 3
    reproduce(source / "benchmark-parameters.yaml", target)
    assert render(Chart.load(target), values, stream=False) == actual
