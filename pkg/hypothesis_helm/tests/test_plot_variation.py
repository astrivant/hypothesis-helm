"""
Verify empirical spread, pairing, censoring and physically bounded plot annotations.
"""

import math
from pathlib import Path

import numpy as np
import pytest
from matplotlib import pyplot as plt
from matplotlib.collections import PolyCollection

from hypothesis_helm.benchmarking.reporting.plots import finish, measured_line, paired_ratios
from hypothesis_helm.benchmarking.reporting.variation import repeated_line


def test_sample_deviation_and_physical_bounds(tmp_path: Path) -> None:
    """
    Check n minus one deviations and both band widths against known numerical answers.

    Args:
        tmp_path (Path): Saved figure destination.

    Returns:
        None: The graph uses sample spread, bounds percentages and reports its sample size.
    """
    figure, axis = plt.subplots()
    centers = repeated_line(axis, [1, 2], [[0, 2, 4], [96, 98, 100]], "recall", "blue", upper=100)
    assert centers == [2, 98]
    areas = [item for item in axis.collections if isinstance(item, PolyCollection)]
    assert len(areas) == 2
    outer = np.asarray(areas[0].get_paths()[0].vertices, dtype=float)
    inner = np.asarray(areas[1].get_paths()[0].vertices, dtype=float)
    assert set(outer[outer[:, 0] == 1, 1]) == {0, 6}
    assert set(inner[inner[:, 0] == 1, 1]) == {0, 4}
    assert set(outer[outer[:, 0] == 2, 1]) == {94, 100}
    assert set(inner[inner[:, 0] == 2, 1]) == {96, 100}
    finish(figure, tmp_path, "variation", "Repeated seed trials.", question="How much do results vary across seeds?")
    svg = (tmp_path / "variation.svg").read_text()
    assert "n=3" in svg and "not confidence intervals" in svg


def test_singletons_and_missing_points_have_no_estimated_spread() -> None:
    """
    Keep missing observations distinct from exact zero spread and avoid bridging their gaps.

    Returns:
        None: Single measurements get no band; repeated estimates on either side remain disconnected.
    """
    figure, axis = plt.subplots()
    centers = repeated_line(axis, [1, 2, 3], [[10], [], [30]], "single", "blue")
    assert centers[0] == 10 and math.isnan(centers[1]) and centers[2] == 30
    assert not axis.collections
    plt.close(figure)
    figure, axis = plt.subplots()
    repeated_line(axis, [1, 2, 3], [[8, 12], [], [28, 32]], "repeated", "blue")
    for collection in axis.collections:
        if isinstance(collection, PolyCollection):
            assert len(collection.get_paths()) == 2
            assert all(len(set(np.asarray(path.vertices, dtype=float)[:, 0])) == 1 for path in collection.get_paths())
    plt.close(figure)


def test_censored_batch_is_marked_without_a_runtime_band() -> None:
    """
    Exclude partially capped batches rather than inventing a completed runtime distribution.

    Returns:
        None: The capped point remains visible, with no connected runtime estimate or spread.
    """
    figure, axis = plt.subplots()
    batches: list[list[dict[str, object]]] = [
        [{"status": "passed", "elapsed_seconds": 2}, {"status": "passed", "elapsed_seconds": 4}],
        [{"status": "passed", "elapsed_seconds": 5}, {"status": "time-limit", "elapsed_seconds": 9}],
    ]
    measured_line(axis, [1, 2], batches, "elapsed_seconds", "runtime", "blue")
    assert np.isnan(np.asarray(axis.lines[0].get_ydata(), dtype=float)[1])
    for area in (item for item in axis.collections if isinstance(item, PolyCollection)):
        assert all(set(np.asarray(path.vertices, dtype=float)[:, 0]) == {1} for path in area.get_paths())
    assert np.asarray(axis.collections[-1].get_offsets(), dtype=float).tolist() == [[2, 7]]
    plt.close(figure)


def test_scaling_variation_uses_paired_ratios() -> None:
    """
    Preserve paired observations instead of dividing independently averaged timings.

    Returns:
        None: Ratios match repeats regardless of order and omit unmatched or capped observations.
    """
    baseline: list[dict[str, object]] = [
        {"repeat": 0, "status": "passed", "elapsed_seconds": 10},
        {"repeat": 1, "status": "passed", "elapsed_seconds": 30},
        {"repeat": 2, "status": "time-limit", "elapsed_seconds": 99},
    ]
    parallel: list[dict[str, object]] = [
        {"repeat": 1, "status": "passed", "elapsed_seconds": 3},
        {"repeat": 0, "status": "passed", "elapsed_seconds": 2},
        {"repeat": 2, "status": "passed", "elapsed_seconds": 1},
        {"repeat": 3, "status": "passed", "elapsed_seconds": 1},
    ]
    assert paired_ratios(baseline, parallel) == [10, 5]
    figure, axis = plt.subplots()
    centers = repeated_line(axis, [2], [paired_ratios(baseline, parallel)], "speedup", "blue")
    assert centers == [7.5]
    assert centers[0] != pytest.approx(40 / 5)
    assert len([item for item in axis.collections if isinstance(item, PolyCollection)]) == 2
    plt.close(figure)
