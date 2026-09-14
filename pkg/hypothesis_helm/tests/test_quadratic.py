"""
Check quadratic recovery, unsupported designs and paired surface publication.
"""

import itertools
import json
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.analysis.quadratic import fit
from hypothesis_helm.benchmarking.reporting.response_surface import plot


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
