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
target = Path("benchmarks")
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
    shutil.copytree(directory, destination, dirs_exist_ok=True)
shutil.copytree(root / "parameters", target / "fixture/parameters", dirs_exist_ok=True)
records = target / "refresh"
records.mkdir(exist_ok=True)
# A new measurement run cannot inherit an earlier manual inspection or interruption record.
for name in ("visual-verification.json", "snapshot-transition.json", "publication-verification.json"):
    (records / name).unlink(missing_ok=True)
record_names = [
    "operations.sh",
    "studies.sh",
    "publish-flamegraphs.py",
    "initialize.py",
    "repository-run.sh",
    "repository-chart.sh",
    "finalize-repository.py",
    "update-documentation.py",
    "verify-publication.py",
    "measured-source.tar.gz",
    "prepare-fixtures.py",
    "plan-topology-retries.py",
    "run-topologies.sh",
    "chart-topology.sh",
    "prepare-topologies.py",
    "catalog-topologies.py",
    "verify-topologies.py",
    "verify-measurements.py",
    "discovery-tables.py",
    "sparsity-tables.py",
    "polish-sparsity.py",
    "measurement-verification.json",
    "publish.py",
    "provenance.json",
    "previous-artifact-inventory.json",
    "retained-fixture-sha256.json",
    "measured-source-hashes.json",
    "plotting-order.patch",
    "status.tsv",
    "started-epoch.txt",
    "finished-epoch.txt",
    "topology-started-epoch.txt",
    "topology-finished-epoch.txt",
    "topology-exit-code.txt",
    "topology-joblog.tsv",
    "topology-inventory.json",
    "topology-jobs.tsv",
]
record_names.extend(path.name for path in root.glob("topology-retry*") if path.is_file())
record_names.append("retry-topologies.sh")
for name in record_names:
    shutil.copy2(root / name, records / name)
shutil.copytree(root / "logs", records / "logs", dirs_exist_ok=True)
checksums = {}
for directory in (root / "outputs").iterdir():
    destination = target / "studies" / directory.name
    for source in directory.rglob("*"):
        if source.is_file():
            copied = destination / source.relative_to(directory)
            expected = hashlib.sha256(source.read_bytes()).hexdigest()
            assert hashlib.sha256(copied.read_bytes()).hexdigest() == expected
            checksums[str(copied.relative_to(target))] = expected
(records / "sha256.json").write_text(json.dumps(checksums, indent=2) + "\n")
(records / "README.md").write_text(
    "\n".join(
        [
            "# Refresh provenance",
            "",
            "Fresh Helm 4 measurements; each independent run has a nine-minute execution ceiling. The studies ran "
            "sequentially, followed by chart graph exports. No earlier timing results were resumed.",
            "",
            f"The sequential synthetic suite took "
            f"{(int((root / 'finished-epoch.txt').read_text()) - int((root / 'started-epoch.txt').read_text())) / 60:.1f} minutes overall.",
            "",
            "[Environment and source fingerprints](provenance.json) · [Study exit codes](status.tsv) · [Artifact checksums](sha256.json)",
            "",
            "Earlier chart snapshots remain covered by [their own checksums](retained-fixture-sha256.json); "
            "they are not measurements from this run.",
            "",
            "The retained shell commands, chart parameter files, seeds, raw results, and logs describe this run. Paths under "
            f"`{root}` identify its staging directory; the published fixtures and "
            "measurements are now under `benchmarks/studies/`.",
            "",
            "All studies and graph exports use the same [recorded application sources](measured-source-hashes.json), "
            "retained in the [source snapshot](measured-source.tar.gz).",
            "",
            "This refresh excludes generated C0/C1 controls except LF and CR. Other Unicode text remains eligible. "
            "The finite Boolean benchmark domains are unchanged; the text policy primarily affects repository path sampling. "
            "Filtering precedes seeded random traversal.",
            "",
            "Timing is from one host and one repetition. Deadline-censored trajectories are reported as incomplete "
            "work, not extrapolated completed checks. Graph baselines are observations, not Kubernetes API schema validation.",
            "",
        ]
    )
)
print(f"Published and verified {len(checksums)} artifacts")
