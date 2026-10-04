"""
Publish measured benchmark artifacts without replacing unrelated documentation.
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

from hypothesis_helm_benchmarking.refresh.plan import STUDIES
from hypothesis_helm_benchmarking.reporting.publication import STUDIES as PUBLISHED_STUDIES
from hypothesis_helm_benchmarking.reporting.publication import publish_study, verify_study

__all__ = ()


root = Path(sys.argv[1])
target = Path(".")
statuses = dict(line.split("\t") for line in (root / "status.tsv").read_text().splitlines())
assert set(statuses) == set(STUDIES)
assert all(status == "0" for status in statuses.values()), statuses
assert (root / "topology-finished-epoch.txt").exists()
assert (root / "topology-retry-finished-epoch.txt").exists()
assert (root / "outputs/chart-topologies/verification.json").exists()
assert (root / "outputs/chart-topologies/results.json").exists()
checksums = {}
directories = sorted((root / "outputs").iterdir())
# Check every study before replacing any previously published files.
for directory in directories:
    verify_study(directory)
for directory in directories:
    checksums.update(publish_study(directory, PUBLISHED_STUDIES / directory.name))
shutil.copytree(
    root / "parameters",
    target / "pkg/hypothesis_helm_benchmarking/assets/fixture/parameters",
    dirs_exist_ok=True,
)
measurements = {
    str(path.relative_to(root / "outputs")): hashlib.sha256(path.read_bytes()).hexdigest()
    for path in (root / "outputs").rglob("*")
    if path.is_file()
}
(root / "measurement-sha256.json").write_text(json.dumps(measurements, indent=2) + "\n")
(root / "sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
print(f"Published and verified {len(checksums)} artifacts; verification records remain in {root}")
