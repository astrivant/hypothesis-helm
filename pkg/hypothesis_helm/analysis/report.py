"""
Publish concise sensitivity evidence and optional diagnostic plots.
"""

import json
from pathlib import Path

from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence


def write_report(output: Path, document: dict[str, object], *, plots: bool = False) -> None:
    """
    Save measurements, a human-readable summary and optional matplotlib plots.

    Args:
        output (Path): Fresh report directory.
        document (dict[str, object]): Completed or partial sensitivity evidence.
        plots (bool): Generate a three-panel PNG and SVG.

    Returns:
        None: Report artifacts are written.
    """
    output.mkdir(parents=True, exist_ok=False)
    (output / "results.json").write_text(json.dumps(document, indent=2, allow_nan=False) + "\n")
    rows = [mapping(row) for row in sequence(document["mutations"])]
    pairs = [mapping(row) for row in sequence(document["interactions"])]
    identifiers = {str(row["name"]): index + 1 for index, row in enumerate(rows)}
    lines = [
        "# Mutation sensitivity",
        "",
        f"Status: **{document['status']}**. Helm render attempts: **{document['renders']}**.",
        "",
        "Distance counts added and removed JSON path/value indicators. A changed value counts twice.",
        "Document and array order matter. These measurements do not prove equivalence or authorize pruning.",
        "Distances assume deterministic rendering with fixed chart dependencies, release, namespace and Kubernetes version.",
        "",
    ]
    if plots:
        plot(output, document)
        lines.extend(["![Sensitivity, interaction and sequence measurements](sensitivity.png)", ""])
    lines += [
        f"Measured {len(rows)} single mutations and {len(pairs)} pairs. The plots include every comparable measurement.",
        "Tables show up to 20 of the largest effects. Mutation IDs follow the order in mutations.json.",
        "",
        "| ID | Mutation | Values path | Replacement | Output distance | Status |",
        "| ---: | --- | --- | --- | ---: | --- |",
    ]

    def literal(value: object) -> str:
        """
        Escape untrusted labels and values for Markdown table cells.

        Args:
            value (object): JSON value to display.

        Returns:
            str: HTML-escaped JSON with table separators encoded.
        """
        import html

        return html.escape(json.dumps(value, ensure_ascii=True)).replace("|", "&#124;")

    for row in sorted(rows, key=lambda row: -int(str(row.get("distance", -1))))[:20]:
        lines.append(
            f"| {identifiers[str(row['name'])]} | {literal(row['name'])} | {literal(row['path'])} | {literal(row['value'])} | "
            f"{row.get('distance', 'N/A')} | {row['status']} |"
        )
    lines += [
        "",
        "## Parameter interactions",
        "",
        "A nonzero mixed difference means the selected output features respond non-additively.",
        "Pairs with order-dependent inputs are excluded from this measure. Render failures have no assigned distance.",
        "",
        "| Mutations | Mixed difference | Status |",
        "| --- | ---: | --- |",
    ]
    for row in sorted(pairs, key=lambda row: -int(str(row.get("mixed_difference_l1", -1))))[:20]:
        lines.append(f"| {literal(row['mutations'])} | {row.get('mixed_difference_l1', 'N/A')} | {row['status']} |")
    lines += [
        "",
        "The ordered sequence in results.json records both cumulative path length and displacement from the baseline.",
        "They differ when later mutations reverse earlier changes. The sequence stops at its first invalid or failed step.",
        "",
        "[Full measurements and render errors](results.json)",
    ]
    (output / "README.md").write_text(with_contents("\n".join(lines) + "\n"))


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Plot mutation distances, pair interactions and ordered path accumulation.

    Args:
        output (Path): Destination for plot files.
        document (dict[str, object]): Recorded sensitivity observations.

    Returns:
        None: PNG and SVG plots are saved.
    """
    import numpy as np
    from matplotlib.backends.backend_agg import FigureCanvasAgg
    from matplotlib.figure import Figure

    figure = Figure(figsize=(20, 7), layout="constrained")
    FigureCanvasAgg(figure)
    axes = figure.subplots(1, 3)
    mutations = [mapping(row) for row in sequence(document["mutations"])]
    names = [str(row["name"]) for row in mutations]
    singles = [(index + 1, int(str(row["distance"]))) for index, row in enumerate(mutations) if "distance" in row]
    if singles:
        axes[0].scatter(*zip(*singles, strict=True), s=22, alpha=0.8)
    else:
        axes[0].text(0.5, 0.5, "No comparable single mutations", transform=axes[0].transAxes, ha="center")
    axes[0].set(
        title=f"Which single changes affect output most?\n{len(singles)} measured mutations; IDs follow the input file",
        xlabel="Mutation ID",
        ylabel="Changed leaf indicators",
    )
    pairs = [mapping(row) for row in sequence(document["interactions"]) if "mixed_difference_l1" in mapping(row)]
    positions = {name: index for index, name in enumerate(names)}
    matrix = np.full((len(names), len(names)), np.nan)
    for row in pairs:
        left, right = (positions[str(name)] for name in sequence(row["mutations"]))
        matrix[left, right] = matrix[right, left] = int(str(row["mixed_difference_l1"]))
    if pairs:
        from matplotlib import colormaps

        colors = colormaps["viridis"].with_extremes(bad="#dddddd")
        heatmap = axes[1].imshow(
            np.ma.masked_invalid(matrix),
            origin="lower",
            interpolation="nearest",
            cmap=colors,
            vmin=0,
            vmax=max(1, float(np.nanmax(matrix))),
            extent=(0.5, len(names) + 0.5, 0.5, len(names) + 0.5),
        )
        figure.colorbar(heatmap, ax=axes[1], label="Interaction magnitude", shrink=0.75)
    else:
        axes[1].text(0.5, 0.5, "No comparable pairs", transform=axes[1].transAxes, ha="center")
    axes[1].set(
        title=f"Which pairs interact?\n{len(pairs)} measured pairs; gray = unmeasured or inapplicable",
        xlabel="Mutation ID",
        ylabel="Mutation ID",
    )
    steps = [mapping(row) for row in sequence(document["sequence"]) if "cumulative_path_length" in mapping(row)]
    indices = list(range(len(steps) + 1))
    if steps:
        axes[2].plot(indices, [0, *(int(str(row["cumulative_path_length"])) for row in steps)], marker=".", label="Cumulative path length")
        axes[2].plot(
            indices, [0, *(int(str(row["endpoint_displacement"])) for row in steps)], marker=".", label="Displacement from baseline"
        )
        axes[2].legend()
    else:
        axes[2].text(0.5, 0.5, "No comparable sequence", transform=axes[2].transAxes, ha="center")
    axes[2].set(
        title=f"Do later changes undo earlier ones?\n{len(steps)} measured steps in explicit input order",
        xlabel="Completed mutation steps",
        ylabel="Leaf indicators",
    )
    for index, axis in enumerate(axes):
        axis.title.set_fontsize(10)
        axis.tick_params(labelsize=9)
        if index != 1:
            axis.grid(alpha=0.2)
    heading = figure.suptitle("Which values changes have the largest effects, and which interact?")
    heading.set_gid("plot-question")
    for suffix in ("png", "svg"):
        figure.savefig(output / f"sensitivity.{suffix}", dpi=240)
    figure.clear()
