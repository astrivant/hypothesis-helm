"""
Measure sample size against known defect discovery using a fully rendered stress chart.
"""

import argparse
import csv
import json
import math
import platform
import shutil
import statistics
import subprocess
import time
from pathlib import Path

from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.stress import FAMILIES, Stress
from hypothesis_helm.benchmarking.charts.structures import expected_manifests
from hypothesis_helm.benchmarking.charts.workload import source_digest
from hypothesis_helm.benchmarking.execution.profiling import profile_settings
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.reporting.variation import bands
from hypothesis_helm.benchmarking.studies.matrix import bundle_key, reference_space
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import RenderFailure, render
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping, number, sequence


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Draw empirical recall and preserve the numbers behind the recommendation.

    Args:
        output (Path): Measured study directory.
        document (dict[str, object]): Complete reference and repeated sampling results.

    Returns:
        None: Matplotlib figures, CSV, and a brief Markdown report are written.
    """
    from matplotlib import pyplot as plt

    rows = [mapping(row) for row in sequence(document["rows"])]
    metadata = mapping(document["metadata"])
    figure, axes = plt.subplots(1, 2, figsize=(13, 5))
    for axis, x, label in (
        (axes[0], [row["sample_size"] for row in rows], "Random inputs tested (plus defaults)"),
        (axes[1], [row["retained_percent"] for row in rows], "Eligible inputs retained (%)"),
    ):
        for metric, label, color in (
            ("bug_recall", "Distinct defects found: mean", "#2563eb"),
            ("error_input_recall", "Erroneous inputs tested: mean", "#d97706"),
        ):
            centers = [100 * number(row[f"mean_{metric}"]) for row in rows]
            axis.plot(x, centers, "o-", label=label, color=color)
            if any(row.get(f"stddev_{metric}") is not None for row in rows):
                bands(
                    axis,
                    [number(value) for value in x],
                    centers,
                    [100 * number(row[f"stddev_{metric}"]) if row.get(f"stddev_{metric}") is not None else math.nan for row in rows],
                    [int(str(row.get("trials", metadata["trials"]))) for row in rows],
                    color,
                    upper=100,
                )
            elif metric == "bug_recall":
                axis.fill_between(
                    x,
                    [100 * number(row["p05_bug_recall"]) for row in rows],
                    [100 * number(row["p95_bug_recall"]) for row in rows],
                    alpha=0.2,
                    color=color,
                    label="5th-95th percentile across seeds (legacy data)",
                )
        axis.plot(x, [row["retained_percent"] for row in rows], ":", label="One-input defect: uniform-sample probability")
        axis.axhline(96, color="grey", linewidth=1, label="96% recall target")
        axis.set(xlabel=label, ylabel="Recall / detection chance (%)", ylim=(-2, 105))
        axis.grid(alpha=0.2)
    axes[0].set_xscale("log")
    axes[1].legend(fontsize=8, loc="lower right")
    finish(
        figure,
        output,
        "sampling-recall",
        "Known synthetic defects; repeated subsets of real Helm observations. No arbitrary-chart recall guarantee.",
    )
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    recommendation = document["suggested_minimum"]
    lines = [
        "# Random sampling and defect discovery",
        "",
        "[Benchmarking](../../benchmarks/README.md)",
        "",
        f"The shared stress chart has {metadata['valid_inputs']} valid inputs and six known defect families. "
        f"Every input was rendered with Helm; {metadata['trials']} seeded samples were evaluated at each size.",
        "",
        "![Sample size and defect recall](sampling-recall.png)",
        "",
        "| Random inputs + defaults | Retained | Mean defects found | 5th percentile recall | "
        "Seeds reaching 96% recall | Erroneous inputs tested |",
        "| ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in rows:
        lines.append(
            f"| {row['sample_size']} + 1 | {number(row['retained_percent']):.1f}% | "
            f"{number(row['mean_bug_recall']) * 6:.2f} / 6 | {number(row['p05_bug_recall']):.1%} | "
            f"{number(row['target_success_rate']):.1%} | {number(row['mean_error_input_recall']):.1%} |"
        )
    lines.extend(
        [
            "",
            f"The first measured sample size reaching 96% defect recall in at least 95% of these seeds is **{recommendation}**.",
            "This is a fixture-specific observation, not a confidence bound or a minimum valid for arbitrary charts.",
            "",
            "With uniform sampling, a defect triggered by only one eligible input is found with probability sample_size / population_size. "
            "Testing 70% gives a 70% chance of finding that defect, regardless of how large the population is.",
            "",
            "The CLI policy is opt-in: `--sample-random 70 --sample-min-cases 128` keeps at least 128 eligible cases, "
            "or all of them when fewer exist. Defaults and protected topology representatives are additional safeguards. "
            "The default floor is a conservative policy choice, not a derived 96% guarantee.",
            "",
            "Timing covers the complete reference render, not separate executions of every sampled subset. "
            "Samples use the production selector and preserve the same ranking as sample size increases.",
            "",
            "[Measurements](results.csv) · [Reference and provenance](results.json) · [Chart recipe](chart-parameters.yaml)",
            "",
        ]
    )
    (output / "README.md").write_text("\n".join(lines))


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Render a complete known population before evaluating repeated random subsets.

    Args:
        argv (list[str] | None): Explicit command arguments or the process command line.
        workspace (FixtureWorkspace | None): Explicit owner of the invocation's reusable chart.

    Returns:
        int: Zero after verified plots, or one when the reference cannot be completed.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("benchmarks/runs/sampling"))
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--trials", type=int, default=500)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        stored = mapping(json.loads((args.output / "results.json").read_text()))
        if stored.get("status") != "complete":
            parser.error("a complete reference is required to plot recall")
        plot(args.output, stored)
        return 0
    if args.trials < 1 or not 0 < args.time_limit <= 540:
        parser.error("require positive trials and an execution limit in (0, 9m]")
    if (args.output / "results.json").exists():
        parser.error("choose a new output directory")
    helm = shutil.which(args.helm)
    if helm is None:
        parser.error("Helm is required")
    logical = args.output / "chart"
    spec = generate(logical, stress=Stress(), workspace=workspace)
    chart = Chart.load(chart_path(logical, workspace=workspace))
    reference, _ = reference_space(chart, spec, 4096)
    baseline = configuration_key(chart.defaults)
    identities = [baseline, *sorted(reference - {baseline})]
    observed: dict[str, int] = {}
    started = time.perf_counter()
    status = "complete"
    try:
        with execution_timer(args.time_limit):
            for identity in identities:
                remaining = args.time_limit - (time.perf_counter() - started)
                if remaining <= 0:
                    raise TimeLimitReached()
                values = mapping(json.loads(identity))
                resources = render(chart, values, helm=helm, release="matrix", timeout=min(30, remaining))
                if bundle_key(resources) != bundle_key(expected_manifests(values, spec)):
                    raise AssertionError("independent stress oracle disagrees with Helm")
                defects = {
                    mapping(resource["metadata"])["name"]
                    for resource in resources
                    if mapping(resource.get("data", {})).get("status") == "incorrect"
                }
                observed[identity] = sum(1 << index for index, name in enumerate(FAMILIES) if "defect-" + name in defects)
                if len(observed) % 100 == 0:
                    print(f"Reference: {len(observed)}/{len(identities)} inputs rendered", flush=True)
    except TimeLimitReached:
        status = "time-limit"
    except RenderFailure as exc:
        if isinstance(exc.__cause__, subprocess.TimeoutExpired) and time.perf_counter() - started >= args.time_limit:
            status = "time-limit"
        else:
            raise
    document: dict[str, object] = {
        "status": status,
        "metadata": {
            "helm": Processes().run([helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "python": platform.python_version(),
            "code_sha256": code_digest(),
            "chart_sha256": source_digest(chart.path),
            "seed": args.seed,
            "trials": args.trials,
            "valid_inputs": len(identities),
            "time_limit_seconds": args.time_limit,
            "execution_seconds": time.perf_counter() - started,
            "profiling": profile_settings(),
        },
        "reference": {"completed": len(observed), "remaining": len(identities) - len(observed), "fault_masks": observed},
        "rows": [],
        "suggested_minimum": None,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    if status != "complete":
        (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
        return 1
    import numpy as np

    population = identities[1:]
    total_errors = sum(bool(mask) for mask in observed.values())
    counts = sorted({min(len(population), 2**index) for index in range(11)} | {math.ceil(0.7 * len(population)), len(population)})
    rows = []
    with BenchmarkProgress("Sampling: sample sizes") as display:
        for count in display.track(counts):
            recall, error_recall = [], []
            for seed in range(args.seed, args.seed + args.trials):
                selected, _ = Sampling(1e-12, count).select(population, lambda value: value, seed)
                mask = observed[baseline]
                erroneous = int(bool(mask))
                for identity in selected:
                    mask |= observed[identity]
                    erroneous += bool(observed[identity])
                recall.append(mask.bit_count() / len(FAMILIES))
                error_recall.append(erroneous / total_errors)
            rows.append(
                {
                    "status": "complete",
                    "sample_size": count,
                    "retained_percent": 100 * count / len(population),
                    "mean_bug_recall": float(np.mean(recall)),
                    "stddev_bug_recall": statistics.stdev(recall) if len(recall) > 1 else None,
                    "stddev_error_input_recall": statistics.stdev(error_recall) if len(error_recall) > 1 else None,
                    "trials": args.trials,
                    "p05_bug_recall": float(np.quantile(recall, 0.05)),
                    "p95_bug_recall": float(np.quantile(recall, 0.95)),
                    "target_success_rate": sum(value >= 0.96 for value in recall) / len(recall),
                    "mean_error_input_recall": float(np.mean(error_recall)),
                }
            )
    document["rows"] = rows
    document["suggested_minimum"] = next(row["sample_size"] for row in rows if number(row["target_success_rate"]) >= 0.95)
    (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
    plot(args.output, document)
    return 0
