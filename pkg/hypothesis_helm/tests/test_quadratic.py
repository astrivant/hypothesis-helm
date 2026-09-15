"""
Check quadratic recovery, unsupported designs and paired surface publication.
"""

import itertools
import json
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.analysis.quadratic import fit
from hypothesis_helm.benchmarking.analysis.symbolic import partition
from hypothesis_helm.benchmarking.reporting.response_surface import plot
from hypothesis_helm.benchmarking.studies.polynomial_surface import main as compare


def test_known_quadratic() -> None:
    """
    Recover an interaction and both curvature terms in normalized coordinates.

    Returns:
        None: Assertions verify coefficients and predictions.
    """
    points = []
    for x, y in itertools.product((10.0, 20.0, 30.0), (0.0, 50.0, 100.0)):
        u, v = (x - 20) / 10, (y - 50) / 50
        points.append((x, y, 7 + 2 * u - 3 * v + 4 * u * v + 5 * u * u - 6 * v * v))
    model = fit(points)
    assert model.coefficients == pytest.approx((7, 2, -3, 4, 5, -6))
    assert model.rmse < 1e-12
    assert model.predict(15, 25) == pytest.approx(8.25)
    with pytest.raises(ValueError, match="outside"):
        model.predict(31, 0)


def test_invalid_designs_and_constant_response() -> None:
    """
    Reject insufficient, nonfinite, duplicate and rank-deficient inputs.

    Returns:
        None: Assertions verify rejection and constant-response diagnostics.
    """
    with pytest.raises(ValueError, match="six"):
        fit([(0.0, 0.0, 1.0)] * 6)
    with pytest.raises(ValueError, match="finite"):
        fit([(float(i), float(i), float("nan")) for i in range(9)])
    with pytest.raises(ValueError, match="average"):
        fit([(0.0, 0.0, 1.0)] * 9)
    with pytest.raises(ValueError, match="identify"):
        fit([(float(i), float(i), 1.0) for i in range(9)])
    model = fit([(float(x), float(y), 0.0) for x, y in itertools.product(range(3), repeat=2)])
    assert model.r_squared is None
    assert model.predict(1, 1) == 0


def test_quartic_recovers_two_diagonal_peaks_on_holdout() -> None:
    """
    Recover two isolated diagonal peaks from training data and predict reserved cells.

    Returns:
        None: The quartic recovers the known surface while the quadratic misses its valley.
    """

    def response(x: float, y: float) -> float:
        """
        Define a nonnegative quartic with peaks at opposite diagonal settings.

        Args:
            x (float): First normalized coordinate.
            y (float): Second normalized coordinate.

        Returns:
            float: Known surface height, not a Helm measurement.
        """
        return 10 - ((x + y) ** 2 - 1) ** 2 - (x - y) ** 2

    rows = [
        {"x": x / 3, "y": y / 3, "response": response(x / 3, y / 3), "repeat": repeat, "status": "passed"}
        for x, y, repeat in itertools.product(range(-3, 4), range(-3, 4), range(2))
    ]
    split = partition(rows, 2, 2026)
    quadratic, quartic = fit(split["train"]), fit(split["train"], degree=4)
    assert len(quartic.coefficients) == 15
    assert quartic.predict(0.5, 0.5) == pytest.approx(10)
    assert quartic.predict(-0.5, -0.5) == pytest.approx(10)
    assert quartic.predict(0, 0) == pytest.approx(9)
    assert max(abs(quartic.predict(x, y) - z) for x, y, z in split["joint"]) < 1e-10
    assert max(abs(quadratic.predict(x, y) - z) for x, y, z in split["joint"]) > 0.1
    with pytest.raises(ValueError, match="identify"):
        fit([(float(x), float(y), 1.0) for x, y in itertools.product(range(3), range(8))], degree=4)


def test_comparison_preserves_source_and_scores_holdout(tmp_path: Path) -> None:
    """
    Publish separate models on a full-rank grid without overwriting prior artifacts.

    Args:
        tmp_path (Path): Isolated input ledger and comparison directory.

    Returns:
        None: Both models are scored and the original source remains byte-identical.
    """
    source = tmp_path / "results.json"
    rows = [
        {
            "axis": "clustering",
            "axis_value": x,
            "error_percent": y,
            "repeat": repeat,
            "strategy": "filter",
            "status": "passed",
            "total_seconds": 10 + (x * y) ** 2,
            "errors_missed": x * y,
        }
        for x, y, repeat in itertools.product(range(5), range(5), range(2))
    ]
    source.write_text(json.dumps({"metadata": {"repeats": 2}, "rows": rows}))
    before = source.read_bytes()
    assert compare(["--input", str(source)]) == 0
    assert source.read_bytes() == before
    result = json.loads((tmp_path / "polynomial-comparison/results.json").read_text())
    for record in result["fits"]:
        assert record["models"]["quartic"]["scores"]["joint"]["rmse"] < 1e-10
        assert record["models"]["quadratic"]["status"] == "fitted"
    with pytest.raises(SystemExit):
        compare(["--input", str(source), "--output", str(tmp_path)])


def test_plot_and_timeout_exclusion(tmp_path: Path) -> None:
    """
    Publish supplied observations and refuse a fit after censoring a cell.

    Args:
        tmp_path (Path): Temporary output directory.

    Returns:
        None: Assertions verify generated artifacts and timeout handling.
    """
    rows = [
        {
            "axis": "clustering",
            "axis_value": x,
            "error_percent": y,
            "repeat": repeat,
            "strategy": "filter",
            "status": "passed",
            "total_seconds": 2 + x * y + repeat,
            "errors_missed": x * y,
        }
        for x, y, repeat in itertools.product((0.0, 0.5, 1.0), (0.0, 50.0, 100.0), range(2))
    ]
    document: dict[str, object] = {"metadata": {"methods": ["filter"], "repeats": 2}, "rows": rows}
    plot(tmp_path, document)
    records = json.loads((tmp_path / "quadratic-fits.json").read_text())["fits"]
    assert len(records) == 2
    assert all(record["status"] == "fitted" for record in records)
    assert len(list(tmp_path.glob("*.png"))) == 2
    rows[0]["status"] = "time-limit"
    plot(tmp_path, document)
    records = json.loads((tmp_path / "quadratic-fits.json").read_text())["fits"]
    assert all(record["status"] == "unavailable" for record in records)
    assert not list(tmp_path.glob("*.png"))
