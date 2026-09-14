"""
Verify PCA feature identity, degenerate populations and real seeded fault projections.
"""

import shutil
from pathlib import Path

import numpy as np
import pytest

from hypothesis_helm.benchmarking.analysis.pca import inject_errors, manifest_features, project
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.structures import configmap
from hypothesis_helm.benchmarking.studies.pca import run_case
from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.schemas.contracts import mapping, number, sequence


def test_manifest_feature_identity() -> None:
    """
    Ignore resource document ordering while preserving resource multiplicity and scalar types.

    Returns:
        None: Feature identities distinguish relevant manifest changes.
    """
    first, second = configmap("first", {"value": 3}), configmap("second", {"value": "3"})
    assert manifest_features([first, second]) == manifest_features([second, first])
    assert manifest_features([first]) != manifest_features([first, first])
    assert manifest_features([configmap("first", {"value": "3"})]) != manifest_features([first])
    assert manifest_features([configmap("first", {"value": True})]) != manifest_features([first])


def test_pca_fixed_basis_and_variance() -> None:
    """
    Reconstruct scores from the stored full-population basis and preserve duplicate output scores.

    Returns:
        None: Coordinates and explained variance use a reproducible full-population fit.
    """
    bundles = [[configmap("sample", {"x": x, "y": y})] for x, y in ((0, 0), (1, 2), (3, 1), (0, 0))]
    scores, basis = project(bundles)
    features = sequence(basis["features"])
    matrix = np.array([[manifest_features(bundle).get(str(name), 0) for name in features] for bundle in bundles])
    expected = ((matrix - np.asarray(basis["center"])) / np.asarray(basis["scale"])) @ np.asarray(basis["components"]).T
    np.testing.assert_allclose(scores, expected)
    np.testing.assert_allclose(scores[0], scores[3])
    assert sum(number(value) for value in sequence(basis["explained_variance_ratio"])) == pytest.approx(1)
    assert np.linalg.norm(scores[0] - scores[1]) > 0


@pytest.mark.parametrize("bundles", [[[]], [[], []], [[configmap("same", {})]] * 3])
def test_pca_constant_population(bundles: list[list[dict[str, object]]]) -> None:
    """
    Represent a constant output population with finite zero coordinates and explained variance.

    Args:
        bundles (list[list[dict[str, object]]]): Identical or empty manifests.

    Returns:
        None: No invented PCA direction or NaN appears in a degenerate population.
    """
    scores, basis = project(bundles)
    assert scores.shape == (len(bundles), 2)
    assert np.all(scores == 0)
    assert basis["explained_variance_ratio"] == [0, 0]


@pytest.mark.integration
def test_seeded_errors_in_real_template(tmp_path: Path) -> None:
    """
    Check deterministic exact-size fault placement against Helm independently of the template tree.

    Args:
        tmp_path (Path): Generated fixture directory.

    Returns:
        None: Every sampled status matches the independent fault membership oracle.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm required")
    generate(tmp_path, input_complexity=6, output_bins=4, structure="boundaries")
    chart = Chart.load(tmp_path)
    values = [{**chart.defaults, "input002": value, "input000": bit} for value in (0, 1, 2) for bit in (False, True)]
    faults = inject_errors(tmp_path, values, 50, 1729)
    previous = (tmp_path / "templates/benchmark-error.yaml").read_bytes()
    assert len(faults) == 3
    assert inject_errors(tmp_path, values, 50, 1729) == faults
    assert (tmp_path / "templates/benchmark-error.yaml").read_bytes() == previous
    for index, value in enumerate(values):
        resources = render(Chart.load(tmp_path), value, release="matrix")
        error = next(item for item in resources if mapping(item["metadata"])["name"] == "benchmark-error")
        assert mapping(error["data"])["status"] == ("incorrect" if index in faults else "expected")


def test_deadline_saves_no_partial_pca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Keep an incomplete reference visibly incomplete instead of fitting misleading PCA axes.

    Args:
        tmp_path (Path): Fixture output directory.
        monkeypatch (pytest.MonkeyPatch): Replace rendering with a budget exception.

    Returns:
        None: Censored output retains accurate work statistics and has no fitted PCA.
    """
    from hypothesis_helm.reporting.budget import TimeLimitReached

    def expired(*args: object, **kwargs: object) -> list[dict[str, object]]:
        """
        Simulate an execution deadline during a render.

        Args:
            *args (object): Renderer positional arguments.
            **kwargs (object): Renderer keyword arguments.

        Returns:
            list[dict[str, object]]: Never returned because the deadline interrupts execution.
        """
        raise TimeLimitReached()

    monkeypatch.setattr("hypothesis_helm.benchmarking.studies.pca.render", expired)
    row = run_case(tmp_path, "equivalence", 6, 5, 1729, 2026, 2, "helm", 30)
    assert row["status"] == "time-limit"
    assert row["remaining"] == row["valid_inputs"]
    assert row["completed"] == 0
    assert "pca" not in row
