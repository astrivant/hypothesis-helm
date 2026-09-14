"""
Prepare fresh output directories, source snapshots, and repository job inventories.
"""

import hashlib
import json
import platform
import shutil
import subprocess
import sys
import tarfile
import time
from pathlib import Path
from textwrap import dedent

from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.charts.scan import discover_charts

root = Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=False)
stamp = int(root.name.rsplit("-", 1)[1])
recipes = Path(__file__).resolve().parent
for recipe in recipes.iterdir():
    if recipe.suffix in {".py", ".sh"}:
        shutil.copy2(recipe, root / recipe.name)
for directory in ("logs", "outputs", "helm/plugins", "matplotlib"):
    (root / directory).mkdir(parents=True, exist_ok=True)
empty_repositories = dedent(
    """
    apiVersion: v1
    repositories: []
    """
).lstrip()
(root / "helm/repositories.yaml").write_text(empty_repositories)
(root / "plotting-order.patch").write_text("")
hashes = {}
sources = [*Path("pkg/hypothesis_helm").rglob("*.py"), Path("pkg/hypothesis_helm/execution/calibration.json")]
for path in sorted(sources):
    if "tests" in path.parts:
        continue
    hashes[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    snapshot = root / "frozen-source" / path
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, snapshot)
(root / "measured-source-hashes.json").write_text(json.dumps(hashes, indent=2) + "\n")
with tarfile.open(root / "measured-source.tar.gz", "w:gz") as archive:
    for name in hashes:
        archive.add(root / "frozen-source" / name, arcname=name)
helm_version = subprocess.check_output(["helm", "version", "--short"], text=True).strip()
revisions = {}
repositories = {}
topologies = []
for name, source in (
    ("bitnami", Path("third_party/bitnami-charts")),
    ("prometheus", Path("third_party/prometheus-community-helm-charts")),
):
    revision = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip():
        raise ValueError(f"Chart checkout has unrecorded changes: {source}")
    revisions[name] = revision
    inventory = discover_charts(source)
    if not inventory:
        raise ValueError(f"No charts discovered in {source}")
    run = Path(f"docs/reports/{name}-runs/{name}-charts_{stamp}")
    run.mkdir(parents=True, exist_ok=False)
    repositories[name] = str(run)
    for directory in ("jobs", "runs", "helm/plugins"):
        (run / directory).mkdir(parents=True, exist_ok=True)
    (run / "helm/repositories.yaml").write_text(empty_repositories)
    (run / "inventory.json").write_text(json.dumps(inventory, indent=2) + "\n")
    (run / "charts.txt").write_bytes(b"".join(str(source / item["chart"]).encode() + b"\0" for item in inventory))
    shutil.copy2(root / "repository-run.sh", run / "run.sh")
    shutil.copy2(root / "repository-chart.sh", run / "chart.sh")
    shutil.copy2(root / "finalize-repository.py", run / "finalize.py")
    metadata = {
        "source": str(source),
        "revision": revision,
        "helm_version": helm_version,
        "workers": 4,
        "implementation_sha256": hashes,
        "implementation_root": str(root / "frozen-source"),
        "chart_timeout_seconds": 300,
        "scan_timeout_seconds": None,
        "max_examples": 100,
        "seed": 0,
        "filter": True,
        "traversal_strategy": "random",
    }
    (run / "run-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    for item in inventory:
        topologies.append(
            {
                **item,
                "repository": name,
                "source": str(source / item["chart"]),
                "output": str(root / "outputs/chart-topologies" / name / item["chart"]),
            }
        )
provenance = {
    "started_epoch": int(time.time()),
    "code_sha256": code_digest(),
    "helm": helm_version,
    "python": platform.python_version(),
    "platform": platform.platform(),
    "time_limit_seconds": 540,
    "source_revisions": revisions,
    "repository_scans": repositories,
    "execution": "Project checks, sequential synthetic studies, topology exports, then repository tests with four workers",
    "traversal_strategy": "random",
    "selection_order": "discover, filter, traverse, execute",
}
(root / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
(root / "topology-inventory.json").write_text(json.dumps(topologies, indent=2) + "\n")
(root / "graph-source-ready.txt").write_text("Source checkouts verified.\n")
(root / "repositories.tsv").write_text("".join(f"{name}\t{run}\n" for name, run in repositories.items()))
ledger = json.loads((recipes / "sha256.json").read_text())
(root / "previous-artifact-inventory.json").write_text(json.dumps([f"benchmarks/{name}" for name in ledger], indent=2) + "\n")
retained_path = recipes / "retained-fixture-sha256.json"
retained = json.loads(retained_path.read_text()) if retained_path.exists() else {}
for name, checksum in ledger.items():
    path = recipes.parent / name
    if any(
        (parent / "Chart.yaml").exists() for parent in path.parents if parent != recipes.parent and parent.is_relative_to(recipes.parent)
    ):
        retained[name] = checksum
(root / "retained-fixture-sha256.json").write_text(json.dumps(retained, indent=2) + "\n")
Path("benchmarks/runs/latest-refresh.txt").write_text(str(root) + "\n")
Path("benchmarks/runs/refresh-state.json").write_text(json.dumps({"root": str(root), "stamp": stamp}, indent=2) + "\n")
print(f"Prepared {len(topologies)} real chart jobs and {len(hashes)} snapshotted application files.")
