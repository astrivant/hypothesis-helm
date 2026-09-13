"""
Verify refreshed artifacts, scan provenance, and local documentation links.
"""

import hashlib
import json
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

root = Path(sys.argv[1])
benchmarks = Path("benchmarks")
checksums = json.loads((benchmarks / "refresh/sha256.json").read_text())
for name, expected in checksums.items():
    path = benchmarks / name
    assert path.is_file(), path
    assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path

previous = json.loads((root / "previous-artifact-inventory.json").read_text())
retained = json.loads((root / "retained-fixture-sha256.json").read_text())
for name, expected in retained.items():
    assert hashlib.sha256((benchmarks / name).read_bytes()).hexdigest() == expected, name
for name in previous:
    path = Path(name)
    assert str(path.relative_to(benchmarks)) in checksums or str(path.relative_to(benchmarks)) in retained, (
        f"Previous artifact not refreshed: {path}"
    )

sources = json.loads((root / "measured-source-hashes.json").read_text())
for name, expected in sources.items():
    assert hashlib.sha256((root / "frozen-source" / name).read_bytes()).hexdigest() == expected, f"Measured application changed: {name}"

scans = {}
for name, directory in json.loads((root / "provenance.json").read_text())["repository_scans"].items():
    run = Path(directory)
    verification = json.loads((run / "verification.json").read_text())
    assert verification["sampled_counterexamples_with_excluded_controls"] == 0
    assert not verification["systemic_execution_failure"], (name, verification)
    ledger = json.loads((run / "sha256.json").read_text())
    for filename, expected in ledger.items():
        path = run / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    scans[name] = {"retained_files": len(ledger), **verification}

documents = [Path("README.md"), Path("docs/reports/bitnami.md"), Path("docs/reports/prometheus.md")]
documents.extend(benchmarks.rglob("README.md"))
documents.extend(
    Path(directory) / "README.md" for directory in json.loads((root / "provenance.json").read_text())["repository_scans"].values()
)
links = 0
for document in documents:
    fenced = False
    for line in document.read_text().splitlines():
        if line.lstrip().startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        for target in re.findall(r"\]\(([^)\n]+)\)", line):
            target = target.split(' "', 1)[0].strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            destination = document.parent / unquote(parsed.path)
            assert destination.exists(), (document, target)
            links += 1

result = {
    "verified_benchmark_artifacts": len(checksums),
    "previous_artifacts_refreshed": sum(str(Path(name).relative_to(benchmarks)) in checksums for name in previous),
    "historical_fixture_files_verified": len(retained),
    "measured_source_files_unchanged": len(sources),
    "local_documentation_links_checked": links,
    "repository_scans": scans,
}
(root / "publication-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
