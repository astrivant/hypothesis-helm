"""
Verify one result per discovered chart and publish a combined repository report.

Run from the project root after all GNU Parallel jobs have exited.
"""

import csv
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from textwrap import dedent

from hypothesis_helm.reporting.repository import write_reports


def read_json(path):
    """
    Read a retained JSON artifact, accepting lossless gzip compression.
    """
    if path.exists():
        return json.loads(path.read_text())
    return json.loads(gzip.decompress(path.with_suffix(path.suffix + ".gz").read_bytes()))


run = Path(sys.argv[1])
name = sys.argv[2]
metadata = json.loads((run / "run-metadata.json").read_text())
inventory = json.loads((run / "inventory.json").read_text())
assert subprocess.check_output(["git", "-C", metadata["source"], "rev-parse", "HEAD"], text=True).strip() == metadata["revision"], (
    "Source revision changed during scan"
)
assert not subprocess.check_output(["git", "-C", metadata["source"], "status", "--porcelain"], text=True).strip(), (
    "Source checkout contains unrecorded modifications"
)
for filename, expected_hash in metadata["implementation_sha256"].items():
    assert hashlib.sha256(Path(filename).read_bytes()).hexdigest() == expected_hash, f"Implementation changed during scan: {filename}"
with (run / "joblog.tsv").open() as stream:
    jobs = list(csv.DictReader(stream, delimiter="\t"))
assert len(jobs) == len(inventory), "Missing or extra completed jobs"
by_sequence = {int(job["Seq"]): job for job in jobs}
assert set(by_sequence) == set(range(1, len(inventory) + 1)), "Invalid job ownership"
assert (run / "finished-epoch.txt").is_file(), "Workers have not all exited"
records = []
supplemental = []
settings = None
for sequence, expected in enumerate(inventory, 1):
    job = by_sequence[sequence]
    assert int(job["Signal"]) == 0, f"Worker {sequence} terminated by signal"
    assert int(job["Exitval"]) in (0, 1, 2), f"Unexpected worker {sequence} exit"
    report = read_json(run / "jobs" / f"{sequence}.json")
    assert report["discovery_complete"] and report["scan_status"] == "completed", f"Worker {sequence} incomplete"
    assert report["unstarted_charts"] == 0
    assert Path(report["directory"]).resolve() == (Path(metadata["source"]) / expected["chart"]).resolve()
    if settings is None:
        settings = report["settings"]
    assert settings == report["settings"], "Workers used different settings"
    roots = [record for record in report["charts"] if record["chart"] == "."]
    assert len(roots) == 1, f"Worker {sequence} has no unique root chart"
    root = roots[0]
    for key in ("name", "version", "kind"):
        assert root.get(key) == expected.get(key), f"Wrong {key} in worker {sequence}"
    for record in report["charts"]:
        if record is not root:
            supplemental.append({"job_sequence": sequence, "parent_chart": expected["chart"], **record})
    root["chart"] = expected["chart"]
    root["job_sequence"] = sequence
    root["process_exit_code"] = int(job["Exitval"])
    root["process_signal"] = int(job["Signal"])
    records.append(root)
for record in records + supplemental:
    if record.get("artifacts"):
        diagnostic_dir = Path(record["artifacts"])
        assert diagnostic_dir.resolve().is_relative_to(run.resolve())
        if not diagnostic_dir.exists():
            diagnostic_dir.mkdir(parents=True)
            (diagnostic_dir / "diagnostic.txt").write_text(
                "No render artifacts were produced.\nStatus: " + record["status"] + "\n" + str(record.get("error", "")) + "\n"
            )
assert settings["filter"] is True and settings["chart_timeout_seconds"] == 300
assert settings["max_examples"] == 100 and settings["seed"] == 0
counts = dict(sorted(Counter(record["status"] for record in records).items()))
phases = {}
for record in records:
    for phase in record.get("phases", []):
        phases.setdefault(phase["phase"], Counter())[phase["status"]] += 1
