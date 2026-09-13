"""
Verify deterministic partitioning and independent parallel runner instances.
"""

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from hypothesis_helm.cli import main
from hypothesis_helm.integrations.sharding import Shard, parse_shard


def test_partition_is_disjoint_complete_and_order_independent() -> None:
    """
    Assign each property once without depending on collection order.

    Returns:
        None: All partitions are disjoint and their union contains the full suite.
    """
    nodes = [f"test_chart_values.py::test_{index}" for index in range(100)]
    seen: set[str] = set()
    for index in range(1, 8):
        shard = Shard(index, 7)
        selected = {node for node in nodes if shard.includes(node)}
        assert selected == {node for node in reversed(nodes) if shard.includes(node)}
        assert not seen.intersection(selected)
        seen.update(selected)
    assert seen == set(nodes)


@pytest.mark.parametrize("value", ["0/4", "5/4", "1/0", "1", "a/4", "1/2/3"])
def test_invalid_shard(value: str) -> None:
    """
    Reject malformed or out-of-range shard coordinates.

    Args:
        value (str): Invalid shard selector.

    Returns:
        None: The selector produces an argument error.
    """
    with pytest.raises(argparse.ArgumentTypeError):
        parse_shard(value)


def test_concurrent_shards_keep_workers_and_reports_isolated(tmp_path: Path) -> None:
    """
    Execute multiple shards concurrently against one saved suite.

    Args:
        tmp_path (Path): Directory shared by independent runner instances.

    Returns:
        None: Every property runs once, reports remain separate, and failures propagate.
    """
    (tmp_path / "test_chart_values.py").write_text(
        """
import pytest
from hypothesis_helm.reporting.output import emit_manifest

@pytest.mark.parametrize("index", range(12))
def test_property(index):
    emit_manifest({"apiVersion": "v1", "kind": "ConfigMap",
                   "metadata": {"name": f"case-{index}"}})
    assert index != 7
"""
    )
    (tmp_path / "values.coalesced.yaml").write_text("flag: false\n")
    cache = tmp_path / "shared-cache"
    reports = tmp_path / "results"
    children = [
        subprocess.Popen(
            [
                str(Path(sys.executable).with_name("hypothesis-helm")),
                "run",
                str(tmp_path),
                "--artifact-dir",
                str(reports),
                "--shard",
                f"{index}/3",
                "--jobs",
                "2",
                "--run-id",
                "cold",
                "--cache-dir",
                str(cache),
                "-o",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=dict(os.environ, PYTHON_CPU_COUNT="2"),
        )
        for index in range(1, 4)
    ]
    names: list[str] = []
    nodeids: set[str] = set()
    statuses = []
    total = 0
    try:
        for index, child in enumerate(children, 1):
            output, diagnostics = child.communicate(timeout=45)
            assert child.returncode in (0, 1), diagnostics
            statuses.append(child.returncode)
            names += [json.loads(line)["metadata"]["name"] for line in output.splitlines()]
            root = reports / "shards" / f"{index}-of-3"
            report = json.loads((root / "report.json").read_text())
            assignment = report["shard"]
            assert assignment["matched"] == 12
            assert assignment["index"] == index
            assert assignment["total"] == 3
            assert not nodeids.intersection(assignment["tests"])
            nodeids.update(assignment["tests"])
            assert report["workers"] == min(2, assignment["selected"])
            assert report["run_id"] == "cold"
            assert Path(report["cache"]).parent.parent == cache
            total += sum(int(suite.get("tests", "0")) for suite in ET.parse(root / "junit.xml").getroot().iter("testsuite"))
        assert sum(statuses) == 1
        assert len(names) == len(set(names)) == len(nodeids) == total == 12
        assert not (tmp_path / "report.json").exists()
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()

    caches = list(cache.glob("*/*.json"))
    assert len(caches) == 3
    outcomes = {node: status for path in caches for node, status in json.loads(path.read_text()).items()}
    assert set(outcomes) == nodeids
    assert list(outcomes.values()).count("failed") == 1
    assert not list(cache.rglob("*.tmp"))
    mergers = [
        subprocess.Popen(
            [
                str(Path(sys.executable).with_name("hypothesis-helm")),
                "aggregate",
                str(reports),
                "--shards",
                "3",
                "--run-id",
                "cold",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for _ in range(2)
    ]
    try:
        for child in mergers:
            _, diagnostics = child.communicate(timeout=30)
            assert child.returncode == 1, diagnostics
    finally:
        for child in mergers:
            if child.poll() is None:
                child.kill()
            child.wait()
    final = reports / "final"
    combined = json.loads((final / "report.json").read_text())
    assert combined["properties"]["selected"] == combined["properties"]["tests"] == 12
    assert combined["properties"]["failures"] == 1
    assert combined["properties"]["reused"] == 0
    assert combined["render_hashes"]["global_unique_bundles"] is None
    assert len(list(ET.parse(final / "junit.xml").iter("testcase"))) == 12
    assert (final / "report.md").exists() and (final / "report.pdf").exists()
    original = (final / "report.json").read_bytes()
    assert main(["aggregate", str(reports), "--shards", "3", "--run-id", "cold"]) == 1
    assert (final / "report.json").read_bytes() == original

    warm = tmp_path / "retry"
    children = [
        subprocess.Popen(
            [
                str(Path(sys.executable).with_name("hypothesis-helm")),
                "run",
                str(tmp_path),
                "--artifact-dir",
                str(warm),
                "--cache-dir",
                str(cache),
                "--run-id",
                "warm",
                "--shard",
                f"{index}/3",
                "--jobs",
                "2",
                "--rerun",
                "failed",
                "-o",
                "json",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for index in range(1, 4)
    ]
    repeated: list[str] = []
    try:
        for child in children:
            output, diagnostics = child.communicate(timeout=45)
            assert child.returncode in (0, 1), diagnostics
            repeated.extend(json.loads(line)["metadata"]["name"] for line in output.splitlines())
    finally:
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()
    assert repeated == ["case-7"]
    assert main(["aggregate", str(warm), "--shards", "3", "--run-id", "warm"]) == 1
    retried = json.loads((warm / "final/report.json").read_text())
    assert retried["properties"]["selected"] == 12
    assert retried["properties"]["reused"] == 11
    assert retried["properties"]["tests"] == retried["properties"]["failures"] == 1


@pytest.mark.parametrize("jobs", ["1", "auto"])
def test_empty_shard_and_empty_match_are_distinct(tmp_path: Path, jobs: str) -> None:
    """
    Allow idle shards without hiding invalid keyword selections.

    Args:
        tmp_path (Path): Directory containing a minimal saved suite.
        jobs (str): Serial or adaptive execution.

    Returns:
        None: An empty partition succeeds while an unmatched keyword remains an error.
    """
    (tmp_path / "test_chart_values.py").write_text("def test_only():\n    pass\n")
    nodeid = "test_chart_values.py::test_only"
    empty = next(index for index in range(1, 4) if not Shard(index, 3).includes(nodeid))
    args = ["run", str(tmp_path), "--shard", f"{empty}/3", "--jobs", jobs]
    assert main(args) == 0
    report = json.loads((tmp_path / "shards" / f"{empty}-of-3" / "report.json").read_text())
    assert report["workers"] == 0
    assert report["shard"]["selected"] == 0
    assert main([*args, "--match", "does_not_exist"]) == 5


def test_shard_collection_is_independent_of_checkout_location(tmp_path: Path) -> None:
    """
    Keep partition ownership stable across independently located generated suites.

    Args:
        tmp_path (Path): Parent directory for two independent generated checkouts.

    Returns:
        None: Collection assigns identical node IDs and respects keyword selection.
    """
    assignments = []
    for name in ("first", "second"):
        output = tmp_path / name
        assert (
            main(
                [
                    "test",
                    "examples/workload",
                    "--collect-only",
                    "--match",
                    "image",
                    "--shard",
                    "1/2",
                    "--artifact-dir",
                    str(output),
                ]
            )
            == 0
        )
        result = output / "shards" / "1-of-2"
        assert (result / "test_chart_values.py").is_file()
        report = json.loads((result / "report.json").read_text())
        assert report["shard"]["matched"] == 3
        assignments.append(report["shard"]["tests"])
    assert assignments[0] == assignments[1]
