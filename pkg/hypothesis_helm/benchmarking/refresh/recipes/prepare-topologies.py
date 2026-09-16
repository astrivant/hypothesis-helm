"""
Add newly measured synthetic fixtures to the pinned real-chart graph inventory.
"""

import json
import sys
import time
from pathlib import Path

root = Path(sys.argv[1])
while not (root / "graph-source-ready.txt").exists():
    time.sleep(5)
records = json.loads((root / "topology-inventory.json").read_text())
recipes = [path for path in (root / "outputs").rglob("*.yaml") if path.parent.name == "cases" or path.name.endswith("-parameters.yaml")]
for recipe in sorted(recipes):
    relative = recipe.relative_to(root / "outputs")
    if relative.parts[0] in {"performance", "structure-sparsity"}:
        continue
    if recipe.parent.name == "cases":
        name = str(relative.parent.parent / "charts" / recipe.stem)
    else:
        name = str(relative.parent / recipe.name.removesuffix("-parameters.yaml"))
    records.append(
        {"repository": "synthetic", "source": str(recipe), "output": str(root / "outputs/chart-topologies/synthetic" / name), "chart": name}
    )
for name, preset in [("normal-quantile", "standard"), ("topology-quantile", "topology")]:
    records.append(
        {
            "repository": "synthetic",
            "source": str(root / "parameters" / f"{preset}.yaml"),
            "output": str(root / "outputs/chart-topologies/synthetic" / name),
            "chart": name,
        }
    )
(root / "topology-inventory.json").write_text(json.dumps(records, indent=2) + "\n")
(root / "topology-jobs.tsv").write_text("\n".join(f"{item['source']}\t{item['output']}" for item in records) + "\n")
print(f"Topology inventory: {len(records)} charts", flush=True)
