"""
Retain exact scalar and categorical sparsity measurements beside their plots.
"""

import csv
import json
import sys
from pathlib import Path

from hypothesis_helm.reporting.contents import with_contents

root = Path(sys.argv[1])
for study in ["sparsity", "structure-sparsity"]:
    directory = root / "outputs" / study
    result = json.loads((directory / "results.json").read_text())
    rows = []
    for run in result["runs"]:
        quality = run.get("quality", {})
        topology = run.get("topology_quality", {})
        rows.append(
            dict(
                stage=run["stage"],
                completed=run["completed"],
                assigned=run["assigned"],
                rendered=run["rendered"],
                pruned=run["pruned"],
                scalar_coverage=quality.get("coverage"),
                scalar_total_variation=quality.get("total_variation"),
                scalar_cdf_error=quality.get("cdf_error"),
                topology_coverage=topology.get("coverage"),
                topology_total_variation=topology.get("total_variation"),
                elapsed_seconds=run["elapsed_seconds"],
                status=run["status"],
            )
        )
    with (directory / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Sparsity and Stochasticity" if study == "sparsity" else "# Sparsity across structural outcomes",
        "",
        "[Benchmarking](../../docs/benchmarking/README.md)",
        "",
        "Each stage uses a smaller nested random subset of the same input prefix, fresh caches, and a nine-minute "
        "ceiling. Case count varies; interaction strength does not. Scalar and categorical outcome distributions are "
        "checked against independent finite references.",
        "",
        "| Stage | Inputs checked / assigned | Helm renders | Scalar coverage | Total variation | Maximum CDF error | Seconds |",
        "| ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        assert row["status"] == "passed", row
        lines.append(
            f"| "
            f"{row['stage']} | "
            f"{row['completed']:,} / "
            f"{row['assigned']:,} | "
            f"{row['rendered']} | "
            f"{100 * row['scalar_coverage']:.2f}% | "
            f"{row['scalar_total_variation']:.5f} | {row['scalar_cdf_error']:.5f} | {row['elapsed_seconds']:.2f} |"
        )
    if any(row["topology_coverage"] is not None for row in rows):
        lines.extend(["", "| Stage | Categorical topology coverage | Categorical total variation |", "| ---: | ---: | ---: |"])
        for row in rows:
            lines.append(f"| {row['stage']} | {100 * row['topology_coverage']:.2f}% | {row['topology_total_variation']:.5f} |")
    lines.extend(
        [
            "",
            "![Outcome coverage and distribution error](sparsity-quality.png)",
            "",
            "![Received outcome distributions](sparsity-distributions.png)",
            "",
            "[Raw JSON](results.json) · [CSV measurements](results.csv)",
            "",
            "One seeded trajectory is shown. Errors need not increase monotonically; categorical outcomes have no CDF "
            "ordering. High distribution coverage does not establish a generally safe trimming level for bug discovery. "
            "Rare faults can be lost.",
            "",
            "See [trimming controls](../../execution/README.md#optional-trimming) "
            "and [refresh commands](../../README.md#reproduce-the-full-project-run).",
            "",
        ]
    )
    if study == "sparsity":
        original = Path("studies/sparsity/README.md").read_text()
        marker = "\n## Fresh measurements\n"
        original = original.split(marker)[0]
        table = lines[6 : lines.index("![Outcome coverage and distribution error](sparsity-quality.png)")]
        (directory / "README.md").write_text(
            with_contents(original + marker + "\n" + "\n".join(table) + "\n[CSV measurements](results.csv)\n")
        )
    else:
        (directory / "README.md").write_text(with_contents("\n".join(lines)))
