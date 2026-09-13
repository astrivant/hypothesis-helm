"""
Publish paired failure-expansion coverage with explicit executed-input denominators.
"""

import csv
import os
import tempfile
from pathlib import Path

from hypothesis_helm.schemas.contracts import mapping, number, sequence

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hypothesis-helm-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {
    "before": "Untrimmed",
    "random": "Random",
    "topology": "Topology",
    "combined": "Both trims",
}


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Export a matrix comparing the same initial selections with expansion disabled and enabled.

    Args:
        output (Path): Destination for plots and the generated explanation.
        document (dict[str, object]): Verified references and paired policy outcomes.

    Returns:
        None: Figures and documentation distinguish failure classes from repeated failing inputs.
    """
    rows = [mapping(row) for row in sequence(document["rows"])]
    references = [mapping(row) for row in sequence(document["references"])]
    if any(row["status"] != "complete" for row in [*rows, *references]):
        raise ValueError("matrix requires completed references and expansion checks")
    structures = [str(row["structure"]) for row in references]
    columns = [(strategy, enabled) for strategy in LABELS for enabled in (False, True)]
    indexed = {(row["structure"], row["strategy"], row["expand_failures"]): row for row in rows}
    figure, axes = plt.subplots(2, 2, figsize=(19, 11))
    panels = (
        ("Distinct erroneous outputs covered", "erroneous_output_coverage", "YlGn", 100),
        ("Erroneous inputs exercised", "erroneous_input_recall", "YlGn", 100),
        ("Inputs checked by policy", "checked_inputs", "YlOrRd", None),
        ("Additional physical executions", "additional_executed", "YlOrRd", None),
    )
    for axis, (title, metric, color, maximum) in zip(axes.flat, panels, strict=True):
        values = []
        for structure in structures:
            values.append(
                [
                    (
                        100 * number(indexed[(structure, strategy, enabled)][metric])
                        if indexed[(structure, strategy, enabled)][metric] is not None
                        else float("nan")
                    )
                    if "coverage" in metric or "recall" in metric
                    else number(indexed[(structure, strategy, enabled)][metric])
                    for strategy, enabled in columns
                ]
            )
        axis.imshow(values, cmap=color, vmin=0, vmax=maximum, aspect="auto")
        axis.set_title(title)
        axis.set_xticks(
            range(len(columns)),
            [LABELS[strategy] + ("\n+ expansion" if enabled else "\nunchanged") for strategy, enabled in columns],
            rotation=25,
            ha="right",
        )
        axis.set_yticks(range(len(structures)), structures)
        axis.grid(False)
        for i, structure in enumerate(structures):
            for j, (strategy, enabled) in enumerate(columns):
                row = indexed[(structure, strategy, enabled)]
                label = f"{values[i][j]:.0f}"
                if metric == "erroneous_output_coverage":
                    label = f"{row['erroneous_outputs_found']}/{row['erroneous_outputs_total']}\n{values[i][j]:.1f}%"
                elif metric == "erroneous_input_recall":
                    label = f"{row['erroneous_inputs_found']}/{row['erroneous_inputs_total']}\n{100 - values[i][j]:.1f}% missed"
                axis.text(
                    j,
                    i,
                    label,
                    ha="center",
                    va="center",
                    fontsize=8,
                    bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"},
                )
    metadata = mapping(document["metadata"])
    figure.suptitle(
        f"Failure expansion · {metadata['error_percent']:g}% seeded errors · matched initial selections",
        fontsize=18,
    )
    figure.text(
        0.5,
        0.015,
        "Initial observations replayed from fresh full Helm populations; added inputs rerendered. "
        "No inferred failures or per-strategy runtime claims.",
        ha="center",
        fontsize=10,
    )
    figure.tight_layout(rect=(0, 0.04, 1, 0.95))
    figure.savefig(output / "failure-expansion.png", dpi=160, facecolor="white")
    figure.savefig(output / "failure-expansion.svg", facecolor="white")
    plt.close(figure)
    svg = output / "failure-expansion.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    with (output / "results.csv").open("w") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[key for key in rows[0] if key not in {"checked_indices", "additional_indices"}],
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Failure expansion",
        "",
        "[Benchmarking](../README.md)",
        "",
        "Topology trimming previously exercised 47 of 51 erroneous inputs in three cases. "
        "The remaining four each produced the same complete manifests as a retained failing input. "
        "The 51 erroneous inputs occupied 43 singleton regions and four two-input regions. "
        "All distinct erroneous outputs were already covered.",
        "",
        "`--expand-failures` is opt-in: after an observed failure, execute omitted members of "
        "that symbolic region within the existing time limit. This measures the extent of a "
        "failure and permits additional checks; it need not discover a new failure class. "
        "Region membership does not label an unexecuted input as a failure.",
        "",
        "```sh",
        "helm hypothesis test ./chart --permutations 2 --trim-topology 2 \\",
        "  --trim-random 2 --expand-failures --time-limit 9m",
        "```",
        "",
        "Expansion continues the initial selection after failures and schedules each omitted "
        "input at most once. The default CLI still stops at its first failure. Unsupported "
        "regions cannot be expanded automatically. An entirely missed failure region cannot "
        "trigger expansion.",
        "",
        "![Paired failure expansion matrix](failure-expansion.png)",
        "",
        "Cells below show **erroneous inputs found before → after expansion (extra executions)**. "
        "The figure also shows the exact percentage missed.",
        "",
        "| Structure | " + " | ".join(LABELS.values()) + " |",
        "|---|" + "---|" * len(LABELS),
    ]
    for structure in structures:
        cells = []
        for strategy in LABELS:
            before, after = (indexed[(structure, strategy, enabled)] for enabled in (False, True))
            counts = []
            for result in (before, after):
                missed = (
                    f"{100 * (1 - number(result['erroneous_input_recall'])):.1f}% missed"
                    if result["erroneous_input_recall"] is not None
                    else "N/A"
                )
                counts.append(f"{result['erroneous_inputs_found']}/{result['erroneous_inputs_total']} ({missed})")
            cells.append(" → ".join(counts) + f" (+{after['additional_executed']})")
        lines.append("| " + structure + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        "**Distinct erroneous outputs covered, before → after:**",
        "",
        "| Structure | " + " | ".join(LABELS.values()) + " |",
        "|---|" + "---|" * len(LABELS),
    ]
    for structure in structures:
        cells = []
        for strategy in LABELS:
            before, after = (indexed[(structure, strategy, enabled)] for enabled in (False, True))
            cells.append(
                f"{before['erroneous_outputs_found']}/{before['erroneous_outputs_total']} → "
                f"{after['erroneous_outputs_found']}/{after['erroneous_outputs_total']}"
            )
        lines.append("| " + structure + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        f"Helm `{metadata['helm']}`; {metadata['error_percent']:g}% erroneous valid inputs "
        f"(rounded down), error seed {metadata['error_seed']}, selection seed {metadata['seed']}, "
        f"trim level {metadata['trim_level']}. "
        "The same placement is reused across matching domains.",
        "",
        "Each category has a fresh complete Helm reference checked against the independent "
        "manifest/error oracle. Policies replay the same initial observations and only consult "
        "a case's observed failure when it is reached. Added inputs are physically rendered "
        "again for each enabled policy. Ground truth is used for scoring, not scheduling.",
        "",
        f"Reference execution plus all added renders share a {metadata['time_limit_seconds']:g}s "
        "ceiling per category. Planning and analysis are excluded. Policy check counts are "
        "not independent full-run timing measurements. The synthetic assertion rejects the "
        "error ConfigMap's incorrect status; ordinary Helm rendering alone accepts that YAML.",
        "",
        "[Raw references and execution records](results.json) · [CSV](results.csv)",
        "",
        "```sh",
        "hypothesis-helm-benchmark expansion \\",
        "  --input-complexity 10 --error-percent 5 --error-seed 1729 \\",
        "  --seed 2026 --trim-level 2 --time-limit 9m --output reports/expansion",
        "```",
        "",
    ]
    (output / "README.md").write_text("\n".join(lines))
