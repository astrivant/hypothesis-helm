"""
Replace marked summaries with measurements from the current verified refresh.
"""

import argparse
import gzip
import json
from pathlib import Path
from statistics import mean

from hypothesis_helm.reporting.links import Publication
from hypothesis_helm.reporting.repository import write_reports


def replace_summary(text, name, replacement):
    """
    Replace one generated block while preserving surrounding editorial text.
    """
    start = f"<!-- refresh:{name}:start -->"
    end = f"<!-- refresh:{name}:end -->"
    if text.count(start) != 1 or text.count(end) != 1:
        raise ValueError(f"Expected exactly one pair of {name} summary markers")
    before, rest = text.split(start)
    if end not in rest:
        raise ValueError(f"Reversed {name} summary markers")
    _, after = rest.split(end)
    return f"{before}{start}\n{replacement.strip()}\n{end}{after}"


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("root", type=Path)
parser.add_argument("--benchmarks-only", action="store_true", help="update study text before repository scans finish")
args = parser.parse_args()
root = args.root
performance = json.loads((root / "outputs/performance/results.json").read_text())
trajectories = [point for point in performance["points"] if point.get("observation") == "progressive-run"]
pruned = [point for point in trajectories if point["pruning"]]
unpruned = [point for point in trajectories if not point["pruning"]]
assert pruned and len(pruned) == len(unpruned), "Missing paired performance trajectories"
assert {point.get("repeat", 0) for point in pruned} == {point.get("repeat", 0) for point in unpruned}
assert len({point.get("repeat", 0) for point in pruned}) == len(pruned), "Duplicate performance trajectory"
limits = {point["time_limit_seconds"] for point in trajectories}
assert len(limits) == 1, "Performance trajectories used different budgets"
limit = limits.pop()
helm = performance["metadata"]["helm"]
qualifier = "averaged" if len(pruned) > 1 else "completed"
summary = (
    f"With Helm `{helm}`, pruning {qualifier} **{mean(point['completed'] for point in pruned):,.0f} checks "
    f"with {mean(point['rendered'] for point in pruned):,.0f} renders**, compared\n"
    f"with **{mean(point['completed'] for point in unpruned):,.0f} checks** without pruning. "
    f"Each run had a **{limit / 60:g}-minute budget**; "
    f"{len(pruned)} {'run was' if len(pruned) == 1 else 'runs were'} measured per method."
)
benchmark_path = Path("benchmarks/README.md")
updates = {benchmark_path: replace_summary(benchmark_path.read_text(), "performance", summary)}
reports = []
if not args.benchmarks_only:
    provenance = json.loads((root / "provenance.json").read_text())
    readme = Path("README.md")
    content = readme.read_text()
    for name, title in (("bitnami", "Bitnami"), ("prometheus", "Prometheus Community")):
        run = Path(provenance["repository_scans"][name])
        verified = json.loads((run / "verification.json").read_text())
        assert verified["all_workers_finished"] and not verified["systemic_execution_failure"]
        report = json.loads(gzip.decompress((run / "scan.json.gz").read_bytes()))
        settings = report["settings"]
        attempts = sum(chart.get("attempts", 0) for chart in report["charts"])
        policy = "`--filter-adaptive`" if settings.get("filter_adaptive") else "`--filter`" if settings["filter"] else "no filtering"
        summary = (
            f"We scanned **{len(report['charts']):,} {title} {'chart' if len(report['charts']) == 1 else 'charts'}**, "
            f"recording **{attempts:,} test attempts**\n"
            f"with {policy}, **{settings['workers']} path workers per chart**, "
            f"and a **{settings['chart_timeout_seconds'] / 60:g}-minute budget per chart**.\n"
            "The reports distinguish test failures, blocked checks and incomplete coverage; chart bugs require triage.\n\n"
            f"Read the [scan results](docs/reports/{name}.md), download the\n"
            f"[combined PDF](docs/reports/{name}.pdf), or inspect the [retained logs and data]({run}/README.md)."
        )
        content = replace_summary(content, name, summary)
        reports.append((name, report))
    updates[readme] = content
# Validate every source and marker before replacing any published summary.
for name, report in reports:
    write_reports(
        report,
        Path("docs/reports") / name,
        publication=Publication(Path.cwd(), "https://github.com/astrivant/hypothesis-helm", "main"),
    )
for path, content in updates.items():
    path.write_text(content)
print("Updated benchmark summaries" if args.benchmarks_only else "Updated benchmark summaries and both repository summaries and links")