started = int((run / "started-epoch.txt").read_text())
finished = int((run / "finished-epoch.txt").read_text())
attempts = sum(record.get("attempts", 0) for record in records)
relative = os.path.relpath(run, "docs/reports")
summary = [
    f"Visited all **{len(records)} discovered charts** with **--filter**, four workers, "
    "and a **five-minute test budget per chart**. No scan-wide deadline was imposed.",
    "",
    f"Recorded **{attempts:,} test attempts** in **{(finished - started) / 60:.1f} minutes**. "
    "Attempts include shrinking and repeated inputs; they are not counts of unique inputs or confirmed bugs.",
    "",
    "**Findings:** " + "; ".join(f"{count} {status}" for status, count in counts.items()) + ".",
    "",
    "Observed failures include chart validation rejections, rendering failures, and possible tooling limitations. "
    "Inferred inputs are not an authoritative chart contract. Findings need triage before being called chart defects; "
    "time-limited coverage remains incomplete.",
    "",
    "Checks: dependency build in isolated copies, Helm lint, Helm template with values-schema checks, and built-in manifest checks. "
    "External kubeconform/kubesec validation was not configured.",
    "",
    f"Source: `{metadata['source']}` at `{metadata['revision']}`; Helm 4.3.0. Per-worker dependency caches are isolated. "
    "Each primary chart has one dedicated job; nested results from parent jobs are retained separately and excluded from totals.",
    "",
    f"[Combined PDF]({name}.pdf) · [Aggregate data]({relative}/scan.json.gz) · [Raw logs and provenance]({relative}/README.md)",
]
phase_summary = []
for phase, phase_counts in phases.items():
    phase_summary.extend([f"**{phase}:** " + "; ".join(f"{count} {status}" for status, count in sorted(phase_counts.items())) + ".", ""])
summary[6:6] = phase_summary
if name == "prometheus":
    summary.extend(
        [
            "",
            "Coverage notes: Alertmanager known-input generation could not expand the recursive schema at config.route.routes[*]; "
            "its deferred robustness phase still ran. Prometheus PostgreSQL Exporter failed baseline lint because datasource password "
            "configuration was not supplied. The nested CRD chart lacks values.yaml. "
            "Kube-Prometheus Stack and Prometheus Operator CRDs reached their test budgets.",
        ]
    )
result = {
    "title": f"{'Bitnami' if name == 'bitnami' else 'Prometheus Community'} Helm chart scan",
    "directory": metadata["source"],
    "started_epoch": started,
    "elapsed_seconds": finished - started,
    "scan_status": "completed",
    "discovery_complete": True,
    "unstarted_charts": 0,
    "charts_discovered": len(records),
    "counts": counts,
    "charts": records,
    "settings": {**settings, "helm": "Helm 4.3.0", "workers": 4, "external_conformity": False},
    "summary": summary,
}
base = str(Path("docs/reports").resolve()) + "/"


def portable(value):
    """
    Make artifact paths relative to the published report directory.
    """
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, str) and value.startswith(base):
        return value.removeprefix(base)
    return value


result = portable(result)
previous_path = Path("docs/reports") / f"{name}.md"
if previous_path.exists():
    previous_epoch = "previous"
    previous_data = Path("docs/reports") / f"{name}-runs"
    candidates = sorted(path for path in previous_data.glob("*/scan.json*") if path.parent != run)
    if candidates:
        previous_report = read_json(candidates[-1].with_suffix("") if candidates[-1].suffix == ".gz" else candidates[-1])
        previous_epoch = str(previous_report["started_epoch"])
        previous_charts = {item["chart"]: item for item in previous_report["charts"]}
        comparison = []
        for item in records:
            before = previous_charts.get(item["chart"])
            if before and before.get("version") == item.get("version"):
                comparison.append(
                    {
                        "chart": item["chart"],
                        "version": item.get("version"),
                        "previous_status": before["status"],
                        "status": item["status"],
                        "previous_attempts": before.get("attempts", 0),
                        "attempts": item.get("attempts", 0),
                    }
                )
        (run / "comparison.json").write_text(
            json.dumps(
                {
                    "previous_started_epoch": previous_report["started_epoch"],
                    "note": "Observed samples only; differences do not establish regressions or complete coverage.",
                    "matched_charts": comparison,
                },
                indent=2,
            )
            + "\n"
        )
    archive = Path("docs/reports") / f"{name}-{previous_epoch}"
    if not archive.with_suffix(".md").exists():
        archive.with_suffix(".md").write_text(previous_path.read_text().replace(f"]({name}.pdf)", f"]({archive.name}.pdf)"))
        shutil.copyfile(previous_path.with_suffix(".pdf"), archive.with_suffix(".pdf"))
