"""
Calibrate topology-aware sample floors against independently checked synthetic defects.
"""

import argparse
import csv
import hashlib
import itertools
import json
import math
import random
import statistics
import time
from pathlib import Path

from attrs import asdict

from hypothesis_helm.benchmarking.charts.faults import Fault, write_faults
from hypothesis_helm.benchmarking.charts.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.charts.generator import generate
from hypothesis_helm.benchmarking.charts.shape import fault_outputs, reshape_faults
from hypothesis_helm.benchmarking.execution.provenance import code_digest
from hypothesis_helm.benchmarking.reporting.plots import finish
from hypothesis_helm.benchmarking.reporting.progress import BenchmarkProgress
from hypothesis_helm.benchmarking.reporting.variation import bands
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.passes.sampling import profile
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.execution.aggressive import CALIBRATION_VERSION, changed_fields, descriptor
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.reporting.contents import with_contents
from hypothesis_helm.schemas.combinations import plan_interactions, trim_values
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence
from hypothesis_helm.schemas.model import ValuesModel


def verify_sweep(document: dict[str, object]) -> None:
    """
    Require every declared breadth/depth sweep cell exactly once.

    Args:
        document (dict[str, object]): Completed calibration with recorded sweep metadata.

    Returns:
        None: Missing, duplicated or mislabeled measurements raise ValueError.
    """
    sweep = mapping(mapping(document["metadata"])["sweep"])
    expected = {
        f"fields-{inputs}-depth-{depth}-placement-{placement}-breadth-{breadth}-output-depth-{output_depth}": (breadth, output_depth)
        for inputs, depth, placement, breadth, output_depth in itertools.product(
            sequence(sweep["inputs"]),
            sequence(sweep["gate_depths"]),
            range(int(str(sweep["placements"]))),
            sequence(sweep["resource_copies"]),
            sequence(sweep["list_wrappers"]),
        )
    }
    cells = [mapping(cell) for cell in sequence(document["profiles"])]
    if document.get("status") != "complete" or len(cells) != len(expected) or {str(cell["case"]) for cell in cells} != expected.keys():
        raise ValueError("calibration must contain every declared sweep cell exactly once")
    for cell in cells:
        shape = mapping(cell["output_shape"])
        if (shape["copies"], shape["wrappers"]) != expected[str(cell["case"])]:
            raise ValueError("calibration output shape does not match its declared sweep cell")


