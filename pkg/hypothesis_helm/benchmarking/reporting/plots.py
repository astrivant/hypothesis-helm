"""
Plot measured capped runtimes, exact-equivalence drops and correctly defined scaling.
"""

from __future__ import annotations

import os
import tempfile
from collections import defaultdict
from pathlib import Path
from statistics import NormalDist, mean
from textwrap import fill

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "hypothesis-helm-matplotlib"))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from hypothesis_helm.benchmarking.reporting.descriptions import describe
from hypothesis_helm.benchmarking.reporting.variation import repeated_line
from hypothesis_helm.schemas.contracts import mapping, sequence

COLORS = ["#2563eb", "#059669", "#d97706", "#9333ea", "#dc2626"]
type Point = dict[str, object]


def numeric(point: Point, key: str) -> float:
    """
    Read a numeric measurement without accepting an unknown estimate.

    Args:
        point (Point): Measured benchmark point.
        key (str): Numeric measurement name.

    Returns:
        float: Recorded numeric value.
    """
    value = point[key]
    if not isinstance(value, int | float):
        raise ValueError(f"missing numeric benchmark measurement: {key}")
    return float(value)


def groups(points: list[Point], family: str) -> dict[tuple[int, int, bool], list[Point]]:
    """
    Group repeated observations without mixing study families or replica counts.

    Args:
        points (list[Point]): Raw measured benchmark points.
        family (str): Study membership to select.

    Returns:
        dict[tuple[int, int, bool], list[Point]]: Observations keyed by count, replicas and pruning.
    """
    result: dict[tuple[int, int, bool], list[Point]] = defaultdict(list)
    for point in points:
        if family in sequence(point["families"]) and point["status"] != "failed":
            key = (
                int(numeric(point, "requested_permutations")),
                int(numeric(point, "replicas")),
                bool(point["pruning"]),
            )
            result[key].append(point)
    return dict(result)


def measured_line(
    axis: Axes,
    xs: list[float],
    observations: list[list[Point]],
    key: str,
    label: str,
    color: str,
) -> None:
    """
    Plot means and sample deviations with explicit deadline-censored markers.

    Args:
        axis (Axes): Destination axes.
        xs (list[float]): Actual workload sizes or replica counts.
        observations (list[list[Point]]): Repeated real observations at each x coordinate.
        key (str): Numeric measurement to display.
        label (str): Legend label.
        color (str): Accessible series color.

    Returns:
        None: Only observed measurements are plotted.
    """
    values = [[numeric(point, key) for point in batch] for batch in observations]
    centers = [mean(batch) for batch in values]
    completed = [
        batch if all(point["status"] == "passed" for point in records) else [] for batch, records in zip(values, observations, strict=True)
    ]
    repeated_line(axis, xs, completed, label, color)
    capped = [index for index, batch in enumerate(observations) if any(point["status"] == "time-limit" for point in batch)]
    if capped:
        axis.scatter(
            [xs[index] for index in capped],
            [centers[index] for index in capped],
            marker="X",
            s=95,
            color=color,
            edgecolors="white",
            zorder=5,
        )


def paired_ratios(baseline: list[Point], parallel: list[Point]) -> list[float]:
    """
    Calculate paired timing ratios only when both workloads completed.

    Args:
        baseline (list[Point]): Single-replica measurements by repetition.
        parallel (list[Point]): Target-replica measurements of the appropriate workload.

    Returns:
        list[float]: One ratio per completed pair, excluding censored observations.
    """
    reference = {int(numeric(point, "repeat")): point for point in baseline}
    ratios = []
    for point in parallel:
        other = reference.get(int(numeric(point, "repeat")))
        if other is not None and other["status"] == point["status"] == "passed":
            ratios.append(numeric(other, "elapsed_seconds") / numeric(point, "elapsed_seconds"))
    return ratios


