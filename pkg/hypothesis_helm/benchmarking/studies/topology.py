"""
Render the compiler's directed multigraph without collapsing nodes or inventing edges.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
from collections import Counter, deque
from pathlib import Path
from textwrap import dedent
from typing import NotRequired, TypedDict

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace
from hypothesis_helm.benchmarking.reporting.descriptions import describe


class GraphNode(TypedDict):
    """
    Identify one compiler graph vertex.

    Attributes:
        id (str): Stable vertex identity.
        kind (str): Compiler vertex category.
    """

    id: str
    kind: str


GraphEdge = TypedDict("GraphEdge", {"from": str, "to": str, "kind": str})


class Graph(TypedDict):
    """
    Describe the exported graph fields used by the visualization.

    Attributes:
        nodes (list[GraphNode]): Complete exported vertices.
        edges (list[GraphEdge]): Directed references, including parallel edges.
        baseline (dict[str, object]): Baseline render observation.
        unresolved (NotRequired[list[dict[str, object]]]): Unresolved access evidence.
        complete_influence_map_proven (NotRequired[bool]): Whether completeness was established.
    """

    nodes: list[GraphNode]
    edges: list[GraphEdge]
    baseline: dict[str, object]
    unresolved: NotRequired[list[dict[str, object]]]
    complete_influence_map_proven: NotRequired[bool]


COLORS = {
    "value": "#0072B2",
    "if": "#E69F00",
    "opaque": "#D55E00",
    "template": "#009E73",
    "manifest": "#CC79A7",
    "manifest-field": "#888888",
}


def analyze(graph: Graph) -> tuple[dict[str, object], dict[str, tuple[float, float]]]:
    """
    Compute graph invariants and a deterministic longest-path layered layout.

    Args:
        graph (Graph): Exported compiler nodes and directed edges, including parallel edges.

    Returns:
        tuple[dict[str, object], dict[str, tuple[float, float]]]: Metrics and positions keyed by original node IDs.

    Raises:
        ValueError: Node identities, endpoints, or the expected acyclic dependency relation are invalid.
    """
    nodes = {item["id"]: item for item in graph["nodes"]}
    if len(nodes) != len(graph["nodes"]):
        raise ValueError("Duplicate graph node IDs")
    outgoing: dict[str, set[str]] = {identifier: set() for identifier in nodes}
    incoming: dict[str, set[str]] = {identifier: set() for identifier in nodes}
    in_degree: Counter[str] = Counter()
    out_degree: Counter[str] = Counter()
    for edge in graph["edges"]:
        source, target = edge["from"], edge["to"]
        if source not in nodes or target not in nodes:
            raise ValueError("Graph edge references an absent node")
        outgoing[source].add(target)
        incoming[target].add(source)
        out_degree[source] += 1
        in_degree[target] += 1
    pending = {identifier: len(parents) for identifier, parents in incoming.items()}
    ready = [identifier for identifier, degree in pending.items() if degree == 0]
    heapq.heapify(ready)
    rank = dict.fromkeys(nodes, 0)
    visited = []
    while ready:
        source = heapq.heappop(ready)
        visited.append(source)
        for target in sorted(outgoing[source]):
            rank[target] = max(rank[target], rank[source] + 1)
            pending[target] -= 1
            if pending[target] == 0:
                heapq.heappush(ready, target)
    if len(visited) != len(nodes):
        raise ValueError("Compiler dependency graph contains a cycle; a DAG layout would misrepresent it")
    components = 0
    unseen = set(nodes)
    while unseen:
        components += 1
        start = min(unseen)
        unseen.remove(start)
        queue = deque([start])
        while queue:
            source = queue.popleft()
            for target in incoming[source] | outgoing[source]:
                if target in unseen:
                    unseen.remove(target)
                    queue.append(target)
    positions: dict[str, tuple[float, float]] = {}
    for level in range(max(rank.values(), default=0) + 1):
        layer = [identifier for identifier in nodes if rank[identifier] == level]
        layer.sort(
            key=lambda identifier: (
                sum(positions[parent][1] for parent in sorted(incoming[identifier])) / len(incoming[identifier])
                if incoming[identifier]
                else 0,
                identifier,
            )
        )
        for index, identifier in enumerate(layer):
            positions[identifier] = (float(level), 0.0 if len(layer) == 1 else 1 - 2 * index / (len(layer) - 1))
    metrics: dict[str, object] = {
        "vertices": len(nodes),
        "edges": len(graph["edges"]),
        "unique_directed_pairs": sum(map(len, outgoing.values())),
        "parallel_edges": len(graph["edges"]) - sum(map(len, outgoing.values())),
        "weak_components": components,
        "isolates": sum(not outgoing[key] and not incoming[key] for key in nodes),
        "acyclic": True,
        "longest_dependency_chain_edges": max(rank.values(), default=0),
        "max_in_degree": max(in_degree.values(), default=0),
        "max_out_degree": max(out_degree.values(), default=0),
        "node_kinds": dict(Counter(node["kind"] for node in nodes.values())),
        "edge_kinds": dict(Counter(edge["kind"] for edge in graph["edges"])),
        "baseline": graph["baseline"],
        "unresolved_accesses": len(graph.get("unresolved", [])),
        "complete_influence_map_proven": graph.get("complete_influence_map_proven", False),
        "layout": "longest directed path rank; parent barycenter ordering; no node or edge filtering",
        "interpretation": (
            "Degree counts include parallel edges. DAG depth is dependency-chain length, not template nesting depth. "
            "Geometry is a layout, not output distance. Reachability does not prove causal influence."
        ),
    }
    return metrics, positions


def plot(graph: Graph, output: Path, title: str) -> dict[str, object]:
    """
    Save all vertices and edges as PNG/SVG, with graph invariants and layout coordinates.

    Args:
        graph (Graph): Compiler dependency graph; no sampled or inferred edges are added.
        output (Path): Destination for figures, mathematical metrics, and positions.
        title (str): Chart identity shown above the plot.

    Returns:
        dict[str, object]: Verified graph invariants and baseline observation status.
    """
    import numpy as np
    from matplotlib import pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    metrics, positions = analyze(graph)
    output.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(16, 10))
    sparse = len(graph["nodes"]) <= 80
    segments = [[positions[edge["from"]], positions[edge["to"]]] for edge in graph["edges"]]
    if segments:
        array = np.array(segments)
        axis.add_collection(LineCollection(segments, colors="#526477", linewidths=1 if sparse else 0.35, alpha=0.65 if sparse else 0.18))
        direction = array[:, 1] - array[:, 0]
        heads = array[:, 0] + 0.82 * direction
        axis.quiver(
            heads[:, 0],
            heads[:, 1],
            0.035 * direction[:, 0],
            0.035 * direction[:, 1],
            angles="xy",
            scale_units="xy",
            scale=1,
            width=0.0015 if sparse else 0.0006,
            color="#526477",
            alpha=0.8 if sparse else 0.3,
        )
    palette = {**COLORS, **{node["kind"]: COLORS.get(node["kind"], "#555555") for node in graph["nodes"]}}
    kinds = Counter(node["kind"] for node in graph["nodes"])
    for kind, color in palette.items():
        points = [positions[item["id"]] for item in graph["nodes"] if item["kind"] == kind]
        if points:
            x, y = zip(*points, strict=True)
            axis.scatter(x, y, s=35 if sparse else 4 if kind == "manifest-field" else 14, color=color, alpha=0.8, zorder=3)
    if sparse:
        for identifier, point in positions.items():
            label = identifier if len(identifier) <= 38 else identifier[:35] + "…"
            axis.annotate(label, point, xytext=(6, 5), textcoords="offset points", fontsize=7, clip_on=True)
    axis.set(
        xlim=(-0.3, max((point[0] for point in positions.values()), default=0) + (0.8 if sparse else 0.3)),
        ylim=(-1.08, 1.08),
        xlabel="Longest directed dependency path from a source (edges)",
        yticks=[],
    )
    figure.suptitle(title)
    axis.set_title(
        f"Directed dependency multigraph · {metrics['vertices']:,} vertices · "
        f"{metrics['edges']:,} edges · {metrics['weak_components']:,} weak components"
    )
    axis.legend(
        handles=[
            Line2D([], [], marker="o", linestyle="none", color=color, label=f"{kind} ({kinds.get(kind, 0):,})")
            for kind, color in palette.items()
        ],
        loc="upper center",
        bbox_to_anchor=(0.5, -0.07),
        ncol=3,
    )
    figure.text(
        0.5,
        0.025,
        dedent(
            """
            Every vertex and edge is drawn; parallel edges may overlap. Positions are layout coordinates, not a distance metric.
            Potential references and baseline observations do not establish exact causality. Unknown access remains unresolved.
            """
        ).strip(),
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.09, 1, describe(figure, "topology")))
    figure.savefig(output / "topology.png", dpi=170, facecolor="white")
    figure.savefig(output / "topology.svg", facecolor="white")
    plt.close(figure)
    (output / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n")
    with (output / "positions.csv").open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["node_id", "dependency_rank", "layout_y"])
        writer.writerows((identifier, *point) for identifier, point in positions.items())
    return metrics


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Plot an existing compiler graph without rerunning chart tests.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero when the full graph and its mathematical summary were saved.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--graph", type=Path, required=True, help="JSON from --export-topological-graph")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--title", default="Helm chart topology")
    args = parser.parse_args(argv)
    metrics = plot(json.loads(args.graph.read_text()), args.output, args.title)
    print(json.dumps(metrics))
    return 0
