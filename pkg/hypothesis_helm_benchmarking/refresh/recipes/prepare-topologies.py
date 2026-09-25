"""
Add newly measured synthetic fixtures to the pinned real-chart graph inventory.
"""

import json
import sys
from pathlib import Path

__all__ = ()


root = Path(sys.argv[1])
if not (root / "graph-source-ready.txt").is_file():
    raise ValueError("Topology exports require initialized chart sources; resume initialization first")
# A retry rebuilds synthetic entries from the retained recipes, rather than
# appending the same charts to the inventory again.
records = [item for item in json.loads((root / "topology-inventory.json").read_text()) if item["repository"] != "synthetic"]
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
