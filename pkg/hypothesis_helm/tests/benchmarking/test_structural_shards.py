"""
Verify paired structural sparsity shards and complete recipe-preserving aggregation.
"""

import json
import shutil
from pathlib import Path

import pytest
from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm_benchmarking.studies.structural_shards import merge
from hypothesis_helm_benchmarking.studies.structural_sparsity import main, verify

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_structural_shards_match_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise six real partitions with cheap measurements and real chart recipes.

    Args:
        tmp_path (Path): Separate serial, shard and merged outputs.
        monkeypatch (pytest.MonkeyPatch): Replace costly measurements and plotting.

    Returns:
        None: Every paired group and recipe survives aggregation; incomplete or mixed evidence fails.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required for version provenance")

    def measurement(chart: Chart, spec: object, strategy: str, **kwargs: object) -> dict[str, object]:
        """
        Return a complete fixed-domain observation while the real runner attaches case evidence.

        Args:
            chart (Chart): Real structural fixture.
            spec (object): Independent fixture specification.
            strategy (str): Selected comparison method.
            **kwargs (object): Execution settings including the repeat seed.

        Returns:
            dict[str, object]: Deterministic row satisfying conservation checks.
        """
        return dict(
            strategy=strategy,
            seed=kwargs["seed"],
            status="passed",
            error=None,
            valid_domain=16,
            completed=16,
            selected=16,
            remaining=0,
            erroneous_inputs_evaluated=7,
            total_seconds=1.0,
            chart_sha256="fixture",
        )

    plotted: list[Path] = []
    monkeypatch.setattr("hypothesis_helm_benchmarking.studies.structural_sparsity.measure", measurement)
    monkeypatch.setattr("hypothesis_helm_benchmarking.reporting.structural_sparsity.plot", lambda output, document: plotted.append(output))
    args = ["--breadths", "4", "--depths", "0", "--placements", "near", "far", "--methods", "default", "filter", "--repeats", "2"]
    paths = []
    with FixtureWorkspace() as workspace:
        assert main([*args, "--output", str(tmp_path / "serial")], workspace=workspace) == 0
        for index in range(6):
            output = tmp_path / str(index)
            assert main([*args, "--shard-count", "6", "--shard-index", str(index), "--output", str(output)], workspace=workspace) == 0
            paths.append(output / "results.json")
            verify(json.loads(paths[-1].read_text()))
    assert plotted == [tmp_path / "serial"]
    assert json.loads(paths[-1].read_text())["rows"] == []
    output = tmp_path / "merged"
    assert main(["--merge-shards", *(str(path) for path in reversed(paths)), "--output", str(output)]) == 0
    assert plotted == [tmp_path / "serial", output]
    combined = json.loads((output / "results.json").read_text())
    serial = json.loads((tmp_path / "serial/results.json").read_text())
    # Only loading time differs: partitioning preserves measurements, seeds and shuffled strategy order.
    fields = set(serial["rows"][0]) - {"discovery_seconds", "wall_seconds"}
    assert [{key: row[key] for key in fields} for row in combined["rows"]] == [{key: row[key] for key in fields} for row in serial["rows"]]
    assert combined["metadata"]["source_shards"] == 6
    assert (output / "results.csv").is_file()
    assert len(list((output / "cases").glob("*.yaml"))) == 2
    for recipe in (output / "cases").glob("*.yaml"):
        assert recipe.read_bytes() == (tmp_path / "serial/cases" / recipe.name).read_bytes()
    with pytest.raises(ValueError, match="every structural sparsity shard"):
        merge(paths[:-1], tmp_path / "missing")
    with pytest.raises(ValueError, match="every structural sparsity shard"):
        merge([*paths[:-1], paths[0]], tmp_path / "duplicate")
    original = paths[0].read_text()
    damaged = json.loads(original)
    damaged["metadata"]["seed"] += 1
    paths[0].write_text(json.dumps(damaged))
    with pytest.raises(ValueError, match="metadata differs"):
        merge(paths, tmp_path / "incompatible")
    for damage in ("missing-row", "duplicate-row", "wrong-owner", "failed-row", "changed-chart"):
        damaged = json.loads(original)
        row = damaged["rows"][0]
        if damage == "missing-row":
            damaged["rows"].pop()
        elif damage == "duplicate-row":
            damaged["rows"].append(row)
        elif damage == "wrong-owner":
            row["repeat"] += 1
        elif damage == "failed-row":
            row["status"] = "failed"
        else:
            for row in damaged["rows"]:
                row["chart_sha256"] = "changed"
        paths[0].write_text(json.dumps(damaged))
        with pytest.raises(AssertionError):
            merge(paths, tmp_path / damage)
        assert not (tmp_path / damage / "results.json").exists()
    paths[0].write_text(original)
    recipe = next((paths[0].parent / "cases").glob("*.yaml"))
    recipe.write_text("operations: {}\n")
    with pytest.raises(ValueError, match="recipe parameters"):
        merge(paths, tmp_path / "bad-recipe")
    assert len(sequence(mapping(serial)["rows"])) == 8


@pytest.mark.parametrize("arguments", [["--shard-count", "0"], ["--shard-index", "-1"], ["--shard-count", "6", "--shard-index", "6"]])
def test_invalid_structural_shard_bounds(arguments: list[str]) -> None:
    """
    Reject impossible shard coordinates before generating or measuring a chart.

    Args:
        arguments (list[str]): Invalid count or zero-based index.

    Returns:
        None: Invalid coordinates are CLI usage errors.
    """
    with pytest.raises(SystemExit) as error:
        main(arguments)
    assert error.value.code == 2