def finish(figure: Figure, output: Path, name: str, subtitle: str, *, question: str | None = None) -> None:
    """
    Export a standalone vector figure and the README raster image.

    Args:
        figure (Figure): Completed measured figure.
        output (Path): Artifact directory.
        name (str): Stable artifact stem.
        subtitle (str): Method and censoring information printed in the figure.
        question (str | None): Explicit reader question for a custom plot outside the registered studies.

    Returns:
        None: PNG and SVG exports are written without requiring a display.
    """
    for axis in figure.axes:
        if not axis.images and not axis.yaxis_inverted():
            axis.set_ylim(bottom=0)
    counts = [
        int(count)
        for axis in figure.axes
        for collection in axis.collections
        if str(collection.get_label()).startswith("_variation_n=")
        for count in str(collection.get_label()).split("=")[1].split(":")
    ]
    if counts:
        sample_label = str(min(counts)) if min(counts) == max(counts) else f"{min(counts)}-{max(counts)}"
        subtitle += (
            f"\nMean ±1 SD (dark), ±2 SD (light); n={sample_label} per shaded point. "
            "Sample spread, not confidence intervals; clipped to physical bounds."
        )
    subtitle = "\n".join(fill(line, width=int(figure.get_figwidth() * 17)) for line in subtitle.splitlines())
    footer = max(0.07, 0.045 + 0.023 * len(subtitle.splitlines()))
    figure.text(0.06, 0.025, subtitle, fontsize=8, color="#475569")
    top = describe(figure, name, question=question)
    figure.tight_layout(rect=(0, footer, 1, top))
    figure.savefig(output / f"{name}.png", dpi=170, facecolor="white")
    figure.savefig(output / f"{name}.svg", facecolor="white")
    plt.close(figure)


