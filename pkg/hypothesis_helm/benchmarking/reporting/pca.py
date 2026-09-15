"""
Plot fixed PCA coordinates, retained output mass and error recall across structural cases.
"""

import csv
import os
import tempfile
from collections import Counter
from pathlib import Path

import numpy as np
from matplotlib.lines import Line2D

from hypothesis_helm.benchmarking.analysis.selection import LABELS as PRESET_LABELS
from hypothesis_helm.benchmarking.analysis.selection import decision, explanation
from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.schemas.contracts import mapping, number, sequence

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hypothesis-helm-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

LABELS = {
    "before": "Before trimming",
    "random": "Random trim",
    "topology": "Topology trim",
    "combined": "Both trims",
    **PRESET_LABELS,
}


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Export a six-category overview, individual plots and exact loss statistics.

    Args:
        output (Path): Destination for PNG, SVG, CSV and concise documentation.
        document (dict[str, object]): Complete observations and shared per-category PCA bases.

    Returns:
        None: Every panel uses the original coordinates and fixed per-category axes.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    document = mapping(current_labels(document))

    rows = [mapping(row) for row in sequence(document["rows"])]
    if not rows or any(row["status"] != "complete" for row in rows):
        raise ValueError("PCA comparison requires complete reference populations")
    metadata = mapping(document["metadata"])
    labels = {key: label for key, label in LABELS.items() if key in mapping(rows[0]["strategies"])}
    width = 4.5 * len(labels)
    figure, axes = plt.subplots(len(rows), len(labels), figsize=(width, 3.8 * len(rows)), squeeze=False)
    csv_rows: list[dict[str, object]] = []
    for row_index, row in enumerate(rows):
        coordinates = np.asarray(row["coordinates"], dtype=float)
        outcome_ids = [int(number(value)) for value in sequence(row["outcome_indices"])]
        faults = {int(number(value)) for value in sequence(row["faulty_indices"])}
        full_counts = Counter(outcome_ids)
        locations = {identity: coordinates[index] for index, identity in enumerate(outcome_ids)}
        faulty_outcomes = {outcome_ids[index] for index in faults}
        variance = sequence(mapping(row["pca"])["explained_variance_ratio"])
        low, high = coordinates.min(axis=0), coordinates.max(axis=0)
        pad = np.maximum((high - low) * 0.12, 0.5)
        individual, panels = plt.subplots(1, len(labels), figsize=(width, 4.8))
        for column, (strategy, label) in enumerate(labels.items()):
            indices = [int(number(value)) for value in sequence(mapping(row["selected_indices"])[strategy])]
            counts = Counter(outcome_ids[index] for index in indices)
            stats = mapping(mapping(row["strategies"])[strategy])
            csv_rows.append(
                {
                    "structure": row["structure"],
                    "strategy": strategy,
                    "valid_inputs": row["valid_inputs"],
                    "faulty_inputs": len(faults),
                    **stats,
                    **decision(mapping(mapping(row.get("topology", {})).get(strategy, {}))),
                }
            )
            for axis in (axes[row_index, column], panels[column]):
                background = np.array(list(locations.values()))
                axis.scatter(background[:, 0], background[:, 1], s=18, c="#cbd5e1", alpha=0.6)
                for erroneous, color, marker in ((False, "#2563eb", "o"), (True, "#dc2626", "X")):
                    kept = [identity for identity in counts if (identity in faulty_outcomes) == erroneous]
                    if kept:
                        points = np.array([locations[identity] for identity in kept])
                        axis.scatter(
                            points[:, 0],
                            points[:, 1],
                            s=[24 + 400 * counts[identity] / max(full_counts.values()) for identity in kept],
                            color=color,
                            marker=marker,
                            edgecolors="white",
                            linewidths=0.6,
                            alpha=0.8,
                        )
                missing = sorted(faulty_outcomes - counts.keys())
                if missing:
                    points = np.array([locations[identity] for identity in missing])
                    axis.scatter(
                        points[:, 0],
                        points[:, 1],
                        s=90,
                        facecolors="none",
                        edgecolors="#d97706",
                        linewidths=1.8,
                    )
                axis.set_xlim(low[0] - pad[0], high[0] + pad[0])
                axis.set_ylim(low[1] - pad[1], high[1] + pad[1])
                axis.set_xlabel(f"PC1 ({100 * number(variance[0]):.1f}% variance)")
                axis.set_ylabel(f"PC2 ({100 * number(variance[1]):.1f}% variance)")
                axis.set_title(
                    f"{label} · {stats['retained']}/{row['valid_inputs']} inputs\n"
                    f"Errors {stats['errors_detected']}/{len(faults)} · outputs "
                    f"{100 * number(stats['output_coverage']):.0f}%",
                    fontsize=10,
                )
                axis.grid(alpha=0.15)
            if column == 0:
                axes[row_index, 0].text(
                    -0.28,
                    0.5,
                    str(row["structure"]),
                    transform=axes[row_index, 0].transAxes,
                    rotation=90,
                    va="center",
                    ha="center",
                    fontsize=12,
                    weight="bold",
                )
        individual.suptitle(
            f"{row['structure']} · {row['actual_error_percent']:.2f}% erroneous inputs · trim level {metadata['trim_level']}"
        )
        individual.tight_layout(rect=(0, 0.08, 1, describe(individual, "output-pca")))
        individual.text(
            0.5,
            0.02,
            (
                "Blue: retained correct outputs · red X: retained erroneous "
                "outputs · orange ring: missed erroneous outputs\n"
                "Gray: full output space · marker area tracks input "
                "count on the same scale before/after · fixed PCA axes"
            ),
            ha="center",
            fontsize=9,
        )
        individual.savefig(output / f"{row['structure']}.png", dpi=160, facecolor="white")
        plt.close(individual)
    figure.suptitle(
        (f"Output space before and after trimming · {metadata['error_percent']:g}% seeded errors · trim level {metadata['trim_level']}"),
        fontsize=17,
    )
    figure.legend(
        handles=[
            Line2D([], [], color="#2563eb", marker="o", linestyle="", label="Retained correct output"),
            Line2D([], [], color="#dc2626", marker="X", linestyle="", label="Retained erroneous output"),
            Line2D(
                [],
                [],
                color="#d97706",
                marker="o",
                markerfacecolor="none",
                linestyle="",
                label="Missed erroneous output",
            ),
            Line2D([], [], color="#cbd5e1", marker="o", linestyle="", label="Full output space"),
        ],
        loc="lower center",
        ncol=4,
        frameon=False,
    )
    figure.tight_layout(rect=(0.03, 0.025, 1, describe(figure, "output-pca")))
    figure.savefig(output / "output-pca.png", dpi=160, facecolor="white")
    figure.savefig(output / "output-pca.svg", facecolor="white")
    plt.close(figure)
    svg = output / "output-pca.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    with (output / "results.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(csv_rows)
    lines = [
        "# Output-space PCA",
        "",
        "[Benchmarking](../../benchmarks/README.md)",
        "",
        f"Real Helm `{metadata['helm']}` renders. Errors occupy "
        f"{metadata['error_percent']:g}% of valid input assignments "
        f"per category, rounded down; "
        f"error seed {metadata['error_seed']}, selection seed "
        f"{metadata['seed']}, trim level {metadata['trim_level']}.",
        "",
        "Faults emit an incorrect status in an added ConfigMap. "
        "They are present before topology analysis. "
        "This is a synthetic error projection, not five percent "
        "of distinct software defects or arbitrary corruptions "
        "of Kubernetes fields.",
        "",
        "![PCA before and after trimming](output-pca.png)",
        "",
        "**Errors found / all erroneous inputs (percentage missed)**. "
        "Several erroneous inputs can produce the same output. "
        "Percentages are exact miss rates within this seeded fixture.",
        "",
        "| Structure | " + " | ".join(labels.values()) + " |",
        "|---|" + "---:|" * len(labels),
    ]
    for row in rows:
        stats = mapping(row["strategies"])
        errors = len(sequence(row["faulty_indices"]))
        cells = []
        for strategy in labels:
            result = mapping(stats[strategy])
            missed = f"{100 * number(result['errors_missed']) / errors:.1f}% missed" if errors else "N/A"
            cells.append(f"{result['errors_detected']}/{errors} ({missed})")
        lines.append(f"| [{row['structure']}]({row['structure']}.png) | " + " | ".join(cells) + " |")
    lines += [
        "",
        "PCA is fitted once per category to every valid input's "
        "output, including repeated outputs. "
        "Resource presence, numeric leaves and typed categorical "
        "leaves become standardized features; "
        "numeric strings remain categorical. Constant features "
        "are removed. Both axes and marker-size scale stay fixed "
        "after trimming. "
        "Axes are not comparable across categories.",
        "",
        "Marker area tracks retained input mass (with a visibility "
        "floor). Orange rings mark erroneous output classes "
        "entirely missed. "
        "PCA can overlap distinct manifests and discards variance: "
        "read the displayed variance percentages and exact output "
        "coverage alongside it. "
        "Error-case recall is distinct from output coverage. "
        "Conservative compiler fallback may retain the whole "
        "domain.",
        "",
        "The complete population is rendered once, with a nine-minute "
        "ceiling per category, and checked against an independent "
        "manifest/error oracle. "
        "Production selectors choose subsets of those observations; "
        "these are not separate execution-time measurements. "
        "Incomplete references are saved with remaining-work "
        "statistics and are not plotted as full populations. "
        "One seeded experiment is not a confidence interval.",
        "",
        "[Raw observations, inputs and PCA bases](results.json) · [CSV statistics](results.csv)",
        "",
        "```sh",
        "hypothesis-helm-benchmark pca \\",
        "  --input-complexity 10 --error-percent 5 --error-seed 1729 \\",
        "  --seed 2026 --trim-level 2 --time-limit 9m --output reports/pca",
        "```",
        "",
        "Use `--plot-only --output reports/pca` to redraw recorded observations.",
        "",
    ]
    lines.extend(explanation(csv_rows))
    if "filter-adaptive" in labels:
        lines += ["Preset PCA columns include failure expansion, replaying each visited input's actual Helm result.", ""]
    (output / "README.md").write_text("\n".join(lines))
