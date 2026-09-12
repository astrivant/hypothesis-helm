"""
Measure seeded Helm defect discovery against --permutations interaction strength.
"""

import argparse
import itertools
import json
import random
import time
from pathlib import Path

from hypothesis_helm.charts.runner import Chart, render
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.combinations import plan_interactions
from hypothesis_helm.schemas.contracts import mapping, sequence

from scripts.benchmark_helm import ROOT, code_digest
from scripts.benchmarking.faults import Fault as Fault
from scripts.benchmarking.faults import write_faults
from scripts.benchmarking.plots import finish
from scripts.benchmarking.workload import source_digest
from scripts.generate_benchmark_chart import generate


def faults(complexity: int, maximum: int, per_order: int, seed: int) -> list[Fault]:
    """
    Select unique fault triggers without inspecting coverage plans.

    Args:
        complexity (int): Number of Boolean chart factors.
        maximum (int): Largest fault interaction order.
        per_order (int): Number of distinct faults at each order from two upward.
        seed (int): Reproducible fixture sampling seed.

    Returns:
        list[Fault]: Uniformly sampled field-subset and Boolean-pattern triggers per order.
    """
    rng = random.Random(seed)
    result: list[Fault] = []
    for order in range(2, maximum + 1):
        subsets = list(itertools.combinations(range(complexity), order))
        for encoded in rng.sample(range(len(subsets) * 2**order), per_order):
            subset, pattern = divmod(encoded, 2**order)
            result.append(
                Fault(
                    f"bug{len(result):03d}",
                    {
                        f"input{bit:03d}": bool(pattern & (1 << position))
                        for position, bit in enumerate(subsets[subset])
                    },
                )
            )
    return result


def fixture(path: Path, complexity: int, defects: list[Fault]) -> Chart:
    """
    Add conditional semantic defects to a generated Helm chart.

    Args:
        path (Path): New chart directory.
        complexity (int): Number of independent Boolean schema factors.
        defects (list[Fault]): Seeded triggers for incorrect ConfigMap fields.

    Returns:
        Chart: Renderable fixture whose contract requires every field to equal expected.
    """
    generate(path, input_complexity=complexity)
    write_faults(path, defects)
    return Chart.load(path)


def plot(output: Path, rows: list[dict[str, object]], defects: list[Fault]) -> None:
    """
    Plot actual defect discoveries and the case cost at each interaction strength.

    Args:
        output (Path): Saved figure destination.
        rows (list[dict[str, object]]): Completed strength runs and first witnesses.
        defects (list[Fault]): Fixed seeded defect population.

    Returns:
        None: Figures show per-run detection rates and completed coverage cost.
    """
    from matplotlib import pyplot as plt

    strengths = [int(str(row["strength"])) for row in rows]
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    axes[0].plot(
        strengths,
        [len(mapping(row["found"])) for row in rows],
        "o-",
        label="Defects found in this run",
    )
    axes[0].axhline(
        len(defects), linestyle="--", color="gray", label=f"{len(defects)} injected defects"
    )
    axes[0].set(ylabel="Distinct injected defects discovered", ylim=(0, len(defects) * 1.1))
    axes[0].legend()
    axes[1].plot(strengths, [row["completed"] for row in rows], "o-", color="#d97706")
    axes[1].set(ylabel="Distinct test cases executed")
    for axis in axes:
        axis.set(xlabel="--permutations (interaction strength)", xticks=strengths)
        axis.grid(alpha=0.2)
    figure.suptitle("Defect discovery as permutation strength increases")
    finish(
        figure,
        output,
        "bug-discovery",
        "Real Helm renders; fixed seeded faults. "
        "Automatic enumeration and inferred groups disabled to isolate strength.",
    )
    figure, axis = plt.subplots(figsize=(10, 4.5))
    for order in sorted({len(defect.terms) for defect in defects}):
        names = {defect.name for defect in defects if len(defect.terms) == order}
        axis.plot(
            strengths,
            [100 * len(names & mapping(row["found"]).keys()) / len(names) for row in rows],
            "o-",
            label=f"{order}-factor faults",
        )
    axis.set(
        xlabel="--permutations (interaction strength)",
        ylabel="Injected faults discovered (%)",
        xticks=strengths,
        ylim=(0, 105),
    )
    axis.legend(ncol=3)
    axis.grid(alpha=0.2)
    figure.suptitle("Detection rate by fault interaction order")
    finish(
        figure,
        output,
        "bug-order",
        "Rates describe this synthetic fault population, "
        "not a probability guarantee for defects in other charts.",
    )


