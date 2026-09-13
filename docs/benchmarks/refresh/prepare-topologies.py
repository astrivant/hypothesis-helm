"""
Add newly measured synthetic fixtures to the pinned real-chart graph inventory.
"""

import json
import sys
import time
from pathlib import Path

from hypothesis_helm.charts.scan import discover_charts

root = Path(sys.argv[1])
while not (root / "graph-source-ready.txt").exists():
    time.sleep(5)
records = json.loads((root / "topology-inventory.json").read_text())
for item in discover_charts(root / "outputs"):
    records.append(
        {
            "repository": "synthetic",
            "source": str(root / "outputs" / item["chart"]),
            "output": str(root / "outputs/chart-topologies/synthetic" / item["chart"]),
            **item,
        }
    )
for name, source in [("normal-quantile", str(root / "standard-chart")), ("topology-quantile", "examples/topology-benchmark")]:
    records.append(
        {"repository": "synthetic", "source": source, "output": str(root / "outputs/chart-topologies/synthetic" / name), "chart": name}
    )
(root / "topology-inventory.json").write_text(json.dumps(records, indent=2) + "\n")
(root / "topology-jobs.tsv").write_text("\n".join(f"{item['source']}\t{item['output']}" for item in records) + "\n")
print(f"Topology inventory: {len(records)} charts", flush=True)
