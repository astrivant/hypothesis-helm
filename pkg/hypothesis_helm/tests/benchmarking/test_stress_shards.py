"""
Verify disjoint stress progression shards and complete recipe-preserving publication.
"""

import json
import shutil
from pathlib import Path

import pytest
from hypothesis_helm_benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm_benchmarking.studies.stress import main
from hypothesis_helm_benchmarking.studies.stress_shards import merge

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.schemas.contracts import mapping, sequence


def test_stress_shards_match_serial(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Run the actual progression planner with a cheap measurement double on six shards.

    Args:
        tmp_path (Path): Independent shard and publication outputs.
        monkeypatch (pytest.MonkeyPatch): Replace expensive renders and plots, preserving generated recipes.

    Returns:
        None: Empty shards, ownership, merge ordering and damaged evidence are handled correctly.
    """
    if not shutil.which("helm"):
        pytest.skip("Helm is required for version provenance")

    def reference(chart: Chart, *args: object) -> tuple[list[str], dict[str, object]]:
        """
        Use the valid default input as a cheap reference.

        Args:
            chart (Chart): Real generated fixture.
            *args (object): Unused specification and limit.

        Returns:
            tuple[list[str], dict[str, object]]: One encoded default and unused distribution.
        """
        return [json.dumps(chart.defaults)], {}

    def measurement(chart: Chart, spec: object, strategy: str, **kwargs: object) -> dict[str, object]:
        """
        Return a complete row while allowing the real runner to attach progression data.

        Args:
            chart (Chart): Generated fixture.
            spec (object): Oracle specification.
            strategy (str): Paired strategy name.
            **kwargs (object): Unused execution settings.

        Returns:
            dict[str, object]: Deterministic measurement evidence.
        """
        return dict(strategy=strategy, status="passed", error=None, completed=1, selected=1, remaining=0, chart_sha256="fixture")

    monkeypatch.setattr("hypothesis_helm_benchmarking.studies.stress.reference_space", reference)
    monkeypatch.setattr("hypothesis_helm_benchmarking.studies.stress.measure", measurement)
    monkeypatch.setattr("hypothesis_helm_benchmarking.studies.stress.plot", lambda *args: None)
    paths = []
    with FixtureWorkspace() as workspace:
        assert main(["--steps", "4", "--output", str(tmp_path / "serial")], workspace=workspace) == 0
        for index in range(6):
            output = tmp_path / str(index)
            assert (
                main(["--steps", "4", "--shard-count", "6", "--shard-index", str(index), "--output", str(output)], workspace=workspace) == 0
            )
            paths.append(output / "results.json")
    output = tmp_path / "merged"
    assert main(["--merge-shards", *(str(path) for path in paths), "--output", str(output)]) == 0
    combined = json.loads((output / "results.json").read_text())
    serial = json.loads((tmp_path / "serial/results.json").read_text())
    assert combined["rows"] == serial["rows"]
    assert len(list((output / "cases").glob("*.yaml"))) == 4
    assert combined["metadata"]["source_shards"] == 6
    for name in (path.name for path in (output / "cases").glob("*.yaml")):
        assert (output / "cases" / name).read_bytes() == (tmp_path / "serial/cases" / name).read_bytes()
    with pytest.raises(ValueError, match="every stress shard"):
        merge(paths[:-1], tmp_path / "missing")
    with pytest.raises(ValueError, match="every stress shard"):
        merge([*paths[:-1], paths[0]], tmp_path / "duplicate")
    original = paths[0].read_text()
    damaged = json.loads(original)
    damaged["metadata"]["seed"] += 1
    paths[0].write_text(json.dumps(damaged))
    with pytest.raises(ValueError, match="metadata differs"):
        merge(paths, tmp_path / "incompatible")
    damaged = json.loads(original)
    damaged["rows"].append(damaged["rows"][0])
    paths[0].write_text(json.dumps(damaged))
    with pytest.raises(ValueError, match="Missing or duplicate"):
        merge(paths, tmp_path / "extra-row")
    paths[0].write_text(original)
    recipe = next((paths[0].parent / "cases").glob("*.yaml"))
    recipe.write_text("parameters: {}\n")
    with pytest.raises(ValueError, match="recipe parameters"):
        merge(paths, tmp_path / "bad-recipe")
    assert len(sequence(mapping(serial)["rows"])) > 0
