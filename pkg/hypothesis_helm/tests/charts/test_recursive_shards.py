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
    library = make_chart(root / "shared-library")
    metadata = library.path / "Chart.yaml"
    metadata.write_text(metadata.read_text() + "type: library\n")
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
    assert all(
        [mapping(chart)["chart"] for chart in sequence(record["charts"])] == ["first", "nested/second", "shared-library"]
        for record in records
    )
    assert aggregate([output], 3, "recursive", tmp_path / "final") == 0
    final = mapping(json.loads((tmp_path / "final/report.json").read_text()))
    assert final["charts_discovered"] == 3 and final["counts"] == {"passed": 2, "skipped-library": 1}
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


def test_shard_cache_retains_verified_completion(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Reuse only this shard's completed inventory, preserving concurrent failures.

    Args:
        tmp_path (Path): Chart and cache roots.
        monkeypatch (pytest.MonkeyPatch): Treat the fixture as unchanged in Git.

    Returns:
        None: Incomplete, different-shard and corrupt-evidence cache entries cannot suppress tests.
    """
    from hypothesis_helm.charts.repositories.cache import ChartCache

    chart = make_chart(tmp_path / "chart")
    monkeypatch.setattr("hypothesis_helm.charts.repositories.cache.chart_changed", lambda *args: False)
    args = Namespace(seed=0, helm="/usr/bin/true", cache_dir=tmp_path / "cache", shard=Shard(1, 3), run_id="first")
    partition = Partition.paths(args.shard, [("alpha",), ("beta",)])
    # Include a path belonging to this shard even if the two-field fixture happened to miss it.
    while not any(partition.owns(unit) for unit in partition.initial):
        partition = Partition.paths(args.shard, [(str(index),) for index in range(len(partition.initial) + 1)])
    partition.visited = [unit for unit in partition.initial if partition.owns(unit)]
    partition.completed = partition.visited.copy()
    result: dict[str, object] = {"status": "passed", "attempts": 1, "work_partition": partition.report()}
    cold = ChartCache.prepare(chart.path, chart.path, args, {})
    cold.publish(result)
    args.run_id = "second"
    warm = ChartCache.prepare(chart.path, chart.path, args, {})
    assert warm.reusable and warm.cached_result["work_partition"] == result["work_partition"]
    args.output_format = "json"
    assert not ChartCache.prepare(chart.path, chart.path, args, {}).reusable
    del args.output_format
    args.shard = Shard(2, 3)
    assert not ChartCache.prepare(chart.path, chart.path, args, {}).reusable
    args.shard = Shard(1, 3)
    assert warm.path is not None
    evidence = warm.path.with_suffix(".evidence.json")
    evidence.write_text("{}")
    assert not ChartCache.prepare(chart.path, chart.path, args, {}).reusable
    warm.publish(result)
    first = ChartCache.prepare(chart.path, chart.path, args, {})
    second = ChartCache.prepare(chart.path, chart.path, args, {})
    first.publish({**result, "status": "interrupted"})
    second.publish(result)
    assert not ChartCache.prepare(chart.path, chart.path, args, {}).reusable


def test_path_timeout_records_unfinished_owned_work(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Retain ownership when a chart deadline prevents completing a property.

    Args:
        tmp_path (Path): Input chart and report root.
        monkeypatch (pytest.MonkeyPatch): Stop a path after one attempt.

    Returns:
        None: Assigned work is visited but never claimed complete after timeout.
    """
    chart = make_chart(tmp_path / "chart")
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.render", lambda *args, **kwargs: [{"kind": "ConfigMap"}])
    monkeypatch.setattr("hypothesis_helm.charts.testing.paths.check_chart", lambda *args, **kwargs: {"status": "time-limit", "attempts": 1})
    shard = next(Shard(index, 3) for index in range(1, 4) if Shard(index, 3).includes(digest(["alpha"])))
    result = check_paths(chart, budget=10, max_examples=2, seed=0, helm="helm", timeout=1, artifacts=tmp_path / "out", shard=shard)
    work = mapping(result["work_partition"])
    assert result["status"] == "time-limit" and work["visited"] and not work["complete"] and not work["completed"]


def test_action_recursive_shard_uses_per_chart_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Exercise the Action's literal Bash command against recursive partitioned testing.

    Args:
        tmp_path (Path): Chart tree and Action artifact root.
        monkeypatch (pytest.MonkeyPatch): Configure the Action's public inputs.

    Returns:
        None: The repository executor receives the Git base and publishes the expected shard report.
    """
    import os
    import shutil
    import sys

    from hypothesis_helm.environment import refresh_env
    from hypothesis_helm.integrations import github_action

    native = shutil.which("helm")
    assert native is not None
    binary = tmp_path / "bin/helm"
    binary.parent.mkdir()
    # Route the plugin call to this checkout without changing the developer's installed Helm plugins.
    binary.write_text(
        dedent(f"""
        #!{sys.executable}
        import os
        import sys
        from hypothesis_helm.cli import main
        if sys.argv[1:2] == ["hypothesis"]:
            raise SystemExit(main(sys.argv[2:]))
        os.execv({native!r}, [{native!r}, *sys.argv[1:]])
        """).lstrip()
    )
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", str(binary.parent) + os.pathsep + os.environ["PATH"])
    make_chart(tmp_path / "charts/first")
    make_chart(tmp_path / "charts/second")
    for name, value in {
        "HH_CHART": str(tmp_path / "charts"),
        "HH_SHARD": "1/3",
        "HH_RUN_ID": "action-recursive",
        "HH_ARTIFACT_DIR": str(tmp_path / "output"),
        "HH_INCREMENTAL": "true",
        "HH_BASE_REF": "HEAD~1",
        "HH_BUILD_DEPENDENCIES": "false",
        "HH_CACHE": "false",
        "HH_MAX_EXAMPLES": "1",
        "HH_JOBS": "2",
        "HH_CHART_TIMEOUT": "30s",
        "HH_VALIDATE_SCHEMAS": "false",
    }.items():
        monkeypatch.setenv(name, value)
    refresh_env()
    assert github_action.main() == 0
    result = mapping(json.loads((tmp_path / "output/shards/1-of-3/report.json").read_text()))
    assert result["report_kind"] == "repository-shard-v1" and result["run_id"] == "action-recursive"
    assert mapping(result["shard"])["index"] == 1
    assert len(sequence(result["charts"])) == 2
    assert (tmp_path / "output/shards/1-of-3/junit.xml").exists()
