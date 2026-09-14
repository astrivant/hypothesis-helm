"""
Plot measured sample floors across paired rendered breadth and depth sweeps.
"""

import csv
import statistics
from collections import defaultdict
from pathlib import Path

from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.schemas.contracts import mapping, sequence


def plot(output: Path, document: dict[str, object]) -> bool:
    """
    Facet measured floor heatmaps by input count and defect-trigger depth.

    Args:
        output (Path): Destination for PNG, SVG and summarized CSV.
        document (dict[str, object]): Measured profiles with independent breadth/depth controls.

    Returns:
        bool: Whether shaped measurements were available and plotted.
    """
    import numpy as np
    from matplotlib import pyplot as plt

    cells = [mapping(cell) for cell in sequence(document["profiles"]) if mapping(cell).get("output_shape")]
    if not cells:
        return False
    groups: dict[tuple[int, int], dict[tuple[int, int], list[int]]] = defaultdict(lambda: defaultdict(list))
    for cell in cells:
        features = mapping(mapping(cell["descriptor"])["features"])
        maximum = mapping(mapping(mapping(cell["analysis"])["complexity"])["maximum_output"])
        group = (int(str(features["input_fields"])), int(str(features["gate_depth"])))
        position = (int(str(maximum["breadth"])), int(str(maximum["depth"])))
        groups[group][position].append(int(str(cell["minimum_cases"])))
    columns = min(3, len(groups))
    figure, axes = plt.subplots(
        (len(groups) + columns - 1) // columns, columns, figsize=(5 * columns, 5 * ((len(groups) + columns - 1) // columns)), squeeze=False
    )
    maximum_floor = max(value for positions in groups.values() for observations in positions.values() for value in observations)
    rows: list[dict[str, object]] = []
    for axis, (group, positions) in zip(axes.flat, sorted(groups.items()), strict=False):
        breadths = sorted({key[0] for key in positions})
        depths = sorted({key[1] for key in positions})
        data = np.full((len(depths), len(breadths)), np.nan)
        for (breadth, depth), values in positions.items():
            center = statistics.mean(values)
            spread = statistics.stdev(values) if len(values) > 1 else None
            x, y = breadths.index(breadth), depths.index(depth)
            data[y, x] = center
            axis.text(
                x, y, f"{center:.1f}" + (f"\n±{spread:.1f}" if spread is not None else "\nn=1"), ha="center", va="center", fontsize=10
            )
            rows.append(
                {
                    "input_fields": group[0],
                    "gate_depth": group[1],
                    "breadth": breadth,
                    "depth": depth,
                    "score": breadth * depth,
                    "mean_case_floor": center,
                    "stddev_case_floor": spread,
                    "placements": len(values),
                }
            )
        picture = axis.imshow(data, origin="lower", aspect="auto", vmin=0, vmax=max(1, maximum_floor), cmap="YlGnBu", alpha=0.65)
        axis.set(
            xticks=range(len(breadths)),
            xticklabels=breadths,
            yticks=range(len(depths)),
            yticklabels=depths,
            xlabel="Most manifest nodes at one level (breadth)",
            ylabel="Longest root-to-value path (depth)",
            title=f"{group[0]} input fields; {group[1]} condition{'s' if group[1] != 1 else ''} per defect",
        )
        figure.colorbar(picture, ax=axis, label="Minimum configurations measured")
    for axis in list(axes.flat)[len(groups) :]:
        axis.set_visible(False)
    finish(
        figure,
        output,
        "complexity-sweep",
        "Cells: mean ±1 sample SD across defect placements; seeds calibrate each floor. Missing cells are not interpolated.",
    )
    with (output / "complexity-sweep.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return True
