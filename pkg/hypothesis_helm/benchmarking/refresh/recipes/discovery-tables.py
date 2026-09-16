"""
Write discovery tables from the fresh measured ledger.
"""

import csv
import json
import sys
from pathlib import Path

from hypothesis_helm.reporting.contents import with_contents

root = Path(sys.argv[1])
for study in ["discovery", "bug-density"]:
    directory = root / "outputs" / study
    result = json.loads((directory / "results.json").read_text())
    metadata = result["metadata"]
    bugs = metadata.get("bugs", {})
    total = bugs.get("total_faults", len(metadata.get("faults", [])))
    rows = [
        dict(
            strength=run["strength"],
            planned=run["planned"],
            completed=run["completed"],
            faults_found=len(run["found"]),
            total_faults=total,
            missed_faults=total - len(run["found"]),
            elapsed_seconds=run["elapsed_seconds"],
            status=run["status"],
        )
        for run in result["runs"]
    ]
    assert total > 0
    with (directory / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Bug discovery by interaction strength",
        "",
        "[Benchmarking](../../docs/benchmarking/README.md)",
        "",
        f"This fixed fixture contains "
        f"{total} injected faults. The planner varies interaction strength from one to six, with automatic enumeration "
        f"and inferred exhaustive groups disabled to isolate strength. Every selected input is rendered with Helm 4.",
        "",
        "| Strength | Inputs tested / planned | Faults found / total | Missed faults | Seconds | Status |",
        "| ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| "
            f"{row['strength']} | "
            f"{row['completed']} / "
            f"{row['planned']} | "
            f"{row['faults_found']} / {total} | {row['missed_faults']} | {row['elapsed_seconds']:.2f} | {row['status']} |"
        )
    lines.extend(
        [
            "",
            "![Known faults found](bug-discovery.png)",
            "",
            "![Discovery by fault order](bug-order.png)",
            "",
            "[JSON ledger](results.json) · [CSV table](results.csv) · [Chart parameters](chart-parameters.yaml)",
            "",
            "These are distinct injected faults; several input assignments can trigger the same fault. Rates describe "
            "this seeded fixture, not expected bug recall for an arbitrary chart.",
            "",
        ]
    )
    (directory / "README.md").write_text(with_contents("\n".join(lines)))
