"""
Verify controlled error populations, real-render assertions, and refreshable comparison surfaces.
"""

import itertools
import json
import shutil
import statistics
from functools import partial
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.charts.error_surface import ErrorPopulation, configure_surface, surface_manifests
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, case_path
from hypothesis_helm.benchmarking.charts.generator import generate, reproduce
from hypothesis_helm.benchmarking.charts.workload import source_digest
from hypothesis_helm.benchmarking.studies.error_surface import METHODS, main, verify
from hypothesis_helm.benchmarking.studies.matrix import bundle_key, measure, reference_space
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.reporting.budget import TimeLimitReached


def test_error_population_control() -> None:
    """
    Keep exact counts and nested prefixes while independently varying measured clustering.

    Returns:
        None: Endpoints, reproducibility, and higher neighbourhood concentration are established.
    """
    paths = tuple(f"switch{index}" for index in range(8))
    scattered, grouped = [], []
    for seed in range(20):
        previous: frozenset[int] = frozenset()
        for rate in (0, 1, 5, 25, 100):
            population = ErrorPopulation.build(paths, rate, 0.5, seed)
            assert len(population.failed) == 256 * rate // 100
            assert previous <= population.failed
            assert population == ErrorPopulation.build(paths, rate, 0.5, seed)
            assert population.neighbor_fraction is None if rate == 0 else population.neighbor_fraction is not None
            previous = population.failed
        scattered.append(float(str(ErrorPopulation.build(paths, 25, 0, seed).neighbor_fraction)))
        grouped.append(float(str(ErrorPopulation.build(paths, 25, 1, seed).neighbor_fraction)))
    assert statistics.mean(grouped) > statistics.mean(scattered) + 0.2
    with pytest.raises(ValueError):
        ErrorPopulation.build(paths, float("nan"), 0, 0)
    with pytest.raises(ValueError):
        ErrorPopulation.build(paths, 25, 2, 0)