def study(chart: Chart, faults: list[Fault], trials: int, seed: int, helm: str, deadline: float) -> dict[str, object]:
    """
    Render one finite population and measure seeded selection at increasing sample sizes.

    Args:
        chart (Chart): Current shared fixture with known defects.
        faults (list[Fault]): Independent defect activation oracle.
        trials (int): Number of calibration seeds at each sample size.
        seed (int): First repeatable sampling seed.
        helm (str): Real Helm executable.
        deadline (float): Shared monotonic study deadline.

    Returns:
        dict[str, object]: Measured profile, sample floor, field floor and recall observations.
    """
    analysis = profile(chart)
    if analysis["status"] != "supported":
        raise ValueError(f"calibration requires supported complexity: {analysis}")
    plan = plan_interactions(ValuesModel.from_schema(chart.schema), 2, max_cases=4096, max_candidates=4096, exhaustive_threshold=10000)
    baseline = configuration_key(chart.defaults)
    values = [value for value in plan.values if configuration_key(value) != baseline]
    observed: dict[str, set[str]] = {}
    for value in [chart.defaults, *values]:
        if time.monotonic() >= deadline:
            raise TimeLimitReached()
        resources = render(chart, value, helm=helm, timeout=min(30, max(0.001, deadline - time.monotonic())), stream=False)
        outputs = list(fault_outputs(resources))
        if not outputs:
            raise AssertionError("Helm output contains no injected-fault ConfigMap")
        actual = outputs[0]
        expected = {fault.name: "incorrect" if fault.active(value) else "expected" for fault in faults}
        if any(actual != expected for actual in outputs):
            raise AssertionError("Helm fault output disagrees with the independent trigger oracle")
        observed[configuration_key(value)] = {name for name, status in actual.items() if status == "incorrect"}
    memberships: dict[str, str] = {}
    filtered, topology = trim_topology(chart.path, chart.defaults, values, values, 2, seed, memberships=memberships)
    groups: dict[str, list[dict[str, object]]] = {}
    for value in values:
        groups.setdefault(memberships[configuration_key(value)], []).append(value)
    counts = sorted(
        {
            1,
            len(groups),
            math.ceil(len(filtered) * 0.7),
            len(filtered),
            *(min(len(filtered), 2**index) for index in range(math.ceil(math.log2(max(1, len(filtered)))) + 1)),
        }
    )
    counts = [count for count in counts if count <= len(filtered)]
    samples: dict[int, list[tuple[float, int]]] = {count: [] for count in counts}
    for trial_seed in range(seed, seed + trials):
        if time.monotonic() >= deadline:
            raise TimeLimitReached()
        # This is exactly the ordinary topology filter, reusing its already compiled groups.
        retained = {configuration_key(value) for members in groups.values() for value in trim_values(members, 2, trial_seed)}
        eligible = [value for value in values if configuration_key(value) in retained]
        protected: set[str] = set()
        represented: set[str] = set()
        for value in eligible:
            identity = configuration_key(value)
            region = memberships[identity]
            if region not in represented:
                protected.add(identity)
                represented.add(region)
        for count in counts:
            selected, evidence = Sampling(1e-12, count).select(
                eligible,
                configuration_key,
                trial_seed,
                protected=protected,
                fields=lambda value: changed_fields(chart.defaults, value),
            )
            found = observed[baseline] | set().union(*(observed[configuration_key(value)] for value in selected))
            samples[count].append((len(found) / len(faults), int(str(evidence["selected_fields"]))))
    rows: list[dict[str, object]] = []
    for count, observations in samples.items():
        recall = sorted(value[0] for value in observations)
        rows.append(
            {
                "sample_size": max(count, len(groups)),
                "eligible": len(filtered),
                "protected": len(groups),
                "mean_bug_recall": statistics.mean(recall),
                "stddev_bug_recall": statistics.stdev(recall) if len(recall) > 1 else None,
                "p05_bug_recall": recall[int(0.05 * (trials - 1))],
                "p95_bug_recall": recall[int(0.95 * (trials - 1))],
                "target_successes": sum(value >= 0.96 for value in recall),
                "trials": trials,
                "minimum_fields": min(value[1] for value in observations),
            }
        )
    passing = [row for row in rows if int(str(row["target_successes"])) / trials >= 0.95]
    if not passing:
        raise ValueError("ordinary filtering did not reach the calibration target; no sampling floor can be published")
    best = min(passing, key=lambda row: int(str(row["sample_size"])))
    return {
        "descriptor": descriptor(analysis, topology, {"strength": 2, "trim": 0, "trim_topology": 2}),
        "minimum_cases": best["sample_size"],
        "minimum_fields": best["minimum_fields"],
        "evidence": {
            "trials": trials,
            "seed_start": seed,
            "target_recall": 0.96,
            "target_success_fraction": 0.95,
            "target_successes": best["target_successes"],
            "mean_bug_recall": best["mean_bug_recall"],
            "known_bugs": len(faults),
            "reference_renders": len(observed),
            "independent_validation": False,
        },
        "analysis": analysis,
        "rows": rows,
        "faults": [asdict(fault) for fault in faults],
        "reference": {
            "defaults": chart.defaults,
            "baseline_bugs": sorted(observed[baseline]),
            "cases": [
                {"values": value, "bugs": sorted(observed[configuration_key(value)]), "region": memberships[configuration_key(value)]}
                for value in values
            ],
        },
    }


