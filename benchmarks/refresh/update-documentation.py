"""
Update headline measurements and scan links from verified replacement ledgers.
"""

import gzip
import json
import re
import sys
from pathlib import Path

from hypothesis_helm.reporting.links import Publication
from hypothesis_helm.reporting.repository import write_reports

root = Path(sys.argv[1])
provenance = json.loads((root / "provenance.json").read_text())
performance = json.loads((root / "outputs/performance/results.json").read_text())
trajectories = {point["pruning"]: point for point in performance["points"] if point.get("observation") == "progressive-run"}
assert set(trajectories) == {False, True}
pruned, unpruned = trajectories[True], trajectories[False]
path = Path("benchmarks/README.md")
content, matches = re.subn(
    r"In this Helm 4 run, pruning completed \*\*[\d,]+ checks with [\d,]+ renders\*\*, compared\nwith \*\*[\d,]+ checks\*\*",
    f"In this Helm 4 run, pruning completed **{pruned['completed']:,} checks with {pruned['rendered']:,} renders**, compared\n"
    f"with **{unpruned['completed']:,} checks**",
    path.read_text(),
)
assert matches == 1
path.write_text(content)
readme = Path("README.md")
content = readme.read_text()
for name, title in (("bitnami", "Bitnami"), ("prometheus", "Prometheus Community")):
    run = Path(provenance["repository_scans"][name])
    verified = json.loads((run / "verification.json").read_text())
    assert verified["all_workers_finished"] and not verified["systemic_execution_failure"]
    report = json.loads(gzip.decompress((run / "scan.json.gz").read_bytes()))
    # Refresh presentation from retained evidence without changing measured results.
    write_reports(
        report,
        Path("docs/reports") / name,
        publication=Publication(Path.cwd(), "https://github.com/astrivant/hypothesis-helm", "main"),
    )
    attempts = sum(chart.get("attempts", 0) for chart in report["charts"])
    content, matches = re.subn(
        rf"We scanned \*\*[\d,]+ {title} charts\*\*, recording \*\*[\d,]+ test attempts\*\*",
        f"We scanned **{len(report['charts'])} {title} charts**, recording **{attempts:,} test attempts**",
        content,
    )
    assert matches == 1
    content, matches = re.subn(
        rf"docs/reports/{name}-runs/{name}-charts_\d+/README.md",
        f"{run}/README.md",
        content,
    )
    assert matches == 1
content = content.replace(
    "with the same filtering and five-minute budget per chart. Results include input-test\n"
    "failures, a baseline configuration failure, missing values, and incomplete coverage.",
    "with the same filtering and five-minute budget per chart. The report distinguishes\n"
    "observed input failures, blocked checks, and incomplete coverage.",
)
readme.write_text(content)
print("Updated benchmark counts and both repository report links")
