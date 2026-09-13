"""
Verify that topology figures preserve the mathematical compiler graph.
"""

import csv
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from hypothesis_helm.benchmarking.benchmark_topology import Graph, analyze, plot


def test_multigraph_invariants_and_exports(tmp_path: Path) -> None:
    """
    Preserve parallel references, disconnected values, and every vertex in the layout.

    Args:
        tmp_path (Path): Destination for the graph figures and coordinate ledger.

    Returns:
        None: Counts and directed rank ordering match the complete fixture graph.
    """
    pytest.importorskip("matplotlib")
    graph: Graph = {
        "nodes": [
            {"id": "v", "kind": "value"},
            {"id": "unused", "kind": "value"},
            {"id": "t", "kind": "template"},
            {"id": "m", "kind": "manifest"},
            {"id": "f", "kind": "manifest-field"},
        ],
        "edges": [
            {"from": "v", "to": "t", "kind": "potential-reference"},
            {"from": "v", "to": "t", "kind": "potential-reference"},
            {"from": "t", "to": "m", "kind": "observed-render"},
            {"from": "m", "to": "f", "kind": "contains"},
        ],
        "baseline": {"status": "rendered", "resources": 1},
    }
    metrics, positions = analyze(graph)
    assert metrics["vertices"] == 5
    assert metrics["edges"] == 4
    assert metrics["parallel_edges"] == 1
    assert metrics["weak_components"] == 2
    assert metrics["isolates"] == 1
    assert metrics["max_in_degree"] == metrics["max_out_degree"] == 2
    assert metrics["longest_dependency_chain_edges"] == 3
    assert set(positions) == {node["id"] for node in graph["nodes"]}
    assert all(positions[edge["from"]][0] < positions[edge["to"]][0] for edge in graph["edges"])
    assert plot(graph, tmp_path, "Complete test graph") == metrics
    assert (tmp_path / "topology.png").stat().st_size > 1000
    assert (tmp_path / "topology.svg").stat().st_size > 1000
    with (tmp_path / "positions.csv").open() as stream:
        assert len(list(csv.DictReader(stream))) == len(graph["nodes"])


def test_reject_invented_endpoints_and_cycles() -> None:
    """
    Reject malformed graphs instead of silently dropping edges or claiming a DAG.

    Returns:
        None: Unknown endpoints and cycles produce explicit errors.
    """
    graph: Graph = {
        "nodes": [{"id": "v", "kind": "value"}],
        "edges": [{"from": "v", "to": "absent", "kind": "potential-reference"}],
        "baseline": {"status": "unavailable"},
    }
    with pytest.raises(ValueError, match="absent node"):
        analyze(graph)
    graph["edges"][0]["to"] = "v"
    with pytest.raises(ValueError, match="cycle"):
        analyze(graph)


def test_layout_is_stable_across_process_hash_seeds() -> None:
    """
    Keep parent-average ordering stable when Python randomizes set iteration.

    Returns:
        None: Independent processes assign identical coordinates to the same graph.
    """
    roots = [f"value-{index}" for index in range(7)]
    graph: Graph = {
        "nodes": [{"id": name, "kind": "value"} for name in roots],
        "edges": [],
        "baseline": {"status": "unavailable"},
    }
    for index, parents in enumerate(itertools.combinations(roots, 3)):
        target = f"template-{index}"
        graph["nodes"].append({"id": target, "kind": "template"})
        graph["edges"].extend({"from": parent, "to": target, "kind": "potential-reference"} for parent in parents)
    script = (
        "import json,sys; from hypothesis_helm.benchmarking.benchmark_topology import analyze; "
        "print(json.dumps(analyze(json.load(sys.stdin))[1], sort_keys=True))"
    )
    coordinates = []
    for seed in ("0", "1", "2"):
        result = subprocess.run(
            [sys.executable, "-c", script],
            input=json.dumps(graph),
            text=True,
            capture_output=True,
            check=True,
            env={**os.environ, "PYTHONHASHSEED": seed},
        )
        coordinates.append(json.loads(result.stdout))
    assert coordinates[0] == coordinates[1] == coordinates[2]