def plot(output: Path, document: dict[str, object]) -> None:
    """
    Publish sample floors and recall variation with explicit calibration-only scope.

    Args:
        output (Path): Study output directory.
        document (dict[str, object]): Completed calibration evidence.

    Returns:
        None: Matplotlib plots, CSV and a concise report are written.
    """
    from matplotlib import pyplot as plt

    figure, axes = plt.subplots(1, 2, figsize=(12, 5))
    table: list[dict[str, object]] = []
    scores = sorted(
        {int(str(mapping(mapping(mapping(cell)["descriptor"])["features"])["maximum_score"])) for cell in sequence(document["profiles"])}
    )
    lines = [
        "# Aggressive sampling calibration",
        "",
        "Generated-chart calibration only. No held-out validation or arbitrary-chart recall guarantee.",
        "",
        "Every input was rendered with Helm and compared with an independent defect-trigger oracle.",
        "Floors include protected symbolic regions. Field coverage counts changed paths separately from configurations.",
        f"Measured maximum output scores: **{', '.join(map(str, scores))}**. Other scores are outside this calibration's range.",
        "[Comparison matrix and graphs](MATRIX.md) · [Proof obligations and tests](../../docs/adaptive-filtering/TESTS.md)",
        "",
        "![Measured sample floors and recall](calibration.png)",
        "",
        "| Case | Max complexity | Gate depth | Fields | Eligible | Protected | Case floor | Field floor | Seeds reaching 96% bug recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for index, entry in enumerate(sequence(document["profiles"])):
        cell = mapping(entry)
        features = mapping(mapping(cell["descriptor"])["features"])
        evidence = mapping(cell["evidence"])
        rows = [mapping(row) for row in sequence(cell["rows"])]
        label = str(cell["case"])
        axes[0].scatter(features["maximum_score"], cell["minimum_cases"], label=label)
        xs = [float(str(row["sample_size"])) for row in rows]
        centers = [100 * float(str(row["mean_bug_recall"])) for row in rows]
        color = f"C{index % 10}"
        axes[1].plot(xs, centers, ".-", color=color, alpha=0.6)
        bands(
            axes[1],
            xs,
            centers,
            [100 * float(str(row["stddev_bug_recall"])) if row.get("stddev_bug_recall") is not None else float("nan") for row in rows],
            [int(str(row["trials"])) for row in rows],
            color,
            upper=100,
        )
        for row in rows:
            table.append({"case": label, **features, **row})
        lines.append(
            f"| {label} | {features['maximum_score']} | {features['gate_depth']} | {features['input_fields']} | "
            f"{rows[0]['eligible']} | {rows[0]['protected']} | {cell['minimum_cases']} | {cell['minimum_fields']} | "
            f"{evidence['target_successes']}/{evidence['trials']} |"
        )
    axes[0].set(xlabel="Maximum manifest breadth × depth", ylabel="Measured minimum configurations")
    axes[1].set(xlabel="Selected configurations (including protected regions)", ylabel="Mean distinct bugs found (%)", ylim=(0, 105))
    for axis in axes:
        axis.grid(alpha=0.2)
    finish(figure, output, "calibration", "Calibration seeds only; structural representatives are preserved; no claim about unseen charts.")
    with (output / "results.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    from hypothesis_helm.benchmarking.reporting.complexity_sweep import plot as plot_sweep

    if plot_sweep(output, document):
        lines += [
            "",
            "## Breadth and depth sweep",
            "",
            "![Sample floors across output breadth and depth](complexity-sweep.png)",
            "",
            "Sibling ConfigMap copies vary breadth; nested List envelopes vary output depth. Axis labels are measured tree dimensions.",
            "Each panel holds input count and defect-trigger depth fixed. "
            "Every shape uses the same paired defect placements and sampling seeds.",
            "Copies preserve the same defect triggers: a flat surface means "
            "increasing output size alone did not increase the measured floor.",
            "Cells show mean ±1 sample standard deviation across placements, not a confidence interval or a recall guarantee.",
            "[Sweep measurements](complexity-sweep.csv)",
            "",
        ]
    lines += [
        "",
        "Complete recall here can follow from preserving every symbolic output region. It does not validate random sampling alone.",
        "",
        "[Calibration JSON](calibration.json) · [Measurements](results.csv)",
        "",
    ]
    (output / "README.md").write_text(with_contents("\n".join(lines)))


def main(argv: list[str] | None = None, *, workspace: FixtureWorkspace | None = None) -> int:
    """
    Reuse one chart while varying input size, gate depth and seeded defect placement.

    Args:
        argv (list[str] | None): Explicit CLI arguments.
        workspace (FixtureWorkspace | None): Owner of the shared benchmark chart.

    Returns:
        int: Zero for completed calibration, one when the execution budget expires.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cache/benchmarks/calibration"))
    parser.add_argument("--inputs", type=int, nargs="+", default=[6, 7, 8])
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--breadths", type=int, nargs="+", default=[1], help="sibling copies of the fault resource (1..16)")
    parser.add_argument("--output-depths", type=int, nargs="+", default=[0], help="nested List envelopes around fault resources (0..5)")
    parser.add_argument("--placements", type=int, default=2)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "calibration.json").read_text())))
        from hypothesis_helm.benchmarking.analysis.calibration_matrix import plot as plot_matrix

        matrix = mapping(json.loads((args.output / "matrix.json").read_text()))
        plot_matrix(args.output, [mapping(row) for row in sequence(matrix["rows"])], mapping(matrix["policy"]))
        return 0
    if not all(2 <= count <= 10 for count in args.inputs) or not all(1 <= depth <= min(args.inputs) for depth in args.depths):
        parser.error("inputs must be 2..10 and depths must fit every input count")
    if not all(1 <= value <= 16 for value in args.breadths) or not all(0 <= value <= 5 for value in args.output_depths):
        parser.error("breadths must be 1..16 and output-depths must be 0..5")
    for values in (args.inputs, args.depths, args.breadths, args.output_depths):
        if len(set(values)) != len(values):
            parser.error("sweep axes must not contain duplicate values")
    if args.trials < 1 or args.placements < 1 or not 0 < args.time_limit <= 540:
        parser.error("trials and placements must be positive; time limit must be at most 9m")
    if (args.output / "calibration.json").exists():
        parser.error("choose a new output directory")
    if workspace is None:
        with FixtureWorkspace() as owned:
            return main(argv, workspace=owned)
    args.output.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    document: dict[str, object] = {
        "version": CALIBRATION_VERSION,
        "status": "complete",
        "profiles": [],
        "independent_validation": False,
        "helm": Processes().run([args.helm, "version", "--short"], capture_output=True, check=True, timeout=30).stdout.strip(),
    }
    profiles: list[dict[str, object]] = []
    document["metadata"] = {
        "code_sha256": code_digest(),
        "helm": document["helm"],
        "time_limit_seconds": args.time_limit,
        "sweep": {
            "inputs": args.inputs,
            "gate_depths": args.depths,
            "resource_copies": args.breadths,
            "list_wrappers": args.output_depths,
            "placements": args.placements,
            "trials": args.trials,
            "seed": args.seed,
        },
    }
    try:
        with execution_timer(args.time_limit):
            cases = itertools.product(args.inputs, args.depths, range(args.placements), args.breadths, args.output_depths)
            total = len(args.inputs) * len(args.depths) * args.placements * len(args.breadths) * len(args.output_depths)
            with BenchmarkProgress("Calibration: chart shapes") as display:
                for inputs, depth, placement, breadth, output_depth in display.track(cases, total=total):
                    name = f"fields-{inputs}-depth-{depth}-placement-{placement}-breadth-{breadth}-output-depth-{output_depth}"
                    logical = args.output / "charts" / name
                    generate(logical, input_complexity=inputs, output_bins=2, workspace=workspace)
                    chart = Chart.load(chart_path(logical, workspace=workspace))
                    fields = list(chart.defaults)
                    rng = random.Random(args.seed + placement)
                    faults = [Fault(f"bug{index}", dict.fromkeys(rng.sample(fields, depth), True)) for index in range(max(2, inputs // 2))]
                    write_faults(logical, faults, workspace=workspace, symbolic=True)
                    reshape_faults(logical, breadth, output_depth, workspace=workspace)
                    result = study(chart, faults, args.trials, args.seed, args.helm, started + args.time_limit)
                    profiles.append({"case": name, "output_shape": {"copies": breadth, "wrappers": output_depth}, **result})
                    print(f"Calibrated {name}: cases >= {result['minimum_cases']}, fields >= {result['minimum_fields']}", flush=True)
    except TimeLimitReached:
        document["status"] = "time-limit"
    document["profiles"] = profiles
    document["elapsed_seconds"] = time.monotonic() - started
    document["id"] = hashlib.sha256(configuration_key({"profiles": profiles}).encode()).hexdigest()
    (args.output / "calibration.json").write_text(json.dumps(document, indent=2) + "\n")
    if document["status"] != "complete":
        return 1
    from hypothesis_helm.benchmarking.analysis.calibration_matrix import evaluate

    verify_sweep(document)
    evaluate(args.output, document)
    plot(args.output, document)
    return 0
