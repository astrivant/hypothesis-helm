"""
Plot structural strategy comparisons using measured runs and exact fixture coverage.
"""

import csv
from pathlib import Path

from hypothesis_helm.benchmarking.analysis.selection import LABELS, explanation
from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Export annotated strategy matrices, a flat CSV and a concise generated README.

    Args:
        output (Path): Artifact destination.
        document (dict[str, object]): Complete matrix measurements and run metadata.

    Returns:
        None: PNG, SVG, CSV and README artifacts reference only observed results.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    document = mapping(current_labels(document))

    import matplotlib.pyplot as plt

    metadata = mapping(document["metadata"])
    strategies = [str(value) for value in sequence(metadata["strategies"])]
    structures = [str(value) for value in sequence(metadata["structures"])]
    rows = [mapping(row) for row in sequence(document["rows"])]
    indexed = {(row["structure"], row["strategy"]): row for row in rows}
    labels = {
        "default": "Default",
        "exact-equivalence": "Exact equivalence",
        "random": "Random trim",
        "topology": "Topology trim",
        "combined": "Both trims",
        **LABELS,
    }
    figure, axes = plt.subplots(2, 2, figsize=(max(15, 3 * len(strategies)), 10))
    panels = (
        ("Outcome coverage (%)", "coverage", "YlGn", 100),
        ("Total time incl. planning (s)", "total_seconds", "YlOrRd", None),
        ("Helm invocations / valid inputs (%)", "render_fraction", "YlOrRd", 100),
        ("Distribution error: total variation (%)", "total_variation", "YlOrRd", 100),
    )
    for axis, (title, metric, color, maximum) in zip(axes.flat, panels, strict=True):
        values: list[list[float]] = []
        for structure in structures:
            line = []
            for strategy in strategies:
                row = indexed[(structure, strategy)]
                if metric in {"coverage", "total_variation"}:
                    value = float(str(mapping(row["distribution"])[metric])) * 100 if row["distribution"] is not None else float("nan")
                elif metric == "render_fraction":
                    value = 100 * int(str(row["render_invocations"])) / int(str(row["valid_domain"]))
                else:
                    value = float(str(row[metric]))
                line.append(value)
            values.append(line)
        axis.imshow(values, cmap=color, vmin=0, vmax=maximum, aspect="auto")
        axis.set_xticks(range(len(strategies)), [labels[item] for item in strategies], rotation=20, ha="right")
        axis.set_yticks(range(len(structures)), structures)
        axis.set_title(title)
        axis.grid(False)
        for i, structure in enumerate(structures):
            for j, strategy in enumerate(strategies):
                capped = indexed[(structure, strategy)]["status"] == "time-limit"
                axis.text(
                    j,
                    i,
                    f"{values[i][j]:.1f}"
                    + ("*" if capped else "")
                    + (" F" if indexed[(structure, strategy)].get("sampling_fallback") else ""),
                    ha="center",
                    va="center",
                    color="black",
                    bbox={"facecolor": "white", "alpha": 0.65, "edgecolor": "none"},
                )
    figure.suptitle(
        f"Structural strategy matrix · {metadata['time_limit_seconds']:g}s execution ceiling",
        fontsize=18,
    )
    figure.text(
        0.04,
        0.02,
        "One seeded run per cell. * = execution deadline; F = adaptive sampling fallback. Coverage uses exact fixture outputs.",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.05, 1, describe(figure, "strategy-matrix")))
    figure.savefig(output / "strategy-matrix.png", dpi=170, facecolor="white")
    figure.savefig(output / "strategy-matrix.svg", facecolor="white")
    plt.close(figure)
    fields = [
        "structure",
        "strategy",
        "trim_random",
        "trim_topology",
        "seed",
        "time_limit_seconds",
        "status",
        "valid_domain",
        "selected",
        "completed",
        "remaining",
        "render_invocations",
        "proved_equivalent",
        "possible_outcomes",
        "observed_outcomes",
        "planning_seconds",
        "analysis_seconds",
        "execution_seconds",
        "total_seconds",
        "initial_selected",
        "expand_failures",
        "additional_scheduled",
        "sample_eligible",
        "sample_retained",
        "sample_minimum",
        "sample_minimum_fields",
        "profile_match",
        "sampling_fallback",
        "calibration_id",
    ]
    with (output / "results.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Structural strategy matrix",
        "",
        "[Benchmarking](../../benchmarks/README.md)",
        "",
        f"Helm `{metadata['helm']}`; "
        f"{metadata['time_limit_seconds']:g}s execution ceiling per run; "
        f"trim level {metadata['trim_level']}; seed {metadata['seed']}.",
        "",
        "All strategy columns use the same complete valid input domain within each case. Planning and analysis are "
        "timed separately and excluded from the execution ceiling. Fresh caches; sequential runs.",
        "",
        "Each trim column uses the stated level; combined enables both at that level. "
        "Exact-equivalence pruning is enabled only in its own column.",
        "",
        "Cells show **outcome coverage / total seconds / Helm invocations**.",
        "",
        "| Structure | " + " | ".join(labels[item] for item in strategies) + " |",
        "|---|" + "---|" * len(strategies),
    ]
    for structure in structures:
        cells = []
        for strategy in strategies:
            row = indexed[(structure, strategy)]
            coverage = 100 * float(str(mapping(row["distribution"])["coverage"])) if row["distribution"] is not None else float("nan")
            cells.append(f"{coverage:.0f}% / {float(str(row['total_seconds'])):.1f}s / {row['render_invocations']}")
        lines.append("| " + structure + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        "![Measured strategy matrix](strategy-matrix.png)",
        "",
        "[Raw measurements](results.json) · [CSV](results.csv)",
        "",
        "Constraints use coupled Boolean inputs; control flow includes an input-dependent loop; "
        "dependencies share a Service/Ingress port; interactions expose a four-way rare branch; "
        "equivalence varies output-irrelevant fields; boundaries cross an integer threshold.",
        "",
        "The current compiler conservatively retains cases it cannot classify. A topology "
        "fallback is a measured limitation, not a failed benchmark. Topology sampling favors "
        "diversity and need not preserve outcome frequencies. These are fixture outcomes, not "
        "bug-discovery guarantees or population-wide confidence intervals.",
        "",
    ]
    lines.extend(explanation(rows))
    (output / "README.md").write_text("\n".join(lines))
    svg = output / "strategy-matrix.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