def scaling_plots(output: Path, points: list[Point], shard_total: int) -> None:
    """
    Plot strong, weak and replica scaling with correct fixed-work comparisons.

    Args:
        output (Path): Figure destination.
        points (list[Point]): Raw observations from one fixed shard configuration.
        shard_total (int): Number of external CI shards defining global input counts.

    Returns:
        None: Three scaling figures are generated from available measurements.
    """
    strong = groups(points, "strong")
    weak = groups(points, "weak")
    if not strong or not weak:
        return
    counts = sorted({key[0] for key in strong})
    replicas = sorted({key[1] for key in strong})
    figure = plt.figure(figsize=(12, 5.4))
    left, right = figure.add_subplot(121), figure.add_subplot(122)
    figure.suptitle("Strong scaling · fixed total permutations", fontsize=17, fontweight="bold")
    for index, workers in enumerate(replicas):
        chosen = [count for count in counts if (count, workers, True) in strong]
        measured_line(
            left,
            [float(count) for count in chosen],
            [strong[(count, workers, True)] for count in chosen],
            "elapsed_seconds",
            f"{workers} worker shards",
            COLORS[index % len(COLORS)],
        )
    for index, count in enumerate(counts):
        baseline = strong.get((count, 1, True), [])
        ratios = [(workers, paired_ratios(baseline, strong.get((count, workers, True), []))) for workers in replicas]
        good = [(workers, ratio) for workers, ratio in ratios if ratio]
        repeated_line(
            right,
            [workers for workers, _ in good],
            [ratio for _, ratio in good],
            label=f"{count:,} global inputs",
            color=COLORS[index % len(COLORS)],
        )
    right.plot(replicas, replicas, "--", color="#94a3b8", label="ideal speedup")
    left.set(xlabel="Global permutation count", ylabel="Measured wall time (s)")
    right.set(xlabel="Parallel worker shards (local)", ylabel="T(1) / T(replicas)", xticks=replicas)
    left.legend(fontsize=9)
    right.legend(fontsize=8, ncol=2)
    finish(
        figure,
        output,
        "strong-scaling",
        "Fresh worker-local caches. Same input prefix at every replica count. X = budget stop; censored runs excluded from speedup.",
    )

    bases = sorted({count // (workers * shard_total) for count, workers, _ in weak})
    figure = plt.figure(figsize=(12, 5.4))
    left, right = figure.add_subplot(121), figure.add_subplot(122)
    figure.suptitle("Weak scaling · fixed permutations per worker", fontsize=17, fontweight="bold")
    for index, base in enumerate(bases):
        weak_chosen = [
            (workers, weak[(base * workers * shard_total, workers, True)])
            for workers in replicas
            if (base * workers * shard_total, workers, True) in weak
        ]
        measured_line(
            left,
            [float(base * workers * shard_total) for workers, _ in weak_chosen],
            [batch for _, batch in weak_chosen],
            "elapsed_seconds",
            f"{base:,} inputs / worker",
            COLORS[index % len(COLORS)],
        )
        baseline = weak.get((base * shard_total, 1, True), [])
        ratios = [(workers, paired_ratios(baseline, batch)) for workers, batch in weak_chosen]
        good = [(workers, ratio) for workers, ratio in ratios if ratio]
        repeated_line(
            right,
            [workers for workers, _ in good],
            [ratio for _, ratio in good],
            color=COLORS[index % len(COLORS)],
            label=f"{base:,} inputs / worker",
        )
    right.axhline(1, color="#94a3b8", linestyle="--", label="ideal weak efficiency")
    left.set(
        xlabel="Global permutation count (grows with workers)",
        ylabel="Measured wall time (s)",
    )
    right.set(xlabel="Parallel worker shards (local)", ylabel="T(1, n) / T(p, p·n)", xticks=replicas)
    left.legend(fontsize=9)
    right.legend(fontsize=8, ncol=2)
    finish(
        figure,
        output,
        "weak-scaling",
        "Each worker receives exactly n inputs after CI sharding. "
        "A flat runtime is ideal weak scaling; deadline stops are not completed timings.",
    )

    count = max(counts)
    replica_chosen = [(workers, strong[(count, workers, True)]) for workers in replicas if (count, workers, True) in strong]
    figure = plt.figure(figsize=(12, 5.4))
    left, right = figure.add_subplot(121), figure.add_subplot(122)
    figure.suptitle(f"Replica benchmark · {count:,} fixed global permutations", fontsize=17, fontweight="bold")
    measured_line(
        left,
        [float(workers) for workers, _ in replica_chosen],
        [batch for _, batch in replica_chosen],
        "completed_per_second",
        "completed checks / second",
        COLORS[0],
    )
    for metric, label, color in (
        ("rendered", "completed Helm renders", COLORS[2]),
        ("pruned", "proved-equivalent render skips", COLORS[1]),
    ):
        measured_line(
            right, [float(workers) for workers, _ in replica_chosen], [batch for _, batch in replica_chosen], metric, label, color
        )
    right.set(xticks=replicas, xlabel="Parallel worker shards (local)", ylabel="Completed input checks")
    left.set(xlabel="Parallel worker shards (local)", ylabel="Completed checks / second", xticks=replicas)
    left.legend(fontsize=9)
    right.legend(fontsize=8, ncol=2)
    finish(
        figure,
        output,
        "replicas",
        "Worker shards are local processes, not separate machines. "
        "Caches are not shared; startup, contention and repeated representatives are measured.",
    )


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Generate README figures using only recorded measurements and declared reference curves.

    Args:
        output (Path): JSON and image artifact directory.
        document (dict[str, object]): Metadata plus raw benchmark measurements.

    Returns:
        None: Available progressive, distribution and scaling figures are exported.
    """
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.16,
            "axes.axisbelow": True,
            "svg.fonttype": "none",
        }
    )
    metadata = mapping(document["metadata"])
    points = [mapping(point) for point in sequence(document["points"])]
    if any(point["shard"] != metadata["shard"] for point in points):
        raise ValueError("cannot plot mixed shard measurements")
    shard = metadata["shard"]
    shard_total = int(str(mapping(shard)["total"])) if shard else 1
    progressive = groups(points, "progressive")
    if progressive:
        figure = plt.figure(figsize=(12, 5.6))
        left, right = figure.add_subplot(121), figure.add_subplot(122)
        figure.suptitle(
            "Permutation benchmark · measured work under a time ceiling",
            fontsize=17,
            fontweight="bold",
        )
        for pruning, color, label in (
            (False, COLORS[2], "render every input"),
            (True, COLORS[1], "exact-equivalence pruning"),
        ):
            counts = sorted(key[0] for key in progressive if key[2] == pruning)
            batches = [progressive[(count, 1, pruning)] for count in counts]
            if not batches:
                continue
            measured_line(left, [float(count) for count in counts], batches, "elapsed_seconds", label, color)
            measured_line(right, [float(count) for count in counts], batches, "completed", label, color)
            censored = [point for batch in batches for point in batch if point.get("observation") == "shared-prefix-censored"]
            if censored:
                first = min(censored, key=lambda point: numeric(point, "requested_permutations"))
                end = max(numeric(point, "censoring_upper_target") for point in censored)
                begin = numeric(first, "requested_permutations")
                left.plot(
                    [begin, end],
                    [numeric(first, "elapsed_seconds")] * 2,
                    "--",
                    color=color,
                    alpha=0.65,
                )
                right.plot([begin, end], [numeric(first, "completed")] * 2, "--", color=color, alpha=0.65)
            if pruning:
                measured_line(right, [float(count) for count in counts], batches, "pruned", "render invocations dropped", COLORS[0])
        limit = float(str(metadata["time_limit_seconds"]))
        left.axhline(limit, linestyle="--", color="#475569", label=f"{limit:g}s execution ceiling")
        left.set(
            xlabel="Requested global permutation count",
            ylabel="Measured wall time (s)",
        )
        right.set(
            xlabel="Requested global permutation count",
            ylabel="Completed checks / skipped renders",
        )
        # Keep measured checkpoints prominent rather than stretching to unfinished targets.
        visible_end = max(key[0] for key in progressive) * 1.1
        left.set_xlim(0, visible_end)
        right.set_xlim(0, visible_end)
        left.legend(fontsize=9)
        right.legend(fontsize=9)
        finish(
            figure,
            output,
            "progressive",
            "Checkpoints within each repeat share one growing run. X and dashed tails mark unfinished targets "
            "in that same capped window, not separate trials.",
        )
    scaling_plots(output, points, shard_total)
    suitable = [
        point
        for point in points
        if point["pruning"]
        and sum(sum(int(str(v)) for v in sequence(mapping(worker)["input_histogram"])) for worker in sequence(point["workers"])) > 0
    ]
    if suitable:
        point = max(suitable, key=lambda item: numeric(item, "completed"))
        observed = [
            sum(int(str(sequence(mapping(worker)["input_histogram"])[index])) for worker in sequence(point["workers"]))
            for index in range(32)
        ]
        rendered = [
            sum(int(str(sequence(mapping(worker)["render_histogram"])[index])) for worker in sequence(point["workers"]))
            for index in range(32)
        ]
        spec = mapping(metadata["distribution"])
        edges = [float(str(value)) for value in sequence(spec["histogram_edges"])]
        xs = [(left + right) / 2 for left, right in zip(edges[:-1], edges[1:], strict=True)]
        total = sum(observed)
        distribution = NormalDist(float(str(spec["mean"])), float(str(spec["stddev"])))
        lower, upper = spec["lower"], spec["upper"]
        start = distribution.cdf(float(str(lower))) if lower is not None else 0.0
        stop = distribution.cdf(float(str(upper))) if upper is not None else 1.0
        reference = [
            total * (distribution.cdf(right) - distribution.cdf(left)) / (stop - start)
            for left, right in zip(edges[:-1], edges[1:], strict=True)
        ]
        width = (edges[-1] - edges[0]) / 32
        figure = plt.figure(figsize=(10, 5.4))
        axis = figure.add_subplot(111)
        figure.suptitle("Received Helm output · predictable normal quantiles", fontsize=17, fontweight="bold")
        axis.bar(
            [x - width * 0.2 for x in xs],
            observed,
            width=width * 0.4,
            color=COLORS[0],
            label="oracle-checked inputs",
        )
        axis.bar(
            [x + width * 0.2 for x in xs],
            rendered,
            width=width * 0.4,
            color=COLORS[1],
            label="completed Helm renders",
        )
        axis.plot(
            xs,
            reference,
            "--",
            color=COLORS[2],
            label=f"Normal reference: mean={spec['mean']}, stddev={spec['stddev']}",
        )
        axis.set(xlabel="Emitted ConfigMap value (rounded normal quantile)", ylabel="Measured frequency")
        axis.legend(fontsize=9)
        finish(
            figure,
            output,
            "output-distribution",
            f"{spec['input_complexity']} inputs; {spec['output_bins']} quantile bins. "
            "Every received value is checked against an independent normal-quantile oracle.",
        )
