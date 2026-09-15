"""
Plot chart size and separation against runtime, discovery cost and missed errors.
"""

import math
import statistics
from pathlib import Path

from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Publish comparable heatmaps and a precise description of the graph distances.

    Args:
        output (Path): Study directory.
        document (dict[str, object]): Complete or explicitly incomplete measurements.

    Returns:
        None: Writes PNG/SVG heatmaps and a human-readable study report.
    """
    import numpy as np
    from matplotlib import pyplot as plt

    metadata = mapping(document["metadata"])
    rows = [mapping(row) for row in sequence(document["rows"])]
    methods = [str(method) for method in sequence(metadata["methods"])]
    placements = [str(placement) for placement in sequence(metadata["placements"])]
    sizes = sorted({(int(str(row["breadth"])), int(str(row["depth"]))) for row in rows})
    lines = [
        "# Structural sparsity: large charts with separated relevant fields",
        "",
        "Can filtering avoid irrelevant structure without missing interactions between distant values?",
        "",
        "Every case has four variable Boolean fields, 16 valid assignments, two pairwise defects and seven erroneous assignments.",
        "All other leaves are constrained to false. The study isolates structural size, not an exponentially growing variable domain.",
        "Breadth counts root branches; depth counts intermediate maps in each branch. Every branch ends in four Boolean leaves.",
        "The tree has 1 + breadth × (depth + 5) nodes. Relevant-node density is 4 divided by this count.",
        "Within each size, every placement has the same values-tree shape, node count, input domain and fault conditions.",
        "",
        "Near puts all four signals in one branch; split uses two branches; far uses four branches.",
        "Distance counts edges on the shortest path through the values tree, including its root. It is not layout spacing.",
        "Different-branch leaves are 2 × (depth + 2) edges apart; same-branch leaves are two edges apart.",
        "Shared resource projections connect the inputs even when their values paths are far apart.",
        "Disconnected uses the far placement but each defect resource references only its own input pair, yielding two independent",
        "components in the input-to-resource graph. The values tree stays connected. Fault triggers stay the same.",
        "",
        "Discovery measures Chart.load (values/schema loading); compiler analysis is measured separately.",
        "Total time includes loading, planning, analysis and execution. Fixture generation and the oracle are excluded.",
        "Each method starts fresh; OS caches may remain warm. Method order is shuffled reproducibly for every repeat.",
        "Filter presets use production selection and failure expansion. Adaptive floors may keep all cases in this small fixed domain.",
        "Each render is checked against an independent oracle. Error counts refer to erroneous inputs, not unique defects.",
        "Cells show mean ±1 sample standard deviation across repeats, not confidence intervals. Blank cells include incomplete runs.",
        "Execution timeouts are per method and do not bound planning. Timed-out observations remain in the raw ledger.",
        "",
        "[Measurements](results.json) · [CSV](results.csv) · [Replayable chart recipes](cases/)",
        "",
    ]
    figure, panels = plt.subplots(1, 2, figsize=(12, 5))
    for panel, disconnected in zip(panels, (False, True), strict=True):
        for bit in range(4):
            panel.scatter(0.2, 0.2 + bit * 0.2, s=180, color="#2563eb")
            panel.text(0.05, 0.2 + bit * 0.2, f"signal{bit}", ha="right", va="center")
        for resource, pair in enumerate(((0, 3), (1, 2))):
            y = 0.35 + resource * 0.3
            panel.scatter(0.8, y, s=250, marker="s", color="#d97706")
            panel.text(0.85, y, f"defect-{resource}", va="center")
            for bit in pair if disconnected else range(4):
                panel.annotate(
                    "", xy=(0.8, y), xytext=(0.2, 0.2 + bit * 0.2), arrowprops={"arrowstyle": "->", "color": "#64748b", "alpha": 0.6}
                )
        panel.set(xlim=(-0.2, 1.3), ylim=(0, 1), title="Two independent resource groups" if disconnected else "Shared resource references")
        panel.set_axis_off()
    figure.suptitle("Values-to-resource dependency graph")
    finish(
        figure,
        output,
        "structural-sparsity-connectivity",
        "Arrows mean a resource reads that input. Node positions do not measure distance.",
        question="Do distant values remain coupled through shared resources, or form independent groups?",
    )
    lines.extend(["![Input-to-resource graph](structural-sparsity-connectivity.png)", ""])
    for metric, title, filename in (
        ("wall_seconds", "Total time (seconds)", "structural-sparsity-runtime"),
        ("discovery_seconds", "Values/schema loading (seconds)", "structural-sparsity-discovery"),
        ("analysis_seconds", "Compiler and selection analysis (seconds)", "structural-sparsity-analysis"),
        ("errors_missed", "Erroneous inputs missed (out of 7)", "structural-sparsity-errors"),
    ):
        grids = []
        deviations = []
        for method in methods:
            grid = np.full((len(sizes), len(placements)), np.nan)
            sd = np.full_like(grid, np.nan)
            for i, (breadth, depth) in enumerate(sizes):
                for j, placement in enumerate(placements):
                    batch = [
                        row
                        for row in rows
                        if row["strategy"] == method
                        and row["breadth"] == breadth
                        and row["depth"] == depth
                        and row["placement"] == placement
                    ]
                    if len(batch) != int(str(metadata["repeats"])) or any(row["status"] != "passed" for row in batch):
                        continue
                    values = [float(str(row[metric])) for row in batch]
                    grid[i, j] = statistics.mean(values)
                    sd[i, j] = statistics.stdev(values) if len(values) > 1 else float("nan")
            grids.append(grid)
            deviations.append(sd)
        valid = [float(value) for grid in grids for value in grid.flat if math.isfinite(float(value))]
        high = 7 if metric == "errors_missed" else max(valid, default=1) or 1
        figure, axes = plt.subplots(
            math.ceil(len(methods) / 2), 2, squeeze=False, figsize=(14, max(4, len(sizes) * 0.4 + 2) * math.ceil(len(methods) / 2))
        )
        for panel, method, grid, sd in zip(axes.flat, methods, grids, deviations, strict=False):
            image = panel.imshow(grid, origin="lower", aspect="auto", vmin=0, vmax=high)
            panel.set(title=method, xlabel="Placement / resource connectivity", ylabel="Breadth × depth")
            panel.set_xticks(range(len(placements)), placements)
            panel.set_yticks(range(len(sizes)), [f"{breadth} × {depth}" for breadth, depth in sizes])
            for (i, j), value in np.ndenumerate(grid):
                if math.isfinite(float(value)):
                    label = f"{value:.3g}" + (f"\n±{sd[i, j]:.2g}" if math.isfinite(float(sd[i, j])) else "")
                    panel.text(
                        j, i, label, ha="center", va="center", fontsize=8, bbox={"facecolor": "white", "alpha": 0.7, "edgecolor": "none"}
                    )
            figure.colorbar(image, ax=panel, label=title)
        for panel in list(axes.flat)[len(methods) :]:
            panel.set_visible(False)
        figure.suptitle(title)
        finish(
            figure,
            output,
            filename,
            "Mean ±1 SD across repeats; blank cells include incomplete runs.",
            question="Does a larger values tree or greater separation increase cost or hide the same seven erroneous inputs?",
        )
        lines.extend([f"![{title}]({filename}.png)", ""])
    (output / "README.md").write_text("\n".join(lines) + "\n")
