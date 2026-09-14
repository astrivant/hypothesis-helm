"""
Verify native filtering-load measurements, phase accounting and censored output.
"""

import json
from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.studies.filtering import METHODS, main, measure
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.schemas.combinations import trim_values


def test_native_filtering_load_matrix(tmp_path: Path) -> None:
    """
    Execute all methods on the same finite chart and redraw the recorded results.

    Args:
        tmp_path (Path): Isolated shared-chart study output.

    Returns:
        None: Native counts, paired seeds, time phases, recipes and plots remain reproducible.
    """
    output = tmp_path / "load"
    assert main(["--inputs", "3", "--depths", "1", "--repeats", "1", "--output", str(output)]) == 0
    original = (output / "results.json").read_bytes()
    document = json.loads(original)
    rows = document["rows"]
    assert {row["strategy"] for row in rows} == set(METHODS)
    assert {row["valid_inputs"] for row in rows} == {8}
    assert {row["seed"] for row in rows} == {2026}
    for row in rows:
        assert row["status"] == "passed"
        assert row["completed"] == row["planned"] and row["remaining"] == 0
        assert row["wall_seconds"] >= row["planning_seconds"] + row["execution_seconds"]
        assert row["planning_seconds"] >= row["complexity_seconds"]
    assert {row["completed"] for row in rows if row["strategy"] in {"baseline", "sample-random"}} == {8}
    assert main(["--output", str(output), "--plot-only"]) == 0
    assert (output / "results.json").read_bytes() == original
    for name in ("filtering-runtime", "filtering-planning", "filtering-completed", "filtering-phases"):
        for extension in ("png", "svg"):
            assert (output / f"{name}.{extension}").stat().st_size > 1000
    assert not list(output.rglob("Chart.yaml"))
    assert len(list((output / "reports").glob("*.json"))) == 4


def test_execution_ceiling_is_not_a_completed_timing(tmp_path: Path) -> None:
    """
    Keep actual remaining work when the execution budget expires.

    Args:
        tmp_path (Path): Finite native chart.

    Returns:
        None: A truncated measurement cannot claim completion or a fully measured runtime.
    """
    root = tmp_path / "chart"
    generate(root, input_complexity=6, output_bins=2)
    row, report = measure(Chart.load(root), "baseline", 2026, 0.001, "helm")
    assert row["status"] == "time-limit"
    assert int(str(row["completed"])) < int(str(row["planned"]))
    assert int(str(row["remaining"])) > 0
    assert report["coverage_complete"] is False


@given(sizes=st.lists(st.integers(1, 50), min_size=1, max_size=12), steps=st.integers(0, 5), seed=st.integers())
def test_supported_region_retention_formula(sizes: list[int], steps: int, seed: int) -> None:
    """
    Check the group-size formula used to explain topology retention before expansion.

    Args:
        sizes (list[int]): Candidate populations of supported nonempty regions.
        steps (int): Quarter-retention depth.
        seed (int): Seed controlling which representatives survive.

    Returns:
        None: Retention equals the sum of upward-rounded group quotas and preserves every group.
    """
    kept = [len(trim_values([{"index": index} for index in range(size)], steps, seed)) for size in sizes]
    denominator = 4**steps
    assert kept == [(size + denominator - 1) // denominator for size in sizes]
    assert all(count >= 1 for count in kept)