def run() -> int:
    """
    Execute independently planned strengths against a fixed faulty chart.

    Returns:
        int: Zero for complete measurements or 124 for an execution-budget stop.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-complexity", type=int, default=8)
    parser.add_argument("--max-strength", type=int, default=6)
    parser.add_argument("--bug-percent", type=float, default=5)
    parser.add_argument("--chart", type=Path, help="existing chart with generated fault metadata")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=180.0)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/benchmarks/bug-density")
    args = parser.parse_args()
    if not 2 <= args.max_strength <= args.input_complexity <= 16:
        parser.error("require 2 <= max-strength <= input-complexity <= 16")
    if not 0 < args.time_limit <= 180:
        parser.error("a time limit up to 180 seconds is required")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.chart is None:
        chart_path = args.output / "chart"
        generate(
            chart_path,
            input_complexity=args.input_complexity,
            bug_percent=args.bug_percent,
            bug_seed=args.seed,
        )
    else:
        chart_path = args.chart
    chart = Chart.load(chart_path)
    spec = mapping(json.loads((chart_path / "benchmark.json").read_text()))
    bug_spec = mapping(spec.get("bugs"))
    defects = [
        Fault(
            str(mapping(value)["name"]),
            {key: bool(expected) for key, expected in mapping(mapping(value)["terms"]).items()},
        )
        for value in sequence(bug_spec.get("faults", []))
    ]
    if not defects:
        parser.error("chart must contain generated faults; increase --bug-percent")
    complexity = int(str(spec["input_complexity"]))
    if not args.max_strength <= complexity <= 16:
        parser.error("require max-strength <= chart input complexity <= 16")
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "seed": args.seed,
            "input_complexity": complexity,
            "bugs": bug_spec,
            "configuration_space_size": str(2**complexity),
            "chart_sha256": source_digest(chart.path),
            "code_sha256": code_digest(),
            "exhaustive_threshold": 0,
            "inferred_groups": False,
            "time_limit_seconds": args.time_limit,
            "method": "application interaction planner; render all cases; record injected failures",
        },
        "runs": rows,
    }
    for strength in range(1, args.max_strength + 1):
        plan = plan_interactions(chart.schema, strength, exhaustive_threshold=0)
        print(f"--permutations {strength}: {len(plan.values)} distinct cases", flush=True)
        found: dict[str, object] = {}
        completed, status = 0, "passed"
        started = time.perf_counter()
        try:
            with execution_timer(args.time_limit):
                for index, values in enumerate(plan.values):
                    resources = render(
                        chart, values, release="discovery", timeout=min(30.0, args.time_limit)
                    )
                    data = mapping(
                        next(
                            resource
                            for resource in resources
                            if mapping(resource["metadata"])["name"] == "injected-faults"
                        )["data"]
                    )
                    exposed = {defect.name for defect in defects if data[defect.name] != "expected"}
                    expected = {defect.name for defect in defects if defect.active(values)}
                    if exposed != expected:
                        raise AssertionError(
                            "fault fixture differs from independent trigger oracle"
                        )
                    for name in exposed:
                        found.setdefault(name, {"case": index + 1, "values": values})
                    completed += 1
        except TimeLimitReached:
            status = "time-limit"
        row: dict[str, object] = {
            "strength": strength,
            "planned": len(plan.values),
            "completed": completed,
            "found": found,
            "elapsed_seconds": time.perf_counter() - started,
            "status": status,
        }
        rows.append(row)
        (args.output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
        print(f"  {len(found)}/{len(defects)} defects found; {status}", flush=True)
        if status == "time-limit":
            return 124
    plot(args.output, rows, defects)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