markdown, _ = write_reports(result, Path("docs/reports") / name)
markdown.write_text("\n".join(line.rstrip() for line in markdown.read_text().splitlines()) + "\n")
(run / "scan.json").write_text(json.dumps(result, indent=2) + "\n")
(run / "supplemental-recursive-results.json").write_text(json.dumps(portable(supplemental), indent=2) + "\n")
verification = {
    "expected_charts": len(inventory),
    "completed_jobs": len(jobs),
    "verified_primary_charts": len(records),
    "supplemental_chart_results": len(supplemental),
    "worker_settings_match": True,
    "source_identity_matches": True,
    "source_revision_unchanged": True,
    "implementation_unchanged": True,
    "no_process_signals": True,
    "all_workers_finished": True,
    "counts": counts,
    "attempts": attempts,
    "phase_counts": phases,
    "systemic_execution_failure": sum(counts.get(status, 0) for status in ("error", "dependency-build-failed", "timeout"))
    > len(records) / 5,
}
(run / "verification.json").write_text(json.dumps(verification, indent=2) + "\n")
(run / "README.md").write_text(
    dedent(f"""
# Retained {name} chart tests

This run supplies the [combined report](../../{name}.md) and [PDF](../../{name}.pdf).
It uses the pinned source checkout recorded in `run-metadata.json`.

- `scan.json.gz`: combined primary results with artifact links relative to `docs/reports/`.
- `inventory.json`: chart discovery records in job order.
- `charts.txt`: NUL-delimited paths consumed by GNU Parallel.
- `run.sh`: exact scan invocation; run from the project root with this directory as its argument.
- `finalize.py`: aggregation recipe; run with this directory and `{name}` as arguments after all workers finish.
- `joblog.tsv`: timings, commands, exit codes, and process signals.
- `jobs/`: original per-worker JSON and stderr; JSON larger than 1 MB is losslessly gzip-compressed.
- `runs/`: per-chart diagnostics, phase statistics, and reproducing values.
- `supplemental-recursive-results.json`: nested results excluded from the primary totals.
- `verification.json`: inventory, ownership, settings, and completion checks.
- `run-metadata.json`: source revision and implementation hashes.
- `sha256.json`: retained-file checksums, excluding itself and disposable dependency caches.

Workers write separate artifact directories and use separate Helm cache directories.
A single finalizer verifies every primary chart and writes one Markdown/PDF report.
Large JSON files under `runs/` are also losslessly gzip-compressed. Use `gzip -dc FILE.json.gz` to read them.
Cache directories under `helm/cache-*` are disposable and excluded from provenance.
A completed repository traversal does not establish exhaustive input coverage.
""").lstrip()
)
(run / "finalize.py").write_text(Path(__file__).read_text())
for path in sorted(run.rglob("*.json")):
    if any(part.startswith("cache-") for part in path.relative_to(run).parts):
        continue
    if path.name == "scan.json" and path.parent == run or path.stat().st_size >= 1_000_000:
        original = path.read_bytes()
        compressed = gzip.compress(original, mtime=0)
        assert gzip.decompress(compressed) == original
        path.with_suffix(".json.gz").write_bytes(compressed)
        path.unlink()
files = {}
for path in sorted(run.rglob("*")):
    if path.is_file() and path.name != "sha256.json" and not any(part.startswith("cache-") for part in path.relative_to(run).parts):
        files[str(path.relative_to(run))] = hashlib.sha256(path.read_bytes()).hexdigest()
(run / "sha256.json").write_text(json.dumps(files, indent=2) + "\n")
print(json.dumps(verification, indent=2))
