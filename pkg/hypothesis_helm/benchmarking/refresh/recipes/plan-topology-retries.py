"""
Retry incomplete exports and drawings while retaining the original job log.
"""

import json
import shutil
import sys
from pathlib import Path

root = Path(sys.argv[1])
inventory_path = root / "topology-inventory.json"
inventory = json.loads(inventory_path.read_text())
relocations = []
for repository, container in (("bitnami", "bitnami"), ("prometheus", "charts")):
    wrapper = root / "outputs/chart-topologies" / repository / container
    if not wrapper.is_dir():
        continue
    for child in wrapper.iterdir():
        destination = wrapper.parent / child.name
        assert not destination.exists(), destination
        child.rename(destination)
    wrapper.rmdir()
    for item in inventory:
        original = Path(item["output"])
        if original.is_relative_to(wrapper):
            item["output"] = str(wrapper.parent / original.relative_to(wrapper))
            relocations.append({"from": str(original), "to": item["output"]})
if relocations:
    shutil.copy2(inventory_path, root / "topology-inventory-initial.json")
    inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")
    (root / "topology-output-relocations.json").write_text(json.dumps(relocations, indent=2) + "\n")
    print(f"Preserved existing publication paths for {len(relocations)} charts", flush=True)
charts = []
plots = []
for item in inventory:
    output = Path(item["output"])
    if (output / "metrics.json").exists() and (output / "topology.png").exists() and (output / "topology.svg").exists():
        continue
    if not (Path(item["source"]) / "values.yaml").exists():
        continue
    if (output / "graph.json").exists():
        plots.append(f"{output}/graph.json\t{output}\t{item['repository']}/{item['chart']}")
    else:
        charts.append(f"{item['source']}\t{output}")
(root / "topology-retry-plots.tsv").write_text("\n".join(plots) + ("\n" if plots else ""))
(root / "topology-retry-charts.tsv").write_text("\n".join(charts) + ("\n" if charts else ""))
print(f"Retrying {len(plots)} drawings and {len(charts)} exports", flush=True)
