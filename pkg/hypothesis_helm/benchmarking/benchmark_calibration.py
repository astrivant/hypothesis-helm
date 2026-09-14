"""
Calibrate topology-aware sample floors against independently checked synthetic defects.
"""

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import time
from pathlib import Path

from attrs import asdict

from hypothesis_helm.benchmarking.benchmark_helm import code_digest
from hypothesis_helm.benchmarking.faults import Fault, write_faults
from hypothesis_helm.benchmarking.fixture import FixtureWorkspace, chart_path
from hypothesis_helm.benchmarking.generate_benchmark_chart import generate
from hypothesis_helm.benchmarking.plots import finish
from hypothesis_helm.charts.model import Chart
from hypothesis_helm.charts.rendering import render
from hypothesis_helm.compiler.passes.sampling import profile
from hypothesis_helm.compiler.passes.topology import trim_topology
from hypothesis_helm.execution.aggressive import CALIBRATION_VERSION, changed_fields, descriptor
from hypothesis_helm.execution.processes import Processes
from hypothesis_helm.execution.sampling import Sampling
from hypothesis_helm.reporting.budget import TimeLimitReached, execution_timer, parse_time_limit
from hypothesis_helm.schemas.combinations import plan_interactions, trim_values
from hypothesis_helm.schemas.contracts import configuration_key, mapping, sequence
from hypothesis_helm.schemas.model import ValuesModel


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
        actual = next(mapping(resource["data"]) for resource in resources if mapping(resource["metadata"])["name"] == "injected-faults")
        expected = {fault.name: "incorrect" if fault.active(value) else "expected" for fault in faults}
        if actual != expected:
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
        "[Comparison matrix and graphs](MATRIX.md) · [Proof obligations and tests](../../docs/aggressive-filtering/TESTS.md)",
        "",
        "![Measured sample floors and recall](calibration.png)",
        "",
        "| Case | Max complexity | Gate depth | Fields | Eligible | Protected | Case floor | Field floor | Seeds reaching 96% bug recall |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for entry in sequence(document["profiles"]):
        cell = mapping(entry)
        features = mapping(mapping(cell["descriptor"])["features"])
        evidence = mapping(cell["evidence"])
        rows = [mapping(row) for row in sequence(cell["rows"])]
        label = str(cell["case"])
        axes[0].scatter(features["maximum_score"], cell["minimum_cases"], label=label)
        axes[1].plot([row["sample_size"] for row in rows], [100 * float(str(row["mean_bug_recall"])) for row in rows], ".-", alpha=0.6)
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
    lines += [
        "",
        "Complete recall here can follow from preserving every symbolic output region. It does not validate random sampling alone.",
        "",
        "[Calibration JSON](calibration.json) · [Measurements](results.csv)",
        "",
    ]
    (output / "README.md").write_text("\n".join(lines))


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
    parser.add_argument("--output", type=Path, default=Path("benchmarks/runs/calibration"))
    parser.add_argument("--inputs", type=int, nargs="+", default=[6, 7, 8])
    parser.add_argument("--depths", type=int, nargs="+", default=[1, 2, 3, 4, 5])
    parser.add_argument("--placements", type=int, default=2)
    parser.add_argument("--trials", type=int, default=100)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--time-limit", type=parse_time_limit, default=540)
    parser.add_argument("--helm", default="helm")
    parser.add_argument("--plot-only", action="store_true")
    args = parser.parse_args(argv)
    if args.plot_only:
        plot(args.output, mapping(json.loads((args.output / "calibration.json").read_text())))
        from hypothesis_helm.benchmarking.calibration_matrix import plot as plot_matrix

        matrix = mapping(json.loads((args.output / "matrix.json").read_text()))
        plot_matrix(args.output, [mapping(row) for row in sequence(matrix["rows"])], mapping(matrix["policy"]))
        return 0
    if not all(2 <= count <= 10 for count in args.inputs) or not all(1 <= depth <= min(args.inputs) for depth in args.depths):
        parser.error("inputs must be 2..10 and depths must fit every input count")
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
    document["metadata"] = {"code_sha256": code_digest(), "helm": document["helm"], "time_limit_seconds": args.time_limit}
    try:
        with execution_timer(args.time_limit):
            for inputs in args.inputs:
                for depth in args.depths:
                    for placement in range(args.placements):
                        name = f"fields-{inputs}-depth-{depth}-placement-{placement}"
                        logical = args.output / "charts" / name
                        generate(logical, input_complexity=inputs, output_bins=2, workspace=workspace)
                        chart = Chart.load(chart_path(logical, workspace=workspace))
                        fields = list(chart.defaults)
                        rng = random.Random(args.seed + placement)
                        faults = [
                            Fault(f"bug{index}", dict.fromkeys(rng.sample(fields, depth), True)) for index in range(max(2, inputs // 2))
                        ]
                        write_faults(logical, faults, workspace=workspace, symbolic=True)
                        result = study(chart, faults, args.trials, args.seed, args.helm, started + args.time_limit)
                        profiles.append({"case": name, **result})
                        print(f"Calibrated {name}: cases >= {result['minimum_cases']}, fields >= {result['minimum_fields']}", flush=True)
    except TimeLimitReached:
        document["status"] = "time-limit"
    document["profiles"] = profiles
    document["elapsed_seconds"] = time.monotonic() - started
    document["id"] = hashlib.sha256(configuration_key({"profiles": profiles}).encode()).hexdigest()
    (args.output / "calibration.json").write_text(json.dumps(document, indent=2) + "\n")
    if document["status"] != "complete":
        return 1
    from hypothesis_helm.benchmarking.calibration_matrix import evaluate

    evaluate(args.output, document)
    plot(args.output, document)
    return 0
