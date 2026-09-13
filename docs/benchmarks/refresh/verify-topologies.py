"""
Verify published drawings against their complete exported graph ledgers.
"""

import csv
import gzip
import io
import json
import sys
from collections import Counter, deque
from pathlib import Path

root = Path(sys.argv[1])
output = root / "outputs/chart-topologies"
rows = json.loads((output / "results.json").read_text())["charts"]
inventory = json.loads((root / "topology-inventory.json").read_text())
assert len(rows) == len(inventory)
assert len({(row["repository"], row["chart"]) for row in rows}) == len(rows)
assert len({row["directory"] for row in rows}) == len(rows)
counts = Counter()
for row in rows:
    directory = output / row["directory"]
    counts[row["status"]] += 1
    if row["status"] not in ("rendered", "static-only"):
        assert row["status"] == "missing-values", row
        continue
    graph = json.loads(gzip.decompress((directory / "graph.json.gz").read_bytes()))
    metrics = json.loads((directory / "metrics.json").read_text())
    coordinates = list(csv.DictReader(io.StringIO(gzip.decompress((directory / "positions.csv.gz").read_bytes()).decode())))
    ids = {node["id"] for node in graph["nodes"]}
    positions = {item["node_id"]: float(item["dependency_rank"]) for item in coordinates}
    assert set(positions) == ids and len(coordinates) == len(ids)
    assert len(ids) == metrics["vertices"] == row["vertices"]
    assert len(graph["edges"]) == metrics["edges"] == row["edges"]
    adjacency = {node: set() for node in ids}
    for edge in graph["edges"]:
        source, target = edge["from"], edge["to"]
        assert positions[source] < positions[target]
        adjacency[source].add(target)
        adjacency[target].add(source)
    components = 0
    unseen = set(ids)
    while unseen:
        components += 1
        queue = deque([unseen.pop()])
        while queue:
            for target in adjacency[queue.popleft()]:
                if target in unseen:
                    unseen.remove(target)
                    queue.append(target)
    assert components == metrics["weak_components"] == row["weak_components"]
    assert len(graph["edges"]) - len(ids) + components == row["undirected_cycle_rank"]
    assert (directory / "topology.png").stat().st_size > 1000
    assert (directory / "topology.svg").stat().st_size > 1000
    assert not any(line.startswith("    ") for line in (directory / "README.md").read_text().splitlines())
result = {
    "charts": len(rows),
    "statuses": dict(counts),
    "verified": [
        "all graph vertices and edges accounted",
        "coordinate identity and directed rank",
        "weak components",
        "underlying multigraph cycle rank",
        "PNG and SVG present",
    ],
}
(output / "verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result))