@pytest.mark.integration
def test_surface_recipe_and_real_oracle(tmp_path: Path) -> None:
    """
    Reproduce one chart and validate every input against an independent output specification.

    Args:
        tmp_path (Path): Retained recipe and replay directory.

    Returns:
        None: Renaming, nested resources, error labels and recipe replay match actual Helm renders.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required")
    logical = tmp_path / "charts" / "surface"
    with FixtureWorkspace() as workspace:
        generate(logical, input_complexity=3, output_bins=2, workspace=workspace)
        spec = configure_surface(logical, 2, workspace=workspace)
        chart = Chart.load(workspace.chart)
        checksum = source_digest(chart.path)
        population = ErrorPopulation.build(tuple(sorted(chart.defaults)), 25, 1, 17)
        found = 0
        for bits in itertools.product((False, True), repeat=3):
            values: dict[str, object] = dict(zip(population.paths, bits, strict=True))
            actual = render(chart, values, release="matrix", stream=False)
            assert bundle_key(actual) == bundle_key(surface_manifests(values, spec))
            found += population.erroneous(values, actual, spec)
        assert found == 2
        assert source_digest(chart.path) == checksum
        reproduced = reproduce(case_path(logical), tmp_path / "replay")
        assert reproduced == spec
        assert source_digest(tmp_path / "replay") == checksum
        generate(tmp_path / "replay", input_complexity=3, output_bins=2, force=True)
        assert not (tmp_path / "replay/templates/surface.yaml").exists()


@pytest.mark.integration
def test_surface_endpoints_and_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Evaluate each method's assertions even when render equivalence avoids a Helm invocation.

    Args:
        tmp_path (Path): Reusable chart and retained case location.
        monkeypatch (pytest.MonkeyPatch): Inject an execution deadline after successful endpoint checks.

    Returns:
        None: Zero errors never expand; full errors expand filtered regions; partial execution retains counts.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required")
    logical = tmp_path / "charts" / "surface"
    with FixtureWorkspace() as workspace:
        generate(logical, input_complexity=3, output_bins=2, workspace=workspace)
        spec = configure_surface(logical, 0, workspace=workspace)
        chart = Chart.load(workspace.chart)
        reference = reference_space(chart, spec, 8)
        for percent in (0, 50, 100):
            population = ErrorPopulation.build(tuple(sorted(chart.defaults)), percent, 0, 5)
            for method in METHODS:
                row = measure(
                    chart,
                    spec,
                    method,
                    level=2,
                    seed=1,
                    limit=8,
                    seconds=30,
                    helm="helm",
                    reference=reference,
                    failure_oracle=partial(population.erroneous, spec=spec),
                )
                assert row["status"] == "passed"
                assert int(str(row["erroneous_inputs_evaluated"])) <= len(population.failed)
                if method in {"default", "exact-equivalence"}:
                    assert row["completed"] == 8
                    assert row["erroneous_inputs_evaluated"] == len(population.failed)
                if percent == 0:
                    assert row["additional_scheduled"] == row["erroneous_inputs_evaluated"] == 0
                if method == "filter" and percent == 100:
                    assert row["completed"] == 8 and int(str(row["additional_executed"])) > 0

        def expired(*args: object, **kwargs: object) -> list[dict[str, object]]:
            """
            Simulate the deadline before any Helm output is returned.

            Args:
                *args (object): Renderer positional arguments.
                **kwargs (object): Renderer keyword arguments.

            Returns:
                list[dict[str, object]]: Never returned before the simulated deadline.
            """
            raise TimeLimitReached()

        monkeypatch.setattr("hypothesis_helm.benchmarking.studies.matrix.render", expired)
        row = measure(
            chart,
            spec,
            "default",
            level=2,
            seed=1,
            limit=8,
            seconds=30,
            helm="helm",
            reference=reference,
            failure_oracle=partial(population.erroneous, spec=spec),
        )
        assert row["status"] == "time-limit" and row["completed"] == 0 and row["remaining"] == 8


@pytest.mark.integration
def test_surface_command_and_plots(tmp_path: Path) -> None:
    """
    Publish a small spread with zero-error N/A cells and reject a damaged ledger.

    Args:
        tmp_path (Path): Complete small real-Helm experiment.

    Returns:
        None: All requested rows, figures, means and independent oracle populations are retained.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required")
    args = [
        "--output-size",
        "2x2",
        "--input-complexity",
        "3",
        "--axes",
        "depth",
        "redundancy",
        "clustering",
        "--depths",
        "0",
        "2",
        "--redundant-inputs",
        "0",
        "2",
        "--clustering",
        "0",
        "1",
        "--error-rates",
        "0",
        "25",
        "100",
        "--methods",
        "default",
        "filter",
        "--repeats",
        "1",
        "--output",
        str(tmp_path),
    ]
    assert main(args) == 0
    result = json.loads((tmp_path / "results.json").read_text())
    verify(result)
    assert len(result["rows"]) == 36
    assert all(row["error_recall"] is None for row in result["rows"] if row["error_count"] == 0)
    assert len(list(tmp_path.glob("*.png"))) == len(list(tmp_path.glob("*.svg"))) == 13
    assert (tmp_path / "clustering-counts.md").is_file()
    assert (tmp_path / "summary.csv").is_file()
    assert not list(tmp_path.rglob("Chart.yaml"))
    result["rows"][-1] = result["rows"][0]
    with pytest.raises(AssertionError):
        verify(result)


@pytest.mark.parametrize("size", ["11x13", "21x21", "2x2", "5X7"])
def test_output_grid(size: str) -> None:
    """
    Produce unique measured settings with endpoints at the requested dimensions.

    Args:
        size (str): Supported dimension spelling.

    Returns:
        None: Assertions verify counts, endpoints and preserved default rates.
    """
    from hypothesis_helm.benchmarking.studies.error_surface import RATES, grid_values, output_size

    dimensions = output_size(size)
    clustering, rates = grid_values(dimensions)
    assert (len(clustering), len(rates)) == dimensions
    assert len(set(clustering)) == len(clustering)
    assert len(set(rates)) == len(rates)
    assert (clustering[0], clustering[-1], rates[0], rates[-1]) == (0, 1, 0, 100)
    if dimensions == (11, 13):
        assert rates == list(RATES)


@pytest.mark.parametrize("size", ["11", "11x", "1x13", "0x0", "11x13x2", "axt", "2.5x3"])
def test_invalid_output_grid(size: str) -> None:
    """
    Reject malformed or degenerate grid dimensions before starting measurements.

    Args:
        size (str): Invalid dimensions.

    Returns:
        None: Parsing fails with a CLI-compatible error.
    """
    import argparse

    from hypothesis_helm.benchmarking.studies.error_surface import output_size

    with pytest.raises(argparse.ArgumentTypeError):
        output_size(size)
