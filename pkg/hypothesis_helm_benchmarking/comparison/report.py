"""
Verify complete matched evidence and render latency, cold-start and speedup plots.
"""

from __future__ import annotations

import logging
from statistics import median, stdev
from typing import TYPE_CHECKING

from hypothesis_helm.reporting.documentation.contents import with_contents

from hypothesis_helm_benchmarking.comparison.model import BACKENDS, Lane, Workload, save, validate_lane

if TYPE_CHECKING:
    from pathlib import Path

__all__ = ("report", "validate_comparison")
LOGGER = logging.getLogger(__name__)


def validate_comparison(workload: Workload, lanes: tuple[Lane, ...]) -> tuple[Lane, ...]:
    """
    Admit exactly one equivalent lane per backend with the same common runtime.

    Args:
        workload (Workload): Exact frozen dispatch manifest.
        lanes (tuple[Lane, ...]): Complete measured backend receipts in any order.

    Returns:
        tuple[Lane, ...]: Validated results in reference, compiled CPU, GPU order.

    Raises:
        ValueError: Lanes are missing, duplicated, stale, non-equivalent or incomparable.
    """
    if len(lanes) != len(BACKENDS) or {lane.backend for lane in lanes} != set(BACKENDS):
        raise ValueError("comparison requires exactly one reference, cpu-vector and gpu lane")
    ordered = tuple(next(lane for lane in lanes if lane.backend == backend) for backend in BACKENDS)
    for lane in ordered:
        validate_lane(workload, lane)
    common = {(lane.hardware.system, lane.hardware.architecture, lane.hardware.python, lane.hardware.numpy) for lane in ordered}
    if len(common) != 1 or ordered[0].hardware.cpus != ordered[1].hardware.cpus:
        raise ValueError("comparison host architecture, CPU allocation or shared runtime differs")
    return ordered


def report(workload: Workload, lanes: tuple[Lane, ...], output: Path) -> None:
    """
    Generate durable measured data and figures only after all three lanes validate.

    Args:
        workload (Workload): Common immutable source and workload manifest.
        lanes (tuple[Lane, ...]): Results from all three actual backends.
        output (Path): Caller-owned publication directory.

    Returns:
        None: JSON, canonical Markdown and paired PNG/SVG figures are written.
    """
    from matplotlib import pyplot as plt

    from hypothesis_helm_benchmarking.reporting.plots import COLORS

    ordered = validate_comparison(workload, lanes)
    LOGGER.info("Rendering matched backend comparison cases=%d repeats=%d", len(workload.batches), workload.repeats)
    output.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 3, figsize=(17, 5))
    for index, lane in enumerate(ordered):
        label = f"{lane.backend} / {lane.hardware.accelerator}"
        medians = [median(sample.wall for sample in case.samples) for case in lane.cases]
        deviations = [stdev(sample.wall for sample in case.samples) for case in lane.cases]
        cold = [case.setup + case.cold.wall for case in lane.cases]
        axes[0].errorbar(
            workload.batches, medians, yerr=deviations, fmt=("o-", "s-", "^-")[index], color=COLORS[index], label=label, capsize=3
        )
        axes[1].plot(workload.batches, cold, ("o-", "s-", "^-")[index], color=COLORS[index], label=label)
        reference = [median(sample.wall for sample in case.samples) for case in ordered[0].cases]
        axes[2].plot(
            workload.batches,
            [base / current for base, current in zip(reference, medians, strict=True)],
            ("o-", "s-", "^-")[index],
            color=COLORS[index],
            label=label,
        )
    axes[0].set(ylabel="Steady pass latency (seconds)", yscale="log")
    axes[1].set(ylabel="Worker setup + first pass (seconds)", yscale="log")
    axes[2].set(ylabel="Reference median / backend median", yscale="log")
    axes[2].axhline(1, color="gray", linestyle="--", linewidth=1)
    for axis in axes:
        axis.set(xlabel="Candidates per worker request", xscale="log", xticks=workload.batches)
        axis.grid(alpha=0.2)
    figure.suptitle("Matched finite-planner backend performance", y=0.99)
    figure.text(0.5, 0.92, "How do backend latency, startup cost and speedup change with the same candidate batches?", ha="center")
    handles, labels = axes[2].get_legend_handles_labels()
    figure.legend(handles, labels, loc="lower center", ncol=3, bbox_to_anchor=(0.5, 0.04))
    figure.text(
        0.5,
        0.01,
        "Identical plan, seed and ordered candidates; synchronized worker IPC and transfer included. "
        "Error bars: sample standard deviation; cold pass excluded from steady repeats.",
        ha="center",
        fontsize=9,
    )
    figure.tight_layout(rect=(0, 0.14, 1, 0.88))
    for suffix in ("png", "svg"):
        figure.savefig(output / f"comparison.{suffix}", dpi=160)
    plt.close(figure)
    save(output / "workload.json", workload)
    save(output / "measurements.json", ordered)
    lines = [
        "# Matched backend comparison",
        "",
        "![Matched backend performance](comparison.png)",
        "",
        f"Measured source: `{workload.source}`. Run: `{workload.run}`, attempt `{workload.attempt}`.",
        "",
        f"All lanes use seed `{workload.seed}`, {workload.candidates:,} candidates, {workload.factors} Boolean factors "
        f"and {workload.repeats} steady repeats per batch size. Every ordered result matches an independent host oracle.",
        "",
        "## Scope and timing",
        "",
        "This suite measures finite-predicate evaluation through the production worker boundary. "
        "It does not measure end-to-end Helm rendering or claim that every study benefits from a GPU. "
        "Shared performance and sparsity studies still execute on CPU.",
        "",
        "Steady latency includes packing, worker IPC, device transfers, synchronization and output decoding. "
        "Engine-reported time and host verification time are retained separately in the measurements. "
        "Cold time includes worker setup and the first full pass, including lazy compilation. "
        "The first pass warms the worker before steady repeats; worker setup is repeated for each batch-size case. "
        "Ratios compare medians on separate runners with their observed hardware below. "
        "No minimum speedup is required; slower GPU results remain valid evidence.",
        "",
        "## Observed hardware",
        "",
        "| Backend | Device | Accelerator | OS / architecture | CPUs | Python | NumPy | Compiler |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for lane in ordered:
        host = lane.hardware
        lines.append(
            f"| {lane.backend} | {lane.device} | {host.accelerator} | {host.system} / {host.architecture} | "
            f"{host.cpus} | {host.python} | {host.numpy} | {host.compiler} |"
        )
    lines.extend(
        [
            "",
            "## Reproduce from retained measurements",
            "",
            "```sh",
            "hypothesis-helm-benchmark backend-comparison report --input studies/backend-comparison/workload.json "
            "--lanes studies/backend-comparison/measurements.json --output .cache/backend-comparison-replot",
            "```",
            "",
            "The manifest and compact measurements are committed beside the plots. "
            "Missing lanes, fallback devices, changed source/workload, output mismatches and invalid durations reject publication.",
            "",
        ]
    )
    (output / "README.md").write_text(with_contents("\n".join(lines), max_depth=3))
    LOGGER.info("Completed matched comparison report output=%s", output)
