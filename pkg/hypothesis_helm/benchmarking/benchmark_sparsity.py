"""
Measure outcome coverage and distribution error while thinning real Helm workloads.
"""

import argparse
import json
import math
import platform
import random
import shutil
import subprocess
import time
from collections import Counter
from pathlib import Path

from hypothesis_helm.benchmarking.benchmark_helm import ROOT, code_digest
from hypothesis_helm.benchmarking.plots import finish
from hypothesis_helm.benchmarking.runner import Job, execute_worker
from hypothesis_helm.benchmarking.topology import expected_topology
from hypothesis_helm.benchmarking.workload import expected_output, source_digest
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.schemas.contracts import configuration_key, mapping


def quality(observed: dict[str, int], reference: dict[str, int], *, ordered: bool = True) -> dict[str, float]:
    """
    Compare discrete frequencies against the exact rounded chart distribution.

    Args:
        observed (dict[str, int]): Received scalar counts from completed assertions.
        reference (dict[str, int]): Exact multiplicities across all quantile selectors.
        ordered (bool): Compute a CDF error only for numerically ordered scalar outcomes.

    Returns:
        dict[str, float]: Support coverage, total variation and maximum CDF error.
    """
    total, population = sum(observed.values()), sum(reference.values())
    if total <= 0 or population <= 0 or any(n < 0 for n in (*observed.values(), *reference.values())):
        raise ValueError("distributions require nonnegative counts and positive totals")
    keys = sorted(set(observed) | set(reference), key=float if ordered else str)
    differences = [observed.get(key, 0) / total - reference.get(key, 0) / population for key in keys]
    cumulative = 0.0
    maximum = 0.0
    for difference in differences:
        cumulative += difference
        maximum = max(maximum, abs(cumulative))
    return {
        "coverage": sum(observed.get(key, 0) > 0 for key in reference) / len(reference),
        "total_variation": sum(abs(value) for value in differences) / 2,
        **({"cdf_error": maximum} if ordered else {}),
    }


def samples(size: int, retain: float, levels: int, seed: int) -> list[list[int]]:
    """
    Build nested random subsets without duplicate input IDs within a run.

    Args:
        size (int): Dense reference workload size.
        retain (float): Fraction retained at each consecutive stage.
        levels (int): Maximum number of stages including the dense run.
        seed (int): Reproducible random ordering seed.

    Returns:
        list[list[int]]: Decreasing prefixes of one shuffled dense input pool.
    """
    if size < 1 or levels < 1 or not 0 < retain < 1:
        raise ValueError("size and levels must be positive; retain must lie between 0 and 1")
    indices = list(range(size))
    random.Random(seed).shuffle(indices)
    result = [indices]
    for _ in range(levels - 1):
        count = max(1, int(len(result[-1]) * retain))
        if count == len(result[-1]):
            break
        result.append(indices[:count])
    return result


def plot(output: Path, rows: list[dict[str, object]], reference: dict[str, int]) -> None:
    """
    Plot per-stage coverage and measured distributions with a common reference.

    Args:
        output (Path): Figure destination.
        rows (list[dict[str, object]]): Successful consecutive fresh-cache executions.
        reference (dict[str, int]): Finite expected outcome multiplicities.

    Returns:
        None: PNG and SVG figures show measured error and support gaps.
    """
    from matplotlib import pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    xs = list(range(1, len(rows) + 1))
    labels = [f"{x}\nn={row['completed']:,}" for x, row in zip(xs, rows, strict=True)]
    for key, label in (("total_variation", "Total variation"), ("cdf_error", "Maximum CDF error")):
        axes[1].plot(xs, [mapping(row["quality"])[key] for row in rows], "o-", label=label)
    axes[0].plot(xs, [100 * float(str(mapping(row["quality"])["coverage"])) for row in rows], "o-")
    axes[0].set(ylabel="Distinct outcomes covered (%)", ylim=(0, 105))
    axes[1].set(ylabel="Distribution error (lower is better)", ylim=(0, 1))
    axes[1].legend()
    for axis in axes:
        axis.set(xticks=xs, xticklabels=labels, xlabel="Consecutive run → increasing sparsity")
        axis.grid(alpha=0.2)
    figure.suptitle("Outcome coverage under progressive input thinning")
    finish(
        figure,
        output,
        "sparsity-quality",
        "Nested random samples; fresh caches per run. One seed; errors need not increase monotonically.",
    )
    figure, axes = plt.subplots(2, 2, figsize=(12, 7))
    chosen = sorted({round(i * (len(rows) - 1) / 3) for i in range(4)})
    values = sorted(reference, key=float)
    population = sum(reference.values())
    expected = [reference[key] / population for key in values]
    for axis, index in zip(axes.flat, chosen, strict=False):
        row = rows[index]
        counts = mapping(row["received_counts"])
        received = [int(str(counts.get(key, 0))) / int(str(row["completed"])) for key in values]
        axis.hist(
            [float(key) for key in values],
            bins=32,
            weights=received,
            color="#2563eb",
            alpha=0.7,
            label="Received frequency",
        )
        axis.hist(
            [float(key) for key in values],
            bins=32,
            weights=expected,
            histtype="step",
            linewidth=2,
            color="#d97706",
            label="Exact reference",
        )
        axis.set(
            title=f"Run {index + 1}: {row['completed']:,} inputs",
            xlabel="Emitted value",
            ylabel="Probability per histogram bin",
            ylim=(0, None),
        )
        axis.legend()
    for axis in list(axes.flat)[len(chosen) :]:
        axis.set_visible(False)
    figure.suptitle("Received outcome distribution as coverage falls")
    finish(
        figure,
        output,
        "sparsity-distributions",
        "Discrete normal-quantile outcomes. Each panel uses its own probability scale; 32 equal-width histogram bins.",
    )


