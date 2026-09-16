"""
Publish measured benchmark artifacts without replacing unrelated documentation.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from hypothesis_helm.benchmarking.refresh.plan import STUDIES

root = Path(sys.argv[1])
target = Path(".")
statuses = dict(line.split("\t") for line in (root / "status.tsv").read_text().splitlines())
assert set(statuses) == set(STUDIES)
assert all(status == "0" for status in statuses.values()), statuses
assert (root / "topology-finished-epoch.txt").exists()
assert (root / "topology-retry-finished-epoch.txt").exists()
assert (root / "outputs/chart-topologies/verification.json").exists()
assert (root / "outputs/chart-topologies/results.json").exists()
shutil.copy2(root / "logs/performance.log", root / "outputs/performance/run.log")
for directory in sorted((root / "outputs").iterdir()):
    destination = target / "studies" / directory.name
    if directory.name == "flamegraphs" and destination.exists():
        # Process IDs change between captures; stale graphs cannot appear to be current.
        shutil.rmtree(destination)
    shutil.copytree(directory, destination, dirs_exist_ok=True, ignore=shutil.ignore_patterns("verification.json"))
    (destination / "verification.json").unlink(missing_ok=True)
shutil.copytree(root / "parameters", target / "pkg/hypothesis_helm/benchmarking/assets/fixture/parameters", dirs_exist_ok=True)
checksums = {}
for directory in (root / "outputs").iterdir():
    destination = target / "studies" / directory.name
    for source in directory.rglob("*"):
        if source.is_file() and source.name != "verification.json":
            copied = destination / source.relative_to(directory)
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            assert hashlib.sha256(copied.read_bytes()).hexdigest() == expected
            checksums[str(copied.relative_to(target))] = expected
(root / "sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
print(f"Published and verified {len(checksums)} artifacts; verification records remain in {root}")
