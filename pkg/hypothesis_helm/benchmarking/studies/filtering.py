"""
Measure filtering runtime as finite input size and gate depth change.
"""

import argparse
import csv
import json
import random
import statistics
import time
from pathlib import Path

from hypothesis_helm.benchmarking.charts.faults import Fault, write_faults
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.reporting.variation import bands, repeated_line
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.runner import check_chart
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import parse_time_limit
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.contracts import mapping, sequence

METHODS = ("baseline", "sample-random", "filter", "filter-adaptive")


def measure(chart: Chart, method: str, seed: int, limit: float, helm: str) -> tuple[dict[str, object], dict[str, object]]:
    """
    Run the real testing engine with the same options as each public flag.

    Args:
        chart (Chart): Prepared finite chart shared by the paired runs.
        method (str): Baseline, percentage selection, ordinary or aggressive filtering.
        seed (int): Paired traversal and selection seed.
        limit (float): Execution ceiling excluding planning, matching normal chart testing.
        helm (str): Helm executable.

    Returns:
        tuple[dict[str, object], dict[str, object]]: Phase measurements and the complete native execution report.
    """
    if method not in METHODS:
        raise ValueError(f"unknown filtering method: {method}")
    filtered = method in {"filter", "filter-adaptive"}
    started = time.perf_counter()
    report = check_chart(
        chart,
        permutations=2,
        random_seed=seed,
        sampling=Sampling(70 if method == "sample-random" else 100, aggressive=method == "filter-adaptive"),
        trim_topology=2 if filtered else 0,
        expand_failures=filtered,
        filter_rejections=filtered,
        time_limit=limit,
        helm=helm,
    )
    wall = time.perf_counter() - started
    sampling = mapping(report.get("sampling", {}))
    aggressive = mapping(sampling.get("aggressive", {}))
    analysis = mapping(aggressive.get("analysis", {}))
    planning = float(str(report["planning_seconds"]))
    execution = float(str(report["execution_seconds"]))
    analysis_seconds = float(str(analysis.get("analysis_seconds", 0)))
    row = {
        "strategy": method,
        "seed": seed,
        "status": report["status"],
        "wall_seconds": wall,
        "planning_seconds": planning,
        "complexity_seconds": analysis_seconds,
        "other_planning_seconds": max(0, planning - analysis_seconds),
        "execution_seconds": execution,
        "other_seconds": max(0, wall - planning - execution),
        "planned": report["planned_iterations"],
        "completed": report["completed_iterations"],
        "remaining": report["remaining_iterations"],
        "regions": mapping(report.get("topology", {})).get("region_count"),
        "sample_minimum": sampling.get("minimum"),
        "sample_minimum_fields": sampling.get("minimum_fields"),
        "profile_match": aggressive.get("match"),
        "fallback": aggressive.get("fallback"),
        "maximum_score": mapping(analysis.get("features") or {}).get("maximum_score"),
    }
    return row, report


