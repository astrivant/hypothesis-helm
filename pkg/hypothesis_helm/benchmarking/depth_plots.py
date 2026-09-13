"""
Plot topology depth sensitivity with fixed workloads and explicit coverage denominators.
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


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Publish coverage and work curves without interpreting reference replay as independent runtimes.

    Args:
        output (Path): Figure and document destination.
        document (dict[str, object]): Complete measured depth sweep.

    Returns:
        None: PNG, SVG, CSV and concise benchmark documentation are written.
    """
    rows = [mapping(row) for row in sequence(document["rows"])]
    references = [mapping(row) for row in sequence(document["references"])]
    if any(row["status"] != "complete" for row in [*rows, *references]):
        raise ValueError("complete references and depth sweeps are required for plotting")
    metadata = mapping(document["metadata"])
    panels = (
        ("Initial checks retained", "initial_checks", 1),
        ("Checks after failure expansion", "checked_inputs", 1),
        ("Additional physical executions", "additional_executed", 1),
        ("Erroneous inputs exercised (%)", "erroneous_input_recall", 100),
        ("Distinct erroneous outputs covered (%)", "erroneous_output_coverage", 100),
        ("Topology selection time (seconds)", "selection_seconds", 1),
    )
    figure, axes = plt.subplots(2, 3, figsize=(17, 10))
    for axis, (title, key, multiplier) in zip(axes.flat, panels, strict=True):
        for reference in references:
            selected = sorted(
                (row for row in rows if row["structure"] == reference["structure"]),
                key=lambda row: number(row["trim_topology"]),
            )
            axis.plot(
                [number(row["trim_topology"]) for row in selected],
                [number(row[key]) * multiplier if row[key] is not None else float("nan") for row in selected],
                marker="o",
                label=str(reference["structure"]),
                alpha=0.8,
            )
        axis.set_title(title)
        axis.set_xlabel("Topology trim depth")
        axis.set_xticks(sequence(metadata["depths"]))
        axis.grid(alpha=0.25)
        if multiplier == 100:
            axis.set_ylim(0, 105)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=4)
    figure.suptitle("Topology depth sweep · random trim 0 · failure expansion enabled", fontsize=17)
    figure.tight_layout(rect=(0, 0.08, 1, 0.95))
    for extension in ("png", "svg"):
        figure.savefig(output / f"topology-depth.{extension}", dpi=160, facecolor="white")
    plt.close(figure)
    svg = output / "topology-depth.svg"
    svg.write_text("\n".join(line.rstrip() for line in svg.read_text().splitlines()) + "\n")
    fields = [key for key in rows[0] if key not in {"topology", "checked_indices", "additional_indices"}]
    with (output / "results.csv").open("w") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    lines = [
        "# Topology trim depth",
        "",
        "[Benchmarking](../README.md)",
        "",
        "Only topology trim depth varies. Random trimming stays at zero and failure expansion stays enabled.",
        "",
        f"Fixed settings: {metadata['input_complexity']} inputs, four normal-quantile outputs, "
        f"{metadata['error_percent']:g}% erroneous valid inputs (rounded down), fault "
        f"seed {metadata['error_seed']}, "
        f"selection seed {metadata['selection_seed']}, topology seed {metadata['topology_seed']}. "
        f"Mixed charts contain {metadata['topology_components']} components with "
        f"shared sampled input wiring.",
        "",
        "![Topology depth sensitivity](topology-depth.png)",
        "",
        "Each cell below is **checks; erroneous inputs found / total (missed percentage)** after expansion.",
        "",
        "| Structure | " + " | ".join(f"Depth {depth}" for depth in sequence(metadata["depths"])) + " |",
        "|---|" + "---|" * len(sequence(metadata["depths"])),
    ]
    for reference in references:
        cells = []
        for depth in sequence(metadata["depths"]):
            row = next(row for row in rows if row["structure"] == reference["structure"] and row["trim_topology"] == depth)
            missed = (
                f"{100 * (1 - number(row['erroneous_input_recall'])):.1f}% missed" if row["erroneous_input_recall"] is not None else "N/A"
            )
            cells.append(f"{row['checked_inputs']}; {row['erroneous_inputs_found']}/{row['erroneous_inputs_total']} ({missed})")
        lines.append("| " + str(reference["structure"]) + " | " + " | ".join(cells) + " |")
    lines += [
        "",
        "## Mixed fixtures",
        "",
        "Topology types are categorical, so weights describe their relative "
        "frequency rather than a normal distribution over arbitrarily ordered names. "
        "Requested probabilities and realized counts are both recorded. Types and "
        "wiring use a separate fixed seed. Components can share inputs; numeric "
        "boundary inputs are reserved so Boolean roles retain their declared types.",
        "",
        "| Fixture | Realized component counts |",
        "|---|---|",
    ]
    for reference in references:
        name = str(reference["structure"])
        if name.startswith("mixed-"):
            import json

            spec = mapping(json.loads((output / "charts" / name / "benchmark.json").read_text()))
            counts = mapping(mapping(spec["structure"])["realized_counts"])
            lines.append("| " + name + " | " + ", ".join(f"{key}: {value}" for key, value in counts.items()) + " |")
    lines += [
        "",
        "Uniform mixes sample all six types. Supported mixes weight dependencies, "
        "interactions and equivalence equally. Unsupported constructs can cause the "
        "conservative compiler to retain every input, including inputs belonging to "
        "otherwise supported components.",
        "",
        "## Measurement",
        "",
        f"Helm `{metadata['helm']}`. A fresh complete population is rendered and "
        f"independently checked for each fixture. All depths replay initial "
        f"observations from that same population; extra failure-expansion inputs are "
        f"physically rendered again for each depth. No failures are inferred from "
        f"unexecuted inputs. These are matched coverage measurements, not independent "
        f"end-to-end runtime comparisons.",
        "",
        f"Reference rendering and all added renders share a "
        f"{metadata['time_limit_seconds']:g}s execution ceiling per fixture. Planning "
        f"and plotting are excluded. The time panel measures topology selection only; "
        f"it excludes expansion grouping and rendering. Partial runs retain "
        f"statistics without publishing a complete plot.",
        "",
        "A single fixed fault/topology seed isolates depth sensitivity; it cannot "
        "establish an optimal default across real charts. Repeated seeds are needed "
        "before changing the provisional `--filter` depth of 2.",
        "",
        "[Raw observations](results.json) · [CSV](results.csv)",
        "",
        "```sh",
        "hypothesis-helm-benchmark topology-depth --time-limit 9m --output reports/topology-depth",
        "```",
        "",
    ]
    (output / "README.md").write_text("\n".join(lines))
