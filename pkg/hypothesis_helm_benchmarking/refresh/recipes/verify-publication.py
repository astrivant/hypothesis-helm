"""
Verify refreshed artifacts, scan provenance, and local documentation links.
"""

import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

from hypothesis_helm_benchmarking.reporting.publication import STUDIES, document_links

__all__ = ()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
parser.add_argument("--benchmarks-only", action="store_true", help="verify studies without requiring fresh repository scans")
args = parser.parse_args()
root = args.root
benchmarks = Path("docs/benchmarking")
checksums = json.loads((root / "sha256.json").read_text())
documentation_edits = {}
for name, expected in checksums.items():
    path = Path(name)
    assert path.is_file(), path
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected and path.name == "README.md":
        relative = path.relative_to(STUDIES)
        measured = root / "outputs" / relative
        published_content = document_links(measured.read_text(), Path("studies") / relative, path)
        assert hashlib.sha256(published_content.encode()).hexdigest() == expected, measured
        documentation_edits[name] = {"measured_sha256": expected, "published_sha256": actual}
    else:
        assert actual == expected, path
    if path.suffix == ".svg":
        assert 'id="plot-question"' in path.read_text(), f"Plot has no reader question: {path}"

measurements = json.loads((root / "measurement-sha256.json").read_text())
for name, expected in measurements.items():
    measured = root / "outputs" / name
    assert hashlib.sha256(measured.read_bytes()).hexdigest() == expected, measured

previous = json.loads((root / "previous-artifact-inventory.json").read_text())
retained = json.loads((root / "retained-fixture-sha256.json").read_text())
for name, expected in retained.items():
    assert hashlib.sha256(Path(name).read_bytes()).hexdigest() == expected, name
flamegraphs = STUDIES / "flamegraphs"
profile = json.loads((root / "outputs/flamegraphs/index.json").read_text())
assert profile["worker_processes"] > 0 and profile["incomplete_captures"] == 0
assert (root / "outputs/flamegraphs/captures.tar.gz").is_file()
assert any(figure["name"] == "workers-combined" for figure in profile["figures"])
assert any(figure["name"].startswith("coordinator-") for figure in profile["figures"])
assert all((flamegraphs / figure[extension]).is_file() for figure in profile["figures"] for extension in ("png", "svg"))
superseded = [name for name in previous if name not in checksums and not Path(name).exists()]
retained_earlier = {
    name: hashlib.sha256(Path(name).read_bytes()).hexdigest() for name in previous if name not in checksums and Path(name).is_file()
}

sources = json.loads((root / "measured-source-hashes.json").read_text())
for name, expected in sources.items():
    assert hashlib.sha256((root / "frozen-source" / name).read_bytes()).hexdigest() == expected, f"Measured application changed: {name}"

scans = {}
repositories = {} if args.benchmarks_only else json.loads((root / "provenance.json").read_text())["repository_scans"]
for name, directory in repositories.items():
    run = Path(directory)
    verification = json.loads((run / "verification.json").read_text())
    assert verification["sampled_counterexamples_with_excluded_controls"] == 0
    assert not verification["systemic_execution_failure"], (name, verification)
    ledger = json.loads((run / "sha256.json").read_text())
    for filename, expected in ledger.items():
        path = run / filename
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected, path
    scans[name] = {"retained_files": len(ledger), **verification}

documents = [Path("README.md")]
if not args.benchmarks_only:
    documents.extend([Path("docs/reports/bitnami.md"), Path("docs/reports/prometheus.md")])
documents.append(benchmarks / "README.md")
documents.extend(STUDIES.rglob("*.md"))
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
    "verified_benchmark_artifacts": len(checksums) - len(documentation_edits),
    "verified_cached_measurements": len(measurements),
    "editorially_updated_readmes": documentation_edits,
    "previous_artifacts_refreshed": sum(name in checksums for name in previous),
    "historical_fixture_files_verified": len(retained),
    "measured_source_files_unchanged": len(sources),
    "local_documentation_links_checked": links,
    "repository_scans": scans,
    "superseded_profile_artifacts": superseded,
    "retained_earlier_artifacts_not_refreshed": retained_earlier,
    "fresh_profile_captures": profile["captures"],
}
(root / "publication-verification.json").write_text(json.dumps(result, indent=2) + "\n")
print(json.dumps(result, indent=2))