def save(output: Path, document: dict[str, object]) -> None:
    """
    Preserve each completed observation before starting another real test run.

    Args:
        output (Path): Study artifact directory.
        document (dict[str, object]): Metadata and completed measurements.

    Returns:
        None: JSON and CSV include incomplete execution counts without extrapolation.
    """
    (output / "results.json").write_text(json.dumps(document, indent=2) + "\n")
    rows = [mapping(row) for row in sequence(document["rows"])]
    if rows:
        with (output / "results.csv").open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Compare runtime and retained work without treating timed-out runs as completed timings.

    Args:
        output (Path): Study output directory.
        document (dict[str, object]): Recorded real-engine phase timings and statuses.

    Returns:
        None: Runtime, planning and phase plots accompany a readable numerical table.
    """
    from hypothesis_helm.benchmarking.reporting.labels import current_labels

    document = mapping(current_labels(document))

    from matplotlib import pyplot as plt

    rows = [mapping(row) for row in sequence(document["rows"])]
    depths = sorted({int(str(row["gate_depth"])) for row in rows})
    colors = dict(zip(METHODS, ("#64748b", "#d97706", "#2563eb", "#059669"), strict=True))
    for metric, name, ylabel in (
        ("wall_seconds", "filtering-runtime", "Total engine time (seconds)"),
        ("planning_seconds", "filtering-planning", "Planning time (seconds)"),
        ("completed", "filtering-completed", "Completed configurations"),
    ):
        figure, axes = plt.subplots(1, len(depths), figsize=(5 * len(depths), 5), squeeze=False, sharey=True)
        for axis, depth in zip(axes[0], depths, strict=True):
            for method in METHODS:
                selected = [row for row in rows if row["strategy"] == method and row["gate_depth"] == depth]
                sizes = sorted({int(str(row["valid_inputs"])) for row in selected})
                batches = [[row for row in selected if row["valid_inputs"] == size] for size in sizes]
                means = [statistics.mean(float(str(row[metric])) for row in batch) for batch in batches]
                complete = [all(row["status"] == "passed" for row in batch) for batch in batches]
                repeated_line(
                    axis,
                    sizes,
                    [[float(str(row[metric])) for row in batch] if done else [] for batch, done in zip(batches, complete, strict=True)],
                    method,
                    colors[method],
                )
                axis.scatter(
                    [size for size, done in zip(sizes, complete, strict=True) if not done],
                    [mean for mean, done in zip(means, complete, strict=True) if not done],
                    marker="x",
                    color=colors[method],
                )
                if method == "filter-adaptive":
                    fallback = [any(row.get("fallback") for row in batch) for batch in batches]
                    if any(fallback):
                        axis.scatter(
                            [size for size, skipped in zip(sizes, fallback, strict=True) if skipped],
                            [mean for mean, skipped in zip(means, fallback, strict=True) if skipped],
                            marker="s",
                            facecolors="none",
                            edgecolors=colors[method],
                            s=70,
                            label="adaptive: fallback",
                        )
            axis.set(title=f"Gate depth {depth}", xlabel="Schema-valid input configurations", ylabel=ylabel)
            axis.set_xscale("log", base=2)
            ticks = sorted({int(str(row["valid_inputs"])) for row in rows})
            axis.set_xticks(ticks, [str(size) for size in ticks])
            axis.grid(alpha=0.2)
            axis.legend(fontsize=8)
        finish(figure, output, name, "X = incomplete run; hollow square = extra sampling disabled by fallback.")
    largest = max(int(str(row["valid_inputs"])) for row in rows)
    figure, axis = plt.subplots(figsize=(12, 5))
    totals: list[list[float]] = []
    labels: list[str] = []
    analysis: list[float] = []
    planning: list[float] = []
    execution: list[float] = []
    other: list[float] = []
    for depth in depths:
        for method in METHODS:
            batch = [row for row in rows if row["strategy"] == method and row["gate_depth"] == depth and row["valid_inputs"] == largest]
            totals.append([float(str(row["wall_seconds"])) for row in batch] if all(row["status"] == "passed" for row in batch) else [])
            labels.append(f"depth {depth}\n{method}")
            for target, key in (
                (analysis, "complexity_seconds"),
                (planning, "other_planning_seconds"),
                (execution, "execution_seconds"),
                (other, "other_seconds"),
            ):
                target.append(statistics.mean(float(str(row[key])) for row in batch))
    bottom = [0.0] * len(labels)
    for amounts, label in (
        (analysis, "Maximum-complexity analysis"),
        (planning, "Other planning and selection"),
        (execution, "Helm and property execution"),
        (other, "Other engine overhead"),
    ):
        axis.bar(range(len(labels)), amounts, bottom=bottom, label=label)
        bottom = [old + added for old, added in zip(bottom, amounts, strict=True)]
    bands(
        axis,
        list(range(len(labels))),
        bottom,
        [statistics.stdev(batch) if len(batch) > 1 else float("nan") for batch in totals],
        [len(batch) for batch in totals],
        "#334155",
    )
    axis.set_xticks(range(len(labels)), labels, rotation=35, ha="right", fontsize=8)
    axis.set(ylabel="Measured seconds", title=f"Phase costs at {largest} possible inputs")
    axis.legend(fontsize=8)
    finish(
        figure,
        output,
        "filtering-phases",
        "Planning includes candidate generation. Chart generation and dependency preparation are excluded.",
    )
    metadata = mapping(document["metadata"])
    lines = [
        "# Filtering load test",
        "",
        "[Theory and conditions](../../docs/adaptive-filtering/README.md#computational-cost)",
        "",
        "A gate is a template `if` condition. Depth counts nested conditions required to reach the innermost branch.",
        "",
        "![Total runtime](filtering-runtime.png)",
        "",
        "![Planning runtime](filtering-planning.png)",
        "",
        "![Completed work](filtering-completed.png)",
        "",
        "![Phase costs](filtering-phases.png)",
        "",
        f"{metadata['repeats']} paired repeats per chart and method; execution ceiling {metadata['time_limit_seconds']} seconds per run.",
        "Dark bands show mean ±1 sample SD; light bands show ±2 SD across paired repeats, not confidence intervals. "
        "Method order is seeded and shuffled for each repeat.",
        "Input count is the full Boolean domain (2^fields), not the interaction-strength flag; strength stays at two.",
        "The small finite domains are fully enumerated before filtering.",
        "Gate depth changes branch rarity, fan-in and equivalent-output regions.",
        "",
        "The engine runs real Helm checks with no shared outcome cache. Each invocation creates its own render-hash cache.",
        "OS and Helm executable caches can remain warm. Chart generation, CLI startup and dependency preparation are excluded.",
        "Planning and analysis are included in total engine time. The execution ceiling does not cap planning.",
        "",
        "`sample-random` retains 70% subject to its normal 128-case floor. `filter` uses topology depth two and failure expansion.",
        "`filter-adaptive` adds its measured floors; unmatched charts keep ordinary filtering. All methods use the same traversal seed.",
        "The chart's injected markers change topology but are not asserted as lint failures in this successful-render load test.",
        "Failure expansion is enabled for both filter presets; workloads with actual failing properties may expand toward the full plan.",
        "",
        "| Fields | Depth | Repeat | Method | Selected | Completed | Total s | Planning s | Complexity s | Execution s | Status |",
        "| ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['input_fields']} | {row['gate_depth']} | {row['repeat']} | {row['strategy']} | {row['planned']} | "
            f"{row['completed']} | {float(str(row['wall_seconds'])):.3f} | {float(str(row['planning_seconds'])):.3f} | "
            f"{float(str(row['complexity_seconds'])):.3f} | {float(str(row['execution_seconds'])):.3f} | {row['status']} |"
        )
    lines += ["", "[Raw timings and fallback decisions](results.csv) · [Full measurements](results.json) · [Chart recipes](cases/)", ""]
    (output / "README.md").write_text(with_contents("\n".join(lines)))


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Run paired real-engine measurements over a reusable parameterized chart.

    Args:
        argv (list[str] | None): Explicit CLI arguments.
        workspace (FixtureWorkspace | None): Owner of the single generated chart.

    Returns:
        int: Zero after successful or time-limited runs, one for unexpected chart failures.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/filtering"))
    parser.add_argument("--inputs", type=int, nargs="+", default=[6, 7, 8, 9])
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 3, 5])
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--fault-seed", type=int, default=2027)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "results.json").read_text())))
        return 0
    if (
        not args.inputs
        or not all(2 <= count <= 12 for count in args.inputs)
        or not all(1 <= depth <= min(args.inputs) for depth in args.depths)
    ):
        parser.error("inputs must be 2..12 and depths must fit every input count")
    if args.repeats < 1 or not 0 < args.time_limit <= 540:
        parser.error("repeats must be positive and the execution ceiling must be in (0, 9m]")
    if (args.output / "results.json").exists():
        parser.error("choose a new output directory")
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "reports").mkdir()
    rows: list[dict[str, object]] = []
    document: dict[str, object] = {
        "metadata": {
            "code_sha256": code_digest(),
            "helm": Processes().run([args.helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
            "repeats": args.repeats,
            "seed": args.seed,
            "fault_seed": args.fault_seed,
            "time_limit_seconds": args.time_limit,
            "time_limit_scope": "execution per method per repeat",
            "inputs": args.inputs,
            "depths": args.depths,
            "status": "running",
        },
        "rows": rows,
    }
    failed = False
    for inputs in args.inputs:
        for depth in args.depths:
            name = f"fields-{inputs}-depth-{depth}"
            logical = args.output / "charts" / name
            generate(logical, input_complexity=inputs, output_bins=2, workspace=workspace)
            chart = Chart.load(chart_path(logical, workspace=workspace))
            rng = random.Random(args.fault_seed)
            faults = [
                Fault(f"bug{index}", dict.fromkeys(rng.sample(list(chart.defaults), depth), True)) for index in range(max(2, inputs // 2))
            ]
            write_faults(logical, faults, workspace=workspace, symbolic=True)
            for repeat in range(args.repeats):
                methods = list(METHODS)
                random.Random(f"{args.seed}:{inputs}:{depth}:{repeat}").shuffle(methods)
                with BenchmarkProgress(f"{name}, repeat {repeat + 1}: filtering methods") as display:
                    for order, method in enumerate(display.track(methods)):
                        row, report = measure(chart, method, args.seed + repeat, args.time_limit, args.helm)
                        rows.append(
                            {
                                "case": name,
                                "input_fields": inputs,
                                "valid_inputs": 2**inputs,
                                "gate_depth": depth,
                                "repeat": repeat,
                                "order": order,
                                **row,
                            }
                        )
                        (args.output / "reports" / f"{name}-{repeat}-{method}.json").write_text(json.dumps(report, indent=2) + "\n")
                        save(args.output, document)
                        print(
                            f"{name} repeat={repeat} {method}: {row['wall_seconds']:.3f}s, "
                            f"{row['completed']}/{row['planned']} {row['status']}",
                            flush=True,
                        )
                        failed |= row["status"] not in {"passed", "time-limit"}
    mapping(document["metadata"])["status"] = "complete"
    save(args.output, document)
    plot(args.output, document)
    return int(failed)
