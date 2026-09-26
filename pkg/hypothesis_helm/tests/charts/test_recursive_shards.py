"""Recursive CI partitions own disjoint work inside the same chart inventory."""

import copy
import json
from argparse import Namespace
from pathlib import Path
from textwrap import dedent

import pytest

from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.repositories.shards import publish_shard
from hypothesis_helm.charts.testing.paths import check_paths
from hypothesis_helm.charts.testing.runner import check_chart
from hypothesis_helm.cli import main
from hypothesis_helm.execution.planning.partition import Partition, digest
from hypothesis_helm.integrations.sharding import Shard
from hypothesis_helm.reporting.reports.shards import aggregate
from hypothesis_helm.schemas.contracts import mapping, sequence


def make_chart(path: Path, *, finite: bool = False) -> Chart:
    """
    Create a chart with two independent values and valid manifests for every candidate.

    Args:
        path (Path): Chart destination.
        finite (bool): Use closed Boolean inputs instead of unbounded strings.

    Returns:
        Chart: Fixture ready for real Helm execution.
    """
    (path / "templates").mkdir(parents=True)
    (path / "Chart.yaml").write_text(
        dedent("""
        apiVersion: v2
        name: partitioned
        version: 1.0.0
        """)
    )
    (path / "values.yaml").write_text("alpha: false\nbeta: false\n" if finite else 'alpha: "ready"\nbeta: "ready"\n')
    (path / "templates/config.yaml").write_text(
        dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          name: partitioned
        data:
          alpha: {{ .Values.alpha | toString | quote }}
          beta: {{ .Values.beta | toString | quote }}
        """)
    )
    (path / "values.schema.json").write_text(
        json.dumps(
            {
                "type": "object",
                "additionalProperties": False,
                "required": ["alpha", "beta"],
                "properties": {name: {"type": "boolean" if finite else "string"} for name in ("alpha", "beta")},
            }
        )
    )
    return Chart.load(path)


@pytest.mark.parametrize("seed", [0, 23])
def test_path_partition_and_empty_shard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, seed: int) -> None:
    """
    Cover two paths exactly once with three shards, independent of seeded traversal.

    Args:
        tmp_path (Path): Fixture and evidence roots.
        monkeypatch (pytest.MonkeyPatch): Replace rendering with bounded successful checks.
        seed (int): Reproducible traversal seed.

    Returns:
        None: Every path has one owner and idle partitions perform no render.
    """
    chart = make_chart(tmp_path / "chart")
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.check_chart", lambda *args, **kwargs: {"status": "passed", "attempts": 2})
    reports = [
        check_paths(
            chart,
            budget=10,
            max_examples=2,
            seed=seed,
            helm="helm",
            timeout=2,
            artifacts=tmp_path / str(index),
            shard=Shard(index, 3),
            filtering=True,
        )
        for index in range(1, 4)
    ]
    work = [mapping(report["work_partition"]) for report in reports]
    selected = [unit for item in work for unit in sequence(item["selected"])]
    assert len(selected) == len(set(selected)) == 2
    assert all(item["complete"] for item in work)
    assert len({str(item["inventory_digest"]) for item in work}) == 1
    assert any(report["status"] == "empty-shard" and report["attempts"] == 0 for report in reports)


@pytest.mark.parametrize("expansion", [False, True])
def test_finite_regions_stay_with_their_owner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, expansion: bool) -> None:
    """
    Preserve exclusive ownership when a failure expands a filtered region.

    Args:
        tmp_path (Path): Finite chart and reports.
        monkeypatch (pytest.MonkeyPatch): Replace Helm with deterministic valid objects.
        expansion (bool): Include topology filtering and failure-region expansion.

    Returns:
        None: Assigned configurations are neither duplicated nor lost across shards.
    """
    chart = make_chart(tmp_path / "chart", finite=True)
    monkeypatch.setattr(
        "hypothesis_helm.charts.testing.runner.render",
        lambda *args, **kwargs: [
            {"apiVersion": "v1", "kind": "ConfigMap", "metadata": {"name": "partitioned"}},
        ],
    )

    def finding(resources: list[dict[str, object]]) -> None:
        """
        Fail a property to exercise expansion rather than just the initial selection.

        Args:
            resources (list[dict[str, object]]): Rendered objects.

        Returns:
            None: The deliberately false property raises for each tested configuration.
        """
        assert not resources

    reports = [
        check_chart(
            chart,
            permutations=2,
            time_limit=30,
            shard=Shard(index, 3),
            trim_topology=1 if expansion else 0,
            expand_failures=expansion,
            properties=(finding,) if expansion else (),
        )
        for index in range(1, 4)
    ]
    work = [mapping(report["work_partition"]) for report in reports]
    visited = [unit for item in work for unit in sequence(item["visited"])]
    assert len(visited) == len(set(visited))
    assert set(visited) == set(mapping(work[0]["units"]))
    assert all(item["complete"] for item in work)


@pytest.fixture
def repository_reports(tmp_path: Path) -> tuple[Path, list[dict[str, object]]]:
    """
    Run three real Helm shards over two recursively discovered charts.

    Args:
        tmp_path (Path): Checkout and artifact roots.

    Returns:
        tuple[Path, list[dict[str, object]]]: Artifact root and portable reports.
    """
    root = tmp_path / "charts"
    make_chart(root / "first")
    make_chart(root / "nested/second", finite=True)
    output = tmp_path / "artifacts"
    for index in range(1, 4):
        assert (
            main(
                [
                    "test",
                    str(root),
                    "--shard",
                    f"{index}/3",
                    "--run-id",
                    "recursive",
                    "--jobs",
                    "2",
                    "--no-build-dependencies",
                    "--artifact-dir",
                    str(output),
                    "--no-cache",
                    "--max-examples",
                    "1",
                    "--chart-timeout",
                    "30s",
                    "--log-file",
                    "/dev/stderr",
                ]
            )
            == 0
        )
    return output, [mapping(json.loads(path.read_text())) for path in sorted(output.glob("shards/*/report.json"))]


def test_recursive_cli_and_aggregation(repository_reports: tuple[Path, list[dict[str, object]]], tmp_path: Path) -> None:
    """
    Produce one final report for all chart sections and retain valid idle shards.

    Args:
        repository_reports (tuple[Path, list[dict[str, object]]]): Real path-worker and finite-plan results.
        tmp_path (Path): Final report destination.

    Returns:
        None: Offline aggregation is complete, portable and idempotent.
    """
    output, records = repository_reports
    assert all([mapping(chart)["chart"] for chart in sequence(record["charts"])] == ["first", "nested/second"] for record in records)
    assert aggregate([output], 3, "recursive", tmp_path / "final") == 0
    final = mapping(json.loads((tmp_path / "final/report.json").read_text()))
    assert final["charts_discovered"] == 2 and final["counts"] == {"passed": 2}
    assert aggregate([output], 3, "recursive", tmp_path / "final") == 0
    assert (tmp_path / "final/report.pdf").is_file()


@pytest.mark.parametrize("damage", ["missing", "run", "settings", "content", "overlap", "incomplete", "inventory"])
def test_aggregation_rejects_invalid_evidence(tmp_path: Path, damage: str) -> None:
    """
    Refuse mismatched or dishonest distributed evidence before writing final reports.

    Args:
        tmp_path (Path): Piped-style input report and publication root.
        damage (str): Independent evidence fault to inject.

    Returns:
        None: Each invalid input fails validation without publishing a final directory.
    """
    records: list[dict[str, object]] = []
    for index in range(1, 4):
        partition = Partition.paths(Shard(index, 3), [("alpha",), ("beta",)])
        partition.visited = [unit for unit in partition.initial if partition.owns(unit)]
        partition.completed = partition.visited.copy()
        record: dict[str, object] = {
            "charts": [
                {
                    "chart": "one",
                    "chart_fingerprint": "same",
                    "work_partition": partition.report(),
                    "status": "passed" if partition.visited else "empty-shard",
                    "attempts": len(partition.visited),
                }
            ],
            "discovery_complete": True,
            "directory": "charts",
            "settings": {},
            "started_epoch": 1,
        }
        publish_shard(record, Namespace(shard=partition.shard, run_id="recursive"), tmp_path, 0)
        records.append(copy.deepcopy(record))
    chart = mapping(sequence(records[0]["charts"])[0])
    work = mapping(chart["work_partition"])
    if damage == "missing":
        records.pop()
    elif damage == "run":
        records[0]["run_id"] = "wrong"
    elif damage == "settings":
        records[0]["settings_digest"] = "wrong"
    elif damage == "content":
        chart["chart_fingerprint"] = "wrong"
    elif damage == "overlap":
        work["visited"] = list(mapping(work["units"]))
    elif damage == "incomplete":
        work["completed"] = []
        work["complete"] = True
        work["selected"] = list(mapping(work["units"]))
    else:
        work["inventory_digest"] = digest("wrong")
    chart["work_partition"] = work
    records[0]["charts"] = [chart]
    path = tmp_path / "inputs.json"
    path.write_text(json.dumps(records))
    with pytest.raises(ValueError):
        aggregate([path], 3, "recursive", tmp_path / "final")
    assert not (tmp_path / "final").exists()
