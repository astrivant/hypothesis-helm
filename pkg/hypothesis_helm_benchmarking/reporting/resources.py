"""
Rank saved phase measurements independently for each resource and process role.
"""

from __future__ import annotations

import json
import logging
import math
from pathlib import Path

from attrs import asdict, frozen
from hypothesis_helm.reporting.documentation.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence

from hypothesis_helm_benchmarking.execution.resources import METRICS

__all__ = ("Rank", "rank", "render_resources")

LOGGER = logging.getLogger(__name__)


@frozen
class Rank:
    """
    Retain a phase's measured amount and completeness before assigning a rank.

    Attributes:
        phase (str): Named execution boundary.
        value (float | None): Complete metric, or None when any contributing capture is missing it.
        observed (float | None): Available subtotal or observed peak, even when incomplete.
        available (int): Number of captures contributing an observation.
        captures (int): Number of captures in which this phase occurred.
        position (int | None): Descending rank among complete measurements only.
        share_percent (float | None): Additive-resource share only when all phase measurements are complete.
    """

    phase: str
    value: float | None
    observed: float | None
    available: int
    captures: int
    position: int | None
    share_percent: float | None


def rank(profiles: list[dict[str, object]], metric: str) -> list[Rank]:
    """
    Sum counters or take peaks without fabricating missing values or summing memory peaks.

    Args:
        profiles (list[dict[str, object]]): Captures from one process role.
        metric (str): Declared resource metric with explicit aggregation semantics.

    Returns:
        list[Rank]: Complete measurements in descending order, then incomplete phases alphabetically.

    Raises:
        ValueError: A measurement is malformed, non-finite, negative or from an unknown format.
    """
    if metric not in METRICS:
        raise ValueError("Unknown phase resource metric")
    buckets: dict[str, list[float | None]] = {}
    for profile in profiles:
        resources = profile.get("resources")
        if resources is None:
            buckets.setdefault("Historical capture without resource counters", []).append(None)
            continue
        usage = mapping(resources)
        if usage.get("format") != "hypothesis-helm-phase-resources-v1":
            raise ValueError("Unsupported phase resource format")
        names = set()
        for item in sequence(usage["phases"]):
            phase = mapping(item)
            name = str(phase["name"])
            if name in names:
                raise ValueError("Duplicate phase in resource capture")
            names.add(name)
            value = mapping(phase["values"])[metric]
            if value is not None and (
                isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value) or value < 0
            ):
                raise ValueError("Resource measurements must be finite and nonnegative or missing")
            # Partial hooks and failed device instrumentation cannot establish complete rankings.
            valid = profile.get("capture_complete") is True
            valid = valid and not (metric.startswith("gpu_") and usage.get("device_errors"))
            buckets.setdefault(name, []).append(float(value) if value is not None and valid else None)
    rows: list[tuple[str, float | None, float | None, int, int]] = []
    for name, observations in buckets.items():
        available = [value for value in observations if value is not None]
        observed = (max(available) if METRICS[metric][2] == "max" else sum(available)) if available else None
        complete = len(available) == len(observations)
        rows.append((name, observed if complete else None, observed, len(available), len(observations)))
    rows.sort(key=lambda row: (row[1] is None, -(row[1] or 0), row[0]))
    total = sum(row[1] or 0 for row in rows)
    shares = METRICS[metric][2] == "sum" and total > 0 and all(row[1] is not None for row in rows)
    return [
        Rank(
            name,
            value,
            observed,
            available,
            captures,
            index + 1 if value is not None else None,
            value / total * 100 if shares and value is not None else None,
        )
        for index, (name, value, observed, available, captures) in enumerate(rows)
    ]