def run() -> int:
    """
    Execute consecutive sparse samples and retain reproducible measurements.

    Returns:
        int: Zero for a completed study, one for failure, or 124 at the deadline.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chart", type=Path, default=Path("benchmark-chart"))
    parser.add_argument("--output", type=Path, default=ROOT / "reports/benchmarks/sparsity")
    parser.add_argument("--count", type=int, default=32768, help="initial distinct-input count")
    parser.add_argument("--retain", type=float, default=0.25, help="fraction retained per run")
    parser.add_argument("--levels", type=int, default=8)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540.0)
    parser.add_argument("--helm", default="helm")
    args = parser.parse_args()
    if not math.isfinite(args.time_limit) or not 0 < args.time_limit <= 540:
        parser.error("time limit must be positive and at most 540 seconds per run")
    try:
        stages = samples(args.count, args.retain, args.levels, args.seed)
    except ValueError as exc:
        parser.error(str(exc))
    spec = mapping(json.loads((args.chart / "benchmark.json").read_text()))
    bins = int(str(spec["output_bins"]))
    complexity = int(str(spec["input_complexity"]))
    if args.count > 2**complexity:
        parser.error("initial count exceeds the finite input domain")
    reference = Counter(
        str(float(expected_output({f"input{bit:03d}": bool(index & (1 << bit)) for bit in range(complexity)}, spec)))
        for index in range(bins)
    )
    topology_reference: Counter[str] = Counter()
    if "topology" in spec:
        roles = list(mapping(mapping(spec["topology"])["roles"]).values())
        for assignment in range(2 ** len(roles)):
            values: dict[str, object] = {str(path): bool(assignment & (1 << bit)) for bit, path in enumerate(roles)}
            topology_reference[configuration_key(expected_topology(values, spec))] += 1
    helm = shutil.which(args.helm)
    if helm is None:
        parser.error("Helm is required")
    args.output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "helm": subprocess.check_output([helm, "version", "--short"], text=True).strip(),
            "seed": args.seed,
            "count": args.count,
            "retain": args.retain,
            "levels": args.levels,
            "time_limit_seconds": args.time_limit,
            "chart_sha256": source_digest(args.chart),
            "code_sha256": code_digest(),
            "platform": platform.platform(),
            "reference": dict(reference),
            "topology_reference": dict(topology_reference),
            "method": "nested uniform thinning of input prefix; fresh caches; discrete reference",
        },
        "runs": rows,
    }
    for stage, indices in enumerate(stages, 1):
        print(f"Run {stage}: {len(indices):,} inputs", flush=True)
        result = execute_worker(
            Job(
                str(args.chart.resolve()),
                indices,
                args.seed,
                8,
                True,
                helm,
                time.perf_counter() + args.time_limit,
            )
        )
        rows.append(result)
        result["stage"] = stage
        result["retained_fraction"] = len(indices) / args.count
        if result["status"] == "passed":
            counts = {key: int(str(value)) for key, value in mapping(result["received_counts"]).items()}
            if sum(counts.values()) != result["completed"] or result["oracle_checks"] != result["completed"]:
                raise AssertionError("incomplete output assertion ledger")
            result["quality"] = quality(counts, dict(reference))
            if topology_reference:
                result["topology_quality"] = quality(
                    {key: int(str(value)) for key, value in mapping(result["topology_counts"]).items()},
                    dict(topology_reference),
                    ordered=False,
                )
        temporary = args.output / "results.tmp"
        temporary.write_text(json.dumps(document, indent=2) + "\n")
        temporary.replace(args.output / "results.json")
        if result["status"] != "passed":
            print(
                f"Stopped: {result['status']}; {result['completed']} completed; {result['error']}",
                flush=True,
            )
            return 124 if result["status"] == "time-limit" else 1
        print(f"  {result['quality']}; {result['rendered']} renders", flush=True)
    plot(args.output, rows, dict(reference))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