def render_resources(files: list[Path], output: Path) -> dict[str, object]:
    """
    Produce independent Markdown tables, raw rankings and Matplotlib panels from saved captures.

    Args:
        files (list[Path]): Fully written process captures, never an implicit benchmark rerun.
        output (Path): Destination beside the existing flame graphs.

    Returns:
        dict[str, object]: File inventory, roles and capture completeness for publication.
    """
    from matplotlib import pyplot as plt

    from hypothesis_helm_benchmarking.reporting.plots import COLORS

    profiles: dict[str, list[dict[str, object]]] = {}
    for path in files:
        document = mapping(json.loads(path.read_text()))
        profiles.setdefault(str(document["role"]), []).append(document)
    output.mkdir(parents=True, exist_ok=True)
    LOGGER.info("Rendering phase resource rankings; roles=%d captures=%d", len(profiles), len(files))
    lines = [
        "# Phase resource rankings",
        "",
        "Which execution phases consume the most of each resource?",
        "",
        "Rankings are independent for each resource and process role. CPU is user plus system process CPU time; wall time includes waits.",
        "Values include profiling overhead. Worker wall times can overlap and are summed process time, not pipeline duration.",
        "Reaped child CPU and storage can overlap captured workers; do not add parent and worker counters across process roles.",
        "RAM is sampled process RSS, not allocation growth or an exact peak. "
        "Aggregated RAM is the largest individual process observation, not concurrent tree RAM.",
        "Storage counters are Linux procfs read_bytes/write_bytes, including waited-for children. "
        "Writes count dirtied bytes, not necessarily flushed bytes or disk footprint.",
        "CUDA time measures synchronized current-stream event intervals, including possible idle gaps; "
        "it is not kernel-active time or SM utilization.",
        "CUDA memory is PyTorch's allocated-memory high-water mark during isolated predicate evaluation, "
        "including retained buffers; driver and external allocations are excluded.",
        "GPU setup peaks, Metal metrics, unprofiled subprocess RAM, unreaped child I/O, network bytes and disk footprint are unavailable.",
        "Missing metrics remain unavailable. Partial captures are unranked; "
        "peaks have no additive percentage share. Zero means an observed zero.",
        "",
    ]
    rankings: dict[str, dict[str, list[dict[str, object]]]] = {}
    for role, captures in sorted(profiles.items()):
        rankings[role] = {}
        figure, axes = plt.subplots(4, 2, figsize=(18, 20), squeeze=False)
        try:
            lines.extend([f"## {role.capitalize()} processes", "", f"![Resource rankings]({role}.png)", ""])
            for (metric, (label, unit, _)), axis in zip(METRICS.items(), axes.flat, strict=True):
                rows = rank(captures, metric)
                rankings[role][metric] = [asdict(row) for row in rows]
                measured = [row for row in rows if row.value is not None]
                if measured:
                    axis.barh([row.phase for row in measured], [row.value for row in measured], color=COLORS[0])
                    axis.invert_yaxis()
                else:
                    axis.text(0.5, 0.5, "Unavailable", ha="center", transform=axis.transAxes)
                axis.set(title=label, xlabel=unit, xlim=(0, None))
                axis.tick_params(axis="y", labelsize=8)
                lines.extend(
                    [
                        f"### {label}",
                        "",
                        f"| Rank | Phase | Amount ({unit}) | Share | Captures |",
                        "| ---: | --- | ---: | ---: | ---: |",
                    ]
                )
                for row in rows:
                    value = f"{row.value:.6g}" if row.value is not None else "Unavailable"
                    if row.value is None and row.observed is not None:
                        value += f" (observed {row.observed:.6g})"
                    share = f"{row.share_percent:.2f}%" if row.share_percent is not None else "n/a"
                    lines.append(f"| {row.position or '-'} | {row.phase} | {value} | {share} | {row.available}/{row.captures} |")
                lines.append("")
            figure.suptitle(f"Phase resource rankings: {role} processes", y=0.995)
            question = figure.text(0.5, 0.975, "Which phases consume the most time, memory and storage I/O?", ha="center")
            question.set_gid("plot-question")
            figure.tight_layout(rect=(0, 0.01, 1, 0.96))
            for extension in ("png", "svg"):
                figure.savefig(output / f"{role}.{extension}", dpi=140)
        finally:
            plt.close(figure)
    (output / "rankings.json").write_text(json.dumps(rankings, indent=2, allow_nan=False) + "\n")
    (output / "README.md").write_text(with_contents("\n".join(lines)))
    return {"directory": "resources", "roles": sorted(profiles), "captures": len(files), "rankings": "resources/rankings.json"}
